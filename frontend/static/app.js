'use strict';
// Session stays in memory. No storage, external resources, tokens in URLs or logs.
const $ = id => document.getElementById(id);
const S = {token:null,epoch:0,busy:false,plot:null,season:null,device:null,assessment:null,analysis:null,file:null,key:null,cultivation:null,visit:null,visitKey:null,intervention:null,interventionKey:null,followup:null,followupKey:null,timelineAsOf:null,timelineFilters:null};
const P = {};
const FAR='/api/farm';
const END='2026-10-24T00:00:00Z';
const STATUS={advisory:'Có mẫu điều kiện trong mô phỏng — cần quan sát ruộng',no_pattern_detected:'Không khớp mẫu demo trong cửa sổ này',insufficient_data:'Chưa đủ dữ liệu'};
const fmt=t=>new Intl.DateTimeFormat('vi-VN',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Ho_Chi_Minh'}).format(new Date(t));
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function message(text,error=false){$('feedback').textContent=text;$('feedback').classList.toggle('error',error);}
function controls(){
  const needs={plot:S.plot,season:S.season,device:S.device,file:S.file,link:S.analysis&&S.assessment,visit:S.visit,intervention:S.intervention,surveyPlan:S.surveyPlan,coverage:S.coverage,reviewAction:S.reviewAllowed,reviewImage:S.reviewItem?.image_url,followup:S.followup,automationJob:S.automationJob,followupSource:S.assessment&&['advisory','insufficient_data'].includes(S.assessment.result.status)};
  document.querySelectorAll('button,select,input,textarea').forEach(e=>{e.disabled=S.busy||Boolean(e.dataset.requires&&!needs[e.dataset.requires])||Boolean(S.visit&&e.closest('#visit-form')&&['source','observed_at','scheduled'].includes(e.name))||Boolean(S.intervention&&e.closest('#intervention-form')&&['source','at'].includes(e.name));});
}
function clearImage(){S.analysis=null;$('image-result').replaceChildren(node('p','Chưa có kết quả ảnh. Không có detection không xác nhận cây khỏe.'));const c=$('image-canvas');c.width=1;c.height=1;c.hidden=true;}
function resetMonitor(){S.assessment=null;S.assessmentBaseId=null;S.assessmentHeadId=null;['assessment','telemetry','assessments','linked','telemetry-pages','assessments-pages','linked-pages'].forEach(id=>$(id).replaceChildren());$('assessment').append(node('p','Chọn thiết bị và đánh giá để xem kết quả.'));}
function clearSession(){
  S.epoch++;S.token=null;S.userId=null;S.plot=null;S.season=null;S.device=null;S.file=null;S.key=null;
  Object.keys(P).forEach(k=>delete P[k]);
  ['plot-select','season-select','device-select','plots-pages','seasons-pages','devices-pages','analyses','analyses-pages'].forEach(id=>$(id).replaceChildren());
  document.querySelectorAll('form').forEach(f=>f.reset());resetMonitor();clearImage();resetCultivation();resetJournal();
  $('workspace').hidden=true;$('auth-panel').hidden=false;$('logout').hidden=true;$('user-label').textContent='Chưa đăng nhập';
}
async function api(path,{method='GET',body,headers={},raw=false,auth=true}={}){
  const epoch=S.epoch;
  const h={...headers};if(auth&&S.token)h.Authorization='Bearer '+S.token;
  if(body!==undefined&&!(body instanceof FormData)){body=JSON.stringify(body);h['Content-Type']='application/json';}
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),90000);
  try{
    const r=await fetch(path,{method,body,headers:h,signal:controller.signal,cache:'no-store',credentials:'omit'});
    if(epoch!==S.epoch)throw new Error('Phiên đã thay đổi; bỏ kết quả cũ.');
    if(!r.ok){
      let d;try{d=await r.json();}catch{d={};}
      if(r.status===401&&auth){clearSession();throw new Error('Phiên không còn hợp lệ. Vui lòng đăng nhập lại.');}
      const retry=r.headers.get('Retry-After');
      const error=new Error(`${d.error?.message||'Không thể hoàn tất yêu cầu.'} [${r.status} · ${d.error?.code||'http_error'}]${retry?' · Thử lại sau '+retry+' giây.':''}${d.request_id?' · Request '+d.request_id:''}`);
      error.status=r.status;error.code=d.error?.code;throw error;
    }
    return raw?await r.blob():await r.json();
  }catch(e){if(e.name==='AbortError')throw new Error('Yêu cầu hết thời gian chờ. Không tự gửi lại. Với nhận diện, kiểm tra lịch sử trước khi tạo tác vụ mới.');throw e;}
  finally{clearTimeout(timeout);}
}
async function run(fn){if(S.busy)return;S.busy=true;controls();message('Đang xử lý…');try{await fn();}catch(e){message(e.message||'Không thể kết nối Backend.',true);}finally{S.busy=false;controls();}}
function pages(key,meta,load){
  P[key]=meta;
  const host=$(key+'-pages');host.replaceChildren();
  const prev=node('button','← Trước','secondary'),next=node('button','Sau →','secondary');
  prev.type=next.type='button';
  prev.onclick=()=>run(()=>load(meta.page-1));next.onclick=()=>run(()=>load(meta.page+1));
  // Mark limits separately so global busy state cannot re-enable boundary buttons.
  prev.dataset.pageBlocked=String(meta.page<=1);next.dataset.pageBlocked=String(!meta.has_next);
  host.append(prev,node('span',`Trang ${meta.page}/${meta.total_pages||1} · ${meta.total} mục`),next);
}
const originalControls=controls;
controls=function(){originalControls();document.querySelectorAll('[data-page-blocked="true"]').forEach(e=>e.disabled=true);};
function options(id,rows,selected){
  const host=$(id);const prior=Array.from(host.options).find(o=>o.value===selected)?.textContent;
  host.replaceChildren(node('option','— Chọn —'));host.firstChild.value='';
  rows.forEach(r=>{const o=node('option',r.name);o.value=r.id;host.append(o);});
  // Keep the active context visible while browsing a different list page.
  if(selected&&!rows.some(r=>r.id===selected)){const o=node('option',prior||'Bối cảnh đang chọn');o.value=selected;host.append(o);}
  host.value=selected||'';
}
async function loadPlots(page=1,selected=S.plot){
  const d=await api(`${FAR}/plots?page=${page}`);options('plot-select',d.items,selected);pages('plots',d.pagination,p=>loadPlots(p));
}
async function loadSeasons(page=1,selected=S.season){
  if(!S.plot)return;
  const d=await api(`${FAR}/plots/${S.plot}/seasons?page=${page}`);options('season-select',d.items,selected);pages('seasons',d.pagination,p=>loadSeasons(p));
}
async function loadDevices(page=1,selected=S.device){
  if(!S.season)return;
  const d=await api(`${FAR}/seasons/${S.season}/devices?page=${page}`);options('device-select',d.items,selected);pages('devices',d.pagination,p=>loadDevices(p));
}
function resetChildren(level){
  resetCultivation();
  resetJournal();
  if(level==='plot'){S.season=null;options('season-select',[],null);$('seasons-pages').replaceChildren();}
  S.device=null;options('device-select',[],null);$('devices-pages').replaceChildren();resetMonitor();
}
async function login(register=false){
  if(!$('auth-form').reportValidity())return;
  const body={email:$('email').value,password:$('password').value};
  try{
    if(register)await api('/api/auth/register',{method:'POST',body,auth:false});
    const d=await api('/api/auth/login',{method:'POST',body,auth:false});S.token=d.access_token;
    const me=await api('/api/auth/me');S.userId=me.user.id;
    $('user-label').textContent=me.user.email;$('logout').hidden=false;$('auth-panel').hidden=true;$('workspace').hidden=false;
    await loadPlots();await loadAnalyses();await loadResearchInbox();await loadAutomationStatus();message('Đã đăng nhập. Chọn ruộng hoặc tạo bối cảnh demo mới.');
  }finally{$('password').value='';body.password='';}
}
$('auth-form').onsubmit=e=>{e.preventDefault();run(()=>login());};
$('register').onclick=()=>run(()=>login(true));
$('logout').onclick=()=>run(async()=>{try{await api('/api/auth/logout',{method:'POST'});clearSession();message('Đã thu hồi phiên và xóa dữ liệu hiển thị.');}catch(e){clearSession();throw new Error('Đã xóa phiên trên giao diện; chưa xác nhận thu hồi trên server. '+e.message);}});
$('plot-select').onchange=()=>run(async()=>{S.plot=$('plot-select').value||null;resetChildren('plot');await loadSeasons();message('Đã đổi ruộng; chọn mùa vụ.');});
$('season-select').onchange=()=>run(async()=>{S.season=$('season-select').value||null;resetChildren('season');await loadDevices();await loadCultivation();await loadVisits();await loadInterventions();await loadFollowups();await loadTimeline();await loadResearch();await loadAutomationJobs();await loadWarningDashboard();message('Đã đổi mùa vụ; chọn thiết bị.');});
$('device-select').onchange=()=>run(async()=>{S.device=$('device-select').value||null;resetMonitor();if(S.device)await refreshMonitor();message('Đã tải bối cảnh thiết bị.');});
// Busy controls are disabled before the handler runs. FormData omits disabled
// controls, so read the explicitly named text/date fields instead.
function formBody(id){return Object.fromEntries(Array.from($(id).elements).filter(e=>e.name).map(e=>[e.name,e.value]));}
for(const kind of ['plot','season','device'])$(kind+'-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const body=formBody(kind+'-form');
  const path=kind==='plot'?'/plots':kind==='season'?`/plots/${S.plot}/seasons`:`/seasons/${S.season}/devices`;
  if(kind==='season'&&!body.end_date)body.end_date=null;
  if(kind==='device')body.source='mock';
  const d=await api(FAR+path,{method:'POST',body});
  S[kind]=d.item.id;
  if(kind==='plot'){resetChildren('plot');await loadPlots(1,S.plot);await loadSeasons();}
  else if(kind==='season'){resetChildren('season');await loadSeasons(1,S.season);await loadDevices();await loadCultivation();await loadVisits();await loadInterventions();await loadFollowups();await loadTimeline();await loadResearch();await loadAutomationJobs();await loadWarningDashboard();}
  else{await loadDevices(1,S.device);resetMonitor();await refreshMonitor();}
  $(kind+'-form').reset();message('Đã tạo '+({plot:'ruộng',season:'mùa vụ',device:'thiết bị mock'}[kind])+'.');
});};
const CONTEXT_LABELS={region:'vùng trồng',province_or_city:'tỉnh/thành phố',rice_variety:'giống lúa',planting_method:'hình thức gieo/cấy',planting_date:'ngày gieo/cấy',sown_on:'ngày gieo',transplanted_on:'ngày cấy',season_status:'trạng thái mùa vụ'};
const PROFILE_LABELS={central:'Miền Trung',southern:'Miền Nam',other:'Vùng khác',unknown:'Chưa xác định',direct_seeded:'Gieo sạ trực tiếp',transplanted:'Cấy',planned:'Dự kiến',active:'Đang canh tác',completed:'Đã kết thúc',archived:'Lưu trữ'};
function resetCultivation(){
  S.cultivation=null;$('cultivation-form').reset();$('cultivation-version').textContent='Chưa chọn mùa vụ';
  $('cultivation-check').textContent='Chọn mùa vụ để khai báo hoặc xem hồ sơ.';
  ['cultivation-history','cultivation-pages','cultivation-revision-detail'].forEach(id=>$(id).replaceChildren());
}
function profileDescription(item){
  const p=item.profile;
  return `Bản ${item.revision} · ${PROFILE_LABELS[p.region]} · ${p.province_or_city||'Chưa rõ tỉnh/thành'} · Giống: ${p.rice_variety||'chưa biết'} · ${PROFILE_LABELS[p.planting_method]} · ${PROFILE_LABELS[p.season_status]}`;
}
async function loadCultivationHistory(page=1){
  if(!S.season)return;
  const d=await api(`${FAR}/seasons/${S.season}/cultivation-profile/revisions?page=${page}`);
  $('cultivation-history').replaceChildren();
  d.items.forEach(item=>{const b=node('button',`${profileDescription(item)} · ${fmt(item.created_at)}`);b.type='button';b.onclick=()=>{
    const p=item.profile,details=node('div',undefined,'assessment');
    details.append(node('h3',`Bản ghi hồ sơ ${item.revision} · chỉ xem`),node('p',profileDescription(item),'small'),node('p',`Ngày gieo: ${p.sown_on||'chưa biết'} · Ngày cấy: ${p.transplanted_on||'chưa biết'} · Địa bàn: ${p.locality||'chưa ghi'}`,'small'),node('p','Lý do: '+item.change_reason,'small'),node('pre',`SHA-256: ${item.profile_sha256}\nRequest gốc: ${item.request_id}`,'hashes'));
    $('cultivation-revision-detail').replaceChildren(details);
  };$('cultivation-history').append(b);});
  if(!d.items.length)$('cultivation-history').append(node('p','Chưa có bản hồ sơ; dữ liệu cũ không được tự điền.','small'));
  pages('cultivation',d.pagination,loadCultivationHistory);
}
async function loadCultivation(){
  if(!S.season)return;
  const d=await api(`${FAR}/seasons/${S.season}/cultivation-profile`);S.cultivation=d.item;
  $('cultivation-form').reset();
  if(d.item)Object.entries(d.item.profile).forEach(([key,value])=>{const input=$('cultivation-form').elements.namedItem(key);if(input)input.value=value??'';});
  $('cultivation-version').textContent=d.item?'Phiên bản '+d.item.revision:'Chưa có hồ sơ';
  $('cultivation-check').textContent=d.context_check.status==='complete'?'Đã đủ trường bối cảnh. Đây là khai báo của người dùng, chưa xác minh chuyên môn và chưa thay đổi quy tắc cảnh báo.':'Còn thiếu: '+d.context_check.missing_fields.map(k=>CONTEXT_LABELS[k]||k).join(', ')+'. Có thể lưu bản chưa đầy đủ; không tự đoán dữ liệu.';
  $('cultivation-revision-detail').replaceChildren();await loadCultivationHistory();
}
$('cultivation-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.season)return;
  const values=formBody('cultivation-form');const reason=values.change_reason;delete values.change_reason;
  for(const key of ['province_or_city','locality','rice_variety','sown_on','transplanted_on'])if(!values[key])values[key]=null;
  await api(`${FAR}/seasons/${S.season}/cultivation-profile`,{method:'PUT',body:{base_revision:S.cultivation?.revision||0,profile:values,change_reason:reason}});
  await loadCultivation();message('Đã lưu hồ sơ. Đánh giá cũ giữ nguyên hồ sơ đã chụp; không tự tính lại cảnh báo.');
});};
$('cultivation-refresh').onclick=()=>run(async()=>{await loadCultivation();message('Đã tải bản hồ sơ hiện tại.');});
const FINDING={uncertain:'Chưa kết luận',absent:'Không ghi nhận dấu hiệu đạo ôn lá trong lần thăm',present:'Ghi nhận dấu hiệu đạo ôn lá'};
function resetVisit(){if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('visit-image');S.visit=null;S.visitKey=null;$('visit-form').reset();$('visit-title').textContent='Ghi lần quan sát mới';['visit-metadata','visit-revisions','visit-revisions-pages','visit-revision-detail'].forEach(id=>$(id).replaceChildren());}
function resetJournal(){if(typeof resetRecordPickers==='function')resetRecordPickers();resetAutomation();if(typeof resetResearch==='function')resetResearch();resetTimeline();resetFollowup();resetManagement();resetVisit();['visits','visits-pages'].forEach(id=>$(id).replaceChildren());}
function localInput(t){const d=new Date(Date.parse(t)+7*3600000);return d.toISOString().slice(0,16);}
function showVisit(item){
  if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('visit-image');
  S.visit=item;S.visitKey=item.id;const form=$('visit-form');form.reset();
  for(const k of ['source','scheduled'])form.elements.namedItem(k).value=String(item[k]);
  form.elements.namedItem('observed_at').value=localInput(item.observed_at);
  for(const k of ['finding','notes','record_status','analysis_id'])form.elements.namedItem(k).value=item.payload[k]??'';
  const r=item.payload.review;form.elements.namedItem('has_review').value=r?'true':'false';
  if(r){form.elements.namedItem('reviewer_alias').value=r.reviewer_alias;form.elements.namedItem('reviewed_at').value=localInput(r.reviewed_at);form.elements.namedItem('reference').value=r.reference;}
  $('visit-title').textContent=`Bổ sung lần ghi · phiên bản ${item.revision}`;
  $('visit-metadata').textContent=`Quan sát: ${fmt(item.observed_at)} · Nhập / available: ${fmt(item.available_at)} · ${item.source} · ${r?'Có khai báo xác minh ngoài hệ thống':'Chưa xác minh'} · Chưa phê duyệt nhãn train. Request: ${item.request_id}`;
}
async function loadVisits(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/observations?page=${page}`);$('visits').replaceChildren();
  d.items.forEach(v=>{const b=node('button',`${fmt(v.observed_at)} · ${FINDING[v.payload.finding]} · ${v.source} · bản ${v.revision}${v.payload.record_status==='voided'?' · Đã thu hồi':''}`);b.onclick=()=>run(()=>openVisit(v.id));$('visits').append(b);});
  if(!d.items.length)$('visits').append(node('p','Chưa có lần quan sát. Không tự tạo dữ liệu thực địa.','small'));
  pages('visits',d.pagination,loadVisits);
}
async function visitRevisions(page=1){
  if(!S.visit)return;const d=await api(`${FAR}/observations/${S.visit.id}/revisions?page=${page}`);$('visit-revisions').replaceChildren();
  d.items.forEach(v=>{const b=node('button',`Bản ${v.revision} · ${fmt(v.recorded_at)} · ${FINDING[v.payload.finding]}`);b.onclick=()=>{
    const box=node('div',undefined,'assessment');box.append(node('h3',`Phiên bản ${v.revision} · chỉ xem`),node('p',FINDING[v.payload.finding]),node('p',v.payload.notes),node('p','Lý do: '+v.change_reason,'small'),node('pre',`SHA-256: ${v.payload_sha256}\nRequest: ${v.request_id}\nAvailable: ${v.available_at}\n${v.payload.review?'Có khai báo xác minh ngoài hệ thống; nền tảng chưa kiểm chứng.':'Chưa xác minh.'}`,'hashes'));$('visit-revision-detail').replaceChildren(box);
  };$('visit-revisions').append(b);});pages('visit-revisions',d.pagination,visitRevisions);
}
async function openVisit(id){const d=await api(`${FAR}/observations/${id}`);showVisit(d.item);await visitRevisions();message('Đã mở nhật ký. Thời điểm/nguồn lần thăm giữ nguyên; sửa bằng phiên bản mới.');}
$('visit-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.season)return;const v=formBody('visit-form');
  const review=v.has_review==='true'?{reviewer_alias:v.reviewer_alias,reviewed_at:v.reviewed_at?v.reviewed_at+':00+07:00':'',reference:v.reference}:null;
  const payload={finding:v.finding,notes:v.notes,analysis_id:v.analysis_id.trim()||null,review,record_status:v.record_status,change_reason:v.change_reason};
  let d;
  if(S.visit)d=await api(`${FAR}/observations/${S.visit.id}`,{method:'PUT',body:{...payload,base_revision:S.visit.revision}});
  else{S.visitKey=S.visitKey||crypto.randomUUID();d=await api(`${FAR}/seasons/${S.season}/observations`,{method:'POST',body:{...payload,client_visit_id:S.visitKey,source:v.source,observed_at:v.observed_at+':00+07:00',scheduled:v.scheduled==='true'}});}
  showVisit(d.item);await loadVisits();await visitRevisions();message('Đã lưu nhật ký. Xác minh tự khai báo chưa là nhãn bệnh được hệ thống phê duyệt.');
});};
$('visit-new').onclick=()=>{resetVisit();controls();message('Nhập một lần quan sát mới; bản cũ vẫn được giữ.');};
$('visit-reload').onclick=()=>run(()=>openVisit(S.visit.id));
$('visits-refresh').onclick=()=>run(async()=>{await loadVisits();message('Đã tải danh sách quan sát.');});
const INTERVENTION_KIND={fungicide:'Thuốc trừ nấm',fertilizer:'Bón phân',irrigation:'Tưới / quản lý nước',other:'Việc khác'};
function resetIntervention(){S.intervention=null;S.interventionKey=null;$('intervention-form').reset();$('intervention-title').textContent='Ghi can thiệp mới';['intervention-metadata','intervention-revisions','intervention-revisions-pages','intervention-revision-detail'].forEach(id=>$(id).replaceChildren());}
function resetManagement(){resetIntervention();['interventions','interventions-pages'].forEach(id=>$(id).replaceChildren());}
function showIntervention(item){
  S.intervention=item;S.interventionKey=item.id;const f=$('intervention-form');f.reset();
  f.elements.namedItem('source').value=item.source;f.elements.namedItem('at').value=localInput(item.at);
  for(const k of ['kind','action_details','notes','record_status'])f.elements.namedItem(k).value=item.payload[k];
  $('intervention-title').textContent=`Sửa can thiệp · phiên bản ${item.revision}`;
  $('intervention-metadata').textContent=`Thực hiện: ${fmt(item.at)} · Nhập / available: ${fmt(item.available_at)} · ${item.source} · Tự khai báo, chưa xác minh. Request: ${item.request_id}`;
}
async function loadInterventions(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/interventions?page=${page}`);$('interventions').replaceChildren();
  d.items.forEach(v=>{const b=node('button',`${fmt(v.at)} · ${INTERVENTION_KIND[v.payload.kind]} · ${v.payload.action_details} · ${v.source} · bản ${v.revision}${v.payload.record_status==='voided'?' · Đã thu hồi':''}`);b.onclick=()=>run(()=>openIntervention(v.id));$('interventions').append(b);});
  if(!d.items.length)$('interventions').append(node('p','Chưa ghi nhận can thiệp. Chưa xác định mức độ đầy đủ của nhật ký.','small'));
  pages('interventions',d.pagination,loadInterventions);
}
async function interventionRevisions(page=1){
  if(!S.intervention)return;const d=await api(`${FAR}/interventions/${S.intervention.id}/revisions?page=${page}`);$('intervention-revisions').replaceChildren();
  d.items.forEach(v=>{const b=node('button',`Bản ${v.revision} · ${fmt(v.recorded_at)} · ${INTERVENTION_KIND[v.payload.kind]} · ${v.payload.record_status}`);b.onclick=()=>{
    const box=node('div',undefined,'assessment');box.append(node('h3',`Can thiệp phiên bản ${v.revision} · chỉ xem`),node('p',v.payload.action_details),node('p',v.payload.notes),node('p','Lý do: '+v.change_reason),node('pre',`SHA-256: ${v.payload_sha256}\nRequest: ${v.request_id}\nAvailable: ${v.available_at}`,'hashes'));$('intervention-revision-detail').replaceChildren(box);
  };$('intervention-revisions').append(b);});pages('intervention-revisions',d.pagination,interventionRevisions);
}
async function openIntervention(id){const d=await api(`${FAR}/interventions/${id}`);showIntervention(d.item);await interventionRevisions();message('Đã mở can thiệp. Sai nguồn hoặc thời điểm: thu hồi rồi tạo lần ghi mới.');}
$('intervention-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.season)return;const v=formBody('intervention-form');const p={kind:v.kind,action_details:v.action_details,notes:v.notes,record_status:v.record_status,change_reason:v.change_reason};let d;
  if(S.intervention)d=await api(`${FAR}/interventions/${S.intervention.id}`,{method:'PUT',body:{...p,base_revision:S.intervention.revision}});
  else{S.interventionKey=S.interventionKey||crypto.randomUUID();d=await api(`${FAR}/seasons/${S.season}/interventions`,{method:'POST',body:{...p,client_intervention_id:S.interventionKey,source:v.source,at:v.at+':00+07:00'}});}
  showIntervention(d.item);await loadInterventions();await interventionRevisions();message('Đã lưu can thiệp và thời điểm nhập. Chưa xác nhận nhật ký đầy đủ, không tự cập nhật cảnh báo cũ.');
});};
$('intervention-new').onclick=()=>{resetIntervention();controls();message('Ghi một can thiệp mới; giữ lịch sử cũ.');};
$('intervention-reload').onclick=()=>run(()=>openIntervention(S.intervention.id));
$('interventions-refresh').onclick=()=>run(async()=>{await loadInterventions();message('Đã tải danh sách can thiệp.');});
const FOLLOWUP_STATE={open:'Cần xử lý',acknowledged:'Đã xem · chờ kiểm tra',checked:'Đã ghi kết quả kiểm tra',closed:'Đã kết thúc công việc'};
const FOLLOWUP_ACTION={create:'Tạo mục',acknowledge:'Xác nhận đã xem',check:'Ghi kết quả kiểm tra',close:'Kết thúc công việc',reopen:'Mở lại theo dõi'};
const RECHECK_REASON={check_not_recorded:'Chưa ghi kiểm tra.',check_not_recorded_after_reopen:'Cần kiểm tra sau lần mở lại.',assessment_changed:'Có đánh giá mới chưa được kiểm tra.',observation_required:'Cần quan sát từ cuối cửa sổ yêu cầu mới nhất.',observation_unavailable:'Không còn tìm thấy quan sát hợp lệ.',observation_voided:'Quan sát dùng lần trước đã bị thu hồi; chọn quan sát active khác.',observation_changed:'Quan sát đã có phiên bản mới; mở lại quan sát và ghi kiểm tra lại.'};
function showCheckStatus(host,c){
  const status=c.check_status;if(!status)return;
  if(status.needs_recheck){host.append(node('p',status.reasons.map(r=>RECHECK_REASON[r]||r).join(' ')));if(c.state==='closed')host.append(node('p','Công việc vẫn đã đóng; thay đổi bằng chứng không tự mở lại. Xem đợt đang mở trước khi quyết định xử lý tiếp.'));else if(c.state==='checked')host.append(node('p','Cần ghi kiểm tra lại trước khi kết thúc; lịch sử lần kiểm tra cũ được giữ.'));}
  const o=status.observation;if(o)host.append(node('p',`Quan sát ${o.visit_id} · đã kiểm bản ${o.checked_revision} · hiện tại ${o.current_revision===null?'không có':`bản ${o.current_revision} · ${o.current_record_status==='active'?'đang sử dụng':'đã thu hồi'}`}`));
}
function resetFollowup(){S.followup=null;S.followupKey=null;$('followup-form').reset();['followups','followups-pages','followup-summary','followup-events','followup-events-pages'].forEach(id=>$(id).replaceChildren());}
async function loadFollowups(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/follow-ups?page=${page}`);$('followups').replaceChildren();
  d.items.forEach(c=>{const b=node('button',`${FOLLOWUP_STATE[c.state]} · ${c.task_kind==='check_data'?'Kiểm tra dữ liệu':'Kiểm tra điều kiện'} · ${fmt(c.window_end)} · ${c.display_freshness==='expired'?'Bản lịch sử':'Trong hạn hiển thị'} · mock`);b.onclick=()=>run(()=>openFollowup(c.id));$('followups').append(b);});
  if(!d.items.length)$('followups').append(node('p','Chưa có mục theo dõi; tạo từ đánh giá mô phỏng cần kiểm tra.','small'));pages('followups',d.pagination,loadFollowups);
}
function showFollowup(c){
  if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('followup-observation');
  S.followup=c;$('followup-form').reset();
  $('followup-summary').textContent=`${FOLLOWUP_STATE[c.state]} · bản ${c.version} · ${c.task_kind==='check_data'?'Kiểm tra dữ liệu thiếu':'Theo dõi điều kiện mô phỏng'} · ${c.display_freshness==='expired'?'Đánh giá đã qua hạn hiển thị; trạng thái công việc vẫn giữ':'Trong hạn hiển thị kỹ thuật'} · Assessment ${c.assessment_id}`;
  const action={open:'acknowledge',acknowledged:'check',checked:'close',closed:'reopen'}[c.state];const o=node('option',FOLLOWUP_ACTION[action]);o.value=action;$('followup-action').replaceChildren(o);if(c.state==='checked'){const recheck=node('option','Ghi kiểm tra lại theo đánh giá / quan sát hiện tại');recheck.value='check';$('followup-action').append(recheck);if(c.check_status?.needs_recheck)$('followup-action').value='check';}if(c.episode_requirement)$('followup-summary').append(node('p',`Đợt theo dõi: yêu cầu v${c.episode_requirement.revision} · Assessment ${c.episode_requirement.assessment_id} · cần kiểm tra từ ${fmt(c.episode_requirement.window_end)} trở đi. Đánh giá gốc giữ nguyên.`));showCheckStatus($('followup-summary'),c);
}
async function followupEvents(page=1){
  if(!S.followup)return;const d=await api(`${FAR}/follow-ups/${S.followup.id}/events?page=${page}`);$('followup-events').replaceChildren();
  d.items.forEach(e=>{const box=node('div',undefined,'assessment');box.append(node('h3',`Bước ${e.version} · ${FOLLOWUP_ACTION[e.payload.action]} · ${fmt(e.recorded_at)}`),node('p',e.payload.reason));
    const v=e.payload.observation_snapshot;if(v)box.append(node('p',`Quan sát ${v.visit_id} · bản ${v.revision} · ${FINDING[v.finding]} · ${v.source} · xác minh tự khai báo; chưa duyệt train`,'small'));
    if(e.payload.resolution)box.append(node('p',e.payload.resolution==='referred_for_review'?'Chuyển xem xét chuyên môn; chưa xác nhận đã có người tiếp nhận.':'Đã ghi nhận việc theo dõi; không xác nhận cây khỏe.','small'));
    box.append(node('pre',`Event ${e.id}\nSHA-256 ${e.payload_sha256}\nRequest ${e.request_id}`,'hashes'));$('followup-events').append(box);
  });pages('followup-events',d.pagination,followupEvents);
}
async function openFollowup(id){const d=await api(`${FAR}/follow-ups/${id}`);showFollowup(d.item);await followupEvents();message('Đã mở công việc theo dõi; không thay kết luận bệnh hoặc cảnh báo cũ.');}
$('followup-create').onclick=()=>run(async()=>{if(S.assessment.assessment_revision){const v=await api(`${FAR}/assessment-versions/${S.assessment.id}/follow-up`);if(!v.case_id)throw new Error('Bản bổ sung chưa có công việc cần xử lý.');await openFollowup(v.case_id);return;}let d=await api(`${FAR}/assessments/${S.assessment.id}/follow-up`);if(!d.item)d=await api(`${FAR}/assessments/${S.assessment.id}/follow-up`,{method:'POST',body:{reason:'Theo dõi đánh giá mô phỏng từ giao diện'}});showFollowup(d.item);await loadFollowups();await followupEvents();message('Đã tạo / mở theo dõi. Công việc và đánh giá điều kiện có trạng thái riêng.');});
$('followups-refresh').onclick=()=>run(()=>loadFollowups());
$('followup-reload').onclick=()=>run(()=>openFollowup(S.followup.id));
$('followup-use-visit').onclick=()=>{$('followup-form').elements.namedItem('observation_id').value=S.visit.id;if(typeof recordPicked==='function')recordPicked('followup-observation',S.visit);message('Đã điền mã quan sát đang mở; server sẽ kiểm tra nguồn, mùa vụ và thời điểm.');};
$('followup-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.followup)return;const v=formBody('followup-form');
  const command={base_version:S.followup.version,action:v.action,reason:v.reason,observation_id:v.action==='check'?v.observation_id.trim()||null:null,resolution:v.action==='close'?v.resolution:null};
  const fingerprint=JSON.stringify([S.followup.id,command]);if(S.followupKey?.fingerprint!==fingerprint)S.followupKey={fingerprint,key:crypto.randomUUID()};
  const body={...command,client_event_id:S.followupKey.key};
  let d;try{d=await api(`${FAR}/follow-ups/${S.followup.id}/events`,{method:'POST',body});}catch(error){if(['episode_recheck_required','followup_observation_changed','followup_version_conflict'].includes(error.code)){await openFollowup(S.followup.id);await loadWarningDashboard();}throw error;}S.followupKey=null;showFollowup(d.item);await loadFollowups();await followupEvents();await loadWarningDashboard();message('Đã lưu bước xử lý và lịch sử; kết quả bệnh không tự thay đổi.');
});};
const TIMELINE_KIND={assessment_version:'Đánh giá bổ sung',survey_plan:'Lịch khảo sát',coverage:'Đối soát can thiệp',review_request:'Yêu cầu / quyết định xác minh',review_grant:'Quyền xem xác minh',assessment:'Đánh giá điều kiện',followup:'Xử lý theo dõi',observation:'Quan sát bệnh',intervention:'Can thiệp',cultivation:'Hồ sơ canh tác',environment:'Số đo gốc',environment_exclusion:'Loại số đo',mock_telemetry:'Bucket IoT mô phỏng',image:'Ảnh đã gắn'};
function resetTimeline(){S.timelineAsOf=null;S.timelineFilters=null;$('timeline-form').reset();['timeline-events','timeline-pages','timeline-cutoff'].forEach(id=>$(id).replaceChildren());}
function timelineDescription(e){
  const d=e.detail;
  if(['survey_plan','coverage','review_request','review_grant'].includes(e.kind))return researchTimelineDescription(e);
  if(['assessment','assessment_version'].includes(e.kind))return STATUS[d.status]||d.status;
  if(e.kind==='followup')return `${FOLLOWUP_ACTION[d.action]} · ${d.reason}`;
  if(e.kind==='observation')return `${FINDING[d.finding]} · ${d.record_status==='voided'?'Đã thu hồi':'Bản ghi đang sử dụng tại phiên bản này'} · ${d.verification==='confirmed'?'Có khai báo xác minh ngoài hệ thống':'Chưa xác minh'}`;
  if(e.kind==='intervention')return `${INTERVENTION_KIND[d.kind]} · ${d.action_details} · ${d.record_status==='voided'?'Đã thu hồi':'Bản ghi đang sử dụng tại phiên bản này'}`;
  if(e.kind==='cultivation')return `${PROFILE_LABELS[d.region]} · Giống ${d.rice_variety||'chưa rõ'} · ${PROFILE_LABELS[d.planting_method]}`;
  if(e.kind==='image')return `${d.status==='no_detection'?'Không có detection · chưa kết luận khỏe':'Kết quả ảnh cần xem chi tiết'} · ${d.model_version} · nguồn ảnh chưa xác minh`;
  if(e.kind==='environment_exclusion')return d.reason;
  const p=e.kind==='environment'?d.payload:d;
  return `${p.air_temperature_c??'chưa đo'} °C · RH ${p.relative_humidity_pct??'chưa đo'}% · Lá ướt: ${p.leaf_wet===null?'chưa đo':p.leaf_wet?'có':'không'}${e.kind==='environment'?' · QC '+d.qc.status+(d.excluded_at?' · Đã đánh dấu loại tại cutoff':''):' · dữ liệu mô phỏng theo giờ'}`;
}
async function loadTimeline(page=1){
  if(!S.season)return;
  if(!S.timelineFilters)S.timelineFilters=formBody('timeline-form');
  const q=new URLSearchParams({page:String(page),kind:S.timelineFilters.kind,axis:S.timelineFilters.axis});
  for(const key of ['from','to'])if(S.timelineFilters[key])q.set(key,S.timelineFilters[key]+':00+07:00');
  if(S.timelineAsOf)q.set('as_of',S.timelineAsOf);
  const d=await api(`${FAR}/seasons/${S.season}/timeline?${q}`);S.timelineAsOf=d.as_of;
  $('timeline-cutoff').textContent=`Thông tin đã ghi nhận đến ${fmt(d.as_of)} · UTC+7. Đang xem ${d.axis==='occurred_at'?'thời điểm sự việc':'thời điểm ghi nhận'}; bấm lấy mới nhất để cập nhật.`;
  $('timeline-events').replaceChildren();
  d.items.forEach(e=>{const box=node('article',undefined,'timeline-event');box.append(node('h3',`${TIMELINE_KIND[e.kind]}${e.revision?' · bản / bước '+e.revision:''}`),node('p',timelineDescription(e)),node('p',`Sự việc: ${fmt(e.occurred_at)} · Ghi nhận: ${fmt(e.recorded_at)} · Nguồn: ${e.source}`,'small'));
    const actions={survey_plan:async()=>openSurvey((await api(`${FAR}/survey-plans/${e.reference_id}`)).item),coverage:async()=>openCoverage((await api(`${FAR}/intervention-coverage/${e.reference_id}`)).item),review_request:async()=>openResearchReview((await api(`${FAR}/review-requests/${e.reference_id}`)).item),review_grant:async()=>openResearchReview((await api(`${FAR}/review-grants/${e.reference_id}`)).item),followup:()=>openFollowup(e.reference_id),observation:()=>openVisit(e.reference_id),intervention:()=>openIntervention(e.reference_id),image:()=>openAnalysis(e.reference_id)};
    const target={survey_plan:'surveillance',coverage:'surveillance',review_request:'review-inbox',review_grant:'review-inbox',followup:'followup',observation:'journal',intervention:'management',image:'vision'}[e.kind];
    if(actions[e.kind]){const b=node('button','Mở bản hiện tại / chi tiết liên quan','secondary');b.onclick=()=>run(async()=>{await actions[e.kind]();$(target).scrollIntoView({behavior:'smooth',block:'start'});});box.append(b);}
    if(['assessment','assessment_version'].includes(e.kind)){const b=node('button','Mở đánh giá đã lưu','secondary');b.onclick=()=>run(async()=>{const baseId=e.detail.base_assessment_id||e.reference_id;const a=await api(`${FAR}/assessments/${baseId}`);S.device=a.item.device_id;await loadDevices(1,S.device);await selectAssessment(baseId,e.reference_id);$('monitor').scrollIntoView({behavior:'smooth',block:'start'});});box.append(b);}
    $('timeline-events').append(box);
  });
  if(!d.items.length)$('timeline-events').append(node('p','Không có sự kiện phù hợp tại cutoff/bộ lọc này. Không suy ra ruộng không có bệnh hoặc không can thiệp.','small'));
  pages('timeline',d.pagination,loadTimeline);
}
$('timeline-form').onsubmit=e=>{e.preventDefault();run(async()=>{S.timelineFilters=formBody('timeline-form');S.timelineAsOf=null;await loadTimeline();message('Đã lọc timeline; mỗi bản sửa là một sự kiện riêng.');});};
$('timeline-refresh').onclick=()=>run(async()=>{S.timelineAsOf=null;await loadTimeline();message('Đã lấy snapshot timeline mới nhất.');});
function resetAutomation(){resetWarningDashboard();S.automationJob=null;S.automationKeys={};['automation-jobs','automation-jobs-pages','automation-selected','automation-run-result','automation-runs','automation-runs-pages','automation-controls','automation-controls-pages'].forEach(id=>$(id).replaceChildren());$('automation-status').textContent='Đăng nhập để xem trạng thái worker.';$('automation-create-form').reset();$('automation-control-form').reset();}
function automationKey(slot,id,body){const signature=JSON.stringify([id,body]);S.automationKeys=S.automationKeys||{};if(S.automationKeys[slot]?.signature!==signature)S.automationKeys[slot]={signature,id:crypto.randomUUID()};return S.automationKeys[slot].id;}
async function loadAutomationStatus(){if(!S.token)return;const d=await api(`${FAR}/automation/status`);const a=d.automation;$('automation-status').textContent=`Launcher: ${a.enabled?'cho phép mock automation':'chưa bật mock automation'} · Worker: ${a.worker_running?'đang chạy':'đang dừng'} · Kiểm tra mỗi ${a.poll_seconds} giây · Poll gần nhất: ${a.last_poll_at?fmt(a.last_poll_at):'chưa có'}${a.last_error_code?' · Lỗi: '+a.last_error_code:''}. Đổi launcher bằng --enable-mock-automation; tắt riêng job không dừng công việc đã nhận.`;}
async function loadAutomationJobs(page=1){
  if(!S.season)return;await loadAutomationStatus();const d=await api(`${FAR}/seasons/${S.season}/automation-jobs?page=${page}`);$('automation-jobs').replaceChildren();
  d.items.forEach(j=>{const b=node('button',`${j.name} · ${j.enabled?'Job bật':'Job tắt'} · ${j.profile.version}${j.profile_matches_runtime?'':' · Cấu hình runtime đã khác'}`);b.onclick=()=>run(()=>openAutomationJob(j.id));$('automation-jobs').append(b);});if(!d.items.length)$('automation-jobs').append(node('p','Chưa có job. Worker không tự đăng ký thiết bị thay người dùng.','small'));pages('automation-jobs',d.pagination,loadAutomationJobs);
}
async function loadAutomationRuns(page=1){
  if(!S.automationJob)return;const d=await api(`${FAR}/automation-jobs/${S.automationJob.id}/runs?page=${page}`);$('automation-runs').replaceChildren();
  d.items.forEach(r=>{const v=r.result,current=r.current_assessment||v?.current_assessment,box=node('div',undefined,'assessment');box.append(node('h3',`${fmt(r.window_end)} · ${r.status} · ${r.attempt_count} lần thử`));
    if(v)box.append(node('p',v.skip_reason?'Bỏ qua: '+v.skip_reason:`${STATUS[v.assessment_status]||v.assessment_status} · Dữ liệu: ${v.freshness?.status||'chưa rõ'} · Snapshot giữ nguyên`));
    if(current)box.append(node('p',`Hiện hành v${current.revision}: ${STATUS[current.snapshot.result.status]} · gốc v1 giữ nguyên.`));if(r.error_code)box.append(node('p','Lỗi: '+r.error_code));if(r.input_changes.length)box.append(node('p',`Đã phát hiện ${r.input_changes.length} đầu vào thay đổi sau snapshot; bản bổ sung được lưu riêng khi hợp lệ, không tự đóng mục cũ.`));
    r.attempts.forEach(a=>box.append(node('p',`Lần ${a.number} · ${a.trigger} · ${a.status} · ${fmt(a.started_at)} · Request ${a.request_id}`,'small')));
    if(v?.assessment_id){const b=node('button','Mở đánh giá của lượt chạy','secondary');b.onclick=()=>run(async()=>{const a=await api(`${FAR}/assessments/${v.assessment_id}`);S.device=a.item.device_id;await loadDevices(1,S.device);await selectAssessment(v.assessment_id);$('monitor').scrollIntoView({behavior:'smooth'});});box.append(b);}
    if(current?.followup_id||v?.followup_id){const b=node('button','Mở công việc theo dõi','secondary');b.onclick=()=>run(async()=>{await openFollowup(current?.followup_id||v.followup_id);$('followup').scrollIntoView({behavior:'smooth'});});box.append(b);}$('automation-runs').append(box);
  });if(!d.items.length)$('automation-runs').append(node('p','Chưa có lượt đánh giá.','small'));pages('automation-runs',d.pagination,loadAutomationRuns);
}
async function loadAutomationControls(page=1){if(!S.automationJob)return;const d=await api(`${FAR}/automation-jobs/${S.automationJob.id}/controls?page=${page}`);$('automation-controls').replaceChildren();d.items.forEach(e=>$('automation-controls').append(node('p',`Bản ${e.version} · ${e.command.enabled?'Bật':'Tắt'} · ${fmt(e.created_at)} · ${e.command.reason}`)));pages('automation-controls',d.pagination,loadAutomationControls);}
async function openAutomationJob(id){const d=await api(`${FAR}/automation-jobs/${id}`);S.automationJob=d.item;$('automation-control-form').reset();$('automation-control-form').elements.namedItem('enabled').value=String(d.item.enabled);$('automation-selected').textContent=`${d.item.name} · bản ${d.item.version} · ${d.item.enabled?'Bật':'Tắt'} · SHA-256 quy tắc ${d.item.profile_sha256} · thiết bị ${d.item.device_id}`;await loadAutomationRuns();await loadAutomationControls();await loadAutomationStatus();}
$('automation-create-form').onsubmit=e=>{e.preventDefault();run(async()=>{const v=formBody('automation-create-form');v.enabled=v.enabled==='true';const d=await api(`${FAR}/devices/${S.device}/automation-jobs`,{method:'POST',body:{...v,client_job_id:automationKey('create',S.device,v)}});delete S.automationKeys.create;$('automation-create-form').reset();await loadAutomationJobs();await openAutomationJob(d.item.id);message('Đã lưu lựa chọn job. Chỉ chạy khi cả launcher và job được bật.');});};
$('automation-control-form').onsubmit=e=>{e.preventDefault();run(async()=>{if(!S.automationJob)return;const v=formBody('automation-control-form');const body={base_version:S.automationJob.version,enabled:v.enabled==='true',reason:v.reason};const d=await api(`${FAR}/automation-jobs/${S.automationJob.id}`,{method:'PUT',body:{...body,client_event_id:automationKey('control',S.automationJob.id,body)}});delete S.automationKeys.control;await loadAutomationJobs();await openAutomationJob(d.item.id);message('Đã lưu bật/tắt; không xóa đánh giá hoặc mục theo dõi cũ.');});};
$('automation-run').onclick=()=>run(async()=>{const d=await api(`${FAR}/automation-jobs/${S.automationJob.id}/run`,{method:'POST',body:{}});$('automation-run-result').textContent=`${d.item.status} · ${d.item.replayed?'Đọc lại cửa sổ đã xử lý':'Lượt xử lý mới'}${d.item.input_changed_after_snapshot?' · Đầu vào đã đổi sau snapshot; giữ kết quả cũ':''}${d.item.current_scope_issue?' · Cần kiểm tra: '+d.item.current_scope_issue:''}`;await loadAutomationRuns();await loadFollowups();await loadAutomationStatus();await loadWarningDashboard();message('Đã kiểm tra cửa sổ giờ hiện tại; dữ liệu vẫn là mock.');});
$('automation-refresh').onclick=()=>run(async()=>{await loadAutomationStatus();await loadAutomationJobs();if(S.automationJob)await openAutomationJob(S.automationJob.id);message('Đã làm mới lịch sử automation.');});
$('automation-open-refresh').onclick=()=>run(()=>openAutomationJob(S.automationJob.id));
async function loadTelemetry(page=1){
  const d=await api(`${FAR}/devices/${S.device}/telemetry?page=${page}`);$('telemetry').replaceChildren();
  d.items.forEach(r=>{const tr=node('tr');[fmt(r.start_at),r.air_temperature_c+' °C',r.relative_humidity_pct+' %',r.leaf_wet?'Có':'Không',r.quality].forEach(v=>tr.append(node('td',v)));$('telemetry').append(tr);});
  pages('telemetry',d.pagination,loadTelemetry);
}
async function loadAssessments(page=1){
  const d=await api(`${FAR}/devices/${S.device}/assessments?page=${page}`);$('assessments').replaceChildren();
  d.items.forEach(a=>{const b=node('button',`${fmt(a.result.window_end)} · v1: ${STATUS[a.result.status]||a.result.status} · mở để xem bản hiện hành`);b.type='button';b.onclick=()=>run(()=>selectAssessment(a.id));$('assessments').append(b);});
  if(!d.items.length)$('assessments').append(node('p','Chưa có đánh giá.','small'));
  pages('assessments',d.pagination,loadAssessments);
}
async function refreshMonitor(){await loadTelemetry();await loadAssessments();}
function assessmentView(a){
  S.assessment=a;
  const r=a.result,box=node('div',undefined,'assessment '+r.status);
  box.append(node('h3',STATUS[r.status]||r.status));
  box.append(node('p',`${fmt(r.window_start)} → ${fmt(r.window_end)} · UTC+7`,'small'));
  const expiry=node('p',undefined,'small');expiry.id='assessment-expiry';box.append(expiry);
  box.append(node('p',`Số giờ: ${r.completeness.received_buckets}/${r.completeness.expected_buckets} · Chuỗi khớp dài nhất: ${r.longest_matching_run_hours??'chưa xác định'}`));
  const list=node('ul');r.reasons.forEach(t=>list.append(node('li',t)));box.append(list);
  if(r.completeness.missing_buckets.length)box.append(node('p','Giờ thiếu: '+r.completeness.missing_buckets.map(fmt).join('; '),'small'));
  box.append(node('p','Mô phỏng · Chưa xác thực thực địa · Chưa có thời gian dự báo trước bệnh','small'));
  if(a.cultivation_context){
    const c=a.cultivation_context;
    box.append(node('p',c.item?'Hồ sơ tại lúc tạo đánh giá: '+profileDescription(c.item):'Chưa có hồ sơ canh tác khi tạo đánh giá này.','small'));
    if(c.crop_age_days!==null)box.append(node('p',`Tuổi theo lịch tại ${c.age_at_local_date}: ${c.crop_age_days} ngày từ ${c.crop_age_basis==='transplanted_on'?'ngày cấy':'ngày gieo'} (ngày đầu = 0). Không tự suy giai đoạn sinh trưởng.`,'small'));
    if(c.recorded_after_window_end)box.append(node('p','Hồ sơ được nhập sau mốc cửa sổ; không chứng minh thông tin đã có khi đó.','small'));
  }else box.append(node('p','Bản đánh giá cũ chưa lưu hồ sơ canh tác; không tự bổ sung vào lịch sử.','small'));
  const details=node('details');details.append(node('summary','Nguồn gốc & phiên bản'),node('p',`Profile: ${a.profile.version} · Tạo lúc ${fmt(a.created_at)} · ${a.mode}`,'small'),node('pre',`Assessment: ${a.id}\nRequest gốc: ${a.request_id}\nProfile SHA-256: ${r.profile_sha256}\nInput SHA-256: ${r.input_sha256}`,'hashes'));box.append(details);
  $('assessment').replaceChildren(box);
  updateExpiry();
}
function updateExpiry(){const e=$('assessment-expiry');if(e&&S.assessment)e.textContent=Date.now()>=Date.parse(S.assessment.valid_until)?'Bản lịch sử · đã qua hạn hiển thị kỹ thuật':'Trong hạn hiển thị kỹ thuật · dữ liệu vẫn là mô phỏng';}
setInterval(updateExpiry,30000);
async function selectAssessment(id,versionId=null){
  const head=(await api(`${FAR}/assessments/${id}/current`)).item;const selected=versionId&&versionId!==id?(await api(`${FAR}/assessment-versions/${versionId}`)).item:versionId===id?(await api(`${FAR}/assessments/${id}/versions?page=1&page_size=100`)).items.find(v=>v.revision===1):head;
  S.assessmentBaseId=id;S.assessmentHeadId=head.id;assessmentView(selected.snapshot);
  const versionBox=node('div',undefined,'assessment');versionBox.append(node('p',`Đang xem v${selected.revision}${selected.id===head.id?' · bản hiện hành':' · bản lịch sử'}; hiện hành là v${head.revision}. Các bản cũ giữ nguyên.`));
  const label=node('label','Chọn phiên bản đánh giá');const picker=node('select');picker.id='assessment-version-select';const versions=(await api(`${FAR}/assessments/${id}/versions?page_size=100`)).items;
  versions.forEach(v=>{const o=node('option',`v${v.revision} · ${STATUS[v.snapshot.result.status]} · nhận ${fmt(v.created_at)}${v.id===head.id?' · hiện hành':''}`);o.value=v.id;picker.append(o);});picker.value=selected.id;picker.onchange=()=>run(()=>selectAssessment(id,picker.value));label.append(picker);versionBox.append(label);$('assessment').prepend(versionBox);await loadLinked();message('Đã mở phiên bản đánh giá; v1 và lịch sử không bị ghi đè.');
}
async function assess(current){
  const d=await api(`${FAR}/devices/${S.device}/assessments`,{method:'POST',body:current?{}:{as_of:END}});await loadAssessments();await selectAssessment(d.item.id);message('Đã đọc bản hiện hành; worker tạo bản bổ sung khi nhận thêm bucket, không sửa v1.');
}
$('seed').onclick=()=>run(async()=>{
  const end=Date.parse(END);const records=Array.from({length:24},(_,i)=>({start_at:new Date(end-(24-i)*3600000).toISOString(),air_temperature_c:26,relative_humidity_pct:i>=18?95:70,leaf_wet:i>=18}));
  const d=await api(`${FAR}/devices/${S.device}/telemetry`,{method:'POST',body:{source:'mock',records}});await loadTelemetry();message(`Đã nạp ${d.inserted} giờ; ${d.replayed} giờ trùng giữ nguyên. Đây là mẫu lịch sử.`);
});
$('assess').onclick=()=>run(()=>assess(false));$('assess-current').onclick=()=>run(()=>assess(true));
$('refresh-monitor').onclick=()=>run(async()=>{await refreshMonitor();message('Đã làm mới số đo và lịch sử.');});
async function loadLinked(page=1){
  $('linked').replaceChildren();if(!S.assessment)return;
  const d=await api(`${FAR}/assessments/${S.assessmentBaseId||S.assessment.id}/analyses?page=${page}`);
  d.items.forEach(a=>{const b=node('button',`${fmt(a.created_at)} · ${a.status} · ${a.model_version}`);b.onclick=()=>run(()=>openAnalysis(a.analysis_id));$('linked').append(b);});
  if(!d.items.length)$('linked').append(node('p','Chưa gắn ảnh vào đánh giá này.','small'));
  pages('linked',d.pagination,loadLinked);
}
async function loadAnalyses(page=1){
  const d=await api(`/api/disease/analyses?page=${page}`);$('analyses').replaceChildren();
  d.items.forEach(a=>{const b=node('button',`${fmt(a.created_at)} · ${a.status==='no_detection'?'Không có detection':a.detection_count+' box'} · ${a.model_version}`);b.onclick=()=>run(()=>openAnalysis(a.analysis_id));$('analyses').append(b);});
  if(!d.items.length)$('analyses').append(node('p','Chưa có nhận diện ảnh.','small'));
  pages('analyses',d.pagination,loadAnalyses);
}
async function renderImage(a){
  clearImage();S.analysis=a;
  const panel=$('image-result');panel.replaceChildren(node('h3',a.status==='no_detection'?'Không có detection — chưa kết luận khỏe':`Đã tìm thấy ${a.detections.length} box`));
  panel.append(node('p',`Model: ${a.model_version} · ${fmt(a.created_at)}`,'small'));
  a.detections.forEach(d=>panel.append(node('p',`${d.disease} · Điểm model ${d.confidence.toFixed(3)} · box (${d.bbox.x1.toFixed(1)}, ${d.bbox.y1.toFixed(1)}, ${d.bbox.x2.toFixed(1)}, ${d.bbox.y2.toFixed(1)})`,'small')));
  panel.append(node('pre',`Analysis: ${a.analysis_id}\nRequest gốc: ${a.request_id}\nSHA-256: ${a.model_sha256}`,'hashes'));
  const blob=await api(a.image_url,{raw:true});
  const bitmap=await createImageBitmap(blob,{imageOrientation:'from-image'});
  try{
    if(bitmap.width!==a.image.width||bitmap.height!==a.image.height)throw new Error('Kích thước sau EXIF không khớp contract. Không vẽ box sai tọa độ.');
    const c=$('image-canvas');c.width=bitmap.width;c.height=bitmap.height;const ctx=c.getContext('2d');ctx.drawImage(bitmap,0,0);
    ctx.lineWidth=Math.max(2,c.width/350);ctx.strokeStyle='#ffcf40';ctx.font=`${Math.max(13,c.width/55)}px sans-serif`;
    a.detections.forEach(d=>{const b=d.bbox;ctx.strokeRect(b.x1,b.y1,b.x2-b.x1,b.y2-b.y1);ctx.fillStyle='#142e24';const label=`${d.disease} · ${d.confidence.toFixed(2)}`;const h=Math.max(20,c.width/40);ctx.fillRect(b.x1,Math.max(0,b.y1-h),Math.min(ctx.measureText(label).width+12,c.width-b.x1),h);ctx.fillStyle='#fff';ctx.fillText(label,b.x1+5,Math.max(h-4,b.y1-4));});
    c.hidden=false;
  }finally{bitmap.close();}
}
async function openAnalysis(id){const a=await api(`/api/disease/analyses/${id}`);await renderImage(a);message('Đã mở ảnh riêng tư; tọa độ box theo ảnh sau EXIF.');}
$('image-file').onchange=()=>{clearImage();S.file=$('image-file').files[0]||null;S.key=S.file?crypto.randomUUID():null;if(S.file&&S.file.size>8*1024*1024){S.file=null;$('image-file').value='';message('Ảnh tối đa 8 MiB.',true);}controls();};
$('image-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.file)return;const body=new FormData();body.append('image',S.file);
  const a=await api('/api/disease/detect',{method:'POST',body,headers:{'Idempotency-Key':S.key}});
  await renderImage(a);await loadAnalyses();message('Đã đọc kết quả V4. Cùng file/tác vụ dùng lại cùng key; không tự retry khi lỗi.');
});};
$('link').onclick=()=>run(async()=>{await api(`${FAR}/assessments/${S.assessmentBaseId||S.assessment.id}/analyses`,{method:'POST',body:{analysis_id:S.analysis.analysis_id}});await loadLinked();message('Đã gắn ảnh vào đánh giá gốc v1; không tự gán ảnh cho bản bổ sung.');});
$('refresh-history').onclick=()=>run(async()=>{await loadAnalyses();message('Đã tải lịch sử. Kiểm tra kết quả trước khi tạo lại tác vụ nhận diện chưa chắc chắn.');});
function resetWarningDashboard(){S.warningEpisode=null;['warning-summary','warning-observation','warning-devices','warning-devices-pages','warning-episodes','warning-episodes-pages','warning-detail','warning-members','warning-members-pages'].forEach(id=>$(id).replaceChildren());$('warning-summary').textContent='Chọn mùa vụ để xem.';}
const FRESHNESS={missing:'Chưa có bucket giờ',stale:'Bucket giờ đã cũ',window_end_bucket_present:'Có bucket giờ cuối · chưa xác nhận đủ cả cửa sổ'};
async function loadWarningDevices(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/warning-dashboard?page=${page}`);const c=d.counts;
  $('warning-summary').textContent=`Đọc lúc ${fmt(d.at_utc)} · ${c.open_count} đợt đang mở: ${c.conditions_count} kiểm tra điều kiện, ${c.data_count} kiểm tra dữ liệu · ${c.legacy_open_cases} việc độc lập/cũ đang mở · Chưa có xác suất bệnh.`;
  const o=d.latest_observation;$('warning-observation').textContent=o?`Quan sát active gần nhất của mùa vụ: ${fmt(o.observed_at)} · nhập ${fmt(o.recorded_at)} · nguồn ${o.source} · ${FINDING[o.finding]} · nền tảng chưa xác minh. Không tự kết thúc đợt từ bản ghi này.`:'Chưa có quan sát active của mùa vụ. Không suy ra không bệnh.';
  $('warning-devices').replaceChildren();d.items.forEach(v=>{const box=node('article',undefined,'assessment');box.append(node('h3',v.name),node('p',`${FRESHNESS[v.freshness]} · ${v.open_episodes} đợt đang mở`));if(v.latest_assessment)box.append(node('p',`v${v.latest_assessment.revision||1} · ${STATUS[v.latest_assessment.status]} · ${fmt(v.latest_assessment.window_end)} · ${v.latest_assessment.expired?'snapshot đã qua hạn hiển thị':'trong hạn hiển thị'}`));const b=node('button','Mở thiết bị để kiểm tra','secondary');b.onclick=()=>run(async()=>{S.device=v.id;await loadDevices(1,S.device);resetMonitor();await loadTelemetry();await loadAssessments();$('monitor').scrollIntoView({behavior:'smooth'});});box.append(b);$('warning-devices').append(box);});if(!d.items.length)$('warning-devices').append(node('p','Chưa có thiết bị.'));pages('warning-devices',d.pagination,loadWarningDevices);
}
async function loadWarningEpisodes(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/warning-episodes?page=${page}`);$('warning-episodes').replaceChildren();d.items.forEach(p=>{const b=node('button',`${FOLLOWUP_STATE[p.state]} · ${p.task_kind==='check_conditions'?'Điều kiện':'Dữ liệu'} · ${p.assessment_count} đánh giá · ${p.latest_window?fmt(p.latest_window):'chưa có'}${p.needs_recheck&&p.state!=='closed'?' · Cần kiểm tra mới nhất':''}`);b.onclick=()=>run(()=>openWarningEpisode(p.id));$('warning-episodes').append(b);});if(!d.items.length)$('warning-episodes').append(node('p','Chưa có đợt mới từ worker; công việc cũ không tự gộp.'));pages('warning-episodes',d.pagination,loadWarningEpisodes);
}
async function loadWarningMembers(page=1){if(!S.warningEpisode)return;const d=await api(`${FAR}/warning-episodes/${S.warningEpisode.id}/assessments?page=${page}`);$('warning-members').replaceChildren();d.items.forEach(m=>{const box=node('article',undefined,'assessment');box.append(node('h3',`${fmt(m.window_end)} · ${STATUS[m.status]}`),node('p',`Gắn vào đợt lúc ${fmt(m.recorded_at)} · Request ${m.request_id}`,'small'));const b=node('button','Mở snapshot đánh giá','secondary');b.onclick=()=>run(async()=>{S.device=m.snapshot.device_id;await loadDevices(1,S.device);await selectAssessment(m.snapshot.base_assessment_id||m.assessment_id,m.assessment_id);$('monitor').scrollIntoView({behavior:'smooth'});});box.append(b);$('warning-members').append(box);});pages('warning-members',d.pagination,loadWarningMembers);}
async function openWarningEpisode(id){const d=await api(`${FAR}/warning-episodes/${id}`);const p=S.warningEpisode=d.item;$('warning-detail').replaceChildren(node('h3',`${FOLLOWUP_STATE[p.state]} · ${p.assessment_count} đánh giá`),node('p',`Từ ${fmt(p.first_window)} đến ${fmt(p.latest_window)} · mới nhất: ${STATUS[p.latest_status]} · ${p.needs_recheck?'Cần xem lại bằng chứng kiểm tra':'Đã ghi kiểm tra theo mốc yêu cầu'}`),node('p','Khoảng giữa các mốc có thể thiếu giờ; không suy ra nguy cơ liên tục hoặc cây khỏe.','small'));showCheckStatus($('warning-detail'),p);const b=node('button','Mở công việc của đợt','secondary');b.onclick=()=>run(async()=>{await openFollowup(p.case_id);$('followup').scrollIntoView({behavior:'smooth'});});$('warning-detail').append(b);await loadWarningMembers();}
async function loadWarningDashboard(){if(!S.season)return;await loadWarningDevices();await loadWarningEpisodes();if(S.warningEpisode)await openWarningEpisode(S.warningEpisode.id);}
$('warning-refresh').onclick=()=>run(async()=>{await loadWarningDashboard();message('Đã đọc lại bảng điều hành; không tạo đánh giá hoặc kết luận bệnh.');});
clearSession();controls();
api('/demo-info',{auth:false}).then(info=>{$('model-info').textContent=`Hồ sơ lúc khởi động: ${info.health.model_version} · ${info.health.device} · SHA-256 ${info.health.model_sha256}. Đây không phải health trực tiếp liên tục.`;$('storage-notice').textContent=info.storage_mode==='pilot'?'PILOT LOCAL: dữ liệu giữ lại khi dừng; cần backup riêng. Không phải production.':'DEMO TẠM: dữ liệu bị dọn khi dừng launcher; không nhập dữ liệu pilot cần giữ.';}).catch(()=>{$('model-info').textContent='Chưa đọc được hồ sơ model lúc khởi động.';$('storage-notice').textContent='Chưa xác định chế độ lưu dữ liệu; kiểm tra launcher trước khi nhập dữ liệu thật.';});
