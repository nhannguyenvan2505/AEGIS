"""Assemble the Stage-1 gatekeeper dataset (ImageFolder) with leakage control.

rice      : EITHER --rice  AEGIS v4 images (reuses its group split; 5,174 images, 3 disease classes)
            OR     --raw-originals "<RiceLeafDiseaseBD>/Original images" (all 6 folders incl. Healthy,
                   Tungro, Leaf smut) + --v4-manifest [+ --v4-excluded]. Near-duplicate components
                   (exact sha256 or dHash Hamming <= 5) are kept in ONE split; components touching a
                   v4 image inherit its split; conflicting / v4-excluded components are dropped; all
                   others get a hash-based 70/15/15 split.
non_rice  : user-collected folder  NEG/<category>/<source>/*.jpg
            category in HARD = weeds, other_crops, soil_water, people_objects,
            text_screens, blurry   (easy = anything else, e.g. "random")
            <source> = one field / site / photographer / website. Whole sources go to one
            split (hash of source name), so near-identical shots never straddle splits.

    python build_gate_dataset.py --rice D:/AEGIS-AI/datasets/processed/aegis_rice_v4/images \
        --neg D:/AEGIS-AI/datasets/non_rice_raw --out D:/AEGIS-AI/datasets/gate_v1 [--copy]

Also drops exact duplicates (sha256) and near duplicates (8x8 average hash, Hamming <= 3)
across ALL splits, and writes gate_manifest.json with counts and warnings.
"""
import argparse
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

EXT = {".jpg", ".jpeg", ".png", ".webp"}
HARD = {"weeds", "other_crops", "soil_water", "people_objects", "text_screens", "blurry"}


def split_for(source, ratios=(0.70, 0.15, 0.15)):
    v = int(hashlib.sha256(source.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if v < ratios[0] else "val" if v < ratios[0] + ratios[1] else "test"


def ahash(path):
    with Image.open(path) as im:
        g = np.asarray(im.convert("L").resize((8, 8), Image.BILINEAR), dtype=np.float32)
    return int("".join("1" if b else "0" for b in (g > g.mean()).ravel()), 2)


def place(src, dst, copy):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    if copy:
        shutil.copy2(src, dst)
    else:
        try:
            os.link(src, dst)  # hard link: no extra disk, same volume
        except OSError:
            shutil.copy2(src, dst)


def dhash(path):
    with Image.open(path) as im:
        im.draft("L", (128, 128))
        g = np.asarray(im.convert("L").resize((9, 8), Image.BILINEAR), dtype=np.float32)
    bits = (g[:, 1:] > g[:, :-1]).ravel()
    return int("".join("1" if b else "0" for b in bits), 2)


def gather_rice_grouped(raw_root, manifest_path, excluded_path, max_hamming=5):
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))
    known = {norm(m["image"]): m["split"] for m in json.loads(Path(manifest_path).read_text(encoding="utf-8"))}
    excluded = {norm(e["image"]) for e in json.loads(Path(excluded_path).read_text(encoding="utf-8"))} if excluded_path else set()
    files = [p for p in sorted(Path(raw_root).rglob("*")) if p.suffix.lower() in EXT]
    if not files:
        raise SystemExit(f"no images under {raw_root}")
    n = len(files)
    sha = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    H = np.array([dhash(p) for p in files], dtype=np.uint64)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    first = {}
    for i, h in enumerate(sha):
        union(i, first.setdefault(h, i))
    table = np.array([bin(b).count("1") for b in range(256)], dtype=np.uint8)
    for start in range(0, n, 256):
        x = (H[start:start + 256, None] ^ H[None, :]).view(np.uint8).reshape(-1, n, 8)
        dist = table[x].sum(axis=2)
        for a, b in zip(*np.nonzero(dist <= max_hamming)):
            union(start + int(a), int(b))

    comps = defaultdict(list)
    for i in range(n):
        comps[find(i)].append(i)
    items, stats = [], Counter()
    for root, members in comps.items():
        paths = [norm(files[i]) for i in members]
        splits = {known[p] for p in paths if p in known}
        if any(p in excluded for p in paths):
            stats["dropped_v4_excluded_component"] += len(members); continue
        if len(splits) > 1:
            stats["dropped_split_conflict_component"] += len(members); continue
        split = next(iter(splits)) if splits else split_for("grp:" + sha[root])
        stats["inherited_from_v4" if splits else "newly_assigned"] += len(members)
        for i in members:
            p = files[i]
            items.append((p, "rice", split, "rice", p.parent.name.lower().replace(" ", "_")))
    GROUP_STATS.update(stats); GROUP_STATS["components"] = len(comps); GROUP_STATS["images"] = n
    return sorted(items, key=lambda t: str(t[0]))


GROUP_STATS = Counter()


def gather(rice_root, neg_root, grouped=None):
    items = list(grouped) if grouped is not None else []  # (path, label, split, category, source)
    for split in ("train", "val", "test") if grouped is None else ():
        for p in sorted((Path(rice_root) / split).glob("*")):
            if p.suffix.lower() in EXT:
                items.append((p, "rice", split, "rice", p.stem.split("__")[0]))
    for p in sorted(Path(neg_root).rglob("*")):
        if p.suffix.lower() not in EXT:
            continue
        rel = p.relative_to(neg_root).parts
        if len(rel) < 3:
            raise SystemExit(f"{p}: expected NEG/<category>/<source>/file, got depth {len(rel)}")
        items.append((p, "non_rice", split_for(f"{rel[0]}/{rel[1]}"), rel[0], rel[1]))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rice", help="AEGIS v4 images root (train/val/test)")
    ap.add_argument("--raw-originals", help="RiceLeafDiseaseBD 'Original images' root (all classes)")
    ap.add_argument("--v4-manifest")
    ap.add_argument("--v4-excluded")
    ap.add_argument("--neg", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--copy", action="store_true")
    a = ap.parse_args()

    if bool(a.rice) == bool(a.raw_originals):
        raise SystemExit("give exactly one of --rice or --raw-originals")
    if a.raw_originals and not a.v4_manifest:
        raise SystemExit("--raw-originals needs --v4-manifest to inherit v4 splits")
    grouped = gather_rice_grouped(a.raw_originals, a.v4_manifest, a.v4_excluded) if a.raw_originals else None
    items, seen_sha, hashes, kept, dropped = gather(a.rice, a.neg, grouped), set(), [], [], Counter()
    for path, label, split, cat, src in items:
        try:
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            h = ahash(path)
        except Exception:
            dropped["unreadable"] += 1
            continue
        if sha in seen_sha:
            dropped["exact_duplicate"] += 1
            continue
        if any(bin(h ^ o).count("1") <= 3 and ol != label for o, ol in hashes):
            dropped["cross_label_near_duplicate"] += 1  # same-looking image labelled both ways
            continue
        seen_sha.add(sha); hashes.append((h, label)); kept.append((path, label, split, cat, src))

    counts, cats = Counter(), Counter()
    for path, label, split, cat, src in kept:
        place(path, Path(a.out) / split / label / f"{src}__{path.name}".replace(" ", "_"), a.copy)
        counts[(split, label)] += 1
        if label == "non_rice":
            cats[cat] += 1

    neg_total = sum(cats.values())
    hard = sum(n for c, n in cats.items() if c in HARD)
    warnings = []
    if neg_total == 0:
        warnings.append("no non_rice images: dataset unusable")
    elif hard / neg_total < 0.5:
        warnings.append(f"hard negatives only {hard / neg_total:.0%} of non_rice (target >= 50%)")
    for c in HARD - set(cats):
        warnings.append(f"missing hard-negative category: {c}")
    r_tr, r_all = counts[("train", "rice")], sum(n for (_, l), n in counts.items() if l == "rice")
    if neg_total and r_all > 2 * neg_total:
        warnings.append(f"rice:non_rice = {r_all}:{neg_total} (> 2:1): use class weights or cap rice per class when training")
    for s in ("val", "test"):
        if counts[(s, "non_rice")] < 100:
            warnings.append(f"{s} has {counts[(s, 'non_rice')]} non_rice images: FPR estimate will be too coarse (need >=100, ideally 300+)")
    manifest = {"counts": {f"{s}/{l}": n for (s, l), n in sorted(counts.items())}, "non_rice_categories": dict(cats),
                "dropped": dict(dropped), "rice_grouping": dict(GROUP_STATS), "warnings": warnings,
                "rice_note": "rice split inherited from v4 group split; rice images are mostly leaf close-ups: add field/mid-range rice shots before trusting recall"}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "gate_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
