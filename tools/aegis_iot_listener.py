"""Standalone ESP32 MQTT listener with console alerts and AEGIS DB persistence."""
import argparse
import json
import os
from pathlib import Path
import sys

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.database_config import settings
from app.iot_mqtt import evaluate_microclimate, save_esp32_reading
from app.mqtt_settings import identify_device, load_mqtt_settings, secure_client


def runtime_config(storage_backend='mysql'):
    cfg = dict(settings())
    cfg['STORAGE_BACKEND'] = storage_backend
    cfg['DATABASE_PATH'] = ROOT / 'backend/instance/aegis.sqlite3'
    return cfg


def print_reading(saved):
    alert = saved['alert']
    print(f"\n📡 [TELEMETRY THỰC TẾ] Thiết bị: {saved['device_uid']}")
    print(f"   🌡️ Nhiệt độ không khí: {saved['temperature']} °C | 💧 Độ ẩm không khí: {saved['humidity']} %")
    if alert['disease'] == 'rice_blast':
        print(f"   ⚠️  🔴 [CẢNH BÁO CAO] {alert['message']}")
    elif alert['disease'] == 'sheath_blight':
        print(f"   ⚠️  🟠 [CẢNH BÁO TRUNG BÌNH] {alert['message']}")
    elif alert['disease'] == 'brown_spot':
        print(f"   ⚠️  🟡 [CẢNH BÁO SỚM] {alert['message']}")
    else:
        print(f"   ✅ {alert['message']}")
    print('-' * 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--broker', help='Overrides AEGIS_MQTT_BROKER')
    parser.add_argument('--port', type=int, help='Overrides AEGIS_MQTT_PORT')
    parser.add_argument('--topic', help='Overrides AEGIS_MQTT_TOPIC')
    parser.add_argument('--storage', choices=('mysql', 'sqlite'), default='mysql')
    parser.add_argument('--no-save', action='store_true', help='Only print alerts without writing to DB')
    args = parser.parse_args()
    # Credentials come only from the environment so they never appear in a command line.
    overrides = {'AEGIS_MQTT_BROKER': args.broker, 'AEGIS_MQTT_PORT': args.port, 'AEGIS_MQTT_TOPIC': args.topic}
    mqtt_settings = load_mqtt_settings({**os.environ, **{k: str(v) for k, v in overrides.items() if v is not None}})
    if mqtt_settings.error:
        parser.error(mqtt_settings.error)

    cfg = runtime_config(args.storage)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        code = getattr(reason_code, 'value', reason_code)
        if code == 0 or str(reason_code) == 'Success':
            print('-> Đã kết nối MQTT Broker thành công!')
            client.subscribe(mqtt_settings.topic)
            print(f'-> Đang lắng nghe luồng dữ liệu từ topic: {mqtt_settings.topic}\n' + '=' * 60)
        else:
            print(f'-> Kết nối thất bại với mã lỗi: {reason_code}')

    def on_message(client, userdata, msg):
        try:
            payload = identify_device(mqtt_settings.topic, msg.topic, json.loads(msg.payload.decode('utf-8')))
            if args.no_save:
                temp = float(payload.get('temperature'))
                hum = float(payload.get('humidity'))
                saved = {
                    'device_uid': payload.get('device_uid', 'Unknown'),
                    'temperature': temp,
                    'humidity': hum,
                    'alert': evaluate_microclimate(temp, hum),
                }
            else:
                saved = save_esp32_reading(cfg, payload, topic=msg.topic, source='esp32_mqtt')
            print_reading(saved)
        except Exception as exc:
            print(f'❌ Lỗi giải mã/lưu gói tin: {exc}')

    if hasattr(mqtt, 'CallbackAPIVersion'):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    else:
        client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    secure_client(client, mqtt_settings)
    print('Đang kết nối đến máy chủ MQTT...')
    client.connect(mqtt_settings.broker, mqtt_settings.port, 60)
    client.loop_forever()


if __name__ == '__main__':
    main()

