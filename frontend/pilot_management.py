"""Append-only intervention diary, enabled only in guarded local pilot storage.

Separate database: no change to core migrations or the observation journal.
Declarations are not prescriptions, verified field data, or evidence of coverage.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from flask import Blueprint, current_app, g, jsonify, request
from pilot_journal import journal_db
from pilot_store import validate_storage


def now():return datetime.now(timezone.utc)


def initialize(path):
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM management_meta').fetchone()[0]
            except (sqlite3.Error,TypeError) as exc:raise ValueError('Unknown management database; refusing to modify it') from exc
            if kind!='aegis-pilot-management-v1':raise ValueError('Unknown management schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE management_meta(kind TEXT NOT NULL)')
        db.execute("INSERT INTO management_meta VALUES ('aegis-pilot-management-v1')")
        db.execute('''CREATE TABLE interventions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('synthetic','field_observed')),at TEXT NOT NULL,
            created_at TEXT NOT NULL,UNIQUE(id,user_id))''')
        db.execute('''CREATE TABLE intervention_revisions(id TEXT PRIMARY KEY,intervention_id TEXT NOT NULL,
            user_id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>=1),payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,change_reason TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL,
            UNIQUE(intervention_id,revision),FOREIGN KEY(intervention_id,user_id) REFERENCES interventions(id,user_id))''')
        db.execute('CREATE INDEX idx_management_owner ON interventions(user_id,season_id,at,id)')
        db.execute('''CREATE VIEW management_history AS SELECT r.*,i.season_id,i.source,i.at
            FROM intervention_revisions r JOIN interventions i ON i.id=r.intervention_id AND i.user_id=r.user_id''')
        db.execute('''CREATE VIEW management_current AS SELECT h.* FROM management_history h WHERE
            h.revision=(SELECT MAX(x.revision) FROM intervention_revisions x WHERE x.intervention_id=h.intervention_id)''')


def enable_management(app,storage):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Core storage must be the same isolated store')
    path=storage/'management.sqlite3';initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.blast_conditions import digest
    from app.farm import body,owned,paginate,within_season,FarmError,text,private,LimitResponse,limit_response
    bp=Blueprint('pilot_management',__name__,url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))
    fields={'kind','action_details','notes','record_status'}

    def instant(value):
        try:
            if not isinstance(value,str):raise ValueError()
            t=datetime.fromisoformat(value.replace('Z','+00:00'))
            if t.tzinfo is None or not 1900<=t.year<=2100:raise ValueError()
            return t.astimezone(timezone.utc)
        except (ValueError,OverflowError):raise FarmError('invalid_intervention','Thời điểm cần ISO8601 có timezone, năm 1900–2100.')

    def payload(data):
        if data['kind'] not in ['fungicide','fertilizer','irrigation','other'] or data['record_status'] not in ['active','voided']:
            raise FarmError('invalid_intervention','Loại can thiệp hoặc trạng thái không hợp lệ.')
        notes=data['notes']
        if not isinstance(notes,str) or len(notes)>2000 or any(ord(c)<32 and c not in '\n\r\t' for c in notes):
            raise FarmError('invalid_intervention','Ghi chú tối đa 2000 ký tự.')
        return dict(kind=data['kind'],action_details=text(data['action_details'],500),notes=notes.strip(),
                    record_status=data['record_status'],verification='user_reported',platform_verified=False)

    def record(db,identifier):
        row=db.execute('SELECT * FROM management_current WHERE intervention_id=? AND user_id=?',(str(identifier),g.user['id'])).fetchone()
        if row is None:raise FarmError('resource_not_found','Không tìm thấy can thiệp.',404)
        return row

    def serialize(row):
        return dict(id=row['intervention_id'],season_id=row['season_id'],source=row['source'],at=row['at'],
            revision=row['revision'],payload=json.loads(row['payload_json']),payload_sha256=row['payload_sha256'],
            change_reason=row['change_reason'],recorded_at=row['created_at'],available_at=row['created_at'],
            request_id=row['request_id'],management_stream_complete=False,training_approved=False)

    def save(db,identifier,revision,p,reason):
        db.execute('INSERT INTO intervention_revisions VALUES (?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()),identifier,g.user['id'],revision,json.dumps(p,ensure_ascii=False,allow_nan=False),digest(p),reason,now().isoformat(),g.request_id))

    @bp.route('/seasons/<uuid:identifier>/interventions',methods=['GET','POST'])
    @require_auth
    def interventions(identifier):
        data=body(fields|{'client_intervention_id','source','at','change_reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            season=owned(core,'seasons',identifier);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'management_current','season_id=? AND user_id=?',(season['id'],g.user['id']),serialize,order='at DESC,intervention_id DESC')
            try:identifier=str(uuid.UUID(data['client_intervention_id']))
            except (ValueError,TypeError,AttributeError):raise FarmError('invalid_intervention','client_intervention_id cần UUID.')
            at=instant(data['at'])
            if at>now():raise FarmError('invalid_intervention','Chỉ ghi việc đã thực hiện, không ghi thời điểm tương lai.')
            within_season(at,season)
            if data['source'] not in ['synthetic','field_observed']:raise FarmError('invalid_intervention','Nguồn không hợp lệ.')
            p=payload(data);reason=text(data['change_reason'],500)
            existing=db.execute('SELECT * FROM interventions WHERE id=?',(identifier,)).fetchone()
            if existing:
                first=db.execute('SELECT * FROM management_history WHERE intervention_id=? AND revision=1',(identifier,)).fetchone()
                if (existing['user_id']==g.user['id'] and existing['season_id']==season['id'] and existing['source']==data['source']
                    and existing['at']==at.isoformat() and first['payload_sha256']==digest(p) and first['change_reason']==reason):
                    r=jsonify(success=True,item=serialize(first));r.headers['Idempotency-Replayed']='true';return r
                raise FarmError('intervention_conflict','Mã lần ghi đã có nội dung khác; không ghi đè.',409)
            db.execute('INSERT INTO interventions VALUES (?,?,?,?,?,?)',(identifier,g.user['id'],season['id'],data['source'],at.isoformat(),now().isoformat()))
            save(db,identifier,1,p,reason)
            return jsonify(success=True,item=serialize(record(db,identifier))),201

    @bp.route('/interventions/<uuid:identifier>',methods=['GET','PUT'])
    @require_auth
    def detail(identifier):
        data=body(fields|{'base_revision','change_reason'}) if request.method=='PUT' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');old=record(db,identifier);owned(core,'seasons',old['season_id'])
            if data is None:return jsonify(success=True,item=serialize(old))
            if type(data['base_revision']) is not int or not 1<=data['base_revision']<=2147483647:raise FarmError('invalid_intervention','base_revision cần số nguyên dương.')
            p=payload(data);reason=text(data['change_reason'],500);same=old['payload_sha256']==digest(p)
            replay=same and data['base_revision']==old['revision']-1 and reason==old['change_reason']
            if data['base_revision']!=old['revision'] and not replay:raise FarmError('intervention_revision_conflict','Bản ghi đã đổi; tải lại để đối chiếu.',409)
            if same:
                r=jsonify(success=True,item=serialize(old));r.headers['Idempotency-Replayed']='true';return r
            save(db,str(identifier),old['revision']+1,p,reason)
            return jsonify(success=True,item=serialize(record(db,identifier))),201

    @bp.get('/interventions/<uuid:identifier>/revisions')
    @require_auth
    def revisions(identifier):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');old=record(db,identifier);owned(core,'seasons',old['season_id'])
            return paginate(db,'management_history','intervention_id=? AND user_id=?',(str(identifier),g.user['id']),serialize,order='revision DESC')
    app.register_blueprint(bp)
