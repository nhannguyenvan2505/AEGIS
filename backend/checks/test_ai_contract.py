"""Backend rejection tests: malformed upstream contract, no real inference."""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect

class UpstreamContractTests(unittest.TestCase):
    def test_malformed_responses_never_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            app=create_app(dict(TESTING=True,DATABASE_PATH=root/'test.db',UPLOAD_DIR=root/'uploads',DETECT_USER_LIMIT=100))
            client=app.test_client();credentials=dict(email='contract@example.test',password='test-password-123')
            client.post('/api/auth/register',json=credentials)
            token=client.post('/api/auth/login',json=credentials).json['access_token']
            def upstream(kind):
                def response(*args,**kwargs):
                    item=dict(class_id=0,class_name='rice_blast',confidence=.8,bbox_xyxy=[0,0,32,32])
                    body=dict(request_id=kwargs['headers']['X-Request-ID'],model_sha256='a'*64,model_version='fake',processing_ms=1,image=dict(width=32,height=32),detections=[item])
                    if kind=='class':item['class_name']='brown_spot'
                    elif kind=='bbox':item['bbox_xyxy']=[0,0,33,32]
                    elif kind=='confidence':item['confidence']=float('nan')
                    elif kind=='version':body['model_version']=''
                    elif kind=='dimensions':body['image']['width']=True
                    elif kind=='json':return Mock(status_code=200,json=Mock(side_effect=ValueError('bad JSON')))
                    return Mock(status_code=200,json=lambda:body)
                return response
            for kind in ['class','bbox','confidence','version','dimensions','json']:
                with self.subTest(kind=kind),patch('app.ai_service.requests.post',side_effect=upstream(kind)):
                    r=client.post('/api/disease/detect',headers={'Authorization':'Bearer '+token},data={'image':(io.BytesIO(b'synthetic'),'x.png')})
                    self.assertEqual(r.status_code,502);self.assertEqual(r.json['error']['code'],'invalid_ai_response')
            with connect(app.config) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0],0)
            self.assertEqual(list((root/'uploads').iterdir()),[])
if __name__=='__main__':unittest.main()
