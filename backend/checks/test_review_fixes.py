"""Small fixes from the 25/11 review that need no MySQL server."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402
from app.push import ExpoTransport, PushTransportError  # noqa: E402


class FakeExpo(ExpoTransport):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def _post(self, url, payload):
        return self.data


class PushTicketShapeTests(unittest.TestCase):
    def test_one_message_accepts_a_single_ticket_object(self):
        ticket = {'status': 'ok', 'id': 'abc'}
        for data in (ticket, [ticket]):
            self.assertEqual(FakeExpo(data).send([{'to': 'x'}]), [ticket], data)

    def test_any_other_mismatch_is_still_rejected(self):
        ticket = {'status': 'ok', 'id': 'abc'}
        for data, count in ((ticket, 2), ([ticket], 2), ([], 1), ('ok', 1), ({}, 2)):
            with self.assertRaises(PushTransportError):
                FakeExpo(data).send([{'to': 'x'}] * count)


class IdempotencyTtlTests(unittest.TestCase):
    def build(self, **config):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_app(dict(TESTING=True, DATABASE_PATH=root / 't.db', UPLOAD_DIR=root / 'u', **config))

    def test_ttl_must_outlast_a_running_ai_call(self):
        for ttl in (0, -1, 60, 63, 64.5, '300'):
            with self.assertRaisesRegex(ValueError, 'IDEMPOTENCY_RUNNING_TTL_SECONDS', msg=repr(ttl)):
                self.build(IDEMPOTENCY_RUNNING_TTL_SECONDS=ttl)
        self.build(IDEMPOTENCY_RUNNING_TTL_SECONDS=64)
        self.build()


if __name__ == '__main__':
    unittest.main()
