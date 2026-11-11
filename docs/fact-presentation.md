# How the virals present facts

The concern: "many facts are thrown in" in our videos. This study looks only at **how each fact enters** (order, form, timing, link to the previous one). General narrative, rhythm and visuals are in the earlier narrative study and were not redone.

## Method and limits

- **Sample: 14 videos.** 7 from TikTok with on-screen text only (the same ones downloaded earlier, plus `meanwhileanimations`, which had not been read), 6 YouTube Shorts with narration and 1 from the competitor The If Engine. 12 of the 14 pass 1M views.
- **On-screen text:** OCR (RapidOCR, 2 frames per second) with tracking of each line: start, end, height on screen (y, from 0 at the top to 1 at the bottom) and size. It gives the screen time of each line with ~0.5 s of error. **Narration:** faster-whisper (small.en) with timings, plus frame sheets every 2 s.
- **Competitors:** @TheIfEngine has 5 Shorts; the biggest has 1.3 thousand views. @IFEARTHCHANGED **has no public video** on YouTube (the channel exists, with no Shorts or videos tab), and both TikTok profiles failed to load through OpenCLI. Only The If Engine remained.
- **Discarded after downloading:** "What If Humans Suddenly Disappeared?" (Clarify Buzz, 9.3M): loose AI images, no fact and audio that is not English. "Earth Had Rings" (Ultra Space Balls, 8.5M): cartoon dialogue, no fact. They stay only as counterexamples.
- YouTube like rate and TikTok like rate cannot be compared with each other. Within each platform, n = 6 or 7: correlation, not proof.
- Raw data (OCR and whisper JSON, transcripts, frame sheets) stays in local study notes.

## Table per video

Legend: **N facts** = verifiable claims (number, mechanism or data point); **num.** = distinct numbers; **screen** = average time each line stays on screen.

| # | Video | Dur. | Views (likes) | N facts / num. | Screen | Dominant form |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | @lunarcheeseee, Earth stopped spinning (TT, text) | 80 s | 28.6M (12.2%) | 4 / 1 quantity | 3.5 s | One live quantity in the panel; the line names the threshold crossed |
| T2 | @lunarcheeseee, sun exploded (TT, text) | 80 s | 17.0M (11.2%) | 5 / 4 | 4.5 s | Number as suspense (the light is 8 min late); numbers in the panel, consequence in the line |
| T3 | @man_ia_c, electrons 5 s (TT, text) | 80 s | 16.5M (12.1%) | 7 / 2 | 3.5 s | Mechanism in 2 short lines, then a ladder of objects (hand, sand, person, Earth, galaxy) |
| T4 | @simplysimulated, all women disappeared (TT, text) | 76 s | 23.1M (12.1%) | 11 / 10 | 3.5 s | Three layers: line = consequence at home; panel = statistic; big card = the number |
| T5 | @meanwhileanimations, all women (TT, text) | 113 s | 17.0M (15.9%, 1.4% shares) | 9 / 7 | 3.0 s | Consequence first, number after as the why; witness planted and paid off |
| T6 | @then.what.animation, rained 1,000 years (TT, text) | 92 s | 11.7M (12.0%) | 2 / 1 quantity | 4.5 s | Almost no fact; water level in the panel, everyday object lines |
| T7 | @zenithwhatif, humans disappeared (TT, text) | 73 s | 9.0M (7.2%) | 6 / 0 (stamps only) | 4.5 s | "cause. effect." pair per time jump |
| Y1 | Zack D. Films, humans grew wings (YT, voice) | 34 s | 21.2M (4.1%) | 6 / 2 | ~4 s per fact | Chain problem, solution, new problem |
| Y2 | Cleo Abram, Moon exploded (YT, voice) | 52 s | 7.6M (3.3%) | 8 / 2 | 2 to 4 s | Audience questions at the start, paid off in order; "bad news / good news" |
| Y3 | xkcd's What If?, Moon of protons (YT, voice) | 88 s | 1.2M (5.0%) | 7 / 3 | ~6 s | Intuition, then break ("You might imagine… However"), mechanism, escalation |
| Y4 | Almost Reality, Earth as big as the Sun (YT, voice) | 28 s | 3.5M (0.9%) | 5 / 0 | ~3 s | Myth corrected, then a list of effects without a why |
| Y5 | TrendTown, Sun exploded (YT, voice) | 23 s | 19.1M (0.8%) | 0 / 0 | n/a | Only mood and adjectives; no fact (counterexample) |
| Y6 | MetaBallStudios, Moon fell to Earth (YT, no speech) | 26 s | 14.6M (2.4%) | 1 / 1 quantity | n/a | Only "Distance (km)" falling from 342,885 to 0 and the Moon growing |
| C1 | The If Engine, Earth froze 1 s (YT, voice) | 24 s | 1.3 thousand (1.4%) | 3 / 1 | ~4 s | Number in the 1st second, effect, why at the end ("Not because… because…") |

**Quick read:** on YouTube, the fact chains (Y1, Y2, Y3) have 3 to 5% likes; the pretty videos without facts (Y4, Y5) stay below 1%, with similar views. On TikTok, what generates the most likes and shares (T5, 15.9% and 1.4%) is not what has the most facts: it is what **plants a witness and pays it off at the end**.

## How each fact enters (detail of the best)

**T1, Earth stopped spinning.** Number first, prepared by the place: "You are standing on the equator." (5.0 s, 3 s on screen) and then "The ground here moves east at 1,037 miles an hour." (8.5 s, 4 s). From there on the number **does not come back in the line**: the panel counts the speed falling (1,029 → 0 mph) and the wind rising (17 → 1,002 mph). The line only enters when the counter crosses a threshold everybody knows: "It is already stronger than any hurricane." (34 s, wind 388) and "The wind is now faster than sound." (47.5 s, wind 830). The other lines are pure consequence ("You do not. Nothing does.", "Everything not bolted down goes with it."). Twist: "The planet stops. The oceans do not." (52.5 s). End card (73 to 80 s, y 0.53, small type): "And the oceans would not stop with it". **One fact, four readings.**

**T2, Sun exploded.** The real fact (light takes 8 min 20 s) becomes suspense, not information: panel "ITS LIGHT ARRIVES" counting from 0 s; line "You won't know for eight minutes." (10.5 s), "Its light is still on the way." (16.5 s). The scale numbers (93 million miles, 1,111 °F, 6,000 miles a second) live in the panel, each with 10 to 25 s of screen; the line only says what you see ("Everything it touches catches fire.", "The ocean is boiling away."). End card with the fact that dismantles the premise: "The sun is too small to ever explode".

**T3, Electrons.** Premise, rule, consequence. Anchor without a fact ("You're in Central Park, New York.", 5 s), visible effect ("You can see the stars through your hands.", 16.5 s), then the mechanism in two lines of 7 and 4 words ("Every atom is now pure positive charge." / "And positive charges repel.", 20.5 to 28 s) and then the ladder of objects, each step bigger: grain of sand = nuclear bomb (31.5 s), every person brighter than the Sun (36.5 s), the Earth comes apart (44 s, panel "EARTH IS NOW 310,752 MILES WIDE" counting), more than the Milky Way (49.5 s). Twist at zero: the electrons come back "and they explode too" ("SAME ENERGY AS THE FIRST BLAST"). Card: "Electrons are 0.03% of your mass".

**T4, simplysimulated.** The densest of the sample (10 numbers) and still no thrown fact, because each number has **one beat only, with its own stamp** (+10 SEC, +1 MIN, +1 HOUR, +1 DAY, +1 WEEK, +9 MONTHS, +1 YEAR, +100 YEARS, +116 YEARS) and three layers that say the same thing in different ways:
- line (y 0.66, 3.5 s): the consequence in household terms: "Hospitals just lost 9 in 10 nurses.", "Half the cribs are suddenly empty.", "Overnight, 4 in 10 workers are gone.";
- panel row (y 0.52, small): the statistic ("~70% OF ALL HEALTH WORKERS");
- big card at the top (y 0.16 to 0.23, number ~5% of screen height, 3 s): "90% OF THE WORLD'S NURSES ARE WOMEN", "94% OF PRESCHOOL TEACHERS", "37% OF WORLD GDP", "76% OF UNPAID CARE WORK".
The percentage becomes "9 in 10" in the line: a fraction you can imagine. Setup and payoff: the panel says "THE OLDEST MAN EVER LIVED TO 116" (60 s) and the next stamp is "+116 YEARS: Humanity ends within one lifetime." (64.5 s). Ending: "PART 2 … WHO WOULD LAST LONGER? TELL US IN THE COMMENTS".

**T5, meanwhileanimations.** Two lessons. (1) **Consequence first, number after, as the why:** "Hospitals collapse within hours." (19 s) → "Nearly 90% of the world's nurses were women." (21.5 s); "40% of the world's workforce vanished overnight." → "And 50% of all customers. Markets crash." (2) **Planted witness:** "This boy was born one minute before it happened." / "Remember him." (26 to 32 s) and, 60 s later: "Remember him? He is the last human on Earth." / "His mother held him for one minute." (90 to 99 s). It is the video with the most likes and shares in the sample. The 46 to 71 s stretch (crime +80%, 12.5 billion hours) is the weakest: statistic without an object, in a row.

**T6 and T7.** Almost no fact. T6 lives on one quantity (WATER X M ABOVE THE STREET) and everyday objects ("the drains give up", "the avenue is a canal", "Life moves upstairs"); the only fact with a number is at the end ("The water takes three centuries to leave."). T7 is the "cause. effect." mold per jump ("Power plants shut down. The lights go out.", "Without pumps, the subways and low streets flood."), and the strong fact is saved for the end ("a thin red line in the rock"). T7 has the lowest likes of the TikToks (7.2%): it is well told, but each jump resembles the previous one (no scale escalation).

**Y1, Zack D. Films, wings (21M in 34 s).** Question at 0 s ("could you actually fly?"); each fact is the condition the previous one created: wings at least 20 feet wide (4.5 s; "20ft" dimension drawn over the wings) → "chest muscles twice the size of a bodybuilder's just to lift them" (8.2 s; the open chest shows the muscle) → "To make these muscles more stable, you would need one giant bone in your chest" (13.5 s) → "But you'd be too heavy to lift off by flapping, so instead you would have to jump off a cliff and glide" (18.5 to 24.5 s) → "And since your lungs aren't designed for flight, you would pass out mid-air, meaning you would need an oxygen tank" (25 to 33 s). Connectors in every fact (Well, and, To make, But, so, And since, meaning). Each fact changes the character's body on screen. It ends on the absurd image (oxygen mask), with no call.

**Y2, Cleo Abram, Moon exploded.** Raises the questions the audience has ("Would tides disappear? Would big chunks rain down on Earth?", 2.7 to 6 s) and pays off both, in order. Mechanism before the number: if the explosion is small, gravity pulls the pieces back together ("bloop bloop bloop"), hence "600 billion of the largest nuclear bombs ever built" (13.8 s; row of bombs on screen). Then it alternates "bad news / good news": the pieces fall, most burn up, the heat cooks us, the tides stay ("less than half… pulled only by the sun", with the OLD TIDES / NEW TIDES lines drawn on the beach), we gain rings, but the axis wobbles. It closes by opening the next video ("how far away the moon actually is").

**Y3, xkcd, Moon of protons.** Uses the audience's intuition and the break: "You might imagine an electron moon orbiting a proton Earth, sort of like a gigantic hydrogen atom. On one level it sort of makes sense." / "However, electron moons do not orbit proton planets." Then the mechanism with a scale comparison ("about 20 orders of magnitude stronger than the gravity", arrows drawn) and the escalation up to "about equal to the … entire observable universe". Doubt appears **once**, with humor, and a firm consequence follows right away: "It's hard to say… nobody knows what the deal with dark energy is. But … nearby galaxies would be safe, since the gravitational influence … can only expand outward at the speed of light."

**Y4 and Y5 (counterexamples).** Y4 starts well (the myth: "most people would imagine a bigger planet with more space to live. But its gravity would become unstoppable") and then dumps five effects in 15 s, with no why or number: the Moon pulled in, planets torn away, oceans, mountains, freezing. Y5 has not a single fact ("this is the beginning of the end", "the last thing you would ever see"). Both have high views and likes below 1%.

**Y6, MetaBall.** Zero words. One number ("Distance (km)", from 342,885 to 0) and the Moon growing in the city sky. 14.6M views. Extreme proof that **one well-shown quantity is worth more than several spoken facts**.

**C1, The If Engine.** Number in the 1st line ("over a thousand miles an hour"), effect ("the ground would break first. You wouldn't. Neither would the air."), why at the end ("Not because Earth froze, because everything else kept moving.") and a next-part question ("What if Earth stopped for a full minute?"). Correct logic, realistic AI images and an effect triad; with 1.3 thousand views, the channel is too new to measure.

## Diagnosis of the `dinosaurs-never-extinct` pilot (same yardstick)

The script has 18 lines, 5 numbers (10 km, 2025, 30 million, 66 million, 25 kg) and **9 doubt marks** (Some say, maybe, may, Some scientists think, Others disagree, Nobody can replay, Odds are, Almost certainly, Nobody can prove it). No viral in the sample passes one. That is the main reason for the "thrown" feeling: half the lines are about the **debate** around the fact, not about what happens in the valley.

| Line | Verdict | Why (short) |
| --- | --- | --- |
| 02.1 "An asteroid 10 kilometers wide misses Earth." + card "wider than Mount Everest is tall" | THROWN (half) | The Everest comparison is good, but the size of a rock that **does not hit** pays off nothing afterwards. In the virals, the number only opens when it becomes the story's yardstick (T1, T2). Here the speed or the "near miss" would serve, not the size. |
| 02.2 "Some say the dinosaurs were already fading." | THROWN | Debate without an object on screen or consequence; opens a question the video does not follow. |
| 02.3 "A 2025 study says maybe not." | THROWN | Authority (year of the study) in place of the fact; "maybe not" does not say what. Two doubts in a row. |
| 02.4 "The herd below never looks up." | TOLD | Visible consequence of the "misses". It would come before the debate, right after 02.1 (cause and effect pair, like T7). |
| 02.5 "Our ancestors may have looked like this animal." | TOLD (weak) | It is the right setup (the witness, as in T5), but arrives as the 5th line of a scene with 4 subjects and with "may". It should be the 1st thing the video says about the witness. |
| 03.1 "Most mammals of the dinosaur age are rat-sized or smaller." | TOLD | Tied to the rat on screen. Repeats the panel ("Mammal size: rat") and 02.5; it could be the number in the panel and the line the consequence ("It eats at night, under their feet."). |
| 03.2 "But one was cat-sized and fed on baby dinosaurs." | THROWN | The best bar-table fact, with no image and no payoff: it opens "so why didn't the others grow?" and the next line answers with a doubt. |
| 03.3 "Some scientists think the giants kept them small." | THROWN (half) | It is the thesis mechanism, but said as an opinion and with nothing on screen showing "keeping small" (the giant taking up the pasture, the food, the day). |
| 03.4 "Others disagree. Nobody can replay that world." | THROWN | Anticlimax: two doubts erase the previous fact. No viral stops the story to say it does not know; xkcd says it once and follows with a firm consequence. |
| 04.1 "30 million years later, the planet is cooling." | TOLD (half) | Visible jump (light, stamp), but no "so what" for the witness. |
| 04.2 "Grass starts to spread across the valley." | TOLD (half) | Visible (the grass grows); pays off nothing. In our world, the grass is what made grazing mammals grow: here it would be the contrast hook. |
| 04.3 "Odds are, the animal near the rock is still rat-sized." | TOLD (weak) | It is the right payoff of 03.3 (the rat is still a rat) and in the right place. It is weak because it is a non-event without a yardstick: it lacks the size it would have in our world to give contrast. |
| 05.1 "66 million years later: no road, no house, no people." | TOLD | Visible absence that pays off the "our ancestors" setup. The best line in the middle. |
| 05.2 "Almost certainly, we never get here. Nobody can prove it." | THROWN (half) | The climax with two doubts. The thesis stands, but the line contradicts itself. |
| 06.1 "In our world, the asteroid hit." | TOLD | Clear twist. |
| 06.2 "Most land animals over 25 kilograms died out." | THROWN | Number without an object or comparison ("25 kg" cannot be seen). It would be "anything bigger than a dog" or the rat from scene 01 surviving. |
| 06.3 "The only dinosaurs left are birds." | TOLD | The eagle lands on the rock where the rat was: pays off the title and the object from scene 01. It is pattern P8 done well. |

**Summary:** 7 told, 4 halfway, 7 thrown. The thrown ones have three causes: (1) **doubt in place of the event** (02.2, 02.3, 03.4, 05.2); (2) **fact without payoff** (02.1, 03.2); (3) **number without an object** (06.2). Scene 02 mixes four subjects in 15 s (size, decline, herd, ancestor): that is where it sounds like a list.

## (a) Fact-presentation patterns

1. **One live quantity, several readings.** The number lives in the panel and changes; the line only enters when it crosses a known threshold. *T1:* wind 388 mph, "It is already stronger than any hurricane"; wind 830, "The wind is now faster than sound". *Y6:* "Distance (km)" from 342,885 to 0, without a word. *T6:* "WATER 10.0 M ABOVE THE STREET".
2. **The number becomes the consequence you see, as an everyday fraction.** The statistic stays on the card or panel; the line says what changes at home. *T4:* card "90% OF THE WORLD'S NURSES ARE WOMEN" and line "Hospitals just lost 9 in 10 nurses."; "Half the cribs are suddenly empty."
3. **Consequence first, number after as the why.** *T5:* "Hospitals collapse within hours." → "Nearly 90% of the world's nurses were women." *C1:* "Not because Earth froze, because everything else kept moving." The mechanism, when it comes first, fits in up to 7 words and is followed at once by the effect (*T3:* "Every atom is now pure positive charge." / "And positive charges repel." → grain of sand becomes a bomb).
4. **Chain problem → solution → new problem.** Each fact is caused by the previous one and causes the next; the connector is in the sentence. *Y1:* 20-foot wings → bodybuilder chest → giant bone → "But… too heavy" → "so… jump off a cliff" → "And since your lungs…" → "meaning… an oxygen tank". *Y2* does the "bad news / good news" version.
5. **The audience question comes before the fact that answers it.** *Y2:* "Would tides disappear? Would big chunks rain down?" (3 to 6 s), answered at 21 and 32 s. *Y3:* the wrong intuition is stated and broken ("You might imagine… a gigantic hydrogen atom… However, electron moons do not orbit proton planets."). *Y4:* "most people would imagine a bigger planet… But its gravity…".
6. **Ladder of known objects.** Each fact climbs a scale step with an object the person knows. *T3:* hand → grain of sand → person → Earth ("EARTH IS NOW 310,752 MILES WIDE") → Milky Way. *Y1:* wing → chest → bone → lung.
7. **Setup and payoff.** Something said early comes back as the climax. *T5:* "This boy was born one minute before it happened. Remember him." (26 s) → "Remember him? He is the last human on Earth." (90 s). *T4:* "THE OLDEST MAN EVER LIVED TO 116" → "+116 YEARS: Humanity ends within one lifetime." *T2:* "ITS LIGHT ARRIVES" count from 0 s → the explosion arrives.
8. **The real fact that reframes goes on the end card, small.** A small all-caps line (~1.5% of the height) right under the repeated question, y ≈ 0.5, for 5 to 7 s. *T2:* "THE SUN IS TOO SMALL TO EVER EXPLODE"; *T3:* "ELECTRONS ARE 0.03% OF YOUR MASS"; *T6:* "1,000 YEARS OF RAIN - 300 YEARS TO DRAIN · ONE AVENUE".
9. **Doubt said once, with something at stake, and right after a firm fact.** *Y3:* "It's hard to say… nobody knows what the deal with dark energy is. But … nearby galaxies would be safe, since … the speed of light." No other video in the sample uses a hedge in the middle.
10. **One beat per fact.** Even in the dense videos (T4, 10 numbers), each fact has its own line, 3 to 4.5 s of screen, its own stamp or cut and never shares the screen with another number. Average of 1 line every ~5 s; never two lines of different subjects in the same cut.

## (b) Checklist "fact told, not thrown" (testable by a reviewer)

For **each line that carries a fact** (number, mechanism or data point), the reviewer fills the table `line | sets up | pays off | form | object | verdict`:

1. **Sets up:** is there, before it (in the previous line, in the image or in the panel), the question, the problem or the yardstick it answers? Cite the line. No answer: THROWN.
2. **Pays off:** does the next line, or the image in the same cut, show what changes because of it? Cite. No answer: THROWN.
3. **Removal test:** delete the line. Does the next one still make sense alone? If yes, the line is loose (THROWN), unless it is the bar-table fact with a visual payoff.
4. **Form:** is it one of the 4: (A) live quantity in the panel and a threshold line; (B) consequence and then the why; (C) mechanism of up to 7 words followed by the effect; (D) chain link problem → solution. Definition without effect: THROWN.
5. **Number:** at most 1 per line. Either it is in the panel or card and the line gives the consequence, or it is in the line with an everyday comparison (fraction "9 in 10", object, known threshold). Number without object or comparison: THROWN.
6. **Object:** the fact touches the witness, the place or the viewer (it is on screen in the same cut).
7. **One subject per scene:** all the fact lines of a scene pull the same thread. Two or more subjects: HIGH.
8. **Doubt:** at most 1 hedge per scene and 2 in the video; the thesis's uncertainty is said once, in its own line, and followed by a firm fact. A line whose only content is "some say / others disagree": THROWN.
9. **Connector:** at least 70% of the fact lines start with or contain a link (then, so, but, and since, which means) or answer the question of the previous line.
10. **Setup and payoff:** at least 1 element (witness, number, object) appears in the first 25 s and comes back in the last 15 s.
11. **Final count:** more than 2 THROWN lines in the video = HIGH; the bar-table fact THROWN = HIGH.

## (c) Proposals (proposals only; nothing was edited)

### `docs/script-rules.md`
- New section **"Fact told"** with the 4 forms (A to D) of the checklist, the removal test and the "one subject per scene" rule.
- Replace "Specific, not generic" with "**fewer facts, one beat each**": 4 to 6 facts per video, each with its own line, cut or stamp; the number that impresses goes to the panel or card, and the line gives the consequence.
- **Doubt:** 1 per scene, 2 per video (today the ceiling is 3, and the pilot has 9 counting "Some say", which today is not counted). Also count "some say/think", "others disagree", "nobody can prove", "odds are".
- **Setup and payoff** as a requirement: the witness or a number from scene 1 comes back at the climax.
- **Text format:** screen line = consequence; statistic in the panel (`panel_rows`) or in the `fact`; never two numbers in the same cut.

### `.claude/agents/script-review.md`
- In the "Fact narrative" section, replace the 6 questions with the **line × sets up × pays off × form × object × verdict** table of checklist (b), with the removal test. More than 2 THROWN = HIGH.
- In "Hedges", add the debate forms (some say/think, others disagree, nobody can…) and lower the ceiling to 1 per scene and 2 per video.
- New HIGH item: "scene with two fact subjects".
- Always ask for 1 rewrite in form (A) for the strongest number (the number leaves the line and goes to the panel with start and end value).

### `.claude/agents/fact-check.md` (sheet in `facts.md`)
Add 4 fields to the sheet (short, 1 line each):
- **Question that sets up:** what the viewer must be thinking for the fact to land well (e.g. F3 "if they were small, did none hunt dinosaurs?").
- **Consequence that pays off:** what is seen or changes right after, on the stage.
- **Suggested form:** A (quantity in the panel: start value → end), B (consequence → why), C (mechanism of up to 7 words → effect) or D (chain link).
- **Links to:** IDs of the facts it causes or depends on (F2 → F4 → FIN-B). The "Spine" is now written as a chain of IDs with arrows, and a fact with no link goes to RESERVE.
- Mark 1 fact as **PANEL** (the video's live quantity) and 1 as **END CARD** (what reframes the premise), besides the FINAL.

### New skill (proposal): `beat-map`
A skill (not an agent, so as not to add runs), run **before the draft**, after `facts.md`: turns the spine into 8 to 12 beats, each with `question → fact (ID) → visible consequence → link to the next`, plus the panel quantity (start → end), the setup and the payoff. The script is written beat by beat, and `script-review` checks line against beat. Input: `thesis.md` and `facts.md`; output: `build/<slug>/beats.md` (~30 lines). Cost: zero agent calls. If the owner prefers an agent, `director` (Mode 1) already reads the draft and could take over the table; a new agent is not recommended.

## Open

- The competitor If Earth Changed has no public video; reassess if it publishes.
- The YouTube sample has Shorts of 23 to 52 s (only xkcd has 88 s). The chain pattern (Y1) was measured at 34 s: in 61 to 70 s, a chain of ~6 links plus the setup and the payoff fits.
