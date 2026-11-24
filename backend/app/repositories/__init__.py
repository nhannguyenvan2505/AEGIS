"""Core domain repositories; SQLite is the default until explicit cutover."""
from contextlib import contextmanager


@contextmanager
def repository(config):
    backend = config.get('STORAGE_BACKEND', 'sqlite')
    if backend == 'mysql':
        from .mysql import mysql_repository
        with mysql_repository(config) as repo:
            yield repo
    elif backend == 'sqlite':
        from ..storage import connect
        from .sqlite import SQLiteRepository
        with connect(config) as connection:
            yield SQLiteRepository(connection)
    else:
        raise ValueError('STORAGE_BACKEND must be sqlite or mysql')
