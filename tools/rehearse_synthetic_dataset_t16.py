"""T16 reproducible cohort join/split, negative controls and full report replay."""
import argparse
import copy
from datetime import timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from dataset_simulation import make,repin,seal,VERSION
from synthetic_dataset import build,FEATURES
from forecast_intake import encoded
from telemetry_audit import stamp
from telemetry_tool import digest


def variant(original,name):
    b=copy.deepcopy(original)
    if name=='shared_environment':
        for e in b['entries']:
            e['mapping']['groups']['shared_environment_alias']='VIRTUAL-SHARED-ENVIRONMENT'
            e['observations']['groups']=copy.deepcopy(e['mapping']['groups'])
    elif name=='late_raw_receipt':
        e=b['entries'][0]; issue=stamp(e['issue_times'][0])
        for r in e['raw']['readings'][:6]: r['received_at']=r['available_at']=(issue+timedelta(hours=2)).isoformat()
    elif name=='future_context_and_qc':
        e=b['entries'][0]; issue=stamp(e['issue_times'][0]); ctx=copy.deepcopy(e['context_revisions'][0])
        ctx.update(revision=2,recorded_at=(issue+timedelta(hours=1)).isoformat(),available_at=(issue+timedelta(hours=1)).isoformat())
        ctx['profile']['sown_on']='2026-08-02'; e['context_revisions'].append(ctx)
        e['raw']['readings'][0].update(excluded_at=(issue+timedelta(hours=2)).isoformat(),
            exclusion_reason='Simulated future QC',exclusion_request_id=e['id'])
    elif name=='immature_train_labels':
        issue=stamp(b['entries'][0]['issue_times'][0])
        b['split_plan']['periods']['train']['label_cutoff']=(issue+timedelta(hours=48)).isoformat()
    elif name=='support_overlap':
        delta=timedelta(days=5)
        for e in b['entries']:
            if b['split_plan']['assignments'][e['id']]!='train': continue
            e['issue_times']=[(stamp(t)+delta).isoformat() for t in e['issue_times']]
            for r in e['raw']['readings']:
                for k in ('observed_at','received_at','available_at'): r[k]=(stamp(r[k])+delta).isoformat()
            e['hourly_policy']['anchor_at']=(stamp(e['hourly_policy']['anchor_at'])+delta).isoformat()
            for v in e['observations']['visits']:
                for k in ('observed_at','recorded_at','available_at'): v[k]=(stamp(v[k])+delta).isoformat()
                if v['review']: v['review']['reviewed_at']=(stamp(v['review']['reviewed_at'])+delta).isoformat()
                v.pop('payload_sha256'); v['payload_sha256']=digest(v)
            e['observations']['exported_at']=(stamp(e['observations']['exported_at'])+delta).isoformat()
        for k in ('start_at','end_at','label_cutoff'):
            b['split_plan']['periods']['train'][k]=(stamp(b['split_plan']['periods']['train'][k])+delta).isoformat()
    else: raise ValueError('Unknown rehearsal variant')
    for e in b['entries']: repin(e)
    return seal(b)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=False)
    b=make(); original=digest(b)
    (args.out/'cohort.input.synthetic.json').write_bytes(encoded(b))
    r=build(b)
    assert r['ready_for_engineering_experiment'] and r['eligible_rows']==18 and len(r['dependency_components'])==9
    assert r['distinct_simulated_events']==9 and digest(b)==original
    (args.out/'dataset.report.synthetic.json').write_bytes(encoded(r))
    # Read the serialized original and reproduce the complete report.
    reloaded=json.loads((args.out/'cohort.input.synthetic.json').read_text(encoding='utf-8'))
    assert build(reloaded)==r
    results={}
    baseline={x['mapping_id']:x for x in r['rows']}
    for name in ('shared_environment','late_raw_receipt','future_context_and_qc','immature_train_labels','support_overlap'):
        v=variant(b,name); report=build(v)
        if name=='shared_environment': assert report['eligible_rows']==0 and len(report['dependency_conflicts'])==1
        elif name=='late_raw_receipt':
            affected=next(x for x in report['rows'] if x['mapping_id']==b['entries'][0]['id'])
            assert affected['feature_status']=='insufficient_data' and affected['synthetic_y']==0
        elif name=='future_context_and_qc':
            for row in report['rows']:
                assert row['predictors_sha256']==baseline[row['mapping_id']]['predictors_sha256']
                assert row['feature_evidence_sha256']==baseline[row['mapping_id']]['feature_evidence_sha256']
        elif name=='immature_train_labels': assert report['split_counts']['train']['rows']==0
        else: assert report['exclusion_counts']['purged_feature_target_support_overlap']==6
        (args.out/(name+'.report.synthetic.json')).write_bytes(encoded(report))
        results[name]=dict(input_sha256=v['bundle_sha256'],report_sha256=report['report_sha256'],
            ready_for_engineering_experiment=report['ready_for_engineering_experiment'],eligible_rows=report['eligible_rows'],
            exclusion_counts=report['exclusion_counts'],dependency_conflicts=len(report['dependency_conflicts']))
    verification=dict(success=True,source='synthetic',generator_version=VERSION,seeds=3,entries=18,
        raw_points=sum(len(e['raw']['readings']) for e in b['entries']),predictor_count=len(FEATURES),
        split_counts=r['split_counts'],declared_components=9,distinct_simulated_events=9,
        input_unchanged=True,serialized_report_replayed=True,controls=results,
        feature_contract_sha256=r['feature_contract_sha256'],protocol_sha256=r['protocol_sha256'],
        training_performed=False,training_approved=False,field_validated=False,
        model_changed=False,test_outcomes_exposed_for_audit=True,blind_holdout_for_model_selection=False,
        limits=['Engineering join/split fixtures; no model fit, accuracy estimate or sample-size claim',
                'Paired virtual positive/negative outcomes use the same environmental waveform',
                'Control inputs are regenerated by variant(original,name) in this versioned rehearsal script'])
    (args.out/'verification.json').write_bytes(encoded(verification))
    print(json.dumps(dict(success=True,rows=18,controls=len(results),declared_components=9,training_approved=False)))


if __name__=='__main__': main()
