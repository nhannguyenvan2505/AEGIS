"""Read-only, owner-scoped season timeline across opt-in pilot stores.

Every revision/link is an event. This is not a disease causal or forecast view.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from flask import Blueprint,current_app,g,jsonify,request
from pilot_store import validate_storage


def now():return datetime.now(timezone.utc)


@contextmanager
def read_store(storage):
    db=sqlite3.connect((storage/'demo.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        for name,file in [('journal','journal.sqlite3'),('management','management.sqlite3'),('raw','telemetry.sqlite3'),('workflow','followup.sqlite3'),('research','research.sqlite3')]:
            path=storage/file
            if not path.is_file():raise ValueError('Missing isolated timeline database')
            db.execute('ATTACH DATABASE ? AS '+name,(path.as_uri()+'?mode=ro',))
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN');yield db
    finally:db.close()


QUERIES=[
"""SELECT 'assessment_version:'||v.id event_id,'assessment_version' kind,'mock' source,
    json_extract(v.snapshot_json,'$.input.as_of') occurred_at,v.created_at recorded_at,
    v.id reference_id,v.base_assessment_id parent_id,v.revision revision,v.snapshot_json detail_json
    FROM workflow.assessment_versions v WHERE v.user_id=:uid AND v.season_id=:season""",
"""SELECT 'assessment:'||a.id event_id,'assessment' kind,'mock' source,a.window_end occurred_at,a.created_at recorded_at,
    a.id reference_id,a.device_id parent_id,NULL revision,a.snapshot_json detail_json
    FROM farm_assessments a JOIN farm_devices d ON d.id=a.device_id AND d.user_id=a.user_id
    WHERE a.user_id=:uid AND d.season_id=:season""",
"""SELECT 'followup:'||e.id,'followup','mock',e.created_at,e.created_at,c.id,c.assessment_id,e.version,e.payload_json
    FROM workflow.events e JOIN workflow.cases c ON c.id=e.case_id AND c.user_id=e.user_id
    WHERE c.user_id=:uid AND c.season_id=:season""",
"""SELECT 'observation:'||h.id,'observation',h.source,h.observed_at,h.created_at,h.visit_id,h.season_id,h.revision,h.payload_json
    FROM journal.history h WHERE h.user_id=:uid AND h.season_id=:season""",
"""SELECT 'intervention:'||h.id,'intervention',h.source,h.at,h.created_at,h.intervention_id,h.season_id,h.revision,h.payload_json
    FROM management.management_history h WHERE h.user_id=:uid AND h.season_id=:season""",
"""SELECT 'cultivation:'||c.id,'cultivation','user_declared',c.created_at,c.created_at,c.season_id,c.season_id,c.revision,c.profile_json
    FROM farm_cultivation_revisions c WHERE c.user_id=:uid AND c.season_id=:season""",
"""SELECT 'mock_telemetry:'||t.device_id||':'||t.start_at,'mock_telemetry','mock',t.start_at,t.created_at,t.device_id,d.season_id,NULL,
    json_object('air_temperature_c',t.air_temperature_c,'relative_humidity_pct',t.relative_humidity_pct,'leaf_wet',t.leaf_wet)
    FROM farm_telemetry t JOIN farm_devices d ON d.id=t.device_id AND d.user_id=t.user_id
    WHERE t.user_id=:uid AND d.season_id=:season""",
"""SELECT 'environment:'||r.id,'environment',json_extract(s.metadata_json,'$.source'),r.observed_at,r.received_at,r.id,r.stream_id,NULL,
    json_object('payload',json(r.payload_json),'qc',json(r.qc_json),'excluded_at',CASE WHEN r.excluded_at<=:asof THEN r.excluded_at ELSE NULL END)
    FROM raw.raw_records r JOIN raw.streams s ON s.id=r.stream_id AND s.user_id=r.user_id
    WHERE r.user_id=:uid AND s.season_id=:season AND s.created_at<=:asof""",
"""SELECT 'environment_exclusion:'||e.sample_id,'environment_exclusion',json_extract(s.metadata_json,'$.source'),e.recorded_at,e.recorded_at,e.sample_id,r.stream_id,NULL,
    json_object('reason',e.reason)
    FROM raw.exclusions e JOIN raw.samples r ON r.id=e.sample_id AND r.user_id=e.user_id JOIN raw.streams s ON s.id=r.stream_id AND s.user_id=r.user_id
    WHERE e.user_id=:uid AND s.season_id=:season AND s.created_at<=:asof""",
"""SELECT 'image_assessment:'||l.assessment_id||':'||l.analysis_id,'image','image_origin_unknown',i.created_at,l.created_at,i.id,l.assessment_id,NULL,
    json_object('status',i.status,'model_version',i.model_version,'model_sha256',i.model_sha256,'link_kind','assessment')
    FROM farm_assessment_analyses l JOIN farm_assessments a ON a.id=l.assessment_id AND a.user_id=l.user_id
    JOIN farm_devices d ON d.id=a.device_id AND d.user_id=a.user_id JOIN analyses i ON i.id=l.analysis_id AND i.user_id=l.user_id
    WHERE l.user_id=:uid AND d.season_id=:season""",
"""SELECT 'image_observation:'||h.id,'image','image_origin_unknown',i.created_at,h.created_at,i.id,h.visit_id,h.revision,
    json_object('status',i.status,'model_version',i.model_version,'model_sha256',i.model_sha256,'link_kind','observation_revision')
    FROM journal.history h JOIN analyses i ON i.id=json_extract(h.payload_json,'$.analysis_id') AND i.user_id=h.user_id
    WHERE h.user_id=:uid AND h.season_id=:season"""
]
QUERIES += [
"""SELECT 'survey_plan:'||e.id,'survey_plan',json_extract(r.payload_json,'$.source'),json_extract(r.payload_json,'$.window_start'),e.created_at,r.id,r.season_id,e.version,
    json_object('state',e.state,'window_end',json_extract(r.payload_json,'$.window_end'),'planned_before_window',json_extract(r.payload_json,'$.planned_before_window'),'reason',json_extract(e.data_json,'$.reason'),'observation_id',json_extract(e.data_json,'$.observation_snapshot.id'))
    FROM research.events e JOIN research.records r ON r.id=e.record_id WHERE r.user_id=:uid AND r.season_id=:season AND r.kind='schedule'""",
"""SELECT 'coverage:'||e.id,'coverage',json_extract(r.payload_json,'$.source'),json_extract(r.payload_json,'$.window_end'),e.created_at,r.id,r.season_id,e.version,
    json_object('state',e.state,'window_start',json_extract(r.payload_json,'$.window_start'),'reason',json_extract(e.data_json,'$.reason'),'inventory_count',json_extract(e.data_json,'$.inventory.active_count'),'provenance','owner_declared_not_independently_verified')
    FROM research.events e JOIN research.records r ON r.id=e.record_id WHERE r.user_id=:uid AND r.season_id=:season AND r.kind='coverage'""",
"""SELECT 'review_request:'||e.id,'review_request',json_extract(r.payload_json,'$.observation_snapshot.source'),e.created_at,e.created_at,r.id,r.season_id,e.version,
    json_object('state',e.state,'decision',json_extract(e.data_json,'$.decision'),'reason',json_extract(e.data_json,'$.reason'),'observation_id',json_extract(r.payload_json,'$.observation_snapshot.id'),'source_revision',json_extract(r.payload_json,'$.observation_snapshot.revision'),'expert_identity_verified',json('false'),'label_approved_for_training',json('false'))
    FROM research.events e JOIN research.records r ON r.id=e.record_id WHERE r.user_id=:uid AND r.season_id=:season AND r.kind='review'""",
"""SELECT 'review_grant:'||e.id,'review_grant','user_declared',e.created_at,e.created_at,r.id,r.season_id,e.version,
    json_object('state',e.state,'reason',json_extract(e.data_json,'$.reason'),'reviewer_alias',json_extract(r.payload_json,'$.reviewer_alias'),'qualification_verified',json('false'))
    FROM research.events e JOIN research.records r ON r.id=e.record_id WHERE r.user_id=:uid AND r.season_id=:season AND r.kind='grant'"""
]
KINDS={'assessment','assessment_version','followup','observation','intervention','cultivation','mock_telemetry','environment','environment_exclusion','image','survey_plan','coverage','review_request','review_grant'}


def enable_timeline(app,storage):
    storage=validate_storage(storage)
    if Path(app.config['DATABASE_PATH']).resolve().parent!=storage:raise ValueError('Wrong isolated store')
    from app.auth import require_auth
    from app.farm import owned,private,FarmError
    bp=Blueprint('pilot_timeline',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def instant(value):
        try:
            t=datetime.fromisoformat(value.replace('Z','+00:00'))
            if t.tzinfo is None or not 1900<=t.year<=2100:raise ValueError()
            return t.astimezone(timezone.utc)
        except (ValueError,OverflowError):raise FarmError('invalid_timeline','Thời điểm cần ISO8601 có timezone.')

    @bp.get('/seasons/<uuid:id>/timeline')
    @require_auth
    def timeline(id):
        allowed={'page','page_size','kind','axis','from','to','as_of'}
        if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args):raise FarmError('invalid_timeline','Tham số không hợp lệ hoặc bị lặp.')
        integers=[]
        for k,default,maximum in [('page','1',1000000),('page_size','20',100)]:
            v=request.args.get(k,default)
            if not v.isascii() or not v.isdigit() or len(v)>7 or not 1<=int(v)<=maximum:raise FarmError('invalid_timeline','Phân trang không hợp lệ.')
            integers.append(int(v))
        page,size=integers;axis=request.args.get('axis','occurred_at');kind=request.args.get('kind','all')
        if axis not in ['occurred_at','recorded_at'] or kind not in KINDS|{'all'}:raise FarmError('invalid_timeline','Trục thời gian hoặc loại sự kiện không hợp lệ.')
        cutoff=instant(request.args['as_of']) if 'as_of' in request.args else now()
        if cutoff>now():raise FarmError('invalid_timeline','Không dùng cutoff tương lai.')
        start=instant(request.args['from']) if 'from' in request.args else None;end=instant(request.args['to']) if 'to' in request.args else None
        if start and end and start>=end:raise FarmError('invalid_timeline','Khoảng thời gian không hợp lệ.')
        params=dict(uid=g.user['id'],season=str(id),asof=cutoff.isoformat(),kind=kind,size=size,offset=(page-1)*size)
        where="recorded_at<=:asof AND (:kind='all' OR kind=:kind)"
        if start:where+=' AND '+axis+'>=:start';params['start']=start.isoformat()
        if end:where+=' AND '+axis+'<:end';params['end']=end.isoformat()
        union=' UNION ALL '.join(QUERIES);cte='WITH timeline AS ('+union+') '
        with read_store(storage) as db:
            owned(db,'seasons',id)
            total=db.execute(cte+'SELECT COUNT(*) FROM timeline WHERE '+where,params).fetchone()[0]
            rows=db.execute(cte+'SELECT * FROM timeline WHERE '+where+' ORDER BY '+axis+' DESC,event_id DESC LIMIT :size OFFSET :offset',params).fetchall()
            items=[]
            for row in rows:
                r=dict(row);d=json.loads(r.pop('detail_json'));k=r['kind']
                if k in ['assessment','assessment_version']:d=dict(status=d['result']['status'],reasons=d['result']['reasons'],mode=d['mode'],valid_until=d['valid_until'],base_assessment_id=d.get('base_assessment_id',r['reference_id']),revision=d.get('assessment_revision',1))
                elif k=='observation':d={x:d[x] for x in ['finding','record_status','verification','platform_verified']}
                elif k=='intervention':d={x:d[x] for x in ['kind','action_details','record_status']}
                elif k=='cultivation':d={x:d[x] for x in ['region','rice_variety','planting_method','season_status']}
                elif k=='followup':d={x:d[x] for x in ['action','reason','observation_id','resolution']}
                r['detail']=d;items.append(r)
        pages=(total+size-1)//size
        return jsonify(success=True,items=items,as_of=cutoff.isoformat(),axis=axis,
            pagination=dict(page=page,page_size=size,total=total,total_pages=pages,has_next=page<pages),
            limits=['Linked images only; event history is not a causal disease claim','Read transactions with cutoff; not a cross-database atomic historical backup'])
    app.register_blueprint(bp)
