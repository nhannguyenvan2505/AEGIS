"""Train the Stage-1 rice/non_rice gatekeeper (YOLO11 classification).

Dataset layout (ImageFolder, split BY SOURCE/FIELD, never by image):
    DATA/train/{rice,non_rice}/*.jpg   DATA/val/...   DATA/test/...

Usage:
    python train_gatekeeper.py --data D:/AEGIS-AI/datasets/gate_v1 --epochs 60
Then calibrate thresholds with eval_gatekeeper.py before setting AEGIS_GATE_WEIGHTS.
"""
import argparse
from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="yolo11n-cls.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--project", default="experiments/gatekeeper")
    ap.add_argument("--name", default="gate_v1")
    a = ap.parse_args()
    YOLO(a.model).train(
        data=a.data, epochs=a.epochs, imgsz=a.imgsz, project=a.project, name=a.name, seed=0,
        label_smoothing=0.1,            # softer logits -> better-behaved OOD entropy
        hsv_h=0.015, hsv_s=0.5, hsv_v=0.4,  # controlled lighting variation
        degrees=15, fliplr=0.5, flipud=0.0, scale=0.4, translate=0.1, erasing=0.3,
        patience=15,
    )


if __name__ == "__main__":
    main()
