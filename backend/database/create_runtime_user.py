"""Create the least-privilege MySQL account the running backend should use.

Migrations (database/migrate.py) need schema privileges; the core backend only reads
and writes rows. This creates or resets a separate account with exactly that.
First-time provisioning of a pilot store creates tables, so do it with the
migration account before switching the pilot to this one.

Passwords come from the environment, never from the command line:
  AEGIS_MYSQL_ADMIN_PASSWORD    account allowed to CREATE USER (default user: root)
  AEGIS_MYSQL_RUNTIME_PASSWORD  new password of the runtime account

    python database/create_runtime_user.py --user aegis_runtime --host %

Then run the backend with AEGIS_MYSQL_USER / AEGIS_MYSQL_PASSWORD set to the runtime
account, and keep AEGIS_MYSQL_MIGRATION_USER / _PASSWORD for migrate.py and backups.
"""
import argparse
import os
from pathlib import Path
import re
import sys

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import migration_settings, settings  # noqa: E402

RUNTIME_PRIVILEGES = 'SELECT, INSERT, UPDATE, DELETE'
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}')
_DATABASE = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}')
_HOST = re.compile(r'[A-Za-z0-9._%-]{1,255}')


def _literal(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "''") + "'"


def runtime_account_statements(database, user, host, password):
    """SQL that leaves `user`@`host` with row access to `database` and nothing else."""
    if not _DATABASE.fullmatch(database) or not _NAME.fullmatch(user) or not _HOST.fullmatch(host):
        raise ValueError('Database, user and host must be plain identifiers')
    if not isinstance(password, str) or len(password) < 16:
        raise ValueError('Runtime password must have at least 16 characters')
    account = f'{_literal(user)}@{_literal(host)}'
    # In a database-level GRANT "_" is a wildcard unless escaped.
    scope = '`' + database.replace('_', r'\_') + '`.*'
    return [f'CREATE USER IF NOT EXISTS {account} IDENTIFIED BY {_literal(password)}',
            f'ALTER USER {account} IDENTIFIED BY {_literal(password)}',
            f'REVOKE ALL PRIVILEGES, GRANT OPTION FROM {account}',
            f'GRANT {RUNTIME_PRIVILEGES} ON {scope} TO {account}']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--user', required=True)
    parser.add_argument('--host', default='localhost', help="client host pattern, e.g. localhost or %%")
    args = parser.parse_args()
    options = settings()['MYSQL']
    admin_user = os.environ.get('AEGIS_MYSQL_ADMIN_USER', 'root')
    admin_password = os.environ.get('AEGIS_MYSQL_ADMIN_PASSWORD')
    password = os.environ.get('AEGIS_MYSQL_RUNTIME_PASSWORD')
    if not admin_password or not password:
        parser.error('Set AEGIS_MYSQL_ADMIN_PASSWORD and AEGIS_MYSQL_RUNTIME_PASSWORD')
    # Resetting an account that migrates or administers would strip its privileges.
    protected = {admin_user.lower(), 'root', migration_settings()['user'].lower()}
    if args.user.lower() in protected:
        parser.error('Choose a new account name; this one runs migrations or administers MySQL')
    statements = runtime_account_statements(options['database'], args.user, args.host, password)
    connection = pymysql.connect(host=options['host'], port=options['port'], user=admin_user,
                                 password=admin_password, charset='utf8mb4', autocommit=True, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
            cursor.execute(f'SHOW GRANTS FOR {_literal(args.user)}@{_literal(args.host)}')
            for row in cursor.fetchall():
                print(row[0])
    finally:
        connection.close()
    print(f'Runtime account ready: {args.user}@{args.host}')


if __name__ == '__main__':
    main()
