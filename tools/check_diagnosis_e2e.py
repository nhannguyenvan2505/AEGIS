"""End-to-end check of image diagnosis through a running Backend and its real AI service.

    python tools/check_diagnosis_e2e.py --url http://127.0.0.1:5000 --images FOLDER [--json report.json]

FOLDER holds a few test images; it should include rice with visible disease and something that is
not rice. The check verifies the API contract (upload, replay, detail, history, image download,
owner isolation, rejections, refused files). It does NOT judge whether a diagnosis is correct.

It creates two throwaway accounts and stores analyses: run it against a test environment only.
Raise DETECT_USER_LIMIT there, or it will wait on 429 answers. Exit 1 if any check fails.
"""
import argparse
import json
import re
import statistics
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import requests

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
STATUSES = ("disease_detected", "uncertain_lesion", "healthy")
REJECTIONS = ("rejected_non_rice", "rejected_poor_quality", "rejected_uncertain_scope")


class Checker:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.failures = []
        self.checks = 0

    def expect(self, passed, what, seen=""):
        self.checks += 1
        if not passed:
            self.failures.append(f"{what}: {str(seen)[:300]}")

    def account(self):
        credentials = {"email": f"e2e-{uuid.uuid4().hex}@example.test", "password": "e2e-" + uuid.uuid4().hex}
        requests.post(self.url + "/api/auth/register", json=credentials, timeout=30).raise_for_status()
        login = requests.post(self.url + "/api/auth/login", json=credentials, timeout=30)
        login.raise_for_status()
        return {"Authorization": "Bearer " + login.json()["access_token"]}

    def get(self, headers, path):
        return requests.get(self.url + path, headers=headers, timeout=60)

    def detect(self, headers, payload, key):
        while True:
            response = requests.post(self.url + "/api/disease/detect", headers={**headers, "Idempotency-Key": key},
                                     files={"image": ("e2e.jpg", payload)}, timeout=120)
            if response.status_code != 429:
                return response
            time.sleep(int(response.headers.get("Retry-After", "5")))

    def history(self, headers):
        items, page = {}, 1
        while True:
            response = self.get(headers, f"/api/disease/analyses?page={page}&page_size=100")
            response.raise_for_status()
            body = response.json()
            items.update({item["analysis_id"]: item for item in body["items"]})
            if not body["pagination"]["has_next"]:
                return items
            page += 1


def by_id(detections):
    return sorted(detections, key=lambda d: d["detection_id"])


def check_accepted(c, owner, other, payload, key, created, name):
    diagnosis = created.get("diagnosis") or {}
    status = diagnosis.get("status")
    boxes = created["detections"]
    c.expect(status in STATUSES and diagnosis.get("is_rice") is True and bool(diagnosis.get("message")),
             f"{name} diagnosis object", diagnosis)
    expected = "detection_found" if status == "disease_detected" else "no_detection"
    c.expect(created["status"] == expected and bool(boxes) == (status == "disease_detected"),
             f"{name} status agrees with boxes", (created["status"], status, len(boxes)))
    c.expect(all(d.get("confidence_level") == ("likely" if d["confidence"] >= 0.5 else "low")
                 and d.get("confidence_label") for d in boxes), f"{name} FR09 labels", boxes)
    c.expect(bool(re.fullmatch("[0-9a-f]{64}", created.get("model_sha256", ""))), f"{name} model digest")

    replay = c.detect(owner, payload, key)
    c.expect(replay.status_code == 200 and replay.headers.get("Idempotency-Replayed") == "true",
             f"{name} replay", (replay.status_code, replay.text))
    path = "/api/disease/analyses/" + created["analysis_id"]
    detail = c.get(owner, path)
    for label, response in (("replay", replay), ("detail", detail)):
        body = response.json() if response.status_code == 200 else {}
        c.expect(body.get("diagnosis") == diagnosis and by_id(body.get("detections", [])) == by_id(boxes)
                 and body.get("status") == created["status"], f"{name} {label} equals the first answer", body)
    image = c.get(owner, path + "/image")
    c.expect(image.status_code == 200 and image.content == payload, f"{name} stored image bytes", image.status_code)
    for suffix in ("", "/image"):
        code = c.get(other, path + suffix).status_code
        c.expect(code == 404, f"{name} hidden from another account {suffix or '/detail'}", code)


def run(c, images):
    owner, other = c.account(), c.account()
    outcomes, latencies, accepted = Counter(), [], {}
    answered = 0
    for path in images:
        payload, key, name = path.read_bytes(), "e2e-" + uuid.uuid4().hex, path.name
        before = len(c.history(owner))
        started = time.perf_counter()
        response = c.detect(owner, payload, key)
        elapsed = (time.perf_counter() - started) * 1000
        c.expect(response.status_code == 200, f"{name} upload", (response.status_code, response.text))
        if response.status_code != 200:
            continue
        answered += 1
        body = response.json()
        if body.get("rejected"):
            outcomes[body["status"]] += 1
            c.expect(body["status"] in REJECTIONS and bool(body.get("message")) and body.get("detections") == [],
                     f"{name} rejection shape", body)
            c.expect(len(c.history(owner)) == before, f"{name} rejection is not stored")
            again = c.detect(owner, payload, key)  # a rejection must not keep the key
            answered += again.status_code == 200
            c.expect(again.status_code == 200 and again.json().get("status") == body["status"],
                     f"{name} key reusable after rejection", (again.status_code, again.text))
        else:
            latencies.append(elapsed)
            outcomes[(body.get("diagnosis") or {}).get("status", "missing")] += 1
            accepted[body["analysis_id"]] = body.get("diagnosis")
            check_accepted(c, owner, other, payload, key, body, name)
            c.expect(len(c.history(owner)) == before + 1, f"{name} stored exactly once")

    listed = c.history(owner)
    c.expect(set(listed) == set(accepted), "history lists exactly the accepted uploads", (len(listed), len(accepted)))
    for analysis_id, diagnosis in accepted.items():
        item = listed.get(analysis_id, {})
        c.expect(item.get("diagnosis") == diagnosis, "history item carries the same diagnosis", item)
    c.expect(not c.history(other), "the other account sees no history")

    stored = len(listed)
    key = "e2e-refused-" + uuid.uuid4().hex
    broken = c.detect(owner, b"this is not an image", key)
    c.expect((broken.status_code, broken.json().get("error", {}).get("code")) == (400, "invalid_image"),
             "a non-image is refused", (broken.status_code, broken.text))
    huge = c.detect(owner, b"x" * (8 * 1024 * 1024 + 1), "e2e-huge-" + uuid.uuid4().hex)
    c.expect((huge.status_code, huge.json().get("error", {}).get("code")) == (413, "upload_too_large"),
             "a file over 8 MiB is refused", (huge.status_code, huge.text))
    c.expect(len(c.history(owner)) == stored, "refused files are not stored")
    if images:
        fixed = c.detect(owner, images[0].read_bytes(), key)
        answered += fixed.status_code == 200
        c.expect(fixed.status_code == 200, "the key of a refused file works for a good one", (fixed.status_code, fixed.text))

    c.expect(outcomes["disease_detected"] > 0, "coverage: no image produced disease_detected", dict(outcomes))
    c.expect(any(outcomes[name] for name in REJECTIONS), "coverage: no image was rejected", dict(outcomes))
    ordered = sorted(latencies)
    return {"images": len(images), "outcomes": dict(sorted(outcomes.items())), "ai_answers": answered,
            "accepted_upload_ms": {
                "n": len(ordered), "p50": round(statistics.median(ordered), 1) if ordered else None,
                "max": round(ordered[-1], 1) if ordered else None}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Backend base URL of a TEST environment")
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    images = sorted(p for p in a.images.iterdir() if p.suffix.lower() in SUFFIXES)
    if not images:
        sys.exit(f"No images in {a.images}")
    checker = Checker(a.url)
    report = run(checker, images)
    report.update(checks=checker.checks, failed=len(checker.failures), failures=checker.failures)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if a.json:
        a.json.write_text(text + "\n", encoding="utf-8")
    sys.exit(1 if checker.failures else 0)


if __name__ == "__main__":
    main()
