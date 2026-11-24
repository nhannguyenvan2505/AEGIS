"""Validate H6 traceability references and evidence bytes, not historical execution."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT=Path(__file__).resolve().parents[1]


def check(local=False):
    matrix=json.loads((ROOT/'docs/THESIS_TRACEABILITY.json').read_text(encoding='utf-8'))
    if matrix['schema_version']!='aegis-thesis-traceability-v1':raise ValueError('Unsupported matrix')
    def locate(value):
        p=PurePosixPath(value)
        if p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value or p.parts[0] not in {'AEGIS','AEGIS-AI'}:
            raise ValueError('Invalid evidence path')
        root=ROOT if p.parts[0]=='AEGIS' else ROOT.parent/'AEGIS-AI'
        path=root.joinpath(*p.parts[1:])
        if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Redirected reference')
        return path
    evidence={}
    checked=0;external=[]
    for e in matrix['evidence']:
        if e['id'] in evidence:raise ValueError('Duplicate evidence ID')
        evidence[e['id']]=e
        if not re.fullmatch('[a-f0-9]{64}',e['sha256']):raise ValueError('Invalid hash')
        path=locate(e['path'])
        if e['kind']=='local_historical' and not local:
            external.append(e['id']);continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=e['sha256']:raise ValueError('Evidence hash mismatch: '+e['id'])
        checked+=1
    ids=[];references=set()
    report=(ROOT/'docs/THESIS_EVIDENCE.md').read_text(encoding='utf-8')
    for row in matrix['requirements']:
        id=row['id'];ids.append(id)
        if row['status'] not in {'implemented','partial','blocked'}:raise ValueError('Invalid status')
        for field in ['title_vi','can_claim_vi','cannot_claim_vi','remaining_vi']:
            if not row[field].strip():raise ValueError('Missing claim boundary')
        if not row['evidence_ids'] or set(row['evidence_ids'])-evidence.keys():raise ValueError('Unmapped evidence')
        if any(x not in {'D01','D02','D03','D04','D05','D06','D07','D08'} for x in row['demo_steps']):raise ValueError('Invalid demo stage')
        for value in row['source_refs']+row['test_refs']:
            path=locate(value)
            if not path.is_file():raise ValueError('Missing reference: '+value)
            if path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8-sig'))
            references.add(value)
        if '| '+id+' — ' not in report or '| '+id+' |' not in report:raise ValueError('Human matrix missing ID')
    if ids!=['R'+str(x).zfill(2) for x in range(1,21)]:raise ValueError('Requirements must be R01..R20 once')
    summary=json.loads((ROOT/'docs/evidence/THESIS_HISTORICAL_SUMMARY.json').read_text(encoding='utf-8'))
    if summary['new_inference_or_training'] or summary['temporal']['trained_model_available']:
        raise ValueError('Unexpected training claim')
    if summary['temporal']['field_metrics'] is not None:raise ValueError('Unexpected field metric')
    return dict(requirements=len(ids),source_test_refs=len(references),evidence_checked=checked,
        local_evidence_requested=local,external_evidence_not_checked=external,
        historical_executions_rerun=False,verified=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--local-evidence',action='store_true')
    print(json.dumps(check(p.parse_args().local_evidence),indent=2))
