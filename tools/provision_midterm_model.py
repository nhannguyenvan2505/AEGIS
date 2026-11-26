"""Fetch the GitHub Release checkpoints (V4 detector + rice/non_rice gatekeeper) or copy a member-provided file; verify SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS={'detector':'checkpoint.json','gatekeeper':'gatekeeper.json'}


def verify(path,metadata,label):
    if not path.is_file() or path.stat().st_size!=metadata['size_bytes']:
        raise ValueError(f'{label} file size differs from the pinned artifact')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata['sha256']:
        raise ValueError(f'{label} SHA-256 differs from the pinned artifact')


def provision(name,source,parser):
    metadata=json.loads((ROOT/'ai_service/api'/ARTIFACTS[name]).read_text())
    target=ROOT/metadata['target']
    if target.exists():
        verify(target,metadata,name);print(f'{name} checkpoint already verified');return
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='model-download-',dir=target.parent) as directory:
        if source:
            source=source.resolve()
        else:
            if not shutil.which('gh'): parser.error('Install GitHub CLI and run gh auth login, or provide --source')
            subprocess.run(['gh','release','download',metadata['release'],'--repo',metadata['repository'],
                            '--pattern',metadata['asset'],'--dir',directory],check=True)
            source=Path(directory)/metadata['asset']
        verify(source,metadata,name)
        staging=Path(directory)/'verified.pt'
        shutil.copy2(source,staging)
        staging.replace(target)
    print(f'{name} checkpoint installed and SHA-256 verified')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',choices=[*ARTIFACTS,'all'],default='all')
    parser.add_argument('--source',type=Path,help='Checkpoint downloaded through the Release page (needs --artifact detector|gatekeeper)')
    args=parser.parse_args()
    if args.source and args.artifact=='all': parser.error('--source needs --artifact detector or gatekeeper')
    for name in (ARTIFACTS if args.artifact=='all' else [args.artifact]):
        provision(name,args.source,parser)


if __name__=='__main__': main()
