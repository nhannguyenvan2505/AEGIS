"""Offline temporal dataset preparation. No training, inference, HTTP or database.

Synthetic examples test software only. Label ambiguity/censoring is retained.
"""
import argparse
from datetime import datetime, timedelta, timezone, date
import hashlib
import json
import math
from pathlib import Path

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=7))
HOUR = timedelta(hours=1)
SPEC = {'version':'aegis-temporal-dataset-v0.1', 'disease':'leaf_blast',
        'lookback_hours':120, 'feature_windows_hours':[6,24,72,120],
        'horizon_hours':72, 'max_survey_gap_hours':24,
        'coverage_policy':'complete 120h temperature/RH/wetness and known calendar age',
        'intervention_policy':'exclude recorded follow-up interventions from primary binary dataset',
        'window_end_policy':'floor actual issued_at to UTC hour; availability checked at actual issued_at',
        'status':'research_design_proposal_not_field_validated'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def stamp(value, hourly=False):
    if not isinstance(value,str):raise ValueError('Timezone-aware ISO8601 timestamp required')
    try:t=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise ValueError('Invalid timestamp') from exc
    if t.tzinfo is None:raise ValueError('Timezone required')
    t=t.astimezone(UTC)
    if not 1900<=t.year<=2100:raise ValueError('Timestamp outside technical bounds')
    if hourly and (t.minute or t.second or t.microsecond):raise ValueError('UTC hourly boundary required')
    return t


def identifier(value):
    if not isinstance(value,str) or not value.strip() or len(value)>160:raise ValueError('Nonempty identifier required')
    return value


def numeric(value,lo,hi):
    if value is None:return None
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid finite technical sensor value')
    return value


def clocked(row,event):
    observed=stamp(row[event]);recorded=stamp(row['recorded_at']);available=stamp(row['available_at'])
    if not observed<=recorded<=available:raise ValueError('Require event <= recorded_at <= available_at')
    return observed,available


def validate_series(s):
    if set(s)!={'plot_id','season_id','device_id','telemetry','context_revisions','surveys','interventions'}:
        raise ValueError('Invalid series fields')
    for key in ['plot_id','season_id','device_id']:identifier(s[key])
    for key in ['telemetry','context_revisions','surveys','interventions']:
        if not isinstance(s[key],list):raise ValueError('Series records must be lists')
    seen=set()
    for r in s['telemetry']:
        if set(r)!={'start_at','available_at','air_temperature_c','relative_humidity_pct','leaf_wet','quality'}:raise ValueError('Invalid telemetry fields')
        t=stamp(r['start_at'],True)
        if t in seen:raise ValueError('Duplicate UTC telemetry hour; do not silently overwrite')
        seen.add(t)
        if stamp(r['available_at'])<t+HOUR:raise ValueError('Bucket available before it finished')
        numeric(r['air_temperature_c'],-50,60);numeric(r['relative_humidity_pct'],0,100)
        if r['leaf_wet'] is not None and type(r['leaf_wet']) is not bool:raise ValueError('Wetness must be bool/null')
        if r['quality'] not in ['valid','missing','suspect']:raise ValueError('Unsupported quality')
    visits=set()
    for r in s['surveys']:
        if set(r)!={'visit_id','revision','observed_at','recorded_at','available_at','finding','verification','scheduled','review_reference'}:raise ValueError('Invalid survey fields')
        identifier(r['visit_id']);clocked(r,'observed_at')
        if type(r['revision']) is not int or r['revision']<1:raise ValueError('Positive survey revision required')
        key=(r['visit_id'],r['revision'])
        if key in visits:raise ValueError('Duplicate survey revision')
        visits.add(key)
        if r['finding'] not in ['absent','present','uncertain'] or r['verification'] not in ['unverified','confirmed']:raise ValueError('Invalid survey finding/verification')
        if type(r['scheduled']) is not bool:raise ValueError('Scheduled flag must be boolean')
        if r['verification']=='confirmed':
            identifier(r['review_reference'])
            if r['finding']=='uncertain':raise ValueError('Uncertain finding cannot be confirmed outcome')
    revisions=set()
    for r in s['context_revisions']:
        if set(r)!={'revision','recorded_at','available_at','profile'}:raise ValueError('Invalid context revision fields')
        if type(r['revision']) is not int or r['revision']<1 or r['revision'] in revisions:raise ValueError('Invalid/duplicate context revision')
        revisions.add(r['revision'])
        if stamp(r['available_at'])<stamp(r['recorded_at']):raise ValueError('Context available before recording')
        p=r['profile']
        required={'schema_version','source','timezone','region','province_or_city','locality','rice_variety','planting_method','sown_on','transplanted_on','season_status'}
        if not isinstance(p,dict) or set(p)!=required or p['schema_version']!='aegis-cultivation-v1' or p['source']!='user_declared' or p['timezone']!='UTC+07:00':raise ValueError('Use Backend cultivation-v1 profile')
        if p['planting_method'] not in ['unknown','direct_seeded','transplanted']:raise ValueError('Invalid planting method')
        if p['region'] not in ['unknown','central','southern','other'] or p['season_status'] not in ['unknown','planned','active','completed','archived']:raise ValueError('Invalid cultivation enum')
        for key in ['province_or_city','locality','rice_variety']:
            if p[key] is not None and (not isinstance(p[key],str) or len(p[key])>200):raise ValueError('Invalid context text')
        for key in ['sown_on','transplanted_on']:
            if p[key] is not None:
                d=date.fromisoformat(p[key])
                if d.isoformat()!=p[key] or not 1900<=d.year<=2100 or d>stamp(r['recorded_at']).astimezone(LOCAL).date():raise ValueError('Invalid/future actual planting date')
        if p['sown_on'] and p['transplanted_on'] and p['sown_on']>p['transplanted_on']:raise ValueError('Sowing after transplant')
        if p['planting_method']=='direct_seeded' and p['transplanted_on']:raise ValueError('Direct seeded cannot have transplant date')
    ids=set()
    for r in s['interventions']:
        if set(r)!={'intervention_id','at','recorded_at','available_at','kind'}:raise ValueError('Invalid intervention fields')
        identifier(r['intervention_id']);clocked(r,'at')
        if r['intervention_id'] in ids:raise ValueError('Duplicate intervention id')
        ids.add(r['intervention_id'])
        if r['kind'] not in ['fungicide','fertilizer','irrigation','other']:raise ValueError('Invalid intervention kind')
    # Revision numbers cannot be used to backdate knowledge.
    for key,identity in [('context_revisions',lambda r:'context'),('surveys',lambda r:r['visit_id'])]:
        groups={}
        for r in s[key]:groups.setdefault(identity(r),[]).append(r)
        for group in groups.values():
            ordered=sorted(group,key=lambda r:r['revision'])
            if any(stamp(b['available_at'])<stamp(a['available_at']) for a,b in zip(ordered,ordered[1:])):raise ValueError('Revision availability must not go backwards')


def feature_row(s,issued):
    window_end=issued.replace(minute=0,second=0,microsecond=0)
    eligible={stamp(r['start_at']):r for r in s['telemetry'] if stamp(r['available_at'])<=issued and stamp(r['start_at'])+HOUR<=window_end and r['quality']=='valid'}
    f={};coverage={}
    for window in SPEC['feature_windows_hours']:
        rows=[eligible.get(window_end-timedelta(hours=window-i)) for i in range(window)]
        for key,short in [('air_temperature_c','temp'),('relative_humidity_pct','rh')]:
            values=[r[key] for r in rows if r and r[key] is not None]
            count=len(values);f[f'{short}_coverage_{window}h']=count/window
            for kind in ['mean','min','max','std']:
                value=None
                if count:
                    mean=math.fsum(values)/count
                    value={'mean':mean,'min':min(values),'max':max(values),'std':math.sqrt(math.fsum((x-mean)**2 for x in values)/count)}[kind]
                f[f'{short}_{kind}_{window}h']=value
        wet=[r['leaf_wet'] if r else None for r in rows]
        known=sum(x is not None for x in wet)
        f[f'wet_coverage_{window}h']=known/window
        f[f'wet_observed_hours_{window}h']=sum(x is True for x in wet) if known else None
        run=longest=0
        for x in wet:
            run=run+1 if x is True else 0;longest=max(longest,run)
        f[f'longest_observed_wet_run_{window}h']=longest if known else None
        f[f'wet_run_left_censored_{window}h']=wet[0] if wet[0] is not None else None
        coverage[str(window)]={'temp':sum(r is not None and r['air_temperature_c'] is not None for r in rows),'rh':sum(r is not None and r['relative_humidity_pct'] is not None for r in rows),'wet':known}
    available=[r for r in s['context_revisions'] if stamp(r['available_at'])<=issued]
    context=max(available,key=lambda r:r['revision']) if available else None
    f.update(region=None,rice_variety=None,planting_method=None,crop_age_days=None,season_status=None)
    if context:
        p=context['profile']
        for key in ['region','rice_variety','planting_method','season_status']:f[key]=p[key]
        age_key={'transplanted':'transplanted_on','direct_seeded':'sown_on'}.get(p['planting_method'])
        if age_key and p[age_key]:
            age=(issued.astimezone(LOCAL).date()-date.fromisoformat(p[age_key])).days
            if age>=0:f['crop_age_days']=age
    ready=all(n==SPEC['lookback_hours'] for n in coverage[str(SPEC['lookback_hours'])].values()) and f['crop_age_days'] is not None
    return {'features':f,'coverage':coverage,'feature_status':'ready' if ready else 'insufficient_data',
            'context_revision':context['revision'] if context else None,
            'context_sha256':digest(context) if context else None}


def label_row(s,issued,label_cutoff):
    end=issued+timedelta(hours=SPEC['horizon_hours'])
    base={'y':None,'status':'censored','label_available_at':None,'onset_interval':None}
    if label_cutoff<end:return base
    latest={}
    for r in s['surveys']:
        if stamp(r['available_at'])<=label_cutoff and (r['visit_id'] not in latest or r['revision']>latest[r['visit_id']]['revision']):latest[r['visit_id']]=r
    visits=sorted(latest.values(),key=lambda r:stamp(r['observed_at']))
    confirmed=[r for r in visits if r['verification']=='confirmed']
    positives=[r for r in confirmed if r['finding']=='present']
    first=positives[0] if positives else None
    if first and stamp(first['observed_at'])<=issued:return dict(base,status='prevalent')
    negatives=[r for r in confirmed if r['finding']=='absent' and r['scheduled']]
    prior=[r for r in negatives if issued-timedelta(hours=SPEC['max_survey_gap_hours'])<=stamp(r['observed_at'])<=issued]
    if not prior:return dict(base,status='baseline_unknown')
    start=stamp(prior[-1]['observed_at'])
    if any(start<=stamp(r['observed_at'])<=end and r['verification']!='confirmed' for r in visits):return dict(base,status='unverified')
    # Exclude post-issue management from the first pure forecast analysis.
    if any(issued<stamp(r['at'])<=end and stamp(r['available_at'])<=label_cutoff for r in s['interventions']):return dict(base,status='intervened')
    if first:
        pos=stamp(first['observed_at'])
        before=[r for r in negatives if stamp(r['observed_at'])<pos]
        if not before:return dict(base,status='baseline_unknown')
        neg=stamp(before[-1]['observed_at'])
        interval={'last_confirmed_negative_at':neg.isoformat(),'first_confirmed_positive_at':pos.isoformat()}
        if neg>=issued and pos<=end:
            return dict(base,y=1,status='positive',onset_interval=interval,
                        label_available_at=max(end,stamp(prior[-1]['available_at']),stamp(first['available_at']),stamp(before[-1]['available_at'])).isoformat())
        if neg<end and pos>issued:return dict(base,status='ambiguous',onset_interval=interval)
    # Negative requires scheduled, confirmed follow-up covering the whole horizon.
    through=[r for r in negatives if stamp(r['observed_at'])>=start]
    tail=next((i for i,r in enumerate(through) if stamp(r['observed_at'])>=end),None)
    if tail is None:return base
    used=through[:tail+1]
    if any(stamp(b['observed_at'])-stamp(a['observed_at'])>timedelta(hours=SPEC['max_survey_gap_hours']) for a,b in zip(used,used[1:])):return dict(base,status='surveillance_gap')
    return dict(base,y=0,status='negative',label_available_at=max([end]+[stamp(r['available_at']) for r in used]).isoformat())


def build(payload):
    if not isinstance(payload,dict) or set(payload)!={'schema_version','source','series','issue_times','label_cutoff'} or payload['schema_version']!='aegis-temporal-input-v1':raise ValueError('Invalid temporal input envelope')
    if payload['source'] not in ['synthetic','field_observed']:raise ValueError('Declare source explicitly')
    if not isinstance(payload['series'],list) or not payload['series']:raise ValueError('Nonempty series list required')
    if not isinstance(payload['issue_times'],list) or not payload['issue_times']:raise ValueError('Nonempty issue times required')
    issued_times=[stamp(t) for t in payload['issue_times']]
    if len(set(issued_times))!=len(issued_times):raise ValueError('Duplicate issue time')
    cutoff=stamp(payload['label_cutoff'])
    if any(t>cutoff for t in issued_times):raise ValueError('Issue time after label cutoff')
    seen=set();rows=[]
    for s in payload['series']:
        validate_series(s)
        key=(s['plot_id'],s['season_id'])
        if key in seen:raise ValueError('One device series per plot-season; no silent sensor mixing')
        seen.add(key)
        for issued in sorted(issued_times):
            features=feature_row(s,issued);label=label_row(s,issued,cutoff)
            row={'plot_id':s['plot_id'],'season_id':s['season_id'],'device_id':s['device_id'],
                 'issued_at':issued.isoformat(),'feature_window_end':issued.replace(minute=0,second=0,microsecond=0).isoformat(),
                 'feature_window_start':(issued.replace(minute=0,second=0,microsecond=0)-timedelta(hours=SPEC['lookback_hours'])).isoformat(),
                 'target_window_end':(issued+timedelta(hours=SPEC['horizon_hours'])).isoformat(),**features,'label':label}
            row['structurally_eligible_field_row']=payload['source']=='field_observed' and features['feature_status']=='ready' and label['y'] is not None
            rows.append(row)
    return {'spec':SPEC,'spec_sha256':digest(SPEC),'input_sha256':digest(payload),'source':payload['source'],
            'rows':rows,'training_performed':False,'model_artifact':None,'model_metrics':None,
            'training_readiness':'blocked_no_field_data' if payload['source']=='synthetic' else 'requires_source_protocol_and_sample_review',
            'limits':['Not a disease forecast; no trained model','72h is a proposed target, not a demonstrated lead time','Synthetic data never prove field performance']}


def partition(rows,plan):
    """Explicit group/time split with purged context and matured labels; no fit."""
    if set(plan)!={'train_end','validation_start','validation_end','test_start','test_end','groups'}:raise ValueError('Invalid split plan')
    bounds={k:stamp(plan[k]) for k in plan if k!='groups'}
    if not bounds['train_end']<bounds['validation_start']<=bounds['validation_end']<bounds['test_start']<=bounds['test_end']:raise ValueError('Invalid chronological bounds')
    if bounds['validation_start']-bounds['train_end']<timedelta(hours=SPEC['lookback_hours']) or bounds['test_start']-bounds['validation_end']<timedelta(hours=SPEC['lookback_hours']):raise ValueError('Insufficient lookback purge')
    if set(plan['groups'])!={'train','validation','test'}:raise ValueError('Explicit train/validation/test groups required')
    owner={}
    for name,groups in plan['groups'].items():
        if not isinstance(groups,list):raise ValueError('Groups must be lists')
        for group in groups:
            if not isinstance(group,list) or len(group)!=2:raise ValueError('Group is [plot_id,season_id]')
            key=tuple(identifier(x) for x in group)
            if key in owner:raise ValueError('Plot-season group reused across splits')
            owner[key]=name
    selected={'train':[],'validation':[],'test':[]};rejected=[]
    for row in rows:
        name=owner.get((row['plot_id'],row['season_id']));t=stamp(row['issued_at']);available=row['label']['label_available_at']
        ok=row['structurally_eligible_field_row'] and name is not None and available is not None
        if ok:
            a=stamp(available)
            if name=='train':ok=t<=bounds['train_end'] and a<=bounds['train_end']
            elif name=='validation':ok=bounds['validation_start']<=t<=bounds['validation_end'] and a<=bounds['validation_end'] and stamp(row['feature_window_start'])>=bounds['train_end']
            else:ok=bounds['test_start']<=t<=bounds['test_end'] and a<=bounds['test_end'] and stamp(row['feature_window_start'])>=bounds['validation_end']
        (selected[name] if ok else rejected).append(row)
    return {'partitions':selected,'rejected':rejected,'plan_sha256':digest(plan),'training_performed':False}


def load(path):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k]=v
        return result
    def invalid(value):raise ValueError('Non-finite JSON constant')
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=invalid)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.input.resolve()==args.output.resolve():p.error('Refuse to overwrite input')
    if args.output.exists():p.error('Output exists; choose a new artifact path')
    try:result=build(load(args.input))
    except (ValueError,TypeError,KeyError,OverflowError) as exc:p.exit(2,'Invalid temporal input: '+str(exc)+'\n')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'rows':len(result['rows']),'training_readiness':result['training_readiness'],'training_performed':False}))


if __name__=='__main__':main()
