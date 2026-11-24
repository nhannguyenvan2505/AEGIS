const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
// Minimal DOM for async state tests. Actual layout/controls are tested in browser.
class Element{
  constructor(tag,text){this.tag=tag;this.textContent=text||'';this.children=[];this.dataset={};this.value='';this.fields=new Map();this.elements={namedItem:name=>{if(!this.fields.has(name))this.fields.set(name,new Element('input'));return this.fields.get(name);}};}
  append(...items){this.children.push(...items);}
  setAttribute(name,value){this[name]=value;}
  prepend(item){this.children.unshift(item);}
  replaceChildren(...items){this.children=items;this.value='';}
  get firstChild(){return this.children[0];}
}
function setup(){
  const elements=new Map();const writes=[];
  const c=vm.createContext({Map,Date,Error,console,S:{token:'synthetic',epoch:1,season:'season-a',busy:false},FAR:'/api/farm',FINDING:{uncertain:'Chưa kết luận'},fmt:x=>x,
    $:id=>{if(!elements.has(id))elements.set(id,new Element('form'));return elements.get(id);},node:(tag,text)=>new Element(tag,text),controls:()=>{},message:()=>{},run:f=>f(),api:async(path)=>{writes.push(path);return {items:[],pagination:{total_pages:1,has_next:false}};}});
  vm.runInContext(fs.readFileSync(__dirname+'/static/record-pickers.js','utf8')+'\nthis.pickers=RECORD_PICKERS;this.load=loadRecordPicker;this.apply=applyRecordPicker;this.reset=resetRecordPickers;',c);
  return {c,elements,writes};
}
const row={id:'visit-owned',revision:1,payload_sha256:'sha1',observed_at:'2026-10-27T10:00:00Z',source:'synthetic',payload:{record_status:'active',finding:'uncertain'}};
test('loading and changing option never writes a form or saves a record',async()=>{
  const {c,elements,writes}=setup();c.api=async path=>{writes.push(path);return {items:[row],pagination:{total_pages:2,has_next:true}};};
  await c.load('review-observation');const p=c.pickers.get('review-observation');p.select.value=row.id;p.select.onchange();
  assert.equal(elements.get('review-request-form').elements.namedItem('observation_id').value,'');
  assert.equal(p.select.firstChild.value,'');assert.equal(writes.length,1);assert.match(writes[0],/page_size=10/);
});
test('revision changes between list and apply do not silently bind new evidence',async()=>{
  const {c,elements}=setup();c.api=async path=>path.includes('?')?{items:[row],pagination:{total_pages:1}}:{item:{...row,revision:2,payload_sha256:'sha2'}};
  await c.load('review-observation');c.pickers.get('review-observation').select.value=row.id;
  await assert.rejects(c.apply('review-observation'),/Bản ghi đã đổi/);
  assert.equal(elements.get('review-request-form').elements.namedItem('observation_id').value,'');
});
test('late response after context change cannot fill another season',async()=>{
  const {c,elements}=setup();c.api=async()=>({items:[row],pagination:{total_pages:1}});await c.load('review-observation');c.pickers.get('review-observation').select.value=row.id;
  let resolve;c.api=()=>new Promise(r=>resolve=r);const pending=c.apply('review-observation');c.S.season='season-b';c.reset();resolve({item:row});await pending;
  assert.equal(elements.get('review-request-form').elements.namedItem('observation_id').value,'');assert.equal(c.pickers.get('review-observation').rows.size,0);
});
test('explicit apply binds viewed revision/hash; no mutation API is called',async()=>{
  const {c,elements,writes}=setup();c.api=async path=>{writes.push(path);return path.includes('?')?{items:[row],pagination:{total_pages:1}}:{item:row};};
  await c.load('review-observation');c.pickers.get('review-observation').select.value=row.id;await c.apply('review-observation');
  const f=elements.get('review-request-form');assert.equal(f.elements.namedItem('observation_id').value,row.id);assert.equal(f.elements.namedItem('source_revision').value,1);assert.equal(f.elements.namedItem('payload_sha256').value,'sha1');assert.equal(writes.length,2);
});
