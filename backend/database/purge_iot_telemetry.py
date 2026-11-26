"""Retention for ESP32 telemetry: delete readings received before a cutoff.

The default period is 180 days (decided 25/11/2026). Nothing schedules this;
without --apply it only counts. Age uses created_at (server clock), not the device's
observed_at. Device bindings are never touched. Back up before --apply.

    python database/purge_iot_telemetry.py
    python database/purge_iot_telemetry.py --apply
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402
from app.iot_mqtt import _db_cursor  # noqa: E402


TELEMETRY_DAYS = 180


def purge(config, older_than_days, *, apply=False, batch=5000, now=None):
    """Return {cutoff, matched, deleted}; each batch commits on its own."""
    if type(older_than_days) is not int or older_than_days < 1:
        raise ValueError('older_than_days must be a positive integer')
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=older_than_days)).isoformat(timespec='seconds')
    with _db_cursor(config) as (cur, is_mysql):
        mark = '%s' if is_mysql else '?'
        cur.execute(f'SELECT COUNT(*) n FROM esp32_telemetry_readings WHERE created_at<{mark}', (cutoff,))
        matched = cur.fetchone()['n']
    deleted = 0
    while apply:
        with _db_cursor(config) as (cur, is_mysql):
            if is_mysql:
                cur.execute('DELETE FROM esp32_telemetry_readings WHERE created_at<%s '
                            'ORDER BY created_at LIMIT %s', (cutoff, batch))
            else:
                cur.execute('DELETE FROM esp32_telemetry_readings WHERE reading_id IN (SELECT reading_id '
                            'FROM esp32_telemetry_readings WHERE created_at<? LIMIT ?)', (cutoff, batch))
            count = cur.rowcount
        deleted += count
        if count < batch:
            break
    return dict(cutoff=cutoff, matched=matched, deleted=deleted)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--older-than-days', type=int, default=TELEMETRY_DAYS)
    parser.add_argument('--apply', action='store_true', help='delete; without it only count')
    args = parser.parse_args()
    if args.older_than_days < 1:
        parser.error('--older-than-days must be at least 1')
    config = dict(settings(), STORAGE_BACKEND='mysql')
    print(json.dumps(purge(config, args.older_than_days, apply=args.apply)))


if __name__ == '__main__':
    main()
