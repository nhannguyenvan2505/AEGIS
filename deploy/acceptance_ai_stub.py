"""Stand-in for the AI service, used by deploy/acceptance.py only. Standard library only.

It answers every upload with one fixed /v2/diagnose result, so the acceptance run can
follow an analysis through the proxy, backend, MySQL, image volume and MongoDB without
model weights. It looks at no image and says nothing about the real models.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


def answer(request_id):
    return dict(request_id=request_id, status='disease_detected', is_rice=True, message='Acceptance stand-in.',
                model_version='acceptance-stub', model_sha256='0' * 64, processing_ms=1,
                image=dict(width=32, height=32),
                detections=[dict(class_id=0, class_name='rice_blast', confidence=0.9, bbox_xyxy=[1, 2, 10, 12])])


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if self.path != '/v2/diagnose':
            self.send_error(404)
            return
        body = json.dumps(answer(self.headers.get('X-Request-ID', ''))).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
