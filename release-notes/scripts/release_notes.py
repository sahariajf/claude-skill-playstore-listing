"""Helper for Google Play release notes.

    python release_notes.py collect [--since REF] [--repo DIR]   commits since the last release
    python release_notes.py check FILE                         validate Play's <lang> … </lang> format
    python release_notes.py mark [--ref HEAD] [--repo DIR]       remember this release's commit

The release marker lives in <repo>/store-listing/release-notes/last-release.txt.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

MAX_CHARS = 500
MARKER = Path("store-listing") / "release-notes" / "last-release.txt"
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2}|-\d{3}|-[A-Z][a-z]{3})?$")
PROMO = [
    (r"#\s*1\b|\bbest\b|\bnumber one\b", "ranking claim"),
    (r"\bfree\b|\bsale\b|\bdiscount|\b\d+\s*%\s*off\b|\bcoupon", "price / promo text"),
    (r"\b(download|install|update|buy)\s+(it\s+)?now\b|\brate us\b", "call to action"),
]


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def app_version(repo: Path) -> str | None:
    pub = repo / "pubspec.yaml"
    if pub.is_file():
        m = re.search(r"^version:\s*([^\s#]+)", pub.read_text(encoding="utf-8"), re.M)
        if m:
            return f"{m.group(1)} (pubspec.yaml)"
    for g in ("android/app/build.gradle", "android/app/build.gradle.kts", "app/build.gradle", "app/build.gradle.kts"):
        p = repo / g
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            name = re.search(r"versionName\s*=?\s*[\"']([^\"']+)", t)
            code = re.search(r"versionCode\s*=?\s*(\d+)", t)
            if name or code:
                return f"{name.group(1) if name else '?'} ({code.group(1) if code else '?'}) ({g})"
    pkg = repo / "package.json"
    if pkg.is_file():
        m = re.search(r'"version"\s*:\s*"([^"]+)"', pkg.read_text(encoding="utf-8"))
        if m:
            return f"{m.group(1)} (package.json)"
    return None


def find_since(repo: Path, since: str | None) -> tuple[str | None, str]:
    if since:
        return since, "--since"
    marker = repo / MARKER
    if marker.is_file():
        ref = marker.read_text(encoding="utf-8").split()[0]
        return ref, str(MARKER)
    try:
        tag = git(repo, "describe", "--tags", "--abbrev=0").strip()
        if tag:
            return tag, "newest tag"
    except RuntimeError:
        pass
    return None, "nothing found"


def collect(repo: Path, since: str | None) -> None:
    ref, how = find_since(repo, since)
    ver = app_version(repo)
    print(f"App version now: {ver or 'unknown'}")
    if not ref:
        print("No start point: no --since, no last-release.txt, no git tag.\n"
              "Ask which commit/tag/date was last released, then run: collect --since <ref>")
        sys.exit(2)
    print(f"Changes since {ref} ({how}):\n")
    start, split = "\x1e", "\x1f"  # record / unit separators: never in commit text or paths
    log = git(repo, "log", f"{ref}..HEAD", "--no-merges", "--date=short",
              f"--pretty=format:{start}%h|%ad|%s%n%b{split}", "--name-only")
    commits = [c for c in log.split(start) if c.strip()]
    if not commits:
        print("(no commits — nothing new to release)")
        return
    for c in commits:
        msg, _, file_part = c.partition(split)
        lines = msg.splitlines()
        head = lines[0].split("|", 2)
        body = [ln.strip() for ln in lines[1:] if ln.strip()]
        files = [ln.strip() for ln in file_part.splitlines() if ln.strip()]
        areas = sorted({"/".join(Path(f).parts[:3]) for f in files})[:6]
        print(f"- {head[1]} {head[0]}  {head[2]}")
        for b in body[:4]:
            if not b.lower().startswith(("co-authored-by", "signed-off-by")):
                print(f"    {b[:140]}")
        if areas:
            print(f"    areas: {', '.join(areas)}")
    print(f"\n{len(commits)} commits. Keep only what users notice; write ≤{MAX_CHARS} characters per language.")


def check(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    fails = warns = 0
    blocks = re.findall(r"<([^/>\s]+)>\n?(.*?)\n?</\1>", text, re.S)
    opened = re.findall(r"<([^/>\s]+)>", text)
    closed = re.findall(r"</([^>\s]+)>", text)
    if not blocks:
        print("FAIL  no <lang> … </lang> blocks found (e.g. <en-US> … </en-US>)")
        sys.exit(1)
    if sorted(opened) != sorted(closed):
        print(f"FAIL  tags do not match: opened {opened}, closed {closed}")
        fails += 1
    leftover = re.sub(r"<([^/>\s]+)>.*?</\1>", "", text, flags=re.S).strip()
    if leftover:
        print(f"FAIL  text outside the language blocks: {leftover[:60]!r}")
        fails += 1
    seen = set()
    for lang, body in blocks:
        n = len(unicodedata.normalize("NFC", body))
        status = "ok"
        if not LANG_RE.match(lang):
            print(f"FAIL  <{lang}>: not a valid language code (e.g. en-US, bn-BD)")
            fails += 1
        if lang in seen:
            print(f"FAIL  <{lang}>: appears twice")
            fails += 1
        seen.add(lang)
        if not body.strip():
            print(f"FAIL  <{lang}>: empty")
            fails += 1
        if n > MAX_CHARS:
            status = f"too long by {n - MAX_CHARS}"
            fails += 1
        for pat, why in PROMO:
            m = re.search(pat, body, re.I)
            if m:
                print(f"WARN  <{lang}>: {m.group(0)!r} — {why}")
                warns += 1
        lines = [ln for ln in body.splitlines() if ln.strip()]
        print(f"{'FAIL' if n > MAX_CHARS else 'INFO'}  <{lang}>: {n}/{MAX_CHARS} characters, {len(lines)} lines — {status}")
    print(f"\n{len(blocks)} language(s) - {fails} fail, {warns} warn")
    sys.exit(1 if fails else 0)


def mark(repo: Path, ref: str) -> None:
    sha = git(repo, "rev-parse", ref).strip()
    p = repo / MARKER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{sha}\n", encoding="utf-8")
    print(f"Saved {sha[:10]} as the last release in {MARKER}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--since")
    c.add_argument("--repo", default=".")
    k = sub.add_parser("check")
    k.add_argument("file")
    m = sub.add_parser("mark")
    m.add_argument("--ref", default="HEAD")
    m.add_argument("--repo", default=".")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    except Exception:
        pass
    if a.cmd == "collect":
        collect(Path(a.repo), a.since)
    elif a.cmd == "check":
        check(Path(a.file))
    else:
        mark(Path(a.repo), a.ref)


if __name__ == "__main__":
    main()
