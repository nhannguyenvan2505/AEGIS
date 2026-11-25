"""Native MySQL integration; disposable schemas only, no Docker commands.

Enable AEGIS_RUN_NATIVE_MYSQL_TESTS=1 after setup_native_mysql.py. Admin credentials
are read privately from database/.env; application data is never used as a fixture.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

import pymysql
from pymysql.constants import CLIENT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'database'))
import test_mysql_core as core
import test_farm_hierarchy as contract
import mobile_http
from app import create_app
from app.database_config import settings
from app.repositories import repository
from setup_native_mysql import apply_schema, local_values
from migrate_sqlite import migrate_core, read


class NativeDatabaseFixture:
    schema_through = None
    grant_host = 'localhost'
    @classmethod
    def setUpClass(cls):
        options = settings()['MYSQL']
        cls.admin = dict(options, user='root', password=local_values()['AEGIS_MYSQL_ROOT_PASSWORD'])
        cls.database = 'aegis_test_'+uuid.uuid4().hex
        cls.mysql = dict(options, database=cls.database)
        with pymysql.connect(**cls.admin, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
                cursor.execute(f'GRANT ALL ON `{cls.database}`.* TO %s@\'localhost\'', (options['user'],))
        cls.addClassCleanup(cls.drop_database)
        with pymysql.connect(**dict(cls.admin, database=cls.database), autocommit=True,
                             client_flag=CLIENT.MULTI_STATEMENTS) as connection:
            apply_schema(connection, through=cls.schema_through)

    @classmethod
    def drop_database(cls):
        if not cls.database.startswith('aegis_test_') or len(cls.database) != 43:
            raise RuntimeError('Invalid disposable schema name')
        with pymysql.connect(**cls.admin, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE `{cls.database}`')
                cursor.execute(f'REVOKE ALL ON `{cls.database}`.* FROM %s@\'localhost\'', (cls.mysql['user'],))


@unittest.skipUnless(os.environ.get('AEGIS_RUN_NATIVE_MYSQL_TESTS') == '1', 'native MySQL integration opt-in required')
class NativeMySQLCoreTests(NativeDatabaseFixture, core.MySQLCoreTests):
    """Run the existing complete core API contract on native MySQL too."""
    __unittest_skip__ = False


@unittest.skipUnless(os.environ.get('AEGIS_RUN_NATIVE_MYSQL_TESTS') == '1', 'native MySQL integration opt-in required')
class NativeFarmHierarchyTests(NativeDatabaseFixture, contract.FarmHierarchyTests):
    setUp = core.MySQLCoreTests.setUp

    def test_upgrade_backfills_legacy_plots_without_changing_seasons(self):
        self.skipTest('SQLite-specific migration is covered by test_farm_hierarchy')

    def test_development_marker_upgrade_preserves_farm_memberships(self):
        self.skipTest('SQLite-only development marker')

    def test_concurrent_updates_allow_exactly_one_version(self):
        farm = self.create()
        path = '/farms/'+farm['id']
        def update(name):
            with self.app.test_client() as client:
                return client.put('/api/farm'+path, headers=self.headers[0],
                    json=dict(name=name, address='Cần Thơ', version=1)).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ['Client one', 'Client two']))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(self.call(path).json['item']['version'], 2)

    def test_area_precision_pagination_and_legacy_contract(self):
        farm = self.create()
        path = '/farms/'+farm['id']
        for area in (0.0001234567, 999999.999999, None):
            response = self.call(path+'/plots', 'POST', dict(name='Precision', area_ha=area))
            self.assertEqual(response.status_code, 201, response.json)
            self.assertEqual(response.json['item']['area_ha'], area)
        page = self.call(path+'/plots?page_size=2').json
        self.assertEqual(page['pagination']['total'], 3)
        self.assertEqual(len(page['items']), 2)
        self.assertTrue(page['pagination']['has_next'])
        self.assertEqual(self.call(path).json['item']['plots_without_area'], 1)
        legacy = self.call('/plots', 'POST', dict(name='Legacy', farm_id=farm['id'], area_ha=2.25))
        self.assertEqual(legacy.status_code, 201)
        self.assertEqual(set(legacy.json['item']), {'id','user_id','name','location_text','created_at'})

    def test_mysql_runtime_does_not_open_sqlite(self):
        with patch('sqlite3.connect', side_effect=AssertionError('Unexpected SQLite runtime connection')):
            farm = self.create()
            plot = self.call('/farms/'+farm['id']+'/plots', 'POST', dict(name='Native', area_ha=1.25)).json['item']
            response = self.call('/plots/'+plot['id']+'/seasons', 'POST', dict(name='Native season', start_date='2026-11-01'))
            self.assertEqual(response.status_code, 201, response.json)
            self.assertEqual(self.call('/farms/'+farm['id']).json['item']['plot_count'], 1)

    def test_sqlite_import_keeps_farm_metadata_uuid_area_and_season(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.db'
            app = create_app(dict(TESTING=True, STORAGE_BACKEND='sqlite', DATABASE_PATH=source,
                                  UPLOAD_DIR=Path(directory)/'uploads'))
            client = app.test_client()
            credentials = dict(email=uuid.uuid4().hex+'@example.test', password='Farm-import-password-123')
            client.post('/api/auth/register', json=credentials)
            token = client.post('/api/auth/login', json=credentials).json['access_token']
            headers = {'Authorization': 'Bearer '+token}
            def post(path, data):
                response = client.post('/api/farm'+path, headers=headers, json=data)
                self.assertEqual(response.status_code, 201, response.json)
                return response.json['item']
            farm = post('/farms', dict(name='Imported farm', address='A'*500, manager='Owner', notes='First\nSecond'))
            plot = post('/farms/'+farm['id']+'/plots', dict(name='Imported plot', area_ha=1.23456789))
            season = post('/plots/'+plot['id']+'/seasons', dict(name='Imported season', start_date='2026-11-01'))
            before = sha256(source.read_bytes()).hexdigest()
            data = read(source)
            report = dict(images={}, archived_analyses=0)
            for _ in range(2):
                with repository(self.config) as repo:
                    migrate_core(repo, source, data, Path(directory)/'destination-uploads', report)
                    actual = repo.owned('farm_holdings', farm['id'], farm['user_id'])
                    self.assertEqual(actual, dict(farm, plot_count=1, area_ha=plot['area_ha'], plots_without_area=0))
                    total, rows = repo.holding_plots(farm['user_id'], farm['id'], 100, 0)
                    self.assertEqual(total, 1)
                    self.assertEqual(rows[0], plot)
                    self.assertEqual(repo.owned('farm_seasons', season['id'], season['user_id']), season)
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), before)

    def test_mobile_typescript_client_over_mysql_http(self):
        self.assertEqual(mobile_http.main(self.config), 0)

    def test_forecast_overview_can_page_all_owned_seasons(self):
        for owner in (0, 1):
            plot = self.call('/plots', 'POST', {'name': 'Overview plot'}, owner=owner).json['item']
            response = self.call('/plots/'+plot['id']+'/seasons', 'POST',
                                 dict(name='Overview season', start_date='2026-01-01'), owner=owner)
            self.assertEqual(response.status_code, 201)
        with repository(self.config) as repo:
            for owner in (0, 1):
                total, rows = repo.page('farm_seasons', 'user_id=?', (self.identifiers[owner],), 10, 0, None)
                self.assertEqual(total, 1)
                self.assertEqual(rows[0]['user_id'], self.identifiers[owner])


@unittest.skipUnless(os.environ.get('AEGIS_RUN_NATIVE_MYSQL_TESTS') == '1', 'native MySQL integration opt-in required')
class NativeFarmUpgradeTests(NativeDatabaseFixture, unittest.TestCase):
    schema_through = 4

    def test_additive_upgrade_keeps_existing_plot_and_season(self):
        owner, plot_id, season_id = (str(uuid.uuid4()) for _ in range(3))
        config = dict(STORAGE_BACKEND='mysql', MYSQL=self.mysql)
        stamp = '2026-11-09T00:00:00+00:00'
        with repository(config) as repo:
            repo.add_user(owner, 'upgrade@example.test', 'unchanged-hash', 1794182400)
            user = repo.uid(owner)
            farm = repo.execute("INSERT INTO farms(owner_user_id,farm_name) VALUES (%s,'API default farm')", (user,)).lastrowid
            repo.execute('INSERT INTO owner_default_farms VALUES (%s,%s)', (user, farm))
            repo.execute('''INSERT INTO farm_fields(external_id,farm_id,user_id,field_name,crop_type,location_text,api_created_at,area_ha)
                VALUES (%s,%s,%s,'Existing plot','rice','Old location',%s,2.5)''', (plot_id,farm,user,stamp))
            repo.add_season(dict(id=season_id,user_id=owner,plot_id=plot_id,name='Existing season',crop='rice',
                                start_date='2026-01-01',end_date=None,created_at=stamp))
            plot_before = repo.owned('farm_plots',plot_id,owner)
            season_before = repo.owned('farm_seasons',season_id,owner)
        with pymysql.connect(**dict(self.admin,database=self.database),autocommit=True,
                             client_flag=CLIENT.MULTI_STATEMENTS) as connection:
            apply_schema(connection)
            apply_schema(connection)
        with repository(config) as repo:
            self.assertEqual(repo.owned('farm_plots',plot_id,owner),plot_before)
            self.assertEqual(repo.owned('farm_seasons',season_id,owner),season_before)
            total, farms = repo.page('farm_holdings','user_id=?',(owner,),100,0,None)
            self.assertEqual(total,1)
            self.assertEqual(farms[0]['name'],'Nông trại của tôi')
            self.assertEqual(farms[0]['area_ha'],2.5)
            self.assertEqual(farms[0]['plot_count'],1)
            self.assertTrue(farms[0]['id'])
            self.assertEqual(repo.one('SELECT status FROM schema_versions WHERE version=5')['status'],'complete')


if __name__ == '__main__':
    unittest.main()
