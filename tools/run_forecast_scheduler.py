"""Run durable forecast jobs in an existing pilot store."""
import argparse
import json
import math
from pathlib import Path
import sys
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'frontend'))
from pilot_app import create_pilot_app
from pilot_store import validate_storage
from forecast_scheduler import ForecastRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--worker-port', type=int, default=8001)
    parser.add_argument('--poll-seconds', type=int, default=5)
    parser.add_argument('--duration', type=float, default=0)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.worker_port <= 65535 or not 5 <= args.poll_seconds <= 3600 or not math.isfinite(args.duration) or args.duration < 0:
        parser.error('Invalid port, poll interval or duration')
    storage = validate_storage(args.store)
    app = create_pilot_app(storage)
    app.config['FORECAST_WORKER_PORT'] = args.worker_port
    runner = ForecastRunner(app, storage)
    started = time.monotonic()
    try:
        while args.duration == 0 or time.monotonic()-started < args.duration:
            try:
                result = runner.tick()
                print(json.dumps(dict(status=result['status'], runs=len(result['runs']))), flush=True)
            except sqlite3.Error:
                print(json.dumps(dict(status='storage_unavailable')), flush=True)
                if args.once:
                    return 1
            if args.once:
                break
            deadline = time.monotonic()+args.poll_seconds
            if args.duration:
                deadline = min(deadline, started+args.duration)
            while time.monotonic() < deadline:
                time.sleep(min(60, max(0, deadline-time.monotonic())))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
