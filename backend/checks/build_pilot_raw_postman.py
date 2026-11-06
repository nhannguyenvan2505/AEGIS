"""Build a separate software-fixture pilot raw collection; never rewrite V4 artifacts."""
import argparse
import copy
import json
from pathlib import Path


def event(kind,code):return dict(listen=kind,script=dict(type='text/javascript',exec=code.splitlines()))


def collection():
    items=[]
    def request(name,method,path,status,body=None,tests='',auth=True):
        r=dict(method=method,header=[],url='{{base_url}}'+path)
        if not auth:r['auth']={'type':'noauth'}
        if body is not None:
            r['header']=[dict(key='Content-Type',value='application/json')]
            r['body']=dict(mode='raw',raw=body if isinstance(body,str) else json.dumps(body,ensure_ascii=False),options={'raw':{'language':'json'}})
        items.append(dict(name=name,request=r,event=[event('test',f"pm.test('HTTP {status}',()=>pm.response.to.have.status({status}));\n"+tests)]))
    request('01 Health - no model required','GET','/health',200,auth=False)
    setup="""const id=()=>pm.variables.replaceIn('{{$guid}}');
pm.collectionVariables.set('owner_email','raw-owner-'+id()+'@example.test');
pm.collectionVariables.set('other_email','raw-other-'+id()+'@example.test');
pm.collectionVariables.set('software_password','Software-fixture-'+id());
for(const key of ['synthetic_client','field_client','controlled_client']) pm.collectionVariables.set(key,id());
const now=Date.now();
pm.collectionVariables.set('season_start',new Date(now-10*86400000).toISOString().slice(0,10));
pm.collectionVariables.set('season_end',new Date(now+10*86400000).toISOString().slice(0,10));
pm.collectionVariables.set('sample_payload',JSON.stringify({records:[{client_sample_id:id(),observed_at:new Date(now-600000).toISOString(),air_temperature_c:26,relative_humidity_pct:95,leaf_wet:null,reported_quality:'unknown',reference:'SOFTWARE FIXTURE - not field evidence'}]}));"""
    items[0]['event'].insert(0,event('prerequest',setup))
    request('02 Register fixture owner','POST','/api/auth/register',201,dict(email='{{owner_email}}',password='{{software_password}}'),auth=False)
    request('03 Login fixture owner','POST','/api/auth/login',200,dict(email='{{owner_email}}',password='{{software_password}}'),"pm.collectionVariables.set('owner_token',pm.response.json().access_token);",auth=False)
    request('04 Create fixture plot','POST','/api/farm/plots',201,dict(name='SOFTWARE FIXTURE raw contract'),"pm.collectionVariables.set('plot_id',pm.response.json().item.id);")
    request('05 Create fixture season','POST','/api/farm/plots/{{plot_id}}/seasons',201,dict(name='SOFTWARE FIXTURE',start_date='{{season_start}}',end_date='{{season_end}}'),"pm.collectionVariables.set('season_id',pm.response.json().item.id);")
    base='/api/farm/seasons/{{season_id}}/environment-streams'
    meta=dict(client_stream_id='{{synthetic_client}}',name='SOFTWARE FIXTURE - not real measurements',source='synthetic',method='manual_reading',instrument='SOFTWARE FIXTURE - no device',reference='SOFTWARE FIXTURE',nominal_interval_seconds=None)
    request('06 Create synthetic fixture stream','POST',base,201,meta)
    field=dict(meta,source='field_observed',client_stream_id='{{field_client}}')
    request('07 Exercise field enum with software fixture','POST',base,201,field)
    controlled=dict(meta,source='controlled_experiment',client_stream_id='{{controlled_client}}',experiment_context=dict(
        schema_version='aegis-controlled-experiment-context-v1',setting='tray',unit_alias='SOFTWARE-FIXTURE-UNIT',batch_alias='SOFTWARE-FIXTURE-BATCH',
        shared_environment_cluster_alias='SOFTWARE-FIXTURE-CLUSTER',control_level='observational_setup',control_description='Software contract run only - no plants',
        uncontrolled_factors=['All conditions are simulated'],setup_reference='SOFTWARE FIXTURE',source_dossier_reference='SOFTWARE FIXTURE - unconfirmed',collection_permission_reference='SOFTWARE FIXTURE - not a real permission'))
    request('08 Create controlled fixture stream','POST',base,201,controlled,"""const d=pm.response.json();pm.collectionVariables.set('stream_id',d.item.id);
pm.test('Raw-only policy',()=>{pm.expect(d.item.training_approved).to.eql(false);const p=d.item.metadata.source_policy;pm.expect(p.raw_only).to.eql(true);for(const k of ['rule_input_approved','disease_labels_approved','field_evaluation_approved','training_approved'])pm.expect(p[k]).to.eql(false);});""")
    request('09 Retry same controlled create','POST',base,200,controlled,"pm.test('Same stream',()=>pm.expect(pm.response.json().item.id).to.eql(pm.collectionVariables.get('stream_id')));")
    conflict=copy.deepcopy(controlled);conflict['experiment_context']['batch_alias']='DIFFERENT-SOFTWARE-FIXTURE'
    request('10 Context conflict is not a rewrite','POST',base,409,conflict)
    for number,source in [(11,'controlled_experiment'),(12,'synthetic'),(13,'field_observed')]:
        request(f'{number:02} Filter {source}','GET',base+'?source='+source+'&page_size=1',200,tests=f"pm.test('Only selected source',()=>{{const d=pm.response.json();pm.expect(d.pagination.total).to.eql(1);pm.expect(d.items[0].metadata.source).to.eql('{source}');}});")
    sample='/api/farm/environment-streams/{{stream_id}}/samples'
    request('14 Import fixture point','POST',sample,201,'{{sample_payload}}',"pm.test('Point null and no hourly/train approval',()=>{const r=pm.response.json().items[0];pm.expect(r.payload.leaf_wet).to.eql(null);pm.expect(r.declared_source).to.eql('controlled_experiment');pm.expect(r.qc.hourly_eligible).to.eql(false);pm.expect(r.training_approved).to.eql(false);});")
    request('15 Retry fixture point','POST',sample,200,'{{sample_payload}}',"pm.test('Replay only',()=>{const d=pm.response.json();pm.expect(d.created).to.eql(0);pm.expect(d.replayed).to.eql(1);});")
    request('16 Source on sample is rejected','POST',sample,400,'{{mixed_payload}}')
    items[-1]['event'].insert(0,event('prerequest',"const p=JSON.parse(pm.collectionVariables.get('sample_payload'));p.records[0].source='field_observed';pm.collectionVariables.set('mixed_payload',JSON.stringify(p));"))
    request('17 Read points without mixing','GET',sample,200,tests="pm.test('Exactly one point',()=>pm.expect(pm.response.json().pagination.total).to.eql(1));")
    request('18 Register other fixture account','POST','/api/auth/register',201,dict(email='{{other_email}}',password='{{software_password}}'),auth=False)
    request('19 Login other fixture account','POST','/api/auth/login',200,dict(email='{{other_email}}',password='{{software_password}}'),"pm.collectionVariables.set('other_token',pm.response.json().access_token);",auth=False)
    request('20 Foreign source access denied','GET',sample,404)
    items[-1]['request']['auth']=dict(type='bearer',bearer=[dict(key='token',value='{{other_token}}',type='string')])
    request('21 Logout owner','POST','/api/auth/logout',200)
    request('22 Revoked owner token denied','GET',sample,401,tests="for(const k of ['owner_token','other_token','software_password','owner_email','other_email','sample_payload','mixed_payload'])pm.collectionVariables.unset(k);")
    return dict(info=dict(name='AEGIS Pilot Raw - software fixture only',schema='https://schema.getpostman.com/json/collection/v2.1.0/collection.json',description='Temporary pilot server with controlled raw opt-in. No checkpoint/inference. All three source enums here carry SOFTWARE FIXTURES, never disease/field evidence. Do not run against a real store or export resolved credentials.'),
                variable=[dict(key='base_url',value='http://127.0.0.1:REPLACE_WITH_TEMP_PORT')],auth=dict(type='bearer',bearer=[dict(key='token',value='{{owner_token}}',type='string')]),item=items)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'postman/AEGIS-Pilot-Raw.postman_collection.json');args=p.parse_args()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as f:json.dump(collection(),f,ensure_ascii=False,indent=2);f.write('\n')
    print('Built 22 software-fixture raw requests; no credentials or inference')


if __name__=='__main__':main()
