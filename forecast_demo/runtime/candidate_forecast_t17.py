"""Offline T17 synthetic candidate. Not registered with the serving worker."""
import hashlib
import json
from pathlib import Path
from datetime import datetime,timedelta

from weather_forecast import FEATURES,CONTRACT_SHA256,prepare_weather

RUNTIME_FILES=('candidate_forecast_t17.py','weather_forecast.py','feature_preparation.py','pipeline.py')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def calibrated_scores(artifact,records):
    import numpy as np
    import pandas as pd
    if not records: return np.array([],dtype=float)
    if any(not isinstance(r,dict) or set(r)!=set(FEATURES) for r in records):
        raise ValueError('Exact label-free FM03 predictor mapping required')
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.number)) for r in records for v in r.values()):
        raise ValueError('Numeric predictors required')
    frame=pd.DataFrame(records,columns=FEATURES)
    if not np.isfinite(frame.to_numpy(dtype=float)).all(): raise ValueError('Finite predictors required')
    if artifact['feature_order']!=list(FEATURES): raise ValueError('Artifact feature order mismatch')
    raw=artifact['base_model'].predict_proba(frame)[:,1]
    eps=artifact['epsilon']; raw=np.clip(raw,eps,1-eps)
    logits=np.log(raw/(1-raw)).reshape(-1,1)
    return artifact['calibrator'].predict_proba(logits)[:,1]


def load_candidate(root,expected_manifest_sha256):
    """Load only an experiment-owned trusted pickle after exact manifest/file pins."""
    root=Path(root); path=root/'manifest.json'
    if sha(path)!=expected_manifest_sha256: raise ValueError('Candidate manifest pin mismatch')
    m=json.loads(path.read_text(encoding='utf-8'))
    if (m['schema_version']!='aegis-t17-synthetic-candidate-v1' or m['source']!='synthetic'
            or m['field_validated'] is not False or m['deployment_activated'] is not False
            or m['feature_contract_sha256']!=CONTRACT_SHA256 or m['feature_order']!=list(FEATURES)
            or m['endpoint_protocol_sha256']!='07f5ae4b14ee7c724ac0a7851e1721b79cdede80876b546d44f7e1e2c937201a'
            or m['experiment_plan_bytes_sha256']!='82553d3243cefded1346cc2b0e8d19cda4e1d87d35a110a848086f33d14581c0'
            or m['artifact']!='candidate.joblib' or m['calibration_scope']!='t17_generator_only'):
        raise ValueError('Unsupported candidate scope/contract')
    if set(m['runtime_sha256'])!=set(RUNTIME_FILES): raise ValueError('Runtime file whitelist mismatch')
    if any(sha(Path(__file__).parent/f)!=m['runtime_sha256'][f] for f in RUNTIME_FILES):
        raise ValueError('Candidate runtime hash mismatch')
    if type(m['threshold']) not in (int,float) or not 0<=m['threshold']<=1: raise ValueError('Invalid candidate threshold')
    if sha(root/m['artifact'])!=m['artifact_sha256']: raise ValueError('Candidate artifact hash mismatch')
    from importlib.metadata import version
    import platform
    expected=m['environment']
    if platform.python_version()!=expected['python'] or any(version(package)!=expected[name] for package,name in
            (('scikit-learn','sklearn'),('numpy','numpy'),('pandas','pandas'),('joblib','joblib'))):
        raise ValueError('Candidate dependency versions changed')
    import joblib
    artifact=joblib.load(root/m['artifact'])
    if artifact['feature_order']!=m['feature_order'] or artifact['threshold']!=m['threshold']:
        raise ValueError('Candidate artifact metadata mismatch')
    return m,artifact


def forecast_candidate(m,artifact,payload):
    if payload.get('source')!='synthetic': raise ValueError('Candidate supports synthetic input only')
    prepared=prepare_weather(payload); result=[]
    for row in prepared['rows']:
        score=float(calibrated_scores(artifact,[row['predictors']])[0]) if row['predictors'] is not None else None
        result.append(dict(source='synthetic',field_validated=False,deployment_activated=False,
            model_version=m['model_version'],issued_at=row['issued_at'],
            horizon_hours=72,target_window_end=(datetime.fromisoformat(row['issued_at'])+timedelta(hours=72)).isoformat(),
            status='forecast_ready' if score is not None else 'insufficient_data',score=score,
            score_semantics='calibrated_within_t17_simulator_not_field_probability',threshold=m['threshold'],
            predicted_event=int(score>=m['threshold']) if score is not None else None,
            feature_contract_sha256=CONTRACT_SHA256,predictors_sha256=row['predictors_sha256'],reasons=row['reasons']))
    return result
