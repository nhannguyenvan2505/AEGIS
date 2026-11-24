"""User-declared rice context; not agronomic validation or warning thresholds."""
from datetime import date, datetime, timedelta, timezone
import json
from .blast_conditions import digest

FIELDS = {'region', 'province_or_city', 'locality', 'rice_variety', 'planting_method',
          'sown_on', 'transplanted_on', 'season_status'}
SCHEMA_VERSION = 'aegis-cultivation-v1'
LOCAL_TZ = timezone(timedelta(hours=7))


def optional_text(value, maximum=120):
    if value is None:
        return None
    if not isinstance(value, str) or len(value.strip()) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError('Trường văn bản sai kiểu, quá dài hoặc có ký tự điều khiển.')
    return value.strip() or None


def actual_day(value, today):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('Ngày thực tế cần YYYY-MM-DD hoặc null.')
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Ngày thực tế không hợp lệ.') from exc
    if result.isoformat() != value or not 1900 <= result.year <= 2100:
        raise ValueError('Ngày cần đúng YYYY-MM-DD, trong phạm vi kỹ thuật 1900–2100.')
    if result > today:
        raise ValueError('Ngày gieo/cấy là ngày thực tế, không được ở tương lai; chưa biết dùng null.')
    return result.isoformat()


def validate_profile(raw, season, today):
    if not isinstance(raw, dict) or set(raw) != FIELDS:
        raise ValueError('Profile cần đúng các trường hồ sơ canh tác; trường chưa biết dùng null/unknown.')
    p = dict(raw)
    enums = {'region': {'unknown', 'central', 'southern', 'other'},
             'planting_method': {'unknown', 'direct_seeded', 'transplanted'},
             'season_status': {'unknown', 'planned', 'active', 'completed', 'archived'}}
    for key, allowed in enums.items():
        if not isinstance(p[key], str) or p[key] not in allowed:
            raise ValueError('Vùng, hình thức gieo/cấy hoặc trạng thái mùa vụ không được hỗ trợ.')
    for key in ['province_or_city', 'locality', 'rice_variety']:
        p[key] = optional_text(p[key], 200 if key == 'locality' else 120)
    for key in ['sown_on', 'transplanted_on']:
        p[key] = actual_day(p[key], today)
    if p['planting_method'] == 'direct_seeded' and p['transplanted_on'] is not None:
        raise ValueError('Gieo sạ trực tiếp không có ngày cấy; nếu chưa rõ hình thức hãy chọn unknown.')
    if p['sown_on'] and p['transplanted_on'] and p['sown_on'] > p['transplanted_on']:
        raise ValueError('Ngày gieo không được sau ngày cấy.')
    # For transplanted rice, nursery sowing may precede field-season start.
    field_date = p['transplanted_on'] if p['planting_method'] == 'transplanted' else p['sown_on'] if p['planting_method'] == 'direct_seeded' else None
    if field_date and (field_date < season['start_date'] or (season['end_date'] and field_date > season['end_date'])):
        raise ValueError('Ngày gieo sạ/ngày cấy ngoài khoảng mùa vụ đã khai báo.')
    return dict(schema_version=SCHEMA_VERSION, source='user_declared', timezone='UTC+07:00', **p)


def context_check(profile):
    if profile is None:
        missing = ['region', 'province_or_city', 'rice_variety', 'planting_method', 'planting_date', 'season_status']
    else:
        missing = [k for k in ['province_or_city', 'rice_variety'] if not profile[k]]
        missing += [k for k in ['region', 'planting_method', 'season_status'] if profile[k] == 'unknown']
        method = profile['planting_method']
        if method == 'direct_seeded' and not profile['sown_on']:
            missing.append('sown_on')
        elif method == 'transplanted' and not profile['transplanted_on']:
            missing.append('transplanted_on')
        elif method == 'unknown':
            missing.append('planting_date')
    return dict(status='incomplete' if missing else 'complete', missing_fields=missing,
                agronomically_verified=False, changes_warning_rule=False,
                meaning='Completeness of user-declared context only; not warning eligibility or field validation')


def latest_profile(db, season_id, user_id):
    if hasattr(db, 'latest_profile'):
        return db.latest_profile(season_id, user_id)
    # Pilot automation still passes its read-only raw SQLite connection.
    from .repositories.sqlite import SQLiteRepository
    return SQLiteRepository(db).latest_profile(season_id, user_id)


def serialize(row):
    return dict(id=row['id'], season_id=row['season_id'], revision=row['revision'],
                profile=json.loads(row['profile_json']), profile_sha256=row['profile_sha256'],
                change_reason=row['change_reason'], created_at=row['created_at'], request_id=row['request_id'])


def envelope(row):
    item = serialize(row) if row is not None else None
    return dict(item=item, context_check=context_check(item['profile'] if item else None))


def assessment_context(row, end, captured_at):
    """Freeze the current record, explicitly showing retrospective availability."""
    result = envelope(row)
    result.update(captured_at=captured_at.isoformat(), age_at_local_date=end.astimezone(LOCAL_TZ).date().isoformat(),
                  crop_age_days=None, crop_age_basis=None, age_reason='unknown_planting_context',
                  recorded_after_window_end=None,
                  interpretation='Current record captured when assessment is created; not evidence it was available at window end')
    if row is None:
        return result
    result['recorded_after_window_end'] = datetime.fromisoformat(row['created_at']) > end
    p = result['item']['profile']
    key = {'direct_seeded': 'sown_on', 'transplanted': 'transplanted_on'}.get(p['planting_method'])
    if key and p[key]:
        days = (date.fromisoformat(result['age_at_local_date']) - date.fromisoformat(p[key])).days
        result.update(crop_age_basis=key, age_reason='planting_after_window_end' if days < 0 else 'calendar_days_day_zero')
        if days >= 0:
            result['crop_age_days'] = days
    return result


def apply_cultivation_migration(db):
    if db.execute('SELECT 1 FROM schema_migrations WHERE version=5').fetchone():
        return
    db.execute('''CREATE TABLE farm_cultivation_revisions (
        id TEXT PRIMARY KEY, season_id TEXT NOT NULL, user_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>=1),
        profile_json TEXT NOT NULL, profile_sha256 TEXT NOT NULL,
        change_reason TEXT NOT NULL, created_at TEXT NOT NULL, request_id TEXT NOT NULL,
        UNIQUE(season_id,revision),
        FOREIGN KEY(season_id,user_id) REFERENCES farm_seasons(id,user_id))''')
    db.execute('CREATE INDEX idx_cultivation_owner ON farm_cultivation_revisions(user_id,season_id,revision)')
    db.execute('INSERT INTO schema_migrations VALUES (5,?,?)',
               ('cultivation_context_revisions', datetime.now(timezone.utc).isoformat()))
