"""Repeatable H6 Backend/offline demo, synthetic temporary data, no checkpoint."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True


def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    steps=[];summary=dict(kind='synthetic_software_demo',training_performed=False,
        checkpoint_loaded=False,native_ui_tested=False,steps=steps,success=False)
    server=worker=None;store=None
    def expect(name,condition):
        steps.append(dict(name=name,passed=bool(condition)))
        if not condition:raise RuntimeError('Demo assertion failed: '+name)
    try:
        import requests
        from werkzeug.serving import make_server,WSGIRequestHandler
        sys.path.insert(0,str(ROOT/'backend'))
        from pilot_app import create_pilot_app
        sys.path.insert(0,str(ROOT/'frontend'))
        from pilot_store import StoreLease
        class QuietHandler(WSGIRequestHandler):
            def log(self,*args,**kwargs):pass
        with tempfile.TemporaryDirectory(prefix='aegis_ui_thesis_') as directory:
            store=Path(directory)
            with StoreLease(store):
                app=create_pilot_app(store,'http://127.0.0.1:9')
                app.logger.disabled=True
                server=make_server('127.0.0.1',0,app,threaded=True,request_handler=QuietHandler)
                worker=threading.Thread(target=server.serve_forever);worker.start()
                origin='http://127.0.0.1:'+str(server.server_port)
                try:
                    with requests.Session() as session:
                        session.trust_env=False
                        def call(name,method,path,status,token=None,data=None):
                            response=session.request(method,origin+path,json=data,
                                headers={'Authorization':'Bearer '+token} if token else {},timeout=15)
                            expect(name,response.status_code==status)
                            steps[-1].update(method=method,path=re.sub(
                                r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',':id',path),status=response.status_code)
                            return response.json()
                        call('D01 unauthenticated capability rejected','GET','/api/mobile/capabilities',401)
                        tokens=[]
                        for index in range(2):
                            credentials=dict(email=str(uuid.uuid4())+'@example.test',password=secrets.token_hex(16))
                            call('D01 register fixture '+str(index),'POST','/api/auth/register',201,data=credentials)
                            tokens.append(call('D01 login fixture '+str(index),'POST','/api/auth/login',200,data=credentials)['access_token'])
                        token=tokens[0]
                        cap=call('D02 pilot capabilities','GET','/api/mobile/capabilities',200,token)
                        expect('D02 mock only, worker/raw off, AI not checked',cap['mode']=='pilot' and cap['follow_up']['source']=='mock'
                            and not cap['mock_automation_process_enabled'] and not cap['controlled_experiment_raw_write']
                            and cap['image_detection']['service_status']=='not_checked')
                        plot=call('D03 owned plot','POST','/api/farm/plots',201,token,dict(name='Synthetic thesis plot'))['item']
                        now=datetime.now(timezone.utc);hour=now.replace(minute=0,second=0,microsecond=0)
                        season=call('D03 owned season','POST','/api/farm/plots/'+plot['id']+'/seasons',201,token,
                            dict(name='Synthetic thesis season',start_date=(now-timedelta(days=7)).date().isoformat(),
                                 end_date=(now+timedelta(days=7)).date().isoformat()))['item']
                        device=call('D03 mock device','POST','/api/farm/seasons/'+season['id']+'/devices',201,token,
                            dict(name='Software only',device_code='thesis-'+uuid.uuid4().hex,source='mock'))['item']
                        records=[dict(start_at=(hour-timedelta(hours=24-i)).isoformat(),air_temperature_c=26,
                            relative_humidity_pct=95,leaf_wet=True) for i in range(24)]
                        call('D03 mock hourly input','POST','/api/farm/devices/'+device['id']+'/telemetry',201,token,dict(source='mock',records=records))
                        assessment=call('D03 rule assessment','POST','/api/farm/devices/'+device['id']+'/assessments',201,token,
                            dict(as_of=hour.isoformat()))['item']
                        expect('D03 advisory is mock rule, no disease diagnosis',assessment['input']['source']=='mock' and assessment['result']['status']=='advisory')
                        case=call('D04 create followup','POST','/api/farm/assessments/'+assessment['id']+'/follow-up',201,token,
                            dict(reason='Software demo follow-up'))['item']
                        base='/api/farm/follow-ups/'+case['id']
                        listing=call('D04 owned list','GET','/api/farm/seasons/'+season['id']+'/follow-ups',200,token)
                        view=call('D04 required and current','GET',base+'/assessment-view',200,token)['item']
                        expect('D04 requirement and current v1 agree',len(listing['items'])==1 and view['required']['id']==assessment['id']
                            and view['current']['revision']==1 and not view['disease_confirmed'] and not view['training_approved'])
                        def command(version,action,observation=None,resolution=None):
                            return dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,
                                reason='Synthetic demo '+action,observation_id=observation,resolution=resolution)
                        ack=command(1,'acknowledge')
                        first=call('D05 acknowledge','POST',base+'/events',201,token,ack)
                        replay=call('D05 exact retry','POST',base+'/events',200,token,ack)
                        expect('D05 same event, no duplicate',first['event']['id']==replay['event']['id'])
                        call('D05 stale workflow version','POST',base+'/events',409,token,command(1,'check',str(uuid.uuid4())))
                        observation=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=datetime.now(timezone.utc).isoformat(),
                            scheduled=True,finding='uncertain',notes='Software fixture only',analysis_id=None,review=None,
                            record_status='active',change_reason='Synthetic demo')
                        visit=call('D06 synthetic uncertain observation','POST','/api/farm/seasons/'+season['id']+'/observations',201,token,observation)['item']
                        call('D06 check','POST',base+'/events',201,token,command(2,'check',visit['id']))
                        correction={k:observation[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']}
                        correction.update(base_revision=1,notes='Corrected software fixture',change_reason='Synthetic revision')
                        call('D06 observation corrected','PUT','/api/farm/observations/'+visit['id'],201,token,correction)
                        detail=call('D06 recheck state','GET',base,200,token)['item']
                        expect('D06 revision change detected','observation_changed' in detail['check_status']['reasons'])
                        call('D06 stale evidence prevents close','POST',base+'/events',409,token,command(3,'close',resolution='followup_recorded'))
                        call('D06 recheck current revision','POST',base+'/events',201,token,command(3,'check',visit['id']))
                        closed=call('D06 close workflow','POST',base+'/events',201,token,command(4,'close',resolution='followup_recorded'))
                        expect('D06 closed is workflow only',closed['item']['state']=='closed' and not closed['item']['disease_confirmed'])
                        immutable=call('D06 original assessment unchanged','GET','/api/farm/assessments/'+assessment['id'],200,token)['item']
                        expect('D06 immutable snapshot bytes as JSON',immutable==assessment)
                        call('D07 other owner denied','GET',base,404,tokens[1])
                        call('D07 logout','POST','/api/auth/logout',200,token)
                        call('D07 revoked token denied','GET','/api/mobile/capabilities',401,token)
                finally:
                    server.shutdown();server.server_close();worker.join(timeout=10)
        sys.path.insert(0,str(ROOT.parent/'AEGIS-AI/temporal_warning'))
        from pipeline import build
        from fixtures import example
        replay=build(example('positive'))
        expect('D08 synthetic replay is not forecast',replay['source']=='synthetic' and not replay['training_performed']
            and replay['training_readiness']=='blocked_no_field_data' and replay['model_metrics'] is None)
        summary['temporal']=dict(source=replay['source'],rows=len(replay['rows']),training_readiness=replay['training_readiness'],model_metrics=None)
        summary['success']=True
    except Exception as exc:
        summary['error_type']=type(exc).__name__
    finally:
        summary.update(at_utc7=datetime.now(timezone(timedelta(hours=7))).isoformat(),
            server_stopped=worker is None or not worker.is_alive(),temporary_store_cleaned=store is None or not store.exists())
        summary['success']=summary['success'] and summary['server_stopped'] and summary['temporary_store_cleaned']
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:summary[k] for k in ['success','server_stopped','temporary_store_cleaned','checkpoint_loaded','training_performed']},indent=2))
    return 0 if summary['success'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    raise SystemExit(run(p.parse_args().out))
