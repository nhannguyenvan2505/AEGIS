"""Check the fixed V4 checkpoint identity without importing ML or loading weights."""
import argparse
import hashlib
import json
from pathlib import Path

MODEL_VERSION = 'aegis-yolo11n-v4-50epochs'
EXPECTED_SHA256 = '1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a'
CHECKPOINT_RELATIVE = 'AEGIS-AI/experiments/yolo/baseline_v4_50epochs/weights/best.pt'


def check(checkpoint):
    path = Path(checkpoint).absolute()
    result = dict(checkpoint=str(path), model_version=MODEL_VERSION, expected_sha256=EXPECTED_SHA256,
                  checkpoint_loaded=False, inference_performed=False, transfer_rights_verified=False)
    try:
        if not path.is_file():
            return dict(result, ok=False, code='checkpoint_missing'), 2
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        actual = digest.hexdigest()
    except OSError:
        return dict(result, ok=False, code='checkpoint_unreadable'), 2
    if actual != EXPECTED_SHA256:
        return dict(result, ok=False, code='checkpoint_hash_mismatch', actual_sha256=actual), 3
    return dict(result, ok=True, code='checkpoint_verified', actual_sha256=actual), 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path,
                        default=Path(__file__).resolve().parents[2] / CHECKPOINT_RELATIVE,
                        help='Read-only path to the authorized V4 file; does not select a different model')
    args = parser.parse_args()
    result, code = check(args.checkpoint)
    print(json.dumps(result, ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
