"""Existing SQLite statements behind named domain operations."""
import math
import sqlite3


class SQLiteRepository:
    def __init__(self, db):
        self.db = db

    def begin(self, write=False):
        self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')

    def user_by_email(self, email):
        return self.db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()

    def add_user(self, identifier, email, password_hash, created_at):
        self.db.execute('INSERT INTO users(id,email,password_hash,created_at) VALUES (?,?,?,?)',
                        (identifier,email,password_hash,created_at))

    def session_user(self, token_hash, now):
        return self.db.execute('''SELECT users.id,users.email FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE token_hash=? AND expires_at>?''', (token_hash,now)).fetchone()

    def add_session(self, token_hash, user_id, expires_at, now):
        self.db.execute('DELETE FROM sessions WHERE expires_at<=?', (now,))
        self.db.execute('INSERT INTO sessions VALUES (?,?,?)', (token_hash,user_id,expires_at))

    def delete_session(self, token_hash):
        self.db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))

    def consume_limit(self, key, start, expires, limit, now, capacity):
        self.begin(True)
        self.db.execute('DELETE FROM rate_limit_buckets WHERE expires_at<=?', (now,))
        row = self.db.execute('SELECT request_count FROM rate_limit_buckets WHERE bucket_key=?', (key,)).fetchone()
        if row and row['request_count'] >= limit:
            return False, max(1, math.ceil(expires-now))
        if row:
            self.db.execute('UPDATE rate_limit_buckets SET request_count=request_count+1 WHERE bucket_key=?', (key,))
        else:
            if self.db.execute('SELECT COUNT(*) FROM rate_limit_buckets').fetchone()[0] >= capacity:
                raise sqlite3.OperationalError('Rate bucket capacity reached')
            self.db.execute('INSERT INTO rate_limit_buckets VALUES (?,?,?,?)', (key,start,1,expires))
        return True, 0

    def reserve(self, user_id, key_hash, payload_hash):
        self.begin(True)
        row = self.db.execute('SELECT * FROM inference_requests WHERE user_id=? AND key_hash=?', (user_id,key_hash)).fetchone()
        if row:
            return ('conflict' if row['payload_hash'] != payload_hash else row['state']),row['analysis_id']
        self.db.execute("INSERT INTO inference_requests VALUES (?,?,?,'running',NULL)", (user_id,key_hash,payload_hash))
        return 'new',None

    def mark_uncertain(self, user_id, key_hash):
        self.db.execute("UPDATE inference_requests SET state='uncertain' WHERE user_id=? AND key_hash=? AND state='running'", (user_id,key_hash))

    def owned(self, kind, identifier, user_id):
        return self.db.execute(f'SELECT * FROM {kind} WHERE id=? AND user_id=?', (identifier,user_id)).fetchone()

    def page(self, table, where, params, size, offset, order):
        # table/where/order originate only in the fixed route implementations.
        total = self.db.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}', params).fetchone()[0]
        rows = self.db.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?', (*params,size,offset)).fetchall()
        return total,rows

    def holding_summary(self, row):
        from ..farm_hierarchy import farm_summary
        return farm_summary(self.db, row)

    def add_holding(self, item):
        self.db.execute('''INSERT INTO farm_holdings
            (id,user_id,name,address,manager,notes,version,created_at,updated_at)
            VALUES (:id,:user_id,:name,:address,:manager,:notes,:version,:created_at,:updated_at)''', item)

    def update_holding(self, fields):
        self.db.execute('''UPDATE farm_holdings SET name=:name,address=:address,manager=:manager,
            notes=:notes,updated_at=:updated_at,version=version+1 WHERE id=:id AND user_id=:user_id''', fields)

    def delete_holding(self, identifier, user_id):
        self.db.execute('DELETE FROM farm_holdings WHERE id=? AND user_id=?', (identifier, user_id))

    def holding_plots(self, user_id, farm_id, size, offset):
        condition = 'p.user_id=? AND m.farm_id=? AND m.user_id=p.user_id'
        source = 'farm_plots p JOIN farm_plot_memberships m ON m.plot_id=p.id'
        total = self.db.execute(f'SELECT COUNT(*) FROM {source} WHERE {condition}', (user_id, farm_id)).fetchone()[0]
        rows = self.db.execute(f'''SELECT p.*,m.farm_id,m.area_ha FROM {source} WHERE {condition}
            ORDER BY p.created_at DESC,p.id DESC LIMIT ? OFFSET ?''', (user_id, farm_id, size, offset)).fetchall()
        return total, rows

    def add_plot(self, item, farm_id=None, area_ha=None):
        from ..farm_hierarchy import default_farm
        farm_id = farm_id or default_farm(self.db, item['user_id'], item['created_at'])
        self.db.execute('INSERT INTO farm_plots VALUES (:id,:user_id,:name,:location_text,:created_at)', item)
        self.db.execute('INSERT INTO farm_plot_memberships (plot_id,user_id,farm_id,area_ha) VALUES (?,?,?,?)',
                        (item['id'], item['user_id'], farm_id, area_ha))
        return dict(item, farm_id=farm_id, area_ha=area_ha)

    def plot_summary(self, row):
        membership = self.db.execute('SELECT farm_id,area_ha FROM farm_plot_memberships WHERE plot_id=? AND user_id=?',
                                      (row['id'],row['user_id'])).fetchone()
        return dict(row, farm_id=membership['farm_id'], area_ha=membership['area_ha'])

    def update_plot(self, fields):
        self.db.execute('UPDATE farm_plots SET name=?,location_text=? WHERE id=? AND user_id=?',
                        (fields['name'],fields['location_text'],fields['id'],fields['user_id']))
        self.db.execute('UPDATE farm_plot_memberships SET area_ha=? WHERE plot_id=? AND user_id=?',
                        (fields['area_ha'],fields['id'],fields['user_id']))

    def delete_plot(self, identifier, user_id):
        season = self.db.execute('SELECT 1 FROM farm_seasons WHERE plot_id=? AND user_id=? LIMIT 1',
                                 (identifier,user_id)).fetchone()
        if season:
            return False
        self.db.execute('DELETE FROM farm_plot_memberships WHERE plot_id=? AND user_id=?', (identifier,user_id))
        self.db.execute('DELETE FROM farm_plots WHERE id=? AND user_id=?', (identifier,user_id))
        return True

    def add_season(self, item):
        self.db.execute('INSERT INTO farm_seasons VALUES (:id,:user_id,:plot_id,:name,:crop,:start_date,:end_date,:created_at)', item)

    def device_code_exists(self, user_id, code):
        return self.db.execute('SELECT 1 FROM farm_devices WHERE user_id=? AND device_code=?', (user_id,code)).fetchone() is not None

    def add_device(self, item):
        self.db.execute('INSERT INTO farm_devices VALUES (:id,:user_id,:season_id,:name,:device_code,:source,:created_at)', item)

    def latest_profile(self, season_id, user_id):
        return self.db.execute('SELECT * FROM farm_cultivation_revisions WHERE season_id=? AND user_id=? ORDER BY revision DESC LIMIT 1', (season_id,user_id)).fetchone()

    def add_profile(self, values):
        self.db.execute('INSERT INTO farm_cultivation_revisions VALUES (?,?,?,?,?,?,?,?,?)', values)

    def reading(self, device_id, start_at):
        return self.db.execute('SELECT * FROM farm_telemetry WHERE device_id=? AND start_at=?', (device_id,start_at)).fetchone()

    def add_reading(self, values):
        self.db.execute('INSERT INTO farm_telemetry VALUES (?,?,?,?,?,?,?)', values)

    def readings(self, device_id, user_id, start, end):
        return self.db.execute('SELECT * FROM farm_telemetry WHERE device_id=? AND user_id=? AND start_at>=? AND start_at<? ORDER BY start_at', (device_id,user_id,start,end)).fetchall()

    def find_assessment(self, device_id, profile_hash, end):
        return self.db.execute('SELECT * FROM farm_assessments WHERE device_id=? AND profile_sha256=? AND window_end=?', (device_id,profile_hash,end)).fetchone()

    def add_assessment(self, values):
        self.db.execute('INSERT INTO farm_assessments VALUES (?,?,?,?,?,?,?,?)', values)

    def link_analysis(self, assessment_id, analysis_id, user_id, created_at):
        return self.db.execute('INSERT OR IGNORE INTO farm_assessment_analyses VALUES (?,?,?,?)', (assessment_id,analysis_id,user_id,created_at)).rowcount == 1

    def save_analysis(self, analysis, detections, key_hash, inference_result=None):
        columns = tuple(analysis)
        self.db.execute(f'INSERT INTO analyses ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(analysis.values()))
        for detection in detections:
            box = detection['bbox']
            self.db.execute('INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?)',
                (detection['detection_id'],analysis['id'],detection['class_id'],detection['disease'],detection['confidence'],box['x1'],box['y1'],box['x2'],box['y2']))
        if key_hash is not None:
            updated = self.db.execute("UPDATE inference_requests SET state='completed',analysis_id=? WHERE user_id=? AND key_hash=? AND state='running'", (analysis['id'],analysis['user_id'],key_hash))
            if updated.rowcount != 1:
                raise sqlite3.IntegrityError('Missing inference reservation')

    def detections(self, analysis_id):
        return self.db.execute('SELECT * FROM detections WHERE analysis_id=? ORDER BY rowid', (analysis_id,)).fetchall()

    def analysis_page(self, user_id, size, offset):
        total = self.db.execute('SELECT COUNT(*) FROM analyses WHERE user_id=?', (user_id,)).fetchone()[0]
        rows = self.db.execute('''SELECT a.*,(SELECT COUNT(*) FROM detections d WHERE d.analysis_id=a.id) detection_count
            FROM analyses a WHERE a.user_id=? ORDER BY a.created_at DESC,a.id DESC LIMIT ? OFFSET ?''', (user_id,size,offset)).fetchall()
        return total,rows
