# Series bible: The Millbrook Outbreak

Update at the end of each approved part (where it stopped, what was planted and not yet paid off).

## Cast (`cast` of Part 1; copy exactly)
- **Sam** (SAM): pharmacist, owner of Millbrook's only pharmacy, lives above it. White coat, blue shirt, short brown hair, headlamp. Studied pharmacy (knows how to recognize signs of rabies).
- **Rosa** (ROSA): neighbor; every night at seven she picks up her mother's medicine (pills). Yellow coat, scarf, long black hair. Her mother has NOT appeared yet (planted, not paid off).
- **Mr. Hale** (MR. HALE): longtime customer, knocks 3 times on the counter "like always". Bitten by a dog in the afternoon; became infected; bit a man at the bus stop. Gray hair, brown shirt, bandaged hand.
- **Bus stop man** (BUS STOP): bitten by Hale; infected.

## Places
- Millbrook main street: bus stop (Oak St, "BUS 14"), pharmacy next door, lamp post.
- Pharmacy: counter, shelves, glass door to the street; pantry upstairs (Sam's apartment).

## Season redo (apply VISUAL-DIRECTION 1 to 26 to Parts 1 to 4, one at a time, checking the connection with the previous one)
Current versions: Part 1 v5, Part 2 v3, Part 3 v3, Part 4 v3 (all awaiting approval; the analysis is in the local continuity notes). Decisions: SURVIVAL RULE card only from Part 4 onward (Part 4 = rule 1); may plant and cut, keeping the plot facts.

## Where Part 1 stopped (DAY 0, 19:31; `scripts/zombie-outbreak-1.json`, 15 scenes, 74.8 s)
- Opening 18:30 "last normal hour"; Sam (pharmacy, lives upstairs), Rosa (mother's medicine at seven), Mr. Hale knocks 3 times on the counter "like always" with his bandaged hand (dog bite); glass of water, he recoils; card RABIES WEEKS × HOURS; Hale bites a man at the stop; 3 infected.
- Scene 08 (wide): Rosa is late, Sam grabs the key ring; 08b: panel FOOD 9 DAYS (the upstairs pantry, "Upstairs pantry"); 09: Rosa runs down the street (bus stop, seen from OUTSIDE) to the pharmacy door; 10 (from inside): the key ring falls, he picks it up, pulls Rosa in, locks; chips SAFE INSIDE 2 and FOOD 4 DAYS.
- 19:30: the hour ends, the light goes (only the headlamp), 7 infected outside, 3 knocks on the glass door (Hale OUTSIDE the frame: the face is the reveal of Part 2), silhouette on the glass, Rosa: "don't open it." → CONTINUE...
- A paper bag with the bottle of Rosa's mother's medicine (the "mom's pills" from seven) stays on the pharmacy counter (left side) in ALL pharmacy scenes of Parts 1 to 4 (prop `pills`, `flat.props`). Rosa never took it.
- The pharmacy's two doors already appear in the counter scene (04): BACK (exit to the alley, left) and STAIRS (stairs to the pantry/apartment upstairs, middle of the wall).
- Open: the dog that bit Hale (mystery of the season).

## Where Part 2 stopped (DAY 0, 19:41; `scripts/zombie-outbreak-2.json`, 10 scenes, 61.8 s)
- Reveal: it is Hale (bandaged hand raised); knocks 3 times, "slow and patient", and waits (wide in the dark, fist visible). Rosa: "the door will hold"; keys tremble; phone with no signal (chip); her mother 3 blocks away, alone.
- Dry sink; Sam and Rosa go up through the STAIRS door; panel "Upstairs pantry · 2 people": 16 L (2 days, 8 L/day) and food 4 days, "water ends first".
- Sam goes back downstairs ("Downstairs"), "Someone has to go outside for water. Two days."; Hale's silhouette returns to the glass; 3 weak knocks → CONTINUE...

## Where Part 3 stopped (DAY 0, 19:47; `scripts/zombie-outbreak-3.json`, 12 scenes, 67.3 s)
- Hale disappears from the glass, Sam breathes; Rosa comes down after him and wants to run to her mother, Sam: "water first, then we think about your mother". "The shuffling outside has faded" = the window.
- The truck left a pallet of water in the alley that morning, behind the back door, which may double the 16 L (chip WATER IN STOCK 16 L). Sam goes out through the BACK door (opens, he passes, closes), Rosa: "be quick, and come back to me".
- Alley with the headlamp on (`light: lamp`): heavy scraping, a figure in the street light (just one), Sam steps back; the whispered voice "Sam..." (TTS, not Chris) → CONTINUE...
- The whisperer is Hale; the figure at the mouth of the alley is Hale as a dark silhouette (actor `outside: "dark"`), just one.

## Where Part 4 stopped (DAY 0, 19:53; `scripts/zombie-outbreak-4.json`, 12 scenes)
- Sam recognizes the voice (Hale, at the counter for years); Hale steps out of the shadow with his bandaged hand; Sam lifts 2 jugs of 5 L (chip 16 L → 26 L, 3 days to 2, the math only in the action), goes in through the back door "a heartbeat before Hale reaches it", sets the jugs on the counter next to the medicine bag and notices that Rosa is not where he left her.
- Hale knocks 3 times slowly on the back door ("the way Hale always did"); Sam freezes and turns off the headlamp ("a knock back would tell the whole street someone is alive"). **Survival rule 1: "Rule one: don't answer a knock."**
- Sam opens the stairs door and calls Rosa; no one answers; only the bag of medicine she came for stayed on the counter; "Her mom is three blocks away. Rosa is gone." → CONTINUE... Part 5 starts from there (Rosa's mother is the lead; Hale is outside the back door; water is left on the pallet; rule 2).
- New 2D system in Part 4: `carry`, `door` + `hide`, single-fist knock, `look`, `prop`, `lean`, contact shadow.

## Geography: two distinct doors (correction)
Pharmacy (back wall, inside): **BACK** door on the left (x 40–220), exit to the alley (Parts 3 and 4; in the alley it is the same door, also on the left); **STAIRS** door in the middle (x 545–725), stairs to the pantry upstairs (Part 2). Front glass door on the right (x 780–945). The Hale who knocks on the glass (Part 2) stays OUTSIDE, behind the glass (actor `outside: true`): never inside the shop. Sam always on the left looking right (the mouth of the alley and the street); Rosa always to Sam's left in the pharmacy shots.

## New system from the redo
`keys` in the wide (in profile), `drop` with `for` (key disappears when picked up), `lamp` light state (only Sam's headlamp; the shop light off), series watermark in the top right corner (`brand.HANDLE_XY_SERIES`, does not cross body or caption).

## Sheet of the `alley` set (alley behind the pharmacy; `tools/flat2d/sets.py`, points in `places.WIDE_POINTS['alley']`)
- Left: the pharmacy's brick wall, BACK steel door (x 40–220), downspout (x 250), green dumpster (x 310–400). Center: wrapped water pallet (x 430–700, label WATER). Right: the mouth of the alley (x 800–1100) with a lamp post and neighboring building; amber backlight; the figures appear through it (`heat`).
- Points: door 230, dumpster 380, pallet 560, mid 730, mouth 900. Sam enters from the left and walks right; the threat's screen direction: right. No foreground (`front: None`): when needed, draw a layer in front (door frame, cropped box).
- Immutable props: pallet, dumpster, BACK door. Light: amber on the right; Sam with headlamp.

## Planted and not yet paid off
- The dog that bit Hale (origin; mystery of the season).
- Rosa's mother 3 blocks away and the seven o'clock medicine (Part 5: clue to the disappearance).
- How Rosa left the pharmacy with the door locked (Part 5).
- The rest of the water on the pallet (Sam only took 2 jugs of 5 L).
- Hale outside the back door, still knowing Sam's name.
- Survival rule 2 (the next part).
- Paid off in the redo: the 3 knocks (P1 → P2 → P4), the keys (P1 → P2), the 16 L (P2 → P3 → P4), the BACK door (P1 → P2 → P3 → P4), the mother (P1 → P2 → P3 → P4).
