import importlib.util
import io
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location('diag_app', Path(__file__).resolve().parents[1] / 'app.py')
api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
from diagnosis import HeuristicGatekeeper  # app.py put the api directory on sys.path


class FakeGate:
    method = 'fake'
    def __init__(self, p): self.p = p
    def classify(self, pixels): return {'rice_probability': self.p, 'probabilities': [1 - self.p, self.p]}


class FakeDetector:
    device = 'cpu'; model_sha256 = 'a' * 64
    def __init__(self, boxes): self.boxes = boxes; self.calls = 0
    def predict(self, pixels, conf=0.25): self.calls += 1; return self.boxes


def textured_png(size=128):
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, (size, size, 3), dtype=np.uint8)
    stream = io.BytesIO(); Image.fromarray(arr).save(stream, format='PNG'); stream.seek(0)
    return stream


def flat_png(value):
    stream = io.BytesIO(); Image.new('RGB', (128, 128), (value,) * 3).save(stream, format='PNG'); stream.seek(0)
    return stream


BOX = lambda conf: [{'class_id': 0, 'confidence': conf, 'xyxy': [10, 10, 60, 60]}]


class DiagnoseTests(unittest.TestCase):
    def post(self, gate_p, boxes, image):
        det = FakeDetector(boxes)
        app = api.create_app(det, max_inflight=1, gatekeeper=FakeGate(gate_p))
        with app.test_client() as c:
            r = c.post('/v2/diagnose', data={'image': (image, 'x.png')})
        return r, det

    def test_non_rice_rejected_and_detector_never_runs(self):
        r, det = self.post(0.04, BOX(0.9), textured_png())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status'], 'rejected_non_rice')
        self.assertFalse(r.json['is_rice']); self.assertEqual(r.json['detections'], [])
        self.assertEqual(det.calls, 0)

    def test_ambiguous_gate_fails_closed(self):
        r, det = self.post(0.55, BOX(0.9), textured_png())
        self.assertEqual(r.json['status'], 'rejected_uncertain_scope'); self.assertEqual(det.calls, 0)

    def test_poor_quality_rejected_before_gate(self):
        for value, issue in [(5, 'too_dark'), (250, 'too_bright')]:
            r, det = self.post(0.99, BOX(0.9), flat_png(value))
            self.assertEqual(r.json['status'], 'rejected_poor_quality')
            self.assertIn(issue, r.json['quality']['issues']); self.assertEqual(det.calls, 0)

    def test_disease_detected(self):
        r, _ = self.post(0.97, BOX(0.8), textured_png())
        self.assertEqual(r.json['status'], 'disease_detected')
        self.assertEqual(r.json['primary_disease'], 'rice_blast'); self.assertEqual(len(r.json['detections']), 1)

    def test_low_confidence_is_uncertain_not_disease(self):
        r, _ = self.post(0.97, BOX(0.15), textured_png())
        self.assertEqual(r.json['status'], 'uncertain_lesion')
        self.assertEqual(r.json['detections'], []); self.assertEqual(len(r.json['uncertain_regions']), 1)

    def test_healthy_flagged_unvalidated(self):
        r, _ = self.post(0.97, [], textured_png())
        self.assertEqual(r.json['status'], 'healthy'); self.assertFalse(r.json['healthy_validated'])

    def test_missing_gate_weights_is_an_error_not_a_rejection(self):
        app = api.create_app(FakeDetector(BOX(0.9)), max_inflight=1, gatekeeper=HeuristicGatekeeper())
        with app.test_client() as c:
            r = c.post('/v2/diagnose', data={'image': (textured_png(), 'x.png')})
            self.assertEqual((r.status_code, r.json['error']['code']), (503, 'gatekeeper_unavailable'))
            h = c.get('/v2/health').json
            self.assertEqual(h['status'], 'degraded'); self.assertFalse(h['gatekeeper']['production_ready'])


if __name__ == '__main__': unittest.main()
