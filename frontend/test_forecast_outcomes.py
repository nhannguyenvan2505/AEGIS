"""T13 pinned journal/workflow references, as-of tracking and no inferred labels."""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_weather_integration as integration
from pilot_backup import audit_data, backup, verify
from pilot_app import create_pilot_app
from pilot_journal import journal_db
from pilot_store import MARKER, KIND
from telemetry_audit import stamp
import forecast_outcomes


class ForecastOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.WeatherIntegrationTests.setUpClass.__func__(cls)

    def setUp(self):
        self.case=integration.WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        self.case.port=self.port
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture,self.client,self.headers=self.case.fixture,self.case.client,self.case.headers
        command=self.case.ready_source()
        response=self.client.post(self.case.url,json=command,headers=self.headers)
        self.assertEqual(response.status_code,201,response.json)
        self.forecast=response.json['item']
        self.issue=stamp(self.forecast['issued_at']);self.end=stamp(self.forecast['target_window_end'])
        self.at=stamp(self.forecast['created_at'])+timedelta(seconds=1)
        for target in ('forecast_outcomes.now','pilot_journal.now','pilot_followup.now'):
            clock=patch(target,side_effect=lambda:self.at);clock.start();self.addCleanup(clock.stop)
        self.url='/api/farm/forecasts/'+self.forecast['id']

    def observation(self,hours=1,finding='uncertain',reviewed=False,source='synthetic',season=None,headers=None,recorded=None):
        observed=self.issue+timedelta(hours=hours)
        self.at=max(self.at,observed)
        data=dict(client_visit_id=str(uuid4()),source=source,observed_at=observed.isoformat(),scheduled=True,
            finding=finding,notes='Ghi nhận synthetic – chưa xác minh bởi nền tảng',analysis_id=None,record_status='active',change_reason='Synthetic evidence',
            review=dict(reviewer_alias='Synthetic declared reviewer',reviewed_at=observed.isoformat(),reference='SYNTHETIC-NOT-PLATFORM-VERIFICATION') if reviewed else None)
        clock=patch('pilot_journal.now',return_value=recorded) if recorded else patch('pilot_journal.now',side_effect=lambda:self.at)
        with clock:
            response=self.client.post('/api/farm/seasons/'+(season or self.fixture.season['id'])+'/observations',json=data,headers=headers or self.headers)
        self.assertEqual(response.status_code,201,response.json)
        return response.json['item']

    def edit(self,observation,**changes):
        self.at+=timedelta(seconds=1)
        data={k:observation['payload'][k] for k in ('finding','notes','analysis_id','review','record_status')}
        data.update(base_revision=observation['revision'],change_reason='Synthetic revision',**changes)
        response=self.client.put('/api/farm/observations/'+observation['id'],json=data,headers=self.headers)
        self.assertEqual(response.status_code,201,response.json)
        return response.json['item']

    def command(self,ref,kind='observation'):
        return dict(client_link_id=str(uuid4()),kind=kind,reference_id=ref['id'],
                    reference_revision=ref.get('revision',ref.get('version')),reason='Explicit synthetic follow-up reference')

    def link(self,ref,kind='observation',command=None,status=201):
        response=self.client.post(self.url+'/outcome-links',json=command or self.command(ref,kind),headers=self.headers)
        self.assertEqual(response.status_code,status,response.json)
        return response.json['item']

    def outcome(self,query=None):
        response=self.client.get(self.url+'/outcome',query_string=query,headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertIsNone(response.json['item']['event_y'])
        self.assertFalse(response.json['item']['platform_verified'])
        self.assertFalse(response.json['item']['label_approved_for_training'])
        return response.json['item']

    def links(self,query=None):
        response=self.client.get(self.url+'/outcome-links',query_string=query,headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        return response.json['items']

    def test_empty_followup_uncertain_and_elapsed_is_censored_not_negative(self):
        self.assertEqual(self.outcome()['status'],'following_up')
        observation=self.observation()
        self.link(observation)
        self.assertEqual(self.outcome()['status'],'uncertain')
        self.at=self.end+timedelta(hours=1)
        result=self.outcome()
        self.assertEqual(result['status'],'censored')
        self.assertEqual(result['evidence_status'],'uncertain')
        self.assertEqual(result['tracking_status'],'window_elapsed')

    def test_single_reviewed_absence_at_horizon_does_not_create_negative_label(self):
        observation=self.observation(hours=72,finding='absent',reviewed=True)
        self.link(observation)
        result=self.outcome()
        self.assertEqual(result['evidence_status'],'reported_absent_at_visits')
        self.assertEqual(result['status'],'censored')
        self.assertEqual(result['within_window_observations'],1)

    def test_unverified_report_then_reviewed_revision_preserves_old_snapshot(self):
        observation=self.observation(finding='present')
        first=self.link(observation)
        captured=first['snapshot']
        before=self.at
        self.assertEqual(self.outcome()['status'],'unverified_report')
        revision=self.edit(observation,review=dict(reviewer_alias='Synthetic alias',reviewed_at=observation['observed_at'],reference='SYNTHETIC-DECLARATION'))
        old=self.links()[0]
        self.assertEqual(old['snapshot'],captured)
        self.assertEqual(old['reference_status'],'stale_revision')
        self.assertEqual(self.outcome()['usable_observations'],0)
        self.assertEqual(self.outcome({'as_of':before.isoformat()})['status'],'unverified_report')
        self.link(revision)
        current=self.outcome()
        self.assertEqual(current['status'],'review_reported_present')
        self.assertEqual(current['usable_observations'],1)
        self.assertEqual(current['unusable_active_links'],1)

    def test_baseline_retrospective_and_visit_interval_not_exact_onset(self):
        baseline=self.observation(hours=-1,finding='absent',reviewed=True)
        self.link(baseline)
        after=self.observation(hours=5,finding='present',reviewed=True)
        self.link(after)
        result=self.outcome()
        self.assertEqual(result['baseline_known_at_issue'],0)
        self.assertEqual(result['baseline_reported_later'],1)
        self.assertEqual(result['reported_visit_interval']['lower_open'],baseline['observed_at'])
        self.assertEqual(result['reported_visit_interval']['upper_closed'],after['observed_at'])
        self.assertTrue(result['reported_visit_interval']['crosses_issue_time'])
        self.assertEqual(result['status'],'review_reported_present')

    def test_baseline_present_blocks_new_event_interpretation_and_known_time(self):
        baseline=self.observation(hours=-2,finding='present',recorded=self.issue-timedelta(hours=1))
        link=self.link(baseline)
        self.assertTrue(link['snapshot']['known_at_issue'])
        result=self.outcome()
        self.assertEqual(result['status'],'baseline_reported_present')
        self.assertEqual(result['baseline_known_at_issue'],1)

    def test_after_window_presence_does_not_become_within_window_event(self):
        self.link(self.observation(hours=71,finding='absent',reviewed=True))
        self.link(self.observation(hours=73,finding='present',reviewed=True))
        result=self.outcome()
        self.assertEqual(result['status'],'censored')
        self.assertEqual(result['after_window_observations'],1)
        self.assertTrue(result['reported_visit_interval']['crosses_target_end'])

    def test_link_idempotency_conflict_and_no_duplicate_evidence(self):
        observation=self.observation()
        command=self.command(observation)
        first=self.link(observation,command=command)
        replay=self.link(observation,command=command,status=200)
        self.assertEqual(replay['id'],first['id'])
        self.assertEqual(replay['snapshot_sha256'],first['snapshot_sha256'])
        response=self.client.post(self.url+'/outcome-links',json=dict(command,reason='Different reason'),headers=self.headers)
        self.assertEqual(response.status_code,409)
        duplicate=self.client.post(self.url+'/outcome-links',json=self.command(observation),headers=self.headers)
        self.assertEqual(duplicate.status_code,409)
        self.assertEqual(self.outcome()['usable_observations'],1)

    def test_void_and_stale_revision_rejected_for_new_link(self):
        observation=self.observation(finding='present',reviewed=True)
        linked=self.link(observation)
        current=self.edit(observation,record_status='voided')
        response=self.client.post(self.url+'/outcome-links',json=self.command(current),headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json['error']['code'],'outcome_reference_voided')
        response=self.client.post(self.url+'/outcome-links',json=self.command(observation),headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.links()[0]['reference_status'],'voided')
        self.assertEqual(self.outcome()['usable_observations'],0)
        self.assertEqual(self.links()[0]['snapshot'],linked['snapshot'])

    def test_retraction_history_asof_replay_and_reattach(self):
        observation=self.observation(finding='present',reviewed=True)
        linked=self.link(observation)
        linked_at=self.at
        self.at+=timedelta(seconds=1)
        url='/api/farm/forecast-outcome-links/'+linked['id']+'/retractions'
        command=dict(base_version=1,reason='Wrong association')
        self.assertEqual(self.client.post(url,json=command,headers=self.headers).status_code,201)
        replay=self.client.post(url,json=command,headers=self.headers)
        self.assertEqual(replay.status_code,200)
        self.assertTrue(replay.json['replayed'])
        self.assertEqual(self.client.post(url,json=dict(command,reason='Different'),headers=self.headers).status_code,409)
        self.assertEqual(self.links()[0]['state'],'retracted')
        self.assertEqual(self.links({'as_of':linked_at.isoformat()})[0]['state'],'active')
        self.assertEqual(self.outcome()['usable_observations'],0)
        self.assertEqual(self.outcome({'as_of':linked_at.isoformat()})['status'],'review_reported_present')
        self.link(observation)
        self.assertEqual(self.outcome()['usable_observations'],1)
        self.assertEqual(self.outcome()['linked_references'],2)

    def test_cross_owner_season_source_auth_and_query_boundaries(self):
        observation=self.observation(source='field_observed')
        response=self.client.post(self.url+'/outcome-links',json=self.command(observation),headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json['error']['code'],'outcome_source_mismatch')
        second=self.client.post('/api/farm/plots/'+self.fixture.plot['id']+'/seasons',
            json=dict(name='Other season',start_date='2026-10-01'),headers=self.headers).json['item']
        other=self.observation(season=second['id'])
        self.assertEqual(self.client.post(self.url+'/outcome-links',json=self.command(other),headers=self.headers).status_code,404)
        plot=self.client.post('/api/farm/plots',json=dict(name='Other owner'),headers=self.fixture.headers[1]).json['item']
        season=self.client.post('/api/farm/plots/'+plot['id']+'/seasons',json=dict(name='Other owner season',start_date='2026-10-01'),headers=self.fixture.headers[1]).json['item']
        foreign=self.observation(season=season['id'],headers=self.fixture.headers[1])
        self.assertEqual(self.client.post(self.url+'/outcome-links',json=self.command(foreign),headers=self.headers).status_code,404)
        for path in (self.url+'/outcome',self.url+'/outcome-links'):
            self.assertEqual(self.client.get(path).status_code,401)
            self.assertEqual(self.client.get(path,headers=self.fixture.headers[1]).status_code,404)
        for query in ('?as_of=x','?as_of=2099-01-01T00:00:00Z','?as_of=2026-11-01','?as_of=x&as_of=y','?event_y=1'):
            self.assertEqual(self.client.get(self.url+'/outcome'+query,headers=self.headers).status_code,400)
        self.assertEqual(self.client.post(self.url+'/outcome-links',json=dict(self.command(other),event_y=1),headers=self.headers).status_code,400)

    def test_future_unavailable_reference_and_pre_forecast_asof(self):
        observation=self.observation()
        created=self.at
        self.at-=timedelta(microseconds=1)
        self.assertEqual(self.client.post(self.url+'/outcome-links',json=self.command(observation),headers=self.headers).status_code,404)
        self.at=created
        self.link(observation)
        before=stamp(self.forecast['created_at'])-timedelta(seconds=1)
        result=self.outcome({'as_of':before.isoformat()})
        self.assertEqual(result['status'],'forecast_not_yet_available')
        self.assertFalse(result['forecast_known_at_as_of'])
        self.assertEqual(result['linked_references'],0)

    def test_current_revision_race_pins_snapshot_then_reports_drift(self):
        observation=self.observation()
        command=self.command(observation)
        entered,release,writer_done=threading.Event(),threading.Event(),threading.Event()
        original=forecast_outcomes.reference
        def paused(*args,**kwargs):
            value=original(*args,**kwargs)
            if not entered.is_set():
                entered.set()
                if not release.wait(10): raise RuntimeError('Test release missing')
            return value
        def link():
            with self.case.app.test_client() as client:
                return client.post(self.url+'/outcome-links',json=command,headers=self.headers)
        def edit():
            data={k:observation['payload'][k] for k in ('finding','notes','analysis_id','review','record_status')}
            data.update(base_revision=1,change_reason='Concurrent edit',notes='Updated')
            try:
                with self.case.app.test_client() as client:
                    return client.put('/api/farm/observations/'+observation['id'],json=data,headers=self.headers)
            finally: writer_done.set()
        with patch('forecast_outcomes.reference',side_effect=paused),ThreadPoolExecutor(max_workers=2) as pool:
            pending=pool.submit(link)
            try:
                self.assertTrue(entered.wait(10))
                self.at+=timedelta(seconds=1)
                writer=pool.submit(edit)
                self.assertFalse(writer_done.wait(.2))
            finally: release.set()
            linked=pending.result(20);edited=writer.result(20)
        self.assertEqual(linked.status_code,201,linked.json)
        self.assertEqual(edited.status_code,201,edited.json)
        self.assertEqual(linked.json['item']['reference_revision'],1)
        self.assertEqual(self.links()[0]['reference_status'],'stale_revision')
        self.assertEqual(self.outcome()['usable_observations'],0)

    def test_concurrent_same_id_and_storage_quota_do_not_duplicate(self):
        observation=self.observation()
        command=self.command(observation)
        def post(_):
            with self.case.app.test_client() as client:
                return client.post(self.url+'/outcome-links',json=command,headers=self.headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(post,range(2))),[200,201])
        with patch('forecast_outcomes.MAX_LINKS',1):
            self.link(observation,command=command,status=200)
            another=self.observation(hours=2)
            self.assertEqual(self.client.post(self.url+'/outcome-links',json=self.command(another),headers=self.headers).status_code,409)

    def test_corruption_rejected_and_forecast_alerts_stay_immutable(self):
        observation=self.observation()
        linked=self.link(observation)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE forecast_outcome_links SET snapshot_json='{}' WHERE id=?",(linked['id'],))
        self.assertEqual(self.client.get(self.url+'/outcome',headers=self.headers).status_code,500)
        self.assertEqual(self.client.post('/api/farm/forecast-outcome-links/'+linked['id']+'/retractions',
            json=dict(base_version=1,reason='Wrong'),headers=self.headers).status_code,500)
        self.assertEqual(self.client.get(self.url,headers=self.headers).json['item'],self.forecast)

    def test_readonly_reopen_backup_and_unsupported_static_fixture(self):
        observation=self.observation(finding='present',reviewed=True)
        self.link(observation)
        expected=self.outcome()
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            before={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('synthetic_forecasts','forecast_outcome_links','forecast_outcome_actions','forecast_alerts')}
        self.case.app.config['FORECAST_WORKER_PORT']=1
        reopened=create_pilot_app(self.fixture.root).test_client()
        result=reopened.get(self.url+'/outcome',headers=self.headers)
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['item'],expected)
        self.assertEqual(self.client.get(self.url,headers=self.headers).json['item'],self.forecast)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(before,{t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in before})
        self.case.app.config['FORECAST_WORKER_PORT']=self.port
        fixture=self.client.post(self.case.url,json=dict(scenario='ready'),headers=self.headers).json['item']
        self.assertEqual(self.client.get('/api/farm/forecasts/'+fixture['id']+'/outcome',headers=self.headers).status_code,409)
        (self.fixture.root/MARKER).write_text(json.dumps(dict(kind=KIND)),encoding='utf-8')
        audit_data(self.fixture.root)
        with tempfile.TemporaryDirectory(prefix='aegis_t13_backup_') as directory:
            backup(self.fixture.root,Path(directory)/'snapshot');verify(Path(directory)/'snapshot')

    def test_journal_corruption_does_not_create_link(self):
        observation=self.observation()
        with journal_db(self.fixture.root/'journal.sqlite3') as db:
            db.execute("UPDATE revisions SET payload_json='{}' WHERE visit_id=?",(observation['id'],))
        response=self.client.post(self.url+'/outcome-links',json=self.command(observation),headers=self.headers)
        self.assertEqual(response.status_code,500,response.json)
        self.assertEqual(response.json['error']['code'],'outcome_reference_storage_error')
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM forecast_outcome_links').fetchone()[0],0)
        self.assertEqual(self.client.get(self.url,headers=self.headers).json['item'],self.forecast)

    def test_forecast_mutation_breaks_capture_hash(self):
        self.link(self.observation())
        changed=dict(self.forecast,score=self.forecast['score']+.01)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute('UPDATE synthetic_forecasts SET result_json=? WHERE id=?',(json.dumps(changed),self.forecast['id']))
        response=self.client.get(self.url+'/outcome',headers=self.headers)
        self.assertEqual(response.status_code,500,response.json)
        self.assertEqual(response.json['error']['code'],'forecast_outcome_storage_error')

    def test_followup_close_is_workflow_only_not_disease_outcome(self):
        device=self.client.post('/api/farm/seasons/'+self.fixture.season['id']+'/devices',
            json=dict(name='Synthetic workflow device',device_code='t13-'+uuid4().hex,source='mock'),headers=self.headers).json['item']
        end=self.issue.replace(minute=0,second=0,microsecond=0)
        records=[dict(start_at=(end-timedelta(hours=24-i)).isoformat(),air_temperature_c=26,relative_humidity_pct=95,leaf_wet=True) for i in range(24)]
        response=self.client.post('/api/farm/devices/'+device['id']+'/telemetry',json=dict(source='mock',records=records),headers=self.headers)
        self.assertEqual(response.status_code,201,response.json)
        assessment=self.client.post('/api/farm/devices/'+device['id']+'/assessments',json=dict(as_of=end.isoformat()),headers=self.headers)
        self.assertEqual(assessment.status_code,201,assessment.json)
        case=self.client.post('/api/farm/assessments/'+assessment.json['item']['id']+'/follow-up',json=dict(reason='Synthetic workflow'),headers=self.headers)
        self.assertEqual(case.status_code,201,case.json)
        case=case.json['item'];self.link(case,'followup')
        observation=self.observation()
        for version,action in ((1,'acknowledge'),(2,'check'),(3,'close')):
            self.at+=timedelta(seconds=1)
            response=self.client.post('/api/farm/follow-ups/'+case['id']+'/events',json=dict(client_event_id=str(uuid4()),
                base_version=version,action=action,reason='Synthetic '+action,
                observation_id=observation['id'] if action=='check' else None,
                resolution='followup_recorded' if action=='close' else None),headers=self.headers)
            self.assertEqual(response.status_code,201,response.json)
        current=dict(case,version=4)
        self.link(current,'followup')
        result=self.outcome()
        self.assertEqual(result['usable_observations'],0)
        self.assertEqual(result['workflow_references'],1)
        self.assertEqual(result['evidence_status'],'not_observed')
        self.assertEqual(result['status'],'following_up')


if __name__=='__main__': unittest.main()
