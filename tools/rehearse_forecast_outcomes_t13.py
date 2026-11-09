"""T13 real HTTP evidence with retrospectively reported synthetic observations."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'frontend')]
import requests
from werkzeug.serving import make_server
from test_weather_integration import WeatherIntegrationTests
from telemetry_audit import stamp


def utc(): return datetime.now(timezone.utc)


def write(path,value):
    with path.open('x',encoding='utf-8') as file:
        json.dump(value,file,indent=2,ensure_ascii=False,allow_nan=False);file.write('\n')


def source_yesterday(case):
    """Keep the demonstration window open when rerun on the midterm day."""
    end=utc().replace(minute=0,second=0,microsecond=0)-timedelta(days=1)
    start=end-timedelta(hours=120)
    case.fixture.time=end+timedelta(seconds=60)
    records=[dict(client_sample_id=str(uuid4()),observed_at=(start+timedelta(minutes=10*i)).isoformat(),
        air_temperature_c=25.,relative_humidity_pct=65.,leaf_wet=True,reported_quality='nominal',
        reference='SYNTHETIC-T13-RETROSPECTIVE-HISTORY') for i in range(720)]
    for i in range(0,len(records),100):
        reply=case.fixture.post('/api/farm/environment-streams/'+case.fixture.stream+'/samples',dict(records=records[i:i+100]))
        if reply.status_code!=201: raise ValueError('Synthetic source intake failed')
    profile=dict(region='central',province_or_city='SYNTHETIC',locality=None,rice_variety='SYNTHETIC_RICE',
        planting_method='direct_seeded',sown_on='2026-10-01',transplanted_on=None,season_status='active')
    with patch('app.farm.now',return_value=case.fixture.time):
        reply=case.client.put('/api/farm/seasons/'+case.fixture.season['id']+'/cultivation-profile',
            json=dict(base_revision=0,profile=profile,change_reason='Synthetic retrospective T13 context'),headers=case.headers)
    if reply.status_code!=201: raise ValueError('Synthetic context failed')
    case.fixture.time=end+timedelta(seconds=120)
    reply=case.fixture.post(case.fixture.source_url,dict(base_revision=1,policy_revision=1,start_at=start.isoformat(),
        end_at=end.isoformat(),as_of=(end+timedelta(seconds=65)).isoformat()))
    if reply.status_code!=201: raise ValueError('Synthetic hourly source failed')
    return dict(scenario='hourly',hourly_source_id=reply.json['item']['id'],issued_at=case.fixture.time.isoformat())


def rehearse(out):
    out.mkdir(parents=True,exist_ok=False)
    with ExitStack() as cleanup:
        cleanup.callback(WeatherIntegrationTests.doClassCleanups)
        WeatherIntegrationTests.setUpClass()
        case=WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        case.port=WeatherIntegrationTests.port
        cleanup.callback(case.doCleanups)
        case.setUp()
        cleanup.enter_context(patch('pilot_journal.now',side_effect=utc))
        command=source_yesterday(case)
        root=case.fixture.root
        with make_server('127.0.0.1',0,case.app,threaded=True) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with requests.Session() as session:
                    session.trust_env=False
                    base='http://127.0.0.1:'+str(server.server_port)
                    def call(method,path,data=None,status=None,params=None):
                        response=session.request(method,base+path,json=data,params=params,headers=case.headers,timeout=20)
                        response.raise_for_status()
                        if status is not None and response.status_code!=status: raise ValueError('Unexpected HTTP status')
                        return response.json()
                    forecast=call('POST',case.url,command,201)['item']
                    url='/api/farm/forecasts/'+forecast['id']
                    issue=stamp(forecast['issued_at'])
                    def observation(hours,finding,reviewed):
                        observed=(issue+timedelta(hours=hours)).isoformat()
                        return call('POST','/api/farm/seasons/'+case.fixture.season['id']+'/observations',
                            dict(client_visit_id=str(uuid4()),source='synthetic',observed_at=observed,scheduled=True,
                                finding=finding,notes='Ghi nhận synthetic phục vụ tổng duyệt T13',analysis_id=None,record_status='active',
                                change_reason='Synthetic retrospective evidence',review=dict(reviewer_alias='SYNTHETIC-DECLARED-REVIEW',
                                    reviewed_at=observed,reference='SYNTHETIC-NOT-PLATFORM-VERIFIED') if reviewed else None),201)['item']
                    def link(observation):
                        command=dict(client_link_id=str(uuid4()),kind='observation',reference_id=observation['id'],
                                     reference_revision=observation['revision'],reason='Explicit synthetic observation reference')
                        return call('POST',url+'/outcome-links',command,201)['item'],command
                    initial=call('GET',url+'/outcome')['item']
                    baseline=observation(-1,'absent',True);link(baseline)
                    reported=observation(6,'present',False)
                    first,first_command=link(reported)
                    unverified=call('GET',url+'/outcome')['item']
                    before_revision=utc().isoformat()
                    edit={k:reported['payload'][k] for k in ('finding','notes','analysis_id','review','record_status')}
                    edit.update(base_revision=1,change_reason='Synthetic declared review added',
                        review=dict(reviewer_alias='SYNTHETIC-DECLARED-REVIEW',reviewed_at=reported['observed_at'],reference='SYNTHETIC-NOT-PLATFORM-VERIFIED'))
                    revision=call('PUT','/api/farm/observations/'+reported['id'],edit,201)['item']
                    stale=call('GET',url+'/outcome')['item']
                    old_asof=call('GET',url+'/outcome',params=dict(as_of=before_revision))['item']
                    second,_=link(revision)
                    reviewed=call('GET',url+'/outcome')['item']
                    retry=call('POST',url+'/outcome-links',first_command,200)
                    if not retry['replayed'] or retry['item']['snapshot_sha256']!=first['snapshot_sha256']:
                        raise ValueError('Pinned link changed on replay')
                    retract_url='/api/farm/forecast-outcome-links/'+second['id']+'/retractions'
                    retract=dict(base_version=1,reason='Withdraw association after synthetic rehearsal')
                    call('POST',retract_url,retract,201)
                    if not call('POST',retract_url,retract,200)['replayed']: raise ValueError('Retraction not idempotent')
                    withdrawn=call('GET',url+'/outcome')['item']
                    links=call('GET',url+'/outcome-links')
                    older=call('POST',case.url,case.base.command,201)['item']
                    closed=call('GET','/api/farm/forecasts/'+older['id']+'/outcome')['item']
                    original=call('GET',url)['item']
                    if (initial['status']!='following_up' or unverified['status']!='unverified_report'
                            or stale['status']!='uncertain' or reviewed['status']!='review_reported_present'
                            or old_asof['status']!='unverified_report' or closed['status']!='censored'
                            or original!=forecast): raise ValueError('Outcome lifecycle or immutable forecast failed')
                    states=dict(initial=initial,unverified_report=unverified,reference_revised=stale,
                                historical_asof=old_asof,review_reported=reviewed,association_retracted=withdrawn,
                                separate_older_unscored_forecast=closed)
                    if any(s['event_y'] is not None or s['platform_verified'] or s['label_approved_for_training'] for s in states.values()):
                        raise ValueError('Operational evidence became a label')
                    write(out/'forecast.synthetic.json',forecast)
                    write(out/'outcome_states.synthetic.json',states)
                    write(out/'links.synthetic.json',links)
                    write(out/'observation_revisions.synthetic.json',dict(original=reported,review_declared=revision))
            finally:
                server.shutdown();thread.join(10)
    if root.exists() or WeatherIntegrationTests.worker.poll() is None or thread.is_alive():
        raise RuntimeError('Rehearsal resources not cleaned')
    verification=dict(success=True,source='synthetic',field_validated=False,
        transport='Actual Backend HTTP and forecast-worker HTTP over loopback',
        clock='Current UTC journal/link/outcome runtime; retrospective synthetic source clock with issue yesterday and retrospective observations',
        forecast_unchanged=True,pinned_revision_preserved=True,asof_preserved_old_knowledge=True,
        retraction_replayed=True,no_training_labels_generated=True,
        separate_older_unscored_forecast_is_censored=True,temporary_store_and_workers_cleaned=True)
    write(out/'verification.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(rehearse(args.out)))
