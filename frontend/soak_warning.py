"""Disposable synthetic operational checks. No real AI, field data or training.

replay: simulated seven-day clock; live: bounded real HTTP/timer + child crash.
Output directory must be new. Never uses a user's existing pilot database.
"""
import argparse
from collections import Counter,defaultdict
from contextlib import ExitStack,closing
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,logging,math,queue,sqlite3,statistics,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
from unittest.mock import patch
from server import build_app
from pilot_mysql_tools import open_readonly,initialized
from pilot_store import StoreLease

KINDS=['continuous','dry','intermittent','outage','late','paused']
PYTHON=Path(__file__).resolve().parent.parent/'backend/.venv/Scripts/python.exe'
DBS=['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3','research.sqlite3','automation.sqlite3']


def utc():return datetime.now(timezone.utc)


def distribution(values):
    ordered=sorted(values);n=len(ordered)
    return dict(n=n,median_ms=round(statistics.median(ordered),3),p95_ms=round(ordered[math.ceil(.95*n)-1],3),max_ms=round(ordered[-1],3),p95_method='nearest_rank') if n else dict(n=0)


class Evidence:
    def __init__(self,out):self.out=out;self.checks=Counter();self.timings=defaultdict(list);self.samples=[];self.lock=threading.Lock()
    def check(self,name,value):
        if not value:raise AssertionError(name)
        with self.lock:self.checks[name]+=1
    def timed(self,kind,fn):
        started=time.perf_counter();result=fn();self.timings[kind].append((time.perf_counter()-started)*1000);return result
    def write(self,name,value):
        (self.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def setup(store,ev):
    app=build_app(store,'http://127.0.0.1:9',{'kind':'synthetic_soak'},automation_enabled=True)
    # Fixture/replay only. Actual live backend below keeps its default 60 writes/min.
    app.config['FARM_WRITE_LIMIT']=100000
    app.logger.setLevel(logging.ERROR);client=app.test_client();owners=[];jobs=[]
    for i in range(2):
        creds=dict(email=f'soak-{i}@example.test',password='soak-synthetic-password-123')
        ev.check('fixture_register201',client.post('/api/auth/register',json=creds).status_code==201)
        response=client.post('/api/auth/login',json=creds);ev.check('fixture_login200',response.status_code==200)
        headers={'Authorization':'Bearer '+response.json['access_token']};owner=client.get('/api/auth/me',headers=headers).json['user']['id']
        plot=client.post('/api/farm/plots',headers=headers,json=dict(name=f'Synthetic soak {i}')).json['item']
        season=client.post('/api/farm/plots/'+plot['id']+'/seasons',headers=headers,json=dict(name='Synthetic operational season',start_date='2026-10-01',end_date='2026-12-31')).json['item']
        owners.append(dict(id=owner,headers=headers,season=season['id']))
        for kind in KINDS:
            d=client.post('/api/farm/seasons/'+season['id']+'/devices',headers=headers,json=dict(name=kind,device_code=f'SOAK-{i}-{kind}',source='mock')).json['item']
            body=dict(client_job_id=str(uuid.uuid4()),name=kind,enabled=True,reason='Synthetic operational rehearsal')
            r=client.post('/api/farm/devices/'+d['id']+'/automation-jobs',headers=headers,json=body);ev.check('fixture_job201',r.status_code==201)
            jobs.append(dict(id=r.json['item']['id'],device=d['id'],kind=kind,owner=i))
    return app,client,owners,jobs


def seed(client,owners,job,starts,ev):
    if not starts:return
    dry=job['kind']=='dry'
    rows=[dict(start_at=t.isoformat(),air_temperature_c=10 if dry else 26,relative_humidity_pct=30 if dry else 95,leaf_wet=not dry) for t in starts]
    def send():return client.post('/api/farm/devices/'+job['device']+'/telemetry',headers=owners[job['owner']]['headers'],json=dict(source='mock',records=rows))
    r=ev.timed('fixture_ingest_test_client',send);ev.check('fixture_ingest201',r.status_code==201)


def inspect_store(store,ev):
    hybrid=initialized(store/'journal.sqlite3')
    if hybrid:
        from app.hybrid_backup import audit
        report=audit(store);ev.check('mysql_hybrid_schema_complete',report['kind']=='aegis-hybrid-audit-v1')
    result=dict(backend='mysql') if hybrid else {}
    for name in ([] if hybrid else DBS):
        with closing(open_readonly(store/name)) as db:
            ev.check('sqlite_integrity_ok',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
            ev.check('sqlite_no_foreign_key_violation',not db.execute('PRAGMA foreign_key_check').fetchall())
        result[name]=dict(bytes=(store/name).stat().st_size)
    with closing(open_readonly(store/'automation.sqlite3')) as db:
        result['run_states']=dict(db.execute('SELECT status,COUNT(*) FROM runs GROUP BY status'))
        result['attempt_states']=dict(db.execute('SELECT status,COUNT(*) FROM attempts GROUP BY status'))
        result['input_change_rows']=db.execute('SELECT COUNT(*) FROM input_changes').fetchone()[0]
        ev.check('no_failed_or_running_final_runs',db.execute("SELECT COUNT(*) FROM runs WHERE status IN ('failed','running','interrupted')").fetchone()[0]==0)
        ev.check('no_duplicate_run_keys',not db.execute('SELECT 1 FROM runs GROUP BY job_id,window_end,profile_sha256 HAVING COUNT(*)>1').fetchall())
    with closing(open_readonly(store/'followup.sqlite3')) as db:
        result['cases']=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0];result['episodes']=db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
        result['members']=db.execute('SELECT COUNT(*) FROM episode_members').fetchone()[0]
        ev.check('no_duplicate_members',not db.execute('SELECT 1 FROM episode_members GROUP BY episode_id,assessment_id HAVING COUNT(*)>1').fetchall())
        ev.check('at_most_one_open_group_per_scope',not db.execute("SELECT 1 FROM episode_heads WHERE state!='closed' GROUP BY user_id,season_id,device_id,profile_sha256,task_kind HAVING COUNT(*)>1").fetchall())
    with closing(open_readonly(store/'demo.db')) as db:
        result['assessments']=db.execute('SELECT COUNT(*) FROM farm_assessments').fetchone()[0]
        ev.check('no_duplicate_assessments',not db.execute('SELECT 1 FROM farm_assessments GROUP BY device_id,profile_sha256,window_end HAVING COUNT(*)>1').fetchall())
        if not hybrid:ev.check('core_migrations_unchanged',set(r[0] for r in db.execute('SELECT version FROM schema_migrations'))=={1,2,3,4,5})
    return result


def replay(store,ev):
    app,client,owners,jobs=setup(store,ev);clock=[datetime(2026,10,10,0,10,tzinfo=timezone.utc)];start=clock[0].replace(minute=0);snapshots={};trace=[];restarts=0
    from app.blast_conditions import digest
    with ExitStack() as stack:
        for target in ['pilot_automation.now','app.farm.now','pilot_episodes.now','pilot_followup.now','pilot_journal.now']:
            stack.enter_context(patch(target,side_effect=lambda:clock[0]))
        for job in jobs:
            starts=[start-timedelta(hours=24-i) for i in range(24)]
            seed(client,owners,job,starts[:-1] if job['kind']=='late' else starts,ev)
        for h in range(168):
            clock[0]=start+timedelta(hours=h,minutes=10);end=clock[0].replace(minute=0)
            for job in jobs:
                if h and not (job['kind']=='late' or job['kind']=='intermittent' and h%6 in [1,2] or job['kind']=='outage' and 24<=h<48):seed(client,owners,job,[end-timedelta(hours=1)],ev)
                if job['kind']=='paused' and h in [36,60]:
                    url='/api/farm/automation-jobs/'+job['id'];headers=owners[job['owner']]['headers'];current=client.get(url,headers=headers).json['item']
                    r=client.put(url,headers=headers,json=dict(client_event_id=str(uuid.uuid4()),base_version=current['version'],enabled=h==60,reason='Synthetic pause/resume'))
                    ev.check('pause_resume201',r.status_code==201)
            runner=app.extensions['mock_automation']
            if h in [96,97]:
                fired=[False];stage='after_assessment' if h==96 else 'after_followup'
                def fail(s):
                    if s==stage and not fired[0]:fired[0]=True;raise RuntimeError('SOAK_SECRET_MARKER')
                runner.checkpoint=fail
            if h==120:
                class Interrupted(BaseException):pass
                runner.checkpoint=lambda s:(_ for _ in ()).throw(Interrupted()) if s=='after_followup' else None
            try:results=ev.timed('replay_worker_tick',runner.tick)
            except BaseException as exc:
                if h!=120 or not isinstance(exc,Interrupted):raise
                ev.check('simulated_interrupt_observed',True)
                app=build_app(store,'http://127.0.0.1:9',{'kind':'replay_restart'},automation_enabled=True);app.logger.setLevel(logging.ERROR);app.config['FARM_WRITE_LIMIT']=100000;client=app.test_client();runner=app.extensions['mock_automation'];restarts+=1
                results=ev.timed('replay_recovery_tick',runner.tick)
            if h in [96,97]:
                ev.check('planned_failed_step_observed',sum(r['status']=='failed' for r in results)==1);runner.checkpoint=lambda s:None;results=ev.timed('replay_recovery_tick',runner.tick)
            ev.check('expected_active_job_count',len(results)==(10 if 36<=h<60 else 12))
            ev.check('all_current_runs_succeeded',all(r['status']=='succeeded' for r in results))
            for r in results:
                a=client.get('/api/farm/assessments/'+r['assessment_id'],headers=owners[next(j['owner'] for j in jobs if j['id']==r['job_id'])]['headers']).json['item']
                snapshots.setdefault(a['id'],digest(a))
                trace.append(dict(hour=h,job_id=r['job_id'],assessment_id=a['id'],status=r['assessment_status'],case_id=r['followup_id'],replayed=r['replayed']))
            clock[0]=end+timedelta(minutes=20)
            for job in jobs:
                if job['kind']=='late':seed(client,owners,job,[end-timedelta(hours=1)],ev)
            replayed=ev.timed('replay_same_window_tick',runner.tick);ev.check('all_same_window_replayed',all(r['replayed'] for r in replayed))
            ev.check('late_input_detected',all(r.get('input_changed_after_snapshot') for r in replayed if next(j['kind'] for j in jobs if j['id']==r['job_id'])=='late'))
            if h==72:
                for job in jobs:
                    if job['kind']!='continuous':continue
                    headers=owners[job['owner']]['headers'];r=next(r for r in results if r['job_id']==job['id']);cid=r['followup_id']
                    p=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=clock[0].isoformat(),scheduled=True,finding='uncertain',notes='Synthetic closing rehearsal',analysis_id=None,review=None,record_status='active',change_reason='Synthetic test')
                    obs=client.post('/api/farm/seasons/'+owners[job['owner']]['season']+'/observations',headers=headers,json=p);ev.check('synthetic_observation201',obs.status_code==201)
                    for version,action in [(1,'acknowledge'),(2,'check'),(3,'close')]:
                        p=dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,reason='Synthetic lifecycle',observation_id=obs.json['item']['id'] if action=='check' else None,resolution='followup_recorded' if action=='close' else None)
                        ev.check('lifecycle201',client.post('/api/farm/follow-ups/'+cid+'/events',headers=headers,json=p).status_code==201)
            if h%24==23:
                for owner in owners:
                    response=ev.timed('replay_dashboard_test_client',lambda:client.get('/api/farm/seasons/'+owner['season']+'/warning-dashboard',headers=owner['headers']))
                    ev.check('daily_dashboard200',response.status_code==200);ev.check('daily_own_six_devices',response.json['pagination']['total']==6)
                print(json.dumps(dict(mode='replay',simulated_hours=h+1,assessments=len(snapshots))),flush=True)
        with closing(open_readonly(store/'demo.db')) as db:
            for id,snapshot in db.execute('SELECT id,snapshot_json FROM farm_assessments'):ev.check('snapshot_unchanged',digest(json.loads(snapshot))==snapshots[id])
        result=inspect_store(store,ev)
        ev.check('expected_assessment_count',result['assessments']==168*12-24*2)
        ev.check('expected_sixteen_cases_and_groups',result['cases']==16 and result['episodes']==16)
        ev.check('one_late_change_per_window',result['input_change_rows']==168*2)
        ev.check('two_injected_failures_audited',result['attempt_states'].get('failed')==2)
        ev.check('simulated_interrupt_audited',result['attempt_states'].get('interrupted')==1)
        ev.write('trace.json',trace)
        return dict(result,simulated_hours=168,owners=2,devices=12,clock_simulated=True,transport='Flask test client + direct worker; no HTTP network',fixture_farm_write_limit=100000,restarts=restarts)


def crash_probe(args):
    # Only this disposable worker process is intentionally terminated by parent.
    resolved=args.storage.resolve();temp_root=Path(tempfile.gettempdir()).resolve()
    if resolved.parent!=temp_root or not resolved.name.startswith('aegis_ui_soak_'):
        raise ValueError('Crash probe only accepts this harness disposable temporary stores')
    with StoreLease(args.storage):
        app=build_app(args.storage,'http://127.0.0.1:9',{'kind':'crash_probe'},automation_enabled=True)
        def hold(stage):
            if stage=='after_followup':
                args.barrier.write_text('after_followup; core and followup committed; audit still running',encoding='utf-8')
                threading.Event().wait(120)
        runner=app.extensions['mock_automation'];runner.checkpoint=hold;runner.tick()


def live(store,ev,duration):
    import requests
    app,client,owners,jobs=setup(store,ev);end=utc().replace(minute=0,second=0,microsecond=0)
    for job in jobs:
        starts=[end-timedelta(hours=24-i) for i in range(24)]
        if job['kind'] in ['intermittent','late']:starts=starts[:-1]
        if job['kind']=='outage':starts=[t-timedelta(hours=48) for t in starts]
        seed(client,owners,job,starts,ev)
        if job['kind']=='paused':
            url='/api/farm/automation-jobs/'+job['id'];headers=owners[job['owner']]['headers'];j=client.get(url,headers=headers).json['item']
            ev.check('fixture_pause201',client.put(url,headers=headers,json=dict(client_event_id=str(uuid.uuid4()),base_version=j['version'],enabled=False,reason='Synthetic initial pause')).status_code==201)
    barrier=ev.out/'CRASH_BARRIER';probe_log=(ev.out/'crash_probe.log').open('w',encoding='utf-8');probe=None;process=None;log=None;ports=[];http=[];stops=[]
    info=ev.out/'model_info.json';info.write_text(json.dumps(dict(kind='test_host',storage_mode='temporary',health=dict(model_version='TEST HOST — no AI loaded',device='none',model_sha256='none'))))
    stopfile=None;url=None
    def stop():
        nonlocal process,log
        if process:
            stopfile.touch();process.wait(timeout=30);ev.check('http_child_graceful_exit0',process.returncode==0);stops.append(dict(pid=process.pid,exit_code=process.returncode));process.stdout.close();process=None
        if log:log.close();log=None
    def launch(name):
        nonlocal process,log,stopfile,url
        stopfile=ev.out/('STOP_'+name);log=(ev.out/(name+'.log')).open('w',encoding='utf-8')
        command=[str(PYTHON),'-u',str(Path(__file__).with_name('server.py')),'--backend','--storage',str(store),'--ai-url','http://127.0.0.1:9','--info',str(info),'--shutdown-file',str(stopfile),'--enable-mock-automation','--automation-poll-seconds','5']
        process=subprocess.Popen(command,cwd=PYTHON.parent.parent.parent,stdout=subprocess.PIPE,stderr=log,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        q=queue.Queue();threading.Thread(target=lambda:q.put(process.stdout.readline()),daemon=True).start();port=int(q.get(timeout=20).strip());ports.append(port);url='http://127.0.0.1:'+str(port)
    def call(path,owner=0,method='GET',data=None,expected=(200,),phase='monitor'):
        started=time.perf_counter();r=requests.request(method,url+path,headers=owners[owner]['headers'],json=data,timeout=15);ms=(time.perf_counter()-started)*1000
        http.append(dict(phase=phase,method=method,path=path,status=r.status_code,elapsed_ms=ms,expected=list(expected)))
        ev.check('http_expected_status',r.status_code in expected)
        if r.status_code==409:ev.check('conflict_is_worker_busy',r.json()['error']['code']=='automation_busy')
        return r
    started=time.perf_counter();actual_start=utc().isoformat();late_changed=False;resumed=False;restarted=False;burst_done=False
    try:
        probe=subprocess.Popen([str(PYTHON),'-u',str(Path(__file__)),'--mode','crash-probe','--storage',str(store),'--barrier',str(barrier)],stdout=probe_log,stderr=probe_log,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+20
        while not barrier.exists() and time.monotonic()<deadline:
            if probe.poll() is not None:break
            time.sleep(.1)
        ev.check('crash_reached_committed_followup_barrier',barrier.exists())
        probe.terminate();probe.wait(timeout=15);ev.check('only_probe_terminated',probe.poll() is not None);probe=None;probe_log.close()
        launch('session1')
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            with closing(open_readonly(store/'automation.sqlite3')) as db:n=db.execute("SELECT COUNT(*) FROM runs WHERE status='succeeded'").fetchone()[0]
            if n==10:break
            time.sleep(.2)
        ev.check('timer_recovered_all_ten_initial_jobs',n==10)
        result=inspect_store(store,ev);ev.check('real_crash_interrupted_attempt',result['attempt_states'].get('interrupted')==1)
        initial_snapshots={}
        with closing(open_readonly(store/'demo.db')) as db:
            initial_snapshots={id:hashlib.sha256(snapshot.encode()).hexdigest() for id,snapshot in db.execute('SELECT id,snapshot_json FROM farm_assessments')}
        while time.perf_counter()-started<duration:
            elapsed=time.perf_counter()-started
            for owner in range(2):
                season=owners[owner]['season'];d=call('/api/farm/seasons/'+season+'/warning-dashboard',owner)
                ev.check('live_owner_six_devices',d.json()['pagination']['total']==6)
                ev.check('live_mock_scope',d.json()['source']=='mock' and d.json()['field_validated'] is False)
            if not late_changed:
                for job in jobs:
                    if job['kind']!='late':continue
                    body=dict(source='mock',records=[dict(start_at=(end-timedelta(hours=1)).isoformat(),air_temperature_c=26,relative_humidity_pct=95,leaf_wet=True)])
                    call('/api/farm/devices/'+job['device']+'/telemetry',job['owner'],'POST',body,(201,),phase='late_ingest')
                    call('/api/farm/devices/'+job['device']+'/telemetry',job['owner'],'POST',body,(200,),phase='ingest_replay')
                late_changed=True
            if elapsed>=duration/3 and not resumed:
                for job in jobs:
                    if job['kind']!='paused':continue
                    base='/api/farm/automation-jobs/'+job['id'];j=call(base,job['owner']).json()['item']
                    call(base,job['owner'],'PUT',dict(client_event_id=str(uuid.uuid4()),base_version=j['version'],enabled=True,reason='Synthetic resume'),(201,),phase='resume')
                resumed=True
            if elapsed>=duration/2 and not restarted:
                stop();launch('session2');restarted=True
            if int(elapsed)%30<2:
                paths=['/api/farm/seasons/'+owners[i%2]['season']+'/warning-dashboard' for i in range(6)]
                with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda p:call(p,0 if owners[0]['season'] in p else 1,phase='concurrent_reads'),paths))
                if not burst_done:call('/api/farm/automation-jobs/'+jobs[0]['id']+'/run',method='POST',data={},expected=(200,409),phase='manual_vs_timer')
            if elapsed>=duration*.75 and not burst_done:
                # Test admission policy, not auto-retry; each request is an explicit probe.
                for i in range(125):
                    r=call('/api/farm/automation-jobs/'+jobs[0]['id']+'/run',method='POST',data={},expected=(200,409,429),phase='quota_burst')
                    if r.status_code==429:ev.check('quota_retry_after_positive',int(r.headers['Retry-After'])>=1)
                burst_done=True
            ev.samples.append(dict(elapsed_seconds=round(time.perf_counter()-started,3),at_utc=utc().isoformat(),worker=call('/api/farm/automation/status').json()['automation']))
            threading.Event().wait(min(2,max(0,duration-(time.perf_counter()-started))))
        result=inspect_store(store,ev)
        ev.check('all_twelve_jobs_eventually_succeeded',result['run_states'].get('succeeded')==12)
        ev.check('expected_ten_case_groups',result['cases']==10 and result['episodes']==10)
        ev.check('two_late_input_changes',result['input_change_rows']==2)
        ev.check('quota429_observed',any(r['status']==429 for r in http))
        with closing(open_readonly(store/'demo.db')) as db:
            after=dict(db.execute('SELECT id,snapshot_json FROM farm_assessments'))
            ev.check('all_initial_snapshots_unchanged',all(hashlib.sha256(after[id].encode()).hexdigest()==sha for id,sha in initial_snapshots.items()))
        foreign=call('/api/farm/seasons/'+owners[1]['season']+'/warning-dashboard',0,expected=(404,),phase='ownership')
        ev.check('foreign_error_has_no_items','items' not in foreign.json())
        measured_duration=time.perf_counter()-started;stop()
        ev.write('http_samples.json',http);ev.write('worker_samples.json',ev.samples)
        by_phase={phase:dict(distribution([r['elapsed_ms'] for r in http if r['phase']==phase]),statuses=dict(Counter(str(r['status']) for r in http if r['phase']==phase))) for phase in sorted({r['phase'] for r in http})}
        return dict(result,requested_seconds=duration,actual_elapsed_seconds=round(measured_duration,3),started_at_utc=actual_start,ended_at_utc=utc().isoformat(),clock_simulated=False,owners=2,devices=12,ports=ports,services_stopped=True,graceful_stops=stops,forced_probe_termination=True,http_requests=len(http),http_by_phase=by_phase,actual_hour_windows_observed=sorted({r['worker']['last_poll_at'][:13] for r in ev.samples if r['worker']['last_poll_at']}),runtime_farm_write_limit=60,runtime_rate_window_seconds=60)
    finally:
        if probe and probe.poll() is None:probe.terminate();probe.wait(timeout=15)
        if not probe_log.closed:probe_log.close()
        if process:
            try:stop()
            except Exception:
                if process and process.poll() is None:process.terminate();process.wait(timeout=15)
                if log:log.close()
        ev.write('http_samples.json',http);ev.write('worker_samples.json',ev.samples)
        ev.write('process_cleanup.json',dict(probe_stopped=probe is None or probe.poll() is not None,backend_stopped=process is None or process.poll() is not None,graceful_stops=stops,ports=ports))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['replay','live','crash-probe'],required=True);p.add_argument('--out',type=Path);p.add_argument('--seconds',type=int,default=180);p.add_argument('--storage',type=Path);p.add_argument('--barrier',type=Path);args=p.parse_args()
    if args.mode=='crash-probe':crash_probe(args);return
    if args.out is None:p.error('--out required')
    if not 60<=args.seconds<=3600:p.error('--seconds must be 60–3600')
    # This live fixture is deliberately fixed to one hour. Multi-hour behavior
    # is tested by replay; do not silently miscount runs at a real hour boundary.
    if args.mode=='live':
        at=utc();remaining=((at.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1))-at).total_seconds()
        if args.seconds+40>remaining:p.error('Live fixture must fit the current UTC hour with 40s setup margin; run after the next hour boundary or use a shorter duration.')
    args.out.mkdir(parents=True,exist_ok=False);ev=Evidence(args.out);started=time.perf_counter();success=False;result=None;error=None;store=None
    ev.write('run_manifest.json',dict(source_path=str(Path(__file__).resolve()),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mode=args.mode,seconds=args.seconds,started_at_utc=utc().isoformat(),clock_simulated=args.mode=='replay'))
    try:
        with tempfile.TemporaryDirectory(prefix='aegis_ui_soak_') as directory:
            store=Path(directory);result=replay(store,ev) if args.mode=='replay' else live(store,ev,args.seconds)
        success=True
    except BaseException as exc:
        error=dict(type=type(exc).__name__,code=str(exc) if isinstance(exc,AssertionError) else 'details_withheld');raise
    finally:
        ev.write('verification.json',dict(success=success,mode=args.mode,error=error,result=result,checks=dict(ev.checks),total_checks=sum(ev.checks.values()),latencies={k:distribution(v) for k,v in ev.timings.items()},wall_seconds=round(time.perf_counter()-started,3),temporary_storage_cleaned=store is None or not store.exists(),real_ai_inference=False,field_data=False))
        ev.write('timing_samples.json',dict(ev.timings))


if __name__=='__main__':main()
