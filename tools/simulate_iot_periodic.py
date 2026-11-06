"""IOT-09: bounded real-time synthetic producer, two nodes and isolated HTTP Backend.

Every measurement uses the current UTC clock. Monotonic scheduling does not
fabricate past readings if the loop is late. No model, broker or hardware.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from uuid import UUID, uuid4, uuid5

import requests

from iot_http_sender import Outbox, drain

ROOT = Path(__file__).resolve().parents[1]
NODES = ('sim-01', 'sim-02')


def measurement(run_id, node, index, measured_at, seed, failure_every):
    """Reproducible values by seed/node/index; live timestamp and run-scoped key."""
    if node not in NODES or type(index) is not int or index < 0:
        raise ValueError('Known simulator node and nonnegative sample index required')
    rng = random.Random(f'{seed}:{node}:{index}')
    failure = failure_every > 0 and (index+1) % failure_every == 0
    return dict(client_sample_id=str(uuid5(UUID(run_id), f'{node}:{index}')),
        observed_at=measured_at.isoformat(),
        air_temperature_c=None if failure else round(27+math.sin(index/10)+rng.uniform(-.2, .2), 3),
        relative_humidity_pct=None if failure else round(84+rng.uniform(-2, 2), 3),
        leaf_wet=None if failure else rng.random() > .5,
        reported_quality='suspect' if failure else 'unknown',
        reference=f'SYNTHETIC periodic run={run_id} node={node} index={index}; no sensor')


def due_index(elapsed, interval, next_index):
    """Returns latest due index and skipped slots; never fills old slots."""
    latest = math.floor(elapsed/interval)
    return (None, 0) if latest < next_index else (latest, latest-next_index)


def offline_at(elapsed, start, seconds):
    return seconds > 0 and start <= elapsed < start+seconds


def validate_config(c):
    if type(c.interval) is not int or not 1 <= c.interval <= 60:
        raise ValueError('interval must be integer seconds from 1 to 60')
    for name, low, high in (('duration', 1, 3600), ('send_interval', .1, 60),
                           ('drain_seconds', 0, 30), ('offline_start', 0, 3600),
                           ('offline_seconds', 0, 3600)):
        value = getattr(c, name)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid bounded simulator duration: '+name)
    if type(c.capacity) is not int or not 1 <= c.capacity <= 1000:
        raise ValueError('capacity must be from 1 to 1000 per node')
    if type(c.sensor_failure_every) is not int or not 0 <= c.sensor_failure_every <= 10000:
        raise ValueError('sensor-failure-every must be from 0 to 10000')


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def run(c, out, state):
    temp = tempfile.TemporaryDirectory(prefix='aegis_ui_iot_http_periodic_')
    store = Path(temp.name)
    session = requests.Session(); session.trust_env = False
    child = log = trace = None
    state.update(schema_version='aegis-periodic-simulator-v1', source='synthetic',
        success=False, status='starting', run_id=str(uuid4()),
        backend_stopped=True, temporary_store_cleaned=False, forced_stop=False,
        hardware_verified=False, mqtt_verified=False, training_performed=False,
        config={k: getattr(c, k) for k in ('duration', 'interval', 'send_interval', 'capacity',
            'seed', 'sensor_failure_every', 'offline_start', 'offline_seconds', 'drain_seconds')},
        nodes=[], skipped_sampling_ticks=0)
    control = store/'control'; control.mkdir()

    def event(kind, **values):
        trace.write(json.dumps(dict(event=kind, at=datetime.now(timezone.utc).isoformat(), **values),
                               ensure_ascii=False, allow_nan=False)+'\n')
        trace.flush()

    def api(method, path, code, data=None, token=None):
        with session.request(method, base+path, json=data,
                headers={} if token is None else {'Authorization': 'Bearer '+token},
                timeout=3, allow_redirects=False) as response:
            if response.status_code != code:
                raise RuntimeError('Unexpected HTTP status during simulator setup/readback')
            return response.json()

    boxes, node_stats, streams, generated_rows, accepted_rows = {}, {}, {}, {}, {}
    try:
        trace = (out/'events.jsonl').open('x', encoding='utf-8')
        log = (out/'backend.log').open('x', encoding='utf-8')
        child = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(ROOT/'tools/rehearse_iot_http.py'),
            '--serve-store', str(store), '--control', str(control)], cwd=ROOT, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        state['backend_stopped'] = False
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('Simulator Backend exited during setup')
            try:
                info = json.loads((control/'ready.json').read_text(encoding='utf-8')); break
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.05)
        else:
            raise RuntimeError('Simulator Backend startup timed out')
        if info['model_loaded']:
            raise RuntimeError('Unexpected model import')
        base = 'http://127.0.0.1:'+str(info['port'])
        credentials = dict(email='periodic-sim@example.test', password='synthetic-periodic-test-2026')
        api('POST', '/api/auth/register', 201, credentials)
        token = api('POST', '/api/auth/login', 200, credentials)['access_token']
        owner = api('GET', '/api/auth/me', 200, token=token)['user']['id']
        today = datetime.now(timezone(timedelta(hours=7))).date()
        for node in NODES:
            plot = api('POST', '/api/farm/plots', 201, {'name': 'SYNTHETIC '+node}, token)['item']
            season = api('POST', '/api/farm/plots/'+plot['id']+'/seasons', 201,
                dict(name='Periodic synthetic session', start_date=(today-timedelta(days=1)).isoformat(),
                    end_date=(today+timedelta(days=1)).isoformat()), token)['item']
            stream = api('POST', '/api/farm/seasons/'+season['id']+'/environment-streams', 201,
                dict(client_stream_id=str(uuid4()), name='SYNTHETIC periodic '+node, source='synthetic',
                    method='sensor_reading', instrument='Virtual temperature/RH/point-wetness; no hardware',
                    reference='SYNTHETIC periodic simulator', nominal_interval_seconds=c.interval), token)['item']
            streams[node] = stream['id']
            boxes[node] = Outbox(store/(node+'.sqlite3'), capacity=c.capacity)
            generated_rows[node], accepted_rows[node] = [], []
            stats = dict(node=node, plot_id=plot['id'], season_id=season['id'], stream_id=stream['id'],
                generated=0, enqueued=0, rejected_buffer_full=0, sensor_failure_samples=0,
                acknowledged=0, attempts=0, retry_cycles=0, max_pending=0)
            node_stats[node] = stats; state['nodes'].append(stats)
        started = time.monotonic()
        state.update(status='running', started_at=datetime.now(timezone.utc).isoformat())
        event('started', run_id=state['run_id'], interval_seconds=c.interval, duration_seconds=c.duration)
        print('SYNTHETIC: sim-01 / sim-02; current UTC measurements; STOP file or Ctrl+C to stop.', flush=True)
        next_index, next_send, last_offline = 0, 0., None
        stop_reason = 'duration'

        def send_cycle(elapsed):
            nonlocal last_offline
            offline = offline_at(elapsed, c.offline_start, c.offline_seconds)
            if offline != last_offline:
                event('transport_paused' if offline else 'transport_enabled', elapsed_seconds=round(elapsed, 3))
                last_offline = offline
            if offline:
                return
            for node in NODES:
                result = drain(boxes[node], base, token, max_attempts=1, max_records=1,
                               timeout_seconds=.5, session=session)
                stats = node_stats[node]
                stats['acknowledged'] += result['acknowledged']
                stats['attempts'] += len(result['events'])
                stats['retry_cycles'] += result['status'] == 'retry_exhausted'
                event('send_cycle', node=node, status=result['status'], acknowledged=result['acknowledged'],
                      pending=boxes[node].count(), outcomes=result['events'])
                if result['status'] in ('operator_required', 'rate_limited'):
                    raise RuntimeError('Sender requires operator review; queued data retained')

        try:
            while True:
                elapsed = time.monotonic()-started
                if (out/'STOP').exists(): stop_reason = 'stop_file'; break
                if elapsed >= c.duration: break
                if child.poll() is not None: raise RuntimeError('Simulator Backend exited during collection')
                index, skipped = due_index(elapsed, c.interval, next_index)
                if index is not None:
                    state['skipped_sampling_ticks'] += skipped
                    if skipped: event('sampling_ticks_skipped', count=skipped, latest_index=index)
                    for node in NODES:
                        sample = measurement(state['run_id'], node, index, datetime.now(timezone.utc),
                                             c.seed, c.sensor_failure_every)
                        stats = node_stats[node]; stats['generated'] += 1
                        stats['sensor_failure_samples'] += sample['reported_quality'] == 'suspect'
                        generated_rows[node].append(sample)
                        try:
                            boxes[node].enqueue(streams[node], sample, source='synthetic')
                        except OverflowError:
                            stats['rejected_buffer_full'] += 1
                            event('buffer_full', node=node, sample=sample)
                        else:
                            stats['enqueued'] += 1; accepted_rows[node].append(sample)
                            event('measurement', node=node, index=index, sample=sample)
                        stats['max_pending'] = max(stats['max_pending'], boxes[node].count())
                    next_index = index+1
                    print(f"t={elapsed:.1f}s index={index} queue="+
                          '/'.join(str(boxes[n].count()) for n in NODES), flush=True)
                if elapsed >= next_send:
                    send_cycle(elapsed)
                    next_send = (math.floor((time.monotonic()-started)/c.send_interval)+1)*c.send_interval
                wait = min(next_index*c.interval, next_send, c.duration)-(time.monotonic()-started)
                time.sleep(max(0, min(.1, wait)))
        except KeyboardInterrupt:
            stop_reason = 'keyboard_interrupt'
        state.update(stop_reason=stop_reason, collection_elapsed_seconds=round(time.monotonic()-started, 3))
        state['planned_sampling_ticks'] = math.ceil(c.duration/c.interval)
        state['window_sampling_ticks'] = math.ceil(min(c.duration, time.monotonic()-started)/c.interval)
        tail_skipped = max(0, state['window_sampling_ticks']-next_index)
        state['skipped_sampling_ticks'] += tail_skipped
        if tail_skipped: event('sampling_ticks_skipped_at_stop', count=tail_skipped)
        # Finite grace period; offline gate remains in force. Never discard pending rows.
        grace_end = time.monotonic()+c.drain_seconds
        try:
            while any(box.count() for box in boxes.values()) and time.monotonic() < grace_end:
                send_cycle(time.monotonic()-started)
                time.sleep(min(.1, c.send_interval))
        except KeyboardInterrupt:
            state['stop_reason'] = 'keyboard_interrupt'
        for node in NODES:
            node_stats[node]['pending'] = boxes[node].count()
        state['collection_finished_at'] = datetime.now(timezone.utc).isoformat()
        event('collection_stopped', reason=state['stop_reason'])
        # Read back all pages while HTTP is still available, with owner auth.
        for node in NODES:
            items, page = [], 1
            while True:
                data = api('GET', '/api/farm/environment-streams/'+streams[node]+f'/samples?page={page}&page_size=100', 200, token=token)
                items.extend(data['items'])
                if not data['pagination']['has_next']: break
                page += 1
            stats = node_stats[node]
            stats['persisted_unique'] = len(items)
            stats['qc_incomplete'] = sum(r['qc']['status'] == 'incomplete' for r in items)
            expected = {s['client_sample_id']: (s['observed_at'], {k: v for k, v in s.items()
                if k not in ('client_sample_id', 'observed_at')}) for s in accepted_rows[node]}
            observed = {r['id']: (r['observed_at'], r['payload']) for r in items}
            if len(items) != len(observed) or any(expected.get(key) != value for key, value in observed.items()):
                raise RuntimeError('HTTP readback differs from generated raw')
            with boxes[node].connect() as db:
                pending_ids = {r[0] for r in db.execute('SELECT message_id FROM pending')}
            if set(observed) | pending_ids != set(expected):
                raise RuntimeError('Enqueued samples missing from both Backend and outbox')
            if stats['acknowledged'] != len(set(observed)-pending_ids):
                raise RuntimeError('ACK/readback/outbox mismatch')
            stats['unacknowledged_but_persisted'] = len(set(observed) & pending_ids)
            stats['readback_matches_original'] = True
            stats['last_observed_at'] = max((r['observed_at'] for r in items), default=None)
            stats['last_received_at'] = max((r['received_at'] for r in items), default=None)
        (control/'STOP').touch(); child.wait(timeout=10)
        if child.returncode != 0: raise RuntimeError('Backend did not exit cleanly')
        state['backend_stopped'] = True
        sys.path.insert(0, str(ROOT/'frontend'))
        from telemetry_tool import export
        for node in NODES:
            bundle = export(store, owner, streams[node], expected_source='synthetic')
            write_json(out/(node+'.raw.synthetic.json'), bundle)
            if len(bundle['readings']) != node_stats[node]['persisted_unique']:
                raise RuntimeError('Export/readback mismatch')
        state['success'] = (all(n['pending'] == 0 and n['rejected_buffer_full'] == 0 for n in state['nodes'])
                            and state['skipped_sampling_ticks'] == 0)
        state['status'] = ('completed' if state['stop_reason'] == 'duration' else 'stopped') if state['success'] else 'incomplete'
    finally:
        # Preserve generated inputs and credential-free SQLite outboxes even on failure.
        try:
            for node, box in boxes.items():
                node_stats[node]['pending'] = box.count()
                with closing(sqlite3.connect(box.path)) as source, closing(sqlite3.connect(out/(node+'.outbox.sqlite3'))) as dest:
                    source.backup(dest)
                write_json(out/(node+'.generated.synthetic.json'), {'source': 'synthetic', 'records': generated_rows[node]})
        finally:
            try:
                if child is not None and child.poll() is None:
                    (control/'STOP').touch()
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        state['forced_stop'] = True; child.terminate(); child.wait(timeout=10)
                state['backend_stopped'] = child is None or child.poll() is not None
                state['backend_exit_code'] = None if child is None else child.returncode
            finally:
                session.close()
                if trace is not None: trace.close()
                if log is not None: log.close()
                try: temp.cleanup()
                finally: state['temporary_store_cleaned'] = not store.exists()
    if state['forced_stop'] or not state['temporary_store_cleaned']:
        raise RuntimeError('Simulator cleanup failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--duration', type=float, default=30)
    p.add_argument('--interval', type=int, default=2)
    p.add_argument('--send-interval', type=float, default=.5)
    p.add_argument('--capacity', type=int, default=16)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--sensor-failure-every', type=int, default=4)
    p.add_argument('--offline-start', type=float, default=4)
    p.add_argument('--offline-seconds', type=float, default=4)
    p.add_argument('--drain-seconds', type=float, default=5)
    c = p.parse_args()
    try: validate_config(c)
    except ValueError: p.exit(2, 'Invalid simulator configuration; see --help.\n')
    out = c.out.resolve()
    try: out.mkdir(parents=True, exist_ok=False)
    except OSError: p.exit(2, 'Use a new writable output directory.\n')
    state = {}
    try:
        run(c, out, state)
    except KeyboardInterrupt:
        state.update(success=False, status='interrupted_during_setup_or_finalization')
    except Exception as exc:
        state.update(success=False, status='failed', failure_type=type(exc).__name__)
    write_json(out/'summary.json', state)
    print(json.dumps(dict(success=state['success'], status=state['status'],
        generated=sum(n['generated'] for n in state.get('nodes', [])),
        pending=sum(n.get('pending', -1) for n in state.get('nodes', [])),
        backend_stopped=state.get('backend_stopped'), temporary_store_cleaned=state.get('temporary_store_cleaned'),
        summary=str(out/'summary.json')), ensure_ascii=False))
    return 0 if state['success'] else 3 if state['status'] == 'incomplete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
