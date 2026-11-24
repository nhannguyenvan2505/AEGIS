"""Owned, append-only follow-up workflow for existing mock assessments.

Operational state never changes risk, disease labels or the assessment snapshot.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import uuid
from flask import Blueprint,current_app,g,jsonify,request
from pilot_journal import journal_db
from pilot_store import validate_storage

TRANSITIONS={('open','acknowledge'):'acknowledged',('acknowledged','check'):'checked',('checked','check'):'checked',('checked','close'):'closed',('closed','reopen'):'acknowledged'}


def action_capabilities(case_row,requirement,status):
    """Workflow eligibility and declared inputs, never a command authorization.

    No selected observation is validated here. Commands still check payload,
    version, owner, evidence, quota and state at execution time.
    """
    assessment=json.loads(case_row['assessment_json'])
    def eligibility(action):
        enabled=(case_row['state'],action) in TRANSITIONS
        return dict(enabled=enabled,disabled_reasons=[] if enabled else ['workflow_state_not_allowed'])
    check=eligibility('check')
    check.update(observation_required=assessment['result']['status']=='advisory',
        observation_constraints=dict(source='synthetic',record_status='active',same_owner_and_season=True,
            observed_at_not_before=requirement['window_end'] if requirement else assessment['result']['window_end'],
            selection_validated=False))
    return dict(projection_version='aegis-followup-actions-v1',base_version=case_row['version'],
        validation_scope='workflow_state_and_declared_inputs',
        actions=dict(acknowledge=eligibility('acknowledge'),check=check),
        needs_recheck=status['needs_recheck'],recheck_reasons=list(status['reasons']))


def now():return datetime.now(timezone.utc)


def check_status(db,case_row,storage):
    """Read current evidence without rewriting the immutable check event.

    The journal and workflow remain separate databases; this is a read-time
    comparison, not an atomic snapshot across all writers.
    """
    from pilot_episodes import check_requirement
    requirement=check_requirement(db,case_row['id'])
    checked=db.execute("SELECT * FROM events WHERE case_id=? AND json_extract(payload_json,'$.action')='check' ORDER BY version DESC LIMIT 1",(case_row['id'],)).fetchone()
    reasons=[];observation_status=None
    if not checked:reasons.append('check_not_recorded')
    else:
        payload=json.loads(checked['payload_json']);observation=payload.get('observation_snapshot');seen=payload.get('assessment_requirement')
        if requirement and (checked['created_at']<requirement['recorded_at'] or
                (requirement['revision']>1 and (not seen or seen.get('assessment_id')!=requirement['assessment_id'])) or
                (seen is not None and seen.get('assessment_id')!=requirement['assessment_id'])):
            reasons.append('assessment_changed')
        needs_observation=json.loads(case_row['assessment_json'])['result']['status']=='advisory'
        if needs_observation and (not observation or observation['observed_at']<(requirement['window_end'] if requirement else json.loads(case_row['assessment_json'])['result']['window_end'])):
            reasons.append('observation_required')
        if observation:
            with journal_db(Path(storage)/'journal.sqlite3') as journal:
                journal.execute('BEGIN')
                current=journal.execute('SELECT * FROM current_records WHERE visit_id=? AND user_id=? AND season_id=?',
                    (observation['visit_id'],case_row['user_id'],case_row['season_id'])).fetchone()
                current_payload=json.loads(current['payload_json']) if current else None
                observation_status=dict(visit_id=observation['visit_id'],checked_revision=observation['revision'],
                    current_revision=current['revision'] if current else None,
                    current_record_status=current_payload['record_status'] if current else None)
                if current is None:reasons.append('observation_unavailable')
                elif current_payload['record_status']!='active':reasons.append('observation_voided')
                elif current['revision']!=observation['revision'] or current['payload_sha256']!=observation['payload_sha256']:
                    reasons.append('observation_changed')
        if checked['version']<case_row['version'] and case_row['state']=='acknowledged':
            reasons.append('check_not_recorded_after_reopen')
    return dict(needs_recheck=bool(reasons),reasons=reasons,checked_version=checked['version'] if checked else None,
                observation=observation_status)


def find_case(db,assessment_id,owner):
    from pilot_episodes import linked_case
    direct=db.execute('SELECT * FROM current_cases WHERE assessment_id=? AND user_id=?',(assessment_id,owner)).fetchone()
    return direct if direct is not None else linked_case(db,assessment_id,owner)


def ensure_case(db,owner,a,reason,request_id,at,origin=None):
    """Caller holds BEGIN IMMEDIATE; shared manual/automation deduplication."""
    from app.blast_conditions import digest
    old=find_case(db,a['id'],owner)
    if old:return old,False
    if a['user_id']!=owner or a['input']['source']!='mock' or a['result']['status'] not in ['advisory','insufficient_data']:raise ValueError('Unsupported follow-up scope')
    id=str(uuid.uuid4());db.execute('INSERT INTO cases VALUES (?,?,?,?,?,?,?)',(id,owner,a['season_id'],a['id'],json.dumps(a,ensure_ascii=False),digest(a),at.isoformat()))
    payload=dict(action='create',reason=reason,observation_id=None,resolution=None,base_version=0,observation_snapshot=None)
    if origin:payload['automation_origin']=origin
    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),id,owner,1,'open',json.dumps(payload,ensure_ascii=False,allow_nan=False),digest(payload),at.isoformat(),request_id))
    return db.execute('SELECT * FROM current_cases WHERE id=?',(id,)).fetchone(),True


def initialize(path):
    from app.hybrid_pilot import initialized
    if initialized(path): return
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM followup_meta').fetchone()[0]
            except (sqlite3.Error,TypeError) as exc:raise ValueError('Unknown follow-up DB; refusing to modify it') from exc
            if kind!='aegis-pilot-followup-v1':raise ValueError('Unknown follow-up schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE followup_meta(kind TEXT NOT NULL)');db.execute("INSERT INTO followup_meta VALUES ('aegis-pilot-followup-v1')")
        db.execute('''CREATE TABLE cases(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            assessment_id TEXT NOT NULL UNIQUE,assessment_json TEXT NOT NULL,assessment_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,UNIQUE(id,user_id))''')
        db.execute('''CREATE TABLE events(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,user_id TEXT NOT NULL,
            version INTEGER NOT NULL,state TEXT NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,request_id TEXT NOT NULL,UNIQUE(case_id,version),
            FOREIGN KEY(case_id,user_id) REFERENCES cases(id,user_id))''')
        db.execute('CREATE INDEX idx_followup_owner ON cases(user_id,season_id,created_at,id)')
        db.execute('''CREATE VIEW current_cases AS SELECT c.*,e.version,e.state,e.created_at AS updated_at FROM cases c
            JOIN events e ON e.case_id=c.id WHERE e.version=(SELECT MAX(x.version) FROM events x WHERE x.case_id=c.id)''')


def enable_followup(app,storage):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Wrong isolated store')
    path=storage/'followup.sqlite3';initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.blast_conditions import digest
    from app.farm import body,owned,paginate,text,private,FarmError,LimitResponse,limit_response
    bp=Blueprint('pilot_followup',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def identifier(v):
        try:return str(uuid.UUID(v))
        except (ValueError,TypeError,AttributeError):raise FarmError('invalid_followup','Cần UUID hợp lệ.')

    def item(r):
        from pilot_episodes import check_requirement
        a=json.loads(r['assessment_json']);expired=datetime.fromisoformat(a['valid_until'])<=now()
        return dict(id=r['id'],season_id=r['season_id'],assessment_id=r['assessment_id'],version=r['version'],state=r['state'],
            created_at=r['created_at'],updated_at=r['updated_at'],source='mock',assessment_sha256=r['assessment_sha256'],
            assessment_status=a['result']['status'],window_end=a['result']['window_end'],valid_until=a['valid_until'],
            display_freshness='expired' if expired else 'within_display_window',assessment_mode=a['mode'],
            task_kind='check_conditions' if a['result']['status']=='advisory' else 'check_data',
            disease_confirmed=False,training_approved=False,episode_requirement=check_requirement(db_for_item(),r['id']),
            check_status=check_status(db_for_item(),r,storage))

    # Serializers run while a request-local connection below is active. Do not
    # keep connections globally or use a second transaction for the group view.
    def db_for_item():return g.followup_connection

    def event(r):return dict(id=r['id'],version=r['version'],state=r['state'],payload=json.loads(r['payload_json']),
        payload_sha256=r['payload_sha256'],recorded_at=r['created_at'],request_id=r['request_id'])

    def case(db,core,id):
        r=db.execute('SELECT * FROM current_cases WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
        if r is None:raise FarmError('resource_not_found','Không tìm thấy mục theo dõi.',404)
        owned(core,'seasons',r['season_id']);return r

    def save(db,id,case_id,version,state,p):
        db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',(id,case_id,g.user['id'],version,state,
            json.dumps(p,ensure_ascii=False,allow_nan=False),digest(p),now().isoformat(),g.request_id))

    @bp.route('/assessments/<uuid:id>/follow-up',methods=['GET','POST'])
    @require_auth
    def create(id):
        data=body({'reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            g.followup_connection=db
            assessment=owned(core,'assessments',id);a=json.loads(assessment['snapshot_json']);owned(core,'seasons',a['season_id'])
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            old=find_case(db,str(id),g.user['id'])
            if data is None:return jsonify(success=True,item=item(old) if old else None)
            reason=text(data['reason'],500)
            if old:
                first=db.execute('SELECT * FROM events WHERE case_id=? AND version=1',(old['id'],)).fetchone()
                if json.loads(first['payload_json'])['reason']!=reason:raise FarmError('followup_conflict','Đánh giá đã có mục theo dõi; mở mục hiện tại.',409)
                return jsonify(success=True,item=item(old)),200
            if a['input']['source']!='mock' or a['result']['status'] not in ['advisory','insufficient_data']:
                raise FarmError('followup_not_required','Chỉ tạo mục theo dõi từ advisory hoặc insufficient_data mô phỏng.',409)
            row,_=ensure_case(db,g.user['id'],a,reason,g.request_id,now())
            return jsonify(success=True,item=item(row)),201

    @bp.get('/seasons/<uuid:id>/follow-ups')
    @require_auth
    def listing(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            g.followup_connection=db
            owned(core,'seasons',id);db.execute('BEGIN')
            where='season_id=? AND user_id=?';params=(str(id),g.user['id'])
            if 'state' in request.args:
                state=request.args.get('state')
                if len(request.args.getlist('state'))!=1 or state not in {'open','acknowledged','checked','closed'}:
                    raise FarmError('invalid_followup_filter','State phải là open, acknowledged, checked hoặc closed.')
                where+=' AND state=?';params+=(state,)
            return paginate(db,'current_cases',where,params,item,allowed_query=('state',))

    @bp.get('/follow-ups/<uuid:id>')
    @require_auth
    def detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            g.followup_connection=db
            db.execute('BEGIN');r=case(db,core,id);return jsonify(success=True,item=item(r))

    @bp.get('/follow-ups/<uuid:id>/assessment-view')
    @require_auth
    def assessment_view(id):
        """Required evidence and current version together; no client-side DB joins.

        The required check may refer to another window/base or an older advisory.
        Do not replace that requirement with the latest assessment unconditionally.
        """
        from pilot_assessment_versions import current, item as version_item
        from pilot_episodes import check_requirement
        from app.mobile_contract import CONTRACT_VERSION
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');r=case(db,core,id)
            requirement=check_requirement(db,r['id'])
            if requirement:
                member=db.execute('SELECT * FROM episode_members WHERE episode_id=? AND assessment_id=?',
                    (requirement['episode_id'],requirement['assessment_id'])).fetchone()
                if member is None or digest(json.loads(member['snapshot_json']))!=member['snapshot_sha256']:
                    raise FarmError('assessment_integrity_error','Không xác minh được đánh giá cần kiểm tra.',503)
                required=json.loads(member['snapshot_json'])
            else:
                required=json.loads(r['assessment_json'])
                if digest(required)!=r['assessment_sha256']:
                    raise FarmError('assessment_integrity_error','Không xác minh được đánh giá gốc.',503)
            base_id=required.get('base_assessment_id',required['id'])
            base=json.loads(owned(core,'assessments',base_id)['snapshot_json'])
            if required['id']==base_id:
                if digest(required)!=digest(base):
                    raise FarmError('assessment_integrity_error','Đánh giá gốc không khớp.',503)
                selected=dict(id=base_id,base_assessment_id=base_id,revision=1,
                    snapshot=base,snapshot_sha256=digest(base))
            else:
                row=db.execute('SELECT * FROM assessment_versions WHERE id=? AND user_id=?',
                    (required['id'],g.user['id'])).fetchone()
                if row is None or row['base_assessment_id']!=base_id or row['snapshot_sha256']!=digest(required):
                    raise FarmError('assessment_integrity_error','Phiên bản cần kiểm tra không khớp.',503)
                try:selected=version_item(row)
                except ValueError:
                    raise FarmError('assessment_integrity_error','Không xác minh được snapshot phiên bản.',503)
            try:head=current(db,base)
            except ValueError:
                raise FarmError('assessment_integrity_error','Không xác minh được phiên bản hiện tại.',503)
            at=now()
            def view(value):
                a=value['snapshot']
                if a['input']['source']!='mock':
                    raise FarmError('assessment_integrity_error','Nguồn đánh giá không phù hợp contract mock.',503)
                return {**{k:value[k] for k in ['id','base_assessment_id','revision','snapshot_sha256']},
                    'snapshot':a,'available_at':a['created_at'],
                    'display_freshness':'expired' if datetime.fromisoformat(a['valid_until'])<=at else 'within_display_window'}
            return jsonify(success=True,contract_version=CONTRACT_VERSION,item=dict(
                followup_id=r['id'],followup_version=r['version'],source='mock',
                required=view(selected),current=view(head),episode_requirement=requirement,
                projection_read_at=at.isoformat(),consistency='followup_transaction_core_separate',
                disease_confirmed=False,training_approved=False,
                action_capabilities=action_capabilities(r,requirement,check_status(db,r,storage))))

    @bp.route('/follow-ups/<uuid:id>/events',methods=['GET','POST'])
    @require_auth
    def events(id):
        data=body({'client_event_id','base_version','action','reason','observation_id','resolution'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            g.followup_connection=db
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');old=case(db,core,id)
            if data is None:return paginate(db,'events','case_id=? AND user_id=?',(str(id),g.user['id']),event,order='version DESC')
            key=identifier(data['client_event_id']);reason=text(data['reason'],500);base=data['base_version'];action=data['action']
            if type(base) is not int or not 1<=base<=2147483647 or action not in ['acknowledge','check','close','reopen']:
                raise FarmError('invalid_followup','Phiên bản hoặc hành động không hợp lệ.')
            obs=identifier(data['observation_id']) if data['observation_id'] is not None else None
            resolution=data['resolution']
            needs_observation=json.loads(old['assessment_json'])['result']['status']=='advisory'
            if obs is not None and action!='check':raise FarmError('invalid_followup','observation_id chỉ dùng cho check.')
            if action=='check' and needs_observation and obs is None:raise FarmError('invalid_followup','Cần quan sát để ghi kết quả kiểm tra điều kiện.')
            if action=='close':
                if resolution not in ['followup_recorded','referred_for_review']:raise FarmError('invalid_followup','Cần kết quả kết thúc luồng.')
            elif resolution is not None:raise FarmError('invalid_followup','resolution chỉ dùng khi kết thúc.')
            command=dict(action=action,reason=reason,observation_id=obs,resolution=resolution,base_version=base)
            existing=db.execute('SELECT * FROM events WHERE id=?',(key,)).fetchone()
            if existing:
                recorded=json.loads(existing['payload_json']);recorded.pop('observation_snapshot',None)
                recorded.pop('assessment_requirement',None)
                if existing['case_id']!=str(id) or existing['user_id']!=g.user['id'] or recorded!=command:raise FarmError('followup_event_conflict','UUID hành động đã có nội dung khác.',409)
                return jsonify(success=True,item=item(old),event=event(existing)),200
            if base!=old['version']:raise FarmError('followup_version_conflict','Mục theo dõi đã đổi; tải lại.',409)
            state=TRANSITIONS.get((old['state'],action))
            if state is None:raise FarmError('invalid_followup_transition','Hành động không phù hợp trạng thái hiện tại.',409)
            from pilot_episodes import check_requirement
            requirement=check_requirement(db,str(id))
            if action=='close':
                status=check_status(db,old,storage)
                if 'assessment_changed' in status['reasons'] or 'observation_required' in status['reasons']:
                    raise FarmError('episode_recheck_required','Có đánh giá mới cần kiểm tra lại trước khi kết thúc đợt.',409)
                if status['needs_recheck']:
                    raise FarmError('followup_observation_changed','Quan sát đã đổi hoặc bị thu hồi; cần ghi kiểm tra lại với quan sát hiện tại còn hợp lệ trước khi kết thúc.',409)
            if requirement and action=='reopen':
                p=db.execute('SELECT * FROM episodes WHERE id=?',(requirement['episode_id'],)).fetchone()
                if db.execute("SELECT 1 FROM episode_heads WHERE user_id=? AND device_id=? AND profile_sha256=? AND task_kind=? AND state!='closed' AND id!=?",(g.user['id'],p['device_id'],p['profile_sha256'],p['task_kind'],p['id'])).fetchone():
                    raise FarmError('episode_already_open','Đã có đợt đang mở cùng phạm vi; hãy mở đợt đó.',409)
            snapshot=None
            if obs:
                with journal_db(storage/'journal.sqlite3') as journal:
                    journal.execute('BEGIN');r=journal.execute('SELECT * FROM current_records WHERE visit_id=? AND user_id=? AND season_id=?',(obs,g.user['id'],old['season_id'])).fetchone()
                    if r is None:raise FarmError('resource_not_found','Không tìm thấy quan sát cùng mùa vụ.',404)
                    p=json.loads(r['payload_json']);a=json.loads(old['assessment_json'])
                    required_end=requirement['window_end'] if requirement else a['result']['window_end']
                    if r['source']!='synthetic' or p['record_status']!='active' or datetime.fromisoformat(r['observed_at'])<datetime.fromisoformat(required_end):raise FarmError('invalid_followup_observation','Luồng mock cần quan sát synthetic active từ cuối cửa sổ mới nhất cần kiểm tra trở đi.')
                    snapshot=dict(visit_id=obs,revision=r['revision'],payload_sha256=r['payload_sha256'],source=r['source'],observed_at=r['observed_at'],
                        available_at=r['created_at'],finding=p['finding'],verification=p['verification'],platform_verified=False,label_approved_for_training=False)
            save(db,key,str(id),old['version']+1,state,dict(command,observation_snapshot=snapshot,assessment_requirement=requirement if action=='check' else None))
            return jsonify(success=True,item=item(case(db,core,id)),event=event(db.execute('SELECT * FROM events WHERE id=?',(key,)).fetchone())),201
    app.register_blueprint(bp)
