"""Generate 3 seeds x 4 virtual operational scenarios and replay every package."""
import argparse
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'frontend'))
from forecast_intake import encoded, package, replay, report
from intake_simulation import make, START, END, EXPORTED, SCENARIOS, VERSION


def http_rehearsal(out):
    """Synthetic points through real HTTP; actual server receipt timestamps."""
    import requests
    from werkzeug.serving import make_server
    import test_journal
    from telemetry_tool import export
    case = test_journal.JournalTests(); thread = None
    try:
        case.setUp()
        d,b = make(20261108, 'clean')
        with make_server('127.0.0.1',0,case.app,threaded=True) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                with requests.Session() as session:
                    session.trust_env=False; base='http://127.0.0.1:'+str(server.server_port)
                    def call(method,path,payload=None,expected=200):
                        r=session.request(method,base+path,json=payload,headers=case.headers[0],timeout=20,allow_redirects=False)
                        if r.status_code!=expected: raise ValueError('Unexpected HTTP status '+str(r.status_code))
                        return r.json()
                    meta={k:b['metadata'][k] for k in ('name','source','method','instrument','reference','nominal_interval_seconds')}
                    meta['client_stream_id']=b['stream_id']
                    stream=call('POST','/api/farm/seasons/'+case.season['id']+'/environment-streams',meta,201)['item']
                    records=[dict(client_sample_id=x['id'],observed_at=x['observed_at'],**x['payload']) for x in b['readings'][:4]]
                    url='/api/farm/environment-streams/'+stream['id']+'/samples'
                    first=call('POST',url,dict(records=records),201)
                    retry=call('POST',url,dict(records=records))
                    assert first['created']==4 and retry['created']==0 and retry['replayed']==4
                    owner=call('GET','/api/auth/me')['user']['id']
            finally:
                server.shutdown(); thread.join(timeout=10)
        # Export only after HTTP server is stopped. It acquires the storage lease.
        b=export(case.root,owner,stream['id'],'synthetic')
        d['linkage']={k:b[k] for k in ('owner_id','season_id','stream_id','bundle_sha256')}
        d['simulation'].update(scenario='http_backfill_four_virtual_points',generated_at=b['exported_at'],
            time_basis='simulated_observations_logs_with_server_receipts')
        d['schedule']['stream_id']=b['stream_id']; d['schedule']['available_at']=b['stream_created_at']
        out.mkdir(); (out/'dossier.input.json').write_bytes(encoded(d)); (out/'raw.input.json').write_bytes(encoded(b))
        package(out/'dossier.input.json',out/'raw.input.json',out/'package',START.isoformat(),END.isoformat(),b['exported_at'])
        verification=replay(out/'package')
        verification.update(actual_backend_http=True, actual_server_receipts=True, virtual_observations=True,
            physical_collection_performed=False, created=first['created'], replayed=retry['replayed'])
    finally:
        case.doCleanups()
    assert not case.root.exists() and thread is not None and not thread.is_alive()
    verification['temporary_store_and_server_cleaned']=True
    (out/'verification.json').write_bytes(encoded(verification))
    return verification


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    results = []
    for seed in (20261108, 20261109, 20261110):
        for scenario in SCENARIOS:
            root = args.out/(str(seed)+'-'+scenario); root.mkdir()
            d, b = make(seed, scenario)
            (root/'dossier.input.json').write_bytes(encoded(d)); (root/'raw.input.json').write_bytes(encoded(b))
            package(root/'dossier.input.json', root/'raw.input.json', root/'package',
                    START.isoformat(), END.isoformat(), EXPORTED.isoformat())
            verification = replay(root/'package')
            early = report(d, b, START.isoformat(), END.isoformat(), END.isoformat())
            (root/'early_asof.report.json').write_bytes(encoded(early))
            final = json.loads((root/'package/report.json').read_text(encoding='utf-8'))
            schedule = final['schedule_diagnostics']['schedule']
            if scenario=='clean': assert schedule['completeness']==1
            elif scenario=='dropout': assert len(schedule['missing_slots'])>=18
            elif scenario=='delayed_receipt':
                assert early['schedule_diagnostics']['schedule']['received_slots'] < schedule['received_slots']
            else:
                assert final['device_minus_reference_seconds']['max']==30 and schedule['off_schedule_samples']==72
            assert final['training_approved'] is False and final['physical_collection_performed'] is False
            results.append(dict(seed=seed, scenario=scenario, readings=len(b['readings']),
                completeness=schedule['completeness'], missing_slots=len(schedule['missing_slots']),
                off_schedule_samples=schedule['off_schedule_samples'],
                early_received_slots=early['schedule_diagnostics']['schedule']['received_slots'],
                final_received_slots=schedule['received_slots'], replay=verification))
    result=dict(success=True, generator_version=VERSION, cases=results, source='synthetic',
        physical_collection_performed=False, field_validated=False, training_performed=False,
        labels_generated=False, model_changed=False, simulation_window_hours=24,
        limits=['Software operational rehearsal; not an event prediction or hardware validation experiment',
                '24-hour virtual intake is not the FM03 120-hour feature readiness gate'])
    result['http_rehearsal']=http_rehearsal(args.out/'http')
    (args.out/'verification.json').write_bytes(encoded(result))
    print(json.dumps(dict(success=True, scenarios=len(results), source='synthetic', physical_collection_performed=False)))


if __name__=='__main__': main()
