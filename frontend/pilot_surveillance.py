"""Visit plans and declared intervention coverage, not approved ML labels."""
import json
from datetime import timedelta
from flask import Blueprint,current_app,g,jsonify,request
from pilot_journal import journal_db
import pilot_research as ledger


def enable_surveillance(app,storage):
    path=ledger.storage_path(app,storage)
    from app.auth import require_auth
    from app.storage import connect
    from app.farm import body,owned,within_season,paginate,text,private,FarmError,LimitResponse,limit_response
    bp=Blueprint('pilot_surveillance',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def serialize(r):
        result=ledger.serialize(r);m=result['metadata']
        if r['kind']=='schedule':
            result['overdue']=r['state']=='planned' and ledger.instant(m['window_end'])<=ledger.now()
            obs=result['current'].get('observation_snapshot');result['linked_observation_changed']=False
            if obs:
                current=ledger.observation(storage,r['user_id'],r['season_id'],obs['id'])
                result['linked_observation_changed']=current['revision']!=obs['revision'] or current['payload']['record_status']!='active'
        else:
            inv=ledger.inventory(storage,r['user_id'],r['season_id'],m['source'],m['window_start'],m['window_end'])
            result['inventory_changed']=inv['sha256']!=result['current']['inventory']['sha256']
            result['coverage_approved_for_training']=False
        return result

    def interval(data,season,closed=False):
        start=ledger.instant(data['window_start']);end=ledger.instant(data['window_end'])
        if start>=end or closed and end>ledger.now():raise FarmError('invalid_research','Cần khoảng [start,end) hợp lệ; đối soát chỉ cho khoảng đã kết thúc.')
        within_season(start,season);within_season(end-timedelta(microseconds=1),season)
        if data['source'] not in ['synthetic','field_observed']:raise FarmError('invalid_research','Nguồn không hợp lệ.')
        return start.isoformat(),end.isoformat()

    @bp.route('/seasons/<uuid:id>/survey-plans',methods=['GET','POST'])
    @require_auth
    def plans(id):
        data=body({'client_plan_id','window_start','window_end','source','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            season=owned(core,'seasons',id);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'current_records',"user_id=? AND season_id=? AND kind='schedule'",(g.user['id'],str(id)),serialize)
            key=ledger.identifier(data['client_plan_id']);old=ledger.replay_create(db,key,str(id),'schedule',data)
            if old:return jsonify(success=True,item=serialize(old)),200
            start,end=interval(data,season);reason=text(data['reason'],500)
            m=dict(window_start=start,window_end=end,source=data['source'],planned_before_window=ledger.now()<=ledger.instant(start))
            return jsonify(success=True,item=serialize(ledger.create(db,key,str(id),'schedule',m,'planned',data,dict(reason=reason,observation_snapshot=None)))),201

    @bp.route('/survey-plans/<uuid:id>/events',methods=['GET','POST'])
    @require_auth
    def plan_events(id):
        data=body({'client_event_id','base_version','state','observation_id','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');r=ledger.owned_record(db,core,id,'schedule')
            if data is None:return paginate(db,'events','record_id=?',(str(id),),ledger.serialize_event,order='version DESC')
            replay=ledger.replay_event(db,r,data)
            if replay:return jsonify(success=True,item=serialize(r),event=ledger.serialize_event(replay)),200
            state=data['state'];reason=text(data['reason'],500);m=json.loads(r['payload_json']);obs=None
            if state not in ['planned','completed','missed','unable','cancelled']:raise FarmError('invalid_research','Trạng thái lịch không hợp lệ.')
            if state=='missed' and ledger.now()<ledger.instant(m['window_end']):raise FarmError('invalid_research','Chưa hết cửa sổ để ghi bỏ lỡ.')
            if state=='completed':
                oid=ledger.identifier(data['observation_id']);obs=ledger.observation(storage,g.user['id'],r['season_id'],oid)
                if obs['source']!=m['source'] or obs['payload']['record_status']!='active' or not ledger.instant(m['window_start'])<=ledger.instant(obs['observed_at'])<ledger.instant(m['window_end']):
                    raise FarmError('invalid_survey_observation','Cần quan sát active cùng nguồn, nằm trong cửa sổ dự kiến.')
                if db.execute("SELECT 1 FROM current_records WHERE kind='schedule' AND user_id=? AND id<>? AND state='completed' AND json_extract(current_data_json,'$.observation_snapshot.id')=?",(g.user['id'],str(id),oid)).fetchone():raise FarmError('survey_observation_conflict','Quan sát đã gắn lịch khác.',409)
            elif data['observation_id'] is not None:raise FarmError('invalid_research','Chỉ completed nhận observation_id.')
            event_id=ledger.identifier(data['client_event_id']);ledger.append(db,str(id),event_id,r['version']+1,state,data,dict(reason=reason,observation_snapshot=obs))
            return jsonify(success=True,item=serialize(ledger.get(db,id)),event=ledger.serialize_event(db.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone())),201

    def coverage_data(data,r):
        state=data['state'];reason=text(data['reason'],500);reference=text(data['evidence_reference'],500,True);m=json.loads(r['payload_json'])
        if state not in ['unknown','partial','reviewed_records','reviewed_no_interventions']:raise FarmError('invalid_research','Trạng thái đối soát không hợp lệ.')
        inv=ledger.inventory(storage,r['user_id'],r['season_id'],m['source'],m['window_start'],m['window_end'])
        if state.startswith('reviewed_') and not reference:raise FarmError('invalid_research','Cần tham chiếu đối soát thực tế.')
        if state=='reviewed_no_interventions' and inv['active_count'] or state=='reviewed_records' and not inv['active_count']:
            raise FarmError('coverage_inventory_conflict','Khai báo không phù hợp nhật ký hiện có.',409)
        return dict(reason=reason,evidence_reference=reference,inventory=inv,provenance='owner_declared_not_independently_verified')

    @bp.get('/survey-plans/<uuid:id>')
    @require_auth
    def plan_detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=serialize(ledger.owned_record(db,core,id,'schedule')))

    @bp.get('/intervention-coverage/<uuid:id>')
    @require_auth
    def coverage_detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=serialize(ledger.owned_record(db,core,id,'coverage')))

    @bp.route('/seasons/<uuid:id>/intervention-coverage',methods=['GET','POST'])
    @require_auth
    def coverage(id):
        data=body({'client_coverage_id','window_start','window_end','source','state','reason','evidence_reference'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            season=owned(core,'seasons',id);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'current_records',"user_id=? AND season_id=? AND kind='coverage'",(g.user['id'],str(id)),serialize)
            key=ledger.identifier(data['client_coverage_id']);old=ledger.replay_create(db,key,str(id),'coverage',data)
            if old:return jsonify(success=True,item=serialize(old)),200
            start,end=interval(data,season,closed=True);meta=dict(window_start=start,window_end=end,source=data['source'])
            value=coverage_data(data,dict(user_id=g.user['id'],season_id=str(id),payload_json=json.dumps(meta)))
            return jsonify(success=True,item=serialize(ledger.create(db,key,str(id),'coverage',meta,data['state'],data,value))),201

    @bp.route('/intervention-coverage/<uuid:id>/events',methods=['GET','POST'])
    @require_auth
    def coverage_events(id):
        data=body({'client_event_id','base_version','state','reason','evidence_reference'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');r=ledger.owned_record(db,core,id,'coverage')
            if data is None:return paginate(db,'events','record_id=?',(str(id),),ledger.serialize_event,order='version DESC')
            replay=ledger.replay_event(db,r,data)
            if replay:return jsonify(success=True,item=serialize(r),event=ledger.serialize_event(replay)),200
            value=coverage_data(data,r);event_id=ledger.identifier(data['client_event_id']);ledger.append(db,str(id),event_id,r['version']+1,data['state'],data,value)
            return jsonify(success=True,item=serialize(ledger.get(db,id))),201
    app.register_blueprint(bp)
