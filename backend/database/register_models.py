"""Record the served model artifacts and their documented metrics in model_versions.

Artifacts are identified by the SHA-256 in each AI manifest, so rows that
inference already created are completed rather than duplicated. Metrics are
copied from project records (model_registry.json); nothing is measured here.

    python database/register_models.py             # add or complete the entries
    python database/register_models.py --activate  # also mark them active

Activation only sets a database flag; it does not change what the AI service loads.
"""
import argparse
import json
from pathlib import Path
import sys

import pymysql

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.database_config import settings  # noqa: E402

REGISTRY = Path(__file__).with_name('model_registry.json')


def load_entries(registry=REGISTRY, root=BACKEND.parent):
    entries = []
    for entry in json.loads(Path(registry).read_text(encoding='utf-8')):
        manifest = json.loads((Path(root) / entry['manifest']).read_text(encoding='utf-8'))
        entries.append(dict(entry, sha256=manifest['sha256'],
                            artifact_path=manifest['target']))
    return entries


def register(options, entries, *, activate=False):
    connection = pymysql.connect(**options, charset='utf8mb4', autocommit=False, connect_timeout=5)
    try:
        results = []
        with connection.cursor() as cursor:
            for entry in entries:
                cursor.execute('SELECT model_version_id FROM model_versions WHERE model_type=%s '
                               'AND artifact_sha256=%s FOR UPDATE', (entry['model_type'], entry['sha256']))
                row = cursor.fetchone()
                values = (entry['version_name'], entry['algorithm'], entry['training_dataset'],
                          json.dumps(entry['metrics']), entry['artifact_path'])
                if row:
                    cursor.execute('UPDATE model_versions SET version_name=%s, algorithm=%s, training_dataset=%s, '
                                   'metrics_json=%s, artifact_path=%s WHERE model_version_id=%s', (*values, row[0]))
                    identifier, action = row[0], 'updated'
                else:
                    cursor.execute('INSERT INTO model_versions(version_name,algorithm,training_dataset,metrics_json,'
                                   'artifact_path,model_type,artifact_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                                   (*values, entry['model_type'], entry['sha256']))
                    identifier, action = cursor.lastrowid, 'added'
                if activate:
                    cursor.execute('UPDATE model_versions SET is_active=FALSE WHERE model_type=%s',
                                   (entry['model_type'],))
                    cursor.execute('UPDATE model_versions SET is_active=TRUE WHERE model_version_id=%s', (identifier,))
                results.append(dict(model_type=entry['model_type'], version=entry['version_name'],
                                    action=action, active=activate))
        connection.commit()
        return results
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--activate', action='store_true', help='mark these versions as the active ones')
    args = parser.parse_args()
    for result in register(settings()['MYSQL'], load_entries(), activate=args.activate):
        print(json.dumps(result))


if __name__ == '__main__':
    main()
