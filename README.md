# Ifscape · video pipeline

Turns a JSON script into a vertical 9:16 Short ready for review, with the brand identity already applied:

- per-scene narration on ElevenLabs, with the timing of every word (optional: text-only videos need no voice);
- time stamps in an amber block;
- uppercase captions with the keyword highlighted;
- @ifscape_lab in the corner.

Clips come from Blender (3D stage built from data), the 2D flat-animation system, or AI video tools you run by hand (Seedance, Veo or Kling) from the prompt list the pipeline creates, with the exact duration of each scene.

## Requirements

- Python 3.10 or newer
- FFmpeg on the PATH (`ffmpeg -version` must answer)
- Pillow: `pip install -r requirements.txt`
- The two brand fonts, free on Google Fonts:
  - [Big Shoulders Display](https://fonts.google.com/specimen/Big+Shoulders+Display)
  - [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono)

  Download them and copy to `fonts/` the variable file (`BigShouldersDisplay[wght].ttf`, `JetBrainsMono[wght].ttf`) or the static ExtraBold. Without them, the pipeline uses a system font and warns; fine for tests only.
- An ElevenLabs account (Starter plan or above, for commercial use), only for narration and generated sound effects
- Optional, for the `upscale` command: [Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0) (`realesrgan-ncnn-vulkan-20220424-windows.zip`), extracted to `tools/realesrgan/`. Runs on AMD, NVIDIA and Intel cards.
- Optional, for the Blender path: Blender 5.2 (Eevee), free

## Setup

```bash
cp .env.example .env
# edit .env with your key and the narrator's voice id
```

The voice id appears on the ElevenLabs voice page (Voice ID). `.env` is never committed.

## Workflow of one video

```bash
# 1. Narration of each scene (only regenerates scenes whose text changed: saves credits)
python -m ifscape voice scripts/sun-went-out.json

# 2. Prompt list with the clip length of each scene
python -m ifscape prompts scripts/sun-went-out.json
#    -> build/sun-went-out/prompts.txt
#    Generate each clip (Seedance, Veo or Kling) and save it as clips/sun-went-out/01.mp4, 02.mp4...

# 3. (Optional) Upscale 720p clips with AI: sharper image in the final 1080p
python -m ifscape upscale scripts/sun-went-out.json
#    -> clips/sun-went-out/hd/01.mp4...; the render uses this version automatically

# 4. Assembly
python -m ifscape render scripts/sun-went-out.json --music track.mp3 [--music-start 12]
#    -> out/sun-went-out.mp4 and out/sun-went-out.post.txt (title, description, sources, checklist)
#    At the end it runs the final gate on its own (step 5).

# 5. Final gate: checks out/<slug>.mp4 with measurements (exits with code 1 on an ERROR)
python -m ifscape qa scripts/sun-went-out.json
#    -> build/sun-went-out/gates/final.json
```

Other paths: `py -m ifscape blender scripts/<slug>.json [--stills 30,900 | --frames 1-1640]` (Blender clips) and `py -m ifscape flat2d scripts/<slug>.json` (2D clips). Also available: `cover`, `status`, `metrics`, `lint`, and `py tools/qa/contact_sheet.py scripts/<slug>.json [--list]`.

You can run `render` before all clips exist. A scene without a clip becomes a provisional card with its prompt, so you review the editing rhythm before spending credits.

To test everything without spending API credits: `python -m ifscape all scripts/sun-went-out.json --dummy` (silent narration, estimated timing).

## Script format

| Field | Where | What it is |
| --- | --- | --- |
| `slug` | script | Name of files and folders (`sun-went-out`) |
| `title`, `description`, `hashtags` | script | Go to the `.post.txt` |
| `sources` | script | List of `{claim, url}`; the post marks `[SOURCE PENDING]` if the url is missing |
| `style` | script or scene | Suffix appended to every prompt (POV, camera, "no text"); the scene can override it |
| `id` | scene | `01`, `02`... is also the clip name |
| `prompt` | scene | Description of the first-frame image (Nano Banana), in English |
| `motion` | scene | Movement only, to animate the image into video; without it, `prompt` becomes a direct text-to-video |
| `motion_style` | script or scene | Suffix of `motion` (style + camera); the scene can override it |
| `tool` | scene | `seedance` (default) or `veo`: where to generate the video; `prompts.txt` shows each one's setup |
| `narration` | scene | The narrator's line; the caption comes from it |
| `captions` | scene | The narration split by hand into chunks of 2 to 4 words, in order; together they repeat the narration. Without it, the split is automatic |
| `on_screen` | scene | Fixed text on screen (e.g. the opening question), without narration |
| `stamp` | scene | Live panel number: `"8 MIN"` swaps (scrolling from the previous one), `"NOW"` becomes a clock, `null` hides, absent keeps the previous |
| `panel_label` | root or scene | Small label above the number (`"TIME WITHOUT HUMANS"`); in a scene, it holds from there on |
| `panel_sub` | scene | Data line under the number, only in this scene (`"SUBWAY PUMPS: OFF"`) |
| `panel_sub_at` | scene | At what point of the scene (0 to 1) the data line enters; default 0 (from the start) |
| `panel_style` | root | `"side"` (default, middle of the screen) or `"hud"` (high, compact, with data lines) |
| `panel_rows` | scene | Only with `"hud"`: up to 3 lines `[label, value]` or `[label, value, when 0 to 1]` under the stopwatch (2 in the scene with the opening question) |
| `counter` | scene | Counter in place of the number: `label`, `start`, `end`, `rate` (per second), `change_at` and `change_over` (s). E.g. a population that plunges with the vanishing. With `unit: "clock"`, `start`/`end` are in milliseconds and the number becomes a real-time stopwatch ("00:01.28"), in a thin mono font (JetBrains Mono Light). |
| `now_clock` | root | Default `true` (running time is always a stopwatch): the "NOW" stamp is a counting-up stopwatch ("00:02.10"), in the `counter` format with `unit: "clock"`. `now_clock_from`: second of the NOW stretch at which it reads zero |
| `closing` | root | Final phrase that gets the 2 s pause before it (e.g. "Comment what I should imagine next."). Empty = "What should I imagine next?" |
| `voice_model` | root | ElevenLabs model for this script only (e.g. `eleven_v4`). Empty = `ELEVENLABS_MODEL` from `.env` |
| `voice_direction` | root | Voice direction tag in square brackets for all narrated scenes (v3/v4 only), e.g. `[calm, dry documentary narration]`; it is not spoken and does not enter the alignment, but it is billed |
| `voice_stability` | root | ElevenLabs stability for this script only (default 0.5) |
| `direction` | scene | Direction tag for this scene only; overrides `voice_direction`; `""` turns the tag off in the scene |
| `credit` | root | Voice format: the @ of the follower who requested the topic. "Idea by @..." enters in the pause before the final question and stays until the end, above the caption |
| `counter.final` | scene | Word in place of the number when the change ends (`"HERE"`, `"GONE"`), in uppercase; the small stopwatch line disappears. Test of the damage-measuring panel |
| `panel_clock` | root | `true`: in scenes with a `counter` (not `unit: "clock"`), a small linear stopwatch (`00:12.40`, thin mono) appears under the damage number and continues between scenes. `panel_clock_from`: video second at which it reads zero (default 0) |
| `final_fact` | root | Voice format: 1-line end card (up to 16 words, small small-caps) with the real fact written out; enters at the start of the pause before the final question and stays until the end, in the gap between the HUD and the side panel (y 760). It is not a source and does not replace the line |
| `end_card` | root | Text format: fact line of the end card, which replaces the phrase "What should I imagine next?"; `true` = card with only the question |
| `highlight` | scene | Words painted amber in the caption |
| `sfx` | root | Spot sounds: `{"sound": "boom", "scene": "01", "at": 0.35, "seconds": 5}`. `at` marks the event; with `peak` in the library, the sound's hit lands on it. Sounds in `sfx/library.json` |
| `ambience` | root | Layers with start and end: `{"sound": "wind", "from": ["04", 0.55], "to": ["08", 0.05], "gain": 0.6, "fade": 1.5}` |
| `sfx_traffic` | root | Car hits at the instants of the `tools/blender/traffic.py` simulation: `{"scene": "01", "at": 0.35, "until": "04"}` (vanishing and end, same as the set's) |
| `sfx_panel` | root | `false` turns off the automatic panel ticks and whooshes (default: on when there are effects) |
| `min_seconds` | scene | Minimum duration (default 2 s); otherwise the scene lasts the narration + 0.45 s |
| `claims` | scene | IDs of the `build/<slug>/facts.md` entries the line uses (`["F4", "FIN-A"]`). `prompts` and `status` warn about a nonexistent ID and about a scene with a number but no entry |
| `master_lufs` | root | Integrated loudness of the final mp4 (two-pass normalization, peak -1.5 dBTP). Default: -16 in the voice format; text-only does not normalize. `false` turns it off |
| `caption_style` | root | `"default"` (default, the usual caption) or `"karaoke"`: voice only, chunks of 1 to 4 words in uppercase (Barlow SemiCondensed 84) and the spoken word in an amber box with Vacuum-colored text, on the timing of `voice.json` (`words[].start/end`); one PNG per word. Center at y 1380, in the close shot at y 560 (above Sam's head); `flat.caption_y` changes it. Design approved in `tools/flat2d/style_v4.py` |
| `panel` | root | `true` (default). `false` turns off for the whole video the panel/stamp, the title question (`on_screen` becomes a plain caption) and the automatic panel sounds; the cover comes out without a title. 2D series |
| `cast` | root | Cast of the 2D series: `{"rosa": {"name": "ROSA", "skin": "#c08a62", "hair": {"color": "#22170f", "style": "long"}, "shirt": "teal", "coat": false, "accessory": "scarf", "marker": "#6fd0c0"}}`. `hair`: color, or `{color, style}` (or `hair_style` beside it), `style` = `short` \| `long` \| `bald` \| `grey`; `accessory` = `headlamp` \| `bandage` \| `scarf` \| `glasses` \| `none`; `coat` = lab coat; `marker` = color on the plan. Colors: `#rrggbb`, `[r, g, b]` or name (`tools/flat2d/cast.py`, `NAMES`). Extra options: `pants` (trousers in `wide`) and `collar`. A `sam` with no color in the cast is the prototype's, with the headlamp |
| `flat` | scene | 2D set (`py -m ifscape flat2d`, drawing in `tools/flat2d/`). `shot`: **`wide`** (a real scene in side view, full-body characters: `set` = `pharmacy` (counter, shelves, glass door with the street) \| `busstop` (shelter, pole, pharmacy facade, buildings) \| `frontdoor` (glass door seen from inside, grille and lock); `actors` `[{id, at, facing?: left\|right, behind?: true (behind the counter), expr?, kind?: people\|infected}]`, `light`, `locked` (locked at the start), `infected` (0 to 8 hunched silhouettes in the background), `camera` as in plan), **`close`** (FRAMING of the wide stage, not another drawing: the same puppet as `who` (default `sam`) front-on, camera zoomed ~3.2 on the head and chest; `bg` becomes the set: `shelves` -> `pharmacy`, `door` -> `frontdoor`, `street` -> `busstop`; `expr`, `light`, `silhouette`), **`duo`** (framing of the stage at zoom ~2.4: `who` `[left, right]`, the same puppet in 3/4 facing each other, `counter`: true puts the counter in the foreground at waist height, `bg` as in close, `expr` text or `{id: expr}`; caption in the top gap, y 560). One character across all shots (`tools/flat2d/figure.py`): same face, outline and palette; the headlamp beam comes from whoever has `headlamp` in every shot and follows `light`; the `appear` silhouette and background infected stay behind the glass (`glass`/`glass_block` mask from `sets.py`), never in front of the frame or the grille. `plan` (floor plan, for a sense of space 1 or 2 times per video: `place` = `pharmacy` \| `street` \| `busstop` (points `shelter`, `curb`, `street`, `pharmacy_door`, `far`), `actors` `[{id, kind: sam\|people\|infected, at}]` or `{cast id, at}` (marker in the `cast` color, head seen from above, name and arrow when walking), `doors`, `windows`, `light`, `infected`, `camera` `{zoom: 1.0 to 1.6 or [from, to], focus: point or [from, to]}`) or `card` (`blocks`: 1 to 3 `{label, value, note?, hot?, at\|word?, source?}`). `events`: `{do, at (0 to 1) \| word ("knocks" or "knocks#2"), offset?, for?}`. Plan: `heat` (`count`), `move` (`who`: actor or `infected`; `to`: point or `[x, y]`), `door` (`state`, `door`?), `window`, `light`, `knock` (`times`, `gap`), `turn` (`who`: becomes a blue-gray dot in 0.6 s, the name disappears), `bite` (`who`, `target`: approaches, white-gray ring pulse and triggers the target's `turn`). Close/duo: `expr` (`to`; `who` in the duo), `talk` (`who`, `word`, `for` \| `until_word`; with neither, speaks until the scene's last word: the mouth switches between 3 shapes per syllable on the `voice.json` timing and closes between words; the narrator does not move anyone's mouth), `recoil` (steps back 20 px and returns), `hand` (shows the bandaged hand, `for`), `grab` (duo: `who` grips the other's arm, optional `target`, `for`), `appear` (silhouette; `state` show/hide), `light`, `knock`. Wide: `walk` \| `run` \| `move` (`who`, `to`: set point or `[x, y]`; step calibrated by the planted foot, no skating), `recoil`, `grab` (`who`, `target`), `hand`, `talk`, `expr`, `knock` (`who`, `on`: `door` \| `counter`: the fist hits on the frame of each beat, with the shake), `drop` (`who`; the key falls, bounces and stays on the floor), `lock` (`who`; the hand goes to the lock and it turns; `state` locked\|unlocked), `light` (store light), `bite` (`who` rushes in and leans over `target`'s shoulder, gray ring pulse, no blood; the target recoils and turns), `turn` (grayed skin, hunched posture, dragging step from then on) and `heat` (silhouettes in the background). Expressions: `calm`, `alert`, `scared`, `sick` (pale, sweat, lost gaze, no wound), `whisper`, `smile`; automatic blink on all. `timeline.json` gains `knock_hit` (frame of each knock = frame of the shake), `bite_contact`, the `turn` that the bite triggers and `end_frame` in `talk`. Points and pieces: `tools/flat2d/places.py` and `sets.py` |
| `clock` | scene | 2D HUD, fixed clock at the top left: `{"day": 0, "from": "18:40", "to": "18:43"}` (24 h in the script, "DAY 0 · 6:42 PM" on screen; the time advances in the scene). Absent = stays stopped at the previous scene's last time; `null` hides |
| `chip` | scene | 2D HUD, occasional chip below the clock: `{"label": "SUPPLIES", "value": "9 DAYS", "at": 0.3 \| "word": "...", "for": 3.0, "level": 0.6}` (or a list). Enters and leaves with a 0.3 s fade and slide; `level` (0 to 1) draws the thin bar. Label up to 26 and value up to 14 characters |
| `sfx[].word` | root | In place of `at`: the cue lands on the start of the voice word (`"billions"`, or `"billions#2"` for the 2nd), plus `offset` in s. It does not drift when the line changes. In `ambience`, `from`/`to` accept `["05", "billions"]` |

## Adjusting the identity

Colors, positions and sizes live in `ifscape/brand.py`. Positions respect the 9:16 safe zones: nothing at the extreme top, at the bottom or in the right-hand button strip.

## Pipeline warnings

- A video of 60 s or less gets a warning, because the TikTok rewards program only pays videos longer than 1 minute.
- **Duration target: 61 to 70 s** (`timing.TARGET_SECONDS`). `prompts` and `voice` show the estimated duration before the voice (line = words / model pace, v4 2.66 and v2 3.0 words/s, + 0.45 s per scene + 2 s pause; measured error of +-0.3% on v4 and up to +-7% on v2) and how many words to cut. `voice` refuses to spend credits on a script more than 5% above 70 s; `--allow-long` records it anyway.
- **Final gate (`qa`):** ERROR (not ready) for wrong resolution, fps or pix_fmt, 60 s or less, a scene with a provisional card and a peak above -0.1 dBTP; WARNING for duration outside the target, video and audio more than 1.5 frames apart, duration different from the sum of the scenes, a clip that freezes, black screen outside the last 4 s and a peak above -1 dBTP. Voice vs. effects comes out only as a measurement (`voice_over_sfx`), with no calibrated threshold yet.
- `py tools/qa/final_sheet.py out/<slug>.mp4 [--times ...]`: sheet of frames of the finished video (`build/<slug>/final/final_sheet.jpg`, with the time on each frame) and audio peaks per second (> -3 dBFS) and silences > 2 s. Look at it before delivering.
- `py tools/qa/sfx_check.py <file.wav|mp3> ...`: duration, RMS, peak and % silence of a generated effect; exits with an error if it is mute. Run it before registering in `sfx/library.json`.
- Blender writes each render's time to `build/<slug>/blender/render_log.jsonl` and warns "Shadow buffer full".
- A clip shorter than the scene freezes on its last frame. Generate the length `prompts.txt` indicates.

## Modules

| Module | Responsibility |
| --- | --- |
| `script.py` | Reads and validates the JSON. Resolves the stamp that holds between scenes (absent = keeps, `null` = hides) and the global or per-scene prompt style |
| `voice.py` | ElevenLabs `POST /v1/text-to-speech/{voice_id}/with-timestamps`. Converts the per-character alignment into per-word times. `--dummy` generates silence at 0.42 s per word to test without the API |
| `timing.py` | Scene duration = narration + 0.45 s (minimum `min_seconds`). Caption in chunks of 3 words (up to 4), not crossing punctuation and not ending on a weak word ("the", "of", "as"...) |
| `graphics.py` | Draws in Pillow the caption (keyword in amber), the @, the end card and the provisional card. Looks for the brand fonts in `fonts/`; without them, uses DejaVu and warns |
| `sfx.py` | Sound effects from `sfx/library.json`: Mixkit for the generic (city, wind, stream, forest, whoosh, impacts; commercial use without attribution) and ElevenLabs Sound Effects for the specific (hits, blackout, flooding subway, collapse, tick; generated once and kept in `sfx/elevenlabs/`). `IFSCAPE_SFX=mixkit` forces Mixkit only, for comparison. Cues come from the script (`sfx`, `ambience`), from the panel (whoosh on the jumps, tick only on the `counter` drop) and from the `traffic.py` simulation (`sfx_traffic`). Mixes in batches of 12, compresses the bus and adjusts in two passes to -21 LUFS, with a limiter at 4x the rate (AAC was overshooting the peak). Ambiences longer than the file repeat with a crossfade (`end` in the library cuts the tail). The synthesized version of 2026-10-21 was discarded (it sounded strange) |
| `panel.py` | Live panel in place of the stamp: clock on "NOW", number scroll on time jumps, `counter` that changes at an instant. Generates a PNG sequence per scene when the number moves |
| `render.py` | Per scene: reframes the clip to 1080x1920 at 30 fps, freezes the last frame if the clip is short, overlays the PNGs with time-based `enable` and encodes H.264. Then concatenates, mixes the optional music track (volume 0.30 in the silences, ducked by the voice with sidechaincompress, 0.5 s fade-in and 1.5 s fade-out) and writes the `.post.txt` with a checklist |
| `prompts.py` | Per scene: where to generate (`tool`: Seedance 2.0 Mini 720P with exact duration, or Veo 3.1 Lite in Flow, always 8 s), the IMAGE prompt (`prompt` + `style`) and the MOTION prompt (`motion` + `motion_style`). Seedance duration in whole seconds, minimum 4 s, with a 0.3 s tolerance covered by the frozen frame. Header with seconds and estimated credits. Warns when a Veo scene exceeds 8 s. Also writes `flow-lote.txt`, two messages for the Flow agent: all the images, then all the videos |
| `upscale.py` | Only for clips below 1080p (AI video at 720p); skips Blender ones, which already come out at 1080p: tested on 2026-10-21, 2x followed by a downscale washed out the shadows and facets of the low-poly. Upscales each clip 2x (720p to 1440p) with Real-ESRGAN `realesr-animevideov3` on the GPU via Vulkan and writes to `clips/<slug>/hd/`; the render prefers that version and downscales to 1080p, which sharpens the image |
| `blender.py` | Path without AI video: computes the scene timeline (from the narration, or estimated without it) into `build/<slug>/blender/timeline.json`, runs `tools/blender/<slug>.py` (or the data-driven `stage` builder in `tools/stage/`) in Blender 5.2 in the background (Eevee, about 0.5 s per frame), joins the frames into `full.mp4` and cuts it into `clips/<slug>/<id>.mp4`. Resumes the render only if the timeline and the code (`tools/blender/**/*.py`, including `lib/`, without `examples/`) did not change. The render trims each clip to the scene's exact time, so cuts join with no jump. Does not overwrite AI clips without `--force` (the `clips/<slug>/.blender` mark indicates Blender clips) |
| `flat2d.py` | 2D set without Blender (`py -m ifscape flat2d scripts/<slug>.json [--stills 30,900] [--force]`; `all` runs it on its own when a scene has `flat`): same timeline as `blender.py`, draws each scene with `tools/flat2d/engine.py` (Pillow, 2x supersample; per frame: plan ~0.12 to 0.2 s, close ~0.2 s, duo ~0.25 to 0.28 s, wide ~0.2 to 0.3 s, card ~0.03 s) straight into FFmpeg and writes `clips/<slug>/<id>.mp4` (1080x1920, 30 fps, bt709). Also writes `build/<slug>/flat2d/timeline.json` (frame of each event, beat, block and chip, for the sound designer) and `render_log.jsonl`. `--stills` uses the whole-video numbering, from 1. Example: `scripts/flat2d-demo.json` |
| `lint.py` | `py -m ifscape lint scripts/<slug>.json`: stamp with a deadline and no source, imperial unit, absolute word, more than 2 numbers in the voice and an internal note in `post.txt`. Only flags (HIGH/MEDIUM/WARNING); exits with code 1 if there is a HIGH. Run it before `script-review` and after the render, on `post.txt` |
| `qa.py` | Final gate of `out/<slug>.mp4` (ffprobe, blackdetect, ebur128): ERROR and WARNING in `build/<slug>/gates/final.json`. Runs on its own at the end of `render` |
| `cover.py` | Opening question as the title (`hook`) and cover = frame 0 without the panel (clean frame from Blender's `full.mp4` + title + @), written by `render` |
| `brand.py` | Colors, positions and sizes of the identity |

## Folder layout

```
scripts/<slug>.json     video scripts (input)
ifscape/                pipeline modules (table above)
tools/                  stage/ (data-driven 3D builder), flat2d/ (2D system), blender/, qa/ (checks, delivery.py), guard/
docs/                   rules and procedures (script-rules.md, review-gates.md, briefing-template.md, visual-identity.md, ...)
assets/                 ready-made models and sets (only LICENSES.md is versioned)
fonts/  sfx/            brand fonts; sound library
build/<slug>/           per-video working files (not versioned)
clips/<slug>/  out/     rendered clips and final videos (not versioned)
research/               local notes (not versioned)
tests/                  unit tests
.claude/agents/ .claude/skills/   Claude Code agents and skills that run the workflow (see CLAUDE.md)
```
