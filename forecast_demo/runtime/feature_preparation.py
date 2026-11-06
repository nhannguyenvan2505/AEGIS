"""Label-free hourly feature preparation; no model, score, training or DB access."""
import argparse
import copy
from datetime import timedelta
import json
import math
from pathlib import Path

from pipeline import SPEC, digest, feature_row, identifier, load, stamp, validate_series

INPUT_SCHEMA = 'aegis-hourly-feature-input-v1'
OUTPUT_SCHEMA = 'aegis-feature-preparation-v1'
WINDOWS = (6, 24, 72, 120)
LOOKBACK = 120


def feature_names():
    names = []
    for hours in WINDOWS:
        for variable in ('temp', 'rh'):
            names.extend(f'{variable}_{stat}_{hours}h' for stat in ('coverage', 'mean', 'min', 'max', 'std'))
        names.extend(f'{stat}_{hours}h' for stat in (
            'wet_coverage', 'wet_observed_hours', 'longest_observed_wet_run',
            'wet_run_left_censored'))
    return tuple(names) + ('region', 'rice_variety', 'planting_method', 'crop_age_days', 'season_status')


FEATURE_NAMES = feature_names()
CONTRACT = {
    'version': 'aegis-hourly-features-v1',
    'feature_names': list(FEATURE_NAMES),
    'lookback_hours': LOOKBACK,
    'feature_windows_hours': list(WINDOWS),
    'readiness': '120 valid available hourly values per variable and known calendar crop age',
    'temperature_unit': 'degC', 'relative_humidity_unit': 'percent',
    'wetness_semantics': 'observed whole-hour boolean, never inferred from RH or a single point',
    'std_definition': 'population standard deviation',
    'preprocessing': 'none; categorical values and nulls are not encoded or imputed',
    'status': 'feature_preparation_only_not_a_forecast',
}


def _prepare(payload):
    if SPEC['lookback_hours'] != LOOKBACK or SPEC['feature_windows_hours'] != list(WINDOWS):
        raise ValueError('Pipeline feature windows changed; review and version the feature contract')
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'source', 'series', 'issue_times'}:
        raise ValueError('Expected label-free hourly feature input envelope')
    if payload['schema_version'] != INPUT_SCHEMA:
        raise ValueError('Unsupported feature input schema')
    if payload['source'] not in ('synthetic', 'field_observed'):
        raise ValueError('Only declared synthetic or field_observed hourly input is supported')
    if not isinstance(payload['series'], list) or not payload['series']:
        raise ValueError('Nonempty series list required')
    if not isinstance(payload['issue_times'], list) or not payload['issue_times']:
        raise ValueError('Nonempty issue_times list required')
    issued_times = [stamp(t) for t in payload['issue_times']]
    if len(set(issued_times)) != len(issued_times):
        raise ValueError('Duplicate issue time')
    rows, groups = [], set()
    for series in payload['series']:
        if not isinstance(series, dict) or set(series) != {
            'plot_id', 'season_id', 'device_id', 'telemetry', 'context_revisions'
        }:
            raise ValueError('Series accepts identity, hourly telemetry and context only; labels are not inputs')
        for key in ('plot_id', 'season_id', 'device_id'):
            identifier(series[key])
        key = (series['plot_id'], series['season_id'])
        if key in groups:
            raise ValueError('One device per plot-season; do not silently mix sensor series')
        groups.add(key)
        # Reuse sensor/context validation without requesting any disease outcome.
        validate_series(dict(series, surveys=[], interventions=[]))
        for issued in sorted(issued_times):
            result = feature_row(series, issued)
            features = result['features']
            if set(features) != set(FEATURE_NAMES):
                raise ValueError('Pipeline feature keys changed; review the feature contract')
            for value in features.values():
                if type(value) is float and not math.isfinite(value):
                    raise ValueError('Non-finite derived feature')
            reasons = []
            for variable, count in result['coverage'][str(LOOKBACK)].items():
                if count != LOOKBACK:
                    reasons.append(dict(code='incomplete_hourly_coverage', variable=variable,
                                        expected_hours=LOOKBACK, available_valid_hours=count,
                                        missing_hours=LOOKBACK-count))
            if features['crop_age_days'] is None:
                reasons.append(dict(code='unknown_calendar_crop_age'))
            ready = not reasons
            if ready != (result['feature_status'] == 'ready'):
                raise ValueError('Pipeline readiness changed; review the feature contract')
            # Only this mapping may later enter preprocessing/model code.
            # IDs, reasons, hashes, context revisions and coverage diagnostics stay outside it.
            predictors = {name: features[name] for name in FEATURE_NAMES} if ready else None
            window_end = issued.replace(minute=0, second=0, microsecond=0)
            rows.append(dict(
                plot_id=series['plot_id'], season_id=series['season_id'], device_id=series['device_id'],
                issued_at=issued.isoformat(), feature_window_end=window_end.isoformat(),
                feature_window_start=(window_end-timedelta(hours=LOOKBACK)).isoformat(),
                feature_status='ready' if ready else 'insufficient_data',
                predictors=predictors,
                predictors_sha256=digest({'contract_sha256': digest(CONTRACT), 'predictors': predictors}) if ready else None,
                coverage=result['coverage'], reasons=reasons,
                context_revision=result['context_revision'], context_sha256=result['context_sha256'],
            ))
    return dict(schema_version=OUTPUT_SCHEMA, source=payload['source'],
                provenance_status='source_declared_not_independently_verified',
                feature_contract=copy.deepcopy(CONTRACT), feature_contract_sha256=digest(CONTRACT),
                input_sha256=digest(payload), rows=rows,
                model_available=False, training_performed=False, training_approved=False,
                limits=['Ready means features are complete, not that a model or disease forecast is available',
                        'No disease label, risk score, probability or forecast is produced',
                        'Raw point observations need a separately validated hourly aggregation',
                        'Synthetic input proves software behavior only; field source is a declaration',
                        'Use only row.predictors as future model input; never flatten the response'])


def prepare(payload):
    """Return features and readiness diagnostics, using only input available at t.

    Does not authorize training or certify provenance. Input is never modified.
    Extra fields (including labels/surveys/rule outputs) are rejected.
    """
    try:
        return _prepare(payload)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('Malformed hourly feature input') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        parser.error('Choose a new output file; input and historical output are preserved')
    try:
        result = prepare(load(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    except (ValueError, OSError, RecursionError) as exc:
        parser.exit(2, 'Feature preparation rejected: '+str(exc)+'\n')
    print(json.dumps(dict(rows=len(result['rows']),
                          ready=sum(r['feature_status'] == 'ready' for r in result['rows']),
                          model_available=False, training_performed=False)))


if __name__ == '__main__':
    main()
