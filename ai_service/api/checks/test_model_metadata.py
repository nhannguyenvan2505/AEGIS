import io,importlib.util,unittest
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('api_metadata',Path(__file__).resolve().parents[1]/'app.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
class Detector:
 model_sha256='b'*64
 device='cpu'
 model_version='candidate-test'
 checkpoint_label='candidate/best.pt'
 def predict(self,pixels):return []
class MetadataTests(unittest.TestCase):
 def test_candidate_metadata_never_claims_v4(self):
  client=api.create_app(Detector()).test_client();health=client.get('/health').json
  self.assertEqual(health['checkpoint'],'candidate/best.pt')
  self.assertEqual(health['model_version'],'candidate-test')
  self.assertEqual((health['nms_iou'],health['max_det']),(0.7,300))
  stream=io.BytesIO();Image.new('RGB',(32,32)).save(stream,format='PNG');stream.seek(0)
  r=client.post('/predict',data={'image':(stream,'a.png')});self.assertEqual(r.status_code,200);self.assertEqual(r.json['model_version'],'candidate-test')
if __name__=='__main__':unittest.main()
