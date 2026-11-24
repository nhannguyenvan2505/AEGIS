"""MySQL domain operations against the documented schema and runtime extensions.

The compatibility lock serializes core transactions across processes. This is
deliberately conservative during migration; no lock spans HTTP inference calls.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import sqlite3
import uuid


def open_connection(config):
    import pymysql
    options = dict(config.get('MYSQL', {}))
    required = ('host','port','user','password','database')
    if any(key not in options or options[key] in ('', None) for key in required):
        raise ValueError('MYSQL requires host, port, user, password and database')
    return pymysql.connect(**options, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                           autocommit=False, connect_timeout=5, read_timeout=15, write_timeout=15,
                           init_command="SET time_zone='+00:00', innodb_lock_wait_timeout=5")


@contextmanager
def mysql_repository(config):
    import pymysql
    connection = None
    try:
        connection = open_connection(config)
        connection.begin()
        repo = MySQLRepository(connection)
        if repo.one('SELECT id FROM runtime_lock WHERE id=1 FOR UPDATE') is None:
            raise sqlite3.OperationalError('Runtime compatibility lock missing')
        yield repo
        connection.commit()
    except BaseException as exc:
        if connection is not None:
            try:
                connection.rollback()
            except pymysql.Error:
                pass  # Preserve the original failure if the connection was lost.
        if isinstance(exc, pymysql.IntegrityError):
            raise sqlite3.IntegrityError(*exc.args) from None
        if isinstance(exc, pymysql.Error):
            raise sqlite3.OperationalError(*exc.args) from None
        raise
    finally:
        if connection is not None:
            connection.close()


def check_schema(config):
    with mysql_repository(config) as repo:
        row = repo.one('SELECT status FROM schema_versions WHERE version=2')
        if not row or row['status'] != 'complete':
            raise RuntimeError('Apply MySQL migration 002_core_runtime.sql before selecting mysql')
        row=repo.one('SELECT status FROM schema_versions WHERE version=3')
        if not row or row['status']!='complete':
            raise RuntimeError('Apply MySQL migration 003_hybrid.sql before selecting mysql')
        row=repo.one('SELECT status FROM schema_versions WHERE version=4')
        if not row or row['status']!='complete':
            raise RuntimeError('Apply MySQL migration 004_api_semantics.sql before selecting mysql')
        row=repo.one('SELECT status FROM schema_versions WHERE version=5')
        if not row or row['status']!='complete':
            raise RuntimeError('Apply MySQL migration 005_farm_hierarchy.sql before selecting mysql')


# Projections expose exactly the UUID/ISO strings expected by the existing API.
PROJECTIONS = {
 'farm_holdings': ('''h.external_id id,u.external_id user_id,h.farm_name name,
                    COALESCE(h.address,'') address,h.manager,COALESCE(h.description,'') notes,
                    h.version,h.api_created_at created_at,h.api_updated_at updated_at,
                    (SELECT COUNT(*) FROM farm_fields p WHERE p.farm_id=h.farm_id AND p.user_id=h.owner_user_id) plot_count,
                    (SELECT COALESCE(SUM(p.area_ha),0) FROM farm_fields p WHERE p.farm_id=h.farm_id AND p.user_id=h.owner_user_id) area_ha,
                    (SELECT COUNT(*) FROM farm_fields p WHERE p.farm_id=h.farm_id AND p.user_id=h.owner_user_id AND p.area_ha IS NULL) plots_without_area''',
                    'farms h JOIN users u ON u.user_id=h.owner_user_id','h.farm_id','h.external_id','u.external_id'),
 'farm_plots': ('''f.external_id id,u.external_id user_id,f.field_name name,f.location_text,
                  f.api_created_at created_at''', 'farm_fields f JOIN users u ON u.user_id=f.user_id', 'f.field_id', 'f.external_id', 'u.external_id'),
 'farm_seasons': ('''c.external_id id,u.external_id user_id,f.external_id plot_id,c.name,c.crop_type crop,
                    DATE_FORMAT(c.start_date,'%%Y-%%m-%%d') start_date,DATE_FORMAT(c.expected_end_date,'%%Y-%%m-%%d') end_date,
                    c.api_created_at created_at''', 'crop_cycles c JOIN farm_fields f ON f.field_id=c.field_id JOIN users u ON u.user_id=c.user_id', 'c.crop_cycle_id', 'c.external_id', 'u.external_id'),
 'farm_devices': ('''d.external_id id,u.external_id user_id,c.external_id season_id,d.device_name name,
                    d.device_code,d.source,d.api_created_at created_at''', "iot_devices d JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id AND d.source='mock' JOIN users u ON u.user_id=d.user_id", 'd.device_id','d.external_id','u.external_id'),
 'farm_telemetry': ('''d.external_id device_id,u.external_id user_id,t.start_at,t.air_temperature_c,t.relative_humidity_pct,
                      t.leaf_wet,t.created_at''', 'mock_hourly_readings t JOIN iot_devices d ON d.device_id=t.device_id JOIN users u ON u.user_id=t.user_id', None,None,'u.external_id'),
 'farm_assessments': ('''a.external_id id,u.external_id user_id,d.external_id device_id,a.profile_sha256,
                        a.window_end,a.status,a.snapshot_json,a.created_at''', 'mock_assessments a JOIN iot_devices d ON d.device_id=a.device_id JOIN users u ON u.user_id=a.user_id','a.assessment_id','a.external_id','u.external_id'),
 'farm_cultivation_revisions': ('''r.id,c.external_id season_id,u.external_id user_id,r.revision,r.profile_json,
                                 r.profile_sha256,r.change_reason,r.created_at,r.request_id''', 'cultivation_revisions r JOIN crop_cycles c ON c.crop_cycle_id=r.crop_cycle_id JOIN users u ON u.user_id=r.user_id', None,'r.id','u.external_id'),
 'analyses': ('''a.external_id id,u.external_id user_id,i.image_url image_path,i.image_width,i.image_height,i.orientation,
                a.model_version,a.status,a.created_at,a.request_id,a.model_sha256,a.ai_processing_ms,a.ai_roundtrip_ms,
                (SELECT COUNT(*) FROM disease_detections dd WHERE dd.analysis_id=a.analysis_id) detection_count''', 'analysis_runs a JOIN crop_images i ON i.image_id=a.image_id JOIN users u ON u.user_id=a.user_id','a.analysis_id','a.external_id','u.external_id'),
}


class MySQLRepository:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        import pymysql
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params)
        except pymysql.IntegrityError as exc:
            cursor.close()
            raise sqlite3.IntegrityError(*exc.args) from None
        except pymysql.Error as exc:
            cursor.close()
            raise sqlite3.OperationalError(*exc.args) from None
        return cursor

    def one(self, sql, params=()):
        with self.execute(sql, params) as cursor:
            return cursor.fetchone()

    def all(self, sql, params=()):
        with self.execute(sql, params) as cursor:
            return cursor.fetchall()

    def begin(self, write=False):
        # The context already began and acquired the compatibility lock.
        pass

    def uid(self, external):
        row = self.one('SELECT user_id FROM users WHERE external_id=%s', (external,))
        if not row:
            raise sqlite3.IntegrityError('Unknown user identifier')
        return row['user_id']

    def pk(self, kind, external, user_id=None):
        _, source, primary, external_column, owner_column = PROJECTIONS[kind]
        sql = f'SELECT {primary} pk FROM {source} WHERE {external_column}=%s'
        params = (external,)
        if user_id is not None:
            sql += f' AND {owner_column}=%s'
            params += (user_id,)
        row = self.one(sql, params)
        if not row:
            raise sqlite3.IntegrityError('Unknown or differently owned resource')
        return row['pk']

    def user_by_email(self, email):
        return self.one("""SELECT u.external_id id,u.email,u.password_hash,r.role_name role
            FROM users u JOIN roles r ON r.role_id=u.role_id WHERE u.email=%s AND u.status='active'""", (email,))

    def add_user(self, identifier, email, password_hash, created_at):
        if not self.one("SELECT role_id FROM roles WHERE role_name='farmer'"):
            raise sqlite3.OperationalError('Missing farmer role seed')
        self.execute('''INSERT INTO users(external_id,role_id,email,username,password_hash,created_at)
            SELECT %s,role_id,%s,%s,%s,%s FROM roles WHERE role_name='farmer' ''',
            (identifier,email,identifier,password_hash,datetime.fromtimestamp(created_at,timezone.utc).replace(tzinfo=None)))

    def session_user(self, token_hash, now):
        return self.one('''SELECT u.external_id id,u.email,r.role_name role FROM sessions s JOIN users u ON u.user_id=s.user_id
            JOIN roles r ON r.role_id=u.role_id
            WHERE s.token_hash=%s AND s.expires_at>%s AND u.status='active' ''', (token_hash,now))

    def admin_users(self, size, offset):
        total = self.one('SELECT COUNT(*) n FROM users')['n']
        rows = self.all('''SELECT u.external_id id,u.email,r.role_name role,u.status FROM users u
            JOIN roles r ON r.role_id=u.role_id ORDER BY u.external_id LIMIT %s OFFSET %s''', (size, offset))
        return total, rows

    def role_user(self, identifier):
        return self.one('''SELECT u.external_id id,u.email,r.role_name role,u.status FROM users u
            JOIN roles r ON r.role_id=u.role_id WHERE u.external_id=%s''', (identifier,))

    def active_admin_count(self):
        return self.one("""SELECT COUNT(*) n FROM users u JOIN roles r ON r.role_id=u.role_id
            WHERE r.role_name='admin' AND u.status='active'""")['n']

    def set_user_role(self, identifier, role, actor_id, reason, created_at):
        old = self.role_user(identifier)
        self.execute('UPDATE users SET role_id=(SELECT role_id FROM roles WHERE role_name=%s) WHERE external_id=%s',
                     (role, identifier))
        self.execute('''INSERT INTO audit_logs(user_id,action,entity_type,entity_id,details_json)
            VALUES (%s,'user_role_changed','user',%s,%s)''',
                     (self.uid(actor_id) if actor_id else None, identifier,
                      json.dumps(dict(old_role=old['role'],new_role=role,reason=reason,recorded_at=created_at))))

    def add_session(self, token_hash, user_id, expires_at, now):
        self.execute('DELETE FROM sessions WHERE expires_at<=%s', (now,))
        self.execute('INSERT INTO sessions VALUES (%s,%s,%s)', (token_hash,self.uid(user_id),expires_at))
        self.execute('UPDATE users SET last_login_at=UTC_TIMESTAMP() WHERE external_id=%s', (user_id,))

    def delete_session(self, token_hash):
        self.execute('DELETE FROM sessions WHERE token_hash=%s', (token_hash,))

    def consume_limit(self, key, start, expires, limit, now, capacity):
        self.execute('DELETE FROM rate_limit_buckets WHERE expires_at<=%s', (now,))
        row = self.one('SELECT request_count FROM rate_limit_buckets WHERE bucket_key=%s', (key,))
        if row and row['request_count'] >= limit:
            return False,max(1,math.ceil(expires-now))
        if row:
            self.execute('UPDATE rate_limit_buckets SET request_count=request_count+1 WHERE bucket_key=%s', (key,))
        else:
            if self.one('SELECT COUNT(*) total FROM rate_limit_buckets')['total'] >= capacity:
                raise sqlite3.OperationalError('Rate bucket capacity reached')
            self.execute('INSERT INTO rate_limit_buckets VALUES (%s,%s,%s,%s)', (key,start,1,expires))
        return True,0

    def reserve(self, user_id, key_hash, payload_hash):
        numeric = self.uid(user_id)
        row = self.one('''SELECT r.*,a.external_id external_analysis FROM inference_requests r
            LEFT JOIN analysis_runs a ON a.analysis_id=r.analysis_id WHERE r.user_id=%s AND r.key_hash=%s''', (numeric,key_hash))
        if row:
            return ('conflict' if row['payload_hash'] != payload_hash else row['state']),row['external_analysis']
        self.execute("INSERT INTO inference_requests VALUES (%s,%s,%s,'running',NULL)", (numeric,key_hash,payload_hash))
        return 'new',None

    def mark_uncertain(self, user_id, key_hash):
        self.execute("UPDATE inference_requests SET state='uncertain' WHERE user_id=%s AND key_hash=%s AND state='running'", (self.uid(user_id),key_hash))

    def owned(self, kind, identifier, user_id):
        projection, source, _, external_column, owner_column = PROJECTIONS[kind]
        return self.one(f'SELECT {projection} FROM {source} WHERE {external_column}=%s AND {owner_column}=%s', (identifier,user_id))

    def page(self, table, where, params, size, offset, order):
        projection, source, _, _, _ = PROJECTIONS[table]
        # Fixed query mappings, never SQL supplied by a request.
        queries = {
          ('farm_holdings','user_id=?'): ('u.external_id=%s', 'h.api_created_at DESC,h.external_id DESC'),
          ('farm_plots','user_id=?'): ('u.external_id=%s', 'f.api_created_at DESC,f.external_id DESC'),
          ('farm_seasons','user_id=?'): ('u.external_id=%s', 'c.api_created_at DESC,c.external_id DESC'),
          ('farm_seasons','user_id=? AND plot_id=?'): ('u.external_id=%s AND f.external_id=%s', 'c.api_created_at DESC,c.external_id DESC'),
          ('farm_devices','user_id=? AND season_id=?'): ('u.external_id=%s AND c.external_id=%s', 'd.api_created_at DESC,d.external_id DESC'),
          ('farm_telemetry','device_id=? AND user_id=?'): ('d.external_id=%s AND u.external_id=%s', 't.start_at DESC'),
          ('farm_assessments','device_id=? AND user_id=?'): ('d.external_id=%s AND u.external_id=%s','a.created_at DESC,a.external_id DESC'),
          ('farm_cultivation_revisions','season_id=? AND user_id=?'): ('c.external_id=%s AND u.external_id=%s','r.revision DESC'),
          ('analyses','user_id=?'): ('u.external_id=%s', 'a.created_at DESC,a.external_id DESC'),
          ('analyses','user_id=? AND id IN (SELECT analysis_id FROM farm_assessment_analyses WHERE assessment_id=? AND user_id=?)'):
              ('''u.external_id=%s AND a.analysis_id IN (SELECT l.analysis_id FROM assessment_analysis_links l
                JOIN mock_assessments ma ON ma.assessment_id=l.assessment_id JOIN users lu ON lu.user_id=l.user_id
                WHERE ma.external_id=%s AND lu.external_id=%s)''', 'a.created_at DESC,a.external_id DESC'),
        }
        condition, ordering = queries[(table,where)]
        total = self.one(f'SELECT COUNT(*) total FROM {source} WHERE {condition}', params)['total']
        rows = self.all(f'SELECT {projection} FROM {source} WHERE {condition} ORDER BY {ordering} LIMIT %s OFFSET %s', (*params,size,offset))
        return total,rows

    def holding_summary(self, row):
        return dict(row)

    def add_holding(self, item):
        self.execute('''INSERT INTO farms(external_id,owner_user_id,farm_name,address,manager,description,
            version,api_created_at,api_updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (item['id'],self.uid(item['user_id']),item['name'],item['address'],item['manager'],item['notes'],
             item['version'],item['created_at'],item['updated_at']))

    def update_holding(self, fields):
        self.execute('''UPDATE farms SET farm_name=%s,address=%s,manager=%s,description=%s,
            api_updated_at=%s,version=version+1 WHERE external_id=%s AND owner_user_id=%s''',
            (fields['name'],fields['address'],fields['manager'],fields['notes'],fields['updated_at'],
             fields['id'],self.uid(fields['user_id'])))

    def delete_holding(self, identifier, user_id):
        numeric = self.pk('farm_holdings', identifier, user_id)
        self.execute('DELETE FROM owner_default_farms WHERE farm_id=%s AND user_id=%s', (numeric,self.uid(user_id)))
        self.execute('DELETE FROM farms WHERE farm_id=%s AND owner_user_id=%s', (numeric,self.uid(user_id)))

    def holding_plots(self, user_id, farm_id, size, offset):
        projection, source, *_ = PROJECTIONS['farm_plots']
        source += ' JOIN farms h ON h.farm_id=f.farm_id AND h.owner_user_id=f.user_id'
        condition = 'u.external_id=%s AND h.external_id=%s'
        params = (user_id, farm_id)
        total = self.one(f'SELECT COUNT(*) total FROM {source} WHERE {condition}', params)['total']
        rows = self.all(f'''SELECT {projection},h.external_id farm_id,f.area_ha FROM {source}
            WHERE {condition} ORDER BY f.api_created_at DESC,f.external_id DESC LIMIT %s OFFSET %s''', (*params,size,offset))
        return total, rows

    def add_plot(self, item, farm_id=None, area_ha=None):
        user = self.uid(item['user_id'])
        if farm_id is not None:
            farm = self.pk('farm_holdings', farm_id, item['user_id'])
        else:
            row = self.one('SELECT farm_id FROM owner_default_farms WHERE user_id=%s', (user,))
            if row:
                farm = row['farm_id']
                farm_id = self.one('SELECT external_id FROM farms WHERE farm_id=%s', (farm,))['external_id']
            else:
                farm_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'aegis:default-farm:' + item['user_id']))
                existing = self.owned('farm_holdings', farm_id, item['user_id'])
                if existing is None:
                    self.add_holding(dict(id=farm_id,user_id=item['user_id'],name='Nông trại của tôi',
                        address='',manager='',notes='',version=1,created_at=item['created_at'],updated_at=item['created_at']))
                farm = self.pk('farm_holdings', farm_id, item['user_id'])
                self.execute('INSERT INTO owner_default_farms VALUES (%s,%s)', (user,farm))
        self.execute('''INSERT INTO farm_fields(external_id,farm_id,user_id,field_name,crop_type,location_text,api_created_at,area_ha)
            VALUES (%s,%s,%s,%s,'rice',%s,%s,%s)''', (item['id'],farm,user,item['name'],item['location_text'],item['created_at'],area_ha))
        return dict(item, farm_id=farm_id, area_ha=area_ha)

    def plot_summary(self, row):
        return self.one('''SELECT f.external_id id,u.external_id user_id,h.external_id farm_id,
            f.field_name name,f.location_text,f.area_ha,f.api_created_at created_at
            FROM farm_fields f JOIN users u ON u.user_id=f.user_id
            JOIN farms h ON h.farm_id=f.farm_id AND h.owner_user_id=f.user_id
            WHERE f.external_id=%s AND u.external_id=%s''', (row['id'],row['user_id']))

    def update_plot(self, fields):
        user = self.uid(fields['user_id'])
        self.execute('''UPDATE farm_fields SET field_name=%s,location_text=%s,area_ha=%s
            WHERE external_id=%s AND user_id=%s''',
            (fields['name'],fields['location_text'],fields['area_ha'],fields['id'],user))

    def delete_plot(self, identifier, user_id):
        field = self.pk('farm_plots',identifier,user_id)
        owner = self.uid(user_id)
        self.one('SELECT field_id FROM farm_fields WHERE field_id=%s AND user_id=%s FOR UPDATE', (field,owner))
        if self.one('SELECT crop_cycle_id FROM crop_cycles WHERE field_id=%s LIMIT 1 FOR UPDATE', (field,)):
            return False
        self.execute('DELETE FROM farm_fields WHERE field_id=%s AND user_id=%s', (field,owner))
        return True

    def add_season(self, item):
        field = self.pk('farm_plots',item['plot_id'],item['user_id'])
        self.execute('''INSERT INTO crop_cycles(external_id,field_id,user_id,name,crop_type,start_date,expected_end_date,api_created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (item['id'],field,self.uid(item['user_id']),item['name'],item['crop'],item['start_date'],item['end_date'],item['created_at']))

    def device_code_exists(self, user_id, code):
        return self.one('SELECT device_id FROM iot_devices WHERE user_id=%s AND device_code=%s', (self.uid(user_id),code)) is not None

    def add_device(self, item):
        cycle = self.pk('farm_seasons',item['season_id'],item['user_id'])
        field = self.one('SELECT field_id FROM crop_cycles WHERE crop_cycle_id=%s', (cycle,))['field_id']
        # Real globally unique hardware identity is not inferred from an owner's mock code.
        self.execute('''INSERT INTO iot_devices(external_id,user_id,crop_cycle_id,field_id,device_uid,device_name,
            protocol,device_code,source,api_created_at) VALUES (%s,%s,%s,%s,%s,%s,'HTTP',%s,'mock',%s)''',
            (item['id'],self.uid(item['user_id']),cycle,field,'mock:'+item['id'],item['name'],item['device_code'],item['created_at']))

    def latest_profile(self, season_id, user_id):
        projection, source, *_ = PROJECTIONS['farm_cultivation_revisions']
        return self.one(f'SELECT {projection} FROM {source} WHERE c.external_id=%s AND u.external_id=%s ORDER BY r.revision DESC LIMIT 1', (season_id,user_id))

    def add_profile(self, values):
        identifier,season,user,revision,profile,sha,reason,created,request_id = values
        self.execute('INSERT INTO cultivation_revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                     (identifier,self.pk('farm_seasons',season,user),self.uid(user),revision,profile,sha,reason,created,request_id))

    def reading(self, device_id, start_at):
        projection, source, *_ = PROJECTIONS['farm_telemetry']
        return self.one(f'SELECT {projection} FROM {source} WHERE d.external_id=%s AND t.start_at=%s', (device_id,start_at))

    def add_reading(self, values):
        device,user,*rest = values
        self.execute('INSERT INTO mock_hourly_readings VALUES (%s,%s,%s,%s,%s,%s,%s)',
                     (self.pk('farm_devices',device,user),self.uid(user),*rest))

    def readings(self, device_id, user_id, start, end):
        projection, source, *_ = PROJECTIONS['farm_telemetry']
        return self.all(f'''SELECT {projection} FROM {source} WHERE d.external_id=%s AND u.external_id=%s
            AND t.start_at>=%s AND t.start_at<%s ORDER BY t.start_at''', (device_id,user_id,start,end))

    def find_assessment(self, device_id, profile_hash, end):
        projection, source, *_ = PROJECTIONS['farm_assessments']
        return self.one(f'SELECT {projection} FROM {source} WHERE d.external_id=%s AND a.profile_sha256=%s AND a.window_end=%s', (device_id,profile_hash,end))

    def add_assessment(self, values):
        identifier,user,device,*rest = values
        self.execute('''INSERT INTO mock_assessments(external_id,user_id,device_id,profile_sha256,window_end,status,snapshot_json,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (identifier,self.uid(user),self.pk('farm_devices',device,user),*rest))

    def link_analysis(self, assessment_id, analysis_id, user_id, created_at):
        assessment = self.pk('farm_assessments',assessment_id,user_id)
        analysis = self.pk('analyses',analysis_id,user_id)
        if self.one('SELECT 1 FROM assessment_analysis_links WHERE assessment_id=%s AND analysis_id=%s', (assessment,analysis)):
            return False
        self.execute('INSERT INTO assessment_analysis_links VALUES (%s,%s,%s,%s)', (assessment,analysis,self.uid(user_id),created_at))
        return True

    def save_analysis(self, analysis, detections, key_hash, inference_result=None):
        user = self.uid(analysis['user_id'])
        image = self.execute('''INSERT INTO crop_images(external_id,uploaded_by,source_type,image_url,image_width,image_height,orientation)
            VALUES (%s,%s,'mobile',%s,%s,%s,%s)''', (analysis['id'],user,analysis['image_path'],analysis['image_width'],analysis['image_height'],analysis['orientation'])).lastrowid
        sha = analysis['model_sha256']
        model = self.one("SELECT model_version_id FROM model_versions WHERE model_type='yolo_detection' AND artifact_sha256=%s", (sha,))
        model_id = model['model_version_id'] if model else self.execute('''INSERT INTO model_versions
            (model_type,version_name,algorithm,artifact_path,artifact_sha256) VALUES ('yolo_detection',%s,'YOLO11',%s,%s)''', (sha,'sha256:'+sha,sha)).lastrowid
        run = self.execute('''INSERT INTO analysis_runs(external_id,user_id,image_id,model_version_id,model_version,model_sha256,status,
            request_id,ai_processing_ms,ai_roundtrip_ms,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (analysis['id'],user,image,model_id,analysis['model_version'],sha,analysis['status'],analysis['request_id'],analysis['ai_processing_ms'],analysis['ai_roundtrip_ms'],analysis['created_at'])).lastrowid
        for detection in detections:
            label = detection['disease']
            disease = self.one('SELECT disease_id FROM diseases WHERE disease_name=%s', (label,))
            disease_id = disease['disease_id'] if disease else self.execute("INSERT INTO diseases(disease_name,crop_type) VALUES (%s,'rice')", (label,)).lastrowid
            box = detection['bbox']
            self.execute('''INSERT INTO disease_detections(external_id,image_id,analysis_id,disease_id,model_version_id,class_id,disease_label,
                confidence,source_confidence,bbox_x,bbox_y,bbox_width,bbox_height,source_bbox)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (detection['detection_id'],image,run,disease_id,model_id,detection['class_id'],label,detection['confidence'],detection['confidence'],
                 box['x1'],box['y1'],box['x2']-box['x1'],box['y2']-box['y1'],json.dumps(box,allow_nan=False)))
        if key_hash is not None:
            cursor = self.execute("UPDATE inference_requests SET state='completed',analysis_id=%s WHERE user_id=%s AND key_hash=%s AND state='running'", (run,user,key_hash))
            if cursor.rowcount != 1:
                raise sqlite3.IntegrityError('Missing inference reservation')
        if self.one('SELECT status FROM schema_versions WHERE version=3'):
            from ..mongo_delivery import inference_event
            inference_event(self,analysis,inference_result or dict(detections=detections,status=analysis['status']))

    def detections(self, analysis_id):
        rows = self.all('''SELECT d.external_id id,d.class_id,d.disease_label disease,d.source_confidence confidence,d.source_bbox
            FROM disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id WHERE a.external_id=%s ORDER BY d.detection_id''', (analysis_id,))
        for row in rows:
            row.update(json.loads(row.pop('source_bbox')))
        return rows

    def analysis_page(self, user_id, size, offset):
        return self.page('analyses','user_id=?',(user_id,),size,offset,None)
