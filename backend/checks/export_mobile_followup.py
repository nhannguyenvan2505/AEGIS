"""Export a synthetic follow-up slice over real local HTTP, then clean its store.

Fixtures contain software-only business payloads, never auth payloads/tokens.
This is not a long-running mobile host, a dataset or a new service.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import threading
import uuid

import requests
from werkzeug.serving import make_server, WSGIRequestHandler

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND));sys.path.insert(0,str(BACKEND.parent/'frontend'))
from pilot_app import create_pilot_app
import test_followup

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass

def export(out):
    out=Path(out).absolute();out.mkdir(parents=True,exist_ok=False)
    f=test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
    server=worker=None;http=requests.Session();http.trust_env=False
    records=[];checks=[];failure=None;root=None;scenarios_verified=[]
    def expect(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    try:
        f.setUp();root=f.root
        f.app=create_pilot_app(root,'http://127.0.0.1:9');f.app.config['FARM_WRITE_LIMIT']=500
        f.client=f.app.test_client();case=f.create()
        path='/api/farm/follow-ups/'+case['id'];season='/api/farm/seasons/'+f.season['id']
        aliases={case['id']:'case_id',f.season['id']:'season_id',f.visit['id']:'observation_id',
                 f.a['id']:'assessment_id',f.device:'device_id'}
        scenario='check_conditions'
        server=make_server('127.0.0.1',0,f.app,threaded=True,request_handler=QuietHandler)
        worker=threading.Thread(target=server.serve_forever);worker.start()
        base='http://127.0.0.1:'+str(server.server_port)
        def call(name,method,url,status,body=None,owner=0):
            headers=f.headers[owner] if owner is not None else {}
            response=http.request(method,base+url,headers=headers,json=body,timeout=10)
            expect(name+' HTTP'+str(status),response.status_code==status)
            data=response.json();rid=response.headers.get('X-Request-ID')
            expect(name+' request ID',str(uuid.UUID(rid))==rid)
            if status>=400:expect(name+' error ID',data.get('request_id')==rid)
            expect(name+' private response',response.headers.get('Cache-Control')=='private, no-store'
                   and 'Authorization' in response.headers.get('Vary',''))
            template=url
            for identifier,alias in aliases.items():template=template.replace(identifier,'{'+alias+'}')
            records.append(dict(step=len(records)+1,name=name,scenario=scenario,
                request=dict(method=method,path=url,path_template=template,
                    auth_context='missing' if owner is None else 'owner' if owner==0 else 'other_owner',body=body),
                response=dict(status=status,headers={k:response.headers[k] for k in
                    ['X-Request-ID','Cache-Control','Vary','Retry-After'] if k in response.headers},body=data)))
            return data
        caps=call('pilot capabilities','GET','/api/mobile/capabilities',200)
        expect('pilot mock available; no AI/worker/raw write',caps['mode']=='pilot' and caps['follow_up']['available']
            and caps['follow_up']['source']=='mock' and not caps['mock_automation_process_enabled']
            and not caps['controlled_experiment_raw_write'] and caps['image_detection']['service_status']=='not_checked')
        listing=call('owned list','GET',season+'/follow-ups',200)
        expect('one owned case',len(listing['items'])==1 and listing['items'][0]['id']==case['id'])
        call('open detail','GET',path,200)
        view=call('required and current','GET',path+'/assessment-view',200)
        schema=json.loads((BACKEND/'docs/MOBILE_FOLLOWUP.schema.json').read_text(encoding='utf-8'))
        expect('composition required keys',set(schema['required'])<=set(view))
        expect('assessmentView required keys',set(schema['$defs']['assessmentView']['required'])<=set(view['item']))
        for key in ['required','current']:
            expect(key+' required keys',set(schema['$defs']['assessmentVersion']['required'])<=set(view['item'][key]))
        def projection(value,observation_required,ack_enabled,check_enabled,needs_recheck):
            item=value['item'];p=item['action_capabilities'];label=scenario+' projection v'+str(item['followup_version'])
            expect(label+' required keys',set(schema['$defs']['actionCapabilities']['required'])<=set(p))
            expect(label+' version and scope',p['projection_version']=='aegis-followup-actions-v1'
                and p['validation_scope']=='workflow_state_and_declared_inputs' and p['base_version']==item['followup_version'])
            expect(label+' only chosen actions',set(p['actions'])=={'acknowledge','check'})
            expect(label+' action eligibility',p['actions']['acknowledge']['enabled']==ack_enabled
                and p['actions']['check']['enabled']==check_enabled)
            for action in p['actions'].values():
                expect(label+' disabled reason',action['disabled_reasons']==([] if action['enabled'] else ['workflow_state_not_allowed']))
            check=p['actions']['check'];constraints=check['observation_constraints']
            expect(label+' observation inputs',check['observation_required']==observation_required
                and constraints['source']=='synthetic' and constraints['record_status']=='active'
                and constraints['same_owner_and_season'] and not constraints['selection_validated']
                and constraints['observed_at_not_before']==item['required']['snapshot']['result']['window_end'])
            expect(label+' recheck state',p['needs_recheck']==needs_recheck)
            return p
        projection(view,True,True,False,True)
        expect('required current v1 same and unverified',view['item']['required']['id']==f.a['id']
            and view['item']['current']['id']==f.a['id'] and not view['item']['disease_confirmed']
            and not view['item']['training_approved'])
        def command(version,action,observation=None,resolution=None):
            return dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,
                reason='Synthetic mobile integration fixture',observation_id=observation,resolution=resolution)
        ack=command(1,'acknowledge')
        first=call('acknowledge','POST',path+'/events',201,ack)
        replay=call('exact acknowledge replay','POST',path+'/events',200,ack)
        expect('same event on replay',first['event']['id']==replay['event']['id'])
        stale=call('stale workflow','POST',path+'/events',409,command(1,'check',f.visit['id']))
        expect('stale code',stale['error']['code']=='followup_version_conflict')
        call('refresh detail','GET',path,200)
        projection(call('refresh assessment view','GET',path+'/assessment-view',200),True,False,True,True)
        call('refresh events','GET',path+'/events',200)
        call('available synthetic observation','GET',season+'/observations',200)
        missing=call('check_conditions rejects missing observation','POST',path+'/events',400,command(2,'check'))
        expect('observation requirement enforced at POST',missing['error']['code']=='invalid_followup')
        checked=call('check observation revision1','POST',path+'/events',201,command(2,'check',f.visit['id']))
        expect('checked version3',checked['item']['state']=='checked' and checked['item']['version']==3)
        correction={k:f.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']}
        correction.update(base_revision=1,notes='Corrected synthetic fixture',change_reason='Software-only revision2')
        call('fixture-only observation correction','PUT','/api/farm/observations/'+f.visit['id'],201,correction)
        changed=call('refresh detects changed observation','GET',path,200)
        expect('requires recheck',changed['item']['check_status']['needs_recheck']
               and 'observation_changed' in changed['item']['check_status']['reasons'])
        changed_projection=projection(call('refresh required current after correction','GET',path+'/assessment-view',200),True,False,True,True)
        expect('projection reports observation changed','observation_changed' in changed_projection['recheck_reasons'])
        blocked=call('close blocked by changed evidence','POST',path+'/events',409,
            command(3,'close',resolution='followup_recorded'))
        expect('close blocked code',blocked['error']['code']=='followup_observation_changed')
        rechecked=call('check observation revision2','POST',path+'/events',201,command(3,'check',f.visit['id']))
        expect('recheck current state',rechecked['item']['version']==4 and not rechecked['item']['check_status']['needs_recheck'])
        events=call('immutable event history','GET',path+'/events',200)
        old_check=next(e for e in events['items'] if e['version']==3)
        expect('old check keeps revision1',old_check['payload']['observation_snapshot']['revision']==1)
        expect('no duplicated ack',len([e for e in events['items'] if e['payload']['action']=='acknowledge'])==1)
        call('final checked detail','GET',path,200)
        original=call('original assessment remains immutable','GET','/api/farm/assessments/'+f.a['id'],200)
        expect('original assessment unchanged',original['item']==f.a)
        projection(call('final check_conditions action projection','GET',path+'/assessment-view',200),True,False,True,False)
        scenarios_verified.append('check_conditions')

        scenario='check_data'
        data_assessment=call('fixture seed insufficient-data assessment','POST',
            '/api/farm/devices/'+f.device+'/assessments',201,
            dict(as_of=(test_followup.END-timedelta(hours=24)).isoformat()))['item']
        aliases[data_assessment['id']]='data_assessment_id'
        expect('insufficient-data seed is mock',data_assessment['result']['status']=='insufficient_data'
            and data_assessment['input']['source']=='mock')
        data_case=call('fixture seed data followup','POST','/api/farm/assessments/'+data_assessment['id']+'/follow-up',201,
            dict(reason='Synthetic data-quality follow-up'))['item']
        aliases[data_case['id']]='data_case_id';data_path='/api/farm/follow-ups/'+data_case['id']
        expect('data task kind',data_case['task_kind']=='check_data')
        projection(call('open check_data action projection','GET',data_path+'/assessment-view',200),False,True,False,True)
        call('acknowledge check_data','POST',data_path+'/events',201,command(1,'acknowledge'))
        projection(call('acknowledged check_data action projection','GET',data_path+'/assessment-view',200),False,False,True,True)
        data_check=call('check_data without observation','POST',data_path+'/events',201,command(2,'check'))
        expect('check_data records no observation',data_check['event']['payload']['observation_snapshot'] is None
            and data_check['item']['version']==3 and data_check['item']['state']=='checked')
        projection(call('checked check_data action projection','GET',data_path+'/assessment-view',200),False,False,True,False)
        data_events=call('check_data event history','GET',data_path+'/events',200)
        expect('check_data has only create ack check',len(data_events['items'])==3)
        final_listing=call('both task types in season list','GET',season+'/follow-ups',200)
        expect('two case kinds retained',len(final_listing['items'])==2
            and {r['task_kind'] for r in final_listing['items']}=={'check_conditions','check_data'})
        scenarios_verified.append('check_data')
        scenario='session_and_owner_boundaries'
        call('other owner denied','GET',path,404,owner=1)
        call('missing token denied','GET',path,401,owner=None)
        call('logout','POST','/api/auth/logout',200)
        call('revoked token denied','GET',path,401)
        secrets=[h['Authorization'] for h in f.headers]+[h['Authorization'].split()[1] for h in f.headers]+['journal-test-password-123']
        serialized=json.dumps(records,ensure_ascii=False)
        expect('no auth credential exported',not any(value in serialized for value in secrets))
        (out/'http_fixtures.json').write_text(serialized+'\n',encoding='utf-8')
        (out/'fixture_context.json').write_text(json.dumps(dict(
            kind='synthetic_software_only_not_field_or_ground_truth',
            seed='Existing FollowupTests fixture via Flask test client; slice requests over real HTTP',
            contract_version='aegis-mobile-followup-v1',
            fixture_version='aegis-mobile-followup-fixture-v2',projection_version='aegis-followup-actions-v1',
            ids=dict(case_id=case['id'],season_id=f.season['id'],observation_id=f.visit['id'],assessment_id=f.a['id'],
                data_case_id=data_case['id'],data_assessment_id=data_assessment['id'],device_id=f.device),
            scenarios_verified=scenarios_verified,
            fixture_clock='Historical synthetic October 2026; expired display window is intentional',
            server_is_stopped_after_export=True,live_credentials_exported=False,
            fixtures_are_not_live_api_resource_ids=True,
            schema_check_level='required-key subset only; not a full JSON Schema engine'),
            ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc)
        raise
    finally:
        http.close()
        if server:
            server.shutdown();server.server_close()
        if worker:worker.join(10)
        f.doCleanups()
        summary=dict(at_utc7=datetime.now(timezone(timedelta(hours=7))).isoformat(),
            success=failure is None,error=failure,requests=len(records),checks=len(checks),
            passed_checks=checks,server_stopped=worker is None or not worker.is_alive(),
            temporary_store_cleaned=root is None or not root.exists(),
            no_model_loaded=not any(k in sys.modules for k in ['torch','ultralytics']),
            scenarios_verified=scenarios_verified,projection_version='aegis-followup-actions-v1',
            native_verified=False,client_scope_accepted=False)
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k!='passed_checks'},ensure_ascii=False,indent=2))
        if failure is None and (not summary['server_stopped'] or not summary['temporary_store_cleaned']):
            raise RuntimeError('Owned fixture resources did not clean up')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New output directory only')
    export(parser.parse_args().out)
