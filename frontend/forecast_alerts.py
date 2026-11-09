"""Transactional, versioned in-app alerts for stored-raw synthetic forecasts."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, g, jsonify, request

from app.auth import require_auth
from app.farm import FarmError, LimitResponse, body, owned, paginate, private, limit_response
from app.storage import connect
from pilot_journal import journal_db
from forecast_history import record, snapshot, issue_us
from pilot_forecast import HOURLY_MODEL_PIN
from telemetry_audit import stamp
from telemetry_tool import digest

POLICY = json.loads(Path(__file__).with_name('forecast_alert_policy.json').read_text(encoding='utf-8'))
POLICY_HASH = digest(POLICY)
VERSION = POLICY['version']


def now():
    return datetime.now(timezone.utc)


def verify_policy(db):
    row = db.execute('SELECT * FROM forecast_alert_policies WHERE version=?', (VERSION,)).fetchone()
    try:
        if row is None or json.loads(row['payload_json']) != POLICY or row['payload_sha256'] != POLICY_HASH:
            raise ValueError('Policy changed')
    except (ValueError, TypeError, KeyError):
        raise FarmError('forecast_alert_policy_error', 'Policy cảnh báo không khớp version đã đóng.', 500)


def initialize(path):
    with journal_db(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_alert_policies(
            version TEXT PRIMARY KEY,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_alerts(
            id TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            forecast_id TEXT NOT NULL REFERENCES synthetic_forecasts(id),scope_key TEXT NOT NULL,
            policy_version TEXT NOT NULL REFERENCES forecast_alert_policies(version),
            kind TEXT NOT NULL CHECK(kind IN ('score_threshold','data_quality')),
            issued_at TEXT NOT NULL,target_window_end TEXT NOT NULL,payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('unread','acknowledged')),
            version INTEGER NOT NULL CHECK(version IN (1,2)),created_at TEXT NOT NULL,acknowledged_at TEXT,
            UNIQUE(forecast_id,policy_version))''')
        db.execute('''CREATE INDEX IF NOT EXISTS idx_forecast_alert_owner
            ON forecast_alerts(user_id,season_id,created_at,id)''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_alert_evaluations(
            forecast_id TEXT NOT NULL REFERENCES synthetic_forecasts(id),
            policy_version TEXT NOT NULL REFERENCES forecast_alert_policies(version),user_id TEXT NOT NULL,
            scope_key TEXT NOT NULL,outcome TEXT NOT NULL,kind TEXT,
            alert_id TEXT REFERENCES forecast_alerts(id),evaluated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,PRIMARY KEY(forecast_id,policy_version))''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_alert_states(
            scope_key TEXT PRIMARY KEY,user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            latest_issue_us INTEGER NOT NULL,latest_forecast_id TEXT NOT NULL REFERENCES synthetic_forecasts(id),
            score_alert_id TEXT REFERENCES forecast_alerts(id),data_alert_id TEXT REFERENCES forecast_alerts(id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_alert_actions(
            id TEXT PRIMARY KEY,alert_id TEXT NOT NULL REFERENCES forecast_alerts(id),user_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action='acknowledge'),base_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,UNIQUE(alert_id,action))''')
        db.execute('INSERT OR IGNORE INTO forecast_alert_policies VALUES (?,?,?)',
                   (VERSION, json.dumps(POLICY, allow_nan=False), POLICY_HASH))
        verify_policy(db)


def eligible(row):
    return (row['scenario'] == 'hourly' and bool(row.get('hourly_source'))
            and row['model_manifest_sha256'] == HOURLY_MODEL_PIN == POLICY['eligible_model_pin'])


def evaluation_item(stored):
    try:
        item = json.loads(stored['payload_json'])
        if (digest(item) != stored['payload_sha256'] or item['forecast_id'] != stored['forecast_id']
                or item['policy_version'] != stored['policy_version'] or item['outcome'] != stored['outcome']
                or item['alert_id'] != stored['alert_id'] or item['scope_key'] != stored['scope_key']):
            raise ValueError('Evaluation mismatch')
        return item
    except (ValueError, TypeError, KeyError):
        raise FarmError('forecast_alert_storage_error', 'Kết quả đánh giá cảnh báo sai hash/định danh.', 500)


def alert_item(stored, at=None):
    try:
        item = json.loads(stored['payload_json'])
        if (digest(item) != stored['payload_sha256'] or item['id'] != stored['id']
                or item['forecast_id'] != stored['forecast_id'] or item['season_id'] != stored['season_id']
                or item['kind'] != stored['kind'] or item['policy_version'] != stored['policy_version']
                or item['scope_key'] != stored['scope_key'] or item['issued_at'] != stored['issued_at']
                or item['target_window_end'] != stored['target_window_end']
                or item['source'] != 'synthetic' or item['field_validated'] is not False
                or item['disease_confirmed'] is not False):
            raise ValueError('Alert mismatch')
        item.update(state=stored['state'], version=stored['version'], created_at=stored['created_at'],
                    acknowledged_at=stored['acknowledged_at'], forecast_window_active=stamp(stored['target_window_end']) > (at or now()))
        return item
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        raise FarmError('forecast_alert_storage_error', 'Cảnh báo đã lưu sai hash/định danh.', 500)


def evaluate(db, user_id, forecast_id):
    """Caller holds BEGIN IMMEDIATE; forecast, snapshot and alert commit together."""
    stored = db.execute('SELECT * FROM synthetic_forecasts WHERE id=? AND user_id=?', (forecast_id, user_id)).fetchone()
    if stored is None:
        raise FarmError('resource_not_found', 'Không tìm thấy dự báo.', 404)
    row = record(stored)
    if not eligible(row):
        return dict(forecast_id=forecast_id, policy_version=VERSION, outcome='not_eligible', alert_id=None), True
    verify_policy(db)
    previous = db.execute('SELECT * FROM forecast_alert_evaluations WHERE forecast_id=? AND policy_version=? AND user_id=?',
                          (forecast_id, VERSION, user_id)).fetchone()
    if previous:
        return evaluation_item(previous), True
    origin = row['hourly_source']
    link = db.execute('''SELECT h.id FROM synthetic_forecast_hourly_sources l JOIN hourly_sources h ON h.id=l.hourly_source_id
        WHERE l.forecast_id=? AND h.id=? AND h.user_id=? AND h.season_id=? AND h.stream_id=?''',
        (forecast_id, origin['id'], user_id, row['season_id'], origin['stream_id'])).fetchone()
    payload = snapshot(db, row)
    try:
        if (link is None or payload is None or row['threshold'] != POLICY['threshold']
                or row['score_semantics'] != POLICY['score_semantics']
                or stamp(row['target_window_end']) != stamp(row['issued_at'])+timedelta(hours=row['horizon_hours'])
                or row['predicted_event'] != (None if row['score'] is None else int(row['score'] >= POLICY['threshold']))):
            raise ValueError('Forecast not eligible under immutable policy')
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise FarmError('forecast_alert_storage_error', 'Forecast không khớp nguồn hoặc policy cảnh báo.', 500)
    scope = dict(user_id=user_id, season_id=row['season_id'], stream_id=origin['stream_id'],
        model_pin=row['model_manifest_sha256'], feature_contract_sha256=row['feature_contract_sha256'],
        horizon_hours=row['horizon_hours'], hourly_policy_revision=origin['policy_revision'],
        policy_version=VERSION, policy_sha256=POLICY_HASH)
    scope_key = digest(scope)
    at, issued = now(), stamp(row['issued_at'])
    kind = 'data_quality' if row['status'] == 'insufficient_data' else 'score_threshold' if row['score'] >= POLICY['threshold'] else None
    state = db.execute('SELECT * FROM forecast_alert_states WHERE scope_key=?', (scope_key,)).fetchone()
    if state and (state['user_id'] != user_id or state['season_id'] != row['season_id']):
        raise FarmError('forecast_alert_storage_error','State cảnh báo sai owner/mùa vụ.',500)
    alert_id, advance = None, False
    if stamp(row['target_window_end']) <= at:
        outcome = 'expired_forecast'
    elif issued > at:
        outcome = 'future_issue'
    elif (at-issued).total_seconds() > POLICY['maximum_forecast_age_seconds']:
        outcome = 'stale_forecast'
    elif state and issue_us(row['issued_at']) <= state['latest_issue_us']:
        outcome = 'same_issue_already_evaluated' if issue_us(row['issued_at']) == state['latest_issue_us'] else 'out_of_order'
    else:
        advance = True
        anchor = state['score_alert_id' if kind == 'score_threshold' else 'data_alert_id'] if state and kind else None
        if kind is None:
            outcome = 'below_threshold'
        elif anchor:
            existing = db.execute('SELECT * FROM forecast_alerts WHERE id=? AND user_id=?', (anchor, user_id)).fetchone()
            if existing is None or existing['scope_key'] != scope_key or existing['kind'] != kind:
                raise FarmError('forecast_alert_storage_error','Cooldown anchor không khớp scope/loại cảnh báo.',500)
            alert_item(existing)
            if (issued-stamp(existing['issued_at'])).total_seconds() < POLICY['cooldown_seconds']:
                outcome, alert_id = 'suppressed_cooldown', anchor
            else:
                outcome = 'created'
        else:
            outcome = 'created'
        if outcome == 'created':
            alert_id = str(uuid4())
            alert = dict(schema_version='aegis-forecast-alert-v1', id=alert_id, forecast_id=forecast_id,
                season_id=row['season_id'], plot_id=row['plot_id'], hourly_source=origin,
                model_version=row['model_version'], model_manifest_sha256=row['model_manifest_sha256'],
                feature_contract_sha256=row['feature_contract_sha256'], input_sha256=row['input_sha256'],
                source='synthetic', field_validated=False, kind=kind, issued_at=row['issued_at'],
                target_window_end=row['target_window_end'], horizon_hours=row['horizon_hours'],
                score=row['score'], score_semantics=row['score_semantics'], threshold=POLICY['threshold'],
                reasons=row['reasons'], disease=row['disease'], disease_confirmed=False,
                scope_key=scope_key, policy_version=VERSION, policy_sha256=POLICY_HASH,
                interpretation=POLICY['interpretation'])
            db.execute('''INSERT INTO forecast_alerts(id,user_id,season_id,forecast_id,scope_key,policy_version,
                kind,issued_at,target_window_end,payload_json,payload_sha256,state,version,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (alert_id,user_id,row['season_id'],forecast_id,scope_key,VERSION,
                kind,row['issued_at'],row['target_window_end'],json.dumps(alert,allow_nan=False),digest(alert),'unread',1,at.isoformat()))
        if state is None:
            db.execute('INSERT INTO forecast_alert_states VALUES (?,?,?,?,?,?,?)',
                (scope_key,user_id,row['season_id'],issue_us(row['issued_at']),forecast_id,None,None))
        else:
            db.execute('UPDATE forecast_alert_states SET latest_issue_us=?,latest_forecast_id=? WHERE scope_key=?',
                       (issue_us(row['issued_at']),forecast_id,scope_key))
        if outcome == 'created':
            column = 'score_alert_id' if kind == 'score_threshold' else 'data_alert_id'
            db.execute('UPDATE forecast_alert_states SET '+column+'=? WHERE scope_key=?', (alert_id,scope_key))
    result = dict(schema_version='aegis-forecast-alert-evaluation-v1',forecast_id=forecast_id,
        policy_version=VERSION,policy_sha256=POLICY_HASH,scope_key=scope_key,outcome=outcome,kind=kind,
        alert_id=alert_id,evaluated_at=at.isoformat(),issued_at=row['issued_at'],
        model_manifest_sha256=row['model_manifest_sha256'],input_sha256=row['input_sha256'],
        source='synthetic',field_validated=False,watermark_advanced=advance)
    db.execute('INSERT INTO forecast_alert_evaluations VALUES (?,?,?,?,?,?,?,?,?,?)',
        (forecast_id,VERSION,user_id,scope_key,outcome,kind,alert_id,at.isoformat(),json.dumps(result,allow_nan=False),digest(result)))
    return result, False


def enable_forecast_alerts(app, path):
    initialize(path)
    bp = Blueprint('forecast_alerts', __name__, url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse, limit_response)
    bp.register_error_handler(FarmError, lambda e: (jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    @bp.get('/forecast-alert-policy')
    @require_auth
    def policy():
        if request.args:
            raise FarmError('invalid_alert_query','Policy không nhận query.')
        with journal_db(path) as db:
            verify_policy(db)
        return jsonify(success=True,item=dict(policy=POLICY,policy_sha256=POLICY_HASH))

    @bp.route('/forecasts/<uuid:id>/alert-evaluation', methods=['GET','POST'])
    @require_auth
    def evaluation(id):
        if request.args:
            raise FarmError('invalid_alert_query','Đánh giá cảnh báo không nhận query.')
        with journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if request.method == 'POST' else 'BEGIN')
            stored = db.execute('SELECT * FROM synthetic_forecasts WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
            if stored is None:
                raise FarmError('resource_not_found','Không tìm thấy dự báo.',404)
            if request.method == 'POST':
                body(set())
                result,replayed = evaluate(db,g.user['id'],str(id))
                return jsonify(success=True,item=result,replayed=replayed),200 if replayed else 201
            old = db.execute('SELECT * FROM forecast_alert_evaluations WHERE forecast_id=? AND policy_version=? AND user_id=?',
                             (str(id),VERSION,g.user['id'])).fetchone()
            result = evaluation_item(old) if old else dict(forecast_id=str(id),policy_version=VERSION,alert_id=None,
                outcome='not_evaluated' if eligible(record(stored)) else 'not_eligible')
            return jsonify(success=True,item=result)

    @bp.get('/forecast-alerts')
    @require_auth
    def alerts():
        args = request.args
        allowed = {'season_id','kind','state','window'}
        if set(args)-allowed-{'page','page_size'} or any(len(args.getlist(k)) != 1 for k in args):
            raise FarmError('invalid_alert_query','Query cảnh báo không hợp lệ.')
        where,params = ['user_id=?'],[g.user['id']]
        assessed = now()
        with connect(app.config) as core,journal_db(path) as db:
            if 'season_id' in args:
                from uuid import UUID
                try: season_id = str(UUID(args['season_id']))
                except (ValueError,TypeError,AttributeError): raise FarmError('invalid_alert_query','season_id cần UUID.')
                owned(core,'seasons',season_id)
                where.append('season_id=?');params.append(season_id)
            for key,choices in [('kind',{'score_threshold','data_quality'}),('state',{'unread','acknowledged'})]:
                if key in args:
                    if args[key] not in choices: raise FarmError('invalid_alert_query','Bộ lọc cảnh báo không hợp lệ.')
                    where.append(key+'=?');params.append(args[key])
            if 'window' in args:
                if args['window'] not in ('active','expired'): raise FarmError('invalid_alert_query','window cần active hoặc expired.')
                where.append('target_window_end'+('>?' if args['window']=='active' else '<=?'));params.append(assessed.isoformat())
            return paginate(db,'forecast_alerts',' AND '.join(where),params,lambda r:alert_item(r,assessed),allowed_query=allowed)

    def owned_alert(db, identifier):
        row = db.execute('SELECT * FROM forecast_alerts WHERE id=? AND user_id=?',(str(identifier),g.user['id'])).fetchone()
        if row is None: raise FarmError('resource_not_found','Không tìm thấy cảnh báo.',404)
        return row

    @bp.get('/forecast-alerts/<uuid:id>')
    @require_auth
    def detail(id):
        if request.args: raise FarmError('invalid_alert_query','Chi tiết cảnh báo không nhận query.')
        with journal_db(path) as db:
            return jsonify(success=True,item=alert_item(owned_alert(db,id)))

    @bp.post('/forecast-alerts/<uuid:id>/acknowledgements')
    @require_auth
    def acknowledge(id):
        if request.args: raise FarmError('invalid_alert_query','Xác nhận không nhận query.')
        with journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE')
            row = owned_alert(db,id)
            alert_item(row)
            data = body({'base_version'})
            base = data['base_version']
            if type(base) is not int or not 1 <= base <= 2147483647:
                raise FarmError('invalid_alert_version','base_version cần số nguyên dương.')
            if row['state']=='acknowledged' and base in (row['version'],row['version']-1):
                return jsonify(success=True,item=alert_item(row),replayed=True)
            if base != row['version']:
                raise FarmError('forecast_alert_version_conflict','Cảnh báo đã đổi, hãy tải lại.',409)
            at = max(now(),stamp(row['created_at'])).isoformat()
            db.execute('UPDATE forecast_alerts SET state=?,version=2,acknowledged_at=? WHERE id=?',('acknowledged',at,str(id)))
            db.execute('INSERT INTO forecast_alert_actions VALUES (?,?,?,?,?,?)',(str(uuid4()),str(id),g.user['id'],'acknowledge',base,at))
            return jsonify(success=True,item=alert_item(owned_alert(db,id)),replayed=False),201

    app.register_blueprint(bp)
