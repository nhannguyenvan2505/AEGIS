"""Diagnosis outcomes are countable from the completion log: no image, no user, no free text."""
import io
import json
import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app

TOOL = Path(__file__).resolve().parents[2] / 'tools' / 'count_diagnosis_outcomes.py'


class OutcomeLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.app = create_app(dict(TESTING=True, DATABASE_PATH=root / 't.db', UPLOAD_DIR=root / 'u', DETECT_USER_LIMIT=100))
        self.client = self.app.test_client(); cred = dict(email='outcome@example.test', password='test-password-123')
        self.client.post('/api/auth/register', json=cred)
        self.headers = {'Authorization': 'Bearer ' + self.client.post('/api/auth/login', json=cred).json['access_token']}

    def tearDown(self):
        self.tmp.cleanup()

    def detect(self, body, key=None):
        """POST one image; return the response and the completion log event it produced."""
        def upstream(*args, **kwargs):
            return Mock(status_code=200, json=lambda: {**body, 'request_id': kwargs['headers']['X-Request-ID']})
        headers = dict(self.headers, **({'Idempotency-Key': key} if key else {}))
        with patch('app.ai_service.requests.post', side_effect=upstream), self.assertLogs(self.app.logger, logging.INFO) as logs:
            response = self.client.post('/api/disease/detect', headers=headers,
                                        data={'image': (io.BytesIO(b'synthetic'), 'secret-name.png')})
        events = [json.loads(record.getMessage()) for record in logs.records
                  if record.getMessage().startswith('{') and 'request_completed' in record.getMessage()]
        self.assertEqual(len(events), 1)
        return response, events[0]

    @staticmethod
    def rejected(status, is_rice=None, **extra):
        return dict(dict(status=status, is_rice=is_rice, message='x', model_sha256='a' * 64, model_version='m',
                         detections=[]), **extra)

    @staticmethod
    def accepted(status):
        return dict(status=status, is_rice=True, message='m', model_sha256='d' * 64, model_version='m',
                    processing_ms=1, image=dict(width=32, height=32), detections=[])

    def test_each_rejection_logs_its_reason(self):
        for status, is_rice in [('rejected_non_rice', False), ('rejected_uncertain_scope', None)]:
            _, event = self.detect(self.rejected(status, is_rice))
            self.assertEqual(event.get('diagnosis_status'), status)
            self.assertNotIn('quality_issues', event)

    def test_poor_quality_logs_only_known_issue_codes(self):
        quality = dict(ok=False, issues=['blur', 'too_dark', 'free text from upstream', 7], metrics={'mean_luminance': 3})
        _, event = self.detect(self.rejected('rejected_poor_quality', quality=quality))
        self.assertEqual((event.get('diagnosis_status'), event.get('quality_issues')),
                         ('rejected_poor_quality', ['blur', 'too_dark']))
        for broken in (None, 'blur', dict(issues='blur'), dict(issues=None)):
            _, event = self.detect(self.rejected('rejected_poor_quality', quality=broken))
            self.assertEqual(event.get('quality_issues'), [], broken)

    def test_accepted_results_log_their_diagnosis_once_even_when_replayed(self):
        response, event = self.detect(self.accepted('healthy'), key='once')
        self.assertEqual((response.status_code, event.get('diagnosis_status')), (200, 'healthy'))
        replayed, event = self.detect(self.accepted('healthy'), key='once')
        self.assertEqual(replayed.headers.get('Idempotency-Replayed'), 'true')
        self.assertNotIn('diagnosis_status', event)

    def test_the_event_carries_no_upload_or_account_detail(self):
        _, event = self.detect(self.rejected('rejected_non_rice', False))
        text = json.dumps(event)
        for secret in ('secret-name', 'outcome@example.test', 'synthetic'):
            self.assertNotIn(secret, text)


class CountToolTests(unittest.TestCase):
    def line(self, **fields):
        event = dict(dict(event='request_completed', service='aegis-backend', status=200), **fields)
        # the prefix Flask's default log handler puts in front of the message
        return '[2026-11-25 21:00:00,000] INFO in observability: ' + json.dumps(event)

    def run_tool(self, lines):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'backend.log'
            log.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            done = subprocess.run([sys.executable, str(TOOL), str(log)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_counts_outcomes_and_quality_reasons_and_skips_other_lines(self):
        report = self.run_tool([
            self.line(diagnosis_status='disease_detected'),
            self.line(diagnosis_status='rejected_non_rice'),
            self.line(diagnosis_status='rejected_poor_quality', quality_issues=['blur', 'too_dark']),
            self.line(diagnosis_status='rejected_poor_quality', quality_issues=['blur']),
            self.line(ai_error_code='ai_busy', status=503),
            self.line(),  # an ordinary request
            self.line(diagnosis_status='healthy', service='aegis-ai'),
            'Traceback (most recent call last):', '{"event": broken', '',
        ])
        self.assertEqual(report['diagnoses'], 4)
        self.assertEqual(report['by_status'], {'disease_detected': 1, 'rejected_non_rice': 1, 'rejected_poor_quality': 2})
        self.assertEqual((report['rejected'], report['rejected_share']), (3, 0.75))
        self.assertEqual(report['quality_issues'], {'blur': 2, 'too_dark': 1})
        self.assertEqual(report['ai_errors'], {'ai_busy': 1})

    def test_events_broken_by_a_console_redirect_are_not_silently_dropped(self):
        # Windows PowerShell 5.1 "*>" wraps long stderr lines, cutting the JSON apart.
        whole = self.line(diagnosis_status='healthy')
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'backend.log'
            log.write_text('python.exe : ' + whole[:90] + '\n' + whole[90:] + '\n' + whole + '\n', encoding='utf-8')
            done = subprocess.run([sys.executable, str(TOOL), str(log)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual((json.loads(done.stdout)['diagnoses'], json.loads(done.stdout)['unreadable_events']), (1, 1))
        self.assertIn('incomplete', done.stderr)

    def test_utf16_and_byte_order_marked_logs_are_read(self):
        for encoding in ('utf-16', 'utf-8-sig'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as directory:
                log = Path(directory) / 'backend.log'
                log.write_text(self.line(diagnosis_status='healthy') + '\n', encoding=encoding)
                done = subprocess.run([sys.executable, str(TOOL), str(log)], capture_output=True, text=True, encoding='utf-8')
                self.assertEqual((done.returncode, json.loads(done.stdout)['diagnoses']), (0, 1), done.stderr)

    def test_an_empty_log_reports_zero_without_a_share(self):
        report = self.run_tool(['nothing here'])
        self.assertEqual((report['diagnoses'], report['rejected_share']), (0, None))


if __name__ == '__main__':
    unittest.main()
