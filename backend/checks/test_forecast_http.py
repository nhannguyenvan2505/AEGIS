"""Run with the Backend interpreter and FM02_PYTHON pointing to the FM-02 interpreter."""
import os
import json
import copy
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from uuid import uuid4

import requests
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from pilot_app import create_pilot_app


class ForecastHTTP(unittest.TestCase):
    def test_local_worker_and_persistent_owner_history(self):
        temp = tempfile.TemporaryDirectory(prefix='aegis_ui_forecast_')
        self.addCleanup(temp.cleanup)
        store = Path(temp.name)
        worker = subprocess.Popen([os.environ['FM02_PYTHON'], '-B',
            str(ROOT/'forecast_demo/runtime/serve_synthetic_forecast.py'), '--port', '0'],
            stdout=subprocess.PIPE, text=True)
        self.addCleanup(worker.stdout.close)
        self.addCleanup(worker.wait, 10)
        self.addCleanup(worker.terminate)
        port = int(worker.stdout.readline())
        app = create_pilot_app(store)
        app.config['FORECAST_WORKER_PORT'] = port
        server = make_server('127.0.0.1', 0, app)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        client = requests.Session()
        client.trust_env = False
        self.addCleanup(client.close)

        def api(method, path, status, token=None, body=None):
            with client.request(method, f'http://127.0.0.1:{server.server_port}/api'+path,
                    headers={'Authorization': 'Bearer '+token} if token else {}, json=body, timeout=15) as r:
                self.assertEqual(r.status_code, status)
                return r.json()

        tokens = []
        for i in range(2):
            cred = dict(email=f'fm03-{i}@example.test', password=str(uuid4()))
            api('POST', '/auth/register', 201, body=cred)
            tokens.append(api('POST', '/auth/login', 200, body=cred)['access_token'])
        owner, other = tokens
        plot = api('POST', '/farm/plots', 201, owner, {'name':'Synthetic demo'})['item']
        season = api('POST', '/farm/plots/'+plot['id']+'/seasons', 201, owner,
                     {'name':'Demo', 'start_date':'2026-01-01'})['item']
        url = '/farm/seasons/'+season['id']+'/forecasts'
        api('GET', url, 401)
        api('GET', '/farm/forecast-overview', 401)
        self.assertEqual(api('GET', '/farm/forecast-overview', 200, other)['items'], [])
        overview = api('GET', '/farm/forecast-overview', 200, owner)['items'][0]
        self.assertEqual(overview['season_id'], season['id'])
        self.assertIsNone(overview['source_revision'])
        self.assertIsNone(overview['latest_forecast'])
        api('GET', '/farm/forecast-overview?page_size=0', 400, owner)
        api('POST', url, 404, other, {'scenario':'ready'})
        api('POST', url, 400, owner, {'scenario':'invalid'})
        item = api('POST', url, 201, owner, {'scenario':'ready'})['item']
        self.assertEqual(item['status'], 'forecast_ready')
        self.assertEqual(item, api('POST', url, 200, owner, {'scenario':'ready'})['item'])
        missing = api('POST', url, 201, owner, {'scenario':'insufficient'})['item']
        self.assertIsNone(missing['score'])
        self.assertTrue(missing['reasons'])
        detail = '/farm/forecasts/'+item['id']
        api('GET', detail, 404, other)
        api('GET', url, 404, other)
        self.assertEqual(api('GET', detail, 200, owner)['item'], item)
        # Arbitrary hourly input exercises the model beyond the two replay fixtures.
        fixture = json.loads((ROOT/'forecast_demo/bundle/input_ready.synthetic.json').read_text(encoding='utf-8'))
        series = fixture['series'][0]
        hourly = dict(source='synthetic', issued_at=fixture['issue_times'][0],
                      device_id=series['device_id'], telemetry=series['telemetry'],
                      context_revisions=series['context_revisions'])
        submitted = dict(scenario='hourly', hourly=hourly)
        api('POST', url, 404, other, submitted)
        actual = api('POST', url, 201, owner, submitted)['item']
        self.assertEqual(actual['score'], item['score'])
        self.assertEqual(actual, api('POST', url, 200, owner, submitted)['item'])
        evidence_url = '/farm/forecasts/'+actual['id']+'/input'
        snapshot = api('GET', evidence_url, 200, owner)['item']
        self.assertEqual(snapshot['series'][0]['plot_id'], plot['id'])
        api('GET', evidence_url, 404, other)
        future = copy.deepcopy(submitted)
        issued = datetime.fromisoformat(hourly['issued_at'])
        future['hourly']['telemetry'].append(dict(start_at=issued.isoformat(),
            available_at=(issued+timedelta(hours=1)).isoformat(), air_temperature_c=50,
            relative_humidity_pct=100, leaf_wet=True, quality='valid'))
        self.assertEqual(api('POST', url, 200, owner, future)['item'], actual)
        changed = copy.deepcopy(submitted)
        for reading in changed['hourly']['telemetry']:
            reading.update(air_temperature_c=24, relative_humidity_pct=65, leaf_wet=False)
        different = api('POST', url, 201, owner, changed)['item']
        self.assertNotEqual(different['score'], actual['score'])
        incomplete = copy.deepcopy(submitted)
        incomplete['hourly']['telemetry'].pop()
        absent = api('POST', url, 201, owner, incomplete)['item']
        self.assertEqual(absent['status'], 'insufficient_data')
        self.assertIsNone(absent['score'])
        late = copy.deepcopy(submitted)
        late['hourly']['telemetry'][-1]['available_at'] = (issued+timedelta(hours=1)).isoformat()
        self.assertEqual(api('POST', url, 200, owner, late)['item'], absent)
        for amendment in ({'source':'field_observed'}, {'y':1}, {'plot_id':plot['id']}):
            invalid = copy.deepcopy(submitted)
            invalid['hourly'].update(amendment)
            api('POST', url, 400, owner, invalid)
        invalid = copy.deepcopy(submitted)
        invalid['hourly']['telemetry'].append(copy.deepcopy(invalid['hourly']['telemetry'][0]))
        api('POST', url, 400, owner, invalid)
        source_url = '/farm/seasons/'+season['id']+'/forecast-source'
        api('GET', source_url, 404, other)
        self.assertIsNone(api('GET', source_url, 200, owner)['item'])
        api('POST', url, 409, owner, {'scenario':'source'})
        update = dict(base_revision=0, hourly=hourly)
        self.assertEqual(api('POST', source_url, 201, owner, update)['revision'], 1)
        self.assertTrue(api('POST', source_url, 200, owner, update)['replayed'])
        managed = api('POST', url, 201, owner, {'scenario':'source'})['item']
        self.assertEqual(managed['source_revision'], 1)
        self.assertEqual(managed['score'], actual['score'])
        self.assertEqual(managed, api('POST', url, 200, owner, {'scenario':'source'})['item'])
        next_hour = copy.deepcopy(hourly)
        next_hour['issued_at'] = (issued+timedelta(hours=1)).isoformat()
        next_hour['telemetry'].pop(0)
        next_hour['telemetry'].append(dict(start_at=issued.isoformat(),
            available_at=next_hour['issued_at'], air_temperature_c=24,
            relative_humidity_pct=65, leaf_wet=False, quality='valid'))
        api('POST', source_url, 409, owner, dict(base_revision=0, hourly=next_hour))
        bad_device = copy.deepcopy(next_hour)
        bad_device['device_id'] = 'different-device'
        api('POST', source_url, 409, owner, dict(base_revision=1, hourly=bad_device))
        self.assertEqual(api('POST', source_url, 201, owner,
                             dict(base_revision=1, hourly=next_hour))['revision'], 2)
        rolling = api('POST', url, 201, owner, {'scenario':'source'})['item']
        self.assertNotEqual(rolling['id'], managed['id'])
        self.assertNotEqual(rolling['issued_at'], managed['issued_at'])
        self.assertEqual(rolling['source_revision'], 2)
        self.assertEqual(api('GET', '/farm/forecasts/'+managed['id'], 200, owner)['item'], managed)
        lacking = copy.deepcopy(next_hour)
        lacking['issued_at'] = (issued+timedelta(hours=2)).isoformat()
        api('POST', source_url, 201, owner, dict(base_revision=2, hourly=lacking))
        unready = api('POST', url, 201, owner, {'scenario':'source'})['item']
        self.assertEqual(unready['status'], 'insufficient_data')
        self.assertIsNone(unready['score'])
        overview = api('GET', '/farm/forecast-overview', 200, owner)['items'][0]
        self.assertEqual(overview['plot_name'], plot['name'])
        self.assertEqual(overview['source_revision'], 3)
        self.assertEqual(overview['latest_forecast'], unready)
        def mobile_check(offline):
            if os.environ.get('FM04_CHECK_MOBILE') == '1':
                subprocess.run(['node', 'scripts/forecast-http.mjs'], cwd=ROOT/'mobile',
                    env=dict(os.environ, EXPO_PUBLIC_API_URL=f'http://127.0.0.1:{server.server_port}/api'),
                    input=json.dumps(dict(season=season['id'], owner=owner, other=other, offline=offline, expectedTotal=8)),
                    text=True, timeout=30, check=True)
        mobile_check(False)
        worker.terminate()
        worker.wait(10)
        mobile_check(True)
        api('POST', url, 503, owner, {'scenario':'ready'})
        self.assertEqual(api('GET', url+'?page_size=1', 200, owner)['pagination']['total'], 8)
        reopened = create_pilot_app(store).test_client()
        self.assertEqual(reopened.get('/api'+detail, headers={'Authorization':'Bearer '+owner}).json['item'], item)
        self.assertEqual(reopened.get('/api'+source_url, headers={'Authorization':'Bearer '+owner}).json['item']['revision'], 3)


if __name__ == '__main__':
    unittest.main()
