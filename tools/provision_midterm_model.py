"""Fetch the private Release checkpoint or copy a member-provided file; verify SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def verify(path,metadata):
    if not path.is_file() or path.stat().st_size!=metadata['size_bytes']:
        raise ValueError('Checkpoint file size differs from the pinned artifact')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata['sha256']:
        raise ValueError('Checkpoint SHA-256 differs from the V4 artifact')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Optional checkpoint downloaded through the private Release page')
    args=parser.parse_args()
    metadata=json.loads((ROOT/'ai_service/api/checkpoint.json').read_text())
    target=ROOT/metadata['target']
    if target.exists():
        verify(target,metadata);print('V4 checkpoint already verified');return
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='model-download-',dir=target.parent) as directory:
        if args.source:
            source=args.source.resolve()
        else:
            if not shutil.which('gh'): parser.error('Install GitHub CLI and run gh auth login, or provide --source')
            subprocess.run(['gh','release','download',metadata['release'],'--repo',metadata['repository'],
                            '--pattern',metadata['asset'],'--dir',directory],check=True)
            source=Path(directory)/metadata['asset']
        verify(source,metadata)
        staging=Path(directory)/'verified.pt'
        shutil.copy2(source,staging)
        staging.replace(target)
    print('V4 checkpoint installed and SHA-256 verified')


if __name__=='__main__': main()
