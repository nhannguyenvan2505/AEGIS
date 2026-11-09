"""Owned, revisioned hourly policies and live raw compilation in pilot storage."""
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request

from app.auth import require_auth
from app.farm import FarmError, LimitResponse, body, limit_response, owned, paginate, private, within_season
from app.storage import connect
from hourly_aggregation import aggregate, checked_policy
from pilot_journal import journal_db
from telemetry_audit import stamp
from telemetry_tool import digest, snapshot


def now():
    return datetime.now(timezone.utc)


def base_revision(value):
    if type(value) is not int or value < 0:
        raise FarmError('invalid_revision', 'base_revision cần số nguyên không âm.')
    return value


def enable_hourly(app, storage):
    path = storage/'telemetry.sqlite3'
    with journal_db(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS hourly_policies(
            stream_id TEXT NOT NULL, user_id TEXT NOT NULL, revision INTEGER NOT NULL,
            created_at TEXT NOT NULL, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
            PRIMARY KEY(stream_id,user_id,revision),
            FOREIGN KEY(stream_id,user_id) REFERENCES streams(id,user_id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS hourly_sources(
            id TEXT PRIMARY KEY, stream_id TEXT NOT NULL, user_id TEXT NOT NULL,
            season_id TEXT NOT NULL, revision INTEGER NOT NULL, policy_revision INTEGER NOT NULL,
            compile_key TEXT NOT NULL, created_at TEXT NOT NULL,
            snapshot_json TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
            UNIQUE(stream_id,user_id,revision), UNIQUE(stream_id,user_id,compile_key),
            FOREIGN KEY(stream_id,user_id,policy_revision)
                REFERENCES hourly_policies(stream_id,user_id,revision))''')
        db.execute('CREATE INDEX IF NOT EXISTS hourly_sources_owner ON hourly_sources(user_id,stream_id,created_at,id)')
    bp = Blueprint('pilot_hourly', __name__, url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse, limit_response)
    bp.register_error_handler(FarmError, lambda e: (jsonify(success=False, error=dict(code=e.code, message=e.message)), e.status))

    def parent(db, core, stream_id):
        row = db.execute('SELECT * FROM streams WHERE id=? AND user_id=?', (str(stream_id), g.user['id'])).fetchone()
        if row is None:
            raise FarmError('resource_not_found', 'Không tìm thấy nguồn đo.', 404)
        season = owned(core, 'seasons', row['season_id'])
        owned(core, 'plots', season['plot_id'])
        return row, season

    def policy_item(row):
        if digest(json.loads(row['payload_json'])) != row['payload_sha256']:
            raise FarmError('hourly_storage_error', 'Sai hash policy đã lưu.', 500)
        return dict(revision=row['revision'], policy=json.loads(row['payload_json']),
                    policy_sha256=row['payload_sha256'], created_at=row['created_at'])

    def source_item(row):
        result = json.loads(row['payload_json'])
        if digest(result) != row['payload_sha256']:
            raise FarmError('hourly_storage_error', 'Sai hash nguồn hourly đã lưu.', 500)
        return dict(id=row['id'], stream_id=row['stream_id'], season_id=row['season_id'],
                    revision=row['revision'], policy_revision=row['policy_revision'],
                    created_at=row['created_at'], result_sha256=result['result_sha256'],
                    bucket_count=len(result['buckets']),
                    statuses={status: sum(b['status'] == status for b in result['buckets'])
                              for status in ('pending', 'complete_numeric', 'partial_numeric', 'insufficient')})

    @bp.route('/environment-streams/<uuid:stream_id>/hourly-policies', methods=['GET', 'POST'])
    @require_auth
    def policies(stream_id):
        data = body({'base_revision', 'policy'}) if request.method == 'POST' else None
        with connect(current_app.config) as core, journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            stream, season = parent(db, core, stream_id)
            if data is None:
                return paginate(db, 'hourly_policies', 'stream_id=? AND user_id=?',
                                (str(stream_id), g.user['id']), policy_item, order='revision DESC')
            base = base_revision(data['base_revision'])
            client_keys = {'schema_version', 'algorithm_version', 'policy_id', 'anchor_at',
                           'interval_seconds', 'tolerance_seconds', 'arrival_grace_seconds',
                           'minimum_coverage_numerator', 'minimum_coverage_denominator',
                           'numeric_method', 'wetness_method'}
            if not isinstance(data['policy'], dict) or set(data['policy']) != client_keys:
                raise FarmError('invalid_hourly_policy', 'Policy thiếu hoặc thừa trường.')
            latest = db.execute('SELECT * FROM hourly_policies WHERE stream_id=? AND user_id=? ORDER BY revision DESC LIMIT 1',
                                (str(stream_id), g.user['id'])).fetchone()
            revision = latest['revision'] if latest else 0
            candidate = dict(data['policy'], source=json.loads(stream['metadata_json'])['source'],
                             stream_id=str(stream_id), revision=revision+1, available_at=now().isoformat())
            try:
                metadata = json.loads(stream['metadata_json'])
                if digest(metadata) != stream['metadata_sha256']:
                    raise ValueError('Metadata hash mismatch')
                candidate = checked_policy(candidate, dict(metadata=metadata, stream_id=str(stream_id),
                    owner_id=g.user['id'], season_id=season['id']), stamp(candidate['anchor_at']), now())
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise FarmError('invalid_hourly_policy', 'Policy không phù hợp nguồn đo hoặc lịch tổng hợp.')
            if latest:
                previous = policy_item(latest)['policy']
                same = all(candidate[key] == previous[key] for key in client_keys)
                if same and base in (revision, revision-1):
                    return jsonify(success=True, item=policy_item(latest), replayed=True)
            if base != revision:
                raise FarmError('hourly_revision_conflict', 'Policy đã đổi, hãy tải revision mới.', 409)
            value_hash = digest(candidate)
            db.execute('INSERT INTO hourly_policies VALUES (?,?,?,?,?,?)',
                       (str(stream_id), g.user['id'], revision+1, candidate['available_at'],
                        json.dumps(candidate, allow_nan=False), value_hash))
            return jsonify(success=True, item=dict(revision=revision+1, policy=candidate,
                           policy_sha256=value_hash, created_at=candidate['available_at']), replayed=False), 201

    @bp.get('/environment-streams/<uuid:stream_id>/hourly-policies/<int:revision>')
    @require_auth
    def policy_detail(stream_id, revision):
        with connect(current_app.config) as core, journal_db(path) as db:
            parent(db, core, stream_id)
            row = db.execute('SELECT * FROM hourly_policies WHERE stream_id=? AND user_id=? AND revision=?',
                             (str(stream_id), g.user['id'], revision)).fetchone()
            if row is None:
                raise FarmError('resource_not_found', 'Không tìm thấy policy.', 404)
            return jsonify(success=True, item=policy_item(row))

    @bp.route('/environment-streams/<uuid:stream_id>/hourly-sources', methods=['GET', 'POST'])
    @require_auth
    def sources(stream_id):
        data = body({'base_revision', 'policy_revision', 'start_at', 'end_at', 'as_of'}) if request.method == 'POST' else None
        with connect(current_app.config) as core, journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            stream, season = parent(db, core, stream_id)
            if data is None:
                return paginate(db, 'hourly_sources', 'stream_id=? AND user_id=?',
                                (str(stream_id), g.user['id']), source_item, order='revision DESC')
            base = base_revision(data['base_revision'])
            if type(data['policy_revision']) is not int or data['policy_revision'] < 1:
                raise FarmError('invalid_revision', 'policy_revision cần số nguyên dương.')
            row = db.execute('SELECT * FROM hourly_policies WHERE stream_id=? AND user_id=? AND revision=?',
                             (str(stream_id), g.user['id'], data['policy_revision'])).fetchone()
            if row is None:
                raise FarmError('resource_not_found', 'Không tìm thấy policy.', 404)
            policy = json.loads(row['payload_json'])
            if digest(policy) != row['payload_sha256']:
                raise FarmError('hourly_storage_error', 'Sai hash policy đã lưu.', 500)
            try:
                start, end, as_of = (stamp(data[key]) for key in ('start_at', 'end_at', 'as_of'))
                captured = now()
                if as_of > captured:
                    raise ValueError('Future as_of')
                within_season(start, season)
                within_season(end-timedelta(microseconds=1), season)
                tolerance = timedelta(seconds=policy['tolerance_seconds'])
                raw = snapshot(db, g.user['id'], str(stream_id), captured, 'synthetic',
                               window=(start-tolerance, end+tolerance, as_of))
                result = aggregate(raw, policy, dict(start_at=start.isoformat(), end_at=end.isoformat(), as_of=as_of.isoformat()))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise FarmError('invalid_hourly_input', 'Nguồn, cửa sổ hoặc thời điểm tổng hợp không hợp lệ.')
            key = digest(dict(policy_sha256=row['payload_sha256'], request=result['request'],
                              buckets=[b['bucket_sha256'] for b in result['buckets']]))
            latest = db.execute('SELECT MAX(revision) FROM hourly_sources WHERE stream_id=? AND user_id=?',
                                (str(stream_id), g.user['id'])).fetchone()[0] or 0
            existing = db.execute('SELECT * FROM hourly_sources WHERE stream_id=? AND user_id=? AND compile_key=?',
                                  (str(stream_id), g.user['id'], key)).fetchone()
            if existing and base in (latest, existing['revision']-1):
                return jsonify(success=True, item=source_item(existing), replayed=True)
            if base != latest:
                raise FarmError('hourly_revision_conflict', 'Nguồn hourly đã đổi, hãy tải revision mới.', 409)
            if existing:
                raise FarmError('hourly_revision_conflict', 'Yêu cầu replay cần revision hiện hành.', 409)
            persisted = max(now(), as_of).isoformat()
            result.pop('result_sha256')
            for bucket in result['buckets']:
                bucket['available_at'] = persisted
                bucket.pop('bucket_sha256')
                bucket['bucket_sha256'] = digest(bucket)
            result['result_sha256'] = digest(result)
            source_id = str(uuid4())
            input_snapshot = dict(raw_bundle=raw, policy=policy, request=result['request'], plot_id=season['plot_id'])
            db.execute('INSERT INTO hourly_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (source_id, str(stream_id), g.user['id'], season['id'], latest+1, data['policy_revision'],
                 key, persisted, json.dumps(input_snapshot, allow_nan=False), digest(input_snapshot),
                 json.dumps(result, allow_nan=False), digest(result)))
            saved = db.execute('SELECT * FROM hourly_sources WHERE id=?', (source_id,)).fetchone()
            return jsonify(success=True, item=source_item(saved), replayed=False), 201

    def source_row(db, core, source_id):
        row = db.execute('SELECT * FROM hourly_sources WHERE id=? AND user_id=?',
                         (str(source_id), g.user['id'])).fetchone()
        if row is None:
            raise FarmError('resource_not_found', 'Không tìm thấy nguồn hourly.', 404)
        parent(db, core, row['stream_id'])
        return row

    @bp.get('/hourly-sources/<uuid:source_id>')
    @require_auth
    def source_detail(source_id):
        with connect(current_app.config) as core, journal_db(path) as db:
            row = source_row(db, core, source_id)
            return jsonify(success=True, item=dict(**source_item(row), result=json.loads(row['payload_json'])))

    @bp.get('/hourly-sources/<uuid:source_id>/input')
    @require_auth
    def source_input(source_id):
        with connect(current_app.config) as core, journal_db(path) as db:
            row = source_row(db, core, source_id)
            if digest(json.loads(row['snapshot_json'])) != row['snapshot_sha256']:
                raise FarmError('hourly_storage_error', 'Sai hash đầu vào đã lưu.', 500)
            return jsonify(success=True, item=json.loads(row['snapshot_json']), snapshot_sha256=row['snapshot_sha256'])

    app.register_blueprint(bp)
