"""Checks Google Play listing text against Play's limits and metadata policy,
and shows where each keyword lands.

    python listing_check.py store-listing/en-US.json [more.json ...]

JSON fields: title, short_description, full_description, and optional
keywords {primary: [...], secondary: [...]}, brand_words [...], competitors [...].
FAIL = Play will reject it or it breaks the metadata policy. WARN = allowed but
risky or weak. Exit code 1 if anything fails. No extra packages needed.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

LIMITS = {"title": 30, "short_description": 80, "full_description": 4000}

# (pattern, why, level per field: title, short, full)
RULES = [
    (r"#\s*1\b|\bno\.?\s*1\b|\bnumber\s+one\b", "ranking claim (#1)", ("FAIL", "FAIL", "FAIL")),
    (r"\bbest\b", "'best' is a ranking/performance claim", ("FAIL", "FAIL", "FAIL")),
    (r"\bapp of the (year|day|month)\b|\bbest of play\b|\beditor'?s'? choice\b|\baward[- ]winning\b",
     "award / store-performance claim", ("FAIL", "FAIL", "FAIL")),
    (r"\bpopular\b|\btrending\b|\btop[- ]rated\b|\bmillions? of (users|downloads)\b|\b\d+\s*[mk]\+?\s+(users|downloads)\b",
     "store-performance claim", ("FAIL", "FAIL", "FAIL")),
    (r"\bfree\b", "'free' is promo/price text", ("FAIL", "FAIL", "WARN")),
    (r"\bno ads\b|\bad[- ]free\b", "'no ads' promotes a deal", ("FAIL", "WARN", "WARN")),
    (r"\bsale\b|\bdiscount|\bcoupon|\bpromo(tion)?\b|\b\d+\s*%\s*off\b|\blimited time\b|\bcheapest\b",
     "price / promo text", ("FAIL", "FAIL", "FAIL")),
    (r"\b(download|install|get it|buy)\s+(it\s+)?now\b", "call to action", ("FAIL", "FAIL", "WARN")),
    (r"\btop\b", "'top' can read as a ranking claim", ("WARN", "WARN", "WARN")),
    (r"\bnew\b", "'new' goes stale and can read as a Play programme badge", ("WARN", "WARN", None)),
    (r"[$€£৳₹]\s*\d|\b\d+\s*(usd|tk|bdt|inr)\b", "looks like a price", ("WARN", "WARN", "WARN")),
]

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U00002B00-\U00002BFF️]")
REPEAT_SPECIAL_RE = re.compile(r"([!?*★☆✓✔•~=_\-+|])\1{1,}")


def char_len(s: str) -> int:
    # Play counts characters (Unicode code points), not bytes.
    return len(unicodedata.normalize("NFC", s))


def count_phrase(text: str, phrase: str) -> int:
    """Whole-phrase matches, letting the last word be plural (hostel/hostels)."""
    pat = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?:s|es)?(?!\w)"
    return len(re.findall(pat, text.lower()))


def check(path: Path) -> list[tuple[str, str, str]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    res: list[tuple[str, str, str]] = []
    fields = {k: (d.get(k) or "") for k in LIMITS}
    brand = {w.lower() for w in d.get("brand_words", [])}

    for k, limit in LIMITS.items():
        n = char_len(fields[k])
        if not fields[k].strip():
            res.append(("FAIL", k, "empty"))
        elif n > limit:
            res.append(("FAIL", k, f"{n}/{limit} characters — too long"))
        else:
            res.append(("INFO", k, f"{n}/{limit} characters"))

    for i, k in enumerate(("title", "short_description", "full_description")):
        text = fields[k]
        for pat, why, levels in RULES:
            level = levels[i]
            if level and re.search(pat, text, re.I):
                hit = re.search(pat, text, re.I).group(0)
                res.append((level, k, f"{hit!r}: {why}"))
        emojis = EMOJI_RE.findall(text)
        if emojis:
            lvl = "FAIL" if k == "title" else ("WARN" if k == "short_description" or len(emojis) > 6 else None)
            if lvl:
                res.append((lvl, k, f"{len(emojis)} emoji — " + ("not allowed in the title" if k == "title" else "keep emoji rare")))
        if REPEAT_SPECIAL_RE.search(text):
            res.append(("FAIL" if k == "title" else "WARN", k,
                        f"repeated special characters {REPEAT_SPECIAL_RE.search(text).group(0)!r}"))
        caps = [w for w in re.findall(r"\b[A-Z]{4,}\b", text) if w.lower() not in brand]
        if caps:
            res.append(("FAIL" if k == "title" else "WARN", k, f"ALL CAPS words {caps[:4]} (only a brand may be all caps)"))
        for comp in d.get("competitors", []):
            if comp and count_phrase(text, comp):
                res.append(("FAIL", k, f"mentions another app ({comp!r}) — comparisons are not allowed"))

    full = fields["full_description"]
    short = fields["short_description"].strip()
    if short and short.lower() in full.lower():
        res.append(("FAIL", "full_description", "repeats the short description word for word"))
    for line in full.splitlines():
        words = line.split()
        if line.count(",") >= 5 and len(words) <= line.count(",") * 3:
            res.append(("FAIL", "full_description", f"looks like a keyword list: {line[:60]!r}…"))
            break
    if re.search(r"[\"“][^\"”]{3,120}[\"”]\s*[-–—]\s*\w+", full) and not re.search(r"\b(review|source|according to)\b", full, re.I):
        res.append(("WARN", "full_description", "looks like a quote/testimonial — needs a clear, attributed source"))
    if re.search(r"★{3,}|⭐{2,}", full):
        res.append(("FAIL", "full_description", "star ratings in text read as store-performance claims"))

    # Keyword map: where each phrase lands.
    kw = d.get("keywords") or {}
    first = full[:250]
    for kind in ("primary", "secondary"):
        for p in kw.get(kind, []):
            t, s, f = (count_phrase(fields["title"], p), count_phrase(short, p), count_phrase(full, p))
            line = f"{p!r}: title {t} · short {s} · full {f}"
            if kind == "primary":
                if not (t or s):
                    res.append(("WARN", "keywords", line + " — primary is in neither title nor short description"))
                elif not count_phrase(first, p):
                    res.append(("WARN", "keywords", line + " — primary not in the first 250 characters of the full text"))
                else:
                    res.append(("INFO", "keywords", line))
            else:
                if f == 0 and not (t or s):
                    res.append(("WARN", "keywords", line + " — not used anywhere"))
                elif f > 4:
                    res.append(("WARN", "keywords", line + " — used often; may read as keyword stuffing"))
                else:
                    res.append(("INFO", "keywords", line))
    # Any word used very often (stuffing), ignoring short/common words and the brand.
    stop = set("the and for you your with that this from are can all its our has have was not but any one who what when how into out each per get".split())
    words = [w for w in re.findall(r"[a-z][a-z'-]{3,}", full.lower()) if w not in stop and w not in brand]
    if words:
        top = max(set(words), key=words.count)
        share = words.count(top) / len(words)
        if words.count(top) >= 12 and share > 0.04:
            res.append(("WARN", "full_description", f"'{top}' is {words.count(top)}× ({share:.0%} of words) — may read as stuffing"))
    return res


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    fails = 0
    for p in sys.argv[1:]:
        print(f"== {p}")
        for level, where, msg in check(Path(p)):
            print(f"{level:4}  {where}: {msg}")
            fails += level == "FAIL"
        print()
    print("all good" if not fails else f"{fails} fail")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
