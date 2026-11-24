"""Import downloaded public non-rice datasets into non_rice_raw/<category>/<source>/ (zip-slip safe).

PlantDoc   (CC BY 4.0)  -> other_crops/plantdoc_<class>_<bucket>/   (classes are NOT rice; corn = nearest grass)
Dryad grasses (CC0, doi:10.5061/dryad.gtht76hhz, Beck et al.) -> weeds/dryad_<species>_<YYYYMMDD>/
           only the grass species (BarnyardGrass, YellowFoxtail, WildOat), --per-species images spread evenly over capture days.
DeepWeeds  (CC BY 4.0)  -> weeds/deepweeds_<YYYYMMDD>/             (source = capture day; label 8 'negative'
                                                                    background flora -> deepweeds_neg_<day>)

    python import_non_rice.py plantdoc  --zip PlantDoc-Dataset-master.zip --out D:/AEGIS-AI/datasets/non_rice_raw
    python import_non_rice.py deepweeds --images-zip images.zip --repo-zip DeepWeeds-master.zip --out ...

Images are copied byte-for-byte (no changes), so CC BY needs only attribution (ATTRIBUTION.csv rows added).
Re-running skips existing files. Filenames are sanitised; nothing is ever written outside --out.
"""
import argparse
import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path

EXT = {".jpg", ".jpeg", ".png"}
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe(s):
    return SAFE.sub("_", s).strip("_") or "x"


def bucket(name, n=4):
    return int(hashlib.sha1(name.encode()).hexdigest()[:6], 16) % n


def write_member(z, member, dst):
    if dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(z.read(member))
    return True


def attribution(out, rows, header=("file", "source_dataset", "license", "url", "changes")):
    p = Path(out) / "ATTRIBUTION.csv"
    new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "image_id", "title", "author", "author_profile_url", "landing_url", "license_url", "changes", "downloaded"])
        w.writerows(rows)


def import_plantdoc(zip_path, out):
    import datetime
    today, rows, n = datetime.date.today().isoformat(), [], 0
    with zipfile.ZipFile(zip_path) as z:
        for m in z.namelist():
            parts = m.split("/")
            if len(parts) < 4 or not parts[-1] or Path(parts[-1]).suffix.lower() not in EXT:
                continue  # expects <root>/<train|test>/<class>/<file>
            cls, fname = parts[2], parts[-1]
            src = f"plantdoc_{safe(cls.lower())}_{bucket(fname)}"
            dst = Path(out) / "other_crops" / src / safe(f"{parts[1]}_{fname}")
            if write_member(z, m, dst):
                n += 1
                rows.append([dst.relative_to(out).as_posix(), "", f"PlantDoc/{cls}", "Singh et al. (PlantDoc)",
                             "", "https://github.com/pratikkayal/PlantDoc-Dataset", "https://creativecommons.org/licenses/by/4.0/",
                             "none (byte-for-byte copy)", today])
    attribution(out, rows)
    print(f"PlantDoc: imported {n} new images")


def import_deepweeds(images_zip, repo_zip, out):
    import datetime
    today, rows, n = datetime.date.today().isoformat(), [], 0
    with zipfile.ZipFile(repo_zip) as rz:
        label_member = next(m for m in rz.namelist() if m.endswith("labels/labels.csv"))
        labels = {r["Filename"]: (r["Label"], r["Species"]) for r in csv.DictReader(io.StringIO(rz.read(label_member).decode("utf-8")))}
    with zipfile.ZipFile(images_zip) as z:
        for m in z.namelist():
            fname = m.rsplit("/", 1)[-1]
            if not fname or Path(fname).suffix.lower() not in EXT or fname not in labels:
                continue
            label, species = labels[fname]
            day = fname[:8]
            src = f"deepweeds_{'neg_' if label == '8' else ''}{safe(day)}"
            dst = Path(out) / "weeds" / src / safe(fname)
            if write_member(z, m, dst):
                n += 1
                rows.append([dst.relative_to(out).as_posix(), "", f"DeepWeeds/{species}", "Olsen et al. (DeepWeeds)", "",
                             "https://github.com/AlexOlsen/DeepWeeds", "https://creativecommons.org/licenses/by/4.0/",
                             "none (byte-for-byte copy)", today])
    attribution(out, rows)
    print(f"DeepWeeds: imported {n} new images ({len(labels)} labelled in repo)")


def pick_even(names, per_species, day_of):
    """Round-robin across capture days (deterministic) so every day contributes."""
    by_day = {}
    for n in sorted(names, key=lambda x: hashlib.sha256(x.encode()).hexdigest()):
        by_day.setdefault(day_of(n), []).append(n)
    out, queues = [], [by_day[d] for d in sorted(by_day)]
    while len(out) < per_species and any(queues):
        for q in queues:
            if q and len(out) < per_species:
                out.append(q.pop(0))
    return out


def import_dryad(rar_path, rar_exe, out, species, per_species, work):
    import datetime, shutil, subprocess
    B = chr(92)
    listing = subprocess.run([rar_exe, "lb", rar_path], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.splitlines()
    members = [l.strip() for l in listing if l.strip().lower().endswith(".jpg")]
    chosen = []
    for sp in species:
        names = [m for m in members if m.split(B)[-1].startswith(sp)]
        chosen += pick_even(names, per_species, lambda n, sp=sp: re.search(sp + "([0-9]{8})", n).group(1))
        print(f"{sp}: {len(names)} available, {sum(1 for c in chosen if c.split(B)[-1].startswith(sp))} chosen")
    work = Path(work)
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"{work} must be empty (extraction target)")
    work.mkdir(parents=True, exist_ok=True)
    listfile = work.parent / (work.name + "_list.txt")
    listfile.write_text(chr(10).join(chosen), encoding="utf-8")
    subprocess.run([rar_exe, "x", "-y", "-idq", rar_path, "@" + str(listfile), str(work) + B], check=True)
    today, rows, n = datetime.date.today().isoformat(), [], 0
    for f in sorted(work.rglob("*.jpg")):
        m = re.match("([A-Za-z]+?)([0-9]{8})", f.name)
        dst = Path(out) / "weeds" / f"dryad_{safe(m.group(1).lower())}_{m.group(2)}" / safe(f.name)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst); n += 1
            rows.append([dst.relative_to(out).as_posix(), "", f"Dryad weedling/{m.group(1)}", "Beck et al.", "",
                         "https://doi.org/10.5061/dryad.gtht76hhz", "https://creativecommons.org/publicdomain/zero/1.0/",
                         "none (byte-for-byte copy)", today])
    attribution(out, rows)
    shutil.rmtree(work); listfile.unlink()
    print(f"Dryad: imported {n} new images")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plantdoc"); p.add_argument("--zip", required=True); p.add_argument("--out", required=True)
    d = sub.add_parser("deepweeds"); d.add_argument("--images-zip", required=True); d.add_argument("--repo-zip", required=True); d.add_argument("--out", required=True)
    y = sub.add_parser("dryad"); y.add_argument("--rar", required=True); y.add_argument("--out", required=True)
    y.add_argument("--rar-exe", default="C:/Program Files/WinRAR/Rar.exe"); y.add_argument("--per-species", type=int, default=300)
    y.add_argument("--species", default="BarnyardGrass,YellowFoxtail,WildOat"); y.add_argument("--work", required=True, help="EMPTY temp dir for extraction (deleted afterwards)")
    a = ap.parse_args()
    if a.cmd == "dryad":
        import_dryad(a.rar, a.rar_exe, a.out, a.species.split(","), a.per_species, a.work)
    elif a.cmd == "plantdoc":
        import_plantdoc(a.zip, a.out)
    else:
        import_deepweeds(a.images_zip, a.repo_zip, a.out)


if __name__ == "__main__":
    main()
