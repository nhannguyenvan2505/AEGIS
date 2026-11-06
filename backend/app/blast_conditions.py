"""Experimental mock-only environmental pattern monitor; not a disease forecast."""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone

PROFILE = {
    'version': 'blast-conditions-mock-v0.1',
    'mode': 'experimental_mock_only',
    'window_hours': 24,
    'consecutive_hours': 6,
    'temperature_min_c': 25.0,
    'temperature_max_c': (82 - 32) * 5 / 9,
    'humidity_exclusive_min_pct': 90,
    'requires_leaf_wet': True,
    'duration_basis': 'Engineering demo assumption, not validated infection duration',
    'source_url': 'https://ipm.ucanr.edu/agriculture/rice/rice-blast/',
}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def parse_time(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an ISO8601 string with timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timezone required')
    parsed = parsed.astimezone(timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError('Hourly bucket boundaries required')
    return parsed

def evaluate(payload):
    """Each record describes a completed one-hour interval [start_at,start_at+1h).

    Caller supplies a deterministic as_of. No DB, clock, HTTP, YOLO or side effects.
    Production observations are deliberately unsupported by this mock profile.
    """
    if not isinstance(payload, dict) or payload.get('source') != 'mock':
        raise ValueError('This experimental profile accepts source=mock only')
    end = parse_time(payload.get('as_of'))
    rows = payload.get('records')
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError('records must be a list of at most 24 hourly buckets')
    start = end - timedelta(hours=PROFILE['window_hours'])
    observed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid record')
        instant = parse_time(row.get('start_at'))
        if instant in observed:
            raise ValueError('Duplicate hourly bucket')
        if not start <= instant < end:
            raise ValueError('Bucket outside completed assessment window')
        temperature, humidity = row.get('air_temperature_c'), row.get('relative_humidity_pct')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in [temperature, humidity]):
            raise ValueError('Temperature and humidity must be finite numbers')
        if not -50 <= temperature <= 60 or not 0 <= humidity <= 100:
            raise ValueError('Value outside technical input bounds')
        if type(row.get('leaf_wet')) is not bool:
            raise ValueError('leaf_wet must be a measured/mock boolean; RH is not its substitute')
        observed[instant] = row
    missing = [start + timedelta(hours=i) for i in range(24) if start + timedelta(hours=i) not in observed]
    result = dict(
        disease='rice_blast', assessment_kind='environmental_pattern',
        profile_version=PROFILE['version'], profile_sha256=digest(PROFILE),
        input_sha256=digest(payload), source='mock', is_mock=True,
        field_validated=False, forecast_horizon_hours=None,
        window_start=start.isoformat(), window_end=end.isoformat(),
        completeness=dict(expected_buckets=24, received_buckets=len(rows), missing_buckets=[t.isoformat() for t in missing]),
        reasons=[], action='Kiểm tra dữ liệu và quan sát ruộng; có thể chụp ảnh để kiểm tra triệu chứng.',
    )
    if missing:
        result.update(status='insufficient_data', longest_matching_run_hours=None,
                      reasons=['Thiếu bucket trong cửa sổ; không nội suy hoặc mặc định nguy cơ thấp.'])
        return result
    longest = run = 0
    for instant in sorted(observed):
        row = observed[instant]
        matches = (PROFILE['temperature_min_c'] <= row['air_temperature_c'] <= PROFILE['temperature_max_c']
                   and row['relative_humidity_pct'] > PROFILE['humidity_exclusive_min_pct']
                   and row['leaf_wet'])
        run = run + 1 if matches else 0
        longest = max(longest, run)
    triggered = longest >= PROFILE['consecutive_hours']
    result.update(status='advisory' if triggered else 'no_pattern_detected', longest_matching_run_hours=longest,
                  reasons=[f'Mẫu hẹp nhiệt độ/độ ẩm/lá ướt đồng thời kéo dài tối đa {longest} giờ liên tục.',
                           'Mốc 6 giờ là giả định demo; chưa chứng minh thời gian nhiễm bệnh.',
                           'Không xác nhận có/không có bệnh, không ước lượng xác suất hoặc ngày xuất hiện bệnh.'])
    return result
