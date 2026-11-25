"""Turn ESP32 readings into alerts and queue the owner's push notification.

Two sources: the built-in microclimate disease rules, and the temperature/humidity
thresholds administrators keep in alert_thresholds. MySQL only: SQLite fixtures
have no alerts tables. Runs on the caller's cursor so the reading, its alerts and
the queued notifications commit together.
"""
from datetime import datetime, timezone

from .push import enqueue

# Decided 25/11/2026: 'high' (rice blast) and 'medium' (sheath blight) only.
ALERT_SEVERITY = {'high': 'high', 'medium': 'warning'}
COOLDOWN_SECONDS = 6 * 3600
CLOCK_SKEW_SECONDS = 300
THRESHOLD_METRICS = {'temperature': ('Nhiệt độ', '°C'), 'humidity': ('Độ ẩm không khí', '%')}
THRESHOLD_TEXT = {'gt': '> {a}', 'gte': '>= {a}', 'lt': '< {a}', 'lte': '<= {a}', 'between': 'trong {a} đến {b}'}
SILENT_SEVERITY = 'info'  # listed as an alert, never pushed
MAX_THRESHOLDS_PER_READING = 50


def _is_current(observed_at, now):
    """A backlog replayed hours later must not announce an old risk as a new one."""
    age = (now - datetime.fromisoformat(observed_at)).total_seconds()
    return -CLOCK_SKEW_SECONDS <= age <= COOLDOWN_SECONDS


def threshold_matches(operator, value, first, second=None):
    if operator == 'between':
        return first <= value <= second
    return {'gt': value > first, 'gte': value >= first, 'lt': value < first, 'lte': value <= first}[operator]


def _threshold_candidates(cur, plot_id, reading):
    """Active rows for this field, its farm, or everywhere, that the reading matches."""
    cur.execute('''SELECT t.threshold_id, t.metric, t.operator, t.threshold_value, t.threshold_value_2, t.severity
                   FROM farm_fields f JOIN alert_thresholds t
                     ON t.field_id=f.field_id OR (t.field_id IS NULL AND t.farm_id=f.farm_id)
                     OR (t.field_id IS NULL AND t.farm_id IS NULL)
                   WHERE f.external_id=%s AND t.is_active AND t.metric IN ('temperature','humidity')
                   ORDER BY t.threshold_id LIMIT %s''', (plot_id, MAX_THRESHOLDS_PER_READING))
    found = []
    for row in cur.fetchall():
        label, unit = THRESHOLD_METRICS[row['metric']]
        first = float(row['threshold_value'])
        second = None if row['threshold_value_2'] is None else float(row['threshold_value_2'])
        value = reading[row['metric']]
        if threshold_matches(row['operator'], value, first, second):
            limit = THRESHOLD_TEXT[row['operator']].format(a=f'{first:g}', b=f'{second or 0:g}')
            found.append(dict(source_key=f"threshold:{row['threshold_id']}", severity=row['severity'],
                              title=f'Cảnh báo ngưỡng · {label}',
                              message=f'{label} {value:g}{unit} chạm ngưỡng đã đặt ({limit}).'))
    return found


def raise_reading_alerts(cur, *, plot_id, device_id, alert, reading, now=None):
    """Return the ids of the alerts created for one normalized reading."""
    if not plot_id or not _is_current(reading['observed_at'], now or datetime.now(timezone.utc)):
        return []
    candidates = []
    severity = ALERT_SEVERITY.get(alert['level'])
    if severity is not None:
        candidates.append(dict(source_key='esp32:' + alert['disease'], severity=severity,
                               title=alert['title'], message=alert['message']))
    candidates += _threshold_candidates(cur, plot_id, reading)
    if not candidates:
        return []
    # The field row lock serializes concurrent readings of one plot.
    cur.execute('SELECT field_id, user_id FROM farm_fields WHERE external_id=%s FOR UPDATE', (plot_id,))
    field = cur.fetchone()
    if field is None:
        return []
    created = []
    for item in candidates:
        # A locking read sees alerts committed while this transaction waited for the lock.
        cur.execute('''SELECT alert_id FROM alerts WHERE field_id=%s AND source_key=%s
                       AND generated_at > UTC_TIMESTAMP() - INTERVAL %s SECOND LIMIT 1 FOR UPDATE''',
                    (field['field_id'], item['source_key'], COOLDOWN_SECONDS))
        if cur.fetchone():
            continue
        cur.execute('''INSERT INTO alerts(field_id,device_id,alert_type,severity,title,message,generated_at,source_key)
                       VALUES (%s,%s,'environment_anomaly',%s,%s,%s,UTC_TIMESTAMP(),%s)''',
                    (field['field_id'], device_id, item['severity'], item['title'][:200], item['message'],
                     item['source_key']))
        created.append(cur.lastrowid)
        if item['severity'] != SILENT_SEVERITY:
            enqueue(cur, field['user_id'], created[-1], item['title'], item['message'])
    return created
