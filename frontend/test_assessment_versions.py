from contextlib import closing
import hashlib
from datetime import timedelta
import json,sqlite3,unittest,uuid
from unittest.mock import patch
import test_episodes
from server import build_app
from pilot_assessment_versions import ensure_version

END=test_episodes.END


class VersionTests(unittest.TestCase):
    create=test_episodes.EpisodeTests.create
    seed=test_episodes.EpisodeTests.seed
    tick=test_episodes.EpisodeTests.tick
    counts=test_episodes.EpisodeTests.counts
    action=test_episodes.EpisodeTests.action
    episodes=test_episodes.EpisodeTests.episodes
    def setUp(self):
        test_episodes.EpisodeTests.setUp(self)
        c=patch('pilot_assessment_versions.now',side_effect=lambda:self.at[0]);c.start();self.addCleanup(c.stop)
    def start(self,n=23):
        self.seed([END-timedelta(hours=24-i) for i in range(n)]);j=self.create();r=self.tick(j['id']);self.j=j;self.first=r;self.id=r['assessment_id'];self.url='/api/farm/assessments/'+self.id
        return r
    def fill(self):self.seed([END-timedelta(hours=1)]);return self.tick(self.j['id'])
    def current(self):return self.client.get(self.url+'/current',headers=self.headers[0]).json['item']
    def attempts(self):return self.client.get(self.url+'/version-attempts',headers=self.headers[0]).json['items']

    def test_v1_immutable_v2_current_with_same_profile_window_and_expiry(self):
        self.start();v1=self.current();self.at[0]+=timedelta(minutes=1);r=self.fill();v2=self.current()
        self.assertEqual(v2['revision'],2);self.assertEqual(v2['previous_id'],self.id);self.assertEqual(v2['snapshot']['result']['status'],'advisory')
        self.assertTrue(r['replayed']);self.assertEqual(r['assessment_id'],self.id);self.assertEqual(r['current_assessment']['id'],v2['id'])
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['item'],v1['snapshot'])
        for key in ['profile','valid_until','cultivation_context']:self.assertEqual(v1['snapshot'][key],v2['snapshot'][key])
        self.assertNotEqual(v1['followup_id'],v2['followup_id']);self.assertEqual(self.counts(),(1,2))
        dashboard=self.client.get(self.base+'/warning-dashboard',headers=self.headers[0]).json
        self.assertEqual(dashboard['items'][0]['latest_assessment']['revision'],2);self.assertEqual(dashboard['items'][0]['latest_assessment']['status'],'advisory')

    def test_progressive_versions_retry_dedup_and_latest_requirement_same_window(self):
        self.start(22);self.seed([END-timedelta(hours=2)]);self.tick(self.j['id']);self.fill();head=self.current();self.assertEqual(head['revision'],3)
        for _ in range(3):self.tick(self.j['id'])
        items=self.client.get(self.url+'/versions',headers=self.headers[0]).json['items'];self.assertEqual([v['revision'] for v in items],[3,2,1]);self.assertEqual(len(self.attempts()),2)
        p=next(p for p in self.episodes().json['items'] if p['task_kind']=='check_data');self.assertEqual(p['required_check']['revision'],3);self.assertEqual(p['required_check']['assessment_id'],head['id'])

    def test_same_timestamp_supplement_requires_recheck_without_automatic_close(self):
        a=self.start();cid=a['followup_id'];self.assertEqual(self.action(cid,1,'acknowledge').status_code,201);self.assertEqual(self.action(cid,2,'check').status_code,201)
        self.fill();r=self.action(cid,3,'close');self.assertEqual(r.status_code,409);self.assertEqual(r.json['error']['code'],'episode_recheck_required')
        self.assertEqual(self.action(cid,3,'check').status_code,201);self.assertEqual(self.action(cid,4,'close').status_code,201)

    def test_owner_read_only_routes_and_pagination(self):
        self.start();self.fill();v=self.current()
        paths=[self.url+'/versions',self.url+'/current',self.url+'/version-attempts','/api/farm/assessment-versions/'+v['id'],'/api/farm/assessment-versions/'+v['id']+'/follow-up']
        for url in paths:
            self.assertEqual(self.client.get(url).status_code,401);self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
            self.assertIn('no-store',self.client.get(url,headers=self.headers[0]).headers['Cache-Control'])
        for q in ['?page=0','?page=1&page=2','?page_size=101','?as_of=x']:self.assertEqual(self.client.get(self.url+'/versions'+q,headers=self.headers[0]).status_code,400)
        p=self.client.get(self.url+'/versions?page_size=1',headers=self.headers[0]).json;self.assertEqual(p['pagination']['total'],2);self.assertTrue(p['pagination']['has_next'])
        self.assertEqual(self.client.post(self.url+'/versions',json={},headers=self.headers[0]).status_code,405)

    def test_rollback_and_sanitized_failed_attempt_then_retry(self):
        self.start();self.seed([END-timedelta(hours=1)])
        for stage in ['before_version_followup','after_version_followup']:
            self.runner.checkpoint=lambda s:(_ for _ in ()).throw(RuntimeError('VERSION_SECRET')) if s==stage else None
            with self.assertLogs(self.app.logger,level='ERROR') as logs:r=self.tick(self.j['id'])
            self.assertEqual(r['status'],'failed');self.assertNotIn('VERSION_SECRET',str(logs.output));self.assertEqual(self.current()['revision'],1);self.assertEqual(self.counts(),(1,1))
        self.runner.checkpoint=lambda s:None;self.tick(self.j['id']);self.assertEqual(self.current()['revision'],2);self.assertEqual(self.counts(),(1,2));self.assertEqual([a['state'] for a in reversed(self.attempts())],['failed','failed','succeeded'])

    def test_failure_after_commit_is_recovered_without_duplicate_version_or_case(self):
        self.start();self.seed([END-timedelta(hours=1)]);self.runner.checkpoint=lambda s:(_ for _ in ()).throw(RuntimeError('VERSION_SECRET')) if s=='after_version_commit' else None
        r=self.tick(self.j['id']);self.assertEqual(r['status'],'failed');self.assertEqual(self.current()['revision'],2)
        self.runner.checkpoint=lambda s:None;self.tick(self.j['id']);self.assertEqual(self.counts(),(1,2));self.assertEqual([a['state'] for a in reversed(self.attempts())],['failed','succeeded'])

    def test_interrupted_executor_recovery_preserves_committed_version(self):
        class Crash(BaseException):pass
        self.start();self.seed([END-timedelta(hours=1)]);self.runner.checkpoint=lambda s:(_ for _ in ()).throw(Crash()) if s=='after_version_commit' else None
        with self.assertRaises(Crash):self.tick(self.j['id'])
        app=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'},automation_enabled=True);owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id']
        app.extensions['mock_automation'].tick(self.j['id'],owner,'manual');self.assertEqual(self.current()['revision'],2);self.assertEqual(self.counts(),(1,2));self.assertEqual([a['state'] for a in reversed(self.attempts())],['interrupted','succeeded'])

    def test_request_id_and_legacy_followup_separate_from_current_followup(self):
        a=self.start();self.seed([END-timedelta(hours=1)]);self.runner.enabled=True;rid=str(uuid.uuid4())
        r=self.client.post('/api/farm/automation-jobs/'+self.j['id']+'/run',json={},headers={**self.headers[0],'X-Request-ID':rid});self.assertEqual(r.status_code,200);v=r.json['item']['current_assessment']
        issued=r.headers['X-Request-ID'];self.assertNotEqual(issued,rid)
        self.assertEqual(v['request_id'],issued);self.assertEqual(v['snapshot']['request_id'],issued);self.assertEqual(self.attempts()[0]['request_id'],issued)
        legacy=self.client.get(self.url+'/follow-up',headers=self.headers[0]).json['item']['id'];new=self.client.get('/api/farm/assessment-versions/'+v['id']+'/follow-up',headers=self.headers[0]).json['case_id']
        self.assertEqual(legacy,a['followup_id']);self.assertNotEqual(legacy,new)

    def test_no_auto_backfill_previous_hour(self):
        self.start();self.at[0]+=timedelta(hours=1);self.seed([END-timedelta(hours=1),END]);self.tick(self.j['id']);self.assertEqual(self.current()['revision'],1)

    def test_retractions_value_changes_or_different_scope_are_rejected(self):
        self.start();base=self.current()['snapshot'];payload={**base['input'],'records':base['input']['records'][:-1]}
        with self.assertRaises(ValueError):ensure_version(self.root/'followup.sqlite3',base,payload,str(uuid.uuid4()),None)
        payload={**base['input'],'records':[{**base['input']['records'][0],'air_temperature_c':15}]+base['input']['records'][1:]}
        with self.assertRaises(ValueError):ensure_version(self.root/'followup.sqlite3',base,payload,str(uuid.uuid4()),None)
        self.assertEqual(self.current()['revision'],1);self.assertEqual(self.attempts(),[])

    def test_upgrade_old_followup_preserves_core_and_existing_case(self):
        self.start();case_id=self.first['followup_id'];before=self.client.get('/api/farm/follow-ups/'+case_id,headers=self.headers[0]).json
        with closing(sqlite3.connect(self.root/'followup.sqlite3')) as db:
            db.execute('DROP TABLE assessment_version_attempts');db.execute('DROP TABLE assessment_versions');db.execute('DROP TABLE assessment_version_meta');db.commit()
        core_sha=hashlib.sha256((self.root/'demo.db').read_bytes()).hexdigest()
        restored=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'})
        self.assertEqual(hashlib.sha256((self.root/'demo.db').read_bytes()).hexdigest(),core_sha)
        self.assertEqual(restored.test_client().get('/api/farm/follow-ups/'+case_id,headers=self.headers[0]).json,before)
        self.assertEqual(restored.test_client().get(self.url+'/current',headers=self.headers[0]).json['item']['revision'],1)

    def test_unknown_version_schema_is_refused_without_rewriting_it(self):
        with closing(sqlite3.connect(self.root/'followup.sqlite3')) as db:db.execute("UPDATE assessment_version_meta SET kind='unknown-schema'");db.commit()
        before=hashlib.sha256((self.root/'followup.sqlite3').read_bytes()).hexdigest()
        with self.assertRaises(ValueError):build_app(self.root,'http://127.0.0.1:9',{'kind':'test'})
        self.assertEqual(hashlib.sha256((self.root/'followup.sqlite3').read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
