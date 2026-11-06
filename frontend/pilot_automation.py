"""Opt-in local mock-rule worker, scoped by authenticated owner job consent.

No YOLO, tokens, external scheduler, network inference or rule threshold changes.
"""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from flask import Blueprint,current_app,g,jsonify,request
from pilot_journal import journal_db
from pilot_store import validate_storage,StoreLease
from pilot_episodes import attach_assessment


def now():return datetime.now(timezone.utc)


def initialize(path):
    existed=path.exists()
    with journal_db(path) as db:
        if existed:
            try:kind=db.execute('SELECT kind FROM automation_meta').fetchone()[0]
            except (sqlite3.Error,TypeError) as exc:raise ValueError('Unknown automation DB; refusing to modify it') from exc
            if kind!='aegis-local-mock-automation-v1':raise ValueError('Unknown automation schema')
            return
        db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE automation_meta(kind TEXT NOT NULL)');db.execute("INSERT INTO automation_meta VALUES ('aegis-local-mock-automation-v1')")
        db.execute('''CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,device_id TEXT NOT NULL,
            name TEXT NOT NULL,profile_json TEXT NOT NULL,profile_sha256 TEXT NOT NULL,enabled INTEGER NOT NULL,
            version INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(device_id,profile_sha256))''')
        db.execute('''CREATE TABLE controls(id TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id),version INTEGER NOT NULL,
            command_sha256 TEXT NOT NULL,command_json TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL,UNIQUE(job_id,version))''')
        db.execute('''CREATE TABLE runs(id TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id),user_id TEXT NOT NULL,
            window_end TEXT NOT NULL,profile_sha256 TEXT NOT NULL,status TEXT NOT NULL,attempt_count INTEGER NOT NULL,
            started_at TEXT NOT NULL,finished_at TEXT,result_json TEXT,error_code TEXT,created_at TEXT NOT NULL,
            UNIQUE(job_id,window_end,profile_sha256))''')
        db.execute('''CREATE TABLE attempts(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),number INTEGER NOT NULL,
            trigger TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,error_code TEXT,
            request_id TEXT NOT NULL,job_version INTEGER NOT NULL,UNIQUE(run_id,number))''')
        db.execute('''CREATE TABLE input_changes(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),
            input_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(run_id,input_sha256))''')
        db.execute('CREATE INDEX idx_automation_owner ON jobs(user_id,season_id,created_at,id)')
        db.execute('CREATE INDEX idx_runs_owner ON runs(user_id,job_id,created_at,id)')


class Busy(RuntimeError):pass


class Runner:
    def __init__(self,app,storage,enabled=False,poll_seconds=30):
        if type(poll_seconds) is not int or not 5<=poll_seconds<=3600:raise ValueError('Poll seconds must be 5–3600')
        self.app=app;self.storage=validate_storage(storage);self.path=self.storage/'automation.sqlite3'
        initialize(self.path);self.enabled=bool(enabled);self.poll_seconds=poll_seconds;self.stop_event=threading.Event();self.thread=None;self.last_poll_at=None;self.last_error_code=None
        self.checkpoint=lambda stage:None  # Fault injection only in tests.

    def start(self):
        if not self.enabled or self.thread and self.thread.is_alive():return
        self.stop_event.clear();self.thread=threading.Thread(target=self.loop,name='aegis-mock-rule-worker',daemon=True);self.thread.start()

    def stop(self,timeout=20):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout)
        return not self.thread or not self.thread.is_alive()

    def loop(self):
        while not self.stop_event.is_set():
            try:self.tick()
            except Busy:pass
            except Exception:
                self.last_error_code='worker_poll_failed'
                self.app.logger.error('Mock automation poll failed; details withheld')
            self.stop_event.wait(self.poll_seconds)

    def status(self):return dict(enabled=self.enabled,poll_seconds=self.poll_seconds,worker_running=bool(self.thread and self.thread.is_alive()),last_poll_at=self.last_poll_at,last_error_code=self.last_error_code,source='mock',field_validated=False)

    def tick(self,job_id=None,owner=None,trigger='scheduled',request_id=None):
        if not self.enabled:raise ValueError('automation_disabled')
        try:lease=StoreLease(self.storage,'.automation.lock');lease.__enter__()
        except RuntimeError as exc:raise Busy('Another local worker is running') from exc
        try:
            at=now();self.last_poll_at=at.isoformat()
            from pilot_assessment_versions import recover
            recover(self.storage/'followup.sqlite3',at)
            with journal_db(self.path) as db:
                # Holding the OS execution lock proves earlier running attempts have no live executor.
                db.execute("UPDATE runs SET status='interrupted',finished_at=?,error_code='executor_interrupted' WHERE status='running'",(at.isoformat(),))
                db.execute("UPDATE attempts SET status='interrupted',finished_at=?,error_code='executor_interrupted' WHERE status='running'",(at.isoformat(),))
                if job_id:
                    jobs=db.execute('SELECT * FROM jobs WHERE id=? AND user_id=?',(job_id,owner)).fetchall()
                    if not jobs:raise ValueError('job_not_found')
                else:jobs=db.execute('SELECT * FROM jobs WHERE enabled=1 ORDER BY created_at,id').fetchall()
            results=[]
            for job in jobs:
                if self.stop_event.is_set() and trigger=='scheduled':break
                results.append(self.run(job['id'],at,trigger,request_id or str(uuid.uuid4())))
            return results
        finally:lease.__exit__(None,None,None)

    def inspect(self,job,at):
        from app.storage import connect
        from app.blast_conditions import PROFILE,digest
        end=at.replace(minute=0,second=0,microsecond=0);start=end-timedelta(hours=24)
        if digest(PROFILE)!=job['profile_sha256']:return None,'profile_changed',None
        with connect(self.app.config) as core:
            core.execute('BEGIN')
            device=core.execute('SELECT * FROM farm_devices WHERE id=? AND user_id=? AND season_id=?',(job['device_id'],job['user_id'],job['season_id'])).fetchone()
            season=core.execute('SELECT * FROM farm_seasons WHERE id=? AND user_id=?',(job['season_id'],job['user_id'])).fetchone()
            if device is None or season is None or device['source']!='mock':return None,'scope_unavailable',None
            local=(end-timedelta(microseconds=1)).astimezone(timezone(timedelta(hours=7))).date().isoformat()
            if local<season['start_date'] or season['end_date'] and local>season['end_date']:return None,'outside_season',None
            profile=core.execute('SELECT profile_json FROM farm_cultivation_revisions WHERE season_id=? AND user_id=? ORDER BY revision DESC LIMIT 1',(job['season_id'],job['user_id'])).fetchone()
            if profile and json.loads(profile[0])['season_status'] in ['planned','completed','archived']:return None,'season_not_active',None
            rows=core.execute('SELECT * FROM farm_telemetry WHERE device_id=? AND user_id=? AND start_at>=? AND start_at<? AND created_at<=? ORDER BY start_at',(job['device_id'],job['user_id'],start.isoformat(),end.isoformat(),at.isoformat())).fetchall()
            latest=core.execute('SELECT MAX(start_at) FROM farm_telemetry WHERE device_id=? AND user_id=? AND start_at<? AND created_at<=?',(job['device_id'],job['user_id'],end.isoformat(),at.isoformat())).fetchone()[0]
        records=[dict(start_at=r['start_at'],air_temperature_c=r['air_temperature_c'],relative_humidity_pct=r['relative_humidity_pct'],leaf_wet=bool(r['leaf_wet'])) for r in rows]
        payload=dict(source='mock',as_of=end.isoformat(),records=records)
        freshness='missing' if latest is None else 'stale' if datetime.fromisoformat(latest)+timedelta(hours=1)<end else 'window_end_bucket_present'
        return payload,None,dict(status=freshness,latest_bucket_start=latest,received_window_buckets=len(rows),expected_window_buckets=24)

    def assess(self,job,payload,at,request_id):
        from app.storage import connect
        from app.blast_conditions import PROFILE,digest,evaluate
        from app.cultivation import latest_profile,assessment_context
        with connect(self.app.config) as core:
            core.execute('BEGIN IMMEDIATE')
            old=core.execute('SELECT snapshot_json FROM farm_assessments WHERE device_id=? AND profile_sha256=? AND window_end=?',(job['device_id'],job['profile_sha256'],payload['as_of'])).fetchone()
            if old:return json.loads(old[0]),False
            season=core.execute('SELECT * FROM farm_seasons WHERE id=? AND user_id=?',(job['season_id'],job['user_id'])).fetchone()
            output=evaluate(payload);end=datetime.fromisoformat(payload['as_of']);recorded=now()
            a=dict(id=str(uuid.uuid4()),user_id=job['user_id'],plot_id=season['plot_id'],season_id=job['season_id'],device_id=job['device_id'],created_at=recorded.isoformat(),request_id=request_id,mode='current_mock',valid_until=(end+timedelta(hours=1)).isoformat(),profile=dict(PROFILE),input=payload,result=output)
            a['cultivation_context']=assessment_context(latest_profile(core,job['season_id'],job['user_id']),end,recorded)
            core.execute('INSERT INTO farm_assessments VALUES (?,?,?,?,?,?,?,?)',(a['id'],job['user_id'],job['device_id'],job['profile_sha256'],payload['as_of'],output['status'],json.dumps(a,ensure_ascii=False,allow_nan=False),recorded.isoformat()))
            return a,True

    def run(self,job_id,at,trigger,request_id):
        from app.blast_conditions import digest
        end=at.replace(minute=0,second=0,microsecond=0).isoformat()
        with journal_db(self.path) as db:
            db.execute('BEGIN IMMEDIATE');job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not job['enabled']:return dict(job_id=job_id,status='disabled',replayed=False)
            old=db.execute('SELECT * FROM runs WHERE job_id=? AND window_end=? AND profile_sha256=?',(job_id,end,job['profile_sha256'])).fetchone()
        payload=skip=freshness=None;inspection_error=None
        try:payload,skip,freshness=self.inspect(job,at)
        except Exception as exc:inspection_error=exc
        if old and old['status'] in ['succeeded','skipped'] and not inspection_error and (old['status']=='succeeded' or skip==json.loads(old['result_json']).get('skip_reason')):
            result=json.loads(old['result_json'])
            changed=bool(payload and result.get('snapshot_input_sha256') and digest(payload)!=result['snapshot_input_sha256'])
            if changed:
                with journal_db(self.path) as db:db.execute('INSERT OR IGNORE INTO input_changes VALUES (?,?,?,?)',(str(uuid.uuid4()),old['id'],digest(payload),at.isoformat()))
            current_version=None
            if payload is not None and skip is None and result.get('assessment_id'):
                try:current_version=self.supplement(result['assessment_id'],payload,request_id,job_id,old['id']);self.last_error_code=None
                except Exception as exc:
                    self.last_error_code='assessment_version_failed';self.app.logger.error('Assessment supplement failed; exception_type=%s',type(exc).__name__)
                    return dict(job_id=job_id,run_id=old['id'],status='failed',error_code='assessment_version_failed',replayed=True)
            return dict(result,run_id=old['id'],replayed=True,input_changed_after_snapshot=changed,current_input_freshness=freshness,current_scope_issue=skip,current_assessment=current_version)
        with journal_db(self.path) as db:
            db.execute('BEGIN IMMEDIATE');run_id=old['id'] if old else str(uuid.uuid4());number=old['attempt_count']+1 if old else 1
            if old:db.execute("UPDATE runs SET status='running',attempt_count=?,started_at=?,finished_at=NULL,error_code=NULL WHERE id=?",(number,at.isoformat(),run_id))
            else:db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,job_id,job['user_id'],end,job['profile_sha256'],'running',number,at.isoformat(),None,None,None,at.isoformat()))
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),run_id,number,trigger,'running',at.isoformat(),None,None,request_id,job['version']))
        try:
            if inspection_error:raise inspection_error
            if skip:result=dict(job_id=job_id,status='skipped',skip_reason=skip,assessment_id=None,followup_id=None,window_end=end,source='mock')
            else:
                a,created=self.assess(job,payload,at,request_id);self.checkpoint('after_assessment')
                with journal_db(self.storage/'followup.sqlite3') as db:
                    db.execute('BEGIN IMMEDIATE')
                    case,case_created,episode_ids=attach_assessment(db,job['user_id'],a,'Tự động theo cấu hình mock đã được chủ mùa vụ bật',request_id,max(now(),datetime.fromisoformat(a['created_at'])),dict(job_id=job_id,run_id=run_id))
                    followup_id=case['id'] if case else None
                self.checkpoint('after_followup')
                current_version=self.supplement(a['id'],payload,request_id,job_id,run_id)
                result=dict(job_id=job_id,status='succeeded',assessment_id=a['id'],assessment_created=created,assessment_status=a['result']['status'],followup_id=followup_id,followup_created=case_created,episode_ids=episode_ids,window_end=end,source='mock',freshness=freshness,snapshot_input_sha256=digest(a['input']),observed_input_sha256=digest(payload),input_changed_after_snapshot=digest(payload)!=digest(a['input']),field_validated=False,current_assessment=current_version)
            self.checkpoint('before_audit_commit')
            with journal_db(self.path) as db:
                db.execute("UPDATE runs SET status=?,finished_at=?,result_json=?,error_code=NULL WHERE id=?",(result['status'],now().isoformat(),json.dumps(result,ensure_ascii=False,allow_nan=False),run_id))
                db.execute('UPDATE attempts SET status=?,finished_at=? WHERE run_id=? AND number=?',(result['status'],now().isoformat(),run_id,number))
            self.last_error_code=None;return dict(result,run_id=run_id,replayed=False)
        except Exception as exc:
            with journal_db(self.path) as db:
                db.execute("UPDATE runs SET status='failed',finished_at=?,error_code='automation_step_failed' WHERE id=?",(now().isoformat(),run_id))
                db.execute("UPDATE attempts SET status='failed',finished_at=?,error_code='automation_step_failed' WHERE run_id=? AND number=?",(now().isoformat(),run_id,number))
            self.last_error_code='automation_step_failed';self.app.logger.error('Mock automation step failed; exception_type=%s',type(exc).__name__)
            return dict(job_id=job_id,run_id=run_id,status='failed',error_code='automation_step_failed',replayed=False)


    def supplement(self,base_id,payload,request_id,job_id,run_id):
        from app.storage import connect
        from pilot_assessment_versions import ensure_version
        with connect(self.app.config) as core:
            row=core.execute('SELECT snapshot_json FROM farm_assessments WHERE id=?',(base_id,)).fetchone()
            base=json.loads(row[0])
        return ensure_version(self.storage/'followup.sqlite3',base,payload,request_id,dict(job_id=job_id,run_id=run_id),self.checkpoint)


def enable_automation(app,storage,enabled=False,poll_seconds=30):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Wrong isolated store')
    runner=Runner(app,storage,enabled,poll_seconds);app.extensions['mock_automation']=runner
    from app.auth import require_auth
    from app.storage import connect
    from app.blast_conditions import PROFILE,digest
    from app.farm import body,owned,paginate,text,private,FarmError,LimitResponse,limit_response
    bp=Blueprint('pilot_automation',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def identifier(v):
        try:return str(uuid.UUID(v))
        except (ValueError,TypeError,AttributeError):raise FarmError('invalid_automation','Cần UUID hợp lệ.')

    def job_item(r):return dict(id=r['id'],season_id=r['season_id'],device_id=r['device_id'],name=r['name'],enabled=bool(r['enabled']),version=r['version'],created_at=r['created_at'],profile=json.loads(r['profile_json']),profile_sha256=r['profile_sha256'],profile_matches_runtime=r['profile_sha256']==digest(PROFILE),source='mock')

    def job(db,core,id):
        r=db.execute('SELECT * FROM jobs WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
        if r is None:raise FarmError('resource_not_found','Không tìm thấy job.',404)
        owned(core,'seasons',r['season_id']);return r

    @bp.get('/automation/status')
    @require_auth
    def status():return jsonify(success=True,automation=runner.status())

    @bp.route('/devices/<uuid:id>/automation-jobs',methods=['GET','POST'])
    @require_auth
    def jobs(id):
        data=body({'client_job_id','name','enabled','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(runner.path) as db:
            device=owned(core,'devices',id);owned(core,'seasons',device['season_id']);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'jobs','device_id=? AND user_id=?',(str(id),g.user['id']),job_item)
            key=identifier(data['client_job_id']);name=text(data['name']);text(data['reason'],500)
            if type(data['enabled']) is not bool:raise FarmError('invalid_automation','enabled cần boolean.')
            old=db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if old:
                first=db.execute('SELECT command_sha256 FROM controls WHERE job_id=? AND version=1',(key,)).fetchone()
                if old['user_id']!=g.user['id'] or old['device_id']!=str(id) or first[0]!=digest(data):raise FarmError('automation_conflict','UUID job đã có nội dung khác.',409)
                return jsonify(success=True,item=job_item(old)),200
            if db.execute('SELECT 1 FROM jobs WHERE device_id=? AND profile_sha256=?',(str(id),digest(PROFILE))).fetchone():raise FarmError('automation_job_exists','Thiết bị đã có job cho cấu hình này.',409)
            if device['source']!='mock':raise FarmError('mock_only','Automation chỉ nhận thiết bị mock.')
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',(key,g.user['id'],device['season_id'],str(id),name,json.dumps(PROFILE),digest(PROFILE),int(data['enabled']),1,now().isoformat()))
            db.execute('INSERT INTO controls VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),key,1,digest(data),json.dumps(data,ensure_ascii=False),now().isoformat(),g.request_id))
            return jsonify(success=True,item=job_item(job(db,core,key))),201

    @bp.get('/seasons/<uuid:id>/automation-jobs')
    @require_auth
    def season_jobs(id):
        with connect(current_app.config) as core,journal_db(runner.path) as db:
            owned(core,'seasons',id);return paginate(db,'jobs','season_id=? AND user_id=?',(str(id),g.user['id']),job_item)

    @bp.route('/automation-jobs/<uuid:id>',methods=['GET','PUT'])
    @require_auth
    def detail(id):
        data=body({'client_event_id','base_version','enabled','reason'}) if request.method=='PUT' else None
        with connect(current_app.config) as core,journal_db(runner.path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');r=job(db,core,id)
            if data is None:return jsonify(success=True,item=job_item(r))
            key=identifier(data['client_event_id']);text(data['reason'],500)
            if type(data['base_version']) is not int or data['base_version']<1 or type(data['enabled']) is not bool:raise FarmError('invalid_automation','Phiên bản hoặc enabled không hợp lệ.')
            old=db.execute('SELECT * FROM controls WHERE id=?',(key,)).fetchone()
            if old:
                if old['job_id']!=str(id) or old['command_sha256']!=digest(data):raise FarmError('automation_event_conflict','UUID sự kiện khác nội dung.',409)
                return jsonify(success=True,item=job_item(r)),200
            if data['base_version']!=r['version']:raise FarmError('automation_version_conflict','Job đã đổi; tải lại.',409)
            db.execute('UPDATE jobs SET enabled=?,version=version+1 WHERE id=?',(int(data['enabled']),str(id)))
            db.execute('INSERT INTO controls VALUES (?,?,?,?,?,?,?)',(key,str(id),r['version']+1,digest(data),json.dumps(data,ensure_ascii=False),now().isoformat(),g.request_id))
            return jsonify(success=True,item=job_item(job(db,core,id))),201

    @bp.post('/automation-jobs/<uuid:id>/run')
    @require_auth
    def manual_run(id):
        body(set())
        with connect(current_app.config) as core,journal_db(runner.path) as db:r=job(db,core,id)
        if not runner.enabled:raise FarmError('automation_disabled','Launcher chưa bật mock automation.',409)
        if not r['enabled']:raise FarmError('automation_job_disabled','Job đang tắt.',409)
        try:result=runner.tick(str(id),g.user['id'],'manual',g.request_id)[0]
        except Busy:raise FarmError('automation_busy','Một lượt chạy khác đang xử lý; xem lịch sử trước khi thử lại.',409)
        if result['status']=='failed':return jsonify(success=False,error=dict(code=result['error_code'],message='Lượt chạy lỗi; có thể đã ghi một phần. Xem lịch sử rồi chạy lại cùng cửa sổ.'),item=result),503
        return jsonify(success=True,item=result)

    @bp.get('/automation-jobs/<uuid:id>/runs')
    @require_auth
    def runs(id):
        with connect(current_app.config) as core,journal_db(runner.path) as db:
            job(db,core,id)
            def serialize(r):
                d=dict(r);d.pop('user_id');raw=d.pop('result_json');d['result']=json.loads(raw) if raw else None
                if d['result'] and d['result'].get('assessment_id'):
                    from pilot_assessment_versions import current
                    with journal_db(storage/'followup.sqlite3') as workflow:
                        a=core.execute('SELECT snapshot_json FROM farm_assessments WHERE id=? AND user_id=?',(d['result']['assessment_id'],g.user['id'])).fetchone()
                        d['current_assessment']=current(workflow,json.loads(a[0])) if a else None
                d['input_changes']=[dict(x) for x in db.execute('SELECT input_sha256,created_at FROM input_changes WHERE run_id=? ORDER BY created_at',(r['id'],))]
                d['attempts']=[dict(x) for x in db.execute('SELECT number,trigger,status,started_at,finished_at,error_code,request_id,job_version FROM attempts WHERE run_id=? ORDER BY number',(r['id'],))]
                return d
            return paginate(db,'runs','job_id=? AND user_id=?',(str(id),g.user['id']),serialize)

    @bp.get('/automation-jobs/<uuid:id>/controls')
    @require_auth
    def controls(id):
        with connect(current_app.config) as core,journal_db(runner.path) as db:
            job(db,core,id)
            def serialize(r):
                result=dict(r);result['command']=json.loads(result.pop('command_json'));return result
            return paginate(db,'controls','job_id=?',(str(id),),serialize,order='version DESC')
    app.register_blueprint(bp);return runner
