"""T15 45 virtual observation scenarios plus actual journal HTTP compatibility."""
import argparse
from collections import Counter
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from endpoint_simulation import make,journal_commands,ISSUE,SCENARIOS,VERSION
from synthetic_endpoints import evaluate,PROTOCOL,PROTOCOL_SHA256
from forecast_intake import encoded
from telemetry_tool import digest


def http_journal(out):
    import requests
    import test_journal
    from werkzeug.serving import make_server
    case=test_journal.JournalTests(); thread=None
    try:
        case.setUp()
        with patch('pilot_journal.now',side_effect=lambda:datetime.now(timezone.utc)):
            with make_server('127.0.0.1',0,case.app,threaded=True) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
                try:
                    with requests.Session() as session:
                        session.trust_env=False; base='http://127.0.0.1:'+str(server.server_port)
                        def call(method,path,data=None,expected=200):
                            response=session.request(method,base+path,json=data,headers=case.headers[0],
                                                     timeout=20,allow_redirects=False)
                            if response.status_code!=expected: raise ValueError('Unexpected HTTP status '+str(response.status_code))
                            return response.json()
                        commands=journal_commands(make(20261108,'negative'))
                        url='/api/farm/seasons/'+case.season['id']+'/observations'
                        created=[call('POST',url,c,201)['item'] for c in commands]
                        for command,item in zip(commands,created):
                            assert call('POST',url,command)['item']==item
                            assert item['payload']['review'] is None and item['payload']['platform_verified'] is False
                            assert item['label_approved_for_training'] is False
                        old=created[2]
                        revision={k:old['payload'][k] for k in ('finding','notes','analysis_id','review','record_status')}
                        revision.update(base_revision=1,finding='uncertain',change_reason='Virtual observation correction; no label approval')
                        updated=call('PUT','/api/farm/observations/'+old['id'],revision,201)['item']
                        history=call('GET','/api/farm/observations/'+old['id']+'/revisions')
                        assert updated['revision']==2 and [r['revision'] for r in history['items']]==[2,1]
                        assert all(r['label_approved_for_training'] is False for r in history['items'])
                finally:
                    server.shutdown(); thread.join(timeout=10)
        out.mkdir()
        (out/'journal.synthetic.json').write_bytes(encoded(dict(created=created,updated=updated,revision_history=history,
            mapping=[dict(simulator_visit_id=c['client_visit_id'],journal_visit_id=r['id']) for c,r in zip(commands,created)],
            clock_basis='Virtual observed times; actual Backend recorded/available times',
            used_as_endpoint_labels=False)))
    finally:
        case.doCleanups()
    assert not case.root.exists() and thread is not None and not thread.is_alive()
    verification=dict(success=True,actual_backend_http=True,source='synthetic',created=4,replayed=4,
        append_revision_preserved=True,journal_remains_unverified=True,training_labels_generated=False,
        endpoint_attestations_promoted_to_journal_review=False,temporary_store_and_server_cleaned=True)
    (out/'verification.json').write_bytes(encoded(verification))
    return verification


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=False)
    cases=[]
    (args.out/'protocol.json').write_bytes(encoded(PROTOCOL))
    for seed in (20261108,20261109,20261110):
        for scenario in SCENARIOS:
            root=args.out/(str(seed)+'-'+scenario); root.mkdir()
            b=make(seed,scenario); before=digest(b)
            (root/'observations.synthetic.json').write_bytes(encoded(b))
            results={str(h):evaluate(b,ISSUE.isoformat(),(ISSUE+timedelta(hours=h)).isoformat()) for h in (60,96,120)}
            assert digest(b)==before
            assert results=={str(h):evaluate(b,ISSUE.isoformat(),(ISSUE+timedelta(hours=h)).isoformat()) for h in (60,96,120)}
            for r in results.values():
                assert r['event_y'] is None and r['training_approved'] is False and r['platform_verified'] is False
            if scenario=='late_review': assert results['96']['status']=='unverified' and results['120']['synthetic_y']==1
            if scenario=='revision_correction': assert results['96']['synthetic_y']==1 and results['120']['synthetic_y']==0
            (root/'results.synthetic.json').write_bytes(encoded(results))
            (root/'journal.commands.synthetic.json').write_bytes(encoded(journal_commands(b)))
            cases.append(dict(seed=seed,scenario=scenario,status_at_96h=results['96']['status'],
                final_status=results['120']['status'],synthetic_y=results['120']['synthetic_y'],
                knowledge_sha256=results['120']['knowledge_sha256'],input_unchanged=True,replay_identical=True))
    verification=dict(success=True,source='synthetic',protocol_sha256=PROTOCOL_SHA256,generator_version=VERSION,
        seeds=3,scenario_types=len(SCENARIOS),cases=cases,final_status_counts=dict(Counter(c['final_status'] for c in cases)),
        actual_journal_http=http_journal(args.out/'http'),physical_collection_performed=False,
        training_performed=False,field_validated=False,operational_event_y_generated=False,
        latent_truth_used=False,model_changed=False,
        limits=['Endpoint rule acceptance on virtual observations, not prediction accuracy',
                'Synthetic_y is offline simulator status, not training-approved or clinical truth',
                'No sensor/outcome join or model selection performed; those belong to T16/T17'])
    (args.out/'verification.json').write_bytes(encoded(verification))
    print(json.dumps(dict(success=True,cases=len(cases),source='synthetic',protocol_sha256=PROTOCOL_SHA256)))


if __name__=='__main__': main()
