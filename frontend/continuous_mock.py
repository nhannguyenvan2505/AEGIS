"""Bounded, disposable continuous mock generator. No real sensors or AI.

Uses actual UTC hours and HTTP; snapshots arriving before readings stay immutable.
The generator is test tooling, never enabled by the product launcher.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime,timedelta,timezone
import ctypes,hashlib,json,math,os,queue,sqlite3,subprocess,tempfile,threading,time,uuid
from pathlib import Path
from soak_warning import DBS,PYTHON,Evidence,distribution,inspect_store
from server import build_app
from pilot_mysql_tools import open_readonly

KINDS=['continuous','dry','intermittent','outage','late','paused']
def utc():return datetime.now(timezone.utc)
def hour(at):return at.replace(minute=0,second=0,microsecond=0)


def row(kind,start):
    dry=kind=='dry'
    return dict(start_at=start.isoformat(),air_temperature_c=10 if dry else 26,relative_humidity_pct=30 if dry else 95,leaf_wet=not dry)


class Generator:
    def __init__(self,epoch,late_seconds=12):self.epoch=hour(epoch);self.late_seconds=late_seconds;self.sent={};self.skipped={}
    def pending(self,device,kind,at):
        """Bounded 24-hour catchup, completed buckets only; no backdated receipt."""
        sent=self.sent.setdefault(device,set());skipped=self.skipped.setdefault(device,set());end=hour(at);items=[]
        for i in range(24):
            start=end-timedelta(hours=24-i);stamp=start.isoformat();slot=int((start-self.epoch).total_seconds()/3600)
            if stamp in sent or stamp in skipped:continue
            if kind=='intermittent' and slot%6 in [1,2] or kind=='outage' and slot%12 in [0,1,2]:skipped.add(stamp);continue
            due=start+timedelta(hours=1,seconds=self.late_seconds if kind=='late' else 0)
            if due<=at:items.append(row(kind,start))
        # Keep state bounded even for a multi-day run.
        cutoff=(end-timedelta(hours=48)).isoformat();sent.intersection_update(x for x in list(sent) if x>=cutoff);skipped.intersection_update(x for x in list(skipped) if x>=cutoff)
        return items
    def acknowledge(self,device,items):self.sent.setdefault(device,set()).update(r['start_at'] for r in items)
    def enabled(self,kind,at):return not (kind=='paused' and int((hour(at)-self.epoch).total_seconds()/3600)%8 in [2,3])
    def state(self):return dict(epoch=self.epoch.isoformat(),late_seconds=self.late_seconds,sent={k:sorted(v) for k,v in self.sent.items()},skipped={k:sorted(v) for k,v in self.skipped.items()})


def process_resources(pid):
    """Windows native counters; no dependency install, never manipulates target."""
    if os.name!='nt':return dict(pid=pid,supported=False,reason='Windows counters only')
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ['peak_working_set','working_set','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile','private_bytes']]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.GetProcessHandleCount.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:raise OSError(ctypes.get_last_error(),'Process metrics unavailable')
    try:
        c=Counters();c.cb=ctypes.sizeof(c)
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb):raise OSError(ctypes.get_last_error(),'Memory metrics unavailable')
        times=[wintypes.FILETIME() for _ in range(4)];count=wintypes.DWORD()
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]):raise OSError(ctypes.get_last_error(),'CPU metrics unavailable')
        if not kernel.GetProcessHandleCount(handle,ctypes.byref(count)):raise OSError(ctypes.get_last_error(),'Handle metrics unavailable')
        seconds=lambda t:((t.dwHighDateTime<<32)+t.dwLowDateTime)/10000000
        return dict(pid=pid,supported=True,working_set_bytes=c.working_set,private_bytes=c.private_bytes,handle_count=count.value,cpu_seconds=seconds(times[2])+seconds(times[3]))
    finally:kernel.CloseHandle(handle)


def worker_pid(launcher_pid):
    """Resolve the Windows venv redirector's Python child, without command lines."""
    if os.name!='nt':return launcher_pid
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    k.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];k.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];k.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=k.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Process inventory unavailable')
    children={}
    try:
        e=Entry();e.size=ctypes.sizeof(e);ok=k.Process32FirstW(handle,ctypes.byref(e))
        while ok:
            if e.exe.lower().startswith('python'):children.setdefault(e.parent,[]).append(e.pid)
            ok=k.Process32NextW(handle,ctypes.byref(e))
    finally:k.CloseHandle(handle)
    pid=launcher_pid
    for _ in range(4):
        next_pids=children.get(pid,[])
        if len(next_pids)!=1:break
        pid=next_pids[0]
    return pid


def execute(out,seconds,restart_seconds,require_boundary,ev,stores=None):
    import requests
    process=None;log=None;ports=[];stops=[];observed=set();tokens=[];owners=[];jobs=[];snapshot_hashes={};generator=Generator(utc());started=time.monotonic();stopfile=None
    stats=dict(http_count=0,resource_count=0,working_set=0,private_bytes=0,handles=0);statuses=Counter();backend_pids=set()
    def record(file,item):
        with (out/file).open('a',encoding='utf-8') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
    with tempfile.TemporaryDirectory(prefix='aegis_ui_continuous_') as directory:
        storage=Path(directory)
        if stores is not None:stores.append(storage)
        app=build_app(storage,'http://127.0.0.1:9',{'kind':'fixture'});client=app.test_client();app.logger.setLevel(40)
        begin=hour(utc());season_start=(begin-timedelta(days=2)).date().isoformat();season_end=(begin+timedelta(days=3)).date().isoformat()
        for i in range(2):
            creds=dict(email=f'continuous-{i}@example.test',password='continuous-synthetic-password-123')
            ev.check('register201',client.post('/api/auth/register',json=creds).status_code==201);auth=client.post('/api/auth/login',json=creds).json
            tokens.append(dict(token=auth['access_token'],expires_at=auth['expires_at'],credentials=creds));headers={'Authorization':'Bearer '+auth['access_token']}
            plot=client.post('/api/farm/plots',headers=headers,json=dict(name=f'Synthetic continuous {i}')).json['item']
            season=client.post('/api/farm/plots/'+plot['id']+'/seasons',headers=headers,json=dict(name='Synthetic multi-hour test',start_date=season_start,end_date=season_end)).json['item'];owners.append(season['id'])
            for kind in KINDS:
                d=client.post('/api/farm/seasons/'+season['id']+'/devices',headers=headers,json=dict(name=kind,device_code=f'CONT-{i}-{kind}',source='mock')).json['item']
                items=generator.pending(d['id'],kind,utc());r=client.post('/api/farm/devices/'+d['id']+'/telemetry',headers=headers,json=dict(source='mock',records=items));ev.check('bootstrap_ingest201',r.status_code==201);generator.acknowledge(d['id'],items)
                j=client.post('/api/farm/devices/'+d['id']+'/automation-jobs',headers=headers,json=dict(client_job_id=str(uuid.uuid4()),name=kind,enabled=generator.enabled(kind,utc()),reason='Synthetic continuous consent')).json['item']
                jobs.append(dict(id=j['id'],device=d['id'],kind=kind,owner=i,version=j['version'],enabled=j['enabled']))
        info=out/'model_info.json';info.write_text(json.dumps(dict(kind='test_host',storage_mode='temporary',health=dict(model_version='TEST HOST — no AI loaded',device='none',model_sha256='none'))))
        runtime_files=list(Path(__file__).parent.glob('pilot_*.py'))+[Path(__file__),Path(__file__).with_name('server.py'),Path(__file__).with_name('soak_warning.py')]+list((Path(__file__).parent.parent/'backend/app').rglob('*.py'))+list((Path(__file__).parent/'static').glob('*'))
        runtime_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime_files if p.is_file()}
        ev.write('runtime_manifest.json',runtime_hashes)
        def frozen_runtime():
            if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha for p,sha in runtime_hashes.items()):raise RuntimeError('Runtime source changed during soak; refusing mixed versions')
        def launch():
            nonlocal process,log,stopfile,url
            frozen_runtime();name='session'+str(len(ports)+1);stopfile=out/('STOP_'+name);log=(out/(name+'.log')).open('w',encoding='utf-8')
            cmd=[str(PYTHON),'-u',str(Path(__file__).with_name('server.py')),'--backend','--storage',str(storage),'--ai-url','http://127.0.0.1:9','--info',str(info),'--shutdown-file',str(stopfile),'--enable-mock-automation','--automation-poll-seconds','5']
            process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=log,text=True,creationflags=subprocess.CREATE_NO_WINDOW,cwd=PYTHON.parent.parent.parent)
            q=queue.Queue();threading.Thread(target=lambda:q.put(process.stdout.readline()),daemon=True).start();port=int(q.get(timeout=20).strip());ports.append(port);url='http://127.0.0.1:'+str(port)
            record('events.jsonl',dict(event='backend_started',at_utc=utc().isoformat(),pid=process.pid,port=port))
        def stop():
            nonlocal process,log
            if process:
                stopfile.touch();process.wait(timeout=30);ev.check('graceful_exit0',process.returncode==0);stops.append(dict(pid=process.pid,exit_code=process.returncode));process.stdout.close();process=None
            if log:log.close();log=None
        def call(path,owner=0,method='GET',body=None,expected=(200,)):
            t=tokens[owner]
            if time.time()>=t['expires_at']-60:
                r=requests.post(url+'/api/auth/login',json=t['credentials'],timeout=15);ev.check('refresh_login200',r.status_code==200);a=r.json();t.update(token=a['access_token'],expires_at=a['expires_at'])
            start=time.perf_counter();r=requests.request(method,url+path,headers={'Authorization':'Bearer '+t['token']},json=body,timeout=15)
            sample=dict(at_utc=utc().isoformat(),method=method,path=path,status=r.status_code,elapsed_ms=(time.perf_counter()-start)*1000);stats['http_count']+=1;statuses[str(r.status_code)]+=1;record('http_samples.jsonl',sample)
            ev.check('http_expected_status',r.status_code in expected)
            return r
        def snapshot_audit():
            import hashlib
            with closing(open_readonly(storage/'demo.db')) as db:
                for id,snapshot in db.execute('SELECT id,snapshot_json FROM farm_assessments'):
                    sha=hashlib.sha256(snapshot.encode()).hexdigest()
                    if id in snapshot_hashes:ev.check('snapshot_immutable',snapshot_hashes[id]==sha)
                    else:snapshot_hashes[id]=sha
            with closing(open_readonly(storage/'followup.sqlite3')) as db:
                for id,snapshot in db.execute('SELECT id,snapshot_json FROM assessment_versions'):
                    key='version:'+id;sha=hashlib.sha256(snapshot.encode()).hexdigest()
                    if key in snapshot_hashes:ev.check('version_snapshot_immutable',snapshot_hashes[key]==sha)
                    else:snapshot_hashes[key]=sha
        url=None
        try:
            launch();last_restart=time.monotonic();last_sample=0;last_audit=0
            while time.monotonic()-started<seconds and not (out/'STOP').exists():
                at=utc();current=hour(at);observed.add(current.isoformat())
                for job in jobs:
                    items=generator.pending(job['device'],job['kind'],at)
                    if items:
                        r=call('/api/farm/devices/'+job['device']+'/telemetry',job['owner'],'POST',dict(source='mock',records=items),(200,201))
                        generator.acknowledge(job['device'],items)
                        record('generator_events.jsonl',dict(at_utc=utc().isoformat(),device=job['device'],kind=job['kind'],bucket_starts=[i['start_at'] for i in items],inserted=r.json()['inserted'],replayed=r.json()['replayed']))
                    enabled=generator.enabled(job['kind'],at)
                    if enabled!=job['enabled']:
                        r=call('/api/farm/automation-jobs/'+job['id'],job['owner'],'PUT',dict(client_event_id=str(uuid.uuid4()),base_version=job['version'],enabled=enabled,reason='Synthetic scheduled pause/resume'),(201,));job.update(version=r.json()['item']['version'],enabled=enabled)
                elapsed=time.monotonic()-started
                if elapsed-last_sample>=5:
                    worker=call('/api/farm/automation/status').json()['automation'];ev.check('worker_running',worker['worker_running'])
                    sample=dict(at_utc=utc().isoformat(),elapsed_seconds=elapsed,launcher_pid=process.pid,backend=process_resources(worker_pid(process.pid)),generator=process_resources(os.getpid()),db_bytes={n:(storage/n).stat().st_size for n in DBS if (storage/n).is_file()},worker=worker)
                    stats['resource_count']+=1;backend_pids.add(sample['backend']['pid'])
                    for key,field in [('working_set','working_set_bytes'),('private_bytes','private_bytes'),('handles','handle_count')]:stats[key]=max(stats[key],sample['backend'][field])
                    record('resources.jsonl',sample)
                    for owner,season in enumerate(owners):ev.check('owned_six_devices',call('/api/farm/seasons/'+season+'/warning-dashboard',owner).json()['pagination']['total']==6)
                    state=out/'generator_state.json';temporary=out/'generator_state.tmp';temporary.write_text(json.dumps(generator.state(),indent=2),encoding='utf-8');temporary.replace(state);last_sample=elapsed
                if elapsed-last_audit>=10:frozen_runtime();snapshot_audit();last_audit=elapsed
                if restart_seconds and time.monotonic()-last_restart>=restart_seconds:stop();launch();last_restart=time.monotonic()
                threading.Event().wait(1)
            completed_duration=time.monotonic()-started>=seconds
            # Drain one timer period so the final observed window is audited.
            threading.Event().wait(6);stop();snapshot_audit();result=inspect_store(storage,ev)
            ev.check('boundary_observed_if_required',not require_boundary or len(observed)>=2)
            with closing(open_readonly(storage/'demo.db')) as db:
                assessments=[json.loads(r[0]) for r in db.execute('SELECT snapshot_json FROM farm_assessments ORDER BY window_end,device_id')]
            with closing(open_readonly(storage/'followup.sqlite3')) as db:
                db.row_factory=sqlite3.Row;revisions=[dict(r) for r in db.execute('SELECT * FROM assessment_versions ORDER BY base_assessment_id,revision')]
                result['assessment_versions']=len(revisions)
                result['version_attempt_states']=dict(db.execute('SELECT state,COUNT(*) FROM assessment_version_attempts GROUP BY state'))
                ev.check('no_unresolved_version_attempt',db.execute("SELECT COUNT(*) FROM assessment_version_attempts WHERE state='running'").fetchone()[0]==0)
            from app.blast_conditions import digest
            originals={a['id']:a for a in assessments};previous={a['id']:a['id'] for a in assessments};numbers={a['id']:1 for a in assessments}
            for v in revisions:
                ev.check('version_base_integrity',digest(originals[v['base_assessment_id']])==v['base_sha256'])
                ev.check('version_hash_integrity',digest(json.loads(v['snapshot_json']))==v['snapshot_sha256'])
                ev.check('version_chain_contiguous',v['previous_id']==previous[v['base_assessment_id']] and v['revision']==numbers[v['base_assessment_id']]+1)
                previous[v['base_assessment_id']]=v['id'];numbers[v['base_assessment_id']]=v['revision']
            job_by_device={j['device']:j for j in jobs};actual_windows=sorted({a['input']['as_of'] for a in assessments})
            ev.check('all_permanently_enabled_devices_assessed',
                {j['device'] for j in jobs if j['kind']!='paused'} <= {a['device_id'] for a in assessments})
            for a in assessments+[json.loads(v['snapshot_json']) for v in revisions]:
                records=a['input']['records'];kind=job_by_device[a['device_id']]['kind']
                # Independent fixture oracle: full dry window cannot be advisory;
                # any incomplete window must stay insufficient, regardless of kind.
                if len(records)<24:ev.check('incomplete_is_not_low_risk',a['result']['status']=='insufficient_data')
                elif kind=='dry':ev.check('full_dry_no_pattern',a['result']['status']=='no_pattern_detected')
                else:ev.check('full_wet_advisory',a['result']['status']=='advisory')
            ev.check('assessments_cross_boundary_if_required',not require_boundary or len(actual_windows)>=2)
            ev.check('windows_bounded_by_actual_time',all(datetime.fromisoformat(w)<=hour(utc()) for w in actual_windows))
            ev.check('resource_samples_present',stats['resource_count']>0)
            ev.write('assessment_trace.json',assessments)
            ev.write('assessment_version_trace.json',[json.loads(v['snapshot_json']) for v in revisions])
            ev.write('workload.json',dict(epoch=generator.epoch.isoformat(),jobs=[{k:v for k,v in j.items() if k!='owner'} for j in jobs],clock_simulated=False,source='mock'))
            # Load only numeric latency samples after services stop. During the
            # run raw HTTP/resource records stream to disk rather than grow RAM.
            with (out/'http_samples.jsonl').open(encoding='utf-8') as f:latencies=[json.loads(line)['elapsed_ms'] for line in f]
            return dict(result,actual_elapsed_seconds=round(time.monotonic()-started,3),requested_seconds=seconds,completed_requested_duration=completed_duration,stop_reason='duration_elapsed' if completed_duration else 'stop_file',observed_hour_windows=sorted(observed),assessment_windows=actual_windows,owners=2,devices=12,http_requests=stats['http_count'],http_statuses=dict(statuses),http_latency=distribution(latencies),resource_samples=stats['resource_count'],backend_pids=sorted(backend_pids),peak_backend_working_set_bytes=stats['working_set'],peak_backend_private_bytes=stats['private_bytes'],peak_backend_handles=stats['handles'],ports=ports,graceful_stops=stops,clock_simulated=False)
        finally:
            if process:
                try:stop()
                except BaseException:
                    if process and process.poll() is None:process.terminate();process.wait(timeout=15)
                    if log:log.close()
            ev.write('cleanup.json',dict(backend_stopped=process is None or process.poll() is not None,ports=ports,graceful_stops=stops))
    # TemporaryDirectory is always closed by caller context, including failure.


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=int,default=300);p.add_argument('--restart-seconds',type=int,default=120);p.add_argument('--require-boundary',action='store_true');args=p.parse_args()
    if not 30<=args.seconds<=86400:p.error('--seconds must be 30–86400')
    if args.restart_seconds and not 30<=args.restart_seconds<=86400:p.error('--restart-seconds must be 0 or 30–86400')
    args.out.mkdir(parents=True,exist_ok=False);ev=Evidence(args.out);success=False;result=None;error=None;start=time.perf_counter();stores=[]
    ev.write('run_manifest.json',dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),started_at_utc=utc().isoformat(),clock_simulated=False))
    try:result=execute(args.out,args.seconds,args.restart_seconds,args.require_boundary,ev,stores);success=True
    except BaseException as exc:error=dict(type=type(exc).__name__,code=str(exc) if isinstance(exc,AssertionError) else 'details_withheld');raise
    finally:ev.write('verification.json',dict(success=success,result=result,error=error,checks=dict(ev.checks),total_checks=sum(ev.checks.values()),wall_seconds=time.perf_counter()-start,temporary_storage_cleaned=all(not p.exists() for p in stores),real_ai_inference=False,field_data=False))


if __name__=='__main__':main()
