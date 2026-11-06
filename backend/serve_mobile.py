"""Development API for mobile; keeps storage separate from pilot and default runtime."""
import argparse
import os
from pathlib import Path
import sys

from app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--pilot-dir', type=Path,
                        help='Opt in to pilot APIs in a named store below this checkout/pilot_data; creates marker if new')
    args = parser.parse_args()
    if args.pilot_dir is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
        from pilot_store import prepare_pilot, StoreLease
        from pilot_app import create_pilot_app
        storage = prepare_pilot(args.pilot_dir)
        # Same server lease as the reference launcher/backup. Never start the worker here.
        with StoreLease(storage):
            app = create_pilot_app(storage, os.environ.get('AEGIS_AI_URL', 'http://127.0.0.1:8000'))
            app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
        return
    root = Path(__file__).resolve().parent / 'mobile-instance'
    app = create_app({'DATABASE_PATH': root / 'aegis.sqlite3', 'UPLOAD_DIR': root / 'uploads'})
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
