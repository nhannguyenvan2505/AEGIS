"""Standalone ESP32 MQTT listener with console alerts and AEGIS DB persistence."""
import argparse
import json
from pathlib import Path
import sys

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.database_config import settings
from app.iot_mqtt import (
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC,
    evaluate_microclimate,
    save_esp32_reading,
)


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
    parser.add_argument('--broker', default=DEFAULT_MQTT_BROKER)
    parser.add_argument('--port', type=int, default=DEFAULT_MQTT_PORT)
    parser.add_argument('--topic', default=DEFAULT_MQTT_TOPIC)
    parser.add_argument('--storage', choices=('mysql', 'sqlite'), default='mysql')
    parser.add_argument('--no-save', action='store_true', help='Only print alerts without writing to DB')
    args = parser.parse_args()

    cfg = runtime_config(args.storage)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        code = getattr(reason_code, 'value', reason_code)
        if code == 0 or str(reason_code) == 'Success':
            print('-> Đã kết nối MQTT Broker thành công!')
            client.subscribe(args.topic)
            print(f'-> Đang lắng nghe luồng dữ liệu từ topic: {args.topic}\n' + '=' * 60)
        else:
            print(f'-> Kết nối thất bại với mã lỗi: {reason_code}')

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
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
    print('Đang kết nối đến máy chủ MQTT...')
    client.connect(args.broker, args.port, 60)
    client.loop_forever()


if __name__ == '__main__':
    main()

