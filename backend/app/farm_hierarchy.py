"""Farm ownership and plot membership without changing legacy plot columns."""
import uuid
from datetime import datetime, timezone


def default_farm(db, user_id, created_at):
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, 'aegis:default-farm:' + user_id))
    db.execute('''INSERT OR IGNORE INTO farm_holdings
        (id,user_id,name,address,manager,notes,version,created_at,updated_at)
        VALUES (?,?,?,'','','',1,?,?)''',
        (identifier, user_id, 'Nông trại của tôi', created_at, created_at))
    return identifier


def apply_farm_hierarchy_migration(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='farm_hierarchy_meta'").fetchone()
    if exists:
        row = db.execute('SELECT version FROM farm_hierarchy_meta WHERE id=1').fetchone()
        if row is None or row['version'] != 1:
            raise RuntimeError('Unsupported farm hierarchy schema')
        return
    draft = db.execute("SELECT 1 FROM schema_migrations WHERE version=6 AND name='owned_farm_hierarchy'").fetchone()
    db.execute('''CREATE TABLE farm_hierarchy_meta (
        id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
        applied_at TEXT NOT NULL)''')
    if draft:
        # Upgrade the earlier development marker without rebuilding user records.
        db.execute('INSERT INTO farm_hierarchy_meta VALUES (1,1,?)', (datetime.now(timezone.utc).isoformat(),))
        db.execute("DELETE FROM schema_migrations WHERE version=6 AND name='owned_farm_hierarchy'")
        return
    db.execute('''CREATE TABLE farm_holdings (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        name TEXT NOT NULL, address TEXT NOT NULL, manager TEXT NOT NULL,
        notes TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(id,user_id))''')
    db.execute('''CREATE TABLE farm_plot_memberships (
        plot_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, farm_id TEXT NOT NULL,
        area_ha REAL CHECK(area_ha IS NULL OR (area_ha>0 AND area_ha<=1000000)),
        FOREIGN KEY(plot_id,user_id) REFERENCES farm_plots(id,user_id),
        FOREIGN KEY(farm_id,user_id) REFERENCES farm_holdings(id,user_id))''')
    db.execute('CREATE INDEX idx_holdings_owner ON farm_holdings(user_id,created_at,id)')
    db.execute('CREATE INDEX idx_memberships_farm ON farm_plot_memberships(user_id,farm_id,plot_id)')
    for owner in db.execute('SELECT DISTINCT user_id FROM farm_plots').fetchall():
        created_at = datetime.now(timezone.utc).isoformat()
        farm_id = default_farm(db, owner['user_id'], created_at)
        db.execute('''INSERT INTO farm_plot_memberships (plot_id,user_id,farm_id,area_ha)
            SELECT id,user_id,?,NULL FROM farm_plots WHERE user_id=?''',
            (farm_id, owner['user_id']))
    db.execute('INSERT INTO farm_hierarchy_meta VALUES (1,1,?)',
               (datetime.now(timezone.utc).isoformat(),))


def farm_summary(db, row):
    totals = db.execute('''SELECT COUNT(*) AS plot_count, COALESCE(SUM(area_ha),0) AS area_ha,
        COUNT(*)-COUNT(area_ha) AS plots_without_area FROM farm_plot_memberships
        WHERE farm_id=? AND user_id=?''', (row['id'], row['user_id'])).fetchone()
    return dict(row, **dict(totals))
