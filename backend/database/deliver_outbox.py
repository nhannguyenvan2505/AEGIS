"""Deliver the Mongo outbox without starting the API, or inspect/requeue it.

The API process already runs a background dispatcher unless
AEGIS_MONGO_DELIVERY_ENABLED=0; use --poll here to run delivery as a
separate process instead. --status prints queue health; --retry-failed
returns parked events to the queue after the cause has been fixed.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database_config import settings
from app.mongo_delivery import deliver, outbox_status, retry_failed


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--poll',type=float,default=0,help='0 runs once; otherwise poll interval >= 1 second')
    parser.add_argument('--status',action='store_true',help='print pending/delivered/failed counts and exit')
    parser.add_argument('--retry-failed',nargs='*',metavar='EVENT_KEY',
                        help='requeue parked events (all when no key is given) and exit')
    args=parser.parse_args()
    if args.poll and args.poll<1: parser.error('--poll must be >= 1')
    config=dict(settings(),STORAGE_BACKEND='mysql')
    if args.status:
        status=outbox_status(config)
        print(json.dumps(status),flush=True)
        sys.exit(1 if status['failed'] else 0)
    if args.retry_failed is not None:
        print(json.dumps(dict(requeued=retry_failed(config,args.retry_failed))),flush=True)
        return
    while True:
        result=deliver(config,limit=1000)
        print(json.dumps(result),flush=True)
        if not args.poll:
            sys.exit(1 if result['failed'] else 0)
        time.sleep(args.poll)


if __name__=='__main__': main()
