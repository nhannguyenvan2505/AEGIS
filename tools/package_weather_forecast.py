"""Package the preselected T09 model only after all frozen acceptance gates pass."""
import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'forecast_demo/runtime'))
from weather_forecast import CONTRACT, CONTRACT_SHA256, FEATURES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def package(run, out):
    acceptance = read(run/'acceptance.json')
    protocol = read(run/'protocol.json')
    if acceptance['passed'] is not True or acceptance['failures']:
        raise ValueError('Acceptance failed; activation refused')
    if sha(run/'protocol.json') != acceptance['protocol_sha256']:
        raise ValueError('Protocol hash mismatch')
    for path, expected in acceptance['source_sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError('Validated source changed: '+path)
    if acceptance['feature_contract_sha256'] != CONTRACT_SHA256:
        raise ValueError('Feature contract changed')
    if [s['seed'] for s in acceptance['seeds']] != protocol['seeds']:
        raise ValueError('Seed coverage mismatch')
    for seed in acceptance['seeds']:
        if set(seed['stress']) != set(protocol['stress']['cases']) or set(seed['metrics']) != set(protocol['quality_scenarios']):
            raise ValueError('Missing acceptance scenarios')
        for case in protocol['quality_scenarios']:
            value = seed['metrics'][case]
            if not (value['candidate']['log_loss'] < value['dummy']['log_loss']
                    and value['candidate']['brier'] < value['dummy']['brier']
                    and value['candidate']['roc_auc'] >= .65):
                raise ValueError('Quality gate failed')
        if seed['degradation'] > .03 or any(r['passed'] != r['trials'] or r['trials'] != 8 for r in seed['stress'].values()):
            raise ValueError('Stress gate failed')
    if (set(acceptance['intervals']) != set(protocol['quality_scenarios'])
            or any(row['deltas']['log_loss']['percentile_95'][1] >= 0 for row in acceptance['intervals'].values())):
        raise ValueError('Pooled uncertainty gate failed')
    model = run/str(protocol['deployment_seed'])/'model.joblib'
    audit = read(model.parent/'audit.json')
    expected = acceptance['primary_model']
    if str(model.relative_to(run)) != expected['path'] or sha(model) != expected['sha256'] or sha(model) != audit['model_sha256']:
        raise ValueError('Preselected artifact mismatch')
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(model, out/'model.joblib')
    manifest = dict(schema_version='aegis-weather-model-bundle-v1', model_version='fm03-weather-logistic-v1',
        artifact='model.joblib', artifact_sha256=sha(out/'model.joblib'), source='synthetic', field_validated=False,
        synthetic_training_authorized=True, field_training_approved=False,
        feature_contract=CONTRACT, feature_contract_sha256=CONTRACT_SHA256, feature_order=list(FEATURES),
        threshold=.5, score_semantics='uncalibrated_model_score', lookback_hours=120, horizon_hours=72,
        fit_partition='train', train_count=len(audit['train_ids']), deployment_seed=protocol['deployment_seed'],
        validated_seeds=protocol['seeds'], protocol_sha256=sha(run/'protocol.json'),
        runtime=dict(python=platform.python_version(), sklearn=version('scikit-learn'),
                     numpy=version('numpy'), pandas=version('pandas'), joblib=version('joblib')),
        acceptance_sha256=sha(run/'acceptance.json'), predictions_sha256=sha(run/'predictions.json'),
        runtime_source_sha256=sha(ROOT/'forecast_demo/runtime/weather_forecast.py'),
        runtime_sources={name: sha(ROOT/'forecast_demo/runtime'/name)
                         for name in ('weather_forecast.py', 'feature_preparation.py', 'pipeline.py')})
    with (out/'manifest.json').open('x', encoding='utf-8') as file:
        json.dump(manifest, file, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps(dict(manifest_sha256=sha(out/'manifest.json'), feature_contract_sha256=CONTRACT_SHA256)))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package(args.run, args.out)
