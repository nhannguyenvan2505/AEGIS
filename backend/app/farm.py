"""Owned farm context, mock telemetry, immutable assessments and image follow-up."""
import json
import math
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .blast_conditions import PROFILE, digest, evaluate, parse_time
from .limits import check_limit
from .repositories import repository as connect
from .cultivation import (validate_profile, latest_profile, serialize as cultivation_revision,
                          envelope as cultivation_envelope, assessment_context)

farm = Blueprint('farm', __name__, url_prefix='/api/farm')
LOCAL_TZ = timezone(timedelta(hours=7))
TABLES = {'farms': 'farm_holdings', 'plots': 'farm_plots', 'seasons': 'farm_seasons', 'devices': 'farm_devices', 'assessments': 'farm_assessments'}


class FarmError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


class LimitResponse(Exception):
    def __init__(self, response):
        self.response = response


@farm.errorhandler(LimitResponse)
def limit_response(exc):
    return exc.response


@farm.errorhandler(OverflowError)
def invalid_time_range(exc):
    return jsonify(success=False, error=dict(code='invalid_timestamp', message='Timestamp vượt phạm vi xử lý.')), 400


@farm.errorhandler(FarmError)
def farm_error(exc):
    return jsonify(success=False, error=dict(code=exc.code, message=exc.message)), exc.status


@farm.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.vary.add('Authorization')
    return response


def now():
    return datetime.now(timezone.utc)


def hour():
    return now().replace(minute=0, second=0, microsecond=0)


def body(required, optional=()):
    limited = check_limit('farm_write', g.user['id'], 'FARM_WRITE_LIMIT')
    if limited is not None:
        # Return the original rate-limit response, including Retry-After.
        raise LimitResponse(limited)
    if not request.is_json:
        raise FarmError('invalid_json', 'Gửi application/json.', 415)
    raw = request.stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise FarmError('payload_too_large', 'JSON tối đa 64 KiB.', 413)
    g.raw_json_payload = raw
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number')
    try:
        data = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        # Decoder depth failures are invalid client input, not server failures.
        raise FarmError('invalid_json', 'JSON không hợp lệ, lồng quá sâu hoặc có key trùng.')
    if not isinstance(data, dict) or set(required) - data.keys() or data.keys() - set(required) - set(optional):
        raise FarmError('invalid_fields', 'Thiếu trường bắt buộc hoặc có trường không được hỗ trợ.')
    return data


def text(value, maximum=120, allow_empty=False):
    if not isinstance(value, str) or len(value.strip()) > maximum or (not allow_empty and not value.strip()):
        raise FarmError('invalid_fields', 'Chuỗi rỗng, sai kiểu hoặc quá dài.')
    if any(ord(c) < 32 for c in value):
        raise FarmError('invalid_fields', 'Không chấp nhận ký tự điều khiển.')
    return value.strip()


def day(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise FarmError('invalid_dates', 'Ngày phải hợp lệ theo YYYY-MM-DD.')


def timestamp(value):
    try:
        return parse_time(value)
    except (ValueError, OverflowError):
        raise FarmError('invalid_timestamp', 'Timestamp cần timezone và đúng mốc giờ.')


def owned(db, kind, identifier):
    if isinstance(db, sqlite3.Connection):
        from .repositories.sqlite import SQLiteRepository
        db = SQLiteRepository(db)
    row = db.owned(TABLES[kind], str(identifier), g.user['id'])
    if row is None:
        raise FarmError('resource_not_found', 'Không tìm thấy tài nguyên.', 404)
    return row


def paginate(db, table, where, params, serialize=dict, order=None, allowed_query=(), fetch_page=None):
    if isinstance(db, sqlite3.Connection):
        from .repositories.sqlite import SQLiteRepository
        db = SQLiteRepository(db)
    if set(request.args) - {'page', 'page_size'} - set(allowed_query):
        raise FarmError('invalid_pagination', 'Chỉ hỗ trợ page và page_size.')
    values = []
    for key, default, maximum in [('page', '1', 1000000), ('page_size', '20', 100)]:
        value = request.args.get(key, default)
        if len(request.args.getlist(key)) > 1 or not value.isascii() or not value.isdigit() or len(value) > 7 or not 1 <= int(value) <= maximum:
            raise FarmError('invalid_pagination', 'Phân trang không hợp lệ.')
        values.append(int(value))
    page, size = values
    order = order or ('start_at DESC' if table == 'farm_telemetry' else 'created_at DESC, id DESC')
    total, rows = (fetch_page(size, (page-1)*size) if fetch_page else
                   db.page(table, where, params, size, (page-1)*size, order))
    pages = (total + size - 1) // size
    return jsonify(success=True, items=[serialize(r) for r in rows],
                   pagination=dict(page=page, page_size=size, total=total, total_pages=pages, has_next=page < pages))


def telemetry(row):
    return dict(start_at=row['start_at'], air_temperature_c=row['air_temperature_c'],
                relative_humidity_pct=row['relative_humidity_pct'], leaf_wet=bool(row['leaf_wet']))


def context(db, device_id):
    device = owned(db, 'devices', device_id)
    season = owned(db, 'seasons', device['season_id'])
    return device, season


def within_season(instant, season):
    local_date = instant.astimezone(LOCAL_TZ).date().isoformat()
    if local_date < season['start_date'] or (season['end_date'] and local_date > season['end_date']):
        raise FarmError('outside_season', 'Thời điểm ngoài ngày mùa vụ (UTC+7).')


def farm_fields(data):
    notes = data.get('notes', '')
    if (not isinstance(notes, str) or len(notes.strip()) > 1000 or
            any(ord(character) < 32 and character not in '\n\r\t' for character in notes)):
        raise FarmError('invalid_fields', 'Ghi chú không hợp lệ hoặc dài quá 1.000 ký tự.')
    return dict(name=text(data['name']), address=text(data['address'], 500),
                manager=text(data.get('manager', ''), 120, True),
                notes=notes.strip())


def checked_version(data, row):
    value = data['version']
    if type(value) is not int or value < 1:
        raise FarmError('invalid_version', 'Phiên bản nông trại không hợp lệ.')
    if value != row['version']:
        raise FarmError('farm_version_conflict', 'Nông trại đã thay đổi. Hãy tải lại trước khi lưu.', 409)


@farm.route('/farms', methods=['GET', 'POST'])
@require_auth
def holdings():
    if request.method == 'GET':
        with connect(current_app.config) as db:
            db.begin()
            return paginate(db, 'farm_holdings', 'user_id=?', (g.user['id'],),
                            db.holding_summary)
    data = body({'name', 'address'}, {'manager', 'notes'})
    stamp = now().isoformat()
    item = dict(id=str(uuid.uuid4()), user_id=g.user['id'], **farm_fields(data),
                version=1, created_at=stamp, updated_at=stamp)
    with connect(current_app.config) as db:
        db.begin(True)
        db.add_holding(item)
        result = db.holding_summary(owned(db, 'farms', item['id']))
    return jsonify(success=True, item=result), 201


@farm.route('/farms/<uuid:identifier>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def holding_detail(identifier):
    data = None
    if request.method == 'PUT':
        data = body({'name', 'address', 'version'}, {'manager', 'notes'})
    elif request.method == 'DELETE':
        data = body({'version'})
    with connect(current_app.config) as db:
        db.begin(data is not None)
        row = owned(db, 'farms', identifier)
        if request.method == 'GET':
            return jsonify(success=True, item=db.holding_summary(row))
        checked_version(data, row)
        if request.method == 'DELETE':
            if db.holding_summary(row)['plot_count']:
                raise FarmError('farm_not_empty', 'Chỉ có thể xóa nông trại khi chưa có ruộng.', 409)
            db.delete_holding(str(identifier), g.user['id'])
            return jsonify(success=True, deleted_id=str(identifier))
        fields = dict(**farm_fields(data), updated_at=now().isoformat(), id=str(identifier), user_id=g.user['id'])
        db.update_holding(fields)
        return jsonify(success=True, item=db.holding_summary(owned(db, 'farms', identifier)))


def create_plot(db, data, farm_id=None):
    fields = plot_fields(data)
    item = dict(id=str(uuid.uuid4()), user_id=g.user['id'], name=fields['name'],
                location_text=fields['location_text'], created_at=now().isoformat())
    if farm_id is None:
        candidate = data.get('farm_id')
        if candidate is not None:
            try:
                candidate = str(uuid.UUID(candidate))
            except (ValueError, TypeError, AttributeError):
                raise FarmError('invalid_farm_id', 'Mã nông trại không hợp lệ.')
            farm_id = owned(db, 'farms', candidate)['id']
        else:
            farm_id = None
    return db.add_plot(item, farm_id=farm_id, area_ha=fields['area_ha'])


def plot_fields(data):
    size = data.get('area_ha')
    if size is not None and (type(size) not in (int, float) or not 0 < size <= 1000000 or not math.isfinite(size)):
        raise FarmError('invalid_area', 'Diện tích phải lớn hơn 0 và không vượt quá 1.000.000 ha.')
    return dict(name=text(data['name']), location_text=text(data.get('location_text', ''), 500, True), area_ha=size)


@farm.route('/farms/<uuid:identifier>/plots', methods=['GET', 'POST'])
@require_auth
def holding_plots(identifier):
    data = body({'name'}, {'location_text', 'area_ha'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        parent = owned(db, 'farms', identifier)
        if data is not None:
            return jsonify(success=True, item=create_plot(db, data, parent['id'])), 201
        return paginate(db, 'farm_plots', '', (),
            fetch_page=lambda size, offset: db.holding_plots(g.user['id'], parent['id'], size, offset))


@farm.route('/plots', methods=['GET', 'POST'])
@require_auth
def plots():
    if request.method != 'POST':
        with connect(current_app.config) as db:
            db.begin()
            return paginate(db, 'farm_plots', 'user_id=?', (g.user['id'],))
    data = body({'name'}, {'location_text', 'farm_id', 'area_ha'})
    with connect(current_app.config) as db:
        db.begin(True)
        item = create_plot(db, data)
    # Keep the legacy create/detail response contract unchanged.
    return jsonify(success=True, item={key: item[key] for key in ('id', 'user_id', 'name', 'location_text', 'created_at')}), 201


@farm.route('/plots/<uuid:identifier>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def plot_detail(identifier):
    data = body({'name', 'area_ha'}, {'location_text'}) if request.method == 'PUT' else (
        body(set()) if request.method == 'DELETE' else None)
    with connect(current_app.config) as db:
        db.begin(data is not None)
        if request.method == 'GET':
            return jsonify(success=True, item=db.plot_summary(owned(db, 'plots', identifier)))
        if request.method == 'PUT':
            fields = plot_fields(data)
            owned(db, 'plots', identifier)
            db.update_plot(dict(**fields, id=str(identifier), user_id=g.user['id']))
            return jsonify(success=True, item=db.plot_summary(owned(db, 'plots', identifier)))
        owned(db, 'plots', identifier)
        if not db.delete_plot(str(identifier), g.user['id']):
            raise FarmError('plot_not_empty', 'Chỉ có thể xóa ruộng khi chưa có mùa vụ.', 409)
        return jsonify(success=True, deleted_id=str(identifier))


@farm.route('/plots/<uuid:identifier>/seasons', methods=['GET', 'POST'])
@require_auth
def seasons(identifier):
    data = body({'name', 'start_date'}, {'end_date'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        parent = owned(db, 'plots', identifier)
        if data is None:
            return paginate(db, 'farm_seasons', 'user_id=? AND plot_id=?', (g.user['id'], parent['id']))
        start = day(data['start_date'])
        end = day(data['end_date']) if data.get('end_date') is not None else None
        if end and end < start:
            raise FarmError('invalid_dates', 'Ngày kết thúc trước ngày bắt đầu.')
        item = dict(id=str(uuid.uuid4()), user_id=g.user['id'], plot_id=parent['id'], name=text(data['name']),
                    crop='rice', start_date=start, end_date=end, created_at=now().isoformat())
        db.add_season(item)
    return jsonify(success=True, item=item), 201


@farm.get('/seasons/<uuid:identifier>')
@require_auth
def season_detail(identifier):
    with connect(current_app.config) as db:
        return jsonify(success=True, item=dict(owned(db, 'seasons', identifier)))


@farm.route('/seasons/<uuid:identifier>/cultivation-profile', methods=['GET', 'PUT'])
@require_auth
def cultivation_profile(identifier):
    data = body({'base_revision', 'profile', 'change_reason'}) if request.method == 'PUT' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        season = owned(db, 'seasons', identifier)
        old = latest_profile(db, season['id'], g.user['id'])
        if data is None:
            return jsonify(success=True, **cultivation_envelope(old))
        if type(data['base_revision']) is not int or not 0 <= data['base_revision'] <= 2147483647:
            raise FarmError('invalid_cultivation_profile', 'base_revision phải là số nguyên không âm.')
        try:
            profile = validate_profile(data['profile'], season, now().astimezone(LOCAL_TZ).date())
        except ValueError as exc:
            raise FarmError('invalid_cultivation_profile', str(exc))
        reason = text(data['change_reason'], 500)
        revision = old['revision'] if old is not None else 0
        profile_hash = digest(profile)
        unchanged = old is not None and old['profile_sha256'] == profile_hash
        # A lost response may be retried against the immediately preceding base.
        replay = unchanged and data['base_revision'] == revision-1 and old['change_reason'] == reason
        if data['base_revision'] != revision and not replay:
            raise FarmError('cultivation_revision_conflict', 'Hồ sơ đã thay đổi; tải bản mới và đối chiếu trước khi lưu.', 409)
        if unchanged:
            response = jsonify(success=True, **cultivation_envelope(old))
            response.headers['Idempotency-Replayed'] = 'true'
            return response
        db.add_profile((str(uuid.uuid4()), season['id'], g.user['id'], revision+1,
                    json.dumps(profile, ensure_ascii=False, allow_nan=False), profile_hash,
                    reason, now().isoformat(), g.request_id))
        return jsonify(success=True, **cultivation_envelope(latest_profile(db, season['id'], g.user['id']))), 201


@farm.get('/seasons/<uuid:identifier>/cultivation-profile/revisions')
@require_auth
def cultivation_history(identifier):
    with connect(current_app.config) as db:
        db.begin()
        season = owned(db, 'seasons', identifier)
        return paginate(db, 'farm_cultivation_revisions', 'season_id=? AND user_id=?',
                        (season['id'], g.user['id']), cultivation_revision, order='revision DESC')


@farm.route('/seasons/<uuid:identifier>/devices', methods=['GET', 'POST'])
@require_auth
def devices(identifier):
    data = body({'name', 'device_code', 'source'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        parent = owned(db, 'seasons', identifier)
        if data is None:
            return paginate(db, 'farm_devices', 'user_id=? AND season_id=?', (g.user['id'], parent['id']))
        if data['source'] != 'mock':
            raise FarmError('mock_only', 'MVP hiện chỉ hỗ trợ thiết bị mock.')
        code = text(data['device_code'], 64)
        if not re.fullmatch(r'[A-Za-z0-9._:-]+', code):
            raise FarmError('invalid_fields', 'device_code chỉ gồm ASCII chữ/số và . _ : -')
        if db.device_code_exists(g.user['id'], code):
            raise FarmError('device_code_exists', 'Mã thiết bị đã được dùng.', 409)
        item = dict(id=str(uuid.uuid4()), user_id=g.user['id'], season_id=parent['id'], name=text(data['name']),
                    device_code=code, source='mock', created_at=now().isoformat())
        db.add_device(item)
    return jsonify(success=True, item=item), 201


@farm.get('/devices/<uuid:identifier>')
@require_auth
def device_detail(identifier):
    with connect(current_app.config) as db:
        return jsonify(success=True, item=dict(owned(db, 'devices', identifier)))


@farm.route('/devices/<uuid:identifier>/telemetry', methods=['GET', 'POST'])
@require_auth
def readings(identifier):
    data = body({'source', 'records'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        device, season = context(db, identifier)
        if data is None:
            return paginate(db, 'farm_telemetry', 'device_id=? AND user_id=?', (device['id'], g.user['id']),
                            lambda r: dict(telemetry(r), source='mock', quality='synthetic'))
        if data['source'] != 'mock':
            raise FarmError('mock_only', 'Chỉ nhận số đo mock.')
        if not isinstance(data['records'], list) or not 1 <= len(data['records']) <= 24:
            raise FarmError('invalid_readings', 'Mỗi batch cần từ 1 đến 24 bucket.')
        rows, seen = [], set()
        cutoff = hour()
        for raw in data['records']:
            if not isinstance(raw, dict) or set(raw) != {'start_at', 'air_temperature_c', 'relative_humidity_pct', 'leaf_wet'}:
                raise FarmError('invalid_readings', 'Bucket thiếu trường hoặc có trường không hỗ trợ.')
            instant = timestamp(raw['start_at'])
            if instant >= cutoff:
                raise FarmError('future_reading', 'Chỉ nhận bucket đã hoàn tất theo giờ server.')
            within_season(instant, season)
            try:
                evaluate(dict(source='mock', as_of=(instant + timedelta(hours=1)).isoformat(), records=[raw]))
            except (ValueError, OverflowError):
                raise FarmError('invalid_readings', 'Giá trị bucket không hợp lệ.')
            stamp = instant.isoformat()
            if stamp in seen:
                raise FarmError('duplicate_bucket', 'Một batch có bucket trùng.')
            seen.add(stamp)
            rows.append(dict(start_at=stamp, air_temperature_c=float(raw['air_temperature_c']),
                             relative_humidity_pct=float(raw['relative_humidity_pct']), leaf_wet=raw['leaf_wet']))
        inserted = replayed = 0
        for row in rows:
            old = db.reading(device['id'], row['start_at'])
            if old:
                if telemetry(old) != row:
                    raise FarmError('telemetry_conflict', 'Bucket đã lưu khác giá trị; dữ liệu không bị ghi đè.', 409)
                replayed += 1
            else:
                db.add_reading((device['id'], g.user['id'], row['start_at'], row['air_temperature_c'],
                            row['relative_humidity_pct'], int(row['leaf_wet']), now().isoformat()))
                inserted += 1
    return jsonify(success=True, inserted=inserted, replayed=replayed, source='mock'), 201 if inserted else 200


def assessment_snapshot(row):
    return json.loads(row['snapshot_json'])


@farm.route('/devices/<uuid:identifier>/assessments', methods=['GET', 'POST'])
@require_auth
def assessments(identifier):
    data = body(set(), {'as_of'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        device, season = context(db, identifier)
        if data is None:
            return paginate(db, 'farm_assessments', 'device_id=? AND user_id=?',
                            (device['id'], g.user['id']), assessment_snapshot)
        cutoff = hour()
        end = timestamp(data['as_of']) if 'as_of' in data else cutoff
        if end > cutoff:
            raise FarmError('future_assessment', 'Không đánh giá cửa sổ tương lai.')
        within_season(end - timedelta(microseconds=1), season)
        profile_hash = digest(PROFILE)
        old = db.find_assessment(device['id'], profile_hash, end.isoformat())
        if old:
            response = jsonify(success=True, item=assessment_snapshot(old))
            response.headers['Idempotency-Replayed'] = 'true'
            return response
        start = end - timedelta(hours=24)
        rows = db.readings(device['id'], g.user['id'], start.isoformat(), end.isoformat())
        payload = dict(source='mock', as_of=end.isoformat(), records=[telemetry(r) for r in rows])
        output = evaluate(payload)
        item = dict(id=str(uuid.uuid4()), user_id=g.user['id'], plot_id=season['plot_id'], season_id=season['id'],
                    device_id=device['id'], created_at=now().isoformat(), request_id=g.request_id,
                    mode='historical_mock' if end < cutoff else 'current_mock',
                    valid_until=(end + timedelta(hours=1)).isoformat(), profile=dict(PROFILE), input=payload, result=output)
        item['cultivation_context'] = assessment_context(latest_profile(db, season['id'], g.user['id']), end, now())
        db.add_assessment((item['id'], g.user['id'], device['id'], profile_hash, end.isoformat(), output['status'],
                    json.dumps(item, ensure_ascii=False, allow_nan=False), item['created_at']))
    return jsonify(success=True, item=item), 201


@farm.get('/assessments/<uuid:identifier>')
@require_auth
def assessment_detail(identifier):
    with connect(current_app.config) as db:
        return jsonify(success=True, item=assessment_snapshot(owned(db, 'assessments', identifier)))


@farm.route('/assessments/<uuid:identifier>/analyses', methods=['GET', 'POST'])
@require_auth
def followup_analyses(identifier):
    data = body({'analysis_id'}) if request.method == 'POST' else None
    with connect(current_app.config) as db:
        db.begin(data is not None)
        assessment = owned(db, 'assessments', identifier)
        if data is None:
            # Pagination via analyses table: no raw image bytes or unauthenticated URLs.
            return paginate(db, 'analyses', 'user_id=? AND id IN (SELECT analysis_id FROM farm_assessment_analyses WHERE assessment_id=? AND user_id=?)',
                            (g.user['id'], assessment['id'], g.user['id']),
                            lambda r: dict(analysis_id=r['id'], status=r['status'], model_version=r['model_version'],
                                           model_sha256=r['model_sha256'], image_url=f'/api/disease/analyses/{r["id"]}/image',
                                           detail_url=f'/api/disease/analyses/{r["id"]}', created_at=r['created_at']))
        try:
            analysis_id = str(uuid.UUID(data['analysis_id']))
        except (ValueError, TypeError, AttributeError):
            raise FarmError('invalid_fields', 'analysis_id phải là UUID.')
        analysis = db.owned('analyses', analysis_id, g.user['id'])
        if analysis is None:
            raise FarmError('resource_not_found', 'Không tìm thấy tài nguyên.', 404)
        inserted = db.link_analysis(assessment['id'], analysis_id, g.user['id'], now().isoformat())
    return jsonify(success=True, assessment_id=assessment['id'], analysis_id=analysis_id), 201 if inserted else 200
