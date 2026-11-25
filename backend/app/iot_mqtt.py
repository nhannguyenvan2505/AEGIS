"""Live ESP32 MQTT telemetry listener, persistence and API endpoints."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
import uuid

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .farm import FarmError, body, owned
from .iot_alerts import raise_reading_alerts
from .repositories import repository
from .storage import connect

DEFAULT_MQTT_BROKER = 'broker.hivemq.com'
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC = 'nckh_aegis_c1se21/farm/sensors'

_SCHEMA_LOCK = threading.Lock()
_INITIALIZED_TARGETS = set()
_LOGGER = logging.getLogger(__name__)

_SQLITE_DDL = (
    '''CREATE TABLE IF NOT EXISTS esp32_telemetry_readings (
        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_uid TEXT NOT NULL,
        plot_id TEXT,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        alert_level TEXT NOT NULL DEFAULT 'safe',
        alert_disease TEXT,
        alert_message TEXT,
        topic TEXT NOT NULL DEFAULT 'nckh_aegis_c1se21/farm/sensors',
        source TEXT NOT NULL DEFAULT 'esp32_mqtt',
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''',
    'CREATE INDEX IF NOT EXISTS idx_esp32_device_time ON esp32_telemetry_readings(device_uid, observed_at)',
    'CREATE INDEX IF NOT EXISTS idx_esp32_plot_time ON esp32_telemetry_readings(plot_id, observed_at)',
    'CREATE INDEX IF NOT EXISTS idx_esp32_observed ON esp32_telemetry_readings(observed_at)',
    '''CREATE TABLE IF NOT EXISTS esp32_device_bindings (
        device_uid TEXT PRIMARY KEY,
        plot_id TEXT,
        device_name TEXT,
        updated_at TEXT NOT NULL
    )''',
)


class DeviceBoundError(Exception):
    """The device is assigned to a plot the caller does not own."""


class DeviceNotRegisteredError(Exception):
    """No administrator has registered the device to any plot."""


def _is_reserved_uid(device_uid):
    # 'Unknown' stands for every packet without an id, so nobody may own it.
    return device_uid.lower() == 'unknown'


def _is_plain_uid(device_uid):
    # MySQL compares bindings accent-insensitively, so non-ASCII look-alikes would alias real ids.
    return device_uid.isascii() and device_uid.isprintable()


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _iso(value):
    """MySQL DATETIME columns hold naive UTC; SQLite already stores the ISO text."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat(timespec='seconds')
    return value


def _dedup_token(reading, plot_id):
    """Identity of a redelivered packet. Anonymous packets are never merged."""
    if _is_reserved_uid(reading['device_uid']):
        return None
    identity = [reading['device_uid'].upper(), plot_id, reading['observed_at'],
                reading['temperature'], reading['humidity']]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def _is_mysql(config):
    return config.get('STORAGE_BACKEND', 'sqlite') == 'mysql'


def _target_key(config):
    if _is_mysql(config):
        mysql_cfg = config.get('MYSQL', {})
        return ('mysql', mysql_cfg.get('host'), mysql_cfg.get('port'), mysql_cfg.get('database'))
    return ('sqlite', str(config.get('DATABASE_PATH')))


def _param(sql, is_mysql):
    return sql if is_mysql else sql.replace('%s', '?')


@contextmanager
def _db_cursor(config):
    """Open an isolated DB connection/cursor for MQTT background writes and queries."""
    ensure_iot_schema(config)
    if _is_mysql(config):
        from .repositories.mysql import open_connection
        conn = open_connection(config)
        try:
            with conn.cursor() as cur:
                yield cur, True
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    conn = sqlite3.connect(str(config['DATABASE_PATH']), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        yield cur, False
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_iot_schema(config):
    """Create the ESP32 tables of a SQLite fixture once per file.

    MySQL tables come from database/mysql/007 and 009; check_schema() enforces them.
    """
    if _is_mysql(config):
        return
    key = _target_key(config)
    with _SCHEMA_LOCK:
        if key in _INITIALIZED_TARGETS:
            return
        conn = sqlite3.connect(str(config['DATABASE_PATH']), timeout=5)
        try:
            for stmt in _SQLITE_DDL:
                conn.execute(stmt)
            columns = {row[1] for row in conn.execute('PRAGMA table_info(esp32_telemetry_readings)')}
            if 'dedup_token' not in columns:
                conn.execute('ALTER TABLE esp32_telemetry_readings ADD COLUMN dedup_token TEXT')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_esp32_dedup '
                         'ON esp32_telemetry_readings(dedup_token)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_esp32_created ON esp32_telemetry_readings(created_at)')
            conn.commit()
        finally:
            conn.close()
        _INITIALIZED_TARGETS.add(key)


def evaluate_microclimate(temperature, humidity):
    """Evaluate SHT30 temperature/humidity against the ESP32 rice disease rules."""
    if 18.0 <= temperature <= 26.5 and humidity >= 85.0:
        return {
            'level': 'high',
            'disease': 'rice_blast',
            'title': 'Nguy cơ cao · Bệnh đạo ôn',
            'message': 'Nguy cơ bùng phát BỆNH ĐẠO ÔN (Rice Blast)! Thời tiết mát ẩm thuận lợi cho bào tử nấm nảy mầm.',
        }
    if 28.0 <= temperature <= 34.0 and humidity >= 85.0:
        return {
            'level': 'medium',
            'disease': 'sheath_blight',
            'title': 'Cảnh báo · Bệnh khô vằn',
            'message': 'Điều kiện nóng ẩm cao, nguy cơ phát sinh BỆNH KHÔ VẰN (Sheath Blight)!',
        }
    if 25.0 <= temperature <= 32.0 and 78.0 <= humidity < 88.0:
        return {
            'level': 'warning',
            'disease': 'brown_spot',
            'title': 'Cảnh báo sớm · Bệnh đốm nâu',
            'message': 'Điều kiện thuận lợi cho nấm BỆNH ĐỐM NÂU (Brown Spot) phát triển.',
        }
    if 26.5 < temperature < 28.0 and humidity >= 85.0:
        # No disease rule covers this band; do not call it safe and do not guess one (decided 25/11/2026).
        return {
            'level': 'warning',
            'disease': None,
            'title': 'Theo dõi · Độ ẩm cao',
            'message': 'Độ ẩm không khí cao, cần theo dõi đồng ruộng. Chưa có luật xác định nguy cơ bệnh cụ thể ở mức nhiệt này.',
        }
    return {
        'level': 'safe',
        'disease': None,
        'title': 'Vi khí hậu an toàn',
        'message': 'Trạng thái vi khí hậu an toàn, cây lúa sinh trưởng bình thường.',
    }


def _finite_number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be numeric')
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f'{name} out of range [{minimum}, {maximum}]')
    return round(number, 2)


def validate_esp32_payload(payload):
    """Validate and normalize an incoming ESP32 JSON telemetry payload."""
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')
    raw_uid = payload.get('device_uid')
    if raw_uid is None or raw_uid == '':
        device_uid = 'Unknown'
    elif isinstance(raw_uid, str) and 1 <= len(raw_uid.strip()) <= 100 and _is_plain_uid(raw_uid.strip()):
        device_uid = raw_uid.strip()
    else:
        raise ValueError('device_uid must be a non-empty ASCII string (<= 100 chars)')

    temperature = _finite_number(payload.get('temperature'), 'temperature', -50.0, 60.0)
    humidity = _finite_number(payload.get('humidity'), 'humidity', 0.0, 100.0)

    plot_id = payload.get('plot_id')
    if plot_id is not None:
        if not isinstance(plot_id, str):
            raise ValueError('plot_id must be a UUID string')
        plot_id = str(uuid.UUID(plot_id))

    observed_raw = payload.get('observed_at')
    if observed_raw is None:
        observed_at = _utc_now()
    else:
        if not isinstance(observed_raw, str):
            raise ValueError('observed_at must be an ISO8601 string')
        parsed = datetime.fromisoformat(observed_raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if not 2000 <= parsed.year <= 9998:
            raise ValueError('observed_at year is out of range')
        observed_at = parsed.astimezone(timezone.utc).isoformat(timespec='seconds')

    return {
        'device_uid': device_uid,
        'plot_id': plot_id,
        'temperature': temperature,
        'humidity': humidity,
        'observed_at': observed_at,
    }


def _registry_device(cur, device_uid):
    """The iot_devices row for a hardware id (MySQL). Letter case does not matter, as for
    bindings; an exact match wins, and only then is the column scanned."""
    query = '''SELECT d.device_id, f.external_id plot_id FROM iot_devices d
               LEFT JOIN farm_fields f ON f.field_id=d.field_id WHERE {} ORDER BY d.device_id LIMIT 1'''
    cur.execute(query.format('d.device_uid=%s'), (device_uid,))
    row = cur.fetchone()
    if row is None:
        cur.execute(query.format('UPPER(d.device_uid)=UPPER(%s)'), (device_uid,))
        row = cur.fetchone()
    return row


def _resolve_plot_for_device(cur, is_mysql, device_uid):
    if _is_reserved_uid(device_uid):
        return None
    cur.execute(_param('SELECT plot_id FROM esp32_device_bindings WHERE device_uid=%s', is_mysql), (device_uid,))
    bound = cur.fetchone()
    if bound and bound['plot_id']:
        return bound['plot_id']
    if is_mysql:
        device = _registry_device(cur, device_uid)
        if device and device['plot_id']:
            return device['plot_id']
    return None


def save_esp32_reading(config, payload, *, topic=DEFAULT_MQTT_TOPIC, source='esp32_mqtt',
                       trust_plot_id=False):
    """Validate, evaluate and persist a single ESP32 temperature/humidity reading.

    A payload's `plot_id` is honoured only with `trust_plot_id=True`, i.e. after the
    caller authorized it. Otherwise (MQTT) the plot comes from the device assignment.
    """
    normalized = validate_esp32_payload(payload)
    alert = evaluate_microclimate(normalized['temperature'], normalized['humidity'])
    created_at = _utc_now()

    with _db_cursor(config) as (cur, is_mysql):
        plot_id = ((normalized['plot_id'] if trust_plot_id else None)
                   or _resolve_plot_for_device(cur, is_mysql, normalized['device_uid']))
        token = _dedup_token(normalized, plot_id)
        on_duplicate = ('ON DUPLICATE KEY UPDATE reading_id=reading_id' if is_mysql
                        else 'ON CONFLICT(dedup_token) DO NOTHING')
        cur.execute(
            _param(
                f'''INSERT INTO esp32_telemetry_readings
                   (device_uid, plot_id, temperature, humidity, alert_level, alert_disease,
                    alert_message, topic, source, observed_at, created_at, dedup_token)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) {on_duplicate}''',
                is_mysql,
            ),
            (
                normalized['device_uid'],
                plot_id,
                normalized['temperature'],
                normalized['humidity'],
                alert['level'],
                alert['disease'],
                alert['message'],
                topic,
                source,
                normalized['observed_at'],
                created_at,
                token,
            ),
        )
        reading_id = cur.lastrowid
        if token is not None:
            # A redelivery answers with the row stored the first time.
            lock = ' FOR UPDATE' if is_mysql else ''
            cur.execute(_param('SELECT reading_id, created_at FROM esp32_telemetry_readings '
                               'WHERE dedup_token=%s' + lock, is_mysql), (token,))
            stored = cur.fetchone()
            reading_id, created_at = stored['reading_id'], _iso(stored['created_at'])
        if is_mysql:
            device = _registry_device(cur, normalized['device_uid'])
            device_id = device['device_id'] if device else None
            raise_reading_alerts(cur, plot_id=plot_id, device_id=device_id, alert=alert, reading=normalized)
            if device_id is not None:
                cur.execute(
                    "UPDATE iot_devices SET status='online', last_seen_at=UTC_TIMESTAMP() WHERE device_id=%s",
                    (device_id,),
                )

    return {
        'id': reading_id,
        'device_uid': normalized['device_uid'],
        'plot_id': plot_id,
        'temperature': normalized['temperature'],
        'humidity': normalized['humidity'],
        'alert': alert,
        'topic': topic,
        'source': source,
        'observed_at': normalized['observed_at'],
        'created_at': created_at,
    }


def _row_to_item(row):
    item = dict(row)
    alert = evaluate_microclimate(float(item['temperature']), float(item['humidity']))
    return {
        'id': item['reading_id'],
        'device_uid': item['device_uid'],
        'plot_id': item['plot_id'],
        'temperature': float(item['temperature']),
        'humidity': float(item['humidity']),
        'alert': {
            'level': item['alert_level'],
            'disease': item['alert_disease'],
            'title': alert['title'],
            'message': item['alert_message'] or alert['message'],
        },
        'topic': item['topic'],
        'source': item['source'],
        'observed_at': _iso(item['observed_at']),
        'created_at': _iso(item['created_at']),
    }


def _assigned_plots(cur, is_mysql, device_uid):
    """Every plot the device is assigned to: its binding and, on MySQL, the iot_devices registry.

    A registry row without a plot yields None, which no user owns.
    """
    cur.execute(_param('SELECT plot_id FROM esp32_device_bindings WHERE device_uid=%s', is_mysql), (device_uid,))
    row = cur.fetchone()
    plots = [row['plot_id']] if row and row['plot_id'] else []
    if is_mysql:
        # iot_devices.device_uid is case-sensitive but bindings are not; match like bindings do.
        cur.execute(
            '''SELECT f.external_id plot_id
               FROM iot_devices d
               LEFT JOIN farm_fields f ON f.field_id=d.field_id
               WHERE UPPER(d.device_uid)=UPPER(%s)''',
            (device_uid,),
        )
        plots.extend(device['plot_id'] for device in cur.fetchall())
    return plots


def bind_device_to_plot(config, device_uid, plot_id, device_name=None, *, allowed_plot_ids=None):
    """Bind an ESP32 device_uid to a plot UUID.

    With `allowed_plot_ids` (the caller's plots) the device must already be assigned by
    an administrator, and only to those plots; an unknown id cannot be claimed. Check
    and write share one transaction. `None` is for administrators, who register devices.
    """
    uid = (device_uid or '').strip()
    if not uid or len(uid) > 100 or not _is_plain_uid(uid) or _is_reserved_uid(uid):
        raise ValueError('device_uid must be 1..100 ASCII characters and not "Unknown"')
    plot_uuid = str(uuid.UUID(plot_id)) if plot_id else None
    updated_at = _utc_now()
    with _db_cursor(config) as (cur, is_mysql):
        # Serialize concurrent claims before reading who holds the device.
        if is_mysql:
            cur.execute(
                '''INSERT INTO esp32_device_bindings(device_uid, plot_id, updated_at)
                   VALUES (%s,NULL,%s) ON DUPLICATE KEY UPDATE device_uid=device_uid''',
                (uid, updated_at),
            )
            cur.execute('SELECT plot_id FROM esp32_device_bindings WHERE device_uid=%s FOR UPDATE', (uid,))
            cur.fetchone()
        else:
            cur.execute('BEGIN IMMEDIATE')
        if allowed_plot_ids is not None:
            allowed = set(allowed_plot_ids)
            assigned = _assigned_plots(cur, is_mysql, uid)
            if not assigned:
                raise DeviceNotRegisteredError(uid)
            if any(plot not in allowed for plot in assigned):
                raise DeviceBoundError(uid)
        if is_mysql:
            cur.execute(
                '''UPDATE esp32_device_bindings SET plot_id=%s,
                   device_name=COALESCE(%s, device_name), updated_at=%s WHERE device_uid=%s''',
                (plot_uuid, device_name, updated_at, uid),
            )
        else:
            cur.execute(
                '''INSERT INTO esp32_device_bindings(device_uid, plot_id, device_name, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(device_uid) DO UPDATE SET
                   plot_id=excluded.plot_id,
                   device_name=COALESCE(excluded.device_name, esp32_device_bindings.device_name),
                   updated_at=excluded.updated_at''',
                (uid, plot_uuid, device_name, updated_at),
            )
    return {'device_uid': uid, 'plot_id': plot_uuid, 'device_name': device_name, 'updated_at': updated_at}


def _in_clause(values):
    return ','.join(['%s'] * len(values))


def query_esp32_telemetry(config, *, plot_ids, plot_id=None, device_uid=None, limit=24):
    """Return the latest ESP32 readings visible to the caller.

    `plot_ids` are the plots the caller owns. A reading is visible only when the plot
    stamped on it at ingest time is in that set. The device's current binding grants
    nothing, so claiming or receiving a device never exposes earlier readings. Pass
    `plot_ids=None` explicitly only for administrators, who may see every reading.
    """
    safe_limit = max(1, min(int(limit), 200))
    if plot_ids is None:
        visible, scope_params = '1=1', ()
        name_scope, name_params = '', ()
    else:
        plot_ids = list(plot_ids)
        if not plot_ids:
            return {'item': None, 'items': [], 'devices': [], 'binding_scope': None}
        marks = _in_clause(plot_ids)
        visible, scope_params = f'r.plot_id IN ({marks})', tuple(plot_ids)
        # A device name belongs to whoever holds the binding now.
        name_scope, name_params = f' AND b.plot_id IN ({marks})', tuple(plot_ids)
    scope, filters, params = 'user', '', []
    if device_uid:
        scope, filters = 'device', ' AND r.device_uid=%s'
        params.append(device_uid)
    elif plot_id:
        scope, filters = 'plot', ' AND r.plot_id=%s'
        params.append(plot_id)
    with _db_cursor(config) as (cur, is_mysql):
        cur.execute(
            _param(
                f'''SELECT r.reading_id, r.device_uid, r.plot_id, r.temperature, r.humidity,
                          r.alert_level, r.alert_disease, r.alert_message, r.topic, r.source,
                          r.observed_at, r.created_at
                   FROM esp32_telemetry_readings r
                   WHERE {visible}{filters}
                   ORDER BY r.observed_at DESC, r.reading_id DESC
                   LIMIT %s''',
                is_mysql,
            ),
            (*scope_params, *params, safe_limit),
        )
        rows = cur.fetchall()

        cur.execute(
            _param(
                f'''SELECT r.device_uid, r.plot_id, b.device_name,
                          r.temperature, r.humidity, r.alert_level, r.alert_disease,
                          r.alert_message, r.observed_at
                   FROM esp32_telemetry_readings r
                   INNER JOIN (
                       SELECT r.device_uid, MAX(r.reading_id) AS max_id
                       FROM esp32_telemetry_readings r
                       WHERE {visible}
                       GROUP BY r.device_uid
                   ) latest ON latest.max_id = r.reading_id
                   LEFT JOIN esp32_device_bindings b ON b.device_uid = r.device_uid{name_scope}
                   ORDER BY r.observed_at DESC, r.reading_id DESC''',
                is_mysql,
            ),
            (*scope_params, *name_params),
        )
        device_rows = cur.fetchall()

    items = [_row_to_item(r) for r in rows]
    devices = []
    for row in device_rows:
        d = dict(row)
        eval_alert = evaluate_microclimate(float(d['temperature']), float(d['humidity']))
        devices.append({
            'device_uid': d['device_uid'],
            'plot_id': d['plot_id'],
            'device_name': d['device_name'],
            'temperature': float(d['temperature']),
            'humidity': float(d['humidity']),
            'alert': {
                'level': d['alert_level'],
                'disease': d['alert_disease'],
                'title': eval_alert['title'],
                'message': d['alert_message'] or eval_alert['message'],
            },
            'observed_at': _iso(d['observed_at']),
        })
    return {
        'item': items[0] if items else None,
        'items': items,
        'devices': devices,
        'binding_scope': scope if items else None,
    }


class MqttTelemetryService:
    """Background paho-mqtt subscriber bridging HiveMQ ESP32 payloads into AEGIS storage."""

    def __init__(self, config, *, broker=None, port=None, topic=None):
        self.config = dict(config)
        self.broker = broker or os.environ.get('AEGIS_MQTT_BROKER', DEFAULT_MQTT_BROKER)
        self.port = int(port or os.environ.get('AEGIS_MQTT_PORT', DEFAULT_MQTT_PORT))
        self.topic = topic or os.environ.get('AEGIS_MQTT_TOPIC', DEFAULT_MQTT_TOPIC)
        self.enabled = os.environ.get('AEGIS_MQTT_ENABLED', '1') == '1'
        self._lock = threading.Lock()
        self._client = None
        self._connected = False
        self._received_count = 0
        self._last_message_at = None
        self._last_error = None

    def start(self):
        if not self.enabled:
            return
        with self._lock:
            if self._client is not None:
                return
            try:
                import paho.mqtt.client as mqtt
            except ImportError as exc:
                self._last_error = f'paho-mqtt not installed: {exc}'
                _LOGGER.warning('MQTT listener disabled: %s', self._last_error)
                return

            ensure_iot_schema(self.config)
            if hasattr(mqtt, 'CallbackAPIVersion'):
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            else:
                client = mqtt.Client()
            client.reconnect_delay_set(min_delay=2, max_delay=30)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            self._client = client
            try:
                client.connect_async(self.broker, self.port, 60)
                client.loop_start()
                _LOGGER.info('MQTT listener starting for %s:%s topic=%s', self.broker, self.port, self.topic)
            except Exception as exc:
                self._last_error = str(exc)
                _LOGGER.warning('MQTT listener failed to start: %s', exc)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        code = getattr(reason_code, 'value', reason_code)
        ok = code == 0 or str(reason_code) == 'Success'
        with self._lock:
            self._connected = ok
            if ok:
                self._last_error = None
            else:
                self._last_error = f'MQTT connect failed ({reason_code})'
        if ok:
            client.subscribe(self.topic)

    def _on_disconnect(self, client, userdata, *args):
        with self._lock:
            self._connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            saved = save_esp32_reading(self.config, payload, topic=msg.topic, source='esp32_mqtt')
            with self._lock:
                self._received_count += 1
                self._last_message_at = saved['observed_at']
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            _LOGGER.warning('MQTT message ignored: %s', exc)

    def status(self):
        with self._lock:
            return {
                'enabled': self.enabled,
                'connected': self._connected,
                'broker': self.broker,
                'port': self.port,
                'topic': self.topic,
                'received_count': self._received_count,
                'last_message_at': self._last_message_at,
                'last_error': self._last_error,
            }


def get_mqtt_status(app):
    service = app.extensions.get('iot_mqtt')
    if service is not None:
        return service.status()
    return {
        'enabled': False,
        'connected': False,
        'broker': os.environ.get('AEGIS_MQTT_BROKER', DEFAULT_MQTT_BROKER),
        'port': int(os.environ.get('AEGIS_MQTT_PORT', DEFAULT_MQTT_PORT)),
        'topic': os.environ.get('AEGIS_MQTT_TOPIC', DEFAULT_MQTT_TOPIC),
        'received_count': 0,
        'last_message_at': None,
        'last_error': None,
    }


def _parse_limit():
    raw = request.args.get('limit', '24')
    if not raw.isascii() or not raw.isdigit():
        raise FarmError('invalid_limit', 'limit phải là số nguyên dương.')
    value = int(raw)
    if not 1 <= value <= 200:
        raise FarmError('invalid_limit', 'limit từ 1 đến 200.')
    return value


def _user_plot_ids(config):
    """Plot ids owned by the authenticated user (storage-backend agnostic)."""
    with repository(config) as db:
        db.begin()
        return list(db.user_plot_ids(g.user['id']))


def _require_device_access(config, device_uid, plot_ids):
    """A device may be used only when bound, and every plot it is assigned to is the caller's."""
    with _db_cursor(config) as (cur, is_mysql):
        cur.execute(_param('SELECT plot_id FROM esp32_device_bindings WHERE device_uid=%s', is_mysql), (device_uid,))
        bound = cur.fetchone()
        assigned = _assigned_plots(cur, is_mysql, device_uid)
    if not (bound and bound['plot_id']) or any(plot not in plot_ids for plot in assigned):
        raise FarmError('device_not_found', 'Không tìm thấy thiết bị.', 404)


def enable_iot_mqtt(app):
    """Initialize ESP32 telemetry tables, routes and background MQTT subscriber."""
    ensure_iot_schema(app.config)
    if not app.testing:
        service = MqttTelemetryService(app.config)
        app.extensions['iot_mqtt'] = service
        service.start()

    bp = Blueprint('iot_mqtt', __name__, url_prefix='/api/iot')

    @bp.after_request
    def private(response):
        response.headers['Cache-Control'] = 'private, no-store'
        response.vary.add('Authorization')
        return response

    @bp.errorhandler(FarmError)
    def handle_farm_error(error):
        return jsonify(success=False, error={'code': error.code, 'message': error.message}), error.status

    @bp.get('/latest')
    @require_auth
    def latest():
        plot_id = request.args.get('plot_id') or None
        device_uid = request.args.get('device_uid') or None
        if plot_id is not None:
            try:
                plot_id = str(uuid.UUID(plot_id))
            except ValueError:
                raise FarmError('invalid_plot_id', 'plot_id phải là UUID hợp lệ.')
            with connect(current_app.config) as db:
                owned(db, 'plots', plot_id)
        data = query_esp32_telemetry(current_app.config, plot_ids=_user_plot_ids(current_app.config),
                                     plot_id=plot_id, device_uid=device_uid, limit=_parse_limit())
        return jsonify(success=True, mqtt=get_mqtt_status(current_app), **data)

    @bp.get('/readings')
    @require_auth
    def readings():
        plot_id = request.args.get('plot_id') or None
        device_uid = request.args.get('device_uid') or None
        if plot_id is not None:
            try:
                plot_id = str(uuid.UUID(plot_id))
            except ValueError:
                raise FarmError('invalid_plot_id', 'plot_id phải là UUID hợp lệ.')
            with connect(current_app.config) as db:
                owned(db, 'plots', plot_id)
        data = query_esp32_telemetry(current_app.config, plot_ids=_user_plot_ids(current_app.config),
                                     plot_id=plot_id, device_uid=device_uid, limit=_parse_limit())
        return jsonify(success=True, mqtt=get_mqtt_status(current_app), **data)

    @bp.post('/ingest')
    @require_auth
    def ingest():
        data = body({'temperature', 'humidity'}, {'device_uid', 'plot_id', 'observed_at'})
        plot_id = data.get('plot_id')
        if plot_id is not None:
            try:
                plot_id = str(uuid.UUID(str(plot_id)))
            except ValueError:
                raise FarmError('invalid_plot_id', 'plot_id phải là UUID hợp lệ.')
            with connect(current_app.config) as db:
                owned(db, 'plots', plot_id)
            data = dict(data, plot_id=plot_id)
        device_uid = data.get('device_uid')
        if device_uid not in (None, ''):
            # Only a device already bound to one of the caller's plots may be fed over HTTP.
            _require_device_access(current_app.config, str(device_uid).strip(), _user_plot_ids(current_app.config))
        elif plot_id is None:
            raise FarmError('invalid_telemetry', 'Cần device_uid đã gán hoặc plot_id của bạn.')
        try:
            saved = save_esp32_reading(
                current_app.config,
                data,
                topic=get_mqtt_status(current_app)['topic'],
                source='esp32_http',
                trust_plot_id=True,  # ownership of plot_id was checked above
            )
        except ValueError as exc:
            raise FarmError('invalid_telemetry', str(exc))
        return jsonify(success=True, item=saved), 201

    @bp.put('/bindings')
    @require_auth
    def bind_plot():
        data = body({'device_uid', 'plot_id'}, {'device_name'})
        try:
            plot_id = str(uuid.UUID(str(data['plot_id'])))
        except ValueError:
            raise FarmError('invalid_plot_id', 'plot_id phải là UUID hợp lệ.')
        with connect(current_app.config) as db:
            owned(db, 'plots', plot_id)
        try:
            binding = bind_device_to_plot(
                current_app.config,
                str(data['device_uid']),
                plot_id,
                data.get('device_name'),
                allowed_plot_ids=_user_plot_ids(current_app.config),
            )
        except DeviceNotRegisteredError:
            raise FarmError('device_not_registered',
                            'Thiết bị chưa được quản trị viên đăng ký cho ruộng của bạn.', 404)
        except DeviceBoundError:
            # Do not let one user take over a device that belongs to another user's plot.
            raise FarmError('device_already_bound', 'Thiết bị đã được gán cho người dùng khác.', 409)
        except ValueError as exc:
            raise FarmError('invalid_binding', str(exc))
        return jsonify(success=True, item=binding)

    app.register_blueprint(bp)

