"""Apply the one-time core extension to an unused Compose development database."""
from pathlib import Path
from verify_databases import run, MYSQL


def main():
    inventory = run('mysql', MYSQL, 'SHOW TABLES;')
    if inventory.returncode:
        raise RuntimeError(inventory.stderr)
    if 'schema_versions' in inventory.stdout.splitlines():
        status = run('mysql', MYSQL, 'SELECT status FROM schema_versions WHERE version=2;')
        if status.returncode or status.stdout.strip() != 'complete':
            raise RuntimeError('Migration incomplete: inspect schema; refusing to rerun partial DDL')
        print('Runtime migration 2 already complete')
        return
    # DDL auto-commits. Require an unused development schema before extending it.
    tables = inventory.stdout.splitlines()
    for table in tables:
        if table == 'roles':
            continue
        if not table.replace('_','').isalnum():
            raise RuntimeError('Unexpected table identifier')
        count = run('mysql', MYSQL, f'SELECT COUNT(*) FROM `{table}`;')
        if count.returncode or count.stdout.strip() != '0':
            raise RuntimeError(f'{table} is not empty; use a reviewed data migration instead')
    sql = (Path(__file__).parent / 'mysql' / '002_core_runtime.sql').read_text(encoding='utf-8')
    result = run('mysql', MYSQL, sql)
    if result.returncode:
        raise RuntimeError(result.stderr)
    print('Runtime migration 2 complete on isolated Compose dev database')


if __name__ == '__main__':
    main()
