"""Read-only audit of ESP32 bindings and readings stored before the ownership fixes.

    python tools/audit_iot_data.py                      # MySQL from backend/database/.env
    python tools/audit_iot_data.py --storage sqlite --database path/to/aegis.sqlite3

Nothing is changed or deleted. Findings are leads for a person to judge: a wrong first
claim looks exactly like a correct one, so every binding is listed for confirmation,
and any reading that arrived over an unauthenticated broker is untrusted regardless.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

TABLES = ('esp32_device_bindings', 'esp32_telemetry_readings')


@contextmanager
def _reader(config):
    """Yield query(sql) -> list of dicts on a connection that cannot write."""
    if config.get('STORAGE_BACKEND', 'sqlite') == 'mysql':
        from app.repositories.mysql import open_connection
        connection = open_connection(config)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SET SESSION TRANSACTION READ ONLY')

                def query(sql):
                    cursor.execute(sql)
                    return list(cursor.fetchall())
                yield query
        finally:
            connection.rollback()
            connection.close()
        return
    connection = sqlite3.connect(Path(config['DATABASE_PATH']).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield lambda sql: [dict(row) for row in connection.execute(sql)]
    finally:
        connection.close()


def audit(config):
    mysql = config.get('STORAGE_BACKEND', 'sqlite') == 'mysql'
    with _reader(config) as query:
        catalog = ('SELECT table_name name FROM information_schema.tables WHERE table_schema=DATABASE()' if mysql
                   else "SELECT name FROM sqlite_master WHERE type='table'")
        present = {row['name'] for row in query(catalog)}
        missing = [name for name in TABLES if name not in present]
        if missing:
            return dict(missing_tables=missing, bindings=[], findings=[], readings_by_source={})
        owners = {row['id']: row['owner_id'] for row in query(
            'SELECT f.external_id id, u.external_id owner_id FROM farm_fields f JOIN users u ON u.user_id=f.user_id'
            if mysql else 'SELECT id, user_id owner_id FROM farm_plots')}
        bindings = query('SELECT device_uid, plot_id, updated_at FROM esp32_device_bindings ORDER BY device_uid')
        registry = query('SELECT d.device_uid, f.external_id plot_id FROM iot_devices d '
                         'LEFT JOIN farm_fields f ON f.field_id=d.field_id') if mysql else []
        groups = query('SELECT device_uid, plot_id, source, COUNT(*) n, MIN(observed_at) first_at, '
                       'MAX(observed_at) last_at FROM esp32_telemetry_readings '
                       'GROUP BY device_uid, plot_id, source ORDER BY device_uid, plot_id, source')

    # Bindings compare device ids case-insensitively on MySQL, so the audit does too.
    registered, assigned = {}, {}
    for row in registry:
        registered.setdefault(row['device_uid'].upper(), set()).add(row['plot_id'])
        assigned.setdefault(row['device_uid'].upper(), set()).add(row['plot_id'])
    for row in bindings:
        if row['plot_id']:
            assigned.setdefault(row['device_uid'].upper(), set()).add(row['plot_id'])

    findings = []

    def report(kind, uid, plot_id, count=1, **extra):
        findings.append(dict(kind=kind, device_uid=uid, plot_id=plot_id, count=count, **extra))

    listed = []
    for row in bindings:
        uid, plot = row['device_uid'], row['plot_id']
        if not plot:
            continue
        listed.append(dict(device_uid=uid, plot_id=plot, owner_id=owners.get(plot), updated_at=row['updated_at']))
        if uid.lower() == 'unknown' or not uid.isascii():
            report('binding_reserved_or_non_ascii_id', uid, plot)
        if plot not in owners:
            report('binding_plot_not_found', uid, plot)
        if any(other != plot for other in registered.get(uid.upper(), ())):
            report('binding_conflicts_with_registry', uid, plot)

    by_source = {}
    for row in groups:
        total = by_source.setdefault(row['source'], dict(count=0, first_at=row['first_at'], last_at=row['last_at']))
        total['count'] += row['n']
        total['first_at'] = min(total['first_at'], row['first_at'])
        total['last_at'] = max(total['last_at'], row['last_at'])
        uid, plot = row['device_uid'], row['plot_id']
        if row['source'] != 'esp32_mqtt' or not plot:
            continue
        span = dict(first_at=row['first_at'], last_at=row['last_at'])
        known = assigned.get(uid.upper(), set())
        if plot not in owners:
            report('mqtt_plot_not_found', uid, plot, row['n'], **span)
        elif not known:
            report('mqtt_plot_without_assignment', uid, plot, row['n'], **span)
        elif plot not in known:
            report('mqtt_plot_differs_from_assignment', uid, plot, row['n'], **span)
    return dict(missing_tables=[], bindings=listed, findings=findings, readings_by_source=by_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--storage', choices=('mysql', 'sqlite'), default='mysql')
    parser.add_argument('--database', type=Path, default=ROOT / 'backend/instance/aegis.sqlite3',
                        help='SQLite file (with --storage sqlite)')
    args = parser.parse_args()
    from app.database_config import settings
    config = dict(settings(), STORAGE_BACKEND=args.storage, DATABASE_PATH=args.database)
    print(json.dumps(audit(config), ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
