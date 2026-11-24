"""Predeclared virtual weather/future-hazard cohort; never uses a model score."""
import copy
from datetime import datetime,timedelta,timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from uuid import NAMESPACE_URL,uuid5

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'frontend'))
from dataset_simulation import make as template_dataset,repin,seal
from synthetic_dataset import build,dependency_components
from telemetry_tool import digest

PLAN_PATH=ROOT/'docs/forecast_data/EXPERIMENT_PLAN_T17.json'
PLAN_BYTES_SHA256='82553d3243cefded1346cc2b0e8d19cda4e1d87d35a110a848086f33d14581c0'
if hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()!=PLAN_BYTES_SHA256:
    raise ValueError('T17 plan changed; start a new experiment version')
PLAN=json.loads(PLAN_PATH.read_text(encoding='utf-8'))
VERSION=PLAN['generator_version']


def rng(seed,role,group,member,part):
    return random.Random(int(digest([VERSION,seed,role,group,member,part])[:16],16))


@lru_cache(maxsize=1)
def template(): return template_dataset(seeds=(20261108,))['entries'][0]


def generate_entry(seed,role,group,member):
    if type(seed) is not int or seed not in PLAN['seeds'] or role not in PLAN['groups']:
        raise ValueError('Frozen seed and split role required')
    if type(group) is not int or not 0<=group<PLAN['groups'][role] or type(member) is not int or not 0<=member<2:
        raise ValueError('Bounded group/member required')
    key=f'{seed}:{role}:{group}:{member}'
    def uid(x): return str(uuid5(NAMESPACE_URL,VERSION+':'+key+':'+str(x)))
    date=datetime.fromisoformat(PLAN['split_issue_dates'][role]).replace(tzinfo=timezone.utc)
    issue=date+timedelta(seconds=65); start=date-timedelta(hours=120); export=issue+timedelta(hours=144)
    parameters=rng(seed,role,group,-1,'parameters'); weather_rng=rng(seed,role,group,-1,'weather')
    temp_mean=parameters.uniform(*PLAN['generator']['temperature_mean_range'])
    rh_mean=parameters.uniform(*PLAN['generator']['humidity_mean_range'])
    phase=parameters.uniform(0,2*math.pi); group_frailty=parameters.gauss(0,PLAN['generator']['group_frailty_std'])
    temperatures=[]; humidities=[]; tr=rr=0
    for h in range(192):
        tr=.96*tr+weather_rng.gauss(0,.25); rr=.96*rr+weather_rng.gauss(0,.8)
        temperatures.append(max(0,min(45,temp_mean+2*math.sin(h/24*2*math.pi+phase)+tr)))
        humidities.append(max(20,min(100,rh_mean+3*math.cos(h/24*2*math.pi+phase)+rr)))
    age=rng(seed,role,group,member,'age').randint(20,65)
    hrng=rng(seed,role,group,member,'hazard'); susceptibility=hrng.gauss(0,PLAN['generator']['unit_susceptibility_std'])
    target=-math.log1p(-hrng.random()); cumulative=0; latent=None
    for h in range(72):
        suit=math.exp(-((temperatures[120+h]-27)**2)/20)/(1+math.exp(-(humidities[120+h]-83)/5))
        cumulative+=math.exp(PLAN['generator']['hourly_log_hazard_intercept']+
            PLAN['generator']['weather_log_hazard_coefficient']*suit+.4*(age-35)/25+group_frailty+susceptibility)
        if latent is None and cumulative>=target: latent=h+1
    e=copy.deepcopy(template()); owner,season,unit,stream=(uid(x) for x in ('owner','season','unit','stream'))
    e['id']=uid('mapping'); e['issue_times']=[issue.isoformat()]
    raw=e['raw']; raw.update(owner_id=owner,season_id=season,stream_id=stream,
        exported_at=export.isoformat(),stream_created_at=(start-timedelta(hours=1)).isoformat())
    raw['metadata'].update(name='T17 VIRTUAL WEATHER',reference=VERSION); raw['metadata_sha256']=digest(raw['metadata'])
    point_rng=rng(seed,role,group,member,'point-noise'); missing_rng=rng(seed,role,group,member,'missingness')
    missing_draw=missing_rng.random(); missing_hour=missing_rng.randrange(120)
    rows=[]
    for n,row in enumerate(raw['readings']):
        if missing_draw<.12 and n//6==missing_hour and n%6<4: continue
        at=start+timedelta(minutes=n*10)
        row.update(id=uid('raw-'+str(n)),stream_id=stream,observed_at=at.isoformat(),
            received_at=(at+timedelta(seconds=2)).isoformat(),available_at=(at+timedelta(seconds=2)).isoformat(),
            request_id=uid('receipt-'+str(n)))
        row['payload'].update(air_temperature_c=temperatures[n//6]+point_rng.uniform(-.1,.1),
            relative_humidity_pct=max(0,min(100,humidities[n//6]+point_rng.uniform(-.1,.1))),reference=VERSION)
        row['payload_sha256']=digest(row['payload']); rows.append(row)
    raw['readings']=rows
    groups={k:f'VIRTUAL:{seed}:{role}:{group}:{k}' for k in ('site_alias','logger_alias','shared_environment_alias','batch_alias')}
    obs=e['observations']; obs.update(owner_id=owner,season_id=season,unit_id=unit,groups=copy.deepcopy(groups),exported_at=export.isoformat())
    obs['simulation'].update(generator_version=VERSION,seed=seed,scenario='stochastic_future_hazard')
    observation_rng=rng(seed,role,group,member,'ascertainment'); ascertainment=observation_rng.random()
    visits=[]
    for index,v in enumerate(obs['visits']):
        hours=index*24; at=issue+timedelta(hours=hours); available=at if index==0 else at+timedelta(minutes=1)
        if ascertainment<.04 and index==3: continue
        finding='present' if latent is not None and latent<=hours else 'absent'
        if .04<=ascertainment<.08 and index==1: finding='uncertain'
        reviewed=not (.08<=ascertainment<.12 and index==1) and finding!='uncertain'
        v.update(id=uid('visit-'+str(index)),observed_at=at.isoformat(),recorded_at=available.isoformat(),
            available_at=available.isoformat(),finding=finding,evidence_reference=VERSION+':virtual-observation')
        v['review']=dict(origin='simulator_attestation',reviewer_alias='VIRTUAL-SIMULATOR',
            reviewed_at=available.isoformat(),reference=VERSION) if reviewed else None
        v.pop('payload_sha256'); v['payload_sha256']=digest(v); visits.append(v)
    obs['visits']=visits
    ctx=e['context_revisions'][0]; ctx['recorded_at']=ctx['available_at']=raw['stream_created_at']
    ctx['profile']['sown_on']=(date-timedelta(days=age)).date().isoformat()
    if .12<=missing_draw<.16: ctx['profile'].update(planting_method='unknown',sown_on=None)
    policy=e['hourly_policy']; policy.update(stream_id=stream,anchor_at=start.isoformat(),available_at=raw['stream_created_at'],policy_id=VERSION)
    e['mapping'].update(owner_id=owner,season_id=season,unit_id=unit,stream_id=stream,groups=copy.deepcopy(groups),
        relationship_available_at=raw['stream_created_at'],snapshot_linked_at='2026-08-20T00:00:00+00:00',
        linkage_reference=VERSION+':'+key)
    repin(e)
    world=dict(source='synthetic',future_temperature=temperatures[120:],future_humidity=humidities[120:],
        group_frailty=group_frailty,hidden_susceptibility=susceptibility,latent_event_hour=latent,
        used_as_predictors=False,used_directly_as_endpoint_label=False)
    return e,world


def chunk_input(entries,role):
    # Four experiment roles map to T16's train/validation/test schema per chunk.
    b=template_dataset(seeds=(20261108,)); b['entries']=entries
    b['dataset_id']=VERSION+':'+role
    mapped='train' if role=='train' else 'test' if role=='test' else 'validation'
    p=b['split_plan']; p['assignments']={e['id']:mapped for e in entries}
    dates={'train':'2026-07-01','validation':PLAN['split_issue_dates'][role] if role in ('calibration','selection') else '2026-07-23','test':'2026-08-03'}
    for split,day in dates.items():
        date=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        p['periods'][split]=dict(start_at=date.isoformat(),end_at=(date+timedelta(days=1)).isoformat(),
            label_cutoff=(date+timedelta(seconds=65,hours=120)).isoformat())
    p.update(available_at='2026-06-01T00:00:00+00:00',data_lock_at='2026-08-20T00:00:00+00:00')
    return seal(b)


def generate_role(seed,role,example_callback=None):
    rows=[]; light=[]; worlds=[]; entries=[]; chunk_hashes=[]
    def flush():
        if not entries: return
        dataset=chunk_input(entries,role); report=build(dataset)
        if report['dependency_conflicts']: raise ValueError('Chunk grouping conflict')
        chunk_hashes.append(dict(input_sha256=dataset['bundle_sha256'],report_sha256=report['report_sha256']))
        for row in report['rows']:
            row['experiment_role']=role; row['replicate_seed']=seed
            rows.append(row)
        entries.clear()
    for group in range(PLAN['groups'][role]):
        for member in range(2):
            e,world=generate_entry(seed,role,group,member)
            if example_callback and group==0 and member==0: example_callback(e,world)
            worlds.append(digest(world))
            light.append(dict(id=e['id'],mapping=e['mapping'],raw=dict(readings=[dict(id=x['id']) for x in e['raw']['readings']]),
                              observations=dict(visits=[dict(id=x['id']) for x in e['observations']['visits']])))
            entries.append(e)
        if len(entries)>=40: flush()
    flush()
    components=dependency_components(light)
    member_component={m:c for c,ms in components.items() for m in ms}
    for row in rows: row['component_id']=member_component[row['mapping_id']]
    return dict(rows=rows,light_entries=light,chunk_hashes=chunk_hashes,world_hashes=worlds)
