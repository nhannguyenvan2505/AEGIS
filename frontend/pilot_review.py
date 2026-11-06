"""Scoped, independent-account evidence review. Never an expert credential or ML approval."""
import json
import re
from pathlib import Path
from flask import Blueprint,current_app,g,jsonify,request,send_file
from pilot_journal import journal_db
import pilot_research as ledger


def enable_review(app,storage):
    path=ledger.storage_path(app,storage)
    from app.auth import require_auth
    from app.storage import connect
    from app.farm import body,owned,paginate,text,private,FarmError,LimitResponse,limit_response
    bp=Blueprint('pilot_review',__name__,url_prefix='/api/farm');bp.after_request(private)
    bp.register_error_handler(LimitResponse,limit_response)
    bp.register_error_handler(FarmError,lambda e:(jsonify(success=False,error=dict(code=e.code,message=e.message)),e.status))

    def accessible(db,core,id,kind):
        r=ledger.get(db,id,kind);m=json.loads(r['payload_json'])
        if g.user['id'] not in [r['user_id'],m['reviewer_id']]:raise FarmError('resource_not_found','Không tìm thấy yêu cầu.',404)
        if not core.execute('SELECT 1 FROM farm_seasons WHERE id=? AND user_id=?',(r['season_id'],r['user_id'])).fetchone():raise FarmError('resource_not_found','Không tìm thấy mùa vụ.',404)
        if kind=='review' and g.user['id']!=r['user_id']:
            grant=ledger.get(db,m['grant_id'],'grant')
            if grant['state']!='active' or r['state']=='cancelled':raise FarmError('resource_not_found','Quyền xem yêu cầu không còn hiệu lực.',404)
        return r

    def serialize(r,db):
        result=ledger.serialize(r);m=result['metadata'];result['owner_account_id']=r['user_id']
        result.update(independent_account=m['reviewer_id']!=r['user_id'],expert_identity_verified=False,expert_qualification_verified=False,label_approved_for_training=False)
        if r['kind']=='review':
            grant=ledger.get(db,m['grant_id'],'grant');v=ledger.observation(storage,r['user_id'],r['season_id'],m['observation_snapshot']['id'])
            result['source_current']=v['revision']==m['observation_snapshot']['revision'] and v['payload_sha256']==m['observation_snapshot']['payload_sha256'] and v['payload']['record_status']=='active'
            result['grant_active']=grant['state']=='active'
            result['decision_current']=r['state']=='decided' and result['source_current'] and result['grant_active']
            result['image_url']='/api/farm/review-requests/'+r['id']+'/image' if m['observation_snapshot']['payload']['analysis_id'] else None
        return result

    @bp.route('/seasons/<uuid:id>/review-grants',methods=['GET','POST'])
    @require_auth
    def grants(id):
        data=body({'client_grant_id','reviewer_alias','qualification_reference','scope','reason'}, {'reviewer_id','reviewer_email'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            owned(core,'seasons',id);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'current_records',"user_id=? AND season_id=? AND kind='grant'",(g.user['id'],str(id)),lambda r:serialize(r,db))
            key=ledger.identifier(data['client_grant_id']);old=ledger.replay_create(db,key,str(id),'grant',data)
            if old:return jsonify(success=True,item=serialize(old,db)),200
            if ('reviewer_id' in data)==('reviewer_email' in data):
                raise FarmError('invalid_research','Chỉ gửi một trong reviewer_id hoặc reviewer_email.')
            if 'reviewer_email' in data:
                email=data['reviewer_email']
                if not isinstance(email,str) or len(email.strip())>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email.strip()):
                    raise FarmError('invalid_research','Cần email tài khoản được chỉ định hợp lệ.')
                target=core.execute('SELECT id FROM users WHERE email=?',(email.strip().lower(),)).fetchone()
                if target is None:raise FarmError('resource_not_found','Không tìm thấy tài khoản được chỉ định.',404)
                reviewer=target['id']
            else:reviewer=ledger.identifier(data['reviewer_id'])
            if reviewer==g.user['id']:raise FarmError('self_review_forbidden','Cần một tài khoản khác để xác minh độc lập.',400)
            if not core.execute('SELECT 1 FROM users WHERE id=?',(reviewer,)).fetchone():raise FarmError('resource_not_found','Không tìm thấy tài khoản được chỉ định.',404)
            if data['scope']!='assigned_observations_and_images':raise FarmError('invalid_research','Chỉ chia sẻ quan sát và ảnh trong yêu cầu được giao.')
            alias=text(data['reviewer_alias']);qualification=text(data['qualification_reference'],500,True);reason=text(data['reason'],500)
            m=dict(reviewer_id=reviewer,reviewer_alias=alias,qualification_reference=qualification,qualification_provenance='owner_declared_unverified',scope=data['scope'])
            return jsonify(success=True,item=serialize(ledger.create(db,key,str(id),'grant',m,'offered',data,dict(reason=reason)),db)),201

    @bp.route('/review-grants/<uuid:id>/events',methods=['GET','POST'])
    @require_auth
    def grant_events(id):
        data=body({'client_event_id','base_version','action','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');r=accessible(db,core,id,'grant');m=json.loads(r['payload_json'])
            if data is None:return paginate(db,'events','record_id=?',(str(id),),ledger.serialize_event,order='version DESC')
            action=data['action'];is_owner=g.user['id']==r['user_id']
            if action=='accept' and (is_owner or g.user['id']!=m['reviewer_id']) or action=='revoke' and not is_owner or action not in ['accept','revoke']:
                raise FarmError('review_action_forbidden','Tài khoản không được thực hiện hành động này.',403)
            replay=ledger.replay_event(db,r,data)
            if replay:return jsonify(success=True,item=serialize(r,db),event=ledger.serialize_event(replay)),200
            if action=='accept' and r['state']!='offered' or action=='revoke' and r['state']=='revoked':raise FarmError('invalid_review_transition','Trạng thái quyền đã đổi.',409)
            reason=text(data['reason'],500);key=ledger.identifier(data['client_event_id']);ledger.append(db,str(id),key,r['version']+1,'active' if action=='accept' else 'revoked',data,dict(reason=reason,action=action))
            return jsonify(success=True,item=serialize(ledger.get(db,id),db)),201

    @bp.route('/seasons/<uuid:id>/review-requests',methods=['GET','POST'])
    @require_auth
    def requests(id):
        data=body({'client_request_id','grant_id','observation_id','source_revision','payload_sha256','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            owned(core,'seasons',id);db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN')
            if data is None:return paginate(db,'current_records',"user_id=? AND season_id=? AND kind='review'",(g.user['id'],str(id)),lambda r:serialize(r,db))
            key=ledger.identifier(data['client_request_id']);old=ledger.replay_create(db,key,str(id),'review',data)
            if old:return jsonify(success=True,item=serialize(old,db)),200
            grant=ledger.owned_record(db,core,ledger.identifier(data['grant_id']),'grant');m=json.loads(grant['payload_json'])
            if grant['season_id']!=str(id) or grant['state']!='active':raise FarmError('review_grant_inactive','Cần quyền cùng mùa vụ đã được tài khoản nhận chấp thuận.',409)
            v=ledger.observation(storage,g.user['id'],str(id),ledger.identifier(data['observation_id']))
            if type(data['source_revision']) is not int or v['revision']!=data['source_revision'] or v['payload_sha256']!=data['payload_sha256'] or v['payload']['record_status']!='active':raise FarmError('review_source_changed','Quan sát đã đổi hoặc bị thu hồi; tải lại.',409)
            reason=text(data['reason'],500);meta=dict(grant_id=grant['id'],reviewer_id=m['reviewer_id'],observation_snapshot=v)
            return jsonify(success=True,item=serialize(ledger.create(db,key,str(id),'review',meta,'pending',data,dict(reason=reason,decision=None,evidence_reference=None)),db)),201

    @bp.get('/review-inbox')
    @require_auth
    def inbox():
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN')
            where="json_extract(payload_json,'$.reviewer_id')=? AND (kind='grant' OR (kind='review' AND state<>'cancelled' AND EXISTS (SELECT 1 FROM current_records parent WHERE parent.id=json_extract(current_records.payload_json,'$.grant_id') AND parent.state='active')))"
            return paginate(db,'current_records',where,(g.user['id'],),lambda r:serialize(r,db))

    @bp.get('/review-requests/<uuid:id>')
    @require_auth
    def detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=serialize(accessible(db,core,id,'review'),db))

    @bp.get('/review-grants/<uuid:id>')
    @require_auth
    def grant_detail(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');return jsonify(success=True,item=serialize(accessible(db,core,id,'grant'),db))

    @bp.route('/review-requests/<uuid:id>/events',methods=['GET','POST'])
    @require_auth
    def decisions(id):
        data=body({'client_event_id','base_version','action','decision','evidence_reference','reason'}) if request.method=='POST' else None
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN IMMEDIATE' if data is not None else 'BEGIN');r=accessible(db,core,id,'review');m=json.loads(r['payload_json']);owner=g.user['id']==r['user_id']
            if data is None:return paginate(db,'events','record_id=?',(str(id),),ledger.serialize_event,order='version DESC')
            action=data['action']
            if action not in ['decide','withdraw','cancel'] or action=='cancel' and not owner or action in ['decide','withdraw'] and (owner or g.user['id']!=m['reviewer_id']):raise FarmError('review_action_forbidden','Hành động không đúng vai trò.',403)
            replay=ledger.replay_event(db,r,data)
            if replay:return jsonify(success=True,item=serialize(r,db),event=ledger.serialize_event(replay)),200
            if r['state']=='cancelled':raise FarmError('invalid_review_transition','Yêu cầu đã hủy.',409)
            reason=text(data['reason'],500);reference=text(data['evidence_reference'],500,True)
            if action=='decide':
                if data['decision'] not in ['supports_present','supports_absent','inconclusive','reject_evidence'] or not reference:raise FarmError('invalid_research','Cần quyết định và tham chiếu bằng chứng.')
                if not serialize(r,db)['source_current']:raise FarmError('review_source_changed','Quan sát đã đổi; cần yêu cầu mới.',409)
                state='decided'
            else:
                if data['decision'] is not None:raise FarmError('invalid_research','Chỉ decide nhận decision.')
                if action=='withdraw' and r['state']!='decided':raise FarmError('invalid_review_transition','Chỉ rút quyết định đã ghi.',409)
                state='withdrawn' if action=='withdraw' else 'cancelled'
            key=ledger.identifier(data['client_event_id']);ledger.append(db,str(id),key,r['version']+1,state,data,dict(action=action,decision=data['decision'],evidence_reference=reference,reason=reason,identity_and_qualification_verified=False,label_approved_for_training=False))
            return jsonify(success=True,item=serialize(ledger.get(db,id),db)),201

    @bp.get('/review-requests/<uuid:id>/image')
    @require_auth
    def evidence_image(id):
        with connect(current_app.config) as core,journal_db(path) as db:
            db.execute('BEGIN');r=accessible(db,core,id,'review');m=json.loads(r['payload_json']);analysis=m['observation_snapshot']['payload']['analysis_id']
            row=core.execute('SELECT image_path FROM analyses WHERE id=? AND user_id=?',(analysis,r['user_id'])).fetchone() if analysis else None
            if row is None:raise FarmError('resource_not_found','Không có ảnh trong yêu cầu.',404)
            root=Path(current_app.config['UPLOAD_DIR']).resolve();file=(root/row['image_path']).resolve()
            if not file.is_relative_to(root):raise FarmError('storage_error','Đường dẫn ảnh không hợp lệ.',500)
            try:
                with file.open('rb') as f:header=f.read(12)
                mime='image/jpeg' if header.startswith(b'\xff\xd8\xff') else 'image/png' if header.startswith(b'\x89PNG\r\n\x1a\n') else 'image/webp' if header.startswith(b'RIFF') and header[8:12]==b'WEBP' else None
                if mime is None:raise FarmError('storage_error','Ảnh lưu trữ không hợp lệ.',500)
                response=send_file(file,mimetype=mime,conditional=False,etag=False,max_age=0)
                response.headers['X-Content-Type-Options']='nosniff';return response
            except FileNotFoundError:raise FarmError('resource_not_found','Không tìm thấy file ảnh.',404)
            except OSError:raise FarmError('storage_error','Không thể đọc ảnh.',500)
    app.register_blueprint(bp)
