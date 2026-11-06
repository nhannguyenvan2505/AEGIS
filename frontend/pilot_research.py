"""Shared append-only pilot ledger, never a core Backend migration."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import uuid
from flask import g
from pilot_journal import journal_db
from pilot_store import validate_storage


def now():return datetime.now(timezone.utc)


def initialize(path):
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM research_meta').fetchone()[0]
            except (sqlite3.Error,TypeError) as exc:raise ValueError('Unknown research database; refusing to modify it') from exc
            if kind!='aegis-pilot-research-v1':raise ValueError('Unknown research schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE research_meta(kind TEXT NOT NULL)');db.execute("INSERT INTO research_meta VALUES ('aegis-pilot-research-v1')")
        db.execute('''CREATE TABLE records(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            kind TEXT NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL)''')
        db.execute('''CREATE TABLE events(id TEXT PRIMARY KEY,record_id TEXT NOT NULL REFERENCES records(id),
            version INTEGER NOT NULL,actor_id TEXT NOT NULL,state TEXT NOT NULL,command_json TEXT NOT NULL,
            command_sha256 TEXT NOT NULL,data_json TEXT NOT NULL,data_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,
            request_id TEXT NOT NULL,UNIQUE(record_id,version))''')
        db.execute('CREATE INDEX idx_research_owner ON records(user_id,season_id,kind,created_at,id)')
        db.execute('''CREATE VIEW current_records AS SELECT r.*,e.version,e.state,e.data_json AS current_data_json,
            e.created_at AS updated_at FROM records r JOIN events e ON e.record_id=r.id
            WHERE e.version=(SELECT MAX(x.version) FROM events x WHERE x.record_id=r.id)''')


def storage_path(app,storage):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Wrong isolated store')
    path=storage/'research.sqlite3';initialize(path);return path


def instant(v):
    from app.farm import FarmError
    try:
        if not isinstance(v,str):raise ValueError()
        t=datetime.fromisoformat(v.replace('Z','+00:00'))
        if t.tzinfo is None or not 1900<=t.year<=2100:raise ValueError()
        return t.astimezone(timezone.utc)
    except (ValueError,OverflowError):raise FarmError('invalid_research','Thời điểm cần ISO8601 có timezone, năm 1900–2100.')


def identifier(v):
    from app.farm import FarmError
    try:return str(uuid.UUID(v))
    except (ValueError,TypeError,AttributeError):raise FarmError('invalid_research','Cần UUID hợp lệ.')


def digest(v):
    from app.blast_conditions import digest as sha
    return sha(v)


def get(db,id,kind=None):
    r=db.execute('SELECT * FROM current_records WHERE id=?',(str(id),)).fetchone()
    if r is None or kind and r['kind']!=kind:
        from app.farm import FarmError
        raise FarmError('resource_not_found','Không tìm thấy bản ghi.',404)
    return r


def owned_record(db,core,id,kind):
    from app.farm import FarmError,owned
    r=get(db,id,kind)
    if r['user_id']!=g.user['id']:raise FarmError('resource_not_found','Không tìm thấy bản ghi.',404)
    owned(core,'seasons',r['season_id']);return r


def replay_create(db,id,season,kind,command):
    from app.farm import FarmError
    r=db.execute('SELECT * FROM current_records WHERE id=?',(id,)).fetchone()
    if r is None:return None
    first=db.execute('SELECT command_sha256 FROM events WHERE record_id=? AND version=1',(id,)).fetchone()
    if r['user_id']!=g.user['id'] or r['season_id']!=season or r['kind']!=kind or first[0]!=digest(command):
        raise FarmError('research_conflict','UUID đã có nội dung khác.',409)
    return r


def append(db,record_id,event_id,version,state,command,data):
    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)',(event_id,record_id,version,g.user['id'],state,
        json.dumps(command,ensure_ascii=False,allow_nan=False),digest(command),json.dumps(data,ensure_ascii=False,allow_nan=False),digest(data),now().isoformat(),g.request_id))


def create(db,id,season,kind,meta,state,command,data):
    db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?)',(id,g.user['id'],season,kind,json.dumps(meta,ensure_ascii=False,allow_nan=False),digest(meta),now().isoformat(),g.request_id))
    append(db,id,str(uuid.uuid4()),1,state,command,data);return get(db,id)


def replay_event(db,r,command):
    from app.farm import FarmError
    key=identifier(command['client_event_id']);base=command['base_version']
    if type(base) is not int or not 1<=base<=2147483647:raise FarmError('invalid_research','base_version cần số nguyên dương.')
    old=db.execute('SELECT * FROM events WHERE id=?',(key,)).fetchone()
    if old:
        if old['record_id']!=r['id'] or old['actor_id']!=g.user['id'] or old['command_sha256']!=digest(command):raise FarmError('research_event_conflict','UUID hành động đã có nội dung khác.',409)
        return old
    if base!=r['version']:raise FarmError('research_version_conflict','Bản ghi đã đổi; tải lại.',409)
    return None


def serialize(r):
    return dict(id=r['id'],season_id=r['season_id'],kind=r['kind'],version=r['version'],state=r['state'],metadata=json.loads(r['payload_json']),
        metadata_sha256=r['payload_sha256'],current=json.loads(r['current_data_json']),created_at=r['created_at'],updated_at=r['updated_at'],training_approved=False)


def serialize_event(r):return dict(id=r['id'],version=r['version'],actor_id=r['actor_id'],state=r['state'],data=json.loads(r['data_json']),data_sha256=r['data_sha256'],recorded_at=r['created_at'],request_id=r['request_id'])


def observation(storage,owner,season,id):
    from app.farm import FarmError
    with journal_db(storage/'journal.sqlite3') as db:
        db.execute('BEGIN');r=db.execute('SELECT * FROM current_records WHERE visit_id=? AND user_id=? AND season_id=?',(id,owner,season)).fetchone()
        if r is None:raise FarmError('resource_not_found','Không tìm thấy quan sát cùng mùa vụ.',404)
        return dict(id=r['visit_id'],revision=r['revision'],source=r['source'],observed_at=r['observed_at'],scheduled_declared=bool(r['scheduled']),
            available_at=r['created_at'],payload=json.loads(r['payload_json']),payload_sha256=r['payload_sha256'])


def inventory(storage,owner,season,source,start,end):
    with journal_db(storage/'management.sqlite3') as db:
        db.execute('BEGIN');rows=db.execute('SELECT * FROM management_current WHERE user_id=? AND season_id=? AND source=? AND at>=? AND at<? ORDER BY intervention_id',(owner,season,source,start,end)).fetchall()
        all_rows=[dict(id=r['intervention_id'],revision=r['revision'],payload_sha256=r['payload_sha256'],record_status=json.loads(r['payload_json'])['record_status'],at=r['at']) for r in rows]
    return dict(records=all_rows,active_count=sum(r['record_status']=='active' for r in all_rows),sha256=digest(all_rows))
