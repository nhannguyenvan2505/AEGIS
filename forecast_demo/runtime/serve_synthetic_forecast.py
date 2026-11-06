"""Local FM-02 inference worker for pinned, synthetic replay scenarios."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
from io import BytesIO
import json
from datetime import timedelta
from pathlib import Path

from synthetic_baseline import forecast, joblib
from feature_preparation import prepare
from pipeline import digest, stamp, validate_series

PACKAGE = Path(__file__).resolve().parents[1]
BUNDLE = PACKAGE / 'bundle'
DATA = BUNDLE
MANIFEST_PIN = '549f84ac7b154aff63f31a1891f87cec21f60298d5bd8c63eeb6deb1792722fa'
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


def inference_worker():
    try:
        manifest = json.loads(checked_bytes(BUNDLE/'manifest.json', MANIFEST_PIN))
        model = joblib.load(BytesIO(checked_bytes(BUNDLE/'baseline.joblib', manifest['artifact_sha256'])))
    except (OSError, ValueError, ImportError):
        model = None

    def predict(data):
        if not isinstance(data, dict):
            return dict(status='invalid_request'), 400
        scenario = data.get('scenario')
        if scenario == 'hourly' and set(data) == {'scenario', 'season_id', 'plot_id', 'hourly'}:
            try:
                payload = hourly_input(data)
            except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
                return dict(status='invalid_hourly_history'), 400
        elif isinstance(scenario, str) and scenario in SCENARIOS and set(data) == {'scenario', 'season_id', 'plot_id'}:
            payload = json.loads(checked_bytes(DATA/f'input_{scenario}.synthetic.json', SCENARIOS[scenario]))
            payload['series'][0].update(plot_id=data['plot_id'], season_id=data['season_id'])
        else:
            return dict(status='invalid_request'), 400
        feature = prepare(payload)['rows'][0]
        if model is None and feature['feature_status'] == 'ready':
            return dict(status='model_unavailable'), 503
        row = forecast(model, payload)[0]
        row.update(schema_version='aegis-forecast-v1', scenario=scenario, disease='leaf_blast',
                   simulation_clock=True, input_sha256=digest(payload), model_manifest_sha256=MANIFEST_PIN,
                   model_version='fm02-logistic-v1', feature_window_start=feature['feature_window_start'],
                   feature_window_end=feature['feature_window_end'], threshold=.5)
        if scenario == 'hourly':
            row['input_snapshot'] = payload
        return row, 200

    return predict


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=8001, type=int)
    args = parser.parse_args()
    predict = inference_worker()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', 0))
                if self.path != '/predict':
                    result, code = {'status': 'unknown_route'}, 404
                elif not 0 < size <= 256*1024:
                    result, code = {'status': 'invalid_size'}, 400
                else:
                    result, code = predict(json.loads(self.rfile.read(size)))
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
