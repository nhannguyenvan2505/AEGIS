"""FM-02 synthetic demo baseline. Train once with fixed settings on the FM-01 split."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from feature_preparation import FEATURE_NAMES, prepare
from synthetic_forecast_data import CONTRACT, SCHEMA, audit_dataset
from pipeline import digest, stamp
from datetime import timedelta


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, allow_nan=False)


def forecast(model, payload):
    if payload.get('source') != 'synthetic':
        raise ValueError('Synthetic baseline requires synthetic hourly input')
    result = []
    for row in prepare(payload)['rows']:
        score = None
        if row['predictors'] is not None:
            frame = pd.DataFrame([row['predictors']], columns=FEATURE_NAMES)
            score = float(model.predict_proba(frame)[0, 1])
        result.append(dict(source='synthetic', field_validated=False, plot_id=row['plot_id'],
            season_id=row['season_id'], issued_at=row['issued_at'], horizon_hours=72,
            target_window_end=(stamp(row['issued_at'])+timedelta(hours=72)).isoformat(),
            status='insufficient_data' if score is None else 'forecast_ready',
            reasons=row['reasons'], predictors_sha256=row['predictors_sha256'],
            score=score, score_semantics='uncalibrated_model_score',
            predicted_event=None if score is None else int(score >= .5)))
    return result


def train(dataset, out):
    manifest = read(dataset/'dataset_manifest.json')
    split = read(dataset/'split_manifest.json')
    tables = ('inputs', 'metadata', 'feature_rows', 'labels', 'future_worlds')
    for file in ['contract.json', 'split_manifest.json', *(t+'.synthetic.jsonl' for t in tables),
                 'input_ready.synthetic.json', 'input_insufficient.synthetic.json']:
        if sha(dataset/file) != manifest['files'][file]:
            raise ValueError('FM-01 input hash mismatch: '+file)
    data = dict(schema_version=manifest['schema_version'], contract=read(dataset/'contract.json'),
                plan=split['plan'], registry=split['registry'])
    if data['schema_version'] != SCHEMA or manifest['source'] != 'synthetic':
        raise ValueError('Expected FM-01 synthetic dataset')
    for t in tables:
        data[t] = [json.loads(line) for line in (dataset/(t+'.synthetic.jsonl')).read_text(encoding='utf-8').splitlines()]
    audit = audit_dataset(data)
    if audit['partitions'] != split['partitions'] or not audit['both_classes_per_partition']:
        raise ValueError('Invalid FM-01 membership or class support')
    features = {r['sample_id']: r['predictors'] for r in data['feature_rows']}
    labels = {r['sample_id']: r['y'] for r in data['labels']}
    def xy(part):
        ids = audit['partitions'][part]
        return pd.DataFrame([features[i] for i in ids], columns=FEATURE_NAMES), [labels[i] for i in ids]
    cats = CONTRACT['categorical_features']
    transform = ColumnTransformer([
        ('numeric', StandardScaler(), [x for x in FEATURE_NAMES if x not in cats]),
        ('category', OneHotEncoder(handle_unknown='ignore'), cats)])
    model = make_pipeline(transform, LogisticRegression(C=1., max_iter=1000, random_state=42))
    x, y = xy('train')
    model.fit(x, y)
    dummy = DummyClassifier(strategy='prior').fit(x, y)
    out.mkdir(parents=True, exist_ok=False)
    path = out/'baseline.joblib'
    joblib.dump(model, path)
    # Deserialize only the file just produced by this invocation.
    restored = joblib.load(path)
    metrics, predictions = {}, []
    for part in ('validation', 'test'):
        x, y = xy(part)
        scores = restored.predict_proba(x)[:, 1]
        np.testing.assert_array_equal(scores, model.predict_proba(x)[:, 1])
        metrics[part] = {}
        for name, probabilities in [('baseline', scores), ('dummy', dummy.predict_proba(x)[:, 1])]:
            predicted = probabilities >= .5
            metrics[part][name] = dict(n=len(y), accuracy=float(accuracy_score(y, predicted)),
                roc_auc=float(roc_auc_score(y, probabilities)), log_loss=float(log_loss(y, probabilities)),
                confusion_matrix_0_1=confusion_matrix(y, predicted, labels=[0, 1]).tolist())
        predictions.extend(dict(partition=part, sample_id=i, y=label, score=float(score))
            for i, label, score in zip(audit['partitions'][part], y, scores))
    histories = {r['sample_id']: r['input'] for r in data['inputs']}
    worlds = {r['sample_id']: r for r in data['future_worlds']}
    for i in audit['partitions']['test']:
        past = histories[i]
        future = copy.deepcopy(past)
        future['series'][0]['telemetry'].extend(worlds[i]['future_telemetry'])
        if forecast(restored, past) != forecast(restored, future):
            raise RuntimeError('Future observations changed prediction')
    ready = forecast(restored, read(dataset/'input_ready.synthetic.json'))
    missing = forecast(restored, read(dataset/'input_insufficient.synthetic.json'))
    if ready[0]['score'] is None or missing[0]['score'] is not None:
        raise RuntimeError('Unexpected feature readiness behavior')
    write(out/'example_predictions.json', dict(ready=ready, insufficient=missing))
    write(out/'evaluation_predictions.json', predictions)
    write(out/'metrics.json', metrics)
    write(out/'manifest.json', dict(schema_version='aegis-synthetic-baseline-v1', source='synthetic',
        model_version='fm02-logistic-v1', field_validated=False, target_kind=CONTRACT['target_kind'],
        lookback_hours=120, horizon_hours=72, threshold=.5, fit_partition='train',
        dataset_manifest_sha256=sha(dataset/'dataset_manifest.json'), split_manifest_sha256=sha(dataset/'split_manifest.json'),
        feature_order=list(FEATURE_NAMES), feature_contract_sha256=CONTRACT['predictor_contract_sha256'],
        artifact=path.name, artifact_sha256=sha(path), train_count=len(audit['partitions']['train']),
        runtime=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__,
                     pandas=pd.__version__, joblib=joblib.__version__),
        reload_predictions_identical=True, future_invariance_test_rows=len(audit['partitions']['test'])))
    return metrics


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--dataset', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    if args.out.exists():
        cli.error('Choose a new output directory')
    print(json.dumps(train(args.dataset, args.out)))
