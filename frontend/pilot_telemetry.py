"""Opt-in raw environmental observations. No hourly aggregation or forecast.

Technical bounds are shared with the temporal design, not disease thresholds.
Source, instrumentation and quality are declarations, never validated by a name.
"""
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import sqlite3
import uuid
from flask import Blueprint,current_app,g,jsonify,request
from pilot_journal import journal_db
from pilot_store import validate_storage
import controlled_source as controlled

SCHEMA='aegis-pilot-telemetry-v1'
QC_VERSION='aegis-raw-qc-v1'


def now():return datetime.now(timezone.utc)


def initialize(path):
    from app.hybrid_pilot import initialized
    if initialized(path): return
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM telemetry_meta').fetchone()[0]
            except (sqlite3.Error,TypeError) as exc:raise ValueError('Unknown telemetry database; refusing to modify it') from exc
            if kind!=SCHEMA:raise ValueError('Unknown telemetry schema')
            return
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE telemetry_meta(kind TEXT NOT NULL)');db.execute('INSERT INTO telemetry_meta VALUES (?)',(SCHEMA,))
        db.execute('''CREATE TABLE streams(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            client_stream_id TEXT NOT NULL,metadata_json TEXT NOT NULL,metadata_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,request_id TEXT NOT NULL,UNIQUE(id,user_id),UNIQUE(user_id,client_stream_id))''')
        db.execute('''CREATE TABLE samples(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,stream_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
            qc_json TEXT NOT NULL,received_at TEXT NOT NULL,request_id TEXT NOT NULL,
            UNIQUE(stream_id,observed_at),UNIQUE(id,user_id),
            FOREIGN KEY(stream_id,user_id) REFERENCES streams(id,user_id))''')
        db.execute('''CREATE TABLE exclusions(sample_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,
            reason TEXT NOT NULL,recorded_at TEXT NOT NULL,request_id TEXT NOT NULL,
            FOREIGN KEY(sample_id,user_id) REFERENCES samples(id,user_id))''')
        db.execute('CREATE INDEX idx_raw_owner ON samples(user_id,stream_id,observed_at,id)')
        db.execute('CREATE INDEX idx_stream_owner ON streams(user_id,season_id,created_at,id)')
        db.execute('''CREATE VIEW raw_records AS SELECT s.*,e.reason AS exclusion_reason,e.recorded_at AS excluded_at,
            e.request_id AS exclusion_request_id FROM samples s LEFT JOIN exclusions e ON e.sample_id=s.id''')


def enable_telemetry(app,storage,controlled_experiments_enabled=False):
    if type(controlled_experiments_enabled) is not bool:raise ValueError('Controlled experiments opt-in must be boolean')
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Core storage must be the same isolated store')
    path=storage/'telemetry.sqlite3';initialize(path)
    from app.auth import require_auth
    from app.storage import connect
    from app.blast_conditions import digest
    from app.farm import body,owned,paginate,within_season,FarmError,text,private,LimitResponse,limit_response
    bp=Blueprint('pilot_telemetry',__name__,url_prefix='/api/farm')
    bp.after_request(private);bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def controlled_write(metadata):
        if metadata['source']==controlled.SOURCE and not controlled_experiments_enabled:
            raise FarmError('controlled_source_disabled','Nguồn khay/chậu cần opt-in raw controlled experiments.',403)

    def instant(v):
        try:
            if not isinstance(v,str):raise ValueError()
            t=datetime.fromisoformat(v.replace('Z','+00:00'))
            if t.tzinfo is None or not 1900<=t.year<=2100:raise ValueError()
            return t.astimezone(timezone.utc)
        except (ValueError,OverflowError):raise FarmError('invalid_telemetry','Thời điểm cần ISO8601 có timezone, năm 1900–2100.')

    def identifier(v):
        try:return str(uuid.UUID(v))
        except (ValueError,TypeError,AttributeError):raise FarmError('invalid_telemetry','Mã client cần UUID.')

    def stream_item(r):
        return dict(id=r['id'],season_id=r['season_id'],client_stream_id=r['client_stream_id'],metadata=json.loads(r['metadata_json']),
            metadata_sha256=r['metadata_sha256'],created_at=r['created_at'],request_id=r['request_id'],training_approved=False)

    def stream(db,core,id):
        r=db.execute('SELECT * FROM streams WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
        if r is None:raise FarmError('resource_not_found','Không tìm thấy nguồn đo.',404)
        return r,owned(core,'seasons',r['season_id'])

    def sample_item(r,metadata):
        result=dict(id=r['id'],stream_id=r['stream_id'],observed_at=r['observed_at'],payload=json.loads(r['payload_json']),
            payload_sha256=r['payload_sha256'],qc=json.loads(r['qc_json']),received_at=r['received_at'],available_at=r['received_at'],
            request_id=r['request_id'],training_approved=False,
            exclusion=None if r['excluded_at'] is None else dict(reason=r['exclusion_reason'],recorded_at=r['excluded_at'],request_id=r['exclusion_request_id']))
        if metadata['source']==controlled.SOURCE:
            result.update(declared_source=controlled.SOURCE,experiment_context_sha256=digest(metadata['experiment_context']))
        return result

    @bp.route('/seasons/<uuid:id>/environment-streams',methods=['GET','POST'])
    @require_auth
    def streams(id):
        data=body({'client_stream_id','name','source','method','instrument','reference','nominal_interval_seconds'},{'experiment_context'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            season=owned(core,'seasons',id);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:
                selected=request.args.getlist('source')
                if len(selected)>1 or selected and selected[0] not in controlled.SOURCES:raise FarmError('invalid_telemetry','Bộ lọc nguồn không hợp lệ.')
                where='season_id=? AND user_id=?';values=(season['id'],g.user['id'])
                if selected:
                    where+=" AND json_extract(metadata_json,'$.source')=?";values+=(selected[0],)
                if set(request.args)-{'source','page','page_size'}:raise FarmError('invalid_pagination','Tham số không hợp lệ.')
                paging=[]
                for name,default,maximum in [('page','1',1000000),('page_size','20',100)]:
                    value=request.args.get(name,default)
                    if len(request.args.getlist(name))>1 or not value.isascii() or not value.isdigit() or len(value)>7 or not 1<=int(value)<=maximum:
                        raise FarmError('invalid_pagination','Phân trang không hợp lệ.')
                    paging.append(int(value))
                page,size=paging
                total=db.execute('SELECT COUNT(*) FROM streams WHERE '+where,values).fetchone()[0]
                rows=db.execute('SELECT * FROM streams WHERE '+where+' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(*values,size,(page-1)*size)).fetchall()
                pages=(total+size-1)//size
                return jsonify(success=True,items=[stream_item(r) for r in rows],pagination=dict(page=page,page_size=size,total=total,total_pages=pages,has_next=page<pages))
            key=identifier(data['client_stream_id']);interval=data['nominal_interval_seconds']
            if data['source'] not in controlled.SOURCES or data['method'] not in ['sensor_reading','manual_reading']:
                raise FarmError('invalid_telemetry','Nguồn hoặc phương pháp đo không hợp lệ.')
            if interval is not None and (type(interval) is not int or not 1<=interval<=86400):raise FarmError('invalid_telemetry','Chu kỳ khai báo cần 1–86400 giây hoặc null.')
            m=dict(name=text(data['name']),source=data['source'],method=data['method'],instrument=text(data['instrument'],500),reference=text(data['reference'],500),
                nominal_interval_seconds=interval,measurement_semantics='point_observation',units=dict(air_temperature_c='degC',relative_humidity_pct='percent',leaf_wet='boolean_point_state'),
                provenance='user_declared',calibration_verified=False)
            if data['source']==controlled.SOURCE:
                controlled_write(m)
                try:experiment=controlled.context(data.get('experiment_context'))
                except ValueError as exc:raise FarmError('invalid_telemetry',str(exc)) from exc
                m.update(schema_version=controlled.METADATA_SCHEMA,experiment_context=experiment,source_policy=dict(controlled.POLICY))
            elif 'experiment_context' in data:raise FarmError('invalid_telemetry','Ngữ cảnh khay chỉ dùng với controlled_experiment.')
            existing=db.execute('SELECT * FROM streams WHERE user_id=? AND client_stream_id=?',(g.user['id'],key)).fetchone()
            if existing:
                if existing['season_id']!=season['id'] or existing['metadata_sha256']!=digest(m):raise FarmError('stream_conflict','UUID nguồn đo đã có nội dung khác.',409)
                r=jsonify(success=True,item=stream_item(existing));r.headers['Idempotency-Replayed']='true';return r
            id=str(uuid.uuid4());db.execute('INSERT INTO streams VALUES (?,?,?,?,?,?,?,?)',(id,g.user['id'],season['id'],key,json.dumps(m,ensure_ascii=False),digest(m),now().isoformat(),g.request_id))
            return jsonify(success=True,item=stream_item(stream(db,core,id)[0])),201

    @bp.route('/environment-streams/<uuid:id>/samples',methods=['GET','POST'])
    @require_auth
    def samples(id):
        data=body({'records'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');parent,season=stream(db,core,id)
            metadata=json.loads(parent['metadata_json'])
            if data is None:return paginate(db,'raw_records','stream_id=? AND user_id=?',(str(id),g.user['id']),lambda r:sample_item(r,metadata),order='observed_at DESC,id DESC')
            controlled_write(metadata)
            raw=data['records']
            if not isinstance(raw,list) or not 1<=len(raw)<=100:raise FarmError('invalid_telemetry','Batch cần 1–100 số đo.')
            cutoff=now();seen_ids=set();seen_times=set();items=[];created=0
            for v in raw:
                if not isinstance(v,dict) or set(v)!={'client_sample_id','observed_at','air_temperature_c','relative_humidity_pct','leaf_wet','reported_quality','reference'}:
                    raise FarmError('invalid_telemetry','Số đo thiếu/thừa trường.')
                key=identifier(v['client_sample_id']);t=instant(v['observed_at']);ts=t.isoformat()
                if t>cutoff:raise FarmError('future_reading','Không nhận số đo tương lai.')
                within_season(t,season)
                if key in seen_ids or ts in seen_times:raise FarmError('duplicate_sample','Trùng UUID hoặc thời điểm trong batch.',409)
                seen_ids.add(key);seen_times.add(ts)
                for k,lo,hi in [('air_temperature_c',-50,60),('relative_humidity_pct',0,100)]:
                    value=v[k]
                    if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi):
                        raise FarmError('invalid_telemetry','Giá trị ngoài giới hạn kỹ thuật hoặc sai kiểu.')
                if v['leaf_wet'] is not None and type(v['leaf_wet']) is not bool:raise FarmError('invalid_telemetry','leaf_wet cần boolean hoặc null.')
                if v['reported_quality'] not in ['unknown','nominal','suspect']:raise FarmError('invalid_telemetry','Cờ chất lượng không hợp lệ.')
                p={k:v[k] for k in ['air_temperature_c','relative_humidity_pct','leaf_wet','reported_quality']};p['reference']=text(v['reference'],500)
                missing=[k for k in ['air_temperature_c','relative_humidity_pct','leaf_wet'] if p[k] is None]
                qc=dict(version=QC_VERSION,missing_fields=missing,reported_suspect=p['reported_quality']=='suspect',
                    status='incomplete' if missing else 'suspect' if p['reported_quality']=='suspect' else 'within_technical_bounds',
                    calibration_verified=False,hourly_eligible=False)
                existing=db.execute('SELECT * FROM samples WHERE id=?',(key,)).fetchone()
                if existing:
                    if existing['user_id']!=g.user['id'] or existing['stream_id']!=str(id) or existing['observed_at']!=ts or existing['payload_sha256']!=digest(p):
                        raise FarmError('sample_conflict','UUID số đo đã có nội dung khác.',409)
                else:
                    if db.execute('SELECT 1 FROM samples WHERE stream_id=? AND observed_at=?',(str(id),ts)).fetchone():raise FarmError('sample_conflict','Đã có số đo ở thời điểm này; không ghi đè.',409)
                    db.execute('INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?)',(key,g.user['id'],str(id),ts,json.dumps(p,ensure_ascii=False,allow_nan=False),digest(p),json.dumps(qc),cutoff.isoformat(),g.request_id));created+=1
                    existing=db.execute('SELECT * FROM samples WHERE id=?',(key,)).fetchone()
                items.append(sample_item(db.execute('SELECT * FROM raw_records WHERE id=?',(key,)).fetchone(),metadata))
            return jsonify(success=True,items=items,created=created,replayed=len(items)-created),201 if created else 200

    @bp.route('/environment-samples/<uuid:id>/exclusion',methods=['GET','POST'])
    @require_auth
    def exclusion(id):
        data=body({'reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            sample=db.execute('SELECT * FROM samples WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
            if sample is None:raise FarmError('resource_not_found','Không tìm thấy số đo.',404)
            parent,_=stream(db,core,sample['stream_id'])
            old=db.execute('SELECT * FROM exclusions WHERE sample_id=?',(str(id),)).fetchone()
            if data is None:return jsonify(success=True,item=None if old is None else {k:old[k] for k in ['sample_id','reason','recorded_at','request_id']})
            controlled_write(json.loads(parent['metadata_json']))
            reason=text(data['reason'],500)
            if old:
                if old['reason']!=reason:raise FarmError('exclusion_conflict','Số đo đã bị loại với lý do khác.',409)
                return jsonify(success=True,item={k:old[k] for k in ['sample_id','reason','recorded_at','request_id']})
            at=now().isoformat();db.execute('INSERT INTO exclusions VALUES (?,?,?,?,?)',(str(id),g.user['id'],reason,at,g.request_id))
            return jsonify(success=True,item=dict(sample_id=str(id),reason=reason,recorded_at=at,request_id=g.request_id)),201
    app.register_blueprint(bp)
