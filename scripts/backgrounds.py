"""Backgrounds for the screenshots and the feature graphic.

Styles (the "look" of a set):

  flat      solid brand colour
  gradient  brand colour fading into the accent, with soft light blobs
  mesh      deep base with large blended colour patches (a "mesh gradient")
  light     a pale tint of the brand with soft accent blobs; dark text

Texture (playstore.json "texture"), on top of any style:
  {"grain": 0.0-1.0, "pattern": "dots" | "grid" | null}

Panorama (playstore.json "panorama": true): one background as wide as the
whole set, cut into one piece per screenshot, so the set reads as one strip
in the Play carousel. The blobs sit across the cuts on purpose.
"""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from common import luminance, mix, soft_blob, vertical_gradient

STYLES = ("flat", "gradient", "mesh", "light")
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def area_colour(canvas: Image.Image, box) -> tuple[int, int, int]:
    """Average colour of a part of the background (to pick readable text colours)."""
    small = canvas.crop(box).convert("RGB").resize((8, 8), Image.BOX)
    raw = small.tobytes()
    n = len(raw) // 3
    return tuple(round(sum(raw[i::3]) / n) for i in range(3))  # type: ignore[return-value]


def _mesh(size, slide_w, n, bg, accent) -> Image.Image:
    W, H = size
    base = mix(bg, BLACK, 0.25)
    k = 8  # draw small, blur, scale up: smooth and fast
    small = Image.new("RGBA", (max(1, W // k), max(1, H // k)), base + (255,))
    unit = max(slide_w, H * 0.46) / k
    colours = [accent, mix(accent, bg, 0.55), mix(bg, WHITE, 0.18)]
    for i in range(n):
        flip = i % 2  # mirror every other slide so the strip doesn't repeat
        blobs = [(0.92, -0.02, 0.62, colours[0], 0.62), (0.02, 0.96, 0.58, colours[1], 0.55),
                 (0.30, 0.48, 0.36, colours[2], 0.30)]
        for x, y, r, c, a in blobs:
            x = (1 - x) if flip else x
            layer = Image.new("RGBA", small.size, c + (0,))
            m = Image.new("L", small.size, 0)
            cx, cy, rr = (i + x) * slide_w / k, y * H / k, r * unit
            ImageDraw.Draw(m).ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=round(255 * a))
            layer.putalpha(m.filter(ImageFilter.GaussianBlur(rr * 0.55)))
            small.alpha_composite(layer)
    return small.resize((W, H), Image.BICUBIC)


def _texture(canvas: Image.Image, texture: dict | None, slide_w: int, dark: bool) -> Image.Image:
    if not texture:
        return canvas
    W, H = canvas.size
    pattern = texture.get("pattern")
    if pattern in ("dots", "grid"):
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        col = (255, 255, 255, 26) if dark else (0, 0, 0, 18)
        step = max(12, round(slide_w * 0.045))
        if pattern == "dots":
            r = max(2, round(step * 0.09))
            for y in range(step // 2, H, step):
                for x in range(step // 2, W, step):
                    d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        else:
            lw = max(1, round(slide_w / 540))
            for x in range(0, W, step):
                d.line((x, 0, x, H), fill=col, width=lw)
            for y in range(0, H, step):
                d.line((0, y, W, y), fill=col, width=lw)
        canvas.alpha_composite(layer)
    grain = float(texture.get("grain") or 0)
    if grain > 0:
        noise = Image.effect_noise((W, H), 48).convert("RGB")
        rgb = canvas.convert("RGB")
        lit = ImageChops.soft_light(rgb, noise)
        canvas = Image.blend(rgb, lit, min(1.0, grain) * 0.6).convert("RGBA")
    return canvas


def make_background(style: str, size, bg, accent, *, texture: dict | None = None,
                    slides: int = 1) -> Image.Image:
    """A background for `slides` screenshots side by side (slides=1: one image).
    size is ONE slide's size; the result is slides x as wide."""
    if style not in STYLES:
        raise ValueError(f"Unknown background style {style!r}; use {STYLES}")
    w, H = size
    W = w * slides
    if style == "flat":
        canvas = Image.new("RGBA", (W, H), bg + (255,))
    elif style == "mesh":
        canvas = _mesh((W, H), w, slides, bg, accent)
    elif style == "light":
        top, bottom = mix(bg, WHITE, 0.94), mix(accent, WHITE, 0.82)
        canvas = vertical_gradient((W, H), top, bottom)
        for i in range(slides):
            soft_blob(canvas, (round((i + 0.95) * w), round(H * 0.12)), round(w * 0.45), accent, 45)
            soft_blob(canvas, (round((i + 0.05) * w), round(H * 0.66)), round(w * 0.40),
                      mix(accent, WHITE, 0.4), 35)
    else:  # gradient
        canvas = vertical_gradient((W, H), mix(bg, WHITE, 0.04), mix(bg, accent, 0.45))
        for i in range(slides):
            soft_blob(canvas, (round((i + 0.92) * w), round(H * 0.10)), round(w * 0.42), accent, 70)
            soft_blob(canvas, (round((i + 0.02) * w), round(H * 0.62)), round(w * 0.38),
                      mix(accent, WHITE, 0.3), 45)
    dark = luminance(area_colour(canvas, (0, 0, w, H))) < 0.4
    return _texture(canvas, texture, w, dark)


def slice_of(wide: Image.Image, index: int, size) -> Image.Image:
    w, h = size
    return wide.crop((index * w, 0, index * w + w, h))
