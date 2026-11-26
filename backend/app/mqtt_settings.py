"""MQTT connection settings from the environment: off by default, secure by default.

The broker and topic have no built-in value, so nothing connects anywhere until an
operator names them. TLS and a login are required unless AEGIS_MQTT_ALLOW_INSECURE=1
(local test brokers only). See docs/IOT_MQTT_SETUP.md.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MqttSettings:
    enabled: bool
    broker: str
    port: int
    topic: str
    tls: bool
    ca_cert: str
    username: str
    password: str = field(repr=False)
    error: str = ''  # why an enabled listener must not connect; empty when usable


def load_mqtt_settings(env):
    broker = env.get('AEGIS_MQTT_BROKER', '').strip()
    topic = env.get('AEGIS_MQTT_TOPIC', '').strip()
    tls = env.get('AEGIS_MQTT_TLS', '1') != '0'
    username = env.get('AEGIS_MQTT_USERNAME', '').strip()
    password = env.get('AEGIS_MQTT_PASSWORD', '')
    problems = []
    raw_port = env.get('AEGIS_MQTT_PORT', '').strip() or ('8883' if tls else '1883')
    port = int(raw_port) if raw_port.isascii() and raw_port.isdigit() else 0
    if not 1 <= port <= 65535:
        problems.append('AEGIS_MQTT_PORT must be 1..65535')
    if not broker:
        problems.append('set AEGIS_MQTT_BROKER')
    if not topic:
        problems.append('set AEGIS_MQTT_TOPIC')
    elif '#' in topic or topic.split('/').count('+') > 1 or any('+' in part and part != '+' for part in topic.split('/')):
        problems.append('AEGIS_MQTT_TOPIC allows no "#" and at most one whole-level "+" (the device id)')
    if not (tls and username and password) and env.get('AEGIS_MQTT_ALLOW_INSECURE') != '1':
        problems.append('TLS, AEGIS_MQTT_USERNAME and AEGIS_MQTT_PASSWORD are required '
                        '(AEGIS_MQTT_ALLOW_INSECURE=1 only for a local test broker)')
    return MqttSettings(enabled=env.get('AEGIS_MQTT_ENABLED', '0') == '1', broker=broker, port=port,
                        topic=topic, tls=tls, ca_cert=env.get('AEGIS_MQTT_CA_CERT', '').strip(),
                        username=username, password=password, error='; '.join(problems))


def secure_client(client, settings):
    """Apply TLS and credentials to a paho client before it connects."""
    if settings.tls:
        client.tls_set(ca_certs=settings.ca_cert or None)  # None: system trust store; certificates are verified
    if settings.username:
        client.username_pw_set(settings.username, settings.password or None)


def identify_device(topic_filter, topic, payload):
    """With a "+" level in the filter, that level of the topic is the device id.

    A broker ACL can restrict each device to its own topic; this stops a payload from
    naming a different device. A shared topic (no "+") keeps the payload's device_uid.
    """
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')
    expected = topic_filter.split('/')
    if '+' not in expected:
        return payload
    actual = topic.split('/')
    if len(actual) != len(expected) or any(e not in ('+', a) for e, a in zip(expected, actual)):
        raise ValueError('Topic does not match the subscribed filter')
    device_uid = actual[expected.index('+')]
    if not device_uid or device_uid != device_uid.strip():
        raise ValueError('Topic carries no usable device id')
    if payload.get('device_uid') not in (None, '', device_uid):
        raise ValueError('device_uid differs from the device id in the topic')
    return dict(payload, device_uid=device_uid)
