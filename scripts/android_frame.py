"""Draws a plain, brand-free Android phone or tablet around a screenshot.

Phone: flat bezel, rounded corners, a punch-hole camera and two side buttons.
Tablet: thicker bezel, smaller corner radius, the camera in the bezel, and
buttons on the top edge. Works for portrait and landscape screenshots.
No logos, no iPhone notch.

    python android_frame.py --screenshot raw/home.png --width 760 --out phone.png
    python android_frame.py --screenshot raw/tablet.png --model tablet --width 1300 --out tablet.png
"""
from __future__ import annotations

import argparse

from PIL import Image, ImageDraw

from common import circle_mask, hex_rgb, mix, rounded, rounded_mask

MODELS = ("phone", "tablet")


def render_device(shot: Image.Image, screen_w: int, model: str = "phone", body: str = "#111418",
                  camera: bool = True):
    """Returns (device RGBA, screen box (x, y, w, h) inside the device image)."""
    shot = shot.convert("RGBA")
    scale = screen_w / shot.width
    screen_h = round(shot.height * scale)
    short = min(screen_w, screen_h)
    tablet = model == "tablet"
    bezel = max(6, round(short * (0.040 if tablet else 0.026)))
    btn = max(3, round(short * 0.007))       # how far buttons stick out
    body_w, body_h = screen_w + 2 * bezel, screen_h + 2 * bezel
    r_body = round(short * (0.055 if tablet else 0.10))
    r_screen = max(4, r_body - bezel)

    # Buttons on the right side (phone) or the top edge (tablet).
    W, H = (body_w, body_h + btn) if tablet else (body_w + btn, body_h)
    ox, oy = (0, btn) if tablet else (0, 0)
    dev = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body_rgb = hex_rgb(body)
    edge_rgb = mix(body_rgb, (255, 255, 255), 0.22)

    d = ImageDraw.Draw(dev)
    if tablet:
        for left, length in ((0.72, 0.05), (0.80, 0.09)):
            x0 = round(W * left)
            d.rounded_rectangle((x0, 0, x0 + round(W * length), 3 * btn), radius=btn, fill=edge_rgb)
    else:
        for top, length in ((0.20, 0.07), (0.30, 0.13)):
            y0 = round(H * top)
            d.rounded_rectangle((body_w - 3 * btn, y0, W - 1, y0 + round(H * length)),
                                radius=btn, fill=edge_rgb)

    # Body with a thin lighter edge.
    edge = Image.new("RGBA", (body_w, body_h), edge_rgb + (255,))
    edge.putalpha(rounded_mask((body_w, body_h), r_body))
    dev.alpha_composite(edge, (ox, oy))
    ring = max(2, round(short * 0.004))
    inner = Image.new("RGBA", (body_w - 2 * ring, body_h - 2 * ring), body_rgb + (255,))
    inner.putalpha(rounded_mask(inner.size, r_body - ring))
    dev.alpha_composite(inner, (ox + ring, oy + ring))

    # Screen.
    screen = rounded(shot.resize((screen_w, screen_h), Image.LANCZOS), r_screen)
    sx, sy = ox + bezel, oy + bezel
    dev.alpha_composite(screen, (sx, sy))

    if camera:
        if tablet:  # a small lens in the middle of the top bezel
            cd = max(6, round(bezel * 0.32))
            lens = Image.new("RGBA", (cd, cd), (40, 44, 52, 255))
            lens.putalpha(circle_mask(cd))
            dev.alpha_composite(lens, (sx + screen_w // 2 - cd // 2, oy + (bezel - cd) // 2))
        else:       # punch-hole, centred near the top of the screen
            cd = max(8, round(screen_w * 0.032))
            ring_d = cd + max(2, round(cd * 0.25))
            outer = Image.new("RGBA", (ring_d, ring_d), (30, 34, 40, 255))
            outer.putalpha(circle_mask(ring_d))
            lens = Image.new("RGBA", (cd, cd), (6, 7, 9, 255))
            lens.putalpha(circle_mask(cd))
            cy = sy + round(screen_w * 0.028)
            cx = sx + screen_w // 2
            dev.alpha_composite(outer, (cx - ring_d // 2, cy - ring_d // 2 + cd // 2))
            dev.alpha_composite(lens, (cx - cd // 2, cy))

    return dev, (sx, sy, screen_w, screen_h)


def render_frameless(shot: Image.Image, screen_w: int):
    """Just the rounded screenshot (frame "none")."""
    scale = screen_w / shot.width
    h = round(shot.height * scale)
    img = rounded(shot.convert("RGBA").resize((screen_w, h), Image.LANCZOS), round(min(screen_w, h) * 0.05))
    return img, (0, 0, screen_w, h)


def render(shot: Image.Image, screen_w: int, frame: str, body: str = "#111418"):
    """frame: "phone", "tablet" or "none"."""
    if frame == "none":
        return render_frameless(shot, screen_w)
    return render_device(shot, screen_w, frame, body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screenshot", required=True)
    ap.add_argument("--width", type=int, default=760, help="screen width in px")
    ap.add_argument("--model", default="phone", choices=MODELS)
    ap.add_argument("--body", default="#111418", help="device body colour")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dev, _ = render_device(Image.open(a.screenshot), a.width, a.model, a.body, not a.no_camera)
    dev.save(a.out)  # keeps transparency on purpose: this is a layer, not an upload
    print(f"saved {a.out} ({dev.width}x{dev.height})")


if __name__ == "__main__":
    main()
