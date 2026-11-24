"""In-process background dispatcher for the Mongo outbox (BE-02).

Replaces delivery in `after_request`: API responses never wait for Mongo.
Several processes may each run a dispatcher; events are claimed with
SKIP LOCKED, so they never deliver the same row concurrently. Set
AEGIS_MONGO_DELIVERY_ENABLED=0 to run `database/deliver_outbox.py --poll`
as a separate process instead.
"""
import logging
import threading

log = logging.getLogger('aegis.outbox')
_registry = {}
_registry_lock = threading.Lock()


class OutboxDispatcher(threading.Thread):
    def __init__(self, config, interval, batch):
        super().__init__(name='aegis-outbox-dispatcher', daemon=True)
        self.config, self.interval, self.batch = config, interval, batch
        self.stopped = threading.Event()
        self.last_result = None
        self.last_error = None

    def run(self):
        from .mongo_delivery import deliver
        errors = 0
        while not self.stopped.is_set():
            try:
                result = deliver(self.config, limit=self.batch)
                self.last_result, self.last_error, errors = result, None, 0
                if result['parked']:
                    log.warning('Mongo outbox parked %d failed event(s)', result['parked'])
                if result['delivered'] == self.batch:
                    continue  # More may be due; drain without waiting.
                wait = self.interval
            except Exception as exc:  # Keep running; MySQL/Mongo may come back.
                errors += 1
                self.last_error = type(exc).__name__
                log.error('Mongo outbox dispatch failed: %s', self.last_error)
                wait = min(60, self.interval * 2 ** min(errors, 5))
            self.stopped.wait(wait)

    def stop(self, timeout=10):
        self.stopped.set()
        self.join(timeout)


def start_dispatcher(app):
    """Start one dispatcher per process and MySQL database; returns it."""
    mysql = app.config['MYSQL']
    key = (mysql.get('host'), mysql.get('port'), mysql.get('database'))
    with _registry_lock:
        current = _registry.get(key)
        if current is not None and current.is_alive():
            return current
        dispatcher = OutboxDispatcher(dict(app.config),
                                      float(app.config.get('MONGO_DELIVERY_INTERVAL_SECONDS', 2)),
                                      int(app.config.get('MONGO_DELIVERY_BATCH', 100)))
        dispatcher.start()
        _registry[key] = dispatcher
        return dispatcher
