"""Owner-scoped, read-only FM03 data readiness at an explicit as-of time."""
from datetime import datetime, timedelta, timezone

from flask import g
from app.farm import FarmError
from telemetry_audit import stamp
from pilot_forecast import stored_hourly_input, HOURLY_MODEL_PIN, prepare_weather


def now():
    return datetime.now(timezone.utc)


def assessment_time(args):
    if set(args) - {'issued_at'} or any(len(args.getlist(k)) != 1 for k in args):
        raise FarmError('invalid_forecast_query', 'Chỉ nhận một issued_at có timezone hoặc để trống.')
    assessed = now()
    try:
        issued = stamp(args['issued_at']) if 'issued_at' in args else assessed
        if issued > assessed:
            raise ValueError('Future issue')
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise FarmError('invalid_forecast_query', 'issued_at cần timezone và không ở tương lai.')
    return issued, assessed, 'explicit_as_of' if args else 'server_clock'


def readiness(core, db, season, issued, assessed, clock):
    end = issued.replace(minute=0, second=0, microsecond=0)
    result = dict(schema_version='aegis-forecast-readiness-v1', season_id=season['id'], plot_id=season['plot_id'],
        source='synthetic', field_validated=False, model_version='fm03-weather-logistic-v1',
        model_manifest_sha256=HOURLY_MODEL_PIN, model_service_status='not_checked',
        issued_at=issued.isoformat(), assessed_at=assessed.isoformat(), clock=clock,
        feature_window_start=(end-timedelta(hours=120)).isoformat(), feature_window_end=end.isoformat(),
        lookback_hours=120, horizon_hours=72, required_numeric_hours=120,
        hourly_source=None, coverage_hours=None, crop_age_known=None, data_ready=False,
        forecast_request=None)
    source = db.execute('''SELECT h.id FROM hourly_sources h JOIN streams s
        ON s.id=h.stream_id AND s.user_id=h.user_id AND s.season_id=h.season_id
        WHERE h.user_id=? AND h.season_id=? AND h.created_at<=?
        ORDER BY h.created_at DESC,h.revision DESC,h.id DESC LIMIT 1''',
        (g.user['id'], season['id'], issued.isoformat())).fetchone()
    if source is None:
        result.update(status='source_missing', reasons=[dict(code='hourly_source_missing')], next_actions=['add_hourly_source'])
        return result
    _, payload, origin = stored_hourly_input(core, db, season, source['id'], issued.isoformat())
    prepared = prepare_weather(payload)
    feature = prepared['rows'][0]
    ready = feature['predictors'] is not None
    age_known = not any(r['code'] == 'unknown_calendar_crop_age' for r in feature['reasons'])
    actions = []
    if any(r['code'] == 'incomplete_hourly_coverage' for r in feature['reasons']):
        actions.append('complete_numeric_history')
    if not age_known:
        actions.append('update_cultivation_profile')
    result.update(status='ready' if ready else 'insufficient_data', data_ready=ready, reasons=feature['reasons'],
        hourly_source=origin, coverage_hours=dict(temperature=feature['coverage']['120']['temp'], humidity=feature['coverage']['120']['rh']),
        crop_age_known=age_known, next_actions=actions,
        input_sha256=prepared['input_sha256'],
        feature_contract_version='aegis-weather-features-v1',
        feature_contract_sha256=prepared['feature_contract_sha256'])
    if ready:
        result['forecast_request'] = dict(scenario='hourly', hourly_source_id=origin['id'], issued_at=issued.isoformat())
    return result
