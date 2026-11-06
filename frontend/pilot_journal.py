"""Opt-in journal in its OWN SQLite file, never a core Backend migration.

Enabled only by the isolated local UI launcher. External reviews are declarations,
not platform verification or approved ML labels.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import json
import sqlite3
import uuid
from flask import Blueprint,current_app,g,jsonify,request
from pilot_store import validate_storage


@contextmanager
def journal_db(path):
    db=sqlite3.connect(path,timeout=15);db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:yield db
    finally:db.close()


def initialize(path):
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM journal_meta').fetchone()[0]
            except sqlite3.Error as exc:raise ValueError('Unknown journal database; refusing to modify it') from exc
            if kind!='aegis-pilot-journal-v1':raise ValueError('Unknown journal schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE journal_meta(kind TEXT NOT NULL)')
        db.execute("INSERT INTO journal_meta VALUES ('aegis-pilot-journal-v1')")
        db.execute('''CREATE TABLE visits(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('synthetic','field_observed')),observed_at TEXT NOT NULL,
            scheduled INTEGER NOT NULL CHECK(scheduled IN (0,1)),created_at TEXT NOT NULL,UNIQUE(id,user_id))''')
        db.execute('''CREATE TABLE revisions(id TEXT PRIMARY KEY,visit_id TEXT NOT NULL,user_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK(revision>=1),payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
            change_reason TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL,
            UNIQUE(visit_id,revision),FOREIGN KEY(visit_id,user_id) REFERENCES visits(id,user_id))''')
        db.execute('CREATE INDEX idx_journal_owner ON visits(user_id,season_id,observed_at,id)')
        db.execute('''CREATE VIEW history AS SELECT r.*,v.season_id,v.source,v.observed_at,v.scheduled
            FROM revisions r JOIN visits v ON v.id=r.visit_id AND v.user_id=r.user_id''')
        db.execute('''CREATE VIEW current_records AS SELECT h.* FROM history h WHERE
            h.revision=(SELECT MAX(x.revision) FROM revisions x WHERE x.visit_id=h.visit_id)''')


def now():return datetime.now(timezone.utc)


def enable_journal(app,storage):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Core storage must be the same isolated store')
    path=storage/'journal.sqlite3'
    initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.blast_conditions import digest
    from app.farm import body,owned,paginate,within_season,FarmError,text,private,LimitResponse,limit_response
    journal=Blueprint('pilot_journal',__name__,url_prefix='/api/farm')
    journal.after_request(private)
    journal.register_error_handler(LimitResponse,limit_response)
    journal.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))
    fields={'finding','notes','analysis_id','review','record_status'}

    def instant(value):
        try:
            if not isinstance(value,str):raise ValueError()
            t=datetime.fromisoformat(value.replace('Z','+00:00'))
            if t.tzinfo is None:raise ValueError()
            t=t.astimezone(timezone.utc)
            if not 1900<=t.year<=2100:raise ValueError()
            return t
        except (ValueError,OverflowError):raise FarmError('invalid_observation','Thời điểm cần ISO8601 có timezone, năm1900–2100.')

    def owned_visit(db,identifier):
        row=db.execute('SELECT * FROM visits WHERE id=? AND user_id=?',(str(identifier),g.user['id'])).fetchone()
        if row is None:raise FarmError('resource_not_found','Không tìm thấy quan sát.',404)
        return row

    def latest(db,identifier):return db.execute('SELECT * FROM current_records WHERE visit_id=? AND user_id=?',(str(identifier),g.user['id'])).fetchone()

    def serialize(row):
        return dict(id=row['visit_id'],season_id=row['season_id'],source=row['source'],disease='leaf_blast',plant_part='leaf',
            observed_at=row['observed_at'],scheduled=bool(row['scheduled']),revision=row['revision'],
            payload=json.loads(row['payload_json']),payload_sha256=row['payload_sha256'],change_reason=row['change_reason'],
            recorded_at=row['created_at'],available_at=row['created_at'],request_id=row['request_id'],label_approved_for_training=False)

    def validate(data,observed,core):
        if data['finding'] not in ['absent','present','uncertain'] or data['record_status'] not in ['active','voided']:
            raise FarmError('invalid_observation','Nhận xét hoặc trạng thái bản ghi không hợp lệ.')
        notes=data['notes']
        if not isinstance(notes,str) or len(notes)>2000 or any(ord(c)<32 and c not in '\n\r\t' for c in notes):raise FarmError('invalid_observation','Ghi chú tối đa2000ký tự.')
        analysis=data['analysis_id']
        if analysis is not None:
            try:analysis=str(uuid.UUID(analysis))
            except (ValueError,TypeError,AttributeError):raise FarmError('invalid_observation','analysis_id cần UUID hoặc null.')
            if not core.execute('SELECT 1 FROM analyses WHERE id=? AND user_id=?',(analysis,g.user['id'])).fetchone():raise FarmError('resource_not_found','Không tìm thấy ảnh thuộc tài khoản.',404)
        review=data['review']
        if review is not None:
            if not isinstance(review,dict) or set(review)!={'reviewer_alias','reviewed_at','reference'}:raise FarmError('invalid_observation','Xác minh cần người/đơn vị, thời điểm và tham chiếu.')
            t=instant(review['reviewed_at'])
            if not observed<=t<=now() or data['finding']=='uncertain':raise FarmError('invalid_observation','Thời điểm/nhận xét chưa phù hợp để khai báo xác minh.')
            review=dict(reviewer_alias=text(review['reviewer_alias']),reviewed_at=t.isoformat(),reference=text(review['reference'],500))
        return dict(finding=data['finding'],notes=notes.strip(),analysis_id=analysis,review=review,record_status=data['record_status'],
            verification='confirmed' if review else 'unverified',verification_provenance='user_reported_external_review' if review else 'not_verified',platform_verified=False)

    def save(db,visit_id,revision,payload,reason):
        db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),visit_id,g.user['id'],revision,
            json.dumps(payload,ensure_ascii=False,allow_nan=False),digest(payload),reason,now().isoformat(),g.request_id))

    @journal.route('/seasons/<uuid:identifier>/observations',methods=['GET','POST'])
    @require_auth
    def observations(identifier):
        data=body({'client_visit_id','source','observed_at','scheduled','change_reason'}|fields) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            season=owned(core,'seasons',identifier);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'current_records','season_id=? AND user_id=?',(season['id'],g.user['id']),serialize,order='observed_at DESC,visit_id DESC')
            try:visit_id=str(uuid.UUID(data['client_visit_id']))
            except (ValueError,TypeError,AttributeError):raise FarmError('invalid_observation','client_visit_id cần UUID.')
            observed=instant(data['observed_at'])
            if observed>now():raise FarmError('invalid_observation','Không ghi quan sát ở tương lai.')
            within_season(observed,season)
            if data['source'] not in ['synthetic','field_observed'] or type(data['scheduled']) is not bool:raise FarmError('invalid_observation','Nguồn/cờ theo lịch không hợp lệ.')
            payload=validate(data,observed,core);reason=text(data['change_reason'],500)
            existing=db.execute('SELECT * FROM visits WHERE id=?',(visit_id,)).fetchone()
            if existing:
                first=db.execute('SELECT * FROM history WHERE visit_id=? AND revision=1',(visit_id,)).fetchone()
                if (existing['user_id']==g.user['id'] and existing['season_id']==season['id'] and existing['source']==data['source'] and existing['observed_at']==observed.isoformat()
                    and bool(existing['scheduled'])==data['scheduled'] and first['payload_sha256']==digest(payload) and first['change_reason']==reason):
                    response=jsonify(success=True,item=serialize(first));response.headers['Idempotency-Replayed']='true';return response
                raise FarmError('observation_conflict','Mã lần ghi đã có nội dung khác; không ghi đè.',409)
            db.execute('INSERT INTO visits VALUES (?,?,?,?,?,?,?)',(visit_id,g.user['id'],season['id'],data['source'],observed.isoformat(),int(data['scheduled']),now().isoformat()))
            save(db,visit_id,1,payload,reason)
            return jsonify(success=True,item=serialize(latest(db,visit_id))),201

    @journal.route('/observations/<uuid:identifier>',methods=['GET','PUT'])
    @require_auth
    def detail(identifier):
        data=body({'base_revision','change_reason'}|fields) if request.method=='PUT' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');visit=owned_visit(db,identifier);old=latest(db,identifier)
            owned(core,'seasons',visit['season_id'])
            if data is None:return jsonify(success=True,item=serialize(old))
            if type(data['base_revision']) is not int or not 1<=data['base_revision']<=2147483647:raise FarmError('invalid_observation','base_revision cần số nguyên dương.')
            payload=validate(data,instant(visit['observed_at']),core);reason=text(data['change_reason'],500)
            same=old['payload_sha256']==digest(payload);replay=same and data['base_revision']==old['revision']-1 and reason==old['change_reason']
            if data['base_revision']!=old['revision'] and not replay:raise FarmError('observation_revision_conflict','Bản ghi đã đổi; tải lại và đối chiếu.',409)
            if same:
                response=jsonify(success=True,item=serialize(old));response.headers['Idempotency-Replayed']='true';return response
            save(db,visit['id'],old['revision']+1,payload,reason)
            return jsonify(success=True,item=serialize(latest(db,identifier))),201

    @journal.get('/observations/<uuid:identifier>/revisions')
    @require_auth
    def history(identifier):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');visit=owned_visit(db,identifier);owned(core,'seasons',visit['season_id'])
            return paginate(db,'history','visit_id=? AND user_id=?',(str(identifier),g.user['id']),serialize,order='revision DESC')
    app.register_blueprint(journal)
