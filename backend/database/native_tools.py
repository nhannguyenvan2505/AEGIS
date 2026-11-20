"""Native MySQL utilities; passwords are passed through the child environment."""
from pathlib import Path
import os
import shutil
import subprocess


def mysql_dump(config, destination):
    executable = shutil.which('mysqldump')
    if not executable:
        candidates = sorted((Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'MySQL').glob('MySQL Server */bin/mysqldump.exe'))
        executable = str(candidates[-1]) if candidates else None
    if not executable:
        raise RuntimeError('Install the native MySQL client or put mysqldump on PATH before migrating')
    options = config['MYSQL']
    command = [executable, '--no-defaults', '--single-transaction', '--no-tablespaces', '--set-gtid-purged=OFF',
               '--host='+options['host'], '--port='+str(options['port']), '--user='+options['user'],
               '--databases', options['database']]
    with Path(destination).open('xb') as output:
        result = subprocess.run(command, env=dict(os.environ, MYSQL_PWD=options['password']),
                                stdout=output, stderr=subprocess.PIPE, timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Native MySQL backup failed; no application rows were imported')
