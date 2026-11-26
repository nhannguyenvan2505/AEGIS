"""AEGIS two-stage diagnosis pipeline (schema 2.0).

Stage 0  image quality  - classical, deterministic checks (blur / dark / bright / no subject)
Stage 1  gatekeeper     - is this a rice plant at all?  Anything not clearly rice is rejected.
Stage 2  detector       - lesion localisation + disease class, only on accepted images.

Design rule: every branch that is not positively "rice + usable" returns a rejection
with an empty detection list. The service never guesses a disease name for an image
it could not validate.
"""
import hashlib
import json
import logging
import math
import os
import threading
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "2.0"
MANIFEST_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "blur_laplacian_var_min": 60.0,
    "dark_mean_max": 40.0,
    "bright_mean_min": 225.0,
    "subject_std_min": 12.0,
    "rice_accept_min": 0.80,       # P(rice) needed to enter stage 2
    "non_rice_reject_min": 0.70,   # P(non_rice) needed to claim "definitely not rice"
    "entropy_max": 0.60,           # normalised entropy ceiling (OOD signal)
    "disease_conf_min": 0.25,      # reliable detection
    "uncertain_conf_min": 0.10,    # below this a box is noise
}

MESSAGES = {
    "rejected_poor_quality": "Ảnh chưa đủ chất lượng để phân tích ({issues}). Vui lòng chụp lại rõ nét, đủ sáng.",
    "rejected_non_rice": "Ảnh không phải cây lúa. Vui lòng chụp lại ảnh cây lúa để chẩn đoán bệnh.",
    "rejected_uncertain_scope": "Không đủ chắc chắn đây là cây lúa nên hệ thống từ chối chẩn đoán. Vui lòng chụp cận lá/khóm lúa, nền đơn giản hơn.",
    "healthy": "Không phát hiện vùng bệnh trên cây lúa ở ngưỡng hiện tại. Đây chưa phải xác nhận cây khỏe; hãy tiếp tục theo dõi.",
    "uncertain_lesion": "Có dấu hiệu bất thường nhưng độ tin cậy chưa đạt ngưỡng kết luận bệnh. Cần kiểm tra thực địa hoặc chụp lại cận cảnh.",
    "disease_detected": "Phát hiện vùng nghi bệnh trên cây lúa; cần xác minh thực địa.",
}

ISSUE_LABELS_VI = {
    "blur": "ảnh mờ", "too_dark": "quá tối",
    "too_bright": "quá sáng", "no_clear_subject": "không có đối tượng rõ ràng",
}


# ---------------------------------------------------------------- stage 0
ANALYSIS_SIDE = 512


def analysis_grid(pixels):
    """Evenly spaced pixels with the long side at ANALYSIS_SIDE; smaller images are returned as they are.

    The sharpness limit only means something on a fixed grid: an integer step (long side // 512) left
    the grid 512 to 640 points wide depending on the upload size, so phone-sized photos were judged
    blurrier than the same picture at 1024 px. At 1024 and 2048 px this picks every 2nd and 4th
    pixel, exactly as before. No averaging: that would change the values the limit was chosen on.
    """
    long_side = max(pixels.shape[:2])
    if long_side <= ANALYSIS_SIDE:
        return pixels

    def picks(length):
        count = -(-length * ANALYSIS_SIDE // long_side)  # round up, so a last partial step is kept
        return np.arange(count) * long_side // ANALYSIS_SIDE

    return pixels[np.ix_(picks(pixels.shape[0]), picks(pixels.shape[1]))]


def assess_quality(pixels, t=DEFAULTS):
    """pixels: HxWx3 uint8 RGB. Returns {ok, issues, metrics}."""
    img = np.asarray(analysis_grid(np.asarray(pixels)), dtype=np.float32)
    gray = img @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:])
    metrics = {
        "laplacian_variance": round(float(lap.var()), 2) if lap.size else 0.0,
        "mean_luminance": round(float(gray.mean()), 2),
        "luminance_std": round(float(gray.std()), 2),
    }
    issues = []
    if metrics["laplacian_variance"] < t["blur_laplacian_var_min"]:
        issues.append("blur")
    if metrics["mean_luminance"] < t["dark_mean_max"]:
        issues.append("too_dark")
    if metrics["mean_luminance"] > t["bright_mean_min"]:
        issues.append("too_bright")
    if metrics["luminance_std"] < t["subject_std_min"]:
        issues.append("no_clear_subject")
    return {"ok": not issues, "issues": issues, "metrics": metrics}


# ---------------------------------------------------------------- stage 1
def normalized_entropy(probs):
    p = np.clip(np.asarray(probs, dtype=np.float64), 1e-12, 1.0)
    p = p / p.sum()
    return float(-(p * np.log(p)).sum() / math.log(len(p))) if len(p) > 1 else 0.0


class HeuristicGatekeeper:
    """Fallback when no trained gatekeeper checkpoint is configured.

    Uses an excess-green vegetation fraction. It cannot tell rice from other green
    plants, so it deliberately NEVER reports high rice probability (cap 0.75 < accept
    threshold): every image is then rejected as uncertain unless it is clearly not
    vegetation. Exists so the service fails closed instead of guessing.
    """
    method = "heuristic_fallback"
    version = "none"

    def classify(self, pixels):
        img = np.asarray(pixels[::4, ::4], dtype=np.float32) / 255.0
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        green = float(((2 * g - r - b) > 0.08).mean())
        rice_prob = min(0.75, green)  # capped: heuristic cannot confirm rice
        return {"rice_probability": rice_prob, "probabilities": [1 - rice_prob, rice_prob]}


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(manifest):
    return json.loads((MANIFEST_DIR / manifest).read_text(encoding="utf-8"))


def pinned_sha256(manifest):
    """SHA-256 of the released artifact named by a manifest next to this file."""
    return read_manifest(manifest)["sha256"]


def check_pin(digest, manifest, label):
    """True for the released artifact. Anything else stops startup unless explicitly allowed."""
    if digest == pinned_sha256(manifest):
        return True
    if os.environ.get("AEGIS_ALLOW_UNPINNED_MODELS") == "1":
        logging.getLogger(__name__).warning("%s SHA-256 %s is not the one in %s; running unpinned",
                                            label, digest[:12], manifest)
        return False
    raise RuntimeError(f"{label} SHA-256 {digest[:12]} differs from {manifest}. Restore the released file, "
                       "or set AEGIS_ALLOW_UNPINNED_MODELS=1 to try a candidate.")


class YoloClsGatekeeper:
    """Ultralytics classification checkpoint with classes {non_rice, rice}."""
    method = "yolo_cls"
    pinned = False  # only build_gatekeeper() checks the release pin; evaluation scripts load candidates

    def __init__(self, weights, imgsz=224):
        from ultralytics import YOLO
        weights = Path(weights)
        if not weights.is_file():
            raise FileNotFoundError(f"Gatekeeper checkpoint missing: {weights}")
        self.sha256 = file_sha256(weights)
        self.model = YOLO(str(weights))
        names = {int(k): v for k, v in self.model.names.items()}
        if set(names.values()) != {"non_rice", "rice"}:
            raise ValueError(f"Gatekeeper classes must be exactly rice/non_rice, got {names}")
        self.rice_index = next(i for i, n in names.items() if n == "rice")
        self.imgsz = imgsz
        self.version = weights.name
        # Ultralytics builds the predictor on first use outside its own lock; concurrent first
        # calls would each build one around the same model.
        self.lock = threading.Lock()

    def classify(self, pixels):
        with self.lock:
            res = self.model.predict(source=np.ascontiguousarray(pixels[:, :, ::-1]), imgsz=self.imgsz, verbose=False)[0]
        probs = res.probs.data.cpu().numpy().astype(np.float64)
        return {"rice_probability": float(probs[self.rice_index]), "probabilities": probs.tolist()}


DEFAULT_GATE_WEIGHTS = Path(__file__).resolve().parents[1] / "experiments/gatekeeper/gate_v1b/best.pt"


def build_gatekeeper():
    """AEGIS_GATE_WEIGHTS, else the provisioned default file, else the always-rejecting heuristic."""
    weights = os.environ.get("AEGIS_GATE_WEIGHTS") or (str(DEFAULT_GATE_WEIGHTS) if DEFAULT_GATE_WEIGHTS.is_file() else None)
    if not weights:
        return HeuristicGatekeeper()
    if not Path(weights).is_file():
        raise FileNotFoundError(f"Gatekeeper checkpoint missing: {weights}")
    digest = file_sha256(weights)  # checked before the file is unpickled
    pinned = check_pin(digest, "gatekeeper.json", "Gatekeeper weights")
    gate = YoloClsGatekeeper(weights)
    if gate.sha256 != digest or file_sha256(weights) != digest:
        raise RuntimeError("Gatekeeper checkpoint changed during loading")
    gate.pinned = pinned
    if pinned:
        gate.version = read_manifest("gatekeeper.json")["release"]
    return gate


# ---------------------------------------------------------------- pipeline
class DiagnosisPipeline:
    def __init__(self, detector, gatekeeper, thresholds=None):
        self.detector, self.gatekeeper = detector, gatekeeper
        self.t = {**DEFAULTS, **(thresholds or {})}

    def describe(self):
        return {"gatekeeper": {"method": self.gatekeeper.method, "version": getattr(self.gatekeeper, "version", "none"),
                               "sha256": getattr(self.gatekeeper, "sha256", None),
                               "pinned": getattr(self.gatekeeper, "pinned", False),
                               "production_ready": self.gatekeeper.method != "heuristic_fallback"},
                "thresholds": self.t}

    def run(self, pixels):
        height, width = pixels.shape[:2]
        base = {"schema_version": SCHEMA_VERSION, "image": {"width": width, "height": height, "orientation": "exif_corrected"},
                "detections": [], "uncertain_regions": [], "decision_support_only": True}

        quality = assess_quality(pixels, self.t)
        base["quality"] = quality
        if not quality["ok"]:
            issues = ", ".join(ISSUE_LABELS_VI[i] for i in quality["issues"])
            return {**base, "status": "rejected_poor_quality", "is_rice": None, "confidence": None,
                    "message": MESSAGES["rejected_poor_quality"].format(issues=issues)}

        gate = self.gatekeeper.classify(pixels)
        p_rice = float(gate["rice_probability"])
        entropy = normalized_entropy(gate["probabilities"])
        base["gatekeeper"] = {"method": self.gatekeeper.method, "rice_probability": round(p_rice, 4),
                              "normalized_entropy": round(entropy, 4),
                              "version": getattr(self.gatekeeper, "version", "none"),
                              "sha256": getattr(self.gatekeeper, "sha256", None)}

        if p_rice < self.t["rice_accept_min"] or entropy > self.t["entropy_max"]:
            if (1 - p_rice) >= self.t["non_rice_reject_min"] and entropy <= self.t["entropy_max"]:
                return {**base, "status": "rejected_non_rice", "is_rice": False,
                        "confidence": round(1 - p_rice, 4), "message": MESSAGES["rejected_non_rice"]}
            return {**base, "status": "rejected_uncertain_scope", "is_rice": None,
                    "confidence": round(max(p_rice, 1 - p_rice), 4), "message": MESSAGES["rejected_uncertain_scope"]}

        reliable, uncertain = self._detect(pixels, width, height)
        if reliable:
            status, conf = "disease_detected", reliable[0]["confidence"]
        elif uncertain:
            status, conf = "uncertain_lesion", uncertain[0]["confidence"]
        else:
            status, conf = "healthy", round(p_rice, 4)
        out = {**base, "status": status, "is_rice": True, "confidence": conf, "message": MESSAGES[status],
               "detections": reliable, "uncertain_regions": uncertain}
        if status == "disease_detected":
            out["primary_disease"] = reliable[0]["class_name"]
        if status == "healthy":
            out["healthy_validated"] = False  # no labelled healthy-rice evaluation exists yet
        return out

    def _detect(self, pixels, width, height):
        from_names = getattr(self.detector, "class_names", None) or {0: "rice_blast", 1: "brown_spot", 2: "sheath_blight"}
        raw = self.detector.predict(pixels, conf=self.t["uncertain_conf_min"])
        reliable, uncertain = [], []
        for p in raw:
            xyxy = np.asarray(p["xyxy"], dtype=float)
            conf = float(p["confidence"])
            if p["class_id"] not in from_names or xyxy.shape != (4,) or not np.isfinite(xyxy).all() or not math.isfinite(conf):
                raise ValueError("Invalid model output")
            left, right = np.clip(xyxy[[0, 2]], 0, width)
            top, bottom = np.clip(xyxy[[1, 3]], 0, height)
            if right <= left or bottom <= top or conf < self.t["uncertain_conf_min"]:
                continue
            item = {"class_id": int(p["class_id"]), "class_name": from_names[p["class_id"]], "confidence": round(conf, 6),
                    "bbox_xyxy": [round(float(v), 2) for v in (left, top, right, bottom)],
                    "bbox_normalized_xyxy": [round(float(v), 6) for v in (left / width, top / height, right / width, bottom / height)]}
            (reliable if conf >= self.t["disease_conf_min"] else uncertain).append(item)
        key = lambda d: -d["confidence"]
        return sorted(reliable, key=key), sorted(uncertain, key=key)
