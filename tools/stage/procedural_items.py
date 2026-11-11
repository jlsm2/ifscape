"""Catalog entries for the pieces made in code (tools/stage/procedural.py), with no file in assets/.

Pure Python: catalog_scan.py appends this list to catalog.json on every scan, and validate.py sees them
through the catalog itself. 'file' starts with 'procedural:' (there is nothing to import).
"""

ITEMS = [
    {"id": "boat", "file": "procedural:boat", "pack": "procedural/stage", "kind": "boat", "tags": ["boat", "water"],
     "height_m": 1.04, "size": [4.6, 1.56, 1.04], "tris": 420, "rigged": False, "actions": [], "materials": 6},
    {"id": "gull", "file": "procedural:gull", "pack": "procedural/stage", "kind": "bird", "tags": ["bird", "sea"],
     "height_m": 0.25, "size": [0.6, 1.4, 0.25], "tris": 60, "rigged": False, "actions": [], "materials": 3},
    {"id": "ice", "file": "procedural:ice", "pack": "procedural/stage", "kind": "ice", "tags": ["ice", "winter", "water"],
     "height_m": 0.09, "size": [220.0, 220.0, 0.09], "tris": 9000, "rigged": False, "actions": [], "materials": 2},
    {"id": "fish_dead", "file": "procedural:fish_dead", "pack": "procedural/stage", "kind": "fish", "tags": ["fish", "sea", "dead"], "height_m": 0.1, "size": [0.45, 0.1, 0.1], "tris": 60, "rigged": False, "actions": [], "materials": 4},
    {"id": "fish_live", "file": "procedural:fish_live", "pack": "procedural/stage", "kind": "fish", "tags": ["fish", "sea"], "height_m": 0.1, "size": [0.4, 0.1, 0.1], "tris": 60, "rigged": False, "actions": [], "materials": 4},
    {"id": "ant", "file": "procedural:ant", "pack": "procedural/stage", "kind": "insect", "tags": ["insect", "ant"],
     "height_m": 0.51, "size": [2.1, 1.7, 0.51], "tris": 2400, "rigged": True,
     "actions": ["Idle", "Walk", "Run", "Rise", "Tremble", "Sag", "SagIdle"], "materials": 6},
    {"id": "anthill", "file": "procedural:anthill", "pack": "procedural/stage", "kind": "anthill", "tags": ["soil", "ant"],
     "height_m": 0.48, "size": [1.6, 1.6, 0.48], "tris": 700, "rigged": False, "actions": [], "materials": 5},
    {"id": "antnest", "file": "procedural:antnest", "pack": "procedural/stage", "kind": "anthill", "tags": ["soil", "ant", "macro"],
     "height_m": 0.03, "size": [0.25, 0.25, 0.03], "tris": 15000, "rigged": False, "actions": [], "materials": 8},
    {"id": "blanket", "file": "procedural:blanket", "pack": "procedural/stage", "kind": "picnic", "tags": ["picnic", "park"],
     "height_m": 0.05, "size": [2.0, 1.5, 0.05], "tris": 700, "rigged": False, "actions": [], "materials": 6},
    {"id": "basket", "file": "procedural:basket", "pack": "procedural/stage", "kind": "picnic", "tags": ["picnic", "park"],
     "height_m": 0.46, "size": [0.5, 0.33, 0.46], "tris": 120, "rigged": False, "actions": [], "materials": 3},
    {"id": "cooler", "file": "procedural:cooler", "pack": "procedural/stage", "kind": "picnic", "tags": ["picnic", "park", "seat"],
     "height_m": 0.36, "size": [0.6, 0.38, 0.36], "tris": 50, "rigged": False, "actions": [], "materials": 2},
    {"id": "bench", "file": "procedural:bench", "pack": "procedural/stage", "kind": "furniture", "tags": ["park", "seat"],
     "height_m": 0.9, "size": [1.8, 0.5, 0.9], "tris": 300, "rigged": False, "actions": [], "materials": 2},
    {"id": "turf", "file": "procedural:turf", "pack": "procedural/stage", "kind": "ground-detail", "tags": ["grass", "macro"],
     "height_m": 0.07, "size": [2.4, 2.4, 0.07], "tris": 9000, "rigged": False, "actions": [], "materials": 6},
    {"id": "crumbs", "file": "procedural:crumbs", "pack": "procedural/stage", "kind": "picnic", "tags": ["picnic", "macro"],
     "height_m": 0.01, "size": [0.5, 0.5, 0.01], "tris": 200, "rigged": False, "actions": [], "materials": 2},
    {"id": "scale", "file": "procedural:scale", "pack": "procedural/stage", "kind": "furniture", "tags": ["bathroom", "scale"],
     "height_m": 0.053, "size": [0.34, 0.3, 0.053], "tris": 120, "rigged": False, "actions": [], "materials": 4},
    {"id": "foam", "file": "procedural:foam", "pack": "procedural/stage", "kind": "foam", "tags": ["water", "foam"], "height_m": 0.01, "size": [1.0, 1.0, 0.01], "tris": 9, "rigged": False, "actions": [], "materials": 1},
]
