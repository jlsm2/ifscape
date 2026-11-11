"""Landscape for the bacteria-disappeared script: terrain with a hillock, forest that yellows and loses its leaves,
cornfield, ocean on the horizon and the fertilizer factory in the distance.

Axes: house at the origin with the porch facing +y, barn to the north, pasture and hillock past the fence,
the terrain slopes down to the north until the sea (y ~ 600). The factory is to the east. What makes it read "ammonia
factory": spheres on legs, thin tall chimneys, the lit flare and the steam plumes.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import kit
from kit import flat

GRASS, FOREST_FLOOR, OCEAN = "#5E7F45", "#3F5A33", "#1C3557"
TRUNK, BRANCH = "#4A3A2A", "#5A4636"
GREEN, YELLOW, RUST, BARE = "#4F7D3B", "#D9A93A", "#C7652B", "#6B5E52"
CONIFER = "#24453A"
CORN, CORN_DRY = "#4E7A3A", "#B89A5A"
PLANT = "#1A2335"

FARM = (-45.0, 45.0, -25.0, 62.0)          # flat farm area (x0, x1, y0, y1)
KNOLL = (-22.0, 70.0, 16.0, 26.0)          # hillock: center x, y, height, radius (top above the canopies)
CORNFIELD = (16.0, 52.0, 6.0, 46.0)


def ground_z(x, y):
    """Terrain height: flat at the farm, hillock north of the pasture, hills sloping down to the sea."""
    kx, ky, kh, kr = KNOLL
    d = math.hypot(x - kx, y - ky)
    knoll = kh * max(0.0, 1 - (d / kr) ** 2) ** 1.5
    fx0, fx1, fy0, fy1 = FARM
    out = max(fx0 - x, x - fx1, fy0 - y, y - fy1, 0.0)            # distance outward from the farm
    fade = min(1.0, out / 40.0)
    rolling = 6 * math.sin(x * 0.021 + 1.3) * math.cos(y * 0.017) + 3 * math.sin(x * 0.05 + y * 0.04)
    descend = -min(30.0, max(0.0, y - fy1) * 0.055)               # slopes down to the north until the sea
    return knoll + fade * (rolling + descend)


def terrain(grass_mat):
    """A single grid, finer near the farm (3 m cells) and coarse far away (20 m cells)."""
    def axis(a0, a1, near0, near1):
        vals, v = [], a0
        while v < a1:
            vals.append(v)
            v += 3.0 if near0 <= v <= near1 else 20.0
        return vals + [a1]
    xs = axis(-700.0, 900.0, -70.0, 70.0)
    ys = axis(-150.0, 640.0, -40.0, 100.0)
    verts = [(x, y, ground_z(x, y)) for y in ys for x in xs]
    nx = len(xs)
    faces = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a, b = j * nx + i, j * nx + i + 1
            faces += [(a, b, b + nx), (a, b + nx, a + nx)] if (i + j) % 2 else [(a, b, a + nx), (b, b + nx, a + nx)]
    return kit.fix_normals(kit.mesh_object("Terrain", verts, faces, [grass_mat]))


def ocean():
    mat = flat("Ocean", OCEAN, rough=0.3, emission="#2C4F7A", strength=0.15)
    return kit.water_grid("Ocean", -1500, 1800, 560, 2600, -31.0, mat, cell=40.0, amp=0.3)


# ---------- trees ----------

def _canopy_geo(rnd, h, r):
    """Canopy of 2 to 3 wobbly, flattened icos (not a perfect ball)."""
    parts = []
    for k in range(rnd.choice((2, 3))):
        c = (rnd.uniform(-0.4, 0.4) * r, rnd.uniform(-0.4, 0.4) * r, h + rnd.uniform(-0.2, 0.5) * r)
        v, f = kit._ico_geo(r * rnd.uniform(0.75, 1.0), c, (1.0, rnd.uniform(0.85, 1.1), 0.8))
        v = [(x * rnd.uniform(0.9, 1.1), y * rnd.uniform(0.9, 1.1), z + rnd.uniform(-0.12, 0.12) * r) for x, y, z in v]
        parts.append((v, f))
    v, f, _ = kit.merge(*parts)
    return v, f


def _branches_geo(rnd, h):
    """Y-shaped branches hidden in the canopy: they show when the leaves fall."""
    parts = [kit.tube_geo([(0, 0, 0), (0, 0, h * 0.55)], (0.2, 0.13), n=6)]
    for k in range(4):
        a = k * math.pi / 2 + rnd.uniform(-0.4, 0.4)
        base = (0, 0, h * rnd.uniform(0.45, 0.6))
        mid = (math.cos(a) * h * 0.14, math.sin(a) * h * 0.14, h * 0.8)
        tip = (math.cos(a) * h * 0.21, math.sin(a) * h * 0.21, h * rnd.uniform(0.92, 1.0))
        parts.append(kit.tube_geo([base, mid, tip], (0.09, 0.05, 0.02), n=4))
        side = (mid[0] + math.cos(a + 1.2) * h * 0.1, mid[1] + math.sin(a + 1.2) * h * 0.1, h * 0.92)
        parts.append(kit.tube_geo([mid, side], (0.04, 0.015), n=4))
    v, f, _ = kit.merge(*parts)
    return v, f


def _conifer_geo(rnd, h):
    parts = [kit._prism_geo(6, 0.18, 0.12, h * 0.3)]
    for k, (r, z) in enumerate(((0.36, 0.22), (0.27, 0.45), (0.18, 0.66))):
        parts.append(kit._prism_geo(7, h * r, 0.0, h * 0.42, oz=h * z))
    v, f, owner = kit.merge(*parts)
    return v, f, [0 if o == 0 else 1 for o in owner]


def autumn_materials(count, rnd):
    """Canopy materials with animatable color (green -> yellow -> rust), each at its own pace."""
    mats = []
    for i in range(count):
        m = flat(f"Leaves{i}", GREEN, rough=0.95)
        mats.append(SimpleNamespace(mat=m, color=kit.principled(m).inputs["Base Color"], lag=rnd.uniform(0.0, 0.25)))
    return mats


def near_tree(name, xy, rnd, leaf_mats, trunk_mat):
    """Tree near the camera: branches (object) + canopy (object that shrinks when the leaves fall)."""
    h = rnd.uniform(5.0, 7.5)
    z = ground_z(*xy)
    v, f = _branches_geo(rnd, h)
    trunk = kit.mesh_object(name + "Trunk", v, f, [trunk_mat], (xy[0], xy[1], z))
    v, f = _canopy_geo(rnd, h * 0.88, h * 0.32)
    leaf = rnd.choice(leaf_mats)
    canopy = kit.mesh_object(name + "Canopy", v, f, [leaf.mat], (xy[0], xy[1], z))
    trunk.rotation_euler = canopy.rotation_euler = (0, 0, rnd.uniform(0, math.tau))
    return SimpleNamespace(trunk=trunk, canopy=canopy, leaf=leaf, height=h)


def far_forest(rnd, leaf_mats, trunk_mat, count=4000, keep_out=()):
    """Distant forest: one mesh per canopy material (few objects), plus the evergreen conifers."""
    groups = {i: [] for i in range(len(leaf_mats))}
    conifers = []
    placed = 0
    while placed < count:
        if rnd.random() < 0.7:
            x, y = rnd.uniform(-320, 320), rnd.uniform(70, 560)      # what is seen from the hillock
        else:
            x, y = rnd.uniform(-650, 850), rnd.uniform(-120, 560)
        if FARM[0] - 6 < x < FARM[1] + 6 and FARM[2] - 6 < y < FARM[3] + 6:
            continue
        if any(x0 < x < x1 and y0 < y < y1 for x0, x1, y0, y1 in keep_out):
            continue
        z = ground_z(x, y)
        h = rnd.uniform(6.0, 11.0)
        if rnd.random() < 0.15:
            v, f, owner = _conifer_geo(rnd, h)
            conifers.append(([(vx + x, vy + y, vz + z) for vx, vy, vz in v], f, owner))
        else:
            trunk = kit._prism_geo(5, 0.3, 0.2, h * 0.6)
            v, f = _canopy_geo(rnd, h * 0.85, h * 0.33)
            g, gf, owner = kit.merge(trunk, (v, f))
            groups[rnd.randrange(len(leaf_mats))].append(([(vx + x, vy + y, vz + z) for vx, vy, vz in g], gf, owner))
        placed += 1
    objs = []
    for i, items in groups.items():
        verts, faces, owner = kit.merge(*[(v, f) for v, f, _ in items])
        mats_idx = [o for _, _, own in items for o in own]
        objs.append(kit.mesh_object(f"Forest{i}", verts, faces, [trunk_mat, leaf_mats[i].mat], face_mats=mats_idx))
    verts, faces, _ = kit.merge(*[(v, f) for v, f, _ in conifers])
    con_idx = [o for _, _, own in conifers for o in own]
    objs.append(kit.mesh_object("Conifers", verts, faces, [trunk_mat, flat("Conifer", CONIFER)], face_mats=con_idx))
    return objs


def autumn(leaf_mats, f0, f_yellow, f_bare):
    """Each material: green until f0, yellow at f_yellow, rust and then gray-brown (no leaves) at f_bare."""
    for leaf in leaf_mats:
        lag = int(min(f_yellow - f0, f_bare - f_yellow) * leaf.lag)          # never goes past f_bare
        kit.key(leaf.color, "default_value", kit.lin(GREEN), 1)
        kit.key(leaf.color, "default_value", kit.lin(GREEN), f0 + lag)
        kit.key(leaf.color, "default_value", kit.lin(YELLOW), f_yellow + lag)
        kit.key(leaf.color, "default_value", kit.lin(RUST), (f_yellow + f_bare) // 2 + lag)
        kit.key(leaf.color, "default_value", kit.lin(BARE), f_bare)


# ---------- cornfield ----------

def _corn_leaf(rnd, px, py, z, length):
    """Corn leaf: wide ribbon that rises, arches and falls (it, not the stalk, makes it read as corn)."""
    a = rnd.uniform(0, math.tau)
    ux, uy = math.cos(a), math.sin(a)
    sx, sy = -uy * 0.05, ux * 0.05
    pts = [(0.0, 0.0), (0.35, 0.28), (0.7, 0.3), (1.0, 0.05)]
    verts = []
    for k, (t, up) in enumerate(pts):
        w = 1.0 - 0.8 * (k / (len(pts) - 1))
        cx, cy, cz = px + ux * t * length, py + uy * t * length, z + up * length
        verts += [(cx + sx * w, cy + sy * w, cz), (cx - sx * w, cy - sy * w, cz)]
    faces = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(len(pts) - 1)]
    return verts, faces


def cornfield(rnd, rows_spacing=0.9, plant_spacing=0.75):
    """Two meshes of corn plants (one yellows before the other, so the field is blotchy at the end)."""
    x0, x1, y0, y1 = CORNFIELD
    groups = ([], [])
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            h = rnd.uniform(1.9, 2.4)
            px, py = x + rnd.uniform(-0.12, 0.12), y + rnd.uniform(-0.12, 0.12)
            parts = [kit._prism_geo(4, 0.035, 0.02, h, ox=px, oy=py)]
            for k in range(6):
                parts.append(_corn_leaf(rnd, px, py, h * (0.22 + 0.11 * k), 0.75 - 0.06 * k))
            for k in range(4):                                                         # tassel
                a = rnd.uniform(0, math.tau)
                parts.append(kit.tube_geo([(px, py, h - 0.05), (px + math.cos(a) * 0.12, py + math.sin(a) * 0.12, h + 0.28)],
                                          (0.015, 0.006), n=3))
            v, f, _ = kit.merge(*parts)
            groups[0 if rnd.random() < 0.6 else 1].append((v, f))
            x += plant_spacing
        y += rows_spacing
    mats, objs = [], []
    for i, items in enumerate(groups):
        m = flat(f"Corn{i}", CORN, rough=0.9)
        mats.append(kit.principled(m).inputs["Base Color"])
        v, f, _ = kit.merge(*items)
        objs.append(kit.mesh_object(f"Corn{i}", v, f, [m]))
    return SimpleNamespace(objs=objs, colors=mats)


# ---------- fertilizer factory ----------

def fertilizer_plant(cx, cy, rnd):
    """Silhouette at ~500 m: ammonia spheres, prilling tower, chimneys, lit flare, racks and amber lights.
    Returns the plumes (objects that rise and grow) and the flame."""
    mat = flat("Plant", PLANT, rough=0.8)
    lamp = flat("PlantLamp", "#2A2410", emission=kit.LUZ, strength=8.0)
    z = ground_z(cx, cy)
    parts = []
    for i in range(3):
        sx, sy = cx - 60 + i * 24, cy - 30
        parts.append(kit._ico_geo(9.0, (sx, sy, z + 13.0)))
        for k in range(8):
            a = k * math.pi / 4
            parts.append(kit._prism_geo(4, 0.5, 0.5, 9.0, ox=sx + math.cos(a) * 7.5, oy=sy + math.sin(a) * 7.5, oz=z))
    parts.append(kit._prism_geo(10, 8.0, 7.5, 61.0, ox=cx + 10, oy=cy + 5, oz=z))                   # prilling tower
    parts.append(kit._box_geo(12, 12, 8, cx + 4, cy - 1, z + 61))
    for k, (dx, h) in enumerate(((-20, 50), (-14, 44), (28, 38))):
        parts.append(kit._prism_geo(8, 2.2, 1.8, h, ox=cx + dx, oy=cy + 20, oz=z))
    parts.append(kit._prism_geo(6, 1.0, 0.7, 70, ox=cx + 45, oy=cy + 30, oz=z))                      # flare
    for k in range(3):
        parts.append(kit._box_geo(80, 6, 1.0, cx - 40, cy + 40 + k * 0.01, z + 3 + k * 2.6))       # pipe rack
    for x in range(-40, 41, 10):
        parts.append(kit._box_geo(0.6, 6, 9, cx + x, cy + 40, z))
    parts.append(kit._box_geo(40, 24, 18, cx - 30, cy + 2, z))                                      # reformer shed
    v, f, _ = kit.merge(*parts)
    plant = kit.mesh_object("FertilizerPlant", v, f, [mat])
    lamps = []
    for _ in range(16):
        p = (cx + rnd.uniform(-60, 50), cy + rnd.uniform(-35, 45), z + rnd.uniform(4, 55))
        lamps.append(kit.mesh_object("PlantLamp", *kit._ico_geo(0.9, p)[:2], [lamp]))
    flame_mat, flame_power = kit.keyed_emission("Flame", "#F5A524", "#FFB347", 30.0)
    flame = kit.mesh_object("Flame", *kit._ico_geo(1.0, (0, 0, 0), (1.8, 1.8, 4.0))[:2], [flame_mat],
                            (cx + 45, cy + 30, z + 73))
    steam = flat("Steam", "#E6EBF2", rough=1.0, emission="#DDE3EC", strength=0.6)   # emissive: does not turn blue
    plumes = []
    for (dx, h) in ((-20, 50), (-14, 44), (28, 38), (10, 69)):
        for k in range(3):
            p = kit.mesh_object("Plume", *kit._ico_geo(1.0, (0, 0, 0), (1, 1, 0.8))[:2], [steam],
                                (cx + dx, cy + (20 if dx != 10 else 5), z + h + 2))
            plumes.append((p, k))
    return SimpleNamespace(plant=plant, lamps=lamps, flame=flame, flame_power=flame_power, plumes=plumes)


def animate_plumes(plumes, rnd, frames, period=90):
    """Each steam puff rises 30 m growing and dissipates; repeats with an offset (the steam never stops)."""
    for obj, k in plumes:
        base = obj.location.copy()
        f = 1 - int(period * k / 3) - rnd.randrange(10)
        while f < frames + period:
            drift = base + Vector((rnd.uniform(-6, 6), rnd.uniform(-3, 3), 30))
            for u, scale in ((0.0, 4.0), (0.7, 14.0), (1.0, 0.0)):
                fr = f + int(period * u) - (1 if u == 1.0 else 0)
                if fr < 1:
                    continue
                obj.location = base.lerp(drift, u)
                obj.scale = (scale, scale, scale * 0.8)
                obj.keyframe_insert("location", frame=fr)
                obj.keyframe_insert("scale", frame=fr)
            f += period
