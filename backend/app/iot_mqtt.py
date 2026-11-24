"""Live ESP32 MQTT telemetry listener, persistence and API endpoints."""
from contextlib import contextmanager
from datetime import datetime, timezone
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
from .storage import connect

DEFAULT_MQTT_BROKER = 'broker.hivemq.com'
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC = 'nckh_aegis_c1se21/farm/sensors'

_SCHEMA_LOCK = threading.Lock()
_INITIALIZED_TARGETS = set()
_LOGGER = logging.getLogger(__name__)

_MYSQL_DDL = (
    '''CREATE TABLE IF NOT EXISTS esp32_telemetry_readings (
        reading_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        device_uid VARCHAR(100) NOT NULL,
        plot_id CHAR(36) NULL,
        temperature DOUBLE NOT NULL,
        humidity DOUBLE NOT NULL,
        alert_level VARCHAR(20) NOT NULL DEFAULT 'safe',
        alert_disease VARCHAR(50) NULL,
        alert_message TEXT NULL,
        topic VARCHAR(200) NOT NULL DEFAULT 'nckh_aegis_c1se21/farm/sensors',
        source VARCHAR(30) NOT NULL DEFAULT 'esp32_mqtt',
        observed_at VARCHAR(40) NOT NULL,
        created_at VARCHAR(40) NOT NULL,
        INDEX idx_esp32_device_time (device_uid, observed_at),
        INDEX idx_esp32_plot_time (plot_id, observed_at),
        INDEX idx_esp32_observed (observed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci''',
    '''CREATE TABLE IF NOT EXISTS esp32_device_bindings (
        device_uid VARCHAR(100) PRIMARY KEY,
        plot_id CHAR(36) NULL,
        device_name VARCHAR(150) NULL,
        updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci''',
)

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


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


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
    """Create the additive ESP32 telemetry tables once per configured database."""
    key = _target_key(config)
    with _SCHEMA_LOCK:
        if key in _INITIALIZED_TARGETS:
            return
        if _is_mysql(config):
            from .repositories.mysql import open_connection
            conn = open_connection(config)
            try:
                with conn.cursor() as cur:
                    for stmt in _MYSQL_DDL:
                        cur.execute(stmt)
                conn.commit()
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(str(config['DATABASE_PATH']), timeout=5)
            try:
                for stmt in _SQLITE_DDL:
                    conn.execute(stmt)
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
    elif isinstance(raw_uid, str) and 1 <= len(raw_uid.strip()) <= 100:
        device_uid = raw_uid.strip()
    else:
        raise ValueError('device_uid must be a non-empty string (<= 100 chars)')

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
        observed_at = parsed.astimezone(timezone.utc).isoformat(timespec='seconds')

    return {
        'device_uid': device_uid,
        'plot_id': plot_id,
        'temperature': temperature,
        'humidity': humidity,
        'observed_at': observed_at,
    }


def _resolve_plot_for_device(cur, is_mysql, device_uid):
    cur.execute(_param('SELECT plot_id FROM esp32_device_bindings WHERE device_uid=%s', is_mysql), (device_uid,))
    bound = cur.fetchone()
    if bound and bound['plot_id']:
        return bound['plot_id']
    if is_mysql:
        cur.execute(
            '''SELECT f.external_id plot_id
               FROM iot_devices d
               LEFT JOIN farm_fields f ON f.field_id=d.field_id
               WHERE d.device_uid=%s''',
            (device_uid,),
        )
        device = cur.fetchone()
        if device and device['plot_id']:
            return device['plot_id']
    return None


def save_esp32_reading(config, payload, *, topic=DEFAULT_MQTT_TOPIC, source='esp32_mqtt'):
    """Validate, evaluate and persist a single ESP32 temperature/humidity reading."""
    normalized = validate_esp32_payload(payload)
    alert = evaluate_microclimate(normalized['temperature'], normalized['humidity'])
    created_at = _utc_now()

    with _db_cursor(config) as (cur, is_mysql):
        plot_id = normalized['plot_id'] or _resolve_plot_for_device(cur, is_mysql, normalized['device_uid'])
        cur.execute(
            _param(
                '''INSERT INTO esp32_telemetry_readings
                   (device_uid, plot_id, temperature, humidity, alert_level, alert_disease,
                    alert_message, topic, source, observed_at, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
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
            ),
        )
        reading_id = cur.lastrowid
        if is_mysql:
            cur.execute(
                "UPDATE iot_devices SET status='online', last_seen_at=UTC_TIMESTAMP() WHERE device_uid=%s",
                (normalized['device_uid'],),
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
        'observed_at': item['observed_at'],
        'created_at': item['created_at'],
    }


def bind_device_to_plot(config, device_uid, plot_id, device_name=None):
    """Bind an ESP32 device_uid to a plot UUID."""
    uid = (device_uid or '').strip()
    if not uid or len(uid) > 100:
        raise ValueError('device_uid must be 1..100 characters')
    plot_uuid = str(uuid.UUID(plot_id)) if plot_id else None
    updated_at = _utc_now()
    with _db_cursor(config) as (cur, is_mysql):
        if is_mysql:
            cur.execute(
                '''INSERT INTO esp32_device_bindings(device_uid, plot_id, device_name, updated_at)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE plot_id=VALUES(plot_id),
                   device_name=COALESCE(VALUES(device_name), device_name),
                   updated_at=VALUES(updated_at)''',
                (uid, plot_uuid, device_name, updated_at),
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


def query_esp32_telemetry(config, *, plot_id=None, device_uid=None, limit=24):
    """Return latest ESP32 readings, per-device summaries, and plot binding scope."""
    safe_limit = max(1, min(int(limit), 200))
    with _db_cursor(config) as (cur, is_mysql):
        scope = 'global'
        rows = []
        if device_uid:
            scope = 'device'
            cur.execute(
                _param(
                    '''SELECT reading_id, device_uid, plot_id, temperature, humidity,
                              alert_level, alert_disease, alert_message, topic, source,
                              observed_at, created_at
                       FROM esp32_telemetry_readings
                       WHERE device_uid=%s
                       ORDER BY observed_at DESC, reading_id DESC
                       LIMIT %s''',
                    is_mysql,
                ),
                (device_uid, safe_limit),
            )
            rows = cur.fetchall()
        elif plot_id:
            cur.execute(
                _param(
                    '''SELECT r.reading_id, r.device_uid, r.plot_id, r.temperature, r.humidity,
                              r.alert_level, r.alert_disease, r.alert_message, r.topic, r.source,
                              r.observed_at, r.created_at
                       FROM esp32_telemetry_readings r
                       LEFT JOIN esp32_device_bindings b ON b.device_uid=r.device_uid
                       WHERE r.plot_id=%s OR b.plot_id=%s
                       ORDER BY r.observed_at DESC, r.reading_id DESC
                       LIMIT %s''',
                    is_mysql,
                ),
                (plot_id, plot_id, safe_limit),
            )
            rows = cur.fetchall()
            if rows:
                scope = 'plot'

        if not rows and not device_uid:
            scope = 'global'
            cur.execute(
                _param(
                    '''SELECT reading_id, device_uid, plot_id, temperature, humidity,
                              alert_level, alert_disease, alert_message, topic, source,
                              observed_at, created_at
                       FROM esp32_telemetry_readings
                       ORDER BY observed_at DESC, reading_id DESC
                       LIMIT %s''',
                    is_mysql,
                ),
                (safe_limit,),
            )
            rows = cur.fetchall()

        cur.execute(
            '''SELECT r.device_uid,
                      COALESCE(b.plot_id, r.plot_id) AS plot_id,
                      b.device_name,
                      r.temperature, r.humidity, r.alert_level, r.alert_disease,
                      r.alert_message, r.observed_at
               FROM esp32_telemetry_readings r
               INNER JOIN (
                   SELECT device_uid, MAX(reading_id) AS max_id
                   FROM esp32_telemetry_readings
                   GROUP BY device_uid
               ) latest ON latest.max_id = r.reading_id
               LEFT JOIN esp32_device_bindings b ON b.device_uid = r.device_uid
               ORDER BY r.observed_at DESC, r.reading_id DESC'''
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
            'observed_at': d['observed_at'],
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
        data = query_esp32_telemetry(current_app.config, plot_id=plot_id, device_uid=device_uid, limit=_parse_limit())
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
        data = query_esp32_telemetry(current_app.config, plot_id=plot_id, device_uid=device_uid, limit=_parse_limit())
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
        try:
            saved = save_esp32_reading(
                current_app.config,
                data,
                topic=get_mqtt_status(current_app)['topic'],
                source='esp32_http',
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
            )
        except ValueError as exc:
            raise FarmError('invalid_binding', str(exc))
        return jsonify(success=True, item=binding)

    app.register_blueprint(bp)

