"""The street a year later (technology-disappeared, scenes 09 to 12): the broken asphalt became garden beds, grass
in the cracks of the sidewalks, piles of asphalt slabs at the curb, a dirt path in the middle for the cart.

Proportions: raised bed 1.2 to 1.5 m wide, 20 to 30 cm high, free length; cabbage and
lettuce 25 to 40 cm; corn and beans on stakes up to 1.8 m. Low-poly reference: Kenney "Nature Kit" (crop_*,
plants in few facets) and the gardens of Quaternius "Farm Pack".
All together in few meshes (one per material): light to render.
"""

import math
import random

import kit
import town_set as ts
from town_set import Geo, mat

PATH_HALF = 1.6                    # dirt path in the middle (cart)
BEDS_X = ((-6.2, -3.4), (-3.1, -1.8), (1.8, 3.1), (3.4, 6.2))


def _plant_geo(rnd, x, y, z, kind):
    if kind == "cabbage":
        r = rnd.uniform(0.16, 0.22)
        return [kit._ico_geo(1.0, (x, y, z + r * 0.6), (r, r, r * 0.75))], 0
    if kind == "leafy":
        parts = []
        for k in range(5):
            a = 2 * math.pi * k / 5 + rnd.uniform(-0.3, 0.3)
            parts.append(kit.tube_geo([(x, y, z), (x + 0.22 * math.cos(a), y + 0.22 * math.sin(a), z + 0.28)],
                                      [0.05, 0.02], n=3, squash=0.4))
        return parts, 1
    h = rnd.uniform(1.2, 1.7)
    parts = [kit.tube_geo([(x, y, z), (x, y, z + h)], [0.03, 0.02], n=4)]
    for k in range(4):
        zz = z + h * (0.3 + 0.17 * k)
        a = rnd.uniform(0, 6.28)
        parts.append(kit.tube_geo([(x, y, zz), (x + 0.32 * math.cos(a), y + 0.32 * math.sin(a), zz + 0.12)],
                                  [0.05, 0.015], n=3, squash=0.3))
    return parts, 2


def beds(rnd):
    """Beds along the main street and the cross street. Returns the list of objects."""
    wood, soil = mat("BedWood", "#7A5A3A"), mat("Soil", "#3E2E22")
    dirt = mat("Dirt", "#6B5440")
    g = Geo()
    plants = {0: [], 1: [], 2: []}
    spans = [(-70.0, ts.CROSS_Y - ts.CROSS_HALF - 1.0), (ts.CROSS_Y + ts.CROSS_HALF + 1.0, 140.0)]
    g.box(-ts.ROAD_HALF, ts.ROAD_HALF, -80, 150, 0.0, 0.03, dirt)   # all the asphalt became dirt
    for y0, y1 in spans:
        y = y0
        while y < y1 - 3:
            L = min(rnd.uniform(5.0, 7.5), y1 - y)
            for xa, xb in BEDS_X:
                g.box(xa, xb, y, y + L, 0.0, 0.26, wood)
                g.box(xa + 0.06, xb - 0.06, y + 0.06, y + L - 0.06, 0.26, 0.29, soil)
                kind = rnd.choice(("cabbage", "cabbage", "leafy", "corn") if y > 50 else ("cabbage", "leafy"))
                rows = max(1, int((xb - xa) / 0.5))
                for i in range(rows):
                    px = xa + (xb - xa) * (i + 0.5) / rows
                    py = y + 0.35
                    while py < y + L - 0.3:
                        if rnd.random() < 0.85:
                            parts, m = _plant_geo(rnd, px + rnd.uniform(-0.05, 0.05), py, 0.29, kind)
                            plants[m] += parts
                        py += 0.55 if kind != "corn" else 0.6
            y += L + 0.6
    for x0, x1 in ((-60, -ts.ROAD_HALF - 4), (ts.ROAD_HALF + 4, 60)):              # cross street too
        for y in (ts.CROSS_Y - 4.5, ts.CROSS_Y + 1.5):
            g.box(x0, x1, y, y + 3.0, 0.0, 0.26, wood)
            g.box(x0 + 0.06, x1 - 0.06, y + 0.06, y + 2.94, 0.26, 0.29, soil)
            for px in range(int(x0) + 1, int(x1), 1):
                parts, m = _plant_geo(rnd, px + 0.3, y + 1.5, 0.29, "cabbage" if px % 3 else "leafy")
                plants[m] += parts
    out = [g.build("Beds")]
    colors = (("Cabbage", "#5E8C46"), ("Leafy", "#7AA04E"), ("Corn", "#4C7A3E"))
    for k, parts in plants.items():
        if parts:
            v, f, _ = kit.merge(*parts)
            o = kit.mesh_object(f"Plants{colors[k][0]}", v, f, [mat(f"Plant{colors[k][0]}", colors[k][1])])
            out.append(kit.fix_normals(o))
    return out


def overgrowth(rnd):
    """Grass in the cracks of the sidewalks and the path (tufts of blades 3+ cm wide) and piles of asphalt slabs
    torn up next to the curb."""
    grass = mat("CrackGrass", "#6E8A3E")
    parts = []
    for s in (1, -1):
        for _ in range(70):
            y = rnd.uniform(-60, 140)
            x = s * rnd.uniform(ts.ROAD_HALF + 0.3, ts.FRONT - 0.3)
            dx, dy = rnd.uniform(-0.4, 0.4), rnd.uniform(-1.4, 1.4)
            for k in range(6):
                u = k / 5
                bx, by = x + dx * u, y + dy * u
                for b in range(3):
                    a = rnd.uniform(0, 6.28)
                    h = rnd.uniform(0.12, 0.3)
                    parts.append(kit.tube_geo([(bx, by, 0.15), (bx + 0.08 * math.cos(a), by + 0.08 * math.sin(a), 0.15 + h)],
                                              [0.03, 0.012], n=3, squash=0.5))
    v, f, _ = kit.merge(*parts)
    tufts = kit.fix_normals(kit.mesh_object("CrackGrass", v, f, [grass]))
    slab = mat("BrokenAsphalt", "#2C313C")
    g = Geo()
    for _ in range(45):
        y = rnd.uniform(-60, 140)
        if abs(y - ts.CROSS_Y) < ts.CROSS_HALF + 2:
            continue
        s = rnd.choice((1, -1))
        x = s * rnd.uniform(ts.ROAD_HALF + 0.35, ts.ROAD_HALF + 0.9)
        for k in range(rnd.randint(2, 4)):
            w, l = rnd.uniform(0.4, 0.8), rnd.uniform(0.5, 1.0)
            v, f = kit._box_geo(w, l, 0.08, -w / 2, -l / 2, 0.0)
            ang = rnd.uniform(0, 6.28)
            tilt = rnd.uniform(-0.25, 0.25)
            v = [(x + vx * math.cos(ang) - vy * math.sin(ang), y + vx * math.sin(ang) + vy * math.cos(ang),
                  0.17 + 0.08 * k + vz + vx * tilt) for vx, vy, vz in v]
            g.add((v, f), slab)
    return [tufts, g.build("AsphaltSlabs")]


def build(rnd):
    return beds(rnd) + overgrowth(rnd)
