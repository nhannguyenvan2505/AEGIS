"""Run existing pilot HTTP acceptance scenarios on disposable MySQL schemas.

Fixtures keep their API payloads and assertions; only the factory is redirected.
Cases that explicitly inspect SQLite files are intentionally not in this suite.
"""
import importlib
import argparse
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'backend'/'checks'));sys.path.insert(0,str(ROOT/'frontend'))
from test_mysql_core import MySQLCoreTests,DATABASE
from pilot_app import create_pilot_app as real_factory
from app.hybrid_pilot import REGISTERED

CASES=[
 ('test_journal','JournalTests','test_external_review_is_revision_not_platform_verification'),
 ('test_followup','FollowupTests','test_full_lifecycle_retry_reopen_and_no_disease_label'),
 ('test_telemetry','TelemetryTests','test_metadata_retry_conflict_and_source_never_guessed'),
 ('test_pilot_hourly','PilotHourlyTests','test_owner_auth_private_and_pagination_all_routes'),
 ('test_pilot_hourly','PilotHourlyTests','test_concurrent_policy_update_has_one_revision'),
 ('test_weather_integration','WeatherIntegrationTests','test_manual_and_scheduler_share_ready_forecast_and_new_pin'),
 ('test_forecast_alerts','ForecastAlertTests','test_insufficient_creates_data_quality_only_and_replays_once'),
 ('test_forecast_history','ForecastHistoryTests','test_issue_order_filters_precision_pagination_and_model_series'),
 ('test_assessment_versions','VersionTests','test_progressive_versions_retry_dedup_and_latest_requirement_same_window'),
 ('test_episodes','EpisodeTests','test_successive_hours_group_and_manual_lookup_preserve_snapshots'),
]


def generated(module_name,class_name,method_name):
    module=importlib.import_module(module_name);original=getattr(module,class_name)
    if not hasattr(original,method_name): raise ValueError('Unknown acceptance case '+method_name)
    class Acceptance(MySQLCoreTests):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            cls.addClassCleanup(original.doClassCleanups)
            original.setUpClass()
        def setUp(self):
            def factory(storage,*args,**kwargs):
                kwargs.update(storage_backend='mysql',config=dict(TESTING=True,MYSQL=self.mysql))
                return real_factory(storage,*args,**kwargs)
            # Patch existing module aliases as well as the lazy import in server.py.
            for target in list(sys.modules.values()):
                if target and getattr(target,'create_pilot_app',None) is real_factory:
                    item=patch.object(target,'create_pilot_app',side_effect=factory)
                    item.start();self.addCleanup(item.stop)
            if hasattr(original,'counts'):
                def counts(case):
                    from app.storage import connect
                    from pilot_journal import journal_db
                    with connect(case.app.config) as core:
                        assessments=core.execute('SELECT COUNT(*) FROM farm_assessments').fetchone()[0]
                    with journal_db(case.root/'followup.sqlite3') as workflow:
                        workflows=workflow.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
                    return assessments,workflows
                item=patch.object(original,'counts',new=counts)
                item.start();self.addCleanup(item.stop)
        def test_existing_http_scenario(self):
            case=original(method_name)
            result=unittest.TestResult();case.run(result)
            if not result.wasSuccessful():
                details='\n'.join(trace for _,trace in result.errors+result.failures)
                self.fail(module_name+'.'+method_name+'\n'+details)
            if result.skipped: self.skipTest(str(result.skipped))
    Acceptance.__name__='MySQL_'+module_name+'_'+method_name
    Acceptance.scenario=module_name+'.'+method_name
    return Acceptance('test_existing_http_scenario')


def main():
    if os.environ.get('AEGIS_RUN_MYSQL_TESTS')!='1': raise RuntimeError('Set AEGIS_RUN_MYSQL_TESTS=1 explicitly')
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='');args=parser.parse_args()
    selected=[case for case in CASES if args.case in '.'.join(case)]
    if not selected: parser.error('No matching acceptance case')
    path=DATABASE/'pilot_acceptance_report.json'
    records=json.loads(path.read_text()) if path.exists() else {}
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):
            records[test.scenario]='passed';super().addSuccess(test)
        def addFailure(self,test,error):
            records[test.scenario]='failed';super().addFailure(test,error)
        def addError(self,test,error):
            records[test.scenario]='error';super().addError(test,error)
    suite=unittest.TestSuite(generated(*case) for case in selected)
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    path.write_text(json.dumps(records,indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())


if __name__=='__main__': main()
