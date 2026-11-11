---
name: outbreak
description: Makes the next part of the 2D fiction series "The Millbrook Outbreak" (zombie, narrated, tools/flat2d system) from briefing to post, with the continuity, style and rules approved by the owner. Use when the owner says "next part", "Part 2", "continue the outbreak" or asks for a new episode of the zombie series.
---

# The Millbrook Outbreak (2D series)

One episode per session. **First of all, read `BIBLE.md` (in this folder)**: cast, where the story stopped, what was already planted. **Then read `VISUAL-DIRECTION.md` (in this folder)**: visual direction rules from the owner's audit of Part 3 (beats, evolving shot, progressive reveal, layers, shot list); they apply from Part 4 onward. The approved Part 1 is the mold: `scripts/zombie-outbreak-1.json` (13+1 scenes, 74.7 s). System: `README.md` (fields `flat`, `cast`, `clock`, `chip`, `caption_style`, `panel`) and the 2D system specifications (local build notes).

## What the series is (closed decisions)
- Fiction with a character, on the SAME Ifscape channel. Title "The Millbrook Outbreak — Part N", no "What if". Ends with a **"CONTINUE..."** card and the line "Continue." (never "Part 2", never `final_fact`).
- Narrator Chris, voice v4, **3rd person** ("Sam locks the door."). Characters speak only in short lines with `talk` (the mouth moves only there).
- Duration **60 to 75 s** as a reference; going over 75 s is accepted: do not cut a card, pause or line just to fit. The `qa` warning about 61 to 70 is Ifscape's target (ignore it). Lint overestimates by ~5%: measure on `timeline.json`.
- **Light check**: poetic license in the story; only what is stated as a real-world fact (science card, post description) gets a quick check with an opened URL. No `fact-check` gate.
- **Survival rule (applies from Part 4 onward)**: every part has ONE `SURVIVAL RULE N` card (an apocalypse "what to do", e.g. "never knock back" in Part 4), tied to what just happened and previously demonstrated by Sam's action (nothing out of nowhere), with a short Chris line ("Rule one: never knock back."). `card` card: label `SURVIVAL RULE N` (≤22), value up to 12 characters in caps (`DON'T ANSWER`), note ≤40, comes before the CONTINUE card. Number in sequence (Part 4 = rule 1).
- **Time continuity**: each part continues from where the previous one stopped (same night or Day 1); never skip days without showing it. Number of parts is open.

## Story rules (what was rejected and must not return)
1. **Nothing out of nowhere.** Every character, object, chip number and fact is introduced before it weighs: who it is, why they are there, why they know (the science comes out of the character's head: "Sam knows those signs from pharmacy school"), where the resource comes from (he says it on screen).
2. **Connection.** Each scene pulls the next (and/so/but/then); setup and payoff (e.g. 3 knocks from Hale → 3 knocks on the door; "last normal hour" → "Exactly one hour later").
3. **More scenes than map.** The floor plan (`plan`) is only for spatial sense, once per episode (opening or new place). The rest: `wide` (full body), `close` and `duo`, with the drawn cast. No "gray dot" as a character.
4. **Everything narrated is shown** (object, place and action, not only action; in Part 2 the sink, phone, stairs and keys were missing). If the narration says someone does or mentions something (hands over the cup, bites, locks, drops the key, turns on the sink, looks at the phone, climbs the stairs), the image shows it: `grab` with `item: cup`, `bite`, `lock`, `drop`, `keys` (trembling keys), `phone` (pulls out the phone, back to the camera, and looks down) and the `insert` shot with `kind: sink` (close-up of the tap with the character's hand; the sink is never a pharmacy prop: a set that does not exist in the place becomes a close-up). The owner decides when a line goes without an image (e.g. "back stairs" stayed only as Sam going to the back). A missing gesture/prop in the system = create it in `tools/flat2d/`, do a close-up or rewrite the line; never invent an object that does not fit the place. Make the line × image table in step 2 and check it again on the MP4 (step 8).
5. No gore: bite = advance + gray ring; infected = gray skin and hunched posture; threat by silhouette behind the glass and sound. An ordinary town (Millbrook), nothing real, no newscast or official alert.

## Style (approved; do not change without the owner)
- Amber technical floor plan over Vacuum; flat, dark side-view sets with warm amber light; **a single character drawing** in all shots (close and duo are a zoom of the same figure from the `wide`); **no nose**; thin warm outline.
- Sam always with a headlamp (the beam follows `light`). The pharmacy door is **glass with a frame**, no grille. The silhouette and infected stay **behind the glass**, backlit.
- HUD: only "DAY N · h:mm PM" at top left + an occasional chip (2 to 3 per video, with the context said before). No title on screen. **Karaoke** caption (amber box on the spoken word).

## Order
1. **Short briefing** (`AskUserQuestion`, recommendation marked): what happens in this episode (1 conflict + 1 hook), new place or not, who appears, cliffhanger. Write `build/zombie-outbreak-N/briefing.md`.
2. **Beats + shot list** (`beats.md`, 10 to 14; short shot list per scene according to `VISUAL-DIRECTION.md`: what changes every ~5 s, what the audience should NOT notice yet, foreground/action/background, where the caption sits; a still scene > ~6 s without a response = split into 2 framings of the same set or give it an event): for each one, "where was it planted?" and "what the image shows" (line × image table: every object, place and action in the line has a row with the prop or gesture that shows it). Update `BIBLE.md` with what this episode plants.
3. **Script** `scripts/zombie-outbreak-N.json` copying the structure of Part 1 (`cast`, `caption_style: karaoke`, `panel: false`, `closing` = a short suspense line that comes AFTER another sentence in the same scene; the voice gets a 2 s pause before it). Events tied to the word (`word`), never to guessed seconds.
4. **Gate:** `py -m ifscape lint` + `script-review` (1 pass; the agent's "Fiction series" section charges lack of connection as HIGH). Apply HIGH and the cheap MEDIUMs.
5. **Voice:** `py -m ifscape voice scripts/<slug>.json --allow-long` + `py tools/qa/voice_check.py`. Avoid spelled-out clock times ("seven forty" was read "seven hundred forty"): use "an hour later" etc.
6. **Image:** `py -m ifscape flat2d scripts/<slug>.json` (~0.17 s/frame, ~6 min). Build the sheet with 2 frames per scene (4 in scenes > 6 s) and LOOK, running the mini-audit from `VISUAL-DIRECTION.md` (write `review-visual.md`): the same character in the 3 shots, nobody cut off at the edge (in `wide`, camera `zoom` 1.35 to 1.6 with `focus` on `center`), nothing passing through an object, chip not covering the title, the action the voice describes actually happening. Spot test: `--stills <frame>`.
7. **Sound:** `sound-designer` agent (reuses `zb_*` and the local cue generator of Part 1). Knocks and blows that need to sound: `"accent": true` on the cue (enters after the compressor; absolute gain ~0.2 to 0.3) and, if the voice would cover it, put the blow in a no-voice window (separate scene or `min_seconds`). The cue's `offset` = event time (`el_peak` is already discounted). `sfx_lufs` -42. Measure the blow's peak on the final MP4 (`astats`): target -8 to -4 dB.
8. **Assembly and MP4 audit (rules 27 to 31 of `VISUAL-DIRECTION.md`):** extract 1 frame per scene from the MP4 and check the line × image table (is everything mentioned on screen?); `py -m ifscape render`, `py tools/qa/final_sheet.py out/<slug>.mp4`, `py -m unittest discover -s tests -q`. Check the last 4 s (CONTINUE card + boom).
9. **Delivery:** `py tools/qa/delivery.py <slug>` and fill in the FILL IN parts; reply to the owner with MP4, cover, PASTE INTO POST block, 6 to 10 lines (what changed, what came out weak, not verified) and "approve?".
10. **After approval:** commit (no `.env`), update `BIBLE.md` (where it stopped) and `research/video-history.md`; a new failure the owner catches becomes a line in `.claude/agents/lessons.md` and a rule here.

5c. **Resolution gate (from the audit of the Part 4 revision; `VISUAL-DIRECTION.md` rules 22 to 26):** no visual fix counts as resolved just because it added an object, changed a character's position or inserted a close-up. Each change answers, in `review-visual.md`, what new information it delivers, whether it is understood in 5 s without audio and whether the place remains real (scale, support, light, object where the body is facing). Beats every 3 to 5 s in a long scene, continuity ledger (including HUD: value before, action, new value) and the 3 passes (no audio, with audio, between shots) before delivering.
5b. **Visual direction (audit):** no shot stays ~5 s with the same composition without identifiable progression; the threat is revealed in stages (dark zone → clue → Sam's perception → partial reveal → hold) with the light source established beforehand; dialogue has 3 to 4 reactions; a new set has a sheet in `BIBLE.md`; the caption does not cover eyes, gesture, threat or the mentioned object.

## Known system limitations (work around them in the script)
- Facing front and in 3/4 the character does not walk (walks only in profile in `wide`).
- After `bite`, the bodies cross for a few frames.
- Ready places: `pharmacy`, `busstop`, `frontdoor` (wide) and `pharmacy`, `street`, `busstop` (plan). A new place = data in `tools/flat2d/places.py` and `sets.py` (check on a still).
- Steps (`road_steps`) are low; a running action sounds better with 2 offset layers.
