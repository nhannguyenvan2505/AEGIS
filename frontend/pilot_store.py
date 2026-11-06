"""Explicit, isolated local pilot storage. Never opens backend/instance."""
from pathlib import Path
import json
import tempfile

PROJECT=Path(__file__).resolve().parent.parent
PILOT_ROOT=PROJECT/'pilot_data'
MARKER='.aegis-pilot.json'
KIND='aegis-local-pilot-v1'


def validate_storage(path):
    path=Path(path).resolve()
    if (path/'.restore-incomplete').exists():raise ValueError('Incomplete restore; do not open this store')
    for name in ['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3','research.sqlite3','automation.sqlite3','uploads','.server.lock','.automation.lock',MARKER]:
        if not (path/name).resolve().is_relative_to(path):
            raise ValueError('Store files must not redirect outside the isolated storage directory')
    temp=Path(tempfile.gettempdir()).resolve()
    if path.parent==temp and path.name.startswith('aegis_ui_') and path.is_dir():return path
    base=PILOT_ROOT.absolute()
    if PILOT_ROOT.exists() and PILOT_ROOT.resolve()!=base:raise ValueError('Pilot root must not be a symlink/junction')
    if path==base or not path.is_relative_to(base):raise ValueError(f'Use a named subdirectory of {base}')
    marker=path/MARKER
    if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('kind')!=KIND:
        raise ValueError('Directory is not an AEGIS pilot store; refusing to open it')
    return path


def prepare_pilot(path):
    path=Path(path).absolute()
    base=PILOT_ROOT.absolute()
    if path.resolve()==base or not path.resolve().is_relative_to(base):raise ValueError(f'Pilot path must be below {base}')
    if path.exists():return validate_storage(path)
    if PILOT_ROOT.exists() and PILOT_ROOT.resolve()!=base:raise ValueError('Pilot root cannot be redirected')
    path.mkdir(parents=True,exist_ok=False)
    (path/MARKER).write_text(json.dumps({'kind':KIND,'purpose':'isolated local pilot; never production database'},indent=2),encoding='utf-8')
    return validate_storage(path)


class StoreLease:
    """OS lock held by the serving backend, including if the launcher crashes."""
    def __init__(self,path,lock_name='.server.lock'):
        if lock_name not in ['.server.lock','.automation.lock']:raise ValueError('Unknown store lock')
        self.path=validate_storage(path);self.file=None;self.lock_name=lock_name
    def __enter__(self):
        self.file=(self.path/self.lock_name).open('a+b')
        self.file.seek(0,2)
        if self.file.tell()==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if __import__('os').name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close();self.file=None
            raise RuntimeError('Pilot store is already being served; do not start another backend') from exc
        return self
    def __exit__(self,*args):
        if self.file:
            self.file.seek(0)
            if __import__('os').name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
            self.file.close();self.file=None
