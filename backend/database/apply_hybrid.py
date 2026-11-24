"""One-time hybrid extension and validator upgrade on the Compose databases."""
from pathlib import Path
from verify_databases import run,MYSQL


def main():
    status=run('mysql',MYSQL,'SELECT status FROM schema_versions WHERE version=3;')
    if status.returncode: raise RuntimeError(status.stderr)
    if status.stdout.strip()=='running': raise RuntimeError('Partial migration 3 requires inspection')
    if status.stdout.strip()!='complete':
        result=run('mysql',MYSQL,(Path(__file__).parent/'mysql'/'003_hybrid.sql').read_text(encoding='utf-8'))
        if result.returncode: raise RuntimeError(result.stderr)
    status=run('mysql',MYSQL,'SELECT status FROM schema_versions WHERE version=4;')
    if status.returncode or status.stdout.strip()=='running': raise RuntimeError('Inspect partial migration 4 before proceeding')
    if status.stdout.strip()!='complete':
        result=run('mysql',MYSQL,(Path(__file__).parent/'mysql'/'004_api_semantics.sql').read_text(encoding='utf-8'))
        if result.returncode: raise RuntimeError(result.stderr)
    script="""
for (const name of ['telemetry_readings','sensor_raw_events','ai_inference_logs']) {
 const options=db.getCollectionInfos({name})[0].options;
 options.validator.$jsonSchema.properties.source.enum=['mock','synthetic','field','bench','legacy','user_uploaded'];
 const result=db.runCommand({collMod:name,validator:options.validator,validationLevel:'strict',validationAction:'error'});
 if (!result.ok) throw new Error('Validator upgrade failed');
}
print('MongoDB validators upgraded');
"""
    result=run('mongo',['sh','-c','exec mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin aegis'],script)
    if result.returncode or 'MongoDB validators upgraded' not in result.stdout: raise RuntimeError('Mongo validator upgrade failed')
    print('Hybrid schema versions 3/4 and Mongo validators ready')


if __name__=='__main__': main()
