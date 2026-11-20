"""Checks the final images and texts against Google Play's rules.

    python check.py store-screenshots/final --config store-screenshots/playstore.json

It checks every folder under final/: the phone set in final/, large-screen
sets in final/tablet7/, final/tablet10/, final/chromebook/, and other
languages in final/<locale>/ (with their own device folders).

FAIL = Play will reject it or it breaks a listing rule. WARN = allowed, but
weaker (e.g. not eligible for Play's big recommendation spots). Exit code 1 if
anything fails. Source: Play Console Help, "Add preview assets to showcase
your app" (answer 9866151).
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from pathlib import Path

from PIL import Image

from common import DEVICES, FEATURE_GRAPHIC, all_locales, load_config, localize, main_language, plain_text

MAX_BYTES = 8 * 1024 * 1024
MAX_RATIO = 2.3        # "the maximum dimension can't be more than 2.3 times as long as the minimum"
MAX_PER_DEVICE = 8

# Google Play: no performance, ranking, award, testimonial, price or promo
# content, and no calls to action, in screenshots and the feature graphic.
FAIL_WORDS = [
    (r"#\s*1\b|\bno\.?\s*1\b|\bnumber\s+one\b", "ranking claim (#1)"),
    (r"\bbest\b", "'best' is a performance claim"),
    (r"\baward|\bapp of the (year|day|month)\b|\bbest of play\b|\beditor'?s'? choice\b", "award claim"),
    (r"\bfree\b", "'free' is promo/price text"),
    (r"\bsale\b|\bdiscount|\bdeal(s)?\b|\bcoupon|\bpromo\b", "promo text"),
    (r"\d+\s*%\s*off\b|\bhalf price\b", "discount text"),
    (r"\b(download|install|get it|play|buy|try)\s+(it\s+)?now\b", "call to action"),
    (r"\bmillion(s)?\s+(of\s+)?(users|downloads|players)\b|\b\d+\s*[mk]\+?\s+(users|downloads|installs)\b",
     "store performance claim"),
    (r"[★☆⭐]|\b[0-5][.,]\d\s*(stars?|rating)|\b\d[\d.,]*\s*[kmb]?\+?\s*(ratings|reviews)\b", "rating / review claim"),
]
WARN_WORDS = [
    (r"\btop\b", "'top' is one of Google's examples of a ranking claim"),
    (r"\bnew\b", "'new' is one of Google's examples to avoid (and it goes stale)"),
    (r"\bpopular\b|\btrending\b|\bhot\b", "can read as a performance claim"),
    (r"[$€£৳₹]\s*\d|\b\d+\s*(usd|tk|bdt|inr)\b", "looks like a price"),
    (r"[\"“].{3,}[\"”]\s*[-–—]\s*\w", "looks like a user testimonial"),
    (r"!{2,}|[A-Z]{3,}!", "shouting / extra punctuation"),
]


def item_texts(cfg: dict) -> list[tuple[str, str]]:
    texts = []
    for s in cfg.get("screenshots", []):
        slug = s.get("slug", "?")
        for key in ("headline", "sub"):
            if s.get(key):
                texts.append((f"{slug}.{key}", s[key]))
        for i, st in enumerate(s.get("stats") or []):
            texts.append((f"{slug}.stats[{i}]", f"{st.get('value', '')} {st.get('label', '')}"))
        for i, c in enumerate(s.get("callouts") or []):
            texts.append((f"{slug}.callouts[{i}]", c.get("text", "")))
    fg = cfg.get("feature_graphic", {})
    for key in ("name", "tagline"):
        if fg.get(key):
            texts.append((f"feature_graphic.{key}", fg[key]))
    return texts


def check_texts(raw_cfg: dict) -> list[tuple[str, str, str]]:
    res = []
    for loc in all_locales(raw_cfg):
        cfg = raw_cfg if loc == main_language(raw_cfg) else localize(raw_cfg, loc)
        tag = "" if loc == main_language(raw_cfg) else f"[{loc}] "
        for where, t in item_texts(cfg):
            t = plain_text(t)
            for pat, why in FAIL_WORDS:
                if re.search(pat, t, re.I):
                    res.append(("FAIL", tag + where, f"{t!r}: {why}"))
            for pat, why in WARN_WORDS:
                if re.search(pat, t, re.I if "A-Z" not in pat else 0):
                    res.append(("WARN", tag + where, f"{t!r}: {why}"))
        alt = (cfg.get("feature_graphic") or {}).get("alt_text")
        if alt and len(alt) > 140:
            res.append(("FAIL", f"{tag}feature_graphic.alt_text", f"{len(alt)} characters; max 140"))
        elif not alt:
            res.append(("WARN", f"{tag}feature_graphic.alt_text", "no alt text; Google asks for one (max 140)"))
    return res


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def dull_background(img: Image.Image) -> bool:
    """Mostly pure white, black or dark grey (Google: avoid these for the feature graphic)."""
    small = img.convert("RGB").resize((32, 16), Image.BOX)
    dull = 0
    raw = small.tobytes()
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.12 and (v < 0.30 or v > 0.94):
            dull += 1
    return dull > 0.6 * 32 * 16


def check_image(p: Path, device: str | None) -> list[tuple[str, str, str]]:
    """device None = feature graphic."""
    res = []
    name = str(p.parent.name + "/" + p.name) if p.parent.name != "final" else p.name
    if p.stat().st_size > MAX_BYTES:
        res.append(("FAIL", name, f"file is {p.stat().st_size / 1e6:.1f} MB (max 8 MB)"))
    with Image.open(p) as img:
        fmt, (w, h) = img.format, img.size
        alpha = has_alpha(img)
        dull = device is None and dull_background(img)
    if fmt not in ("PNG", "JPEG"):
        res.append(("FAIL", name, f"format {fmt}; use PNG or JPEG"))
    if alpha:
        res.append(("FAIL", name, "has transparency (alpha); save as 24-bit PNG or JPEG"))
    if device is None:
        if (w, h) != FEATURE_GRAPHIC:
            res.append(("FAIL", name, f"{w}x{h}; the feature graphic must be exactly 1024x500"))
        if dull:
            res.append(("WARN", name, "mostly white, black or dark grey; Google advises a colourful background"))
        return res
    lo, hi = DEVICES[device]["sides"]
    short, long_ = min(w, h), max(w, h)
    if short < lo or long_ > hi:
        res.append(("FAIL", name, f"{w}x{h}; each side must be {lo}-{hi} px for {device} screenshots"))
    if long_ > MAX_RATIO * short:
        res.append(("FAIL", name, f"{w}x{h}; the long side is more than 2.3x the short side"))
    if short < 1080:
        res.append(("WARN", name, f"{w}x{h}; under 1080 px, not eligible for Play's recommendation spots"))
    if abs(long_ / short - 16 / 9) > 0.02:
        res.append(("WARN", name, f"{w}x{h} is not 9:16 / 16:9, which Play's recommendation spots require"))
    return res


def images_in(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg"))


def check_folder(final: Path, main: bool) -> tuple[list, int]:
    """One language folder (final/ or final/<locale>/) with its device sub-folders."""
    res = []
    files = images_in(final)
    feature = [p for p in files if "feature" in p.stem.lower()]
    groups = {"phone": [p for p in files if p not in feature]}
    for dev in DEVICES:
        if dev != "phone" and (final / dev).is_dir():
            groups[dev] = images_in(final / dev)
    total = 0
    where = "set" if main else f"set {final.name}"
    for dev, shots in groups.items():
        for p in shots:
            res += check_image(p, dev)
        n = len(shots)
        total += n
        if n > MAX_PER_DEVICE:
            res.append(("FAIL", f"{where}/{dev}", f"{n} screenshots; Play takes up to {MAX_PER_DEVICE} per device type"))
        elif 0 < n < 4:
            res.append(("WARN", f"{where}/{dev}", f"{n} screenshots; Play's recommendation spots need at least 4"))
    for p in feature:
        res += check_image(p, None)
    if main:
        if total < 2:
            res.append(("FAIL", where, f"{total} screenshots; Play needs at least 2 to publish"))
        if not feature:
            res.append(("FAIL", where, "no feature-graphic.png; it is required to publish"))
    return res, total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("final_dir")
    ap.add_argument("--config")
    a = ap.parse_args()

    final = Path(a.final_dir)
    results, total = check_folder(final, True)
    for sub in sorted(p for p in final.iterdir() if p.is_dir() and p.name not in DEVICES):
        r, n = check_folder(sub, False)
        results += r
        total += n
    if a.config:
        cfg, _ = load_config(a.config)
        results += check_texts(cfg)

    for level, where, msg in results:
        print(f"{level:4}  {where}: {msg}")
    fails = sum(1 for r in results if r[0] == "FAIL")
    warns = sum(1 for r in results if r[0] == "WARN")
    print(f"\n{total} screenshots - {fails} fail, {warns} warn" + ("" if results else " - all good"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
