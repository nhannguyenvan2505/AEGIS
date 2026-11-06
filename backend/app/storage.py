"""Local SQLite persistence. One analysis owns zero or more detections."""
from contextlib import contextmanager
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .migrations import apply_migrations


@contextmanager
def connect(config):
    connection = sqlite3.connect(str(config['DATABASE_PATH']), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_storage(config):
    Path(config['DATABASE_PATH']).parent.mkdir(parents=True, exist_ok=True)
    Path(config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    with connect(config) as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                image_path TEXT NOT NULL UNIQUE,
                image_width INTEGER NOT NULL CHECK(image_width > 0),
                image_height INTEGER NOT NULL CHECK(image_height > 0),
                orientation TEXT NOT NULL,
                model_version TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('detection_found', 'no_detection')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS detections (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                class_id INTEGER NOT NULL CHECK(class_id IN (0,1,2)),
                disease TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                x1 REAL NOT NULL, y1 REAL NOT NULL,
                x2 REAL NOT NULL, y2 REAL NOT NULL,
                CHECK(x1 >= 0 AND y1 >= 0 AND x2 > x1 AND y2 > y1)
            );
            CREATE INDEX IF NOT EXISTS idx_detections_analysis ON detections(analysis_id);
            CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at);
            CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id);
            CREATE INDEX IF NOT EXISTS idx_analyses_user_created ON analyses(user_id, created_at DESC, id DESC);
            CREATE TRIGGER IF NOT EXISTS analyses_require_user
            BEFORE INSERT ON analyses
            WHEN NEW.user_id IS NULL OR NOT EXISTS (SELECT 1 FROM users WHERE id=NEW.user_id)
            BEGIN SELECT RAISE(ABORT, 'valid user required'); END;
        ''')
        apply_migrations(db)


def save_analysis(payload, result, config, user_id, key_hash=None):
    analysis_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    # Preserve original bytes privately; bbox coordinates use EXIF-corrected dimensions.
    filename = analysis_id + '.bin'
    path = Path(config['UPLOAD_DIR']) / filename
    image = result['image']
    written = False
    try:
        with path.open('xb') as stream:
            written = True
            stream.write(payload)
        with connect(config) as db:
            db.execute('''INSERT INTO analyses
                       (id,user_id,image_path,image_width,image_height,orientation,model_version,status,created_at,
                        request_id,model_sha256,ai_processing_ms,ai_roundtrip_ms)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (analysis_id, user_id, filename, image['width'], image['height'],
                        image['orientation'], result['model_version'], result['status'], created_at,
                        result['request_id'], result['model_sha256'], result['timings']['ai_processing_ms'],
                        result['timings']['ai_roundtrip_ms']))
            for detection in result['detections']:
                detection_id = str(uuid.uuid4())
                box = detection['bbox']
                db.execute('INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?)',
                           (detection_id, analysis_id, detection['class_id'], detection['disease'],
                            detection['confidence'], box['x1'], box['y1'], box['x2'], box['y2']))
                detection['detection_id'] = detection_id
            if key_hash is not None:
                updated = db.execute('''UPDATE inference_requests SET state='completed',analysis_id=?
                    WHERE user_id=? AND key_hash=? AND state='running' ''',
                    (analysis_id, user_id, key_hash))
                if updated.rowcount != 1:
                    raise sqlite3.IntegrityError('Missing inference reservation')
    except (OSError, sqlite3.Error):
        # Normal failure compensation; crash consistency requires a later recovery job.
        if written:
            path.unlink(missing_ok=True)
        raise
    return dict(result, analysis_id=analysis_id, user_id=user_id, created_at=created_at,
                image_path=filename, image_url=f'/api/disease/analyses/{analysis_id}/image')


def get_analysis(analysis_id, config, user_id):
    with connect(config) as db:
        analysis = db.execute('SELECT * FROM analyses WHERE id=? AND user_id=?', (analysis_id, user_id)).fetchone()
        if analysis is None:
            return None
        rows = db.execute('SELECT * FROM detections WHERE analysis_id=? ORDER BY rowid', (analysis_id,)).fetchall()
    return dict(success=True, analysis_id=analysis['id'], user_id=analysis['user_id'],
                image_url=f'/api/disease/analyses/{analysis["id"]}/image',
                created_at=analysis['created_at'], image_path=analysis['image_path'],
                model_version=analysis['model_version'], status=analysis['status'],
                request_id=analysis['request_id'], model_sha256=analysis['model_sha256'],
                timings=dict(ai_processing_ms=analysis['ai_processing_ms'],ai_roundtrip_ms=analysis['ai_roundtrip_ms']),
                image=dict(width=analysis['image_width'], height=analysis['image_height'], orientation=analysis['orientation']),
                detections=[dict(detection_id=r['id'], class_id=r['class_id'], disease=r['disease'], confidence=r['confidence'],
                                 bbox=dict(x1=r['x1'], y1=r['y1'], x2=r['x2'], y2=r['y2'])) for r in rows])


def list_analyses(config, user_id, page, page_size):
    with connect(config) as db:
        # Keep count and page in the same SQLite read snapshot.
        db.execute('BEGIN')
        total = db.execute('SELECT COUNT(*) FROM analyses WHERE user_id=?', (user_id,)).fetchone()[0]
        rows = db.execute('''SELECT a.*, (SELECT COUNT(*) FROM detections d WHERE d.analysis_id=a.id) AS detection_count
            FROM analyses a WHERE a.user_id=? ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?''',
                          (user_id, page_size, (page-1)*page_size)).fetchall()
    pages = (total + page_size - 1) // page_size
    return dict(success=True, items=[dict(analysis_id=r['id'], created_at=r['created_at'],
                model_version=r['model_version'], status=r['status'], detection_count=r['detection_count'],
                request_id=r['request_id'],model_sha256=r['model_sha256'],
                timings=dict(ai_processing_ms=r['ai_processing_ms'],ai_roundtrip_ms=r['ai_roundtrip_ms']),
                image=dict(width=r['image_width'], height=r['image_height'], orientation=r['orientation']),
                image_url=f'/api/disease/analyses/{r["id"]}/image') for r in rows],
                pagination=dict(page=page, page_size=page_size, total=total, total_pages=pages,
                                has_next=page < pages))


def get_image_record(analysis_id, user_id, config):
    with connect(config) as db:
        return db.execute('SELECT image_path FROM analyses WHERE id=? AND user_id=?',
                          (analysis_id, user_id)).fetchone()
