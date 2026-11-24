"""T16 join/split fixtures. Weather is independent of scenario-assigned outcomes."""
import copy
from datetime import datetime,timedelta,timezone
import math
import random
from uuid import NAMESPACE_URL,uuid5

from endpoint_simulation import make as observations,ISSUE as OLD_ISSUE
from intake_simulation import make as raw_template
from synthetic_dataset import SCHEMA,PROTOCOL_SHA256,SPLITS
from telemetry_audit import stamp
from telemetry_tool import digest

VERSION='aegis-t16-join-split-fixture-v1'
START=datetime(2026,9,1,tzinfo=timezone.utc)


def seal(b):
    b.pop('bundle_sha256',None); b['bundle_sha256']=digest(b)
    return b


def repin(e):
    seal(e['raw']); seal(e['observations'])
    e['mapping'].update(raw_bundle_sha256=e['raw']['bundle_sha256'],
        observation_bundle_sha256=e['observations']['bundle_sha256'],
        context_sha256=digest(e['context_revisions']),hourly_policy_sha256=digest(e['hourly_policy']))


def make(seeds=(20261108,20261109,20261110),shared_environment=False):
    entries=[]; assignments={}; periods={}
    for si,split in enumerate(SPLITS):
        base=START+timedelta(days=si*11); issue=base+timedelta(seconds=65)
        periods[split]=dict(start_at=base.isoformat(),end_at=(base+timedelta(days=1)).isoformat(),
                            label_cutoff=(issue+timedelta(hours=120)).isoformat())
        for seed in seeds:
            for label in ('negative','positive'):
                key=str(seed)+':'+split+':'+label
                def uid(s): return str(uuid5(NAMESPACE_URL,VERSION+':'+key+':'+s))
                owner=uid('owner'); season=uid('season'); unit=uid('unit'); stream=uid('stream')
                _,raw=raw_template(seed,'clean'); raw=copy.deepcopy(raw)
                start=base-timedelta(hours=120)
                raw.update(owner_id=owner,season_id=season,stream_id=stream,
                    exported_at=(issue+timedelta(hours=144)).isoformat(),
                    stream_created_at=(start-timedelta(hours=1)).isoformat())
                raw['metadata']['reference']=VERSION; raw['metadata_sha256']=digest(raw['metadata'])
                template=raw['readings'][0]; rows=[]
                # Same environmental waveform for the paired outcome fixtures.
                rng=random.Random(seed+si*100)
                for n in range(720):
                    at=start+timedelta(minutes=10*n); r=copy.deepcopy(template)
                    r.update(id=uid('point-'+str(n)),stream_id=stream,observed_at=at.isoformat(),
                        received_at=(at+timedelta(seconds=2)).isoformat(),available_at=(at+timedelta(seconds=2)).isoformat(),
                        request_id=uid('receipt-'+str(n)))
                    r['payload'].update(air_temperature_c=26+2*math.sin(n/144*2*math.pi)+rng.uniform(-.2,.2),
                        relative_humidity_pct=78+8*math.cos(n/144*2*math.pi),leaf_wet=None,reference=VERSION)
                    r['payload_sha256']=digest(r['payload']); rows.append(r)
                raw['readings']=rows; seal(raw)
                obs=copy.deepcopy(observations(seed,label)); shift=issue-OLD_ISSUE
                obs.update(owner_id=owner,season_id=season,unit_id=unit,exported_at=(issue+timedelta(hours=144)).isoformat())
                groups=dict(site_alias='VIRTUAL-SITE-'+key,logger_alias='VIRTUAL-LOGGER-'+key,
                    shared_environment_alias='VIRTUAL-SHARED-ENVIRONMENT' if shared_environment else 'VIRTUAL-ENV-'+split+'-'+str(seed),
                    batch_alias='VIRTUAL-BATCH-'+key)
                obs['groups']=groups
                for v in obs['visits']:
                    v['id']=uid(v['id'])
                    for k in ('observed_at','recorded_at','available_at'): v[k]=(stamp(v[k])+shift).isoformat()
                    if v['review']: v['review']['reviewed_at']=(stamp(v['review']['reviewed_at'])+shift).isoformat()
                    v.pop('payload_sha256'); v['payload_sha256']=digest(v)
                seal(obs)
                policy=dict(schema_version='aegis-raw-hourly-policy-v1',algorithm_version='aegis-slot-hourly-v1',
                    policy_id=VERSION,revision=1,source='synthetic',stream_id=stream,
                    available_at=raw['stream_created_at'],anchor_at=start.isoformat(),interval_seconds=600,
                    tolerance_seconds=5,arrival_grace_seconds=60,minimum_coverage_numerator=4,
                    minimum_coverage_denominator=5,numeric_method='slot_arithmetic_mean',wetness_method='point_diagnostics_only')
                profile=dict(schema_version='aegis-cultivation-v1',source='user_declared',timezone='UTC+07:00',
                    region='central',province_or_city='VIRTUAL',locality=None,rice_variety='VIRTUAL',
                    planting_method='direct_seeded',sown_on='2026-08-01',transplanted_on=None,season_status='active')
                context=[dict(revision=1,recorded_at=raw['stream_created_at'],available_at=raw['stream_created_at'],profile=profile)]
                e=dict(id=uid('mapping'),raw=raw,observations=obs,context_revisions=context,hourly_policy=policy,
                    issue_times=[issue.isoformat()],mapping=dict(owner_id=owner,season_id=season,unit_id=unit,stream_id=stream,
                        groups=copy.deepcopy(groups),relationship_available_at=raw['stream_created_at'],
                        snapshot_linked_at='2026-10-01T00:00:00+00:00',linkage_reference=VERSION+':explicit-'+key,
                        use_rights_status='project_generated_simulation',use_rights_reference='Project-generated virtual fixture; no third-party intake',
                        raw_bundle_sha256=raw['bundle_sha256'],observation_bundle_sha256=obs['bundle_sha256'],
                        context_sha256=digest(context),hourly_policy_sha256=digest(policy)))
                entries.append(e); assignments[e['id']]=split
    b=dict(schema_version=SCHEMA,source='synthetic',dataset_id=VERSION,protocol_sha256=PROTOCOL_SHA256,entries=entries,
        split_plan=dict(schema_version='aegis-synthetic-group-time-split-v1',plan_id=VERSION,
            available_at=(START-timedelta(days=10)).isoformat(),purpose='engineering_audit_not_blind_model_selection',
            assignments=assignments,periods=periods,data_lock_at='2026-10-01T00:00:00+00:00',embargo_hours=24))
    return seal(b)
