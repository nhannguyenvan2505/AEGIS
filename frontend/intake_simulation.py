"""Seeded virtual source generator for T14; no disease/outcome simulation."""
import copy
from datetime import datetime, timedelta, timezone
import math
import random
from uuid import NAMESPACE_URL, uuid5

from forecast_intake import SCHEMA
from telemetry_monitor import POLICY_SCHEMA
from telemetry_tool import digest

VERSION = 'aegis-t14-virtual-source-v1'
SCENARIOS = ('clean', 'dropout', 'delayed_receipt', 'clock_qc')
START = datetime(2026, 11, 6, tzinfo=timezone.utc)
END = START+timedelta(days=1)
EXPORTED = END+timedelta(hours=2)


def make(seed, scenario):
    if type(seed) is not int or not 0 <= seed < 2**32 or scenario not in SCENARIOS:
        raise ValueError('Known scenario and uint32 seed required')
    rng = random.Random(seed)
    def uid(name): return str(uuid5(NAMESPACE_URL, VERSION+':'+str(seed)+':'+scenario+':'+name))
    def iso(t): return t.isoformat()
    metadata = dict(name='VIRTUAL-T14-'+scenario, source='synthetic', method='sensor_reading',
        instrument='SOFTWARE GENERATOR; NO PHYSICAL SENSOR', reference=VERSION,
        nominal_interval_seconds=600, measurement_semantics='point_observation',
        units=dict(air_temperature_c='degC', relative_humidity_pct='percent', leaf_wet='boolean_point_state'),
        provenance='user_declared', calibration_verified=False)
    b = dict(schema_version='aegis-raw-telemetry-export-v1', exported_at=iso(EXPORTED),
        owner_id=uid('owner'), season_id=uid('season'), stream_id=uid('stream'), metadata=metadata,
        metadata_sha256=digest(metadata), stream_created_at=iso(START-timedelta(hours=1)),
        readings=[], training_approved=False, hourly_aggregation_performed=False,
        limits=['Virtual source; simulated observation, receipt, exclusion and export clocks'])
    for n in range(144):
        noise = rng.uniform(-.4, .4)
        if scenario == 'dropout' and (36 <= n < 54 or rng.random() < .04): continue
        at = START+timedelta(seconds=n*600)
        if scenario == 'clock_qc' and n >= 72: at += timedelta(seconds=30)
        received = at+timedelta(seconds=3600 if scenario == 'delayed_receipt' else 2)
        payload = dict(air_temperature_c=26+2*math.sin(n/144*2*math.pi)+noise,
                       relative_humidity_pct=78+10*math.cos(n/144*2*math.pi)+noise,
                       leaf_wet=None, reported_quality='unknown', reference=VERSION+':virtual-point-'+str(n))
        if scenario == 'clock_qc':
            if n % 17 == 0: payload['relative_humidity_pct'] = None
            if n % 13 == 0: payload['reported_quality'] = 'suspect'
        missing = [k for k in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet') if payload[k] is None]
        excluded = scenario == 'clock_qc' and n % 19 == 0
        b['readings'].append(dict(id=uid('point-'+str(n)), stream_id=b['stream_id'],
            observed_at=iso(at), received_at=iso(received), available_at=iso(received),
            request_id=uid('receipt-'+str(n)), payload=payload, payload_sha256=digest(payload),
            excluded_at=iso(END+timedelta(seconds=60)) if excluded else None,
            exclusion_reason='Simulated QC exclusion' if excluded else None,
            exclusion_request_id=uid('exclusion-'+str(n)) if excluded else None,
            qc=dict(version='aegis-raw-qc-v1', missing_fields=missing,
                reported_suspect=payload['reported_quality']=='suspect', status='incomplete',
                calibration_verified=False, hourly_eligible=False)))
    b['bundle_sha256'] = digest(b)
    d = dict(schema_version=SCHEMA, source_id='VIRTUAL-'+str(seed)+'-'+scenario, source_kind='synthetic',
        evidence_origin='software_simulation', site_alias='VIRTUAL-SITE', unit_alias='VIRTUAL-UNIT-'+str(seed),
        season_alias='VIRTUAL-SEASON', logger_alias='VIRTUAL-LOGGER-'+str(seed),
        shared_environment_alias='VIRTUAL-SHARED-ENVIRONMENT', collection_batch_alias='VIRTUAL-BATCH-'+str(seed),
        provider_reference='Team software simulation, no hardware/provider intake',
        use_rights_reference='Project-generated virtual fixture; not a real-source permission',
        linkage={k: b[k] for k in ('owner_id', 'season_id', 'stream_id', 'bundle_sha256')},
        sensor=dict(instrument_reference=metadata['instrument'], units=copy.deepcopy(metadata['units']),
                    measurement_semantics='point_observation', calibration_verified=False),
        simulation=dict(generator_version=VERSION, seed=seed, scenario=scenario,
            generated_at=iso(EXPORTED), time_basis='simulated_observation_receipt_and_log_clocks'),
        schedule=dict(schema_version=POLICY_SCHEMA, stream_id=b['stream_id'], available_at=b['stream_created_at'],
            anchor_at=iso(START), interval_seconds=600, tolerance_seconds=5, arrival_grace_seconds=60,
            stale_after_seconds=1800, receipt_silence_after_seconds=1800),
        clock_logs=[dict(device_at=iso(START+timedelta(hours=12, seconds=30 if scenario=='clock_qc' else 0)),
                         reference_at=iso(START+timedelta(hours=12)), recorded_at=iso(START+timedelta(hours=12, minutes=1)),
                         reference='Simulated device/reference comparison; not a physical clock check')],
        missingness_logs=[], forecast_training_eligibility='not_assessed', field_validated=False)
    if scenario == 'dropout':
        d['missingness_logs'] = [dict(start_at=iso(START+timedelta(hours=6)), end_at=iso(START+timedelta(hours=9)),
            recorded_at=iso(END+timedelta(minutes=1)), reason='Injected virtual outage; other random losses lack a cause log',
            reference='Generator configuration; not a measured network incident')]
    return d, b
