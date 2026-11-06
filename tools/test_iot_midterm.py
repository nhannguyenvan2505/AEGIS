"""Failure propagation tests only; HTTP/process success is checked by the real run."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import rehearse_iot_midterm as midterm


class MidtermFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)/'new-run'

    def invoke(self):
        with patch.object(sys, 'argv', ['rehearse_iot_midterm.py', '--out', str(self.out)]), redirect_stdout(io.StringIO()):
            return midterm.main()

    def assert_failure_only(self, stage):
        result = json.loads((self.out/'summary.json').read_text(encoding='utf-8'))
        self.assertFalse(result['success'])
        self.assertEqual(result['stage'], stage)
        self.assertTrue((self.out/'DEMO_FAILED.md').is_file())
        self.assertFalse((self.out/'DEMO_REPORT.md').exists())
        return result

    def test_http_failure_blocks_later_steps_and_pass_report(self):
        with (patch.object(midterm.http_rehearsal, 'run', side_effect=RuntimeError('private fixture message')),
                patch.object(midterm.crash_rehearsal, 'run') as crash):
            self.assertEqual(self.invoke(), 1)
            crash.assert_not_called()
        result = self.assert_failure_only('http')
        self.assertEqual(result['failure_type'], 'RuntimeError')
        self.assertNotIn('private fixture message', json.dumps(result))

    def test_http_cleanup_failure_is_not_success(self):
        failed_cleanup = dict(success=True, temporary_store_cleaned=False,
                              backend_stopped=True, forced_stop=False)
        with (patch.object(midterm.http_rehearsal, 'run', return_value=failed_cleanup),
                patch.object(midterm.crash_rehearsal, 'run') as crash):
            self.assertEqual(self.invoke(), 1)
            crash.assert_not_called()
        result = self.assert_failure_only('http')
        self.assertEqual(result['failed_check'], 'http_succeeded_and_cleaned')

    def test_crash_stage_failure_keeps_partial_evidence_but_no_pass(self):
        http = dict(success=True, temporary_store_cleaned=True, backend_stopped=True,
            forced_stop=False, streams=2, persisted_unique_samples=6, checks_passed=37,
            checks=['tcp_closed_before_ack_keeps_outbox'])

        def fail_crash(out, lifecycle):
            lifecycle.update(backend_stopped=True, temporary_store_cleaned=True, forced_stop=False)
            raise RuntimeError('Acceptance failed: injected_crash_fixture_failure')

        with (patch.object(midterm.http_rehearsal, 'run', return_value=http),
                patch.object(midterm.crash_rehearsal, 'run', side_effect=fail_crash)):
            self.assertEqual(self.invoke(), 1)
        result = self.assert_failure_only('sender_crash')
        self.assertTrue(result['components']['http']['success'])
        self.assertTrue(result['sender_crash_lifecycle']['temporary_store_cleaned'])
        self.assertEqual(result['failed_check'], 'injected_crash_fixture_failure')

    def test_existing_output_is_refused_without_running_any_stage(self):
        self.out.mkdir(); sentinel = self.out/'keep.txt'; sentinel.write_text('keep', encoding='utf-8')
        with patch.object(midterm.http_rehearsal, 'run') as http, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                self.invoke()
            self.assertEqual(raised.exception.code, 2)
            http.assert_not_called()
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep')
        self.assertFalse((self.out/'summary.json').exists())


if __name__ == '__main__':
    unittest.main()
