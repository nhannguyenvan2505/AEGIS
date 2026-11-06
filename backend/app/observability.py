"""Request correlation and payload-free completion logs."""
import json
import logging
import time
import uuid

from flask import g, request


def init_observability(app):
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        # Public boundary always generates a new ID; client IDs are untrusted.
        g.request_id = str(uuid.uuid4())
        g.request_started = time.perf_counter()

    @app.after_request
    def complete_request(response):
        duration = round((time.perf_counter() - g.request_started) * 1000, 3)
        response.headers['X-Request-ID'] = g.request_id
        response.headers['X-Processing-Time-Ms'] = str(duration)
        if response.status_code >= 400 and response.is_json:
            body = response.get_json()
            if isinstance(body, dict):
                body['request_id'] = g.request_id
                response.set_data(app.json.dumps(body) + '\n')
        event = dict(event='request_completed', service='aegis-backend', request_id=g.request_id,
                     method=request.method, route=request.url_rule.rule if request.url_rule else 'unmatched',
                     status=response.status_code, processing_ms=duration)
        for key in ['analysis_id', 'model_sha256', 'ai_error_code']:
            if hasattr(g, key):
                event[key] = getattr(g, key)
        # Never log tokens, passwords, multipart filenames, bytes or query strings.
        app.logger.info(json.dumps(event, ensure_ascii=True))
        return response
