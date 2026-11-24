"""Owner-scoped chronological forecast trends and pinned snapshot explanations."""
from datetime import datetime, timezone
import json
import math
import re
import sqlite3

from flask import Blueprint, current_app, g, jsonify, request
import requests

from app.auth import require_auth
from app.farm import FarmError, LimitResponse, owned, paginate, private, limit_response
from app.storage import connect
from pilot_journal import journal_db
from pilot_forecast import MODEL_PIN, HOURLY_MODEL_PIN
from telemetry_audit import stamp
from telemetry_tool import digest
from weather_forecast import FEATURES
from feature_preparation import CONTRACT as FULL_CONTRACT

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def issue_us(value):
    delta = stamp(value)-EPOCH
    return delta.days*86400000000+delta.seconds*1000000+delta.microseconds


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def record(stored, season=None):
    try:
        row = json.loads(stored['result_json'])
        if row['id'] != stored['id'] or row['model_manifest_sha256'] != stored['model_pin']:
            raise ValueError('Stored identity differs')
        if season and (row['season_id'] != season['id'] or row['plot_id'] != season['plot_id']):
            raise ValueError('Season identity differs')
        if row['source'] != 'synthetic' or row['field_validated'] is not False:
            raise ValueError('Source differs')
        if type(row['horizon_hours']) is not int or not 1 <= row['horizon_hours'] <= 744:
            raise ValueError('Horizon differs')
        issue_us(row['issued_at'])
        if row['status'] == 'forecast_ready':
            if not number(row['score']) or not 0 <= row['score'] <= 1:
                raise ValueError('Bad stored score')
        elif row['status'] != 'insufficient_data' or row['score'] is not None:
            raise ValueError('Bad stored status')
        return row
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        raise FarmError('forecast_storage_error', 'Dữ liệu dự báo đã lưu không hợp lệ.', 500)


def snapshot(db, row):
    stored = db.execute('SELECT input_json FROM synthetic_forecast_inputs WHERE forecast_id=?', (row['id'],)).fetchone()
    if stored is None:
        return None
    try:
        payload = json.loads(stored['input_json'])
        series = payload['series'][0]
        if (len(payload['series']) != 1 or len(payload['issue_times']) != 1
                or digest(payload) != row['input_sha256'] or series['plot_id'] != row['plot_id']
                or series['season_id'] != row['season_id'] or issue_us(payload['issue_times'][0]) != issue_us(row['issued_at'])):
            raise ValueError('Snapshot differs')
        return payload
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError):
        raise FarmError('forecast_storage_error', 'Snapshot dự báo sai hash hoặc định danh.', 500)


def point(db, stored, season):
    row = record(stored, season)
    payload = snapshot(db, row)
    scenario = row['scenario']
    kind = 'fixture_'+scenario if scenario in ('ready', 'insufficient') else 'stored_raw' if row.get('hourly_source') else 'hourly_history'
    identity = dict(source=row['source'], disease=row['disease'], model_manifest_sha256=row['model_manifest_sha256'],
        model_version=row['model_version'], feature_contract_sha256=row.get('feature_contract_sha256'),
        horizon_hours=row['horizon_hours'], threshold=row['threshold'],
        score_semantics=row['score_semantics'], input_kind=kind,
        hourly_policy_revision=(row.get('hourly_source') or {}).get('policy_revision'),
        device_id=payload['series'][0]['device_id'] if payload else None)
    return dict(id=row['id'], issued_at=row['issued_at'], created_at=row['created_at'],
        status=row['status'], score=row['score'], predicted_event=row['predicted_event'],
        reasons=row['reasons'], input_sha256=row['input_sha256'], snapshot_available=payload is not None,
        hourly_source=row.get('hourly_source'), series_key=digest(identity), series_identity=identity)


def comparisons(items):
    groups = {}
    for item in items:
        groups.setdefault(item['series_key'], []).append(item)
    series = []
    for key, points in sorted(groups.items()):
        points.sort(key=lambda p: (issue_us(p['issued_at']), p['created_at'], p['id']))
        buckets = {}
        for p in points:
            buckets.setdefault(issue_us(p['issued_at']), []).append(p)
        previous, boundary = None, 'first_in_page'
        for issued, bucket in sorted(buckets.items()):
            if len(bucket) > 1 or any(p.get('same_issue_count', 1) > 1 for p in bucket):
                for p in bucket:
                    p['comparison'] = dict(status='same_issue_revision', previous_forecast_id=None, score_delta=None)
                previous, boundary = None, 'after_ambiguous_issue'
                continue
            p = bucket[0]
            status, delta, previous_id = boundary, None, None
            if p['status'] == 'insufficient_data':
                status, previous, boundary = 'insufficient_data', None, 'after_data_gap'
            elif not p.get('snapshot_available', True):
                status, previous, boundary = 'snapshot_unavailable', None, 'after_snapshot_gap'
            else:
                if previous:
                    gap = (issued-issue_us(previous['issued_at']))/3600000000
                    if gap > p['series_identity']['horizon_hours']:
                        status = 'time_gap'
                    else:
                        status, delta, previous_id = 'comparable', p['score']-previous['score'], previous['id']
                previous, boundary = p, 'first_in_page'
            p['comparison'] = dict(status=status, previous_forecast_id=previous_id, score_delta=delta)
        series.append(dict(key=key, identity=points[0]['series_identity'],
                           max_comparison_gap_hours=points[0]['series_identity']['horizon_hours'],
                           point_ids=[p['id'] for p in points],
                           comparison_edges=[dict(from_forecast_id=p['comparison']['previous_forecast_id'],
                               to_forecast_id=p['id'], score_delta=p['comparison']['score_delta'])
                               for p in points if p['comparison']['status'] == 'comparable']))
    return series


def check_explanation(answer, row):
    expected = dict(schema_version='aegis-forecast-explanation-v1', source='synthetic', field_validated=False,
        status='explained', plot_id=row['plot_id'], season_id=row['season_id'], issued_at=row['issued_at'],
        model_manifest_sha256=row['model_manifest_sha256'], model_version=row['model_version'],
        input_sha256=row['input_sha256'], predictors_sha256=row['predictors_sha256'],
        score_semantics='uncalibrated_model_score', contribution_units='logit',
        feature_space='transformed_model_inputs', interpretation='model_contributions_not_disease_causes')
    if any(answer[k] != v for k, v in expected.items()):
        raise ValueError('Explanation identity/contract differs')
    if answer['feature_contract_sha256'] != (row.get('feature_contract_sha256') or digest(FULL_CONTRACT)):
        raise ValueError('Feature contract differs')
    terms = answer['terms']
    if not isinstance(terms, list) or not 1 <= len(terms) <= 1024:
        raise ValueError('Invalid term count')
    if row['model_manifest_sha256'] == HOURLY_MODEL_PIN and [t['feature'] for t in terms] != list(FEATURES):
        raise ValueError('Weather feature order differs')
    names = set()
    for term in terms:
        name = term['feature']
        if not isinstance(name, str) or not 1 <= len(name) <= 240 or name in names:
            raise ValueError('Invalid transformed feature')
        names.add(name)
        if any(not number(term[k]) for k in ('coefficient', 'transformed_value', 'contribution_logit')):
            raise ValueError('Non-finite term')
        if abs(term['coefficient']*term['transformed_value']-term['contribution_logit']) > 1e-12:
            raise ValueError('Term does not reconstruct')
    keys = ('intercept', 'sum_contributions', 'logit', 'reconstructed_score', 'score', 'reconstruction_error')
    if any(not number(answer[k]) for k in keys):
        raise ValueError('Non-finite reconstruction')
    total = math.fsum(t['contribution_logit'] for t in terms)
    logit = answer['intercept']+total
    score = 1/(1+math.exp(-logit)) if logit >= 0 else math.exp(logit)/(1+math.exp(logit))
    for actual, target in [(answer['sum_contributions'], total), (answer['logit'], logit),
                           (answer['reconstructed_score'], score), (answer['score'], score), (score, row['score'])]:
        if abs(actual-target) > 1e-12:
            raise ValueError('Explanation does not match stored score')
    if not 0 <= answer['reconstruction_error'] <= 1e-12 or answer['reasons']:
        raise ValueError('Invalid explanation diagnostics')


def enable_forecast_history(app, path):
    bp = Blueprint('forecast_history', __name__, url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse, limit_response)
    bp.register_error_handler(FarmError, lambda e: (jsonify(success=False, error=dict(code=e.code, message=e.message)), e.status))

    @bp.get('/seasons/<uuid:id>/forecast-trend')
    @require_auth
    def trend(id):
        with connect(current_app.config) as core, journal_db(path) as db:
            season = dict(owned(core, 'seasons', id))
            allowed = {'model_pin', 'horizon_hours', 'from', 'to'}
            args = request.args
            if set(args)-allowed-{'page', 'page_size'} or any(len(args.getlist(k)) != 1 for k in args):
                raise FarmError('invalid_forecast_query', 'Query lịch sử không hợp lệ.')
            where, params = ['user_id=?', 'season_id=?'], [g.user['id'], str(id)]
            try:
                if 'model_pin' in args:
                    if not re.fullmatch('[0-9a-f]{64}', args['model_pin']):
                        raise ValueError('Bad pin')
                    where.append('model_pin=?'); params.append(args['model_pin'])
                if 'horizon_hours' in args:
                    value = args['horizon_hours']
                    if not value.isascii() or not value.isdigit() or len(value) > 3 or not 1 <= int(value) <= 744:
                        raise ValueError('Bad horizon')
                    where.append("json_extract(result_json,'$.horizon_hours')=?"); params.append(int(value))
                bounds = {key: issue_us(args[key]) for key in ('from', 'to') if key in args}
                if 'from' in bounds and 'to' in bounds and bounds['from'] > bounds['to']:
                    raise ValueError('Reversed time')
                for key, operator in [('from', '>='), ('to', '<=')]:
                    if key in bounds:
                        where.append("forecast_issue_us(json_extract(result_json,'$.issued_at'))"+operator+'?')
                        params.append(bounds[key])
            except (ValueError, TypeError, OverflowError, AttributeError):
                raise FarmError('invalid_forecast_query', 'Pin/horizon hoặc khoảng issue time không hợp lệ.')
            db.create_function('forecast_issue_us', 1, issue_us, deterministic=True)
            try:
                page = paginate(db, 'synthetic_forecasts', ' AND '.join(where), params,
                    lambda r: point(db, r, season),
                    order="forecast_issue_us(json_extract(result_json,'$.issued_at')) DESC,created_at DESC,id DESC",
                    allowed_query=allowed).get_json()
                # Detect revisions sharing an issue even when pagination splits them.
                times = sorted({issue_us(p['issued_at']) for p in page['items']})
                if times:
                    visible = {p['id']: p for p in page['items']}
                    candidates = db.execute('''SELECT * FROM synthetic_forecasts WHERE user_id=? AND season_id=?
                        AND forecast_issue_us(json_extract(result_json,'$.issued_at')) IN ('''+','.join('?' for _ in times)+')',
                        [g.user['id'], str(id), *times]).fetchall()
                    counts = {}
                    for candidate in candidates:
                        p = visible.get(candidate['id'])
                        if p is None:
                            p = point(db, candidate, season)
                        key = (p['series_key'], issue_us(p['issued_at']))
                        counts[key] = counts.get(key, 0)+1
                    for p in page['items']:
                        p['same_issue_count'] = counts[(p['series_key'], issue_us(p['issued_at']))]
            except (sqlite3.DatabaseError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise FarmError('forecast_storage_error', 'Không thể đọc lịch sử dự báo hợp lệ.', 500)
            page.update(schema_version='aegis-forecast-trend-v1', comparison_scope='returned_page',
                        score_semantics='uncalibrated_model_score', series=comparisons(page['items']))
            return jsonify(page)

    @bp.get('/forecasts/<uuid:id>/explanation')
    @require_auth
    def explanation(id):
        with journal_db(path) as db:
            stored = db.execute('SELECT * FROM synthetic_forecasts WHERE id=? AND user_id=?', (str(id), g.user['id'])).fetchone()
            if stored is None:
                raise FarmError('resource_not_found', 'Không tìm thấy dự báo.', 404)
            if request.args:
                raise FarmError('invalid_forecast_query', 'Giải thích dùng đúng snapshot đã lưu, không nhận query.')
            row = record(stored)
            payload = snapshot(db, row)
        if row['status'] == 'insufficient_data':
            return jsonify(success=True, item=dict(schema_version='aegis-forecast-explanation-v1', forecast_id=str(id),
                status='insufficient_data', source='synthetic', field_validated=False,
                model_manifest_sha256=row['model_manifest_sha256'], model_version=row['model_version'],
                score=None, terms=[], reasons=row['reasons'], explanation_scope='stored_abstention'))
        if payload is None:
            raise FarmError('forecast_snapshot_missing', 'Dự báo này không lưu snapshot để giải thích.', 409)
        if row['model_manifest_sha256'] not in (MODEL_PIN, HOURLY_MODEL_PIN):
            raise FarmError('forecast_model_unsupported', 'Worker hiện không giữ artifact đúng pin của dự báo này.', 409)
        try:
            with requests.Session() as session:
                session.trust_env = False
                port = current_app.config.get('FORECAST_WORKER_PORT', 8001)
                response = session.post(f'http://127.0.0.1:{port}/explain',
                    json=dict(model_manifest_sha256=row['model_manifest_sha256'], input_snapshot=payload),
                    timeout=(2, 10), allow_redirects=False)
            if response.status_code == 503:
                raise FarmError('model_unavailable', 'Artifact đúng pin chưa sẵn sàng để giải thích.', 503)
            response.raise_for_status()
            answer = response.json()
            check_explanation(answer, row)
        except requests.ConnectionError:
            raise FarmError('model_unavailable', 'Không kết nối được worker để giải thích.', 503)
        except requests.Timeout:
            raise FarmError('forecast_timeout', 'Worker giải thích phản hồi quá chậm.', 504)
        except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise FarmError('forecast_explanation_invalid', 'Giải thích không khớp model, snapshot hoặc score đã lưu.', 502)
        answer['forecast_id'] = str(id)
        return jsonify(success=True, item=answer)

    app.register_blueprint(bp)
