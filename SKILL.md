---
name: playstore-screenshots
description: Make Google Play Store screenshots (phone 1080x1920, plus 7"/10" tablet and Chromebook sets) and the 1024x500 feature graphic for an Android app from its real screens, in every listing language. Finds the app's main benefits, suggests realistic demo data (and offers to add it to the database), captures clean screenshots with adb or takes them from a folder, builds framed images with two-colour headlines, varied layouts (tilted 3D phone, stats cards, callouts, headline at the bottom), mesh/gradient/light backgrounds, grain and panoramas (or with the agent's own image AI), and checks everything against Play's current size, text and safe-area rules. Use when someone asks for Play Store / Google Play screenshots, store listing images, a feature graphic, tablet screenshots, localized screenshots, or ASO images for an Android app.
---

# Google Play screenshots

You help the user make a full Google Play image set for their Android app:
**4–8 phone screenshots (1080×1920)**, the **feature graphic (1024×500)**, and, when the app
supports them, **tablet / Chromebook** sets and **one set per listing language**.
Every image shows the **real app** with a short benefit headline.

Talk in plain, simple English. Ask before anything that changes data, the phone, the user's
accounts, or downloads anything.

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
  playstore.json      settings: app, colours, fonts, headlines, layouts, languages
  fonts/              font files (fonts.py puts downloads here)
  raw/                raw screenshots from the phone (and tablet)
  work/<slug>/        versions to choose from (+ .overlay.png layers)
  work/tablet10/…     same for a device; work/bn-BD/… for a language
  prompts/<slug>/     prompt.md + files to attach, for any image AI (ALL-PROMPTS.md = all)
  final/              upload these: 01-….png … 0N-….png, feature-graphic.png
  final/tablet10/     tablet set;  final/bn-BD/ (+ final/bn-BD/tablet10/) per language
  showcase.png        preview of the whole set
  demo-data.md        demo data that was added, and how to remove it
```

## Google Play rules (follow these, `check.py` enforces them)

Source: Play Console Help, "Add preview assets to showcase your app" (answer 9866151).

- Phone screenshots: 2–8; PNG or JPEG up to 8 MB, **no transparency**; each side 320–3840 px;
  the long side at most **2.3×** the short side. Use **1080×1920**: Play's recommendation spots
  need **at least 4** screenshots at **9:16 portrait (min 1080×1920) or 16:9 landscape
  (min 1920×1080)**.
- Tablets (7" and 10") and Chromebook: up to 8 each, at least 4; sides 1,080–7,680 px; 9:16 or
  16:9. They must show the real large-screen layout. Google advises **no extra text** on
  large-screen shots (it can be cut off), so by default they get no headline
  (`devices.<name>.text: true` turns it on).
- Feature graphic: exactly **1024×500**, JPEG or 24-bit PNG, required to publish. Keep the icon,
  name and slogan out of the edge "cutoff zones"; keep the centre free if there is a promo video
  (a play button covers it); avoid device frames and plain white/black/grey backgrounds; give it
  **alt text** (max 140 characters).
- Screenshots must show the **real app experience**. No made-up UI.
- Text: short taglines only, **under 20% of the image**. **No** performance, ranking, award or
  testimonial content ("#1", "best", "top", "new", "app of the year", star ratings, review
  quotes, download counts), **no** price or promo text ("free", "sale", "% off"), **no** calls to
  action ("download now", "try now").
- Text in images needs a version per listing language (Google: "provide separate screenshots …
  for each language that you support").
- iPhone App Store sizes are the wrong shape for Play's recommendation spots: make 9:16 sets.

## Step 0 — Remember

If `store-screenshots/playstore.json` exists, read it and say what is done
(benefits, raw shots, picked versions, feature graphic, devices, languages). Offer: continue, or
redo one part.

## Step 1 — Learn the app and write the headlines

1. Read the code: the main screens, data models, features, onboarding, README / store text.
   Check whether the app supports tablets / large screens (layouts for `sw600dp`, Compose window
   size classes, `resizeableActivity`) and which languages it ships (`res/values-bn/`, `l10n/`,
   `.arb` files). Mention both in your plan.
2. Find the brand: colours (Flutter `lib/theme/*colors*.dart`, Android `res/values/colors.xml`,
   Compose `Color.kt`, CSS variables) and font (`google_fonts`, `res/font/`, CSS).
   - Colours go in `brand.background` (usually the darkest brand colour) and `brand.accent`.
     `brand.highlight` (optional) colours the marked headline words; leave it `null` until the
     colour step (4a). Text colours are picked automatically against the real background and
     made readable.
3. Write **4–8 benefits**, best first. Each = a headline (verb + benefit, 2–5 words) and an
   optional sub line (one short sentence). Benefits, not features:
   "SPLIT BAZAR COSTS" not "EXPENSE MODULE". Specific, about the user, no banned words.
   **Mark the 1–3 words that carry the benefit**, so the headline reads in two colours:
   - `*word*` → highlight colour: `"Split *bazar costs*"`
   - `_word_` → accent font (an italic serif from `fonts.accent`): `"Every meal, _counted_"`
   - `\n` forces a line break: `"Log bazar\n*in seconds*"`. `\*` / `\_` print a real `*` / `_`.
4. Plan a **mix of layouts** so the set doesn't look like one slide five times (see 4c). Default
   plan for 5 screens: `top`, `tilted`, `bubble` or `stats`, `bottom`, `top`.
5. Show them as a numbered list (headline, sub, layout) and ask the user to confirm or change.
   Save to `playstore.json` (`screenshots[].slug` = `01-split-costs`, `headline`, `sub`, `layout`).

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
   remove it. At the end (Step 8) ask whether to remove it now or keep it for next time.
   For other languages, suggest demo data in that language too (names, items) if the app shows it.

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
For a tablet set, use a tablet emulator (e.g. "Pixel Tablet") and save to `raw/tablet/…`.
For another language, the user switches the phone's language (or the app's) and you save to
`raw/bn-BD/…`.

**B. From a folder** — the user puts PNGs in `store-screenshots/raw/`.

Look at every raw screenshot and rate it:
- **Great** — full of realistic data, clear, shows the benefit.
- **Usable** — fine but could be better (say what).
- **Retake** — empty list, error/toast, loading spinner, keyboard open, cut text, debug banner,
  personal data, odd status bar. Say exactly what to change.

Pair each benefit with its best Great/Usable shot (`screenshots[].raw`; tablets
`raw_tablet7` / `raw_tablet10`, Chromebook `raw_chromebook`). Confirm with the user.

Status bar: many phones ignore parts of demo mode (low battery %, notification icons stay).
Set `"status_bar": {"clean": true}` in `playstore.json` and every script hides the icons on the
right of the status bar and keeps the clock. It only touches the phone's status bar, never the
app. Tune `height` (px) or `keep_left` (0–1, where the clean area starts; 0 hides the clock too) if
needed, for all shots or per screenshot (`screenshots[].status_bar`, e.g. `{"keep_left": 0}`).

## Step 4 — Make the screenshots

### 4a. Highlight colour
The marked words need a colour that stands out from the background **behind the headline**.
Rules (the same idea as most good app palettes: a brand colour plus an accent in a
contrasting hue):
- **Different hue, not just lighter.** The highlight should sit about 50° or more away on the
  colour wheel from the background behind the text. Brand teal on a teal/navy gradient reads
  as "the same colour, lighter" and looks dull.
- **Readable:** at least 4.5:1 contrast with that background.
- On **cool dark** backgrounds (navy, blue, teal, green, purple), warm highlights pop: gold,
  amber, peach. On **warm dark** ones: sky, mint, lilac. On **light** backgrounds the brand
  accent, darkened, usually works.
- **No pure red** (it reads as an error or money owed), no more than two text colours in a
  headline, and **one highlight colour for the whole set**.
- Chips keep the brand accent; only the marked words and stats values use the highlight.

With `brand.highlight: null` the scripts apply these rules automatically. To let the user
choose, render the options on their real screenshot:
```bash
python SKILL_DIR/scripts/colors.py --config store-screenshots/playstore.json --style mesh
```
It writes `work/colors-<style>.png` (the headline in each option, with contrast and hue gap)
and marks the automatic pick. Show it, ask which one, and set `brand.highlight` to that hex.
Re-run with the style the user picked; light and dark styles need different highlights.

**Optional: palette ideas from ui-ux-pro-max.** If the `ui-ux-pro-max` skill is installed, search
its palettes for the app's product type and compare their accents on the real screenshot:
```bash
python <ui-ux-pro-max>/scripts/search.py "<product type, e.g. expense splitter students>" --domain color -n 3
python SKILL_DIR/scripts/colors.py --config … --try "#F59E0B" --try "#8B5CF6"
```
Use its Accent / Secondary colours as ideas only: the brand colours from the app's code win, and
every option still has to pass the rules above.

### 4b. Fonts (optional, recommended)
If the app has no usable font file, offer a curated pair (ask before downloading):
```bash
python SKILL_DIR/scripts/fonts.py list
python SKILL_DIR/scripts/fonts.py get clean --config store-screenshots/playstore.json
```
It downloads static `.ttf` files from Google Fonts (SIL Open Font License) into
`store-screenshots/fonts/` and sets `fonts.bold`, `fonts.regular` and `fonts.accent` (an italic
serif for `_marked_` words). Pick the pair that fits the app's mood. One family only:
`fonts.py family "Hind Siliguri" --weight Bold --role bold --config …`.

### 4c. Build the versions
```bash
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json --slug 01-split-costs
python SKILL_DIR/scripts/compose.py --config … --slug 01-split-costs --layouts top,tilted,bottom
```
Writes `work/<slug>/<style>.png` for each **style** (default `gradient`, `mesh`, `light`,
`popout`; `--styles` picks others, `flat` too). `--layouts` also renders other layouts as
`<style>-<layout>.png`, to compare.

Styles (the look):
- `gradient` brand colour fading to the accent; `mesh` deep base with large blended colour
  patches; `light` pale brand tint with dark text; `flat` one solid colour.
- `popout` lifts one part of the real screen out of the phone, bigger. Set
  `screenshots[].popout` = `[x0, y0, x1, y1]` in **raw screenshot pixels** around one card or panel
  that shows the benefit (open the raw image to find it). Without it, popout puts an accent circle
  behind the phone.
- `"texture": {"grain": 0.3, "pattern": "dots" | "grid"}` adds film grain and/or a subtle pattern
  to every style.
- `"panorama": true` draws one background across the whole set, so the screenshots join up in
  the Play carousel.

Layouts (per screenshot, `screenshots[].layout`; mix them):
- `top` (default): headline on top, phone below, running off the bottom.
- `bottom`: phone on top, running off the top edge, headline at the bottom.
- `tilted`: the phone turned in 3D. Tune with `"tilt": {"turn": 22, "lean": 6, "rot": -4}`
  (degrees; `tilt` works on any layout).
- `stats`: headline, then 2–3 fact cards, then a smaller phone.
  `"stats": [{"value": "3 taps", "label": "to log a bazar"}, …]`. Facts must be **true about the
  app** (counts of features, speed, offline…). Never ratings, downloads, users or awards.
- `bubble`: phone moved aside for `callouts`.
- `callouts` (any layout, up to 3): `[{"text": "Rice 10 kg bought"}, {"kind": "chip", "text": "Works offline"}]`.
  A bubble is a speech bubble; a chip is an accent pill. Optional `side` (`left`/`right`),
  `y` (0–1 of the height), `rot`. Use real words from the app (an item, a status), not reviews.

Show the versions to the user (open the images) and ask which one, or what to change (headline
words, marked words, colours, layout, popout box). Re-run for that slug after changes. If a run
prints `added text covers ~N%`, shorten the text: Google asks for taglines under 20%.

### 4d. AI polish (optional, use what the agent has)
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
  The overlay also holds the stats cards and callouts, so their spelling stays exact.
  Open the result: if the AI moved the phone or misspelled the headline, drop it.
- **No image tool** (for example plain Claude Code): skip this; the code-made styles are the
  choices. Do not ask the user to set anything up unless they want AI polish.

### 4e. Prompts for any image AI (always offer this)
The user may want to make the images in another tool (ChatGPT, Gemini, Midjourney, Canva…).
Write a short **idea** per screen in `playstore.json` (`screenshots[].idea`, one line: the visual
twist, e.g. "the balance card floats out of the phone, a few soft coins around it"), and optional
`extra` files to attach (e.g. a food photo). Then:
```bash
python SKILL_DIR/scripts/prompts.py --config store-screenshots/playstore.json [--style mesh]
python SKILL_DIR/scripts/prompts.py --config … --locale bn-BD     # prompts/bn-BD/
python SKILL_DIR/scripts/prompts.py --config … --device tablet10  # prompts/tablet10/
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

### 4f. Pick
```bash
python SKILL_DIR/scripts/compose.py --config store-screenshots/playstore.json --pick 01-split-costs mesh
python SKILL_DIR/scripts/compose.py --config … --pick 01-split-costs gradient-tilted
python SKILL_DIR/scripts/compose.py --config … --pick 01-split-costs work/01-split-costs/ai-1.png
```
The first picked image sets the style: use the same style for the rest of the set (needed for a
panorama) unless the user wants variety. Keep slugs numbered in upload order.

## Step 5 — Tablets and Chromebook (if the app supports large screens)

Ask whether the app supports tablets / Chromebook. If yes, Play shows a separate tablet set to
large-screen users, and its recommendation spots want at least 4.
1. Raw shots must come from a tablet (or tablet emulator) showing the **real tablet layout**.
   Set `screenshots[].raw_tablet10` (and/or `raw_tablet7`, `raw_chromebook`).
2. Sizes: tablet7 1080×1920, tablet10 1440×2560, Chromebook 2560×1440. For landscape tablet
   shots: `"devices": {"tablet10": {"size": [2560, 1440]}}`. Large-screen shots get no headline
   by default (Google's advice); `"text": true` adds it.
```bash
python SKILL_DIR/scripts/compose.py --config … --device tablet10
python SKILL_DIR/scripts/compose.py --config … --device tablet10 --pick 01-split-costs mesh
```
Results go to `work/tablet10/` and `final/tablet10/`. The frame is a plain Android tablet
(Chromebook: no frame).

## Step 6 — Other languages

For each listing language besides the main one (`"language": "en-US"`), add a block under
`"locales"`. Translate the **meaning**, not word by word, keep it short, and mark the benefit
words again. Only what differs is needed:
```json
"locales": {
  "bn-BD": {
    "fonts": {"bold": "fonts/HindSiliguri-Bold.ttf", "regular": "fonts/HindSiliguri-Regular.ttf"},
    "uppercase": false,
    "screenshots": {
      "01-split-costs": {"headline": "বাজারের *খরচ ভাগ করুন*", "sub": "…", "raw": "raw/bn-BD/01-home.png"}
    },
    "feature_graphic": {"tagline": "…", "alt_text": "…"}
  }
}
```
- Use the app's own screens in that language when the app is translated (`raw` per slug).
- Pick a font that has the script: `fonts.py get bangla --config … --locale bn-BD` (or
  `devanagari`; any Google Font with `fonts.py family`).
- **Complex scripts** (Bangla, Hindi, Arabic, Thai…) need Pillow with libraqm to join letters
  correctly. The scripts print a WARN if it is missing. Then either the user installs
  libraqm + FriBiDi, or make that language's images with the image-AI prompts (4e,
  `--locale`) and check the spelling with the user.
```bash
python SKILL_DIR/scripts/compose.py --config … --locale bn-BD
python SKILL_DIR/scripts/compose.py --config … --locale bn-BD --pick 01-split-costs mesh
python SKILL_DIR/scripts/feature_graphic.py --config … --locale bn-BD
```
Results go to `work/bn-BD/` and `final/bn-BD/`.

## Step 7 — Feature graphic

Set `feature_graphic.tagline` (one short line, same text rules, markup works), `alt_text` (what the
image shows, max 140 characters), `video: true` if the listing has a promo video, and optionally
`feature_graphic.screenshots` (1–2 raw shots; default = the first two). `app.icon` = the 512 px icon.
```bash
python SKILL_DIR/scripts/feature_graphic.py --config store-screenshots/playstore.json
python SKILL_DIR/scripts/feature_graphic.py --config store-screenshots/playstore.json --pick cards
```
Styles: `gradient`, `duo` (two phones), `mesh`, `cards` (screens as tilted cards, **no device
frame**, which follows Google's advice), plus `flat` and `light` via `--styles`. Each also writes
`<style>.guide.png` with the edge cutoff zones (red) and, with `video`, the play-button area.
Google shows those zones only as a picture, so the margins are an approximation: if a WARN says
text is in a zone, fix it. Show the versions and the guide, let the user pick. AI polish works the
same way as 4d, and `prompts.py` (4e) also writes `prompts/feature-graphic/`. The result must be
exactly 1024×500 — `--pick` refuses other sizes.

## Step 8 — Check and finish

```bash
python SKILL_DIR/scripts/check.py store-screenshots/final --config store-screenshots/playstore.json
python SKILL_DIR/scripts/showcase.py store-screenshots/final --out store-screenshots/showcase.png
```
`check.py` covers every set in `final/` (phone, devices, languages) and the texts of every
language. Fix every FAIL. Explain WARNs in one line each. Show `showcase.png` (run it per folder
for tablet or language sets).

Finish with:
- the upload list in order (Play Console → Grow → Store presence → Main store listing →
  Phone screenshots / 7-inch / 10-inch tablet / Chromebook / Feature graphic; other languages via
  "Manage translations");
- the feature graphic alt text to paste;
- a tip: try a different first screenshot with Play Console's **Store listing experiments**;
- if adb was used: confirm demo mode is off;
- ask whether to remove the demo data now (Step 2.4).

## playstore.json

```json
{
  "app": { "name": "MyApp", "package": "com.example.myapp", "icon": "../assets/icon.png",
           "about": "a money tracker for students" },
  "language": "en-US",
  "brand": { "background": "#0B1B3A", "accent": "#14B8A6", "highlight": null, "text": null, "phone": "#111418" },
  "fonts": { "bold": "fonts/Inter-ExtraBold.ttf", "regular": "fonts/Inter-Regular.ttf",
             "accent": "fonts/InstrumentSerif-Italic.ttf" },
  "frame": "android",
  "uppercase": false,
  "size": [1080, 1920],
  "texture": { "grain": 0.3, "pattern": null },
  "panorama": false,
  "status_bar": { "clean": true },
  "prompt_style": "clean, modern, soft depth and shadows, premium app-store look",
  "devices": { "tablet10": { "size": [1440, 2560], "text": false } },
  "screenshots": [
    { "slug": "01-track-spending", "headline": "Track every *taka*",
      "sub": "See where the money goes, day by day", "layout": "top",
      "raw": "raw/01-home.png", "raw_tablet10": "raw/tablet/01-home.png",
      "popout": [40, 620, 1040, 1180],
      "idea": "the spending card floats out of the phone", "extra": [] },
    { "slug": "02-offline", "headline": "Works _without internet_", "layout": "stats",
      "raw": "raw/02-offline.png",
      "stats": [{ "value": "0 MB", "label": "needed to save" }, { "value": "Auto", "label": "sync when online" }] },
    { "slug": "03-shared", "headline": "One *shared* list", "layout": "bubble", "raw": "raw/03-list.png",
      "callouts": [{ "text": "Rice 10 kg bought" }, { "kind": "chip", "text": "Live for everyone" }] }
  ],
  "feature_graphic": { "tagline": "Money made *simple*", "alt_text": "MyApp icon beside its spending screen",
                       "video": false, "screenshots": ["raw/01-home.png"] },
  "locales": { "bn-BD": { "uppercase": false, "screenshots": { "01-track-spending": { "headline": "…" } } } }
}
```
`about`, `prompt_style`, `idea`, `extra` and `prompt_layout` (which style the layout prompt uses)
are only used by `prompts.py`.
Paths are relative to the folder of `playstore.json`. `text: null` = white or dark text picked
automatically against the real background. Per screenshot you can override `background`,
`accent`, `tilt` and `shift` (move the phone sideways, share of the width).
`frame: "none"` = no phone, just the rounded screenshot.
