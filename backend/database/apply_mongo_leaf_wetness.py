"""Add leaf_wet (bool) to the telemetry_readings validator of an existing MongoDB.

New databases get it from mongo/001_design.js. Idempotent; works for the Docker
and the native instance (same host/port/.env). Needs the Mongo root account
(aegis_root), because collMod is an administrative command:

    backend\.venv\Scripts\python.exe backend/database/apply_mongo_leaf_wetness.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402
from pymongo import MongoClient  # noqa: E402


def main():
    env = Path(__file__).with_name('.env')
    values = dict(line.split('=', 1) for line in env.read_text(encoding='utf-8-sig').splitlines()
                  if '=' in line and not line.lstrip().startswith('#'))
    mongo = settings()['MONGO']
    with MongoClient(host=mongo['host'], port=mongo['port'], username='aegis_root',
                     password=values['AEGIS_MONGO_ROOT_PASSWORD'], authSource='admin',
                     serverSelectionTimeoutMS=5000) as client:
        db = client[mongo['database']]
        info = db.command('listCollections', filter={'name': 'telemetry_readings'})['cursor']['firstBatch']
        if not info:
            raise SystemExit('telemetry_readings does not exist; initialise the database first')
        validator = info[0]['options']['validator']
        properties = validator['$jsonSchema']['properties']
        if properties.get('leaf_wet') == {'bsonType': 'bool'}:
            print('telemetry_readings already accepts leaf_wet')
            return
        properties['leaf_wet'] = {'bsonType': 'bool'}
        db.command('collMod', 'telemetry_readings', validator=validator,
                   validationLevel='strict', validationAction='error')
        print('telemetry_readings validator now accepts leaf_wet (bool)')


if __name__ == '__main__':
    main()
