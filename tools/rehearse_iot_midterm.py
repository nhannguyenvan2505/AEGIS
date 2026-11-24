"""IOT-08: one-command synthetic IoT rehearsal with HTTP, recovery and QC.

Reuses IOT-06/07 without changing their implementation. Writes a Vietnamese
presentation report and fresh, traceable evidence; does not load an AI model.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'frontend'))

import rehearse_iot_http as http_rehearsal
import rehearse_iot_sender_crash as crash_rehearsal
from rehearse_iot import BASE, END
from telemetry_audit import audit, load
from telemetry_monitor import monitor, POLICY_SCHEMA

SOURCE_PATHS = (
    'tools/rehearse_iot_midterm.py', 'tools/rehearse_iot_http.py',
    'tools/rehearse_iot_sender_crash.py', 'tools/iot_http_sender.py',
    'tools/rehearse_iot.py', 'backend/pilot_app.py',
    'frontend/pilot_telemetry.py', 'frontend/telemetry_tool.py',
    'frontend/telemetry_audit.py', 'frontend/telemetry_monitor.py',
)


def hashes():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_PATHS}


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def report_text(result):
    http, crash = result['components']['http'], result['components']['sender_crash']
    lines = [
        '# AEGIS — tổng duyệt IoT midterm', '',
        '**KẾT QUẢ: ĐẠT phạm vi mô phỏng. Toàn bộ dữ liệu là SYNTHETIC.**', '',
        'Thời điểm chạy (UTC+7): '+result['executed_at'], '',
        'Luồng kiểm: phát sinh phép đo → SQLite outbox → HTTP loopback → raw validation '
        '→ SQLite Backend → ACK ứng dụng → truy xuất/export → báo cáo QC.', '',
        '| Phần | Kết quả mới của lượt này |', '|---|---|',
        f"| HTTP, buffer và retry | {http['checks_passed']} checkpoint đạt; hai vùng, {http['persisted_unique_samples']} raw duy nhất |",
        f"| Sender bị dừng sau ACK | {crash['checks_passed']} checkpoint đạt; exit77/77/0/0; {crash['persisted_unique_samples']} raw duy nhất trong kho riêng |",
        f"| Đối soát tổng duyệt | {result['checks_passed']} checkpoint đạt; nguồn giữ nguyên hash, kho/process đã dọn |", '',
        'Hai bài kiểm dùng **hai kho tạm độc lập**. Sáu raw HTTP và hai raw crash không '
        'được cộng thành số đo của cùng một ruộng hoặc cùng một chuỗi thời gian.', '',
        '## Chất lượng dữ liệu trên raw của chính lượt HTTP này', '',
        'Lịch demo có12slot/giờ,5phút/slot. Bài HTTP cố ý gửi3slot đầu cho mỗi vùng; '
        '9slot còn lại không gửi theo kịch bản. Đây không phải số liệu dropout của thiết bị thật.', '',
        '| Vùng ảo | Raw/slot đến hạn | Slot thiếu | Đầy đủ theo lịch demo | T / RH / lá ướt có giá trị | Tuổi đo (giây) | Tuổi nhận (giây) | Trạng thái |',
        '|---|---:|---:|---:|---|---:|---:|---|',
    ]
    for row in result['qc_streams']:
        c = row['non_null_slots']
        lines.append(f"| {row['alias']} | {row['received_slots']}/{row['due_slots']} | "
            f"{row['missing_slots']} | {row['completeness']:.0%} | "
            f"{c['air_temperature_c']} / {c['relative_humidity_pct']} / {c['leaf_wet']} | "
            f"{row['measurement_age_seconds']:.1f} | {row['receipt_age_seconds']:.1f} | "
            f"{row['measurement_status']} / {row['receipt_status']} |")
    lines += ['',
        'Tuổi nhận nhỏ cho biết Backend vừa nhận raw. Tuổi đo lớn vì fixture có '
        'observed_at cố định01/11/2026: dữ liệu gửi bù vẫn là phép đo cũ. Timestamp nhận '
        'là giờ server thật, không bị lùi về giờ đo. Không dùng độ trễ fixture này làm SLA.', '',
        'QC dùng snapshot hash hợp lệ, policy theo từng stream, as_of=exported_at; '
        'không dùng receipt/exclusion tương lai. Ngưỡng stale600giây và lịch5phút là '
        'cấu hình kỹ thuật demo, chưa là quy trình thu thực địa.', '',
        '## Lời dẫn trình bày khoảng5phút', '',
        '1. **0:00–0:45:** Giới thiệu hai node/vùng ảo và source=synthetic. '
        'Chạy lệnh tổng duyệt; Backend/process/kho tạm được tạo tự động.',
        '2. **0:45–1:45:** Mở [HTTP summary](http/summary.json). Chỉ ra queue đầy, '
        'mất ACK sau DB commit, retry replay và giữ nguyên observed_at/received_at.',
        '3. **1:45–2:45:** Mở [crash summary](sender_crash/summary.json) và '
        '[marker](sender_crash/crash_markers.json): hai sender exit77 sau ACK201/200; '
        'sender mới phục hồi, Backend không nhân đôi.',
        '4. **2:45–4:00:** Dùng bảng QC: hai vùng đều3/12slot, thiếu9slot theo kịch bản; '
        'nhận mới không biến giờ đo cũ thành mới. Mở [QC vùng0](qc/node0.monitor.json).',
        '5. **4:00–5:00:** Mở [raw snapshot](http/node0.raw.synthetic.json) để đối chiếu '
        'UUID, stream, observed_at, received_at và training_approved=false; nêu giới hạn.', '',
        '## Giới hạn và cách dùng bằng chứng', '',
        '- HTTP thật trên loopback cùng máy; chưa ESP32, Wi-Fi/MQTT, mất điện hoặc vận hành ruộng.',
        '- Crash là process os._exit(77) sau ACK trước DELETE, chưa crash giữa SQLite commit.',
        '- Không có model dự báo, nhãn bệnh, xác minh hiệu chuẩn hoặc AI-ready hourly. '
        'Mọi raw vẫn training_approved=false, hourly_eligible=false.',
        '- Không lấy75% slot chưa gửi của fixture thành tỷ lệ mất mạng thực tế; '
        'không lấy điểm lá ướt thành cả giờ ướt.',
        '- Báo cáo là artifact tĩnh sau chạy, không phải dashboard realtime hoặc màn mobile đã tích hợp.',
        '- Snapshot/UUID đều của kho test; không có token/password/DB session trong gói evidence.', '',
        '## File để kiểm tra', '',
        '- [Summary tổng](summary.json): trạng thái từng phần, checkpoint và cleanup.',
        '- [Manifest nguồn](source_manifest.json): SHA256 trước/sau các dependency đã dùng.',
        '- [Policy vùng0](qc/node0.policy.synthetic.json), [audit vùng0](qc/node0.audit.json).',
        '- [Policy vùng1](qc/node1.policy.synthetic.json), [monitor vùng1](qc/node1.monitor.json).', '',
        'Nếu không thể chạy live tại buổi trình bày, có thể mở báo cáo/evidence của lượt '
        'đã thành công này và nói rõ đó là kết quả đã lưu. Không trình bày như vừa chạy live.', '',
    ]
    return '\n'.join(lines)


def run(out, result):
    source_before = hashes()
    checks = []
    result.update(schema_version='aegis-iot-midterm-v1', success=False, source='synthetic',
        executed_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        components={}, qc_streams=[], checks=checks,
        hardware_verified=False, mqtt_verified=False, training_performed=False, forecast_performed=False)

    def check(name, condition):
        if not condition:
            raise RuntimeError('Acceptance failed: '+name)
        checks.append(name)

    for name in ('http', 'sender_crash', 'qc'):
        (out/name).mkdir()
    result['stage'] = 'http'
    print('[1/3] HTTP: hai vung, buffer, retry, mat ACK va restart Backend...', flush=True)
    http = http_rehearsal.run(out/'http')
    write_json(out/'http/summary.json', http)
    result['components']['http'] = http
    check('http_succeeded_and_cleaned', http['success'] is True and http['temporary_store_cleaned'] is True
          and http['backend_stopped'] is True and http['forced_stop'] is False)
    check('http_has_two_streams_and_six_raw', http['streams'] == 2 and http['persisted_unique_samples'] == 6)
    check('http_transport_not_test_client', 'tcp_closed_before_ack_keeps_outbox' in http['checks'])

    result['stage'] = 'sender_crash'
    print('[2/3] Sender: hai lan crash sau ACK, khoi phuc va replay...', flush=True)
    lifecycle = {}
    try:
        crash = crash_rehearsal.run(out/'sender_crash', lifecycle)
    finally:
        result['sender_crash_lifecycle'] = lifecycle
    write_json(out/'sender_crash/summary.json', crash)
    result['components']['sender_crash'] = crash
    check('sender_crash_succeeded_and_cleaned', crash['success'] is True and crash['temporary_store_cleaned'] is True
          and crash['backend_stopped'] is True and crash['forced_stop'] is False)
    check('sender_process_exit_codes_match', [p['exit_code'] for p in crash['sender_runs']] == [77, 77, 0, 0])
    check('sender_crash_has_two_unique_raw', crash['persisted_unique_samples'] == 2)

    result['stage'] = 'qc'
    print('[3/3] QC: snapshot moi, slot thieu, tuoi do va tuoi nhan...', flush=True)
    for i in range(2):
        path = out/'http'/f'node{i}.raw.synthetic.json'
        raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        bundle = load(path)
        # Policy is explicitly declared for this current offline demonstration.
        # No claim that it was known when the historical fixture was measured.
        policy = dict(schema_version=POLICY_SCHEMA, stream_id=bundle['stream_id'],
            available_at=bundle['stream_created_at'], anchor_at=BASE.isoformat(), interval_seconds=300,
            tolerance_seconds=5, arrival_grace_seconds=60, stale_after_seconds=600,
            receipt_silence_after_seconds=600)
        as_of = bundle['exported_at']
        m = monitor(bundle, policy, BASE.isoformat(), END.isoformat(), as_of)
        a = audit(bundle, BASE.isoformat(), END.isoformat(), as_of)
        check(f'node{i}_synthetic_unapproved', bundle['metadata']['source'] == 'synthetic'
              and bundle['training_approved'] is False and m['hourly_eligible'] is False)
        check(f'node{i}_monitor_evaluated', m['status'] == 'evaluated')
        schedule, freshness = m['schedule'], m['freshness']
        check(f'node{i}_fixture_schedule_counts', schedule['due_slots'] == 12
              and schedule['received_slots'] == 3 and len(schedule['missing_slots']) == 9
              and schedule['completeness'] == .25)
        check(f'node{i}_per_field_counts', all(schedule['non_null_slots'][key] == 3
              for key in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet')))
        check(f'node{i}_backfill_is_old_measurement', freshness['measurement_status'] == 'stale'
              and freshness['measurement_age_seconds'] > freshness['receipt_age_seconds'])
        check(f'node{i}_audit_matches_raw', a['received']['samples'] == len(bundle['readings']) == 3
              and a['aggregation_performed'] is False and a['training_approved'] is False)
        for suffix, data in (('policy.synthetic', policy), ('monitor', m), ('audit', a)):
            write_json(out/'qc'/f'node{i}.{suffix}.json', data)
        check(f'node{i}_raw_file_unchanged', raw_hash == hashlib.sha256(path.read_bytes()).hexdigest())
        result['qc_streams'].append(dict(alias='Vung ao '+str(i), stream_id=bundle['stream_id'],
            due_slots=schedule['due_slots'], received_slots=schedule['received_slots'],
            missing_slots=len(schedule['missing_slots']), completeness=schedule['completeness'],
            non_null_slots=schedule['non_null_slots'], **freshness,
            qc_status_counts=a['received']['qc'],
            raw_file=f'http/node{i}.raw.synthetic.json', monitor_file=f'qc/node{i}.monitor.json'))

    source_after = hashes()
    check('source_hashes_unchanged_during_rehearsal', source_before == source_after)
    write_json(out/'source_manifest.json', dict(before=source_before, after=source_after))
    result.update(success=True, stage='complete', checks_passed=len(checks),
        component_checkpoints=sum(c['checks_passed'] for c in result['components'].values()),
        backend_stopped=True, temporary_stores_cleaned=True,
        scope='Synthetic HTTP loopback + sender process recovery + offline QC; no hardware or forecast')
    # Report success only after all nested assertions and cleanup checks passed.
    with (out/'DEMO_REPORT.md').open('x', encoding='utf-8') as f:
        f.write(report_text(result))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True, help='New evidence/report directory')
    args = p.parse_args()
    out = args.out.resolve()
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError:
        p.exit(2, 'Use a new writable output directory.\n')
    result = {}
    started = time.monotonic()
    try:
        run(out, result)
    except Exception as exc:
        result.update(success=False, failure_type=type(exc).__name__)
        if isinstance(exc, RuntimeError) and str(exc).startswith('Acceptance failed: '):
            result['failed_check'] = str(exc).removeprefix('Acceptance failed: ')
        with (out/'DEMO_FAILED.md').open('x', encoding='utf-8') as f:
            f.write('# Tong duyet chua dat\n\nXem summary.json; khong su dung nhu bang chung PASS.\n')
    result['elapsed_wall_seconds'] = round(time.monotonic()-started, 3)
    write_json(out/'summary.json', result)
    print(json.dumps(dict(success=result['success'], stage=result.get('stage'),
        checks_passed=result.get('checks_passed'), component_checkpoints=result.get('component_checkpoints'),
        elapsed_wall_seconds=result['elapsed_wall_seconds'],
        report=str(out/('DEMO_REPORT.md' if result['success'] else 'DEMO_FAILED.md')),
        summary=str(out/'summary.json')), ensure_ascii=False))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
