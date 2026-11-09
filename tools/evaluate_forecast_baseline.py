"""T07 diagnostics of the frozen FM-02 artifact on its original FM-01 split."""
import argparse
import copy
import csv
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score, log_loss,
                             precision_score, recall_score, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'forecast_demo/runtime'))
from feature_preparation import FEATURE_NAMES
from pipeline import digest, stamp
from serve_synthetic_forecast import MANIFEST_PIN, checked_bytes
from synthetic_baseline import forecast, read, sha
from synthetic_forecast_data import CONTRACT, audit_dataset

PLAN = dict(threshold=.5, calibration_bins=5, cluster_bootstrap_replicates=2000,
            bootstrap_seed=20261107, missing_hours=[1, 6, 24, 120], stress_partition='validation',
            model_fitting=False, threshold_selection=False, calibration_fitting=False,
            evaluation_scope='Historical synthetic validation/test, already inspected during development')


def calibration(y, scores, bins=5):
    y, scores = np.asarray(y), np.asarray(scores)
    membership = np.minimum((scores*bins).astype(int), bins-1)
    rows = []
    error = 0.
    for index in range(bins):
        selected = membership == index
        count = int(selected.sum())
        mean = float(scores[selected].mean()) if count else None
        rate = float(y[selected].mean()) if count else None
        if count:
            error += count/len(y)*abs(mean-rate)
        rows.append(dict(lower=index/bins, upper=(index+1)/bins, count=count,
                         mean_score=mean, observed_event_rate=rate))
    return dict(bins=rows, expected_calibration_error=error)


def metrics(y, scores):
    y, scores = np.asarray(y), np.asarray(scores)
    predicted = scores >= PLAN['threshold']
    return dict(n=len(y), positive_count=int(y.sum()), prevalence=float(y.mean()),
        predicted_positive_count=int(predicted.sum()), mean_score=float(scores.mean()),
        accuracy=float(accuracy_score(y, predicted)), balanced_accuracy=float(balanced_accuracy_score(y, predicted)),
        precision=float(precision_score(y, predicted, zero_division=0)),
        recall=float(recall_score(y, predicted, zero_division=0)),
        specificity=float(recall_score(y, predicted, pos_label=0, zero_division=0)),
        f1=float(f1_score(y, predicted, zero_division=0)), roc_auc=float(roc_auc_score(y, scores)),
        average_precision=float(average_precision_score(y, scores)),
        log_loss=float(log_loss(y, scores, labels=[0, 1])),
        brier=float(brier_score_loss(y, scores)), confusion_matrix_0_1=confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        calibration=calibration(y, scores, PLAN['calibration_bins']))


def paired_cluster_intervals(y, scores, dummy, clusters):
    """Paired row-weighted deltas, resampling entire shared-weather clusters."""
    y, scores, dummy = np.asarray(y), np.asarray(scores), np.asarray(dummy)
    labels = sorted(set(clusters))
    indices = [np.flatnonzero(np.asarray(clusters) == label) for label in labels]
    rng = np.random.default_rng(PLAN['bootstrap_seed'])
    draws = rng.integers(0, len(labels), size=(PLAN['cluster_bootstrap_replicates'], len(labels)))
    counts = np.array([len(index) for index in indices])
    eps = np.finfo(float).eps
    def loss(probabilities):
        p = np.clip(probabilities, eps, 1-eps)
        return -(y*np.log(p)+(1-y)*np.log(1-p))
    differences = dict(log_loss=loss(scores)-loss(dummy),
                       brier=(scores-y)**2-(dummy-y)**2,
                       accuracy=((scores >= .5) == y).astype(float)-((dummy >= .5) == y).astype(float))
    result = dict(cluster_count=len(labels), replicates=len(draws), seed=PLAN['bootstrap_seed'], deltas={})
    for name, values in differences.items():
        totals = np.array([values[index].sum() for index in indices])
        samples = totals[draws].sum(axis=1)/counts[draws].sum(axis=1)
        lower, upper = np.quantile(samples, [.025, .975])
        result['deltas'][name] = dict(baseline_minus_dummy=float(values.mean()),
                                    percentile_95=[float(lower), float(upper)])
    return result


def missing_sensitivity(model, inputs, worlds, ids, original_scores):
    cases = []
    for field in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet'):
        for count in PLAN['missing_hours']:
            abstained = 0
            for sample_id in ids:
                payload = copy.deepcopy(inputs[sample_id])
                for row in payload['series'][0]['telemetry'][-count:]:
                    row[field] = None
                row = forecast(model, payload)[0]
                if row['status'] != 'insufficient_data' or row['score'] is not None:
                    raise ValueError('Missing history failed to abstain')
                abstained += 1
            cases.append(dict(field=field, missing_hours=count, trials=len(ids), abstained=abstained))
    restored = future_invariant = 0
    for sample_id, original in zip(ids, original_scores):
        payload = copy.deepcopy(inputs[sample_id])
        issued = stamp(payload['issue_times'][0])
        payload['series'][0]['telemetry'][-1]['available_at'] = (issued+timedelta(minutes=1)).isoformat()
        if forecast(model, payload)[0]['score'] is not None:
            raise ValueError('Late receipt was used before availability')
        payload['issue_times'] = [(issued+timedelta(minutes=1)).isoformat()]
        if not np.isclose(forecast(model, payload)[0]['score'], original, atol=1e-12, rtol=0):
            raise ValueError('Restored history changed score')
        restored += 1
        future = copy.deepcopy(inputs[sample_id])
        future['series'][0]['telemetry'].extend(worlds[sample_id]['future_telemetry'])
        if not np.isclose(forecast(model, future)[0]['score'], original, atol=1e-12, rtol=0):
            raise ValueError('Future observations changed past score')
        future_invariant += 1
    return dict(partition='validation', cases=cases, missing_trials=sum(r['trials'] for r in cases),
                late_receipt_abstained=restored, restored_identical=restored, future_invariant=future_invariant)


def evaluate(dataset, bundle, reference):
    manifest = json.loads(checked_bytes(bundle/'manifest.json', MANIFEST_PIN))
    if sha(reference/'manifest.json') != MANIFEST_PIN:
        raise ValueError('Reference run is not the pinned FM-02 bundle')
    if sha(dataset/'dataset_manifest.json') != manifest['dataset_manifest_sha256']:
        raise ValueError('Dataset manifest differs from frozen training data')
    if sha(dataset/'split_manifest.json') != manifest['split_manifest_sha256']:
        raise ValueError('Split manifest differs from frozen training split')
    if manifest['feature_order'] != list(FEATURE_NAMES) or manifest['threshold'] != PLAN['threshold']:
        raise ValueError('Feature order or fixed threshold mismatch')
    for package, installed in [('sklearn', sklearn.__version__), ('numpy', np.__version__),
                               ('pandas', pd.__version__), ('joblib', joblib.__version__)]:
        if installed != manifest['runtime'][package]:
            raise ValueError('Runtime version mismatch: '+package)
    if platform.python_version_tuple()[:2] != tuple(manifest['runtime']['python'].split('.')[:2]):
        raise ValueError('Python major/minor version mismatch')
    dataset_manifest = read(dataset/'dataset_manifest.json')
    for name, expected in dataset_manifest['files'].items():
        if Path(name).name != name or sha(dataset/name) != expected:
            raise ValueError('FM-01 artifact hash mismatch')
    split = read(dataset/'split_manifest.json')
    data = dict(schema_version=dataset_manifest['schema_version'], contract=read(dataset/'contract.json'),
                plan=split['plan'], registry=split['registry'])
    for name in ('inputs', 'metadata', 'feature_rows', 'labels', 'future_worlds'):
        data[name] = [json.loads(line) for line in (dataset/(name+'.synthetic.jsonl')).read_text(encoding='utf-8').splitlines()]
    audit = audit_dataset(data)
    if audit['partitions'] != split['partitions']:
        raise ValueError('Recomputed membership differs from fixed split')
    model_bytes = checked_bytes(bundle/'baseline.joblib', manifest['artifact_sha256'])
    model = joblib.load(BytesIO(model_bytes))
    reloaded = joblib.load(BytesIO(model_bytes))
    features = {r['sample_id']: r['predictors'] for r in data['feature_rows']}
    labels = {r['sample_id']: r['y'] for r in data['labels']}
    metadata = {r['sample_id']: r for r in data['metadata']}
    inputs = {r['sample_id']: r['input'] for r in data['inputs']}
    worlds = {r['sample_id']: r for r in data['future_worlds']}
    def frame(ids):
        return pd.DataFrame([features[sample_id] for sample_id in ids], columns=FEATURE_NAMES)
    train_ids = audit['partitions']['train']
    train = frame(train_ids)
    prior = float(np.mean([labels[sample_id] for sample_id in train_ids]))
    transform = model.named_steps['columntransformer']
    numeric = [name for name in FEATURE_NAMES if name not in CONTRACT['categorical_features']]
    scaler = transform.named_transformers_['numeric']
    np.testing.assert_allclose(scaler.mean_, train[numeric].to_numpy(dtype=float).mean(axis=0), atol=1e-12, rtol=0)
    np.testing.assert_allclose(scaler.var_, train[numeric].to_numpy(dtype=float).var(axis=0), atol=1e-12, rtol=0)
    if int(scaler.n_samples_seen_) != len(train_ids):
        raise ValueError('Scaler fitted row count differs from train')
    encoder = transform.named_transformers_['category']
    for name, categories in zip(CONTRACT['categorical_features'], encoder.categories_):
        if list(categories) != sorted(train[name].unique().tolist()):
            raise ValueError('Encoded categories differ from train')
    old_predictions = read(reference/'evaluation_predictions.json')
    for row in old_predictions:
        if (set(row) != {'partition', 'sample_id', 'y', 'score'} or type(row['y']) is not int
                or type(row['score']) not in (float, int) or not np.isfinite(row['score'])
                or not 0 <= row['score'] <= 1):
            raise ValueError('Invalid reference prediction')
    old = {(r['partition'], r['sample_id']): r for r in old_predictions}
    expected_keys = {(part, sample_id) for part in ('validation', 'test') for sample_id in audit['partitions'][part]}
    if set(old) != expected_keys or len(old) != len(old_predictions):
        raise ValueError('Reference predictions have unexpected membership')
    old_metrics = read(reference/'metrics.json')
    result = dict(plan=PLAN, model_version=manifest['model_version'], model_manifest_sha256=MANIFEST_PIN,
        model_artifact_sha256=manifest['artifact_sha256'], dataset_manifest_sha256=sha(dataset/'dataset_manifest.json'),
        split_manifest_sha256=sha(dataset/'split_manifest.json'), dummy_train_prior=prior,
        counts=dict(total=audit['total'], ready=audit['selected'], excluded=len(audit['excluded']),
                    partitions={part: len(ids) for part, ids in audit['partitions'].items()}, class_counts=audit['class_counts']),
        preprocessing=dict(train_rows=len(train_ids), scaler_matches_train=True, categories_match_train=True,
                           constant_train_features=[name for name in FEATURE_NAMES if train[name].nunique(dropna=False) == 1]),
        runtime=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__, joblib=joblib.__version__),
        partitions={}, reference_max_score_delta=0., reload_scores_identical=True, reference_metrics_match=True)
    rows = []
    for part in ('validation', 'test'):
        ids = audit['partitions'][part]
        x = frame(ids)
        y = np.array([labels[sample_id] for sample_id in ids])
        scores = model.predict_proba(x)[:, 1]
        np.testing.assert_array_equal(scores, reloaded.predict_proba(x)[:, 1])
        previous = np.array([old[(part, sample_id)]['score'] for sample_id in ids])
        if any(old[(part, sample_id)]['y'] != labels[sample_id] for sample_id in ids):
            raise ValueError('Reference target differs from frozen label')
        np.testing.assert_allclose(scores, previous, atol=1e-12, rtol=0)
        result['reference_max_score_delta'] = max(result['reference_max_score_delta'], float(np.max(np.abs(scores-previous))))
        dummy = np.full(len(y), prior)
        models = dict(baseline=metrics(y, scores), dummy=metrics(y, dummy))
        for name, metric in models.items():
            if set(old_metrics[part][name]) != {'n', 'accuracy', 'roc_auc', 'log_loss', 'confusion_matrix_0_1'}:
                raise ValueError('Invalid reference metric fields')
            for key, value in old_metrics[part][name].items():
                np.testing.assert_allclose(metric[key], value, atol=1e-12, rtol=0)
        result['partitions'][part] = dict(models=models, coverage=len(ids)/sum(m['partition'] == part for m in data['metadata']),
            paired_cluster_intervals=paired_cluster_intervals(y, scores, dummy, [metadata[i]['cluster'] for i in ids]))
        for sample_id, target, score in zip(ids, y, scores):
            prediction = int(score >= .5)
            p = float(np.clip(score, np.finfo(float).eps, 1-np.finfo(float).eps))
            rows.append(dict(partition=part, sample_id=sample_id, cluster=metadata[sample_id]['cluster'],
                y=int(target), score=float(score), predicted_event=prediction,
                outcome=('TP' if target else 'FP') if prediction else ('FN' if target else 'TN'),
                log_loss=float(-np.log(p if target else 1-p)), brier=float((score-target)**2)))
        if part == 'validation':
            result['sensitivity'] = missing_sensitivity(model, inputs, worlds, ids, scores)
    coefficients = model.named_steps['logisticregression'].coef_[0]
    names = transform.get_feature_names_out()
    result['largest_absolute_coefficients'] = [dict(feature=str(names[i]), coefficient=float(coefficients[i]))
                                              for i in np.argsort(-np.abs(coefficients))[:15]]
    result['error_counts'] = {part: {outcome: sum(r['partition'] == part and r['outcome'] == outcome for r in rows)
                                   for outcome in ('TN', 'FP', 'FN', 'TP')} for part in ('validation', 'test')}
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=ROOT/'forecast_demo/bundle')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new output directory')
    result, rows = evaluate(args.dataset, args.bundle, args.reference)
    args.out.mkdir(parents=True, exist_ok=False)
    for name, value in [('evaluation.json', result), ('evaluation_plan.json', PLAN)]:
        with (args.out/name).open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
    with (args.out/'predictions.csv').open('x', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = dict(success=True, source_sha256=sha(Path(__file__)),
        reference_sha256={name: sha(args.reference/name) for name in ('manifest.json', 'metrics.json', 'evaluation_predictions.json')},
        outputs_sha256={p.name: sha(p) for p in args.out.iterdir()}, model_fitting_performed=False)
    with (args.out/'verification.json').open('x', encoding='utf-8') as output:
        json.dump(verification, output, indent=2)
    print(json.dumps(dict(success=True, reference_max_score_delta=result['reference_max_score_delta'],
                         reference_metrics_match=result['reference_metrics_match'], counts=result['counts'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
