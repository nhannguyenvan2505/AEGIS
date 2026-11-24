"""T16 joins, separate cutoffs, dependency closure and temporal purge acceptance."""
import copy
from datetime import timedelta
import unittest
from uuid import uuid4

from dataset_simulation import make,repin,seal
from synthetic_dataset import build,FEATURES
from telemetry_audit import stamp
from telemetry_tool import digest


class SyntheticDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=make(seeds=(20261108,))

    def setUp(self): self.b=copy.deepcopy(self.base)

    def one(self):
        self.b['entries']=self.b['entries'][:1]
        self.b['split_plan']['assignments']={self.b['entries'][0]['id']:'train'}
        return self.b['entries'][0]

    def run_build(self):
        for e in self.b['entries']: repin(e)
        return build(seal(self.b))

    def test_ready_fixture_has_strict_model_matrices_and_declared_group_counts(self):
        r=self.run_build(); self.assertTrue(r['ready_for_engineering_experiment'])
        self.assertEqual((r['eligible_rows'],len(r['dependency_components']),r['distinct_simulated_events']),(6,3,3))
        for s in ('train','validation','test'):
            self.assertEqual(r['split_counts'][s]['class_counts'],{'0':1,'1':1})
            for row in r['matrices'][s]:
                self.assertEqual(set(row),{'row_id','predictors','synthetic_y'})
                self.assertEqual(set(row['predictors']),set(FEATURES)); self.assertEqual(len(FEATURES),41)
        self.assertFalse(r['training_approved']); self.assertFalse(r['sufficient_for_scientific_claims'])
        self.assertFalse(r['blind_holdout_for_model_selection'])

    def test_shared_legacy_environment_blocks_every_split(self):
        self.b=make(seeds=(20261108,),shared_environment=True); r=self.run_build()
        self.assertFalse(r['ready_for_engineering_experiment']); self.assertEqual(r['eligible_rows'],0)
        self.assertEqual(len(r['dependency_conflicts']),1)

    def test_dependency_closure_is_transitive_across_alias_dimensions(self):
        a,b,c=self.b['entries'][0],self.b['entries'][2],self.b['entries'][4]
        b['mapping']['groups']['site_alias']=a['mapping']['groups']['site_alias']
        c['mapping']['groups']['logger_alias']=b['mapping']['groups']['logger_alias']
        for e in (b,c): e['observations']['groups']=copy.deepcopy(e['mapping']['groups'])
        r=self.run_build(); self.assertEqual(len(r['dependency_components']),1)
        self.assertEqual(r['dependency_conflicts'][0]['splits'],['test','train','validation'])

    def test_reused_raw_sample_ids_cannot_cross_splits(self):
        self.b['entries'][2]['raw']['readings'][0]['id']=self.b['entries'][0]['raw']['readings'][0]['id']
        r=self.run_build(); self.assertTrue(r['dependency_conflicts'])
        self.assertFalse(r['ready_for_engineering_experiment'])

    def test_source_owner_season_and_raw_pin_mismatch_fail(self):
        for mode in ('source','owner','season','pin','rights'):
            self.b=copy.deepcopy(self.base); e=self.one()
            if mode=='source': e['raw']['metadata']['source']='field_observed'; e['raw']['metadata_sha256']=digest(e['raw']['metadata'])
            elif mode=='owner': e['mapping']['owner_id']=str(uuid4())
            elif mode=='season': e['mapping']['season_id']=str(uuid4())
            elif mode=='rights': e['mapping']['use_rights_status']='unknown'
            if mode=='pin':
                e['mapping']['raw_bundle_sha256']='bad'
                with self.assertRaises(ValueError): build(seal(self.b))
            else:
                with self.subTest(mode=mode),self.assertRaises(ValueError): self.run_build()

    def test_duplicate_mapping_and_duplicate_unit_issue_are_rejected(self):
        for new_id in (False,True):
            self.b=copy.deepcopy(self.base); e=copy.deepcopy(self.b['entries'][0])
            if new_id: e['id']=str(uuid4())
            self.b['entries'].append(e); self.b['split_plan']['assignments'][e['id']]='train'
            with self.assertRaises(ValueError): self.run_build()

    def test_future_context_and_exclusion_do_not_change_features_or_evidence(self):
        e=self.one(); before=self.run_build()['rows'][0]; issue=stamp(e['issue_times'][0])
        context=copy.deepcopy(e['context_revisions'][0]); context.update(revision=2,
            recorded_at=(issue+timedelta(hours=1)).isoformat(),available_at=(issue+timedelta(hours=1)).isoformat())
        context['profile']['sown_on']='2026-08-02'; e['context_revisions'].append(context)
        row=e['raw']['readings'][0]; row.update(excluded_at=(issue+timedelta(hours=2)).isoformat(),
            exclusion_reason='Future simulated QC',exclusion_request_id=str(uuid4()))
        after=self.run_build()['rows'][0]
        self.assertEqual(before['predictors_sha256'],after['predictors_sha256'])
        self.assertEqual(before['feature_evidence_sha256'],after['feature_evidence_sha256'])
        self.assertEqual(after['context_revision'],1)

    def test_late_raw_receipts_leave_missing_features_even_with_mature_labels(self):
        e=self.one(); issue=stamp(e['issue_times'][0])
        for row in e['raw']['readings'][:6]:
            row['received_at']=row['available_at']=(issue+timedelta(hours=2)).isoformat()
        r=self.run_build()['rows'][0]
        self.assertEqual(r['feature_status'],'insufficient_data'); self.assertIsNone(r['predictors'])
        self.assertEqual(r['synthetic_y'],0); self.assertFalse(r['engineering_eligible'])

    def test_late_mapping_and_unknown_calendar_age_are_explicit_exclusions(self):
        e=self.one(); e['mapping']['relationship_available_at']=(stamp(e['issue_times'][0])+timedelta(seconds=1)).isoformat()
        e['context_revisions'][0]['profile'].update(planting_method='unknown',sown_on=None)
        r=self.run_build()['rows'][0]
        self.assertIn('relationship_not_available_at_issue',r['reasons'])
        self.assertIn('features_insufficient_as_of_issue',r['reasons'])

    def test_label_cutoff_changes_outcome_without_changing_predictors(self):
        e=self.one(); issue=stamp(e['issue_times'][0]); v=copy.deepcopy(e['observations']['visits'][2])
        v.update(revision=2,finding='present',recorded_at=(issue+timedelta(hours=100)).isoformat(),
                 available_at=(issue+timedelta(hours=100)).isoformat())
        v['review']['reviewed_at']=v['available_at']; v.pop('payload_sha256'); v['payload_sha256']=digest(v)
        e['observations']['visits'].append(v)
        self.b['split_plan']['periods']['train']['label_cutoff']=(issue+timedelta(hours=96)).isoformat()
        old=self.run_build()['rows'][0]
        self.b['split_plan']['periods']['train']['label_cutoff']=(issue+timedelta(hours=120)).isoformat()
        new=self.run_build()['rows'][0]
        self.assertEqual((old['synthetic_y'],new['synthetic_y']),(0,1))
        self.assertEqual(old['predictors_sha256'],new['predictors_sha256'])
        self.assertEqual(old['feature_evidence_sha256'],new['feature_evidence_sha256'])

    def test_unmature_endpoint_and_outside_period_are_not_eligible(self):
        e=self.one(); issue=stamp(e['issue_times'][0])
        self.b['split_plan']['periods']['train']['label_cutoff']=(issue+timedelta(hours=48)).isoformat()
        self.b['split_plan']['periods']['train']['start_at']=(issue+timedelta(hours=1)).isoformat()
        r=self.run_build()['rows'][0]
        self.assertEqual(r['endpoint_status'],'following_up')
        self.assertIn('issue_outside_split_period',r['reasons']); self.assertFalse(r['engineering_eligible'])

    def test_plan_label_maturity_order_and_lock_guards(self):
        for mode in ('labels_after_next_issue','after_lock','plan_unknown','unknown_assignment','snapshot_linked_before_export'):
            self.b=copy.deepcopy(self.base); p=self.b['split_plan']
            if mode=='labels_after_next_issue': p['periods']['train']['label_cutoff']=p['periods']['validation']['start_at']
            elif mode=='after_lock': p['data_lock_at']='2026-09-02T00:00:00Z'
            elif mode=='plan_unknown': p['available_at']='2026-09-02T00:00:00Z'
            elif mode=='unknown_assignment': p['assignments'][self.b['entries'][0]['id']]='other'
            else: self.b['entries'][0]['mapping']['snapshot_linked_at']=self.b['entries'][0]['mapping']['relationship_available_at']
            with self.subTest(mode=mode),self.assertRaises(ValueError): self.run_build()

    def test_purge_support_overlap_even_when_groups_are_distinct(self):
        # Move the train issues +5 days while keeping the later periods fixed.
        # Their targets now overlap validation's 120h feature history.
        p=self.b['split_plan']; delta=timedelta(days=5)
        for e in self.b['entries'][:2]:
            e['issue_times']=[(stamp(t)+delta).isoformat() for t in e['issue_times']]
            # Existing raw ends too early: extend using a translated copy of the source.
            for r in e['raw']['readings']:
                for k in ('observed_at','received_at','available_at'): r[k]=(stamp(r[k])+delta).isoformat()
            for k in ('anchor_at',): e['hourly_policy'][k]=(stamp(e['hourly_policy'][k])+delta).isoformat()
            for v in e['observations']['visits']:
                for k in ('observed_at','recorded_at','available_at'): v[k]=(stamp(v[k])+delta).isoformat()
                if v['review']: v['review']['reviewed_at']=(stamp(v['review']['reviewed_at'])+delta).isoformat()
                v.pop('payload_sha256'); v['payload_sha256']=digest(v)
            e['observations']['exported_at']=(stamp(e['observations']['exported_at'])+delta).isoformat()
        for k in ('start_at','end_at','label_cutoff'):
            p['periods']['train'][k]=(stamp(p['periods']['train'][k])+delta).isoformat()
        # Train cutoff Sep11 still precedes validation Sep12.
        r=self.run_build(); self.assertFalse(r['dependency_conflicts'])
        self.assertEqual(r['exclusion_counts']['purged_feature_target_support_overlap'],2)
        self.assertEqual(r['split_counts']['train']['rows'],0)

    def test_missing_split_and_single_class_never_claim_engineering_readiness(self):
        self.one(); r=self.run_build(); self.assertFalse(r['ready_for_engineering_experiment'])
        self.assertEqual(r['split_counts']['train']['class_counts'],{'0':1,'1':0})

    def test_input_immutability_and_repeatability(self):
        before=copy.deepcopy(self.b); a=build(self.b); b=build(self.b)
        self.assertEqual(self.b,before); self.assertEqual(a,b)


if __name__=='__main__': unittest.main()
