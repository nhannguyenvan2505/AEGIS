"""Local hybrid database settings; environment overrides the ignored dev file."""
import os
from pathlib import Path


def _reader():
    path = Path(__file__).resolve().parents[1]/'database'/'.env'
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, separator, value = line.partition('=')
                if separator: values[key.strip()] = value.strip()
    def get(key, default=None):
        return os.environ.get(key, values.get(key, default))
    return get


def migration_settings():
    """MySQL options for schema changes and backups.

    AEGIS_MYSQL_MIGRATION_USER / _PASSWORD let the running backend use an account
    without schema privileges; unset, migrations use the application account.
    """
    options = dict(settings()['MYSQL'])
    get = _reader()
    user = get('AEGIS_MYSQL_MIGRATION_USER')
    if user:
        options.update(user=user, password=get('AEGIS_MYSQL_MIGRATION_PASSWORD', ''))
    return options


def settings():
    get = _reader()
    return dict(
        MONGO_DELIVERY_ENABLED=get('AEGIS_MONGO_DELIVERY_ENABLED','1')=='1',
        MYSQL=dict(host=get('AEGIS_MYSQL_HOST','127.0.0.1'),port=int(get('AEGIS_MYSQL_PORT','3307')),
                   user=get('AEGIS_MYSQL_USER','aegis_app'),password=get('AEGIS_MYSQL_PASSWORD',''),database=get('AEGIS_MYSQL_DATABASE','aegis')),
        MONGO=dict(host=get('AEGIS_MONGO_HOST','127.0.0.1'),port=int(get('AEGIS_MONGO_PORT','27018')),
                   username=get('AEGIS_MONGO_USER','aegis_app'),password=get('AEGIS_MONGO_PASSWORD',''),
                   authSource=get('AEGIS_MONGO_DATABASE','aegis'),database=get('AEGIS_MONGO_DATABASE','aegis')),
    )
