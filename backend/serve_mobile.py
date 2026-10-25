"""Development API for mobile; keeps storage separate from pilot and default runtime."""
import argparse
from pathlib import Path

from app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / 'mobile-instance'
    app = create_app({'DATABASE_PATH': root / 'aegis.sqlite3', 'UPLOAD_DIR': root / 'uploads'})
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
