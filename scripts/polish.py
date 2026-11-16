"""Puts the REAL app screen back on top of an AI-polished image.

Image models like to "improve" the app UI (wrong numbers, made-up buttons).
Google Play needs screenshots that show the real app, so after any AI step we
scale the AI image to the exact Play size and lay the phone (and pop-out) from
the scaffold's overlay on top of it again.

    python polish.py --overlay work/01-split-costs/gradient.overlay.png \\
        --ai work/01-split-costs/ai-raw-1.png --out work/01-split-costs/ai-1.png

Use --no-paste-back only if the AI output kept the phone pixel-exact anyway.
"""
from __future__ import annotations

import argparse

from PIL import Image

from common import cover, save_flat


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overlay", required=True, help="<style>.overlay.png from compose.py")
    ap.add_argument("--ai", required=True, help="image returned by the AI tool")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-paste-back", action="store_true")
    a = ap.parse_args()

    overlay = Image.open(a.overlay).convert("RGBA")
    ai = Image.open(a.ai).convert("RGBA")
    if ai.size != overlay.size:
        ratio_ai = ai.width / ai.height
        ratio_ov = overlay.width / overlay.height
        if abs(ratio_ai - ratio_ov) > 0.02:
            print(f"[note] AI image is {ai.width}x{ai.height}; cropping the sides/top to "
                  f"{overlay.width}x{overlay.height}. Check that the headline was not cut.")
        ai = cover(ai, overlay.size)
    if not a.no_paste_back:
        ai.alpha_composite(overlay)
    save_flat(ai, a.out)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
