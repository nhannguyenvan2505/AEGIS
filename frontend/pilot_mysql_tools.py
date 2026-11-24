"""Lazy database readers for standalone offline monitoring commands."""
from pathlib import Path
import sys


def _module():
    path=str(Path(__file__).resolve().parent.parent/'backend')
    if path not in sys.path: sys.path.insert(0,path)
    from app import hybrid_pilot
    return hybrid_pilot


def open_readonly(path): return _module().open_readonly(path)
def initialized(path): return _module().initialized(path)
