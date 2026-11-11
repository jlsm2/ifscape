"""2D "Live Floor Plan" system: amber technical floor plan on Vacuum, Sam close-up and card.

Approved prototype: style_v3.py (direction A + the closes from C).
Modules: common (palette, fonts, easing), places (places by preset, data only), tracks (timeline of the
states), plan/close/card (one per shot type), hud (clock and chip, isolated so the drawing can be swapped),
engine (builds the scene frame by frame) and validate (checks the script's 'flat' field, without Pillow).
The backend that writes clips/<slug>/<id>.mp4 is ifscape/flat2d.py.
"""
