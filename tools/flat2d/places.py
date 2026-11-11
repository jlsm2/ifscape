"""Places of the technical floor plan, data only (final frame coordinates 1080x1920, no Pillow).

To add a place ('apartment'): copy a preset, swap the pieces and points and
check on a still (py -m ifscape flat2d scripts/<slug>.json --stills N). Drawing rules:
- everything that matters stays at x < 930 (strip of buttons on the right) and between y 540 and 1300 (the caption sits below,
  the clock above);
- 'rooms': lit rooms (floor warms when the light turns on); 'walls' is the room outline;
- 'doors': hinge, leaf length and closed/open angles in degrees (0 = right, 90 = down);
- 'windows': wall segment with glass (state closed/open/broken);
- 'points': named points for 'move', 'camera.focus' and the center of the infected;
- 'infected_spots': positions of the infected around the group's center, in the order they appear.
"""

PHARMACY = {
    "title": "PHARMACY · GROUND FLOOR",
    "title_xy": (100, 560),
    "rooms": [{"rect": (100, 640, 600, 1180), "light": "main"}],
    "rects": [                                  # prateleiras (contorno fino)
        (130, 680, 180, 840), (200, 680, 250, 840), (270, 680, 320, 840), (340, 680, 390, 840),
    ],
    "lines": [                                  # (x0, y0, x1, y1, color, width): counter and street
        (100, 900, 440, 900, "amb", 4),
        (650, 540, 650, 1300, "dim", 2),
        (905, 540, 905, 1300, "dim", 2),
    ],
    "dashes": [(778, 540, 778, 1300)],          # street center line
    "labels": [                                 # (x, y, texto, tamanho, cor)
        (130, 850, "SHELVES", 18, "dim"),
        (300, 910, "COUNTER", 18, "dim"),
        (668, 548, "MAIN ST", 24, "dim"),
    ],
    "doors": {
        "front": {"hinge": (600, 970), "length": 210, "closed": 90, "open": 180, "label": "DOOR",
                  "label_xy": (420, 1196), "state": "open"},
        "back": {"hinge": (100, 1060), "length": 90, "closed": 90, "open": 0, "label": "BACK",
                 "label_xy": (100, 1196), "state": "closed"},
    },
    "windows": {"shop": {"a": (600, 690), "b": (600, 900), "state": "closed", "label": "GLASS", "label_xy": (612, 700)}},
    "lights": {"main": [(240, 770), (470, 1000)]},
    "dims": [((100, 1240), (600, 1240), "12 m")],
    "points": {
        "center": (350, 1000), "aisle": (220, 1010), "shelves": (300, 790), "counter": (270, 950),
        "door": (540, 1075), "back": (160, 1110), "outside": (700, 1075), "street": (790, 960),
        "street_near": (745, 1075), "street_far": (790, 680), "window": (560, 795),
    },
    "sam": "aisle",
    "infected_center": "street",
    "infected_spots": [(0, 0), (-30, -50), (40, 45), (-60, -110), (-40, -15), (-70, 95), (60, -150),
                       (20, 125), (-20, -175), (55, -70), (-55, 50), (30, 190)],
}

STREET = {
    "title": "ELM ST · 2 BLOCKS",
    "title_xy": (100, 560),
    "rooms": [{"rect": (100, 640, 400, 900), "light": "shop"}, {"rect": (100, 1000, 400, 1260), "light": None}],
    "rects": [],
    "lines": [(470, 540, 470, 1300, "dim", 2), (860, 540, 860, 1300, "dim", 2)],
    "dashes": [(665, 540, 665, 1300)],
    "labels": [(112, 655, "DINER", 22, "dim"), (112, 1015, "LAUNDRY", 22, "dim"), (488, 548, "ELM ST", 24, "dim")],
    "doors": {"diner": {"hinge": (400, 760), "length": 90, "closed": 90, "open": 180, "label": "DINER",
                        "label_xy": (240, 912), "state": "closed"}},
    "windows": {},
    "lights": {"shop": [(250, 770)]},
    "dims": [((470, 1290), (860, 1290), "9 m")],
    "points": {"center": (665, 960), "diner": (360, 820), "corner": (520, 1240), "street": (665, 900),
               "street_far": (665, 640), "street_near": (600, 1150)},
    "sam": "corner",
    "infected_center": "street_far",
    "infected_spots": PHARMACY["infected_spots"],
}

BUSSTOP = {                                     # bus stop: pharmacy, sidewalk with the shelter and the street
    "title": "BUS STOP · OAK ST",
    "title_xy": (100, 560),
    "rooms": [{"rect": (100, 640, 420, 980), "light": "pharm"}],
    "rects": [(490, 1060, 520, 1180), (130, 680, 170, 800), (190, 680, 230, 800)],   # banco e prateleiras
    "lines": [
        (470, 1020, 470, 1220, "amb", 4),       # shelter: back and the two sides (open to the street)
        (470, 1020, 600, 1020, "amb", 4),
        (470, 1220, 600, 1220, "amb", 4),
        (640, 540, 640, 1300, "dim", 3),        # curb
        (905, 540, 905, 1300, "dim", 2),
    ],
    "dashes": [(772, 540, 772, 1300)],
    "labels": [
        (112, 940, "PHARMACY", 22, "dim"), (482, 1232, "BUS STOP", 20, "dim"), (452, 600, "SIDEWALK", 20, "dim"),
        (660, 548, "OAK ST", 24, "dim"),
    ],
    "doors": {"pharmacy": {"hinge": (420, 840), "length": 90, "closed": 90, "open": 0, "label": "DOOR",
                           "label_xy": (100, 996), "state": "closed"}},
    "windows": {"shop": {"a": (420, 670), "b": (420, 800), "state": "closed", "label": "GLASS", "label_xy": (430, 690)}},
    "lights": {"pharm": [(260, 840)]},
    "dims": [((420, 1270), (640, 1270), "4 m")],
    "points": {
        "center": (540, 960), "shelter": (545, 1120), "curb": (615, 1100), "street": (770, 1060),
        "pharmacy_door": (470, 885), "far": (790, 610), "inside": (260, 880), "sidewalk": (540, 900),
        "street_near": (720, 1200),
    },
    "sam": "shelter",
    "infected_center": "far",
    "infected_spots": PHARMACY["infected_spots"],
}

PLACES = {"pharmacy": PHARMACY, "street": STREET, "busstop": BUSSTOP}

# 'wide' shot (side view, drawing in sets.py): named points (x, y of the foot) of each set
WIDE_POINTS = {
    "pharmacy": {"door": (860, 1240), "counter": (605, 1240), "behind_counter": (340, 1240), "aisle": (200, 1240),
                 "center": (520, 1240), "outside": (1180, 1240), "back": (80, 1240), "stairs": (635, 1240)},
    "busstop": {"pharmacy_door": (330, 1240), "shelter": (760, 1240), "curb": (540, 1290), "street": (600, 1420),
                "far": (1010, 1240), "lamp": (470, 1240), "center": (540, 1240), "left": (-120, 1240),
                "right": (1200, 1240)},
    "frontdoor": {"door": (620, 1240), "lock": (740, 1240), "inside": (320, 1240), "back": (110, 1240),
                  "center": (540, 1240), "left": (-120, 1240)},
    "alley": {"door": (230, 1240), "pallet": (560, 1240), "dumpster": (380, 1240), "mouth": (900, 1240), "mid": (730, 1240),
              "center": (540, 1240), "left": (-120, 1240), "right": (1200, 1240), "back": (110, 1240)},
}
WIDE_SETS = tuple(WIDE_POINTS)
# door that opens in the 'wide' (`door` event): leaf box in the world (x0, y0, x1, y1); hinge on the left
WIDE_DOORS = {"alley": (40, 730, 220, 1240), "pharmacy": (40, 730, 220, 1240)}   # pharmacy: only with `door` in the scene (covers the left shelf)
# second pharmacy door (`door` event with `door: "stairs"`, flat `stairs`): the stairs to the pantry; the BACK is the exit to the alley
STAIRS_DOOR = {"pharmacy": (545, 730, 725, 1240)}
PILLS_X = 205                   # bag of medicine on the pharmacy counter (left side; the jugs start at 500)
KNOCK_ON = ("door", "counter")

DOOR_STATES = ("open", "closed", "locked")
WINDOW_STATES = ("closed", "open", "broken")
LIGHT_STATES = ("on", "off", "flicker", "lamp")   # lamp: only the headlamp (wide)
