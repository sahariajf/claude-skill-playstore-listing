"""Picks the highlight colour for *marked* headline words, and previews options.

Rule of thumb (the same one most good app palettes follow: a brand colour plus
an accent in a CONTRASTING hue):

- The highlight must differ in hue from the background behind the headline
  (about 50 degrees or more on the colour wheel) AND reach 4.5:1 contrast.
  Brand teal on a teal/navy gradient fails the first test: it reads as the same
  colour, just lighter.
- On cool dark backgrounds (blue, navy, teal, green, purple) a warm highlight
  pops: amber, peach, gold. On warm dark backgrounds, a cool one: sky, mint.
- Avoid pure red for highlights: it reads as an error or money owed.
- On light backgrounds the brand accent, darkened to 4.5:1, usually works.
- One highlight colour for the whole set.

`brand.highlight` in playstore.json always wins. With no highlight set, the
scripts use auto_highlight() below.

    python colors.py --config store-screenshots/playstore.json                 # preview -> work/colors-<style>.png
    python colors.py --config ... --style light --slug 02-see-spending
    python colors.py --config ... --try "#F59E0B" --try "#8B5CF6"             # add your own ideas
    python colors.py --bg "#071D3C" --accent "#009C96"                        # just list the options
"""
from __future__ import annotations

import argparse
import colorsys

from PIL import Image, ImageDraw

from common import contrast, hex_rgb, luminance, readable

# Highlight colours that read well on dark backgrounds (they are darkened
# automatically for light ones).
CLASSICS = {
    "amber": "#FFC27A", "gold": "#FFD166", "peach": "#FFA987", "coral": "#FF8F70",
    "lime": "#C5F06B", "mint": "#6EE7B7", "sky": "#7CC8FF", "lilac": "#C4A5FF", "pink": "#FF8DC7",
}


def to_hex(c) -> str:
    return "#%02X%02X%02X" % tuple(c)


def hls(c):
    h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in c))
    return h * 360, l, s


def hue_gap(a, b) -> float:
    d = abs(hls(a)[0] - hls(b)[0]) % 360
    return min(d, 360 - d)


def _is_red(c) -> bool:
    h, _, s = hls(c)
    return s > 0.45 and (h >= 345 or h <= 12)


def _from_hls(h, l, s):
    return tuple(round(x * 255) for x in colorsys.hls_to_rgb((h % 360) / 360, l, s))


def _score(c, base, accent) -> float:
    """Higher = better highlight on `base`."""
    gap = hue_gap(c, base) if hls(base)[2] > 0.12 else 90  # grey base: any hue contrasts
    score = min(gap, 120) + min(contrast(c, base), 10) * 4
    h = hls(c)[0]
    cool_base = 150 <= hls(base)[0] <= 290
    if cool_base and 20 <= h <= 60:      # warm on cool pops
        score += 25
    if _is_red(c):
        score -= 60
    if hue_gap(c, accent) < 20:          # it's the brand colour itself: nice if it contrasts
        score += 10
    return score


def candidates(base, accent, extra: list[str] | None = None) -> list[tuple[str, tuple]]:
    """(name, colour) options, made readable on `base` (4.5:1), best first."""
    dark = luminance(base) < 0.4
    raw = [("brand accent", accent)]
    h, _, _ = hls(accent)
    raw.append(("accent complement", _from_hls(h + 180, 0.74 if dark else 0.36, 0.85)))
    raw += [(n, hex_rgb(v)) for n, v in CLASSICS.items()]
    raw += [(f"your {v}", hex_rgb(v)) for v in (extra or [])]
    out, seen = [], set()
    for name, c in raw:
        if not dark and name in CLASSICS:   # pastel classics -> deeper tone for light backgrounds
            hh, _, ss = hls(c)
            c = _from_hls(hh, 0.40, min(1.0, ss))
        c = readable(c, base, 4.5)
        key = to_hex(c)
        if key not in seen:
            seen.add(key)
            out.append((name, c))
    return sorted(out, key=lambda nc: -_score(nc[1], base, accent))


def auto_highlight(accent, base) -> tuple[int, int, int]:
    """The brand accent if it stands apart from the background behind the
    text; otherwise the best contrasting-hue option."""
    dark = luminance(base) < 0.4
    acc = readable(accent, base, 4.5)
    if not dark or hls(base)[2] < 0.12 or hue_gap(accent, base) >= 50:
        return acc
    return candidates(base, accent)[0][1]


def highlight_for(look_highlight: str | None, item_accent: str | None, accent, base):
    """brand.highlight (if set) made readable, else auto_highlight()."""
    if look_highlight and not item_accent:
        return readable(hex_rgb(look_highlight), base, 4.5)
    return auto_highlight(accent, base)


# ---------------------------------------------------------------- preview

def preview(cfg_path: str, style: str, slug: str | None, extra: list[str], n: int) -> None:
    from compose import compose, look_for, shot_entries
    from backgrounds import area_colour
    from common import device_info, load_config, load_font, out_dir, prepare_raw, raw_of, save_flat

    cfg, root = load_config(cfg_path)
    dev = device_info(cfg, "phone")
    look = look_for(cfg, root, dev)
    items = [i for i in shot_entries(cfg, slug) if "*" in i.get("headline", "") or "_" in i.get("headline", "")]
    item = (items or shot_entries(cfg, slug))[0]
    shot = prepare_raw(Image.open(root / raw_of(item)), cfg, item)
    W, H = dev["size"]
    # Background behind the text, from a render without highlight.
    first, _, _ = compose(shot, item, dict(look, highlight="#FFFFFF"), style=style, size=(W, H))
    band = (0, round(H * 0.68), W, H) if item.get("layout") == "bottom" else (0, 0, W, round(H * 0.32))
    base = area_colour(first, band)
    accent = hex_rgb(item.get("accent") or look["accent"])
    auto = to_hex(auto_highlight(accent, base))
    opts = candidates(base, accent, extra)[:n]
    if auto not in [to_hex(c) for _, c in opts]:
        opts = [("auto", hex_rgb(auto))] + opts[: n - 1]
    crop_h = round(H * 0.34)
    tw, th = 420, round(420 * crop_h / W)
    cols = min(4, len(opts))
    rows = -(-len(opts) // cols)
    pad, gap, lab = 40, 24, 70
    sheet = Image.new("RGB", (pad * 2 + cols * tw + (cols - 1) * gap, pad * 2 + rows * (th + lab + gap)), (242, 244, 247))
    d = ImageDraw.Draw(sheet)
    font = load_font(look["fonts"]["regular"] or look["fonts"]["bold"], 22)
    print(f"Background behind the headline: {to_hex(base)}  (style {style}, {item['slug']})")
    for i, (name, c) in enumerate(opts):
        img, _, _ = compose(shot, item, dict(look, highlight=to_hex(c)), style=style, size=(W, H))
        if item.get("layout") == "bottom":
            img = img.crop((0, H - crop_h, W, H))
        else:
            img = img.crop((0, 0, W, crop_h))
        x = pad + (i % cols) * (tw + gap)
        y = pad + (i // cols) * (th + lab + gap)
        sheet.paste(img.convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        tag = " (auto)" if to_hex(c) == auto else ""
        d.text((x, y + th + 10), f"{i + 1}. {name}{tag}", font=font, fill=(17, 24, 39))
        d.text((x, y + th + 38), f"{to_hex(c)}  ·  {contrast(c, base):.1f}:1  ·  hue gap {hue_gap(c, base):.0f}°",
               font=font, fill=(90, 98, 110))
        print(f"{i + 1}. {name:18} {to_hex(c)}  contrast {contrast(c, base):4.1f}:1  hue gap {hue_gap(c, base):3.0f}{tag}")
    out = save_flat(sheet, out_dir(root, "work", cfg) / f"colors-{style}.png")
    print(f"saved {out.relative_to(root)}  -> set the chosen one as brand.highlight")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--style", default="mesh", help="background style to preview on")
    ap.add_argument("--slug", help="screenshot to preview (default: the first with marked words)")
    ap.add_argument("--try", dest="extra", action="append", default=[], help="extra colour to compare (#RRGGBB)")
    ap.add_argument("-n", type=int, default=8, help="how many options")
    ap.add_argument("--bg", help="without --config: the background behind the headline")
    ap.add_argument("--accent", help="without --config: the brand accent")
    a = ap.parse_args()
    if a.config:
        preview(a.config, a.style, a.slug, a.extra, a.n)
        return
    if not (a.bg and a.accent):
        ap.error("needs --config, or --bg and --accent")
    base, accent = hex_rgb(a.bg), hex_rgb(a.accent)
    print(f"auto: {to_hex(auto_highlight(accent, base))}")
    for i, (name, c) in enumerate(candidates(base, accent, a.extra)[:a.n], 1):
        print(f"{i}. {name:18} {to_hex(c)}  contrast {contrast(c, base):4.1f}:1  hue gap {hue_gap(c, base):3.0f}")


if __name__ == "__main__":
    main()
