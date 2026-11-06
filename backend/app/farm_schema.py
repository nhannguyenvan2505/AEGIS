"""Additive schema for owned farm context and immutable mock assessments."""
from datetime import datetime, timezone


def apply_farm_migration(db):
    if db.execute('SELECT 1 FROM schema_migrations WHERE version=4').fetchone():
        return
    statements = [
        '''CREATE TABLE farm_plots (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL, location_text TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(id,user_id))''',
        '''CREATE TABLE farm_seasons (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, plot_id TEXT NOT NULL,
            name TEXT NOT NULL, crop TEXT NOT NULL CHECK(crop='rice'),
            start_date TEXT NOT NULL, end_date TEXT,
            created_at TEXT NOT NULL, UNIQUE(id,user_id),
            CHECK(end_date IS NULL OR end_date>=start_date),
            FOREIGN KEY(plot_id,user_id) REFERENCES farm_plots(id,user_id))''',
        '''CREATE TABLE farm_devices (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, season_id TEXT NOT NULL,
            name TEXT NOT NULL, device_code TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source='mock'), created_at TEXT NOT NULL,
            UNIQUE(id,user_id), UNIQUE(user_id,device_code),
            FOREIGN KEY(season_id,user_id) REFERENCES farm_seasons(id,user_id))''',
        '''CREATE TABLE farm_telemetry (
            device_id TEXT NOT NULL, user_id TEXT NOT NULL, start_at TEXT NOT NULL,
            air_temperature_c REAL NOT NULL CHECK(air_temperature_c BETWEEN -50 AND 60),
            relative_humidity_pct REAL NOT NULL CHECK(relative_humidity_pct BETWEEN 0 AND 100),
            leaf_wet INTEGER NOT NULL CHECK(leaf_wet IN (0,1)), created_at TEXT NOT NULL,
            PRIMARY KEY(device_id,start_at),
            FOREIGN KEY(device_id,user_id) REFERENCES farm_devices(id,user_id))''',
        '''CREATE TABLE farm_assessments (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, device_id TEXT NOT NULL,
            profile_sha256 TEXT NOT NULL, window_end TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('advisory','no_pattern_detected','insufficient_data')),
            snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(id,user_id), UNIQUE(device_id,profile_sha256,window_end),
            FOREIGN KEY(device_id,user_id) REFERENCES farm_devices(id,user_id))''',
        'CREATE UNIQUE INDEX idx_analyses_owner_pair ON analyses(id,user_id)',
        '''CREATE TABLE farm_assessment_analyses (
            assessment_id TEXT NOT NULL, analysis_id TEXT NOT NULL, user_id TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY(assessment_id,analysis_id),
            FOREIGN KEY(assessment_id,user_id) REFERENCES farm_assessments(id,user_id),
            FOREIGN KEY(analysis_id,user_id) REFERENCES analyses(id,user_id))''',
        'CREATE INDEX idx_plots_owner ON farm_plots(user_id,created_at,id)',
        'CREATE INDEX idx_seasons_parent ON farm_seasons(user_id,plot_id,created_at,id)',
        'CREATE INDEX idx_devices_parent ON farm_devices(user_id,season_id,created_at,id)',
        'CREATE INDEX idx_assessments_owner ON farm_assessments(user_id,device_id,created_at,id)',
    ]
    # execute, not executescript: keep the caller's migration transaction atomic.
    for statement in statements:
        db.execute(statement)
    db.execute('INSERT INTO schema_migrations VALUES (4,?,?)',
               ('farm_mock_warning_mvp', datetime.now(timezone.utc).isoformat()))
