"""Raw telemetry staging tools: loopback import or stopped-store read-only export.

No aggregation, model inference, or field training approval.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from pilot_store import validate_storage,StoreLease
import controlled_source as controlled


def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def load(path):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def invalid(v):raise ValueError('Nonfinite JSON number')
    if path.stat().st_size>64*1024:raise ValueError('Input JSON exceeds 64 KiB')
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=invalid)


def export(store,owner,stream_id,expected_source=None):
    from datetime import datetime,timezone
    store=validate_storage(store);path=store/'telemetry.sqlite3'
    if not path.is_file():raise ValueError('Missing telemetry database; never create during export')
    with StoreLease(store),closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        if db.execute('SELECT kind FROM telemetry_meta').fetchone()[0]!='aegis-pilot-telemetry-v1':raise ValueError('Unsupported telemetry schema')
        s=db.execute('SELECT * FROM streams WHERE id=? AND user_id=?',(stream_id,owner)).fetchone()
        if s is None:raise ValueError('Stream not found for selected owner')
        m=json.loads(s['metadata_json'])
        if digest(m)!=s['metadata_sha256']:raise ValueError('Metadata hash mismatch')
        source=controlled.validate_metadata(m)
        if expected_source is not None and expected_source!=source:raise ValueError('Selected stream does not match expected source')
        readings=[]
        for row in db.execute('SELECT * FROM raw_records WHERE stream_id=? AND user_id=? ORDER BY observed_at,id',(stream_id,owner)):
            r=dict(row);r.pop('user_id');r['payload']=json.loads(r.pop('payload_json'));r['qc']=json.loads(r.pop('qc_json'))
            if digest(r['payload'])!=r['payload_sha256']:raise ValueError('Sample hash mismatch')
            r['available_at']=r['received_at'];readings.append(r)
        result=dict(schema_version='aegis-raw-telemetry-export-v1',exported_at=datetime.now(timezone.utc).isoformat(),
            owner_id=owner,season_id=s['season_id'],stream_id=stream_id,metadata=m,metadata_sha256=s['metadata_sha256'],
            stream_created_at=s['created_at'],readings=readings,training_approved=False,hourly_aggregation_performed=False,
            limits=['Declared source/instrument, calibration not verified','Point wetness does not establish wet duration','Empty stream does not establish coverage'])
        if source==controlled.SOURCE:
            result.update(schema_version=controlled.EXPORT_SCHEMA,source_policy=dict(controlled.POLICY))
        controlled.validate_export(result)
        result['bundle_sha256']=digest(result);return result


def import_records(url,stream_id,path,token):
    # Never send credentials to an arbitrary host or follow a redirect.
    import requests
    from uuid import UUID
    stream_id=str(UUID(stream_id));u=urlsplit(url)
    if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost','::1'] or u.username or u.password or u.path not in ['','/'] or u.query or u.fragment:
        raise ValueError('Only a loopback HTTP origin is accepted')
    if not token or '\n' in token or '\r' in token:raise ValueError('Set AEGIS_PILOT_TOKEN to a valid local token')
    payload=load(path)
    with requests.Session() as session:
        session.trust_env=False
        r=session.post(url.rstrip('/')+'/api/farm/environment-streams/'+stream_id+'/samples',json=payload,
            headers={'Authorization':'Bearer '+token},timeout=20,allow_redirects=False)
    if r.status_code not in [200,201]:raise ValueError('Import refused: HTTP '+str(r.status_code)+'; no automatic retry')
    result=r.json();return dict(http_status=r.status_code,created=result['created'],replayed=result['replayed'],request_id=r.headers.get('X-Request-ID'))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('snapshot');s.add_argument('--store',type=Path,required=True);s.add_argument('--owner-id',required=True);s.add_argument('--stream-id',required=True);s.add_argument('--out',type=Path,required=True)
    s.add_argument('--expected-source',choices=controlled.SOURCES,help='Refuse a stream from a different source')
    i=sub.add_parser('import');i.add_argument('--url',required=True);i.add_argument('--stream-id',required=True);i.add_argument('--file',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='snapshot':
            out=args.out.resolve();store=validate_storage(args.store)
            if out.exists() or out.is_relative_to(store):raise ValueError('Use a new output file outside pilot storage')
            result=export(store,args.owner_id,args.stream_id,args.expected_source)
            out.parent.mkdir(parents=True,exist_ok=True)
            with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
            print('Raw staging snapshot written; no aggregation or training approval')
        else:print(json.dumps(import_records(args.url,args.stream_id,args.file,os.environ.get('AEGIS_PILOT_TOKEN',''))))
    except (ValueError,TypeError,KeyError,RuntimeError,sqlite3.Error,OSError) as exc:
        # HTTP client exceptions can contain headers/URLs; keep their details private.
        p.exit(2,('Telemetry tool blocked: local connection failed' if type(exc).__module__.startswith('requests') else 'Telemetry tool blocked: '+str(exc))+'\n')


if __name__=='__main__':main()
