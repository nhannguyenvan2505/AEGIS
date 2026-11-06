from datetime import datetime,timedelta,timezone
import io
import hashlib
import json
import unittest
from unittest.mock import patch
import uuid
import test_followup
END=test_followup.END


class TimelineTests(unittest.TestCase):
    def setUp(self):
        test_followup.FollowupTests.setUp(self)
        self.case=test_followup.FollowupTests.create(self)
        self.timeline='/api/farm/seasons/'+self.season['id']+'/timeline'
        p=dict(client_intervention_id=str(uuid.uuid4()),source='synthetic',at=END.isoformat(),kind='irrigation',action_details='Timeline irrigation',notes='',record_status='active',change_reason='Test')
        self.intervention=self.client.post('/api/farm/seasons/'+self.season['id']+'/interventions',json=p,headers=self.headers[0]).json['item']

    def get(self,suffix='',owner=0):return self.client.get(self.timeline+suffix,headers=self.headers[owner])

    def test_types_pagination_and_stable_order(self):
        r=self.get('?page_size=100');self.assertEqual(r.status_code,200);items=r.json['items']
        self.assertTrue({'assessment','followup','observation','intervention','mock_telemetry'}.issubset({x['kind'] for x in items}))
        first=self.get('?page_size=2').json
        second=self.get('?page_size=2&page=2&as_of='+first['as_of'].replace('+','%2B')).json
        self.assertEqual(first['pagination']['total'],len(items));self.assertEqual(len(second['items']),2)
        self.assertFalse({x['event_id'] for x in first['items']} & {x['event_id'] for x in second['items']})
        self.assertEqual(len(items),len({x['event_id'] for x in items}))

    def test_owner_auth_filters_and_invalid_arguments(self):
        self.assertEqual(self.client.get(self.timeline).status_code,401);self.assertEqual(self.get(owner=1).status_code,404)
        for suffix in ['?kind=bad','?axis=bad','?page=0','?page_size=101','?page=1&page=2','?foo=1','?as_of=2100-01-01T00:00:00Z','?from=2026-10-25T00:00:00','?from=2026-10-25T00:00:00Z&to=2026-10-24T00:00:00Z']:
            with self.subTest(suffix=suffix):self.assertEqual(self.get(suffix).status_code,400)
        r=self.get('?kind=intervention');self.assertEqual(len(r.json['items']),1);self.assertIn('no-store',r.headers['Cache-Control'])

    def test_revision_history_and_recorded_axis_cutoff(self):
        p={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};p.update(base_revision=1,record_status='voided')
        with patch('pilot_journal.now',return_value=END+timedelta(hours=4)):
            self.assertEqual(self.client.put('/api/farm/observations/'+self.visit['id'],json=p,headers=self.headers[0]).status_code,201)
        early=self.get('?kind=observation&as_of=2026-10-24T03:00:00Z').json['items']
        self.assertEqual(len(early),1);self.assertEqual(early[0]['detail']['record_status'],'active')
        later=self.get('?kind=observation&as_of=2026-10-24T05:00:00Z').json['items'];self.assertEqual(len(later),2)
        self.assertEqual({x['revision'] for x in later},{1,2})
        r=self.get('?kind=observation&axis=recorded_at&from=2026-10-24T03:00:00Z&to=2026-10-24T05:00:00Z')
        self.assertEqual(len(r.json['items']),1);self.assertEqual(r.json['items'][0]['revision'],2)

    def test_linked_images_only_and_no_detection_not_healthy(self):
        result=dict(success=True,model_version='mock',model_sha256='a'*64,status='no_detection',image=dict(width=32,height=32,orientation='exif_corrected'),detections=[],timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=1.))
        with patch('app.routes.predict_image',return_value=result):
            image=self.client.post('/api/disease/detect',headers=self.headers[0],data={'image':(io.BytesIO(b'test'),'test.png')}).json
        self.assertEqual(self.get('?kind=image').json['items'],[])
        self.client.post('/api/farm/assessments/'+self.a['id']+'/analyses',json={'analysis_id':image['analysis_id']},headers=self.headers[0])
        r=self.get('?kind=image').json['items'];self.assertEqual(len(r),1)
        self.assertEqual(r[0]['detail']['status'],'no_detection');self.assertEqual(r[0]['source'],'image_origin_unknown')
        self.assertNotIn('healthy',json.dumps(r));self.assertNotIn('image_bytes',json.dumps(r))

    def test_raw_exclusion_not_applied_before_available(self):
        h=self.headers[0]
        with patch('pilot_telemetry.now',return_value=END+timedelta(hours=1)):
            stream=self.client.post('/api/farm/seasons/'+self.season['id']+'/environment-streams',json=dict(client_stream_id=str(uuid.uuid4()),name='Raw test',source='synthetic',method='manual_reading',instrument='Test',reference='Test',nominal_interval_seconds=None),headers=h).json['item']
            sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=END.isoformat(),air_temperature_c=26,relative_humidity_pct=95,leaf_wet=None,reported_quality='unknown',reference='Test')
            self.client.post('/api/farm/environment-streams/'+stream['id']+'/samples',json=dict(records=[sample]),headers=h)
        with patch('pilot_telemetry.now',return_value=END+timedelta(hours=4)):
            self.client.post('/api/farm/environment-samples/'+sample['client_sample_id']+'/exclusion',json={'reason':'Test exclusion'},headers=h)
        self.assertEqual(self.get('?kind=environment&as_of=2026-10-24T00:30:00Z').json['items'],[])
        early=self.get('?kind=environment&as_of=2026-10-24T02:00:00Z').json['items'];self.assertIsNone(early[0]['detail']['excluded_at'])
        late=self.get('?kind=environment&as_of=2026-10-24T05:00:00Z').json['items'];self.assertIsNotNone(late[0]['detail']['excluded_at'])
        self.assertEqual(len(self.get('?kind=environment_exclusion').json['items']),1)

    def test_readonly_five_db_hashes_and_no_other_season_events(self):
        names=['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3']
        before={n:hashlib.sha256((self.root/n).read_bytes()).hexdigest() for n in names}
        self.assertEqual(self.get('?page_size=100').status_code,200)
        for n,d in before.items():self.assertEqual(hashlib.sha256((self.root/n).read_bytes()).hexdigest(),d)
        season=self.client.post('/api/farm/plots/'+self.plot['id']+'/seasons',json=dict(name='Other season',start_date='2026-10-01',end_date='2026-12-31'),headers=self.headers[0]).json['item']
        self.assertEqual(self.client.get('/api/farm/seasons/'+season['id']+'/timeline',headers=self.headers[0]).json['items'],[])

    def test_cultivation_and_observation_image_links(self):
        p=dict(region='unknown',province_or_city=None,locality=None,rice_variety=None,planting_method='unknown',sown_on=None,transplanted_on=None,season_status='unknown')
        r=self.client.put('/api/farm/seasons/'+self.season['id']+'/cultivation-profile',json=dict(base_revision=0,profile=p,change_reason='Test context'),headers=self.headers[0])
        self.assertEqual(r.status_code,201);self.assertEqual(len(self.get('?kind=cultivation').json['items']),1)
        result=dict(success=True,model_version='mock',model_sha256='a'*64,status='no_detection',image=dict(width=32,height=32,orientation='exif_corrected'),detections=[],timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=1.))
        with patch('app.routes.predict_image',return_value=result):
            image=self.client.post('/api/disease/detect',headers=self.headers[0],data={'image':(io.BytesIO(b'test'),'test.png')}).json
        p={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};p.update(base_revision=1,analysis_id=image['analysis_id'])
        self.client.put('/api/farm/observations/'+self.visit['id'],json=p,headers=self.headers[0])
        images=self.get('?kind=image').json['items'];self.assertEqual(len(images),1)
        self.assertEqual(images[0]['detail']['link_kind'],'observation_revision')


if __name__=='__main__':unittest.main()
