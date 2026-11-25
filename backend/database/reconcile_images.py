"""Compare uploaded images with the database. Read-only: nothing is moved or deleted.

  missing  a row refers to an image that is not in the upload directory
  orphans  a file no row refers to (recent files are skipped: an upload is written
           to disk just before its rows commit)

Images of records archived by the SQLite import have no crop_images row and are
listed as orphans, so review the list before removing anything by hand.
Exit status is 1 when images are missing.

    python database/reconcile_images.py --uploads backend/mysql-instance/uploads
"""
import argparse
import json
from pathlib import Path
import sys
import time

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402

IN_FLIGHT_MINUTES = 60


def reconcile(options, uploads, *, min_age_minutes=IN_FLIGHT_MINUTES, now=None):
    uploads = Path(uploads)
    if not uploads.is_dir():
        raise FileNotFoundError(f'Image directory not found: {uploads}')
    # List files first: a row committed after this listing cannot turn its file into an orphan.
    files = {path.name: path.stat() for path in uploads.iterdir() if path.is_file()}
    connection = pymysql.connect(**options, charset='utf8mb4', autocommit=True, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT image_url FROM crop_images')
            referenced = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()
    cutoff = (time.time() if now is None else now) - min_age_minutes * 60
    missing = sorted(name for name in referenced - set(files) if not (uploads / name).is_file())
    unknown = set(files) - referenced
    orphans = sorted(name for name in unknown if files[name].st_mtime <= cutoff)
    return dict(referenced=len(referenced), files=len(files), missing=missing, orphans=orphans,
                orphan_bytes=sum(files[name].st_size for name in orphans),
                skipped_recent=len(unknown) - len(orphans))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--uploads', type=Path, required=True)
    parser.add_argument('--min-age-minutes', type=int, default=IN_FLIGHT_MINUTES)
    args = parser.parse_args()
    try:
        result = reconcile(settings()['MYSQL'], args.uploads, min_age_minutes=args.min_age_minutes)
    except (FileNotFoundError, pymysql.Error) as exc:
        sys.exit(f'ERROR: {exc}')
    print(json.dumps(result, indent=2))
    sys.exit(1 if result['missing'] else 0)


if __name__ == '__main__':
    main()
