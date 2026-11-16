"""Draws a plain, brand-free Android phone around a screenshot.

Flat bezel, rounded corners, a punch-hole camera and two side buttons.
No logos, no iPhone notch.

    python android_frame.py --screenshot raw/home.png --width 760 --out phone.png
"""
from __future__ import annotations

import argparse

from PIL import Image, ImageDraw

from common import circle_mask, hex_rgb, mix, rounded, rounded_mask


def render_phone(shot: Image.Image, screen_w: int, body: str = "#111418",
                 camera: bool = True):
    """Returns (phone RGBA, screen box (x, y, w, h) inside the phone image)."""
    shot = shot.convert("RGBA")
    scale = screen_w / shot.width
    screen_h = round(shot.height * scale)
    bezel = max(6, round(screen_w * 0.026))
    btn = max(3, round(screen_w * 0.007))      # how far buttons stick out
    body_w, body_h = screen_w + 2 * bezel, screen_h + 2 * bezel
    r_body = round(screen_w * 0.10)
    r_screen = max(4, r_body - bezel)

    W, H = body_w + 2 * btn, body_h
    phone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body_rgb = hex_rgb(body)
    edge_rgb = mix(body_rgb, (255, 255, 255), 0.22)

    # Side buttons (right side): power, then volume.
    d = ImageDraw.Draw(phone)
    bx0, bx1 = btn + body_w - btn, W - 1
    for top, length in ((0.20, 0.07), (0.30, 0.13)):
        y0 = round(H * top)
        d.rounded_rectangle((bx0, y0, bx1, y0 + round(H * length)), radius=btn, fill=edge_rgb)

    # Body with a thin lighter edge.
    edge = Image.new("RGBA", (body_w, body_h), edge_rgb + (255,))
    edge.putalpha(rounded_mask((body_w, body_h), r_body))
    phone.alpha_composite(edge, (btn, 0))
    ring = max(2, round(screen_w * 0.004))
    inner = Image.new("RGBA", (body_w - 2 * ring, body_h - 2 * ring), body_rgb + (255,))
    inner.putalpha(rounded_mask(inner.size, r_body - ring))
    phone.alpha_composite(inner, (btn + ring, ring))

    # Screen.
    screen = rounded(shot.resize((screen_w, screen_h), Image.LANCZOS), r_screen)
    sx, sy = btn + bezel, bezel
    phone.alpha_composite(screen, (sx, sy))

    # Punch-hole camera, centred near the top of the screen.
    if camera:
        cd = max(8, round(screen_w * 0.032))
        ring_d = cd + max(2, round(cd * 0.25))
        outer = Image.new("RGBA", (ring_d, ring_d), (30, 34, 40, 255))
        outer.putalpha(circle_mask(ring_d))
        lens = Image.new("RGBA", (cd, cd), (6, 7, 9, 255))
        lens.putalpha(circle_mask(cd))
        cy = sy + round(screen_w * 0.028)
        cx = sx + screen_w // 2
        phone.alpha_composite(outer, (cx - ring_d // 2, cy - ring_d // 2 + cd // 2))
        phone.alpha_composite(lens, (cx - cd // 2, cy))

    return phone, (sx, sy, screen_w, screen_h)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screenshot", required=True)
    ap.add_argument("--width", type=int, default=760, help="screen width in px")
    ap.add_argument("--body", default="#111418", help="phone body colour")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    phone, _ = render_phone(Image.open(a.screenshot), a.width, a.body, not a.no_camera)
    phone.save(a.out)  # keeps transparency on purpose: this is a layer, not an upload
    print(f"saved {a.out} ({phone.width}x{phone.height})")


if __name__ == "__main__":
    main()
