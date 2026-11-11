"""The series cast ('cast' at the top of the script), data only and no Pillow (script.py validates on load).

    "cast": {"rosa": {"name": "ROSA", "skin": "#c68e64", "hair": {"color": "#2a1d17", "style": "long"},
                      "shirt": "#4f7a6a", "coat": false, "accessory": "scarf", "marker": "#7fc8a9"}}

Colors: "#rrggbb", [r, g, b] or a name from the NAMES table. 'hair' accepts the color alone, the color with 'hair_style'
beside it, or {color, style}. Extra fields (optional): 'pants' (in the 'wide' shot) and 'collar'.
Each character must be recognizable in 1 s by silhouette (hair, lab coat, accessory) and by color.
"""

HAIR_STYLES = ("short", "long", "bald", "grey")
ACCESSORIES = ("headlamp", "bandage", "scarf", "glasses", "none")
CAST_KEYS = {"name", "skin", "hair", "hair_style", "shirt", "coat", "accessory", "marker", "pants", "collar"}

NAMES = {
    "amber": (245, 165, 36), "white": (232, 234, 230), "black": (30, 30, 34), "grey": (150, 154, 160),
    "gray": (150, 154, 160), "brown": (92, 62, 44), "dark_brown": (52, 38, 30), "blonde": (196, 160, 96),
    "auburn": (120, 62, 40), "navy": (40, 58, 96), "blue": (62, 104, 150), "teal": (52, 120, 118),
    "green": (74, 120, 84), "olive": (104, 108, 64), "mustard": (190, 150, 50), "maroon": (110, 46, 50),
    "rust": (156, 82, 46), "purple": (98, 74, 128), "beige": (200, 184, 156), "cream": (226, 222, 210),
    "skin_light": (232, 196, 164), "skin_medium": (214, 168, 128), "skin_tan": (190, 140, 100),
    "skin_brown": (150, 100, 70), "skin_dark": (104, 70, 50),
}

# the approved prototype's Sam (close.py before the cast): without 'cast', the close comes out identical to before
SAM = {"name": "SAM", "skin": (214, 168, 128), "hair": (52, 38, 30), "hair_style": "short",
       "shirt": (226, 222, 210), "collar": (62, 104, 150), "coat": False, "accessory": "headlamp",
       "marker": (245, 165, 36), "pants": (44, 50, 64)}
EXTRA = {"name": "", "skin": (196, 160, 128), "hair": (70, 66, 64), "hair_style": "short",
         "shirt": (108, 114, 126), "coat": False, "accessory": "none", "marker": (138, 148, 166),
         "pants": (44, 48, 58)}              # extra ('people') and full-body infected without a cast
GREY_HAIR = (168, 170, 172)
COAT = (232, 234, 230)


def color(value, where: str) -> tuple:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in NAMES:
            return NAMES[v]
        h = v.lstrip("#")
        if len(h) == 6 and all(c in "0123456789abcdef" for c in h):
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    if isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in value):
        return tuple(value)
    raise ValueError(f"{where}: color '{value}' (use \"#rrggbb\", [r, g, b] or a name: {', '.join(sorted(NAMES))})")


def _darker(c: tuple, k: float = 0.62) -> tuple:
    return tuple(int(v * k) for v in c)


def normalize(cid: str, raw: dict) -> dict:
    """One cast character with all fields resolved (colors as tuples)."""
    where = f"cast.{cid}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be an object {{name, skin, hair, shirt, coat, accessory, marker}}")
    extra = sorted(k for k in raw if k not in CAST_KEYS and not str(k).startswith("_"))
    if extra:
        raise ValueError(f"{where}: unknown field(s) {extra} (accepts {sorted(CAST_KEYS)})")
    base = dict(SAM if cid == "sam" else EXTRA)
    if cid != "sam":
        base["accessory"] = "none"
    look = dict(base)
    look["name"] = str(raw.get("name", cid)).strip().upper()
    if not look["name"] or len(look["name"]) > 10:
        raise ValueError(f"{where}: 'name' of 1 to 10 characters (it is the label on the floor plan)")
    for k in ("skin", "shirt", "marker", "pants", "collar"):
        if k in raw:
            look[k] = color(raw[k], f"{where}.{k}")
    hair = raw.get("hair")
    style = raw.get("hair_style")
    if isinstance(hair, dict):
        bad = sorted(set(hair) - {"color", "style"})
        if bad:
            raise ValueError(f"{where}.hair: accepts only 'color' and 'style' (got {bad})")
        style = hair.get("style", style)
        hair = hair.get("color")
    if style is not None:
        if style not in HAIR_STYLES:
            raise ValueError(f"{where}: hair style '{style}' (valid: {', '.join(HAIR_STYLES)})")
        look["hair_style"] = style
    if hair is not None:
        look["hair"] = color(hair, f"{where}.hair")
    elif look["hair_style"] == "grey":
        look["hair"] = GREY_HAIR
    if not isinstance(raw.get("coat", False), bool):
        raise ValueError(f"{where}: 'coat' is true (lab coat) or false")
    look["coat"] = raw.get("coat", base["coat"])
    acc = raw.get("accessory", look["accessory"]) or "none"
    if acc not in ACCESSORIES:
        raise ValueError(f"{where}: 'accessory' '{acc}' (vale: {', '.join(ACCESSORIES)})")
    look["accessory"] = acc
    if "collar" not in raw and ("shirt" in raw or look["coat"]):
        # collar: with a lab coat the shirt shows underneath; without one, the shirt itself, darker
        look["collar"] = look["shirt"] if look["coat"] else _darker(look["shirt"])
    if "marker" not in raw and cid != "sam":
        look["marker"] = tuple(min(255, int(v * 1.25) + 20) for v in look["shirt"])
    look["body"] = COAT if look["coat"] else look["shirt"]
    look["id"] = cid
    return look


def check(raw) -> dict:
    """The whole 'cast': {id: character}. Returns the resolved characters."""
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not raw:
        raise ValueError("'cast' is an object {id: {name, skin, hair, shirt, coat, accessory, marker}}")
    out = {}
    for cid, look in raw.items():
        if not str(cid).replace("_", "").isalnum():
            raise ValueError(f"cast: id '{cid}' only with letters, digits and _")
        out[str(cid)] = normalize(str(cid), look)
    return out


def look_for(cast: dict | None, cid: str, kind: str = "") -> dict:
    """Look of an actor: from the cast; Sam without a cast is the prototype's; the rest is an extra."""
    cast = cast or {}
    if cid in cast:
        return cast[cid]
    if cid == "sam" or kind == "sam":
        return {**SAM, "body": SAM["shirt"], "id": "sam"}
    return {**EXTRA, "body": EXTRA["shirt"], "id": cid}
