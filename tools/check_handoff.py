"""No-checkpoint regression runner. Run inside a verified source handoff."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SUITES = {'backend': ROOT / 'backend/checks', 'pilot': ROOT / 'frontend',
          'temporal': ROOT.parent / 'AEGIS-AI/temporal_warning',
          'image_contract': ROOT.parent / 'AEGIS-AI/api/checks', 'handoff': ROOT / 'tools'}


def child(suite, forbidden):
    allowed_environment = Path(sys.prefix).resolve()
    forbidden = [Path(x).resolve() for x in forbidden]
    def guard(event, args):
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(allowed_environment):
            return
        if any(path.is_relative_to(base) for base in forbidden):
            raise PermissionError('Original workspace source access forbidden')
    sys.addaudithook(guard)
    # No PYTHONPATH/current-working-directory imports: child is launched with -I.
    sys.dont_write_bytecode = True
    location = SUITES[suite]
    sys.path.insert(0, str(location))
    if suite == 'temporal':
        sys.path.insert(0, str(ROOT / 'frontend'))
    tests = unittest.defaultTestLoader.discover(str(location), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=1).run(tests)
    origins = {}
    for name in ('app', 'server', 'pilot_store', 'pipeline', 'bridge'):
        module = sys.modules.get(name)
        if module and getattr(module, '__file__', None):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(ROOT.parent.resolve()):
                raise RuntimeError('Source import outside handoff: ' + name)
            origins[name] = path.relative_to(ROOT.parent.resolve()).as_posix()
    print(json.dumps(dict(suite=suite, tests=result.testsRun, failures=len(result.failures),
                         errors=len(result.errors), skipped=len(result.skipped), origins=origins)))
    return 0 if result.wasSuccessful() and not result.skipped else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', choices=SUITES)
    p.add_argument('--forbid-source', action='append', default=[])
    args = p.parse_args()
    if args.suite:
        return child(args.suite, args.forbid_source)
    from build_handoff import verify
    manifest = verify(ROOT.parent)
    print('Verified %s source files; fake detector only, no checkpoint loaded.' % len(manifest['files']), flush=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', NO_PROXY='127.0.0.1,localhost')
    env.pop('PYTHONPATH', None)
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        env.pop(name, None)
    codes = []
    for suite in SUITES:
        command = [sys.executable, '-I', '-u', str(Path(__file__).resolve()), '--suite', suite]
        for base in args.forbid_source:
            command += ['--forbid-source', base]
        codes.append(subprocess.run(command, cwd=ROOT.parent, env=env).returncode)
    return int(any(codes))


if __name__ == '__main__':
    raise SystemExit(main())
