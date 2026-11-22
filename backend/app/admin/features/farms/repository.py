from app.admin.core import db

FARM_SELECT = '''f.external_id id, f.farm_name name, f.address, f.manager, f.latitude, f.longitude,
                 u.external_id owner_id, u.email owner_email, f.api_created_at created_at,
                 (SELECT COUNT(*) FROM farm_fields p WHERE p.farm_id=f.farm_id) plot_count,
                 (SELECT COALESCE(SUM(p.area_ha),0) FROM farm_fields p WHERE p.farm_id=f.farm_id) area_ha'''
FARM_SOURCE = 'farms f JOIN users u ON u.user_id=f.owner_user_id'
PLOT_SELECT = '''p.external_id id, f.external_id farm_id, f.farm_name, u.external_id owner_id, u.email owner_email,
                 p.field_name name, p.area_ha, p.crop_type, p.soil_type, p.status, p.location_text,
                 p.latitude, p.longitude, p.api_created_at created_at'''
PLOT_SOURCE = 'farm_fields p JOIN farms f ON f.farm_id=p.farm_id JOIN users u ON u.user_id=p.user_id'
SEASON_SELECT = '''c.external_id id, p.external_id plot_id, p.field_name plot_name, u.external_id owner_id,
                   c.name, c.crop_type, c.variety, c.start_date, c.expected_end_date, c.actual_end_date,
                   c.status, c.api_created_at created_at'''
SEASON_SOURCE = 'crop_cycles c JOIN farm_fields p ON p.field_id=c.field_id JOIN users u ON u.user_id=c.user_id'


def _like(value):
    return '%' + value.replace('%', r'\%').replace('_', r'\_') + '%'


def list_farms(owner_id=None, q=None):
    where, params = [], []
    if owner_id:
        where.append('u.external_id=%s'); params.append(owner_id)
    if q:
        where.append('(f.farm_name LIKE %s OR f.address LIKE %s)'); params += [_like(q)] * 2
    return db.paged(FARM_SELECT, FARM_SOURCE, where, params, 'f.farm_id DESC')


def farm(identifier):
    return db.one(f'SELECT {FARM_SELECT}, f.description notes FROM {FARM_SOURCE} WHERE f.external_id=%s', (identifier,))


def plots_of_farm(identifier):
    return db.query(f'SELECT {PLOT_SELECT} FROM {PLOT_SOURCE} WHERE f.external_id=%s ORDER BY p.field_id', (identifier,))


def list_plots(filters):
    columns = {'farm_id': 'f.external_id', 'owner_id': 'u.external_id', 'status': 'p.status', 'crop_type': 'p.crop_type'}
    where = [f'{columns[k]}=%s' for k in filters if k in columns]
    params = [v for k, v in filters.items() if k in columns]
    return db.paged(PLOT_SELECT, PLOT_SOURCE, where, params, 'p.field_id DESC')


def plot(identifier):
    return db.one(f'SELECT {PLOT_SELECT} FROM {PLOT_SOURCE} WHERE p.external_id=%s', (identifier,))


def seasons_of_plot(identifier):
    return db.query(f'SELECT {SEASON_SELECT} FROM {SEASON_SOURCE} WHERE p.external_id=%s '
                    'ORDER BY c.crop_cycle_id DESC', (identifier,))


def season(identifier):
    return db.one(f'SELECT {SEASON_SELECT}, c.notes FROM {SEASON_SOURCE} WHERE c.external_id=%s', (identifier,))


def season_devices(identifier):
    return db.query('''SELECT d.external_id id, d.device_code, d.device_name, d.status, d.source, d.last_seen_at
                       FROM iot_devices d JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id
                       WHERE c.external_id=%s''', (identifier,))


def season_revisions(identifier):
    return db.query('''SELECT r.revision, r.change_reason, r.profile_sha256, r.created_at
                       FROM cultivation_revisions r JOIN crop_cycles c ON c.crop_cycle_id=r.crop_cycle_id
                       WHERE c.external_id=%s ORDER BY r.revision DESC''', (identifier,))


def season_profile(identifier):
    row = db.one('''SELECT r.profile_json FROM cultivation_revisions r JOIN crop_cycles c
                    ON c.crop_cycle_id=r.crop_cycle_id WHERE c.external_id=%s ORDER BY r.revision DESC LIMIT 1''',
                 (identifier,))
    return row['profile_json'] if row else None
