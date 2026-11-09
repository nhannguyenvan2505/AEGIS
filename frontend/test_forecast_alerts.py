"""T12 in-app alert policy, real-worker forecast integration and durable recovery."""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_weather_integration as integration
from test_hourly_features import cohort
from forecast_alerts import VERSION, POLICY_HASH
from forecast_scheduler import ForecastRunner
from pilot_app import create_pilot_app
from pilot_backup import backup, verify, audit_data
from pilot_journal import journal_db
from pilot_store import MARKER, KIND
from telemetry_audit import stamp


def positive_cohort():
    """Synthetic software positive control; no observed disease label."""
    bundle, policy, request, context = cohort()
    for index, row in enumerate(bundle['readings']):
        hour = index//6
        row['payload'].update(air_temperature_c=27+1.5*math.sin(hour*2*math.pi/24),
                              relative_humidity_pct=92+3*math.cos(hour*2*math.pi/24))
    return bundle, policy, request, context


class ForecastAlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.WeatherIntegrationTests.setUpClass.__func__(cls)

    def setUp(self):
        self.case = integration.WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        self.case.port = self.port
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture, self.client, self.headers = self.case.fixture, self.case.client, self.case.headers
        self.clock = patch('forecast_alerts.now', side_effect=lambda: self.fixture.time)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.command = self.case.base.command.copy()

    def post(self, command=None, status=201):
        command = command or dict(self.command, issued_at=self.fixture.time.isoformat())
        response = self.client.post(self.case.url, json=command, headers=self.headers)
        self.assertEqual(response.status_code,status,response.json)
        return response.json['item']

    def evaluation(self, row, method='GET'):
        response = self.client.open('/api/farm/forecasts/'+row['id']+'/alert-evaluation',method=method,
                                    json={} if method=='POST' else None,headers=self.headers)
        self.assertIn(response.status_code,(200,201),response.json)
        return response.json

    def alerts(self, **query):
        response = self.client.get('/api/farm/forecast-alerts',query_string=query,headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        return response.json['items']

    def positive(self):
        with patch('test_weather_integration.cohort',side_effect=positive_cohort):
            self.command = self.case.ready_source()
        row = self.post(self.command)
        self.assertGreaterEqual(row['score'],.5)
        return row

    def test_insufficient_creates_data_quality_only_and_replays_once(self):
        row = self.post()
        self.assertEqual(row['status'],'insufficient_data')
        alert = self.alerts()[0]
        self.assertEqual(alert['kind'],'data_quality')
        self.assertIsNone(alert['score'])
        self.assertFalse(alert['disease_confirmed'])
        self.assertFalse(alert['field_validated'])
        self.assertEqual(alert['reasons'],row['reasons'])
        self.assertEqual(alert['policy_sha256'],POLICY_HASH)
        self.assertEqual(self.evaluation(row)['item']['outcome'],'created')
        self.assertEqual(self.post(status=200),row)
        self.assertTrue(self.evaluation(row,'POST')['replayed'])
        self.assertEqual(len(self.alerts()),1)

    def test_positive_score_and_below_threshold_are_distinct(self):
        row = self.positive()
        alert = self.alerts()[0]
        self.assertEqual(alert['kind'],'score_threshold')
        self.assertEqual(alert['forecast_id'],row['id'])
        self.assertEqual(alert['score'],row['score'])
        self.assertEqual(alert['model_manifest_sha256'],row['model_manifest_sha256'])

    def test_below_threshold_does_not_create_low_risk_alert(self):
        self.command = self.case.ready_source()
        row = self.post()
        self.assertLess(row['score'],.5)
        self.assertEqual(self.evaluation(row)['item']['outcome'],'below_threshold')
        self.assertEqual(self.alerts(),[])

    def test_cooldown_boundary_ack_does_not_rearm_and_payload_immutable(self):
        first = self.post()
        original = self.alerts()[0]
        self.fixture.time += timedelta(seconds=60)
        second = self.post()
        result = self.evaluation(second)['item']
        self.assertEqual(result['outcome'],'suppressed_cooldown')
        self.assertEqual(result['alert_id'],original['id'])
        url = '/api/farm/forecast-alerts/'+original['id']+'/acknowledgements'
        self.assertEqual(self.client.post(url,json=dict(base_version=1),headers=self.headers).status_code,201)
        replay = self.client.post(url,json=dict(base_version=1),headers=self.headers)
        self.assertEqual(replay.status_code,200)
        self.assertTrue(replay.json['replayed'])
        self.assertEqual(replay.json['item']['forecast_id'],first['id'])
        self.fixture.time += timedelta(seconds=60)
        self.assertEqual(self.evaluation(self.post())['item']['outcome'],'suppressed_cooldown')
        self.fixture.time = stamp(first['issued_at'])+timedelta(hours=6)
        boundary = self.post()
        self.assertEqual(self.evaluation(boundary)['item']['outcome'],'created')
        self.assertEqual(len(self.alerts()),2)
        old = self.client.get('/api/farm/forecast-alerts/'+original['id'],headers=self.headers).json['item']
        for key in ('forecast_id','score','reasons','issued_at','hourly_source'):
            self.assertEqual(old[key],original[key])
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM forecast_alert_actions').fetchone()[0],1)

    def test_score_and_data_quality_have_independent_cooldowns(self):
        self.fixture.time = stamp('2026-11-06T00:01:00Z')
        self.post()
        self.positive()
        self.assertEqual({a['kind'] for a in self.alerts()},{'score_threshold','data_quality'})

    def test_same_issue_new_source_and_out_of_order_are_suppressed(self):
        first = self.post()
        new_source = self.fixture.post(self.fixture.source_url,dict(self.fixture.command,base_revision=1,
            as_of=(stamp(self.fixture.command['as_of'])+timedelta(seconds=1)).isoformat()))
        self.assertEqual(new_source.status_code,201,new_source.json)
        same = self.post(dict(self.command,hourly_source_id=new_source.json['item']['id']))
        self.assertNotEqual(first['id'],same['id'])
        self.assertEqual(self.evaluation(same)['item']['outcome'],'same_issue_already_evaluated')
        self.fixture.time += timedelta(seconds=120)
        self.post()
        older = self.post(dict(self.command,issued_at=(self.fixture.time-timedelta(seconds=60)).isoformat()))
        self.assertEqual(self.evaluation(older)['item']['outcome'],'out_of_order')
        self.assertEqual(len(self.alerts()),1)

    def test_expired_stale_future_skip_without_advancing_watermark(self):
        base = self.fixture.time
        for delta,clock,outcome in [(0,base+timedelta(hours=2),'stale_forecast'),
                                    (1,base+timedelta(hours=73),'expired_forecast'),
                                    (100,base,'future_issue')]:
            self.fixture.time = clock
            row = self.post(dict(self.command,issued_at=(base+timedelta(seconds=delta)).isoformat()))
            item = self.evaluation(row)['item']
            self.assertEqual(item['outcome'],outcome)
            self.assertFalse(item['watermark_advanced'])
        self.assertEqual(self.alerts(),[])
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM forecast_alert_states').fetchone()[0],0)

    def test_historical_backfill_explicit_get_readonly_and_fixture_ineligible(self):
        with patch('forecast_alerts.evaluate',return_value=({},False)):
            historical = self.post()
        self.assertEqual(self.evaluation(historical)['item']['outcome'],'not_evaluated')
        self.assertEqual(self.alerts(),[])
        self.assertFalse(self.evaluation(historical,'POST')['replayed'])
        self.assertEqual(len(self.alerts()),1)
        fixture = self.post(dict(scenario='ready'))
        self.assertEqual(self.evaluation(fixture)['item']['outcome'],'not_eligible')
        self.assertEqual(self.evaluation(fixture,'POST')['item']['outcome'],'not_eligible')
        self.assertEqual(len(self.alerts()),1)

    def test_maximum_age_boundary_is_exact(self):
        base=self.fixture.time
        self.fixture.time=base+timedelta(hours=1)
        first=self.post(dict(self.command,issued_at=base.isoformat()))
        self.assertEqual(self.evaluation(first)['item']['outcome'],'created')
        self.fixture.time += timedelta(microseconds=2)
        older=self.post(dict(self.command,issued_at=(base+timedelta(microseconds=1)).isoformat()))
        self.assertEqual(self.evaluation(older)['item']['outcome'],'stale_forecast')
        self.assertEqual(len(self.alerts()),1)

    def test_owner_auth_query_ack_versions_filters_and_window(self):
        row = self.post(); alert = self.alerts()[0]
        url = '/api/farm/forecast-alerts/'+alert['id']
        for route in (url,'/api/farm/forecasts/'+row['id']+'/alert-evaluation'):
            self.assertEqual(self.client.get(route).status_code,401)
            self.assertEqual(self.client.get(route,headers=self.fixture.headers[1]).status_code,404)
        self.assertEqual(self.client.get('/api/farm/forecast-alerts',headers=self.fixture.headers[1]).json['items'],[])
        self.assertEqual(self.client.get('/api/farm/forecast-alerts',query_string=dict(season_id=row['season_id']),headers=self.fixture.headers[1]).status_code,404)
        for query in ('?x=1','?state=closed','?kind=low_risk','?window=x','?season_id=bad','?page_size=101','?state=unread&state=unread'):
            self.assertEqual(self.client.get('/api/farm/forecast-alerts'+query,headers=self.headers).status_code,400)
        self.assertEqual(len(self.alerts(state='unread',kind='data_quality',season_id=row['season_id'],window='active')),1)
        ack=url+'/acknowledgements'
        for base in (0,True,'1'):
            self.assertEqual(self.client.post(ack,json=dict(base_version=base),headers=self.headers).status_code,400)
        self.assertEqual(self.client.post(ack,json=dict(base_version=2),headers=self.headers).status_code,409)
        self.assertEqual(self.client.post(ack,json=dict(base_version=1,threshold=.1),headers=self.headers).status_code,400)
        self.assertEqual(self.client.post(ack,json=dict(base_version=1),headers=self.fixture.headers[1]).status_code,404)
        response=self.client.get(url,headers=self.headers)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertIn('Authorization',response.headers['Vary'])
        self.fixture.time += timedelta(hours=73)
        self.assertEqual(self.alerts(window='active'),[])
        self.assertEqual(len(self.alerts(window='expired')),1)
        self.assertFalse(self.alerts()[0]['forecast_window_active'])

    def test_reopen_offline_and_backup_preserve_alert_and_ack(self):
        self.post(); alert=self.alerts()[0]
        ack='/api/farm/forecast-alerts/'+alert['id']+'/acknowledgements'
        self.assertEqual(self.client.post(ack,json=dict(base_version=1),headers=self.headers).status_code,201)
        reopened=create_pilot_app(self.fixture.root)
        reopened.config['FORECAST_WORKER_PORT']=1
        response=reopened.test_client().get('/api/farm/forecast-alerts/'+alert['id'],headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['item']['state'],'acknowledged')
        (self.fixture.root/MARKER).write_text(json.dumps(dict(kind=KIND)),encoding='utf-8')
        audit_data(self.fixture.root)
        with tempfile.TemporaryDirectory(prefix='aegis_t12_backup_') as directory:
            backup(self.fixture.root,Path(directory)/'backup')
            verify(Path(directory)/'backup')

    def test_policy_corruption_rolls_back_forecast_transaction(self):
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE forecast_alert_policies SET payload_sha256='bad'")
        response=self.client.post(self.case.url,json=self.command,headers=self.headers)
        self.assertEqual(response.status_code,500,response.json)
        self.assertEqual(response.json['error']['code'],'forecast_alert_policy_error')
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            for table in ('synthetic_forecasts','synthetic_forecast_inputs','forecast_alerts','forecast_alert_evaluations'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)

    def test_alert_payload_corruption_rejected(self):
        self.post(); alert=self.alerts()[0]
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE forecast_alerts SET payload_json='{}' WHERE id=?",(alert['id'],))
        self.assertEqual(self.client.get('/api/farm/forecast-alerts/'+alert['id'],headers=self.headers).status_code,500)

    def test_failure_after_alert_insert_rolls_back_all_forecast_artifacts(self):
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("""CREATE TRIGGER simulated_t12_failure BEFORE INSERT ON forecast_alert_evaluations
                BEGIN SELECT RAISE(ABORT,'simulated test failure'); END""")
        response=self.client.post(self.case.url,json=self.command,headers=self.headers)
        self.assertEqual(response.status_code,500)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            for table in ('synthetic_forecasts','synthetic_forecast_inputs','synthetic_forecast_hourly_sources',
                          'forecast_alerts','forecast_alert_states','forecast_alert_evaluations'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)

    def test_concurrent_replay_and_ack_create_one_each(self):
        def send(_):
            with self.case.app.test_client() as client:
                result=client.post(self.case.url,json=self.command,headers=self.headers)
                return result.status_code,result.json
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(send,range(2)))
        self.assertEqual(sorted(r[0] for r in results),[200,201])
        alert=self.alerts()[0]
        def ack(_):
            with self.case.app.test_client() as client:
                result=client.post('/api/farm/forecast-alerts/'+alert['id']+'/acknowledgements',json=dict(base_version=1),headers=self.headers)
                return result.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(ack,range(2))),[200,201])
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            for table in ('forecast_alerts','forecast_alert_evaluations','forecast_alert_actions'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)

    def test_scheduler_actual_process_crash_recovers_without_duplicate_alert(self):
        with patch('forecast_scheduler.now',side_effect=lambda:self.fixture.time):
            job=self.client.post('/api/farm/environment-streams/'+self.fixture.stream+'/forecast-jobs',
                json=dict(client_job_id=str(uuid4()),name='T12 recovery',interval_seconds=60,enabled=True),headers=self.headers)
            self.assertEqual(job.status_code,201,job.json)
            script='''
import os,sys
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'backend'),str(Path.cwd()/'frontend')]
from pilot_app import create_pilot_app
from forecast_scheduler import ForecastRunner
import forecast_alerts
from telemetry_audit import stamp
at=stamp(sys.argv[3]);forecast_alerts.now=lambda:at
app=create_pilot_app(Path(sys.argv[1]));app.config['FORECAST_WORKER_PORT']=int(sys.argv[2])
runner=ForecastRunner(app,Path(sys.argv[1]))
def crash(stage):
 if stage=='after_forecast':os._exit(73)
runner.checkpoint=crash;runner.tick(at)
'''
            root=Path(__file__).resolve().parents[1]
            process=subprocess.run([sys.executable,'-B','-c',script,str(self.fixture.root),str(self.port),self.fixture.time.isoformat()],
                                   cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(process.returncode,73,process.stderr)
            self.assertEqual(len(self.alerts()),1)
            self.case.app.config['FORECAST_WORKER_PORT']=1
            self.fixture.time += timedelta(seconds=1)
            result=ForecastRunner(self.case.app,self.fixture.root).tick()
            self.assertEqual(result['runs'][0]['status'],'succeeded')
            self.assertEqual(len(self.alerts()),1)
            with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM forecast_alert_evaluations').fetchone()[0],1)


if __name__=='__main__': unittest.main()
