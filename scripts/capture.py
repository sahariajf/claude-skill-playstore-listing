"""Takes clean raw screenshots from an Android phone or emulator with adb.

It never taps or types on the phone: the person opens each screen, this only
takes the picture, and only when the right app is in front.

    python capture.py devices
    python capture.py demo on            # clean status bar: 12:00, full battery/signal, no icons
    python capture.py foreground         # which app is in front
    python capture.py shot --package com.example.app --out store-screenshots/raw/home.png
    python capture.py demo off           # back to normal (always do this at the end)

Add --serial <id> when more than one device is connected. adb is found on PATH,
in $ADB, $ANDROID_HOME / $ANDROID_SDK_ROOT, or the default SDK folder.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def find_adb() -> str:
    cands = [os.environ.get("ADB"), shutil.which("adb")]
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            cands.append(str(Path(os.environ[env]) / "platform-tools" / "adb"))
    home = Path.home()
    cands += [
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
        str(home / "Library" / "Android" / "sdk" / "platform-tools" / "adb"),
        str(home / "Android" / "Sdk" / "platform-tools" / "adb"),
    ]
    for c in cands:
        if not c:
            continue
        for p in (c, c + ".exe"):
            if Path(p).is_file():
                return p
    sys.exit("adb not found. Install Android platform-tools or set ADB=/path/to/adb.")


def adb(args, serial=None, binary=False, check=True):
    cmd = [find_adb()] + (["-s", serial] if serial else []) + list(args)
    r = subprocess.run(cmd, capture_output=True)
    if check and r.returncode != 0:
        sys.exit(f"adb failed: {' '.join(args)}\n{r.stderr.decode(errors='replace')}")
    return r.stdout if binary else r.stdout.decode(errors="replace")


def foreground(serial=None) -> str | None:
    out = adb(["shell", "dumpsys", "activity", "activities"], serial)
    for key in ("topResumedActivity", "mResumedActivity", "ResumedActivity"):
        for line in out.splitlines():
            if key in line:
                m = re.search(r"\s([A-Za-z0-9_.]+)/[A-Za-z0-9_.$]+", line)
                if m:
                    return m.group(1)
    return None


def demo(on: bool, serial=None, hhmm: str = "1200") -> None:
    def bc(*extra):
        adb(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", *extra], serial, check=False)
    if on:
        adb(["shell", "settings", "put", "global", "sysui_demo_allowed", "1"], serial)
        bc("-e", "command", "enter")
        bc("-e", "command", "clock", "-e", "hhmm", hhmm)
        bc("-e", "command", "battery", "-e", "level", "100", "-e", "plugged", "false")
        bc("-e", "command", "network", "-e", "wifi", "show", "-e", "level", "4")
        bc("-e", "command", "network", "-e", "mobile", "show", "-e", "datatype", "none", "-e", "level", "4")
        bc("-e", "command", "notifications", "-e", "visible", "false")
        print("Demo mode on (clock %s:%s). Some phone brands ignore parts of it - check the first shot."
              % (hhmm[:2], hhmm[2:]))
    else:
        bc("-e", "command", "exit")
        adb(["shell", "settings", "put", "global", "sysui_demo_allowed", "0"], serial)
        print("Demo mode off.")


def shot(package: str | None, out: str, serial=None, allow_any=False) -> None:
    top = foreground(serial)
    if package and not allow_any and top != package:
        print(f"NOT TAKEN: {package} is not in front (in front: {top}). "
              f"Ask the person to open the screen in the app, then try again.")
        sys.exit(2)
    data = adb(["exec-out", "screencap", "-p"], serial, binary=True)
    if not data.startswith(PNG_SIG):
        # Very old adb on Windows turns \n into \r\n.
        data = data.replace(b"\r\n", b"\n")
    if not data.startswith(PNG_SIG):
        sys.exit("screencap did not return a PNG (is the screen on and unlocked?)")
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    try:
        from PIL import Image
        w, h = Image.open(p).size
        print(f"saved {p} ({w}x{h})")
    except Exception:
        print(f"saved {p}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices")
    sub.add_parser("foreground")
    d = sub.add_parser("demo")
    d.add_argument("state", choices=("on", "off"))
    d.add_argument("--time", default="1200", help="clock as HHMM")
    s = sub.add_parser("shot")
    s.add_argument("--package", help="only take it when this app is in front")
    s.add_argument("--out", required=True)
    s.add_argument("--allow-any", action="store_true", help="skip the app-in-front check")
    a = ap.parse_args()

    if a.cmd == "devices":
        print(adb(["devices", "-l"]).strip())
    elif a.cmd == "foreground":
        print(foreground(a.serial) or "unknown")
    elif a.cmd == "demo":
        demo(a.state == "on", a.serial, a.time)
    elif a.cmd == "shot":
        shot(a.package, a.out, a.serial, a.allow_any)


if __name__ == "__main__":
    main()
