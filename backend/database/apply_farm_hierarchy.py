"""Apply the additive farm API migration once, without replacing existing data."""
from pathlib import Path
import sys

import pymysql
from pymysql.constants import CLIENT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings


def main():
    connection = pymysql.connect(**settings()['MYSQL'], charset='utf8mb4', autocommit=True,
                                 client_flag=CLIENT.MULTI_STATEMENTS, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            for version in (2, 3, 4):
                cursor.execute('SELECT status FROM schema_versions WHERE version=%s', (version,))
                if cursor.fetchone() != ('complete',):
                    raise RuntimeError(f'Complete migration {version} before the farm hierarchy upgrade')
            cursor.execute('SELECT status FROM schema_versions WHERE version=5')
            row = cursor.fetchone()
            if row == ('complete',):
                print('Farm hierarchy migration 5 already complete')
                return
            if row:
                raise RuntimeError('Partial migration 5: inspect schema before continuing; DDL will not be replayed')
            sql = (Path(__file__).parent/'mysql'/'005_farm_hierarchy.sql').read_text(encoding='utf-8')
            cursor.execute(sql)
            while cursor.nextset():
                pass
    finally:
        connection.close()
    print('Farm hierarchy migration 5 complete; existing fields and seasons retained')


if __name__ == '__main__':
    main()
