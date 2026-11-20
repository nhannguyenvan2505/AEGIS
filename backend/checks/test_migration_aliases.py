"""Account collisions must retain identities and source bytes during opt-in import."""
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'database'), str(Path(__file__).resolve().parents[1])]
from migrate_sqlite import rename_demo_duplicates


class MigrationAliasTests(unittest.TestCase):
    def test_duplicate_demo_emails_keep_uuid_password_and_ownership(self):
        mobile = Path('backend/instance/aegis.sqlite3')
        demo = Path('pilot_data/forecast-midterm/demo.db')
        smoke = Path('pilot_data/smoke/demo.db')
        def user(identifier, email):
            return dict(id=identifier,email=email,password_hash='original-'+identifier)
        original = {
            smoke: dict(users=[user('cccccccc-0000-0000-0000-000000000000','midterm@example.test')]),
            demo: dict(users=[user('bbbbbbbb-0000-0000-0000-000000000000','owner@example.test'),
                              user('dddddddd-0000-0000-0000-000000000000','midterm@example.test')],
                       farm_plots=[dict(id='plot-id',user_id='bbbbbbbb-0000-0000-0000-000000000000')]),
            mobile: dict(users=[user('aaaaaaaa-0000-0000-0000-000000000000','owner@example.test')]),
        }
        changed, aliases = rename_demo_duplicates(original)
        self.assertEqual(len(aliases),2)
        self.assertEqual(changed[mobile]['users'],original[mobile]['users'])
        self.assertEqual(changed[demo]['farm_plots'],original[demo]['farm_plots'])
        self.assertEqual(changed[demo]['users'][0]['id'],original[demo]['users'][0]['id'])
        self.assertEqual(changed[demo]['users'][0]['password_hash'],original[demo]['users'][0]['password_hash'])
        self.assertEqual(original[demo]['users'][0]['email'],'owner@example.test')
        self.assertEqual(changed[demo]['users'][0]['email'],'owner+demo-bbbbbbbb@example.test')
        self.assertEqual(changed[demo]['users'][1]['email'],'midterm@example.test')
        self.assertEqual(rename_demo_duplicates(original),(changed,aliases))

    def test_alias_collision_refuses_silent_reassignment(self):
        sources = {
            Path('backend/instance/aegis.sqlite3'): dict(users=[dict(id='first',email='a@example.test'),
                                                            dict(id='third',email='a+demo-second@example.test')]),
            Path('pilot_data/forecast-midterm/demo.db'): dict(users=[dict(id='second',email='a@example.test')]),
        }
        with self.assertRaises(RuntimeError):
            rename_demo_duplicates(sources)


if __name__ == '__main__':
    unittest.main()
