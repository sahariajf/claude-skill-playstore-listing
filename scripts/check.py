"""Checks the final images and texts against Google Play's rules.

    python check.py store-screenshots/final --config store-screenshots/playstore.json

FAIL = Play will reject it or it breaks a listing rule. WARN = allowed, but
weaker (e.g. too small for Play's big recommendation spots). Exit code 1 if
anything fails.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

from common import FEATURE_GRAPHIC, load_config

MAX_BYTES = 8 * 1024 * 1024

# Google Play: no ranking/award/performance claims, no price or promo text,
# no calls to action in screenshots. (Store listing best practice + Metadata policy.)
FAIL_WORDS = [
    (r"#\s*1\b|\bno\.?\s*1\b|\bnumber\s+one\b", "ranking claim (#1)"),
    (r"\bbest\b", "'best' is a performance claim"),
    (r"\baward|\bapp of the (year|day|month)\b|\bbest of play\b|\beditor'?s'? choice\b", "award claim"),
    (r"\bfree\b", "'free' is promo/price text"),
    (r"\bsale\b|\bdiscount|\bdeal(s)?\b|\bcoupon|\bpromo\b", "promo text"),
    (r"\d+\s*%\s*off\b|\bhalf price\b", "discount text"),
    (r"\b(download|install|get it|play|buy)\s+(it\s+)?now\b", "call to action"),
    (r"\bmillion(s)?\s+(of\s+)?(users|downloads|players)\b|\b\d+\s*[mk]\+?\s+(users|downloads)\b", "store performance claim"),
]
WARN_WORDS = [
    (r"\btop\b", "'top' can read as a ranking claim"),
    (r"\bpopular\b|\btrending\b|\bhot\b", "can read as a performance claim"),
    (r"\bnew\b", "'new' goes stale; avoid it in screenshots"),
    (r"[$€£৳₹]\s*\d|\b\d+\s*(usd|tk|bdt|inr)\b", "looks like a price"),
    (r"!{2,}|[A-Z]{3,}!", "shouting / extra punctuation"),
]


def check_texts(cfg: dict) -> list[tuple[str, str, str]]:
    res = []
    texts = []
    for s in cfg.get("screenshots", []):
        for key in ("headline", "sub"):
            if s.get(key):
                texts.append((f"{s.get('slug', '?')}.{key}", s[key]))
    fg = cfg.get("feature_graphic", {})
    if fg.get("tagline"):
        texts.append(("feature_graphic.tagline", fg["tagline"]))
    for where, t in texts:
        for pat, why in FAIL_WORDS:
            if re.search(pat, t, re.I):
                res.append(("FAIL", where, f"{t!r}: {why}"))
        for pat, why in WARN_WORDS:
            if re.search(pat, t, re.I if "A-Z" not in pat else 0):
                res.append(("WARN", where, f"{t!r}: {why}"))
    return res


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def check_image(p: Path, feature: bool) -> list[tuple[str, str, str]]:
    res = []
    name = p.name
    if p.stat().st_size > MAX_BYTES:
        res.append(("FAIL", name, f"file is {p.stat().st_size / 1e6:.1f} MB (max 8 MB)"))
    with Image.open(p) as img:
        fmt, (w, h) = img.format, img.size
        alpha = has_alpha(img)
    if fmt not in ("PNG", "JPEG"):
        res.append(("FAIL", name, f"format {fmt}; use PNG or JPEG"))
    if alpha:
        res.append(("FAIL", name, "has transparency (alpha); save as 24-bit PNG or JPEG"))
    if feature:
        if (w, h) != FEATURE_GRAPHIC:
            res.append(("FAIL", name, f"{w}x{h}; the feature graphic must be exactly 1024x500"))
        return res
    short, long_ = min(w, h), max(w, h)
    if short < 320 or long_ > 3840:
        res.append(("FAIL", name, f"{w}x{h}; each side must be 320-3840 px"))
    if long_ > 2 * short:
        res.append(("FAIL", name, f"{w}x{h}; the long side is more than 2x the short side"))
    if short < 1080:
        res.append(("WARN", name, f"{w}x{h}; under 1080 px, too small for Play's big recommendation spots"))
    if abs(long_ / short - 16 / 9) > 0.02:
        res.append(("WARN", name, f"{w}x{h} is not 9:16 / 16:9"))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("final_dir")
    ap.add_argument("--config")
    a = ap.parse_args()

    folder = Path(a.final_dir)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    feature = [p for p in files if "feature" in p.stem.lower()]
    shots = [p for p in files if p not in feature]

    results = []
    for p in shots:
        results += check_image(p, False)
    for p in feature:
        results += check_image(p, True)
    n = len(shots)
    if n < 2 or n > 8:
        results.append(("FAIL", "set", f"{n} phone screenshots; Play takes 2-8"))
    elif n < 4:
        results.append(("WARN", "set", f"{n} phone screenshots; 4+ is what Play's big recommendation spots want"))
    if not feature:
        results.append(("FAIL", "set", "no feature-graphic.png; it is required to publish"))
    if a.config:
        cfg, _ = load_config(a.config)
        results += check_texts(cfg)

    for level, where, msg in results:
        print(f"{level:4}  {where}: {msg}")
    fails = sum(1 for r in results if r[0] == "FAIL")
    warns = sum(1 for r in results if r[0] == "WARN")
    print(f"\n{n} screenshots, {len(feature)} feature graphic - {fails} fail, {warns} warn"
          + ("" if results else " - all good"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
