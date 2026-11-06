"""Cultivation context: versioning, ownership, dates and immutable snapshots."""
import copy
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
import test_farm as fixtures
from app import create_app
from app.blast_conditions import digest
from app.storage import connect


class CultivationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FarmTests('test_full_chain_snapshot_replay_and_restart')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.url='/api/farm/seasons/'+self.f.season['id']+'/cultivation-profile'
        self.profile=dict(region='central',province_or_city='Tỉnh demo',locality='Khu mô phỏng',
                          rice_variety='Giống khai báo thử',planting_method='transplanted',
                          sown_on='2026-09-20',transplanted_on='2026-10-05',season_status='active')

    def put(self,profile=None,base=0,owner=0,reason='Khai báo hồ sơ ban đầu',client=None):
        return (client or self.f.client).put(self.url,headers=self.f.headers[owner],
                 json=dict(base_revision=base,profile=self.profile if profile is None else profile,change_reason=reason))

    def get(self,suffix='',owner=0):return self.f.client.get(self.url+suffix,headers=self.f.headers[owner])

    def test_unknown_legacy_is_not_inferred_from_season_start(self):
        data=self.get().json
        self.assertIsNone(data['item']);self.assertEqual(data['context_check']['status'],'incomplete')
        self.assertIn('planting_date',data['context_check']['missing_fields'])
        self.assertEqual(self.get('/revisions').json['pagination']['total'],0)
        a=self.f.assess().json['item']['cultivation_context']
        self.assertIsNone(a['crop_age_days']);self.assertIsNone(a['item'])

    def test_roundtrip_replay_and_restart(self):
        r=self.put();self.assertEqual(r.status_code,201)
        d=r.json;self.assertEqual(d['item']['revision'],1)
        self.assertEqual(d['item']['profile_sha256'],digest(d['item']['profile']))
        self.assertEqual(d['context_check']['status'],'complete')
        self.assertFalse(d['context_check']['agronomically_verified'])
        self.assertFalse(d['context_check']['changes_warning_rule'])
        self.assertEqual(d['item']['request_id'],r.headers['X-Request-ID'])
        retry=self.put();self.assertEqual(retry.status_code,200)
        self.assertEqual(retry.json,d);self.assertEqual(retry.headers['Idempotency-Replayed'],'true')
        restarted=create_app(self.f.config).test_client()
        self.assertEqual(restarted.get(self.url,headers=self.f.headers[0]).json,d)
        self.assertEqual(self.get('/revisions').json['pagination']['total'],1)

    def test_owner_auth_and_database_parent_integrity(self):
        self.put()
        for suffix in ['', '/revisions']:
            self.assertEqual(self.get(suffix,1).status_code,404)
            self.assertEqual(self.f.client.get(self.url+suffix).status_code,401)
        self.assertEqual(self.put(owner=1).status_code,404)
        self.assertEqual(self.f.client.put(self.url,json={}).status_code,401)
        with self.assertRaises(sqlite3.IntegrityError),connect(self.f.config) as db:
            other=db.execute('SELECT id FROM users WHERE id<>?',(self.f.plot['user_id'],)).fetchone()[0]
            db.execute('INSERT INTO farm_cultivation_revisions VALUES (?,?,?,?,?,?,?,?,?)',
                       ('bad',self.f.season['id'],other,1,'{}','hash','bad','now','request'))

    def test_partial_unknown_is_allowed_but_not_complete(self):
        p=dict(region='unknown',province_or_city=None,locality=None,rice_variety=None,
               planting_method='unknown',sown_on=None,transplanted_on=None,season_status='planned')
        r=self.put(p);self.assertEqual(r.status_code,201)
        self.assertEqual(r.json['context_check']['status'],'incomplete')
        self.assertIn('planting_date',r.json['context_check']['missing_fields'])
        self.assertEqual(r.json['item']['profile']['season_status'],'planned')

    def test_dates_and_strict_fields(self):
        cases=[('transplanted_on','2026-10-25'),('sown_on','2026-10-06'),
               ('transplanted_on','2026-09-30'),('sown_on','2026-02-30'),
               ('transplanted_on','20261005'),('transplanted_on',True),
               ('season_status',[]),('region',{}),('rice_variety',True),('rice_variety','x'*121),
               ('rice_variety','private\nvalue'),('planting_method','invented')]
        for key,value in cases:
            p=copy.deepcopy(self.profile);p[key]=value
            with self.subTest(key=key,value=value):self.assertEqual(self.put(p).status_code,400)
        p=dict(self.profile,user_id='forged');self.assertEqual(self.put(p).status_code,400)
        p=dict(self.profile);del p['region'];self.assertEqual(self.put(p).status_code,400)
        self.assertEqual(self.put(base=True).status_code,400)
        self.assertEqual(self.put(base=-1).status_code,400)
        self.assertEqual(self.put(reason='').status_code,400)
        self.assertEqual(self.get('/revisions').json['pagination']['total'],0)

    def test_direct_seeded_date_and_age_not_converted_to_transplant_age(self):
        p=dict(self.profile,planting_method='direct_seeded',sown_on='2026-10-05',transplanted_on=None)
        self.assertEqual(self.put(p).status_code,201)
        a=self.f.assess().json['item']['cultivation_context']
        self.assertEqual(a['crop_age_days'],19);self.assertEqual(a['crop_age_basis'],'sown_on')
        self.assertEqual(a['item']['profile']['planting_method'],'direct_seeded')
        self.assertEqual(self.put(dict(p,transplanted_on='2026-10-06'),base=1).status_code,400)
        self.assertEqual(self.put(dict(p,sown_on='2026-09-30'),base=1).status_code,400)

    def test_revision_conflict_history_and_no_op(self):
        first=self.put().json['item']
        second=self.put(dict(self.profile,rice_variety='Đã sửa'),base=1,reason='Sửa khai báo giống')
        self.assertEqual(second.status_code,201)
        self.assertEqual(self.put(dict(self.profile,rice_variety='Ghi đè sai'),base=1).status_code,409)
        replay=self.put(dict(self.profile,rice_variety='Đã sửa'),base=1,reason='Sửa khai báo giống')
        self.assertEqual(replay.status_code,200)
        self.assertEqual(self.put(dict(self.profile,rice_variety='Đã sửa'),base=2).status_code,200)
        history=self.get('/revisions?page_size=1').json
        self.assertEqual(history['items'][0]['revision'],2);self.assertTrue(history['pagination']['has_next'])
        self.assertEqual(self.get('/revisions?page=2&page_size=1').json['items'][0],first)
        for suffix in ['/revisions?page=0','/revisions?x=1','/revisions?page=1&page=2']:
            self.assertEqual(self.get(suffix).status_code,400)

    def test_concurrent_edit_only_one_wins(self):
        self.put();barrier=threading.Barrier(2)
        def edit(i):
            with self.f.app.test_client() as client:
                barrier.wait(timeout=5)
                return self.put(dict(self.profile,rice_variety='Change '+str(i)),base=1,client=client).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,[1,2]))
        self.assertEqual(sorted(results),[201,409])
        self.assertEqual(self.get('/revisions').json['pagination']['total'],2)

    def test_context_frozen_on_assessment_and_retrospective_availability(self):
        self.put();self.f.ingest();first=self.f.assess().json['item']
        ctx=first['cultivation_context'];self.assertEqual(ctx['item']['revision'],1)
        self.assertTrue(ctx['recorded_after_window_end']);self.assertEqual(ctx['crop_age_days'],19)
        self.put(dict(self.profile,rice_variety='Updated later'),base=1)
        self.assertEqual(self.f.assess().json['item'],first)
        with patch('app.farm.now',return_value=fixtures.END+timedelta(hours=1,minutes=30)):
            second=self.f.assess().json['item']
        self.assertEqual(second['cultivation_context']['item']['revision'],2)
        self.assertEqual(first['profile'],second['profile'])
        # A profile entered today cannot invent negative age for a historical window.
        old=self.f.assess(as_of='2026-10-02T00:00:00Z').json['item']['cultivation_context']
        self.assertIsNone(old['crop_age_days']);self.assertEqual(old['age_reason'],'planting_after_window_end')

    def test_migration_preserves_v4_data_credentials_and_old_snapshots(self):
        self.f.ingest();a=self.f.assess().json['item'];a.pop('cultivation_context')
        with connect(self.f.config) as db:
            db.execute('UPDATE farm_assessments SET snapshot_json=? WHERE id=?',(json.dumps(a),a['id']))
            db.execute('DROP TABLE farm_cultivation_revisions')
            db.execute('DELETE FROM schema_migrations WHERE version=5')
            before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in ['users','sessions','farm_plots','farm_seasons','farm_devices','farm_telemetry','farm_assessments']}
        app=create_app(self.f.config);create_app(self.f.config)
        with connect(self.f.config) as db:
            for table,rows in before.items():self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM '+table)],rows)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations WHERE version=5').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farm_cultivation_revisions').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(app.test_client().post('/api/farm'+self.f.assess_url,json={},headers=self.f.headers[0]).json['item'],a)

    def test_quota_head_and_logs(self):
        self.assertEqual(self.f.client.head(self.url,headers=self.f.headers[0]).status_code,200)
        self.assertEqual(self.get('/revisions').json['pagination']['total'],0)
        with self.assertLogs(self.f.app.logger,level='INFO') as logs:
            self.put(dict(self.profile,rice_variety='PRIVATE_VARIETY_928'))
        self.assertNotIn('PRIVATE_VARIETY_928','\n'.join(logs.output))
        self.assertNotIn(self.f.headers[0]['Authorization'],'\n'.join(logs.output))
        with patch('app.limits.consume',return_value=(False,7)):
            r=self.put(base=1)
        self.assertEqual(r.status_code,429);self.assertEqual(r.headers['Retry-After'],'7')


if __name__=='__main__':unittest.main()
