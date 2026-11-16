"""Shared helpers for the Play Store screenshot scripts.

Only needs Pillow. Works on Windows, macOS and Linux.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# Google Play sizes we build for.
PLAY_SHOT = (1080, 1920)      # 9:16 phone screenshot
FEATURE_GRAPHIC = (1024, 500)  # required feature graphic

# System fonts tried when no font is given. Never bundled: we only use what is
# already on the machine, or the font file the user / app provides.
_FONT_CANDIDATES = {
    "bold": [
        "C:/Windows/Fonts/seguibl.ttf",      # Segoe UI Black
        "C:/Windows/Fonts/segoeuib.ttf",     # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ],
}


# ---------------------------------------------------------------- config

def load_config(path: str | os.PathLike) -> tuple[dict, Path]:
    """Read playstore.json. Returns (config, folder the config lives in)."""
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        return json.load(f), p.parent.resolve()


def save_config(cfg: dict, path: str | os.PathLike) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------- colours

def hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError(f"Not a colour: {value!r} (use #RRGGBB)")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a, b, t: float) -> tuple[int, int, int]:
    """Blend colour a toward b by t (0..1)."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def luminance(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def auto_text(bg) -> tuple[int, int, int]:
    """White on dark backgrounds, near-black on light ones."""
    return (255, 255, 255) if luminance(bg) < 0.4 else (17, 24, 39)


# ---------------------------------------------------------------- fonts

def resolve_font(spec: str | None, kind: str = "bold") -> str | None:
    """Font spec is a file path, optionally with '#Variation' for variable
    fonts, e.g. 'fonts/IBMPlexSans[wdth,wght].ttf#Bold'. Falls back to a
    system font, then to Pillow's built-in font (None)."""
    if spec:
        path = spec.split("#", 1)[0]
        if Path(path).is_file():
            return spec
        print(f"[font] not found: {path} - using a system font instead")
    for cand in _FONT_CANDIDATES.get(kind, []) + _FONT_CANDIDATES["bold"]:
        if Path(cand).is_file():
            return cand
    return None


def load_font(spec: str | None, size: int) -> ImageFont.FreeTypeFont:
    if not spec:
        return ImageFont.load_default(size=size)
    path, _, variation = spec.partition("#")
    font = ImageFont.truetype(path, size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except Exception:  # not a variable font, or unknown name
            try:
                names = [n.decode() if isinstance(n, bytes) else n
                         for n in font.get_variation_names()]
                print(f"[font] variation {variation!r} not found; has {names}")
            except Exception:
                pass
    return font


def text_width(font, s: str) -> int:
    l, _, r, _ = font.getbbox(s)
    return r - l


def wrap(text: str, font, max_w: int) -> list[str]:
    """Greedy word wrap. Keeps manual line breaks ('\\n')."""
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if not cur or text_width(font, trial) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def balance(text: str, font, max_w: int, lines: list[str]) -> list[str]:
    """Same number of lines, but as even as possible (no lonely last word)."""
    if len(lines) < 2:
        return lines
    best = lines
    w = max_w
    while w > max_w // 3:
        w -= max(4, max_w // 60)
        trial = wrap(text, font, w)
        if len(trial) > len(lines) or any(text_width(font, ln) > w for ln in trial):
            break
        best = trial
    return best


def fit_text(text: str, spec: str | None, max_w: int, max_lines: int,
             size_max: int, size_min: int):
    """Biggest font size (size_max..size_min) where the text fits in
    max_lines lines of max_w. Returns (font, lines)."""
    size = size_max
    while True:
        font = load_font(spec, size)
        lines = wrap(text, font, max_w)
        fits = len(lines) <= max_lines and all(text_width(font, ln) <= max_w for ln in lines)
        if fits or size <= size_min:
            return font, balance(text, font, max_w, lines)
        size = max(size_min, size - 3)


def line_height(font) -> int:
    asc, desc = font.getmetrics()
    return asc + desc


def draw_lines(draw: ImageDraw.ImageDraw, lines, font, cx: int, y: int, fill,
               gap: float = 0.08, align: str = "center") -> int:
    """Draw lines centred on cx (or left-aligned at cx). Returns the y under the last line."""
    lh = line_height(font)
    anchor = "ma" if align == "center" else "la"
    for ln in lines:
        draw.text((cx, y), ln, font=font, fill=fill, anchor=anchor)
        y += round(lh * (1 + gap))
    return y - round(lh * gap)


# ---------------------------------------------------------------- shapes

def rounded_mask(size, radius: int, scale: int = 4) -> Image.Image:
    """Smooth (anti-aliased) rounded-rectangle mask."""
    w, h = size
    big = Image.new("L", (w * scale, h * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, w * scale - 1, h * scale - 1), radius=radius * scale, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def circle_mask(d: int, scale: int = 4) -> Image.Image:
    big = Image.new("L", (d * scale, d * scale), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * scale - 1, d * scale - 1), fill=255)
    return big.resize((d, d), Image.LANCZOS)


def rounded(img: Image.Image, radius: int) -> Image.Image:
    out = img.convert("RGBA")
    out.putalpha(ImageChops.multiply(out.getchannel("A"), rounded_mask(out.size, radius)))
    return out


def shadow_of(layer: Image.Image, blur: int, opacity: float, color=(0, 0, 0)) -> Image.Image:
    """Soft shadow with the same size as `layer` (draw it with an offset)."""
    a = layer.getchannel("A").point(lambda v: round(v * opacity))
    sh = Image.new("RGBA", layer.size, color + (0,))
    sh.putalpha(a)
    return sh.filter(ImageFilter.GaussianBlur(blur))


def paste_shadow(canvas: Image.Image, layer: Image.Image, xy, blur=40,
                 opacity=0.45, offset=(0, 24)) -> None:
    pad = blur * 3
    big = Image.new("RGBA", (layer.width + 2 * pad, layer.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(layer, (pad, pad))
    sh = shadow_of(big, blur, opacity)
    canvas.alpha_composite(sh, (xy[0] - pad + offset[0], xy[1] - pad + offset[1]))


def vertical_gradient(size, top, bottom) -> Image.Image:
    mask = Image.linear_gradient("L").resize(size, Image.BICUBIC)
    return Image.composite(Image.new("RGBA", size, bottom + (255,)),
                           Image.new("RGBA", size, top + (255,)), mask)


def soft_blob(canvas: Image.Image, center, radius: int, color, alpha: int) -> None:
    """A big blurred light circle. Drawn small and scaled up (it is blurry
    anyway), with empty padding so the blur never shows a square edge."""
    k = 4
    r = max(4, radius // k)
    pad = r
    size = 2 * r + 2 * pad
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((pad, pad, pad + 2 * r, pad + 2 * r), fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(r / 3))
    blob = Image.new("RGBA", (size, size), color + (0,))
    blob.putalpha(mask)
    blob = blob.resize((size * k, size * k), Image.BICUBIC)
    full = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    full.paste(blob, (center[0] - (r + pad) * k, center[1] - (r + pad) * k))
    canvas.alpha_composite(full)


def cover(img: Image.Image, size) -> Image.Image:
    """Scale to fill `size`, then centre-crop."""
    w, h = size
    s = max(w / img.width, h / img.height)
    r = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


# ---------------------------------------------------------------- status bar

def clean_status_bar(img: Image.Image, height: int | None = None, keep_left: float = 0.30) -> Image.Image:
    """Hide the phone's status-bar icons (low battery, notifications) on the
    right, keeping the clock on the left. Only touches the system status bar,
    never the app: each column on the right is replaced by an empty column
    from the middle, so gradients and colours stay as they were."""
    out = img.convert("RGB").copy()
    w, h = out.size
    sb = height or round(h * 0.040)  # ~24dp on most phones
    # The middle of a status bar is empty (screenshots never include the
    # camera hole), so that column is the clean background to copy.
    column = out.crop((w // 2, 0, w // 2 + 1, sb))
    for x in range(round(w * keep_left), w):
        out.paste(column, (x, 0))
    return out


def prepare_raw(img: Image.Image, cfg: dict, item: dict | None = None) -> Image.Image:
    """Apply the raw-screenshot fixes (currently: status bar). A screenshot's
    own "status_bar" settings override the config-wide ones."""
    sb = {**(cfg.get("status_bar") or {}), **((item or {}).get("status_bar") or {})}
    if sb.get("clean"):
        return clean_status_bar(img, sb.get("height"), sb.get("keep_left", 0.30))
    return img


# ---------------------------------------------------------------- saving

def save_flat(img: Image.Image, path: str | os.PathLike) -> Path:
    """Save with NO transparency (Play rejects alpha). PNG or JPEG by suffix."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rgb = img
    if img.mode in ("RGBA", "LA", "P"):
        base = Image.new("RGB", img.size, (255, 255, 255))
        base.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
        rgb = base
    elif img.mode != "RGB":
        rgb = img.convert("RGB")
    if p.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(p, "JPEG", quality=92, optimize=True)
    else:
        rgb.save(p, "PNG", optimize=True)
    return p


def parse_size(s: str) -> tuple[int, int]:
    w, _, h = s.lower().partition("x")
    return int(w), int(h)
