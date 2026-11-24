"""Owner-scoped immutable synthetic forecast history in pilot storage."""
from datetime import datetime, timezone, timedelta
import json
import math
import re
from pathlib import Path
import sys
from uuid import UUID, uuid4

from flask import Blueprint, current_app, g, jsonify, request
import requests

from app.auth import require_auth
from app.storage import connect
from app.farm import FarmError, LimitResponse, body, limit_response, owned, paginate, private
from app.blast_conditions import digest
from pilot_journal import journal_db
from hourly_aggregation import project_feature_input
from telemetry_audit import stamp

# Feature preparation uses only the standard library; ML packages stay in the worker.
RUNTIME = Path(__file__).resolve().parents[1]/'forecast_demo/runtime'
if str(RUNTIME) not in sys.path:
    sys.path.append(str(RUNTIME))
from weather_forecast import prepare_weather, CONTRACT_SHA256 as WEATHER_CONTRACT_SHA256

MODEL_PIN = '549f84ac7b154aff63f31a1891f87cec21f60298d5bd8c63eeb6deb1792722fa'
HOURLY_MODEL_PIN = '2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f'


def stored_hourly_input(core, db, season, source_id, issue_time):
    try:
        source_id = str(UUID(source_id))
        issued = stamp(issue_time)
        if issued > datetime.now(timezone.utc):
            raise ValueError('Future issue')
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise FarmError('invalid_hourly_reference', 'Cần UUID nguồn hourly và issued_at hợp lệ, đã xảy ra.')
    source = db.execute('''SELECT h.* FROM hourly_sources h JOIN streams s
        ON s.id=h.stream_id AND s.user_id=h.user_id AND s.season_id=h.season_id
        WHERE h.id=? AND h.user_id=? AND h.season_id=?''',
        (source_id, g.user['id'], season['id'])).fetchone()
    if source is None:
        raise FarmError('resource_not_found', 'Không tìm thấy nguồn hourly của mùa vụ.', 404)
    owned(core, 'plots', season['plot_id'])
    try:
        compiled = json.loads(source['payload_json'])
        raw_input = json.loads(source['snapshot_json'])
        if digest(compiled) != source['payload_sha256'] or digest(raw_input) != source['snapshot_sha256']:
            raise ValueError('Stored hash mismatch')
        if (compiled['source'] != 'synthetic' or compiled['stream_id'] != source['stream_id']
                or compiled['season_id'] != season['id'] or compiled['owner_id'] != g.user['id']
                or raw_input['plot_id'] != season['plot_id']):
            raise ValueError('Stored identity mismatch')
        if issued < stamp(source['created_at']) or any(stamp(b['available_at']) > issued for b in compiled['buckets']):
            raise FarmError('hourly_source_unavailable', 'Nguồn hourly chưa có tại issued_at đã chọn.', 409)
        context = core.execute('''SELECT * FROM farm_cultivation_revisions
            WHERE season_id=? AND user_id=? AND created_at<=? ORDER BY revision DESC LIMIT 1''',
            (season['id'], g.user['id'], issued.isoformat())).fetchone()
        revisions = []
        if context is not None:
            profile = json.loads(context['profile_json'])
            if digest(profile) != context['profile_sha256']:
                raise ValueError('Context hash mismatch')
            revisions.append(dict(revision=context['revision'], recorded_at=context['created_at'],
                                  available_at=context['created_at'], profile=profile))
        payload = project_feature_input(compiled, season['plot_id'], revisions, issued.isoformat())
        series = payload['series'][0]
        end = issued.replace(minute=0, second=0, microsecond=0)
        series['telemetry'] = sorted((b for b in series['telemetry']
            if end-timedelta(hours=120) <= stamp(b['start_at']) < end and stamp(b['available_at']) <= issued),
            key=lambda b: stamp(b['start_at']))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise FarmError('hourly_storage_error', 'Nguồn hourly hoặc hồ sơ canh tác đã lưu không hợp lệ.', 500)
    hourly = dict(source='synthetic', issued_at=issued.isoformat(), device_id=source['stream_id'],
                  telemetry=series['telemetry'], context_revisions=revisions)
    origin = dict(id=source_id, stream_id=source['stream_id'], revision=source['revision'],
                  policy_revision=source['policy_revision'], result_sha256=compiled['result_sha256'],
                  as_of=compiled['request']['as_of'], available_at=source['created_at'],
                  context_revision=context['revision'] if context is not None else None)
    return hourly, payload, origin


def call_model(season, scenario, hourly=None, *, weather=False):
    payload = dict(plot_id=season['plot_id'], season_id=season['id'], scenario=scenario)
    identity = payload.copy()
    if scenario == 'hourly':
        payload['hourly'] = hourly
        if weather:
            payload['model_route'] = 'weather'
    try:
        with requests.Session() as session:
            session.trust_env = False
            port = current_app.config.get('FORECAST_WORKER_PORT', 8001)
            response = session.post(f'http://127.0.0.1:{port}/predict', json=payload, timeout=(2, 10), allow_redirects=False)
        if response.status_code == 503:
            raise FarmError('model_unavailable', 'Mô hình dự báo chưa sẵn sàng.', 503)
        if response.status_code == 400 and response.json().get('status') == 'invalid_hourly_history':
            raise FarmError('invalid_hourly_history', 'Lịch sử theo giờ sai schema, nguồn hoặc thời gian.')
        response.raise_for_status()
        row = response.json()
        if any(row[k] != v for k, v in identity.items()):
            raise ValueError('identity')
        if (row['source'] != 'synthetic' or row['field_validated'] is not False
                or row['simulation_clock'] is not True or row['horizon_hours'] != 72
                or row['schema_version'] != 'aegis-forecast-v1'
                or row['model_version'] != ('fm03-weather-logistic-v1' if weather else 'fm02-logistic-v1') or row['threshold'] != .5
                or row['disease'] != 'leaf_blast'
                or row['model_manifest_sha256'] != (HOURLY_MODEL_PIN if weather else MODEL_PIN)
                or not re.fullmatch('[0-9a-f]{64}', row['input_sha256'])):
            raise ValueError('contract')
        if weather and (row['model_route'] != 'weather' or row['feature_contract_version'] != 'aegis-weather-features-v1'
                        or row['feature_contract_sha256'] != WEATHER_CONTRACT_SHA256
                        or row['score_semantics'] != 'uncalibrated_model_score'):
            raise ValueError('weather contract')
        issued = datetime.fromisoformat(row['issued_at'])
        if issued.tzinfo is None or datetime.fromisoformat(row['target_window_end']) != issued + timedelta(hours=72):
            raise ValueError('horizon')
        if row['status'] == 'forecast_ready':
            score = row['score']
            if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1 or row['predicted_event'] != int(score >= .5):
                raise ValueError('score')
        elif row['status'] != 'insufficient_data' or row['score'] is not None or row['predicted_event'] is not None:
            raise ValueError('status')
        return row
    except requests.ConnectionError:
        raise FarmError('model_unavailable', 'Không kết nối được dịch vụ dự báo.', 503)
    except requests.Timeout:
        raise FarmError('forecast_timeout', 'Dịch vụ dự báo phản hồi quá chậm.', 504)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise FarmError('forecast_invalid_response', 'Phản hồi dự báo không hợp lệ.', 502)


def persist_forecast(path, season_id, row, snapshot, storage_hash=None, origin=None):
    key = (g.user['id'], str(season_id), row['scenario'], row['model_manifest_sha256'], storage_hash or row['input_sha256'])
    with journal_db(path) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT result_json FROM synthetic_forecasts WHERE user_id=? AND season_id=? AND scenario=? AND model_pin=? AND input_hash=?', key).fetchone()
        if existing:
            return json.loads(existing[0]), True
        db.execute('INSERT INTO synthetic_forecasts VALUES (?,?,?,?,?,?,?,?)',
                   (row['id'], *key, row['created_at'], json.dumps(row, allow_nan=False)))
        if snapshot is not None:
            db.execute('INSERT INTO synthetic_forecast_inputs VALUES (?,?)', (row['id'], json.dumps(snapshot, allow_nan=False)))
        if origin is not None:
            db.execute('INSERT INTO synthetic_forecast_hourly_sources VALUES (?,?)', (row['id'], origin['id']))
            from forecast_alerts import evaluate
            evaluate(db, g.user['id'], row['id'])
    return row, False


def issue_stored_forecast(path, season, source_id, issued_at, replay_only=False):
    """Shared T05 operation for authenticated requests and owner-scoped jobs."""
    with connect(current_app.config) as core, journal_db(path) as db:
        db.execute('BEGIN')
        hourly, expected_input, origin = stored_hourly_input(core, db, season, source_id, issued_at)
        storage_hash = digest(dict(input_sha256=digest(expected_input), hourly_source=origin))
        existing = db.execute('''SELECT result_json FROM synthetic_forecasts
            WHERE user_id=? AND season_id=? AND scenario='hourly' AND model_pin=? AND input_hash=?''',
            (g.user['id'], season['id'], HOURLY_MODEL_PIN, storage_hash)).fetchone()
        if existing:
            return json.loads(existing[0]), True
    if replay_only:
        raise FarmError('forecast_not_found', 'Chưa có forecast đã lưu cho lượt chạy.', 404)
    row = call_model(season, 'hourly', hourly, weather=True)
    snapshot = row.pop('input_snapshot', None)
    expected_features = prepare_weather(expected_input)['rows'][0]
    expected_status = 'forecast_ready' if expected_features['predictors'] is not None else 'insufficient_data'
    if (not isinstance(snapshot, dict) or digest(snapshot) != row['input_sha256']
            or digest(expected_input) != row['input_sha256']
            or stamp(row['issued_at']) != stamp(issued_at) or row['status'] != expected_status
            or row['reasons'] != expected_features['reasons']
            or row['predictors_sha256'] != expected_features['predictors_sha256']):
        raise FarmError('forecast_invalid_response', 'Kết quả không khớp nguồn hourly đã chọn.', 502)
    row.update(id=str(uuid4()), created_at=datetime.now(timezone.utc).isoformat(), hourly_source=origin)
    return persist_forecast(path, season['id'], row, snapshot, storage_hash, origin)


def enable_forecast(app, storage):
    from forecast_readiness import assessment_time, readiness
    path = storage/'telemetry.sqlite3'
    with journal_db(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS synthetic_forecasts(
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, season_id TEXT NOT NULL,
            scenario TEXT NOT NULL, model_pin TEXT NOT NULL, input_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, result_json TEXT NOT NULL,
            UNIQUE(user_id,season_id,scenario,model_pin,input_hash))''')
        db.execute('''CREATE TABLE IF NOT EXISTS synthetic_forecast_inputs(
            forecast_id TEXT PRIMARY KEY REFERENCES synthetic_forecasts(id), input_json TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS synthetic_hourly_sources(
            season_id TEXT NOT NULL, user_id TEXT NOT NULL, revision INTEGER NOT NULL,
            input_hash TEXT NOT NULL, hourly_json TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(season_id,user_id,revision))''')
        db.execute('''CREATE TABLE IF NOT EXISTS synthetic_forecast_hourly_sources(
            forecast_id TEXT PRIMARY KEY REFERENCES synthetic_forecasts(id),
            hourly_source_id TEXT NOT NULL REFERENCES hourly_sources(id))''')
    bp = Blueprint('pilot_forecast', __name__, url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse, limit_response)
    bp.register_error_handler(FarmError, lambda e: (jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    @bp.get('/forecast-overview')
    @require_auth
    def overview():
        # Bound each response by the existing season pagination and owner boundary.
        from forecast_readiness import now as readiness_now
        assessed = readiness_now()
        with connect(current_app.config) as core, journal_db(path) as db:
            def serialize(season):
                plot = owned(core, 'plots', season['plot_id'])
                source = db.execute('''SELECT revision FROM synthetic_hourly_sources
                    WHERE user_id=? AND season_id=? ORDER BY revision DESC LIMIT 1''',
                    (g.user['id'], season['id'])).fetchone()
                latest = db.execute('''SELECT result_json FROM synthetic_forecasts
                    WHERE user_id=? AND season_id=? ORDER BY created_at DESC,id DESC LIMIT 1''',
                    (g.user['id'], season['id'])).fetchone()
                return dict(plot_id=plot['id'], plot_name=plot['name'], season_id=season['id'],
                    season_name=season['name'], source_revision=source['revision'] if source else None,
                    latest_forecast=json.loads(latest['result_json']) if latest else None,
                    raw_forecast_readiness=readiness(core, db, season, assessed, assessed, 'server_clock'))
            return paginate(core, 'farm_seasons', 'user_id=?', (g.user['id'],), serialize)

    @bp.get('/seasons/<uuid:id>/forecast-readiness')
    @require_auth
    def forecast_readiness(id):
        with connect(current_app.config) as core, journal_db(path) as db:
            season = dict(owned(core, 'seasons', id))
            issued, assessed, clock = assessment_time(request.args)
            return jsonify(success=True, item=readiness(core, db, season, issued, assessed, clock))

    @bp.route('/seasons/<uuid:id>/forecast-source', methods=['GET', 'POST'])
    @require_auth
    def source(id):
        with connect(current_app.config) as core:
            season = dict(owned(core, 'seasons', id))
        if request.method != 'POST':
            with journal_db(path) as db:
                latest = db.execute('''SELECT * FROM synthetic_hourly_sources
                    WHERE season_id=? AND user_id=? ORDER BY revision DESC LIMIT 1''',
                    (str(id), g.user['id'])).fetchone()
            if latest is None:
                return jsonify(success=True, item=None)
            return jsonify(success=True, item=dict(revision=latest['revision'],
                hourly=json.loads(latest['hourly_json']), input_sha256=latest['input_hash'],
                created_at=latest['created_at']))
        data = body({'base_revision', 'hourly'})
        if type(data['base_revision']) is not int or data['base_revision'] < 0:
            raise FarmError('invalid_revision', 'base_revision cần số nguyên không âm.')
        hourly = data['hourly']
        # Validate all hourly records through the same checked inference boundary.
        call_model(season, 'hourly', hourly)
        value_hash = digest(hourly)
        with journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('''SELECT * FROM synthetic_hourly_sources
                WHERE season_id=? AND user_id=? ORDER BY revision DESC LIMIT 1''',
                (str(id), g.user['id'])).fetchone()
            revision = latest['revision'] if latest else 0
            replay = latest is not None and value_hash == latest['input_hash']
            if replay and data['base_revision'] in (revision, revision-1):
                return jsonify(success=True, revision=revision, replayed=True)
            if data['base_revision'] != revision:
                raise FarmError('source_revision_conflict', 'Nguồn đã đổi. Hãy tải revision hiện tại.', 409)
            if latest:
                previous = json.loads(latest['hourly_json'])
                if hourly['device_id'] != previous['device_id']:
                    raise FarmError('source_device_conflict', 'Nguồn hiện tại gắn với device_id đã khai báo.', 409)
                current_time = datetime.fromisoformat(hourly['issued_at'].replace('Z', '+00:00'))
                previous_time = datetime.fromisoformat(previous['issued_at'].replace('Z', '+00:00'))
                if current_time <= previous_time:
                    raise FarmError('source_clock_conflict', 'Lượt cập nhật cần issued_at tiến lên.', 409)
            db.execute('INSERT INTO synthetic_hourly_sources VALUES (?,?,?,?,?,?)',
                (str(id), g.user['id'], revision+1, value_hash, json.dumps(hourly, allow_nan=False),
                 datetime.now(timezone.utc).isoformat()))
        return jsonify(success=True, revision=revision+1, replayed=False), 201

    @bp.route('/seasons/<uuid:id>/forecasts', methods=['GET','POST'])
    @require_auth
    def forecasts(id):
        with connect(current_app.config) as core:
            season = dict(owned(core, 'seasons', id))
        if request.method != 'POST':
            with journal_db(path) as db:
                return paginate(db, 'synthetic_forecasts', 'user_id=? AND season_id=?',
                                (g.user['id'], str(id)), lambda r: json.loads(r['result_json']))
        data = body({'scenario'}, {'hourly', 'hourly_source_id', 'issued_at'})
        scenario = data['scenario']
        if scenario not in ('ready', 'insufficient', 'hourly', 'source'):
            raise FarmError('invalid_scenario', 'Chọn source, ready, insufficient hoặc hourly kèm lịch sử.')
        stored = scenario == 'hourly' and 'hourly_source_id' in data
        extra = {'hourly_source_id', 'issued_at'} if stored else {'hourly'} if scenario == 'hourly' else set()
        if set(data) != {'scenario'} | extra:
            raise FarmError('invalid_scenario', 'Gửi lịch sử hourly hoặc nguồn hourly đã lưu cùng issued_at.')
        if stored:
            row, replayed = issue_stored_forecast(path, season, data['hourly_source_id'], data['issued_at'])
            return jsonify(success=True, item=row, replayed=replayed), 200 if replayed else 201
        source_revision = None
        if scenario == 'source':
            with journal_db(path) as db:
                latest = db.execute('''SELECT revision,hourly_json FROM synthetic_hourly_sources
                    WHERE season_id=? AND user_id=? ORDER BY revision DESC LIMIT 1''',
                    (str(id), g.user['id'])).fetchone()
            if latest is None:
                raise FarmError('forecast_source_missing', 'Mùa vụ chưa có lịch sử hourly.', 409)
            source_revision = latest['revision']
            data['hourly'] = json.loads(latest['hourly_json'])
            scenario = 'hourly'
        row = call_model(season, scenario, data.get('hourly'))
        snapshot = row.pop('input_snapshot', None)
        if scenario == 'hourly':
            if not isinstance(snapshot, dict) or digest(snapshot) != row['input_sha256']:
                raise FarmError('forecast_invalid_response', 'Sai dấu vết đầu vào dự báo.', 502)
        row.update(id=str(uuid4()), created_at=datetime.now(timezone.utc).isoformat())
        if source_revision is not None:
            row['source_revision'] = source_revision
            scenario = 'source'
            row['scenario'] = scenario
        row, replayed = persist_forecast(path, id, row, snapshot)
        return jsonify(success=True, item=row, replayed=replayed), 200 if replayed else 201

    @bp.get('/forecasts/<uuid:id>')
    @require_auth
    def detail(id):
        with journal_db(path) as db:
            row = db.execute('SELECT result_json FROM synthetic_forecasts WHERE user_id=? AND id=?', (g.user['id'], str(id))).fetchone()
        if row is None:
            raise FarmError('resource_not_found', 'Không tìm thấy dự báo.', 404)
        return jsonify(success=True, item=json.loads(row[0]))

    @bp.get('/forecasts/<uuid:id>/input')
    @require_auth
    def input_snapshot(id):
        with journal_db(path) as db:
            row = db.execute('''SELECT i.input_json FROM synthetic_forecast_inputs i
                JOIN synthetic_forecasts f ON f.id=i.forecast_id
                WHERE f.id=? AND f.user_id=?''', (str(id), g.user['id'])).fetchone()
        if row is None:
            raise FarmError('resource_not_found', 'Không tìm thấy đầu vào dự báo.', 404)
        return jsonify(success=True, item=json.loads(row[0]))

    app.register_blueprint(bp)
    from forecast_history import enable_forecast_history
    enable_forecast_history(app, path)
    from forecast_alerts import enable_forecast_alerts
    enable_forecast_alerts(app, path)
    from forecast_outcomes import enable_forecast_outcomes
    enable_forecast_outcomes(app, storage)
