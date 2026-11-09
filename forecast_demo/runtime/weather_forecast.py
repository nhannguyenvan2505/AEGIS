"""Versioned label-free weather features and synthetic FM-03 inference."""
from datetime import timedelta

from feature_preparation import FEATURE_NAMES, prepare
from pipeline import digest, feature_row, stamp

FEATURES = tuple(n for n in FEATURE_NAMES if n.startswith(('temp_', 'rh_')) or n == 'crop_age_days')
CONTRACT = dict(version='aegis-weather-features-v1', feature_names=list(FEATURES),
    lookback_hours=120, feature_windows_hours=[6, 24, 72, 120],
    readiness='120 valid available temperature/RH hours and known calendar crop age',
    wetness='Excluded; point observations never infer whole-hour wetness',
    missing_numeric='Abstain; no imputation', score_semantics='uncalibrated_model_score')
CONTRACT_SHA256 = digest(CONTRACT)


def prepare_weather(payload):
    result = prepare(payload)  # reuse strict validation and as-of semantics
    series = {(s['plot_id'], s['season_id']): s for s in payload['series']}
    for row in result['rows']:
        item = feature_row(series[(row['plot_id'], row['season_id'])], stamp(row['issued_at']))
        row['reasons'] = [r for r in row['reasons'] if r.get('variable') != 'wet']
        row['feature_status'] = 'insufficient_data' if row['reasons'] else 'ready'
        row['predictors'] = None if row['reasons'] else {n: item['features'][n] for n in FEATURES}
        row['predictors_sha256'] = None if row['reasons'] else digest(dict(
            contract_sha256=CONTRACT_SHA256, predictors=row['predictors']))
    result['feature_contract'] = CONTRACT.copy()
    result['feature_contract_sha256'] = CONTRACT_SHA256
    return result


def forecast_weather(model, payload):
    if payload.get('source') != 'synthetic':
        raise ValueError('FM03 is authorized for synthetic input only')
    result = []
    for row in prepare_weather(payload)['rows']:
        score = None
        if row['predictors'] is not None:
            import pandas as pd
            score = float(model.predict_proba(pd.DataFrame([row['predictors']], columns=FEATURES))[0, 1])
        result.append(dict(source='synthetic', field_validated=False, plot_id=row['plot_id'],
            season_id=row['season_id'], issued_at=row['issued_at'], horizon_hours=72,
            target_window_end=(stamp(row['issued_at'])+timedelta(hours=72)).isoformat(),
            status='insufficient_data' if score is None else 'forecast_ready', reasons=row['reasons'],
            predictors_sha256=row['predictors_sha256'], score=score,
            score_semantics='uncalibrated_model_score', predicted_event=None if score is None else int(score >= .5),
            feature_contract_version=CONTRACT['version'], feature_contract_sha256=CONTRACT_SHA256))
    return result
