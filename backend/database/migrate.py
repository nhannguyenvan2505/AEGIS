"""Apply pending numbered MySQL migrations to the configured database.

Works for the native and the Docker instance (settings come from the environment
or database/.env). Back up first: MySQL DDL commits immediately.

    python database/migrate.py --status    # list versions, change nothing
    python database/migrate.py             # apply whatever is pending
"""
import argparse
from pathlib import Path
import sys

import pymysql
from pymysql.constants import CLIENT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent / 'mysql'


def numbered_migrations():
    """(version, path) for 002 onwards; 001_design.sql is the bootstrap."""
    found = ((int(path.name[:3]), path) for path in SQL_DIR.glob('[0-9][0-9][0-9]_*.sql'))
    return sorted(item for item in found if item[0] >= 2)


def _has_table(cursor, name):
    cursor.execute('SELECT COUNT(*) FROM information_schema.tables '
                   'WHERE table_schema=DATABASE() AND table_name=%s', (name,))
    return cursor.fetchone()[0] != 0


def _run(cursor, path):
    cursor.execute(path.read_text(encoding='utf-8'))
    while cursor.nextset():
        pass


def applied_versions(cursor):
    if not _has_table(cursor, 'schema_versions'):
        return {}
    cursor.execute('SELECT version, status FROM schema_versions')
    return dict(cursor.fetchall())


def apply_schema(connection, through=None):
    """Apply trusted numbered SQL once; never replay a partial DDL migration.

    `connection` needs the default tuple cursor, autocommit and MULTI_STATEMENTS.
    `through` stops after that version (upgrade tests only). Returns new versions.
    """
    done = []
    with connection.cursor() as cursor:
        fresh = not _has_table(cursor, 'users')
        if fresh:
            _run(cursor, SQL_DIR / '001_design.sql')
        elif not _has_table(cursor, 'schema_versions'):
            raise RuntimeError('Existing database has no runtime marker; inspect it before upgrading')
        for version, path in numbered_migrations():
            if through is not None and version > through:
                break
            status = applied_versions(cursor).get(version)
            if status == 'complete':
                continue
            if status:
                raise RuntimeError(f'Partial migration {version}; inspect schema instead of replaying DDL')
            _run(cursor, path)
            done.append(version)
            print(f'Migration {version} complete', flush=True)
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--status', action='store_true', help='show versions without changing anything')
    args = parser.parse_args()
    options = settings()['MYSQL']
    connection = pymysql.connect(**options, charset='utf8mb4', autocommit=True, connect_timeout=5,
                                 client_flag=CLIENT.MULTI_STATEMENTS)
    try:
        if args.status:
            with connection.cursor() as cursor:
                applied = applied_versions(cursor)
            for version, path in numbered_migrations():
                print(f'{version:>3}  {applied.get(version, "pending"):<9} {path.name}')
            return
        done = apply_schema(connection)
        print(f'Database {options["database"]}: ' + (f'applied {done}' if done else 'already up to date'))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
