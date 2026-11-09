"""Predeclared synthetic T08 experiments. Never modifies the serving bundle."""
import argparse
import copy
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'forecast_demo/runtime'))
from feature_preparation import FEATURE_NAMES, prepare
from pipeline import feature_row, stamp
from synthetic_baseline import sha
from synthetic_forecast_data import build, export
from evaluate_forecast_baseline import metrics, paired_cluster_intervals, PLAN

WEATHER_NAMES = tuple(n for n in FEATURE_NAMES if n.startswith(('temp_', 'rh_')) or n == 'crop_age_days')
CATEGORIES = ['region', 'rice_variety', 'planting_method', 'season_status']
PROTOCOL_PIN = '84b9a72c8167111f9a01443fb12405525dbcf3cb6098c023e0913a64d1cc27f3'


def write(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, allow_nan=False)
        file.write('\n')


def experimental_features(payload, variant):
    """Validate the label-free envelope before applying the versioned weather gate."""
    prepared = prepare(payload)
    if len(prepared['rows']) != 1:
        raise ValueError('One series and issue required')
    if variant == 'full':
        return prepared['rows'][0]['predictors']
    if variant != 'weather':
        raise ValueError('Unknown feature contract')
    row = feature_row(payload['series'][0], stamp(payload['issue_times'][0]))
    coverage = row['coverage']['120']
    if coverage['temp'] != 120 or coverage['rh'] != 120 or row['features']['crop_age_days'] is None:
        return None
    return {n: row['features'][n] for n in WEATHER_NAMES}


def model_for(name, seed, protocol):
    if name == 'dummy':
        return DummyClassifier(strategy='prior')
    names = FEATURE_NAMES if name.startswith('full_') else WEATHER_NAMES
    cats = [n for n in CATEGORIES if n in names]
    preprocessing = ColumnTransformer([
        ('numeric', StandardScaler(), [n for n in names if n not in cats]),
        ('category', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cats)])
    estimator = (HistGradientBoostingClassifier(random_state=seed, **protocol['hgb'])
                 if name.endswith('_hgb') else LogisticRegression(
                     C=float(name.rsplit('_', 1)[1]), max_iter=protocol['logistic']['max_iter'], random_state=seed))
    return make_pipeline(preprocessing, estimator)


def select(validation):
    return min(validation, key=lambda n: (validation[n]['log_loss'], validation[n]['brier'], n))


def stress(models, data, ids):
    inputs = {r['sample_id']: r['input'] for r in data['inputs']}
    worlds = {r['sample_id']: r for r in data['future_worlds']}
    labels = {r['sample_id']: r['y'] for r in data['labels']}
    wet_vectors = {'full': [], 'weather': []}
    base_vectors = {'full': [], 'weather': []}
    counts = {name: dict(rows=len(ids), wet_null_scored=0, temperature_null_abstained=0,
                         unknown_age_abstained=0, future_invariant=0) for name in models if name != 'dummy'}
    for sid in ids:
        original = inputs[sid]
        wet, temp, age, future = [copy.deepcopy(original) for _ in range(4)]
        for row in wet['series'][0]['telemetry']:
            row['leaf_wet'] = None
        temp['series'][0]['telemetry'][-1]['air_temperature_c'] = None
        for rev in age['series'][0]['context_revisions']:
            rev['profile']['sown_on'] = None
            rev['profile']['transplanted_on'] = None
        future['series'][0]['telemetry'].extend(worlds[sid]['future_telemetry'])
        for variant in ('full', 'weather'):
            base = experimental_features(original, variant)
            wet_features = experimental_features(wet, variant)
            temp_missing = experimental_features(temp, variant) is None
            age_missing = experimental_features(age, variant) is None
            if base != experimental_features(future, variant):
                raise AssertionError('Future changed as-of features')
            base_vectors[variant].append(base)
            wet_vectors[variant].append(wet_features)
            for name in counts:
                if name.startswith(variant+'_'):
                    counts[name]['temperature_null_abstained'] += int(temp_missing)
                    counts[name]['unknown_age_abstained'] += int(age_missing)
                    counts[name]['future_invariant'] += 1
    for name in counts:
        variant = name.split('_')[0]
        selected = [i for i, vector in enumerate(wet_vectors[variant]) if vector is not None]
        if selected:
            columns = FEATURE_NAMES if variant == 'full' else WEATHER_NAMES
            frame = pd.DataFrame([wet_vectors[variant][i] for i in selected], columns=columns)
            scores = models[name].predict_proba(frame)[:, 1]
            original = pd.DataFrame([base_vectors[variant][i] for i in selected], columns=columns)
            np.testing.assert_array_equal(scores, models[name].predict_proba(original)[:, 1])
            counts[name]['wet_null_scored'] = len(selected)
            counts[name]['wet_null_metrics'] = metrics([labels[ids[i]] for i in selected], scores)
            counts[name]['wet_null_score_delta'] = 0.
    return counts


def run(protocol_path, out):
    # This runner implements one frozen experiment, not an arbitrary tuning API.
    if sha(protocol_path) != PROTOCOL_PIN:
        raise ValueError('Protocol differs from frozen T08; declare a new experiment version')
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=False)
    # Persist exact protocol bytes before generating new draws or fitting anything.
    (out/'protocol.json').write_bytes(protocol_path.read_bytes())
    write(out/'protocol_frozen.json', dict(sha256=sha(out/'protocol.json'), phase='before_generation_and_fit'))
    seed = protocol['seed']
    data = build(seed, protocol['counts'])
    manifest = export(data, out/'dataset')
    print(json.dumps(dict(phase='dataset_exported', rows=manifest['rows'], ready=manifest['ready'])), flush=True)
    audit = data['audit']
    features = {r['sample_id']: r['predictors'] for r in data['feature_rows']}
    labels = {r['sample_id']: r['y'] for r in data['labels']}
    metadata = {r['sample_id']: r for r in data['metadata']}

    def xy(part, name):
        ids = audit['partitions'][part]
        names = WEATHER_NAMES if name.startswith('weather_') else FEATURE_NAMES
        return pd.DataFrame([features[i] for i in ids], columns=names), np.array([labels[i] for i in ids])

    models, validation = {}, {}
    for name in protocol['candidates']:
        model = model_for(name, seed, protocol)
        x, y = xy('train', name)
        model.fit(x, y)
        x, y = xy('validation', name)
        scores = model.predict_proba(x)[:, 1]
        validation[name] = metrics(y, scores)
        models[name] = model
        print(json.dumps(dict(phase='validation', candidate=name, log_loss=validation[name]['log_loss'])), flush=True)
    winner = select(validation)
    selection = dict(winner=winner, validation=validation,
                     protocol_sha256=sha(out/'protocol.json'), dataset_manifest_sha256=sha(out/'dataset/dataset_manifest.json'),
                     phase='frozen_before_test_scoring', selection_uses_test=False)
    write(out/'selection.json', selection)
    # No model/threshold changes are allowed below this boundary.
    test, predictions, artifacts = {}, [], {}
    selected_models = {n: models[n] for n in dict.fromkeys([winner, 'full_lr_1', 'dummy'])}
    for name, model in selected_models.items():
        path = out/(name+'.joblib')
        joblib.dump(model, path)
        restored = joblib.load(path)  # only our newly written local artifact
        x, y = xy('test', name)
        scores = restored.predict_proba(x)[:, 1]
        np.testing.assert_array_equal(scores, model.predict_proba(x)[:, 1])
        test[name] = metrics(y, scores)
        artifacts[name] = dict(file=path.name, sha256=sha(path), reload_predictions_identical=True)
        predictions.extend(dict(model=name, sample_id=sid, cluster=metadata[sid]['cluster'], y=int(label), score=float(score))
                           for sid, label, score in zip(audit['partitions']['test'], y, scores))
    winner_scores = [r['score'] for r in predictions if r['model'] == winner]
    dummy_scores = [r['score'] for r in predictions if r['model'] == 'dummy']
    _, y = xy('test', winner)
    PLAN['bootstrap_seed'] = protocol['bootstrap']['seed']
    PLAN['cluster_bootstrap_replicates'] = protocol['bootstrap']['replicates']
    intervals = paired_cluster_intervals(y, winner_scores, dummy_scores,
                                         [metadata[i]['cluster'] for i in audit['partitions']['test']])
    stress_results = stress(models, data, audit['partitions']['validation'])
    result = dict(source='synthetic', field_validated=False, winner=winner, threshold=protocol['threshold'],
        protocol_sha256=sha(out/'protocol.json'), selection_sha256=sha(out/'selection.json'),
        dataset_manifest_sha256=sha(out/'dataset/dataset_manifest.json'),
        cohort=dict(total=audit['total'], ready=audit['selected'],
                    partitions={p: dict(total=sum(r['partition'] == p for r in data['metadata']), ready=len(ids),
                                        ready_clusters=len({metadata[i]['cluster'] for i in ids}))
                                for p, ids in audit['partitions'].items()}, class_counts=audit['class_counts']),
        validation=validation, test=test, paired_test_intervals=intervals,
        validation_stress=stress_results, artifacts=artifacts,
        production_bundle_changed=False, calibration_fitting=False, limitations=protocol['limitations'])
    write(out/'test_predictions.json', predictions)
    write(out/'results.json', result)
    source_paths = [Path(__file__), ROOT/'tools/evaluate_forecast_baseline.py',
                    *(ROOT/'forecast_demo/runtime'/f for f in (
                        'synthetic_forecast_data.py', 'pipeline.py', 'feature_preparation.py', 'cluster_partition.py'))]
    write(out/'experiment_manifest.json', dict(
        protocol_sha256=sha(out/'protocol.json'), results_sha256=sha(out/'results.json'),
        selection_sha256=sha(out/'selection.json'),
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        runtime=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                     sklearn=sklearn.__version__, joblib=joblib.__version__),
        feature_orders=dict(full=list(FEATURE_NAMES), weather=list(WEATHER_NAMES)),
        train_sample_ids=audit['partitions']['train'],
        stress_measurement='Future feature equality for all models; actual batched wet-null scores for weather models',
        serving_manifest_sha256=sha(ROOT/'forecast_demo/bundle/manifest.json')))
    print(json.dumps(dict(winner=winner, test=test)), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT/'forecast_experiments_t08/protocol.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.protocol, args.out)
