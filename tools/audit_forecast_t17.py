"""Replay frozen T17 holdout and artifacts; never refit or select a new model."""
import argparse
import json
from pathlib import Path

from experiment_forecast_t17 import sha,write,ROOT,PLAN,PLAN_BYTES_SHA256,FEATURES,CONTRACT_SHA256,score_rows
from t17_cohort import generate_role,dependency_components
from t17_metrics import metrics,paired_bootstrap
from candidate_forecast_t17 import load_candidate,forecast_candidate
from hourly_aggregation import prepare_feature_input
from telemetry_audit import stamp
from telemetry_tool import digest
import numpy as np


def audit(root):
    root=Path(root)
    def load(name): return json.loads((root/name).read_text(encoding='utf-8'))
    frozen=load('plan.freeze.json'); selection=load('selection.freeze.json'); report=load('report.json')
    if frozen['plan_bytes_sha256']!=PLAN_BYTES_SHA256 or frozen['plan']!=PLAN: raise ValueError('Plan mismatch')
    for p,pin in frozen['source_sha256'].items():
        if sha(ROOT/p)!=pin: raise ValueError('Frozen source changed: '+p)
    events=[json.loads(line) for line in (root/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [e['event'] for e in events]==['plan_frozen','selection_frozen','holdout_opened','report_completed']
    assert all(stamp(x['at'])<=stamp(y['at']) for x,y in zip(events,events[1:]))
    assert events[0]['sha256']==sha(root/'plan.freeze.json')==selection['plan_freeze_sha256']
    assert events[1]['sha256']==events[2]['selection_freeze_sha256']==sha(root/'selection.freeze.json')==report['selection_freeze_sha256']
    assert events[3]['sha256']==sha(root/'report.json')
    assert report['selection']==selection and selection['holdout_used_for_selection'] is False
    cohort=load('cohort.audit.json'); allrows=[]; testrows=[]; scores={n:[] for n in report['aggregate_test']}; max_error=0
    for idx,seed in enumerate(PLAN['seeds']):
        development=load(str(seed)+'/development.rows.synthetic.json')
        for role in ('train','calibration','selection'): allrows.extend(development[role])
        saved=load(str(seed)+'/test.predictions.synthetic.json'); testrows.extend(saved['rows']); allrows.extend(saved['rows'])
        replay=generate_role(seed,'test')
        assert replay['rows']==saved['rows']
        assert replay['chunk_hashes']==cohort['chunks'][-3+idx]['chunks']
        assert replay['world_hashes']==cohort['chunks'][-3+idx]['world_hashes']
        manifest,artifact=load_candidate(root/str(seed)/'candidate',selection['candidate_manifest_pins'][str(seed)])
        actual=score_rows(saved['rows'],artifact,True); expected=saved['scores'][selection['selected']]
        for a,e in zip(actual,expected):
            assert (a is None)==(e is None)
            if a is not None: max_error=max(max_error,abs(a-e)); assert abs(a-e)<1e-12
        example=load(str(seed)+'/example.test.input.synthetic.json')['entry']
        issue=stamp(example['issue_times'][0]); end=issue.replace(minute=0,second=0,microsecond=0)
        from datetime import timedelta
        payload=prepare_feature_input(example['raw'],example['hourly_policy'],dict(
            start_at=(end-timedelta(hours=120)).isoformat(),end_at=end.isoformat(),as_of=issue.isoformat()),
            example['mapping']['unit_id'],example['context_revisions'])
        result=forecast_candidate(manifest,artifact,payload)[0]
        row_idx=next(i for i,r in enumerate(saved['rows']) if r['mapping_id']==example['id'])
        assert result['score']==actual[row_idx]
        for name in scores: scores[name].extend(saved['scores'][name])
    assert len(allrows)==576 and len({r['mapping_id'] for r in allrows})==576
    metadata=[dict(id=r['mapping_id'],mapping=dict(unit_id=r['unit_id'],season_id=r['season_id'],stream_id=r['stream_id'],groups=r['groups']),
        raw=dict(readings=[]),observations=dict(visits=[])) for r in allrows]
    components=dependency_components(metadata)
    assert components==cohort['components'] and len(components)==288
    for row in allrows:
        if row['predictors'] is not None:
            assert set(row['predictors'])==set(FEATURES)
            assert row['predictors_sha256']==digest(dict(contract_sha256=CONTRACT_SHA256,predictors=row['predictors']))
        if row['synthetic_y'] is not None:
            assert stamp(row['target_window_end'])<=stamp(row['endpoint_available_at'])<=stamp(row['label_cutoff'])
    recomputed={n:metrics(testrows,s,selection['thresholds'][n]) for n,s in scores.items()}
    assert recomputed==report['aggregate_test']
    ci=paired_bootstrap(testrows,scores,selection['thresholds'],PLAN['bootstrap']['replicates'],PLAN['bootstrap']['seed'],selection['selected'])
    assert ci==report['confidence_intervals']
    assert sha(ROOT/'forecast_demo/weather_bundle/manifest.json')==report['serving_manifest_sha256']
    assert sha(ROOT/'forecast_demo/weather_bundle/model.joblib')==report['serving_artifact_sha256']
    return dict(success=True,source='synthetic',plan_source_and_stage_order_verified=True,
        holdout_rows_regenerated=144,total_rows_audited=576,dependency_components=288,
        candidate_artifacts_reopened=3,maximum_score_replay_error=max_error,raw_example_inference_matches=True,
        aggregate_metrics_and_300_bootstraps_replayed=True,serving_bundle_unchanged=True,
        refitting_performed=False,holdout_retuning_performed=False,
        candidate_qualified_for_synthetic_shadow=report['candidate_qualified_for_synthetic_shadow'],deployment_activated=False)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); result=audit(args.run); write(args.out,result); print(json.dumps(result))


if __name__=='__main__': main()
