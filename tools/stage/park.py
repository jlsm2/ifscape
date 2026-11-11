"""'park' stage: neighborhood city park surrounded by buildings (ants-human-size v2).

Plan (meters; POV camera at [0, 0] looking +y; the ground of the lawn and the paths sits at z = 0):
- LAWN x -34..34, y -26..46, enclosed by a low hedge (0.9 m) with openings at the paths.
  Foreground (y 2..12, |x| < 8) stays FREE for the script: picnic blanket, anthill, ant, witness.
- PATH A (gravel, 3 m): horizontal at y = 17, end to end. Benches on the back edge (seat at y = 19.0,
  facing the camera, at x = -22, -10, 14, 24), trash cans beside them, lamp posts on the front edge (y = 15.2).
- PATH B: vertical at x = 6, from y = 17 to the back gate (y = 46); in the middle, the round PLAZA (center [6, 31],
  radius 6) with a fountain (5 m) and a ring flower bed; 2 benches in the plaza. PATH D: horizontal at y = 31 from the
  plaza to the left edge.
- Trees (Quaternius commontree, green): alley behind the benches, plaza ring, groups on the sides and in the back,
  street trees on the outer sidewalk.
- SURROUNDINGS: 3 m sidewalk, 8 m street with a dashed line and parked cars, outer sidewalk, and 3 layers of
  buildings: a row of low Kenney City Kit Commercial buildings facing the park (13 to 25 m, facades
  white, beige or brick through the variation textures), towers behind (30 to 55 m) and the horizon of simple blocks
  (40 to 90 m) out to ~320 m, which the distance mist erases.
Seats for whoever sits with 'Sitting' (the Quaternius hip sits at 0.36 m, 0.2 m behind the root):
person at BENCH_SEATS[i] with "z": 0.06 and "face" 270 (looks at the camera).

Sources: Kenney City Kit Commercial / Suburban / Roads and Food Kit (CC0, assets/LICENSES.md); real reference:
neighborhood plaza surrounded by 4 to 8-story buildings (Bryant Park, New York, and Parque da Jaqueira, Recife:
central lawn, alley of trees, benches facing the lawn, black lamp posts, facades right after the street).
"""

import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import kit  # noqa: E402

import models  # noqa: E402

LAWN = (-34.0, 34.0, -26.0, 46.0)          # x0, x1, y0, y1 of the lawn
WALK = 3.0                                  # inner sidewalk (between the hedge and the street)
ROAD = 8.0
OUTER = 3.5                                 # outer sidewalk (before the buildings)
PATH_A_Y, PATH_B_X, PATH_D_Y = 17.0, 6.0, 31.0
PATH_S_Y = -16.0                            # south path (behind the POV camera): benches facing north
PLAZA = (6.0, 31.0, 6.0)
PATH_W = 3.0
BENCH_SEATS = [(-17.0, 19.0), (-4.5, 19.0), (2.2, 19.0), (10.5, 19.0), (21.0, 19.0)]   # center of the seat, facing -y
SOUTH_SEATS = [(-20.0, -18.0), (-8.0, -18.0), (9.0, -18.0), (20.0, -18.0)]   # facing +y
PLAZA_BENCHES = [(-0.9, 31.0 + 3.6, 0.0), (12.9, 31.0 - 3.6, 0.0)]
LAMPS_AT = [(-28.0, 15.2), (-17.0, 15.2), (-8.5, 15.2), (12.5, 15.2), (24.0, 15.2), (1.6, 26.6), (10.4, 35.4),
            (-26.0, -14.2), (-2.0, -14.2), (15.0, -14.2)]
FRONT_FREE = (-8.0, 8.0, 1.0, 13.0)          # foreground free for the script (nothing of the stage spawns here)
VARIANTS = ("", "variation-a", "variation-b")
CITY = Path(models.ASSETS) / "kenney" / "city-kit-commercial" / "Models"
FACTOR = 10.0                                # 1 City Kit unit = 10 m (walking ~3.2 m)
LAMPS = []                                   # park lamp posts (procedural.LAMPS receives these too)


def on_lawn(x, y, pad=0.0):
    """Free lawn (outside paths, plaza and the hedge strip): where the grass may spawn."""
    x0, x1, y0, y1 = LAWN
    if not (x0 + 1.0 + pad < x < x1 - 1.0 - pad and y0 + 1.0 + pad < y < y1 - 1.0 - pad):
        return False
    if abs(y - PATH_A_Y) < PATH_W / 2 + 0.25 + pad or abs(y - PATH_S_Y) < PATH_W / 2 + 0.25 + pad:
        return False
    if abs(x - PATH_B_X) < PATH_W / 2 + 0.25 + pad and y > PATH_A_Y:
        return False
    if abs(y - PATH_D_Y) < PATH_W / 2 + 0.25 + pad and x < PLAZA[0]:
        return False
    if math.hypot(x - PLAZA[0], y - PLAZA[1]) < PLAZA[2] + 0.3 + pad:
        return False
    return True


def _mat(name, hexa, rough=0.9, spec=0.15):
    m = kit.flat(name, hexa, rough=rough)
    p = kit.principled(m)
    if "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value = spec
    return m


def _mesh(name, parts, mats, coll, location=(0, 0, 0)):
    import procedural
    return procedural._mesh(name, parts, mats, coll, location)


def _box(x0, x1, y0, y1, z0, z1):
    import procedural
    return procedural._box(x0, x1, y0, y1, z0, z1)


def _cyl(n, r0, r1, z0, z1, cx=0.0, cy=0.0, rot=0.0):
    import procedural
    return procedural._cyl(n, r0, r1, z0, z1, cx, cy, rot)


def _ring(n, r0, r1, z, cx, cy):
    """Flat ring (crown) of n segments in z."""
    v = [(cx + r * math.cos(math.tau * i / n), cy + r * math.sin(math.tau * i / n), z) for r in (r0, r1) for i in range(n)]
    f = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def _disc(n, r, z, cx, cy):
    v = [(cx, cy, z)] + [(cx + r * math.cos(math.tau * i / n), cy + r * math.sin(math.tau * i / n), z) for i in range(n)]
    f = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    return v, f


# ---------- ground ----------

def _lawn(coll, rng):
    """Lawn on a 0.5 m grid with per-vertex color: wide patches, medium patches (1 to 2 m) and mower stripes
    of 3 m along y (light and dark, like a trimmed park lawn). Flush with the sidewalk (z = 0)."""
    x0, x1, y0, y1 = LAWN
    step = 0.5
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((x0 + i * step, y0 + j * step, 0.0))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    mat = _mat("park_lawn", "#6E9A4C", rough=1.0, spec=0.05)
    nt = mat.node_tree
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    nt.links.new(attr.outputs["Color"], kit.principled(mat).inputs["Base Color"])
    obj = kit.mesh_object("park_lawn", verts, faces, [mat], face_mats=[0] * len(faces))
    lo, hi = kit.lin("#56803A"), kit.lin("#82AE58")
    cols = obj.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    flat = []
    for (x, y, _z) in verts:
        t = 0.5 + 0.22 * (math.sin(x * 0.21 + 1.7) * math.cos(y * 0.17) + 0.6 * math.sin(x * 0.07 - y * 0.09 + 0.6))
        t += 0.16 * math.sin(x * 1.9 + y * 0.8 + 0.3) * math.cos(y * 1.6 - x * 0.5)          # patches of 1 to 2 m
        t = min(1.0, max(0.0, t + rng.uniform(-0.07, 0.07)))
        stripe = 1.1 if int((x + 2.0 - x0) // 4.0) % 2 else 0.91                                 # mower stripes
        flat += [(lo[k] + (hi[k] - lo[k]) * t) * stripe for k in range(3)] + [1.0]
    cols.data.foreach_set("color", flat)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def _paths(coll):
    """Gravel paths 1 cm above the lawn (no z-fighting), low stone curb at the edges, plaza."""
    grav, curb = _mat("park_gravel", "#CDB993", 1.0, 0.05), _mat("park_curb", "#A49C8E", 0.95)
    x0, x1, y0, y1 = LAWN
    z, h = 0.012, PATH_W / 2
    parts = [(*_box(x0, x1, PATH_A_Y - h, PATH_A_Y + h, 0.0, z), 0),
             (*_box(x0, x1, PATH_S_Y - h, PATH_S_Y + h, 0.0, z), 0),
             (*_box(PATH_B_X - h, PATH_B_X + h, PATH_A_Y + h, y1, 0.0, z), 0),
             (*_box(x0, PLAZA[0], PATH_D_Y - h, PATH_D_Y + h, 0.0, z), 0),
             (*_disc(40, PLAZA[2], z + 0.002, PLAZA[0], PLAZA[1]), 0)]
    # curb: 12 cm x 6 cm ruler at the edges of path A (outside the mouths of B)
    for yy in (PATH_A_Y - h - 0.06, PATH_A_Y + h):
        segs = [(x0, x1)] if yy < PATH_A_Y else [(x0, PATH_B_X - h), (PATH_B_X + h, x1)]
        for a, b in segs:
            parts.append((*_box(a, b, yy, yy + 0.06, 0.0, 0.05), 1))
    parts.append((*_ring(40, PLAZA[2], PLAZA[2] + 0.12, 0.05, PLAZA[0], PLAZA[1]), 1))
    _mesh("park_paths", parts, [grav, curb], coll)


def _city_ground(coll):
    """Sidewalks (light, z 0), street (asphalt, z -0.15, with a dashed line) and the city ground out to the horizon."""
    side, asph, line, base = (_mat("sidewalk", "#BDB5A6", 0.95), _mat("asphalt", "#5D6168", 0.9, 0.1),
                              _mat("road_line", "#E8E1CF", 0.8), _mat("city_floor", "#8C8A86", 1.0, 0.05))
    x0, x1, y0, y1 = LAWN
    a0, a1, b0, b1 = x0 - WALK, x1 + WALK, y0 - WALK, y1 + WALK               # inner sidewalk
    r0, r1, s0, s1 = a0 - ROAD, a1 + ROAD, b0 - ROAD, b1 + ROAD                 # rua
    o0, o1, p0, p1 = r0 - OUTER, r1 + OUTER, s0 - OUTER, s1 + OUTER             # outer sidewalk
    parts = []

    def frame(ax0, ax1, ay0, ay1, bx0, bx1, by0, by1, z0, z1, mi):
        parts.append((*_box(bx0, bx1, by0, ay0, z0, z1), mi))
        parts.append((*_box(bx0, bx1, ay1, by1, z0, z1), mi))
        parts.append((*_box(bx0, ax0, ay0, ay1, z0, z1), mi))
        parts.append((*_box(ax1, bx1, ay0, ay1, z0, z1), mi))

    frame(x0, x1, y0, y1, a0, a1, b0, b1, -0.16, 0.0, 0)
    frame(a0, a1, b0, b1, r0, r1, s0, s1, -0.18, -0.15, 1)
    frame(r0, r1, s0, s1, o0, o1, p0, p1, -0.16, 0.0, 0)
    # dashed line in the middle of the street (3 m dash, 3 gap)
    for yy in ((b0 + s0) / 2, (b1 + s1) / 2):
        x = r0
        while x < r1:
            parts.append((*_box(x, min(x + 3.0, r1), yy - 0.08, yy + 0.08, -0.15, -0.145), 2))
            x += 6.0
    for xx in ((a0 + r0) / 2, (a1 + r1) / 2):
        y = s0
        while y < s1:
            parts.append((*_box(xx - 0.08, xx + 0.08, y, min(y + 3.0, s1), -0.15, -0.145), 2))
            y += 6.0
    # crosswalk at the mouth of path B (back) and path A (sides)
    for k in range(6):
        xx = PATH_B_X - 2.5 + k * 1.0
        parts.append((*_box(xx, xx + 0.5, b1, s1, -0.15, -0.144), 2))
    for sx in (1, -1):
        for k in range(6):
            yy = PATH_A_Y - 2.5 + k * 1.0
            xa, xb = (a1, r1) if sx > 0 else (r0, a0)
            parts.append((*_box(xa, xb, yy, yy + 0.5, -0.15, -0.144), 2))
    _mesh("park_streets", parts, [side, asph, line], coll)
    # city ground: large grid, below everything, out to 700 m
    R = 700.0
    v = [(-R, -R, -0.17), (R, -R, -0.17), (R, R, -0.17), (-R, R, -0.17)]
    _mesh("city_floor", [(v, [(0, 1, 2, 3)], 0)], [base], coll)
    return dict(walk=(a0, a1, b0, b1), road=(r0, r1, s0, s1), outer=(o0, o1, p0, p1))


def _hedges(coll, rng):
    """Low hedge (0.9 m), faceted, around the lawn, with openings at the mouths of the paths."""
    green, dark = _mat("hedge_a", "#4E7A36", 1.0, 0.05), _mat("hedge_b", "#456F30", 1.0, 0.05)
    x0, x1, y0, y1 = LAWN
    t, gap = 0.75, 2.0
    runs = [((x0, y1 - t / 2), (x1, y1 - t / 2), [(PATH_B_X - gap, PATH_B_X + gap)]),
            ((x0, y0 + t / 2), (x1, y0 + t / 2), []),
            ((x0 + t / 2, y0), (x0 + t / 2, y1), [(PATH_A_Y - gap, PATH_A_Y + gap), (PATH_D_Y - gap, PATH_D_Y + gap),
                                                  (PATH_S_Y - gap, PATH_S_Y + gap)]),
            ((x1 - t / 2, y0), (x1 - t / 2, y1), [(PATH_A_Y - gap, PATH_A_Y + gap), (PATH_S_Y - gap, PATH_S_Y + gap)])]
    parts = []
    for (ax, ay), (bx, by), gaps in runs:
        horiz = ay == by
        L0, L1 = (ax, bx) if horiz else (ay, by)
        s = L0
        while s < L1 - 0.1:
            e = min(L1, s + rng.uniform(1.6, 2.4))
            if not any(g0 < (s + e) / 2 < g1 for g0, g1 in gaps):
                h = rng.uniform(0.82, 0.98)
                if horiz:
                    parts.append((*_box(s + 0.02, e - 0.02, ay - t / 2, ay + t / 2, 0.0, h), rng.randint(0, 1)))
                else:
                    parts.append((*_box(ax - t / 2, ax + t / 2, s + 0.02, e - 0.02, 0.0, h), rng.randint(0, 1)))
            s = e
    _mesh("park_hedges", parts, [green, dark], coll)


# ---------- furniture ----------

def bench_parts(length=1.8, seat=0.42):
    """Park bench: 3 seat slats, 2 backrest, black iron feet. Local: seat center at (0, 0),
    front toward -y (whoever sits looks toward -y)."""
    L = length / 2
    p = []
    for k in range(3):
        y0 = -0.2 + k * 0.14
        p.append((*_box(-L, L, y0, y0 + 0.11, seat - 0.035, seat), 0))
    for k in range(2):
        z0 = seat + 0.12 + k * 0.17
        p.append((*_box(-L, L, 0.24, 0.27, z0, z0 + 0.12), 0))
    for sx in (-L + 0.15, L - 0.15):
        p.append((*_box(sx - 0.03, sx + 0.03, -0.2, -0.15, 0.0, seat - 0.035), 1))
        p.append((*_box(sx - 0.03, sx + 0.03, 0.2, 0.26, 0.0, seat + 0.45), 1))
        p.append((*_box(sx - 0.03, sx + 0.03, -0.22, 0.26, seat - 0.07, seat - 0.035), 1))
        p.append((*_box(sx - 0.03, sx + 0.03, -0.18, 0.0, seat + 0.18, seat + 0.22), 1))     # arm
    return p


def spawn_bench(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Script piece 'bench': 1.8 m park bench (seat at 0.42 m). Whoever sits on it with 'Sitting': same
    position as the bench, "z": 0.06, same 'face' as the bench."""
    wood, iron = _mat("bench_wood", "#9A6B43", 0.85), _mat("bench_iron", "#2A2E33", 0.6, 0.3)
    o = _mesh(name, bench_parts(float(spec.get("len", 1.8))), [wood, iron], coll)
    o.location = (x, y, 0.0)
    o.rotation_euler = (0, 0, heading + math.pi / 2)     # heading = where the sitter looks (local front -y)
    return SimpleNamespace(obj=o, height=0.9, positions=None)


def _lamp(coll, k, x, y):
    import procedural
    iron = _mat("park_lamp_iron", "#22262B", 0.55, 0.3)
    glass = kit.flat("park_lamp_glass", "#FFE9BE", rough=0.35, emission="#FFC46B", strength=0.0)
    parts = [(*_cyl(8, 0.11, 0.09, 0.0, 0.35, x, y), 0), (*_cyl(6, 0.05, 0.04, 0.35, 3.3, x, y), 0),
             (*_cyl(6, 0.16, 0.12, 3.3, 3.36, x, y), 0), (*_cyl(6, 0.13, 0.17, 3.36, 3.72, x, y), 1),
             (*_cyl(6, 0.2, 0.02, 3.72, 3.95, x, y), 0)]
    _mesh(f"park_lamp{k}", parts, [iron, glass], coll)
    light = bpy.data.objects.new(f"park_lamp{k}_light", bpy.data.lights.new(f"park_lamp{k}_light", "POINT"))
    light.data.color = kit.lin("#FFC46B")[:3]
    light.data.shadow_soft_size = 0.2
    light.data.energy = 0.0
    light.data.use_shadow = False
    light.location = (x, y, 3.5)
    coll.objects.link(light)
    procedural.LAMPS.append(SimpleNamespace(light=light, bulb=glass, power=180.0))


def _bin(coll, k, x, y):
    green = _mat("bin_green", "#33503A", 0.7, 0.2)
    _mesh(f"park_bin{k}", [(*_cyl(8, 0.24, 0.26, 0.0, 0.85, x, y), 0), (*_cyl(8, 0.28, 0.28, 0.85, 0.9, x, y), 0)],
          [green], coll)


def _flowerbed(coll, rng, name, pts_fn, n):
    """Flower bed: dark earth 2 cm + Kenney nature-kit flowers (red, yellow, purple) as instances."""
    ids = ["flower-reda", "flower-redb", "flower-yellowa", "flower-yellowb", "flower-purplea", "flower-purpleb"]
    for k in range(n):
        x, y = pts_fn(rng)
        o = models.static_instance(rng.choice(ids), f"{name}_f{k}", coll, height=rng.uniform(0.28, 0.42))
        o.location = (x, y, 0.02)
        o.rotation_euler = (0, 0, rng.uniform(0, math.tau))


def _plaza(coll, rng):
    cx, cy, r = PLAZA
    soil = _mat("bed_soil", "#5A4130", 1.0, 0.0)
    _mesh("plaza_bed", [(*_ring(40, 3.0, 4.0, 0.025, cx, cy), 0)], [soil], coll)
    f = models.static_instance("fountain-round-detail", "plaza_fountain", coll, height=1.1)
    tpl = models.static_template("fountain-round-detail")
    k = 5.0 / max(tpl.width, 1e-6)
    f.scale = (k, k, 1.1 / tpl.height)
    f.location = (cx, cy, 0.0)

    def ring_pt(rg):
        a, rr = rg.uniform(0, math.tau), rg.uniform(3.1, 3.9)
        return cx + rr * math.cos(a), cy + rr * math.sin(a)
    _flowerbed(coll, rng, "plaza_bed", ring_pt, 70)
    for k2, (bx, by, _h) in enumerate(PLAZA_BENCHES):
        face = math.atan2(cy - by, cx - bx)
        spawn_bench(f"plaza_bench{k2}", coll, {}, bx, by, face, 0, 0, 30, rng)


def _beds(coll, rng):
    """Two rectangular flower beds on the front edge of path A (outside the free foreground)."""
    soil = _mat("bed_soil", "#5A4130", 1.0, 0.0)
    for k, (bx0, bx1) in enumerate(((-15.0, -10.0), (12.0, 17.0))):
        y0, y1 = PATH_A_Y - PATH_W / 2 - 1.6, PATH_A_Y - PATH_W / 2 - 0.4
        _mesh(f"park_bed{k}", [(*_box(bx0, bx1, y0, y1, 0.0, 0.025), 0)], [soil], coll)
        _flowerbed(coll, rng, f"park_bed{k}", lambda rg: (rg.uniform(bx0 + 0.15, bx1 - 0.15), rg.uniform(y0 + 0.15, y1 - 0.15)), 34)


def _trees(coll, rng, keepout):
    ids = ["commontree-1", "commontree-2", "commontree-3", "commontree-4", "commontree-5"]
    spots = []
    for x in range(-31, 34, 6):                                   # double alley behind the benches (closed canopy)
        if abs(x - PATH_B_X) > 3:
            spots.append((x + rng.uniform(-0.6, 0.6), 22.0 + rng.uniform(-0.5, 0.5), (8.5, 11.0)))
        if abs(x + 3 - PATH_B_X) > 3:
            spots.append((x + 3 + rng.uniform(-0.6, 0.6), 25.5 + rng.uniform(-0.6, 0.6), (9.0, 12.0)))
    for x in range(-31, 34, 6):                                   # south alley
        spots.append((x + rng.uniform(-0.6, 0.6), -20.5 + rng.uniform(-0.5, 0.5), (8.5, 11.0)))
    for k in range(5):                                            # plaza ring
        a = math.radians(40 + k * 72)
        spots.append((PLAZA[0] + 9.0 * math.cos(a), PLAZA[1] + 9.0 * math.sin(a), (8.0, 10.0)))
    spots += [(-14.0, -8.0, (8.0, 10.0)), (-26.0, -18.0, (8.5, 10.5)), (-12.0, -21.0, (8.0, 10.0)),
              (13.0, -6.0, (8.0, 10.0)), (26.0, -14.0, (8.5, 10.5)), (19.0, -22.0, (8.0, 10.0)), (-29.0, -4.0, (8.0, 10.0))]
    spots += [(-17.0, 5.5, (8.5, 10.5)), (-23.0, 0.5, (9.0, 11.0)), (-27.0, 9.0, (8.0, 10.0)), (-20.0, -10.0, (8.0, 10.0)),
              (17.5, 3.0, (8.5, 10.5)), (24.0, 9.0, (9.0, 11.0)), (27.0, -4.0, (8.0, 10.0)), (14.0, -14.0, (8.0, 10.0))]
    for k in range(9):                                            # back of the park
        spots.append((rng.uniform(-31, 31), rng.uniform(37, 43), (8.0, 11.0)))
    out = []
    for k, (x, y, hr) in enumerate(spots):
        if not on_lawn(x, y, pad=0.8):
            continue
        if any(math.hypot(x - kx, y - ky) < kr for kx, ky, kr in keepout):
            continue
        if FRONT_FREE[0] < x < FRONT_FREE[1] and FRONT_FREE[2] < y < FRONT_FREE[3]:
            continue
        o = models.static_instance(rng.choice(ids), f"park_tree{k}", coll, height=rng.uniform(*hr))
        o.location = (x, y, -0.02)
        o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        out.append((x, y))
    return out


def _street_trees(coll, rng, g):
    ids = ["commontree-1", "commontree-2", "commontree-5"]
    a0, a1, b0, b1 = g["walk"]
    k = 0
    for x in range(int(a0) + 4, int(a1) - 2, 9):
        for y in (b1 - 1.2, b0 + 1.2):
            if abs(x - PATH_B_X) < 4:
                continue
            o = models.static_instance(rng.choice(ids), f"street_tree{k}", coll, height=rng.uniform(7.0, 9.0))
            o.location = (x + rng.uniform(-0.5, 0.5), y, 0.0)
            o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            k += 1
    for y in range(int(b0) + 4, int(b1) - 2, 9):
        for x in (a1 - 1.2, a0 + 1.2):
            if abs(y - PATH_A_Y) < 4 or abs(y - PATH_D_Y) < 4:
                continue
            o = models.static_instance(rng.choice(ids), f"street_tree{k}", coll, height=rng.uniform(7.0, 9.0))
            o.location = (x, y + rng.uniform(-0.5, 0.5), 0.0)
            o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            k += 1


def _street_props(coll, rng, g):
    """Street lamps (Kenney light-curved) on the outer sidewalk and parked cars in both lanes."""
    o0, o1, p0, p1 = g["outer"]
    r0, r1, s0, s1 = g["road"]
    k = 0
    for x in range(int(o0) + 6, int(o1) - 4, 18):
        for y, face in ((p1 - 0.6, -math.pi / 2), (p0 + 0.6, math.pi / 2)):
            o = models.static_instance("light-curved", f"street_light{k}", coll, height=7.0)
            o.location = (x, y, 0.0)
            o.rotation_euler = (0, 0, face + math.pi / 2)
            k += 1
    cars = ["sedan", "taxi", "suv", "hatchback-sports", "van", "sedan-sports", "suv-luxury", "delivery"]
    a0, a1, b0, b1 = g["walk"]
    k = 0
    lanes = [((b1 + s1) / 2 - 2.1, 0.0, (r0 + 4, r1 - 4)), ((b1 + s1) / 2 + 2.1, math.pi, (r0 + 4, r1 - 4)),
             ((b0 + s0) / 2 + 2.1, math.pi, (r0 + 4, r1 - 4))]
    for y, hd, (xa, xb) in lanes:
        x = xa + rng.uniform(0, 6)
        while x < xb:
            if rng.random() < 0.55 and abs(x - PATH_B_X) > 5:
                cid = rng.choice(cars)
                o = models.static_instance(cid, f"car{k}", coll)
                tpl = models.static_template(cid)
                s = 4.4 / max(tpl.width, 1e-6)
                o.scale = (s, s, s)
                o.location = (x, y, -0.15)
                o.rotation_euler = (0, 0, hd + math.pi / 2)
                k += 1
            x += rng.uniform(6.0, 11.0)
    for x, hd in (((a1 + r1) / 2 + 2.1, 0.0), ((a0 + r0) / 2 - 2.1, math.pi)):
        y = s0 + 6
        while y < s1 - 6:
            if rng.random() < 0.5 and abs(y - PATH_A_Y) > 5 and abs(y - PATH_D_Y) > 5:
                cid = rng.choice(cars)
                o = models.static_instance(cid, f"car{k}", coll)
                tpl = models.static_template(cid)
                s = 4.4 / max(tpl.width, 1e-6)
                o.scale = (s, s, s)
                o.location = (x, y, -0.15)
                o.rotation_euler = (0, 0, hd)
                k += 1
            y += rng.uniform(6.0, 11.0)


# ---------- buildings ----------

_variant_mesh: dict = {}


def _building_mesh(ident, variant):
    """Building mesh with the variation texture (white, beige or brick facade): copy per (id, variation)."""
    tpl = models.static_template(ident)
    if not variant:
        return tpl
    key = (ident, variant)
    if key not in _variant_mesh:
        me = tpl.mesh.copy()
        img = bpy.data.images.load(str(CITY / "Textures" / f"{variant}.png"), check_existing=True)
        for i, m in enumerate(me.materials):
            if m is None or not m.use_nodes:
                continue
            m2 = m.copy()
            for n in m2.node_tree.nodes:
                if n.type == "TEX_IMAGE":
                    n.image = img
            me.materials[i] = m2
        _variant_mesh[key] = SimpleNamespace(mesh=me, height=tpl.height, width=tpl.width)
    return _variant_mesh[key]


def _place_building(coll, name, ident, variant, x, y, face, factor=FACTOR, shadow=True):
    tpl = _building_mesh(ident, variant)
    o = bpy.data.objects.new(name, tpl.mesh)
    coll.objects.link(o)
    o.scale = (factor, factor, factor)
    o.location = (x, y, -0.02)
    o.rotation_euler = (0, 0, face)
    o.visible_shadow = shadow
    return o


def _row(coll, rng, name, start, end, depth_axis, front, face, ids, gap=(0.6, 2.0), shadow=True):
    """Row of buildings along one side: 'front' = facade coordinate; the row's axis is x or y."""
    pos, k = start, 0
    while pos < end:
        ident = rng.choice(ids)
        item = models.CATALOG[ident]["size"]
        w = item[0] * FACTOR
        d = item[1] * FACTOR
        c = pos + w / 2
        if depth_axis == "y":
            x, y = c, front + math.copysign(d / 2, front)
        else:
            x, y = front + math.copysign(d / 2, front), c
        _place_building(coll, f"{name}{k}", ident, rng.choice(VARIANTS), x, y, face, shadow=shadow)
        pos += w + rng.uniform(*gap)
        k += 1


def _city(coll, rng, g):
    o0, o1, p0, p1 = g["outer"]
    low = ["building-a", "building-b", "building-c", "building-d", "building-e", "building-f", "building-g",
           "building-h", "building-i", "building-k", "building-l"]
    tall = ["building-j", "building-m", "building-n", "building-skyscraper-a", "building-skyscraper-b",
            "building-skyscraper-c", "building-skyscraper-d", "building-skyscraper-e"]
    # 1st layer: facades facing the park (Kenney puts the facade at -y after import: rotates 180 at the back)
    _row(coll, rng, "bld_n", o0 - 30, o1 + 30, "y", p1 + 0.5, math.pi, low)
    _row(coll, rng, "bld_s", o0 - 30, o1 + 30, "y", p0 - 0.5, 0.0, low)
    _row(coll, rng, "bld_e", p0, p1, "x", o1 + 0.5, math.pi / 2, low)
    _row(coll, rng, "bld_w", p0, p1, "x", o0 - 0.5, -math.pi / 2, low)
    # 2nd layer: towers behind the first (shadow only on themselves: far away, they do not cover the park)
    k = 0
    for side in range(4):
        for j in range(7):
            u = -1.0 + 2.0 * (j + rng.uniform(0.15, 0.85)) / 7
            d = rng.uniform(95, 135)
            if side == 0:
                x, y, face = u * 120, d, math.pi
            elif side == 1:
                x, y, face = u * 120, -d + 20, 0.0
            elif side == 2:
                x, y, face = d, u * 110 + 10, math.pi / 2
            else:
                x, y, face = -d, u * 110 + 10, -math.pi / 2
            _place_building(coll, f"bld_t{k}", rng.choice(tall), rng.choice(VARIANTS), x, y, face,
                            factor=FACTOR * rng.uniform(0.95, 1.2), shadow=False)
            k += 1
    # 3rd layer: horizon of simple blocks (Kenney low-detail) from 160 to 320 m
    lows = [i for i in models.CATALOG if i.startswith("low-detail-building")]
    for k in range(70):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(165, 320)
        ident = rng.choice(lows)
        f = rng.uniform(16, 26)
        o = _place_building(coll, f"bld_far{k}", ident, rng.choice(VARIANTS[:2]), r * math.cos(a), r * math.sin(a) + 10,
                            rng.choice((0, math.pi / 2, math.pi, -math.pi / 2)), factor=f, shadow=False)
        o.scale.z = f * rng.uniform(0.9, 1.9)


def build_park(coll, sdef, rng, keepout=()):
    """The whole 'park' stage (ground, paths, hedge, furniture, trees, streets, cars and buildings)."""
    _lawn(coll, rng)
    _paths(coll)
    g = _city_ground(coll)
    _hedges(coll, rng)
    for k, (x, y) in enumerate(BENCH_SEATS):
        spawn_bench(f"park_bench{k}", coll, {}, x, y, -math.pi / 2, 0, 0, 30, rng)
        _bin(coll, k, x + 1.35, y + 0.1)
    for k, (x, y) in enumerate(SOUTH_SEATS):
        spawn_bench(f"park_sbench{k}", coll, {}, x, y, math.pi / 2, 0, 0, 30, rng)
        _bin(coll, 10 + k, x - 1.35, y - 0.1)
    for k, (x, y) in enumerate(LAMPS_AT):
        _lamp(coll, k, x, y)
    _plaza(coll, rng)
    _beds(coll, rng)
    _trees(coll, rng, keepout)
    _street_trees(coll, rng, g)
    _street_props(coll, rng, g)
    _city(coll, rng, g)


# ---------- picnic (script pieces) ----------

def spawn_blanket(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Checkered picnic blanket (red and cream), 'len' = longer side (default 2.0 m; the other is 0.75 of that),
    3 mm above the ground, with a plate, sandwiches, apples and a can from the Kenney Food Kit on top ("food": false removes them)."""
    L = float(spec.get("len", 2.0))
    W = L * 0.75
    cols = spec.get("colors") or ("#B8432F", "#EDE2CC")         # 'colors': [hex, hex] (another blanket)
    red = _mat("blanket_red" if cols[0] == "#B8432F" else f"blanket_{cols[0][1:]}", cols[0], 0.95, 0.05)
    cream = _mat("blanket_cream" if cols[1] == "#EDE2CC" else f"blanket_{cols[1][1:]}", cols[1], 0.95, 0.05)
    n = 8
    parts = []
    for i in range(n):
        for j in range(int(n * 0.75)):
            x0, y0 = -L / 2 + i * L / n, -W / 2 + j * W / int(n * 0.75)
            dz = 0.003 + 0.004 * math.sin(i * 1.7 + j * 2.3) ** 2          # light folds (not a flat board)
            parts.append((*_box(x0, x0 + L / n, y0, y0 + W / int(n * 0.75), 0.0, dz), (i + j) % 2))
    o = _mesh(name, parts, [red, cream], coll)
    o.location = (x, y, 0.0)
    o.rotation_euler = (0, 0, heading)
    if spec.get("food", True):
        white = _mat("plate", "#F1EEE8", 0.5, 0.3)
        plate = _mesh(f"{name}_plate", [(*_cyl(12, 0.13, 0.15, 0.0, 0.018), 0)], [white], coll)
        plate.parent = o
        plate.location = (L * 0.08, -W * 0.12, 0.007)
        food = [("sandwich", (L * 0.08, -W * 0.12, 0.025), 0.06), ("sandwich", (L * 0.12, -W * 0.06, 0.025), 0.06),
                ("apple", (-L * 0.05, -W * 0.25, 0.007), 0.08), ("apple", (-L * 0.1, -W * 0.18, 0.007), 0.08),
                ("soda-can", (L * 0.25, -W * 0.02, 0.007), 0.12), ("grapes", (-L * 0.02, -W * 0.02, 0.007), 0.12)]
        for k, (ident, loc, h) in enumerate(food):
            f = models.static_instance(ident, f"{name}_food{k}", coll, height=h)
            f.parent = o
            f.location = loc
            f.rotation_euler = (0, 0, rng.uniform(0, math.tau))
    return SimpleNamespace(obj=o, height=0.05, positions=None)


def spawn_basket(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Wicker picnic basket with lid and handle; 'len' = length (default 0.5 m; height 0.28, handle 0.45)."""
    L = float(spec.get("len", 0.5))
    W, H = L * 0.65, L * 0.56
    wick, wick2, cloth = (_mat("wicker", "#B5864D", 0.95, 0.05), _mat("wicker_dark", "#94693A", 0.95, 0.05),
                          _mat("blanket_red", "#B8432F", 0.95, 0.05))
    parts = []
    bands = 5
    for b in range(bands):                                    # alternating wicker bands (reads as woven)
        z0, z1 = H * b / bands, H * (b + 1) / bands
        sh = 0.96 + 0.04 * b / bands                           # the basket opens up a little toward the top
        parts.append((*_box(-L / 2 * sh, L / 2 * sh, -W / 2 * sh, W / 2 * sh, z0, z1), b % 2))
    for k in range(7):                                         # vertical weave rods (4 mm outward)
        u = -L / 2 + L * (k + 0.5) / 7
        for sy in (-1, 1):
            parts.append((*_box(u - 0.008, u + 0.008, sy * W / 2 - 0.004, sy * W / 2 + 0.004, 0.0, H), 1))
    for k in range(4):
        u = -W / 2 + W * (k + 0.5) / 4
        for sx in (-1, 1):
            parts.append((*_box(sx * L / 2 - 0.004, sx * L / 2 + 0.004, u - 0.008, u + 0.008, 0.0, H), 1))
    parts.append((*_box(-L / 2 * 1.03, L / 2 * 1.03, -W / 2 * 1.03, W / 2 * 1.03, H, H + 0.025), 1))     # lid
    parts.append((*_box(-L * 0.18, L * 0.18, -W / 2 * 1.06, -W / 2 * 1.03, H - 0.06, H + 0.02), 2))      # pano saindo
    for sx in (-1, 1):                                         # handle: 2 shafts + bar
        parts.append((*_box(sx * L * 0.2 - 0.012, sx * L * 0.2 + 0.012, -0.012, 0.012, H, H + 0.17), 1))
    parts.append((*_box(-L * 0.2 - 0.012, L * 0.2 + 0.012, -0.014, 0.014, H + 0.15, H + 0.185), 1))
    o = _mesh(name, parts, [wick, wick2, cloth], coll)
    o.location = (x, y, 0.006)
    o.rotation_euler = (0, 0, heading)
    return SimpleNamespace(obj=o, height=H + 0.18, positions=None)


def spawn_cooler(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Cooler box (0.36 m high, 0.56 x 0.36): serves as a seat for whoever sits on the blanket with 'Sitting'
    (same 'at' and 'face' as the person: the hip lands on top, 0.2 m behind the root; use the person at at + 0.2 m in front)."""
    blue, white = _mat("cooler_blue", "#2F6E9E", 0.6, 0.3), _mat("cooler_white", "#ECEAE4", 0.6, 0.3)
    parts = [(*_box(-0.28, 0.28, -0.18, 0.18, 0.0, 0.29), 0), (*_box(-0.29, 0.29, -0.19, 0.19, 0.29, 0.36), 1),
             (*_box(-0.3, -0.28, -0.05, 0.05, 0.2, 0.26), 1), (*_box(0.28, 0.3, -0.05, 0.05, 0.2, 0.26), 1)]
    o = _mesh(name, parts, [blue, white], coll)
    o.location = (x, y, 0.006)
    o.rotation_euler = (0, 0, heading + math.pi / 2)
    return SimpleNamespace(obj=o, height=0.36, positions=None)


def spawn_turf(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Grass mat for the MACRO (camera close to the ground): 2 to 7 cm blades, clovers and pebbles on a disc of radius
    'len' (default 1.2 m) around 'at'. Declare only in macro scenes (no 'span'): from afar the blades become
    smaller than 1 pixel and would shimmer. 'clear': [[x, y, r], ...] (world) leaves the blanket and basket spot without grass;
    'density' = blades per m² (default 1400)."""
    R = float(spec.get("len", 1.2))
    if spec.get("seed") is not None:                    # same grass in different scenes (the closing repeats the macro of f1)
        rng = random.Random(f"turf{spec['seed']}")
    clear = [tuple(c) for c in spec.get("clear", [])]
    greens = [_mat(f"turf_g{k}", h, 0.9, 0.1) for k, h in enumerate(("#5B8A3C", "#6F9C48", "#4C7A33", "#82A957"))]
    clover, stone = _mat("turf_clover", "#4F8A3A", 0.8, 0.1), _mat("turf_stone", "#9C968A", 0.95, 0.05)
    verts, faces, mi = [], [], []

    def blocked(px, py):
        return any(math.hypot(x + px - cx, y + py - cy) < cr for cx, cy, cr in clear)

    blade = float(spec.get("blade", 1.0))          # 'blade' > 1: tall grass of the POV foreground (bigger blades, no shimmer)
    n = int(float(spec.get("density", 1400 / blade ** 1.5)) * math.pi * R * R)
    for _k in range(n):
        r, a = R * math.sqrt(rng.random()), rng.uniform(0, math.tau)
        px, py = r * math.cos(a), r * math.sin(a)
        if blocked(px, py):
            continue
        h = rng.uniform(0.02, 0.07) * (1.0 if rng.random() > 0.15 else 1.4) * blade
        w = rng.uniform(0.003, 0.006) * blade ** 0.8
        b = rng.uniform(0, math.tau)
        lean = rng.uniform(-0.35, 0.35) * h
        dx, dy = math.cos(b) * w, math.sin(b) * w
        tx, ty = -math.sin(b) * lean, math.cos(b) * lean
        base = len(verts)
        verts += [(px - dx, py - dy, 0.0), (px + dx, py + dy, 0.0), (px + tx, py + ty, h)]
        faces.append((base, base + 1, base + 2))
        mi.append(rng.randint(0, 3))
    for _k in range(int(40 * R * R)):                   # clovers: 3 flat leaves 1-3 cm off the ground
        r, a = R * math.sqrt(rng.random()), rng.uniform(0, math.tau)
        px, py, pz = r * math.cos(a), r * math.sin(a), rng.uniform(0.01, 0.03)
        if blocked(px, py):
            continue
        rot = rng.uniform(0, math.tau)
        for j in range(3):
            c = rot + j * math.tau / 3
            s0 = 0.009
            base = len(verts)
            verts += [(px, py, pz), (px + math.cos(c - 0.6) * s0, py + math.sin(c - 0.6) * s0, pz + 0.002),
                      (px + math.cos(c) * s0 * 1.5, py + math.sin(c) * s0 * 1.5, pz + 0.003),
                      (px + math.cos(c + 0.6) * s0, py + math.sin(c + 0.6) * s0, pz + 0.002)]
            faces.append((base, base + 1, base + 2, base + 3))
            mi.append(4)
    for _k in range(int(25 * R * R)):                   # pebbles of 4 to 12 mm
        r, a = R * math.sqrt(rng.random()), rng.uniform(0, math.tau)
        px, py = r * math.cos(a), r * math.sin(a)
        if blocked(px, py):
            continue
        s0 = rng.uniform(0.004, 0.012)
        v, f = _cyl(5, s0, s0 * 0.6, 0.0, s0 * 0.8, px, py, rng.uniform(0, 1))
        base = len(verts)
        verts += v
        faces += [tuple(i + base for i in ff) for ff in f]
        mi += [5] * len(f)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in greens + [clover, stone]:
        me.materials.append(m)
    for poly, idx in zip(me.polygons, mi):
        poly.material_index = idx
        poly.use_smooth = False
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location = (x, y, 0.0)
    o.visible_shadow = False
    return SimpleNamespace(obj=o, height=0.07, positions=None)


def spawn_crumbs(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Bread crumbs (2.5 to 6 mm, crumb and crust) in a radius 'len' (default 0.25 m) around 'at'; 'count' = how many
    (default 18). Setup and payoff of the macro (the trail that carries the crumbs, then the still crumbs).
    Round 3: irregular faceted lumps (before, a 5-sided truncated cone, which read as a stool)."""
    import bmesh
    R, n = float(spec.get("len", 0.25)), int(spec.get("count", 18))
    crumb, crust = _mat("crumb", "#E8CF9A", 0.9, 0.1), _mat("crust", "#B07A3E", 0.9, 0.1)
    bm = bmesh.new()
    for _k in range(n):
        r, a = R * math.sqrt(rng.random()), rng.uniform(0, math.tau)
        s0 = rng.uniform(0.0012, 0.003)
        geo = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        vs = geo["verts"]
        sx, sy, sz = rng.uniform(0.85, 1.3), rng.uniform(0.75, 1.1), rng.uniform(0.55, 0.8)
        rot = rng.uniform(0, math.tau)
        c, s_ = math.cos(rot), math.sin(rot)
        cx, cy = r * math.cos(a), r * math.sin(a)
        for v in vs:
            px, py, pz = v.co.x * sx * rng.uniform(0.85, 1.12), v.co.y * sy * rng.uniform(0.85, 1.12), v.co.z * sz
            v.co.x, v.co.y = cx + s0 * (px * c - py * s_), cy + s0 * (px * s_ + py * c)
            v.co.z = s0 * (pz + sz * 0.8)
        mi = 0 if rng.random() > 0.3 else 1
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = mi
            f.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(crumb)
    me.materials.append(crust)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location = (x, y, 0.0)
    return SimpleNamespace(obj=o, height=0.01, positions=None)
