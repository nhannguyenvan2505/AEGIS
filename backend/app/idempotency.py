"""Persistent reservations; never automatically take over ambiguous inference work."""
from hashlib import sha256
from .storage import connect


def reserve(config, user_id, key, payload):
    key_hash = sha256(key.encode('ascii')).hexdigest()
    payload_hash = sha256(payload).hexdigest()
    with connect(config) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM inference_requests WHERE user_id=? AND key_hash=?',
                         (user_id, key_hash)).fetchone()
        if row is not None:
            return key_hash, ('conflict' if row['payload_hash'] != payload_hash else row['state']), row['analysis_id']
        db.execute("INSERT INTO inference_requests VALUES (?,?,?,'running',NULL)",
                   (user_id, key_hash, payload_hash))
    return key_hash, 'new', None


def mark_uncertain(config, user_id, key_hash):
    with connect(config) as db:
        db.execute("UPDATE inference_requests SET state='uncertain' WHERE user_id=? AND key_hash=? AND state='running'",
                   (user_id, key_hash))
