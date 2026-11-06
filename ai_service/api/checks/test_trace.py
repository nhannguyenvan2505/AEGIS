import importlib.util
import io
import sys
import unittest
import uuid
from pathlib import Path

from PIL import Image

spec=importlib.util.spec_from_file_location('traced_ai_api',Path(__file__).resolve().parents[1]/'app.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)


class FakeDetector:
    model_sha256='a'*64
    device='cpu'

    def predict(self,pixels):return []


class AITraceTests(unittest.TestCase):
    def setUp(self):
        self.detector=FakeDetector();self.client=api.create_app(self.detector).test_client()

    def image(self):
        stream=io.BytesIO();Image.new('RGB',(32,32)).save(stream,format='PNG');stream.seek(0);return stream

    def test_predict_preserves_backend_id_and_loaded_hash(self):
        trace=str(uuid.uuid4())
        r=self.client.post('/predict',headers={'X-Request-ID':trace},data={'image':(self.image(),'x.png')})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['request_id'],trace);self.assertEqual(r.headers['X-Request-ID'],trace)
        self.assertEqual(r.json['model_sha256'],self.detector.model_sha256)
        self.assertGreaterEqual(r.json['processing_ms'],0)

    def test_bad_id_is_replaced_on_error(self):
        r=self.client.post('/predict',headers={'X-Request-ID':'untrusted-value'})
        self.assertEqual(r.status_code,400)
        self.assertEqual(str(uuid.UUID(r.headers['X-Request-ID'])),r.json['request_id'])
        self.assertNotEqual(r.json['request_id'],'untrusted-value')

    def test_inference_failure_retains_trace(self):
        def fail(_):raise RuntimeError('synthetic inference failure')
        self.detector.predict=fail
        trace=str(uuid.uuid4())
        r=self.client.post('/predict',headers={'X-Request-ID':trace},data={'image':(self.image(),'x.png')})
        self.assertEqual(r.status_code,503);self.assertEqual(r.json['request_id'],trace)

    def test_health_reports_loaded_model_hash(self):
        self.assertEqual(self.client.get('/health').json['model_sha256'],'a'*64)


if __name__=='__main__':unittest.main()
