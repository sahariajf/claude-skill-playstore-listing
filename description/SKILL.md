---
name: playstore-description
description: Write a search-optimised (ASO) Google Play store listing for an Android app — app title (30), short description (80) and full description (4,000) — from the app's real features, with keyword research, a keyword map, Play policy checks, and a checklist of everything else the listing needs (category, tags, contact, privacy policy, Data safety, video, translations). Use when someone asks for Play Store description, store listing text, ASO keywords, app title ideas, or "what do I need for my Play listing".
---

# Google Play listing text (ASO)

You write the words of a Google Play listing so that the right people **find** the app in Play
search and **install** it when they read it. Everything must be true about the real app.
Plain, simple English (or the listing language). Part of the `claude-skill-playstore-listing` toolkit, next to `playstore-screenshots` and `playstore-release-notes`.

`SKILL_DIR` = this folder. The checker is `SKILL_DIR/scripts/listing_check.py` (Python 3.9+, no extra packages).
Work folder in the app project: `store-listing/` — one JSON per language (`en-US.json`, `bn-BD.json`)
plus a readable `listing.md`. If `store-screenshots/playstore.json` exists, reuse its app name,
benefits and headlines so the words match the images.

## Play rules (the checker enforces these)

| Field | Limit | Rules |
|---|---|---|
| App name (title) | **30** chars | Unique, no emoji, no ALL CAPS (unless the brand is), no repeated special characters, no "free", "no ads", "best", "#1", "sale", ranking or price words; avoid "new" and "top". |
| Short description | **80** chars | One clear sentence about what the app does. No promo ("free", "discount") or ranking ("#1", "best") words. |
| Full description | **4,000** chars | Everyday language, not a keyword list. No repeated/unrelated keywords, no comma-separated keyword blocks, don't repeat the short description, no comparing with other apps, no unattributed testimonials ("Great app!" – user), no "best"/"#1"/"app of the year"/"popular", no prices or discounts, no emoji walls. Must describe what the app really does. |

Sources: Google Play Metadata policy (support.google.com/googleplay/android-developer/answer/9898842)
and Store listing best practices (…/answer/13393723).

## Step 1 — Learn the app

Read the code, README, onboarding, and `store-screenshots/playstore.json` if present. List:
- what it does in one sentence; who it is for (country, audience, their own words);
- 5–10 real features, and the **one thing it does that others don't** (the "information gain":
  the line competitors cannot write). If the code says a feature is not built or hidden, never claim it.

## Step 2 — Keywords (adapted from SEO practice for Play search)

1. **Seeds**: 10–20 phrases a user would type in Play search — the problem ("split meal cost"),
   the activity ("bazar hisab"), the category ("mess manager"), local words and spellings
   (e.g. Banglish, Hinglish) the audience really uses. Ask the user for words their users say.
2. **Expand** each seed with modifiers (app, calculator, tracker, manager, hisab, for students/hostel),
   Play search autocomplete (if the agent can browse play.google.com, read the suggestions and the
   top 5 competitor listings), and the app's own feature names. Aim for 30–50 candidates.
3. **Filter**: drop competitor brand names (never use them), words the app can't back up, and banned words.
4. **Group** near-duplicates (same intent → one group). Pick:
   - **1 primary** phrase (highest intent, describes the app) — goes in the **title** and
     **short description**, and in the **first sentence** of the full description;
   - **5–8 secondary** phrases — each used **naturally 1–3 times** in the full description,
     ideally in a feature heading or the first line of a section;
   - long-tail phrases for feature lines.
   No fixed keyword density. Never write a keyword list. One idea per sentence.
5. Show the keyword map as a table (phrase · where it goes · why) and let the user change it.

## Step 3 — Write

- **Title (≤30)**: `Brand: primary phrase` or `Brand - primary phrase`, e.g. "MessBro: Mess Meal & Bazar".
  Give 3 options, best first. Brand first unless the brand is unknown and the phrase is the search term.
- **Short description (≤80)**: benefit + primary phrase + who it is for. 3 options.
- **Full description (≤4,000, aim 1,500–2,500)**:
  1. Opening (2–3 sentences, first 250 chars matter most — shown before "More"): what it is, for whom,
     the main benefit, primary phrase once.
  2. 4–7 short feature sections, each with a plain heading line (no emoji needed; a simple "•" list is fine),
     benefit first, the feature after; secondary phrases fit here.
  3. The "only here" section — the information-gain line.
  4. Trust: privacy (what data, why), who made it, how to get help (support email/site).
  5. A plain closing line (no "download now!").
- Write it as `store-listing/en-US.json`:
```json
{
  "language": "en-US",
  "title": "…", "short_description": "…", "full_description": "…",
  "keywords": { "primary": ["…"], "secondary": ["…"] },
  "brand_words": ["MessBro"], "competitors": ["Other App Name"]
}
```
  and a readable `store-listing/listing.md` (title options, short options, full text, keyword map, checklist).

## Step 4 — Check
```bash
python SKILL_DIR/scripts/listing_check.py store-listing/en-US.json
```
Fix every FAIL. Explain each WARN in one line or fix it. The report also shows where each keyword
appears (title / short / full count) — the primary must be in all three, secondaries 1–3× in full.

## Step 5 — Everything else the listing needs (always give this checklist)

Fill in what the code/README tells you, mark the rest "to do":
- **Category** (Play Console → Store settings): best-fit category + why. Up to **5 tags**.
- **Contact details**: support email (required), website, phone (optional).
- **Privacy policy URL** (required for most apps; must be a live public page).
- **Data safety form**: list what the app collects (from the code: auth/email, analytics, crash
  reporting, location…), whether it is shared, encrypted in transit, can be deleted (account delete URL).
- **Content rating** questionnaire, **target audience**, **ads** declaration, **app access**
  (test login for reviewers if the app needs sign-in — the user creates it; never invent credentials).
- **Graphics**: 512×512 icon, 1024×500 feature graphic, 4–8 phone screenshots (`playstore-screenshots`),
  optional YouTube promo video.
- **Translations**: the main audience's language (e.g. `bn-BD`) — offer to write it with its own
  local keywords (not a word-for-word translation).
- **Custom store listings / Store listing experiments**: try 2 short descriptions or titles A/B.
- **How to know it works** (for each change): Play Console → Statistics → store listing visitors,
  conversion rate, and Acquisition → search terms. Re-check 2–4 weeks after a change.

## Step 6 — Hand over
Show the final title, short description and the first 250 characters of the full description, the
check result, and where the files are. Copy-paste order for Play Console:
Grow → Store presence → Main store listing → App name / Short description / Full description.
