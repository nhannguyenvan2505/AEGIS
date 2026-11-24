'use strict';
const SURVEY_STATE={planned:'Dự kiến',completed:'Đã gắn quan sát',missed:'Bỏ lỡ',unable:'Không thực hiện được',cancelled:'Đã hủy'};
const COVERAGE_STATE={unknown:'Chưa biết độ đầy đủ',partial:'Chưa đầy đủ',reviewed_records:'Đã đối soát các bản ghi',reviewed_no_interventions:'Đã đối soát và khai báo không can thiệp'};
const REVIEW_STATE={offered:'Chờ tài khoản nhận chấp thuận',active:'Quyền đang có hiệu lực',revoked:'Quyền đã thu hồi',pending:'Chờ xem bằng chứng',decided:'Đã ghi quyết định',withdrawn:'Quyết định đã rút',cancelled:'Yêu cầu đã hủy'};
const REVIEW_DECISION={supports_present:'Bằng chứng hỗ trợ có dấu hiệu',supports_absent:'Bằng chứng hỗ trợ không ghi nhận dấu hiệu',inconclusive:'Chưa đủ căn cứ',reject_evidence:'Bằng chứng không phù hợp'};
const RESEARCH_ACTION={accept:'Chấp thuận quyền xem yêu cầu',revoke:'Thu hồi quyền',decide:'Ghi / sửa quyết định',withdraw:'Rút quyết định',cancel:'Hủy yêu cầu'};
function researchKey(slot,fingerprint){
  S.researchKeys=S.researchKeys||{};const old=S.researchKeys[slot];
  if(old?.fingerprint!==fingerprint)S.researchKeys[slot]={fingerprint,key:crypto.randomUUID()};return S.researchKeys[slot].key;
}
function researchEvent(slot,id,body){return {...body,client_event_id:researchKey(slot,JSON.stringify([id,body]))};}
function clearReviewImage(){if(S.reviewImageUrl)URL.revokeObjectURL(S.reviewImageUrl);S.reviewImageUrl=null;const image=$('review-evidence-image');image.removeAttribute('src');image.hidden=true;}
function resetResearch(){
  if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('survey-observation','review-observation','review-grant');
  S.surveyPlan=null;S.coverage=null;S.reviewItem=null;S.reviewAllowed=false;S.researchKeys={};clearReviewImage();
  for(const id of ['survey-plans','survey-plans-pages','survey-selected','survey-history','survey-history-pages','coverage-list','coverage-list-pages','coverage-selected','coverage-history','coverage-history-pages','review-grants','review-grants-pages','review-requests','review-requests-pages','review-inbox-list','review-inbox-list-pages','review-detail','review-history','review-history-pages','review-account-id'])$(id).replaceChildren();
  for(const id of ['survey-plan-form','survey-event-form','coverage-create-form','coverage-event-form','review-grant-form','review-request-form','review-action-form'])$(id).reset();
}
function researchTimelineDescription(e){
  const d=e.detail;
  if(e.kind==='survey_plan')return `${SURVEY_STATE[d.state]} · ${d.planned_before_window?'Lập trước cửa sổ':'Lịch nhập hồi cứu'} · ${d.reason}`;
  if(e.kind==='coverage')return `${COVERAGE_STATE[d.state]} · khai báo chủ mùa vụ, chưa duyệt train · ${d.reason}`;
  if(e.kind==='review_grant')return `${REVIEW_STATE[d.state]} · ${d.reviewer_alias} · chưa xác minh chuyên môn`;
  return `${REVIEW_STATE[d.state]}${d.decision?' · '+REVIEW_DECISION[d.decision]:''} · chưa duyệt train · ${d.reason}`;
}
async function loadResearch(){if(!S.season)return;await loadSurveyPlans();await loadCoverage();await loadOwnerGrants();await loadOwnerRequests();await loadResearchInbox();}
async function ledgerHistory(url,host,page=1){
  const d=await api(url+'?page='+page);$(host).replaceChildren();
  d.items.forEach(e=>{const box=node('div',undefined,'assessment');box.append(node('h3',`Bản ${e.version} · ${fmt(e.recorded_at)} · ${SURVEY_STATE[e.state]||COVERAGE_STATE[e.state]||REVIEW_STATE[e.state]||e.state}`),node('p',e.data.reason));
    if(e.data.observation_snapshot)box.append(node('p',`Quan sát ${e.data.observation_snapshot.id} · bản ${e.data.observation_snapshot.revision}`,'small'));
    if(e.data.decision)box.append(node('p',REVIEW_DECISION[e.data.decision]));if(e.data.evidence_reference)box.append(node('p','Tham chiếu: '+e.data.evidence_reference,'small'));
    box.append(node('pre',`SHA-256 ${e.data_sha256}\nRequest ${e.request_id}`,'hashes'));$(host).append(box);
  });pages(host,d.pagination,p=>ledgerHistory(url,host,p));
}
async function loadSurveyPlans(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/survey-plans?page=${page}`);$('survey-plans').replaceChildren();
  d.items.forEach(c=>{const b=node('button',`${SURVEY_STATE[c.state]} · ${fmt(c.metadata.window_start)} → ${fmt(c.metadata.window_end)} · ${c.metadata.source}${c.overdue?' · Quá hạn, chưa ghi kết quả':''}${!c.metadata.planned_before_window?' · Nhập hồi cứu':''}${c.linked_observation_changed?' · Quan sát đã sửa, cần xem lại':''}`);b.onclick=()=>run(()=>openSurvey(c));$('survey-plans').append(b);});
  if(!d.items.length)$('survey-plans').append(node('p','Chưa lập lịch. Chưa có lịch không có nghĩa đã khảo sát đủ.','small'));pages('survey-plans',d.pagination,loadSurveyPlans);
}
async function openSurvey(c){if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('survey-observation');S.surveyPlan=c;$('survey-event-form').reset();$('survey-selected').textContent=`Lịch ${c.id} · bản ${c.version} · ${SURVEY_STATE[c.state]}${c.linked_observation_changed?' · Quan sát hiện tại khác bản đã gắn':''}`;await ledgerHistory(`${FAR}/survey-plans/${c.id}/events`,'survey-history');message('Đã mở lịch; cửa sổ và nguồn giữ nguyên. Sai lịch thì hủy và tạo lịch mới.');}
$('survey-plan-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const v=formBody('survey-plan-form');const command={...v,window_start:v.window_start+':00+07:00',window_end:v.window_end+':00+07:00'};
  const body={...command,client_plan_id:researchKey('plan-create',JSON.stringify([S.season,command]))};const d=await api(`${FAR}/seasons/${S.season}/survey-plans`,{method:'POST',body});
  delete S.researchKeys['plan-create'];$('survey-plan-form').reset();await loadSurveyPlans();await openSurvey(d.item);
});};
$('survey-event-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.surveyPlan)return;const v=formBody('survey-event-form');const body=researchEvent('plan-event',S.surveyPlan.id,{base_version:S.surveyPlan.version,state:v.state,observation_id:v.state==='completed'?v.observation_id.trim()||null:null,reason:v.reason});
  const d=await api(`${FAR}/survey-plans/${S.surveyPlan.id}/events`,{method:'POST',body});delete S.researchKeys['plan-event'];await loadSurveyPlans();await openSurvey(d.item);
});};
$('survey-use-visit').onclick=()=>{$('survey-event-form').elements.namedItem('observation_id').value=S.visit.id;if(typeof recordPicked==='function')recordPicked('survey-observation',S.visit);message('Đã điền quan sát. Server kiểm nguồn, cửa sổ và việc dùng quan sát cho lịch khác.');};
$('survey-refresh').onclick=()=>run(async()=>{await loadSurveyPlans();await loadCoverage();message('Đã làm mới lịch và đối soát; chọn lại bản cần sửa để lấy phiên bản hiện tại.');});
async function loadCoverage(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/intervention-coverage?page=${page}`);$('coverage-list').replaceChildren();
  d.items.forEach(c=>{const b=node('button',`${COVERAGE_STATE[c.state]} · ${fmt(c.metadata.window_start)} → ${fmt(c.metadata.window_end)} · ${c.metadata.source}${c.inventory_changed?' · Nhật ký đã thay đổi, cần đối soát lại':''}`);b.onclick=()=>run(()=>openCoverage(c));$('coverage-list').append(b);});
  if(!d.items.length)$('coverage-list').append(node('p','Chưa có khoảng được đối soát. Danh sách trống không xác nhận không can thiệp.','small'));pages('coverage-list',d.pagination,loadCoverage);
}
async function openCoverage(c){S.coverage=c;$('coverage-event-form').reset();$('coverage-selected').textContent=`Đối soát ${c.id} · bản ${c.version} · ${COVERAGE_STATE[c.state]}${c.inventory_changed?' · Cần xem lại nhật ký đã thay đổi':''} · Chưa phê duyệt train`;await ledgerHistory(`${FAR}/intervention-coverage/${c.id}/events`,'coverage-history');message('Đã mở đối soát; trạng thái là khai báo của chủ mùa vụ.');}
$('coverage-create-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const v=formBody('coverage-create-form');const command={...v,window_start:v.window_start+':00+07:00',window_end:v.window_end+':00+07:00'};
  const d=await api(`${FAR}/seasons/${S.season}/intervention-coverage`,{method:'POST',body:{...command,client_coverage_id:researchKey('coverage-create',JSON.stringify([S.season,command]))}});
  delete S.researchKeys['coverage-create'];$('coverage-create-form').reset();await loadCoverage();await openCoverage(d.item);
});};
$('coverage-event-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  if(!S.coverage)return;const v=formBody('coverage-event-form');const d=await api(`${FAR}/intervention-coverage/${S.coverage.id}/events`,{method:'POST',body:researchEvent('coverage-event',S.coverage.id,{...v,base_version:S.coverage.version})});
  delete S.researchKeys['coverage-event'];await loadCoverage();await openCoverage(d.item);
});};
async function loadOwnerGrants(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/review-grants?page=${page}`);$('review-grants').replaceChildren();
  d.items.forEach(c=>{const b=node('button',`${c.metadata.reviewer_alias} · ${REVIEW_STATE[c.state]} · ${c.id}`);b.onclick=()=>run(()=>openResearchReview(c));$('review-grants').append(b);});pages('review-grants',d.pagination,loadOwnerGrants);
}
async function loadOwnerRequests(page=1){
  if(!S.season)return;const d=await api(`${FAR}/seasons/${S.season}/review-requests?page=${page}`);$('review-requests').replaceChildren();
  d.items.forEach(c=>{const b=node('button',reviewRequestLabel(c));b.onclick=()=>run(()=>openResearchReview(c));$('review-requests').append(b);});pages('review-requests',d.pagination,loadOwnerRequests);
}
function reviewRequestLabel(c){return `${REVIEW_STATE[c.state]} · Quan sát ${c.metadata.observation_snapshot.id} bản ${c.metadata.observation_snapshot.revision}${!c.source_current?' · Nguồn đã đổi':''}${!c.grant_active?' · Quyền không còn hiệu lực':''}${c.current.decision?' · '+REVIEW_DECISION[c.current.decision]:''}`;}
async function loadResearchInbox(page=1){
  if(!S.token)return;$('review-account-id').textContent='UUID tài khoản của bạn: '+S.userId+' · Chỉ cung cấp cho chủ mùa vụ khi đồng ý nhận việc.';
  const d=await api(`${FAR}/review-inbox?page=${page}`);$('review-inbox-list').replaceChildren();
  d.items.forEach(c=>{const b=node('button',c.kind==='grant'?`${REVIEW_STATE[c.state]} · ${c.metadata.reviewer_alias}`:reviewRequestLabel(c));b.onclick=()=>run(()=>openResearchReview(c));$('review-inbox-list').append(b);});
  if(!d.items.length)$('review-inbox-list').append(node('p','Chưa có quyền hoặc yêu cầu được giao.','small'));pages('review-inbox-list',d.pagination,loadResearchInbox);
  if(S.reviewItem?.owner_account_id!==S.userId&&S.reviewItem?.kind==='review'&&!d.items.some(c=>c.id===S.reviewItem.id)&&page===1){S.reviewItem=null;S.reviewAllowed=false;clearReviewImage();$('review-detail').replaceChildren();$('review-history').replaceChildren();$('review-history-pages').replaceChildren();}
}
async function openResearchReview(c){
  if(c.kind==='review')c=(await api(`${FAR}/review-requests/${c.id}`)).item;
  S.reviewItem=c;clearReviewImage();$('review-action-form').reset();const host=$('review-detail');host.replaceChildren(node('h3',c.kind==='grant'?'Quyền xem yêu cầu được giao':'Yêu cầu xác minh phiên bản quan sát'),node('p',`${REVIEW_STATE[c.state]} · bản ${c.version} · Tài khoản khác chủ mùa vụ, danh tính/chuyên môn chưa được nền tảng xác minh.`));
  const owner=c.owner_account_id===S.userId;let actions=[];
  if(c.kind==='grant'){
    host.append(node('p',`Quyền ${c.id} · Phạm vi: chỉ quan sát và ảnh trong yêu cầu cụ thể. Chấp thuận chưa tự mở toàn bộ mùa vụ.`,'small'));
    if(!owner&&c.state==='offered')actions=['accept'];if(owner&&c.state!=='revoked')actions=['revoke'];
    // Opening a grant is read-only. The request form uses an explicit choice.
  }else{
    const v=c.metadata.observation_snapshot;host.append(node('p',`${FINDING[v.payload.finding]} · nguồn ${v.source} · quan sát ${fmt(v.observed_at)} · bản ${v.revision}`),node('p',v.payload.notes),node('p',`SHA-256 ${v.payload_sha256}`,'hashes'),node('p',`${c.source_current?'Nguồn vẫn là phiên bản hiện tại':'Nguồn đã sửa/thu hồi; quyết định không còn áp dụng cho bản hiện tại'}. ${c.grant_active?'Quyền đang hoạt động':'Quyền đã ngừng'}. Chưa duyệt làm nhãn train.`,'small'));
    if(c.current.decision)host.append(node('p',REVIEW_DECISION[c.current.decision]));
    if(owner&&c.state!=='cancelled')actions=['cancel'];
    if(!owner&&c.grant_active&&c.state!=='cancelled'){if(c.source_current)actions.push('decide');if(c.state==='decided')actions.push('withdraw');}
  }
  S.reviewAllowed=actions.length>0;$('review-action').replaceChildren();actions.forEach(action=>{const o=node('option',RESEARCH_ACTION[action]);o.value=action;$('review-action').append(o);});
  await ledgerHistory(`${FAR}/${c.kind==='grant'?'review-grants':'review-requests'}/${c.id}/events`,'review-history');message('Đã mở bằng chứng được chia sẻ; quyết định không tự sửa quan sát nguồn.');
}
$('review-grant-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const v=formBody('review-grant-form');delete v.share_consent;const command={...v,scope:'assigned_observations_and_images'};
  const d=await api(`${FAR}/seasons/${S.season}/review-grants`,{method:'POST',body:{...command,client_grant_id:researchKey('grant-create',JSON.stringify([S.season,command]))}});
  delete S.researchKeys['grant-create'];$('review-grant-form').reset();await loadOwnerGrants();await openResearchReview(d.item);
});};
$('review-request-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const v=formBody('review-request-form');v.source_revision=Number(v.source_revision);
  const d=await api(`${FAR}/seasons/${S.season}/review-requests`,{method:'POST',body:{...v,client_request_id:researchKey('request-create',JSON.stringify([S.season,v]))}});
  delete S.researchKeys['request-create'];$('review-request-form').reset();if(typeof invalidateRecordPickers==='function')invalidateRecordPickers('review-observation','review-grant');await loadOwnerRequests();await openResearchReview(d.item);
});};
$('review-use-visit').onclick=()=>{const f=$('review-request-form');for(const [k,v] of Object.entries({observation_id:S.visit.id,source_revision:S.visit.revision,payload_sha256:S.visit.payload_sha256}))f.elements.namedItem(k).value=v;if(typeof recordPicked==='function')recordPicked('review-observation',S.visit);message('Đã điền đúng phiên bản và hash đang mở; tải lại quan sát trước nếu đã được sửa nơi khác.');};
$('review-action-form').onsubmit=e=>{e.preventDefault();run(async()=>{
  const c=S.reviewItem;if(!c||!S.reviewAllowed)return;const v=formBody('review-action-form');let command={base_version:c.version,action:v.action,reason:v.reason};
  if(c.kind==='review')command={...command,decision:v.action==='decide'?v.decision:null,evidence_reference:v.evidence_reference};
  const d=await api(`${FAR}/${c.kind==='grant'?'review-grants':'review-requests'}/${c.id}/events`,{method:'POST',body:researchEvent('review-action',c.id,command)});
  delete S.researchKeys['review-action'];if(S.season){await loadOwnerGrants();await loadOwnerRequests();}await loadResearchInbox();await openResearchReview(d.item);
});};
$('review-inbox-refresh').onclick=()=>run(()=>loadResearchInbox());
$('review-owner-refresh').onclick=()=>run(async()=>{await loadOwnerGrants();await loadOwnerRequests();message('Đã làm mới trạng thái quyền và nguồn quan sát.');});
$('review-show-image').onclick=()=>run(async()=>{if(!S.reviewItem?.image_url)return;clearReviewImage();const blob=await api(S.reviewItem.image_url,{raw:true});S.reviewImageUrl=URL.createObjectURL(blob);$('review-evidence-image').src=S.reviewImageUrl;$('review-evidence-image').hidden=false;message('Ảnh bằng chứng được chia sẻ trong yêu cầu này; kết quả AI không tự xác minh bệnh.');});
resetResearch();controls();
