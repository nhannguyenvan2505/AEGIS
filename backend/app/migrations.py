"""Additive SQLite migrations, inside the storage connection context."""
from datetime import datetime, timezone
from .farm_schema import apply_farm_migration
from .cultivation import apply_cultivation_migration
from .farm_hierarchy import apply_farm_hierarchy_migration

TRACE_COLUMNS = {'request_id': 'TEXT', 'model_sha256': 'TEXT',
                 'ai_processing_ms': 'REAL', 'ai_roundtrip_ms': 'REAL'}


def apply_migrations(db):
    db.execute('BEGIN IMMEDIATE')
    db.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)''')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(analyses)')}
    applied = db.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone()
    if applied and set(TRACE_COLUMNS) - columns:
        raise RuntimeError('Trace migration recorded but database columns are missing')
    if not applied:
        for name, sql_type in TRACE_COLUMNS.items():
            if name not in columns:
                db.execute(f'ALTER TABLE analyses ADD COLUMN {name} {sql_type}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_analyses_request_id ON analyses(request_id) WHERE request_id IS NOT NULL')
        db.execute('INSERT INTO schema_migrations VALUES (1,?,?)',
                   ('analysis_trace_metadata', datetime.now(timezone.utc).isoformat()))
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=2').fetchone():
        db.execute('''CREATE TABLE rate_limit_buckets (
            bucket_key TEXT PRIMARY KEY,window_start INTEGER NOT NULL,
            request_count INTEGER NOT NULL CHECK(request_count>0),expires_at INTEGER NOT NULL)''')
        db.execute('CREATE INDEX idx_rate_limit_expiry ON rate_limit_buckets(expires_at)')
        db.execute('INSERT INTO schema_migrations VALUES (2,?,?)',
                   ('shared_rate_limit_buckets', datetime.now(timezone.utc).isoformat()))
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=3').fetchone():
        db.execute('''CREATE TABLE inference_requests (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key_hash TEXT NOT NULL, payload_hash TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('running','completed','uncertain')),
            analysis_id TEXT REFERENCES analyses(id),
            PRIMARY KEY(user_id,key_hash))''')
        db.execute('INSERT INTO schema_migrations VALUES (3,?,?)',
                   ('inference_idempotency', datetime.now(timezone.utc).isoformat()))
    apply_farm_migration(db)
    apply_cultivation_migration(db)
    # Farm hierarchy first: it removes an old development marker stored as
    # schema_migrations version 6, which the role migration below now owns.
    apply_farm_hierarchy_migration(db)
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=6').fetchone():
        # Idempotent: a store upgraded from the old farm-hierarchy marker may
        # already have these columns/table.
        columns = {row[1] for row in db.execute('PRAGMA table_info(users)')}
        if 'role' not in columns:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'farmer' CHECK(role IN ('farmer','admin'))")
        if 'status' not in columns:
            db.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive','locked'))")
        db.execute('''CREATE TABLE IF NOT EXISTS role_audit (
            id INTEGER PRIMARY KEY, actor_id TEXT REFERENCES users(id),
            target_id TEXT NOT NULL REFERENCES users(id), old_role TEXT NOT NULL,
            new_role TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)''')
        db.execute('INSERT INTO schema_migrations VALUES (6,?,?)',
                   ('user_roles_and_status', datetime.now(timezone.utc).isoformat()))
