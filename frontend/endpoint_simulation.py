"""T15 declared observation scenarios, not a disease biology model."""
from datetime import datetime,timedelta,timezone
import random
from uuid import NAMESPACE_URL,uuid5

from synthetic_endpoints import PROTOCOL_SHA256,SCHEMA,validate
from telemetry_tool import digest

VERSION='aegis-t15-simulated-observations-v1'
ISSUE=datetime(2026,11,1,tzinfo=timezone.utc)
EXPORT=ISSUE+timedelta(hours=144)
SCENARIOS=('positive','negative','uncertain','missed_visit','late_review','prevalent',
           'ambiguous_issue','ambiguous_end','intervened','unverified','voided',
           'revision_correction','baseline_late','missing_baseline','late_intervention')


def seal(r):
    r.pop('payload_sha256',None); r['payload_sha256']=digest(r)
    return r


def make(seed,scenario):
    if type(seed) is not int or not 0<=seed<2**32 or scenario not in SCENARIOS:
        raise ValueError('uint32 seed and known scenario required')
    rng=random.Random(seed)
    def uid(name): return str(uuid5(NAMESPACE_URL,VERSION+':'+str(seed)+':'+scenario+':'+name))
    def at(h): return (ISSUE+timedelta(hours=h)).isoformat()
    def visit(h,finding='absent',reviewed=True,revision=1,available=None,status='active'):
        available=h+(rng.randint(1,5)/60) if available is None else available
        return seal(dict(id=uid('visit-'+str(h)),revision=revision,observed_at=at(h),recorded_at=at(available),
            available_at=at(available),scheduled=h in (0,24,48,72),finding=finding,record_status=status,
            review=dict(origin='simulator_attestation',reviewer_alias='VIRTUAL-SIMULATOR',reviewed_at=at(available),
                        reference=VERSION+':'+scenario) if reviewed and finding!='uncertain' else None,
            evidence_reference=VERSION+':virtual-observation-'+str(h)))
    visits=[visit(0,available=0),visit(24),visit(48),visit(72)]
    interventions=[]
    if scenario=='positive': visits[2]=visit(48,'present')
    elif scenario=='uncertain': visits[1]=visit(24,'uncertain',False)
    elif scenario=='missed_visit': visits.pop(1)
    elif scenario=='late_review': visits[2]=visit(48,'present',False); visits.append(visit(48,'present',revision=2,available=100))
    elif scenario=='prevalent': visits[0]=visit(0,'present',available=0)
    elif scenario=='ambiguous_issue': visits=[visit(-1,available=-1),visit(12,'present')]
    elif scenario=='ambiguous_end': visits=[visit(0,available=0),visit(24),visit(48),visit(84,'present')]
    elif scenario in ('intervened','late_intervention'):
        interventions=[dict(id=uid('intervention'),at=at(36),recorded_at=at(100 if scenario=='late_intervention' else 37),
            available_at=at(100 if scenario=='late_intervention' else 37),reference='Declared virtual management event; no treatment recommendation')]
    elif scenario=='unverified': visits[1]=visit(24,'absent',False)
    elif scenario=='voided': visits.append(visit(72,revision=2,available=100,status='voided'))
    elif scenario=='revision_correction':
        visits[1]=visit(24,'present'); visits.append(visit(24,revision=2,available=100))
    elif scenario=='baseline_late': visits[0]=visit(0,available=1)
    elif scenario=='missing_baseline': visits.pop(0)
    b=dict(schema_version=SCHEMA,source='synthetic',evidence_origin='software_simulation',protocol_sha256=PROTOCOL_SHA256,
        owner_id=uid('owner'),unit_id=uid('unit'),season_id=uid('season'),
        groups=dict(site_alias='VIRTUAL-SITE',logger_alias='VIRTUAL-LOGGER-'+str(seed),
                    shared_environment_alias='VIRTUAL-SHARED-ENVIRONMENT',batch_alias='VIRTUAL-BATCH-'+str(seed)),
        simulation=dict(generator_version=VERSION,seed=seed,scenario=scenario,
                        clock_basis='all_observation_review_record_and_export_times_simulated'),
        exported_at=EXPORT.isoformat(),visits=visits,interventions=interventions)
    b['bundle_sha256']=digest(b)
    return b


def journal_commands(b):
    """Initial revisions only. Explicitly do not promote attestation into user review."""
    validate(b)
    return [dict(client_visit_id=r['id'],source='synthetic',observed_at=r['observed_at'],scheduled=r['scheduled'],
                 finding=r['finding'],notes='Virtual T15 observation: '+r['evidence_reference'],analysis_id=None,
                 review=None,record_status=r['record_status'],change_reason='T15 software simulation')
            for r in b['visits'] if r['revision']==1]
