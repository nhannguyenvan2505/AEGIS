"""Smoke check of a running AI service, for deployments and CI. Standard library only.

    python smoke_check.py --url http://127.0.0.1:8000 --expect ready
    python smoke_check.py --url http://127.0.0.1:8000 --expect degraded   # no gatekeeper weights

It checks that the service answers and which models it runs, not whether the models are accurate.
"""
import argparse
import json
import random
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib


def noise_png(size=128):
    """A textured RGB image that passes the quality checks, so the gatekeeper has to judge it."""
    rng = random.Random(0)
    rows = b"".join(b"\x00" + bytes(rng.getrandbits(8) for _ in range(size * 3)) for _ in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def call(request):
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def diagnose(url):
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="smoke.png"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode() + noise_png() + f"\r\n--{boundary}--\r\n".encode()
    return call(urllib.request.Request(url + "/v2/diagnose", data=body,
                                       headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}))


def wait_for_health(url, seconds):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return call(url + "/health")
        except (OSError, ValueError) as error:  # not listening yet, or not answering JSON yet
            if time.monotonic() >= deadline:
                sys.exit(f"FAIL service did not answer within {seconds}s: {type(error).__name__}")
            time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--expect", choices=["ready", "degraded"], default="ready")
    ap.add_argument("--wait", type=int, default=0, help="seconds to wait for the service to start answering")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    failures = []

    def check(name, passed, seen):
        print(f"{'pass' if passed else 'FAIL'}  {name}: {seen}")
        if not passed:
            failures.append(name)

    status, health = wait_for_health(url, a.wait)
    gate = health.get("gatekeeper", {})
    wanted = 200 if a.expect == "ready" else 503
    check("health", (status, health.get("status")) == (wanted, a.expect), f"HTTP {status} {health.get('status')}")
    check("detector is the released file", health.get("model_pinned") is True, health.get("model_pinned"))
    status, result = diagnose(url)
    if a.expect == "ready":
        check("gatekeeper is the released file", gate.get("pinned") is True, gate.get("version"))
        check("diagnose answers", (status, result.get("schema_version")) == (200, "2.0"),
              f"HTTP {status} {result.get('status')}")
        used = result.get("gatekeeper", {}).get("sha256")
        check("diagnose used that gatekeeper", bool(used) and used == gate.get("sha256"), str(used)[:12])
    else:
        code = result.get("error", {}).get("code")
        check("diagnose refuses without a gatekeeper", (status, code) == (503, "gatekeeper_unavailable"),
              f"HTTP {status} {code}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
