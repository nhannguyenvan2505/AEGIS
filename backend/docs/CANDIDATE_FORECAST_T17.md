# T17 offline candidate handoff

[Báo cáo thí nghiệm](../../docs/FORECAST_EXPERIMENT_T17.md).
**Candidate chưa qua gate shadow**; FM03 runtime/pin/threshold giữ nguyên.
Không có HTTP route hoặc migration T17.

`forecast_demo/runtime/candidate_forecast_t17.py` cung cấp:

- `load_candidate(root,expected_manifest_sha256)`: kiểm bundle/runtime/dependency
  trước deserialize artifact thí nghiệm đã biết/pin.
- `forecast_candidate(manifest,artifact,label_free_payload)`: dùng gate FM03 và
  41 predictors, chặn source thực/label injection, abstain khi missing/unknown age.
- `calibrated_scores(artifact,predictor_mappings)`: exact whitelist, không nhận
  labels/metadata hoặc numeric bool/nonfinite.

Python trong ML venv, PYTHONPATH trỏ `D:/AEGIS/forecast_demo/runtime`:

```python
from pathlib import Path
from candidate_forecast_t17 import load_candidate, forecast_candidate
root = Path('D:/AEGIS/forecast_experiment_t17/run01/2026111701/candidate')
pin = 'e200452a1d500312122369f09a932eb3c49c2b06e442a638f81bf1697afc478a'
manifest, artifact = load_candidate(root, pin)
# payload: aegis-hourly-feature-input-v1, source=synthetic, không chứa label.
# result = forecast_candidate(manifest, artifact, payload)
```

Output có issue/target end/horizon72, predictor hash, score, threshold0,30,
predicted_event/insufficient reasons. Score semantics:
`calibrated_within_t17_simulator_not_field_probability`. Feature vector contract
giữ nguyên; calibration/score semantics là của candidate riêng. Luôn giữ
field_validated=false, deployment_activated=false; không tự tạo label/alert.

Load/replay được không có nghĩa được promote. T18 phải kiểm report qualification,
target/protocol/calibration semantics, shadow, rollback và history/explanation/
alerts trước khi thay pin. Qualification hiện=false nên không thay serving.
