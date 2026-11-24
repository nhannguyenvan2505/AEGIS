'use strict';
// Existing owned resources only; choosing fills a form, never saves it.
const RECORD_PICKERS=new Map();
const observationLabel=v=>`${fmt(v.observed_at)} · ${FINDING[v.payload.finding]} · ${v.source} · bản ${v.revision} · ${v.id.slice(0,8)}`;
const activeObservation=v=>v.payload.record_status==='active';
const PICKER_CONFIGS=[
  {id:'followup-observation',form:'followup-form',title:'Chọn quan sát cho lần kiểm tra',kind:'observation',requires:'followup',context:()=>S.followup?.id,
    eligible:v=>activeObservation(v)&&v.source==='synthetic'&&Date.parse(v.observed_at)>=Date.parse(S.followup.episode_requirement?.window_end||S.followup.window_end)},
  {id:'survey-observation',form:'survey-event-form',title:'Chọn quan sát cho lịch đang mở',kind:'observation',requires:'surveyPlan',context:()=>S.surveyPlan?.id,
    eligible:v=>activeObservation(v)&&v.source===S.surveyPlan.metadata.source&&Date.parse(v.observed_at)>=Date.parse(S.surveyPlan.metadata.window_start)&&Date.parse(v.observed_at)<Date.parse(S.surveyPlan.metadata.window_end)},
  {id:'review-observation',form:'review-request-form',title:'Chọn quan sát cần xác minh',kind:'observation',requires:'season',context:()=>S.season,eligible:activeObservation},
  {id:'review-grant',form:'review-request-form',title:'Chọn quyền xác minh đã chấp thuận',kind:'grant',requires:'season',context:()=>S.season,eligible:v=>v.state==='active'},
  {id:'visit-image',form:'visit-form',title:'Chọn kết quả ảnh của bạn · tùy chọn',kind:'image',requires:'season',context:()=>S.season+':'+(S.visit?.id||'new'),eligible:()=>true}
];
function pickerContext(config){return S.token&&S.season&&config.context()?`${S.epoch}|${S.season}|${config.context()}`:null;}
function pickerLabel(config,row){
  if(config.kind==='observation')return observationLabel(row);
  if(config.kind==='grant')return `${row.metadata.reviewer_alias} · đã chấp thuận · bản ${row.version} · ${fmt(row.updated_at)} · ${row.id.slice(0,8)}`;
  return `${fmt(row.created_at)} · ${row.model_version} · ${row.status} · nguồn ảnh chưa xác minh · ${row.analysis_id.slice(0,8)}`;
}
function recordPicked(id,row){const p=RECORD_PICKERS.get(id);if(p)p.chosen.textContent=row?`Đang dùng: ${pickerLabel(p.config,row)}. Chưa tự lưu biểu mẫu.`:'Chưa chọn bản ghi.';}
function invalidateRecordPickers(...ids){for(const id of ids){const p=RECORD_PICKERS.get(id);if(!p)continue;p.context=null;p.rows.clear();p.select.replaceChildren();p.pager.replaceChildren();p.chosen.textContent='Chưa chọn bản ghi.';}}
function resetRecordPickers(){invalidateRecordPickers(...RECORD_PICKERS.keys());}
function pickerListPath(config,page){
  const base=config.kind==='image'?'/api/disease/analyses':`${FAR}/seasons/${S.season}/${config.kind==='grant'?'review-grants':'observations'}`;
  return `${base}?page=${page}&page_size=10`;
}
async function loadRecordPicker(id,page=1){
  const p=RECORD_PICKERS.get(id),config=p.config,context=pickerContext(config);
  if(!context)throw new Error('Mở đúng mùa vụ và công việc trước khi chọn bản ghi.');
  const data=await api(pickerListPath(config,page));if(context!==pickerContext(config))return;
  p.context=context;p.rows=new Map(data.items.filter(config.eligible).map(v=>[config.kind==='image'?v.analysis_id:v.id,v]));
  p.select.replaceChildren(node('option','— Chọn bản ghi trên trang này —'));p.select.firstChild.value='';
  for(const [key,row] of p.rows){const option=node('option',pickerLabel(config,row));option.value=key;p.select.append(option);}
  p.pager.replaceChildren();const prev=node('button','Trang trước','secondary'),next=node('button','Trang sau','secondary');prev.type=next.type='button';
  prev.dataset.pageBlocked=String(page<=1);next.dataset.pageBlocked=String(!data.pagination.has_next);
  prev.onclick=()=>run(()=>loadRecordPicker(id,page-1));next.onclick=()=>run(()=>loadRecordPicker(id,page+1));
  p.pager.append(prev,node('span',`Trang ${page}/${data.pagination.total_pages||1} · ${p.rows.size} bản ghi phù hợp trên trang này`),next);
  message(p.rows.size?'Chọn bản ghi rồi bấm dùng lựa chọn; thao tác này chưa lưu.':'Trang này chưa có bản ghi phù hợp. Có thể xem trang khác hoặc tạo bản ghi mới.');
}
function fillPickedRecord(config,row){
  const f=$(config.form);
  if(config.kind==='image')f.elements.namedItem('analysis_id').value=row.analysis_id;
  else if(config.kind==='grant')f.elements.namedItem('grant_id').value=row.id;
  else{f.elements.namedItem('observation_id').value=row.id;if(config.form==='review-request-form'){f.elements.namedItem('source_revision').value=row.revision;f.elements.namedItem('payload_sha256').value=row.payload_sha256;}}
  recordPicked(config.id,row);
}
async function applyRecordPicker(id){
  const p=RECORD_PICKERS.get(id),config=p.config,context=pickerContext(config),row=p.rows.get(p.select.value);
  if(!context||context!==p.context||!row)throw new Error('Tải lại danh sách và chọn bản ghi trong đúng bối cảnh.');
  const key=config.kind==='image'?row.analysis_id:row.id;
  const path=config.kind==='image'?`/api/disease/analyses/${key}`:`${FAR}/${config.kind==='grant'?'review-grants':'observations'}/${key}`;
  const data=await api(path);if(context!==pickerContext(config))return;const current=config.kind==='image'?data:data.item;
  if(!config.eligible(current)||(config.kind==='observation'&&(current.revision!==row.revision||current.payload_sha256!==row.payload_sha256))||(config.kind==='grant'&&current.version!==row.version)){
    invalidateRecordPickers(id);throw new Error('Bản ghi đã đổi hoặc không còn phù hợp. Tải lại để xem bản hiện tại; biểu mẫu chưa được thay lựa chọn.');
  }
  fillPickedRecord(config,current);message('Đã điền lựa chọn và phiên bản đã xem. Kiểm tra lý do rồi lưu biểu mẫu khi bạn sẵn sàng.');
}
function clearPickedRecord(config){
  const f=$(config.form);f.elements.namedItem(config.kind==='image'?'analysis_id':config.kind==='grant'?'grant_id':'observation_id').value='';
  if(config.id==='review-observation'){f.elements.namedItem('source_revision').value='';f.elements.namedItem('payload_sha256').value='';}
  recordPicked(config.id,null);message('Đã bỏ lựa chọn khỏi biểu mẫu; chưa sửa dữ liệu đã lưu.');
}
for(const config of PICKER_CONFIGS){
  const box=node('div',undefined,'assessment');box.id=config.id+'-picker';const label=node('label',config.title),select=node('select');select.id=config.id+'-select';select.setAttribute('aria-label',config.title);label.append(select);
  const load=node('button','Tải danh sách để chọn','secondary'),apply=node('button','Dùng lựa chọn này','secondary'),clear=node('button','Bỏ lựa chọn','secondary');
  for(const b of [load,apply,clear]){b.type='button';b.dataset.requires=config.requires;}
  load.onclick=()=>run(()=>loadRecordPicker(config.id));apply.onclick=()=>run(()=>applyRecordPicker(config.id));clear.onclick=()=>clearPickedRecord(config);
  const chosen=node('p','Chưa chọn bản ghi.','small'),pager=node('div',undefined,'pager');box.append(label,load,apply,clear,chosen,pager);$(config.form).prepend(box);
  RECORD_PICKERS.set(config.id,{config,select,apply,rows:new Map(),context:null,chosen,pager});select.onchange=()=>controls();
}
const recordPickerControls=controls;
controls=function(){recordPickerControls();for(const p of RECORD_PICKERS.values())p.apply.disabled=S.busy||!p.rows.has(p.select.value)||p.context!==pickerContext(p.config);};
resetRecordPickers();controls();
for(const [form,field,title] of [
  ['followup-form','observation_id','Quan sát đã chọn · mã tham chiếu'],['survey-event-form','observation_id','Quan sát gắn lịch · mã tham chiếu'],
  ['review-request-form','observation_id','Quan sát cần xác minh · mã tham chiếu'],['review-request-form','grant_id','Quyền đã chọn · mã tham chiếu'],
  ['visit-form','analysis_id','Ảnh đang dùng · mã tham chiếu, có thể để trống']]){
  const input=$(form).elements.namedItem(field);input.readOnly=true;if(input.parentElement?.firstChild?.nodeType===3)input.parentElement.firstChild.textContent=title;
}
for(const field of ['source_revision','payload_sha256'])$('review-request-form').elements.namedItem(field).readOnly=true;
