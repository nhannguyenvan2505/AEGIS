"""Pinned local FM-02 replay and FM-03 stored-raw synthetic inference."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
from io import BytesIO
import json
from datetime import timedelta
from pathlib import Path
from importlib.metadata import version

from synthetic_baseline import forecast, joblib
from feature_preparation import prepare
from pipeline import digest, stamp, validate_series
from weather_forecast import prepare_weather, forecast_weather, CONTRACT_SHA256, FEATURES
from forecast_explanation import explain

PACKAGE = Path(__file__).resolve().parents[1]
BUNDLE = PACKAGE / 'bundle'
DATA = BUNDLE
MANIFEST_PIN = '549f84ac7b154aff63f31a1891f87cec21f60298d5bd8c63eeb6deb1792722fa'
WEATHER_BUNDLE = PACKAGE / 'weather_bundle'
WEATHER_MANIFEST_PIN = '2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f'
SCENARIOS = {
    'ready': '926d72c66d5b79b07b5ab12b142c37f94d3dcdd4782df959277ed69e586a8e75',
    'insufficient': '792336a860e86f51fe4b5b68064d48c2cc28f520769d7c2c1daf3be8096ccb5c',
}


def checked_bytes(path, expected):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError('Artifact digest mismatch')
    return content


def hourly_input(data):
    history = data['hourly']
    required = {'source', 'issued_at', 'device_id', 'telemetry', 'context_revisions'}
    if not isinstance(history, dict) or set(history) != required or history['source'] != 'synthetic':
        raise ValueError('Expected synthetic hourly history')
    issued = stamp(history['issued_at'])
    end = issued.replace(minute=0, second=0, microsecond=0)
    series = dict(plot_id=data['plot_id'], season_id=data['season_id'], device_id=history['device_id'],
                  telemetry=history['telemetry'], context_revisions=history['context_revisions'])
    validate_series(dict(series, surveys=[], interventions=[]))
    series['telemetry'] = sorted((r for r in series['telemetry']
        if end-timedelta(hours=120) <= stamp(r['start_at']) < end and stamp(r['available_at']) <= issued),
        key=lambda r: stamp(r['start_at']))
    series['context_revisions'] = sorted((r for r in series['context_revisions']
        if stamp(r['available_at']) <= issued), key=lambda r: r['revision'])
    return dict(schema_version='aegis-hourly-feature-input-v1', source='synthetic',
                issue_times=[issued.isoformat()], series=[series])


def inference_worker(*, with_explanation=False):
    try:
        manifest = json.loads(checked_bytes(BUNDLE/'manifest.json', MANIFEST_PIN))
        model = joblib.load(BytesIO(checked_bytes(BUNDLE/'baseline.joblib', manifest['artifact_sha256'])))
    except (OSError, ValueError, ImportError):
        model = None
    try:
        weather_manifest = json.loads(checked_bytes(WEATHER_BUNDLE/'manifest.json', WEATHER_MANIFEST_PIN))
        if (weather_manifest['model_version'] != 'fm03-weather-logistic-v1'
                or weather_manifest['feature_contract_sha256'] != CONTRACT_SHA256
                or weather_manifest['feature_order'] != list(FEATURES)
                or weather_manifest['source'] != 'synthetic' or weather_manifest['field_validated'] is not False):
            raise ValueError('Weather bundle contract mismatch')
        for name, expected in weather_manifest['runtime_sources'].items():
            checked_bytes(Path(__file__).parent/name, expected)
        for name, distribution in [('sklearn', 'scikit-learn'), ('numpy', 'numpy'), ('pandas', 'pandas'), ('joblib', 'joblib')]:
            if version(distribution) != weather_manifest['runtime'][name]:
                raise ValueError('Weather runtime version mismatch')
        weather_model = joblib.load(BytesIO(checked_bytes(WEATHER_BUNDLE/weather_manifest['artifact'], weather_manifest['artifact_sha256'])))
    except (OSError, ValueError, ImportError, KeyError, TypeError, EOFError):
        weather_model = None

    def predict(data):
        if not isinstance(data, dict):
            return dict(status='invalid_request'), 400
        scenario = data.get('scenario')
        weather = data.get('model_route') == 'weather'
        hourly_keys = {'scenario', 'season_id', 'plot_id', 'hourly'} | ({'model_route'} if weather else set())
        if scenario == 'hourly' and set(data) == hourly_keys:
            try:
                payload = hourly_input(data)
            except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
                return dict(status='invalid_hourly_history'), 400
        elif isinstance(scenario, str) and scenario in SCENARIOS and set(data) == {'scenario', 'season_id', 'plot_id'}:
            payload = json.loads(checked_bytes(DATA/f'input_{scenario}.synthetic.json', SCENARIOS[scenario]))
            payload['series'][0].update(plot_id=data['plot_id'], season_id=data['season_id'])
        else:
            return dict(status='invalid_request'), 400
        feature = (prepare_weather(payload) if weather else prepare(payload))['rows'][0]
        active_model = weather_model if weather else model
        if active_model is None and feature['feature_status'] == 'ready':
            return dict(status='model_unavailable'), 503
        row = (forecast_weather(active_model, payload) if weather else forecast(active_model, payload))[0]
        row.update(schema_version='aegis-forecast-v1', scenario=scenario, disease='leaf_blast',
                   simulation_clock=True, input_sha256=digest(payload),
                   model_manifest_sha256=WEATHER_MANIFEST_PIN if weather else MANIFEST_PIN,
                   model_version='fm03-weather-logistic-v1' if weather else 'fm02-logistic-v1', feature_window_start=feature['feature_window_start'],
                   feature_window_end=feature['feature_window_end'], threshold=.5)
        if weather:
            row['model_route'] = 'weather'
        if scenario == 'hourly':
            row['input_snapshot'] = payload
        return row, 200

    def explanation(data):
        if not isinstance(data, dict) or set(data) != {'model_manifest_sha256', 'input_snapshot'}:
            return dict(status='invalid_request'), 400
        pin = data['model_manifest_sha256']
        if pin not in (MANIFEST_PIN, WEATHER_MANIFEST_PIN):
            return dict(status='unsupported_model'), 409
        weather = pin == WEATHER_MANIFEST_PIN
        try:
            result = explain(weather_model if weather else model, data['input_snapshot'], pin,
                             'fm03-weather-logistic-v1' if weather else 'fm02-logistic-v1', weather)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            return dict(status='invalid_explanation_input'), 400
        return result, 503 if result['status'] == 'model_unavailable' else 200

    return (predict, explanation) if with_explanation else predict


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=8001, type=int)
    args = parser.parse_args()
    predict, explanation = inference_worker(with_explanation=True)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', 0))
                if self.path not in ('/predict', '/explain'):
                    result, code = {'status': 'unknown_route'}, 404
                elif not 0 < size <= 256*1024:
                    result, code = {'status': 'invalid_size'}, 400
                else:
                    operation = explanation if self.path == '/explain' else predict
                    result, code = operation(json.loads(self.rfile.read(size)))
            except (TypeError, ValueError, OSError):
                result, code = {'status': 'invalid_request_or_fixture'}, 400
            body = json.dumps(result, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(server.server_port, flush=True)
        server.serve_forever()
