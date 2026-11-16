---
name: playstore-screenshots
description: Make Google Play Store screenshots (1080x1920) and the 1024x500 feature graphic for an Android app from its real screens. Finds the app's main benefits, suggests realistic demo data (and offers to add it to the database), captures clean screenshots with adb or takes them from a folder, builds framed images with headlines in 3 styles (or with the agent's own image AI), and checks everything against Play's size and text rules. Use when someone asks for Play Store / Google Play screenshots, store listing images, a feature graphic, or ASO images for an Android app.
---

# Google Play screenshots

You help the user make a full Google Play image set for their Android app:
**4–8 phone screenshots (1080×1920)** and the **feature graphic (1024×500)**.
Every image shows the **real app** with a short benefit headline.

Talk in plain, simple English. Ask before anything that changes data, the phone, or the user's accounts.

Sister skills in this toolkit (repo `claude-skill-playstore-listing`):
- `playstore-description` (`description/SKILL.md`): title, short and full description with ASO keywords, plus
  the checklist for the rest of the listing. Offer it after the screenshots, and reuse the same benefits.
- `playstore-release-notes` (`release-notes/SKILL.md`): the "What's new" text for each update, from the
  git history, in Play's `<en-US> … </en-US>` format.
If those skills aren't installed on their own, read their `SKILL.md` from this repo and follow it.

## Setup

- `SKILL_DIR` = the folder this `SKILL.md` is in. Scripts are in `SKILL_DIR/scripts/`.
- Python 3.9+ with Pillow (`pip install Pillow`). Use `python3` on macOS/Linux, `python` on Windows.
- adb (Android platform-tools) only if screenshots come from a phone or emulator.
- Work folder in the user's project: `store-screenshots/` (create it). Settings live in
  `store-screenshots/playstore.json`. Copy `SKILL_DIR/example.playstore.json` to start.

```
store-screenshots/
  playstore.json      settings: app, colours, fonts, headlines
  raw/                raw screenshots from the phone
  work/<slug>/        versions to choose from (+ .overlay.png layers)
  prompts/<slug>/     prompt.md + files to attach, for any image AI (ALL-PROMPTS.md = all)
  final/              upload these: 01-….png … 0N-….png, feature-graphic.png
  showcase.png        preview of the whole set
  demo-data.md        demo data that was added, and how to remove it
```

## Google Play rules (follow these, `check.py` enforces them)

- Phone screenshots: 2–8 per device type; PNG or JPEG, **no transparency**; each side 320–3840 px;
  long side at most 2× the short side. Use **1080×1920**. 4+ at ≥1080 px is what Play reportedly
  wants for its large recommendation spots, so aim for 4–8.
- Feature graphic: exactly **1024×500**, no transparency, required to publish.
- Screenshots must show the **real app experience**. No made-up UI.
- Text: short taglines only. **No** ranking/award claims ("#1", "best", "top", "app of the year"),
  **no** price or promo text ("free", "sale", "% off"), **no** calls to action ("download now").
- Text in images needs a version per listing language (English unless the user says otherwise).
- iPhone-sized images (e.g. 1290×2796) are **rejected** by Play: 2796/1290 is more than 2:1.

## Step 0 — Remember

If `store-screenshots/playstore.json` exists, read it and say what is done
(benefits, raw shots, picked versions, feature graphic). Offer: continue, or redo one part.

## Step 1 — Learn the app and write the headlines

1. Read the code: the main screens, data models, features, onboarding, README / store text.
2. Find the brand: colours (Flutter `lib/theme/*colors*.dart`, Android `res/values/colors.xml`,
   Compose `Color.kt`, CSS variables) and font (`google_fonts`, `res/font/`, CSS).
   - Colours go in `brand.background` (usually the darkest brand colour) and `brand.accent`.
   - Font: ask for the font file. If it is a Google Font, the user can download it from
     fonts.google.com (ask before downloading anything). A variable font works:
     `"fonts/IBMPlexSans[wdth,wght].ttf#Bold"`. With no font file, a system font is used.
3. Write **4–8 benefits**, best first. Each = a headline (verb + benefit, 2–5 words) and an
   optional sub line (one short sentence). Benefits, not features:
   "SPLIT BAZAR COSTS" not "EXPENSE MODULE". Specific, about the user, no banned words.
4. Show them as a numbered list and ask the user to confirm or change. Save to `playstore.json`
   (`screenshots[].slug` = `01-split-costs`, `headline`, `sub`).

## Step 2 — Demo data (so the screens look real)

Empty or messy screens make bad screenshots. For each benefit's screen:

1. Look at the models and suggest **realistic demo data**: believable names, amounts and dates
   in the current month, enough rows to fill the screen without scrolling, numbers that add up
   (totals, balances). Match the app's country/currency. No real people's data.
2. Show it as a short table per screen and ask: **"Add this to the database?"**
3. Only after a clear yes, add it the safest way available, in this order:
   1. the app's own seed/fixture script,
   2. the app's API, signed in as a **separate demo account** the user created themselves,
   3. a direct database script — only if the user asks for it.
   Always put it in a **separate demo account / group / workspace**. Never edit real users' data.
   Never type passwords for the user; they sign in or create the demo account themselves.
4. Write `store-screenshots/demo-data.md`: what was added, where, and one command or steps to
   remove it. At the end (Step 6) ask whether to remove it now or keep it for next time.

## Step 3 — Raw screenshots

Ask which way:

**A. From a phone or emulator (adb)** — you never tap or type on the phone; the user does.
```bash
python SKILL_DIR/scripts/capture.py devices
python SKILL_DIR/scripts/capture.py demo on          # 12:00, full battery, no notification icons
# user opens the screen, then:
python SKILL_DIR/scripts/capture.py shot --package <app.id> --out store-screenshots/raw/01-home.png
python SKILL_DIR/scripts/capture.py demo off         # ALWAYS at the end
```
`shot` refuses if the app is not in front (exit code 2): tell the user to open it and retry.
Debug builds: ask the user to hide the debug banner if the app shows one.

**B. From a folder** — the user puts PNGs in `store-screenshots/raw/`.

Look at every raw screenshot and rate it:
- **Great** — full of realistic data, clear, shows the benefit.
- **Usable** — fine but could be better (say what).
- **Retake** — empty list, error/toast, loading spinner, keyboard open, cut text, debug banner,
  personal data, odd status bar. Say exactly what to change.

Pair each benefit with its best Great/Usable shot (`screenshots[].raw`). Confirm with the user.

Status bar: many phones ignore parts of demo mode (low battery %, notification icons stay).
Set `"status_bar": {"clean": true}` in `playstore.json` and every script hides the icons on the
right of the status bar and keeps the clock. It only touches the phone's status bar, never the
app. Tune `height` (px) or `keep_left` (0–1, where the clean area starts; 0 hides the clock too) if
needed, for all shots or per screenshot (`screenshots[].status_bar`, e.g. `{"keep_left": 0}`).

## Step 4 — Make the screenshots

### 4a. Build 3 versions per screenshot
```bash
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json --slug 01-split-costs
```
Writes `work/<slug>/flat.png`, `gradient.png`, `popout.png`.
- `popout` lifts one part of the real screen out of the phone, bigger. Set
  `screenshots[].popout` = `[x0, y0, x1, y1]` in **raw screenshot pixels** around one card or panel
  that shows the benefit (open the raw image to find it). Without it, popout puts an accent circle
  behind the phone.
- Show the 3 versions to the user (open the images) and ask which one, or what to change
  (headline words, colours, popout box). Re-run for that slug after changes.

### 4b. AI polish (optional, use what the agent has)
Check which image tools you have:
- **An image edit/generation tool** (e.g. a Gemini "Nano Banana" MCP `edit_image`, an OpenAI image
  tool, or your own built-in image model): offer an AI-polished version. Send the chosen scaffold
  (`work/<slug>/<style>.png`) with this kind of prompt:
  > Polish this Google Play screenshot. Keep the exact layout: same headline text and spelling at
  > the top, same phone position and size. Do NOT change anything inside the phone screen. Improve
  > only the background, lighting, depth and headline styling, in the brand colours <bg> and
  > <accent>. Portrait 9:16. Keep all text inside the middle 80% of the width. No extra text,
  > no logos, no badges, no prices.

  Then always put the real screen back:
  ```bash
  python SKILL_DIR/scripts/polish.py --overlay work/<slug>/<style>.overlay.png \
      --ai work/<slug>/ai-raw-1.png --out work/<slug>/ai-1.png
  ```
  Open the result: if the AI moved the phone or misspelled the headline, drop it.
- **No image tool** (for example plain Claude Code): skip this; the 3 code-made styles are the
  choices. Do not ask the user to set anything up unless they want AI polish.

### 4c. Prompts for any image AI (always offer this)
The user may want to make the images in another tool (ChatGPT, Gemini, Midjourney, Canva…).
Write a short **idea** per screen in `playstore.json` (`screenshots[].idea`, one line: the visual
twist, e.g. "the balance card floats out of the phone, a few soft coins around it"), and optional
`extra` files to attach (e.g. a food photo). Then:
```bash
python SKILL_DIR/scripts/prompts.py --config store-screenshots/playstore.json [--style popout]
```
It writes `store-screenshots/prompts/<slug>/` with the files to attach (`1-layout.png` scaffold,
`2-screen.png` real screen, `3-logo.png`, extras) and `prompt.md`, plus `prompts/ALL-PROMPTS.md`.
Each screen gets two short prompts:
- **A. Layout locked** — attach layout + screen. The phone stays in place, so afterwards
  `polish.py` pastes the real screen back (save the result as `work/<slug>/ai-raw-1.png`).
- **B. Free design** — attach screen + logo. More creative; the phone may move, so check by eye
  that the app screen was not changed, then `--pick` the file directly.
Tell the user where the folder is and show one prompt as an example. When they bring results back,
run `polish.py` (A) or look at it carefully (B), then pick.

### 4d. Pick
```bash
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json --pick 01-split-costs gradient
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json --pick 01-split-costs work/01-split-costs/ai-1.png
```
The first picked image sets the style: use the same style for the rest of the set unless the user
wants variety. Keep slugs numbered in upload order.

## Step 5 — Feature graphic

Set `feature_graphic.tagline` (one short line, same text rules) and optionally
`feature_graphic.screenshots` (1–2 raw shots; default = the first two). `app.icon` = the 512 px icon.
```bash
python SKILL_DIR/scripts/feature_graphic.py --config store-screenshots/playstore.json
python SKILL_DIR/scripts/feature_graphic.py --config store-screenshots/playstore.json --pick duo
```
Styles: `flat`, `gradient`, `duo` (two phones). Show them, let the user pick. AI polish works the
same way as 4b if available, and `prompts.py` (4c) also writes `prompts/feature-graphic/` for any
image AI. The result must be exactly 1024×500 — `--pick` refuses other sizes.

## Step 6 — Check and finish

```bash
python SKILL_DIR/scripts/check.py store-screenshots/final --config store-screenshots/playstore.json
python SKILL_DIR/scripts/showcase.py store-screenshots/final --out store-screenshots/showcase.png
```
Fix every FAIL. Explain WARNs in one line each. Show `showcase.png`.

Finish with:
- the upload list in order (Play Console → Grow → Store presence → Main store listing →
  Phone screenshots / Feature graphic);
- a tip: try a different first screenshot with Play Console's **Store listing experiments**;
- if adb was used: confirm demo mode is off;
- ask whether to remove the demo data now (Step 2.4).

## playstore.json

```json
{
  "app": { "name": "MyApp", "package": "com.example.myapp", "icon": "../assets/icon.png",
           "about": "a money tracker for students" },
  "brand": { "background": "#0B1B3A", "accent": "#14B8A6", "text": null, "phone": "#111418" },
  "fonts": { "bold": "fonts/Inter-Bold.ttf", "regular": "fonts/Inter-Regular.ttf" },
  "frame": "android",
  "uppercase": true,
  "size": [1080, 1920],
  "status_bar": { "clean": true },
  "prompt_style": "clean, modern, soft depth and shadows, premium app-store look",
  "screenshots": [
    { "slug": "01-track-spending", "headline": "Track every taka",
      "sub": "See where the money goes, day by day",
      "raw": "raw/01-home.png", "popout": [40, 620, 1040, 1180],
      "idea": "the spending card floats out of the phone", "extra": [] }
  ],
  "feature_graphic": { "tagline": "Money made simple", "screenshots": ["raw/01-home.png"] }
}
```
`about`, `prompt_style`, `idea`, `extra` and `prompt_layout` (which style the layout prompt uses)
are only used by `prompts.py`.
Paths are relative to the folder of `playstore.json`. `text: null` = white or dark text picked
automatically. Per screenshot you can override `background` and `accent`.
`frame: "none"` = no phone, just the rounded screenshot.
