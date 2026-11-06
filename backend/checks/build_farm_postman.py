"""Compose a farm/warning demo around the existing detection collection."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
collection=json.loads((ROOT/'postman/AEGIS.postman_collection.json').read_text(encoding='utf-8'))
collection['info']['name']='AEGIS Farm Warning MVP (mock + real V4)'
collection['info']['description']='Full local demo. Farm/telemetry are mock; image inference uses V4. Run on isolated DB. No calibrated disease prediction.'
collection['info'].pop('_postman_id',None)

def event(kind,code):
    return dict(listen=kind,script={'type':'text/javascript','exec':code.splitlines()})

def req(name,method,path,status,body=None,code='',before='',other=False):
    request=dict(method=method,header=[],url='{{base_url}}/api/farm'+path)
    if body is not None:
        request['header']=[dict(key='Content-Type',value='application/json')]
        request['body']=dict(mode='raw',raw=body if isinstance(body,str) else json.dumps(body),options={'raw':{'language':'json'}})
    if other:request['auth']={'type':'bearer','bearer':[{'key':'token','type':'string','value':'{{other_token}}'}]}
    tests=f"pm.test('HTTP {status}',()=>pm.response.to.have.status({status}));\n"+code
    events=[event('test',tests)]
    if before:events.insert(0,event('prerequest',before))
    return dict(name=name,request=request,event=events)

def store(key):return f"pm.environment.set('{key}',pm.response.json().item.id);"

setup=[
    req('F01 Create owned plot','POST','/plots',201,{'name':'Ruộng demo cảnh báo','location_text':'Dữ liệu mô phỏng'},store('plot_id')),
    req('F02 Create rice season','POST','/plots/{{plot_id}}/seasons',201,{'name':'Mùa vụ mock','start_date':'2026-10-01','end_date':'2026-12-31'},store('season_id')),
    req('F03 Register mock device','POST','/seasons/{{season_id}}/devices',201,{'name':'Thiết bị mock','device_code':'DEMO1','source':'mock'},store('device_id')),
    req('F04 Upload 24 hourly mock buckets','POST','/devices/{{device_id}}/telemetry',201,'{{telemetry_body}}',
        "pm.test('24 inserted',()=>pm.expect(pm.response.json().inserted).to.eql(24));",
        """const end=Date.parse('2026-10-24T00:00:00Z');
const records=Array.from({length:24},(_,i)=>({start_at:new Date(end-(24-i)*3600000).toISOString(),air_temperature_c:26,relative_humidity_pct:i>=18?95:70,leaf_wet:i>=18}));
pm.environment.set('telemetry_body',JSON.stringify({source:'mock',records}));"""),
    req('F05 Replay telemetry','POST','/devices/{{device_id}}/telemetry',200,'{{telemetry_body}}',
        "pm.test('Replay without new rows',()=>{pm.expect(pm.response.json().inserted).to.eql(0);pm.expect(pm.response.json().replayed).to.eql(24);});"),
    req('F06 Assess completed mock window','POST','/devices/{{device_id}}/assessments',201,{'as_of':'2026-10-24T00:00:00Z'},
        store('assessment_id')+"""
const a=pm.response.json().item;
pm.environment.set('assessment_snapshot',JSON.stringify(a));
pm.test('Explainable mock advisory',()=>{
 pm.expect(a.result.status).to.eql('advisory');pm.expect(a.result.longest_matching_run_hours).to.eql(6);
 pm.expect(a.result.is_mock).to.eql(true);pm.expect(a.result.field_validated).to.eql(false);
 pm.expect(a.result.forecast_horizon_hours).to.eql(null);pm.expect(a.result).not.to.have.property('probability');
 pm.expect(a.profile.duration_basis).to.include('demo assumption');
 pm.expect(a.plot_id).to.eql(pm.environment.get('plot_id'));pm.expect(a.season_id).to.eql(pm.environment.get('season_id'));
 pm.expect(a.result.profile_sha256).to.match(/^[0-9a-f]{64}$/);pm.expect(a.result.input_sha256).to.match(/^[0-9a-f]{64}$/);
 pm.expect(a.request_id).to.eql(pm.response.headers.get('X-Request-ID'));
});"""),
    req('F07 Replay immutable assessment','POST','/devices/{{device_id}}/assessments',200,{'as_of':'2026-10-24T00:00:00Z'},
        "pm.test('Same snapshot and replay header',()=>{pm.expect(pm.response.json().item).to.eql(JSON.parse(pm.environment.get('assessment_snapshot')));pm.expect(pm.response.headers.get('Idempotency-Replayed')).to.eql('true');});"),
    req('F08 Assessment detail','GET','/assessments/{{assessment_id}}',200,code="pm.test('Stored snapshot',()=>pm.expect(pm.response.json().item).to.eql(JSON.parse(pm.environment.get('assessment_snapshot'))));"),
    req('F09 Assessment history','GET','/devices/{{device_id}}/assessments',200,code="pm.test('One history item',()=>pm.expect(pm.response.json().pagination.total).to.eql(1));"),
    req('F10 Missing data is not low risk','POST','/devices/{{device_id}}/assessments',201,{'as_of':'2026-10-23T23:00:00Z'},
        "pm.test('Missing first hour',()=>{const d=pm.response.json().item.result;pm.expect(d.status).to.eql('insufficient_data');pm.expect(d.completeness.missing_buckets).to.have.length(1);});"),
    req('F11 Reject modified existing bucket','POST','/devices/{{device_id}}/telemetry',409,'{{conflict_body}}',
        "pm.test('Conflict',()=>pm.expect(pm.response.json().error.code).to.eql('telemetry_conflict'));",
        "const d=JSON.parse(pm.environment.get('telemetry_body'));d.records=d.records.slice(0,1);d.records[0].air_temperature_c=27;pm.environment.set('conflict_body',JSON.stringify(d));"),
    req('F12 Telemetry history','GET','/devices/{{device_id}}/telemetry?page_size=100',200,code="pm.test('24 synthetic records',()=>{pm.expect(pm.response.json().pagination.total).to.eql(24);pm.response.json().items.forEach(x=>pm.expect(x.quality).to.eql('synthetic'));});"),
    req('F13 Plot detail','GET','/plots/{{plot_id}}',200),
    req('F14 Season detail','GET','/seasons/{{season_id}}',200),
    req('F15 Device detail','GET','/devices/{{device_id}}',200),
]
link=[
    req('F16 Link V4 image check to warning','POST','/assessments/{{assessment_id}}/analyses',201,{'analysis_id':'{{analysis_id}}'}),
    req('F17 Replay image link','POST','/assessments/{{assessment_id}}/analyses',200,{'analysis_id':'{{analysis_id}}'}),
    req('F18 Linked image analyses','GET','/assessments/{{assessment_id}}/analyses',200,code="pm.test('Same V4 analysis',()=>{const x=pm.response.json();pm.expect(x.pagination.total).to.eql(1);pm.expect(x.items[0].analysis_id).to.eql(pm.environment.get('analysis_id'));pm.expect(x.items[0].model_sha256).to.eql(pm.environment.get('model_sha256'));});"),
    req('F19 Warning snapshot remains intact','GET','/assessments/{{assessment_id}}',200,code="pm.test('Image does not rewrite warning',()=>pm.expect(pm.response.json().item).to.eql(JSON.parse(pm.environment.get('assessment_snapshot'))));"),
]
foreign=[req('F20 Other user plot list empty','GET','/plots',200,other=True,code="pm.test('No foreign plots',()=>pm.expect(pm.response.json().items).to.eql([]));")]
for i,path in enumerate(['/plots/{{plot_id}}','/seasons/{{season_id}}','/devices/{{device_id}}',
                         '/devices/{{device_id}}/telemetry','/devices/{{device_id}}/assessments',
                         '/assessments/{{assessment_id}}','/assessments/{{assessment_id}}/analyses'],21):
    foreign.append(req(f'F{i} Other user denied {path}','GET',path,404,other=True))
foreign.append(req('F28 Other user cannot evaluate','POST','/devices/{{device_id}}/assessments',404,{},other=True))
items=[]
for original in collection['item']:
    item=copy.deepcopy(original)
    if item['name'].startswith('13 Detect'):
        item['event'][-1]['script']['exec'] += ["pm.test('V4 is still default',()=>{const d=pm.response.json();pm.expect(d.model_version).to.eql('aegis-yolo11n-v4-50epochs');pm.expect(d.model_sha256).to.eql('1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a');});"]
    items.append(item)
    if item['name'].startswith('07 Current'):items.extend(setup)
    if item['name'].startswith('14 Read'):items.extend(link)
    if item['name'].startswith('20 Login'):items.extend(foreign)
collection['item']=items
target=ROOT/'postman/AEGIS-Farm-Warning.postman_collection.json'
target.write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Created',target,'requests=',len(items))
