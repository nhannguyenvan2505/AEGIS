"""Frozen T17 development/calibration/selection, then one locked holdout opening."""
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[_name]='1'
import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from t17_cohort import ROOT,PLAN,PLAN_BYTES_SHA256,PLAN_PATH,generate_role,dependency_components,digest
from t17_metrics import metrics,select_threshold,paired_bootstrap
sys.path.insert(0,str(ROOT/'forecast_demo/runtime'))
from candidate_forecast_t17 import calibrated_scores,load_candidate,RUNTIME_FILES
from weather_forecast import FEATURES,CONTRACT_SHA256
from forecast_intake import encoded
from synthetic_endpoints import PROTOCOL_SHA256
from telemetry_audit import stamp


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path)
    with path.open('xb') as f: f.write(encoded(value))


def frame(rows): return pd.DataFrame([r['predictors'] for r in rows],columns=FEATURES)
def fit_rows(rows): return [r for r in rows if r['engineering_eligible']]


def fit_models(train,calibration,seed):
    tr,cal=fit_rows(train),fit_rows(calibration)
    if len({r['synthetic_y'] for r in tr})!=2 or len({r['synthetic_y'] for r in cal})!=2:
        raise ValueError('Frozen cohort lacks both classes in train/calibration; report failure, do not resample')
    x,y=frame(tr),[r['synthetic_y'] for r in tr]; xc,yc=frame(cal),[r['synthetic_y'] for r in cal]
    prior=DummyClassifier(strategy='prior').fit(x,y)
    models={}
    bases=dict(logistic=make_pipeline(StandardScaler(),LogisticRegression(**PLAN['models']['logistic'],random_state=seed)),
        hist_gradient_boosting=HistGradientBoostingClassifier(**PLAN['models']['hist_gradient_boosting'],random_state=seed))
    for name,base in bases.items():
        base.fit(x,y); epsilon=PLAN['calibration']['epsilon']; p=np.clip(base.predict_proba(xc)[:,1],epsilon,1-epsilon)
        calibrator=LogisticRegression(C=PLAN['calibration']['C'],max_iter=1000,random_state=seed)
        calibrator.fit(np.log(p/(1-p)).reshape(-1,1),yc)
        models[name]=dict(base_model=base,calibrator=calibrator,epsilon=epsilon,feature_order=list(FEATURES))
    return prior,models


def score_rows(rows,model,calibrated=False):
    ids=[i for i,r in enumerate(rows) if r['predictors'] is not None]; scores=[None]*len(rows)
    if ids:
        records=[rows[i]['predictors'] for i in ids]
        values=calibrated_scores(model,records) if calibrated else model.predict_proba(pd.DataFrame(records,columns=FEATURES))[:,1]
        for i,v in zip(ids,values): scores[i]=float(v)
    return scores


def check_groups(parts):
    light=[e for part in parts for e in part['light_entries']]; components=dependency_components(light)
    roles={r['mapping_id']:r['experiment_role'] for part in parts for r in part['rows']}
    if any(len({roles[m] for m in members})!=1 for members in components.values()):
        raise ValueError('Dependency group crosses experiment roles')
    rows=[r for part in parts for r in part['rows']]; order=('train','calibration','selection','test')
    for left,right in zip(order,order[1:]):
        a=[r for r in rows if r['experiment_role']==left]; b=[r for r in rows if r['experiment_role']==right]
        if a and b:
            if max(stamp(r['target_window_end']) for r in a)+timedelta(hours=24)>=min(stamp(r['feature_window_start']) for r in b):
                raise ValueError('Feature/target support overlaps experiment roles')
            if max(stamp(r['label_cutoff']) for r in a)>=min(stamp(r['issued_at']) for r in b):
                raise ValueError('Earlier labels not mature before next role')
    return components


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); out=args.out; out.mkdir(parents=True,exist_ok=False)
    def event(name,**data):
        with (out/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(dict(event=name,at=datetime.now(timezone.utc).isoformat(),**data),sort_keys=True)+'\n')
    source_files=['tools/experiment_forecast_t17.py','tools/t17_cohort.py','tools/t17_metrics.py',
        'frontend/synthetic_dataset.py','frontend/dataset_simulation.py','frontend/hourly_aggregation.py','frontend/synthetic_endpoints.py',
        'frontend/endpoint_simulation.py','frontend/intake_simulation.py','frontend/forecast_intake.py',
        'frontend/telemetry_audit.py','frontend/telemetry_tool.py','frontend/controlled_source.py']
    frozen=dict(plan_bytes_sha256=PLAN_BYTES_SHA256,plan=PLAN,source_sha256={p:sha(ROOT/p) for p in source_files},
        runtime_sha256={p:sha(ROOT/'forecast_demo/runtime'/p) for p in RUNTIME_FILES},
        environment=dict(python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__,pandas=pd.__version__,joblib=joblib.__version__,threads=1))
    write(out/'plan.freeze.json',frozen); event('plan_frozen',sha256=sha(out/'plan.freeze.json'))
    old=ROOT/'forecast_demo/weather_bundle'
    if sha(old/'manifest.json')!='2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f': raise ValueError('Serving comparator pin changed')
    old_manifest=json.loads((old/'manifest.json').read_text()); assert sha(old/'model.joblib')==old_manifest['artifact_sha256']
    serving=joblib.load(old/'model.joblib')
    dev={}; parts=[]; pooled_rows=[]; selection_scores={name:[] for name in ('prior','logistic','hist_gradient_boosting','fm03_frozen')}
    for seed in PLAN['seeds']:
        root=out/str(seed); root.mkdir()
        data={}
        for role in ('train','calibration','selection'):
            def example(e,w,role=role):
                if role=='train': write(root/'example.train.input.synthetic.json',dict(entry=e,future_world=w,world_not_predictors=True))
            part=generate_role(seed,role,example); parts.append(part); data[role]=part
            print(json.dumps(dict(seed=seed,role=role,rows=len(part['rows']),stage='development')),flush=True)
        prior,models=fit_models(data['train']['rows'],data['calibration']['rows'],seed)
        rows=data['selection']['rows']; scores=dict(prior=score_rows(rows,prior),fm03_frozen=score_rows(rows,serving))
        scores.update({name:score_rows(rows,a,True) for name,a in models.items()})
        for name in selection_scores: selection_scores[name].extend(scores[name])
        pooled_rows.extend(rows); dev[seed]=dict(data=data,prior=prior,models=models)
        write(root/'development.rows.synthetic.json',{role:part['rows'] for role,part in data.items()})
    check_groups(parts)
    selection_metrics={name:metrics(pooled_rows,scores,.5) for name,scores in selection_scores.items()}
    selected=min(('logistic','hist_gradient_boosting'),key=lambda n:(selection_metrics[n]['log_loss'],selection_metrics[n]['brier'],n))
    choices={name:select_threshold(pooled_rows,scores,PLAN['selection']['threshold_grid'],PLAN['selection']['minimum_event_recall_including_abstentions'])
             for name,scores in selection_scores.items() if name!='fm03_frozen'}
    thresholds={n:c['threshold'] for n,c in choices.items()}; thresholds['fm03_frozen']=.5
    candidate_pins={}
    for seed,item in dev.items():
        root=out/str(seed)/'candidate'; root.mkdir(); artifact=item['models'][selected]; artifact['threshold']=thresholds[selected]
        joblib.dump(artifact,root/'candidate.joblib')
        manifest=dict(schema_version='aegis-t17-synthetic-candidate-v1',model_version='fm04-t17-'+selected+'-sigmoid-v1',
            source='synthetic',field_validated=False,deployment_activated=False,artifact='candidate.joblib',artifact_sha256=sha(root/'candidate.joblib'),
            feature_contract_sha256=CONTRACT_SHA256,feature_order=list(FEATURES),endpoint_protocol_sha256=PROTOCOL_SHA256,
            experiment_plan_bytes_sha256=PLAN_BYTES_SHA256,calibration_scope='t17_generator_only',threshold=thresholds[selected],
            replicate_seed=seed,runtime_sha256=frozen['runtime_sha256'],environment=frozen['environment'])
        write(root/'manifest.json',manifest); candidate_pins[str(seed)]=sha(root/'manifest.json')
        m,a=load_candidate(root,candidate_pins[str(seed)])
        # Explicit replay on scored rows, retaining abstentions as None.
        assert score_rows(item['data']['selection']['rows'],a,True)==score_rows(item['data']['selection']['rows'],artifact,True)
    selection=dict(selected=selected,selection_metrics=selection_metrics,threshold_choices=choices,thresholds=thresholds,
        primary_artifact_seed=PLAN['selection']['primary_artifact_seed'],candidate_manifest_pins=candidate_pins,
        plan_freeze_sha256=sha(out/'plan.freeze.json'),holdout_generated=False,holdout_used_for_selection=False)
    write(out/'selection.freeze.json',selection); event('selection_frozen',sha256=sha(out/'selection.freeze.json'))
    event('holdout_opened',selection_freeze_sha256=sha(out/'selection.freeze.json'))
    test_rows=[]; test_scores={n:[] for n in selection_scores}; per_seed={}; raw_versus_calibrated={}
    for seed,item in dev.items():
        root=out/str(seed)
        def example(e,w): write(root/'example.test.input.synthetic.json',dict(entry=e,future_world=w,world_not_predictors=True))
        part=generate_role(seed,'test',example); parts.append(part); rows=part['rows']; test_rows.extend(rows)
        scores=dict(prior=score_rows(rows,item['prior']),fm03_frozen=score_rows(rows,serving))
        scores.update({n:score_rows(rows,a,True) for n,a in item['models'].items()})
        for name in test_scores: test_scores[name].extend(scores[name])
        per_seed[str(seed)]={n:metrics(rows,s,thresholds[n]) for n,s in scores.items()}
        raw_versus_calibrated[str(seed)]={n:dict(raw=metrics(rows,score_rows(rows,a['base_model']),thresholds[n]),
            calibrated=per_seed[str(seed)][n]) for n,a in item['models'].items()}
        write(root/'test.predictions.synthetic.json',dict(rows=rows,scores=scores))
        print(json.dumps(dict(seed=seed,role='test',rows=len(rows),stage='holdout')),flush=True)
    components=check_groups(parts)
    aggregate={n:metrics(test_rows,s,thresholds[n]) for n,s in test_scores.items()}
    intervals=paired_bootstrap(test_rows,test_scores,thresholds,PLAN['bootstrap']['replicates'],PLAN['bootstrap']['seed'],selected)
    gate=PLAN['acceptance']; checks=dict(
        paired_brier_better_than_prior=intervals['selected_minus_prior']['brier']['upper']<gate['paired_delta_brier_upper_vs_prior_below'],
        paired_log_loss_better_than_prior=intervals['selected_minus_prior']['log_loss']['upper']<gate['paired_delta_log_loss_upper_vs_prior_below'],
        feature_coverage=aggregate[selected]['feature_coverage']>=gate['minimum_feature_coverage'],
        event_recall=aggregate[selected]['event_recall_including_abstentions'] is not None and aggregate[selected]['event_recall_including_abstentions']>=gate['minimum_event_recall_including_abstentions'])
    if sha(old/'manifest.json')!='2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f' or sha(old/'model.joblib')!=old_manifest['artifact_sha256']:
        raise ValueError('Serving bundle changed during T17')
    report=dict(success=True,source='synthetic',selected=selected,selection=selection,aggregate_test=aggregate,
        per_seed_test=per_seed,calibration_diagnostics=raw_versus_calibrated,confidence_intervals=intervals,
        acceptance_checks=checks,candidate_qualified_for_synthetic_shadow=all(checks.values()),
        primary_artifact_seed=selection['primary_artifact_seed'],candidate_manifest_pins=candidate_pins,
        total_rows=sum(len(p['rows']) for p in parts),dependency_components=len(components),
        role_counts=dict(Counter(r['experiment_role'] for p in parts for r in p['rows'])),
        endpoint_status_counts=dict(Counter(r['endpoint_status'] for r in test_rows)),
        plan_freeze_sha256=sha(out/'plan.freeze.json'),selection_freeze_sha256=sha(out/'selection.freeze.json'),
        serving_manifest_sha256=sha(old/'manifest.json'),serving_artifact_sha256=sha(old/'model.joblib'),
        serving_unchanged=True,deployment_activated=False,field_validated=False,
        limits=['Synthetic generator experiment, not field disease performance',
                'First observed event interval is not infection time; lead bounds are observation intervals',
                'False alerts use decisive 72h unit windows, not a measured continuous deployment rate',
                'Intervals resample dependency groups within seeds; three seeds do not cover all possible generators',
                'Holdout opened once after model/threshold artifacts froze; no holdout retuning or serving activation'])
    write(out/'report.json',report)
    write(out/'cohort.audit.json',dict(components=components,chunks=[dict(chunks=p['chunk_hashes'],world_hashes=p['world_hashes']) for p in parts]))
    event('report_completed',sha256=sha(out/'report.json'))
    print(json.dumps(dict(success=True,selected=selected,qualified=report['candidate_qualified_for_synthetic_shadow'],checks=checks)),flush=True)


if __name__=='__main__': main()
