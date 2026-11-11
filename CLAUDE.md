# Project context: AI-assisted short-video channels

Production pipeline for vertical short videos generated with AI. Videos are in English, for an American audience. Scripts, narration, image prompts and post text are in English.

## The two series

| | Ifscape (What If) | The Millbrook Outbreak (zombie series; skill `outbreak`) |
| --- | --- | --- |
| Promise | A "What if..." curiosity answered start to finish | Continuous survival story, part by part |
| Format | One closed video per topic | Numbered parts of a season |
| Duration | 61 to 70 s | 60 to 75 s |
| Voice | No narration (on-screen text only); the narrator Chris, second person, is kept only as a comparison version | Chris (v4), third person; karaoke captions |
| Camera | Observer POV, eye height, low-poly 3D (slow orbit only in space) | 2D "Live Floor Plan" + wide/close/duo scenes (`tools/flat2d`) |
| Ending | "What should I imagine next?" | Card and line "Continue..." |
| Pipeline | Supported | Supported (`py -m ifscape flat2d`; rules and continuity in `.claude/skills/outbreak/`) |

Same 9:16 file (1080x1920, bt709) for YouTube Shorts, TikTok and Instagram Reels, one account per series on each platform, topics never mixed.

## Ifscape: closed decisions

- Name **Ifscape**, handle **@ifscape_lab** (`brand.HANDLE_TEXT`). Differentiator: checked science, time jumps, topics requested in the comments.
- **Structure of a video:** hook 0 to 2 s (question in `on_screen` + strongest image) -> the moment (2 to 20 s, NOW stamp) -> time jumps (1 day, 1 year, centuries; only deadlines with a source) -> one real science fact in the middle -> ending: twist + "What should I imagine next?".
- **Script: read `docs/script-rules.md` in full when writing or reviewing.** Summary: 12-year-old friend test; sentences of ~12 words linked by and/so/but/then; fact tied to a stage object; dry tone; anti-slop; real fact only at the end, on the `final_fact` card; **duration 61 to 70 s** (~130 to 150 words on v4, with 2 voice-free windows of 2 to 4 s); voice above effects (8 LU, only with narration); metric units; numbers (digits from 10 up, spelled out from 1 to 9).
- **Viral study:** lessons from 15 viral videos and the rules derived from them (sentence names what changes on screen, witness task, signature number, damage panel, `final_fact`) are in `docs/viral-study.md` and in the "viral study lessons" block of `docs/script-rules.md`.
- **Follower credit only in the post DESCRIPTION** ("Idea by @user on <platform>"), never in the video.
- **Do not change the visual identity** ("Instrument": Barlow, amber `#F5A524` over Vacuum `#0B0F17`, live panel, safe zones) without being asked. Full text in `docs/visual-identity.md` (values in `ifscape/brand.py`).
- Topic queue and follower requests: `research/topic-bank.md` (local, optional). Video history, costs and prices: `research/video-history.md` (local, optional). State of the video in production: `build/<slug>/progress.md`.

## Lean mode (default for new videos)

Data-driven video: the `stage` field in each scene assembles everything from ready-made assets in `assets/` (no `tools/blender/<slug>.py`). Builder in `tools/stage/` (README there). 5 to 6 scenes, one session per video, one continuous story (one place, one witness, hypotheses as conflict) instead of 12 loose facts. **Default: format B, no narration (`"format": "text"`, sentences of 6 to 10 words on screen, no voice).** ElevenLabs only generates sound effects and ambiences when the library lacks them. A script is born as text; the voice version only on request.

**Flow:**
0. Premise test (`director` Mode 0, title only -> `build/<slug>/premise.md`).
1. Thesis in 5 lines + through-line (`build/<slug>/thesis.md`).
2. `fact-check` researches by **consequence chain**, with **3 to 6 fronts in parallel derived from the TOPIC** (not a fixed mold; include one on myths and, for a reused video, one on what the set already shows; step 3 of the `new-video` skill) and 1 consolidation (`chain.md`, links C1..Cn); <= 6 to 12 facts in the script. A data point only enters with **literal excerpt + opened URL** ([R] = summary only, NO SOURCE). Before opening a source, search `docs/verified-sources.md` (and add the new ones). Candidates may come from **Gemini Deep Research through Chrome** (`docs/deep-research-procedure.md`; hints only, `fact-check` opens every URL; ask the owner before sending the prompt; measure cost and false-candidate rate on the first video). `facts.md` carries Consequences and Survival with a source deadline, a measured analog or the status "UNTESTED" (never "humans survive" by assumption); that status stays in the entry, and on screen the strongest sourced link and "may/could/would likely" apply, never the crutch "nobody tested it". `premise.md` carries the premise's **central question** and **register**. **Tone regulator:** moderate sensationalism in tone, image and "may/could" sentences; forbidden: a number or deadline without a source stated as fact, and a normal-world image in a calamity (`docs/script-rules.md`).
2b. **Beat map** (skill `beat-map`, no agent): `beats.md` with 8 to 12 beats (question -> fact -> visible consequence -> link), the panel's live quantity and the setup and payoff. Rules for "fact told" in `docs/script-rules.md` (doubt: 1 per scene and 2 per video; 1 subject per scene; removal test).
3. Script with `stage` (written beat by beat), with the 10 lenses -> `py -m ifscape lint` + `script-review` + `fact-check` (check) in parallel, 1 pass, stop with no CRITICAL or HIGH. **Shortcut: skill `new-video` (full order and gates).**
4. **The owner approves the set's STILLS sheet + the panel phrase** before the heavy render (the script passes gate G3 with no stop for the owner): the set is judged in image, not in text. The set comes from a **believable floor plan or a ready-made set (CC0)**, with surroundings, layers and people in action (criteria in G4); never props scattered over the `meadow`.
5. Stills 1x -> **stills quality review** (`art-director` Mode 1 on the contact sheet; I fix what is cheap) -> full render -> `qa` gate + `anim_audit.py` and `jitter.py --step` **always** (cheap, no agent; common false positive: "x ground" on terrain; `animation-qa` only if they flag something real) -> gates and delivery. (Voice only in the narrator format.) Movement: the step is calibrated by the planted foot, `span` pieces do not restart and the camera follows the witness; skating or a "rowing" mouse is a defect.

**Autonomous mode:** I review myself and deliver only the final product. The owner is called at 3 points: the **entry briefing** (short chat questions with a marked recommendation; `docs/briefing-template.md` -> `build/<slug>/briefing.md`; includes "voice or text" for every video), the **set stills sheet + the panel phrase** (before the heavy render) and the **delivery**. In between run the **gates G1 to G8** (`docs/review-gates.md`, up to 2 rounds per gate; the residue goes in the delivery sheet). Delivery is `py tools/qa/delivery.py <slug>` -> `build/<slug>/delivery.md` + MP4, cover, "PASTE INTO POST" block and a 6-to-10-line summary. Every new failure the owner catches becomes a new gate or criterion.

Active agents (`.claude/agents/`): `fact-check`, `director` (Mode 0 only), `script-review` (with the "fact told" table), `art-director` (Mode 1 on the stills before the full render), `animation-qa` (only if `anim_audit.py`/`jitter.py` flag something real), `blender-specialist` (when a model is missing or when the set cannot come out of a believable floor plan with the builder alone; **may download ENTIRE ready-made SETS, not only assets**, see "Sets and assets"), `sound-designer` (**ALWAYS on a video without narration**, after the stills and `blender/timeline.json` and before the final render that goes to the owner: `qa` only measures volume and let loops and poor sound through; on videos with voice, only if `qa` flags it). No new agent stage without the owner's order. Every failure the owner catches becomes a line in `.claude/agents/lessons.md` (failure, who should have caught it, rule, bad -> good) and the rule goes into the responsible agent.

Older videos (with `tools/blender/<slug>.py`) follow the old process; **to rework one into text**: replace the `Frames` block of the voice word script (`kit.W`) with seconds per scene, write the `"format": "text"` script with the same scene ids, generate `sfx`/`ambience` by scene fraction and run `blender` + `render`; the old `voice.json` leaves the folder. **The script shows the world without X and the effect on humans and planet (main rule).** **Look at the final video before delivering:** extract frames (opening, event, each card, last 4 s) and check caption, panel, cuts and card; the `qa` gate once passed with a cut-off card. **Always close:** every text video ends with an end card and the closing sound (`sfx.py` does it on its own).

**Freezing what is approved:** after each approval, a new lesson or rule applies to the NEXT video. The current one reopens only for a CRITICAL (false fact, platform rule) or if the owner asks after seeing the cost in one line.

## Token economy

- One video per session; after publishing, `/clear`.
- Always a NEW Blender agent per round (it reads `build/<slug>/blender/NOTES.md`); do not resume with SendMessage.
- One file per type that gets overwritten (`review.md`, `factcheck.md`), never `review-N.md`.
- Browser research: Claude in Chrome.
- Video history goes to `research/video-history.md`, not to this file.

## Platform rules

- **YouTube, inauthentic content:** no monetization for generic, repetitive or templated content, nor disturbing images just to hold attention. Escalating penalty: warning, 90 days, removal. Using AI to visualize your own stories is allowed.
- **AI label on** for every video on all three platforms.
- **Forbidden:** real people's faces, brands, characters from films and series; simulating a real newscast, official alerts or real cities in panic.
- **Goals:** YPP 1,000 subscribers + 4,000 h (or 10M Shorts views in 90 days; later changes to be confirmed). TikTok Creator Rewards: 10 thousand followers, 100 thousand views in 30 days, videos > 1 min.

## Budget

Keep costs low. Blender (free) instead of AI video clips. ElevenLabs narration cached by text (it neither regenerates nor spends if the line does not change). Publishing is manual, by design (human review separates the channel from "mass content").

## Architecture

Python 3.10+, FFmpeg, Pillow; ElevenLabs via `urllib`. Do not add dependencies unnecessarily. `ifscape/` modules: table in `README.md`.

```
scripts/<slug>.json -> voice -> build/<slug>/voice/*, voice.json
                    -> blender -> clips/<slug>/*  (data-driven stage, or tools/blender/<slug>.py in older videos)
                    -> render -> out/<slug>.mp4 + out/<slug>.post.txt  (ends by running the qa gate)
```

Decisions that matter:
- Overlays as PNG (Pillow), not ASS captions.
- 2 s pause before "What should I imagine next?" (`voice.load_manifest`); the music finishes its fade-out there. The question can be re-recorded alone (`voice/<id>_closing.mp3`+`.json`, `voice.with_closing_take`).
- A scene without a clip becomes a provisional card with the prompt.
- Blender render color: Standard, not AgX. Time jumps without flickering sky (light changes only slowly).
- **Sets and assets:** `blender-specialist` may use **entire ready-made sets**, not only loose assets, when cheaper or better than building from scratch. Free-license sources: CC0 first (Kenney, Quaternius, Poly Pizza CC0, Poly Haven, OpenGameArt, itch.io CC0, Sketchfab CC0); CC-BY only with credit in the post description; nothing paid, no license text or editorial-only use. State the size before downloading. Record source, URL, license and date in `assets/LICENSES.md`; show a still before the full render; adapt to the palette and safe zones. Cost per frame: warn if it exceeds ~3 s.
- **Panel:** the big number must be understood in 1 s with no explanation (simple ratio, distance, count; never an index derived from own calculation). Limits: value <= 14 characters, label <= 26, 2 `panel_rows` lines with the title on screen, integer-only counter (thousands separator works). A scene with `on_screen` shows only the title (sentences in their own scene; title in 2 lines of ~18 characters).
- **Sound without narration:** `sound-designer` always enters; per-scene ambience that changes with the story, own sound for every visible action, no audible loop, `boom`+drone at the end, peak <= -1 dBTP (`sfx_lufs` in the script if it overshoots). `sfx.py` spaces the counter ticks that change per frame.
- After every final render of an older video: `tools/qa/flicker.py`, `anim_audit.py`, `jitter.py --step`; fix CRITICAL and HIGH. In lean mode, `anim_audit.py` and `jitter.py --step` always run (step 5); `flicker.py` only if `qa` or the frames flag it.
- **Git:** `.env` never goes up (check before pushing). Commit at the end of each video. Local cleanup only on request (frames in `build/<slug>/blender/frames` and `preview` are the buffer for `--frames`; `out/`, `clips/`, `.blend`, voice, sound and the `.md` files stay).

### Commands

```bash
py -m ifscape voice   scripts/<slug>.json [--force] [--allow-long]
py -m ifscape blender scripts/<slug>.json [--stills 30,900 | --frames 1-1640]
py -m ifscape render  scripts/<slug>.json [--music track.mp3] [--music-start 12]
py -m ifscape all     scripts/<slug>.json --dummy     # test without the API
py -m ifscape qa | cover | status | metrics | prompts | upscale scripts/<slug>.json
py tools/qa/contact_sheet.py scripts/<slug>.json [--list]
```

Script fields: `README.md`; current examples: `scripts/stage-demo.json` (stage) and `scripts/moon-earth-gravity.json`.

## Environment

Windows: use `py` (`python` falls to the Microsoft Store). ElevenLabs voice Chris (`iP95p4xoKVk53GoZ742B`): ~3 words/s on v2, ~2.6 on v4. Duration = words / pace + 2 s final pause + ~0.45 s per scene. `--dummy` (2.4 words/s) overestimates. **Patch scripts in Windows Bash:** never a heredoc with `\n`, nested quotes or escapes (it corrupted scripts); write the script with `Write`/`Edit` and run it. The script JSON is edited by one hand at a time: after `sound-designer` records `sfx`, `sfx_auto` and `ambience`, the generator must not overwrite (merge).
