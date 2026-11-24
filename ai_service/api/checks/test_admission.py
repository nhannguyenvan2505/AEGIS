import importlib.util
import io
import threading
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

spec=importlib.util.spec_from_file_location('admission_ai',Path(__file__).resolve().parents[1]/'app.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)


class AdmissionTests(unittest.TestCase):
    def image(self):
        stream=io.BytesIO();Image.new('RGB',(32,32)).save(stream,format='PNG');stream.seek(0);return stream

    def test_full_capacity_rejected_and_slot_released_after_failure(self):
        entered=threading.Event();release=threading.Event()
        class Detector:
            device='cpu';model_sha256='a'*64
            def predict(self,pixels):
                entered.set()
                if not release.wait(timeout=5):raise RuntimeError('test timeout')
                raise RuntimeError('synthetic GPU failure')
        detector=Detector();app=api.create_app(detector,max_inflight=1)
        def first():
            with app.test_client() as client:return client.post('/predict',data={'image':(self.image(),'x.png')})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(first)
            try:
                self.assertTrue(entered.wait(timeout=5))
                with app.test_client() as client:
                    response=client.post('/predict',data={'image':(self.image(),'x.png')})
                    self.assertEqual(response.status_code,503);self.assertEqual(response.json['error']['code'],'ai_busy')
                    self.assertEqual(response.headers['Retry-After'],'1')
                    self.assertEqual(response.json['request_id'],response.headers['X-Request-ID'])
            finally:release.set()
            self.assertEqual(future.result(timeout=5).status_code,503)
        detector.predict=lambda _:[]
        with app.test_client() as client:self.assertEqual(client.post('/predict',data={'image':(self.image(),'x.png')}).status_code,200)

    def test_invalid_upload_also_releases_admission(self):
        class Detector:
            device='cpu';model_sha256='a'*64
            def predict(self,pixels):return []
        app=api.create_app(Detector(),max_inflight=1)
        with app.test_client() as client:
            self.assertEqual(client.post('/predict').status_code,400)
            self.assertEqual(client.post('/predict',data={'image':(self.image(),'x.png')}).status_code,200)

    def test_invalid_capacity_rejected_before_model_load(self):
        for value in [0,-1,True]:
            with self.subTest(value=value),patch.object(api,'Detector') as expensive:
                with self.assertRaises(ValueError):api.create_app(max_inflight=value)
                expensive.assert_not_called()


if __name__=='__main__':unittest.main()
