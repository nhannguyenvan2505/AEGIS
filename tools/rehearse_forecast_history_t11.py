"""T11 live loopback HTTP evidence in an isolated synthetic test fixture."""
import argparse
from contextlib import ExitStack
from datetime import timedelta
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'frontend')]
import requests
from werkzeug.serving import make_server
from test_weather_integration import WeatherIntegrationTests
from telemetry_audit import stamp


def write(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, allow_nan=False)
        file.write('\n')


def rehearse(out):
    out.mkdir(parents=True, exist_ok=False)
    with ExitStack() as cleanup:
        cleanup.callback(WeatherIntegrationTests.doClassCleanups)
        WeatherIntegrationTests.setUpClass()
        case = WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        case.port = WeatherIntegrationTests.port
        cleanup.callback(case.doCleanups)
        case.setUp()
        command = case.ready_source()
        with make_server('127.0.0.1', 0, case.app, threaded=True) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    base = 'http://127.0.0.1:'+str(server.server_port)
                    def call(method, path, body=None):
                        response = session.request(method, base+path, json=body, headers=case.headers, timeout=20)
                        response.raise_for_status()
                        return response.json()
                    forecasts = []
                    for seconds in (0, 30, 3600):
                        body = dict(command, issued_at=(stamp(command['issued_at'])+timedelta(seconds=seconds)).isoformat())
                        forecasts.append(call('POST', case.url, body)['item'])
                    call('POST', case.url, dict(scenario='ready'))  # independently grouped FM02 fixture
                    explanation = call('GET', '/api/farm/forecasts/'+forecasts[0]['id']+'/explanation')['item']
                    trend = call('GET', '/api/farm/seasons/'+case.fixture.season['id']+'/forecast-trend')
                    original = call('GET', '/api/farm/forecasts/'+forecasts[0]['id'])['item']
                    if original != forecasts[0] or abs(explanation['score']-original['score']) > 1e-12:
                        raise ValueError('Stored prediction or explanation changed')
                    if forecasts[-1]['status'] != 'insufficient_data' or len(trend['series']) != 2:
                        raise ValueError('Trend did not preserve gap/model grouping')
                    write(out/'forecast.synthetic.json', original)
                    write(out/'explanation.synthetic.json', explanation)
                    write(out/'trend.synthetic.json', trend)
                    write(out/'verification.json', dict(success=True, source='synthetic', field_validated=False,
                        transport='Real Flask HTTP and model-worker HTTP over loopback',
                        source_clock='Fixed synthetic fixture; actual process/HTTP transport',
                        model_version=original['model_version'], model_pin=original['model_manifest_sha256'],
                        input_sha256=original['input_sha256'], score=original['score'],
                        terms=len(explanation['terms']), reconstruction_error=explanation['reconstruction_error'],
                        forecast_unchanged=True, ready_and_insufficient_exercised=True, separate_model_series=2))
            finally:
                server.shutdown()
                thread.join(10)
    return dict(success=True, temporary_store_and_workers_cleaned=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.out)))
