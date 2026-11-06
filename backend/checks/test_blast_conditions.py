"""Independent acceptance scenarios for the experimental mock profile."""
import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.blast_conditions import evaluate, PROFILE

def fixture(hours=0):
    end=datetime(2026,10,24,tzinfo=timezone.utc)
    rows=[]
    for i in range(24):
        wet=i < hours
        rows.append(dict(start_at=(end-timedelta(hours=24-i)).isoformat(),air_temperature_c=26,
                         relative_humidity_pct=95 if wet else 70,leaf_wet=wet))
    return dict(source='mock',as_of=end.isoformat(),records=rows)

class BlastConditionsTests(unittest.TestCase):
    def test_six_hours_triggers_but_five_does_not(self):
        self.assertEqual(evaluate(fixture(6))['status'],'advisory')
        self.assertEqual(evaluate(fixture(5))['status'],'no_pattern_detected')
    def test_interrupted_hours_are_not_summed(self):
        p=fixture(12)
        for i in [3,7,11]:p['records'][i]['leaf_wet']=False
        self.assertEqual(evaluate(p)['longest_matching_run_hours'],3)
        self.assertEqual(evaluate(p)['status'],'no_pattern_detected')
    def test_missing_and_empty_never_become_low_risk(self):
        for rows in [[],fixture(24)['records'][1:],fixture(24)['records'][:-1]]:
            p=fixture();p['records']=rows
            self.assertEqual(evaluate(p)['status'],'insufficient_data')
    def test_high_humidity_cannot_replace_leaf_wetness(self):
        p=fixture(24)
        for r in p['records']:r['leaf_wet']=False
        self.assertEqual(evaluate(p)['status'],'no_pattern_detected')
        del p['records'][0]['leaf_wet']
        with self.assertRaises(ValueError):evaluate(p)
    def test_boundaries_and_no_broader_biological_claim(self):
        for temp,rh,expected in [(25,95,'advisory'),(PROFILE['temperature_max_c'],95,'advisory'),
                                  (24.99,95,'no_pattern_detected'),(28,95,'no_pattern_detected'),(26,90,'no_pattern_detected')]:
            p=fixture(24)
            for r in p['records']:r.update(air_temperature_c=temp,relative_humidity_pct=rh)
            self.assertEqual(evaluate(p)['status'],expected)
    def test_duplicate_future_old_and_unzoned_rejected(self):
        for kind in ['duplicate','future','old','unzoned']:
            p=fixture()
            p['records'][0]['start_at']={'duplicate':p['records'][1]['start_at'],'future':p['as_of'],
                                        'old':'2026-10-22T00:00:00+00:00','unzoned':'2026-10-23T00:00:00'}[kind]
            with self.subTest(kind=kind),self.assertRaises(ValueError):evaluate(p)
    def test_invalid_numbers_and_types_rejected(self):
        for key,value in [('air_temperature_c',float('nan')),('air_temperature_c',True),
                          ('relative_humidity_pct',101),('relative_humidity_pct',float('inf')),('leaf_wet',1)]:
            p=fixture();p['records'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):evaluate(p)
    def test_real_observations_not_accepted_by_mock_profile(self):
        p=fixture();p['source']='sensor'
        with self.assertRaises(ValueError):evaluate(p)
    def test_order_independent_decision_and_no_input_mutation(self):
        p=fixture(6);original=copy.deepcopy(p);a=evaluate(p)
        self.assertEqual(p,original)
        p['records'].reverse();b=evaluate(p)
        self.assertEqual(a['status'],b['status']);self.assertEqual(a['profile_sha256'],b['profile_sha256'])
    def test_output_is_explicitly_unvalidated_and_not_a_forecast(self):
        r=evaluate(fixture(6))
        self.assertTrue(r['is_mock']);self.assertFalse(r['field_validated'])
        self.assertIsNone(r['forecast_horizon_hours']);self.assertNotIn('probability',r)

if __name__=='__main__':unittest.main()
