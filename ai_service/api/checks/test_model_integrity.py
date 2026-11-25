"""Startup SHA-256 pinning and health reporting. No real model is loaded."""
import hashlib
import importlib.util
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch  # noqa: F401  (import before patch.dict, which would otherwise unload and re-import it)

spec = importlib.util.spec_from_file_location('integrity_app', Path(__file__).resolve().parents[1] / 'app.py')
api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
import diagnosis  # app.py put the api directory on sys.path


class FakeYOLO:
    loaded = 0

    def __init__(self, weights):
        FakeYOLO.loaded += 1
        gate = Path(weights).name.startswith('gate')
        self.names = {0: 'non_rice', 1: 'rice'} if gate else dict(api.CLASS_NAMES)


class FakeDetector:
    device = 'cpu'; model_sha256 = 'a' * 64
    def predict(self, pixels, conf=0.25): return []


class FakeGate:
    method = 'fake'; version = 'gate-test'; sha256 = 'c' * 64; pinned = True
    def classify(self, pixels): return {'rice_probability': 0.99, 'probabilities': [0.01, 0.99]}


class StartupPinTests(unittest.TestCase):
    """A file that is not the released artifact must stop the service before it is loaded."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        FakeYOLO.loaded = 0
        fake = types.ModuleType('ultralytics'); fake.YOLO = FakeYOLO
        for patcher in (patch.dict(sys.modules, {'ultralytics': fake}), patch.dict(os.environ)):
            patcher.start(); self.addCleanup(patcher.stop)
        os.environ.pop('AEGIS_ALLOW_UNPINNED_MODELS', None)
        os.environ.pop('AEGIS_GATE_WEIGHTS', None)

    def file(self, name, content=b'not the released weights'):
        path = Path(self.temp.name) / name
        path.write_bytes(content)
        return path

    def test_replaced_gatekeeper_weights_are_refused_before_loading(self):
        os.environ['AEGIS_GATE_WEIGHTS'] = str(self.file('gate.pt'))
        with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
            diagnosis.build_gatekeeper()
        self.assertEqual(FakeYOLO.loaded, 0)

    def test_replaced_default_detector_weights_are_refused_before_loading(self):
        with patch.object(api, 'WEIGHTS', self.file('best.pt')):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                api.Detector()
        self.assertEqual(FakeYOLO.loaded, 0)

    def test_explicit_candidate_detector_is_allowed_and_marked_unpinned(self):
        detector = api.Detector(weights=self.file('candidate.pt'))
        self.assertEqual((detector.model_version, detector.pinned), ('aegis-yolo11n-candidate', False))

    def test_opt_out_loads_a_candidate_and_marks_it_unpinned(self):
        path = self.file('gate.pt', b'candidate')
        os.environ.update(AEGIS_GATE_WEIGHTS=str(path), AEGIS_ALLOW_UNPINNED_MODELS='1')
        gate = diagnosis.build_gatekeeper()
        self.assertEqual((gate.sha256, gate.pinned), (hashlib.sha256(b'candidate').hexdigest(), False))

    def test_released_artifact_loads_as_pinned(self):
        path = self.file('gate.pt', b'released')
        os.environ['AEGIS_GATE_WEIGHTS'] = str(path)
        with patch.object(diagnosis, 'pinned_sha256', return_value=hashlib.sha256(b'released').hexdigest()):
            gate = diagnosis.build_gatekeeper()
        # Stored with every analysis, so it must name the release, not the file ("best.pt").
        self.assertEqual((gate.pinned, gate.version), (True, 'gatekeeper-gate-v1b-2026-11-24'))


class GatekeeperConcurrencyTests(unittest.TestCase):
    """Ultralytics builds its predictor on the first call outside its own lock, so callers must not overlap."""

    def test_concurrent_requests_never_enter_the_model_together(self):
        running, peak, guard = [], [], threading.Lock()

        class SlowModel:
            names = {0: 'non_rice', 1: 'rice'}

            def __init__(self, weights):
                pass

            def predict(self, **kwargs):
                with guard:
                    running.append(1); peak.append(len(running))
                time.sleep(0.05)
                with guard:
                    running.pop()
                probs = types.SimpleNamespace(data=torch.tensor([0.1, 0.9]))
                return [types.SimpleNamespace(probs=probs)]

        fake = types.ModuleType('ultralytics'); fake.YOLO = SlowModel
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'ultralytics': fake}):
            weights = Path(directory) / 'gate.pt'; weights.write_bytes(b'x')
            gate = diagnosis.YoloClsGatekeeper(weights)
            pixels = np.zeros((64, 64, 3), dtype=np.uint8)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: gate.classify(pixels)['rice_probability'], range(4)))
        self.assertEqual(max(peak), 1)
        self.assertEqual([round(r, 3) for r in results], [0.9] * 4)


class ManifestTests(unittest.TestCase):
    def test_pins_come_from_the_release_manifests(self):
        self.assertEqual(diagnosis.pinned_sha256('checkpoint.json')[:12], '1b755ca0263d')
        self.assertEqual(diagnosis.pinned_sha256('gatekeeper.json')[:12], 'be639ce13319')


class HealthTests(unittest.TestCase):
    def get(self, path, gatekeeper):
        return api.create_app(FakeDetector(), max_inflight=1, gatekeeper=gatekeeper).test_client().get(path)

    def test_health_is_unavailable_while_the_gatekeeper_is_missing(self):
        response = self.get('/health', diagnosis.HeuristicGatekeeper())
        self.assertEqual((response.status_code, response.json['status']), (503, 'degraded'))
        self.assertEqual(response.json['model_sha256'], 'a' * 64)

    def test_health_is_ready_with_a_gatekeeper_and_names_it(self):
        response = self.get('/health', FakeGate())
        self.assertEqual((response.status_code, response.json['status']), (200, 'ready'))
        for body in (response.json, self.get('/v2/health', FakeGate()).json):
            gate = body['gatekeeper']
            self.assertEqual((gate['version'], gate['sha256'], gate['pinned']), ('gate-test', 'c' * 64, True))


if __name__ == '__main__': unittest.main()
