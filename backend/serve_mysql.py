"""Run the core API against the isolated MySQL dev database."""
import argparse
import os
from pathlib import Path

from app import create_app


def read_environment(path):
    """Read simple KEY=value dev configuration without executing shell content."""
    values = {}
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        key, separator, value = raw.partition('=')
        if not separator:
            raise ValueError('Expected KEY=value in database environment file')
        values[key.strip()] = value.strip()
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument('--env-file',type=Path,default=root/'database'/'.env')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=5001)
    parser.add_argument('--uploads',type=Path,default=root/'mysql-instance'/'uploads')
    args = parser.parse_args()
    values = read_environment(args.env_file)
    def setting(key, default=None):
        return os.environ.get(key,values.get(key,default))
    password = setting('AEGIS_MYSQL_PASSWORD')
    if not password:
        parser.error('AEGIS_MYSQL_PASSWORD is required in environment or --env-file')
    app = create_app(dict(STORAGE_BACKEND='mysql',UPLOAD_DIR=args.uploads,
        MYSQL=dict(host=setting('AEGIS_MYSQL_HOST','127.0.0.1'),port=int(setting('AEGIS_MYSQL_PORT','3307')),
                   user=setting('AEGIS_MYSQL_USER','aegis_app'),password=password,
                   database=setting('AEGIS_MYSQL_DATABASE','aegis'))))
    app.run(host=args.host,port=args.port,debug=False,use_reloader=False)


if __name__ == '__main__':
    main()
