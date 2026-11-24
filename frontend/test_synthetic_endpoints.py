"""T15 observation rules, maturity and revision knowledge acceptance."""
import copy
from datetime import timedelta
import unittest
from uuid import uuid4

from endpoint_simulation import make,seal,ISSUE,EXPORT,SCENARIOS,journal_commands
from synthetic_endpoints import evaluate,validate,PROTOCOL_SHA256
from telemetry_tool import digest


def reseal(b):
    b.pop('bundle_sha256',None); b['bundle_sha256']=digest(b)
    return b


def result(b,hours=120): return evaluate(b,ISSUE.isoformat(),(ISSUE+timedelta(hours=hours)).isoformat())


class SyntheticEndpointTests(unittest.TestCase):
    def test_scenario_statuses_and_binary_scope_three_seeds(self):
        expected=dict(positive='positive',negative='negative',uncertain='uncertain',missed_visit='censored',
            late_review='positive',prevalent='prevalent',ambiguous_issue='ambiguous',ambiguous_end='ambiguous',
            intervened='intervened',unverified='unverified',voided='censored',revision_correction='negative',
            baseline_late='baseline_unavailable_at_issue',missing_baseline='censored',late_intervention='intervened')
        for seed in (20261108,20261109,20261110):
            for scenario in SCENARIOS:
                with self.subTest(seed=seed,scenario=scenario):
                    r=result(make(seed,scenario)); self.assertEqual(r['status'],expected[scenario])
                    self.assertEqual(r['synthetic_y'],1 if scenario in ('positive','late_review') else
                                     0 if scenario in ('negative','revision_correction') else None)
                    self.assertIsNone(r['event_y']); self.assertFalse(r['training_approved'])
                    self.assertFalse(r['platform_verified']); self.assertFalse(r['label_approved_for_training'])

    def test_maturity_and_exact_horizon_receipt_are_separate(self):
        b=make(1,'positive')
        self.assertEqual(result(b,71)['status'],'following_up')
        self.assertEqual(result(b,72)['synthetic_y'],1)
        b=make(1,'negative'); r=result(b,72)
        self.assertIsNone(r['synthetic_y']); self.assertEqual(r['status'],'censored')
        self.assertEqual(result(b,73)['synthetic_y'],0)
        self.assertGreater(result(b,73)['synthetic_endpoint_available_at'],(ISSUE+timedelta(hours=72)).isoformat())

    def test_no_visits_is_censored_not_negative(self):
        b=make(1,'negative'); b['visits']=[]; reseal(b)
        self.assertEqual(result(b)['status'],'censored'); self.assertIsNone(result(b)['synthetic_y'])

    def test_late_review_is_not_visible_in_old_cutoff(self):
        b=make(2,'late_review'); early=result(b,96); late=result(b,120)
        self.assertEqual(early['status'],'unverified'); self.assertEqual(late['synthetic_y'],1)
        self.assertTrue(all(r['revision']==1 for r in early['selected_revisions']))
        self.assertEqual(late['synthetic_endpoint_available_at'],(ISSUE+timedelta(hours=100)).isoformat())

    def test_future_revision_preserves_earlier_knowledge_hash_and_result(self):
        b=make(3,'revision_correction'); before=copy.deepcopy(b); before['visits']=before['visits'][:-1]; reseal(before)
        old=result(b,96); previous=result(before,96)
        self.assertEqual(old['synthetic_y'],1); self.assertEqual(result(b)['synthetic_y'],0)
        self.assertEqual(old['knowledge_sha256'],previous['knowledge_sha256'])
        self.assertEqual(old['selected_revisions'],previous['selected_revisions'])
        self.assertNotEqual(old['input_bundle_sha256'],previous['input_bundle_sha256'])

    def test_void_and_late_intervention_revise_known_state_only_after_available(self):
        for scenario in ('voided','late_intervention'):
            b=make(1,scenario)
            self.assertEqual(result(b,96)['synthetic_y'],0)
            self.assertIsNone(result(b,120)['synthetic_y'])
        self.assertEqual(result(make(1,'late_intervention'))['status'],'intervened')

    def test_interval_boundaries_and_horizon_equality(self):
        r=result(make(1,'ambiguous_issue')); self.assertTrue(r['observed_event_interval']['crosses_issue'])
        r=result(make(1,'ambiguous_end')); self.assertTrue(r['observed_event_interval']['crosses_target_end'])
        b=make(1,'negative'); b['visits'][-1]['finding']='present'; seal(b['visits'][-1]); reseal(b)
        r=result(b); self.assertEqual(r['synthetic_y'],1)
        self.assertEqual(r['observed_event_interval']['upper_closed'],(ISSUE+timedelta(hours=72)).isoformat())
        self.assertEqual(result(make(1,'prevalent'))['status'],'prevalent')

    def test_positive_after_horizon_with_complete_absence_does_not_delay_negative(self):
        b=make(1,'ambiguous_end'); extra=make(1,'negative')['visits'][-1]
        b['visits'].append(extra); reseal(b); r=result(b)
        self.assertEqual(r['synthetic_y'],0)
        self.assertLess(r['synthetic_endpoint_available_at'],(ISSUE+timedelta(hours=73)).isoformat())

    def test_missing_scheduled_visit_even_with_ad_hoc_visit_stays_censored(self):
        b=make(1,'missed_visit'); row=copy.deepcopy(b['visits'][1]); row['id']=str(uuid4())
        row.update(observed_at=(ISSUE+timedelta(hours=23)).isoformat(),recorded_at=(ISSUE+timedelta(hours=23)).isoformat(),
                   available_at=(ISSUE+timedelta(hours=23)).isoformat(),scheduled=False,review=None)
        seal(row); b['visits'].append(row); reseal(b)
        self.assertIsNone(result(b)['synthetic_y'])

    def test_unattested_baseline_present_is_not_silent_negative(self):
        b=make(1,'negative'); b['visits'][0].update(finding='present',review=None); seal(b['visits'][0]); reseal(b)
        self.assertEqual(result(b)['status'],'unverified')

    def test_protocol_source_and_prediction_fields_rejected(self):
        for key,value in (('source','field_observed'),('source','controlled_experiment'),('protocol_sha256','bad'),
                          ('score',.9),('image_prediction','blast'),('evidence_origin','journal_external_review')):
            b=make(1,'negative'); b[key]=value; reseal(b)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): result(b)
            with self.assertRaises(ValueError): journal_commands(b)

    def test_corruption_and_invalid_review_provenance_rejected(self):
        b=make(1,'negative'); b['visits'][0]['finding']='present'
        with self.assertRaises(ValueError): result(b)
        for origin in ('user_reported_external_review','model_prediction'):
            b=make(1,'negative'); b['visits'][0]['review']['origin']=origin; seal(b['visits'][0]); reseal(b)
            with self.assertRaises(ValueError): result(b)

    def test_revision_history_is_full_and_times_and_identity_immutable(self):
        for mode in ('missing_first','duplicate','changed_time','backdated_revision'):
            b=make(1,'late_review')
            if mode=='missing_first': b['visits']=[r for r in b['visits'] if not (r['id']==b['visits'][-1]['id'] and r['revision']==1)]
            elif mode=='duplicate': b['visits'].append(copy.deepcopy(b['visits'][0]))
            elif mode=='changed_time': b['visits'][-1]['observed_at']=(ISSUE+timedelta(hours=49)).isoformat(); seal(b['visits'][-1])
            else: b['visits'][-1]['recorded_at']=b['visits'][-1]['available_at']=(ISSUE+timedelta(hours=48)).isoformat(); seal(b['visits'][-1])
            reseal(b)
            with self.subTest(mode=mode),self.assertRaises(ValueError): result(b)

    def test_bad_availability_timezone_and_future_cutoff_rejected(self):
        for value in ('2026-11-01T00:00:00', '2026-10-31T00:00:00Z'):
            b=make(1,'negative'); b['visits'][1]['available_at']=value; seal(b['visits'][1]); reseal(b)
            with self.assertRaises(ValueError): result(b)
        with self.assertRaises(ValueError): result(make(1,'negative'),145)
        self.assertEqual(result(make(1,'negative'),-1)['status'],'not_yet_issued')

    def test_generation_repeat_input_unchanged_and_journal_does_not_gain_review(self):
        for scenario in SCENARIOS:
            b=make(1,scenario); before=copy.deepcopy(b); result(b)
            self.assertEqual(b,before); self.assertEqual(b,make(1,scenario))
            for command in journal_commands(b):
                self.assertIsNone(command['review']); self.assertEqual(command['source'],'synthetic')


if __name__=='__main__': unittest.main()
