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
    ap.add_argument("--neg-root", help="non_rice_raw root (<category>/<source>/file): enables per-category report")
    ap.add_argument("--report-thr", type=float, default=0.80, help="rice_accept_min used for the per-category report")
    a = ap.parse_args()
    gate = YoloClsGatekeeper(a.weights)
    items = collect(a.data, "rice") + collect(a.data, "non_rice")
    cat_of = {}
    if a.neg_root:  # gate_v1 file name is "<source>__<original name>" with spaces -> "_"
        for f in Path(a.neg_root).rglob("*"):
            r = f.relative_to(a.neg_root).parts
            if f.suffix.lower() in EXT and len(r) >= 3:
                cat_of[f"{r[1]}__{f.name}".replace(" ", "_")] = r[0]
    y, p, h, names = [], [], [], []
    for path, label in items:
        names.append((path, label))
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
    if a.neg_root:
        acc = (p >= a.report_thr) & (h <= a.entropy_max)
        cats = {}
        for (path, label), ok, pr in zip(names, acc, p):
            if label == "non_rice":
                cats.setdefault(cat_of.get(path.name, "unknown"), []).append((bool(ok), float(pr)))
        print(f"\nper-category non_rice at rice_accept_min={a.report_thr} (false accept = wrongly accepted as rice)")
        print(f"{'category':16s}{'n':>6s}{'false_accept':>14s}{'FPR':>8s}{'max P(rice)':>13s}{'mean P(rice)':>14s}")
        for c, v in sorted(cats.items()):
            fa = sum(o for o, _ in v)
            print(f"{c:16s}{len(v):6d}{fa:14d}{fa / len(v):8.4f}{max(q for _, q in v):13.3f}{np.mean([q for _, q in v]):14.3f}")
        miss = [(float(pr), path.name) for (path, label), ok, pr in zip(names, acc, p) if label == "rice" and not ok]
        print(f"\nrice rejected at this threshold: {len(miss)}/{n_pos}")
        for pr, n in sorted(miss)[:10]:
            print(f"  P(rice)={pr:.3f}  {n}")
    print(f"\nlowest threshold with FPR <= {a.max_fpr}: {chosen}  (set rice_accept_min)" if chosen else "\nNO threshold meets target FPR: improve hard negatives / retrain")


if __name__ == "__main__":
    main()
