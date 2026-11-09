"""T15 offline simulated endpoint rules, independent of operational T13 outcomes."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID

from forecast_intake import encoded, exact, read_json_bytes, text
from telemetry_audit import stamp
from telemetry_tool import digest

PROTOCOL_PATH = Path(__file__).resolve().parents[1]/'docs/forecast_data/SYNTHETIC_ENDPOINT_PROTOCOL_T15.json'
PROTOCOL = read_json_bytes(PROTOCOL_PATH.read_bytes())
PROTOCOL_SHA256 = digest(PROTOCOL)
if PROTOCOL_SHA256 != '07f5ae4b14ee7c724ac0a7851e1721b79cdede80876b546d44f7e1e2c937201a':
    raise ValueError('T15 protocol pin changed; publish a new version explicitly')
SCHEMA = 'aegis-synthetic-endpoint-observations-v1'


def identifier(v):
    if not isinstance(v, str) or str(UUID(v)) != v: raise ValueError('Canonical UUID required')


def validate(b):
    exact(b, ('schema_version','source','evidence_origin','protocol_sha256','owner_id','unit_id','season_id',
              'groups','simulation','exported_at','visits','interventions','bundle_sha256'))
    unsigned = dict(b); pin = unsigned.pop('bundle_sha256')
    if (digest(unsigned) != pin or b['schema_version'] != SCHEMA or b['source'] != 'synthetic'
            or b['evidence_origin'] != 'software_simulation' or b['protocol_sha256'] != PROTOCOL_SHA256):
        raise ValueError('Synthetic observation schema, hash or protocol mismatch')
    for key in ('owner_id','unit_id','season_id'): identifier(b[key])
    exact(b['groups'], ('site_alias','logger_alias','shared_environment_alias','batch_alias'))
    for v in b['groups'].values(): text(v)
    exact(b['simulation'], ('generator_version','seed','scenario','clock_basis'))
    for k in ('generator_version','scenario'): text(b['simulation'][k])
    if type(b['simulation']['seed']) is not int or not 0 <= b['simulation']['seed'] < 2**32:
        raise ValueError('Simulation seed must be uint32')
    if b['simulation']['clock_basis'] != 'all_observation_review_record_and_export_times_simulated':
        raise ValueError('Explicit simulated time basis required')
    exported = stamp(b['exported_at'])
    if not isinstance(b['visits'],list) or len(b['visits']) > 10000:
        raise ValueError('Bounded observation history required')
    history = {}; observed_ids = {}
    for r in b['visits']:
        exact(r, ('id','revision','observed_at','recorded_at','available_at','scheduled','finding',
                  'record_status','review','evidence_reference','payload_sha256'))
        identifier(r['id']); text(r['evidence_reference'])
        if (type(r['revision']) is not int or r['revision'] < 1 or type(r['scheduled']) is not bool
                or r['finding'] not in ('absent','present','uncertain') or r['record_status'] not in ('active','voided')):
            raise ValueError('Invalid observation revision/finding/status')
        raw = dict(r); p = raw.pop('payload_sha256')
        if digest(raw) != p: raise ValueError('Observation payload hash mismatch')
        observed, recorded, available = (stamp(r[k]) for k in ('observed_at','recorded_at','available_at'))
        if not observed <= recorded <= available <= exported:
            raise ValueError('Observation/record/availability ordering invalid')
        if observed in observed_ids and observed_ids[observed] != r['id']:
            raise ValueError('Distinct visits at same observation timestamp are ambiguous')
        observed_ids[observed] = r['id']
        review = r['review']
        if review is not None:
            exact(review, ('origin','reviewer_alias','reviewed_at','reference'))
            if review['origin'] != 'simulator_attestation' or r['finding']=='uncertain':
                raise ValueError('Only explicit simulator attestations can be decisive here')
            text(review['reviewer_alias']); text(review['reference'])
            if not observed <= stamp(review['reviewed_at']) <= available:
                raise ValueError('Review time ordering invalid')
        history.setdefault(r['id'], []).append(r)
    for rows in history.values():
        rows.sort(key=lambda r:r['revision'])
        if [r['revision'] for r in rows] != list(range(1,len(rows)+1)):
            raise ValueError('Full consecutive revision history required')
        if len({(stamp(r['observed_at']),r['scheduled']) for r in rows}) != 1:
            raise ValueError('Observation time and scheduled flag are immutable')
        if any(stamp(x[k]) > stamp(y[k]) for x,y in zip(rows,rows[1:]) for k in ('recorded_at','available_at')):
            raise ValueError('Revision knowledge times must be monotonic')
    if not isinstance(b['interventions'],list) or len(b['interventions']) > 10000:
        raise ValueError('Bounded intervention declarations required')
    ids=set()
    for r in b['interventions']:
        exact(r, ('id','at','recorded_at','available_at','reference'))
        identifier(r['id']); text(r['reference'])
        if r['id'] in ids: raise ValueError('Duplicate intervention')
        ids.add(r['id'])
        if not stamp(r['at']) <= stamp(r['recorded_at']) <= stamp(r['available_at']) <= exported:
            raise ValueError('Intervention knowledge ordering invalid')


def evaluate(b, issued_at, as_of):
    validate(b)
    issue,cut = stamp(issued_at),stamp(as_of)
    if cut > stamp(b['exported_at']): raise ValueError('as_of exceeds observation snapshot export')
    end=issue+timedelta(hours=PROTOCOL['horizon_hours'])
    latest={}
    for r in b['visits']:
        if stamp(r['available_at']) <= cut and (r['id'] not in latest or r['revision'] > latest[r['id']]['revision']):
            latest[r['id']]=r
    selected=sorted(latest.values(),key=lambda r:(stamp(r['observed_at']),r['id']))
    active=[r for r in selected if r['record_status']=='active']
    interventions=sorted([r for r in b['interventions'] if stamp(r['available_at']) <= cut
                          and issue < stamp(r['at']) <= end],key=lambda r:r['id'])
    valid=[r for r in active if r['review'] is not None]
    positives=[r for r in valid if r['finding']=='present']
    first=positives[0] if positives else None
    before=[r for r in valid if r['finding']=='absent' and stamp(r['observed_at']) <= issue
            and issue-timedelta(hours=PROTOCOL['baseline_window_hours']) <= stamp(r['observed_at'])]
    baseline=before[-1] if before else None
    baseline_known=bool(baseline and stamp(baseline['available_at']) <= issue)
    interval=None
    if first:
        lower=[r for r in valid if r['finding']=='absent' and stamp(r['observed_at']) < stamp(first['observed_at'])]
        if lower:
            lower=lower[-1]
            interval=dict(lower_open=lower['observed_at'],upper_closed=first['observed_at'],
                absent_visit_id=lower['id'],present_visit_id=first['id'],
                crosses_issue=stamp(lower['observed_at']) < issue < stamp(first['observed_at']),
                crosses_target_end=stamp(lower['observed_at']) < end < stamp(first['observed_at']))
    relevant_end=min(end,stamp(first['observed_at'])) if first and stamp(first['observed_at'])>issue else end
    relevant=[r for r in active if issue-timedelta(hours=24) <= stamp(r['observed_at']) <= relevant_end]
    invalid_uncertain=any(r['finding']=='uncertain' for r in relevant)
    unreviewed=any(r['review'] is None and r['finding']!='uncertain' for r in relevant)
    planned=[issue+timedelta(hours=h) for h in PROTOCOL['planned_followup_hours']]
    required=[t for t in planned if t <= relevant_end]
    completed={stamp(r['observed_at']) for r in valid if r['scheduled']}
    missing=[t.isoformat() for t in required if t not in completed]
    chain=sorted({stamp(r['observed_at']) for r in valid if baseline
                  and stamp(baseline['observed_at']) <= stamp(r['observed_at']) <= relevant_end})
    max_gap=max(((y-x).total_seconds()/3600 for x,y in zip(chain,chain[1:])),default=None)
    status='censored'; reasons=[]; y=None
    if cut < issue: status='not_yet_issued'; reasons=['issue_after_cutoff']
    elif first and stamp(first['observed_at']) <= issue: status='prevalent'; reasons=['first_attested_present_before_or_at_issue']
    elif cut < end: status='following_up'; reasons=['target_window_not_mature']
    elif interventions: status='intervened'; reasons=['known_intervention_in_target_window']
    elif invalid_uncertain: status='uncertain'; reasons=['uncertain_observation_in_required_history']
    elif unreviewed: status='unverified'; reasons=['missing_simulator_attestation']
    elif baseline is None: reasons=['no_attested_absent_baseline_within_24h']
    elif not baseline_known: status='baseline_unavailable_at_issue'; reasons=['baseline_reported_retrospectively']
    elif first and interval and (interval['crosses_issue'] or interval['crosses_target_end']):
        status='ambiguous'; reasons=['event_interval_crosses_target_boundary']
    elif missing: reasons=['missing_required_scheduled_visits']
    elif max_gap is not None and max_gap > PROTOCOL['max_survey_gap_hours']:
        reasons=['survey_gap_exceeds_protocol']
    elif first and issue < stamp(first['observed_at']) <= end:
        if interval and issue <= stamp(interval['lower_open']): status='positive'; y=1
        else: status='ambiguous'; reasons=['no_interval_fully_inside_target_window']
    else:
        # Every planned visit through the horizon must explicitly attest absent.
        negatives={stamp(r['observed_at']) for r in valid if r['scheduled'] and r['finding']=='absent'}
        if all(t in negatives for t in planned): status='negative'; y=0
        else: reasons=['insufficient_absent_surveillance_through_horizon']
    decisive=[r for r in selected if issue-timedelta(hours=24) <= stamp(r['observed_at']) <= relevant_end]
    availability=max([end]+[stamp(r['available_at']) for r in decisive]) if y is not None else None
    knowledge=dict(visits=selected,interventions=interventions)
    return dict(schema_version='aegis-synthetic-endpoint-result-v1',source='synthetic',
        evidence_origin='software_simulation',protocol_id=PROTOCOL['protocol_id'],protocol_sha256=PROTOCOL_SHA256,
        input_bundle_sha256=b['bundle_sha256'],owner_id=b['owner_id'],unit_id=b['unit_id'],season_id=b['season_id'],
        groups=b['groups'],issued_at=issue.isoformat(),target_window_end=end.isoformat(),as_of=cut.isoformat(),
        status=status,reasons=reasons,synthetic_y=y,synthetic_endpoint_available_at=availability.isoformat() if availability else None,
        observed_event_interval=interval,baseline_known_at_issue=baseline_known,
        baseline_visit_id=baseline['id'] if baseline else None,missing_required_visit_times=missing,
        maximum_observed_survey_gap_hours=max_gap,selected_revisions=selected,
        voided_visit_ids=[r['id'] for r in selected if r['record_status']=='voided'],
        known_interventions=interventions,knowledge_sha256=digest(knowledge),
        target='first_simulator_attested_leaf_symptom_event_interval',
        event_y=None,label_approved_for_training=False,platform_verified=False,field_validated=False,
        training_approved=False,latent_generator_truth_used=False,
        limits=['Synthetic endpoint only; no disease verification or field performance evidence',
                'Interval is between observations, not infection time or exact onset',
                '72h/24h and scheduled visit rules are simulation design choices',
                'T13 operational outcomes and journal external-review declarations are unchanged'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations',type=Path,required=True); p.add_argument('--issued-at',required=True)
    p.add_argument('--as-of',required=True); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    try:
        result=evaluate(read_json_bytes(args.observations.read_bytes()),args.issued_at,args.as_of)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('xb') as f: f.write(encoded(result))
        print(json.dumps(dict(status=result['status'],synthetic_y=result['synthetic_y'],source='synthetic',training_approved=False)))
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError):
        p.exit(2,'Synthetic endpoint blocked: invalid observations/cutoff or existing output.\n')


if __name__=='__main__': main()
