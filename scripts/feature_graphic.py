"""Builds the Google Play feature graphic (1024x500, no transparency).

App icon + app name + one short line on the left, the real app on the right.
Styles:

  flat      solid brand colour, one phone
  gradient  brand -> accent gradient with soft blobs, one phone
  duo       gradient with two phones (needs 2 screenshots; else one phone
            with an accent circle behind it)
  mesh      mesh background, one phone
  light     pale brand tint, dark text, one phone
  cards     gradient with the screens as tilted cards, NO device frame
            (Google's feature-graphic advice is to avoid device imagery)

Markup works in the name and tagline: *word* = highlight colour,
_word_ = accent font.

Safe areas: Google asks to keep the logo, name, slogan and main UI out of the
"cutoff zones" near the edges, and puts a play button in the middle when the
listing has a promo video ("feature_graphic": {"video": true}). Google shows
those zones only as a picture, so the margins here are an approximation. Each
render also writes <style>.guide.png with the zones drawn on (not for upload),
and prints a WARN when text or the icon is inside them.

    python feature_graphic.py --name "MessBro" --tagline "Meals, bazar and bills for your *mess*" \\
        --icon assets/icon.png --screenshot raw/home.png --screenshot raw/meals.png \\
        --bg "#071D3C" --accent "#009C96" --style duo --out work/feature-graphic/duo.png

    python feature_graphic.py --config store-screenshots/playstore.json             # all styles
    python feature_graphic.py --config store-screenshots/playstore.json --pick duo  # -> final/
    python feature_graphic.py --config ... --locale bn-BD     # work/bn-BD/feature-graphic/...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from android_frame import render, render_frameless
from backgrounds import area_colour, make_background
from colors import highlight_for
from common import (FEATURE_GRAPHIC, abs_spec, auto_text, config_fonts, fit_rich, hex_rgb, load_config,
                    mix, out_dir, paste_clipped, paste_shadow, prepare_raw,
                    resolve_font, rounded, save_flat, tilt_layer)

STYLES = ("flat", "gradient", "duo", "mesh", "light", "cards")
EDGE_X, EDGE_Y = 0.07, 0.10     # approximate cutoff zones (share of width / height)
PLAY_R = 0.16                   # approximate play-button keep-clear radius (share of height)


def _inside(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def safe_warnings(boxes: list[tuple[str, tuple]], video: bool) -> list[str]:
    W, H = FEATURE_GRAPHIC
    ex, ey = round(W * EDGE_X), round(H * EDGE_Y)
    out = []
    for name, (x0, y0, x1, y1) in boxes:
        if x0 < ex or y0 < ey or x1 > W - ex or y1 > H - ey:
            out.append(f"{name} reaches into the edge cutoff zone")
        if video:
            r = round(H * PLAY_R)
            if _inside((x0, y0, x1, y1), (W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r)):
                out.append(f"{name} sits under the video play button (centre)")
    return out


def guide(img: Image.Image, video: bool) -> Image.Image:
    """The image with the cutoff zones (red) and play-button area drawn on. Not for upload."""
    W, H = img.size
    out = img.convert("RGBA")
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ex, ey = round(W * EDGE_X), round(H * EDGE_Y)
    red = (239, 68, 68, 90)
    d.rectangle((0, 0, W, ey), fill=red)
    d.rectangle((0, H - ey, W, H), fill=red)
    d.rectangle((0, ey, ex, H - ey), fill=red)
    d.rectangle((W - ex, ey, W, H - ey), fill=red)
    if video:
        r = round(H * PLAY_R)
        d.ellipse((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r), outline=(239, 68, 68, 230), width=4)
        d.polygon([(W // 2 - r // 3, H // 2 - r // 2), (W // 2 - r // 3, H // 2 + r // 2), (W // 2 + r // 2, H // 2)],
                  fill=(255, 255, 255, 200))
    out.alpha_composite(layer)
    return out


def build(name: str, tagline: str | None, icon: Image.Image | None, shots: list[Image.Image], *,
          style: str, bg: str, accent: str, text: str | None = None, highlight: str | None = None,
          fonts: dict | None = None, body: str = "#111418", texture: dict | None = None,
          video: bool = False):
    """Returns (RGBA image, [(what, box)] of the key elements for the safe-area check)."""
    W, H = FEATURE_GRAPHIC
    fonts = fonts or {"bold": resolve_font(None, "bold"), "regular": resolve_font(None, "regular"), "accent": None}
    bg_c, acc_c = hex_rgb(bg), hex_rgb(accent)
    bstyle = {"duo": "gradient", "cards": "gradient"}.get(style, style)
    canvas = make_background(bstyle, (W, H), bg_c, acc_c, texture=texture)
    boxes: list[tuple[str, tuple]] = []
    play_r = round(H * PLAY_R)

    # --- the app on the right
    text_right = W - 64
    if shots:
        second = shots[1] if style in ("duo", "cards") and len(shots) > 1 else None
        if style == "duo" and second is None:
            r = 215
            cx, cy = 845, 330
            ImageDraw.Draw(canvas).ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(acc_c, bg_c, 0.15) + (255,))
        if style == "cards":
            cards = [(second, 640, 92, -6)] if second is not None else []
            cards.append((shots[0], 850, 62, 5))
            for shot, cx, top, rot in cards:
                card, _ = render_frameless(shot, 205)
                card = tilt_layer(card, rot=rot)
                x = cx - card.width // 2
                paste_shadow(canvas, card, (x, top), blur=22, opacity=0.45, offset=(0, 12))
                paste_clipped(canvas, card, (x, top))
            text_right = 520 if second is not None else 700
        else:
            if second is not None:
                p2, _ = render(second, 190, "phone", body)
                x2, y2 = 690 - p2.width // 2, 118
                paste_shadow(canvas, p2, (x2, y2), blur=22, opacity=0.45, offset=(0, 12))
                paste_clipped(canvas, p2, (x2, y2))
            p1, _ = render(shots[0], 222, "phone", body)
            x1, y1 = 858 - p1.width // 2, 58
            paste_shadow(canvas, p1, (x1, y1), blur=26, opacity=0.5, offset=(0, 14))
            paste_clipped(canvas, p1, (x1, y1))
            text_right = 560 if second is not None else 700
    if video:  # keep the middle free for the play button
        text_right = min(text_right, W // 2 - play_r - 12)

    # --- icon + name + tagline on the left, centred as a block
    left = round(W * EDGE_X) + 4
    max_w = text_right - left - 24
    base = area_colour(canvas, (left, round(H * 0.15), max(left + 1, text_right), round(H * 0.85)))
    txt_c = hex_rgb(text) if text and style != "light" else auto_text(base)
    hl_c = highlight_for(highlight, None, acc_c, base)
    nr = fit_rich(name, (fonts["bold"], fonts["accent"]), max_w, 2, 74, 40)
    tr = fit_rich(tagline, (fonts["regular"] or fonts["bold"], fonts["accent"]), max_w, 2, 34, 20) if tagline else None
    icon_px = 112 if icon is not None else 0
    gap_icon, gap_tag = 26, 12
    block = icon_px + (gap_icon if icon_px else 0) + nr.height(0.02) + ((gap_tag + tr.height(0.15)) if tr else 0)
    y = (H - block) // 2
    if icon is not None:
        ic = rounded(icon.convert("RGBA").resize((icon_px, icon_px), Image.LANCZOS), round(icon_px * 0.22))
        paste_shadow(canvas, ic, (left, y), blur=14, opacity=0.35, offset=(0, 8))
        canvas.alpha_composite(ic, (left, y))
        boxes.append(("icon", (left, y, left + icon_px, y + icon_px)))
        y += icon_px + gap_icon
    d = ImageDraw.Draw(canvas)
    y0 = y
    y = nr.draw(d, left, y, txt_c, hl_c, gap=0.02, align="left")
    boxes.append(("app name", (left, y0, left + nr.width(), y)))
    if tr:
        y0 = y + gap_tag
        y = tr.draw(d, left, y0, mix(txt_c, base, 0.15), hl_c, gap=0.15, align="left")
        boxes.append(("tagline", (left, y0, left + tr.width(), y)))
    return canvas, boxes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--locale", help="a language from \"locales\" (e.g. bn-BD)")
    ap.add_argument("--styles", default="gradient,duo,mesh,cards")
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
    ap.add_argument("--font-accent")
    ap.add_argument("--video", action="store_true", help="the listing has a promo video (keep the centre clear)")
    ap.add_argument("--out")
    a = ap.parse_args()

    if a.config:
        cfg, root = load_config(a.config, a.locale)
        work = out_dir(root, "work", cfg) / "feature-graphic"
        if a.pick:
            src = work / f"{a.pick}.png" if not Path(a.pick).suffix else Path(a.pick)
            if not src.is_absolute() and not src.is_file():
                src = root / a.pick
            if not src.is_file():
                sys.exit(f"Not found: {src}")
            img = Image.open(src)
            if img.size != FEATURE_GRAPHIC:
                sys.exit(f"{src} is {img.width}x{img.height}; the feature graphic must be 1024x500.")
            out = save_flat(img, out_dir(root, "final", cfg) / "feature-graphic.png")
            print(f"final: {out.relative_to(root)}")
            return
        app, brand = cfg.get("app", {}), cfg.get("brand", {})
        fg = cfg.get("feature_graphic", {})
        icon_path = abs_spec(root, app.get("icon"))
        icon = Image.open(icon_path) if icon_path and Path(icon_path).is_file() else None
        shot_paths = fg.get("screenshots") or [s["raw"] for s in cfg.get("screenshots", [])[:2]]
        by_raw = {s.get("raw"): s for s in cfg.get("screenshots", [])}
        shots = [prepare_raw(Image.open(root / p), cfg, by_raw.get(p)) for p in shot_paths if (root / p).is_file()]
        video = bool(fg.get("video"))
        for style in [s.strip() for s in a.styles.split(",") if s.strip()]:
            if style not in STYLES:
                sys.exit(f"Unknown style {style!r}; use {STYLES}.")
            img, boxes = build(fg.get("name") or app.get("name", "App"), fg.get("tagline"), icon, shots,
                               style=style, bg=fg.get("background", brand.get("background", "#111827")),
                               accent=brand.get("accent", "#3B82F6"), text=brand.get("text"),
                               highlight=brand.get("highlight"), fonts=config_fonts(cfg, root),
                               body=brand.get("phone", "#111418"), texture=cfg.get("texture"), video=video)
            out = save_flat(img, work / f"{style}.png")
            guide(img, video).save(work / f"{style}.guide.png")
            print(f"saved {out.relative_to(root)} (+ {style}.guide.png)")
            for w in safe_warnings(boxes, video):
                print(f"  [WARN] {style}: {w}")
        return

    if not (a.name and a.out):
        ap.error("needs --name and --out (or use --config)")
    fonts = {"bold": resolve_font(a.font_bold, "bold"), "regular": resolve_font(a.font_regular, "regular"),
             "accent": resolve_font(a.font_accent, "accent")}
    img, boxes = build(a.name, a.tagline, Image.open(a.icon) if a.icon else None,
                       [Image.open(p) for p in a.screenshot], style=a.style, bg=a.bg, accent=a.accent,
                       text=a.text, fonts=fonts, video=a.video)
    out = save_flat(img, a.out)
    guide(img, a.video).save(out.with_suffix(".guide.png"))
    print(f"saved {a.out}")
    for w in safe_warnings(boxes, a.video):
        print(f"  [WARN] {w}")


if __name__ == "__main__":
    main()
