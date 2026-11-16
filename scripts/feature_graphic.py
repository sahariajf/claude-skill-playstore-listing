"""Builds the Google Play feature graphic (1024x500, no transparency).

App icon + app name + one short line on the left, the real app in a phone on
the right (bleeding off the bottom). Styles:

  flat      solid brand colour, one phone
  gradient  brand -> accent gradient with soft blobs, one phone
  duo       gradient with two phones (needs 2 screenshots; else one phone
            with an accent circle behind it)

Keep the left text short. If the listing has a promo video, Play puts a play
button in the middle of this image, so nothing important should sit there.

    python feature_graphic.py --name "MessBro" --tagline "Meals, bazar and bills for your mess" \\
        --icon assets/icon.png --screenshot raw/home.png --screenshot raw/meals.png \\
        --bg "#071D3C" --accent "#009C96" --style duo --out work/feature-graphic/duo.png

    python feature_graphic.py --config store-screenshots/playstore.json            # all styles
    python feature_graphic.py --config store-screenshots/playstore.json --pick duo # -> final/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from android_frame import render_phone
from common import (FEATURE_GRAPHIC, auto_text, draw_lines, fit_text, hex_rgb, line_height,
                    load_config, mix, paste_shadow, prepare_raw, resolve_font, rounded, save_flat,
                    soft_blob, vertical_gradient)

STYLES = ("flat", "gradient", "duo")


def build(name: str, tagline: str | None, icon: Image.Image | None, shots: list[Image.Image],
          *, style: str, bg: str, accent: str, text: str | None = None,
          font_bold: str | None = None, font_regular: str | None = None,
          body: str = "#111418") -> Image.Image:
    W, H = FEATURE_GRAPHIC
    bg_c, acc_c = hex_rgb(bg), hex_rgb(accent)
    txt_c = hex_rgb(text) if text else auto_text(bg_c)

    if style == "flat":
        canvas = Image.new("RGBA", (W, H), bg_c + (255,))
    else:
        canvas = vertical_gradient((W, H), mix(bg_c, (255, 255, 255), 0.04), mix(bg_c, acc_c, 0.40))
        soft_blob(canvas, (round(W * 0.80), round(H * 0.05)), 300, acc_c, 80)
        soft_blob(canvas, (round(W * 0.05), round(H * 1.0)), 260, mix(acc_c, (255, 255, 255), 0.3), 40)

    # --- phones on the right
    if shots:
        main_shot = shots[0]
        second = shots[1] if style == "duo" and len(shots) > 1 else None
        if style == "duo" and second is None:
            d = ImageDraw.Draw(canvas)
            r = 215
            cx, cy = 845, 330
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(acc_c, bg_c, 0.15) + (255,))
        if second is not None:
            p2, _ = render_phone(second, 190, body=body)
            x2, y2 = 690 - p2.width // 2, 118
            paste_shadow(canvas, p2, (x2, y2), blur=22, opacity=0.45, offset=(0, 12))
            canvas.alpha_composite(p2, (x2, y2))
        p1, _ = render_phone(main_shot, 222, body=body)
        x1, y1 = 858 - p1.width // 2, 58
        paste_shadow(canvas, p1, (x1, y1), blur=26, opacity=0.5, offset=(0, 14))
        canvas.alpha_composite(p1, (x1, y1))
        text_right = 560 if second is not None else 700
    else:
        text_right = W - 64

    # --- icon + name + tagline on the left, centred as a block
    left = 64
    max_w = text_right - left - 24
    nfont, nlines = fit_text(name, font_bold, max_w, 2, 74, 44)
    tfont = tlines = None
    if tagline:
        tfont, tlines = fit_text(tagline, font_regular or font_bold, max_w, 2, 34, 22)
    icon_px = 112 if icon is not None else 0
    gap_icon, gap_tag = 26, 12
    block = icon_px + (gap_icon if icon_px else 0)
    block += round(line_height(nfont) * (len(nlines) + 0.02 * (len(nlines) - 1)))
    if tlines:
        block += gap_tag + round(line_height(tfont) * (len(tlines) + 0.15 * (len(tlines) - 1)))
    y = (H - block) // 2
    if icon is not None:
        ic = rounded(icon.convert("RGBA").resize((icon_px, icon_px), Image.LANCZOS), round(icon_px * 0.22))
        paste_shadow(canvas, ic, (left, y), blur=14, opacity=0.35, offset=(0, 8))
        canvas.alpha_composite(ic, (left, y))
        y += icon_px + gap_icon
    d = ImageDraw.Draw(canvas)
    y = draw_lines(d, nlines, nfont, left, y, txt_c, gap=0.02, align="left")
    if tlines:
        draw_lines(d, tlines, tfont, left, y + gap_tag, mix(txt_c, bg_c, 0.15), gap=0.15, align="left")
    return canvas


def _abs(root: Path, p: str | None) -> str | None:
    if not p:
        return None
    path, sep, var = p.partition("#")
    full = Path(path) if Path(path).is_absolute() else root / path
    return f"{full}{sep}{var}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--styles", default=",".join(STYLES))
    ap.add_argument("--pick", metavar="STYLE_OR_FILE", help="copy a version to final/feature-graphic.png")
    ap.add_argument("--name")
    ap.add_argument("--tagline")
    ap.add_argument("--icon")
    ap.add_argument("--screenshot", action="append", default=[])
    ap.add_argument("--style", default="gradient", choices=STYLES)
    ap.add_argument("--bg", default="#111827")
    ap.add_argument("--accent", default="#3B82F6")
    ap.add_argument("--text")
    ap.add_argument("--font-bold")
    ap.add_argument("--font-regular")
    ap.add_argument("--out")
    a = ap.parse_args()

    if a.config:
        cfg, root = load_config(a.config)
        if a.pick:
            src = root / "work" / "feature-graphic" / f"{a.pick}.png" if a.pick in STYLES else Path(a.pick)
            if not src.is_absolute() and not src.is_file():
                src = root / a.pick
            img = Image.open(src)
            if img.size != FEATURE_GRAPHIC:
                sys.exit(f"{src} is {img.width}x{img.height}; the feature graphic must be 1024x500.")
            out = save_flat(img, root / "final" / "feature-graphic.png")
            print(f"final: {out.relative_to(root)}")
            return
        app, brand, fonts = cfg.get("app", {}), cfg.get("brand", {}), cfg.get("fonts", {})
        fg = cfg.get("feature_graphic", {})
        icon_path = _abs(root, app.get("icon"))
        icon = Image.open(icon_path) if icon_path and Path(icon_path).is_file() else None
        shot_paths = fg.get("screenshots") or [s["raw"] for s in cfg.get("screenshots", [])[:2]]
        by_raw = {s.get("raw"): s for s in cfg.get("screenshots", [])}
        shots = [prepare_raw(Image.open(root / p), cfg, by_raw.get(p)) for p in shot_paths if (root / p).is_file()]
        fb = resolve_font(_abs(root, fonts.get("bold")), "bold")
        fr = resolve_font(_abs(root, fonts.get("regular")), "regular")
        for style in [s.strip() for s in a.styles.split(",") if s.strip()]:
            img = build(app.get("name", "App"), fg.get("tagline"), icon, shots, style=style,
                        bg=fg.get("background", brand.get("background", "#111827")),
                        accent=brand.get("accent", "#3B82F6"), text=brand.get("text"),
                        font_bold=fb, font_regular=fr, body=brand.get("phone", "#111418"))
            out = save_flat(img, root / "work" / "feature-graphic" / f"{style}.png")
            print(f"saved {out.relative_to(root)}")
        return

    if not (a.name and a.out):
        ap.error("needs --name and --out (or use --config)")
    img = build(a.name, a.tagline, Image.open(a.icon) if a.icon else None,
                [Image.open(p) for p in a.screenshot], style=a.style, bg=a.bg, accent=a.accent,
                text=a.text, font_bold=resolve_font(a.font_bold, "bold"),
                font_regular=resolve_font(a.font_regular, "regular"))
    save_flat(img, a.out)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
