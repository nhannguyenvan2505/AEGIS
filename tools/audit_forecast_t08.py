"""Read-only re-audit of T08 data, frozen models and earlier evidence hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'forecast_demo/runtime'))
from synthetic_forecast_data import build, audit_dataset
from serve_synthetic_forecast import MANIFEST_PIN
from feature_preparation import prepare
from pipeline import digest
sys.path.insert(0, str(ROOT/'frontend'))
from hourly_aggregation import aggregate


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)


def audit(run):
    checks = []
    verified = 0

    def hashes(base, mapping):
        nonlocal verified
        for name, expected in mapping.items():
            if sha(base/name) != expected:
                raise ValueError('Hash mismatch: '+str(base/name))
            verified += 1

    summary = read(ROOT/'forecast_experiments_t08/summary.json')
    hashes(ROOT, summary['files_sha256'])
    manifest = read(run/'experiment_manifest.json')
    hashes(ROOT, manifest['source_sha256'])
    protocol = read(run/'protocol.json')
    if sha(run/'protocol.json') != manifest['protocol_sha256']:
        raise ValueError('Frozen protocol mismatch')
    result, selection = read(run/'results.json'), read(run/'selection.json')
    hashes(run, {'results.json': manifest['results_sha256'], 'selection.json': manifest['selection_sha256']})
    dataset = run/'dataset'
    dataset_manifest = read(dataset/'dataset_manifest.json')
    hashes(dataset, dataset_manifest['files'])
    if sha(dataset/'dataset_manifest.json') != result['dataset_manifest_sha256']:
        raise ValueError('Dataset manifest not linked to result')
    checks.append('Protocol, source, original summary and dataset file hashes match')

    tables = ('inputs', 'metadata', 'feature_rows', 'labels', 'future_worlds')
    stored = {t: [json.loads(line) for line in (dataset/(t+'.synthetic.jsonl')).read_text().splitlines()] for t in tables}
    split = read(dataset/'split_manifest.json')
    regenerated = build(protocol['seed'], protocol['counts'])
    for table in tables:
        if stored[table] != regenerated[table]:
            raise ValueError('Regenerated table differs: '+table)
    stored.update(schema_version=dataset_manifest['schema_version'], contract=read(dataset/'contract.json'),
                  plan=split['plan'], registry=split['registry'])
    audit_result = audit_dataset(stored)
    if audit_result != {key: split[key] for key in audit_result}:
        raise ValueError('Recomputed split audit differs')
    if stored['plan'] != regenerated['plan'] or stored['registry'] != regenerated['registry']:
        raise ValueError('Regenerated split differs')
    checks.append('All five tables reproduce exactly from frozen seed; features, oracle labels and temporal/group audit recomputed')

    metadata = {r['sample_id']: r for r in stored['metadata']}
    features = {r['sample_id']: r['predictors'] for r in stored['feature_rows']}
    labels = {r['sample_id']: r['y'] for r in stored['labels']}
    units = {(r['plot_id'], r['season_id']): r for r in stored['registry']['units']}
    for meta in stored['metadata']:
        aliases = units[(meta['plot_id'], meta['season_id'])]['clusters']['shared_environment']
        if aliases != ['syn-environment-'+meta['cluster']]:
            raise ValueError('Bootstrap cluster disagrees with independence registry')
    for part, ids in split['partitions'].items():
        expected = result['cohort']['partitions'][part]
        if expected['ready'] != len(ids) or expected['ready_clusters'] != len({metadata[i]['cluster'] for i in ids}):
            raise ValueError('Cohort count differs')
    old = ROOT/'fm01_synthetic_forecast_20261105/run02/metadata.synthetic.jsonl'
    historical_ids = {json.loads(line)['sample_id'] for line in old.read_text().splitlines()}
    if historical_ids & set(metadata):
        raise ValueError('New seed reused historical sample IDs')
    checks.append('Bootstrap cluster matches registry; no historical sample-ID overlap')

    winner = min(selection['validation'], key=lambda n: (selection['validation'][n]['log_loss'], selection['validation'][n]['brier'], n))
    if winner != result['winner'] or winner != selection['winner']:
        raise ValueError('Winner does not follow declared validation ranking')
    predictions = read(run/'test_predictions.json')
    ids = split['partitions']['test']
    train_ids = split['partitions']['train']
    for name, artifact in result['artifacts'].items():
        # Check trusted recorded file hash before deserialization.
        hashes(run, {artifact['file']: artifact['sha256']})
        model = joblib.load(run/artifact['file'])
        rows = [r for r in predictions if r['model'] == name]
        if [r['sample_id'] for r in rows] != ids:
            raise ValueError('Test predictions have missing, duplicated or out-of-order IDs')
        columns = manifest['feature_orders']['weather' if name.startswith('weather_') else 'full']
        x = pd.DataFrame([features[i] for i in ids], columns=columns)
        scores = model.predict_proba(x)[:, 1]
        np.testing.assert_array_equal(scores, [r['score'] for r in rows])
        y = np.array([labels[i] for i in ids])
        if any(r['y'] != labels[r['sample_id']] or r['cluster'] != metadata[r['sample_id']]['cluster'] for r in rows):
            raise ValueError('Saved prediction target or cluster differs')
        if name == 'dummy':
            assert_close(scores, np.mean([labels[i] for i in train_ids]))
        else:
            transform = model.steps[0][1]
            numeric = transform.transformers_[0][2]
            train = pd.DataFrame([features[i] for i in train_ids], columns=columns)
            scaler = transform.named_transformers_['numeric']
            assert_close(scaler.mean_, train[numeric].mean().to_numpy())
            assert_close(scaler.var_, train[numeric].var(ddof=0).to_numpy())
            if scaler.n_samples_seen_ != len(train_ids):
                raise ValueError('Scaler count differs from train only')
        predicted = scores >= protocol['threshold']
        tn, fp = int(((y == 0) & ~predicted).sum()), int(((y == 0) & predicted).sum())
        fn, tp = int(((y == 1) & ~predicted).sum()), int(((y == 1) & predicted).sum())
        p = np.clip(scores, np.finfo(float).eps, 1-np.finfo(float).eps)
        ranks = pd.Series(scores).rank(method='average').to_numpy()
        positives, negatives = int(y.sum()), int((1-y).sum())
        independent = dict(log_loss=float(-(y*np.log(p)+(1-y)*np.log(1-p)).mean()),
                           brier=float(((scores-y)**2).mean()), accuracy=float((predicted == y).mean()),
                           recall=tp/(tp+fn), specificity=tn/(tn+fp), precision=tp/(tp+fp) if tp+fp else 0.,
                           roc_auc=float((ranks[y == 1].sum()-positives*(positives+1)/2)/(positives*negatives)))
        for key, value in independent.items():
            assert_close(value, result['test'][name][key])
        if result['test'][name]['confusion_matrix_0_1'] != [[tn, fp], [fn, tp]]:
            raise ValueError('Confusion matrix differs')
    checks.append('All three saved models reproduce 765 test scores; train-only scaler mean/variance and Dummy prior match')
    checks.append('Test log loss, Brier, AUC, accuracy, precision/recall/specificity and confusion independently recomputed')

    hourly = ROOT/'hourly_contract_v1'
    saved_hourly = read(hourly/'hourly.synthetic.json')
    replay_hourly = aggregate(read(hourly/'raw.synthetic.json'), read(hourly/'policy.synthetic.json'), saved_hourly['request'])
    if replay_hourly != saved_hourly:
        raise ValueError('T02 raw-to-hourly replay differs')
    t03_input = read(hourly/'t03_feature_input.synthetic.json')
    t03_features = read(hourly/'t03_features.synthetic.json')
    if prepare(t03_input) != t03_features:
        raise ValueError('T03 feature replay differs')
    t03 = read(hourly/'t03_summary.json')
    if digest(t03_input) != t03['feature_input_sha256'] or digest(t03_features) != t03['feature_output_sha256']:
        raise ValueError('T03 input/output semantic digest differs')
    t05_input = read(hourly/'t05_input.synthetic.json')
    t05_features = prepare(t05_input)['rows'][0]
    t05_forecast = read(hourly/'t05_forecast.synthetic.json')
    if (t05_features['predictors'] is not None or t05_forecast['status'] != 'insufficient_data'
            or t05_forecast['score'] is not None or t05_features['reasons'] != t05_forecast['reasons']):
        raise ValueError('T05 stored forecast disagrees with feature gate')
    checks.append('T02 raw-to-hourly and T03 input-to-features replay exactly; T05 insufficient forecast matches wetness gate')

    if sha(ROOT/'forecast_demo/bundle/manifest.json') != MANIFEST_PIN:
        raise ValueError('Serving manifest changed')
    serving = read(ROOT/'forecast_demo/bundle/manifest.json')
    hashes(ROOT/'forecast_demo/bundle', {serving['artifact']: serving['artifact_sha256']})
    prior = {}
    for name in ('t03', 't04', 't05', 't06'):
        value = read(ROOT/f'hourly_contract_v1/{name}_summary.json')
        hashes(ROOT/'hourly_contract_v1', value.get('artifacts_sha256', {}))
        for file, expected in value['source_sha256'].items():
            prior[file] = dict(task=name, sha256=expected)
    hashes(ROOT, {file: evidence['sha256'] for file, evidence in prior.items()})
    t07 = read(ROOT/'forecast_evaluation_t07/summary.json')
    hashes(ROOT, t07['source_sha256'])
    hashes(ROOT/'forecast_evaluation_t07/run02', t07['artifacts_sha256'])
    checks.append('T03–T06 latest source hashes, T04–T07 recorded artifact hashes and pinned serving model match')
    return dict(success=True, scope='Read-only T08 data audit, T02/T03/T05 replay and T03–T07 evidence hashes; no fitting or service deployment',
                run=str(run.relative_to(ROOT)), checked_file_hashes=verified,
                regenerated_rows=len(metadata), regenerated_tables=list(tables), checks=checks,
                field_validated=False, production_bundle_changed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT/'forecast_experiments_t08/run03')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new audit report path')
    result = audit(args.run.resolve())
    with args.out.open('x', encoding='utf-8') as file:
        json.dump(result, file, indent=2)
        file.write('\n')
    print(json.dumps(result))
