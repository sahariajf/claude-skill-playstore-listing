---
name: playstore-release-notes
description: Write Google Play "What's new" release notes for a new app version from the git history since the last release — user-facing changes only, in plain words, max 500 characters per language, in Play Console's language-tag format (<en-US> … </en-US>, <bn-BD> … </bn-BD>). Use when someone is releasing an update to the Play Store, asks for release notes, "what's new" text, or changelog text for Play Console.
---

# Google Play release notes ("What's new")

You turn the commits since the last Play release into short, friendly release notes, in the exact
format Play Console accepts. Part of the `claude-skill-playstore-listing` toolkit, next to `playstore-screenshots` and `playstore-description`.

`SKILL_DIR` = this folder. Helper: `SKILL_DIR/scripts/release_notes.py` (Python 3.9+, git on PATH).
Work folder in the app project: `store-listing/release-notes/`.

## Play format and rules

- One block per language, the language code in tags, notes inside:
  ```
  <en-US>
  • Add bazar items straight from the shared list
  • Bazar saved offline now sends itself when you're back online
  • Fixed: meal totals on the bill
  </en-US>
  <bn-BD>
  …
  </bn-BD>
  ```
- **500 characters per language** (spaces and new lines count). Over that, Play Console and the
  upload API refuse it.
- Language codes are Play's: `en-US`, `en-GB`, `bn-BD`, `hi-IN`, … — only languages the listing has.
- No promotions, prices, ranking claims or calls to action ("best", "#1", "free", "download now").
- Users read it on a phone in a few seconds: 2–5 short lines, most important first.

## Step 1 — What changed since the last release

```bash
python SKILL_DIR/scripts/release_notes.py collect            # since the last release marker / tag
python SKILL_DIR/scripts/release_notes.py collect --since v1.2.0
python SKILL_DIR/scripts/release_notes.py collect --since <commit>
```
It finds the start point in this order: `--since`, the commit saved in
`store-listing/release-notes/last-release.txt`, the newest git tag, else it asks you to pass one.
It prints the app version (pubspec.yaml / build.gradle / package.json), and every commit with its
subject, body and changed areas. If the user is unsure, ask which version or date was last released.

## Step 2 — Pick what users notice

From the commits, keep only changes a user can see or feel:
- **New** — new screens, actions, options.
- **Better** — faster, simpler, clearer, works offline, fewer steps.
- **Fixed** — bugs a user could hit (say what now works, not what was broken in code terms).

Drop: refactors, tests, CI, dependency bumps, code style, internal tools, docs, anything not in the
app build. Merge related commits into one line. Never mention commit hashes, file names or jargon
("API", "state", "cache", "migration"). Never claim something that is not in this build.

Show the user the kept/dropped list in one short table and let them change it.

## Step 3 — Write

- Start each line with "• ". Benefit first, plain words, ≤ ~90 characters a line.
- Order: biggest new thing → other new → better → fixed. 2–5 lines.
- If more changed than fits, end with "• Small fixes and improvements".
- Other languages: write them naturally (not word-for-word), same facts, their own 500 limit.
- Save as `store-listing/release-notes/<version>.txt` (exactly the Play format above).

## Step 4 — Check
```bash
python SKILL_DIR/scripts/release_notes.py check store-listing/release-notes/<version>.txt
```
Checks the tags (open/close, valid codes, no duplicates), 500 characters per language, empty blocks,
promo words. Fix every FAIL.

## Step 5 — After it is released
When the user confirms the release is live (or uploaded), save the start point for next time:
```bash
python SKILL_DIR/scripts/release_notes.py mark            # writes HEAD to last-release.txt
```
Suggest tagging the release in git too (`git tag v<version>`) — only if the user wants; never push
tags without being asked.
