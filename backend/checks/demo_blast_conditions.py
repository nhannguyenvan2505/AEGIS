"""Create deterministic mock scenarios and run the independent pattern monitor."""
import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.blast_conditions import evaluate,PROFILE

def scenarios():
    end=datetime(2026,10,24,tzinfo=timezone.utc)
    records=[dict(start_at=(end-timedelta(hours=24-i)).isoformat(),air_temperature_c=26,
                  relative_humidity_pct=70,leaf_wet=False) for i in range(24)]
    base=dict(source='mock',as_of=end.isoformat(),records=records)
    values=[]
    values.append(('complete_no_pattern',copy.deepcopy(base),'no_pattern_detected'))
    p=copy.deepcopy(base)
    for r in p['records'][-6:]:r.update(relative_humidity_pct=95,leaf_wet=True)
    values.append(('six_consecutive_hours',p,'advisory'))
    p=copy.deepcopy(base)
    for r in p['records'][-5:]:r.update(relative_humidity_pct=95,leaf_wet=True)
    values.append(('five_hours',p,'no_pattern_detected'))
    p=copy.deepcopy(base)
    for i in [0,1,2,10,11,12]:p['records'][i].update(relative_humidity_pct=95,leaf_wet=True)
    values.append(('two_separate_three_hour_runs',p,'no_pattern_detected'))
    p=copy.deepcopy(base)
    for r in p['records']:r['relative_humidity_pct']=95
    values.append(('humid_without_leaf_wet',p,'no_pattern_detected'))
    p=copy.deepcopy(base);p['records'].pop(12)
    values.append(('missing_middle_hour',p,'insufficient_data'))
    p=copy.deepcopy(base);p['records']=p['records'][:-2]
    values.append(('stale_last_two_hours',p,'insufficient_data'))
    p=copy.deepcopy(base);p['records']=[]
    values.append(('no_readings',p,'insufficient_data'))
    return values

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    checks=[]
    for name,payload,expected in scenarios():
        response=evaluate(payload);assert response['status']==expected,(name,response['status'])
        (args.out/(name+'.json')).write_text(json.dumps(dict(input=payload,expected_status=expected,output=response),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        checks.append(dict(case=name,expected_status=expected,actual_status=response['status'],passed=True))
    summary=dict(at_utc7=datetime.now(timezone(timedelta(hours=7))).isoformat(),status='passed',
                 scope='Synthetic software checks, not disease prediction validation',profile=PROFILE,
                 engine_sha256=hashlib.sha256((Path(__file__).resolve().parents[1]/'app/blast_conditions.py').read_bytes()).hexdigest(),checks=checks)
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS 8 deterministic mock scenarios; no DB, HTTP, GPU or real sensor data used')
if __name__=='__main__':main()
