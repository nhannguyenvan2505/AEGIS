"""Apply the retention periods decided on 25/11/2026.

ESP32 telemetry is kept 180 days; Mongo outbox events already delivered are kept
30 days. Pending and failed events are never removed. Without --apply this only
counts, and nothing schedules it. Back up before --apply.

    python database/retention.py
    python database/retention.py --apply
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database_config import settings  # noqa: E402
from app.repositories.mysql import open_connection  # noqa: E402
from purge_iot_telemetry import TELEMETRY_DAYS, purge  # noqa: E402

OUTBOX_DAYS = 30


def purge_outbox(config, older_than_days=OUTBOX_DAYS, *, apply=False, batch=5000):
    """Remove delivered outbox events; Mongo already holds their documents."""
    if type(older_than_days) is not int or older_than_days < 1:
        raise ValueError('older_than_days must be a positive integer')
    where = ("status='delivered' AND delivered_at IS NOT NULL "
             'AND delivered_at < UTC_TIMESTAMP(6) - INTERVAL %s DAY')
    connection = open_connection(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) n FROM mongo_outbox WHERE ' + where, (older_than_days,))
            matched = cursor.fetchone()['n']
        connection.commit()
        deleted = 0
        while apply:
            with connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM mongo_outbox WHERE {where} LIMIT %s', (older_than_days, batch))
                count = cursor.rowcount
            connection.commit()
            deleted += count
            if count < batch:
                break
    finally:
        connection.close()
    return dict(older_than_days=older_than_days, matched=matched, deleted=deleted)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--telemetry-days', type=int, default=TELEMETRY_DAYS)
    parser.add_argument('--outbox-days', type=int, default=OUTBOX_DAYS)
    parser.add_argument('--apply', action='store_true', help='delete; without it only count')
    args = parser.parse_args()
    if args.telemetry_days < 1 or args.outbox_days < 1:
        parser.error('Retention periods must be at least 1 day')
    config = dict(settings(), STORAGE_BACKEND='mysql')
    print(json.dumps(dict(applied=args.apply,
                          esp32_telemetry=purge(config, args.telemetry_days, apply=args.apply),
                          mongo_outbox=purge_outbox(config, args.outbox_days, apply=args.apply))))


if __name__ == '__main__':
    main()
