"""Shared helpers for the Play Store screenshot scripts.

Only needs Pillow. Works on Windows, macOS and Linux.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, features

# Headlines can be in any script (Bangla, ★…): never crash printing them on a
# console whose code page can't show them (e.g. Windows cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="backslashreplace")

# Google Play sizes we build for.
PLAY_SHOT = (1080, 1920)      # 9:16 phone screenshot
FEATURE_GRAPHIC = (1024, 500)  # required feature graphic

# Device types Play takes screenshots for. "text": False follows Google's
# large-screen advice ("exclude additional text that is not part of your core
# app experience, as this can get cut off"). Override any of it per project in
# playstore.json "devices": {"tablet10": {"size": [2560, 1440], "text": true}}.
DEVICES = {
    "phone":      {"size": (1080, 1920), "frame": "phone",  "text": True,  "raw_key": "raw",
                   "sides": (320, 3840)},
    "tablet7":    {"size": (1080, 1920), "frame": "tablet", "text": False, "raw_key": "raw_tablet7",
                   "sides": (1080, 7680)},
    "tablet10":   {"size": (1440, 2560), "frame": "tablet", "text": False, "raw_key": "raw_tablet10",
                   "sides": (1080, 7680)},
    "chromebook": {"size": (2560, 1440), "frame": "none",   "text": False, "raw_key": "raw_chromebook",
                   "sides": (1080, 7680)},
}

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

def main_language(cfg: dict) -> str:
    return cfg.get("language", "en-US")


def load_config(path: str | os.PathLike, locale: str | None = None) -> tuple[dict, Path]:
    """Read playstore.json. Returns (config, folder the config lives in).

    With a locale other than the main "language", that locale's overrides
    (headlines, fonts, raw screenshots...) are merged in, and its images go
    to their own sub-folder (work/bn-BD/, final/bn-BD/)."""
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        cfg = json.load(f)
    if locale and locale != main_language(cfg):
        cfg = localize(cfg, locale)
        cfg["_locale_dir"] = locale
    return cfg, p.parent.resolve()


def save_config(cfg: dict, path: str | os.PathLike) -> None:
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
        f.write("\n")


def localize(cfg: dict, locale: str) -> dict:
    """Merge cfg["locales"][locale] over the main config.

    A locale block can override "fonts", "brand", "uppercase", "prompt_style",
    per slug any screenshot field ("headline", "sub", "raw", "stats",
    "callouts"...), and "feature_graphic" fields. Anything not given falls back
    to the main language."""
    loc = (cfg.get("locales") or {}).get(locale)
    if loc is None:
        sys.exit(f"No locale {locale!r} in the config (add it under \"locales\").")
    out = copy.deepcopy(cfg)
    out["language"] = locale
    for key in ("fonts", "brand", "feature_graphic"):
        if key in loc:
            out[key] = {**(out.get(key) or {}), **loc[key]}
    for key in ("uppercase", "prompt_style"):
        if key in loc:
            out[key] = loc[key]
    per_slug = loc.get("screenshots") or {}
    unknown = set(per_slug) - {s.get("slug") for s in out.get("screenshots", [])}
    if unknown:
        print(f"[locale {locale}] unknown slug(s) ignored: {sorted(unknown)}")
    for item in out.get("screenshots", []):
        item.update(per_slug.get(item.get("slug"), {}))
    return out


def all_locales(cfg: dict) -> list[str]:
    main = main_language(cfg)
    return [main] + [k for k in (cfg.get("locales") or {}) if k != main]


def device_info(cfg: dict, device: str = "phone") -> dict:
    if device not in DEVICES:
        sys.exit(f"Unknown device {device!r}. Use one of {sorted(DEVICES)}.")
    info = {**DEVICES[device], **((cfg.get("devices") or {}).get(device) or {})}
    if device == "phone":
        if cfg.get("size"):
            info["size"] = cfg["size"]
        if cfg.get("frame") == "none":
            info["frame"] = "none"
    info["size"] = tuple(info["size"])
    info["name"] = device
    return info


def raw_of(item: dict, device: str = "phone") -> str | None:
    return item.get(DEVICES[device]["raw_key"])


def out_dir(root: Path, kind: str, cfg: dict, device: str = "phone") -> Path:
    """work/ or final/ folder for this language and device:
    final/, final/tablet10/, final/bn-BD/, final/bn-BD/tablet10/ ..."""
    d = root / kind
    if cfg.get("_locale_dir"):
        d = d / cfg["_locale_dir"]
    return d if device == "phone" else d / device


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


def contrast(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def auto_text(bg) -> tuple[int, int, int]:
    """White on dark backgrounds, near-black on light ones."""
    return (255, 255, 255) if luminance(bg) < 0.4 else (17, 24, 39)


def readable(color, bg, minimum: float = 3.0) -> tuple[int, int, int]:
    """The colour, lightened or darkened just enough to read on bg."""
    target = (255, 255, 255) if luminance(bg) < 0.4 else (0, 0, 0)
    out = tuple(color)
    for i in range(1, 21):
        if contrast(out, bg) >= minimum:
            break
        out = mix(color, target, i / 20)
    return out  # type: ignore[return-value]


# ---------------------------------------------------------------- fonts

def resolve_font(spec: str | None, kind: str = "bold") -> str | None:
    """Font spec is a file path, optionally with '#Variation' for variable
    fonts, e.g. 'fonts/IBMPlexSans[wdth,wght].ttf#Bold'. Falls back to a
    system font, then to Pillow's built-in font (None). kind="accent" has no
    fallback: without an accent font, _marked_ words use the highlight colour."""
    if spec:
        path = spec.split("#", 1)[0]
        if Path(path).is_file():
            return spec
        print(f"[font] not found: {path} - using a system font instead")
    if kind == "accent":
        return None
    for cand in _FONT_CANDIDATES.get(kind, []) + _FONT_CANDIDATES["bold"]:
        if Path(cand).is_file():
            return cand
    return None


@lru_cache(maxsize=256)
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


def abs_spec(root: Path, p: str | None) -> str | None:
    """Config path (relative to playstore.json, maybe with '#Variation') -> absolute."""
    if not p:
        return None
    path, sep, var = p.partition("#")
    full = Path(path) if Path(path).is_absolute() else root / path
    return f"{full}{sep}{var}"


def config_fonts(cfg: dict, root: Path) -> dict:
    """{"bold", "regular", "accent"} font specs from the config, resolved."""
    f = cfg.get("fonts") or {}
    return {"bold": resolve_font(abs_spec(root, f.get("bold")), "bold"),
            "regular": resolve_font(abs_spec(root, f.get("regular")), "regular"),
            "accent": resolve_font(abs_spec(root, f.get("accent")), "accent")}


# Scripts Pillow can only draw correctly with libraqm (complex shaping).
_COMPLEX = re.compile("[\u0590-\u08ff\u0900-\u0dff\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff]")
_warned_shaping = False


def warn_shaping(text: str) -> None:
    global _warned_shaping
    if _warned_shaping or not _COMPLEX.search(text or "") or features.check("raqm"):
        return
    _warned_shaping = True
    print("[WARN] This text needs complex shaping (e.g. Bangla, Hindi, Arabic), but this Pillow "
          "has no libraqm, so letters may join wrongly. Install libraqm + FriBiDi (Pillow docs: "
          "Installation > External libraries) or make these images with the image-AI prompts.")


# ---------------------------------------------------------------- rich text
#
# Headlines may mark words:  *word*  -> highlight colour
#                            _word_  -> accent font (e.g. an italic serif);
#                                       highlight colour if there is no accent font
#                            \n      -> line break;  \* and \_ -> a literal * or _

HL, ACC = 1, 2
_MARKS = re.compile(r"(?<!\\)[*_]")


def plain_text(text: str | None) -> str:
    """The words without markup (for rule checks and prompts)."""
    return _MARKS.sub("", text or "").replace("\\*", "*").replace("\\_", "_")


def marked_words(text: str | None) -> list[str]:
    """Phrases wrapped in *...* or _..._ (for prompts)."""
    return [plain_text(m.group(2)).strip()
            for m in re.finditer(r"(?<!\\)([*_])(.+?)(?<!\\)\1", text or "", re.S)]


def parse_marks(text: str) -> list[list[list[tuple[str, int]]]]:
    """paragraphs -> words -> (text, flags) segments."""
    paras, flags = [], 0
    for para in text.split("\n"):
        words: list = []
        cur: list = []
        buf = ""
        i = 0
        while i < len(para):
            ch = para[i]
            if ch == "\\" and i + 1 < len(para) and para[i + 1] in "*_":
                buf += para[i + 1]
                i += 2
                continue
            if ch in "*_":
                if buf:
                    cur.append((buf, flags))
                    buf = ""
                flags ^= HL if ch == "*" else ACC
            elif ch.isspace():
                if buf:
                    cur.append((buf, flags))
                    buf = ""
                if cur:
                    words.append(cur)
                    cur = []
            else:
                buf += ch
            i += 1
        if buf:
            cur.append((buf, flags))
        if cur:
            words.append(cur)
        paras.append(words)
    return paras


class Rich:
    """A block of marked-up text at one size, wrapped to max_w and balanced."""

    def __init__(self, text: str, fonts: tuple[str | None, str | None], size: int, max_w: int,
                 upper: bool = False, accent_scale: float = 1.1):
        warn_shaping(text)
        self.base = load_font(fonts[0], size)
        self.acc = load_font(fonts[1], round(size * accent_scale)) if fonts[1] else None
        self.paras = parse_marks(text.upper() if upper else text)
        self.space = self.base.getlength(" ")
        self.max_w = max_w
        self.lines = self._wrap(max_w)
        if len(self.lines) > 1:  # same number of lines, as even as possible
            n, w = len(self.lines), max_w
            while w > max_w // 3:
                w -= max(4, max_w // 60)
                trial = self._wrap(w)
                if len(trial) > n or any(self.line_w(ln) > w for ln in trial):
                    break
                self.lines = trial

    def font(self, flags: int):
        return self.acc if (flags & ACC and self.acc) else self.base

    def word_w(self, word) -> float:
        return sum(self.font(f).getlength(t) for t, f in word)

    def line_w(self, line) -> float:
        return sum(self.word_w(w) for w in line) + self.space * max(0, len(line) - 1)

    def _wrap(self, max_w: int):
        lines = []
        for words in self.paras:
            cur: list = []
            for w in words:
                if cur and self.line_w(cur + [w]) > max_w:
                    lines.append(cur)
                    cur = [w]
                else:
                    cur.append(w)
            lines.append(cur)
        return lines

    def fits(self, max_lines: int) -> bool:
        return len(self.lines) <= max_lines and all(self.line_w(ln) <= self.max_w for ln in self.lines)

    def width(self) -> int:
        return round(max((self.line_w(ln) for ln in self.lines), default=0))

    def _metrics(self, line):
        fonts = {self.font(f) for w in line for _, f in w} or {self.base}
        return max(f.getmetrics()[0] for f in fonts), max(f.getmetrics()[1] for f in fonts)

    def height(self, gap: float = 0.08) -> int:
        h = 0
        for i, ln in enumerate(self.lines):
            a, d = self._metrics(ln)
            h += a + d + (round((a + d) * gap) if i < len(self.lines) - 1 else 0)
        return h

    def draw(self, draw: ImageDraw.ImageDraw, x: int, y: int, fill, highlight=None,
             gap: float = 0.08, align: str = "center") -> int:
        """Draw centred on x (or left-aligned at x). Returns the y under the last line."""
        highlight = highlight or fill
        for i, ln in enumerate(self.lines):
            a, d = self._metrics(ln)
            cx = x - self.line_w(ln) / 2 if align == "center" else x
            for word in ln:
                for t, f in word:
                    font = self.font(f)
                    colour = highlight if (f & HL or (f & ACC and not self.acc)) else fill
                    draw.text((cx, y + a), t, font=font, fill=colour, anchor="ls")
                    cx += font.getlength(t)
                cx += self.space
            y += a + d + (round((a + d) * gap) if i < len(self.lines) - 1 else 0)
        return y


def fit_rich(text: str, fonts: tuple[str | None, str | None], max_w: int, max_lines: int,
             size_max: int, size_min: int, upper: bool = False) -> Rich:
    """Biggest size (size_max..size_min) where the text fits in max_lines lines of max_w."""
    size = size_max
    while True:
        r = Rich(text, fonts, size, max_w, upper)
        if r.fits(max_lines) or size <= size_min:
            return r
        size = max(size_min, size - 3)


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


def paste_clipped(canvas: Image.Image, layer: Image.Image, xy) -> None:
    """alpha_composite that allows the layer to be partly off the canvas."""
    x, y = round(xy[0]), round(xy[1])
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(layer.width, canvas.width - x), min(layer.height, canvas.height - y)
    if x1 > x0 and y1 > y0:
        canvas.alpha_composite(layer.crop((x0, y0, x1, y1)), (x + x0, y + y0))


def paste_shadow(canvas: Image.Image, layer: Image.Image, xy, blur=40,
                 opacity=0.45, offset=(0, 24)) -> None:
    pad = blur * 3
    big = Image.new("RGBA", (layer.width + 2 * pad, layer.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(layer, (pad, pad))
    sh = shadow_of(big, blur, opacity)
    paste_clipped(canvas, sh, (xy[0] - pad + offset[0], xy[1] - pad + offset[1]))


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
    paste_clipped(canvas, blob, (center[0] - (r + pad) * k, center[1] - (r + pad) * k))


def cover(img: Image.Image, size) -> Image.Image:
    """Scale to fill `size`, then centre-crop."""
    w, h = size
    s = max(w / img.width, h / img.height)
    r = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


# ---------------------------------------------------------------- 3D tilt

def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with pivoting (8x8 here; no numpy needed)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _perspective_coeffs(out_pts, in_pts) -> list[float]:
    """Coefficients for Image.transform(PERSPECTIVE): output point -> input point."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(out_pts, in_pts):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rhs.append(u)
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs.append(v)
    return _solve(rows, rhs)


def tilt_layer(layer: Image.Image, turn: float = 0, lean: float = 0, rot: float = 0,
               depth: float = 1.7) -> Image.Image:
    """Turn a flat layer in 3D and rotate it, like a phone held at an angle.

    turn  degrees around the vertical axis (+ = the right edge goes away)
    lean  degrees around the horizontal axis (+ = the top edge goes away)
    rot   degrees in the picture plane (+ = clockwise)
    """
    out = layer.convert("RGBA")
    if abs(turn) > 0.1 or abs(lean) > 0.1:
        ss = 2  # supersample for smooth edges
        big = out.resize((out.width * ss, out.height * ss), Image.BICUBIC)
        w, h = big.size
        d = depth * max(w, h)
        ty, tx = math.radians(turn), math.radians(lean)
        pts = []
        for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            x1, z1 = x * math.cos(ty), -x * math.sin(ty)       # around the vertical axis
            y2, z2 = y * math.cos(tx), z1 + y * math.sin(tx)   # around the horizontal axis
            s = d / (d - z2)
            pts.append((x1 * s, y2 * s))
        minx, miny = min(p[0] for p in pts), min(p[1] for p in pts)
        pts = [(x - minx + 2, y - miny + 2) for x, y in pts]
        size = (math.ceil(max(p[0] for p in pts)) + 2, math.ceil(max(p[1] for p in pts)) + 2)
        coeffs = _perspective_coeffs(pts, [(0, 0), (w, 0), (w, h), (0, h)])
        big = big.transform(size, Image.PERSPECTIVE, coeffs, Image.BICUBIC)
        out = big.resize((max(1, size[0] // ss), max(1, size[1] // ss)), Image.LANCZOS)
    if abs(rot) > 0.05:
        out = out.rotate(-rot, resample=Image.BICUBIC, expand=True)
    return out


# ---------------------------------------------------------------- status bar

def clean_status_bar(img: Image.Image, height: int | None = None, keep_left: float = 0.30) -> Image.Image:
    """Hide the phone's status-bar icons (low battery, notifications) on the
    right, keeping the clock on the left. Only touches the system status bar,
    never the app: each column on the right is replaced by an empty column
    from the middle, so gradients and colours stay as they were."""
    out = img.convert("RGB").copy()
    w, h = out.size
    # ~24dp: about 4% of a tall phone screen, less on tablets and landscape.
    sb = height or round(h * 0.040 if h / w > 1.9 else max(w, h) * 0.0225)
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
