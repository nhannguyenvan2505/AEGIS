from app.admin.core import db

SELECT = '''d.external_id id, d.device_code, d.device_uid, d.device_name, d.protocol, d.firmware_version,
            d.status, d.source, d.last_seen_at, d.installed_at, d.api_created_at created_at,
            p.external_id plot_id, p.field_name plot_name, c.external_id season_id, c.name season_name,
            u.external_id owner_id, u.email owner_email'''
SOURCE = '''iot_devices d LEFT JOIN farm_fields p ON p.field_id=d.field_id
            LEFT JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id JOIN users u ON u.user_id=d.user_id'''


def list_page(filters, q=None):
    columns = {'status': 'd.status', 'source': 'd.source', 'owner_id': 'u.external_id', 'plot_id': 'p.external_id'}
    where = [f'{columns[k]}=%s' for k in filters if k in columns]
    params = [v for k, v in filters.items() if k in columns]
    if q:
        like = '%' + q.replace('%', r'\%').replace('_', r'\_') + '%'
        where.append('(d.device_code LIKE %s OR d.device_name LIKE %s)'); params += [like, like]
    return db.paged(SELECT, SOURCE, where, params, 'd.device_id DESC')


def detail(identifier):
    return db.one(f'SELECT {SELECT} FROM {SOURCE} WHERE d.external_id=%s', (identifier,))


def find(identifier):
    return db.one('SELECT device_id, status FROM iot_devices WHERE external_id=%s', (identifier,))


def season_context(season_external_id):
    return db.one('SELECT crop_cycle_id, field_id, user_id FROM crop_cycles WHERE external_id=%s', (season_external_id,))


def code_exists(user_id, code):
    return db.one('SELECT 1 x FROM iot_devices WHERE user_id=%s AND device_code=%s', (user_id, code)) is not None


def create(values):
    db.execute('''INSERT INTO iot_devices(external_id,user_id,field_id,crop_cycle_id,device_uid,device_code,device_name,
                  protocol,firmware_version,status,source,api_created_at)
                  VALUES (%(external_id)s,%(user_id)s,%(field_id)s,%(crop_cycle_id)s,%(external_id)s,%(device_code)s,
                  %(device_name)s,%(protocol)s,%(firmware_version)s,'offline',%(source)s,%(created_at)s)''', values)


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
