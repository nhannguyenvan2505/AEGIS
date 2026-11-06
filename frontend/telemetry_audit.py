"""Read-only raw telemetry diagnostics; no field certification or aggregation."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import statistics
from telemetry_tool import digest
import controlled_source as controlled

FIELDS=['air_temperature_c','relative_humidity_pct','leaf_wet']


def stamp(v):
    if not isinstance(v,str):raise ValueError('Timezone-aware ISO8601 required')
    t=datetime.fromisoformat(v.replace('Z','+00:00'))
    if t.tzinfo is None or not 1900<=t.year<=2100:raise ValueError('Invalid timestamp')
    return t.astimezone(timezone.utc)


def load(path):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def invalid(v):raise ValueError('Nonfinite number')
    if path.stat().st_size>64*1024*1024:raise ValueError('Audit input exceeds 64 MiB')
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=invalid)


def validate(b):
    raw=dict(b);sha=raw.pop('bundle_sha256',None)
    if digest(raw)!=sha:raise ValueError('Snapshot hash/schema mismatch')
    controlled.validate_export(b)
    if b['training_approved'] is not False or b['hourly_aggregation_performed'] is not False:raise ValueError('Only unapproved raw staging is supported')
    m=b['metadata']
    if digest(m)!=b['metadata_sha256'] or m['measurement_semantics']!='point_observation':raise ValueError('Metadata hash/semantics mismatch')
    if m['calibration_verified'] is not False:raise ValueError('Unsupported declared calibration status')
    if m['units']!=dict(air_temperature_c='degC',relative_humidity_pct='percent',leaf_wet='boolean_point_state'):raise ValueError('Unexpected units')
    cadence=m['nominal_interval_seconds']
    if cadence is not None and (type(cadence) is not int or not 1<=cadence<=86400):raise ValueError('Invalid nominal cadence')
    exported=stamp(b['exported_at'])
    if stamp(b['stream_created_at'])>exported:raise ValueError('Metadata after export')
    ids=set();times=set()
    for r in b['readings']:
        if r['id'] in ids or stamp(r['observed_at']) in times or r['stream_id']!=b['stream_id']:raise ValueError('Duplicate sample/time or stream mismatch')
        ids.add(r['id']);times.add(stamp(r['observed_at']))
        if not stamp(r['observed_at'])<=stamp(r['received_at'])==stamp(r['available_at'])<=exported:raise ValueError('Invalid observation/availability ordering')
        if r['excluded_at'] is not None:
            if not stamp(r['received_at'])<=stamp(r['excluded_at'])<=exported or not r['exclusion_reason']:raise ValueError('Invalid exclusion ordering/reason')
        elif r['exclusion_reason'] is not None:raise ValueError('Reason without exclusion time')
        p=r['payload']
        if digest(p)!=r['payload_sha256']:raise ValueError('Sample payload hash mismatch')
        for k,lo,hi in [('air_temperature_c',-50,60),('relative_humidity_pct',0,100)]:
            v=p[k]
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi):raise ValueError('Invalid raw numeric value')
        if p['leaf_wet'] is not None and type(p['leaf_wet']) is not bool:raise ValueError('Invalid point wetness')
        if p['reported_quality'] not in ['unknown','nominal','suspect']:raise ValueError('Invalid reported quality')
        missing=[k for k in FIELDS if p[k] is None]
        expected=dict(version='aegis-raw-qc-v1',missing_fields=missing,reported_suspect=p['reported_quality']=='suspect',
            status='incomplete' if missing else 'suspect' if p['reported_quality']=='suspect' else 'within_technical_bounds',calibration_verified=False,hourly_eligible=False)
        if r['qc']!=expected:raise ValueError('Stored QC does not match technical rules')


def stats(values):
    if not values:return dict(count=0,min=None,median=None,p95_nearest_rank=None,max=None)
    v=sorted(values)
    return dict(count=len(v),min=v[0],median=statistics.median(v),p95_nearest_rank=v[math.ceil(.95*len(v))-1],max=v[-1])


def constant_run(rows,key):
    best=dict(sample_count=0,elapsed_seconds=0,start_at=None,end_at=None);start=None;last=None;n=0
    for r in rows:
        value=r['payload'][key]
        if value is None:start=None;last=None;n=0;continue
        if start is None or value!=last:start=r['observed_at'];n=1
        else:n+=1
        last=value
        candidate=dict(sample_count=n,elapsed_seconds=(stamp(r['observed_at'])-stamp(start)).total_seconds(),start_at=start,end_at=r['observed_at'])
        if (candidate['sample_count'],candidate['elapsed_seconds'])>(best['sample_count'],best['elapsed_seconds']):best=candidate
    return best


def audit(b,start,end,as_of):
    validate(b);start=stamp(start);end=stamp(end);as_of=stamp(as_of)
    if not start<end<=as_of<=stamp(b['exported_at']):raise ValueError('Require start < end <= as_of <= snapshot export')
    known=stamp(b['stream_created_at'])<=as_of
    window=[r for r in b['readings'] if start<=stamp(r['observed_at'])<end]
    received=sorted([r for r in window if known and stamp(r['available_at'])<=as_of],key=lambda r:stamp(r['observed_at']))
    excluded=[r for r in received if r['excluded_at'] is not None and stamp(r['excluded_at'])<=as_of]
    excluded_ids={r['id'] for r in excluded};active=[r for r in received if r['id'] not in excluded_ids]
    gaps=[(stamp(y['observed_at'])-stamp(x['observed_at'])).total_seconds() for x,y in zip(received,received[1:])]
    cadence=b['metadata']['nominal_interval_seconds'] if known else None
    def counts(rows):return dict(samples=len(rows),missing_fields={k:sum(r['payload'][k] is None for r in rows) for k in FIELDS},qc=dict(Counter(r['qc']['status'] for r in rows)),reported_quality=dict(Counter(r['payload']['reported_quality'] for r in rows)))
    result=dict(schema_version='aegis-telemetry-audit-v1',input_bundle_sha256=b['bundle_sha256'],declared_source=b['metadata']['source'],
        window_start=start.isoformat(),window_end_exclusive=end.isoformat(),as_of=as_of.isoformat(),stream_known_as_of=known,
        received=counts(received),not_excluded_as_of=counts(active),excluded_as_of_count=len(excluded),
        retrospective_not_available_count=len(window)-len(received),
        received_latency_seconds=stats([(stamp(r['received_at'])-stamp(r['observed_at'])).total_seconds() for r in received]),
        observed_interval_seconds=stats(gaps),declared_nominal_interval_seconds=cadence,
        intervals_exceeding_nominal_count=None if cadence is None else sum(g>cadence for g in gaps),
        longest_constant_observed_runs={k:constant_run(received,k) for k in FIELDS},
        first_received_observation_at=received[0]['observed_at'] if received else None,last_received_observation_at=received[-1]['observed_at'] if received else None,
        coverage_fraction=None,missing_expected_samples=None,wet_duration_hours=None,aggregation_performed=False,training_approved=False,
        limits=['Diagnostics only, no QC acceptance threshold or calibration certification',
                'Intervals exceeding nominal can be jitter; not automatically dropped samples',
                'Repeated values can be stable environment; not automatically stuck sensors',
                'Constant runs use observed points and do not establish continuity across gaps',
                'Coverage needs a declared schedule/anchor and protocol; empty is not complete',
                'Retrospective unavailable counts inspect the snapshot; never use this report as forecast features'])
    if b['metadata']['source']==controlled.SOURCE:
        result.update(schema_version='aegis-telemetry-audit-v2',experiment_context=b['metadata']['experiment_context'],
                      source_policy=dict(controlled.POLICY),experiment_context_is_predictor=False)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['bundle','out']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['start','end','as-of']:p.add_argument('--'+name,required=True)
    args=p.parse_args()
    try:
        if args.out.exists():raise ValueError('Refuse overwrite; use a new output file')
        result=audit(load(args.bundle),args.start,args.end,args.as_of)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        print('Audit written; diagnostic only; training_approved=false')
    except (ValueError,TypeError,KeyError,OSError) as exc:p.exit(2,'Audit blocked: '+str(exc)+'\n')


if __name__=='__main__':main()
