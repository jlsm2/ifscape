""""Instrument" visual identity in 1080x1920 numbers.

Chosen among three directions, following the layout of the niche's viral videos:
question in the top third, panel with a number on the left in the middle of the screen, small sentence at the bottom
and a dark end card. Barlow font (DIN style, OFL license), mixed case, soft shadow in place of the
hard outline. Replaces identity D (Big Shoulders in caps with an outline).
"""

from pathlib import Path

W, H = 1080, 1920
FPS = 30

# Palette (the same as the brand)
VACUO = "#0B0F17"    # darkest background and text shadow
NEVOA = "#1B2333"    # background of the placeholder cards
LUZ = "#F5A524"      # amber: panel dot and keyword
TEXTO = "#F4F6F8"    # texto principal
QUIETO = "#8A94A6"   # secondary text

# Fonts (files in fonts/)
FONT_TEXT = "Barlow-Medium.ttf"                  # frases
FONT_BOLD = "Barlow-SemiBold.ttf"                # question, label, end card
FONT_NUMBER = "BarlowSemiCondensed-SemiBold.ttf"  # panel number
FONT_CLOCK = "JetBrainsMono[wght].ttf"           # panel stopwatch (counter with unit "clock"): mono, the digits do not jump
FONT_CLOCK_WEIGHT = 300                          # Light: thinner, fits "00:01.28" without looking heavy
FONT_FALLBACKS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"]

# Soft shadow (replaces the hard outline)
SHADOW_BLUR = 10
SHADOW_ALPHA = 0.6
SHADOW_OFFSET = 3

# Positions (9:16 safe zones: away from the top, the bottom and the buttons on the right)
STAMP_XY = (72, 860)            # live panel: on the left, in the middle of the screen (as in the viral videos)
HANDLE_XY = (72, 1440)
HANDLE_XY_SERIES = (748, 262)       # 2D series (panel: false): clock line, on the right; in close-ups the footer is the character's body
HANDLE_TEXT = "@ifscape_lab"
HANDLE_SIZE = 30

# Voice format: caption in short chunks, at the bottom
CAPTION_SIZE = 76
CAPTION_MAX_W = 820
CAPTION_CENTER_Y = 1290

# Text-only format
TEXT_HOOK_SIZE = 66             # opening question, in the top third
TEXT_HOOK_CENTER_Y = 560
TEXT_CAPTION_SIZE = 44          # narration sentence: small, at the bottom, one at a time
TEXT_CAPTION_MAX_W = 780        # ends before x = 930 (button strip)
TEXT_CAPTION_CENTER_Y = 1290
TEXT_FADE = 0.2

# Credit to the follower who asked for the topic ("Idea by @someone"), in the pause before the final question, above the caption
CREDIT_SIZE = 44
CREDIT_CENTER_Y = 1120         # room above the final question, which breaks into 2 lines

# 1-line end card (final_fact): the real fact written in small caps,
# in the pause before the final question; in the gap between the HUD (ends at y 556) and the side panel (starts at y 860).
FINAL_FACT_SIZE = 30
FINAL_FACT_MAX_W = 780
FINAL_FACT_CENTER_Y = 760

# Live panel
PANEL_W, PANEL_H = 900, 260
PANEL_LABEL_SIZE = 28
PANEL_VALUE_SIZE = 118
PANEL_SUB_SIZE = 34
PANEL_RULE_W = 380              # thin line under the label
PANEL_FPS = 15                  # frames per second of the number (the video stays at 30)
PANEL_ROLL = 0.6                # how long the number roll lasts on a time jump (s)
PANEL_FADE = 0.3                # panel fade in and out when the neighboring scene has no panel (s)

# HUD panel ("hud" style): compact at the top, on the left, over the sky (the cleanest
# background), with 2 to 3 data lines (label + amber value). With the opening question on screen, only 2 lines
# (the question starts at y = 470). Type big enough for a phone (>= 26 px).
HUD_XY = (72, 216)
HUD_W, HUD_H = 560, 340
HUD_LABEL_SIZE = 24
HUD_VALUE_SIZE = 64
HUD_ROW_LABEL_SIZE = 26
HUD_ROW_VALUE_SIZE = 30
HUD_ROW_H = 40
HUD_RULE_W = 360
HUD_MAX_ROWS = 3
HUD_MAX_ROWS_WITH_HOOK = 2

# Fact card (scene 'fact' field, backlog 0): amber number, one sentence and the source, on the left.
# Only with panel_style "hud" (the side panel takes that place). Ends before x = 930 (button strip).
FACT_XY = (72, 900)           # below the question (y 470 to 700), above the caption (y 1290)
FACT_XY_SIDE = (72, 520)      # side panel (default): the card sits at the top, with no opening question in the scene
FACT_W = 620
FACT_VALUE_SIZE = 64
FACT_TEXT_SIZE = 31
FACT_FADE = 0.25
FACT_MAX_CHARS = 110

# Karaoke caption (caption_style "karaoke", 2D series; approved design from style_v4.py): the
# spoken word in an amber box. Centered at y 1380 on the plan and on the card (the plan ends at ~1290); on the close-up, in the gap
# above Sam's head (KARAOKE_CLOSE_Y), so as not to cover face or body.
KARAOKE_SIZE = 84
KARAOKE_MAX_W = 780             # centered in 1080: from x 150 to 930 (button strip on the right); above that, 2 lines
KARAOKE_CENTER_Y = 1380
KARAOKE_CLOSE_Y = 560           # close-up: between the HUD (chip ends at y 406) and the top of the head (y 740), fits in 2 lines
KARAOKE_PAD_X = 14              # box margin to the sides of the word
KARAOKE_BOX = (56, 50)          # box: how far it extends up and down from the line center
KARAOKE_LINE_H = 112            # line height when the chunk breaks into 2
KARAOKE_RADIUS = 12
KARAOKE_STROKE = 6
KARAOKE_MARGIN = 12             # transparent border of the image
KARAOKE_HOLD = 0.25             # the box stays on the word this long after it ends; in a longer silence, it disappears

# End card (text format only): replaces the phrase "What should I imagine next?"
END_FACT_SIZE = 62
END_CTA_SIZE = 46

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
