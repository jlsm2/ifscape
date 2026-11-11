"""Terrain, river, bridge, layered background (hills, trees, mountain range), village and cabin of two-humans-left.

Axes: x east, y north, z up. River along x (center yc(x), width ~16 m); near bank (south, y < 0) with the
cabin; village on the opposite bank (north). The wooden bridge crosses at x = 4. Camera almost always looking toward +y.
Background in 3 layers: hills (the terrain itself rises far away), ~120 instanced trees, bluish mountain range.
"""

import math
import random

import bpy

import kit
import valley_houses as vh
import valley_lib as vl
from kit import lin

BRIDGE_X = 4.0
LANE_X = 4.0
DECK_Z = 0.5
KNOLL = (-3.0, -36.0)               # low hill south of the cabin: camera of 06 (sees the valley from above)
KNOLL_H = 3.6
FOUNTAIN = (10.5, 31.5)


def yc(x):
    return 2.5 * math.sin((x - BRIDGE_X) / 30.0)


def _smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def height(x, y):
    t = abs(y - yc(x))
    if t < 4.5:
        h = -0.95
    elif t < 8.0:
        h = -0.95 * (1 - _smooth((t - 4.5) / 3.5))
    else:
        h = 0.0
    far = max(abs(x) - 70.0, abs(y) - 90.0, 0.0)
    amp = 0.7 * _smooth(far / 60.0) + 0.12
    h += amp * (math.sin(x * 0.11 + 1.3) * math.sin(y * 0.09 + 0.4) + 0.5 * math.sin(x * 0.27 + y * 0.21))
    dn = max(y - 95.0, 0.0)
    ds = max(-y - 80.0, 0.0)
    dx = max(abs(x) - 140.0, 0.0)
    h += 20.0 * (dn / 170.0) ** 1.7 + 14.0 * (ds / 160.0) ** 1.7 + 22.0 * (dx / 160.0) ** 1.7
    h += KNOLL_H * math.exp(-((x - KNOLL[0]) ** 2 + (y - KNOLL[1]) ** 2) / (2 * 9.0 ** 2))
    h += 3.5 * _smooth((dn - 20) / 80.0) * (0.5 + 0.5 * math.sin(x * 0.045 + 2.0))
    return h


def _axis(a, b, fine0, fine1, step_f, step_c):
    out, v = [], a
    while v < fine0:
        out.append(v)
        v += step_c
    v = fine0
    while v < fine1:
        out.append(v)
        v += step_f
    v = fine1
    while v <= b + 1e-6:
        out.append(v)
        v += step_c
    return out


def terrain():
    xs = _axis(-450, 450, -100, 100, 2.5, 30.0)
    ys = _axis(-420, 480, -75, 100, 2.5, 30.0)
    greens = [vl.mat(f"Grass{i}", c) for i, c in enumerate(("#4F7048", "#5A7C4E", "#648653", "#6E8F58", "#7A8B55"))]
    bank = vl.mat("Bank", "#6F7552")
    hill = vl.mat("HillA", "#4A7054")
    far = vl.mat("HillB", "#456A6E")
    dirt = vl.mat("PatchDirt", "#66583E")
    verts = [(x, y, height(x, y)) for y in ys for x in xs]
    nx = len(xs)
    faces, fm = [], []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            h = height(cx, cy)
            t = abs(cy - yc(cx))
            if t < 9.6 and h < 0.4:
                fm.append(5)
            elif h > 14:
                fm.append(7)
            elif h > 3.5 and abs(cx) > 60:
                fm.append(6)
            else:
                n = (math.sin(cx * 0.31 + 1.0) * math.sin(cy * 0.27) + 0.6 * math.sin(cx * 0.09 + cy * 0.13)
                     + 0.5 * math.sin(cx * 0.83) * math.sin(cy * 0.71))
                if n > 9.0:
                    fm.append(8)
                else:
                    fm.append(min(4, max(0, int((n + 1.0) * 1.7))))
    for m in (*greens, bank, hill):
        mottle(m)
    obj = kit.mesh_object("Terrain", verts, faces, [*greens, bank, hill, far, dirt], face_mats=fm)
    return obj


def mottle(mat, lift=1.0):
    """Ground color variation in world space (does not flicker with the camera): large blotches (8 m) and dark tufts
    (1.5 m) multiply the flat face color between ~0.8 and ~1.15. lift lightens (grass over the ground)."""
    nt = mat.node_tree
    n, ln = nt.nodes, nt.links
    p = kit.principled(mat)
    base = tuple(p.inputs["Base Color"].default_value)
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.12
    big.inputs["Detail"].default_value = 1.0
    small = n.new("ShaderNodeTexNoise")
    small.inputs["Scale"].default_value = 0.65
    small.inputs["Detail"].default_value = 0.0
    geo = n.new("ShaderNodeNewGeometry")
    ln.new(geo.outputs["Position"], big.inputs["Vector"])
    ln.new(geo.outputs["Position"], small.inputs["Vector"])
    r1 = n.new("ShaderNodeMapRange")
    r1.inputs["From Min"].default_value, r1.inputs["From Max"].default_value = 0.35, 0.65
    r1.inputs["To Min"].default_value, r1.inputs["To Max"].default_value = 0.82 * lift, 1.14 * lift
    ln.new(big.outputs["Fac"], r1.inputs["Value"])
    r2 = n.new("ShaderNodeMapRange")
    r2.inputs["From Min"].default_value, r2.inputs["From Max"].default_value = 0.55, 0.62
    r2.inputs["To Min"].default_value, r2.inputs["To Max"].default_value = 1.0, 0.86
    ln.new(small.outputs["Fac"], r2.inputs["Value"])
    mul = n.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    ln.new(r1.outputs["Result"], mul.inputs[0])
    ln.new(r2.outputs["Result"], mul.inputs[1])
    col = n.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.blend_type = "MULTIPLY"
    col.inputs["Factor"].default_value = 1.0
    col.inputs["A"].default_value = base
    ln.new(mul.outputs[0], col.inputs["B"])
    ln.new(col.outputs["Result"], p.inputs["Base Color"])
    return mat


TRAILS = [
        [(-9.0, -15.2), (-6.5, -14.0), (-3.0, -12.6), (1.0, -11.3), (4.0, -10.4)],
        [(-9.0, -16.0), (-13.5, -19.5), (-19.0, -18.5), (-25.0, -18.0)],
        [(-8.0, -17.5), (-9.5, -21.5), (-13.0, -24.0), (-18.0, -24.5), (-22.0, -27.0)],
        [(4.0, -36.0), (3.0, -28.0), (4.0, -18.0), (4.0, -10.4)],
        [(-45.0, -12.0), (-30.0, -11.5), (-15.0, -10.8), (0.0, -10.0), (14.0, -9.5), (30.0, -8.5), (50.0, -7.0)],
        [(-45.0, 9.5), (-30.0, 9.0), (-12.0, 9.0), (4.0, 10.5), (20.0, 11.5), (40.0, 11.5), (60.0, 12.0)],
        [(4.0, -36.0), (12.0, -31.0), (16.0, -28.0)],
    ]


def trails():
    """Dirt trails (ribbons glued to the terrain): cabin-bridge, cabin-cabins, garden, banks, hill-bridge."""
    dirt = mottle(vl.mat("Trail", "#6E5E44"))
    lines = TRAILS
    verts, faces = [], []
    for pts in lines:
        samples = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 1.5))
            samples += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
        samples.append(pts[-1])
        base = len(verts)
        for k, (x, y) in enumerate(samples):
            a = samples[min(k + 1, len(samples) - 1)]
            b = samples[max(k - 1, 0)]
            dx, dy = a[0] - b[0], a[1] - b[1]
            ln = math.hypot(dx, dy) or 1.0
            nx_, ny_ = -dy / ln * 0.45, dx / ln * 0.45
            for sgn in (-1, 1):
                px, py = x + sgn * nx_, y + sgn * ny_
                verts.append((px, py, max(height(px, py), -0.2) + 0.04))
        for k in range(len(samples) - 1):
            i = base + 2 * k
            faces.append((i, i + 2, i + 3, i + 1))
    return kit.mesh_object("Trails", verts, faces, [dirt])


def water():
    m = vl.mat("Water", "#1F4A72", rough=0.25, emission="#2A6296", strength=0.12)
    w = kit.water_grid("Water", -240, 240, -26, 26, -0.4, m, cell=3.0, amp=0.03)
    w.visible_shadow = False
    return w


def bridge():
    """Wooden bridge: loose boards in two tones (4 cm gap, staggered ends) over stringers,
    two-rail handrail, 8 posts per side with cap, X braces between posts and trestles in the river."""
    from mathutils import Matrix
    import random as _r
    rr = _r.Random(8)
    wood = vl.mat("BridgeWood", "#8A6A44")
    wood2 = vl.mat("BridgeWood2", "#74583A")
    dark = vl.mat("BridgeDark", "#5E4630")
    y0, y1 = yc(BRIDGE_X) - 10.5, yc(BRIDGE_X) + 10.5
    base = [kit._box_geo(3.0, y1 - y0, 0.17, BRIDGE_X - 1.5, y0, DECK_Z - 0.22)]
    for sx in (-1.45, 1.45):                                          # longarinas
        base.append(kit._box_geo(0.22, y1 - y0 + 0.2, 0.3, BRIDGE_X + sx - 0.11, y0 - 0.1, DECK_Z - 0.36))
    planks = [[], []]
    k, yy = 0, y0
    while yy < y1 - 0.2:
        ext = rr.uniform(-0.06, 0.06)
        planks[k % 2].append(kit._box_geo(3.4 + ext, 0.41, 0.06, BRIDGE_X - 1.7 - ext / 2 + rr.uniform(-0.03, 0.03),
                                          yy, DECK_Z - 0.06))
        yy += 0.45
        k += 1
    deck = [kit.mesh_object("BridgeBase", *kit.merge(*base)[:2], [dark]),
            kit.mesh_object("BridgeDeck", *kit.merge(*planks[0])[:2], [wood]),
            kit.mesh_object("BridgeDeck2", *kit.merge(*planks[1])[:2], [wood2])]
    posts, rails = [], []
    for side in (-1.55, 1.55):
        rails.append(kit._box_geo(0.12, y1 - y0, 0.1, BRIDGE_X + side - 0.06, y0, DECK_Z + 0.95))
        rails.append(kit._box_geo(0.08, y1 - y0, 0.08, BRIDGE_X + side - 0.04, y0, DECK_Z + 0.48))
        ys = [y0 + 0.3 + k * (y1 - y0 - 0.6) / 7 for k in range(8)]
        for yy in ys:
            posts.append(kit._box_geo(0.14, 0.14, 1.05, BRIDGE_X + side - 0.07, yy - 0.07, DECK_Z - 0.06))
            posts.append(kit._box_geo(0.19, 0.19, 0.06, BRIDGE_X + side - 0.095, yy - 0.095, DECK_Z + 1.04))
        for ya, yb in zip(ys, ys[1:]):                                # X between posts, outside the handrail
            for za, zb in ((DECK_Z + 0.05, DECK_Z + 0.9), (DECK_Z + 0.9, DECK_Z + 0.05)):
                ln = math.hypot(yb - ya - 0.14, zb - za)
                ang = math.atan2(zb - za, yb - ya - 0.14)
                v, f = kit._box_geo(0.05, ln, 0.07, -0.025, 0, -0.035)
                m = Matrix.Translation((BRIDGE_X + side + (0.1 if side > 0 else -0.1), ya + 0.07, za)) @ \
                    Matrix.Rotation(ang, 4, "X")
                posts.append(kit.xform_geo((v, f), m))
    for k in range(5):                                # trestles inside the river
        yy = yc(BRIDGE_X) - 5.5 + k * 2.75
        for side in (-1.3, 1.3):
            posts.append(kit._box_geo(0.3, 0.3, DECK_Z + 1.2, BRIDGE_X + side - 0.15, yy, -1.4))
        posts.append(kit._box_geo(3.0, 0.24, 0.24, BRIDGE_X - 1.5, yy + 0.03, DECK_Z - 0.6))
    pr = kit.mesh_object("BridgeRails", *kit.merge(*rails, *posts)[:2], [dark])
    stone = vl.mat("BridgeStone", "#57534C")
    ab = []
    for ya, yb in ((y0 + 0.1, y0 + 1.5), (y1 - 1.5, y1 - 0.1)):     # stone abutments under the ends
        ab.append(kit._box_geo(3.2, yb - ya, DECK_Z - 0.24 + 0.8, BRIDGE_X - 1.6, ya, -0.8))
    pa = kit.mesh_object("BridgeAbut", *kit.merge(*ab)[:2], [stone])
    return [*deck, pr, pa]


# ---------- vila ----------

# (name, x, y, rotz in degrees, nx, ny, ridge along x?)   rot -90: door toward +x; +90: toward -x; 180: toward -y (river)
VILLAGE_A = [
    ("a1", -8, 15, -90, 2, 2, True), ("a2", -8, 22, -90, 2, 2, True),
    ("a3", 16, 15, 90, 2, 2, True), ("a4", 16, 22, 90, 3, 2, True),
    ("a5", -26, 15, 180, 2, 2, True), ("a6", -39, 16, 180, 2, 2, True),
    ("a7", 29, 14, 180, 2, 2, True), ("a8", 42, 15, 180, 3, 2, True), ("a9", 54, 14, 180, 2, 2, True),
    ("a10", 4, 46, 180, 4, 2, True), ("a11", -19, 31, -90, 2, 2, True), ("a12", 29, 33, 90, 2, 2, True),
    ("a13", 16, 41, 90, 2, 2, True), ("a14", -8, 41, -90, 2, 2, True),
]
VILLAGE_B = [
    ("b1", -8, 28, -90, 2, 2, True), ("b2", -8, 34, -90, 2, 2, True),
    ("b3", 16, 28, 90, 2, 2, True), ("b4", 16, 34, 90, 2, 2, True),
    ("b5", -22, 42, -90, 3, 2, True), ("b6", -33, 28, -90, 2, 2, True), ("b7", 38, 30, 90, 2, 2, True),
    ("b8", 28, 47, 180, 2, 2, True), ("b9", -18, 52, 180, 2, 2, True), ("b10", 14, 54, 180, 2, 2, True),
    ("b11", -5, 56, 180, 2, 2, True),
]
HUTS = [("h1", -26, -17, 0, 2, 2, True), ("h2", -22, -27, 90, 2, 2, True), ("h3", 16, -31, 180, 2, 2, True),
        ("h4", 12, -20, 90, 2, 2, True)]
CABIN = ("cabin", -12.0, -15.0, -90, 2, 2, True)


def village(which, rnd=None, gable=False):
    out = []
    for name, x, y, r, nx, ny, rx in which:
        out.append(vh.house(name, x, y, math.radians(r), nx, ny, ridge_x=rx, gable=gable))
    return out


def chimneys(houses, count, rnd):
    """Stone chimneys (with cap) on the alley houses (the ones the camera of 08 sees), coming out of the roof at 1/4 of the
    ridge; they turn with the house. Returns the top positions."""
    from mathutils import Matrix, Vector
    mat = vl.mat("Chimney", "#5E5850")
    cap = vl.mat("ChimneyCap", "#3E3A36")
    tops = []
    lane = [h for h in houses if -14 < h.pos[0] < 22 and 12 < h.pos[1] < 62]
    rest = [h for h in houses if h not in lane]
    pick = lane[:count] + rest[:max(0, count - len(lane))]
    for h in pick:
        x, y = h.pos
        W, D = h.size
        lx, ly = (W * 0.27, 0.55) if h.ridge_x else (0.55, D * 0.27)
        top = h.height + 0.75
        geo = kit.merge(kit._box_geo(0.62, 0.62, top - 1.8, lx - 0.31, ly - 0.31, 1.8),
                        kit._box_geo(0.76, 0.76, 0.12, lx - 0.38, ly - 0.38, top))
        o = kit.mesh_object(f"{h.name}Chimney", geo[0], geo[1], [mat, cap], (x, y, 0.0),
                            face_mats=[0 if k == 0 else 1 for k in geo[2]])
        o.rotation_euler.z = h.rot
        h.objs.append(o)
        w = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(h.rot, 4, "Z") @ Vector((lx, ly, top + 0.12))
        tops.append(tuple(w))
    return tops


def plaza_and_lane():
    dirt = mottle(vl.mat("Lane", "#8A7855"))
    lane = kit.box_span("Lane", LANE_X - 3.2, LANE_X + 3.2, yc(BRIDGE_X) + 7.0, 58.0, -0.03, 0.06, dirt)
    plaza = kit.box_span("Plaza", LANE_X - 8, LANE_X + 8, 25.0, 37.0, -0.025, 0.06, dirt)
    return [lane, plaza, *fountain(*FOUNTAIN)]


def _ring_geo(n, r_in, r_out, z0, z1, phase=0.0):
    """Solid ring (basin): n sides, inner and outer radius, from z0 to z1."""
    rings = []
    for r, z in ((r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0)):
        rings.append([(r * math.cos(phase + 2 * math.pi * i / n), r * math.sin(phase + 2 * math.pi * i / n), z)
                      for i in range(n)])
    v = [p for ring in rings for p in ring]
    f = [(k * n + i, k * n + (i + 1) % n, ((k + 1) % 4) * n + (i + 1) % n, ((k + 1) % 4) * n + i)
         for k in range(4) for i in range(n)]
    return v, f


def fountain(x, y):
    """Square fountain: octagonal stone basin (35 cm rim with protruding cap), water, column with dish."""
    st = vl.mat("FountainStone", "#7A766C")
    st2 = vl.mat("FountainCap", "#8E8A80")
    water = vl.mat("FountainWater", "#2A5478", rough=0.3, emission="#2A6296", strength=0.15)
    ph = math.pi / 8
    parts = [_ring_geo(8, 1.45, 1.8, 0.0, 0.5, ph), _ring_geo(8, 1.38, 1.9, 0.5, 0.62, ph),
             kit._prism_geo(8, 1.5, 1.5, 0.08, oz=0.0),
             kit._prism_geo(8, 0.3, 0.24, 1.15, oz=0.05), kit._prism_geo(8, 0.25, 0.62, 0.16, oz=1.08),
             kit._prism_geo(8, 0.62, 0.6, 0.06, oz=1.24), kit._prism_geo(6, 0.12, 0.05, 0.35, oz=1.3)]
    v, f, own = kit.merge(*parts)
    o = kit.mesh_object("Fountain", v, f, [st, st2], (x, y, 0.0), face_mats=[1 if k in (1, 5) else 0 for k in own])
    kit.fix_normals(o)
    wv, wf = kit._prism_geo(8, 1.47, 1.47, 0.02, oz=0.4)
    w = kit.mesh_object("FountainWater", wv, wf, [water], (x, y, 0.0))
    return [o, w]


def windmill(x, y):
    return vl.place(vl.town("windmill"), (x, y, 3.2), math.radians(180), 2.0, name="Windmill")


# ---------- background ----------

def mountains(rnd):
    near = vl.mat("MtnNear", "#3E5580")
    far = vl.mat("MtnFar", "#566B94")
    out = []
    ring = [(x, 560 + rnd.uniform(0, 60)) for x in range(-760, 761, 85)]
    ring += [(-640 + rnd.uniform(-30, 30), y) for y in range(-420, 520, 90)]
    ring += [(640 + rnd.uniform(-30, 30), y) for y in range(-420, 520, 90)]
    ring += [(x, -520) for x in range(-700, 701, 110)]
    for k, (x, y) in enumerate(ring):
        hgt = rnd.uniform(60, 130)
        r = hgt * rnd.uniform(2.0, 3.0)
        v, f = kit._prism_geo(7, r, r * 0.05, hgt, oz=-5.0)
        out.append(kit.mesh_object(f"Mtn{k}", v, f, [near if k % 2 else far], (x, y, 0)))
        out[-1].visible_shadow = False
    return out


def trees(rnd, count=120):
    """Line of instanced trees (Kenney 'tree' mold), outside the village, the cabin and the river."""
    parts = vl.town("tree")
    objs = []
    tries = 0
    while len(objs) < count and tries < 8000:
        tries += 1
        x, y = rnd.uniform(-170, 170), rnd.uniform(-110, 150)
        if abs(y - yc(x)) < 14 or (-60 < x < 75 and 5 < y < 62) or (-40 < x < 28 and -40 < y < -3):
            continue
        if y < 5 and abs(y) < 45 and abs(x) < 40:
            continue
        s = rnd.uniform(2.1, 3.2) * (1.0 + 0.5 * max(abs(x) - 60, 0) / 100)
        objs += vl.place(parts, (x, y, height(x, y) - 0.1), rnd.uniform(0, 6.28), s, name="Tree")
    return objs


def far_roofs():
    """3 distant village roofs (small houses) to give scale to the background."""
    out = []
    for k, (x, y) in enumerate(((115, 45), (-105, 75), (150, 95))):
        out.append(vh.house(f"far{k}", x, y, math.radians(180), 2, 2))
    return out


# ---------- cabana (interior e quintal) ----------

FZ = 0.3                                                 # cabin floor (the terrain reaches ~0.2 m inside here)


def cabin_interior(cabin):
    """Interior 4.6 x 4.6 m: 1.5 m bookshelf with 4 books (24 x 16 x 3 cm) on the north wall (the window beside it shows the village),
    table with pots, bed on the west wall, floor."""
    x0, y0 = CABIN[1], CABIN[2]
    wood = vl.mat("InWood", "#6A4A30")
    dark = vl.mat("InDark", "#2E2018")
    plank2 = vl.mat("InPlank", "#3A2A1E")
    fl = []
    for k in range(16):                                  # floor of 2-tone boards (top at z 0)
        xa = x0 - 2.2 + k * 0.275
        fl.append((kit._box_geo(0.275, 4.4, 0.3, xa, y0 - 2.2, FZ - 0.3), k % 2))
    v_, f_, own_ = kit.merge(*[g for g, _ in fl])
    floor = kit.mesh_object("CabinFloor", v_, f_, [dark, plank2], face_mats=[fl[o][1] for o in own_])
    sy = y0 + 2.3 - 0.2                                  # north wall (inner)
    sx = x0 - 0.75                                      # shelf x -12.75 .. -11.25 (between the 2 windows)
    parts = [kit._box_geo(1.5, 0.3, 0.04, sx, sy - 0.3, z) for z in (0.45, 0.95, 1.45, 1.95)]
    parts += [kit._box_geo(0.04, 0.3, 2.0, sx, sy - 0.3, 0.0), kit._box_geo(0.04, 0.3, 2.0, sx + 1.46, sy - 0.3, 0.0),
              kit._box_geo(1.5, 0.02, 2.0, sx, sy - 0.04, 0.0)]
    shelf = kit.mesh_object("Shelf", *kit.merge(*parts)[:2], [wood])
    tx, ty = x0 + 1.15, y0 + 0.55                       # table on the right, in front of the shelf
    tp = [kit._box_geo(1.2, 0.75, 0.06, tx - 0.6, ty - 0.375, 0.72)]
    for lx in (-0.55, 0.48):
        for ly in (-0.32, 0.25):
            tp.append(kit._box_geo(0.07, 0.07, 0.72, tx + lx, ty + ly, 0.0))
    for cx_, cy_, back in ((tx - 0.15, ty - 0.75, -1), (tx + 0.95, ty, 0)):      # 2 cadeiras (assento + encosto)
        tp.append(kit._box_geo(0.42, 0.42, 0.05, cx_ - 0.21, cy_ - 0.21, 0.44))
        for lx in (-0.18, 0.13):
            for ly in (-0.18, 0.13):
                tp.append(kit._box_geo(0.05, 0.05, 0.44, cx_ + lx, cy_ + ly, 0.0))
        if back:
            tp.append(kit._box_geo(0.42, 0.05, 0.5, cx_ - 0.21, cy_ - 0.23, 0.49))
        else:
            tp.append(kit._box_geo(0.05, 0.42, 0.5, cx_ + 0.18, cy_ - 0.21, 0.49))
    table = kit.mesh_object("Table", *kit.merge(*tp)[:2], [wood])
    bm = [vl.mat("BedFrame", "#4A3424"), vl.mat("BedSheet", "#B8AC90"), vl.mat("BedBlanket", "#7A3A2E")]
    bxa, bya = x0 - 2.12, y0 - 0.1                       # bed on the west wall: 0.95 x 2.0 m
    bg = [(kit._box_geo(0.95, 2.0, 0.3, bxa, bya, 0.12), 0), (kit._box_geo(0.08, 0.08, 0.12, bxa, bya, 0.0), 0),
          (kit._box_geo(0.08, 0.08, 0.12, bxa + 0.87, bya, 0.0), 0), (kit._box_geo(0.08, 0.08, 0.12, bxa, bya + 1.92, 0.0), 0),
          (kit._box_geo(0.08, 0.08, 0.12, bxa + 0.87, bya + 1.92, 0.0), 0),
          (kit._box_geo(0.95, 0.08, 0.75, bxa, bya + 1.92, 0.0), 0),
          (kit._box_geo(0.87, 1.9, 0.14, bxa + 0.04, bya + 0.02, 0.42), 1),
          (kit._box_geo(0.97, 1.3, 0.06, bxa - 0.01, bya - 0.01, 0.54), 2),
          (kit._box_geo(0.6, 0.32, 0.1, bxa + 0.17, bya + 1.5, 0.56), 1)]
    v_, f_, o_ = kit.merge(*[g for g, _ in bg])
    bed = [kit.mesh_object("Bed", v_, f_, bm, face_mats=[bg[o][1] for o in o_])]
    pots = vl.place(vl.nature("pot_small", True), (tx - 0.3, ty, 0.78), 0.0, 0.9, name="Pot")
    pots += vl.place(vl.nature("pot_large", True), (tx + 0.25, ty + 0.1, 0.78), 0.0, 0.8, name="Pot")
    rug_a = vl.mat("Rug", "#6E3428")
    rug_b = vl.mat("RugBand", "#A0643A")
    rv, rf, ro = kit.merge(kit._box_geo(2.0, 1.4, 0.015, x0 - 1.15, y0 - 1.25, 0.0),
                           kit._box_geo(1.7, 1.1, 0.008, x0 - 1.0, y0 - 1.1, 0.015),
                           kit._box_geo(1.4, 0.8, 0.006, x0 - 0.85, y0 - 0.95, 0.023))
    rug = kit.mesh_object("Rug", rv, rf, [rug_a, rug_b], face_mats=[0 if o == 0 else (1 if o == 1 else 0) for o in ro])
    chest_m = vl.mat("Chest", "#5A3A24")
    band_m = vl.mat("ChestBand", "#2E241C")
    cv, cf, co = kit.merge(kit._box_geo(0.8, 0.45, 0.45, x0 - 2.05, y0 - 1.6, 0.0),
                           kit._box_geo(0.84, 0.49, 0.06, x0 - 2.07, y0 - 1.62, 0.45),
                           kit._box_geo(0.06, 0.47, 0.47, x0 - 1.9, y0 - 1.61, 0.0),
                           kit._box_geo(0.06, 0.47, 0.47, x0 - 1.4, y0 - 1.61, 0.0))
    chest = kit.mesh_object("Chest", cv, cf, [chest_m, band_m], face_mats=[0 if o < 2 else 1 for o in co])
    books, dim = [], []
    for k in range(4):                                  # 4 books standing on the 3rd tier, amber glow per book
        m, sock = vl.glow_mat(f"Book{k}", "#F5A524", 0.0)
        kit.principled(m).inputs["Base Color"].default_value = lin(("#5A3A24", "#3A4A5A", "#4A3A2A", "#5A4A2A")[k])
        b = kit.box(f"Book{k}", (sx + 0.55 + k * 0.1, sy - 0.15, 1.49), (0.05, 0.16, 0.26), m)
        books.append((b, sock))
    dms = [vl.mat(f"BookDim{i}", c) for i, c in enumerate(("#3E342C", "#3A3A42", "#4A3628", "#34302A"))]
    import random as _r
    rb = _r.Random(3)
    for z in (0.45, 0.95, 1.45, 1.95):                  # shelves with unlit books (not empty)
        x = sx + 0.06
        while x < sx + 1.38:
            if z == 1.45 and sx + 0.5 < x < sx + 0.98:
                x = sx + 0.98
                continue
            w, hgt = rb.uniform(0.035, 0.06), rb.uniform(0.18, 0.3) if z < 1.9 else rb.uniform(0.15, 0.22)
            if rb.random() < 0.18:
                x += rb.uniform(0.08, 0.2)
                continue
            dim.append(kit.box(f"BookDim", (x + w / 2, sy - 0.15, z + 0.04), (w, 0.15, hgt), rb.choice(dms)))
            x += w + 0.004
    items = [shelf, table, *bed, *pots, rug, chest, *[b for b, _ in books], *dim]
    for o in items:
        o.location.z += FZ
    return [floor, *items], books


def garden(rnd, stage):
    """Garden beside the door (east of the cabin): Nature Kit beds; stage 0 = small, 1 = large."""
    out = []
    rows = 2 if stage == 0 else 5
    for r in range(rows):
        for k in range(3 if stage == 0 else 5):
            out += vl.place(vl.nature("crops_dirtRow", True), (-8.2 + r * 1.3, -19.5 + k * 1.6, 0.02), math.pi / 2, 1.7,
                            name="Bed")
            out += vl.place(vl.nature("crops_wheatStageB"), (-8.2 + r * 1.3, -19.5 + k * 1.6, 0.03), 0, 1.8,
                            name="Crop")
    return out


def fence(x0, y0, x1, y1, step=2.0):
    out = []
    parts = vl.nature("fence_simple", True)
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
    ang = math.atan2(y1 - y0, x1 - x0)
    for k in range(n):
        u = (k + 0.5) / n
        out += vl.place(parts, (x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, 0), ang, step, name="Fence")
    return out


def carved_post(x, y):
    """2.2 m carved pole (hexagonal, 0.36 m) with stone base, carved rings, pointed capital and the amber line tree
    on the east face (local +x). Returns (objects, sockets)."""
    import random as _r
    wood = vl.mat("PostWood", "#6A4A32")
    dark = vl.mat("PostDark", "#3E2A1C")
    stone = vl.mat("PostStone", "#6E6A62")
    body = [kit._prism_geo(6, 0.19, 0.16, 2.05, oz=0.0)]
    rings = [kit._prism_geo(6, 0.205, 0.2, 0.07, oz=z) for z in (0.12, 1.98)]
    capg = [kit._prism_geo(6, 0.22, 0.0, 0.32, oz=2.05)]
    v, f, own = kit.merge(*body, *rings, *capg)
    post = kit.mesh_object("Post", v, f, [wood, dark], (x, y, 0), face_mats=[0 if k == 0 else 1 for k in own])
    kit.fix_normals(post)
    rr = _r.Random(5)
    sv = []
    for k in range(7):
        a = 2 * math.pi * k / 7 + rr.uniform(-0.2, 0.2)
        sv.append(kit._ico_geo(rr.uniform(0.11, 0.16), (0.3 * math.cos(a), 0.3 * math.sin(a), 0.02), (1.2, 1.0, 0.6)))
    sm = kit.merge(*sv)
    stones = kit.mesh_object("PostStones", sm[0], sm[1], [stone], (x, y, 0))
    m_lines, sock_lines = vl.glow_mat("PostLines", "#F5A524", 0.0)
    m_hot, sock_hot = vl.glow_mat("PostHot", "#FF6A2A", 0.0)
    X = 0.168          # east face of the hexagon: lines 1 cm outward
    segs = []

    def line(y0, z0, y1, z1, w=0.026):
        ln = math.hypot(y1 - y0, z1 - z0)
        ang = math.atan2(z1 - z0, y1 - y0)
        v_, f_ = kit._box_geo(0.02, ln, w, 0, 0, -w / 2)
        o = kit.mesh_object("Line", v_, f_, [m_lines], (x + X, y + y0, z0))
        o.rotation_euler = (ang, 0, 0)
        o.visible_shadow = False
        segs.append(o)

    line(-0.07, 0.25, -0.07, 0.9)       # roots: two equal branches, rise in parallel
    line(0.07, 0.25, 0.07, 0.9)
    line(-0.07, 0.9, 0.07, 1.5)         # they cross: the two lines meet
    line(0.07, 0.9, -0.07, 1.5)
    line(-0.07, 1.5, -0.07, 1.92)       # and continue upward
    line(0.07, 1.5, 0.07, 1.92)
    for zz in (0.25,):                  # root nodes (small diamonds)
        for yy in (-0.07, 0.07):
            gv, gf = kit._gem_geo(0.03)
            g = kit.mesh_object("Knot", gv, gf, [m_lines], (x + X + 0.005, y + yy, zz))
            g.visible_shadow = False
            segs.append(g)
    hv, hf = kit._gem_geo(0.07)
    hot = kit.mesh_object("PostHot", hv, hf, [m_hot], (x + X + 0.02, y, 1.2))
    hot.visible_shadow = False
    return [post, stones, *segs, hot], (sock_lines, sock_hot)


def _tongue_geo(h, r, bend, twist, n=6):
    """Tongue of flame: rings that taper to the tip, with S curve (bend) and twist; rounded base."""
    pts, rad = [], []
    for k in range(7):
        u = k / 6
        pts.append((bend * math.sin(math.pi * u) * u, 0.3 * bend * math.sin(2 * math.pi * u), h * u))
        rad.append(r * (0.55 + 0.45 * math.sin(math.pi * min(u * 1.6, 1.0))) * (1 - u) ** 0.8 + 0.004)
    return kit.tube_geo(pts, rad, n=n, twist=twist)


def fire(x, y, scale=1.0, ring=1.0, f0=1, f1=2, seed=0, fade=None):
    """Bonfire: firewood and stones (Nature Kit, recolored), layered flame (7 orange tongues with curve and 4 light
    amber cores), ember on the ground and 10 sparks that rise in a cycle. The flame undulates by scale (LINEAR keys every
    2 frames, slow waves summed: no jump). The light is constant (only changes in the final pause, in a ramp).
    fade=(fa, fb): the flame lowers until it vanishes from fa to fb (end signal) and the sparks stop being born at fa.
    Returns (objects, flame socket, light, ember socket, tongues)."""
    import random as _r
    rr = _r.Random(seed)
    logs = vl.place(vl.nature("campfire_logs", True), (x, y, 0.0), 0, 3.0 * scale * ring, name="Fire")
    rocks = vl.place(vl.nature("campfire_stones", "stone"), (x, y, 0.0), 0, 3.0 * scale * ring, name="FireStones")
    m, sock = vl.glow_mat("FlameMat", "#FF8A1E", 7.0)
    kit.principled(m).inputs["Base Color"].default_value = kit.lin("#FF8A1E")
    core = vl.mat("FlameCore", "#FFC24A", emission="#FFC24A", strength=9.0)
    m2, esock = vl.glow_mat("EmberMat", "#FF6A1A", 2.5)
    objs = list(logs) + list(rocks)
    tongues = []
    for k in range(11):
        inner = k >= 7
        a = 2 * math.pi * k / 7 + rr.uniform(-0.3, 0.3)
        rd = (0.0 if inner else 0.11) * scale * ring
        hgt = (rr.uniform(0.35, 0.5) if inner else rr.uniform(0.45, 0.85)) * scale
        rad = (0.07 if inner else 0.11) * scale
        v, f = _tongue_geo(hgt, rad, rr.uniform(0.04, 0.1) * scale, rr.uniform(0, 1))
        o = kit.mesh_object("Flame", v, f, [core if inner else m],
                            (x + rd * math.cos(a) + (rr.uniform(-0.05, 0.05) * scale if inner else 0),
                             y + rd * math.sin(a), 0.1 * scale))
        o.rotation_euler = (math.radians(rr.uniform(-8, 8)), math.radians(rr.uniform(-8, 8)), a)
        o.visible_shadow = False
        kit.fix_normals(o)
        ph, sp = rr.uniform(0, 6.28), rr.uniform(0.9, 1.3)
        for fr in range(f0, f1 + 1, 2):
            t = fr * sp
            sz = 1.0 + 0.16 * math.sin(t * 0.31 + ph) + 0.08 * math.sin(t * 0.73 + 2 * ph)
            sx = 1.0 + 0.08 * math.sin(t * 0.47 + ph + 1)
            e = 1.0
            if fade:
                u_ = min(max((fr - fade[0]) / (fade[1] - fade[0]), 0.0), 1.0)
                e = 1.0 - u_ * u_ * (3 - 2 * u_)
            o.scale = (sx * (0.25 + 0.75 * e), sx * (0.25 + 0.75 * e), max(sz * e, 0.0))
            o.keyframe_insert("scale", frame=fr)
            o.rotation_euler.z = a + 0.25 * math.sin(t * 0.11 + ph)
            o.keyframe_insert("rotation_euler", index=2, frame=fr)
        vl.linear(o)
        objs.append(o)
        tongues.append(o)
    gv, gf = kit._gem_geo(0.018 * scale)
    spark_me = vl.mesh_from_geo("FireSpark", (gv, gf), core)
    for k in range(10):
        sp = vl.obj_of(f"FireSpark{k}", spark_me, (x, y, 0.3 * scale))
        sp.visible_shadow = False
        period = rr.randint(34, 50)
        start = f0 - rr.randint(0, period)
        dx, dy = rr.uniform(-0.25, 0.25), rr.uniform(-0.25, 0.25)
        cyc = start
        while cyc < (fade[0] if fade else f1):
            for u in (0.0, 0.13, 0.5, 0.87, 1.0):
                fr = cyc + int(u * period)
                if fr < f0 - 60 or fr > f1 + 60:
                    continue
                s_ = 0.0 if u in (0.0, 1.0) else (1.0 - 0.7 * u)
                sp.location = (x + dx * u * scale, y + dy * u * scale, (0.3 + 1.4 * u) * scale)
                sp.scale = (s_, s_, s_)
                sp.keyframe_insert("location", frame=fr)
                sp.keyframe_insert("scale", frame=fr)
            cyc += period
        vl.linear(sp)
        objs.append(sp)
    v, f = kit._ico_geo(0.36 * scale * ring, (0, 0, 0), (1.0, 1.0, 0.16))
    emb = kit.mesh_object("Ember", v, f, [m2], (x, y, 0.06 * scale))
    emb.visible_shadow = False
    objs.append(emb)
    ld = bpy.data.lights.new("FireLight", "POINT")
    ld.color, ld.energy, ld.shadow_soft_size, ld.use_shadow = (1.0, 0.55, 0.22), 260.0 * scale, 0.2, False
    lo = bpy.data.objects.new("FireLight", ld)
    bpy.context.collection.objects.link(lo)
    lo.location = (x, y, 0.8 * scale)
    objs.append(lo)
    return objs, sock, ld, esock, tongues


def lantern_mesh(r=0.08):
    """Paper lantern: octagonal body wider at the top (r), narrower mouth at the bottom, height 1.3 r; the whole
    paper glows amber (emissive material, strength animated by the scene)."""
    m, sock = vl.glow_mat("LanternMat", "#F5A524", 0.0)
    v, f = kit._prism_geo(8, 0.72 * r, r, 1.3 * r, oz=-0.65 * r)
    return vl.mesh_from_geo("Lantern", (v, f), m), m, sock


def _blocked(x, y):
    t = y - yc(x)
    if abs(t) < 8.6:
        return True
    if -16.5 < x < -7.5 and -19 < y < -11.5 or (-9 < x < -2.5 and -20.5 < y < -12):    # cabana e horta
        return True
    if abs(x - LANE_X) < 3.8 and y > 8 or (abs(x - LANE_X) < 2.4 and abs(y) < 12):
        return True
    if abs(x - LANE_X) < 9 and 24 < y < 38:
        return True
    return False


def ground_cover(rnd, grass=0, rocks=120, flowers=160, bushes=40):
    """Grass, stones, flowers and bushes (Nature Kit, instances) in 3 layers: south bank, village bank, hill."""
    out = []
    gp = [vl.nature("grass_large", "green"), vl.nature("grass", "green"), vl.nature("grass_leafsLarge", "green")]
    fl = [vl.nature(n, "plant") for n in ("flower_redA", "flower_yellowA", "flower_purpleA", "flower_yellowC", "flower_purpleC")]
    rk = [vl.nature(n, "stone") for n in ("rock_smallA", "rock_smallB", "rock_smallC", "stone_largeA", "stone_smallE",
                                 "rock_smallFlatA", "stone_largeC")]
    bs = [vl.nature(n, "green") for n in ("plant_bush", "plant_bushLarge", "plant_bushSmall", "plant_bushDetailed")]
    zones = [(-45, 50, -48, -9.0, 0.55), (-70, 80, 9.5, 90, 0.35), (-40, 40, -75, -48, 0.10)]
    for kind, n in (("g", grass), ("r", rocks), ("f", flowers), ("b", bushes)):
        made = 0
        while made < n:
            r = rnd.random()
            acc = 0.0
            for z in zones:
                acc += z[4]
                if r < acc:
                    break
            x, y = rnd.uniform(z[0], z[1]), rnd.uniform(z[2], z[3])
            if _blocked(x, y):
                continue
            made += 1
            if kind == "g":
                out += vl.place(gp[made % 3], (x, y, height(x, y) - 0.02), rnd.uniform(0, 6.28), rnd.uniform(1.2, 2.0),
                                name="Cover")
            elif kind == "r":
                out += vl.place(rk[made % len(rk)], (x, y, height(x, y) - 0.04), rnd.uniform(0, 6.28),
                                rnd.uniform(0.9, 1.9), name="Rock")
            elif kind == "f":
                out += vl.place(fl[made % 5], (x, y, height(x, y) - 0.02), rnd.uniform(0, 6.28), rnd.uniform(1.0, 1.6),
                                name="Flower")
            else:
                out += vl.place(bs[made % 4], (x, y, height(x, y) - 0.02), rnd.uniform(0, 6.28), rnd.uniform(2.2, 3.6),
                                name="Bush")
    keep_out = [(-4.0, -13.6), (0.0, -15.5), (-3.2, -14.4), (-3.0, -36.0), (-1.2, -20.2), (-2.5, -38.5), (-2.5, -37.0), (-2.9, -10.7), (-1.6, -10.2)]
    for (bx0, bx1, by0, by1), ng, nr, nf, nb in (((-22, 16, -46, -20.6), 0, 30, 60, 14),
                                                  ((-16, 16, -25, -9.5), 0, 22, 40, 8)):
        for kind, n in (("g", ng), ("r", nr), ("f", nf), ("b", nb)):
            made = 0
            while made < n:
                x, y = rnd.uniform(bx0, bx1), rnd.uniform(by0, by1)
                if _blocked(x, y) or any((x - kx) ** 2 + (y - ky) ** 2 < 2.2 ** 2 for kx, ky in keep_out):
                    continue
                made += 1
                z = height(x, y)
                if kind == "g":
                    out += vl.place(gp[made % 3], (x, y, z - 0.02), rnd.uniform(0, 6.28), rnd.uniform(0.7, 1.1), name="Cover")
                elif kind == "r":
                    out += vl.place(rk[made % len(rk)], (x, y, z - 0.04), rnd.uniform(0, 6.28), rnd.uniform(0.9, 1.9), name="Rock")
                elif kind == "f":
                    out += vl.place(fl[made % 5], (x, y, z - 0.02), rnd.uniform(0, 6.28), rnd.uniform(1.0, 1.6), name="Flower")
                else:
                    out += vl.place(bs[made % 4], (x, y, z - 0.02), rnd.uniform(0, 6.28), rnd.uniform(2.2, 3.6), name="Bush")
    for k in range(260):                                       # river banks: reeds and stones at the waterline
        x = rnd.uniform(-60, 70)
        side = -1 if k % 2 else 1
        y = yc(x) + side * rnd.uniform(7.6, 8.8)
        if abs(x - BRIDGE_X) < 2.6:
            continue
        is_rock = k % 3 == 0
        pick = rk[rnd.randrange(len(rk))] if is_rock else gp[0]
        out += vl.place(pick, (x, y, max(height(x, y), -0.3) - 0.02), rnd.uniform(0, 6.28),
                        rnd.uniform(0.8, 1.5) if is_rock else rnd.uniform(1.6, 2.6), name="Reed")
    return out


# ---------- fine grass (Geometry Nodes) ----------

def _seg_dist(px, py, pts):
    best = 1e9
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1e-9
        u = min(max(((px - x0) * dx + (py - y0) * dy) / L2, 0.0), 1.0)
        best = min(best, math.hypot(px - x0 - u * dx, py - y0 - u * dy))
    return best


def _tuft_mesh(name, k, mat):
    """Grass tuft: 5 to 7 triangular blades (base 3.5 cm, 9 to 20 cm tall) opening outward."""
    import random as _r
    rnd = _r.Random(k)
    v, f = [], []
    nb = 5 + k % 3
    for i in range(nb):
        a = 2 * math.pi * i / nb + rnd.uniform(-0.3, 0.3)
        hgt = rnd.uniform(0.09, 0.2)
        lean = rnd.uniform(0.03, 0.08)
        ca, sa = math.cos(a), math.sin(a)
        r0 = 0.025
        bx, by = r0 * ca, r0 * sa
        px, py = -sa * 0.018, ca * 0.018
        base = len(v)
        v += [(bx - px, by - py, -0.02), (bx + px, by + py, -0.02), (bx + lean * ca, by + lean * sa, hgt)]
        f.append((base, base + 1, base + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    me.update()
    return me


def grass_carpet(houses=(), keep_out=(), density=16.0, seed=3):
    """Fine grass (tufts of 14 to 30 cm) scattered by Geometry Nodes over a 1 m base mesh on both banks
    near the cameras; density 0 on the river, trails, alley, square, garden, cabin and houses. A single object."""
    mats = [mottle(vl.mat(f"Tuft{i}", c), 1.0) for i, c in enumerate(("#6A8C55", "#5E7E4C", "#7A9058"))]
    col = bpy.data.collections.new("TuftModels")
    bpy.context.scene.collection.children.link(col)
    bpy.context.view_layer.layer_collection.children["TuftModels"].exclude = True
    for k in range(3):
        o = bpy.data.objects.new(f"Tuft{k}", _tuft_mesh(f"Tuft{k}", k, mats[k]))
        col.objects.link(o)
    zones = [(-34.0, 24.0, -48.0, -8.0), (-22.0, 32.0, 8.0, 50.0)]
    verts, faces, wts = [], [], []
    for (x0, x1, y0, y1) in zones:
        nx_, ny_ = int(x1 - x0), int(y1 - y0)
        base = len(verts)
        for j in range(ny_ + 1):
            for i in range(nx_ + 1):
                x, y = x0 + i, y0 + j
                verts.append((x, y, height(x, y)))
                w = 1.0
                if _blocked(x, y):
                    w = 0.0
                if any(_seg_dist(x, y, pts) < 0.8 for pts in TRAILS):
                    w = 0.0
                if any(math.hypot(x - hx, y - hy) < r for hx, hy, r in houses):
                    w = 0.0
                if any(math.hypot(x - hx, y - hy) < r for hx, hy, r in keep_out):
                    w = 0.0
                wts.append(w)
        for j in range(ny_):
            for i in range(nx_):
                a = base + j * (nx_ + 1) + i
                faces.append((a, a + 1, a + nx_ + 2, a + nx_ + 1))
    me = bpy.data.meshes.new("GrassBase")
    me.from_pydata(verts, [], faces)
    me.update()
    base_obj = bpy.data.objects.new("GrassCarpet", me)
    bpy.context.collection.objects.link(base_obj)
    g = base_obj.vertex_groups.new(name="dens")
    for i, w in enumerate(wts):
        if w > 0:
            g.add([i], w, "REPLACE")
    ng = bpy.data.node_groups.new("GrassScatter", "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    dsock = ng.interface.new_socket("Density Mask", in_out="INPUT", socket_type="NodeSocketFloat")
    dsock.default_value = 1.0
    N, L = ng.nodes, ng.links
    gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    dist.inputs["Density"].default_value = density
    dist.inputs["Seed"].default_value = seed
    L.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    mulnode = N.new("ShaderNodeMath")
    mulnode.operation = "GREATER_THAN"
    mulnode.inputs[1].default_value = 0.5
    L.new(gin.outputs["Density Mask"], mulnode.inputs[0])
    L.new(mulnode.outputs[0], dist.inputs["Selection"])
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = col
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rr = N.new("FunctionNodeRandomValue")
    rr.data_type = "FLOAT_VECTOR"
    rr.inputs["Max"].default_value = (0, 0, 2 * math.pi)
    rr.inputs["Seed"].default_value = seed + 1
    rs = N.new("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    rs.inputs["Min"].default_value, rs.inputs["Max"].default_value = 0.7, 1.3
    rs.inputs["Seed"].default_value = seed + 2
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    L.new(dist.outputs["Points"], inst.inputs["Points"])
    L.new(info.outputs["Instances"], inst.inputs["Instance"])
    L.new(rr.outputs["Value"], inst.inputs["Rotation"])
    L.new(rs.outputs["Value"], inst.inputs["Scale"])
    L.new(inst.outputs["Instances"], gout.inputs["Geometry"])
    mod = base_obj.modifiers.new("GrassScatter", "NODES")
    mod.node_group = ng
    ident = next(i.identifier for i in ng.interface.items_tree
                 if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == "Density Mask")
    entry = getattr(mod.properties.inputs, ident)
    entry.type, entry.attribute_name = "ATTRIBUTE", "dens"
    base_obj.visible_shadow = False
    return base_obj


def smoke(tops, f0, f1, colors):
    """Chimney smoke: 8 faceted lumps per chimney in a continuous line, matte and opaque, that rise 6 m, grow and
    then shrink until they vanish (never loose shiny spheres). colors: [(frame, '#hex')] switched only on the cuts."""
    mat = vl.mat("Smoke", colors[0][1], rough=1.0)
    p = kit.principled(mat)
    for fr, c in colors:
        p.inputs["Base Color"].default_value = kit.lin(c)
        p.inputs["Base Color"].keyframe_insert("default_value", frame=fr)
    vl.constant(mat.node_tree)
    me = vl.mesh_from_geo("Puff", kit._ico_geo(0.5, (0, 0, 0), (1.0, 1.0, 0.72)), mat)
    out = []
    period = 200
    for k, (x, y, z) in enumerate(tops):
        for j in range(8):
            sp = vl.obj_of(f"Smoke{k}_{j}", me, (x, y, z), (0, 0, 0.4 * j), (0, 0, 0))
            sp.visible_shadow = False
            fr0 = f0 - (j * period // 8) - (k * 13) % 30
            while fr0 < f1:
                for u, zz, sc, dx in ((0.0, 0.0, 0.35, 0.0), (0.15, 0.8, 0.8, 0.2), (0.45, 2.6, 1.3, 0.9),
                                      (0.75, 4.4, 1.5, 1.8), (1.0, 6.0, 0.0, 2.5)):
                    fr = fr0 + int(u * period)
                    if f0 - 80 <= fr <= f1 + 80:
                        sp.location = (x + dx, y + 0.3 * dx, z + zz)
                        sp.scale = (sc, sc, sc)
                        sp.keyframe_insert("location", frame=fr)
                        sp.keyframe_insert("scale", frame=fr)
                fr0 += period
            vl.linear(sp)
            out.append(sp)
    return out
