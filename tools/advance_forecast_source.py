"""Advance a managed synthetic hourly source; never uses the wall clock as simulated time."""
import argparse
import copy
from datetime import datetime, timedelta
import getpass
import json
from urllib.parse import urlsplit
from uuid import UUID

import requests


def advance_hourly(hourly, hours, mode):
    if hourly.get('source') != 'synthetic' or type(hours) is not int or not 1 <= hours <= 120 or mode not in ('dry', 'wet', 'missing'):
        raise ValueError('Expected synthetic source, 1..120 hours and dry/wet/missing mode')
    result = copy.deepcopy(hourly)
    issued = datetime.fromisoformat(hourly['issued_at'].replace('Z', '+00:00'))
    if issued.tzinfo is None:
        raise ValueError('Simulation timestamp needs timezone')
    start = issued.replace(minute=0, second=0, microsecond=0)
    end = start+timedelta(hours=hours)
    # Replace only newly simulated hours, keep context and the preceding history.
    result['telemetry'] = [r for r in result['telemetry']
        if end-timedelta(hours=120) <= datetime.fromisoformat(r['start_at'].replace('Z', '+00:00')) < start]
    for offset in range(hours):
        at = start+timedelta(hours=offset)
        result['telemetry'].append(dict(start_at=at.isoformat(), available_at=(at+timedelta(hours=1)).isoformat(),
            air_temperature_c=None if mode == 'missing' else 27 if mode == 'wet' else 24,
            relative_humidity_pct=None if mode == 'missing' else 97 if mode == 'wet' else 65,
            leaf_wet=None if mode == 'missing' else mode == 'wet', quality='missing' if mode == 'missing' else 'valid'))
    result['issued_at'] = (issued+timedelta(hours=hours)).isoformat()
    return result


def advance(base, email, password, season, hours, mode):
    target = urlsplit(base)
    if target.scheme != 'http' or target.hostname != '127.0.0.1' or target.username or target.password or target.path not in ('', '/') or target.query or target.fragment:
        raise ValueError('Demo API must be http://127.0.0.1:<port>')
    season = str(UUID(season))
    with requests.Session() as session:
        session.trust_env = False
        def api(method, path, payload=None):
            with session.request(method, base.rstrip('/')+'/api'+path, json=payload, timeout=15, allow_redirects=False) as response:
                if response.status_code not in (200, 201):
                    raise RuntimeError('Demo API failed HTTP '+str(response.status_code))
                return response.json()
        token = api('POST', '/auth/login', dict(email=email, password=password))['access_token']
        session.headers['Authorization'] = 'Bearer '+token
        path = '/farm/seasons/'+season
        source = api('GET', path+'/forecast-source')['item']
        if source is None:
            raise ValueError('Season has no managed source; run demo seed first')
        hourly = advance_hourly(source['hourly'], hours, mode)
        saved = api('POST', path+'/forecast-source', dict(base_revision=source['revision'], hourly=hourly))
        forecast = api('POST', path+'/forecasts', dict(scenario='source'))['item']
        return dict(season_id=season, source_revision=saved['revision'], forecast_id=forecast['id'],
                    issued_at=forecast['issued_at'], status=forecast['status'], score=forecast['score'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:5000')
    parser.add_argument('--email', default='midterm@example.test')
    parser.add_argument('--season', required=True)
    parser.add_argument('--hours', type=int, choices=range(1, 121), default=1, metavar='1..120')
    parser.add_argument('--mode', choices=['dry', 'wet', 'missing'], required=True)
    args = parser.parse_args()
    try:
        result = advance(args.api, args.email, getpass.getpass('Demo password: '), args.season, args.hours, args.mode)
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        print(json.dumps(dict(success=False, failure_type=type(exc).__name__,
            message='Check the current source/history before issuing another simulation step.')))
        return 1
    print(json.dumps(dict(success=True, **result)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
