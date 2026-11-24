"""Deterministic synthetic raw-pipeline acceptance; no sensor, broker or model.

Uses Flask test-client transport and real SQLite in a disposable pilot store.
Only a redacted summary and explicitly synthetic raw snapshots leave that store.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
from unittest.mock import patch
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'frontend'))
from pilot_app import create_pilot_app
from telemetry_tool import export
from telemetry_audit import audit

BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)
END = BASE + timedelta(hours=1)
NAMESPACE = UUID('825037e8-8359-42b4-9902-a938c7d426b0')


def generated(node, seed=42):
    """Twelve five-minute slots; stable keys survive retransmission.

    node is a simulator alias, NOT an authenticated device ID in the raw API.
    Changes to seed change values but keep keys, intentionally causing conflicts
    if a different simulation is retried into the same existing stream.
    """
    rng = random.Random(f'{seed}:{node}')
    rows = []
    for i in range(12):
        rows.append(dict(
            client_sample_id=str(uuid5(NAMESPACE, f'{node}:{i}')),
            observed_at=(BASE + timedelta(minutes=5*i)).isoformat(),
            air_temperature_c=26.0 if i < 6 else 40.0 if i == 6 else round(27+rng.random(), 3),
            relative_humidity_pct=None if i == 8 else 90.0,
            leaf_wet=None if i == 8 else True,
            reported_quality='suspect' if i == 8 else 'unknown',
            reference=f'SYNTHETIC seed={seed} node={node} slot={i}; no hardware',
        ))
    return rows


def run(out):
    checks = []

    def check(name, condition):
        if not condition:
            raise RuntimeError('Acceptance failed: ' + name)
        checks.append(name)

    def status(response, expected, name):
        check(name, response.status_code == expected)
        return response.get_json()

    check('generator_reproducible', generated('sim-a') == generated('sim-a'))
    check('node_message_keys_disjoint',
          {r['client_sample_id'] for r in generated('sim-a')}.isdisjoint(
              r['client_sample_id'] for r in generated('sim-b')))
    with tempfile.TemporaryDirectory(prefix='aegis_ui_iot_acceptance_') as directory:
        store = Path(directory)
        app = create_pilot_app(store, ai_url='http://127.0.0.1:9')
        app.config.update(TESTING=True, FARM_WRITE_LIMIT=500)
        app.logger.setLevel('WARNING')
        client = app.test_client()
        headers = []
        for i in range(2):
            # Disposable fixture identities only; never included in output.
            credentials = dict(email=f'iot-{i}@example.test', password='synthetic-local-check-2026')
            status(client.post('/api/auth/register', json=credentials), 201, f'owner_{i}_created')
            login = status(client.post('/api/auth/login', json=credentials), 200, f'owner_{i}_login')
            headers.append({'Authorization': 'Bearer ' + login['access_token']})
        owner = client.get('/api/auth/me', headers=headers[0]).get_json()['user']['id']
        sources = []
        for node in ('sim-a', 'sim-b'):
            plot = status(client.post('/api/farm/plots', json={'name': 'SYNTHETIC '+node},
                                      headers=headers[0]), 201, node+'_plot')['item']
            season = status(client.post('/api/farm/plots/'+plot['id']+'/seasons',
                json=dict(name='SYNTHETIC only', start_date='2026-10-01', end_date='2026-12-31'),
                headers=headers[0]), 201, node+'_season')['item']
            meta = dict(client_stream_id=str(uuid5(NAMESPACE, node)), name='SYNTHETIC '+node,
                source='synthetic', method='sensor_reading', instrument='Software simulator; no sensor',
                reference='SYNTHETIC acceptance fixture only', nominal_interval_seconds=300)
            stream_url = '/api/farm/seasons/'+season['id']+'/environment-streams'
            with patch('pilot_telemetry.now', return_value=BASE-timedelta(minutes=1)):
                stream = status(client.post(stream_url, json=meta, headers=headers[0]),
                                201, node+'_stream')['item']
            check(node+'_source_isolated', stream['metadata']['source'] == 'synthetic'
                  and stream['season_id'] == season['id'] and stream['training_approved'] is False)
            url = '/api/farm/environment-streams/'+stream['id']+'/samples'
            rows = generated(node)
            # First four on time. Remaining observations are buffered by fixture.
            with patch('pilot_telemetry.now', return_value=BASE+timedelta(minutes=20)):
                initial = status(client.post(url, json={'records': rows[:4]}, headers=headers[0]),
                                 201, node+'_initial_ingest')
            first_received = initial['items'][0]['received_at']
            with patch('pilot_telemetry.now', return_value=END):
                # Discarding the first response models ACK loss after commit.
                replay = status(client.post(url, json={'records': rows[:4]}, headers=headers[0]),
                                200, node+'_response_loss_retry')
                check(node+'_retry_does_not_rewrite_receipt', replay['created'] == 0
                      and replay['replayed'] == 4 and replay['items'][0]['received_at'] == first_received)
                for slot in (7, 6, 5, 4, 8, 9):
                    status(client.post(url, json={'records': [rows[slot]]}, headers=headers[0]),
                           201, node+f'_backfill_slot_{slot}')
            items = status(client.get(url+'?page_size=100', headers=headers[0]),
                           200, node+'_readback')['items']
            check(node+'_raw_exact_and_ordered', len(items) == 10 and
                  [r['observed_at'] for r in items] == sorted((r['observed_at'] for r in rows[:10]), reverse=True)
                  and {r['id']: r['payload'] for r in items}
                  == {r['client_sample_id']: {k: v for k, v in r.items()
                      if k not in ('client_sample_id', 'observed_at')} for r in rows[:10]})
            missing = next(r for r in items if r['id'] == rows[8]['client_sample_id'])
            check(node+'_missing_and_suspect_preserved', missing['qc']['status'] == 'incomplete'
                  and missing['qc']['reported_suspect'] is True and missing['payload']['leaf_wet'] is None)
            check(node+'_raw_not_approved_for_ai', all(r['qc']['hourly_eligible'] is False
                  and r['training_approved'] is False for r in items))
            sources.append(dict(node=node, plot=plot['id'], season=season['id'],
                                stream=stream['id'], url=url, rows=rows))
        a, b = sources
        check('two_distinct_regions_and_streams', a['plot'] != b['plot']
              and a['season'] != b['season'] and a['stream'] != b['stream'])
        status(client.get(a['url']), 401, 'anonymous_refused')
        status(client.get(a['url'], headers=headers[1]), 404, 'foreign_owner_hidden')
        status(client.post(a['url'], json={'records': a['rows'][:1]}, headers=headers[1]),
               404, 'foreign_owner_write_refused')
        status(client.post('/api/farm/environment-streams/'+str(uuid5(NAMESPACE, 'absent'))+'/samples',
            json={'records': a['rows'][:1]}, headers=headers[0]), 404, 'unregistered_stream_refused')
        invalid = []
        good = a['rows'][10]
        missing_field = deepcopy(good); missing_field.pop('relative_humidity_pct')
        invalid.append(('missing_field', missing_field))
        for name, changes in (
            ('numeric_string', dict(air_temperature_c='26')),
            ('numeric_bool', dict(air_temperature_c=True)),
            ('nan', dict(air_temperature_c=float('nan'))),
            ('temperature_outside_technical_bounds', dict(air_temperature_c=77)),
            ('rh_outside_bounds', dict(relative_humidity_pct=101)),
            ('point_wetness_not_boolean', dict(leaf_wet=1)),
            ('explicit_wrong_units', dict(units={'air_temperature_c': 'degF'})),
            ('unsupported_schema_field', dict(schema_version=999)),
            ('device_cannot_override_region', dict(field_id=b['plot'])),
            ('device_cannot_set_receipt', dict(received_at=END.isoformat())),
            ('clock_unknown', dict(observed_at=None)),
            ('timezone_missing', dict(observed_at='2026-11-01T00:50:00')),
            ('future_clock', dict(observed_at=(END+timedelta(seconds=1)).isoformat())),
        ):
            invalid.append((name, dict(good, **changes)))
        with patch('pilot_telemetry.now', return_value=END):
            for name, bad in invalid:
                status(client.post(a['url'], json={'records': [bad]}, headers=headers[0]),
                       400, name+'_refused')
            status(client.post(a['url'], json={'records': [good, invalid[0][1]]}, headers=headers[0]),
                   400, 'mixed_batch_rejected')
            status(client.post(a['url'], json={'records': [dict(a['rows'][0], air_temperature_c=27)]},
                headers=headers[0]), 409, 'same_id_changed_payload_conflict')
            status(client.post(a['url'], json={'records': [dict(a['rows'][0],
                client_sample_id=str(uuid5(NAMESPACE, 'other-id')))]}, headers=headers[0]),
                409, 'same_time_different_id_conflict')
            status(client.post(b['url'], json={'records': a['rows'][:1]}, headers=headers[0]),
                   409, 'message_cannot_move_between_streams')
        check('invalid_batches_leave_no_partial_insert',
              client.get(a['url'], headers=headers[0]).get_json()['pagination']['total'] == 10)
        # No server or worker was started; factory restart reads persisted SQLite.
        restarted = create_pilot_app(store, ai_url='http://127.0.0.1:9').test_client()
        check('factory_restart_persists_raw',
              restarted.get(a['url'], headers=headers[0]).get_json()['pagination']['total'] == 10)
        exclusion_url = '/api/farm/environment-samples/'+a['rows'][6]['client_sample_id']+'/exclusion'
        with patch('pilot_telemetry.now', return_value=END+timedelta(minutes=2)):
            status(client.post(exclusion_url, json={'reason': 'SYNTHETIC review of injected step'},
                               headers=headers[0]), 201, 'exclusion_appended')
        summaries = []
        for source in sources:
            before = hashlib.sha256((store/'telemetry.sqlite3').read_bytes()).hexdigest()
            bundle = export(store, owner, source['stream'], expected_source='synthetic')
            check(source['node']+'_export_readonly', before == hashlib.sha256(
                (store/'telemetry.sqlite3').read_bytes()).hexdigest())
            report = audit(bundle, BASE.isoformat(), END.isoformat(), (END+timedelta(minutes=1)).isoformat())
            past = audit(bundle, BASE.isoformat(), END.isoformat(), END.isoformat())
            check(source['node']+'_no_future_exclusion_leakage', report['excluded_as_of_count'] == 0)
            check(source['node']+'_no_future_receipt_leakage', audit(bundle, BASE.isoformat(),
                (BASE+timedelta(minutes=15)).isoformat(), (BASE+timedelta(minutes=15)).isoformat())['received']['samples'] == 0)
            check(source['node']+'_delayed_receipt_visible', past['received']['samples'] == 10
                  and report['received_latency_seconds']['max'] == 2400)
            check(source['node']+'_constant_run_is_diagnostic',
                  report['longest_constant_observed_runs']['air_temperature_c']['sample_count'] == 6
                  and report['coverage_fraction'] is None)
            if source['node'] == 'sim-a':
                after = audit(bundle, BASE.isoformat(), END.isoformat(), (END+timedelta(minutes=3)).isoformat())
                check('exclusion_only_after_recorded_time', after['excluded_as_of_count'] == 1
                      and after['received']['samples'] == 10)
            # Fixture schedule is known exactly. This is NOT general production coverage.
            observed = {r['observed_at'] for r in bundle['readings']}
            absent = [r['observed_at'] for r in source['rows'] if r['observed_at'] not in observed]
            check(source['node']+'_intentional_silence_detected', len(absent) == 2)
            measured_age = (END-max(datetime.fromisoformat(r['observed_at'])
                                    for r in bundle['readings'])).total_seconds()
            receipt_age = (END-max(datetime.fromisoformat(r['received_at'])
                                   for r in bundle['readings'])).total_seconds()
            check(source['node']+'_new_receipt_is_not_fresh_measurement', measured_age == 900
                  and receipt_age == 0)
            summaries.append(dict(simulated_node_alias=source['node'], source='synthetic',
                expected_fixture_slots=12, persisted_unique_samples=10, missing_fixture_slots=absent,
                fixture_row_completeness=10/12,
                fixture_non_null_counts={k: sum(r['payload'][k] is not None for r in bundle['readings'])
                    for k in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet')},
                measured_age_at_window_end_seconds=measured_age, receipt_age_at_window_end_seconds=receipt_age,
                latency_seconds=report['received_latency_seconds']))
            for suffix, value in (('raw.synthetic', bundle), ('audit.synthetic', report),
                                  ('generated.synthetic', {'records': source['rows']})):
                with (out/(source['node']+'.'+suffix+'.json')).open('x', encoding='utf-8') as f:
                    json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        check('no_model_imported', not any(k in sys.modules for k in ('torch', 'ultralytics', 'joblib')))
    check('temporary_store_cleaned', not store.exists())
    return dict(schema_version='aegis-iot-acceptance-v1', success=True, source='synthetic',
        executed_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        seed=42, fixture_window_start=BASE.isoformat(), fixture_window_end=END.isoformat(),
        transport='Flask test client (in-process); not socket HTTP or MQTT',
        checks_passed=len(checks), checks=checks, streams=summaries,
        temporary_store_cleaned=True, hardware_verified=False, broker_verified=False,
        training_performed=False, forecast_performed=False,
        limits=['Outage and ACK loss are fixture operations, not network failure tests',
                'Simulator aliases do not implement authenticated physical devices',
                'Stuck/spike values retained; raw API has no sequential online QC',
                'Fixture cadence/coverage is not an approved field protocol',
                'Unsynced clock is rejected; no device quarantine or buffer firmware tested'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New evidence directory; refuses overwrite')
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.exit(2, 'Use a new writable output directory.\n')
    try:
        result = run(out)
    except Exception as exc:
        # Do not serialize responses, credentials, headers or arbitrary exception text.
        result = dict(success=False, failure_type=type(exc).__name__, source='synthetic')
        if isinstance(exc, RuntimeError) and str(exc).startswith('Acceptance failed: '):
            result['failed_check'] = str(exc).removeprefix('Acceptance failed: ')
    with (out/'summary.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result if not result['success'] else {
        'success': True, 'checks_passed': result['checks_passed'],
        'temporary_store_cleaned': result['temporary_store_cleaned'], 'summary': str(out/'summary.json')}))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
