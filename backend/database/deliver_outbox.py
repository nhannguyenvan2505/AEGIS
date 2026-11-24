"""Retry pending Mongo delivery once or continuously without starting the API."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database_config import settings
from app.mongo_delivery import deliver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poll',type=float,default=0,help='0 runs once; otherwise poll interval >= 1 second')
    args=parser.parse_args()
    if args.poll and args.poll<1: parser.error('--poll must be >= 1')
    config=dict(settings(),STORAGE_BACKEND='mysql')
    while True:
        result=deliver(config,limit=1000)
        print(result,flush=True)
        if not args.poll:
            sys.exit(1 if result['failed'] else 0)
        time.sleep(args.poll)


if __name__=='__main__': main()
