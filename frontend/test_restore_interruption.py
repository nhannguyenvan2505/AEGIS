"""H5-T03: real process exit immediately before clearing restore sentinel.

Only owned temporary seven-DB fixtures. No production hooks or recovery changes.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'backend'))
import pilot_backup
from pilot_backup import backup,verify,inventory,audit_data,digest
from pilot_store import MARKER,KIND,StoreLease,validate_storage

TRACES=[]
EXIT_AT_BOUNDARY=77

def worker(mode,bundle,target,signal):
    """Private child modes, limited to direct system-temp fixture roots."""
    target=Path(target).absolute();signal=Path(signal).absolute()
    if target.parent!=Path(tempfile.gettempdir()).resolve() or not target.name.startswith('aegis_ui_'):
        raise ValueError('Worker accepts only owned disposable temp roots')
    if mode=='crash':
        original=Path.unlink
        def unlink(path,*args,**kwargs):
            if path==target/'.restore-incomplete':
                signal.write_text(json.dumps(dict(
                    boundary='restore_verified_before_sentinel_unlink',
                    sentinel_present=path.is_file(),pilot_marker_present=(target/MARKER).is_file(),
                    all_restore_checks_returned=True)),encoding='utf-8')
                # Actual child termination, with no Python cleanup/finally handlers.
                os._exit(EXIT_AT_BOUNDARY)
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',unlink):pilot_backup.restore(Path(bundle),target)
        raise AssertionError('Expected crash boundary was not reached')
    elif mode=='probe':
        from pilot_app import create_pilot_app
        from server import build_app
        probes={
            'validate_storage':lambda:validate_storage(target),
            'server_lease':lambda:StoreLease(target),
            'automation_lease':lambda:StoreLease(target,'.automation.lock'),
            'api_factory':lambda:create_pilot_app(target,'http://127.0.0.1:9'),
            'reference_ui_factory':lambda:build_app(target,'http://127.0.0.1:9',{'kind':'test'})}
        denied=[]
        for name,call in probes.items():
            try:call()
            except ValueError as exc:
                if str(exc)!='Incomplete restore; do not open this store':raise
                denied.append(name)
            else:raise AssertionError('Incomplete store opened: '+name)
        signal.write_text(json.dumps(dict(blocked=denied)),encoding='utf-8')
    else:raise ValueError('Unknown child mode')


class RestoreInterruptionTests(unittest.TestCase):
    def setUp(self):
        from test_pilot_backup import rich_fixture
        self.f=rich_fixture(self);self.f.runner.stop()
        self.temp=tempfile.TemporaryDirectory(prefix='aegis_ui_restore_boundary_artifacts_')
        self.addCleanup(self.temp.cleanup);self.artifacts=Path(self.temp.name)
        self.bundle=self.artifacts/'backup';self.original=inventory(self.f.root)
        self.manifest=backup(self.f.root,self.bundle)
        self.backup_before=inventory(self.bundle)

    def child(self,mode,target,signal):
        return subprocess.run([sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),
            '--worker',mode,str(self.bundle),str(target),str(signal)],
            cwd=self.artifacts,capture_output=True,text=True,timeout=30)

    def cli(self,target):
        return subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'pilot_backup.py'),
            'restore','--bundle',str(self.bundle),'--destination',str(target)],
            cwd=self.artifacts,capture_output=True,text=True,timeout=30)

    def assert_preserved(self):
        self.assertEqual(inventory(self.f.root),self.original)
        self.assertEqual(inventory(self.bundle),self.backup_before)
        self.assertEqual(verify(self.bundle),self.manifest)

    def assert_open_without_worker_or_duplicates(self,target):
        from pilot_app import create_pilot_app
        self.assertEqual(inventory(target),self.original)
        self.assertEqual(audit_data(target),self.manifest['database_checks'])
        with ExitStack() as stack:
            stack.enter_context(StoreLease(target));stack.enter_context(StoreLease(target,'.automation.lock'))
            for lock in ['.server.lock','.automation.lock']:
                with self.assertRaises(RuntimeError):
                    with StoreLease(target,lock):pass
        app=create_pilot_app(target,'http://127.0.0.1:9');runner=app.extensions['mock_automation']
        self.addCleanup(runner.stop)
        self.assertFalse(runner.enabled);self.assertIsNone(runner.thread)
        client=app.test_client();ids=self.f.backup_ids
        response=client.get('/api/mobile/capabilities',headers=self.f.headers[0])
        self.assertEqual(response.status_code,200);self.assertFalse(response.json['mock_automation_process_enabled'])
        self.assertFalse(response.json['controlled_experiment_raw_write'])
        response=client.get('/api/farm/assessments/'+ids['assessment_id']+'/versions',headers=self.f.headers[0])
        self.assertEqual(response.status_code,200);self.assertEqual([r['revision'] for r in response.json['items']],[3,2,1])
        observation=client.get('/api/farm/observations/'+ids['visit_id'],headers=self.f.headers[0])
        self.assertEqual(observation.status_code,200);self.assertEqual(observation.json['item']['revision'],2)
        self.assertEqual(client.get('/api/farm/observations/'+ids['visit_id'],headers=self.f.headers[1]).status_code,404)
        events=client.get('/api/farm/follow-ups/'+ids['case_id']+'/events',headers=self.f.headers[0])
        self.assertEqual(events.status_code,200)
        with client.get('/api/disease/analyses/'+ids['analysis_id']+'/image',headers=self.f.headers[0]) as image:
            self.assertEqual(image.status_code,200)
        self.assertIsNone(runner.thread)
        # Opening/read-only API calls with existing sessions do not create business rows.
        self.assertEqual(audit_data(target),self.manifest['database_checks'])
        self.assertEqual(inventory(target),self.original)
        return dict(worker_running=False,all_seven_database_audits_equal=True,
                    data_inventory_unchanged_after_read=True,assessment_revisions=[3,2,1],observation_revision=2)

    def test_crash_before_sentinel_clear_blocks_restart_and_fresh_restore_recovers(self):
        with tempfile.TemporaryDirectory(prefix='aegis_ui_restore_partial_') as partial_name, \
             tempfile.TemporaryDirectory(prefix='aegis_ui_restore_recovered_') as fresh_name:
            partial=Path(partial_name);fresh=Path(fresh_name)
            signal=self.artifacts/'crash_boundary.json'
            child=self.child('crash',partial,signal)
            self.assertEqual(child.returncode,EXIT_AT_BOUNDARY)
            checkpoint=json.loads(signal.read_text(encoding='utf-8'))
            self.assertTrue(checkpoint['sentinel_present']);self.assertTrue(checkpoint['pilot_marker_present'])
            self.assertEqual(json.loads((partial/MARKER).read_text(encoding='utf-8'))['kind'],KIND)
            partial_before=inventory(partial);copied=json.loads(json.dumps(partial_before))
            copied['files'].pop('.restore-incomplete')
            self.assertEqual(copied,self.original)  # all bytes exist, but opening remains forbidden
            probe_signal=self.artifacts/'restart_probe.json'
            probe=self.child('probe',partial,probe_signal);self.assertEqual(probe.returncode,0)
            denied=json.loads(probe_signal.read_text(encoding='utf-8'))['blocked']
            self.assertEqual(len(denied),5)
            self.assertEqual(inventory(partial),partial_before)
            retry=self.cli(partial);self.assertEqual(retry.returncode,2)
            self.assertIn('Restore target must be new/empty',retry.stderr)
            self.assertEqual(inventory(partial),partial_before)
            recovered=self.cli(fresh);self.assertEqual(recovered.returncode,0)
            self.assertFalse((fresh/'.restore-incomplete').exists())
            opened=self.assert_open_without_worker_or_duplicates(fresh)
            self.assertEqual(inventory(partial),partial_before)
            self.assert_preserved()
            TRACES.append(dict(test=self.id(),child_exit=child.returncode,checkpoint=checkpoint,
                restart_probes_blocked=denied,retry_same_destination_exit=retry.returncode,
                fresh_restore_exit=recovered.returncode,partial_untouched_during_recovery=True,
                source_and_backup_unchanged=True,source_inventory_digest=digest(self.original),
                recovered=opened,real_power_loss_or_disk_failure_tested=False))

    def test_normal_restore_control_clears_sentinel_and_preserves_all_data(self):
        with tempfile.TemporaryDirectory(prefix='aegis_ui_restore_control_') as name:
            target=Path(name);control=self.cli(target)
            self.assertEqual(control.returncode,0);self.assertFalse((target/'.restore-incomplete').exists())
            opened=self.assert_open_without_worker_or_duplicates(target);self.assert_preserved()
            TRACES.append(dict(test=self.id(),restore_exit=control.returncode,
                sentinel_removed=True,source_and_backup_unchanged=True,recovered=opened))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(*sys.argv[2:])
    else:unittest.main()
