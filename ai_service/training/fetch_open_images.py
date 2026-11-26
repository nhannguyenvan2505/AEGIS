"""Download CC BY-only Open Images V7 photos as `people_objects` non_rice negatives.

Output layout (what build_gate_dataset.py expects):
    <out>/<category>/<author_key>/<ImageID>.jpg          + <out>/ATTRIBUTION.csv

Safety rules baked in
  * LICENSE: only images whose License URL is exactly CC BY (creativecommons.org/licenses/by/<ver>/).
    BY-NC / BY-SA / BY-ND / unknown are dropped.
  * Integrity: Flickr original is MD5-checked against OriginalMD5 BEFORE any resize.
  * Changes: images are downsized to --max-side; ATTRIBUTION.csv records this (CC BY asks for changes to be indicated).
  * No plants: images carrying any plant-like label (Plant, Tree, Flower, ...) are excluded so a rice-like
    scene can never be labelled non_rice.
  * Source = photographer, so build_gate_dataset.py keeps one author's photos in one split.
  * Generic User-Agent; no account data is sent.

Metadata URLs below are from memory of the public Open Images layout and were NOT verified here:
the script validates CSV headers at run time and fails loudly; override with --*-url if Google moved them.

    python fetch_open_images.py --out D:/AEGIS-AI/datasets/non_rice_raw --dry-run
    python fetch_open_images.py --out D:/AEGIS-AI/datasets/non_rice_raw --per-label 40
"""
import argparse
import base64
import csv
import datetime
import hashlib
import io
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

BASE = "https://storage.googleapis.com/openimages"
CLASS_DESC_URL = f"{BASE}/v7/oidv7-class-descriptions.csv"
LABELS_URL = {"validation": f"{BASE}/v7/oidv7-val-annotations-human-imagelabels.csv",
              "test": f"{BASE}/v7/oidv7-test-annotations-human-imagelabels.csv"}
IMAGES_URL = {"validation": f"{BASE}/2018_04/validation/validation-images-with-rotation.csv",
              "test": f"{BASE}/2018_04/test/test-images-with-rotation.csv"}
DEFAULT_LABELS = ["Person", "Dog", "Cat", "Chair", "Table", "Car", "Bicycle", "Book", "Laptop", "Mobile phone",
                  "Clothing", "Building", "Cup", "Bottle", "Toy", "Furniture"]
EXCLUDE_LABELS = ["Plant", "Tree", "Flower", "Houseplant", "Fruit", "Vegetable", "Leaf", "Grass", "Crop", "Field",
                  "Food", "Garden", "Agriculture"]
CC_BY_RE = re.compile(r"^https?://creativecommons\.org/licenses/by/\d\.\d/?$")
UA = "dataset-fetch/1.0"
NEED_META = {"ImageID", "OriginalURL", "OriginalLandingURL", "License", "Author", "AuthorProfileURL", "Title", "OriginalMD5"}
NEED_LABELS = {"ImageID", "LabelName", "Confidence"}


def is_cc_by(license_url):
    return bool(CC_BY_RE.match((license_url or "").strip()))


def author_key(profile_url, author, image_id):
    raw = profile_url or author or image_id
    return "oi_" + hashlib.sha1(raw.encode()).hexdigest()[:10]


def fetch(url, cache_dir):
    dst = Path(cache_dir) / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("/", 3)[-1])
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading metadata {url}", file=sys.stderr)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst.with_suffix(dst.suffix + ".part"), "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        dst.with_suffix(dst.suffix + ".part").rename(dst)
    return dst


def read_csv(path, need):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = need - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path}: missing columns {sorted(missing)}; got {reader.fieldnames}. Override --*-url or fix constants.")
        yield from reader


def select_images(label_mids, exclude_mids, label_rows, meta_rows, per_label, seed):
    """Pure selection logic (unit-tested). Returns list of (label_mid, meta_row)."""
    pos = {}
    for r in label_rows:
        if r["Confidence"] == "1":
            pos.setdefault(r["ImageID"], set()).add(r["LabelName"])
    meta = {r["ImageID"]: r for r in meta_rows if is_cc_by(r["License"]) and r["OriginalURL"]}
    rng, chosen, used = random.Random(seed), [], set()
    for mid in label_mids:
        cand = sorted(i for i, labs in pos.items() if mid in labs and not (labs & exclude_mids) and i in meta and i not in used)
        rng.shuffle(cand)
        for i in cand[:per_label]:
            used.add(i); chosen.append((mid, meta[i]))
    return chosen


def download_one(row, dest_dir, max_side, use_thumb):
    url = row["Thumbnail300KURL"] if use_thumb else row["OriginalURL"]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):  # polite retry: Flickr answers 429 when hit too fast
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read(25 * 1024 * 1024)
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == 4:
                raise
            wait = e.headers.get("Retry-After", "")
            time.sleep(min(float(wait) if wait.isdigit() else 2 ** (attempt + 2), 120))
    time.sleep(0.5)
    if not use_thumb and row["OriginalMD5"]:
        if base64.b64encode(hashlib.md5(data).digest()).decode() != row["OriginalMD5"]:
            raise ValueError("MD5 mismatch (image changed or removed upstream)")
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        resized = max(im.size) > max_side
        if resized:
            im.thumbnail((max_side, max_side))
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{row['ImageID']}.jpg"
        im.save(path, quality=90)
    return path, resized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--category", default="people_objects")
    ap.add_argument("--labels", default=",".join(DEFAULT_LABELS), help="comma-separated Open Images display names")
    ap.add_argument("--splits", default="validation", help="validation,test (train metadata is huge; not supported)")
    ap.add_argument("--per-label", type=int, default=40)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--use-thumbnail", action="store_true", help="use Google-hosted 300K thumbnail (reliable, low-res, no MD5 check)")
    ap.add_argument("--dry-run", action="store_true", help="metadata only: report counts, download no images")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--class-desc-url", default=CLASS_DESC_URL)
    a = ap.parse_args()
    out, cache = Path(a.out), Path(a.cache or Path(a.out) / ".oi_cache")

    with open(fetch(a.class_desc_url, cache), newline="", encoding="utf-8") as f:
        names = {row[1].lower(): row[0] for row in csv.reader(f) if len(row) >= 2}
    want = [n.strip() for n in a.labels.split(",") if n.strip()]
    label_mids = [names[n.lower()] for n in want if n.lower() in names]
    for n in want:
        if n.lower() not in names:
            print(f"WARN label not in class list: {n}", file=sys.stderr)
    exclude_mids = {names[n.lower()] for n in EXCLUDE_LABELS if n.lower() in names}
    for n in EXCLUDE_LABELS:
        if n.lower() not in names:
            print(f"WARN exclude label not in class list: {n}", file=sys.stderr)

    chosen = []
    for split in a.splits.split(","):
        if split not in LABELS_URL:
            raise SystemExit(f"unsupported split {split}")
        label_rows = list(read_csv(fetch(LABELS_URL[split], cache), NEED_LABELS))
        meta_rows = list(read_csv(fetch(IMAGES_URL[split], cache), NEED_META | {"Thumbnail300KURL"}))
        sel = select_images(label_mids, exclude_mids, label_rows, meta_rows, a.per_label, a.seed)
        print(f"{split}: {len(sel)} CC BY images selected from {len(meta_rows)} metadata rows", file=sys.stderr)
        chosen += sel
    authors = len({author_key(r["AuthorProfileURL"], r["Author"], r["ImageID"]) for _, r in chosen})
    print(f"selected {len(chosen)} images from {authors} distinct authors (more authors = better leakage-free splitting)")
    if a.dry_run or not chosen:
        return

    today, ok, failed = datetime.date.today().isoformat(), 0, 0
    attr_path = out / "ATTRIBUTION.csv"
    new_file = not attr_path.exists()
    out.mkdir(parents=True, exist_ok=True)
    with open(attr_path, "a", newline="", encoding="utf-8") as af, ThreadPoolExecutor(a.workers) as pool:
        w = csv.writer(af)
        if new_file:
            w.writerow(["file", "image_id", "title", "author", "author_profile_url", "landing_url", "license_url", "changes", "downloaded"])
        jobs = {}
        for _, r in chosen:
            d = out / a.category / author_key(r["AuthorProfileURL"], r["Author"], r["ImageID"])
            if (d / f"{r['ImageID']}.jpg").exists():
                continue
            jobs[pool.submit(download_one, r, d, a.max_side, a.use_thumbnail)] = r
        for fut in as_completed(jobs):
            r = jobs[fut]
            try:
                path, resized = fut.result()
            except Exception as e:  # dead links are normal for Flickr originals
                failed += 1; print(f"skip {r['ImageID']}: {e}", file=sys.stderr); continue
            ok += 1
            w.writerow([path.relative_to(out).as_posix(), r["ImageID"], r["Title"], r["Author"], r["AuthorProfileURL"], r["OriginalLandingURL"],
                        r["License"], f"converted to JPEG{'; resized to max side %d px' % a.max_side if resized else ''}", today])
    print(f"downloaded {ok}, skipped {failed}. Record the run in docs/DATA_SOURCES.md (version, date, counts).")


if __name__ == "__main__":
    main()
