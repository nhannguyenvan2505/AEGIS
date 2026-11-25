"""Core persistence facade. One analysis owns zero or more detections."""
from contextlib import contextmanager
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .migrations import apply_migrations
from .repositories import repository


@contextmanager
def connect(config):
    if config.get('STORAGE_BACKEND', 'sqlite') == 'mysql':
        from .hybrid_pilot import PilotConnection
        from .repositories.mysql import mysql_repository
        with mysql_repository(config) as repo:
            yield PilotConnection(repo.connection,config,'','core')
        return
    if config.get('STORAGE_BACKEND', 'sqlite') != 'sqlite':
        raise ValueError('Unknown storage backend')
    connection = sqlite3.connect(str(config['DATABASE_PATH']), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_storage(config):
    if config.get('STORAGE_BACKEND', 'sqlite') == 'mysql':
        from .repositories.mysql import check_schema
        check_schema(config)
        Path(config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
        return
    if config.get('STORAGE_BACKEND', 'sqlite') != 'sqlite':
        raise ValueError('STORAGE_BACKEND must be sqlite or mysql')
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


DIAGNOSIS_COLUMNS = ('diagnosis_status', 'rice_probability', 'gatekeeper_method',
                     'gatekeeper_version', 'gatekeeper_sha256', 'uncertain_regions')


def diagnosis_columns(diagnosis):
    """Column values for an optional diagnosis record; all NULL when the AI gave none."""
    values = dict.fromkeys(DIAGNOSIS_COLUMNS)
    if diagnosis is not None:
        values.update({name: diagnosis.get(name) for name in DIAGNOSIS_COLUMNS})
        values['uncertain_regions'] = json.dumps(diagnosis.get('uncertain_regions') or [], allow_nan=False)
    return values


# FR09, decision D-07: every returned box says how far to trust it. Derived from the stored
# confidence when answering, so older analyses are labelled too and nothing new is persisted.
CONFIDENCE_LIKELY_FROM = 0.50
CONFIDENCE_LABELS = {'low': 'Low Confidence – Field Verification Required',
                     'likely': 'Khả năng cao – vẫn khuyến nghị kiểm tra ruộng'}


def with_confidence_level(detection):
    level = 'likely' if detection['confidence'] >= CONFIDENCE_LIKELY_FROM else 'low'
    return dict(detection, confidence_level=level, confidence_label=CONFIDENCE_LABELS[level])


# The message is not stored: for the three saved statuses the AI service sends a fixed sentence.
# This copy must match MESSAGES in ai_service/api/diagnosis.py (a test compares them).
DIAGNOSIS_MESSAGES = {
    'healthy': 'Không phát hiện vùng bệnh trên cây lúa ở ngưỡng hiện tại. Đây chưa phải xác nhận cây khỏe; hãy tiếp tục theo dõi.',
    'uncertain_lesion': 'Có dấu hiệu bất thường nhưng độ tin cậy chưa đạt ngưỡng kết luận bệnh. Cần kiểm tra thực địa hoặc chụp lại cận cảnh.',
    'disease_detected': 'Phát hiện vùng nghi bệnh trên cây lúa; cần xác minh thực địa.',
}


def with_saved_diagnosis(response, row):
    """Add the same `diagnosis` object the POST answered. Nothing is added when none was saved."""
    status = row['diagnosis_status']
    if status is None:  # /predict (v1) or stored before migration 008: unknown, never guessed
        return response
    return dict(response, diagnosis=dict(status=status, is_rice=True, message=DIAGNOSIS_MESSAGES[status]))


def save_analysis(payload, result, config, user_id, key_hash=None, diagnosis=None):
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
        for detection in result['detections']:
            detection['detection_id'] = str(uuid.uuid4())
        with repository(config) as db:
            db.save_analysis(dict(id=analysis_id,user_id=user_id,image_path=filename,
                image_width=image['width'],image_height=image['height'],orientation=image['orientation'],
                model_version=result['model_version'],status=result['status'],created_at=created_at,
                request_id=result['request_id'],model_sha256=result['model_sha256'],
                ai_processing_ms=result['timings']['ai_processing_ms'],
                ai_roundtrip_ms=result['timings']['ai_roundtrip_ms'],
                **diagnosis_columns(diagnosis)),result['detections'],key_hash,result)
    except (OSError, sqlite3.Error):
        # Normal failure compensation; crash consistency requires a later recovery job.
        if written:
            path.unlink(missing_ok=True)
        raise
    return dict(result, analysis_id=analysis_id, user_id=user_id, created_at=created_at,
                image_path=filename, image_url=f'/api/disease/analyses/{analysis_id}/image',
                detections=[with_confidence_level(d) for d in result['detections']])


def get_analysis(analysis_id, config, user_id):
    with repository(config) as db:
        analysis = db.owned('analyses', analysis_id, user_id)
        if analysis is None:
            return None
        rows = db.detections(analysis_id)
    response = dict(success=True, analysis_id=analysis['id'], user_id=analysis['user_id'],
                image_url=f'/api/disease/analyses/{analysis["id"]}/image',
                created_at=analysis['created_at'], image_path=analysis['image_path'],
                model_version=analysis['model_version'], status=analysis['status'],
                request_id=analysis['request_id'], model_sha256=analysis['model_sha256'],
                timings=dict(ai_processing_ms=analysis['ai_processing_ms'],ai_roundtrip_ms=analysis['ai_roundtrip_ms']),
                image=dict(width=analysis['image_width'], height=analysis['image_height'], orientation=analysis['orientation']),
                detections=[with_confidence_level(dict(
                    detection_id=r['id'], class_id=r['class_id'], disease=r['disease'], confidence=r['confidence'],
                    bbox=dict(x1=r['x1'], y1=r['y1'], x2=r['x2'], y2=r['y2']))) for r in rows])
    return with_saved_diagnosis(response, analysis)


def list_analyses(config, user_id, page, page_size):
    with repository(config) as db:
        db.begin()
        total, rows = db.analysis_page(user_id,page_size,(page-1)*page_size)
    pages = (total + page_size - 1) // page_size
    return dict(success=True, items=[with_saved_diagnosis(dict(analysis_id=r['id'], created_at=r['created_at'],
                model_version=r['model_version'], status=r['status'], detection_count=r['detection_count'],
                request_id=r['request_id'],model_sha256=r['model_sha256'],
                timings=dict(ai_processing_ms=r['ai_processing_ms'],ai_roundtrip_ms=r['ai_roundtrip_ms']),
                image=dict(width=r['image_width'], height=r['image_height'], orientation=r['orientation']),
                image_url=f'/api/disease/analyses/{r["id"]}/image'), r) for r in rows],
                pagination=dict(page=page, page_size=page_size, total=total, total_pages=pages,
                                has_next=page < pages))


def get_image_record(analysis_id, user_id, config):
    with repository(config) as db:
        return db.owned('analyses', analysis_id, user_id)
