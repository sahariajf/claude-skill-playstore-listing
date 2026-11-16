"""Builds Google Play phone screenshots (1080x1920, no transparency).

Headline on top, the REAL app screenshot inside a plain Android phone below,
bleeding off the bottom edge. Three styles:

  flat      solid brand colour
  gradient  brand colour fading to the accent, with soft light blobs
  popout    gradient + one part of the screen enlarged and lifted out of the
            phone (needs a "popout" box); without a box it puts an accent
            circle behind the phone instead

One screenshot:
    python compose.py --screenshot raw/home.png --headline "Split bazar costs" \\
        --sub "Everyone pays their fair share" --bg "#071D3C" --accent "#009C96" \\
        --style gradient --out work/01/gradient.png

Everything in playstore.json (writes work/<slug>/<style>.png for each style):
    python compose.py --config store-screenshots/playstore.json
    python compose.py --config store-screenshots/playstore.json --slug 01-split-costs --styles popout

Pick a version (copies it to final/<slug>.png as a flat PNG):
    python compose.py --config store-screenshots/playstore.json --pick 01-split-costs gradient
    python compose.py --config store-screenshots/playstore.json --pick 01-split-costs work/01-split-costs/ai-2.png

Each render also writes <style>.overlay.png: the phone (and pop-out) alone on a
transparent canvas. polish.py uses it to put the real app screen back on top
of an AI-polished image.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from android_frame import render_phone
from common import (PLAY_SHOT, auto_text, cover, draw_lines, fit_text, hex_rgb, load_config,
                    mix, paste_shadow, parse_size, prepare_raw, resolve_font, rounded, save_flat,
                    soft_blob, vertical_gradient)

STYLES = ("flat", "gradient", "popout")


def background(style: str, size, bg, accent) -> Image.Image:
    W, H = size
    if style == "flat":
        return Image.new("RGBA", size, bg + (255,))
    canvas = vertical_gradient(size, mix(bg, (255, 255, 255), 0.04), mix(bg, accent, 0.45))
    soft_blob(canvas, (round(W * 0.92), round(H * 0.10)), round(W * 0.42), accent, 70)
    soft_blob(canvas, (round(W * 0.02), round(H * 0.62)), round(W * 0.38), mix(accent, (255, 255, 255), 0.3), 45)
    return canvas


def compose(shot: Image.Image, headline: str, sub: str | None, *, style: str,
            bg: str, accent: str, text: str | None = None, size=PLAY_SHOT,
            font_bold: str | None = None, font_regular: str | None = None,
            frame: str = "android", body: str = "#111418",
            popout: list[int] | None = None, uppercase: bool = True):
    """Returns (final RGBA canvas, overlay RGBA with only the phone/pop-out)."""
    W, H = size
    bg_c, acc_c = hex_rgb(bg), hex_rgb(accent)
    txt_c = hex_rgb(text) if text else auto_text(bg_c)
    canvas = background(style, size, bg_c, acc_c)
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))

    # --- headline + sub line (top ~25%, inside the middle 84%)
    d = ImageDraw.Draw(canvas)
    max_w = round(W * 0.84)
    y = round(H * 0.06)
    head = headline.upper() if uppercase else headline
    hfont, hlines = fit_text(head, font_bold, max_w, 2, round(W * 0.105), round(W * 0.066))
    y = draw_lines(d, hlines, hfont, W // 2, y, txt_c, gap=0.02)
    if sub:
        sfont, slines = fit_text(sub, font_regular or font_bold, max_w, 2, round(W * 0.048), round(W * 0.036))
        y += round(H * 0.016)
        y = draw_lines(d, slines, sfont, W // 2, y, mix(txt_c, bg_c, 0.18), gap=0.12)
    text_bottom = y

    # --- phone
    screen_w = round(W * 0.70)
    if frame == "none":
        scale = screen_w / shot.width
        phone = rounded(shot.resize((screen_w, round(shot.height * scale)), Image.LANCZOS), round(screen_w * 0.07))
        sx = sy = 0
    else:
        phone, (sx, sy, _, _) = render_phone(shot, screen_w, body=body)
    px = (W - phone.width) // 2
    py = text_bottom + round(H * 0.045)

    if style == "popout" and not popout:
        # No box to lift out: an accent circle behind the phone instead.
        r = round(W * 0.47)
        circle = Image.new("RGBA", size, (0, 0, 0, 0))
        soft = mix(acc_c, bg_c, 0.15)
        cd = ImageDraw.Draw(circle)
        cy = py + round(phone.height * 0.30)
        cd.ellipse((W // 2 - r, cy - r, W // 2 + r, cy + r), fill=soft + (255,))
        canvas.alpha_composite(circle)

    paste_shadow(canvas, phone, (px, py), blur=round(W * 0.035), opacity=0.45, offset=(0, round(W * 0.02)))
    canvas.alpha_composite(phone, (px, py))
    overlay.alpha_composite(phone, (px, py))

    # --- pop-out: a part of the real screen, bigger, floating over the phone
    if style == "popout" and popout:
        x0, y0, x1, y1 = popout
        part = shot.convert("RGBA").crop((x0, y0, x1, y1))
        target_w = round(W * 0.90)
        k = target_w / part.width
        part = part.resize((target_w, round(part.height * k)), Image.LANCZOS)
        part = rounded(part, round(W * 0.03))
        # Same height as where that part sits in the phone, kept on screen.
        in_phone = screen_w / shot.width
        mid =py + sy + round((y0 + y1) / 2 * in_phone)
        top = mid - part.height // 2
        top = max(text_bottom + round(H * 0.03), min(top, H - part.height - round(H * 0.04)))
        left = (W - part.width) // 2
        paste_shadow(canvas, part, (left, top), blur=round(W * 0.03), opacity=0.5, offset=(0, round(W * 0.018)))
        canvas.alpha_composite(part, (left, top))
        overlay.alpha_composite(part, (left, top))

    return canvas, overlay


# ---------------------------------------------------------------- config mode

def shot_entries(cfg: dict, slug: str | None):
    items = cfg.get("screenshots", [])
    if slug:
        items = [s for s in items if s.get("slug") == slug]
        if not items:
            sys.exit(f"No screenshot with slug {slug!r} in the config.")
    return items


def run_config(cfg_path: str, slug: str | None, styles: list[str]) -> None:
    cfg, root = load_config(cfg_path)
    brand = cfg.get("brand", {})
    fonts = cfg.get("fonts", {})
    size = tuple(cfg.get("size", PLAY_SHOT))
    fb = resolve_font(_abs(root, fonts.get("bold")), "bold")
    fr = resolve_font(_abs(root, fonts.get("regular")), "regular")
    for item in shot_entries(cfg, slug):
        raw = root / item["raw"]
        if not raw.is_file():
            print(f"[skip] {item['slug']}: raw screenshot not found: {raw}")
            continue
        shot = prepare_raw(Image.open(raw), cfg, item)
        for style in styles:
            img, ov = compose(
                shot, item["headline"], item.get("sub"), style=style,
                bg=item.get("background", brand.get("background", "#111827")),
                accent=item.get("accent", brand.get("accent", "#3B82F6")),
                text=brand.get("text"), size=size, font_bold=fb, font_regular=fr,
                frame=cfg.get("frame", "android"), body=brand.get("phone", "#111418"),
                popout=item.get("popout"), uppercase=cfg.get("uppercase", True))
            out = root / "work" / item["slug"] / f"{style}.png"
            save_flat(img, out)
            ov.save(out.with_suffix(".overlay.png"))
            print(f"saved {out.relative_to(root)}")


def pick(cfg_path: str, slug: str, choice: str) -> None:
    cfg, root = load_config(cfg_path)
    src = Path(choice)
    if choice in STYLES or not src.suffix:
        src = root / "work" / slug / f"{choice}.png"
    elif not src.is_absolute() and not src.is_file():
        src = root / choice
    if not src.is_file():
        sys.exit(f"Not found: {src}")
    img = Image.open(src)
    size = tuple(cfg.get("size", PLAY_SHOT))
    if img.size != size:
        img = cover(img.convert("RGB"), size)
    out = save_flat(img, root / "final" / f"{slug}.png")
    print(f"final: {out.relative_to(root)} ({img.width}x{img.height})")


def _abs(root: Path, p: str | None) -> str | None:
    if not p:
        return None
    path, sep, var = p.partition("#")
    full = Path(path) if Path(path).is_absolute() else root / path
    return f"{full}{sep}{var}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="playstore.json (batch mode)")
    ap.add_argument("--slug", help="only this screenshot (config mode)")
    ap.add_argument("--styles", default=",".join(STYLES), help="comma list: flat,gradient,popout")
    ap.add_argument("--pick", nargs=2, metavar=("SLUG", "STYLE_OR_FILE"), help="copy a version to final/")
    # single mode
    ap.add_argument("--screenshot")
    ap.add_argument("--headline")
    ap.add_argument("--sub")
    ap.add_argument("--style", default="gradient", choices=STYLES)
    ap.add_argument("--bg", default="#111827")
    ap.add_argument("--accent", default="#3B82F6")
    ap.add_argument("--text", help="text colour (default: auto)")
    ap.add_argument("--font-bold")
    ap.add_argument("--font-regular")
    ap.add_argument("--frame", default="android", choices=("android", "none"))
    ap.add_argument("--popout", help="x0,y0,x1,y1 box in screenshot pixels")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--keep-case", action="store_true", help="do not uppercase the headline")
    ap.add_argument("--out")
    a = ap.parse_args()

    styles = [s.strip() for s in a.styles.split(",") if s.strip()]
    bad = [s for s in styles if s not in STYLES]
    if bad:
        sys.exit(f"Unknown style(s): {bad}. Use {STYLES}.")

    if a.config and a.pick:
        pick(a.config, *a.pick)
    elif a.config:
        run_config(a.config, a.slug, styles)
    else:
        if not (a.screenshot and a.headline and a.out):
            ap.error("single mode needs --screenshot, --headline and --out (or use --config)")
        box = [int(v) for v in a.popout.split(",")] if a.popout else None
        img, ov = compose(
            Image.open(a.screenshot), a.headline, a.sub, style=a.style, bg=a.bg,
            accent=a.accent, text=a.text, size=parse_size(a.size),
            font_bold=resolve_font(a.font_bold, "bold"),
            font_regular=resolve_font(a.font_regular, "regular"),
            frame=a.frame, popout=box, uppercase=not a.keep_case)
        out = save_flat(img, a.out)
        ov.save(out.with_suffix(".overlay.png"))
        print(f"saved {out}")


if __name__ == "__main__":
    main()
