"""One-shot database preparation for a deployment, run before the backend starts.

An empty database is provisioned completely. An existing database is never migrated:
pending migrations are reported and the command fails, so that someone backs up and
runs database/migrate.py on purpose. The backend's row-only account is created when
it is missing and is otherwise left alone.

Environment (besides the AEGIS_MYSQL_* connection settings):
  AEGIS_MYSQL_MIGRATION_USER / _PASSWORD   owns the schema
  AEGIS_MYSQL_ADMIN_USER / _PASSWORD       may create accounts (default user: root)
  AEGIS_MYSQL_RUNTIME_USER / _PASSWORD     the account the backend will use
  AEGIS_MYSQL_RUNTIME_HOST                 its client host pattern (default: %)
"""
import os
from pathlib import Path
import sys

import pymysql
from pymysql.constants import CLIENT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database_config import migration_settings  # noqa: E402
from create_runtime_user import runtime_account_statements  # noqa: E402
from migrate import apply_schema, applied_versions, numbered_migrations  # noqa: E402


def _connect(options, **extra):
    return pymysql.connect(**options, charset='utf8mb4', autocommit=True, connect_timeout=5, **extra)


def _prepare_schema(migration):
    connection = _connect(migration, client_flag=CLIENT.MULTI_STATEMENTS)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
            empty = cursor.fetchone()[0] == 0
            applied = applied_versions(cursor)
        if empty:
            apply_schema(connection)
            return 'provisioned', []
        pending = [version for version, _ in numbered_migrations() if applied.get(version) != 'complete']
        return ('pending' if pending else 'ready'), pending
    finally:
        connection.close()


def initialize(admin, migration, runtime_user, runtime_password, runtime_host='%'):
    """Return {state: provisioned|ready|pending, pending: [...], account: created|kept|None}."""
    if runtime_user.lower() in {migration['user'].lower(), str(admin['user']).lower(), 'root'}:
        raise ValueError('The runtime account must differ from the migration and admin accounts')
    # Validate before touching anything.
    statements = runtime_account_statements(migration['database'], runtime_user, runtime_host, runtime_password)
    state, pending = _prepare_schema(migration)
    if state == 'pending':
        return dict(state=state, pending=pending, account=None)
    connection = _connect(admin)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM mysql.user WHERE user=%s AND host=%s',
                           (runtime_user, runtime_host))
            if cursor.fetchone()[0]:
                account = 'kept'
            else:
                for statement in statements:
                    cursor.execute(statement)
                account = 'created'
    finally:
        connection.close()
    return dict(state=state, pending=pending, account=account)


def main():
    migration = migration_settings()
    env = os.environ
    missing = [name for name in ('AEGIS_MYSQL_ADMIN_PASSWORD', 'AEGIS_MYSQL_RUNTIME_USER',
                                 'AEGIS_MYSQL_RUNTIME_PASSWORD') if not env.get(name)]
    if missing:
        sys.exit('Set ' + ', '.join(missing))
    admin = dict(host=migration['host'], port=migration['port'],
                 user=env.get('AEGIS_MYSQL_ADMIN_USER', 'root'), password=env['AEGIS_MYSQL_ADMIN_PASSWORD'])
    try:
        result = initialize(admin, migration, env['AEGIS_MYSQL_RUNTIME_USER'],
                            env['AEGIS_MYSQL_RUNTIME_PASSWORD'], env.get('AEGIS_MYSQL_RUNTIME_HOST', '%'))
    except (ValueError, RuntimeError, pymysql.Error) as exc:
        sys.exit(f'Database preparation failed: {exc}')
    if result['state'] == 'pending':
        sys.exit(f'Migrations {result["pending"]} are pending and nothing was changed. Back up first, then run '
                 'database/migrate.py (see deploy/README.md, "Nâng cấp").')
    print(f'Database {result["state"]}; runtime account {result["account"]}.')


if __name__ == '__main__':
    main()
