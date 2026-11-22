"""Evaluate the Stage-1 gatekeeper on a held-out folder and sweep accept thresholds.

    python eval_gatekeeper.py --weights best.pt --data DATA/test --max-fpr 0.01

Reports (per threshold): FPR on non_rice (non-rice wrongly ACCEPTED), correct-rejection
rate, rice precision / recall. Prints the lowest threshold meeting --max-fpr, which
becomes `rice_accept_min` in diagnosis.DEFAULTS. Use a test set that contains hard
negatives (weeds, other crops, water/soil, people, text) - not only easy ones.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from diagnosis import YoloClsGatekeeper, normalized_entropy  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def collect(root, label):
    return [(p, label) for p in sorted((Path(root) / label).rglob("*")) if p.suffix.lower() in EXT]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--max-fpr", type=float, default=0.01)
    ap.add_argument("--entropy-max", type=float, default=0.60)
    a = ap.parse_args()
    gate = YoloClsGatekeeper(a.weights)
    items = collect(a.data, "rice") + collect(a.data, "non_rice")
    y, p, h = [], [], []
    for path, label in items:
        out = gate.classify(np.asarray(Image.open(path).convert("RGB")))
        y.append(label == "rice"); p.append(out["rice_probability"]); h.append(normalized_entropy(out["probabilities"]))
    y, p, h = np.array(y), np.array(p), np.array(h)
    n_neg, n_pos = int((~y).sum()), int(y.sum())
    print(f"rice={n_pos} non_rice={n_neg}")
    print("thr   FPR(non_rice accepted)  correct_reject  rice_precision  rice_recall")
    chosen = None
    for thr in np.arange(0.50, 1.0, 0.05):
        acc = (p >= thr) & (h <= a.entropy_max)
        fpr = float((acc & ~y).sum() / max(n_neg, 1))
        prec = float((acc & y).sum() / max(acc.sum(), 1))
        rec = float((acc & y).sum() / max(n_pos, 1))
        print(f"{thr:.2f}  {fpr:8.4f}               {1 - fpr:8.4f}        {prec:8.4f}        {rec:8.4f}")
        if chosen is None and fpr <= a.max_fpr:
            chosen = round(float(thr), 2)
    print(f"\nlowest threshold with FPR <= {a.max_fpr}: {chosen}  (set rice_accept_min)" if chosen else "\nNO threshold meets target FPR: improve hard negatives / retrain")


if __name__ == "__main__":
    main()
