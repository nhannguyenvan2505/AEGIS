"""Build a selected, deterministic two-workspace source copy; never invokes Git."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / 'tools/handoff_allowlist.json'
BLOCKED = {'.db', '.sqlite', '.sqlite3', '.pt', '.pth', '.onnx', '.key', '.pem', '.log'}


def safe_relative(value):
    p = PurePosixPath(value)
    if (not isinstance(value, str) or '\\' in value or ':' in value or
            p.is_absolute() or '..' in p.parts or len(p.parts) < 2 or
            p.parts[0] not in {'AEGIS', 'AEGIS-AI'} or p.as_posix() != value):
        raise ValueError('Invalid package path')
    if (p.suffix.lower() in BLOCKED or any(x in p.parts for x in
            {'.git', '.venv', 'node_modules', '__pycache__', 'uploads', 'pilot_data', 'datasets', 'experiments', 'weights'}) or
            any(x.startswith('.env') and x != '.env.example' for x in p.parts)):
        raise ValueError('Private/runtime path is not source')
    return p


def regular_file(base, relative):
    path = base.joinpath(*relative.parts)
    # Resolve containment AND reject links/junctions in every component.
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError('Path escapes source boundary')
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Linked source is not allowed')
        if current.resolve() != current.absolute():
            raise ValueError('Redirected source is not allowed')
    if not path.is_file():
        raise ValueError('Missing regular source file: ' + relative.as_posix())
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out):
    out = Path(out).absolute()
    roots = {'AEGIS': ROOT, 'AEGIS-AI': ROOT.parent / 'AEGIS-AI'}
    if any(out.resolve().is_relative_to(p.resolve()) for p in
           [ROOT / 'backend', ROOT / 'frontend', ROOT / 'tools', roots['AEGIS-AI']]):
        raise ValueError('Output cannot be inside packaged source')
    values = json.loads(RULES.read_text(encoding='utf-8'))['files']
    if not values or values != sorted(set(values)):
        raise ValueError('Allowlist must be unique and sorted')
    selected = []
    for value in values:
        relative = safe_relative(value)
        source = regular_file(roots[relative.parts[0]], PurePosixPath(*relative.parts[1:]))
        selected.append((value, source))
    out.mkdir(parents=True, exist_ok=False)
    entries = []
    for value, source in selected:
        destination = out.joinpath(*PurePosixPath(value).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha(source) != sha(destination):
            raise ValueError('Source changed while packaging')
        entries.append(dict(path=value, size=destination.stat().st_size, sha256=sha(destination)))
    manifest = dict(schema='aegis-source-handoff-v1', files=entries,
                    model_included=False, runtime_data_included=False)
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    verify(out)
    return manifest


def verify(out):
    out = Path(out).absolute()
    manifest = json.loads((out / 'MANIFEST.json').read_text(encoding='utf-8'))
    if (manifest.get('schema') != 'aegis-source-handoff-v1' or
            manifest.get('model_included') is not False or manifest.get('runtime_data_included') is not False):
        raise ValueError('Unsupported source manifest')
    seen = set()
    for entry in manifest['files']:
        relative = safe_relative(entry['path'])
        if entry['path'] in seen:
            raise ValueError('Duplicate manifest path')
        seen.add(entry['path'])
        path = regular_file(out, relative)
        if path.stat().st_size != entry['size'] or sha(path) != entry['sha256']:
            raise ValueError('Source hash/size mismatch: ' + entry['path'])
    actual = set()
    for path in out.rglob('*'):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise ValueError('Linked package member')
        if path.is_file():
            actual.add(path.relative_to(out).as_posix())
    if actual != seen | {'MANIFEST.json'}:
        raise ValueError('Missing or unlisted package file')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--out', type=Path, help='NEW directory only')
    action.add_argument('--verify', type=Path)
    args = p.parse_args()
    result = build(args.out) if args.out else verify(args.verify)
    print(json.dumps(dict(files=len(result['files']), verified=True)))
