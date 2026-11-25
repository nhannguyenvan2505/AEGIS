"""Run the ESP32 MQTT listener as its own process, next to the backend.

Use it when the web server must not subscribe (several workers or restarts would
each take a copy of the feed): start this one process with AEGIS_MQTT_ENABLED=1 and
start the backend with AEGIS_MQTT_ENABLED=0. Give both the same
AEGIS_MQTT_STATUS_FILE so the administrator view still shows the listener.
Messages published while this process is down are not replayed.

    python database/run_mqtt.py            # subscribe until stopped
    python database/run_mqtt.py --check    # exit 0 when a fresh report says connected
"""
import argparse
import logging
import os
from pathlib import Path
import signal
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import settings  # noqa: E402
from app.iot_mqtt import MqttTelemetryService  # noqa: E402
from app.mqtt_status import read_status, write_status  # noqa: E402
from app.repositories.mysql import check_schema  # noqa: E402

HEARTBEAT_SECONDS = 5
_LOGGER = logging.getLogger(__name__)


def runtime_config():
    config = dict(settings(), STORAGE_BACKEND='mysql')
    check_schema(config)
    return config


def serve(service, status_path, stop, interval=HEARTBEAT_SECONDS):
    """Report until `stop` is set, then disconnect and say so."""
    def report():
        if status_path:
            try:
                write_status(status_path, service.status())
            except OSError as exc:  # subscribing matters more than reporting
                _LOGGER.warning('Could not write the MQTT status file: %s', exc)

    try:
        while not stop.is_set():
            report()
            stop.wait(interval)
    finally:
        service.stop()
        report()


def check(status_path):
    return 0 if read_status(status_path)['connected'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='report health from the status file and exit')
    args = parser.parse_args(argv)
    status_path = os.environ.get('AEGIS_MQTT_STATUS_FILE')
    if args.check:
        if not status_path:
            sys.exit('--check needs AEGIS_MQTT_STATUS_FILE')
        sys.exit(check(status_path))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    service = MqttTelemetryService(runtime_config())
    if not service.settings.enabled:
        sys.exit('Set AEGIS_MQTT_ENABLED=1 for the listener process.')
    service.start()
    if not service.started:
        sys.exit(service.status()['last_error'] or 'MQTT listener did not start')
    stop = threading.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: stop.set())
    serve(service, status_path, stop)


if __name__ == '__main__':
    main()
