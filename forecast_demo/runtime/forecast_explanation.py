"""Exact additive explanation of a pinned binary logistic pipeline; no fitting."""
import math

import numpy as np
import pandas as pd

from feature_preparation import FEATURE_NAMES, prepare
from weather_forecast import FEATURES, prepare_weather
from pipeline import digest


def explain(model, payload, model_pin, model_version, weather):
    if payload.get('source') != 'synthetic':
        raise ValueError('Only synthetic explanations supported')
    prepared = prepare_weather(payload) if weather else prepare(payload)
    if len(prepared['rows']) != 1:
        raise ValueError('Exactly one series and issue required')
    row = prepared['rows'][0]
    result = dict(schema_version='aegis-forecast-explanation-v1', source='synthetic', field_validated=False,
        plot_id=row['plot_id'], season_id=row['season_id'], issued_at=row['issued_at'],
        model_manifest_sha256=model_pin, model_version=model_version,
        input_sha256=digest(payload), predictors_sha256=row['predictors_sha256'],
        feature_contract_sha256=prepared['feature_contract_sha256'],
        score_semantics='uncalibrated_model_score', contribution_units='logit',
        feature_space='transformed_model_inputs', interpretation='model_contributions_not_disease_causes',
        reasons=row['reasons'], intercept=None, logit=None, sum_contributions=None,
        reconstructed_score=None, score=None, reconstruction_error=None, terms=[])
    if row['predictors'] is None:
        return dict(result, status='insufficient_data')
    if model is None:
        return dict(status='model_unavailable')
    estimator, preprocessing = model.steps[-1][1], model[:-1]
    if list(estimator.classes_) != [0, 1] or estimator.coef_.shape[0] != 1:
        raise ValueError('Only binary 0/1 logistic artifact supported')
    frame = pd.DataFrame([row['predictors']], columns=FEATURES if weather else FEATURE_NAMES)
    transformed = preprocessing.transform(frame)
    if hasattr(transformed, 'toarray'):
        transformed = transformed.toarray()
    vector = np.asarray(transformed)[0]
    names = list(preprocessing.get_feature_names_out())
    weights = estimator.coef_[0]
    if len(vector) != len(names) or len(weights) != len(names):
        raise ValueError('Transformed feature order differs')
    intercept = float(estimator.intercept_[0])
    terms = [dict(feature=str(name), transformed_value=float(value), coefficient=float(weight),
                  contribution_logit=float(value*weight)) for name, value, weight in zip(names, vector, weights)]
    total = math.fsum(t['contribution_logit'] for t in terms)
    logit = intercept+total
    reconstructed = 1/(1+math.exp(-logit)) if logit >= 0 else math.exp(logit)/(1+math.exp(logit))
    score = float(model.predict_proba(frame)[0, 1])
    decision = float(model.decision_function(frame)[0])
    if not all(math.isfinite(v) for v in [intercept, total, logit, score, reconstructed, decision]):
        raise ValueError('Non-finite explanation')
    if abs(logit-decision) > 1e-12 or abs(reconstructed-score) > 1e-12:
        raise ValueError('Explanation does not reconstruct pinned prediction')
    return dict(result, status='explained', intercept=intercept, logit=logit,
        sum_contributions=total, reconstructed_score=reconstructed, score=score,
        reconstruction_error=abs(reconstructed-score), terms=terms)
