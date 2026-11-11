"""Umbrella thorn acacia (Vachellia tortilis), low-poly: old with a flat crown, and young, both procedural.

SOURCE: procedural (Ifscape, viruses-disappeared, 2026-10-24).
Proportions (https://en.wikipedia.org/wiki/Vachellia_tortilis; direction.md §4): old 6–10 m, flat crown ~1.5x the
height in width; short trunk (1.5–2.5 m) that opens into 3–5 limbs inclined 35–50° up to the "table" crown;
young 1.5–3 m, smaller and rounder crown. Low-poly references: Quaternius "Ultimate Nature" (crown in flattened
masses), Kenney Nature Kit (chamfered trunk). Crown in 3 layers with gaps of sky (art.md §2: #5C6E3A old,
#6E8A40 young, trunk #4A3E34).

Usage: old(name, location, mats, rnd, height=8.0), young(name, location, mats, rnd, height=2.4).
mats = {"trunk": mat, "crown": mat}. Origin at the base; the crown is a child object ("<name>Crown") for the wind.
"""

import math

from mathutils import Vector

import kit


def _pad(r, center, rnd, flat=0.2):
    v, f = kit._ico_geo(r, center, (1.0, rnd.uniform(0.75, 1.0), flat))
    c = Vector(center)
    out = []
    for p in v:
        d = Vector(p) - c
        k = 1.0 + rnd.uniform(-0.16, 0.16)
        out.append(tuple(c + Vector((d.x * k, d.y * k, d.z * (1.0 + rnd.uniform(-0.3, 0.3))))))
    return out, f


def _limbs(rnd, n, trunk_h, top_h, spread, r0, r1, lean=(35, 50)):
    """Limbs: from the top of the trunk upward and outward; returns geometries and the tips (for the crown)."""
    geos, tips = [], []
    base_a = rnd.uniform(0, 2 * math.pi)
    for j in range(n):
        a = base_a + 2 * math.pi * j / n + rnd.uniform(-0.35, 0.35)
        tilt = math.radians(rnd.uniform(*lean))
        reach = spread * rnd.uniform(0.55, 0.85)
        h = top_h - trunk_h
        mid = (math.cos(a) * reach * 0.45, math.sin(a) * reach * 0.45, trunk_h + h * 0.5 + rnd.uniform(-0.2, 0.2))
        tip = (math.cos(a) * reach, math.sin(a) * reach, top_h - rnd.uniform(0.1, 0.5) * h * 0.2)
        geos.append(kit.tube_geo([(0, 0, trunk_h * 0.92), mid, tip], [r0, (r0 + r1) / 2, r1], n=6))
        # secondary branch
        a2 = a + rnd.choice((-1, 1)) * rnd.uniform(0.5, 0.9)
        tip2 = (mid[0] + math.cos(a2) * reach * 0.45, mid[1] + math.sin(a2) * reach * 0.45, top_h - h * 0.1)
        geos.append(kit.tube_geo([mid, tip2], [r1 * 1.2, r1 * 0.6], n=5))
        tips += [tip, tip2]
        del tilt
    return geos, tips


def _crown(name, mats, rnd, tips, width, top_h, layers=3, pads=12, flat=0.2, parent=None, pad_r=(0.22, 0.34)):
    geos = []
    R = width / 2
    for k in range(pads):
        # mosaic: points in a disc, with gaps (rejects points too close together)
        a = rnd.uniform(0, 2 * math.pi)
        d = R * math.sqrt(rnd.uniform(0.0, 1.0)) * 0.78
        layer = k % layers
        z = top_h + (layer - (layers - 1) / 2) * width * 0.045 + rnd.uniform(-0.05, 0.05) * width * 0.1
        r = width * rnd.uniform(*pad_r)
        geos.append(_pad(r, (math.cos(a) * d, math.sin(a) * d, z), rnd, flat))
    for t in tips[: max(2, len(tips) // 2)]:
        geos.append(_pad(width * rnd.uniform(0.18, 0.24), (t[0], t[1], top_h + width * 0.02), rnd, flat))
    v, f, _ = kit.merge(*geos)
    o = kit.mesh_object(f"{name}Crown", v, f, [mats["crown"]])
    for p in o.data.polygons:
        p.use_smooth = False
    if parent is not None:
        o.parent = parent
    return o


def old(name, location, mats, rnd, height=8.0, width=None):
    """Old acacia: short thick trunk, 4–5 limbs, wide flat crown (~1.5x the height) in 3 layers."""
    width = width or height * 1.5
    trunk_h = height * 0.25
    top = height * 0.86
    geos = [kit.tube_geo([(0, 0, -0.2), (0.05, 0.03, trunk_h * 0.6), (0.0, 0.0, trunk_h)],
                         [height * 0.042, height * 0.035, height * 0.03], n=7)]
    g, tips = _limbs(rnd, rnd.choice((4, 5)), trunk_h, top, width / 2, height * 0.024, height * 0.01)
    geos += g
    v, f, _ = kit.merge(*geos)
    trunk = kit.mesh_object(name, v, f, [mats["trunk"]], location)
    for p in trunk.data.polygons:
        p.use_smooth = False
    crown = _crown(name, mats, rnd, tips, width, top + height * 0.04, layers=3, pads=13, flat=0.16, parent=trunk)
    return trunk, crown


def young(name, location, mats, rnd, height=2.4):
    """Young acacia: the same "table" as the old one in miniature (it rhymes with it: reads as "young acacia"), thin trunk (>= 8 px at
    8 m: ~6 cm) that forks low, 2–3 open branches, flat crown ~0.9x the height in 4–5 tufts with gaps."""
    width = height * rnd.uniform(0.85, 1.0)
    trunk_h = height * 0.32
    top = height * 0.86
    geos = [kit.tube_geo([(0, 0, -0.05), (0.03, 0.01, trunk_h * 0.6), (0.0, 0.02, trunk_h)], [0.035, 0.03, 0.026], n=6)]
    g, tips = _limbs(rnd, rnd.choice((2, 3)), trunk_h, top, width / 2, 0.022, 0.01, lean=(30, 45))
    geos += g
    v, f, _ = kit.merge(*geos)
    trunk = kit.mesh_object(name, v, f, [mats["trunk"]], location)
    for p in trunk.data.polygons:
        p.use_smooth = False
    crown = _crown(name, mats, rnd, tips, width, top, layers=2, pads=5, flat=0.28, parent=trunk,
                   pad_r=(0.2, 0.28))
    return trunk, crown
