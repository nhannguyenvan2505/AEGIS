"""Regenerate portable Postman artifacts; no account/token data is exported."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'postman'
ROOT.mkdir(exist_ok=True)


def event(listen, code):
    return {'listen': listen, 'script': {'type': 'text/javascript', 'exec': code.splitlines()}}


def request(name, method, path, status, *, body=None, code='', error=None, auth=None, before=''):
    req = {'method': method, 'header': [], 'url': '{{base_url}}' + path}
    if body:
        req['body'] = body
        if body['mode'] == 'raw':
            req['header'].append({'key': 'Content-Type', 'value': 'application/json'})
    if auth is not None:
        req['auth'] = auth
    test = f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));\n'
    if error:
        test += f'pm.test("Error contract", () => {{const d=pm.response.json(); pm.expect(d.success).to.eql(false); pm.expect(d.error.code).to.eql({json.dumps(error)});}});\n'
    test += code
    item = {'name': name, 'request': req, 'event': [event('test', test)]}
    if before:
        item['event'].insert(0, event('prerequest', before))
    return item


def raw(value):
    return {'mode': 'raw', 'raw': json.dumps(value), 'options': {'raw': {'language': 'json'}}}


def file_body(filename):
    return {'mode': 'formdata', 'formdata': [{'key': 'image', 'type': 'file', 'src': 'fixtures/' + filename}]}


NOAUTH = {'type': 'noauth'}
OTHER = {'type': 'bearer', 'bearer': [{'key': 'token', 'type': 'string', 'value': '{{other_token}}'}]}
CREDS = raw({'email': '{{email}}', 'password': '{{password}}'})
OTHER_CREDS = raw({'email': '{{other_email}}', 'password': '{{other_password}}'})
items = [
    request('01 Health', 'GET', '/health', 200, auth=NOAUTH,
            code='pm.test("Backend alive", () => pm.expect(pm.response.json().service).to.eql("aegis-backend"));'),
    request('02 Register owner (fresh account each run)', 'POST', '/api/auth/register', 201, body=CREDS, auth=NOAUTH,
            before='''const id=pm.variables.replaceIn('{{$guid}}');
pm.environment.set('email', 'postman-'+id+'@example.test');
pm.environment.set('password', 'Test-'+id);
['access_token','user_id','analysis_id','image_url','other_token','other_user_id','detection_request_id','model_sha256'].forEach(k=>pm.environment.unset(k));''',
            code='pm.environment.set("user_id",pm.response.json().user.id);'),
    request('03 Duplicate email', 'POST', '/api/auth/register', 409, body=CREDS, auth=NOAUTH, error='email_exists'),
    request('04 Invalid registration', 'POST', '/api/auth/register', 400, auth=NOAUTH,
            body=raw({'email': 'invalid', 'password': 'short'}), error='invalid_credentials'),
    request('05 Wrong password', 'POST', '/api/auth/login', 401, auth=NOAUTH,
            body=raw({'email': '{{email}}', 'password': 'Wrong-password-123'}), error='invalid_login'),
    request('06 Login owner', 'POST', '/api/auth/login', 200, body=CREDS, auth=NOAUTH,
            code='''const d=pm.response.json();
pm.test('Bearer session',()=>{pm.expect(d.token_type).to.eql('Bearer'); pm.expect(d.access_token).to.be.a('string').and.not.empty; pm.expect(d.expires_at).to.be.above(Date.now()/1000);});
if(pm.response.code===200) pm.environment.set('access_token',d.access_token);'''),
    request('07 Current user', 'GET', '/api/auth/me', 200,
            code='pm.test("Owner identity",()=>pm.expect(pm.response.json().user.id).to.eql(pm.environment.get("user_id")));'),
    request('08 Detection needs token', 'POST', '/api/disease/detect', 401, auth=NOAUTH, error='unauthorized'),
    request('09 Missing image', 'POST', '/api/disease/detect', 400, error='missing_or_multiple_images'),
    request('10 Empty image', 'POST', '/api/disease/detect', 400, body=file_body('empty.bin'), error='empty_image'),
    request('11 Invalid image bytes', 'POST', '/api/disease/detect', 400, body=file_body('invalid.txt'), error='invalid_image'),
    request('12 Oversized image', 'POST', '/api/disease/detect', 413, body=file_body('too-large.bin'), error='upload_too_large'),
    request('13 Detect real image and save', 'POST', '/api/disease/detect', 200, body=file_body('sample.jpg'),
            code='''const d=pm.response.json();
pm.test('Detection contract',()=>{
 pm.expect(d.success).to.eql(true); pm.expect(d.user_id).to.eql(pm.environment.get('user_id'));
 pm.expect(d.analysis_id).to.be.a('string').and.not.empty;
 pm.expect(d.model_version).to.be.a('string').and.not.empty;
 pm.expect(d.status).to.be.oneOf(['detection_found','no_detection']);
 pm.expect(d.image.orientation).to.eql('exif_corrected');
 pm.expect(d.detections).to.be.an('array');
 d.detections.forEach(x=>{
  pm.expect(x.detection_id).to.be.a('string');
  pm.expect(['rice_blast','brown_spot','sheath_blight'][x.class_id]).to.eql(x.disease);
  pm.expect(x.confidence).to.be.within(0,1);
  pm.expect(x.bbox.x1).to.be.at.least(0); pm.expect(x.bbox.x2).to.be.above(x.bbox.x1).and.at.most(d.image.width);
  pm.expect(x.bbox.y1).to.be.at.least(0); pm.expect(x.bbox.y2).to.be.above(x.bbox.y1).and.at.most(d.image.height);
 });
});
pm.test('Origin trace and artifact',()=>{
 pm.expect(d.request_id).to.eql(pm.response.headers.get('X-Request-ID'));
 pm.expect(d.model_sha256).to.match(/^[0-9a-f]{64}$/);
 pm.expect(d.timings.ai_processing_ms).to.be.at.least(0);pm.expect(d.timings.ai_roundtrip_ms).to.be.at.least(0);
});
if(pm.response.code===200){pm.environment.set('analysis_id',d.analysis_id);pm.environment.set('image_url',d.image_url);pm.environment.set('detection_request_id',d.request_id);pm.environment.set('model_sha256',d.model_sha256);}'''),
    request('14 Read persisted detail', 'GET', '/api/disease/analyses/{{analysis_id}}', 200,
            code='pm.test("Persisted owner and origin trace",()=>{const d=pm.response.json();pm.expect(d.analysis_id).to.eql(pm.environment.get("analysis_id"));pm.expect(d.user_id).to.eql(pm.environment.get("user_id"));pm.expect(d.request_id).to.eql(pm.environment.get("detection_request_id"));pm.expect(d.model_sha256).to.eql(pm.environment.get("model_sha256"));pm.expect(pm.response.headers.get("X-Request-ID")).not.to.eql(d.request_id);});'),
    request('15 History page', 'GET', '/api/disease/analyses?page=1&page_size=20', 200,
            code='''pm.test('History includes saved result',()=>{const d=pm.response.json();pm.expect(d.pagination.total).to.eql(1);pm.expect(d.items[0].analysis_id).to.eql(pm.environment.get('analysis_id'));});'''),
    request('16 Invalid pagination', 'GET', '/api/disease/analyses?page=0', 400, error='invalid_pagination'),
    request('17 View private image', 'GET', '{{image_url}}', 200,
            code='''pm.test('Image headers',()=>{pm.expect(pm.response.headers.get('Content-Type')).to.match(/^image\/(jpeg|png|webp)/);pm.expect(pm.response.headers.get('Cache-Control')).to.include('no-store');pm.expect(pm.response.headers.get('X-Content-Type-Options')).to.eql('nosniff');});'''),
    request('18 Image needs token', 'GET', '{{image_url}}', 401, auth=NOAUTH, error='unauthorized'),
    request('19 Register other user', 'POST', '/api/auth/register', 201, body=OTHER_CREDS, auth=NOAUTH,
            before="const id=pm.variables.replaceIn('{{$guid}}');pm.environment.set('other_email','postman-other-'+id+'@example.test');pm.environment.set('other_password','Test-'+id);",
            code='pm.environment.set("other_user_id",pm.response.json().user.id);'),
    request('20 Login other user', 'POST', '/api/auth/login', 200, body=OTHER_CREDS, auth=NOAUTH,
            code='if(pm.response.code===200)pm.environment.set("other_token",pm.response.json().access_token);'),
    request('21 Other user cannot read detail', 'GET', '/api/disease/analyses/{{analysis_id}}', 404, auth=OTHER, error='analysis_not_found'),
    request('22 Other user cannot view image', 'GET', '{{image_url}}', 404, auth=OTHER, error='analysis_not_found'),
    request('23 Other user history is empty', 'GET', '/api/disease/analyses', 200, auth=OTHER,
            code='pm.test("Isolated history",()=>{pm.expect(pm.response.json().pagination.total).to.eql(0);pm.expect(pm.response.json().items).to.eql([]);});'),
    request('24 Logout other user', 'POST', '/api/auth/logout', 200, auth=OTHER,
            code='pm.environment.unset("other_token");pm.environment.unset("other_password");'),
    request('25 Logout owner', 'POST', '/api/auth/logout', 200),
    request('26 Revoked token is rejected', 'GET', '/api/auth/me', 401, error='unauthorized',
            code='pm.environment.unset("access_token");pm.environment.unset("password");'),
]
# Keep the first successful analysis as the origin for replay/history assertions.
origin = next(item for item in items if item['name'].startswith('13 '))
origin['request']['header'].append({'key': 'Idempotency-Key', 'value': '{{idempotency_key}}'})
origin['event'].insert(0, event('prerequest', "pm.environment.set('idempotency_key',pm.variables.replaceIn('{{$guid}}'));"))
origin['event'][-1]['script']['exec'].append("if(pm.response.code===200)pm.environment.set('origin_result',JSON.stringify(pm.response.json()));")
extra = [
    request('13a Replay same image and key', 'POST', '/api/disease/detect', 200,
            body=file_body('sample.jpg'), code='''pm.test('Replay preserves complete result',()=>{
pm.expect(pm.response.headers.get('Idempotency-Replayed')).to.eql('true');
pm.expect(pm.response.json()).to.deep.eql(JSON.parse(pm.environment.get('origin_result')));
pm.expect(pm.response.headers.get('X-Request-ID')).not.to.eql(pm.response.json().request_id);
});'''),
    request('13b Same key different bytes', 'POST', '/api/disease/detect', 409,
            body=file_body('invalid.txt'), error='idempotency_conflict'),
    request('13c Invalid key', 'POST', '/api/disease/detect', 400,
            body=file_body('sample.jpg'), error='invalid_idempotency_key'),
]
for item in extra:
    item['request']['header'].append({'key': 'Idempotency-Key', 'value':
        'invalid key' if item['name'].startswith('13c') else '{{idempotency_key}}'})
items[items.index(origin)+1:items.index(origin)+1] = extra
collection = {
    'info': {'name': 'AEGIS Backend — Local acceptance',
             'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
             'description': 'Run in order with local Backend + AI running. Prepare fixtures first. Creates 2 fresh local test accounts and 1 analysis per run. No fixed confidence/detection-count assumption. See postman/README.md.'},
    'auth': {'type': 'bearer', 'bearer': [{'key': 'token', 'type': 'string', 'value': '{{access_token}}'}]},
    'item': items,
    'event': [event('test', '''pm.test('Current request headers',()=>{
 pm.expect(pm.response.headers.get('X-Request-ID')).to.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
 pm.expect(Number(pm.response.headers.get('X-Processing-Time-Ms'))).to.be.at.least(0);
});
if(pm.response.code>=400)pm.test('Error request ID',()=>pm.expect(pm.response.json().request_id).to.eql(pm.response.headers.get('X-Request-ID')));''')],
}
keys = ['email','password','access_token','user_id','analysis_id','image_url','other_email','other_password','other_token','other_user_id','detection_request_id','model_sha256','idempotency_key','origin_result']
environment = {'name': 'AEGIS Local', '_postman_variable_scope': 'environment',
               'values': [{'key':'base_url','value':'http://127.0.0.1:5000','enabled':True,'type':'default'}] +
                         [{'key':k,'value':'','enabled':True,'type':'secret' if 'password' in k or 'token' in k else 'default'} for k in keys]}
for name, value in [('AEGIS.postman_collection.json',collection), ('AEGIS-Local.postman_environment.json',environment)]:
    (ROOT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print('Generated collection:', len(items), 'requests; environment has no credentials/tokens')
