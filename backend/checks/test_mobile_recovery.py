"""H2-T03 HTTP recovery acceptance on disposable synthetic pilot stores.

No mobile code, AI/checkpoint, production DB or new API behavior.
"""
from contextlib import closing
import importlib
import json
import logging
from pathlib import Path
import sqlite3
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import requests
from werkzeug.serving import make_server, WSGIRequestHandler

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND));sys.path.insert(0,str(BACKEND.parent/'frontend'))
from pilot_app import create_pilot_app
from app.auth import token_digest
from app.storage import connect
import test_followup

TRACES=[]

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass

class Capture(logging.Handler):
    def __init__(self):super().__init__();self.messages=[]
    def emit(self,record):self.messages.append(record.getMessage())

class MobileRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.release=threading.Event();self.committed=threading.Event();self.delay_path=None
        f=test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
        self.addCleanup(f.doCleanups);f.setUp();self.f=f
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9');f.app.config['FARM_WRITE_LIMIT']=500
        f.client=f.app.test_client();self.case=f.create();self.path='/api/farm/follow-ups/'+self.case['id']
        self.owner=dict(f.headers[0]);self.other=dict(f.headers[1]);self.trace=[]
        self.capture=Capture();f.app.logger.addHandler(self.capture)
        self.addCleanup(f.app.logger.removeHandler,self.capture)
        original=f.app.wsgi_app
        def application(environ,start_response):
            iterable=original(environ,start_response)
            if environ['REQUEST_METHOD']=='POST' and environ['PATH_INFO']==self.delay_path:
                self.delay_path=None;self.committed.set()
                def delayed():
                    try:
                        if not self.release.wait(10):raise RuntimeError('Test response barrier timed out')
                        yield from iterable
                    finally:
                        if hasattr(iterable,'close'):iterable.close()
                return delayed()
            return iterable
        f.app.wsgi_app=application
        self.server=make_server('127.0.0.1',0,f.app,threaded=True,request_handler=QuietHandler)
        self.thread=threading.Thread(target=self.server.serve_forever)
        self.thread.start();self.addCleanup(self.stop_server)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.http=requests.Session();self.http.trust_env=False;self.addCleanup(self.http.close)

    def stop_server(self):
        self.release.set();self.server.shutdown();self.server.server_close();self.thread.join(10)
        self.assertFalse(self.thread.is_alive())

    def tearDown(self):
        # Only request-completion records are diagnostic examples; no body/auth/query.
        allowed={'event','service','request_id','method','route','status','processing_ms',
                 'analysis_id','model_sha256','ai_error_code'}
        for value in self.capture.messages:
            if value.startswith('{'):
                event=json.loads(value)
                if event.get('event')=='request_completed':
                    self.assertTrue(set(event)<=allowed)
        serial=json.dumps(self.trace)
        secrets=[self.owner['Authorization'],self.other['Authorization'],
                 self.owner['Authorization'].split()[1],self.other['Authorization'].split()[1],
                 'journal-test-password-123']
        self.assertFalse(any(secret in serial or any(secret in v for v in self.capture.messages)
                             for secret in secrets),'Credential found in diagnostic output')
        TRACES.append(dict(test=self.id(),requests=self.trace))

    def call(self,method,path,*,headers=None,payload=None,timeout=10):
        response=self.http.request(method,self.base+path,headers=self.owner if headers is None else headers,
            json=payload,timeout=timeout)
        body=response.json();rid=response.headers.get('X-Request-ID')
        self.assertEqual(str(uuid.UUID(rid)),rid)
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        self.assertIn('Authorization',response.headers.get('Vary',''))
        code=(body.get('error') or {}).get('code')
        if response.status_code>=400:self.assertEqual(body['request_id'],rid)
        route=path.replace(self.case['id'],'{case_id}').replace(self.f.season['id'],'{season_id}')
        self.trace.append(dict(method=method,route_template=route,status=response.status_code,
            request_id=rid,error_code=code,retry_after=response.headers.get('Retry-After')))
        return response,body

    def command(self,version,action='acknowledge'):
        return dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,
            reason='H2-T03 synthetic HTTP acceptance',
            observation_id=self.f.visit['id'] if action=='check' else None,resolution=None)

    def event_count(self):
        response,body=self.call('GET',self.path+'/events');self.assertEqual(response.status_code,200)
        return len(body['items'])

    def test_refresh_and_expired_snapshot_are_not_session_expiry(self):
        response,caps=self.call('GET','/api/mobile/capabilities')
        self.assertEqual(response.status_code,200);self.assertTrue(caps['follow_up']['available'])
        self.assertEqual(caps['image_detection']['service_status'],'not_checked')
        response,listing=self.call('GET','/api/farm/seasons/'+self.f.season['id']+'/follow-ups')
        self.assertEqual(listing['items'][0]['id'],self.case['id'])
        _,view=self.call('GET',self.path+'/assessment-view')
        self.assertEqual(view['item']['required']['display_freshness'],'expired')
        self.assertEqual(view['item']['required']['id'],self.f.a['id'])
        self.assertEqual(view['item']['current']['id'],self.f.a['id'])
        _,detail=self.call('GET',self.path);self.assertEqual(detail['item']['state'],'open')
        response,body=self.call('POST',self.path+'/events',payload=self.command(1))
        self.assertEqual(response.status_code,201);self.assertEqual(body['item']['version'],2)

    def test_stale_version_refresh_then_new_user_intent(self):
        self.assertEqual(self.call('POST',self.path+'/events',payload=self.command(1))[0].status_code,201)
        stale=self.command(1,'check')
        response,body=self.call('POST',self.path+'/events',payload=stale)
        self.assertEqual(response.status_code,409);self.assertEqual(body['error']['code'],'followup_version_conflict')
        _,detail=self.call('GET',self.path);self.call('GET',self.path+'/assessment-view');self.event_count()
        self.assertEqual(detail['item']['version'],2)
        new=self.command(detail['item']['version'],'check')
        self.assertNotEqual(new['client_event_id'],stale['client_event_id'])
        response,body=self.call('POST',self.path+'/events',payload=new)
        self.assertEqual(response.status_code,201);self.assertEqual(body['item']['version'],3)

    def test_conflicting_payload_does_not_rewrite_original_event(self):
        command=self.command(1);_,first=self.call('POST',self.path+'/events',payload=command)
        response,body=self.call('POST',self.path+'/events',payload=dict(command,reason='Changed payload'))
        self.assertEqual(response.status_code,409);self.assertEqual(body['error']['code'],'followup_event_conflict')
        response,replay=self.call('POST',self.path+'/events',payload=command)
        self.assertEqual(response.status_code,200);self.assertEqual(replay['event']['id'],first['event']['id'])
        self.assertEqual(self.event_count(),2)  # created + acknowledged

    def test_timeout_after_commit_exact_replay_keeps_event_and_current_item(self):
        command=self.command(1);initial=self.event_count();self.delay_path=self.path+'/events'
        try:
            with self.assertRaises(requests.Timeout):
                self.call('POST',self.path+'/events',payload=command,timeout=(3,.5))
            self.assertTrue(self.committed.wait(2),'Timeout did not reach the intended post-commit boundary')
            self.trace.append(dict(method='POST',route_template='/api/farm/follow-ups/{case_id}/events',
                transport_outcome='timeout_no_http_response',request_id=None))
            _,detail=self.call('GET',self.path);self.assertEqual(detail['item']['version'],2)
            _,events=self.call('GET',self.path+'/events')
            event=next(e for e in events['items'] if e['id']==command['client_event_id'])
            self.assertEqual(len(events['items']),initial+1)
            # State advances before replay: replay event is old, item must stay current.
            self.assertEqual(self.call('POST',self.path+'/events',payload=self.command(2,'check'))[0].status_code,201)
            response,replay=self.call('POST',self.path+'/events',payload=command)
            self.assertEqual(response.status_code,200);self.assertEqual(replay['event']['id'],event['id'])
            self.assertEqual(replay['event']['request_id'],event['request_id'])
            self.assertNotEqual(response.headers['X-Request-ID'],event['request_id'])
            self.assertEqual(replay['event']['version'],2);self.assertEqual(replay['item']['version'],3)
            self.assertEqual(self.event_count(),initial+2)
        finally:self.release.set()

    def test_rate_limit_has_no_effect_and_wait_then_exact_retry(self):
        command=self.command(1);before=self.event_count();self.f.app.config['FARM_WRITE_LIMIT']=1
        response,body=self.call('POST',self.path+'/events',payload=command)
        self.assertEqual(response.status_code,429);self.assertEqual(body['error']['code'],'rate_limit_exceeded')
        seconds=int(response.headers['Retry-After']);self.assertGreaterEqual(seconds,1)
        self.assertEqual(self.event_count(),before)
        # Advance only limiter's module clock; no real long wait or OS/auth clock change.
        limits=importlib.import_module('app.limits')
        with patch.object(limits,'time',SimpleNamespace(time=lambda:time.time()+seconds+1)):
            response,body=self.call('POST',self.path+'/events',payload=command)
        self.assertEqual(response.status_code,201);self.assertEqual(body['event']['id'],command['client_event_id'])

    def test_integrity_unavailable_has_no_fallback_and_can_refresh_after_repair(self):
        before=self.event_count()
        with closing(sqlite3.connect(self.f.root/'followup.sqlite3')) as db:
            old=db.execute('SELECT assessment_sha256 FROM cases WHERE id=?',(self.case['id'],)).fetchone()[0]
            with db:db.execute('UPDATE cases SET assessment_sha256=? WHERE id=?',('0'*64,self.case['id']))
        try:
            response,body=self.call('GET',self.path+'/assessment-view')
            self.assertEqual(response.status_code,503);self.assertEqual(body['error']['code'],'assessment_integrity_error')
            self.assertNotIn('item',body);self.assertNotIn('Retry-After',response.headers)
            self.assertEqual(self.event_count(),before)
        finally:
            with closing(sqlite3.connect(self.f.root/'followup.sqlite3')) as db:
                with db:db.execute('UPDATE cases SET assessment_sha256=? WHERE id=?',(old,self.case['id']))
        response,body=self.call('GET',self.path+'/assessment-view')
        self.assertEqual(response.status_code,200);self.assertEqual(body['item']['required']['id'],self.f.a['id'])

    def test_auth_expiry_relogin_and_account_switch_preserve_owner_boundary(self):
        auth=importlib.import_module('app.auth')
        with connect(self.f.app.config) as db:
            expiry=db.execute('SELECT expires_at FROM sessions WHERE token_hash=?',
                (token_digest(self.owner['Authorization'].split()[1]),)).fetchone()[0]
        command=self.command(1);before=self.event_count()
        with patch.object(auth,'time',SimpleNamespace(time=lambda:expiry)):
            for method,path,payload in [('GET',self.path,None),('POST',self.path+'/events',command)]:
                response,body=self.call(method,path,payload=payload)
                self.assertEqual(response.status_code,401);self.assertEqual(body['error']['code'],'unauthorized')
        self.assertEqual(self.event_count(),before)
        response,body=self.call('GET',self.path,headers=self.other)
        self.assertEqual(response.status_code,404);self.assertEqual(body['error']['code'],'resource_not_found')
        # Auth endpoint's private header comes from pilot factory, not a native cache test.
        response,login=self.call('POST','/api/auth/login',headers={},
            payload=dict(email='journal-owner@example.test',password='journal-test-password-123'))
        self.assertEqual(response.status_code,200)
        self.owner={'Authorization':'Bearer '+login['access_token']}
        self.assertEqual(self.call('GET',self.path)[0].status_code,200)
        self.assertEqual(self.call('POST','/api/auth/logout')[0].status_code,200)
        self.assertEqual(self.call('GET',self.path)[0].status_code,401)

if __name__=='__main__':unittest.main()
