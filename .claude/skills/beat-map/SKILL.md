---
name: beat-map
description: Builds the beat map of an Ifscape video before the script draft. Use after facts.md and thesis.md, before writing scripts/<slug>.json. Turns the causal spine into 8 to 12 beats (question, fact, visible consequence, link) so each fact is told, not thrown.
---

# Beat map

Basis: `docs/fact-presentation.md` (14 videos) and the "Fact told" section of `docs/script-rules.md`. Runs on the main model, no agent (cost: no calls). Input: `build/<slug>/thesis.md` and `build/<slug>/facts.md`. Output: `build/<slug>/beats.md` (~30 lines).

## How to do it

1. **Choose the live quantity** (form A): the number the whole video tracks on the panel (`panel_rows`), with start and end value (e.g. "Biggest mammal: 12 kilograms → 15 tonnes"). **Legibility test:** the big number must be understood in 1 s without explanation (simple ratio "WEIGHT x1 → x4,900,000", distance, count); no index derived from your own calculation ("% of strength by weight, 100 = stands up" was rejected in ants). The counter only shows integers (thousands separator works); value ≤ 14 characters and label ≤ 26. Mark the PANEL fact in the sheet. If there is no good quantity, the stamp's stopwatch is enough.
1b. **Choose the signature number** (1 per video, from the sheet) and the **ladder of 3 to 5 thresholds** that the panel crosses (PANEL block of `facts.md`). The signature number appears in 3 places: panel at frame 0, one sentence, post caption.
0. **Follow the CHAIN in `facts.md`:** each beat is a link of the researched chain (DATA, ANALOG or INFERENCE marked); inference only enters with "may/could/probably". In a calamity, the image of every beat shows a world in decline (see "Tone regulator" in `docs/script-rules.md`).
1c. **Give the witness a task** (viral study): a small, concrete goal inside the premise (grab, save, reach, keep, hide) that can fail. Mark which fact is the OBSTACLE and which is the TOOL. The task and the threat to it appear within ~3 s, and there is an "almost" in the middle (loses and recovers). No shouted orders: the voice narrates what "you" do in short sentences.
2. **Choose the setup and the payoff:** one element (the witness, a number, an object) that appears in the first 25 s and returns in the last 15 s, changed in meaning.
3. **Build 8 to 12 beats**, one per line, in the order of the spine (`F2 → F4 → …`). Each beat:
   `scene/second | question the viewer asks | fact (sheet ID) | form A, B, C or D | where it lives (VOICE/PANEL/SUB-LINE/CARD) | image BEFORE/WITH/AFTER the sentence | consequence that is seen (object on the stage) | link to the next (but, so, and since, which means)`.
4. **Assembly rules:**
   - one subject per scene; one beat per fact (4 to 6 facts per video, each with its own sentence, cut or stamp);
   - never two numbers in the same cut; the strong number goes to the panel or the card and the sentence gives the consequence as a fraction of daily life;
   - explicit doubt (maybe, some say, others disagree, nobody can, odds are, almost certainly) appears once, in its own sentence, followed by a firm fact; at most 1 per scene and 2 per video. "may/could/would likely" tied to a consequence is the permitted verb of inference and does not count;
   - a fact with no link to its neighbors, no object on the stage or no visible consequence goes to RESERVE, not to the script;
   - the visible consequence is written as **what is on screen at the sentence's frame** (place, action, object). A fact from another place (farmland, sea, city) calls for a scene or insert of that place in the map; if it does not fit the set budget, the fact goes to RESERVE. Ants: "36% MORE WHEAT" over the park, and "No ant digs this soil" with no paw digging;
   - the real fact that reframes the premise stays at the end, on the `final_fact` card (without the phrase "In our world", abolished);
   - **image before, with or after:** the panel changes ~0.5 s BEFORE the voice; the voice confirms WITH or AFTER what the image shows. Only 1 fact per video is said before the image, and only if it is a threshold planted and paid off within ~13 s;
   - **at most 2 numbers in the voice** in the whole video (with narration); in the text format the "Honest number on screen" rule of `docs/script-rules.md` applies (≤ 3 number pieces per screen, lint enforces it). Where it says "voice", read "on-screen sentence" in the text format, and the "no-voice window" becomes a no-sentence window;
   - **home stretch:** false relief ("everything returns") followed by a short twist and the real fact (`final_fact`), before "What should I imagine next?"; the climax has a 2-to-4 s window with no voice, with the sound rising and the panel moving.
5. **Removal test** on each beat (delete it and see whether the next still makes sense); if it does, the beat is loose: cut or merge.
6. End the file with the **duration table**: sentences × (1 s + 0.3 s per word, minimum 2 s) per scene, to reach 61 to 70 s.

## Afterwards

The script is written beat by beat. The `script-review` agent checks each line against the map (table prepares / pays off / form / object / verdict).
