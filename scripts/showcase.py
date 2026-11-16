"""One preview image of the whole set: screenshots in upload order, the
feature graphic underneath. For reviewing (and for a README), not for upload.

    python showcase.py store-screenshots/final --out store-screenshots/showcase.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from common import load_font, resolve_font, rounded, save_flat


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("final_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--height", type=int, default=820, help="height of each screenshot")
    ap.add_argument("--title", help="optional line of text at the top")
    ap.add_argument("--bg", default="#F2F4F7")
    a = ap.parse_args()

    folder = Path(a.final_dir)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    feature = [p for p in files if "feature" in p.stem.lower()]
    shots = [Image.open(p).convert("RGB") for p in files if p not in feature]
    if not shots and not feature:
        raise SystemExit(f"No images in {folder}")

    pad, gap, h = 60, 36, a.height
    thumbs = [rounded(s.resize((round(s.width * h / s.height), h), Image.LANCZOS), 28) for s in shots]
    row_w = sum(t.width for t in thumbs) + gap * max(0, len(thumbs) - 1)
    fg = Image.open(feature[0]).convert("RGB") if feature else None
    fg_w = min(max(row_w // 2, 1024), row_w or 1024, 1280) if fg else 0
    fg_img = rounded(fg.resize((fg_w, round(fg.height * fg_w / fg.width)), Image.LANCZOS), 20) if fg else None

    title_h = 0
    font = None
    if a.title:
        font = load_font(resolve_font(None, "bold"), 40)
        title_h = 80
    W = pad * 2 + max(row_w, fg_w)
    H = pad * 2 + title_h + (h if thumbs else 0) + ((gap + fg_img.height) if fg_img else 0)
    canvas = Image.new("RGBA", (W, H), Image.new("RGB", (1, 1), a.bg).getpixel((0, 0)) + (255,))
    y = pad
    if a.title:
        ImageDraw.Draw(canvas).text((pad, y), a.title, font=font, fill=(17, 24, 39))
        y += title_h
    x = pad + (W - 2 * pad - row_w) // 2
    for t in thumbs:
        canvas.alpha_composite(t, (x, y))
        x += t.width + gap
    if fg_img:
        y += (h + gap) if thumbs else 0
        canvas.alpha_composite(fg_img, ((W - fg_img.width) // 2, y))
    save_flat(canvas, a.out)
    print(f"saved {a.out} ({W}x{H})")


if __name__ == "__main__":
    main()
