"""Writes a short, ready-to-paste image-AI prompt for every screenshot and the
feature graphic, plus a folder with the files to attach. Use them in ANY image
tool (ChatGPT, Gemini, Midjourney, Ideogram, Canva AI...): open the folder,
attach the files, paste the prompt.

    python prompts.py --config store-screenshots/playstore.json
    python prompts.py --config store-screenshots/playstore.json --slug 01-split-costs --style popout

Writes:
    prompts/ALL-PROMPTS.md              every prompt in one file
    prompts/01-split-costs/prompt.md    the prompt for that screen
    prompts/01-split-costs/1-layout.png the scaffold (layout to keep)       [prompt A]
    prompts/01-split-costs/2-screen.png the real app screen (raw)
    prompts/01-split-costs/3-logo.png   the app icon / logo
    prompts/01-split-costs/4-…          any extra files from "extra"
    prompts/feature-graphic/…           same for the feature graphic

Two prompts per screen:
  A. Layout locked (best): attach the layout + screen. The result keeps the
     phone in place, so polish.py can paste the real screen back on top.
  B. Free design: attach the screen + logo. More creative, but the phone can
     move, so the real screen can't be pasted back: check the UI by eye.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import DEVICES, device_info, load_config, marked_words, out_dir, plain_text, prepare_raw, raw_of

BANNED = 'No other text, no badges, no prices, no "#1", "best", "free" or "download now".'


def _abs(root: Path, p: str | None) -> Path | None:
    if not p:
        return None
    path = Path(p.split("#", 1)[0])
    return path if path.is_absolute() else root / path


def _copy(src: Path | None, folder: Path, name: str) -> str | None:
    if not src or not src.is_file():
        return None
    dst = folder / f"{name}{src.suffix.lower()}"
    shutil.copyfile(src, dst)
    return dst.name


def _copy_screen(src: Path, folder: Path, name: str, cfg: dict, item: dict | None = None) -> str | None:
    """Copy a raw screenshot with the config's fixes (clean status bar) applied."""
    if not src.is_file():
        return None
    from PIL import Image
    dst = folder / f"{name}.png"
    prepare_raw(Image.open(src), cfg, item).save(dst)
    return dst.name


def _quote(s: str | None) -> str:
    return (s or "").replace('"', "'")


def screen_prompt(cfg: dict, item: dict, files: dict, size=(1080, 1920), work: str = "work") -> str:
    app, brand = cfg.get("app", {}), cfg.get("brand", {})
    bg = item.get("background", brand.get("background", "#111827"))
    acc = item.get("accent", brand.get("accent", "#3B82F6"))
    look = cfg.get("prompt_style", "clean, modern, soft depth and shadows, premium app-store look")
    head = plain_text(item["headline"])
    head = head.upper() if cfg.get("uppercase", True) else head
    sub = f' and the sub line "{_quote(plain_text(item["sub"]))}"' if item.get("sub") else ""
    marked = marked_words(item["headline"])
    if marked:
        sub += (" (make " + ", ".join(f'"{_quote(m)}"' for m in marked)
                + " stand out in the accent colour or an elegant italic)")
    w, h = size
    shape = f"{'portrait 9:16' if h > w else 'landscape 16:9'} ({w}x{h})"
    lang = cfg.get("language", "en-US")
    lang_note = "" if lang.startswith("en") else f"\nAll text is in {lang}; keep it exactly as written."
    idea = f"\nIdea: {item['idea']}" if item.get("idea") else ""
    extra = ""
    if files.get("extra"):
        extra = f"\nYou may use {', '.join(files['extra'])} as a small decoration."
    frame = ("a modern Android phone (thin bezel, punch-hole camera, no iPhone notch)"
             if cfg.get("frame", "android") != "none" else "a rounded card, no phone frame")
    about = f' ({app["about"]})' if app.get("about") else ""

    parts = [f"## {item['slug']}\n"]
    if files.get("layout"):
        parts.append(
            "### A. Layout locked (recommended)\n\n"
            f"Attach: `{files['layout']}`, `{files['screen']}`\n\n"
            "```text\n"
            f"Polish this Google Play screenshot, {shape}.\n"
            f'Image 1 is the exact layout: keep the headline "{_quote(head)}"{sub}, '
            "same spelling, same phone position and size.\n"
            "Image 2 is the real app screen inside the phone: do not redraw, retype or change it.\n"
            f"Only improve the background, light and headline style. Brand colours {bg} and {acc}; {look}."
            f"{idea}{extra}{lang_note}\n"
            f"Keep all text inside the middle 80% of the width. {BANNED}\n"
            "```\n\n"
            f"Save the result as `{work}/{item['slug']}/ai-raw-1.png` (then -2, -3 …).\n")
    attach_b = [f for f in (files.get("screen"), files.get("logo")) if f] + files.get("extra", [])
    parts.append(
        "### B. Free design\n\n"
        f"Attach: {', '.join(f'`{f}`' for f in attach_b)}\n\n"
        "```text\n"
        f'Design a Google Play screenshot, {shape}, for the app "{_quote(app.get("name", "App"))}"{about}.\n'
        f'Top: bold headline "{_quote(head)}"{sub.replace(" and the sub line", ", smaller sub line")}.\n'
        f"Below: image 1 shown inside {frame}, large, bleeding off the bottom edge. "
        "Keep the screen exactly as given: do not redraw, retype or change it.\n"
        f"Brand colours {bg} and {acc}; {look}."
        + (" Use the logo (image 2) only if it fits naturally." if files.get("logo") else "")
        + f"{idea}{extra}{lang_note}\n"
        f"Keep all text inside the middle 80% of the width. {BANNED}\n"
        "```\n\n"
        f"Save the result as `{work}/{item['slug']}/ai-free-1.png`. Check the app screen was not changed.\n")
    return "\n".join(parts)


def feature_prompt(cfg: dict, files: dict, work: str = "work") -> str:
    app, brand = cfg.get("app", {}), cfg.get("brand", {})
    fg = cfg.get("feature_graphic", {})
    look = cfg.get("prompt_style", "clean, modern, soft depth and shadows, premium app-store look")
    shots = files.get("screens", [])
    n = len(shots)
    attach = ([files["logo"]] if files.get("logo") else []) + shots
    logo_i = 1 if files.get("logo") else 0
    phones = (f"images {logo_i + 1}-{logo_i + n}" if n > 1 else f"image {logo_i + 1}") if n else ""
    tag = f' and the line "{_quote(plain_text(fg["tagline"]))}"' if fg.get("tagline") else ""
    about = f' ({app["about"]})' if app.get("about") else ""
    return (
        "## feature-graphic\n\n"
        f"Attach: {', '.join(f'`{f}`' for f in attach)}\n\n"
        "```text\n"
        f'Design a Google Play feature graphic, landscape, exactly 1024x500, for the app "{_quote(app.get("name", "App"))}"{about}.\n'
        + ("Left: the app icon (image 1), " if logo_i else "Left: ")
        + f'the name "{_quote(app.get("name", "App"))}" in bold{tag}.\n'
        + (f"Right: {phones} as slightly tilted floating cards (no device frames), "
           "keep the screens exactly as given.\n" if n else "")
        + f"Brand colours {brand.get('background', '#111827')} and {brand.get('accent', '#3B82F6')}; {look}. "
        "Avoid a plain white, black or grey background.\n"
        "Keep the icon, name and line well away from the edges (Play crops them)"
        + (" and keep the centre free for the video play button" if fg.get("video") else "")
        + f". {BANNED}\n"
        "```\n\n"
        f"Save the result as `{work}/feature-graphic/ai-1.png`, then pick it "
        "(feature_graphic.py --pick checks it is 1024x500).\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--slug", help="only this screenshot")
    ap.add_argument("--style", default="gradient", help="which scaffold to use as the layout (flat/gradient/popout)")
    ap.add_argument("--no-feature", action="store_true", help="skip the feature graphic prompt")
    ap.add_argument("--locale", help='a language from "locales": writes prompts/<locale>/')
    ap.add_argument("--device", default="phone", choices=sorted(DEVICES), help="writes prompts/<device>/")
    a = ap.parse_args()

    cfg, root = load_config(a.config, a.locale)
    size = device_info(cfg, a.device)["size"]
    work = out_dir(root, "work", cfg, a.device)
    work_rel = work.relative_to(root).as_posix()
    out_root = out_dir(root, "prompts", cfg, a.device)
    out_root.mkdir(parents=True, exist_ok=True)
    logo = _abs(root, cfg.get("app", {}).get("icon"))

    items = cfg.get("screenshots", [])
    if a.slug:
        items = [s for s in items if s.get("slug") == a.slug]
        if not items:
            sys.exit(f"No screenshot with slug {a.slug!r} in the config.")

    # Make sure each layout scaffold exists (built by compose.py).
    items = [s for s in items if raw_of(s, a.device)]
    missing = [s for s in items if not (work / s["slug"] / f"{s.get('prompt_layout', a.style)}.png").is_file()]
    if missing:
        from compose import run_config
        for s in missing:
            run_config(a.config, s["slug"], [s.get("prompt_layout", a.style)], a.device, a.locale)

    sections = []
    for s in items:
        folder = out_root / s["slug"]
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        style = s.get("prompt_layout", a.style)
        files = {
            "layout": _copy(work / s["slug"] / f"{style}.png", folder, "1-layout"),
            "screen": _copy_screen(root / raw_of(s, a.device), folder, "2-screen", cfg, s),
            "logo": _copy(logo, folder, "3-logo"),
            "extra": [],
        }
        for i, e in enumerate(s.get("extra", []), start=4):
            name = _copy(_abs(root, e), folder, f"{i}-{Path(e).stem}")
            if name:
                files["extra"].append(name)
        if not files["screen"]:
            print(f"[skip] {s['slug']}: raw screenshot not found ({raw_of(s, a.device)})")
            continue
        text = screen_prompt(cfg, s, files, size, work_rel)
        (folder / "prompt.md").write_text(text, encoding="utf-8")
        sections.append(text)
        print(f"{folder.relative_to(root).as_posix()}/  ({', '.join(sorted(p.name for p in folder.iterdir()))})")

    if not a.no_feature and not a.slug and a.device == "phone":
        folder = out_root / "feature-graphic"
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        fg = cfg.get("feature_graphic", {})
        shot_paths = fg.get("screenshots") or [s["raw"] for s in cfg.get("screenshots", [])[:2]]
        files = {"logo": _copy(logo, folder, "1-logo"), "screens": []}
        start = 2 if files["logo"] else 1
        for i, p in enumerate(shot_paths, start=start):
            name = _copy_screen(root / p, folder, f"{i}-screen", cfg)
            if name:
                files["screens"].append(name)
        text = feature_prompt(cfg, files, out_dir(root, "work", cfg).relative_to(root).as_posix())
        (folder / "prompt.md").write_text(text, encoding="utf-8")
        sections.append(text)
        print(f"{folder.relative_to(root).as_posix()}/  ({', '.join(sorted(p.name for p in folder.iterdir()))})")

    if not a.slug:
        intro = (
            f"# Image prompts — {cfg.get('app', {}).get('name', 'App')}\n\n"
            "Use these in any image AI. For each one: open its folder in `prompts/`, attach the files "
            "listed, paste the prompt.\n\n"
            "- **A. Layout locked** keeps the phone in place, so the real screen can be pasted back "
            "on top afterwards (`polish.py`). Best for Play's 'show the real app' rule.\n"
            "- **B. Free design** is more creative; check by eye that the app screen was not changed.\n"
            f"- Ask for {size[0]}x{size[1]}. If the tool can't, a close shape works: it is cropped to fit.\n\n")
        (out_root / "ALL-PROMPTS.md").write_text(intro + "\n---\n\n".join(sections), encoding="utf-8")
        print(f"{out_root.relative_to(root).as_posix()}/ALL-PROMPTS.md")


if __name__ == "__main__":
    main()
