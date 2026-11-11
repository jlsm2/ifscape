# "Instrument" visual identity (Ifscape)

Moved out of CLAUDE.md on 2026-10-24. The values live in `ifscape/brand.py`; read this file when touching the panel, captions, cover or end card.

## "Instrument" visual identity (2026-10-21)

The owner dropped identity D (Big Shoulders in all caps with an outline) because it "did not look professional". Of three directions (previews in local research notes), the owner chose **A · Instrument**, with the layout of the niche's viral videos. The values are in `ifscape/brand.py`.

- **Palette (same as the brand):**

  | Name | Color | Use |
  | --- | --- | --- |
  | Vacuum | `#0B0F17` | End card background and text shadow |
  | Mist | `#1B2333` | Surfaces |
  | Light | `#F5A524` | Amber: panel dot, keyword and final call |
  | Text | `#F4F6F8` | Main text and panel number |
  | Secondary | `#8A94A6` | Supporting text |
- **Fonts:** Barlow (DIN style, OFL license, in `fonts/`). Medium for the sentences, SemiBold for the question, label and card, SemiCondensed SemiBold for the number. **Mixed case**, as written in the script. **Soft shadow** instead of the hard outline.
- **Layout (the viral videos' layout):**
  - opening question as the title (`cover.hook`, since 2026-10-21): the whole question in Barlow SemiBold 100 px, all the same size, in 2 balanced, centered lines starting at y = 470 (inside the central square y 420-1500, which shows even in the 1:1 crop of Instagram's browser upload; at y = 300 the first line was cut off in the 2026-10-21 post), with the `highlight` word in amber, over a dark gradient that ends before the panel. It appears at frame 0, with no fade-in, and leaves with a fade. The giant keyword (poster style) was tested and dropped;
  - live panel on the left, mid-screen (x = 72, y = 860);
  - small narration sentence at the bottom (44 px, y = 1290, max width 780 px), one at a time, with soft entry and exit;
  - @ at y = 1440.
- **Live panel (`ifscape/panel.py`):** amber dot plus a small spaced all-caps label (`panel_label`, e.g. "TIME WITHOUT HUMANS"), thin line, big white number and a data line in small normal text, white, Barlow Medium (`panel_sub`, with `panel_sub_at` to enter mid-scene; 2026-10-23: it used to be amber). The data line repeats the number the voice says at that moment and enters on the trigger word; it never carries a new fact.
  - The number always moves:
    - running time is always a stopwatch (2026-10-23): "NOW" counts up in "00:02.10" and the countdown to an event counts down in "00:01.28" (`counter` with `unit: "clock"`), in JetBrains Mono Light, in real time;
    - on a time jump, the number scrolls quickly from the previous value to the new one (0.6 s);
    - countdown with no time unit ("200 MILLION", "300,000", with the label "YEARS AGO"): the number scrolls down to the next value or to "NOW";
    - a `counter` rises slowly and changes in an instant (opening of humans-vanished: the world population plummets to 0 with the disappearance).
  - The value comes from `stamp` ("2 DAYS"), and on screen the units come out in lowercase ("2 days").
  - With `stamp: null` on the neighboring scene, the panel leaves and returns with a 0.3 s fade.
- **HUD panel (`"panel_style": "hud"`, 2026-10-24; the mid-screen panel remains the default):** compact at the top left (x = 72, y = 216), over the sky, which is the cleanest background. Small label, thin line, stopwatch at 64 px and **2 to 3 data lines** (`panel_rows`: `[label, value]` or `[label, value, when 0 to 1]`; gray label, amber value right-aligned, 26 and 30 px). With the opening question on screen, only 2 lines (it starts at y = 470). Soft dark smudge behind it (no card border), because on a bright sky white and amber lost contrast. It enters last in the composition, above the title gradient (which was erasing it). Measured area: 3.1% of the screen with 3 data lines, against 4.6% for the mid-screen panel with time only. This is where the sourced fact appears when there is no narrator (format B). Tests: `build/_painel_teste/` (local). Limits: type must stay >= 26 px to read on a phone; the panel was checked on rendered frames, **not** on a real phone.
- **Keyword (`highlight`):** painted amber, no block.
- **End card (text format, `end_card`):** the sentence "What should I imagine next?" becomes a Vacuum card with the `end_card` sentence (Barlow SemiBold 62 px; `|` forces a line break) and the call in amber. With `"end_card": true`, the card shows only the question, in amber at 62 px, centered (humans-vanished, 2026-10-21). The panel disappears 0.3 s before the card enters.
- **Voice format:** captions in short chunks, Barlow 76 px, at the bottom (y = 1290). Exception (2026-10-23): in a bright scene (midday sky, snow, moonlight in the final call) the scene carries `"scrim": true` and the caption gets a soft dark gradient behind it (VOID at 40%, blurred), the same device as the cover title. Only in moon-disappeared for now (scenes 10, 11 and 12).
- **Clip style (Ifscape):** low-poly 3D, simple geometric shapes, flat matte colors, dark blue night with amber light (the brand palette). The camera stays POV at eye height; the overhead model-diorama view was rejected. Chosen on 2026-10-19 after seeing that the "what if" niche on Shorts is dominated by low-poly and that the realistic style (The If Engine) gets few views. The exact suffix is in the `style` of `scripts/moon-earth-gravity.json`.
- **Logo and avatar:** eclipsed sun (amber crescent) next to the IFSCAPE wordmark (still from identity D; revisit together with the new one if the owner asks).
- **Positions:** all respect the 9:16 safe zones. Nothing at the extreme top, at the bottom (caption and platform name) or in the strip of buttons on the right (x > 930).

Do not change the identity unless the owner asks.
