"""Heartbeat a separate MQTT listener process leaves for the web process.

The file holds the listener's full status (broker and topic, never credentials) so the
administrator view keeps working when only database/run_mqtt.py subscribes. Both
processes name it with AEGIS_MQTT_STATUS_FILE.
"""
import json
import os
from pathlib import Path
import time

MAX_AGE_SECONDS = 30
_EMPTY = dict(enabled=True, connected=False, broker='', port=0, topic='', received_count=0,
              last_message_at=None, last_error=None)


def write_status(path, status, *, now=None):
    """Replace the file atomically so a reader never sees half of it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(dict(status, updated_at=time.time() if now is None else now)),
                         encoding='utf-8')
    for attempt in range(10):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:  # Windows refuses while a reader has the file open
            if attempt == 9:
                raise
            time.sleep(0.02)


def read_status(path):
    """The last report. A listener that is silent or unreadable is never shown as connected."""
    try:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
        age = time.time() - float(record['updated_at'])
        status = {key: record[key] for key in _EMPTY}
    except (OSError, ValueError, KeyError, TypeError):
        return dict(_EMPTY, last_error='MQTT listener has not reported yet')
    if age > MAX_AGE_SECONDS:
        status.update(connected=False, last_error='MQTT listener stopped reporting')
    return status
