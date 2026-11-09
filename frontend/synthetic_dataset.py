"""T16 explicit synthetic joins, point-in-time features and audited group/time splits."""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import sys

from forecast_intake import encoded,exact,read_json_bytes,text
from hourly_aggregation import aggregate,project_feature_input
from synthetic_endpoints import evaluate,validate as validate_observations,identifier,PROTOCOL_SHA256
from telemetry_audit import stamp,validate as validate_raw
from telemetry_tool import digest

RUNTIME=Path(__file__).resolve().parents[1]/'forecast_demo/runtime'
if str(RUNTIME) not in sys.path: sys.path.append(str(RUNTIME))
from weather_forecast import prepare_weather,FEATURES,CONTRACT_SHA256

SCHEMA='aegis-synthetic-dataset-input-v1'
SPLITS=('train','validation','test')


def validate(b):
    exact(b,('schema_version','source','dataset_id','protocol_sha256','entries','split_plan','bundle_sha256'))
    unsigned=dict(b); pin=unsigned.pop('bundle_sha256')
    if digest(unsigned)!=pin or b['schema_version']!=SCHEMA or b['source']!='synthetic' or b['protocol_sha256']!=PROTOCOL_SHA256:
        raise ValueError('Dataset source/schema/protocol/hash mismatch')
    text(b['dataset_id'])
    if not isinstance(b['entries'],list) or not 1<=len(b['entries'])<=50: raise ValueError('Require 1..50 explicit mappings')
    ids=set(); keys=set(); total=0
    for e in b['entries']:
        exact(e,('id','mapping','raw','observations','context_revisions','hourly_policy','issue_times'))
        identifier(e['id'])
        if e['id'] in ids: raise ValueError('Duplicate mapping ID')
        ids.add(e['id']); m=e['mapping']; raw=e['raw']; obs=e['observations']
        exact(m,('owner_id','season_id','unit_id','stream_id','raw_bundle_sha256','observation_bundle_sha256',
                 'context_sha256','hourly_policy_sha256','groups','relationship_available_at','snapshot_linked_at','linkage_reference',
                 'use_rights_status','use_rights_reference'))
        validate_raw(raw); validate_observations(obs)
        if raw['metadata']['source']!='synthetic': raise ValueError('Synthetic raw required')
        for k in ('owner_id','season_id'):
            if m[k]!=raw[k] or m[k]!=obs[k]: raise ValueError('Owner/season join mismatch')
        if m['unit_id']!=obs['unit_id'] or m['stream_id']!=raw['stream_id'] or m['groups']!=obs['groups']:
            raise ValueError('Unit/stream/dependency join mismatch')
        if (m['raw_bundle_sha256']!=raw['bundle_sha256'] or m['observation_bundle_sha256']!=obs['bundle_sha256']
                or m['context_sha256']!=digest(e['context_revisions']) or m['hourly_policy_sha256']!=digest(e['hourly_policy'])):
            raise ValueError('Explicit mapping pins do not match inputs')
        text(m['linkage_reference']); text(m['use_rights_reference'])
        linked=stamp(m['snapshot_linked_at'])
        if not stamp(m['relationship_available_at'])<=linked or any(stamp(x['exported_at'])>linked for x in (raw,obs)):
            raise ValueError('Snapshot linkage cannot precede source exports or relationship knowledge')
        if any(stamp(x['available_at'])>linked for x in e['context_revisions']) or stamp(e['hourly_policy']['available_at'])>linked:
            raise ValueError('Snapshot linkage predates context/policy knowledge')
        if m['use_rights_status']!='project_generated_simulation': raise ValueError('Only declared project-generated virtual data supported')
        if not isinstance(e['issue_times'],list) or not e['issue_times']: raise ValueError('Issue times required')
        for t in e['issue_times']:
            issue=stamp(t); key=(m['unit_id'],m['season_id'],m['stream_id'],issue)
            if key in keys: raise ValueError('Duplicate unit/season/stream/issue row')
            keys.add(key); total+=1
        if total>1000: raise ValueError('Dataset exceeds 1000 scheduled rows')
    p=b['split_plan']
    exact(p,('schema_version','plan_id','available_at','purpose','assignments','periods','data_lock_at','embargo_hours'))
    if p['schema_version']!='aegis-synthetic-group-time-split-v1' or p['purpose']!='engineering_audit_not_blind_model_selection':
        raise ValueError('Engineering split plan required')
    text(p['plan_id']); known=stamp(p['available_at']); lock=stamp(p['data_lock_at'])
    if type(p['embargo_hours']) is not int or not 0<=p['embargo_hours']<=744: raise ValueError('Bounded integer embargo required')
    exact(p['assignments'],ids); exact(p['periods'],SPLITS)
    if any(x not in SPLITS for x in p['assignments'].values()): raise ValueError('Unknown split assignment')
    for split in SPLITS:
        q=p['periods'][split]; exact(q,('start_at','end_at','label_cutoff'))
        start,end,cut=(stamp(q[k]) for k in ('start_at','end_at','label_cutoff'))
        if not known<=start<end<=cut<=lock: raise ValueError('Invalid split knowledge/period/lock ordering')
    for left,right in zip(SPLITS,SPLITS[1:]):
        if stamp(p['periods'][left]['label_cutoff'])>=stamp(p['periods'][right]['start_at']):
            raise ValueError('Earlier labels must be available before next split starts')
    for e in b['entries']:
        cut=stamp(p['periods'][p['assignments'][e['id']]]['label_cutoff'])
        if cut>stamp(e['observations']['exported_at']): raise ValueError('Label cutoff exceeds observation export')
        if any(stamp(e[k]['exported_at'])>lock for k in ('raw','observations')):
            raise ValueError('Source snapshot exported after data lock')
        if stamp(e['mapping']['snapshot_linked_at'])>lock or any(stamp(x['available_at'])>lock for x in e['context_revisions']):
            raise ValueError('Mapping/context knowledge exceeds data lock')


def dependency_components(entries):
    """Union by every shared identifier, including transitive links and raw reuse."""
    parent={e['id']:e['id'] for e in entries}; seen={}
    def root(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    for e in sorted(entries,key=lambda e:e['id']):
        m=e['mapping']
        tokens=[(k,m[k]) for k in ('unit_id','season_id','stream_id')]
        tokens += [(k,v) for k,v in m['groups'].items()]
        tokens += [('raw_sample_id',r['id']) for r in e['raw']['readings']]
        tokens += [('observation_id',r['id']) for r in e['observations']['visits']]
        for token in tokens:
            if token in seen:
                a,c=root(e['id']),root(seen[token]); parent[max(a,c)]=min(a,c)
            else: seen[token]=e['id']
    groups={}
    for e in entries: groups.setdefault(root(e['id']),[]).append(e['id'])
    return {digest(sorted(members)):sorted(members) for members in groups.values()}


def build(b):
    validate(b); p=b['split_plan']; assignments=p['assignments']
    components=dependency_components(b['entries']); member_component={m:k for k,v in components.items() for m in v}
    conflicts=[dict(component_id=k,members=v,splits=sorted({assignments[m] for m in v}))
               for k,v in sorted(components.items()) if len({assignments[m] for m in v})>1]
    conflicted={m for c in conflicts for m in c['members']}
    rows=[]
    for e in sorted(b['entries'],key=lambda e:e['id']):
        m=e['mapping']; split=assignments[e['id']]; q=p['periods'][split]
        for issued_at in sorted(e['issue_times'],key=stamp):
            issue=stamp(issued_at); end=issue.replace(minute=0,second=0,microsecond=0); start=end-timedelta(hours=120)
            hourly=aggregate(e['raw'],e['hourly_policy'],dict(start_at=start.isoformat(),end_at=end.isoformat(),as_of=issue.isoformat()))
            payload=project_feature_input(hourly,m['unit_id'],e['context_revisions'],issue.isoformat())
            feature=prepare_weather(payload)['rows'][0]
            label=evaluate(e['observations'],issue.isoformat(),q['label_cutoff'])
            reasons=[]
            if stamp(m['relationship_available_at'])>issue: reasons.append('relationship_not_available_at_issue')
            if not stamp(q['start_at'])<=issue<stamp(q['end_at']): reasons.append('issue_outside_split_period')
            if feature['feature_status']!='ready': reasons.append('features_insufficient_as_of_issue')
            if label['synthetic_y'] is None: reasons.append('endpoint_not_binary_at_split_cutoff')
            if e['id'] in conflicted: reasons.append('dependency_component_crosses_splits')
            evidence=digest(dict(bucket_sha256=[x['bucket_sha256'] for x in hourly['buckets']],
                context_sha256=feature['context_sha256'],policy_sha256=hourly['policy_sha256'],issued_at=issue.isoformat()))
            row=dict(row_id=digest(dict(mapping_id=e['id'],issued_at=issue.isoformat())),mapping_id=e['id'],
                component_id=member_component[e['id']],split=split,owner_id=m['owner_id'],unit_id=m['unit_id'],
                season_id=m['season_id'],stream_id=m['stream_id'],groups=m['groups'],issued_at=issue.isoformat(),
                feature_window_start=start.isoformat(),feature_window_end=end.isoformat(),feature_cutoff=issue.isoformat(),
                relationship_available_at=m['relationship_available_at'],snapshot_linked_at=m['snapshot_linked_at'],
                target_window_end=label['target_window_end'],label_cutoff=q['label_cutoff'],
                feature_status=feature['feature_status'],feature_reasons=feature['reasons'],
                predictors=feature['predictors'],predictors_sha256=feature['predictors_sha256'],
                feature_contract_sha256=CONTRACT_SHA256,feature_evidence_sha256=evidence,
                context_revision=feature['context_revision'],context_sha256=feature['context_sha256'],
                raw_bundle_sha256=e['raw']['bundle_sha256'],endpoint_status=label['status'],
                synthetic_y=label['synthetic_y'],endpoint_available_at=label['synthetic_endpoint_available_at'],
                endpoint_knowledge_sha256=label['knowledge_sha256'],observed_event_interval=label['observed_event_interval'],
                reasons=reasons,engineering_eligible=not reasons,training_approved=False,field_validated=False)
            rows.append(row)
    # Purge earlier rows whose feature+target support touches a later split.
    candidates=[r for r in rows if r['engineering_eligible']]
    for row in candidates:
        others=[x for x in candidates if SPLITS.index(x['split'])>SPLITS.index(row['split'])
                and stamp(row['target_window_end'])+timedelta(hours=p['embargo_hours'])>=stamp(x['feature_window_start'])]
        if others:
            row['engineering_eligible']=False; row['reasons'].append('purged_feature_target_support_overlap')
            row['purged_against_row_ids']=sorted(x['row_id'] for x in others)
    matrices={s:[dict(row_id=r['row_id'],predictors=r['predictors'],synthetic_y=r['synthetic_y'])
                 for r in rows if r['split']==s and r['engineering_eligible']] for s in SPLITS}
    for records in matrices.values():
        if any(set(r['predictors'])!=set(FEATURES) for r in records): raise ValueError('Predictor whitelist mismatch')
    counts={s:dict(rows=len(matrices[s]),class_counts={str(y):sum(r['synthetic_y']==y for r in matrices[s]) for y in (0,1)},
                   declared_components=len({r['component_id'] for r in rows if r['split']==s and r['engineering_eligible']})) for s in SPLITS}
    events={(r['unit_id'],r['season_id'],r['observed_event_interval']['present_visit_id'])
            for r in rows if r['engineering_eligible'] and r['synthetic_y']==1}
    ready=not conflicts and all(counts[s]['rows'] and all(counts[s]['class_counts'].values()) for s in SPLITS)
    result=dict(schema_version='aegis-synthetic-dataset-report-v1',source='synthetic',dataset_id=b['dataset_id'],
        input_bundle_sha256=b['bundle_sha256'],protocol_sha256=PROTOCOL_SHA256,feature_contract_sha256=CONTRACT_SHA256,
        split_plan_sha256=digest(p),rows=rows,matrices=matrices,split_counts=counts,dependency_components=components,
        dependency_conflicts=conflicts,distinct_simulated_events=len(events),scheduled_rows=len(rows),
        eligible_rows=sum(r['engineering_eligible'] for r in rows),
        exclusion_counts=dict(Counter(reason for r in rows for reason in r['reasons'])),
        ready_for_engineering_experiment=bool(ready),sufficient_for_scientific_claims=False,
        training_approved=False,training_performed=False,field_validated=False,
        test_outcomes_exposed_for_audit=True,blind_holdout_for_model_selection=False,
        limits=['Declared synthetic dependency components are not physical independent units',
                'Two classes and nonempty splits are engineering checks, not sample-size justification',
                'Only matrices[*].predictors may enter future estimators; never flatten audit rows',
                'This fixture tests joins/splits, not weather-to-disease predictability or model accuracy'])
    result['report_sha256']=digest(result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); args=p.parse_args()
    try:
        result=build(read_json_bytes(args.input.read_bytes()))
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('xb') as f: f.write(encoded(result))
        print(json.dumps(dict(ready=result['ready_for_engineering_experiment'],rows=result['scheduled_rows'],eligible=result['eligible_rows'],source='synthetic')))
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError):
        p.exit(2,'Dataset blocked: invalid source/mapping/split input or existing output.\n')


if __name__=='__main__': main()
