"""Append-only reference snapshots and operational follow-up for forecasts.

This module never generates training labels or turns a reported review into
platform verification. Journal/follow-up stores remain read-only here.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from flask import Blueprint, g, jsonify, request
from app.auth import require_auth
from app.farm import FarmError, LimitResponse, body, owned, paginate, private, text, limit_response
from app.storage import connect
from pilot_journal import journal_db
from forecast_history import record, snapshot
from telemetry_audit import stamp
from telemetry_tool import digest

MAX_LINKS = 500  # storage/query bound, not a research sample-size requirement


def now():
    return datetime.now(timezone.utc)


def identifier(value):
    try:
        if not isinstance(value, str): raise ValueError('Not UUID')
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise FarmError('invalid_outcome_link', 'Cần UUID hợp lệ.')


@contextmanager
def reference_store(path):
    from app.hybrid_pilot import initialized,connection
    if initialized(path):
        with connection(path,readonly=True) as db: yield db
        return
    db = None
    try:
        db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
    except sqlite3.Error:
        if db is not None: db.close()
        raise FarmError('outcome_reference_unavailable', 'Không mở được kho tham chiếu chỉ đọc.', 500)
    try:
        yield db
    finally:
        db.close()


def initialize(path):
    with journal_db(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_outcome_links(
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,season_id TEXT NOT NULL,
            forecast_id TEXT NOT NULL REFERENCES synthetic_forecasts(id),kind TEXT NOT NULL CHECK(kind IN ('observation','followup')),
            reference_id TEXT NOT NULL,reference_revision INTEGER NOT NULL,
            command_json TEXT NOT NULL,command_sha256 TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('active','retracted')),
            version INTEGER NOT NULL CHECK(version IN (1,2)),retracted_at TEXT)''')
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_forecast_outcome_active
            ON forecast_outcome_links(forecast_id,kind,reference_id,reference_revision) WHERE state='active' ''')
        db.execute('''CREATE INDEX IF NOT EXISTS idx_forecast_outcome_owner
            ON forecast_outcome_links(user_id,forecast_id,created_at,id)''')
        db.execute('''CREATE TABLE IF NOT EXISTS forecast_outcome_actions(
            id TEXT PRIMARY KEY,link_id TEXT NOT NULL REFERENCES forecast_outcome_links(id),user_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action='retract'),base_version INTEGER NOT NULL,reason TEXT NOT NULL,
            created_at TEXT NOT NULL,UNIQUE(link_id,action))''')


def assessment_time(args):
    if set(args)-{'as_of','page','page_size'} or any(len(args.getlist(k)) != 1 for k in args):
        raise FarmError('invalid_outcome_query', 'Query outcome không hợp lệ.')
    assessed = now()
    try:
        cutoff = stamp(args['as_of']) if 'as_of' in args else assessed
        if cutoff > assessed: raise ValueError('Future as-of')
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise FarmError('invalid_outcome_query', 'as_of cần timezone và không ở tương lai.')
    return cutoff, assessed


def owned_forecast(core, db, forecast_id):
    stored = db.execute('SELECT * FROM synthetic_forecasts WHERE id=? AND user_id=?',(str(forecast_id),g.user['id'])).fetchone()
    if stored is None: raise FarmError('resource_not_found','Không tìm thấy dự báo.',404)
    row = record(stored)
    owned(core,'seasons',row['season_id'])
    try:
        if stamp(row['target_window_end']) != stamp(row['issued_at'])+timedelta(hours=row['horizon_hours']):
            raise ValueError('Target differs')
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise FarmError('forecast_storage_error','Cửa sổ dự báo đã lưu không hợp lệ.',500)
    if row['scenario'] not in ('hourly','source') or snapshot(db,row) is None:
        raise FarmError('forecast_outcome_not_supported','Cần forecast có lịch sử hourly và snapshot gốc; fixture tĩnh không được dùng.',409)
    return row


def reference(journal, followup, kind, reference_id, user_id, cutoff):
    try:
        if kind == 'observation':
            row = journal.execute('''SELECT * FROM history WHERE visit_id=? AND user_id=? AND created_at<=?
                ORDER BY revision DESC LIMIT 1''',(reference_id,user_id,cutoff.isoformat())).fetchone()
            if row is None: return None
            payload = json.loads(row['payload_json'])
            review = payload['review']
            if review is not None and (not isinstance(review,dict) or set(review)!={'reviewer_alias','reviewed_at','reference'}
                    or not isinstance(review['reviewer_alias'],str) or not review['reviewer_alias'].strip()
                    or not isinstance(review['reference'],str) or not review['reference'].strip()):
                raise ValueError('Invalid review declaration')
            if (digest(payload) != row['payload_sha256'] or payload['finding'] not in ('absent','present','uncertain')
                    or payload['record_status'] not in ('active','voided') or payload['platform_verified'] is not False
                    or payload['verification'] != ('confirmed' if review else 'unverified')
                    or payload['verification_provenance'] != ('user_reported_external_review' if review else 'not_verified')
                    or stamp(row['observed_at']) > stamp(row['created_at'])):
                raise ValueError('Bad observation snapshot')
            if review and (payload['finding']=='uncertain' or not stamp(row['observed_at']) <= stamp(review['reviewed_at']) <= stamp(row['created_at'])):
                raise ValueError('Bad reported review')
            return dict(id=reference_id,season_id=row['season_id'],source=row['source'],disease='leaf_blast',plant_part='leaf',
                revision=row['revision'],observed_at=row['observed_at'],scheduled=bool(row['scheduled']),
                recorded_at=row['created_at'],available_at=row['created_at'],payload=payload,
                payload_sha256=row['payload_sha256'],verification_scope='user_reported_external_review' if review else 'not_verified',
                platform_verified=False,label_approved_for_training=False)
        row = followup.execute('''SELECT c.*,e.version,e.state,e.payload_json AS event_json,e.payload_sha256 AS event_sha256,
                e.created_at AS updated_at FROM cases c JOIN events e ON e.case_id=c.id AND e.user_id=c.user_id
                WHERE c.id=? AND c.user_id=? AND e.created_at<=? ORDER BY e.version DESC LIMIT 1''',
                (reference_id,user_id,cutoff.isoformat())).fetchone()
        if row is None: return None
        if digest(json.loads(row['assessment_json'])) != row['assessment_sha256'] or digest(json.loads(row['event_json'])) != row['event_sha256']:
            raise ValueError('Bad follow-up snapshot')
        return dict(id=reference_id,season_id=row['season_id'],source='mock',revision=row['version'],state=row['state'],
            created_at=row['created_at'],recorded_at=row['updated_at'],available_at=row['updated_at'],
            assessment_id=row['assessment_id'],assessment_sha256=row['assessment_sha256'],event_sha256=row['event_sha256'],
            workflow_reference_only=True,platform_verified=False,label_approved_for_training=False)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, sqlite3.DatabaseError):
        raise FarmError('outcome_reference_storage_error','Tham chiếu journal/follow-up sai hash hoặc cấu trúc.',500)


def phase(reference_snapshot, forecast):
    if reference_snapshot.get('workflow_reference_only'): return 'workflow_reference'
    observed = stamp(reference_snapshot['observed_at'])
    if observed <= stamp(forecast['issued_at']): return 'before_or_at_issue'
    if observed <= stamp(forecast['target_window_end']): return 'within_target_window'
    return 'after_target_window'


def validate_link(stored, forecast):
    try:
        command, captured = json.loads(stored['command_json']), json.loads(stored['snapshot_json'])
        if (digest(command) != stored['command_sha256'] or digest(captured) != stored['snapshot_sha256']
                or command['client_link_id'] != stored['id'] or captured['reference']['id'] != stored['reference_id']
                or captured['reference']['revision'] != stored['reference_revision']
                or captured['forecast']['id'] != stored['forecast_id'] or captured['reference']['season_id'] != stored['season_id']
                or captured['forecast']['forecast_sha256'] != digest(forecast)):
            raise ValueError('Link identity/hash differs')
    except (ValueError, TypeError, KeyError, AttributeError):
        raise FarmError('forecast_outcome_storage_error','Liên kết outcome sai hash/định danh.',500)
    return command,captured


def link_item(db, journal, followup, stored, cutoff, forecast):
    command,captured = validate_link(stored,forecast)
    actual = db.execute('SELECT * FROM forecast_outcome_actions WHERE link_id=?',(stored['id'],)).fetchone()
    if (actual is None and (stored['state']!='active' or stored['version']!=1)
            or actual is not None and (stored['state']!='retracted' or stored['version']!=2
                or actual['user_id']!=stored['user_id'] or actual['base_version']!=1
                or actual['created_at']!=stored['retracted_at'] or stamp(actual['created_at'])<stamp(stored['created_at']))):
        raise FarmError('forecast_outcome_storage_error','Ledger retraction không khớp state/version.',500)
    action = actual if actual is not None and stamp(actual['created_at'])<=cutoff else None
    effective_state = 'retracted' if action else 'active'
    head = reference(journal,followup,stored['kind'],stored['reference_id'],g.user['id'],cutoff)
    if head is None:
        status = 'reference_unavailable'
    elif head['season_id'] != stored['season_id']:
        status = 'reference_scope_changed'
    elif stored['kind']=='observation' and head['payload']['record_status']=='voided':
        status = 'voided'
    elif head['revision'] != stored['reference_revision']:
        status = 'stale_revision'
    elif digest(head) != digest(captured['reference']):
        status = 'changed_snapshot'
    else:
        status = 'current'
    usable = effective_state=='active' and status=='current' and stored['kind']=='observation'
    return dict(schema_version='aegis-forecast-outcome-link-v1',id=stored['id'],forecast_id=stored['forecast_id'],
        kind=stored['kind'],reference_id=stored['reference_id'],reference_revision=stored['reference_revision'],
        created_at=stored['created_at'],state=effective_state,version=2 if action else 1,
        retraction=dict(reason=action['reason'],recorded_at=action['created_at']) if action else None,
        reason=command['reason'],snapshot=captured,snapshot_sha256=stored['snapshot_sha256'],
        reference_status=status,reference_assessed_as_of=cutoff.isoformat(),current_reference_revision=head['revision'] if head else None,
        usable_for_observation_summary=usable,label_approved_for_training=False,platform_verified=False)


def summary(forecast, links, cutoff):
    observations = [x for x in links if x['usable_for_observation_summary']]
    refs = [x['snapshot']['reference'] for x in observations]
    baseline = [r for r in refs if phase(r,forecast)=='before_or_at_issue']
    within = [r for r in refs if phase(r,forecast)=='within_target_window']
    after = [r for r in refs if phase(r,forecast)=='after_target_window']
    baseline_present = any(r['payload']['finding']=='present' for r in baseline)
    present = [r for r in within if r['payload']['finding']=='present']
    reviewed = [r for r in present if r['payload']['review'] is not None]
    uncertain = any(r['payload']['finding']=='uncertain' or r['payload']['verification']=='unverified' for r in within)
    unusable = any(x['kind']=='observation' and x['state']=='active' and x['reference_status']!='current' for x in links)
    closed = cutoff >= stamp(forecast['target_window_end'])
    if baseline_present: evidence = 'baseline_reported_present'
    elif reviewed: evidence = 'review_reported_present'
    elif present: evidence = 'unverified_report'
    elif uncertain or unusable: evidence = 'uncertain'
    elif within: evidence = 'reported_absent_at_visits'
    else: evidence = 'not_observed'
    if evidence in ('baseline_reported_present','review_reported_present','unverified_report'): status=evidence
    elif closed: status='censored'
    elif evidence=='uncertain': status='uncertain'
    else: status='following_up'
    reviewed_present = sorted([r for r in within+after if r['payload']['finding']=='present' and r['payload']['review']],key=lambda r:stamp(r['observed_at']))
    interval = None
    if reviewed_present:
        upper = reviewed_present[0]
        lower = sorted([r for r in refs if r['payload']['finding']=='absent' and r['payload']['review']
                        and stamp(r['observed_at']) < stamp(upper['observed_at'])],key=lambda r:stamp(r['observed_at']))
        if lower:
            interval = dict(lower_open=lower[-1]['observed_at'],upper_closed=upper['observed_at'],
                absent_observation_id=lower[-1]['id'],present_observation_id=upper['id'],
                crosses_issue_time=stamp(lower[-1]['observed_at']) <= stamp(forecast['issued_at']) < stamp(upper['observed_at']),
                crosses_target_end=stamp(lower[-1]['observed_at']) <= stamp(forecast['target_window_end']) < stamp(upper['observed_at']),
                semantics='between_linked_reported_visits_not_validated_onset',platform_verified=False)
    known = stamp(forecast['created_at'])<=cutoff
    if not known: status='forecast_not_yet_available'
    elif cutoff<stamp(forecast['issued_at']): status='not_yet_issued'
    return dict(schema_version='aegis-forecast-outcome-v1',forecast_id=forecast['id'],issued_at=forecast['issued_at'],
        target_window_end=forecast['target_window_end'],horizon_hours=forecast['horizon_hours'],
        model_manifest_sha256=forecast['model_manifest_sha256'],forecast_status=forecast['status'],forecast_score=forecast['score'],
        source=forecast['source'],field_validated=False,as_of=cutoff.isoformat(),
        status=status,evidence_status=evidence,tracking_status='window_elapsed' if closed else 'following_up',window_closed=closed,
        forecast_known_at_as_of=known,
        evidence_scope='explicitly_linked_references_only_not_exhaustive',linked_references=len(links),
        active_references=sum(x['state']=='active' for x in links),usable_observations=len(refs),
        baseline_observations=len(baseline),baseline_known_at_issue=sum(stamp(r['available_at'])<=stamp(forecast['issued_at']) for r in baseline),
        baseline_reported_later=sum(stamp(r['available_at'])>stamp(forecast['issued_at']) for r in baseline),
        within_window_observations=len(within),after_window_observations=len(after),
        unusable_active_links=sum(x['state']=='active' and x['reference_status']!='current' for x in links),
        workflow_references=sum(x['kind']=='followup' and x['state']=='active' and x['reference_status']=='current' for x in links),
        reported_visit_interval=interval,event_y=None,label_approved_for_training=False,platform_verified=False,
        interpretation='operational_followup_not_verified_disease_label')


def enable_forecast_outcomes(app, storage):
    path = storage/'telemetry.sqlite3'
    initialize(path)
    bp = Blueprint('forecast_outcomes',__name__,url_prefix='/api/farm')
    bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    @bp.route('/forecasts/<uuid:id>/outcome-links',methods=['GET','POST'])
    @require_auth
    def links(id):
        # Read source transactions outlive the telemetry transaction, so the
        # pinned current revision cannot commit a change before the link commits.
        with connect(app.config) as core, reference_store(storage/'journal.sqlite3') as journal, \
                reference_store(storage/'followup.sqlite3') as followup, journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if request.method=='POST' else 'BEGIN')
            forecast = owned_forecast(core,db,id)
            if request.method=='GET':
                cutoff,assessed=assessment_time(request.args)
                page=paginate(db,'forecast_outcome_links','forecast_id=? AND user_id=? AND created_at<=?',
                    (str(id),g.user['id'],cutoff.isoformat()),lambda r:link_item(db,journal,followup,r,cutoff,forecast),allowed_query={'as_of'}).get_json()
                page.update(as_of=cutoff.isoformat(),assessed_at=assessed.isoformat())
                return jsonify(page)
            if request.args: raise FarmError('invalid_outcome_query','POST liên kết không nhận query.')
            data=body({'client_link_id','kind','reference_id','reference_revision','reason'})
            command=dict(client_link_id=identifier(data['client_link_id']),kind=data['kind'],reference_id=identifier(data['reference_id']),
                         reference_revision=data['reference_revision'],reason=text(data['reason'],500))
            if command['kind'] not in ('observation','followup') or type(command['reference_revision']) is not int or not 1<=command['reference_revision']<=2147483647:
                raise FarmError('invalid_outcome_link','Kind hoặc revision tham chiếu không hợp lệ.')
            at=now()
            if at<stamp(forecast['created_at']):
                raise FarmError('forecast_outcome_clock_error','Giờ liên kết phải sau thời điểm forecast được lưu.',409)
            existing=db.execute('SELECT * FROM forecast_outcome_links WHERE id=?',(command['client_link_id'],)).fetchone()
            if existing:
                if existing['user_id']!=g.user['id'] or existing['forecast_id']!=str(id) or existing['command_sha256']!=digest(command):
                    raise FarmError('outcome_link_conflict','Mã liên kết đã có nội dung khác.',409)
                return jsonify(success=True,item=link_item(db,journal,followup,existing,at,forecast),replayed=True)
            ref=reference(journal,followup,command['kind'],command['reference_id'],g.user['id'],at)
            if ref is None or ref['season_id']!=forecast['season_id']:
                raise FarmError('resource_not_found','Không tìm thấy tham chiếu cùng owner/mùa vụ.',404)
            if ref['revision']!=command['reference_revision']:
                raise FarmError('outcome_reference_revision_conflict','Tham chiếu đã đổi revision, hãy tải lại.',409)
            if command['kind']=='observation':
                if ref['source']!=forecast['source']:
                    raise FarmError('outcome_source_mismatch','Không ghép observation thực với forecast synthetic.',409)
                if ref['payload']['record_status']!='active':
                    raise FarmError('outcome_reference_voided','Observation đã void, không thể tạo liên kết mới.',409)
            duplicate=db.execute('SELECT id FROM forecast_outcome_links WHERE forecast_id=? AND kind=? AND reference_id=? AND reference_revision=? AND state=?',
                (str(id),command['kind'],command['reference_id'],command['reference_revision'],'active')).fetchone()
            if duplicate: raise FarmError('outcome_link_exists','Revision này đã được liên kết, không tạo bằng chứng trùng.',409)
            if db.execute('SELECT COUNT(*) FROM forecast_outcome_links WHERE forecast_id=?',(str(id),)).fetchone()[0]>=MAX_LINKS:
                raise FarmError('outcome_link_limit','Đã đạt giới hạn lưu trữ liên kết cho forecast.',409)
            captured=dict(forecast=dict(id=forecast['id'],issued_at=forecast['issued_at'],target_window_end=forecast['target_window_end'],
                model_manifest_sha256=forecast['model_manifest_sha256'],input_sha256=forecast['input_sha256'],
                forecast_sha256=digest(forecast)),reference=ref,phase=phase(ref,forecast),
                known_at_issue=stamp(ref['available_at'])<=stamp(forecast['issued_at']),
                platform_verified=False,label_approved_for_training=False)
            db.execute('''INSERT INTO forecast_outcome_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (command['client_link_id'],g.user['id'],forecast['season_id'],str(id),command['kind'],command['reference_id'],
                 command['reference_revision'],json.dumps(command,allow_nan=False),digest(command),json.dumps(captured,allow_nan=False),
                 digest(captured),at.isoformat(),'active',1,None))
            saved=db.execute('SELECT * FROM forecast_outcome_links WHERE id=?',(command['client_link_id'],)).fetchone()
            return jsonify(success=True,item=link_item(db,journal,followup,saved,at,forecast),replayed=False),201

    @bp.get('/forecasts/<uuid:id>/outcome')
    @require_auth
    def outcome(id):
        if set(request.args)-{'as_of'}: raise FarmError('invalid_outcome_query','Outcome chỉ nhận as_of.')
        cutoff,assessed=assessment_time(request.args)
        with connect(app.config) as core,reference_store(storage/'journal.sqlite3') as journal, \
                reference_store(storage/'followup.sqlite3') as followup,journal_db(path) as db:
            db.execute('BEGIN')
            forecast=owned_forecast(core,db,id)
            rows=db.execute('SELECT * FROM forecast_outcome_links WHERE forecast_id=? AND user_id=? AND created_at<=? ORDER BY created_at,id',
                            (str(id),g.user['id'],cutoff.isoformat())).fetchall()
            items=[link_item(db,journal,followup,r,cutoff,forecast) for r in rows]
            result=summary(forecast,items,cutoff);result['assessed_at']=assessed.isoformat()
            return jsonify(success=True,item=result)

    @bp.post('/forecast-outcome-links/<uuid:id>/retractions')
    @require_auth
    def retract(id):
        if request.args: raise FarmError('invalid_outcome_query','Retraction không nhận query.')
        with connect(app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE')
            stored=db.execute('SELECT * FROM forecast_outcome_links WHERE id=? AND user_id=?',(str(id),g.user['id'])).fetchone()
            if stored is None: raise FarmError('resource_not_found','Không tìm thấy liên kết.',404)
            forecast=owned_forecast(core,db,stored['forecast_id'])
            validate_link(stored,forecast)
            data=body({'base_version','reason'})
            base,reason=data['base_version'],text(data['reason'],500)
            if type(base) is not int or not 1<=base<=2147483647: raise FarmError('invalid_outcome_link','base_version không hợp lệ.')
            old=db.execute('SELECT * FROM forecast_outcome_actions WHERE link_id=?',(str(id),)).fetchone()
            if old:
                if (stored['state']!='retracted' or stored['version']!=2 or stored['retracted_at']!=old['created_at']
                        or old['base_version']!=1 or old['user_id']!=g.user['id'] or old['action']!='retract'):
                    raise FarmError('forecast_outcome_storage_error','State/version retraction không hợp lệ.',500)
                if base not in (1,2) or old['reason']!=reason:
                    raise FarmError('outcome_retraction_conflict','Liên kết đã retract với nội dung khác.',409)
                return jsonify(success=True,item=dict(link_id=str(id),state='retracted',version=2,reason=old['reason'],recorded_at=old['created_at']),replayed=True)
            if stored['state']!='active' or stored['version']!=1 or stored['retracted_at'] is not None:
                raise FarmError('forecast_outcome_storage_error','State liên kết không khớp ledger.',500)
            if base!=stored['version']: raise FarmError('outcome_link_version_conflict','Version liên kết đã đổi.',409)
            at=max(now(),stamp(stored['created_at'])).isoformat()
            db.execute('INSERT INTO forecast_outcome_actions VALUES (?,?,?,?,?,?,?)',(str(uuid4()),str(id),g.user['id'],'retract',base,reason,at))
            db.execute('UPDATE forecast_outcome_links SET state=?,version=2,retracted_at=? WHERE id=?',('retracted',at,str(id)))
            return jsonify(success=True,item=dict(link_id=str(id),state='retracted',version=2,reason=reason,recorded_at=at),replayed=False),201

    app.register_blueprint(bp)
