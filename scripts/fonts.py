"""Curated Google Fonts pairs for the screenshots, and a downloader.

Each pair has a bold headline font, a regular font for sub lines, and an
accent font for _marked_ headline words (usually an italic serif). All are
open-licence (SIL OFL) fonts from Google Fonts.

    python fonts.py list
    python fonts.py get clean --config store-screenshots/playstore.json
    python fonts.py get bangla --config store-screenshots/playstore.json --locale bn-BD
    python fonts.py family "Hind Siliguri" --weight Bold --config ... --role bold

`get` and `family` download static .ttf files into <config folder>/fonts/ and write the paths into playstore.json ("fonts", or the locale's
"fonts"). Downloading needs the user's OK first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from common import load_config, save_config

# name: (bold family, weight), (regular family, weight), (accent family, style or None), note
PAIRS = {
    "clean":     (("Inter", "ExtraBold"), ("Inter", "Regular"), ("Instrument Serif", "Italic"),
                  "neutral and modern; fits most apps"),
    "tight":     (("Inter Tight", "ExtraBold"), ("Inter", "Regular"), ("Instrument Serif", "Italic"),
                  "condensed, confident headlines (media, AI, finance)"),
    "friendly":  (("Plus Jakarta Sans", "ExtraBold"), ("Plus Jakarta Sans", "Medium"), ("Fraunces", "Italic"),
                  "warm and rounded (lifestyle, health, family)"),
    "geometric": (("Outfit", "Bold"), ("Outfit", "Regular"), ("Fraunces", "Italic"),
                  "clean geometric shapes (productivity, tools)"),
    "tech":      (("Space Grotesk", "Bold"), ("Inter", "Regular"), ("Instrument Serif", "Italic"),
                  "technical, a little quirky (dev tools, AI, finance)"),
    "editorial": (("DM Serif Display", "Regular"), ("Inter", "Regular"), ("DM Serif Display", "Italic"),
                  "serif headlines (reading, food, travel)"),
    "bold":      (("Archivo Black", "Regular"), ("Inter", "Regular"), ("Instrument Serif", "Italic"),
                  "heavy and loud (sports, games, shopping)"),
    "playful":   (("Fredoka", "SemiBold"), ("Nunito", "Regular"), ("Caveat", "Bold"),
                  "soft and fun (kids, education, social)"),
    "bangla":    (("Hind Siliguri", "Bold"), ("Hind Siliguri", "Regular"), None,
                  "Bangla + Latin (needs Pillow with libraqm for correct Bangla shaping)"),
    "devanagari": (("Hind", "Bold"), ("Hind", "Regular"), None,
                   "Hindi/Marathi + Latin (needs Pillow with libraqm)"),
}

CSS = "https://fonts.googleapis.com/css2?family={family}:ital,wght@{ital},{weight}"
UA = {"User-Agent": "playstore-listing-skill"}  # a non-browser agent gets plain .ttf files
WEIGHTS = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "medium": 500,
           "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}


def _get(url: str) -> bytes:
    for attempt in range(2):  # one retry for a slow connection
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except TimeoutError:
            if attempt:
                raise
    raise AssertionError("unreachable")


def fetch(family: str, style: str, folder: Path) -> str:
    """Download one style ("Bold", "Regular", "Italic", "SemiBold Italic"...) from
    Google Fonts as a static .ttf. Returns the file name."""
    italic = "italic" in style.lower()
    name = re.sub(r"(?i)\s*italic", "", style).replace(" ", "").lower() or "regular"
    if name not in WEIGHTS:
        sys.exit(f"Unknown weight {style!r}; use one of {', '.join(w.title() for w in WEIGHTS)} (+ Italic).")
    url = CSS.format(family=family.replace(" ", "+"), ital=1 if italic else 0, weight=WEIGHTS[name])
    try:
        css = _get(url).decode("utf-8")
    except Exception as e:
        sys.exit(f"Google Fonts has no {family!r} {style} (or no connection): {e}")
    m = re.search(r"src:\s*url\((https://[^)]+\.ttf)\)", css)
    if not m:
        sys.exit(f"Google Fonts returned no .ttf for {family!r} {style}.")
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / f"{family.replace(' ', '')}-{style.replace(' ', '')}.ttf"
    if not dst.is_file():
        dst.write_bytes(_get(m.group(1)))
        print(f"downloaded {dst.name} ({family} {style}, SIL Open Font License)")
    return dst.name


def write_fonts(cfg_path: str, locale: str | None, fonts: dict) -> None:
    cfg, root = load_config(cfg_path)
    rel = {k: f"fonts/{v}" for k, v in fonts.items()}
    if locale:
        loc = cfg.setdefault("locales", {}).setdefault(locale, {})
        loc["fonts"] = {**(loc.get("fonts") or {}), **rel}
    else:
        cfg["fonts"] = {**(cfg.get("fonts") or {}), **rel}
    save_config(cfg, cfg_path)
    print(f"playstore.json {'locales.' + locale + '.' if locale else ''}fonts = {json.dumps(rel)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("pair", choices=sorted(PAIRS))
    g.add_argument("--config", required=True)
    g.add_argument("--locale")
    f = sub.add_parser("family")
    f.add_argument("name")
    f.add_argument("--weight", default="Bold", help='e.g. Bold, Regular, Italic, "SemiBold Italic"')
    f.add_argument("--role", default="bold", choices=("bold", "regular", "accent"))
    f.add_argument("--config", required=True)
    f.add_argument("--locale")
    a = ap.parse_args()

    if a.cmd == "list":
        for name, (b, r, acc, note) in PAIRS.items():
            accent = f" + {acc[0]} {acc[1]}" if acc else ""
            print(f"{name:11} {b[0]} {b[1]} / {r[0]} {r[1]}{accent}\n            {note}")
        return
    folder = Path(a.config).resolve().parent / "fonts"
    if a.cmd == "get":
        b, r, acc, _ = PAIRS[a.pair]
        fonts = {"bold": fetch(*b, folder), "regular": fetch(*r, folder)}
        if acc:
            fonts["accent"] = fetch(*acc, folder)
        write_fonts(a.config, a.locale, fonts)
    else:
        write_fonts(a.config, a.locale, {a.role: fetch(a.name, a.weight, folder)})


if __name__ == "__main__":
    main()
