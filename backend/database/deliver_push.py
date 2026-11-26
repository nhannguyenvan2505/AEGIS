"""Send queued Expo push notifications and check their receipts.

Opt-in: this sends alert titles, messages and device tokens to Expo, so it refuses
to run unless AEGIS_PUSH_ENABLED=1. Set EXPO_ACCESS_TOKEN if the Expo project
enforces push security. Run it as its own process, next to the backend.

    python database/deliver_push.py            # one pass
    python database/deliver_push.py --poll 30  # keep running, every 30 seconds
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402
from app.push import PushTransportError, check_receipts, deliver, transport_from_environment  # noqa: E402


def run_once(config, transport):
    result = dict(send=deliver(config, transport))
    try:
        result['receipts'] = check_receipts(config, transport)
    except PushTransportError as exc:
        result['receipts'] = dict(error=exc.code)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--poll', type=int, metavar='SECONDS', help='repeat forever at this interval')
    args = parser.parse_args()
    if os.environ.get('AEGIS_PUSH_ENABLED') != '1':
        parser.error('Push delivery is off. Set AEGIS_PUSH_ENABLED=1 to send to Expo.')
    if args.poll is not None and args.poll < 5:
        parser.error('--poll must be at least 5 seconds')
    config, transport = settings(), transport_from_environment()
    while True:
        try:
            print(json.dumps(run_once(config, transport)), flush=True)
        except Exception as exc:  # keep polling; MySQL may come back
            if args.poll is None:
                raise
            print(json.dumps(dict(error=type(exc).__name__)), flush=True)
        if args.poll is None:
            return
        time.sleep(args.poll)


if __name__ == '__main__':
    main()
