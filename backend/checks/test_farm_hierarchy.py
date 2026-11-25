"""Owned farm -> plot -> season CRUD and additive migration regressions."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect


class FarmHierarchyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root/'test.db', UPLOAD_DIR=root/'uploads', FARM_WRITE_LIMIT=500)
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.headers = []
        for email in ('farms@example.test', 'other-farms@example.test'):
            credentials = dict(email=email, password='Farm-test-password-123')
            self.client.post('/api/auth/register', json=credentials)
            token = self.client.post('/api/auth/login', json=credentials).json['access_token']
            self.headers.append({'Authorization': 'Bearer ' + token})

    def call(self, path, method='GET', data=None, owner=0):
        return self.client.open('/api/farm'+path, method=method, json=data, headers=self.headers[owner])

    def create(self, **changes):
        response = self.call('/farms', 'POST', dict(name='An Bình', address='Long Tuyền, Bình Thủy, Cần Thơ', manager='Nguyễn Văn Minh', notes='Theo dõi mực nước.', **changes))
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['item']

    def test_empty_create_edit_delete_and_restart(self):
        self.assertEqual(self.call('/farms').json['items'], [])
        item = self.create()
        path = '/farms/'+item['id']
        self.assertEqual(item['plot_count'], 0)
        self.assertEqual(item['area_ha'], 0)
        changed = self.call(path, 'PUT', dict(name='An Bình mới', address='Cần Thơ', manager='', notes='', version=1))
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json['item']['version'], 2)
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/api/farm'+path, headers=self.headers[0]).json['item']['name'], 'An Bình mới')
        self.assertEqual(self.call(path, 'DELETE', {'version': 2}).status_code, 200)
        self.assertEqual(self.call(path).status_code, 404)

    def test_chain_totals_and_nonempty_delete_are_atomic(self):
        item = self.create()
        path = '/farms/'+item['id']
        for size in (1.2, 2.6, None):
            response = self.call(path+'/plots', 'POST', dict(name='Ruộng', area_ha=size))
            self.assertEqual(response.status_code, 201, response.json)
        plot = response.json['item']
        season = self.call('/plots/'+plot['id']+'/seasons', 'POST', dict(name='Đông xuân', start_date='2026-11-01'))
        self.assertEqual(season.status_code, 201)
        totals = self.call(path).json['item']
        self.assertEqual(totals['plot_count'], 3)
        self.assertAlmostEqual(totals['area_ha'], 3.8)
        self.assertEqual(totals['plots_without_area'], 1)
        self.assertEqual(self.call(path, 'DELETE', {'version': 1}).json['error']['code'], 'farm_not_empty')
        self.assertEqual(self.call(path+'/plots').json['pagination']['total'], 3)
        self.assertEqual(self.call('/plots/'+plot['id']+'/seasons').json['items'][0]['id'], season.json['item']['id'])

    def test_owner_isolation_and_cross_owner_attachment(self):
        farm = self.create()
        path = '/farms/'+farm['id']
        for method, suffix, data in [('GET', '', None), ('PUT', '', dict(name='Other', address='Other', version=1)),
                                     ('DELETE', '', {'version': 1}), ('GET', '/plots', None), ('POST', '/plots', {'name': 'Other'})]:
            self.assertEqual(self.call(path+suffix, method, data, owner=1).status_code, 404)
        self.assertEqual(self.call('/plots', 'POST', {'name': 'Other', 'farm_id': farm['id']}, owner=1).status_code, 404)
        self.assertEqual(self.call('/farms', owner=1).json['pagination']['total'], 0)
        self.assertEqual(self.call('/plots', owner=1).json['pagination']['total'], 0)

    def test_stale_edit_and_delete_do_not_overwrite(self):
        farm = self.create()
        path = '/farms/'+farm['id']
        data = dict(name='Updated', address='Cần Thơ', version=1)
        self.assertEqual(self.call(path, 'PUT', data).status_code, 200)
        self.assertEqual(self.call(path, 'PUT', data).status_code, 409)
        self.assertEqual(self.call(path, 'DELETE', {'version': 1}).status_code, 409)
        self.assertEqual(self.call(path).json['item']['name'], 'Updated')

    def test_input_boundaries_and_pagination(self):
        for data in ({'name': '', 'address': 'A'}, {'name': 'A', 'address': ' '},
                     {'name': 'A', 'address': 'A', 'user_id': 'spoof'}, {'name': 'A', 'address': 'A', 'notes': 'x'*1001}):
            self.assertEqual(self.call('/farms', 'POST', data).status_code, 400)
        farm = self.create()
        for size in (-1, 0, True, '2.4', float('inf'), float('nan'), 1000001):
            self.assertEqual(self.call('/farms/'+farm['id']+'/plots', 'POST', dict(name='Invalid', area_ha=size)).status_code, 400)
        self.assertEqual(self.call('/farms/'+farm['id']).json['item']['plot_count'], 0)
        self.assertEqual(self.call('/farms?page_size=0').status_code, 400)
        response = self.call('/farms?page=1&page_size=1')
        self.assertEqual(response.json['pagination']['total'], 1)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertIn('Authorization', response.headers['Vary'])

    def test_legacy_plot_creation_stays_compatible(self):
        plot = self.call('/plots', 'POST', {'name': 'Ruộng cũ', 'location_text': 'Vị trí'}).json['item']
        farm = self.call('/farms').json['items'][0]
        self.assertEqual(farm['name'], 'Nông trại của tôi')
        self.assertEqual(farm['plot_count'], 1)
        self.assertEqual(self.call('/plots').json['items'][0]['id'], plot['id'])
        self.assertEqual(self.call('/farms/'+farm['id']+'/plots').json['items'][0]['id'], plot['id'])

    def test_upgrade_backfills_legacy_plots_without_changing_seasons(self):
        plot = self.call('/plots', 'POST', {'name': 'Legacy'}).json['item']
        season = self.call('/plots/'+plot['id']+'/seasons', 'POST', dict(name='Legacy season', start_date='2026-01-01')).json['item']
        with connect(self.config) as db:
            db.execute('DROP TABLE farm_plot_memberships')
            db.execute('DROP TABLE farm_holdings')
            db.execute('DROP TABLE farm_hierarchy_meta')
        restarted = create_app(self.config).test_client()
        farms = restarted.get('/api/farm/farms', headers=self.headers[0]).json['items']
        self.assertEqual(len(farms), 1)
        self.assertEqual(farms[0]['plot_count'], 1)
        self.assertEqual(restarted.get('/api/farm/plots/'+plot['id']+'/seasons', headers=self.headers[0]).json['items'][0], season)
        create_app(self.config)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farm_holdings').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farm_plot_memberships').fetchone()[0], 1)
            self.assertEqual({row[0] for row in db.execute('SELECT version FROM schema_migrations')}, {1,2,3,4,5,6,7})
            self.assertEqual(db.execute('SELECT version FROM farm_hierarchy_meta WHERE id=1').fetchone()[0], 1)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_development_marker_upgrade_preserves_farm_memberships(self):
        farm = self.create()
        plot = self.call('/farms/'+farm['id']+'/plots', 'POST', dict(name='Existing plot', area_ha=2.4)).json['item']
        with connect(self.config) as db:
            db.execute('DROP TABLE farm_hierarchy_meta')
            # Version 6 now belongs to the role migration; reuse its row as the old marker.
            db.execute("UPDATE schema_migrations SET name='owned_farm_hierarchy' WHERE version=6")
        restarted = create_app(self.config).test_client()
        result = restarted.get('/api/farm/farms/'+farm['id']+'/plots', headers=self.headers[0])
        self.assertEqual(result.json['items'][0], plot)
        with connect(self.config) as db:
            self.assertEqual({row[0] for row in db.execute('SELECT version FROM schema_migrations')}, {1,2,3,4,5,6,7})
            self.assertEqual(db.execute('SELECT version FROM farm_hierarchy_meta WHERE id=1').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT name FROM schema_migrations WHERE version=6').fetchone()[0], 'user_roles_and_status')


if __name__ == '__main__':
    unittest.main()
