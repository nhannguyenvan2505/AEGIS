"""Extend the frozen farm collection; keep the original 57-request artifact."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=json.loads((ROOT/'postman/AEGIS-Farm-Warning.postman_collection.json').read_text(encoding='utf-8'))
source['info']['name']='AEGIS Cultivation Context (mock + real V4)'
source['info']['description']='Isolated local DB only. Versioned user-declared context; does not change warning rules.'
profile=dict(region='central',province_or_city='Tỉnh demo',locality='Địa bàn mô phỏng',rice_variety='Giống demo',
             planting_method='transplanted',sown_on='2026-09-20',transplanted_on='2026-10-05',season_status='active')
base='/api/farm/seasons/{{season_id}}/cultivation-profile'


def req(name,method,path,status,body=None,tests='',other=False):
    request=dict(method=method,header=[],url='{{base_url}}'+path)
    if body is not None:
        request['header']=[dict(key='Content-Type',value='application/json')]
        request['body']=dict(mode='raw',raw=json.dumps(body,ensure_ascii=False),options={'raw':{'language':'json'}})
    if other:request['auth']={'type':'bearer','bearer':[{'key':'token','type':'string','value':'{{other_token}}'}]}
    code=f"pm.test('HTTP {status}',()=>pm.response.to.have.status({status}));\n"+tests
    return dict(name=name,request=request,event=[dict(listen='test',script={'type':'text/javascript','exec':code.splitlines()})])


def edit(revision,variety,reason):return dict(base_revision=revision,profile=dict(profile,rice_variety=variety),change_reason=reason)


setup=[
 req('C01 Legacy context is unknown','GET',base,200,tests="pm.test('No invented planting date',()=>{pm.expect(pm.response.json().item).to.eql(null);pm.expect(pm.response.json().context_check.status).to.eql('incomplete');});"),
 req('C02 Record cultivation revision1','PUT',base,201,edit(0,'Giống demo','Khai báo ban đầu'),"pm.test('Revision and context only',()=>{const d=pm.response.json();pm.expect(d.item.revision).to.eql(1);pm.expect(d.context_check.status).to.eql('complete');pm.expect(d.context_check.agronomically_verified).to.eql(false);pm.expect(d.context_check.changes_warning_rule).to.eql(false);});"),
 req('C03 Read cultivation profile','GET',base,200,tests="pm.test('Transplant date is explicit',()=>pm.expect(pm.response.json().item.profile.transplanted_on).to.eql('2026-10-05'));"),
 req('C04 Retry same save','PUT',base,200,edit(0,'Giống demo','Khai báo ban đầu'),"pm.test('No duplicate revision',()=>{pm.expect(pm.response.json().item.revision).to.eql(1);pm.expect(pm.response.headers.get('Idempotency-Replayed')).to.eql('true');});"),
 req('C05 Correct declared variety','PUT',base,201,edit(1,'Giống đã đối chiếu sổ','Đối chiếu sổ ghi chép'),"pm.test('Revision2',()=>pm.expect(pm.response.json().item.revision).to.eql(2));"),
 req('C06 Reject stale edit','PUT',base,409,edit(1,'Ghi đè sai','Bản cũ'),"pm.test('Conflict code',()=>pm.expect(pm.response.json().error.code).to.eql('cultivation_revision_conflict'));"),
 req('C07 Cultivation history','GET',base+'/revisions',200,tests="pm.test('Descending immutable revisions',()=>{const d=pm.response.json();pm.expect(d.pagination.total).to.eql(2);pm.expect(d.items.map(x=>x.revision)).to.eql([2,1]);});"),
]
after_assessment=[
 req('C08 Update context after assessment','PUT',base,201,edit(2,'Giống sửa sau đánh giá','Bổ sung sau snapshot'),"pm.test('Revision3',()=>pm.expect(pm.response.json().item.revision).to.eql(3));"),
 req('C09 Read current revision3','GET',base,200,tests="pm.test('Current context differs from frozen assessment',()=>{pm.expect(pm.response.json().item.revision).to.eql(3);pm.expect(JSON.parse(pm.environment.get('assessment_snapshot')).cultivation_context.item.revision).to.eql(2);});"),
]
foreign=[req('C10 Other user cannot read context','GET',base,404,other=True),
         req('C11 Other user cannot read revisions','GET',base+'/revisions',404,other=True),
         req('C12 Other user cannot edit context','PUT',base,404,edit(3,'Foreign','Not owner'),other=True)]
items=[]
for original in source['item']:
    item=copy.deepcopy(original)
    if item['name'].startswith('F06 '):
        item['event'][-1]['script']['exec'] += ["pm.test('Frozen cultivation revision2 and correct age basis',()=>{const c=pm.response.json().item.cultivation_context;pm.expect(c.item.revision).to.eql(2);pm.expect(c.crop_age_days).to.eql(19);pm.expect(c.crop_age_basis).to.eql('transplanted_on');pm.expect(c.recorded_after_window_end).to.eql(true);});"]
    items.append(item)
    if item['name'].startswith('F02 '):items.extend(setup)
    if item['name'].startswith('F06 '):items.extend(after_assessment)
    if item['name'].startswith('F20 '):items.extend(foreign)
source['item']=items
target=ROOT/'postman/AEGIS-Cultivation.postman_collection.json'
target.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Created',target,'requests=',len(items))
