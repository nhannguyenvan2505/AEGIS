from app.admin.core import db
from app.admin.core.filters import like as _user_like, user_clause

SELECT = '''d.external_id id, d.device_code, d.device_uid, d.device_name, d.protocol, d.firmware_version,
            d.sensor_type, d.status, d.source, d.last_seen_at, d.installed_at, d.api_created_at created_at,
            p.external_id plot_id, p.field_name plot_name, c.external_id season_id, c.name season_name,
            u.external_id owner_id, u.email owner_email, u.full_name owner_name'''
SOURCE = '''iot_devices d LEFT JOIN farm_fields p ON p.field_id=d.field_id
            LEFT JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id JOIN users u ON u.user_id=d.user_id'''


def list_page(filters, q=None, user=None):
    columns = {'sensor_type': 'd.sensor_type', 'status': 'd.status', 'source': 'd.source', 'owner_id': 'u.external_id', 'plot_id': 'p.external_id'}
    where = [f'{columns[k]}=%s' for k in filters if k in columns]
    params = [v for k, v in filters.items() if k in columns]
    if user:
        where.append(user_clause()); params += [_user_like(user)] * 2
    if q:
        like = '%' + q.replace('%', r'\%').replace('_', r'\_') + '%'
        where.append('(d.device_code LIKE %s OR d.device_name LIKE %s)'); params += [like, like]
    return db.paged(SELECT, SOURCE, where, params, 'd.device_id DESC')


def detail(identifier):
    return db.one(f'SELECT {SELECT} FROM {SOURCE} WHERE d.external_id=%s', (identifier,))


def find(identifier):
    return db.one('SELECT device_id, field_id, sensor_type, status FROM iot_devices WHERE external_id=%s', (identifier,))


def registration(identifier, lock=False):
    return db.one('''SELECT d.device_id, d.device_uid, p.external_id plot_id FROM iot_devices d
                     LEFT JOIN farm_fields p ON p.field_id=d.field_id WHERE d.external_id=%s'''
                  + (' FOR UPDATE' if lock else ''), (identifier,))


def lock_binding(device_uid):
    # The row a claim locks first: a claim running now either finishes before the
    # release or sees that the device is no longer registered.
    db.execute('''INSERT INTO esp32_device_bindings(device_uid, plot_id, updated_at)
                  VALUES (%s,NULL,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE device_uid=device_uid''', (device_uid,))


def release(device_id, device_uid, placeholder):
    db.execute("UPDATE iot_devices SET device_uid=%s, sensor_type=NULL, status='inactive' WHERE device_id=%s",
               (placeholder, device_id))
    db.execute('DELETE FROM esp32_device_bindings WHERE device_uid=%s', (device_uid,))


def season_context(season_external_id):
    return db.one('SELECT crop_cycle_id, field_id, user_id FROM crop_cycles WHERE external_id=%s', (season_external_id,))


def code_exists(user_id, code):
    return db.one('SELECT 1 x FROM iot_devices WHERE user_id=%s AND device_code=%s', (user_id, code)) is not None


def uid_exists(device_uid):
    # The column is case-sensitive but bindings are not.
    return db.one('SELECT 1 x FROM iot_devices WHERE UPPER(device_uid)=UPPER(%s)', (device_uid,)) is not None


def uid_bound_elsewhere(device_uid, field_id):
    return db.one('''SELECT 1 x FROM esp32_device_bindings b WHERE b.device_uid=%s AND b.plot_id IS NOT NULL
                     AND b.plot_id<>(SELECT external_id FROM farm_fields WHERE field_id=%s)''',
                  (device_uid, field_id)) is not None


def sensor_taken(field_id, sensor_type, exclude_device_id=None):
    return db.one('SELECT 1 x FROM iot_devices WHERE field_id=%s AND sensor_type=%s AND device_id<>%s',
                  (field_id, sensor_type, exclude_device_id or 0)) is not None


def create(values):
    db.execute('''INSERT INTO iot_devices(external_id,user_id,field_id,crop_cycle_id,device_uid,device_code,device_name,sensor_type,
                  protocol,firmware_version,status,source,api_created_at)
                  VALUES (%(external_id)s,%(user_id)s,%(field_id)s,%(crop_cycle_id)s,%(device_uid)s,%(device_code)s,
                  %(device_name)s,%(sensor_type)s,%(protocol)s,%(firmware_version)s,'offline',%(source)s,%(created_at)s)''', values)


def update(device_id, fields):
    sets = ','.join(f'{k}=%s' for k in fields)  # khóa lấy từ danh sách cố định ở routes
    db.execute(f'UPDATE iot_devices SET {sets} WHERE device_id=%s', [*fields.values(), device_id])


def telemetry(device_id, start=None, end=None):
    where, params = ['device_id=%s'], [device_id]
    if start:
        where.append('start_at>=%s'); params.append(start)
    if end:
        where.append('start_at<=%s'); params.append(end)
    return db.query(f'''SELECT start_at, air_temperature_c, relative_humidity_pct, leaf_wet
                        FROM mock_hourly_readings WHERE {' AND '.join(where)} ORDER BY start_at DESC LIMIT 500''', params)
