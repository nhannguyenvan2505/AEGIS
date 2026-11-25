"""Turn ESP32 microclimate warnings into alerts and queue the owner's push notification.

MySQL only: SQLite fixtures have no alerts tables. Runs on the caller's cursor so
the reading, its alert and the queued notification commit together.
"""
from datetime import datetime, timezone

from .push import enqueue

# Decided 25/11/2026: 'high' (rice blast) and 'medium' (sheath blight) only.
ALERT_SEVERITY = {'high': 'high', 'medium': 'warning'}
COOLDOWN_SECONDS = 6 * 3600
CLOCK_SKEW_SECONDS = 300


def _is_current(observed_at, now):
    """A backlog replayed hours later must not announce an old risk as a new one."""
    age = (now - datetime.fromisoformat(observed_at)).total_seconds()
    return -CLOCK_SKEW_SECONDS <= age <= COOLDOWN_SECONDS


def raise_microclimate_alert(cur, *, plot_id, device_uid, alert, observed_at, now=None):
    """Return the new alert id, or None when no alert is due."""
    severity = ALERT_SEVERITY.get(alert['level'])
    if severity is None or not plot_id or not _is_current(observed_at, now or datetime.now(timezone.utc)):
        return None
    # The field row lock serializes concurrent readings of one plot.
    cur.execute('SELECT field_id, user_id FROM farm_fields WHERE external_id=%s FOR UPDATE', (plot_id,))
    field = cur.fetchone()
    if field is None:
        return None
    source_key = 'esp32:' + alert['disease']
    # A locking read sees alerts committed while this transaction waited for the lock.
    cur.execute('''SELECT alert_id FROM alerts WHERE field_id=%s AND source_key=%s
                   AND generated_at > UTC_TIMESTAMP() - INTERVAL %s SECOND LIMIT 1 FOR UPDATE''',
                (field['field_id'], source_key, COOLDOWN_SECONDS))
    if cur.fetchone():
        return None
    cur.execute('SELECT device_id FROM iot_devices WHERE device_uid=%s AND field_id=%s',
                (device_uid, field['field_id']))
    device = cur.fetchone()
    cur.execute('''INSERT INTO alerts(field_id,device_id,alert_type,severity,title,message,generated_at,source_key)
                   VALUES (%s,%s,'environment_anomaly',%s,%s,%s,UTC_TIMESTAMP(),%s)''',
                (field['field_id'], device['device_id'] if device else None, severity,
                 alert['title'][:200], alert['message'], source_key))
    alert_id = cur.lastrowid
    enqueue(cur, field['user_id'], alert_id, alert['title'], alert['message'])
    return alert_id
