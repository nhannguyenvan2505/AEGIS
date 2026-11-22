"""Stage-2 evaluation: mAP@0.5, mAP@0.5:0.95, per-class P/R/F1, confusion matrix.

    python eval_detector.py --weights best.pt --data dataset.yaml --split test

Ultralytics writes confusion_matrix(.png) and PR curves to the run directory.
Evaluate on a split that is separated by field/source from training.
"""
import argparse
from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.001)  # low conf for a fair mAP
    a = ap.parse_args()
    m = YOLO(a.weights)
    r = m.val(data=a.data, split=a.split, imgsz=a.imgsz, conf=a.conf, iou=0.7, plots=True)
    print(f"mAP@0.5={r.box.map50:.4f}  mAP@0.5:0.95={r.box.map:.4f}  P={r.box.mp:.4f}  R={r.box.mr:.4f}")
    for i, idx in enumerate(r.box.ap_class_index):
        p, rc = float(r.box.p[i]), float(r.box.r[i])
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        print(f"{r.names[int(idx)]:15s} P={p:.4f} R={rc:.4f} F1={f1:.4f} AP50={r.box.ap50[i]:.4f} AP={r.box.ap[i]:.4f}")
    print(f"confusion matrix: {r.save_dir}/confusion_matrix.png")


if __name__ == "__main__":
    main()
