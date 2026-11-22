"""Generate synthetic non_rice images for build_gate_dataset.py.

  text_screens : memes, document pages, chat/app-like screenshots, error dialogs,
                 plain-colour banners with text. No external data needed.
  blurry       : degraded copies of REAL non-rice images (--src NEG_SRC/<category>/<source>/*.jpg):
                 gaussian / motion blur, low-res upscale, noise, JPEG crush.
                 Each copy keeps its original <source>, so the split stays leakage-free
                 (a blurred copy never lands in a different split than its original).

    python synth_negatives.py --out D:/AEGIS-AI/datasets/non_rice_raw --text 600 --src D:/AEGIS-AI/datasets/non_rice_raw --blurry 600

NEVER feed rice images to --src: blurred rice must stay `rice`/quality-rejected, not non_rice.
Output layout: <out>/text_screens/<style>_<bucket>/NNNN.jpg, <out>/blurry/<source>/NNNN.jpg
"""
import argparse
import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",  # Impact lacks Vietnamese glyphs (tofu boxes)
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
SENTENCES = ["Cây lúa bị bệnh gì vậy mọi người?", "Thông báo: lỗi kết nối máy chủ", "Họp lúc 9h sáng mai, nhớ mang tài liệu",
             "Giá nông sản hôm nay", "404 Not Found", "Quên mật khẩu?", "Đã gửi • 10:42", "When you finally fix the bug",
             "Total: 1,250,000 VND", "Please sign in to continue", "Lorem ipsum dolor sit amet, consectetur adipiscing elit"]
STYLES = ["meme", "document", "chat", "dialog", "banner"]


def font(size, rng):
    paths = [p for p in FONT_CANDIDATES if Path(p).is_file()]
    return ImageFont.truetype(rng.choice(paths), size) if paths else ImageFont.load_default()


def rand_color(rng, lo=0, hi=255):
    return tuple(rng.randint(lo, hi) for _ in range(3))


def text_image(style, rng):
    w, h = rng.choice([(640, 480), (800, 600), (480, 854), (1080, 720), (720, 720)])
    if style == "meme":  # photo-like noisy backdrop + big outlined caption
        arr = np.random.default_rng(rng.randint(0, 2**31)).integers(40, 215, (h // 8, w // 8, 3), dtype=np.uint8)
        im = Image.fromarray(arr).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    elif style == "document":
        im = Image.new("RGB", (w, h), (250, 250, 245))
    elif style == "chat":
        im = Image.new("RGB", (w, h), rand_color(rng, 225, 250))
    elif style == "dialog":
        im = Image.new("RGB", (w, h), rand_color(rng, 30, 80))
    else:
        im = Image.new("RGB", (w, h), rand_color(rng, 20, 235))
    d = ImageDraw.Draw(im)
    if style == "meme":
        f = font(max(24, h // 10), rng)
        for y in (h * 0.05, h * 0.78):
            t = rng.choice(SENTENCES).upper()
            d.text((w * 0.05, y), t, font=f, fill="white", stroke_width=3, stroke_fill="black")
    elif style == "document":
        f = font(max(14, h // 30), rng)
        y = 20
        while y < h - 30:
            d.text((30, y), rng.choice(SENTENCES) + " " + rng.choice(SENTENCES), font=f, fill=(20, 20, 20))
            y += int(f.size * 1.6) if hasattr(f, "size") else 18
    elif style == "chat":
        f = font(max(16, h // 28), rng)
        y = 20
        while y < h - 60:
            right = rng.random() < 0.5
            t = rng.choice(SENTENCES)
            tw = int(d.textlength(t, font=f))
            x = w - tw - 50 if right else 20
            d.rounded_rectangle([x - 10, y - 6, x + tw + 10, y + f.size + 10], 12, fill=(120, 190, 255) if right else (255, 255, 255))
            d.text((x, y), t, font=f, fill=(10, 10, 10))
            y += f.size + 34
    elif style == "dialog":
        bw, bh = int(w * 0.7), int(h * 0.35)
        x0, y0 = (w - bw) // 2, (h - bh) // 2
        d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(240, 240, 240))
        d.rectangle([x0, y0, x0 + bw, y0 + bh // 5], fill=(0, 90, 180))
        d.text((x0 + 15, y0 + bh // 3), rng.choice(SENTENCES), font=font(max(16, h // 26), rng), fill="black")
    else:
        d.text((w * 0.08, h * 0.4), rng.choice(SENTENCES), font=font(max(28, h // 8), rng), fill=rand_color(rng, 0, 255))
    return im


def degrade(im, rng):
    kind = rng.choice(["gauss", "motion", "lowres", "noise", "jpeg"])
    if kind == "gauss":
        return im.filter(ImageFilter.GaussianBlur(rng.uniform(4, 14)))
    if kind == "motion":  # average of shifted copies along a random axis-aligned/diagonal direction
        a = np.asarray(im, dtype=np.float32); k = rng.choice([9, 15, 25])
        dy, dx = rng.choice([(0, 1), (1, 0), (1, 1), (1, -1)])
        acc = sum(np.roll(a, (dy * s, dx * s), axis=(0, 1)) for s in range(k)) / k
        return Image.fromarray(acc.clip(0, 255).astype(np.uint8))
    if kind == "lowres":
        w, h = im.size
        s = rng.choice([12, 16, 24])
        return im.resize((max(8, w // s), max(8, h // s)), Image.BILINEAR).resize((w, h), Image.BICUBIC)
    if kind == "noise":
        a = np.asarray(im, dtype=np.float32) + np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(25, 60), (im.height, im.width, 3))
        return Image.fromarray(a.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    buf = io.BytesIO(); im.resize((im.width // 4, im.height // 4)).save(buf, "JPEG", quality=rng.randint(5, 15)); buf.seek(0)
    return Image.open(buf).convert("RGB").resize(im.size, Image.BILINEAR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", type=int, default=0, help="number of text_screens images")
    ap.add_argument("--src", help="NEG root holding real non-rice images (for blurry)")
    ap.add_argument("--blurry", type=int, default=0)
    ap.add_argument("--buckets", type=int, default=20, help="pseudo-sources per style, so splits are well spread")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)

    for i in range(a.text):
        style = STYLES[i % len(STYLES)]
        dst = out / "text_screens" / f"synth_{style}_{rng.randrange(a.buckets):02d}"
        dst.mkdir(parents=True, exist_ok=True)
        text_image(style, rng).save(dst / f"{i:05d}.jpg", quality=rng.randint(70, 95))

    if a.blurry:
        if not a.src:
            raise SystemExit("--blurry needs --src (real non-rice images); refusing to invent content")
        srcs = [p for p in sorted(Path(a.src).rglob("*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                and len(p.relative_to(a.src).parts) >= 3 and p.relative_to(a.src).parts[0] != "blurry"]
        if not srcs:
            raise SystemExit("no source images found under --src (expected <category>/<source>/file)")
        for i in range(a.blurry):
            p = rng.choice(srcs)
            source = p.relative_to(a.src).parts[1]
            dst = out / "blurry" / source
            dst.mkdir(parents=True, exist_ok=True)
            with Image.open(p) as im:
                degrade(im.convert("RGB"), rng).save(dst / f"{p.stem}__blur{i:05d}.jpg", quality=85)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
