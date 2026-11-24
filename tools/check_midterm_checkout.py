"""Bounded checkout rehearsal: hybrid forecast API and optional real image AI.

Creates synthetic accounts/resources on the configured local demo databases.
Run on an isolated checkout/Compose project before handing the source to a member.
"""
import argparse
import contextlib
import getpass
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

import requests
import forecast_demo

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ai-python',type=Path)
    args=parser.parse_args()
    run=ROOT/'demo_runs'/('checkout-'+uuid4().hex);run.mkdir(parents=True)
    state=dict(success=False,real_image_ai=False,forecast=False,iot=False)
    session=requests.Session();session.trust_env=False
    ai=None
    with (run/'image-ai.log').open('w',encoding='utf-8') as log:
        try:
            if args.ai_python:
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                environment=dict(os.environ,AEGIS_AI_PORT=str(port),CUDA_VISIBLE_DEVICES='-1')
                ai=subprocess.Popen([str(args.ai_python),'-u',str(ROOT/'ai_service/api/app.py')],cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,env=environment,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                base=f'http://127.0.0.1:{port}'
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if ai.poll() is not None: raise RuntimeError('Image AI exited before readiness')
                    try:
                        health=session.get(base+'/health',timeout=1).json()
                        if health.get('model_sha256')=='1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a': break
                    except requests.RequestException: pass
                    time.sleep(.25)
                else: raise RuntimeError('Image AI readiness timed out')
                os.environ['AEGIS_AI_URL']=base
                image=run/'technical-image.png'
                subprocess.run([str(args.ai_python),'-c',
                    "from PIL import Image; import sys; Image.new('RGB',(64,64),(120,120,120)).save(sys.argv[1])",str(image)],check=True)
            password=uuid4().hex
            email='checkout-'+uuid4().hex+'@example.test'
            original=forecast_demo.seed
            def seed(base,email,password):
                regions=original(base,email,password)
                assert len(regions)==2 and regions[0]['score']!=regions[1]['score']
                login=session.post(base+'/api/auth/login',json=dict(email=email,password=password),timeout=10)
                login.raise_for_status();headers={'Authorization':'Bearer '+login.json()['access_token']}
                capabilities=session.get(base+'/api/mobile/capabilities',headers=headers,timeout=10)
                assert capabilities.json()['mode']=='pilot'
                state['forecast']=True
                if args.ai_python:
                    with image.open('rb') as stream:
                        response=session.post(base+'/api/disease/detect',files={'image':('technical.png',stream,'image/png')},
                                              headers=headers,timeout=90)
                    if response.status_code!=200: raise RuntimeError('Image integration HTTP '+str(response.status_code))
                    assert response.json()['model_sha256']=='1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a'
                    detail=session.get(base+'/api/disease/analyses/'+response.json()['analysis_id'],headers=headers,timeout=10)
                    assert detail.status_code==200
                    state['real_image_ai']=True
                return regions
            command=['forecast_demo.py','--model-python',str(ROOT/'forecast_demo/.venv/Scripts/python.exe'),
                     '--store',str(ROOT/'pilot_data'/('checkout-'+uuid4().hex)),'--port','0','--email',email,'--duration','.1']
            output=io.StringIO()
            with patch.object(sys,'argv',command),patch.object(getpass,'getpass',return_value=password),patch.object(forecast_demo,'seed',side_effect=seed),contextlib.redirect_stdout(output):
                code=forecast_demo.main()
            launcher=json.loads(output.getvalue().splitlines()[-1])
            if code: raise RuntimeError('Launcher failed; inspect '+launcher['log_path'])
            import simulate_iot_periodic
            iot_command=['simulate_iot_periodic.py','--out',str(run/'iot'),'--duration','5','--interval','1',
                         '--offline-seconds','0','--sensor-failure-every','3','--email',email]
            with patch.object(sys,'argv',iot_command),patch.object(getpass,'getpass',return_value=password),contextlib.redirect_stdout(io.StringIO()):
                iot_code=simulate_iot_periodic.main()
            if iot_code: raise RuntimeError('IoT rehearsal failed; inspect checkout IoT summary')
            state['iot']=True
            sys.path.insert(0,str(ROOT/'backend'))
            from app.database_config import settings
            from app.mongo_delivery import deliver
            delivery=deliver(dict(settings(),STORAGE_BACKEND='mysql'),limit=1000)
            if delivery['failed']: raise RuntimeError('Mongo delivery failed after rehearsal')
            state.update(success=True,services_stopped=launcher['services_stopped'])
        finally:
            if ai:
                ai.terminate()
                try: ai.wait(timeout=10)
                except subprocess.TimeoutExpired: ai.kill();ai.wait(timeout=5)
            (run/'summary.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps(state))


if __name__=='__main__': main()
