"""Additive, immutable late-input snapshots in the opt-in followup store.

Core assessment remains v1. Same source/profile/window, monotonically added
immutable buckets only. No retraction, training or threshold changes.
"""
from datetime import datetime,timezone
import json,uuid
from flask import Blueprint,current_app,g,jsonify,request
from pilot_journal import journal_db
from pilot_store import validate_storage

def now():return datetime.now(timezone.utc)


def initialize(path):
    with journal_db(path) as db:
        if db.execute('SELECT kind FROM followup_meta').fetchone()[0]!='aegis-pilot-followup-v1':raise ValueError('Wrong followup DB')
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='assessment_version_meta'").fetchone():
            if db.execute('SELECT kind FROM assessment_version_meta').fetchone()[0]!='aegis-assessment-versions-v1':raise ValueError('Unknown version schema')
            return
        db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE assessment_version_meta(kind TEXT NOT NULL)');db.execute("INSERT INTO assessment_version_meta VALUES ('aegis-assessment-versions-v1')")
        db.execute('''CREATE TABLE assessment_versions(id TEXT PRIMARY KEY,base_assessment_id TEXT NOT NULL,user_id TEXT NOT NULL,
            season_id TEXT NOT NULL,device_id TEXT NOT NULL,profile_sha256 TEXT NOT NULL,revision INTEGER NOT NULL,
            previous_id TEXT NOT NULL,base_sha256 TEXT NOT NULL,input_sha256 TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL,
            UNIQUE(base_assessment_id,revision),UNIQUE(base_assessment_id,input_sha256))''')
        db.execute('''CREATE TABLE assessment_version_attempts(id TEXT PRIMARY KEY,base_assessment_id TEXT NOT NULL,user_id TEXT NOT NULL,
            input_sha256 TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,finished_at TEXT,error_code TEXT,
            request_id TEXT NOT NULL,version_id TEXT)''')
        db.execute('CREATE INDEX idx_version_owner ON assessment_versions(user_id,season_id,base_assessment_id,revision)')
        db.execute('CREATE INDEX idx_version_attempt ON assessment_version_attempts(base_assessment_id,input_sha256,created_at)')


def recover(path,at):
    # Caller must hold the same OS execution lock as the worker.
    with journal_db(path) as db:db.execute("UPDATE assessment_version_attempts SET state='interrupted',finished_at=?,error_code='executor_interrupted' WHERE state='running'",(at.isoformat(),))


def current(db,base):
    from app.blast_conditions import digest
    r=db.execute('SELECT * FROM assessment_versions WHERE base_assessment_id=? AND user_id=? ORDER BY revision DESC LIMIT 1',(base['id'],base['user_id'])).fetchone()
    if r:
        if r['base_sha256']!=digest(base):raise ValueError('Base assessment integrity mismatch')
        data=item(r)
    else:data=dict(id=base['id'],base_assessment_id=base['id'],revision=1,previous_id=None,base_sha256=digest(base),input_sha256=digest(base['input']),snapshot_sha256=digest(base),created_at=base['created_at'],request_id=base['request_id'],snapshot=base,is_supplemental=False)
    from pilot_followup import find_case
    case=find_case(db,data['id'],base['user_id'])
    return dict(data,followup_id=case['id'] if case else None)


def item(r):
    from app.blast_conditions import digest
    a=json.loads(r['snapshot_json'])
    if digest(a)!=r['snapshot_sha256']:raise ValueError('Version snapshot integrity mismatch')
    return {**{k:r[k] for k in ['id','base_assessment_id','revision','previous_id','base_sha256','input_sha256','snapshot_sha256','created_at','request_id']},'snapshot':a,'is_supplemental':True}


def ensure_version(path,base,payload,request_id,origin,checkpoint=lambda s:None):
    """Worker execution lock held. Snapshot+case+membership commit together."""
    from app.blast_conditions import PROFILE,digest,evaluate
    from pilot_episodes import attach_assessment,linked_case
    from pilot_followup import find_case
    base_id=base['id'];owner=base['user_id'];sha=digest(payload);at=max(now(),datetime.fromisoformat(base['created_at']))
    if payload['source']!='mock' or payload['as_of']!=base['input']['as_of'] or digest(PROFILE)!=digest(base['profile']):raise ValueError('Version scope/profile mismatch')
    with journal_db(path) as db:
        head=current(db,base)
        if sha==head['input_sha256'] or sha==digest(base['input']):
            case=find_case(db,head['id'],owner)
            # A committed version can outlive a failed audit-finalization step.
            failed=db.execute("SELECT 1 FROM assessment_version_attempts WHERE base_assessment_id=? AND input_sha256=? AND state IN ('failed','interrupted') AND NOT EXISTS(SELECT 1 FROM assessment_version_attempts b WHERE b.base_assessment_id=? AND b.input_sha256=? AND b.state='succeeded')",(base_id,sha,base_id,sha)).fetchone()
            if failed:db.execute('INSERT INTO assessment_version_attempts VALUES (?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),base_id,owner,sha,'succeeded',at.isoformat(),at.isoformat(),None,request_id,head['id']))
            return dict(head,followup_id=case['id'] if case else None,created=False)
        previous={r['start_at']:r for r in head['snapshot']['input']['records']};new={r['start_at']:r for r in payload['records']}
        if len(new)!=len(payload['records']) or not previous.keys()<=new.keys() or any(new[k]!=v for k,v in previous.items()):raise ValueError('Version may only add immutable hourly buckets')
        output=evaluate(payload)
        attempt=str(uuid.uuid4());db.execute('INSERT INTO assessment_version_attempts VALUES (?,?,?,?,?,?,?,?,?,?)',(attempt,base_id,owner,sha,'running',at.isoformat(),None,None,request_id,None))
    version_id=None
    try:
        with journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE');head=current(db,base)
            existing=db.execute('SELECT * FROM assessment_versions WHERE base_assessment_id=? AND input_sha256=?',(base_id,sha)).fetchone()
            if existing:version=item(existing);version_id=version['id'];case=find_case(db,version_id,owner)
            else:
                version_id=str(uuid.uuid4());revision=head['revision']+1
                a={**base,'id':version_id,'base_assessment_id':base_id,'assessment_revision':revision,'previous_assessment_id':head['id'],'created_at':at.isoformat(),'request_id':request_id,'input':payload,'result':output,'mode':'supplemental_mock','context_policy':'frozen_from_base_assessment'}
                db.execute('INSERT INTO assessment_versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(version_id,base_id,owner,base['season_id'],base['device_id'],digest(PROFILE),revision,head['id'],digest(base),sha,digest(a),json.dumps(a,ensure_ascii=False,allow_nan=False),at.isoformat(),request_id))
                checkpoint('before_version_followup')
                case,_,_=attach_assessment(db,owner,a,'Đánh giá bổ sung từ bucket mock nhận muộn',request_id,at,origin)
                checkpoint('after_version_followup')
                version=item(db.execute('SELECT * FROM assessment_versions WHERE id=?',(version_id,)).fetchone())
        checkpoint('after_version_commit')
        with journal_db(path) as db:db.execute("UPDATE assessment_version_attempts SET state='succeeded',finished_at=?,version_id=? WHERE id=?",(now().isoformat(),version_id,attempt))
        return dict(version,followup_id=case['id'] if case else None,created=not bool(existing))
    except Exception:
        with journal_db(path) as db:db.execute("UPDATE assessment_version_attempts SET state='failed',finished_at=?,error_code='assessment_version_failed',version_id=? WHERE id=?",(now().isoformat(),version_id,attempt))
        raise


def enable_assessment_versions(app,storage):
    storage=validate_storage(storage);path=storage/'followup.sqlite3';initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.farm import owned,private,FarmError
    from pilot_followup import find_case
    bp=Blueprint('assessment_versions',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))
    bp.register_error_handler(ValueError,lambda e:(jsonify(success=False,error=dict(code='assessment_integrity_error',message='Không xác minh được phiên bản đánh giá.')),503))
    def base(core,id):return json.loads(owned(core,'assessments',id)['snapshot_json'])
    def version(db,core,id):
        r=db.execute('SELECT * FROM assessment_versions WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
        if r is None:raise FarmError('resource_not_found','Không tìm thấy phiên bản.',404)
        a=base(core,r['base_assessment_id'])
        from app.blast_conditions import digest
        if digest(a)!=r['base_sha256']:raise FarmError('assessment_integrity_error','Không xác minh được bản gốc.',503)
        return item(r)
    @bp.get('/assessments/<uuid:id>/current')
    @require_auth
    def latest(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=current(db,base(core,id)))
    @bp.get('/assessments/<uuid:id>/versions')
    @require_auth
    def listing(id):
        if set(request.args)-{'page','page_size'}:raise FarmError('invalid_pagination','Chỉ page/page_size.')
        values=[]
        for key,default,maximum in [('page','1',1000000),('page_size','20',100)]:
            value=request.args.get(key,default)
            if len(request.args.getlist(key))>1 or not value.isascii() or not value.isdigit() or len(value)>7 or not 1<=int(value)<=maximum:raise FarmError('invalid_pagination','Phân trang không hợp lệ.')
            values.append(int(value))
        page,size=values
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');a=base(core,id);head=current(db,a);rows=db.execute('SELECT * FROM assessment_versions WHERE base_assessment_id=? AND user_id=? ORDER BY revision DESC',(str(id),g.user['id'])).fetchall()
            # v1 is returned from its original core bytes, never reinserted/rewritten.
            from app.blast_conditions import digest
            first=dict(id=a['id'],base_assessment_id=a['id'],revision=1,previous_id=None,base_sha256=digest(a),input_sha256=digest(a['input']),snapshot_sha256=digest(a),created_at=a['created_at'],request_id=a['request_id'],snapshot=a,is_supplemental=False)
            items=[item(r) for r in rows]+[first];total=len(items);pages=(total+size-1)//size
            return jsonify(success=True,items=items[(page-1)*size:page*size],current_id=head['id'],pagination=dict(page=page,page_size=size,total=total,total_pages=pages,has_next=page<pages))
    @bp.get('/assessment-versions/<uuid:id>')
    @require_auth
    def detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:return jsonify(success=True,item=version(db,core,id))
    @bp.get('/assessment-versions/<uuid:id>/follow-up')
    @require_auth
    def followup(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');v=version(db,core,id);c=find_case(db,v['id'],g.user['id']);return jsonify(success=True,case_id=c['id'] if c else None)
    @bp.get('/assessments/<uuid:id>/version-attempts')
    @require_auth
    def attempts(id):
        from app.farm import paginate
        with connect(current_app.config) as core,journal_db(path) as db:
            base(core,id);return paginate(db,'assessment_version_attempts','base_assessment_id=? AND user_id=?',(str(id),g.user['id']),order='created_at DESC,rowid DESC')
    app.register_blueprint(bp)
