"""BE-02 unit checks that need no database: backoff policy and request path."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.mongo_delivery import BACKOFF_MAX_SECONDS, MAX_ATTEMPTS, backoff_seconds


class OutboxUnitTests(unittest.TestCase):
    def test_backoff_grows_and_is_capped(self):
        delays = [backoff_seconds(n) for n in range(1, MAX_ATTEMPTS)]
        self.assertEqual(delays[:4], [5, 10, 20, 40])
        self.assertEqual(delays, sorted(delays))
        self.assertEqual(backoff_seconds(100), BACKOFF_MAX_SECONDS)

    def test_responses_never_trigger_delivery(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch('app.mongo_delivery.deliver', side_effect=AssertionError('delivery on request path')), \
                patch('app.outbox_dispatcher.start_dispatcher') as start:
            app = create_app(dict(TESTING=True, STORAGE_BACKEND='sqlite',
                                  DATABASE_PATH=Path(temp) / 'aegis.sqlite3', UPLOAD_DIR=Path(temp) / 'uploads'))
            self.assertEqual(app.test_client().get('/health').status_code, 200)
            start.assert_not_called()  # Tests and SQLite fixtures never start a dispatcher.
            self.assertNotIn('outbox_dispatcher', app.extensions)


if __name__ == '__main__':
    unittest.main()
