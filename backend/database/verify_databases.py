"""Integration checks for the isolated Compose dev databases (Python stdlib only).

MySQL fixtures are rolled back on each connection, including rejection cases.
Mongo fixtures use generated ObjectIds and are removed in a finally block.
No SQLite files or application runtime are accessed.
"""
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parent
COMPOSE = ['docker', 'compose', '--env-file', str(ROOT / '.env'), '-f', str(ROOT / 'compose.yaml')]


def run(service, command, payload):
    return subprocess.run(COMPOSE + ['exec', '-T', service] + command,
                          input=payload, text=True, capture_output=True, timeout=60)


MYSQL = ['sh', '-c', 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql --batch --skip-column-names -u "$MYSQL_USER" -D aegis']


def mysql_check(label, sql, expected_error=None):
    result = run('mysql', MYSQL, sql)
    if expected_error is None:
        if result.returncode:
            raise RuntimeError(f'{label}: {result.stderr}')
    elif result.returncode == 0 or f'ERROR {expected_error} ' not in result.stderr:
        raise RuntimeError(f'{label}: expected MySQL error {expected_error}; {result.stderr}')
    print(f'PASS {label}')
    return result.stdout.strip()


def main():
    tables = mysql_check('MySQL table inventory', "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE';").splitlines()
    expected = {'roles','users','password_reset_tokens','farms','farm_fields','crop_cycles',
                'iot_devices','diseases','crop_images','model_versions','disease_detections',
                'risk_predictions','treatment_recommendations','alerts','notifications',
                'alert_thresholds','audit_logs','system_settings'}
    runtime = 'schema_versions' in tables
    if runtime:
        expected |= {'schema_versions','runtime_lock','owner_default_farms','analysis_runs','sessions',
                     'rate_limit_buckets','inference_requests','mock_hourly_readings','mock_assessments',
                     'assessment_analysis_links','cultivation_revisions'}
    if 'mongo_outbox' in tables:
        expected |= {'mongo_outbox','pilot_stores','pilot_scope_locks','legacy_archive','migration_sources'}
        import json
        layout=json.loads((ROOT/'pilot_schema.json').read_text(encoding='utf-8'))
        scopes={'journal.sqlite3':'j','management.sqlite3':'m','telemetry.sqlite3':'t','followup.sqlite3':'f','research.sqlite3':'r','automation.sqlite3':'a'}
        keys=mysql_check('Pilot namespace registry', 'SELECT store_key FROM pilot_stores;').splitlines()
        for key in keys:
            expected.update('p_'+key+'_'+scopes[filename]+'_'+name for filename,data in layout.items() for name in data['columns'])
    if set(tables) != expected:
        raise RuntimeError(f'Unexpected MySQL tables: {tables}')
    token = uuid.uuid4().hex
    fixture = f"""
START TRANSACTION;
INSERT INTO users(role_id,email,username,password_hash)
 SELECT role_id,'verify-{token}@example.invalid','verify-{token}','test-only' FROM roles WHERE role_name='farmer';
SET @u=LAST_INSERT_ID();
INSERT INTO farms(owner_user_id,farm_name) VALUES(@u,'verification'); SET @f=LAST_INSERT_ID();
INSERT INTO farm_fields(farm_id,field_name,crop_type{',user_id,api_created_at' if runtime else ''}) VALUES(@f,'verification','rice'{",@u,'2026-11-09T00:00:00+00:00'" if runtime else ''}); SET @field=LAST_INSERT_ID();
INSERT INTO crop_images(field_id,uploaded_by,source_type,image_url{',image_width,image_height,orientation' if runtime else ''}) VALUES(@field,@u,'mobile','test-only'{",32,32,'exif_corrected'" if runtime else ''}); SET @image=LAST_INSERT_ID();
INSERT INTO model_versions(model_type,version_name,algorithm,artifact_path) VALUES('yolo_detection','verify-{token}','test','test-only'); SET @model=LAST_INSERT_ID();
"""
    detection = 'INSERT INTO disease_detections(image_id,model_version_id,confidence{columns}) VALUES(@image,@model,{values});'
    if runtime:
        fixture += f"""INSERT INTO analysis_runs(external_id,user_id,image_id,model_version_id,model_version,model_sha256,status,created_at)
          VALUES('{token}',@u,@image,@model,'test','{'a'*64}','no_detection','2026-11-09T00:00:00+00:00'); SET @analysis=LAST_INSERT_ID();"""
        detection = "INSERT INTO disease_detections(image_id,model_version_id,analysis_id,class_id,disease_label,source_confidence,source_bbox,confidence{columns}) VALUES(@image,@model,@analysis,0,'test',0.8,'{{}}',{values});"
    mysql_check('valid confidence/bbox and rollback', fixture + detection.format(
        columns=',bbox_x,bbox_y,bbox_width,bbox_height', values='0.8,0,0,10,20') + 'ROLLBACK;')
    for label, statement, error in [
        ('confidence range', detection.format(columns='', values='1.1'), 3819),
        ('partial bbox', detection.format(columns=',bbox_x', values='0.8,0'), 3819),
        ('foreign key', 'INSERT INTO farms(owner_user_id,farm_name) VALUES(-1,\'invalid\');', 1452),
        ('ObjectId format', detection.format(columns=',inference_log_id', values="0.8,'not-an-objectid'"), 3819),
        ('threshold bounds', "INSERT INTO alert_thresholds(metric,operator,threshold_value) VALUES('humidity','between',50);", 3819),
        ('unique email', f"INSERT INTO users(role_id,email,username,password_hash) SELECT role_id,email,'duplicate-{token}','test' FROM users WHERE user_id=@u;", 1062),
    ]:
        mysql_check(label, fixture + statement + 'ROLLBACK;', error)
    # is_active defaults false above. A duplicate active version must fail.
    mysql_check('single active model per type', fixture +
                "UPDATE model_versions SET is_active=TRUE WHERE model_version_id=@model;" +
                f"INSERT INTO model_versions(model_type,version_name,algorithm,artifact_path,is_active) VALUES('yolo_detection','other-{token}','test','test',TRUE);ROLLBACK;", 1062)
    remaining = mysql_check('MySQL fixture cleanup',
                            f"SELECT COUNT(*) FROM users WHERE email='verify-{token}@example.invalid';")
    if remaining != '0':
        raise RuntimeError('MySQL fixtures were not rolled back')
    mongo_script = (ROOT / 'verify_mongo.js').read_text(encoding='utf-8')
    result = run('mongo', ['sh', '-c', 'exec mongosh --quiet -u aegis_app -p "$AEGIS_MONGO_PASSWORD" --authenticationDatabase aegis aegis'], mongo_script)
    if result.returncode or 'PASS MongoDB schema, validators, indexes and fixture cleanup' not in result.stdout:
        raise RuntimeError(f'MongoDB verification failed: {result.stdout}\n{result.stderr}')
    # mongosh stdin includes interactive prompts; retain only meaningful results.
    for line in result.stdout.splitlines():
        if 'PASS ' in line:
            print(line[line.index('PASS '):])
    print('PASS all database integration checks')


if __name__ == '__main__':
    main()
