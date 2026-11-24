"""Durable owner-scoped forecast schedules, executed by a separate worker."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import UUID, uuid4

from flask import Blueprint, current_app, g, jsonify, request

from app.auth import require_auth
from app.farm import FarmError, LimitResponse, body, limit_response, owned, paginate, private, text
from app.storage import connect
from pilot_forecast import HOURLY_MODEL_PIN as MODEL_PIN, issue_stored_forecast
from pilot_journal import journal_db
from pilot_store import StoreLease, validate_storage
from telemetry_tool import digest

MAX_ATTEMPTS = 3
RETRY_SECONDS = 30


def now():
    return datetime.now(timezone.utc)


def initialize(path):
    with journal_db(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_jobs(
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, season_id TEXT NOT NULL,
            stream_id TEXT NOT NULL, name TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
            enabled INTEGER NOT NULL, version INTEGER NOT NULL, next_run_at TEXT NOT NULL,
            created_at TEXT NOT NULL, command_json TEXT NOT NULL, command_sha256 TEXT NOT NULL,
            UNIQUE(user_id,stream_id), FOREIGN KEY(stream_id,user_id) REFERENCES streams(id,user_id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_runs(
            id TEXT PRIMARY KEY, forecast_job_id TEXT NOT NULL REFERENCES forecast_jobs(id),
            user_id TEXT NOT NULL, season_id TEXT NOT NULL, job_version INTEGER NOT NULL,
            scheduled_at TEXT NOT NULL, issued_at TEXT NOT NULL,
            hourly_source_id TEXT REFERENCES hourly_sources(id), model_pin TEXT NOT NULL,
            status TEXT NOT NULL, attempt_count INTEGER NOT NULL, next_attempt_at TEXT NOT NULL,
            forecast_id TEXT REFERENCES synthetic_forecasts(id), error_code TEXT,
            created_at TEXT NOT NULL, finished_at TEXT, UNIQUE(forecast_job_id,scheduled_at,job_version))''')
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS forecast_one_active_run
            ON forecast_runs(forecast_job_id) WHERE status IN ('pending','retry','running')''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_attempts(
            id TEXT PRIMARY KEY, forecast_run_id TEXT NOT NULL REFERENCES forecast_runs(id),
            number INTEGER NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
            finished_at TEXT, error_code TEXT, UNIQUE(forecast_run_id,number))''')
        db.execute('CREATE INDEX IF NOT EXISTS forecast_runs_owner ON forecast_runs(user_id,forecast_job_id,created_at,id)')


def interval(value):
    if type(value) is not int or not 60 <= value <= 86400:
        raise FarmError('invalid_forecast_schedule', 'interval_seconds cần số nguyên từ60 đến86400.')
    return value


def enable_forecast_schedules(app, storage):
    path = storage/'telemetry.sqlite3'
    initialize(path)
    bp = Blueprint('forecast_schedules', __name__, url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse, limit_response)
    bp.register_error_handler(FarmError, lambda e: (jsonify(success=False, error=dict(code=e.code, message=e.message)), e.status))

    def scope(db, core, stream_id):
        stream = db.execute('SELECT * FROM streams WHERE id=? AND user_id=?', (str(stream_id), g.user['id'])).fetchone()
        if stream is None:
            raise FarmError('resource_not_found', 'Không tìm thấy nguồn đo.', 404)
        season = owned(core, 'seasons', stream['season_id'])
        owned(core, 'plots', season['plot_id'])
        return stream

    def job(db, core, identifier):
        row = db.execute('SELECT * FROM forecast_jobs WHERE id=? AND user_id=?', (str(identifier), g.user['id'])).fetchone()
        if row is None:
            raise FarmError('resource_not_found', 'Không tìm thấy lịch dự báo.', 404)
        scope(db, core, row['stream_id'])
        return row

    def item(row):
        return {**{key: row[key] for key in ('id', 'season_id', 'stream_id', 'name', 'interval_seconds',
                                            'version', 'next_run_at', 'created_at')},
                'enabled': bool(row['enabled']), 'max_attempts': MAX_ATTEMPTS}

    @bp.route('/environment-streams/<uuid:stream_id>/forecast-jobs', methods=['GET', 'POST'])
    @require_auth
    def jobs(stream_id):
        data = body({'client_job_id', 'name', 'interval_seconds', 'enabled'}) if request.method == 'POST' else None
        with connect(current_app.config) as core, journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            stream = scope(db, core, stream_id)
            if data is None:
                return paginate(db, 'forecast_jobs', 'user_id=? AND stream_id=?', (g.user['id'], str(stream_id)), item)
            try:
                identifier = str(UUID(data['client_job_id']))
            except (ValueError, TypeError, AttributeError):
                raise FarmError('invalid_forecast_schedule', 'client_job_id cần UUID.')
            if type(data['enabled']) is not bool or json.loads(stream['metadata_json'])['source'] != 'synthetic':
                raise FarmError('invalid_forecast_schedule', 'Lịch v1 dùng nguồn synthetic và enabled boolean.')
            command = dict(data, client_job_id=identifier, name=text(data['name']), interval_seconds=interval(data['interval_seconds']))
            old = db.execute('SELECT * FROM forecast_jobs WHERE id=?', (identifier,)).fetchone()
            if old:
                if old['user_id'] != g.user['id'] or old['stream_id'] != str(stream_id) or old['command_sha256'] != digest(command):
                    raise FarmError('forecast_job_conflict', 'UUID job đã có nội dung khác.', 409)
                return jsonify(success=True, item=item(old), replayed=True)
            if db.execute('SELECT 1 FROM forecast_jobs WHERE user_id=? AND stream_id=?', (g.user['id'], str(stream_id))).fetchone():
                raise FarmError('forecast_job_conflict', 'Nguồn đo đã có lịch dự báo.', 409)
            at = now().isoformat()
            db.execute('INSERT INTO forecast_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (identifier, g.user['id'], stream['season_id'], str(stream_id), command['name'],
                        command['interval_seconds'], int(command['enabled']), 1, at, at, json.dumps(command), digest(command)))
            return jsonify(success=True, item=item(job(db, core, identifier)), replayed=False), 201

    @bp.route('/forecast-jobs/<uuid:identifier>', methods=['GET', 'PUT'])
    @require_auth
    def controls(identifier):
        data = body({'base_version', 'enabled', 'interval_seconds'}) if request.method == 'PUT' else None
        with connect(current_app.config) as core, journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            row = job(db, core, identifier)
            if data is None:
                return jsonify(success=True, item=item(row))
            if type(data['base_version']) is not int or data['base_version'] < 1 or type(data['enabled']) is not bool:
                raise FarmError('invalid_forecast_schedule', 'base_version và enabled sai kiểu.')
            seconds = interval(data['interval_seconds'])
            same = bool(row['enabled']) == data['enabled'] and row['interval_seconds'] == seconds
            if same and data['base_version'] in (row['version'], row['version']-1):
                return jsonify(success=True, item=item(row), replayed=True)
            if data['base_version'] != row['version']:
                raise FarmError('forecast_job_conflict', 'Lịch đã đổi, hãy tải version mới.', 409)
            at = now().isoformat()
            db.execute('UPDATE forecast_jobs SET enabled=?,interval_seconds=?,version=version+1,next_run_at=? WHERE id=?',
                       (int(data['enabled']), seconds, at, str(identifier)))
            db.execute("""UPDATE forecast_runs SET status='cancelled',error_code='job_updated',finished_at=?
                WHERE forecast_job_id=? AND status IN ('pending','retry')""", (at, str(identifier)))
            return jsonify(success=True, item=item(job(db, core, identifier)), replayed=False)

    @bp.get('/forecast-jobs/<uuid:identifier>/runs')
    @require_auth
    def runs(identifier):
        with connect(current_app.config) as core, journal_db(path) as db:
            job(db, core, identifier)
            return paginate(db, 'forecast_runs', 'forecast_job_id=? AND user_id=?', (str(identifier), g.user['id']))

    @bp.get('/forecast-runs/<uuid:identifier>')
    @require_auth
    def run_detail(identifier):
        with connect(current_app.config) as core, journal_db(path) as db:
            row = db.execute('SELECT * FROM forecast_runs WHERE id=? AND user_id=?', (str(identifier), g.user['id'])).fetchone()
            if row is None:
                raise FarmError('resource_not_found', 'Không tìm thấy lượt chạy.', 404)
            job(db, core, row['forecast_job_id'])
            attempts = db.execute('SELECT * FROM forecast_attempts WHERE forecast_run_id=? ORDER BY number', (str(identifier),)).fetchall()
            return jsonify(success=True, item=dict(**dict(row), attempts=[dict(a) for a in attempts]))

    app.register_blueprint(bp)


class ForecastRunner:
    def __init__(self, app, storage):
        self.app = app
        self.storage = validate_storage(storage)
        self.path = self.storage/'telemetry.sqlite3'
        self.checkpoint = lambda stage: None

    def tick(self, at=None):
        at = at or now()
        if at.tzinfo is None or at > now():
            raise ValueError('Tick requires an available timezone-aware time')
        at = at.astimezone(timezone.utc)
        lease = StoreLease(self.storage, '.automation.lock')
        try:
            lease.__enter__()
        except RuntimeError:
            return dict(status='busy', runs=[])
        try:
            with journal_db(self.path) as db:
                jobs = db.execute("""SELECT j.* FROM forecast_jobs j WHERE
                    (j.enabled=1 AND ((j.next_run_at<=? AND NOT EXISTS(SELECT 1 FROM forecast_runs r WHERE r.forecast_job_id=j.id
                        AND r.status IN ('pending','retry','running')))
                    OR EXISTS(SELECT 1 FROM forecast_runs r WHERE r.forecast_job_id=j.id
                        AND r.status IN ('pending','retry','running') AND r.next_attempt_at<=?)))
                    OR EXISTS(SELECT 1 FROM forecast_runs r WHERE r.forecast_job_id=j.id AND r.status='running')
                    ORDER BY j.next_run_at,j.id LIMIT 100""", (at.isoformat(), at.isoformat())).fetchall()
            results = []
            for job in jobs:
                with self.app.app_context():
                    results.append(self.run(job['id'], at))
            return dict(status='polled', runs=results)
        finally:
            lease.__exit__(None, None, None)

    def claim(self, identifier, at):
        with journal_db(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            job = db.execute('SELECT * FROM forecast_jobs WHERE id=?', (identifier,)).fetchone()
            active = db.execute("SELECT * FROM forecast_runs WHERE forecast_job_id=? AND status IN ('pending','retry','running')", (identifier,)).fetchone()
            if not job['enabled'] and (active is None or active['status'] != 'running'):
                return None
            if active:
                if active['next_attempt_at'] > at.isoformat():
                    return None
                return dict(active)
            if job['next_run_at'] > at.isoformat():
                return None
            source = db.execute('''SELECT id FROM hourly_sources WHERE user_id=? AND season_id=? AND stream_id=?
                AND created_at<=? ORDER BY revision DESC LIMIT 1''',
                (job['user_id'], job['season_id'], job['stream_id'], at.isoformat())).fetchone()
            run_id = str(uuid4())
            status = 'pending' if source else 'skipped'
            db.execute('INSERT INTO forecast_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (run_id, identifier, job['user_id'], job['season_id'], job['version'], job['next_run_at'], at.isoformat(),
                 source['id'] if source else None, MODEL_PIN, status, 0, at.isoformat(), None,
                 None if source else 'hourly_source_missing', at.isoformat(), None if source else at.isoformat()))
            db.execute('UPDATE forecast_jobs SET next_run_at=? WHERE id=?',
                       ((at+timedelta(seconds=job['interval_seconds'])).isoformat(), identifier))
            return dict(db.execute('SELECT * FROM forecast_runs WHERE id=?', (run_id,)).fetchone())

    def finish(self, run, at, status, forecast_id=None, error=None, attempt_status=None):
        at = max(at, now())
        with journal_db(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            retry_at = at+timedelta(seconds=RETRY_SECONDS*2**max(0, run['attempt_count']-1))
            db.execute('UPDATE forecast_runs SET status=?,forecast_id=?,error_code=?,next_attempt_at=?,finished_at=? WHERE id=?',
                (status, forecast_id, error, retry_at.isoformat(), None if status == 'retry' else at.isoformat(), run['id']))
            if run['attempt_count']:
                db.execute('UPDATE forecast_attempts SET status=?,finished_at=?,error_code=? WHERE forecast_run_id=? AND number=?',
                    (attempt_status or status, at.isoformat(), error, run['id'], run['attempt_count']))
        return dict(id=run['id'], status=status, forecast_id=forecast_id, error_code=error)

    def run(self, identifier, at):
        run = self.claim(identifier, at)
        if run is None or run['status'] == 'skipped':
            return dict(id=run['id'] if run else None, status='skipped')
        with connect(self.app.config) as core:
            user = core.execute('SELECT id,email FROM users WHERE id=?', (run['user_id'],)).fetchone()
            if user is None:
                return self.finish(run, at, 'failed', error='owner_unavailable')
            g.user = dict(user)
            try:
                season = dict(owned(core, 'seasons', run['season_id']))
            except FarmError:
                return self.finish(run, at, 'failed', error='scope_unavailable')
        if run['model_pin'] != MODEL_PIN:
            return self.finish(run, at, 'failed', error='model_changed')
        if run['status'] == 'running':
            try:
                forecast, _ = issue_stored_forecast(self.path, season, run['hourly_source_id'], run['issued_at'], replay_only=True)
                return self.finish(run, at, 'succeeded', forecast['id'], attempt_status='recovered')
            except FarmError as exc:
                if exc.code != 'forecast_not_found':
                    return self.finish(run, at, 'failed', error=exc.code)
            with journal_db(self.path) as db:
                job = db.execute('SELECT enabled,version FROM forecast_jobs WHERE id=?', (identifier,)).fetchone()
            if not job['enabled'] or job['version'] != run['job_version']:
                return self.finish(run, at, 'cancelled', error='job_updated', attempt_status='interrupted')
            status = 'retry' if run['attempt_count'] < MAX_ATTEMPTS else 'failed'
            return self.finish(run, at, status, error='interrupted', attempt_status='interrupted')
        with journal_db(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            job = db.execute('SELECT enabled,version FROM forecast_jobs WHERE id=?', (identifier,)).fetchone()
            if not job['enabled'] or job['version'] != run['job_version']:
                db.execute("UPDATE forecast_runs SET status='cancelled',error_code='job_updated',finished_at=? WHERE id=?", (at.isoformat(), run['id']))
                return dict(id=run['id'], status='cancelled', error_code='job_updated')
            run['attempt_count'] += 1
            db.execute("UPDATE forecast_runs SET status='running',attempt_count=? WHERE id=?", (run['attempt_count'], run['id']))
            db.execute('INSERT INTO forecast_attempts VALUES (?,?,?,?,?,?,?)',
                       (str(uuid4()), run['id'], run['attempt_count'], 'running', at.isoformat(), None, None))
        self.checkpoint('before_forecast')
        try:
            forecast, _ = issue_stored_forecast(self.path, season, run['hourly_source_id'], run['issued_at'])
            self.checkpoint('after_forecast')
            return self.finish(run, at, 'succeeded', forecast['id'])
        except FarmError as exc:
            retry = exc.code in ('model_unavailable', 'forecast_timeout', 'forecast_invalid_response')
            status = 'retry' if retry and run['attempt_count'] < MAX_ATTEMPTS else 'failed'
            return self.finish(run, at, status, error=exc.code)
        except sqlite3.Error:
            status = 'retry' if run['attempt_count'] < MAX_ATTEMPTS else 'failed'
            return self.finish(run, at, status, error='storage_unavailable')
        except Exception:
            self.app.logger.error('Forecast scheduler run failed; details withheld')
            return self.finish(run, at, 'failed', error='internal_error')
