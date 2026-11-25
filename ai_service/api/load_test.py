"""Concurrent load check for a running AI service (POST /v2/diagnose).

    python load_test.py --url http://127.0.0.1:8000 --images DIR [--concurrency 1 2 4 8] [--requests 60]

Every image is first sent alone to record its answer; the same image under load must get the same
answer. The only accepted failure is HTTP 503 ai_busy (admission limit). Exits 1 on anything else.
Latency is measured by this client, so it includes the upload and decoding.
"""
import argparse
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def diagnose(url, payload):
    started = time.perf_counter()
    response = requests.post(url + "/v2/diagnose", files={"image": ("image", payload)}, timeout=120)
    elapsed = (time.perf_counter() - started) * 1000
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body, elapsed


def answer(body):
    """The parts of a result that must not change with load."""
    return (body.get("status"), tuple((d["class_id"], round(d["confidence"], 2)) for d in body.get("detections", [])),
            round(body.get("gatekeeper", {}).get("rice_probability", -1.0), 2))


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--images", type=Path, required=True, help="folder with a few test images, ideally mixed")
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--requests", type=int, default=60, help="requests per concurrency level")
    ap.add_argument("--json", type=Path, help="also write the report here")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    payloads = [p.read_bytes() for p in sorted(a.images.iterdir()) if p.suffix.lower() in SUFFIXES]
    if not payloads:
        sys.exit(f"No images in {a.images}")

    reference = []
    for payload in payloads:
        status, body, _ = diagnose(url, payload)
        if status != 200:
            sys.exit(f"Reference request failed: HTTP {status} {body.get('error')}")
        reference.append(answer(body))
    report = {"images": len(payloads), "statuses_in_reference": dict(Counter(r[0] for r in reference)), "levels": []}
    failures = 0

    for level in a.concurrency:
        def one(i):
            index = i % len(payloads)
            try:
                status, body, elapsed = diagnose(url, payloads[index])
            except requests.RequestException as exc:
                return type(exc).__name__, 0.0
            if status == 200:
                return ("ok" if answer(body) == reference[index] else "different_answer"), elapsed
            code = body.get("error", {}).get("code")
            return ("ai_busy" if (status, code) == (503, "ai_busy") else f"http_{status}_{code}"), elapsed

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            rows = list(pool.map(one, range(a.requests)))
        wall = time.perf_counter() - started
        outcomes = Counter(outcome for outcome, _ in rows)
        latencies = [ms for outcome, ms in rows if outcome == "ok"]
        failures += sum(n for outcome, n in outcomes.items() if outcome not in ("ok", "ai_busy"))
        report["levels"].append({
            "concurrency": level, "requests": a.requests, "outcomes": dict(outcomes),
            "ok_per_second": round(len(latencies) / wall, 2),
            "ok_p50_ms": round(statistics.median(latencies), 1) if latencies else None,
            "ok_p95_ms": round(percentile(latencies, 0.95), 1) if latencies else None,
            "ok_max_ms": round(max(latencies), 1) if latencies else None})

    status, health, _ = (lambda r: (r.status_code, r.json(), 0))(requests.get(url + "/health", timeout=10))
    report.update(health_after={"http": status, "status": health.get("status"), "device": health.get("device")},
                  unexpected_failures=failures)
    text = json.dumps(report, indent=2)
    print(text)
    if a.json:
        a.json.write_text(text + "\n", encoding="utf-8")
    sys.exit(1 if failures or status != 200 else 0)


if __name__ == "__main__":
    main()
