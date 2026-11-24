"""T17 safety of scientific denominators, plan locks, cohort and offline inference.

Only development fixtures are generated here; the T17 test role stays unopened.
"""
import copy
from datetime import timedelta
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT/'forecast_demo/runtime'))
from experiment_forecast_t17 import fit_models,score_rows
from t17_cohort import generate_entry,chunk_input,PLAN,PLAN_BYTES_SHA256,digest
from t17_metrics import metrics,select_threshold,paired_bootstrap
from candidate_forecast_t17 import calibrated_scores,load_candidate,forecast_candidate,sha,RUNTIME_FILES
from weather_forecast import FEATURES,CONTRACT_SHA256
from hourly_aggregation import prepare_feature_input
from dataset_simulation import make
from synthetic_dataset import build

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frame=pd.DataFrame([{f:float(i) for f in FEATURES} for i in range(8)],columns=FEATURES)
        y=[0]*4+[1]*4
        base=make_pipeline(StandardScaler(),LogisticRegression()).fit(frame,y)
        cls.artifact=dict(base_model=base,calibrator=LogisticRegression().fit(np.arange(-4,4).reshape(-1,1),y),
            epsilon=1e-6,feature_order=list(FEATURES),threshold=.5)
        e=make(seeds=(20261108,))['entries'][0]
        cls.payload=prepare_feature_input(e['raw'],e['hourly_policy'],dict(
            start_at=e['hourly_policy']['anchor_at'],end_at=e['issue_times'][0][:13]+':00:00+00:00',as_of=e['issue_times'][0]),
            e['mapping']['unit_id'],e['context_revisions'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aegis_t17_'); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)

    def package(self):
        joblib.dump(self.artifact,self.root/'candidate.joblib')
        m=dict(schema_version='aegis-t17-synthetic-candidate-v1',source='synthetic',field_validated=False,
            deployment_activated=False,model_version='software-unit-fixture',artifact='candidate.joblib',
            artifact_sha256=sha(self.root/'candidate.joblib'),feature_contract_sha256=CONTRACT_SHA256,feature_order=list(FEATURES),
            endpoint_protocol_sha256='07f5ae4b14ee7c724ac0a7851e1721b79cdede80876b546d44f7e1e2c937201a',
            experiment_plan_bytes_sha256=PLAN_BYTES_SHA256,calibration_scope='t17_generator_only',threshold=.5,
            runtime_sha256={n:sha(ROOT/'forecast_demo/runtime'/n) for n in RUNTIME_FILES},
            environment=dict(python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__,pandas=pd.__version__,joblib=joblib.__version__))
        (self.root/'manifest.json').write_text(json.dumps(m),encoding='utf-8'); return m,sha(self.root/'manifest.json')

    def test_frozen_plan_and_deterministic_development_generator(self):
        e,w=generate_entry(PLAN['seeds'][0],'train',0,0)
        self.assertEqual((e,w),generate_entry(PLAN['seeds'][0],'train',0,0))
        self.assertFalse(w['used_as_predictors']); self.assertFalse(w['used_directly_as_endpoint_label'])
        with self.assertRaises(ValueError): generate_entry(1,'train',0,0)

    def test_future_world_is_outside_feature_contract(self):
        e,w=generate_entry(PLAN['seeds'][0],'train',0,0); before=digest(e['raw'])
        w['future_humidity']=[1]*72; w['latent_event_hour']=1
        self.assertEqual(digest(e['raw']),before)
        self.assertNotIn('future_temperature',e['mapping'])
        self.assertNotIn('latent_event_hour',e['raw'])

    def test_group_members_share_environment_and_cannot_cross_roles(self):
        a,_=generate_entry(PLAN['seeds'][0],'train',0,0); b,_=generate_entry(PLAN['seeds'][0],'train',0,1)
        r=build(chunk_input([a,b],'train'))
        self.assertEqual(len(r['dependency_components']),1)
        self.assertNotEqual(a['mapping']['unit_id'],b['mapping']['unit_id'])

    def test_metrics_abstained_events_are_misses_and_unresolved_are_separate(self):
        rows=[dict(synthetic_y=y,observed_event_interval=None,issued_at='2026-07-01T00:00:00Z') for y in (1,1,0,None)]
        m=metrics(rows,[.9,None,.8,.9],.5)
        self.assertEqual(m['event_recall_including_abstentions'],.5)
        self.assertEqual(m['feature_coverage'],.75); self.assertEqual(m['decisive_alert_precision'],.5)
        self.assertEqual(m['alerts_with_unresolved_outcome'],1); self.assertEqual(m['observable_unit_days'],9)
        self.assertAlmostEqual(m['false_alerts_per_100_observable_unit_days'],100/9)

    def test_metrics_empty_and_invalid_probabilities(self):
        self.assertIsNone(metrics([],[],.5)['brier'])
        with self.assertRaises(ValueError): metrics([dict(synthetic_y=0)],[float('nan')],.5)
        with self.assertRaises(ValueError): metrics([dict(synthetic_y=0)],[],.5)

    def test_threshold_selection_flags_infeasible_recall_without_imputation(self):
        rows=[dict(synthetic_y=y,observed_event_interval=None) for y in (1,1,0)]
        choice=select_threshold(rows,[.8,None,.2],[.1,.5,.9],.75)
        self.assertFalse(choice['recall_constraint_met'])
        self.assertEqual(choice['threshold'],.5)

    def test_cluster_bootstrap_is_paired_and_reproducible(self):
        rows=[dict(synthetic_y=y,observed_event_interval=None,replicate_seed=1,component_id=str(i//2)) for i,y in enumerate([0,1]*4)]
        scores=dict(prior=[.5]*8,candidate=[.1,.9]*4)
        a=paired_bootstrap(rows,scores,dict(prior=.5,candidate=.5),20,7,'candidate')
        self.assertEqual(a,paired_bootstrap(rows,scores,dict(prior=.5,candidate=.5),20,7,'candidate'))
        self.assertLess(a['selected_minus_prior']['brier']['upper'],0)

    def test_candidate_reopen_matches_in_memory_scores(self):
        m,pin=self.package(); loaded,artifact=load_candidate(self.root,pin)
        a=forecast_candidate(m,self.artifact,self.payload); b=forecast_candidate(loaded,artifact,self.payload)
        self.assertEqual(a,b); self.assertEqual(a[0]['horizon_hours'],72)
        self.assertFalse(a[0]['deployment_activated']); self.assertFalse(a[0]['field_validated'])

    def test_missing_numeric_hour_and_unknown_age_abstain(self):
        m,_=self.package()
        for mode in ('temperature','age'):
            p=copy.deepcopy(self.payload)
            if mode=='temperature': p['series'][0]['telemetry'][0]['air_temperature_c']=None
            else: p['series'][0]['context_revisions'][0]['profile'].update(planting_method='unknown',sown_on=None)
            r=forecast_candidate(m,self.artifact,p)[0]
            self.assertIsNone(r['score']); self.assertEqual(r['status'],'insufficient_data')

    def test_real_source_and_label_injection_are_rejected(self):
        m,_=self.package()
        for change in (dict(source='field_observed'),dict(labels=[1]),dict(score=.9)):
            with self.assertRaises(ValueError): forecast_candidate(m,self.artifact,dict(self.payload,**change))

    def test_predictor_whitelist_and_numeric_types(self):
        good={f:1.0 for f in FEATURES}
        for changed in (dict(good,label=1),dict(good,crop_age_days=True),dict(good,crop_age_days=float('inf'))):
            with self.assertRaises(ValueError): calibrated_scores(self.artifact,[changed])

    def test_bad_manifest_pin_and_artifact_bytes_refuse_before_pickle_load(self):
        _,pin=self.package()
        with patch('joblib.load',side_effect=AssertionError('Must not deserialize')):
            with self.assertRaises(ValueError): load_candidate(self.root,'0'*64)
            with (self.root/'candidate.joblib').open('ab') as f: f.write(b'corrupt')
            with self.assertRaises(ValueError): load_candidate(self.root,pin)

    def test_runtime_endpoint_plan_and_dependency_pins(self):
        m,_=self.package()
        for key,value in (('endpoint_protocol_sha256','bad'),('experiment_plan_bytes_sha256','bad'),
                          ('runtime_sha256',dict(m['runtime_sha256'],**{'pipeline.py':'bad'})),
                          ('environment',dict(m['environment'],sklearn='0.0'))):
            changed=dict(m,**{key:value}); (self.root/'manifest.json').write_text(json.dumps(changed),encoding='utf-8')
            with self.assertRaises(ValueError): load_candidate(self.root,sha(self.root/'manifest.json'))

    def test_training_requires_two_classes_without_resampling(self):
        rows=[dict(engineering_eligible=True,synthetic_y=0,predictors={f:1 for f in FEATURES})]
        with self.assertRaises(ValueError): fit_models(rows,rows,1)

    def test_offline_candidate_input_is_not_mutated(self):
        m,_=self.package(); before=copy.deepcopy(self.payload)
        forecast_candidate(m,self.artifact,self.payload)
        self.assertEqual(before,self.payload)


if __name__=='__main__': unittest.main()
