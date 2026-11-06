"""Operational mock follow-up groups, not epidemiological disease episodes.

Additive tables in the opt-in followup DB. No core migration or model changes.
"""
from datetime import datetime, timezone, timedelta
import json
import uuid
from flask import Blueprint, current_app, g, jsonify, request
from pilot_journal import journal_db
from pilot_store import validate_storage


def now():return datetime.now(timezone.utc)


def initialize(path):
    with journal_db(path) as db:
        if db.execute('SELECT kind FROM followup_meta').fetchone()[0]!='aegis-pilot-followup-v1':raise ValueError('Wrong followup store')
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='episode_meta'").fetchone():
            if db.execute('SELECT kind FROM episode_meta').fetchone()[0]!='aegis-mock-episodes-v1':raise ValueError('Unknown episode schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE episode_meta(kind TEXT NOT NULL)')
        db.execute("INSERT INTO episode_meta VALUES ('aegis-mock-episodes-v1')")
        db.execute('''CREATE TABLE episodes(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            device_id TEXT NOT NULL,profile_sha256 TEXT NOT NULL,task_kind TEXT NOT NULL,case_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,FOREIGN KEY(case_id,user_id) REFERENCES cases(id,user_id))''')
        db.execute('''CREATE TABLE episode_members(id TEXT PRIMARY KEY,episode_id TEXT NOT NULL REFERENCES episodes(id),
            assessment_id TEXT NOT NULL,window_end TEXT NOT NULL,status TEXT NOT NULL,snapshot_json TEXT NOT NULL,
            snapshot_sha256 TEXT NOT NULL,recorded_at TEXT NOT NULL,request_id TEXT NOT NULL,
            UNIQUE(episode_id,assessment_id))''')
        db.execute('CREATE INDEX idx_episode_scope ON episodes(user_id,season_id,device_id,profile_sha256,task_kind)')
        db.execute('''CREATE VIEW episode_heads AS SELECT p.*,c.state,c.version,c.updated_at,
            (SELECT MIN(window_end) FROM episode_members m WHERE m.episode_id=p.id) first_window,
            (SELECT MAX(window_end) FROM episode_members m WHERE m.episode_id=p.id) latest_window,
            (SELECT COUNT(*) FROM episode_members m WHERE m.episode_id=p.id) assessment_count
            FROM episodes p JOIN current_cases c ON c.id=p.case_id AND c.user_id=p.user_id''')


def linked_case(db,assessment_id,owner):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='episode_members'").fetchone():return None
    return db.execute('''SELECT c.* FROM current_cases c JOIN episodes p ON p.case_id=c.id
        JOIN episode_members m ON m.episode_id=p.id WHERE m.assessment_id=? AND p.user_id=?
        AND ((m.status='advisory' AND p.task_kind='check_conditions') OR
             (m.status='insufficient_data' AND p.task_kind='check_data')) LIMIT 1''',(assessment_id,owner)).fetchone()


def attach_assessment(db,owner,a,reason,request_id,at,origin):
    """Caller holds BEGIN IMMEDIATE in followup DB: group + case + links atomic."""
    from app.blast_conditions import digest
    from pilot_followup import ensure_case
    if a['user_id']!=owner or a['input']['source']!='mock':raise ValueError('Wrong episode scope')
    status=a['result']['status'];kind={'advisory':'check_conditions','insufficient_data':'check_data'}.get(status)
    profile=digest(a['profile']);case=None;created=False
    # Retries keep the original assignment even after closing the group.
    existing=linked_case(db,a['id'],owner) if kind else None
    active=db.execute('''SELECT * FROM episode_heads WHERE user_id=? AND device_id=? AND
        season_id=? AND profile_sha256=? AND state!='closed' ORDER BY created_at,id''',
        (owner,a['device_id'],a['season_id'],profile)).fetchall()
    targets=list(active)
    if kind:
        matched=next((p for p in active if p['task_kind']==kind),None)
        if existing:
            case=existing
        elif matched:
            case=db.execute('SELECT * FROM current_cases WHERE id=?',(matched['case_id'],)).fetchone()
        else:
            case,created=ensure_case(db,owner,a,reason,request_id,at,origin)
            eid=str(uuid.uuid4())
            db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?)',(eid,owner,a['season_id'],a['device_id'],profile,kind,case['id'],at.isoformat()))
            targets.append(db.execute('SELECT * FROM episode_heads WHERE id=?',(eid,)).fetchone())
    if existing:
        p=db.execute('SELECT * FROM episode_heads WHERE case_id=?',(existing['id'],)).fetchone()
        if p and all(t['id']!=p['id'] for t in targets):targets.append(p)
    ids=[]
    for p in targets:
        # Never send a late historical window into a newer group.
        if p['first_window'] and a['result']['window_end']<p['first_window']:continue
        db.execute('INSERT OR IGNORE INTO episode_members VALUES (?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()),p['id'],a['id'],a['result']['window_end'],status,json.dumps(a,ensure_ascii=False),digest(a),at.isoformat(),request_id))
        ids.append(p['id'])
    return case,created,ids


def check_requirement(db,case_id):
    """Newest relevant snapshot; weak/absent patterns never erase prior requirements."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='episodes'").fetchone():return None
    p=db.execute('SELECT * FROM episodes WHERE case_id=?',(case_id,)).fetchone()
    if not p:return None
    status='advisory' if p['task_kind']=='check_conditions' else None
    m=db.execute("SELECT * FROM episode_members WHERE episode_id=? AND (? IS NULL OR status=?) ORDER BY window_end DESC,COALESCE(json_extract(snapshot_json,'$.assessment_revision'),1) DESC,recorded_at DESC,id DESC LIMIT 1",(p['id'],status,status)).fetchone()
    return dict(episode_id=p['id'],window_end=m['window_end'],recorded_at=m['recorded_at'],assessment_id=m['assessment_id'],revision=json.loads(m['snapshot_json']).get('assessment_revision',1)) if m else None


def serialize(db,p,storage):
    from pilot_followup import check_status
    requirement=check_requirement(db,p['case_id'])
    case_row=db.execute('SELECT * FROM current_cases WHERE id=?',(p['case_id'],)).fetchone()
    status=check_status(db,case_row,storage)
    latest=db.execute("SELECT * FROM episode_members WHERE episode_id=? ORDER BY window_end DESC,COALESCE(json_extract(snapshot_json,'$.assessment_revision'),1) DESC,recorded_at DESC,id DESC LIMIT 1",(p['id'],)).fetchone()
    return dict(p,source='mock',field_validated=False,disease_confirmed=False,needs_recheck=status['needs_recheck'],check_status=status,
        required_check=requirement,latest_status=latest['status'] if latest else None,
        latest_assessment_id=latest['assessment_id'] if latest else None)


def enable_episodes(app,storage):
    storage=validate_storage(storage);path=storage/'followup.sqlite3';initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.farm import owned,paginate,private,FarmError
    from pilot_timeline import read_store
    bp=Blueprint('pilot_episodes',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def episode(db,core,id):
        p=db.execute('SELECT * FROM episode_heads WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
        if p is None:raise FarmError('resource_not_found','Không tìm thấy đợt theo dõi.',404)
        owned(core,'seasons',p['season_id']);return p

    @bp.get('/seasons/<uuid:id>/warning-episodes')
    @require_auth
    def listing(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            owned(core,'seasons',id);db.execute('BEGIN')
            return paginate(db,'episode_heads','user_id=? AND season_id=?',(g.user['id'],str(id)),lambda p:serialize(db,p,storage),order="(state='closed'),latest_window DESC,id")

    @bp.get('/warning-episodes/<uuid:id>')
    @require_auth
    def detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=serialize(db,episode(db,core,id),storage))

    @bp.get('/warning-episodes/<uuid:id>/assessments')
    @require_auth
    def members(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');episode(db,core,id)
            def item(r):
                d=dict(r);d['snapshot']=json.loads(d.pop('snapshot_json'));return d
            return paginate(db,'episode_members','episode_id=?',(str(id),),item,order='window_end DESC,id')

    @bp.get('/seasons/<uuid:id>/warning-dashboard')
    @require_auth
    def dashboard(id):
        # A read-only view, no assessment creation, no worker tick or state transitions.
        with read_store(storage) as db:
            owned(db,'seasons',id);uid=g.user['id'];at=now();end=at.replace(minute=0,second=0,microsecond=0)
            count=dict(db.execute('''SELECT COUNT(*) total,SUM(state!='closed') open_count,
                SUM(state!='closed' AND task_kind='check_conditions') conditions_count,
                SUM(state!='closed' AND task_kind='check_data') data_count
                FROM workflow.episode_heads WHERE user_id=? AND season_id=?''',(uid,str(id))).fetchone())
            count={k:v or 0 for k,v in count.items()}
            legacy=db.execute('''SELECT COUNT(*) FROM workflow.current_cases c WHERE user_id=? AND season_id=?
                AND state!='closed' AND NOT EXISTS(SELECT 1 FROM workflow.episodes p WHERE p.case_id=c.id)''',(uid,str(id))).fetchone()[0]
            obs=db.execute('''SELECT visit_id,observed_at,created_at,payload_json,source FROM journal.current_records
                WHERE user_id=? AND season_id=? AND json_extract(payload_json,'$.record_status')='active'
                ORDER BY observed_at DESC,created_at DESC,visit_id DESC LIMIT 1''',(uid,str(id))).fetchone()
            observation=None if obs is None else dict(id=obs['visit_id'],observed_at=obs['observed_at'],recorded_at=obs['created_at'],source=obs['source'],finding=json.loads(obs['payload_json'])['finding'],platform_verified=False)
            # Correlated indexed lookups keep this scoped to this owner's season.
            table='''(SELECT d.*,
                (SELECT MAX(t.start_at) FROM farm_telemetry t WHERE t.user_id=d.user_id AND t.device_id=d.id AND t.start_at<?) latest_bucket,
                (SELECT COALESCE((SELECT v.snapshot_json FROM workflow.assessment_versions v WHERE v.base_assessment_id=a.id AND v.user_id=a.user_id ORDER BY v.revision DESC LIMIT 1),a.snapshot_json) FROM farm_assessments a WHERE a.user_id=d.user_id AND a.device_id=d.id ORDER BY a.window_end DESC LIMIT 1) latest_assessment,
                (SELECT COUNT(*) FROM workflow.episode_heads p WHERE p.user_id=d.user_id AND p.device_id=d.id AND p.state!='closed') open_episodes
                FROM farm_devices d)'''
            # paginate binds its params in both count and select; the subquery uses a literal safe ISO timestamp.
            table=table.replace('t.start_at<?','t.start_at<\''+end.isoformat()+'\'')
            def device(r):
                a=json.loads(r['latest_assessment']) if r['latest_assessment'] else None
                freshness='missing' if r['latest_bucket'] is None else 'stale' if datetime.fromisoformat(r['latest_bucket'])+timedelta(hours=1)<end else 'window_end_bucket_present'
                return dict(id=r['id'],name=r['name'],source=r['source'],latest_bucket=r['latest_bucket'],freshness=freshness,
                    open_episodes=r['open_episodes'],latest_assessment=None if not a else dict(id=a['id'],base_assessment_id=a.get('base_assessment_id',a['id']),revision=a.get('assessment_revision',1),status=a['result']['status'],window_end=a['result']['window_end'],expired=datetime.fromisoformat(a['valid_until'])<=at),
                    priority='check_data' if freshness!='window_end_bucket_present' else 'check_followup' if r['open_episodes'] else 'review_context')
            response=paginate(db,table,'user_id=? AND season_id=?',(uid,str(id)),device,
                order="(latest_bucket IS NOT NULL),latest_bucket,id")
            data=response.get_json();data.update(at_utc=at.isoformat(),source='mock',field_validated=False,
                counts=dict(count,legacy_open_cases=legacy),latest_observation=observation,
                data_scope='hourly_mock_only; raw sensor streams are not aggregated here')
            return jsonify(data)
    app.register_blueprint(bp)
