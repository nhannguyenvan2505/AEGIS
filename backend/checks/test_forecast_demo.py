"""Exercise the actual launcher, shutdown and restart against an isolated pilot store."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import forecast_demo
from advance_forecast_source import advance


class ForecastDemo(unittest.TestCase):
    def test_restart_preserves_seed_and_history(self):
        store = ROOT/'pilot_data'/('launcher_acceptance_'+uuid4().hex)
        def cleanup():
            target = store.resolve()
            self.assertEqual(target.parent, (ROOT/'pilot_data').resolve())
            self.assertTrue(target.name.startswith('launcher_acceptance_'))
            if target.exists():
                shutil.rmtree(target)
        self.addCleanup(cleanup)
        password = str(uuid4())
        results = []
        original_seed = forecast_demo.seed
        def seed_and_advance(base, email, password):
            initial = original_seed(base, email, password)
            self.assertNotEqual(*[r['score'] for r in initial])
            missing = advance(base, email, password, initial[0]['season_id'], 1, 'missing')
            self.assertEqual(missing['status'], 'insufficient_data')
            self.assertIsNone(missing['score'])
            recovered = advance(base, email, password, initial[0]['season_id'], 120, 'dry')
            self.assertEqual(recovered['status'], 'forecast_ready')
            self.assertEqual(recovered['source_revision'], 3)
            # A repeated seed preserves the advanced clock, source and prediction.
            return original_seed(base, email, password)
        for index in range(2):
            output = io.StringIO()
            argv = ['forecast_demo.py', '--model-python', os.environ['FM02_PYTHON'],
                    '--store', str(store), '--port', '0', '--duration', '.01']
            with patch.object(sys, 'argv', argv), patch.object(forecast_demo.getpass, 'getpass', return_value=password), patch.object(forecast_demo, 'seed', side_effect=seed_and_advance if index == 0 else original_seed), contextlib.redirect_stdout(output):
                code = forecast_demo.main()
            result = json.loads(output.getvalue().splitlines()[-1])
            if code:
                self.fail(json.dumps(result)+'\n'+Path(result['log_path']).read_text(encoding='utf-8'))
            self.assertTrue(result['services_stopped'])
            self.assertTrue(result['store_preserved'])
            self.assertNotIn(password, output.getvalue())
            ready = Path(result['log_path']).parent/'ready.json'
            self.assertEqual(json.loads(ready.read_text(encoding='utf-8'))['regions'], result['regions'])
            self.assertNotIn(password, ready.read_text(encoding='utf-8'))
            results.append(result)
        self.assertEqual(results[0]['regions'], results[1]['regions'])
        self.assertEqual(len(results[0]['regions']), 2)
        self.assertNotEqual(*[r['score'] for r in results[0]['regions']])
        with contextlib.closing(sqlite3.connect(store/'telemetry.sqlite3')) as db:
        self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_forecasts').fetchone()[0], 4)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_hourly_sources').fetchone()[0], 4)
        with contextlib.closing(sqlite3.connect(store/'demo.db')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
