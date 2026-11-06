"""H5-T02: commit an observation revision after check read, before event insert.

Two actual HTTP requests, real temporary SQLite stores and an Event barrier;
no production hooks, sleeps, AI, real observations or cross-database atomicity claim.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import queue
import sys
import threading
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.blast_conditions import digest
from pilot_app import create_pilot_app
from pilot_journal import journal_db
import pilot_followup
import test_followup

RACE_TRACES = []


class ObservationDuringCheckTests(unittest.TestCase):
    create = test_followup.FollowupTests.create
    command = test_followup.FollowupTests.command

    def setUp(self):
        test_followup.FollowupTests.setUp(self)
        self.app = create_pilot_app(self.root, 'http://127.0.0.1:9')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.case = self.create()
        self.assertEqual(self.command(self.case['id'], 1, 'acknowledge')[0].status_code, 201)
        self.events_url = '/api/farm/follow-ups/'+self.case['id']+'/events'
        self.detail_url = '/api/farm/follow-ups/'+self.case['id']

    def event_bytes(self, event_id):
        with journal_db(self.root/'followup.sqlite3') as db:
            return tuple(db.execute('SELECT payload_json,payload_sha256,created_at,request_id,version,state '
                                    'FROM events WHERE id=?', (event_id,)).fetchone())

    def paused_check(self, change_observation):
        import requests
        from werkzeug.serving import make_server
        read = threading.Event()
        resume = threading.Event()
        outcome = queue.Queue(maxsize=1)
        seen = {}
        phases = []
        original = pilot_followup.journal_db

        @contextmanager
        def checkpoint(path):
            from flask import request
            selected = (Path(path) == self.root/'journal.sqlite3' and not seen
                        and request.method == 'POST' and request.path == self.events_url)
            with original(path) as db:
                yield db
                if selected:
                    row = db.execute('SELECT revision,payload_sha256 FROM current_records WHERE visit_id=?',
                                     (self.visit['id'],)).fetchone()
                    seen.update(revision=row['revision'], payload_sha256=row['payload_sha256'])
            if selected:
                # The journal reader is closed; the follow-up write has not happened.
                phases.extend(['revision_1_read', 'journal_reader_closed', 'check_paused_before_insert'])
                read.set()
                if not resume.wait(15):
                    raise AssertionError('Checkpoint was not released')
                phases.append('check_resumed')

        command = dict(client_event_id=str(uuid.uuid4()), base_version=2, action='check',
                       reason='Synthetic deterministic race', observation_id=self.visit['id'], resolution=None)
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        base = 'http://127.0.0.1:'+str(server.server_port)
        def check_request():
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.post(base+self.events_url, headers=self.headers[0], json=command, timeout=25)
                    outcome.put((response.status_code, response.json()))
            except Exception as exc:
                outcome.put(exc)
        worker = threading.Thread(target=check_request, daemon=True)
        revised = None
        with patch('pilot_followup.journal_db', new=checkpoint):
            server_thread.start()
            worker.start()
            try:
                self.assertTrue(read.wait(10), 'Check did not reach the selected read boundary')
                self.assertTrue(worker.is_alive())
                self.assertEqual(seen['revision'], 1)
                self.assertEqual(seen['payload_sha256'], self.visit['payload_sha256'])
                with journal_db(self.root/'followup.sqlite3') as db:
                    count = db.execute('SELECT COUNT(*) FROM events WHERE case_id=?', (self.case['id'],)).fetchone()[0]
                self.assertEqual(count, 2)  # Create/ack only; no check event yet.
                if change_observation:
                    payload = {k:self.payload[k] for k in ['finding', 'notes', 'analysis_id', 'review', 'record_status']}
                    payload.update(base_revision=1, notes='Synthetic correction while check is paused',
                                   change_reason='H5-T02 software fixture')
                    with requests.Session() as session:
                        session.trust_env = False
                        response = session.put(base+'/api/farm/observations/'+self.visit['id'],
                                               headers=self.headers[0], json=payload, timeout=10)
                        self.assertEqual(response.status_code, 201)
                        revised = response.json()['item']
                        self.assertEqual(revised['revision'], 2)
                        current = session.get(base+'/api/farm/observations/'+self.visit['id'],
                                              headers=self.headers[0], timeout=10).json()['item']
                        self.assertEqual(current['payload_sha256'], revised['payload_sha256'])
                    self.assertFalse(resume.is_set())
                    phases.append('revision_2_committed_before_resume')
                else:
                    phases.append('no_revision_change_control')
            finally:
                resume.set()
                worker.join(timeout=30)
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertFalse(server_thread.is_alive())
        result = outcome.get_nowait()
        if isinstance(result, Exception):
            raise result
        status, body = result
        self.assertEqual(status, 201)
        phases.append('check_response_received')
        return command, body, revised, dict(phases=phases, reader_revision=seen['revision'],
            events_before_resume=count, journal_reader_closed_before_writer=True,
            worker_stopped=True, server_stopped=True, real_http=True)

    def test_committed_revision_during_check_keeps_old_event_and_requires_recheck(self):
        command, body, revised, trace = self.paused_check(change_observation=True)
        event = body['event']
        snapshot = event['payload']['observation_snapshot']
        self.assertEqual(snapshot['revision'], 1)
        self.assertEqual(snapshot['payload_sha256'], self.visit['payload_sha256'])
        self.assertNotEqual(snapshot['payload_sha256'], revised['payload_sha256'])
        self.assertFalse(snapshot['platform_verified'])
        self.assertFalse(snapshot['label_approved_for_training'])
        self.assertEqual(digest(event['payload']), event['payload_sha256'])
        status = body['item']['check_status']
        self.assertEqual(body['item']['version'], 3)
        self.assertEqual(body['item']['state'], 'checked')
        self.assertTrue(status['needs_recheck'])
        self.assertIn('observation_changed', status['reasons'])
        self.assertEqual(status['observation']['checked_revision'], 1)
        self.assertEqual(status['observation']['current_revision'], 2)
        frozen = self.event_bytes(event['id'])
        replay = self.client.post(self.events_url, headers=self.headers[0], json=command)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json['event'], event)
        self.assertTrue(replay.json['item']['check_status']['needs_recheck'])
        detail = self.client.get(self.detail_url, headers=self.headers[0]).json['item']
        self.assertTrue(detail['check_status']['needs_recheck'])
        denied = self.command(self.case['id'], 3, 'close')[0]
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(denied.json['error']['code'], 'followup_observation_changed')
        self.assertEqual(len(self.client.get(self.events_url, headers=self.headers[0]).json['items']), 3)
        rechecked = self.command(self.case['id'], 3, 'check')[0]
        self.assertEqual(rechecked.status_code, 201)
        self.assertEqual(rechecked.json['event']['payload']['observation_snapshot']['revision'], 2)
        self.assertEqual(rechecked.json['event']['payload']['observation_snapshot']['payload_sha256'], revised['payload_sha256'])
        self.assertFalse(rechecked.json['item']['check_status']['needs_recheck'])
        self.assertEqual(self.command(self.case['id'], 4, 'close')[0].status_code, 201)
        self.assertEqual(self.event_bytes(event['id']), frozen)
        self.assertEqual(self.client.get('/api/farm/assessments/'+self.a['id'], headers=self.headers[0]).json['item'], self.a)
        self.assertFalse(body['item']['disease_confirmed'])
        self.assertFalse(body['item']['training_approved'])
        RACE_TRACES.append(dict(case='revision_committed_at_checkpoint', **trace,
            event_revision=1, current_revision=2, initial_needs_recheck=True, close_before_recheck=409,
            recheck_revision=2, close_after_recheck=201, original_event_bytes_unchanged=True,
            same_command_replay_preserved_original_event=True, original_assessment_unchanged=True))

    def test_same_checkpoint_without_edit_keeps_check_current(self):
        _, body, revised, trace = self.paused_check(change_observation=False)
        self.assertIsNone(revised)
        self.assertEqual(body['event']['payload']['observation_snapshot']['revision'], 1)
        self.assertFalse(body['item']['check_status']['needs_recheck'])
        status = body['item']['check_status']['observation']
        self.assertEqual((status['checked_revision'], status['current_revision']), (1, 1))
        self.assertEqual(self.command(self.case['id'], 3, 'close')[0].status_code, 201)
        RACE_TRACES.append(dict(case='same_checkpoint_no_edit_control', **trace,
            event_revision=1, current_revision=1, initial_needs_recheck=False, close_after_check=201))


if __name__ == '__main__':
    unittest.main()
