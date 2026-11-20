"""Builds Google Play screenshots (phone 1080x1920, tablets, Chromebook; no transparency).

A benefit headline plus the REAL app screen in a plain Android phone or tablet.

Styles (versions to choose from; the background look):
  flat      solid brand colour
  gradient  brand colour fading to the accent, with soft light blobs
  popout    gradient + one part of the screen enlarged and lifted out of the
            phone (needs a "popout" box; without one, an accent circle sits
            behind the phone)
  mesh      deep base with large blended colour patches
  light     pale brand tint, dark text

Layouts (per screenshot, "layout" in playstore.json; mix them across the set):
  top       headline on top, phone below, running off the bottom edge (default)
  bottom    phone on top, running off the top edge, headline at the bottom
  tilted    headline on top, phone turned in 3D ("tilt": {"turn", "lean", "rot"})
  stats     headline, a row of 2-3 fact cards ("stats"), smaller phone
  bubble    phone moved aside to make room for "callouts" (chips / speech bubbles)

Headline markup: *word* = highlight colour, _word_ = accent font (fonts.accent).

One screenshot:
    python compose.py --screenshot raw/home.png --headline "Split *bazar* costs" \\
        --sub "Everyone pays their fair share" --bg "#071D3C" --accent "#009C96" \\
        --style mesh --layout tilted --out work/01/mesh.png

Everything in playstore.json (writes work/<slug>/<style>.png for each style):
    python compose.py --config store-screenshots/playstore.json
    python compose.py --config store-screenshots/playstore.json --slug 01-split-costs --styles popout
    python compose.py --config ... --slug 01-split-costs --layouts top,tilted,bottom   # compare layouts
    python compose.py --config ... --device tablet10        # work/tablet10/<slug>/...
    python compose.py --config ... --locale bn-BD           # work/bn-BD/<slug>/...

Pick a version (copies it to final/<slug>.png as a flat PNG):
    python compose.py --config store-screenshots/playstore.json --pick 01-split-costs gradient
    python compose.py --config ... --pick 01-split-costs gradient-tilted
    python compose.py --config ... --pick 01-split-costs work/01-split-costs/ai-2.png

Each render also writes <name>.overlay.png: the device, pop-out, stats and
callouts alone on a transparent canvas. polish.py uses it to put the real app
screen back on top of an AI-polished image.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from android_frame import render
from backgrounds import area_colour, make_background, slice_of
from colors import highlight_for
from common import (DEVICES, auto_text, config_fonts, cover, device_info, fit_rich, hex_rgb,
                    load_config, luminance, mix, out_dir, paste_clipped, paste_shadow, parse_size,
                    prepare_raw, raw_of, readable, resolve_font, rounded, save_flat, tilt_layer)

STYLES = ("flat", "gradient", "popout", "mesh", "light")
LAYOUTS = ("top", "bottom", "tilted", "stats", "bubble")
TILT_DEFAULT = {"turn": 22, "lean": 6, "rot": -4}
# Screen width (share of the canvas width) for a tall phone screen, per layout.
PHONE_W = {"top": 0.70, "bottom": 0.70, "tilted": 0.66, "stats": 0.60, "bubble": 0.64}


def bg_style(style: str) -> str:
    return "gradient" if style == "popout" else style


def look_for(cfg: dict, root: Path, dev: dict) -> dict:
    brand = cfg.get("brand", {})
    return {"bg": brand.get("background", "#111827"), "accent": brand.get("accent", "#3B82F6"),
            "text": brand.get("text"), "highlight": brand.get("highlight"),
            "phone": brand.get("phone", "#111418"), "fonts": config_fonts(cfg, root),
            "uppercase": cfg.get("uppercase", True), "texture": cfg.get("texture"),
            "frame": dev["frame"], "show_text": dev["text"]}


# ---------------------------------------------------------------- add-ons

def stats_row(stats: list[dict], fonts: dict, W: int, u: int, max_w: int, colours: dict,
              dark: bool) -> Image.Image:
    """A row of 2-3 fact cards: big value, small label."""
    stats = stats[:3]
    n = len(stats)
    gap = round(W * 0.03)
    cw = (max_w - gap * (n - 1)) // n
    pad = round(u * 0.03)
    vals = [fit_rich(s.get("value", ""), (fonts["bold"], fonts["accent"]), cw - 2 * pad, 1,
                     round(u * 0.072), round(u * 0.04)) for s in stats]
    labs = [fit_rich(s.get("label", ""), (fonts["regular"] or fonts["bold"], None), cw - 2 * pad, 2,
                     round(u * 0.032), round(u * 0.024)) for s in stats]
    vgap = round(u * 0.012)
    ch = 2 * pad + max(v.height(0.02) for v in vals) + vgap + max(lb.height(0.1) for lb in labs)
    row = Image.new("RGBA", (max_w, ch), (0, 0, 0, 0))
    fill = (255, 255, 255, 24) if dark else (255, 255, 255, 235)
    for i, (v, lb) in enumerate(zip(vals, labs)):
        card = rounded(Image.new("RGBA", (cw, ch), fill), round(u * 0.028))
        d = ImageDraw.Draw(card)
        y = v.draw(d, cw // 2, pad, colours["highlight"], colours["highlight"], gap=0.02)
        lb.draw(d, cw // 2, y + vgap, colours["sub"], colours["highlight"], gap=0.1)
        row.alpha_composite(card, (i * (cw + gap), 0))
    return row


def callout_layer(c: dict, fonts: dict, W: int, u: int, accent, dark: bool, side: str) -> Image.Image:
    """A chip (pill in the accent colour) or a speech bubble whose tail points at the device."""
    if c.get("kind") == "chip":
        t = fit_rich(c["text"], (fonts["bold"], fonts["accent"]), round(W * 0.5), 1,
                     round(u * 0.036), round(u * 0.026))
        px, py = round(t.base.size * 0.65), round(t.base.size * 0.38)
        w, h = t.width() + 2 * px, t.height() + 2 * py
        layer = rounded(Image.new("RGBA", (w, h), accent + (255,)), h // 2)
        ink = auto_text(accent)
        t.draw(ImageDraw.Draw(layer), w // 2, py, ink, ink)
        return layer
    t = fit_rich(c["text"], (fonts["regular"] or fonts["bold"], fonts["accent"]), round(W * 0.42), 3,
                 round(u * 0.036), round(u * 0.026))
    px, py = round(t.base.size * 0.8), round(t.base.size * 0.6)
    w, h = t.width() + 2 * px, t.height(0.15) + 2 * py
    tail = round(t.base.size * 0.55)
    box = (255, 255, 255) if dark else (17, 24, 39)
    layer = Image.new("RGBA", (w, h + tail), (0, 0, 0, 0))
    layer.alpha_composite(rounded(Image.new("RGBA", (w, h), box + (255,)), round(min(h, t.base.size * 2) * 0.45)))
    # The tail sits on the side that faces the device.
    tx = w - round(w * 0.22) if side == "left" else round(w * 0.22)
    tip = tx + (tail if side == "left" else -tail)
    ImageDraw.Draw(layer).polygon([(tx - tail // 2, h - 2), (tx + tail // 2, h - 2), (tip, h + tail)], fill=box)
    ink = (17, 24, 39) if dark else (255, 255, 255)
    t.draw(ImageDraw.Draw(layer), w // 2, py, ink, readable(accent, box, 3.0), gap=0.15)
    return layer


# ---------------------------------------------------------------- compose

def compose(shot: Image.Image, item: dict, look: dict, *, style: str, size=(1080, 1920),
            background: Image.Image | None = None):
    """Returns (final RGBA canvas, overlay RGBA with only the device and add-ons, info)."""
    W, H = size
    u = min(W, round(H * 0.5625))       # text unit: the width of a 9:16 canvas
    bstyle = bg_style(style)
    bg_c = hex_rgb(item.get("background") or look["bg"])
    acc_c = hex_rgb(item.get("accent") or look["accent"])
    canvas = background.copy() if background is not None else make_background(
        bstyle, size, bg_c, acc_c, texture=look.get("texture"))
    # Text colours are picked against the background actually behind the text.
    text_band = (0, round(H * 0.68), W, H) if item.get("layout") == "bottom" else (0, 0, W, round(H * 0.32))
    base = area_colour(canvas, text_band)
    dark = luminance(base) < 0.4
    txt_c = hex_rgb(look["text"]) if look.get("text") and bstyle != "light" else auto_text(base)
    hl_c = highlight_for(look.get("highlight"), item.get("accent"), acc_c, base)
    colours = {"text": txt_c, "highlight": hl_c, "sub": mix(txt_c, base, 0.18)}
    fonts = look["fonts"]
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    layout = item.get("layout") or "top"
    if layout not in LAYOUTS:
        sys.exit(f"Unknown layout {layout!r}; use {LAYOUTS}.")
    show_text = bool(look.get("show_text", True) and item.get("headline"))
    if not show_text:
        layout = "center"
    stats = item.get("stats") or []
    if layout == "stats" and not stats:
        print(f"[note] {item.get('slug', '')}: layout 'stats' needs \"stats\"; using 'top'.")
        layout = "top"
    added_area = 0

    # --- text block (measured first: "bottom" needs its height)
    max_w = round(W * 0.84)
    head = sub = None
    block_h = 0
    if show_text:
        lines = max(2, item["headline"].count("\n") + 1)
        head = fit_rich(item["headline"], (fonts["bold"], fonts["accent"]), max_w, lines,
                        round(u * 0.105), round(u * 0.066), upper=look.get("uppercase", True))
        block_h = head.height(0.02)
        if item.get("sub"):
            sub = fit_rich(item["sub"], (fonts["regular"] or fonts["bold"], fonts["accent"]), max_w, 2,
                           round(u * 0.048), round(u * 0.036))
            block_h += round(H * 0.016) + sub.height(0.12)
        added_area += max(head.width(), sub.width() if sub else 0) * block_h

    def draw_text(y: int) -> int:
        y = head.draw(d, W // 2, y, txt_c, hl_c, gap=0.02)
        if sub:
            y = sub.draw(d, W // 2, y + round(H * 0.016), colours["sub"], hl_c, gap=0.12)
        return y

    text_top = H
    y_after = 0
    if layout == "bottom":
        text_top = H - round(H * 0.065) - block_h
        draw_text(text_top)
    elif show_text:
        y_after = draw_text(round(H * 0.06))

    # --- stats row
    if layout == "stats":
        row = stats_row(stats, fonts, W, u, max_w, colours, dark)
        ry = y_after + round(H * 0.03)
        canvas.alpha_composite(row, ((W - row.width) // 2, ry))
        overlay.alpha_composite(row, ((W - row.width) // 2, ry))
        added_area += row.width * row.height
        y_after = ry + row.height

    # --- device
    ratio = shot.width / shot.height
    if layout == "center":
        screen_w = round(min(W * 0.84, H * 0.86 * ratio) * 0.95)
    elif ratio >= 1:            # landscape screen (tablet / Chromebook)
        screen_w = round(W * 0.88)
    elif ratio > 0.56:          # portrait tablet screen
        screen_w = round(W * 0.80)
    else:                       # tall phone screen
        screen_w = round(W * PHONE_W[layout])
    dev, (_, sy, _, _) = render(shot, screen_w, look["frame"], look["phone"])
    in_dev = screen_w / shot.width
    tilt = dict(TILT_DEFAULT) if layout == "tilted" else {}
    tilt.update(item.get("tilt") or {})
    tilted = any(abs(float(tilt.get(k, 0))) > 0.05 for k in ("turn", "lean", "rot"))
    if tilted:
        dev = tilt_layer(dev, float(tilt.get("turn", 0)), float(tilt.get("lean", 0)), float(tilt.get("rot", 0)))
    shift = float(item.get("shift", 0.07 if layout == "bubble" else 0))
    px = (W - dev.width) // 2 + round(W * shift)
    if layout == "center":
        py = (H - dev.height) // 2
    elif layout == "bottom":
        py = text_top - round(H * 0.04) - dev.height
    else:
        py = y_after + round(H * (0.035 if layout in ("tilted", "stats") else 0.045))

    if style == "popout" and not item.get("popout"):
        # No box to lift out: an accent circle behind the device instead.
        r = round(W * 0.47)
        cx = px + dev.width // 2
        cy = py + round(dev.height * (0.70 if layout == "bottom" else 0.30))
        circle = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(circle).ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(acc_c, base, 0.15) + (255,))
        canvas.alpha_composite(circle)

    paste_shadow(canvas, dev, (px, py), blur=round(W * 0.035), opacity=0.45, offset=(0, round(W * 0.02)))
    paste_clipped(canvas, dev, (px, py))
    paste_clipped(overlay, dev, (px, py))

    # --- pop-out: a part of the real screen, bigger, floating over the device
    if style == "popout" and item.get("popout"):
        x0, y0, x1, y1 = item["popout"]
        part = shot.convert("RGBA").crop((x0, y0, x1, y1))
        target_w = round(W * 0.90)
        k = target_w / part.width
        part = rounded(part.resize((target_w, round(part.height * k)), Image.LANCZOS), round(u * 0.03))
        mid = py + (round(dev.height * 0.45) if tilted else sy + round((y0 + y1) / 2 * in_dev))
        if layout == "bottom":
            lo, hi = round(H * 0.04), text_top - part.height - round(H * 0.03)
        else:
            lo, hi = y_after + round(H * 0.03), H - part.height - round(H * 0.04)
        top = max(lo, min(mid - part.height // 2, hi))
        left = (W - part.width) // 2
        paste_shadow(canvas, part, (left, top), blur=round(W * 0.03), opacity=0.5, offset=(0, round(W * 0.018)))
        canvas.alpha_composite(part, (left, top))
        overlay.alpha_composite(part, (left, top))

    # --- callouts (chips / speech bubbles), on any layout
    default_y = [0.30, 0.48, 0.18] if layout == "bottom" else [0.52, 0.72, 0.40]
    for i, c in enumerate((item.get("callouts") or [])[:3]):
        if not c.get("text"):
            continue
        side = c.get("side") or ("left" if layout == "bubble" or i % 2 == 0 else "right")
        layer = callout_layer(c, fonts, W, u, acc_c, dark, side)
        added_area += layer.width * layer.height
        layer = tilt_layer(layer, rot=float(c.get("rot", -4 if side == "left" else 4)))
        x = round(W * 0.05) if side == "left" else W - round(W * 0.05) - layer.width
        y = round(H * float(c.get("y", default_y[i]))) - layer.height // 2
        paste_shadow(canvas, layer, (x, y), blur=round(W * 0.02), opacity=0.35, offset=(0, round(W * 0.01)))
        paste_clipped(canvas, layer, (x, y))
        paste_clipped(overlay, layer, (x, y))

    return canvas, overlay, {"text_area": added_area / (W * H), "layout": layout}


# ---------------------------------------------------------------- config mode

def shot_entries(cfg: dict, slug: str | None):
    items = cfg.get("screenshots", [])
    if slug:
        items = [s for s in items if s.get("slug") == slug]
        if not items:
            sys.exit(f"No screenshot with slug {slug!r} in the config.")
    return items


def run_config(cfg_path: str, slug: str | None, styles: list[str], device: str = "phone",
               locale: str | None = None, layouts: list[str] | None = None) -> None:
    cfg, root = load_config(cfg_path, locale)
    dev = device_info(cfg, device)
    size = dev["size"]
    look = look_for(cfg, root, dev)
    all_items = cfg.get("screenshots", [])
    work = out_dir(root, "work", cfg, device)
    wide: dict = {}
    for item in shot_entries(cfg, slug):
        raw_rel = raw_of(item, device)
        if not raw_rel:
            print(f"[skip] {item['slug']}: no \"{DEVICES[device]['raw_key']}\". Take this screen on a "
                  f"{device} (or emulator): Play wants the real large-screen layout.")
            continue
        raw = root / raw_rel
        if not raw.is_file():
            print(f"[skip] {item['slug']}: raw screenshot not found: {raw}")
            continue
        shot = prepare_raw(Image.open(raw), cfg, item)
        area = 0.0
        for lay in layouts or [None]:
            it = {**item, "layout": lay} if lay else item
            for style in styles:
                background = None
                if cfg.get("panorama"):
                    if style not in wide:
                        wide[style] = make_background(
                            bg_style(style), size, hex_rgb(look["bg"]), hex_rgb(look["accent"]),
                            texture=look.get("texture"), slides=len(all_items))
                    background = slice_of(wide[style], all_items.index(item), size)
                img, ov, info = compose(shot, it, look, style=style, size=size, background=background)
                area = max(area, info["text_area"])
                out = work / item["slug"] / f"{style}-{lay}.png" if lay else work / item["slug"] / f"{style}.png"
                save_flat(img, out)
                ov.save(out.with_suffix(".overlay.png"))
                print(f"saved {out.relative_to(root)}")
        if area > 0.20:
            print(f"[WARN] {item['slug']}: added text covers ~{area:.0%} of the image; Google asks for "
                  "taglines under 20%. Shorten the headline/sub or drop a callout.")


def pick(cfg_path: str, slug: str, choice: str, device: str = "phone", locale: str | None = None) -> None:
    cfg, root = load_config(cfg_path, locale)
    size = device_info(cfg, device)["size"]
    src = Path(choice)
    if not src.suffix:
        src = out_dir(root, "work", cfg, device) / slug / f"{choice}.png"
    elif not src.is_absolute() and not src.is_file():
        src = root / choice
    if not src.is_file():
        sys.exit(f"Not found: {src}")
    img = Image.open(src)
    if img.size != size:
        img = cover(img.convert("RGB"), size)
    out = save_flat(img, out_dir(root, "final", cfg, device) / f"{slug}.png")
    print(f"final: {out.relative_to(root)} ({img.width}x{img.height})")


def _csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="playstore.json (batch mode)")
    ap.add_argument("--slug", help="only this screenshot (config mode)")
    ap.add_argument("--styles", default="gradient,mesh,light,popout", help=f"comma list of {','.join(STYLES)}")
    ap.add_argument("--layouts", help=f"also render these layouts, as <style>-<layout>.png ({','.join(LAYOUTS)})")
    ap.add_argument("--device", default="phone", choices=sorted(DEVICES))
    ap.add_argument("--locale", help="a language from \"locales\" (e.g. bn-BD)")
    ap.add_argument("--pick", nargs=2, metavar=("SLUG", "VERSION_OR_FILE"), help="copy a version to final/")
    # single mode
    ap.add_argument("--screenshot")
    ap.add_argument("--headline")
    ap.add_argument("--sub")
    ap.add_argument("--style", default="gradient", choices=STYLES)
    ap.add_argument("--layout", default="top", choices=LAYOUTS)
    ap.add_argument("--tilt", help="turn,lean,rot in degrees, e.g. 16,4,-3")
    ap.add_argument("--stat", action="append", default=[], help='"VALUE|label" (repeat for 2-3 cards)')
    ap.add_argument("--callout", action="append", default=[], help='"text" or "chip:text" (repeatable)')
    ap.add_argument("--bg", default="#111827")
    ap.add_argument("--accent", default="#3B82F6")
    ap.add_argument("--highlight", help="colour for *marked* words (default: accent)")
    ap.add_argument("--text", help="text colour (default: auto)")
    ap.add_argument("--font-bold")
    ap.add_argument("--font-regular")
    ap.add_argument("--font-accent", help="font for _marked_ words, e.g. an italic serif")
    ap.add_argument("--grain", type=float, default=0)
    ap.add_argument("--pattern", choices=("dots", "grid"))
    ap.add_argument("--frame", default="phone", choices=("phone", "tablet", "none"))
    ap.add_argument("--popout", help="x0,y0,x1,y1 box in screenshot pixels")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--keep-case", action="store_true", help="do not uppercase the headline")
    ap.add_argument("--out")
    a = ap.parse_args()

    styles = _csv(a.styles)
    bad = [s for s in styles if s not in STYLES] + [x for x in _csv(a.layouts) if x not in LAYOUTS]
    if bad:
        sys.exit(f"Unknown style/layout: {bad}. Styles: {STYLES}. Layouts: {LAYOUTS}.")

    if a.config and a.pick:
        pick(a.config, *a.pick, device=a.device, locale=a.locale)
    elif a.config:
        run_config(a.config, a.slug, styles, a.device, a.locale, _csv(a.layouts) or None)
    else:
        if not (a.screenshot and a.headline and a.out):
            ap.error("single mode needs --screenshot, --headline and --out (or use --config)")
        item = {"headline": a.headline, "sub": a.sub, "layout": a.layout,
                "popout": [int(v) for v in a.popout.split(",")] if a.popout else None,
                "stats": [dict(zip(("value", "label"), s.split("|", 1))) for s in a.stat],
                "callouts": [{"kind": "chip", "text": c[5:]} if c.startswith("chip:") else {"text": c}
                             for c in a.callout]}
        if a.tilt:
            item["tilt"] = dict(zip(("turn", "lean", "rot"), (float(v) for v in a.tilt.split(","))))
        texture = {"grain": a.grain, "pattern": a.pattern} if (a.grain or a.pattern) else None
        look = {"bg": a.bg, "accent": a.accent, "text": a.text, "highlight": a.highlight,
                "phone": "#111418", "uppercase": not a.keep_case, "texture": texture,
                "frame": a.frame, "show_text": True,
                "fonts": {"bold": resolve_font(a.font_bold, "bold"),
                          "regular": resolve_font(a.font_regular, "regular"),
                          "accent": resolve_font(a.font_accent, "accent")}}
        img, ov, info = compose(Image.open(a.screenshot), item, look, style=a.style, size=parse_size(a.size))
        out = save_flat(img, a.out)
        ov.save(out.with_suffix(".overlay.png"))
        print(f"saved {out}")
        if info["text_area"] > 0.20:
            print(f"[WARN] added text covers ~{info['text_area']:.0%} of the image (Google: under 20%).")


if __name__ == "__main__":
    main()
