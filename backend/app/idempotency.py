"""Persistent reservations; never automatically take over ambiguous inference work."""
from hashlib import sha256
import time
from .repositories import repository as connect


def reserve(config, user_id, key, payload):
    key_hash = sha256(key.encode('ascii')).hexdigest()
    payload_hash = sha256(payload).hexdigest()
    with connect(config) as db:
        state, analysis_id = db.reserve(user_id, key_hash, payload_hash, int(time.time()),
                                        config.get('IDEMPOTENCY_RUNNING_TTL_SECONDS', 300))
    return key_hash, state, analysis_id


def release(config, user_id, key_hash):
    with connect(config) as db:
        db.release(user_id, key_hash)


def mark_uncertain(config, user_id, key_hash):
    with connect(config) as db:
        db.mark_uncertain(user_id, key_hash)
