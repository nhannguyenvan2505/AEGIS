"""Image contract tests with a fake detector: no claim of model quality."""
import importlib.util
import io
import unittest
from unittest import mock
from pathlib import Path
from PIL import Image

spec=importlib.util.spec_from_file_location('image_contract_api',Path(__file__).resolve().parents[1]/'app.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)

def encoded(size=(64,48),fmt='PNG',**kwargs):
    stream=io.BytesIO();Image.new('RGB',size,(100,120,80)).save(stream,format=fmt,**kwargs)
    return stream.getvalue()

class ImageContractTests(unittest.TestCase):
    def setUp(self):
        class Detector:
            device='cpu'; model_sha256='a'*64; model_version='fake-image-contract'
            def predict(self,pixels): return []
        self.detector=Detector();self.app=api.create_app(self.detector);self.client=self.app.test_client()
    def post(self,payload):
        return self.client.post('/predict',data={'image':(io.BytesIO(payload),'untrusted.bin')})
    def test_supported_formats_and_no_detection_semantics(self):
        for fmt in ['JPEG','PNG','WEBP']:
            with self.subTest(fmt=fmt):
                r=self.post(encoded(fmt=fmt));self.assertEqual(r.status_code,200)
                self.assertEqual(r.json['status'],'no_detection');self.assertEqual(r.json['detections'],[])
                self.assertIn('không xác nhận lá khỏe',r.json['message'])
    def test_reject_bad_small_large_pixel_animated_and_byte_limit(self):
        animated=io.BytesIO()
        Image.new('RGB',(32,32),'red').save(animated,format='PNG',save_all=True,append_images=[Image.new('RGB',(32,32),'blue')],duration=100)
        for payload in [b'',b'invalid',encoded((31,64)),encoded((4001,4000)),encoded(fmt='BMP'),animated.getvalue()]:
            with self.subTest(length=len(payload)): self.assertEqual(self.post(payload).status_code,400)
        self.assertEqual(self.post(b'x'*(8*1024*1024+1)).status_code,413)
    def test_unsupported_formats_never_reach_their_parser(self):
        Image.init()
        for fmt in ['BMP','GIF','TIFF','PPM']:
            with self.subTest(fmt=fmt):
                payload=encoded(fmt=fmt);factory,accept=Image.OPEN[fmt];parsed=[]
                def spy(*args,**kwargs):
                    parsed.append(fmt)
                    return factory(*args,**kwargs)
                with mock.patch.dict(Image.OPEN,{fmt:(spy,accept)}):
                    response=self.post(payload)
                self.assertEqual(response.status_code,400)
                self.assertEqual(response.json['error']['code'],'invalid_image')
                self.assertEqual(parsed,[])
    def test_exif_dimensions_and_box_clipping_use_corrected_frame(self):
        seen=[]
        def predict(pixels):
            seen.append(pixels.shape)
            return [dict(class_id=0,confidence=.8,xyxy=[-1,-2,999,999])]
        self.detector.predict=predict
        exif=Image.Exif();exif[274]=6
        r=self.post(encoded((48,64),'JPEG',exif=exif))
        self.assertEqual(r.status_code,200);self.assertEqual(seen,[(48,64,3)])
        self.assertEqual(r.json['image'],dict(width=64,height=48,orientation='exif_corrected'))
        self.assertEqual(r.json['detections'][0]['bbox_xyxy'],[0.,0.,64.,48.])
        self.assertEqual(r.json['detections'][0]['bbox_normalized_xyxy'],[0.,0.,1.,1.])
    def test_completion_log_has_no_image_bytes_or_filename(self):
        with self.assertLogs(self.app.logger,level='INFO') as captured:
            self.post(encoded())
        text='\n'.join(captured.output)
        self.assertNotIn('untrusted.bin',text);self.assertNotIn('PNG',text)
        self.assertIn('request_completed',text)

if __name__=='__main__': unittest.main()
