"""T12 live HTTP rehearsal with current issue/evaluation clock and synthetic history."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
import threading
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'frontend')]
import requests
from werkzeug.serving import make_server
from test_weather_integration import WeatherIntegrationTests


def write(path,value):
    with path.open('x',encoding='utf-8') as file:
        json.dump(value,file,indent=2,allow_nan=False);file.write('\n')


def utc(): return datetime.now(timezone.utc)


def rehearse(out):
    out.mkdir(parents=True,exist_ok=False)
    with ExitStack() as cleanup:
        cleanup.callback(WeatherIntegrationTests.doClassCleanups)
        WeatherIntegrationTests.setUpClass()
        case=WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        case.port=WeatherIntegrationTests.port
        cleanup.callback(case.doCleanups)
        case.setUp()
        root=case.fixture.root
        with make_server('127.0.0.1',0,case.app,threaded=True) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with requests.Session() as session:
                    session.trust_env=False
                    base='http://127.0.0.1:'+str(server.server_port)
                    def call(method,path,data=None,expected=None):
                        response=session.request(method,base+path,json=data,headers=case.headers,timeout=20)
                        response.raise_for_status()
                        if expected is not None and response.status_code!=expected:
                            raise ValueError('Unexpected HTTP status')
                        return response.json()
                    start_time=utc()
                    end=start_time.replace(minute=0,second=0,microsecond=0)
                    if start_time<end+timedelta(seconds=65):
                        raise ValueError('Latest hourly bucket has not closed grace; rerun after minute 1:05')
                    missing=call('POST',case.url,dict(case.base.command,issued_at=start_time.isoformat()),201)['item']
                    missing_eval=call('GET','/api/farm/forecasts/'+missing['id']+'/alert-evaluation')['item']
                    if missing_eval['outcome']!='created' or missing_eval['kind']!='data_quality':
                        raise ValueError('Fresh data-quality alert missing')
                    records=[]
                    begin=end-timedelta(hours=120)
                    for index in range(720):
                        hour=index//6
                        records.append(dict(client_sample_id=str(uuid4()),observed_at=(begin+timedelta(minutes=10*index)).isoformat(),
                            air_temperature_c=27+1.5*math.sin(hour*2*math.pi/24),
                            relative_humidity_pct=92+3*math.cos(hour*2*math.pi/24),leaf_wet=True,
                            reported_quality='nominal',reference='SYNTHETIC-T12-POSITIVE-CONTROL'))
                    for index in range(0,len(records),100):
                        case.fixture.time=utc()
                        call('POST','/api/farm/environment-streams/'+case.fixture.stream+'/samples',dict(records=records[index:index+100]),201)
                    profile=dict(region='central',province_or_city='SYNTHETIC',locality=None,rice_variety='SYNTHETIC_RICE',
                        planting_method='direct_seeded',sown_on='2026-10-01',transplanted_on=None,season_status='active')
                    call('PUT','/api/farm/seasons/'+case.fixture.season['id']+'/cultivation-profile',
                         dict(base_revision=0,profile=profile,change_reason='Synthetic T12 software positive control'),201)
                    case.fixture.time=utc()
                    source=call('POST',case.fixture.source_url,dict(base_revision=1,policy_revision=1,
                        start_at=begin.isoformat(),end_at=end.isoformat(),as_of=case.fixture.time.isoformat()),201)['item']
                    command=dict(scenario='hourly',hourly_source_id=source['id'],issued_at=utc().isoformat())
                    forecast=call('POST',case.url,command,201)['item']
                    evaluation=call('GET','/api/farm/forecasts/'+forecast['id']+'/alert-evaluation')['item']
                    if forecast['status']!='forecast_ready' or evaluation['kind']!='score_threshold' or evaluation['outcome']!='created':
                        raise ValueError('Synthetic positive control did not create threshold alert')
                    replay=call('POST',case.url,command,200)
                    if not replay['replayed'] or replay['item']!=forecast: raise ValueError('Forecast replay changed')
                    next_forecast=call('POST',case.url,dict(command,issued_at=utc().isoformat()),201)['item']
                    suppressed=call('GET','/api/farm/forecasts/'+next_forecast['id']+'/alert-evaluation')['item']
                    if suppressed['outcome']!='suppressed_cooldown' or suppressed['alert_id']!=evaluation['alert_id']:
                        raise ValueError('Cooldown did not preserve original alert')
                    alert_url='/api/farm/forecast-alerts/'+evaluation['alert_id']
                    acknowledged=call('POST',alert_url+'/acknowledgements',dict(base_version=1),201)
                    duplicate_ack=call('POST',alert_url+'/acknowledgements',dict(base_version=1),200)
                    alerts=call('GET','/api/farm/forecast-alerts')
                    if len(alerts['items'])!=2 or not duplicate_ack['replayed']:
                        raise ValueError('Duplicate alerts or acknowledgement')
                    write(out/'policy.json',call('GET','/api/farm/forecast-alert-policy')['item'])
                    write(out/'alerts.synthetic.json',alerts)
                    write(out/'evaluations.synthetic.json',dict(data_quality=missing_eval,score_threshold=evaluation,cooldown=suppressed))
                    write(out/'forecast.synthetic.json',forecast)
                    write(out/'acknowledgement.synthetic.json',acknowledged)
            finally:
                server.shutdown();thread.join(10)
    if root.exists() or WeatherIntegrationTests.worker.poll() is None or thread.is_alive():
        raise RuntimeError('Rehearsal resources not cleaned')
    result=dict(success=True,source='synthetic',field_validated=False,
        clock='Current UTC runtime/issue/evaluation; synthetic retrospective 120h observations; intake fixture clock advanced from current UTC',
        transport='Actual Backend HTTP and model-worker HTTP on loopback',
        data_quality_alert=True,score_threshold_alert=True,cooldown_suppressed=True,
        forecast_replay_unchanged=True,ack_replayed=True,alert_count=2,
        no_external_notification_delivery=True,temporary_store_and_workers_cleaned=True)
    write(out/'verification.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(rehearse(args.out)))
