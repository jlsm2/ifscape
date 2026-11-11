"""'riverside' stage: promenade along a mid-sized city's river, with a cable-stayed footbridge, construction crane and mountain range in the background
(gravity-doubled).

Plan (meters; POV camera at [0, 0] looking +y; the promenade sits at z = 0):
- OUR PROMENADE: wide paving slabs from x -120 to 120, y -8 to 9. Foreground free x -8..8, y 1..8 (witness, scale).
  Slatted benches facing the river (backs to the camera, seat at y = 6.7, x = -6.5, -3.0, 0.5; whoever sits
  with 'Sitting' is at [x, 6.9], "z": 0.06, "face": 90). Drinks kiosk x -2.0..-0.4, y 7.3..8.7 with a porch of
  plaster ceiling (z 2.45) that extends to y 5.2 over two small posts. Plane trees in pits at y = 4.6 (x <= -10 and >= 11),
  black lamp posts and trash cans. Behind the camera: street and a row of buildings (y -20).
- Steel GUARDRAIL at y = 9.0 (1.1 m) with an opening x 3.5..6.5 (footbridge head).
- RIVER: stone quay wall (face at y 9.4 and 48.6), water at z = -2.6 (light Geometry Nodes ripple that fades with
  distance, tones in bands along the current, dark edge next to the walls), from x -400 to 400.
- CABLE-STAYED FOOTBRIDGE: 2.4 m deck at x = 5, from y 9 to 49 (rises 0.3 m in the middle), 16 m A-shaped pylon at y = 24
  (feet in the water), 22 fan stays, guardrails. Cue 'sag' (shape key) lowers the deck and stretches the stays.
- OPPOSITE BANK: quay with a stone parapet (0.6 m), walkway y 49..57 with plane trees, pedestrian promenade, 3 layers of
  buildings (Kenney City Kit Commercial: low row at y 67.5, towers at 95-160 m outside the central wedge, horizon of
  blocks out to 320 m); CONSTRUCTION SITE (x -32..-12) with an 8-story building under construction and a 48 m TOWER CRANE at [-16, 72] (jib of
  36 m pointing along the river's diagonal); SEQUOIA of ~45 m at [-26, 58] (target of 'dry'); low bluish MOUNTAIN RANGE at
  650-1000 m (central peak [0, 820] at ~420 m).
- People in the background (always in action): a couple walking on the opposite bank's promenade and a runner; both stop (or swap the
  run for a step) on the camera cue 'sink' and continue more slowly (doubled weight).

References (real numbers): 40 m pedestrian cable-stayed footbridge with a single pylon (Ponte Joaquim Cardozo and the
Capibaribe footbridge, Recife; Passerelle Saint-Georges, Lyon): deck 2.5-3 m, pylon 15-20 m, stays of 6-10 cm;
stone quay 2.5-3.5 m above the water on the Rhône in Lyon (Quai Saint-Antoine); urban construction-site tower crane: tower of
40-50 m, jib 30-50 m, counter-jib 10-15 m with a concrete ballast (Liebherr 150 EC-B); adult giant sequoia: 50-85 m,
narrow conical crown. Low-poly style: Kenney City Kit Commercial (CC0) and Quaternius (CC0).
"""

import math
import random
from types import SimpleNamespace

import bpy
import bmesh
from mathutils import Matrix, Vector

import kit
import rigs
from lib import anim_curves as ac

import models
import park

RAIL_Y, RAIL_H = 9.0, 1.1
GAP = (3.5, 6.5)
QUAY_NEAR, QUAY_FAR = 9.4, 48.6           # faces of the quay walls
FAR_TOP = 49.0                            # start of the opposite bank's walkway
WATER_Z = -1.8                            # river 1.8 m below the promenade (low quay: the water shows between the uprights)
BRIDGE_X, BRIDGE_HW = 5.0, 1.2
BRIDGE_Y = (9.0, 49.0)
CAMBER = 0.3
PYLON_Y, PYLON_H = 24.0, 16.0
ROW1_Y = 67.5
LOT = (-32.0, -12.0)
CRANE_AT, CRANE_H, JIB_LEN, CJIB_LEN = (-16.0, 72.0), 46.0, 36.0, 12.0
JIB_DIR = math.atan2(0.87, 0.5)            # jib to the right and to the back: away from the sequoia, sideways, tip in the S4 frame
TROLLEY_S, HOOK_DROP = 25.0, 22.0
SEQUOIA_AT, SEQUOIA_H = (-26.0, 58.0), 45.0
KIOSK = (-2.0, -0.4, 7.3, 8.7)
PORCH = (-2.3, -0.3, 5.2, 7.3, 2.45)       # x0, x1, y0, y1, ceiling height
BENCHES = [(-6.5, 6.7), (-3.0, 6.7), (0.5, 6.7)]     # center of the seat, facing +y (the river)
TREES_NEAR = [(-10.0, 4.6), (-17.0, 4.6), (-24.0, 4.6), (-31.0, 4.6), (-38.0, 4.6), (11.0, 4.6), (18.0, 4.6),
              (25.0, 4.6), (32.0, 4.6), (39.0, 4.6)]
LAMPS_AT = [(-12.5, 8.55), (-4.6, 8.55), (8.6, 8.55), (14.5, 8.55), (21.5, 8.55), (-20.0, 8.55), (28.5, 8.55)]
RIDGE_PEAKS = [(0.0, 820.0, 420.0, 170.0), (-250.0, 760.0, 320.0, 150.0), (240.0, 880.0, 370.0, 170.0),
               (-560.0, 860.0, 380.0, 200.0), (520.0, 790.0, 300.0, 160.0), (-900.0, 950.0, 420.0, 230.0),
               (880.0, 960.0, 400.0, 230.0), (-120.0, 960.0, 330.0, 160.0), (120.0, 700.0, 210.0, 110.0)]
PLATFORMS = []                            # (x, y, radius, height): scale (whoever steps on rises 5 cm)
EVENTS = []                               # frames of the camera cue 'sink' (the background people react)
TARGETS = {}                              # name -> SimpleNamespace(obj, height, at): cue targets
_reg = {"sag": [], "bend": [], "fall": [], "buckle": {}, "slump": [], "walkers": [], "crack": []}
_mats = {}


# ---------- utilidades ----------

def _mat(name, hexa, rough=0.9, spec=0.15):
    key = (name, hexa)
    if key not in _mats:
        m = kit.flat(f"R_{name}", hexa, rough=rough)
        p = kit.principled(m)
        if "Specular IOR Level" in p.inputs:
            p.inputs["Specular IOR Level"].default_value = spec
        _mats[key] = m
    return _mats[key]


def _P():
    import procedural
    return procedural


def _mesh(name, parts, mats, coll, location=(0, 0, 0)):
    return _P()._mesh(name, parts, mats, coll, location)


def _box(x0, x1, y0, y1, z0, z1):
    return _P()._box(x0, x1, y0, y1, z0, z1)


def _cyl(n, r0, r1, z0, z1, cx=0.0, cy=0.0, rot=0.0):
    return _P()._cyl(n, r0, r1, z0, z1, cx, cy, rot)


def _bar(p, q, r, n=4, rot=0.785, r1=None):
    """Prism with n sides from p to q (stay, truss bar, pylon leg); r1 tapers at the q tip."""
    p, q = Vector(p), Vector(q)
    d = (q - p).normalized()
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(a).normalized()
    v = d.cross(u).normalized()
    r1 = r if r1 is None else r1
    verts = []
    for c, rr in ((p, r), (q, r1)):
        for i in range(n):
            t = rot + math.tau * i / n
            verts.append(tuple(c + (u * math.cos(t) + v * math.sin(t)) * rr))
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, f


def _tube(points, r, n=4):
    """Tube through several points (stay with rings in the middle: vibration and 'sag' deform by shape key)."""
    pts = [Vector(p) for p in points]
    d = (pts[-1] - pts[0]).normalized()
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(a).normalized()
    v = d.cross(u).normalized()
    verts, faces = [], []
    for c in pts:
        for i in range(n):
            t = 0.785 + math.tau * i / n
            verts.append(tuple(c + (u * math.cos(t) + v * math.sin(t)) * r))
    for k in range(len(pts) - 1):
        a0, b0 = k * n, (k + 1) * n
        faces += [(a0 + i, a0 + (i + 1) % n, b0 + (i + 1) % n, b0 + i) for i in range(n)]
    faces += [tuple(range(n - 1, -1, -1)), tuple(range(len(verts) - n, len(verts)))]
    return verts, faces


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _out_back(u, s=1.4):
    u = max(0.0, min(1.0, u)) - 1.0
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def deck_z(y):
    """Height of the footbridge deck top (rises CAMBER in the middle)."""
    u = (y - BRIDGE_Y[0]) / (BRIDGE_Y[1] - BRIDGE_Y[0])
    return CAMBER * math.sin(math.pi * max(0.0, min(1.0, u)))


def sag_profile(y):
    """Shape of the deck sag (1 = middle of the larger span): two spans supported on the pylon and on the banks."""
    if y <= BRIDGE_Y[0] or y >= BRIDGE_Y[1]:
        return 0.0
    if y < PYLON_Y:
        return 0.55 * math.sin(math.pi * (y - BRIDGE_Y[0]) / (PYLON_Y - BRIDGE_Y[0]))
    return math.sin(math.pi * (y - PYLON_Y) / (BRIDGE_Y[1] - PYLON_Y))


def surface_height(x, y):
    """Where a piece stands: promenades (0), scale (+5 cm), footbridge deck or the water."""
    for px, py, r, h in PLATFORMS:
        if math.hypot(x - px, y - py) < r:
            return h
    if QUAY_NEAR < y < QUAY_FAR:
        if abs(x - BRIDGE_X) < BRIDGE_HW:
            return deck_z(y)
        return WATER_Z
    return 0.0


# ---------- ground, quay and water ----------

def _tiles(coll, rng, name, x0, x1, y0, y1, w, d, tones, z=0.0):
    """Paving slabs (one face per stone, tone drawn among 'tones'): the pattern shows through the tone change, no gaps."""
    mats = [_mat(f"{name}{k}", h, 0.95, 0.08) for k, h in enumerate(tones)]
    verts, faces, mi = [], [], []
    y = y0
    row = 0
    while y < y1 - 1e-6:
        ya = min(y1, y + d)
        x = x0 - (w / 2 if row % 2 else 0.0)
        while x < x1 - 1e-6:
            xa, xb = max(x0, x), min(x1, x + w)
            base = len(verts)
            verts += [(xa, y, z), (xb, y, z), (xb, ya, z), (xa, ya, z)]
            faces.append((base, base + 1, base + 2, base + 3))
            mi.append(rng.randrange(len(mats)))
            x += w
        y = ya
        row += 1
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    for p, i in zip(me.polygons, mi):
        p.material_index = i
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def _ground(coll, rng):
    _tiles(coll, rng, "prom_near", -60, 60, -8.0, 8.8, 0.6, 0.6, ("#B7B0A3", "#B0A99C", "#BDB6A9", "#AAA396", "#B5AD9F"))
    _tiles(coll, rng, "prom_near_mid", -120, -60, -8.0, 8.8, 1.2, 1.2, ("#B7B0A4", "#AFA89B", "#BEB7AA"))
    _tiles(coll, rng, "prom_near_mid2", 60, 120, -8.0, 8.8, 1.2, 1.2, ("#B7B0A4", "#AFA89B", "#BEB7AA"))
    _paving_details(coll, rng)
    _tiles(coll, rng, "prom_near_far", -400, -120, -8.0, 8.8, 6.0, 4.0, ("#B6AFA3",))
    _tiles(coll, rng, "prom_near_far2", 120, 400, -8.0, 8.8, 6.0, 4.0, ("#B6AFA3",))
    stone, asph, base = _mat("coping", "#CFCAC0", 0.9), _mat("asphalt", "#5D6168", 0.9, 0.1), _mat("city_floor", "#8C8A86", 1.0, 0.05)
    parts = [(*_box(-400, 400, 8.8, QUAY_NEAR, 0.0, 0.06), 0),                     # quay cap stone
             (*_box(-400, 400, -16.0, -8.0, -0.15, -0.12), 1),                      # street behind the camera
             (*_box(-400, 400, -19.5, -16.0, -0.15, 0.0), 0)]
    _mesh("near_coping", parts, [stone, asph], coll)
    # opposite bank: quay cap, walkway, street (hidden behind the parapet at eye level), sidewalk
    _tiles(coll, rng, "prom_far", -400, 400, FAR_TOP + 0.4, 57.0, 2.0, 1.5, ("#B4AD9F", "#ABA496", "#BAB3A6"))
    parts = [(*_box(-400, 400, QUAY_FAR, FAR_TOP + 0.4, 0.0, 0.06), 0),
             (*_box(-400, 400, 57.0, 64.5, -0.15, -0.12), 1),
             (*_box(-400, 400, 64.5, ROW1_Y, -0.15, 0.0), 0)]
    _mesh("far_ground", parts, [stone, asph], coll)
    R = 900.0                                     # city ground on both sides (the river stays free between the walls)
    _mesh("city_floor", [([(-R, -R, -0.18), (R, -R, -0.18), (R, 8.8, -0.18), (-R, 8.8, -0.18)], [(0, 1, 2, 3)], 0),
                          ([(-R, FAR_TOP, -0.18), (R, FAR_TOP, -0.18), (R, R, -0.18), (-R, R, -0.18)], [(0, 1, 2, 3)], 0)],
          [base], coll)


def _paving_details(coll, rng):
    """Dark granite strips (every 3.6 m, in x and along the quay), drainage grates and plane-tree leaves
    fallen in the foreground (the ground does not stay smooth: G4 rule, ground without function <= 1/3 of the frame)."""
    gran, grate, leafs = (_mat("granite", "#96918A", 0.85, 0.1), _mat("drain", "#5A5D5F", 0.6, 0.3),
                          [_mat(f"leaf{k}", h, 0.9, 0.05) for k, h in enumerate(("#9C7B3C", "#7E7B3A", "#B08A46", "#6F6A34"))])
    parts = []
    x = -59.4
    while x < 60:
        parts.append((*_box(x - 0.09, x + 0.09, -8.0, 8.8, 0.0, 0.003), 0))
        x += 3.6
    for yy in (2.0, 8.5):
        parts.append((*_box(-60, 60, yy - 0.09, yy + 0.09, 0.0, 0.004), 0))
    for gx in (-5.4, 1.8, 9.0, -12.6):                           # drainage grates in the middle strip
        parts.append((*_box(gx - 0.45, gx + 0.45, 1.9, 2.1, 0.0, 0.006), 1))
    _mesh("paving_bands", parts, [gran, grate], coll)
    verts, faces, mi = [], [], []
    for k in range(260):
        x, y = rng.uniform(-14, 14), rng.uniform(-1.0, 8.6)
        if rng.random() < 0.5:                                    # more leaves next to the pits and the guardrail
            x, y = rng.uniform(-14, 14), rng.uniform(7.6, 8.7)
        s = rng.uniform(0.05, 0.09)
        a = rng.uniform(0, math.tau)
        base = len(verts)
        for j in range(5):
            t = a + math.tau * j / 5
            r = s * (1.0 if j % 2 == 0 else 0.6)
            verts.append((x + r * math.cos(t), y + r * math.sin(t), 0.006 + rng.uniform(0, 0.004)))
        faces.append(tuple(range(base, base + 5)))
        mi.append(rng.randrange(4))
    me = bpy.data.meshes.new("fallen_leaves")
    me.from_pydata(verts, [], faces)
    for m in leafs:
        me.materials.append(m)
    for p, i in zip(me.polygons, mi):
        p.material_index = i
    o = bpy.data.objects.new("fallen_leaves", me)
    coll.objects.link(o)
    o.visible_shadow = False


def _quay_walls(coll, rng):
    """Stone quay walls (1.1 x 0.55 m blocks in 3 tones, dark wet band next to the water, slime line).
    Only the opposite bank's face shows head-on; ours is a smooth face (the camera does not see it)."""
    tones = [_mat("quay_a", "#9C968A", 0.95, 0.05), _mat("quay_b", "#8F897D", 0.95, 0.05), _mat("quay_c", "#A7A194", 0.95, 0.05),
             _mat("quay_wet", "#5E5A50", 0.7, 0.2), _mat("quay_moss", "#4F5A3E", 0.9, 0.05)]
    verts, faces, mi = [], [], []
    yf = QUAY_FAR
    rows = int((0.0 - (WATER_Z - 0.6)) / 0.55) + 1
    for r in range(rows):
        z1 = -r * 0.55
        z0 = max(WATER_Z - 0.6, z1 - 0.55)
        x = -400.0 + (0.55 if r % 2 else 0.0)
        while x < 400.0:
            w = 1.1 if abs(x) < 220 else 8.0
            base = len(verts)
            verts += [(x, yf, z0), (x + w, yf, z0), (x + w, yf, z1), (x, yf, z1)]
            faces.append((base, base + 3, base + 2, base + 1))
            mi.append(rng.randrange(3))
            x += w
    for z0, z1, m in ((WATER_Z - 0.6, WATER_Z + 0.35, 3), (WATER_Z + 0.35, WATER_Z + 0.5, 4)):   # molhado e limo
        base = len(verts)
        verts += [(-400, yf - 0.01, z0), (400, yf - 0.01, z0), (400, yf - 0.01, z1), (-400, yf - 0.01, z1)]
        faces.append((base, base + 3, base + 2, base + 1))
        mi.append(m)
    me = bpy.data.meshes.new("quay_far_face")
    me.from_pydata(verts, [], faces)
    for m in tones:
        me.materials.append(m)
    for p, i in zip(me.polygons, mi):
        p.material_index = i
    coll.objects.link(bpy.data.objects.new("quay_far_face", me))
    near = [(*_box(-400, 400, RAIL_Y, QUAY_NEAR, WATER_Z - 0.8, 0.0), 0),
            (*_box(-400, 400, QUAY_NEAR - 0.01, QUAY_NEAR + 0.0, WATER_Z - 0.6, WATER_Z + 0.35), 3)]
    _mesh("quay_near", near, tones, coll)
    far = [(*_box(-400, 400, QUAY_FAR, FAR_TOP + 0.4, WATER_Z - 0.8, 0.0), 0)]
    # stone parapet of the opposite bank (0.6 m), open at the footbridge head
    cap = _mat("coping", "#CFCAC0", 0.9)
    for a, b in ((-400.0, BRIDGE_X - 1.6), (BRIDGE_X + 1.6, 400.0)):
        far.append((*_box(a, b, FAR_TOP, FAR_TOP + 0.35, 0.0, 0.55), 1))
        far.append((*_box(a, b, FAR_TOP - 0.04, FAR_TOP + 0.39, 0.55, 0.63), 2))
    _mesh("quay_far", far, [tones[0], tones[1], cap], coll)


def _waves_group():
    ng = bpy.data.node_groups.new("RiverWaves", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(pos.outputs[0], sep.inputs[0])
    tm = N.new("GeometryNodeInputSceneTime")
    ln = N.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    L.new(pos.outputs[0], ln.inputs[0])

    def m(op, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]
    total = None
    # ripple that runs with the current (+x) and a weak crossed one; fades with distance (no shimmer far away)
    for kx, ky, w, amp, fade in ((0.85, 0.32, 2.1, 0.035, 95.0), (-0.45, 1.35, 3.0, 0.018, 70.0), (2.0, 0.9, 4.4, 0.009, 40.0)):
        ph = m("ADD", m("ADD", m("MULTIPLY", sep.outputs["X"], kx), m("MULTIPLY", sep.outputs["Y"], ky)),
               m("MULTIPLY", tm.outputs["Seconds"], -w))
        fall = m("MAXIMUM", m("SUBTRACT", 1.0, m("DIVIDE", ln.outputs["Value"], fade)), 0.0)
        term = m("MULTIPLY", m("MULTIPLY", m("SINE", ph), amp), fall)
        total = term if total is None else m("ADD", total, term)
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(total, comb.inputs["Z"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs[0], sp.inputs["Geometry"])
    L.new(comb.outputs[0], sp.inputs["Offset"])
    L.new(sp.outputs[0], go.inputs[0])
    return ng


def _water_material():
    """River water: gray-green in bands along the current (noise stretched in x), lighter and with a sideways sky
    reflection (Layer Weight), darker next to the walls; low roughness (sky and bank reflection)."""
    mat = bpy.data.materials.new("river_water")
    mat.use_nodes = True
    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    p = kit.principled(mat)
    p.inputs["Roughness"].default_value = 0.16
    p.inputs["Specular IOR Level"].default_value = 0.35
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.06, 0.55, 1.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 2.0
    L.new(mp.outputs[0], nz.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.4, 0.62
    ramp.color_ramp.elements[0].color = kit.lin("#1F3F40")
    ramp.color_ramp.elements[1].color = kit.lin("#4A6E68")
    L.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.2
    sky = N.new("ShaderNodeMix")
    sky.data_type = "RGBA"
    L.new(lw.outputs["Facing"], sky.inputs[0])
    L.new(ramp.outputs["Color"], sky.inputs[6])
    sky.inputs[7].default_value = kit.lin("#7A9094")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])

    def m(op, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]
    edge = m("MINIMUM", m("SUBTRACT", sep.outputs["Y"], QUAY_NEAR), m("SUBTRACT", QUAY_FAR, sep.outputs["Y"]))
    shade = m("MULTIPLY", m("SUBTRACT", 1.0, m("MINIMUM", m("DIVIDE", edge, 2.2), 1.0)), 0.45)
    shade.node.use_clamp = True
    dark = N.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    L.new(shade, dark.inputs[0])
    L.new(sky.outputs[2], dark.inputs[6])
    dark.inputs[7].default_value = (0.35, 0.4, 0.4, 1.0)
    L.new(dark.outputs[2], p.inputs["Base Color"])
    return mat


def _water(coll):
    xs = []
    n = 220
    for i in range(n + 1):
        u = i / n * 2 - 1
        xs.append(400.0 * (0.85 * u ** 3 + 0.15 * u))
    ys = [QUAY_NEAR + (QUAY_FAR - QUAY_NEAR) * j / 44 for j in range(45)]
    verts = [(x, y, 0.0) for y in ys for x in xs]
    faces = []
    W = len(xs)
    for j in range(len(ys) - 1):
        for i in range(W - 1):
            p = j * W + i
            q = p + W
            faces += [(p, p + 1, q + 1), (p, q + 1, q)] if (i + j) % 2 else [(p, p + 1, q), (p + 1, q + 1, q)]
    o = _mesh("river", [(verts, faces, 0)], [_water_material()], coll, (0, 0, WATER_Z))
    mod = o.modifiers.new("Waves", "NODES")
    mod.node_group = _waves_group()
    o.visible_shadow = False
    return o


def _boats(coll, river, span):
    """Two boats moored next to the opposite bank's wall (the water disappears inside the hull: procedural._boat_mask) and
    rocking slowly: they give scale and say 'this is water'."""
    P = _P()
    boats = []
    for k, (x, y, hd) in enumerate(((-19.0, QUAY_FAR - 1.1, 0.05), (23.0, QUAY_FAR - 1.1, math.pi - 0.04))):
        res = P.spawn_boat(f"riv_boat{k}", coll, {"len": 4.2}, x, y, hd, span[0], span[1], 30, random.Random(k), ropes=False)
        res.obj.location.z = WATER_Z
        boats.append(res.obj)
        P.FLOATERS[-1].moored = True
    P._boat_mask(river.data.materials[0], boats)


# ---------- guardrail, furniture, kiosk ----------

def _railing(coll):
    steel = _mat("rail_steel", "#3A4744", 0.5, 0.35)
    parts = []
    for a, b in ((-120.0, GAP[0]), (GAP[1], 120.0)):
        x = a
        while x <= b + 1e-6:
            parts.append((*_box(x - 0.035, x + 0.035, RAIL_Y - 0.035, RAIL_Y + 0.035, 0.06, RAIL_H), 0))
            x += 1.6
        parts.append((*_box(a, b, RAIL_Y - 0.045, RAIL_Y + 0.045, RAIL_H - 0.06, RAIL_H + 0.01), 0))
        parts.append((*_box(a, b, RAIL_Y - 0.02, RAIL_Y + 0.02, 0.55, 0.59), 0))
        parts.append((*_box(a, b, RAIL_Y - 0.02, RAIL_Y + 0.02, 0.16, 0.2), 0))
        if a == -120.0 or b == 120.0:
            pass
    for x in GAP:                                    # small posts at the footbridge head
        parts.append((*_box(x - 0.08, x + 0.08, RAIL_Y - 0.08, RAIL_Y + 0.08, 0.06, RAIL_H + 0.05), 0))
    _mesh("railing", parts, [steel], coll)


def _kiosk(coll):
    """Drinks kiosk with a porch: light plaster ceiling (target of 'crack') over 2 small posts, striped awning
    on top, 1.05 m counter. Returns (ceiling, porch) — the porch (ceiling + awning) is what gives a few cm."""
    x0, x1, y0, y1 = KIOSK
    wall, base, trim, dark, wood = (_mat("kiosk_wall", "#E6D9BE", 0.85), _mat("kiosk_base", "#2F5A4C", 0.8),
                                    _mat("kiosk_trim", "#2F5A4C", 0.7), _mat("kiosk_inside", "#3A3330", 1.0),
                                    _mat("kiosk_wood", "#8E6440", 0.8))
    H = 2.75
    parts = [(*_box(x0, x1, y0 + 0.12, y1, 0.0, 0.3), 1),                      # green baseboard
             (*_box(x0, x1, y0 + 0.12, y1, 0.3, 1.0), 0),                      # counter wall
             (*_box(x0, x0 + 0.15, y0 + 0.12, y1, 1.0, H), 0), (*_box(x1 - 0.15, x1, y0 + 0.12, y1, 1.0, H), 0),
             (*_box(x0, x1, y1 - 0.15, y1, 1.0, H), 0), (*_box(x0, x1, y0 + 0.12, y0 + 0.3, 2.05, H), 0),
             (*_box(x0 + 0.15, x1 - 0.15, y0 + 0.35, y1 - 0.15, 0.3, 2.05), 3),  # dark interior behind the window
             (*_box(x0 - 0.05, x1 + 0.05, y0 - 0.25, y0 + 0.14, 1.0, 1.06), 4),  # wooden counter
             (*_box(x0 - 0.06, x1 + 0.06, y0 + 0.06, y1 + 0.06, H, H + 0.14), 2)]
    _mesh("kiosk", parts, [wall, base, trim, dark, wood], coll)
    # cups and bottles on the counter (Kenney Food Kit)
    for k, (ident, dx, h) in enumerate((("cup-coffee", 0.35, 0.1), ("cup-coffee", 0.55, 0.1), ("mug", 1.15, 0.1))):
        o = models.static_instance(ident, f"kiosk_cup{k}", coll, height=h)
        o.location = (x0 + dx, y0 - 0.05, 1.06)
    # porch: small posts + plaster ceiling (below) + striped awning (above), a single piece so it gives way together
    px0, px1, py0, py1, zc = PORCH
    posts = [(*_box(px0 + 0.02, px0 + 0.1, py0 + 0.02, py0 + 0.1, 0.0, zc), 0),
             (*_box(px1 - 0.1, px1 - 0.02, py0 + 0.02, py0 + 0.1, 0.0, zc), 0)]
    _mesh("porch_posts", posts, [trim], coll)
    plaster, cream, green = _mat("plaster", "#ECE7DD", 0.95, 0.05), _mat("awning_cream", "#EFE8D8", 0.9), _mat("awning_green", "#2F6B57", 0.9)
    nx, ny = 10, 12                                  # ceiling as a grid (the 'crack' sinks the middle by shape key)
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((px0 + (px1 - px0) * i / nx, py0 + (py1 - py0) * j / ny, zc))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + nx + 1, a + nx + 2, a + 1))      # normal facing down (whoever looks from below sees it)
    parts = [(verts, faces, 0)]
    parts.append((*_box(px0, px1, py0, py0 + 0.08, zc, zc + 0.22), 1))           # testeira
    parts.append((*_box(px0, px0 + 0.06, py0, py1, zc, zc + 0.22), 1))
    parts.append((*_box(px1 - 0.06, px1, py0, py1, zc, zc + 0.22), 1))
    n_st = 8                                          # tilted striped awning (slopes forward)
    for k in range(n_st):
        xa, xb = px0 - 0.1 + (px1 - px0 + 0.2) * k / n_st, px0 - 0.1 + (px1 - px0 + 0.2) * (k + 1) / n_st
        v = [(xa, py0 - 0.15, zc + 0.18), (xb, py0 - 0.15, zc + 0.18), (xb, py1, zc + 0.55), (xa, py1, zc + 0.55),
             (xa, py0 - 0.15, zc + 0.24), (xb, py0 - 0.15, zc + 0.24), (xb, py1, zc + 0.61), (xa, py1, zc + 0.61)]
        f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        parts.append((v, f, 2 if k % 2 else 3))
    porch = _mesh("porch", parts, [plaster, cream, green, cream], coll)
    # shape key 'Sag': the middle of the ceiling and awning goes down (1 = 1 m at the center), the edges fixed
    porch.shape_key_add(name="Basis")
    sk = porch.shape_key_add(name="Sag", from_mix=False)
    sk.slider_min, sk.slider_max = 0.0, 1.0
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
    for i, v in enumerate(porch.data.vertices):
        ux = 1 - min(1.0, abs(v.co.x - cx) / ((px1 - px0) / 2))
        uy = 1 - min(1.0, abs(v.co.y - cy) / ((py1 - py0) / 2))
        sk.data[i].co = v.co + Vector((0, 0, -math.sin(ux * math.pi / 2) * math.sin(uy * math.pi / 2)))
    return porch


def _table_and_benches(coll, rng):
    for k, (x, y) in enumerate(BENCHES):
        park.spawn_bench(f"riv_bench{k + 1}", coll, {}, x, y, math.pi / 2, 0, 0, 30, rng)
    for k, (x, y) in enumerate(((-8.0, 6.6), (-14.0, 6.6), (12.0, 6.6))):
        park._bin(coll, 30 + k, x, y)
    for k, (x, y) in enumerate(LAMPS_AT):
        park._lamp(coll, 40 + k, x, y)


def _trees(coll, rng):
    """Plane trees in pits on our sidewalk (10 to 14 m, one of 18 m) and on the opposite bank (9 to 12 m)."""
    ids = ["commontree-1", "commontree-2", "commontree-3", "commontree-4", "commontree-5"]
    pit, grate = _mat("tree_pit", "#4A3D30", 1.0, 0.0), _mat("tree_grate", "#2A2E33", 0.6, 0.3)
    parts = []
    for k, (x, y) in enumerate(TREES_NEAR):
        h = 18.0 if k == 0 else rng.uniform(11.0, 14.0)
        o = models.static_instance(rng.choice(ids), f"riv_tree{k}", coll, height=h)
        o.location = (x, y, -0.02)
        o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        parts.append((*_box(x - 0.7, x + 0.7, y - 0.7, y + 0.7, 0.0, 0.012), 0))
        for s in (-1, 1):
            parts.append((*_box(x - 0.75, x + 0.75, y + s * 0.7 - 0.04, y + s * 0.7 + 0.04, 0.0, 0.03), 1))
            parts.append((*_box(x + s * 0.7 - 0.04, x + s * 0.7 + 0.04, y - 0.75, y + 0.75, 0.0, 0.03), 1))
    _mesh("tree_pits", parts, [pit, grate], coll)
    k = 0
    x = -110.0
    while x < 110.0:
        if abs(x - BRIDGE_X) > 4.5 and math.hypot(x - SEQUOIA_AT[0], 53.0 - SEQUOIA_AT[1]) > 7:
            o = models.static_instance(rng.choice(ids), f"far_tree{k}", coll, height=rng.uniform(9.0, 12.0))
            o.location = (x + rng.uniform(-0.6, 0.6), 53.2 + rng.uniform(-0.3, 0.3), -0.02)
            o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            k += 1
        x += 8.5


def _far_benches(coll, rng):
    for k, x in enumerate((-44.0, -18.0, 15.0, 33.0, 52.0)):
        park.spawn_bench(f"far_bench{k}", coll, {}, x, 56.4, -math.pi / 2, 0, 0, 30, rng)


# ---------- passarela estaiada ----------

def _bridge(coll):
    """Deck (with edge beams and guardrails) and stays with shape key 'Sag' (1 = 1 m in the middle of the larger span);
    the stays also have 'Vib' (lateral displacement of the middle, 1 = 1 m) for the light vibration."""
    concrete, girder, steel = _mat("deck", "#BDB8AD", 0.9), _mat("girder", "#D8D5CE", 0.8), _mat("rail_steel", "#3A4744", 0.5, 0.35)
    white = _mat("pylon", "#E4E2DC", 0.75)
    y0, y1 = BRIDGE_Y
    segs = 80
    ys = [y0 + (y1 - y0) * k / segs for k in range(segs + 1)]
    x0, x1 = BRIDGE_X - BRIDGE_HW, BRIDGE_X + BRIDGE_HW
    verts, faces, mi = [], [], []

    def strip(xa, xb, za, zb, m):
        """Ribbon along y: rectangle (xa..xb, za..zb above the deck top) in each slice."""
        base = len(verts)
        for y in ys:
            z = deck_z(y)
            verts.extend([(xa, y, z + za), (xb, y, z + za), (xb, y, z + zb), (xa, y, z + zb)])
        for k in range(segs):
            a, b = base + 4 * k, base + 4 * (k + 1)
            for i in range(4):
                faces.append((a + i, a + (i + 1) % 4, b + (i + 1) % 4, b + i))
                mi.append(m)
    strip(x0, x1, -0.25, 0.0, 0)                                # laje
    strip(x0 - 0.12, x0 + 0.08, -0.75, 0.12, 1)                 # edge beams
    strip(x1 - 0.08, x1 + 0.12, -0.75, 0.12, 1)
    strip(x0 + 0.02, x0 + 0.09, RAIL_H - 0.07, RAIL_H, 2)       # handrails
    strip(x1 - 0.09, x1 - 0.02, RAIL_H - 0.07, RAIL_H, 2)
    strip(x0 + 0.03, x0 + 0.07, 0.5, 0.55, 2)
    strip(x1 - 0.07, x1 - 0.03, 0.5, 0.55, 2)
    deck_parts = [(verts, faces, mi)]
    y = y0 + 0.6
    while y < y1 - 0.3:                                         # guardrail uprights every 2 m
        z = deck_z(y)
        for xx in (x0 + 0.055, x1 - 0.055):
            deck_parts.append((*_box(xx - 0.04, xx + 0.04, y - 0.04, y + 0.04, z, z + RAIL_H), 2))
        y += 2.0
    deck = _mesh("bridge_deck", deck_parts, [concrete, girder, steel], coll)
    _sag_key(deck, lambda co: Vector((0, 0, -sag_profile(co.y))))
    # A-shaped pylon (feet in the river), crossbeam under the deck, foundation block
    apex = Vector((BRIDGE_X, PYLON_Y, PYLON_H))
    legs = []
    for s in (-1, 1):
        foot = Vector((BRIDGE_X + s * 2.5, PYLON_Y, WATER_Z - 0.4))
        legs.append((*_bar(foot, apex + Vector((s * 0.25, 0, 0)), 0.38, 4, r1=0.24), 0))
    legs.append((*_box(BRIDGE_X - 2.35, BRIDGE_X + 2.35, PYLON_Y - 0.35, PYLON_Y + 0.35, -1.15, -0.75), 0))
    legs.append((*_box(BRIDGE_X - 3.4, BRIDGE_X + 3.4, PYLON_Y - 0.9, PYLON_Y + 0.9, WATER_Z - 0.5, WATER_Z + 0.35), 1))
    legs.append((*_box(BRIDGE_X - 0.45, BRIDGE_X + 0.45, PYLON_Y - 0.3, PYLON_Y + 0.3, PYLON_H - 0.4, PYLON_H + 0.6), 0))
    _mesh("bridge_pylon", legs, [white, _mat("pier_concrete", "#8E8A80", 0.95)], coll)
    # stays: from the top of the pylon to the deck edges (fan), intermediate rings for the vibration
    anchors = []
    for d in (3.0, 6.0, 9.0, 12.0, 14.4):
        anchors.append(PYLON_Y - d)
    for d in (4.0, 8.0, 12.0, 16.0, 20.0, 24.4):
        anchors.append(PYLON_Y + d)
    cparts, meta = [], []
    for k, ya in enumerate(sorted(anchors)):
        rank = abs(ya - PYLON_Y) / 24.4
        top_z = PYLON_H - 0.6 - 2.6 * (1 - rank)
        for xx in (x0 + 0.02, x1 - 0.02):
            top = Vector((BRIDGE_X + (xx - BRIDGE_X) * 0.08, PYLON_Y + (0.12 if ya > PYLON_Y else -0.12), top_z))
            bot = Vector((xx, ya, deck_z(ya) + 0.1))
            pts = [top.lerp(bot, u / 8) for u in range(9)]
            v, f = _tube(pts, 0.04, 4)
            cparts.append((v, f, 0))
            meta.append((ya, len(v)))
    cables = _mesh("bridge_cables", cparts, [steel], coll)
    cables.visible_shadow = False
    # stay shape keys: 'Sag' (the bottom end goes down with the deck: stay follows straight) and 'Vib'
    me = cables.data
    cables.shape_key_add(name="Basis")
    sag = cables.shape_key_add(name="Sag", from_mix=False)
    vib = cables.shape_key_add(name="Vib", from_mix=False)
    for sk in (sag, vib):
        sk.slider_min, sk.slider_max = -1.0, 1.0
    idx = 0
    for (ya, nv) in meta:
        rings = nv // 4
        for r in range(rings):
            u = r / (rings - 1)
            for i in range(4):
                co = me.vertices[idx].co
                sag.data[idx].co = co + Vector((0, 0, -sag_profile(ya) * u))
                vib.data[idx].co = co + Vector((0.6 * math.sin(math.pi * u), 0, 0.8 * math.sin(math.pi * u)))
                idx += 1
    return deck, cables


def _sag_key(obj, fn):
    obj.shape_key_add(name="Basis")
    sk = obj.shape_key_add(name="Sag", from_mix=False)
    sk.slider_min, sk.slider_max = -1.0, 1.0
    for i, v in enumerate(obj.data.vertices):
        sk.data[i].co = v.co + fn(v.co)
    return sk


# ---------- obra e grua ----------

def _construction(coll, rng):
    """8-story building under construction (concrete slabs and pillars; bottom 3 floors closed with brick and window
    openings, the upper ones open), hoarding, dumpster and material piles."""
    conc, brick, hoard, dark = (_mat("site_concrete", "#A9A59C", 0.95), _mat("site_brick", "#9A5A43", 0.95),
                                _mat("site_hoarding", "#5F7C8E", 0.8), _mat("site_dark", "#3C3A37", 1.0))
    x0, x1, y0, y1 = -30.0, -19.0, 69.0, 80.0
    parts = []
    for fl in range(9):
        z = fl * 3.2
        parts.append((*_box(x0, x1, y0, y1, z - 0.3 if fl else -0.1, z), 0))
    for fl in range(8):
        z = fl * 3.2
        for cx in (x0 + 0.3, (x0 + x1) / 2, x1 - 0.3):
            for cy in (y0 + 0.3, (y0 + y1) / 2, y1 - 0.3):
                parts.append((*_box(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25, z, z + 2.9), 0))
        if fl < 3:                                          # brick with window openings on the front facade
            for k in range(4):
                xa = x0 + 0.55 + k * 2.6
                parts.append((*_box(xa, xa + 1.0, y0 + 0.05, y0 + 0.3, z, z + 2.9), 1))
                parts.append((*_box(xa + 1.0, xa + 2.1, y0 + 0.05, y0 + 0.3, z, z + 0.9), 1))
                parts.append((*_box(xa + 1.0, xa + 2.1, y0 + 0.05, y0 + 0.3, z + 2.3, z + 2.9), 1))
            parts.append((*_box(x0 + 0.05, x0 + 0.3, y0, y1, z, z + 2.9), 1))
            parts.append((*_box(x1 - 0.3, x1 - 0.05, y0, y1, z, z + 2.9), 1))
        else:                                                # temporary guardrail (dark strip)
            parts.append((*_box(x0, x1, y0 - 0.05, y0 + 0.05, z + 0.95, z + 1.1), 3))
    _mesh("site_building", parts, [conc, brick, hoard, dark], coll)
    hp = []
    for a, b in ((LOT[0], -22.5), (-19.5, LOT[1])):               # hoarding with a gate
        hp.append((*_box(a, b, ROW1_Y - 0.6, ROW1_Y - 0.5, -0.15, 2.3), 2))
    hp.append((*_box(-23.0, -19.0, 76.0, 80.0, 0.0, 0.7), 3))                 # dumpster and material
    hp.append((*_box(-14.5, -12.8, 68.0, 70.5, 0.0, 1.2), 1))
    _mesh("site_hoarding", hp, [conc, brick, hoard, dark], coll)


def _crane(coll):
    """Tower crane: 2 m lattice tower (0.22 m bars: nothing thinner than ~3 px at 70 m), cab, top
    tower, 36 m jib with ties, 12 m counter-jib with ballast; trolley, cable and hanging load.
    The jib has the shape key 'Bend' (1 = 1 m of deflection at the tip, parabola); the load is a separate object."""
    yel, gray, cab, conc = (_mat("crane_yellow", "#DDB13E", 0.6, 0.25), _mat("crane_gray", "#5A5E63", 0.6, 0.2),
                            _mat("crane_cab", "#E9E6DE", 0.6, 0.2), _mat("crane_ballast", "#8E8A80", 0.95))
    cx, cy = CRANE_AT
    H, w = CRANE_H, 1.0
    parts = []
    corners = [(-w, -w), (w, -w), (w, w), (-w, w)]
    for ax, ay in corners:
        parts.append((*_bar((ax, ay, 0.0), (ax, ay, H), 0.13, 4, rot=0.0), 0))
    z = 0.0
    while z < H - 0.1:
        z2 = min(H, z + 3.0)
        for k in range(4):
            (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
            parts.append((*_bar((ax, ay, z), (bx, by, z2), 0.08, 4), 0))
            parts.append((*_bar((ax, ay, z), (bx, by, z), 0.07, 4), 0))
        z = z2
    parts.append((*_box(-2.5, 2.5, -2.5, 2.5, -0.15, 0.6), 1))                  # concrete base
    mast = _mesh("crane_mast", parts, [yel, conc], coll, (cx, cy, 0.0))
    # rotating part (jib, counter-jib, top tower, cab) at the top of the tower, local +x = jib
    top = []
    top.append((*_box(-1.3, 1.3, -1.3, 1.3, 0.0, 0.7), 1))                      # slewing table
    top.append((*_box(-0.2, 1.6, 1.15, 3.2, 0.1, 2.5), 2))                       # cab beside it
    for ax, ay in corners:                                                      # top tower (pyramid)
        top.append((*_bar((ax * 0.9, ay * 0.9, 0.7), (0.0, 0.0, 7.5), 0.11, 4), 0))
    L, CL = JIB_LEN, CJIB_LEN
    jz, jh = 0.9, 1.7                                                           # jib: lower chord at jz
    xs = [1.0 + k * 3.0 for k in range(int((L - 1.0) / 3.0) + 1)] + [L]
    for a, b in zip(xs, xs[1:]):
        hh = jh * (1 - 0.5 * a / L)
        hb = jh * (1 - 0.5 * b / L)
        top.append((*_bar((a, -0.75, jz), (b, -0.75, jz), 0.1, 4), 0))
        top.append((*_bar((a, 0.75, jz), (b, 0.75, jz), 0.1, 4), 0))
        top.append((*_bar((a, 0.0, jz + hh), (b, 0.0, jz + hb), 0.1, 4), 0))
        top.append((*_bar((a, -0.75, jz), (b, 0.0, jz + hb), 0.07, 4), 0))
        top.append((*_bar((a, 0.75, jz), (b, 0.0, jz + hb), 0.07, 4), 0))
        top.append((*_bar((a, -0.75, jz), (a, 0.75, jz), 0.06, 4), 0))
    top.append((*_bar((0.0, 0.0, 7.5), (L * 0.55, 0.0, jz + jh * (1 - 0.275)), 0.06, 4), 0))   # tirantes
    top.append((*_bar((0.0, 0.0, 7.5), (L * 0.95, 0.0, jz + jh * 0.53), 0.05, 4), 0))
    top.append((*_box(-CL, -1.0, -0.8, 0.8, jz - 0.1, jz + 0.35), 0))          # counter-jib (beam)
    top.append((*_box(-CL, -CL + 3.2, -1.0, 1.0, jz - 1.9, jz - 0.1), 3))       # concrete ballast
    top.append((*_bar((0.0, 0.0, 7.5), (-CL + 0.5, 0.0, jz + 0.35), 0.06, 4), 0))
    head = _mesh("crane_top", top, [yel, gray, cab, conc], coll, (cx, cy, H))
    head.rotation_euler = (0, 0, JIB_DIR)
    bend = _sag_key(head, lambda co: Vector((0, 0, -(max(0.0, co.x - 1.0) / (L - 1.0)) ** 2)))
    bend.name = "Bend"
    # trolley + cable + hook block + load: child of the rotating part, pivot at the trolley (swings)
    load = []
    load.append((*_box(-0.6, 0.6, -0.5, 0.5, -0.4, 0.0), 1))
    load.append((*_bar((0, 0, -0.4), (0, 0, -HOOK_DROP), 0.06, 4), 1))
    load.append((*_box(-0.35, 0.35, -0.25, 0.25, -HOOK_DROP - 0.8, -HOOK_DROP), 0))
    for sx, sy in ((-0.9, -0.6), (0.9, -0.6), (0.9, 0.6), (-0.9, 0.6)):
        load.append((*_bar((0, 0, -HOOK_DROP - 0.8), (sx, sy, -HOOK_DROP - 2.6), 0.035, 4), 1))
    load.append((*_box(-1.1, 1.1, -0.75, 0.75, -HOOK_DROP - 3.9, -HOOK_DROP - 2.6), 4))     # block pallet
    hook = _mesh("crane_load", load, [yel, gray, cab, conc, _mat("crane_blocks", "#9C7A55", 0.9)], coll)
    hook.parent = head
    hook.location = (TROLLEY_S, 0.0, jz)
    hook.rotation_mode = "XYZ"
    for o in (mast, head, hook):
        o.visible_shadow = True
    return head, hook


# ---------- sequoia, serra, cidade ----------

def _sequoia(coll):
    """Slender sequoia of SEQUOIA_H m (reddish trunk, narrow conical crown in 9 faceted tiers).
    The foliage uses its own material with the top (20% from above) that dries by 'dry' (DryAmount value 0 -> 1)."""
    x, y = SEQUOIA_AT
    H = SEQUOIA_H
    bark = _mat("sequoia_bark", "#7A4A33", 0.95, 0.05)
    leaf = bpy.data.materials.new("sequoia_leaf")
    leaf.use_nodes = True
    nt = leaf.node_tree
    N, Ln = nt.nodes, nt.links
    p = kit.principled(leaf)
    p.inputs["Roughness"].default_value = 0.95
    p.inputs["Specular IOR Level"].default_value = 0.05
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Ln.new(tc.outputs["Object"], sep.inputs[0])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.35
    Ln.new(tc.outputs["Object"], nz.inputs["Vector"])
    edge = N.new("ShaderNodeMath")                      # z + noise (irregular edge between green and dry)
    edge.operation = "MULTIPLY_ADD"
    Ln.new(nz.outputs["Fac"], edge.inputs[0])
    edge.inputs[1].default_value = 4.0
    Ln.new(sep.outputs["Z"], edge.inputs[2])
    amount = N.new("ShaderNodeValue")
    amount.name = "DryAmount"
    amount.outputs[0].default_value = 0.0
    thr = N.new("ShaderNodeMapRange")                   # threshold drops from H+3 (nothing dry) to 0.8 H (20% from above)
    Ln.new(amount.outputs[0], thr.inputs["Value"])
    thr.inputs["To Min"].default_value, thr.inputs["To Max"].default_value = H + 3.0, 0.8 * H + 2.0
    step = N.new("ShaderNodeMath")
    step.operation = "GREATER_THAN"
    Ln.new(edge.outputs[0], step.inputs[0])
    Ln.new(thr.outputs["Result"], step.inputs[1])
    var = N.new("ShaderNodeMix")                        # green in 2 tones
    var.data_type = "RGBA"
    Ln.new(nz.outputs["Fac"], var.inputs[0])
    var.inputs[6].default_value = kit.lin("#34502F")
    var.inputs[7].default_value = kit.lin("#4A6A3C")
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    Ln.new(step.outputs[0], mix.inputs[0])
    Ln.new(var.outputs[2], mix.inputs[6])
    mix.inputs[7].default_value = kit.lin("#A9844A")
    Ln.new(mix.outputs[2], p.inputs["Base Color"])
    parts = [(*_cyl(8, 1.1, 0.25, 0.0, H * 0.97), 0), (*_cyl(8, 1.6, 1.1, 0.0, 1.2), 0)]
    rng = random.Random("sequoia")
    tiers = 9
    for k in range(tiers):
        z0 = 9.0 + (H - 9.0) * k / tiers
        z1 = z0 + (H - 9.0) / tiers * 1.55
        r0 = 4.2 * (1 - k / tiers) ** 0.8 + 0.8
        v, f = _cyl(9, r0, r0 * 0.35, z0, min(z1, H), 0.0, 0.0, rng.uniform(0, 1))
        v = [(a * rng.uniform(0.9, 1.1), b * rng.uniform(0.9, 1.1), c) for a, b, c in v]
        parts.append((v, f, 1))
    parts.append((*_cyl(7, 0.9, 0.0, H - 2.0, H + 1.5), 1))
    o = _mesh("sequoia", parts, [bark, leaf], coll, (x, y, -0.02))
    return o, leaf


def _ridge(coll, rng):
    """Low mountain range in the back (650 to 1,100 m): faceted grid with peaks (Gaussians) and ridges by noise; color by
    height (gray-green slope, light bluish top). The distance mist makes it bluish."""
    xs = [-2600 + 50 * i for i in range(105)]
    ys = [560 + 35 * j for j in range(17)]

    def h(x, y):
        z = 0.0
        for px, py, ph, pr in RIDGE_PEAKS:
            z = max(z, ph * math.exp(-((x - px) ** 2 + (y - py) ** 2 * 1.6) / (2 * pr * pr)))
        base = 120 * _smooth((y - 600) / 220) + 60 * math.sin(x * 0.004 + 1.1) * _smooth((y - 640) / 200)
        crest = 35 * abs(math.sin(x * 0.011 + y * 0.004)) + 18 * math.sin(x * 0.031 - y * 0.02)
        return max(-5.0, max(z, base) + crest * _smooth((y - 620) / 150)) - 8.0 * (1 - _smooth((y - 560) / 80))
    verts = [(x, y, h(x, y)) for y in ys for x in xs]
    W = len(xs)
    faces = []
    for j in range(len(ys) - 1):
        for i in range(W - 1):
            a = j * W + i
            faces.append((a, a + 1, a + W + 1, a + W))
    mat = kit.flat("ridge", "#6E7C80", rough=1.0)
    nt = mat.node_tree
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    nt.links.new(attr.outputs["Color"], kit.principled(mat).inputs["Base Color"])
    o = kit.mesh_object("ridge", verts, faces, [mat], face_mats=[0] * len(faces))
    cols = o.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    lo, mid, hi = kit.lin("#56665A"), kit.lin("#6C7A82"), kit.lin("#97A2AC")
    flat = []
    for (_x, _y, z) in verts:
        t = max(0.0, min(1.0, z / 420.0)) + rng.uniform(-0.05, 0.05)
        a, b, u = (lo, mid, t / 0.6) if t < 0.6 else (mid, hi, (t - 0.6) / 0.4)
        u = max(0.0, min(1.0, u))
        flat += [a[k] + (b[k] - a[k]) * u for k in range(3)] + [1.0]
    cols.data.foreach_set("color", flat)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    o.visible_shadow = False
    return o, h


def _city(coll, rng):
    """3 layers of Kenney City Kit Commercial buildings on the opposite bank (facade toward -y), nothing tall in the central
    wedge (the mountain range must show above: |x| < 0.32 y only buildings of 9 to 13 m), and a row behind the camera."""
    low_all = ["building-a", "building-b", "building-c", "building-d", "building-e", "building-f", "building-g",
               "building-h", "building-i", "building-k"]
    low_mid = ["building-a", "building-b", "building-c", "building-d", "building-e", "building-h"]
    tall = ["building-j", "building-m", "building-n", "building-skyscraper-a", "building-skyscraper-b",
            "building-skyscraper-c", "building-skyscraper-e"]
    F = park.FACTOR
    for (a, b) in ((-170.0, LOT[0] - 0.5), (LOT[1] + 0.5, 170.0)):
        pos, k = a, 0
        while pos < b:
            ids = low_mid if abs(pos) < 26 else low_all
            ident = rng.choice(ids)
            w, d = models.CATALOG[ident]["size"][0] * F, models.CATALOG[ident]["size"][1] * F
            if pos + w > b + 1.0:
                break
            park._place_building(coll, f"bld_r1_{int(a)}_{k}", ident, rng.choice(park.VARIANTS), pos + w / 2,
                                 ROW1_Y + d / 2, math.pi)
            pos += w + rng.uniform(0.4, 1.6)
            k += 1
    k = 0
    for j in range(18):                                   # towers outside the central wedge
        for _ in range(20):
            x, y = rng.uniform(-170, 170), rng.uniform(95, 165)
            if abs(x) > 0.33 * y:
                break
        park._place_building(coll, f"bld_t{k}", rng.choice(tall), rng.choice(park.VARIANTS), x, y, math.pi,
                             factor=F * rng.uniform(0.95, 1.2), shadow=False)
        k += 1
    lows = [i for i in models.CATALOG if i.startswith("low-detail-building")]
    for k in range(80):
        a = math.radians(rng.uniform(30, 150))
        r = rng.uniform(170, 330)
        x, y = r * math.cos(a), r * math.sin(a) + 20
        f = rng.uniform(16, 24)
        o = park._place_building(coll, f"bld_far{k}", rng.choice(lows), rng.choice(park.VARIANTS[:2]), x, y,
                                 rng.choice((0, math.pi / 2, math.pi, -math.pi / 2)), factor=f, shadow=False)
        o.scale.z = f * (rng.uniform(0.7, 1.1) if abs(x) < 0.32 * y else rng.uniform(0.9, 1.8))
    pos = -120.0                                          # behind the camera
    while pos < 120.0:
        ident = rng.choice(low_all)
        w = models.CATALOG[ident]["size"][0] * F
        d = models.CATALOG[ident]["size"][1] * F
        park._place_building(coll, f"bld_back{int(pos)}", ident, rng.choice(park.VARIANTS), pos + w / 2,
                             -19.5 - d / 2, 0.0, shadow=False)
        pos += w + rng.uniform(0.5, 1.5)


# ---------- people in the background ----------

def _background_people(coll):
    """Couple on the opposite bank's promenade and a runner (animated in finish(), when the frame of the 'sink' is known)."""
    out = []
    for name, ident, y, x0, d, v, gait in (("bg_couple_a", "man", 50.7, -7.0, 1, 0.85, "Walk"),
                                            ("bg_couple_b", "womancasual", 51.4, -6.4, 1, 0.85, "Walk"),
                                            ("bg_runner", "animatedhuman", 55.1, 34.0, -1, 2.6, "Run")):
        rig = models.rig_spawn(ident, name, coll, height=1.72 if ident == "man" else 1.66)
        for o in rigs.all_objects(rig):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
        rig.root.location = (x0, y, 0.0)
        rig.root.rotation_euler = (0, 0, (0.0 if d > 0 else math.pi) + math.pi / 2)
        out.append(SimpleNamespace(rig=rig, y=y, x0=x0, d=d, v=v, gait=gait))
    _reg["walkers"] = out


def planted_per_frame(rig, key):
    """m per frame of the planted-foot action; without a foot bone in the skeleton, stride of 1.5 m (run 2.6 m) per cycle."""
    feet = models.feet_of(rig)
    if feet:
        return rigs.planted_speed(rig, key, feet) * rig.scale
    a0, a1 = rig.t.actions[key].frame_range
    return (2.6 if 'run' in key.lower() else 1.5) / max(a1 - a0, 1)


def _animate_background(fps, last):
    """They always walk; at the 'sink' the couple brakes, stops for ~2 s and continues at 65% (doubled weight); the runner starts walking."""
    ev = EVENTS[0] if EVENTS else None
    for w in _reg["walkers"]:
        rig = w.rig
        feet = models.feet_of(rig)
        frames = list(range(1, last + 1))

        def speed(f):
            t = f / fps
            if ev is None or f < ev:
                return w.v
            te = (f - ev) / fps
            if w.gait == "Run":
                return w.v + (1.05 - w.v) * _smooth(te / 1.2)
            if te < 0.6:
                return w.v * (1 - _smooth(te / 0.6))
            if te < 2.6:
                return 0.0
            return 0.65 * w.v * _smooth((te - 2.6) / 0.9)
        dist, d = [], 0.0
        for f in frames:
            d += speed(f) / fps
            dist.append(d)
        rigs.loop(rig, models.pick_action(rig, "Idle"), 1, last)
        pts = [(w.x0 + w.d * s, w.y, 0.0) for s in dist]
        heads = [0.0 if w.d > 0 else math.pi] * len(pts)
        rigs.key_root(rig, frames[::2], pts[::2], heads[::2])
        gaits = [w.gait] if (w.gait == "Walk" or ev is None) else ["Run", "Walk"]
        for g in gaits:
            key = models.pick_action(rig, g)
            per = planted_per_frame(rig, key)
            a0 = rig.t.actions[key].frame_range[0]
            times = [a0 + s / max(per, 1e-4) for s in dist]
            if g == "Run" and ev is not None:
                infl = [1.0 - _smooth((f - ev) / (1.0 * fps)) for f in frames]
            elif w.gait == "Run":
                infl = [_smooth((f - ev) / (1.0 * fps)) for f in frames]
            else:
                infl = [min(1.0, speed(f) / max(0.25 * w.v, 1e-3)) for f in frames]
            rigs.timed(rig, key, frames, times, infl)


# ---------- stage assembly ----------

def build_riverside(coll, sdef, rng, keepout=(), span=(1, 1)):
    """The whole stage. Returns {name: SimpleNamespace(obj, height, at)} of the targets the cues may cite."""
    TARGETS.clear()
    _ground(coll, rng)
    _quay_walls(coll, rng)
    river = _water(coll)
    _boats(coll, river, span)
    _railing(coll)
    porch = _kiosk(coll)
    _table_and_benches(coll, rng)
    _trees(coll, rng)
    _far_benches(coll, rng)
    deck, cables = _bridge(coll)
    _construction(coll, rng)
    head, hook = _crane(coll)
    seq, leaf = _sequoia(coll)
    ridge, ridge_h = _ridge(coll, rng)
    _city(coll, rng)
    _background_people(coll)
    scene = bpy.context.scene
    if hasattr(scene.eevee, "use_raytracing"):          # reflection of the bank and the sky in the river (screen-space raytracing)
        scene.eevee.use_raytracing = True
        opts = scene.eevee.ray_tracing_options
        opts.resolution_scale = "2"
        opts.use_denoise = True
    TARGETS["bridge"] = SimpleNamespace(obj=deck, height=PYLON_H, at=(BRIDGE_X, 32.0, 0.0), deck=deck, cables=cables)
    TARGETS["crane"] = SimpleNamespace(obj=head, height=CRANE_H, at=(CRANE_AT[0], CRANE_AT[1], 0.0), head=head, hook=hook)
    TARGETS["kiosk"] = SimpleNamespace(obj=porch, height=2.6, at=((KIOSK[0] + KIOSK[1]) / 2, 7.5, 0.0), porch=porch, coll=coll)
    TARGETS["tree_tall"] = SimpleNamespace(obj=seq, height=SEQUOIA_H, at=(*SEQUOIA_AT, 0.0), leaf=leaf)
    TARGETS["ridge"] = SimpleNamespace(obj=ridge, height=420.0, at=(0.0, 820.0, 0.0), h=ridge_h, coll=coll)
    TARGETS["river"] = SimpleNamespace(obj=river, height=0.1, at=(0.0, 30.0, WATER_Z))
    return TARGETS


# ---------- script pieces ----------

def spawn_scale(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Analog bathroom scale (0.34 x 0.30 m, 5 cm): rubber top, round display with a red needle.
    The needle is a separate object (turns by 'needle'): 0 until someone steps on; near '70' trembling; doubles at the 'buckle'."""
    body, top, glass, red = (_mat("scale_body", "#E8E6E1", 0.5, 0.3), _mat("scale_top", "#3B3E42", 0.9),
                             _mat("scale_glass", "#F4F1EA", 0.3, 0.4), _mat("scale_needle", "#C8322A", 0.6))
    parts = [(*_box(-0.17, 0.17, -0.15, 0.15, 0.0, 0.045), 0), (*_box(-0.15, 0.15, -0.13, 0.09, 0.045, 0.052), 1),
             (*_cyl(16, 0.045, 0.045, 0.045, 0.053, 0.0, -0.105), 2)]
    o = _mesh(name, parts, [body, top, glass], coll)
    o.location = (x, y, 0.0)
    o.rotation_euler = (0, 0, heading - math.pi / 2)
    needle = _mesh(f"{name}_needle", [(*_box(-0.003, 0.003, 0.0, 0.038, 0.0, 0.003), 0)], [red], coll)
    needle.parent = o
    needle.location = (0.0, -0.105, 0.054)
    needle.rotation_mode = "XYZ"
    PLATFORMS.append((x, y, 0.16, 0.05))
    _reg.setdefault("scales", []).append(SimpleNamespace(obj=o, needle=needle, at=(x, y)))
    return SimpleNamespace(obj=o, height=0.05, positions=None)


def carry(obj_prop, holder, frame):
    """Static piece in the right hand of whoever is seated (cup in the lap): child of the Palm.R bone, upright."""
    rig = holder.rig
    scene = bpy.context.scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pb = rig.arm.pose.bones["Palm.R"]
    bone_m = rig.arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    hand = rig.arm.matrix_world @ pb.tail
    fwd = Vector((math.cos(rig.root.rotation_euler.z - math.pi / 2), math.sin(rig.root.rotation_euler.z - math.pi / 2), 0))
    k = obj_prop.obj.scale[0]
    world = Matrix.Translation(hand + fwd * 0.02 + Vector((0, 0, 0.005))) @ Matrix.Diagonal((k, k, k, 1.0))
    o = obj_prop.obj
    o.parent, o.parent_type, o.parent_bone = rig.arm, "BONE", "Palm.R"
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = bone_m.inverted() @ world
    obj_prop.carrier = holder
    obj_prop.positions = [(frame, hand.copy())]


# ---------- gatilhos ----------

CUES = ("fall", "crack", "sag", "bend", "dry", "slump")
GESTURES = ("buckle", "release")


def cue(do, prop, c, f, start, end, fps, coll):
    """Cues of the riverside stage (and 'fall', which works for any static piece)."""
    t = TARGETS.get(prop.name)
    if do == "fall":
        _reg["fall"].append((prop, f, float(c.get("g", 19.6)), coll))
        return
    if t is None:
        kit.problem(f"cue '{do}' on '{prop.name}': only the riverside stage targets ({', '.join(sorted(TARGETS))})")
        return
    if do == "sag" and prop.name == "bridge":
        _reg["sag"].append((f, float(c.get("dy", 0.12)), max(1, int(float(c.get("dur", 3.0)) * fps))))
    elif do == "bend" and prop.name == "crane":
        _reg["bend"].append((f, float(c.get("deg", 2.5)), max(1, int(float(c.get("dur", 3.0)) * fps))))
    elif do == "dry" and prop.name == "tree_tall":
        nt = t.leaf.node_tree
        dur = max(1, int(float(c.get("dur", 6.0)) * fps))
        fr = list(range(start, f + dur + 1, 2)) + [f + dur]
        ac.write(nt, 'nodes["DryAmount"].outputs[0].default_value', 0, fr,
                 [_smooth((x - f) / dur) ** 0.8 if x > f else 0.0 for x in fr])
    elif do == "crack" and prop.name == "kiosk":
        _crack_kiosk(t, f, max(1, int(float(c.get("dur", 3.0)) * fps)), fps)
    elif do == "slump" and prop.name == "ridge":
        _reg["slump"].append((t, f, fps))
    else:
        kit.problem(f"cue '{do}' does not work for '{prop.name}'")


# --- rachaduras ---

def _crack_paths(rng, length, angle, width, depth=0):
    """Winding polyline (steps of length/14), tapers at the tip and drops 2 branches. [(p0, p1, w0, w1, g0, g1)]."""
    segs = []
    n = 14
    p = Vector((0.0, 0.0))
    a = angle
    for k in range(n):
        a += rng.uniform(-0.45, 0.45)
        q = p + Vector((math.cos(a), math.sin(a))) * (length / n)
        w0, w1 = width * (1 - 0.65 * k / n), width * (1 - 0.65 * (k + 1) / n)
        segs.append((p.copy(), q.copy(), w0, w1, k / n, (k + 1) / n))
        if depth == 0 and k in (4, 9):
            for s in _crack_paths(rng, length * 0.45, a + rng.choice((-1, 1)) * rng.uniform(0.6, 1.1), width * 0.55, 1):
                g0 = k / n + s[4] * 0.45
                segs.append((s[0] + q, s[1] + q, s[2], s[3], g0, k / n + s[5] * 0.45))
        p = q
    return segs


def _crack_material(name, hexa, fr, vals):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "DITHERED"
    nt = mat.node_tree
    p = kit.principled(mat)
    p.inputs["Base Color"].default_value = kit.lin(hexa)
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "grow"
    thr = nt.nodes.new("ShaderNodeValue")
    thr.name = "Grow"
    lt = nt.nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(attr.outputs["Fac"], lt.inputs[0])
    nt.links.new(thr.outputs[0], lt.inputs[1])
    nt.links.new(lt.outputs[0], p.inputs["Alpha"])
    thr.outputs[0].default_value = 0.0
    ac.write(nt, 'nodes["Grow"].outputs[0].default_value', 0, fr, vals)
    return mat


def _crack_mesh(name, coll, segs, to_world, mat):
    verts, faces, grow = [], [], []
    for p0, p1, w0, w1, g0, g1 in segs:
        d = (p1 - p0).normalized()
        nrm = Vector((-d.y, d.x))
        base = len(verts)
        for c, w in ((p0, w0), (p1, w1)):
            for s in (-0.5, 0.5):
                verts.append(tuple(to_world(c + nrm * (w * s))))
        faces.append((base, base + 1, base + 3, base + 2))
        grow += [g0, g0, g1, g1]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("grow", "FLOAT", "POINT")
    at.data.foreach_set("value", grow)
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.visible_shadow = False
    return o


def _crack_kiosk(t, f, dur, fps):
    """Cracks in the plaster ceiling of the porch (seen from below) and in the counter wall; they grow in 'dur' (fast at the
    start, then slowly), the porch gives 4 cm and 6 plaster chips fall (doubled g)."""
    rng = random.Random("crack_kiosk")
    fr = list(range(f - 1, f + dur + 2))
    vals = [0.0 if x < f else 1.02 * (1 - (1 - min(1.0, (x - f) / dur)) ** 2.2) for x in fr]
    mat = _crack_material("crack_plaster", "#3A342E", fr, vals)
    px0, px1, py0, py1, zc = PORCH
    porch = t.porch
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
    for k, (ox, oy, ang, ln) in enumerate(((cx + 0.1, cy - 0.1, 2.6, 1.5), (cx - 0.05, cy + 0.05, -0.6, 1.3),
                                           (cx + 0.15, cy, 1.2, 0.9))):
        segs = _crack_paths(rng, ln, ang, 0.026)
        # on the ceiling, attached to the porch (gives along with it): local coordinates of the porch, 3 mm below the plaster
        o = _crack_mesh(f"crack_ceiling{k}", t.coll, segs, lambda q, ox=ox, oy=oy: Vector((ox + q.x, oy + q.y, zc - 0.003)), mat)
        o.parent = porch
        _crack_follow(o, porch, (px0, px1, py0, py1))
    x0, x1, y0, _y1 = KIOSK
    segs = _crack_paths(rng, 0.8, -1.2, 0.014)
    _crack_mesh("crack_counter", t.coll, segs, lambda q: Vector((x0 + 0.7 + q.x, y0 + 0.11, 0.95 + q.y)), mat)
    # the porch gives (shape key 'Sag': 1 = 1 m at the center) 4 cm along with the cracks
    sk = porch.data.shape_keys
    ac.write(sk, 'key_blocks["Sag"].value', 0, fr, [0.04 * v / 1.02 for v in vals])
    # plaster chips falling from the middle of the ceiling
    plaster = _mat("plaster", "#ECE7DD", 0.95, 0.05)
    for k in range(6):
        v = [(rng.uniform(-1, 1) * 0.02, rng.uniform(-1, 1) * 0.02, rng.uniform(-1, 1) * 0.004) for _ in range(6)]
        fl = bmesh.new()
        for p in v:
            fl.verts.new(p)
        bmesh.ops.convex_hull(fl, input=fl.verts)
        me = bpy.data.meshes.new(f"flake{k}")
        fl.to_mesh(me)
        fl.free()
        me.materials.append(plaster)
        o = bpy.data.objects.new(f"plaster_flake{k}", me)
        t.coll.objects.link(o)
        o.visible_shadow = False
        x, y = cx + rng.uniform(-0.5, 0.5), cy + rng.uniform(-0.6, 0.6)
        f0 = f + int(rng.uniform(0.6, 2.6) * fps)
        T = math.sqrt(2 * (zc - 0.05) / 19.6)
        frames = list(range(f0, f0 + int(T * fps) + 2))
        locs, rots = [], []
        for x_ in frames:
            tt = min(T, (x_ - f0) / fps)
            locs.append((x + 0.15 * tt, y, zc - 0.04 - 0.5 * 19.6 * tt * tt))
            rots.append(tt * 9.0)
        ac.write_vec(o, "location", [f0 - 1] + frames, [locs[0]] + locs)
        ac.write(o, "rotation_euler", 0, [f0 - 1] + frames, [0.0] + rots)
        ac.write_vec(o, "scale", [1, f0 - 1, f0], [(0, 0, 0), (0, 0, 0), (1, 1, 1)])
        o.location, o.scale = locs[0], (0, 0, 0)


def _crack_follow(o, porch, rect):
    """The ceiling crack goes down with the porch's 'Sag' (simple driver: local z = -value x shape at the center)."""
    px0, px1, py0, py1 = rect
    o.location = (0, 0, 0)
    d = o.driver_add("location", 2).driver
    d.type = "SCRIPTED"
    var = d.variables.new()
    var.name = "s"
    var.targets[0].id_type = "KEY"
    var.targets[0].id = porch.data.shape_keys
    var.targets[0].data_path = 'key_blocks["Sag"].value'
    d.expression = "-0.85*s"


# --- witness gestures ---

def gesture(prop, name, f, fps, c):
    if prop.rig is None:
        kit.problem(f"gesture '{name}' on '{prop.name}', which has no skeleton")
        return
    _reg["buckle"].setdefault(prop.name, (prop, []))[1].append((f, name))


DROP = 0.2                       # how much the hip drops in the 'buckle' (m)
LEG_SIGN = 1.0                   # direction of the thigh turn (measured on a still: knee goes forward)


def _write_buckle(prop, evs, fps, last):
    """'buckle': the knees give way (the Body bone drops 27 cm with the feet held by the asset's IK), the torso leans,
    the shoulders rise and the hand on the guardrail side grabs the rail (IK); holds crouched, breathing deeply.
    'release': pushes and returns standing in 1.1 s. Written as an added layer (COMBINE) over the underlying action."""
    rig = prop.rig
    evs.sort()
    frames = list(range(1, last + 1))
    w = {}
    cur, seg = 0.0, None
    pending = list(evs)
    for fr in frames:
        while pending and pending[0][0] <= fr:
            seg = (pending.pop(0), cur)
        if seg is not None:
            (f0, kind), frm = seg
            u = (fr - f0) / fps
            if kind == "buckle":
                # gives fast (0.5 s to 75%), sinks slowly to 100% in 2.5 s, with a jolt in the middle
                a = 0.75 * (1 - (1 - min(1.0, u / 0.5)) ** 2) + 0.25 * _smooth((u - 0.5) / 2.0)
                a += 0.05 * math.sin(min(u, 1.0) * math.pi) * (u > 0.35)
                cur = frm + (1.0 - frm) * min(1.0, a)
            else:
                cur = frm * (1 - _smooth(u / 1.1))
        w[fr] = cur
    scene = bpy.context.scene
    # forward: Body offset in bone space to go down 0.27 m in the world
    scene.frame_set(evs[0][0])
    pb = rig.arm.pose.bones["Body"]
    rest = rig.arm.matrix_world @ pb.bone.matrix_local
    down = rest.to_3x3().inverted() @ Vector((0, 0, -DROP))
    M = rig.arm.matrix_world
    hip = M @ rig.arm.pose.bones["UpperLeg.L"].head
    knee = M @ rig.arm.pose.bones["LowerLeg.L"].head
    L1 = (hip - knee).length
    L2 = max(0.2, knee.z - surface_height(knee.x, knee.y) - 0.075)      # shin to the ankle (the asset has no foot bone)

    def legs(d):
        """Angles (degrees) of the thigh forward and the shin backward that lower the hip 'd' with the foot under it."""
        lo, hi = 0.0, 1.4
        for _ in range(40):
            a = (lo + hi) / 2
            b = math.asin(min(1.0, L1 * math.sin(a) / L2))
            if L1 * math.cos(a) + L2 * math.cos(b) > L1 + L2 - d:
                lo = a
            else:
                hi = a
        return math.degrees(a), math.degrees(b)
    act = bpy.data.actions.new(f"{rig.name}Buckle")
    slot = act.slots.new(id_type="OBJECT", name=rig.arm.name)
    from bpy_extras import anim_utils as au
    bag = au.action_ensure_channelbag_for_slot(act, slot)
    dl = [down * w[fr] for fr in frames]
    for i in range(3):
        fc = bag.fcurves.new('pose.bones["Body"].location', index=i, group_name="Body")
        fc.keyframe_points.add(len(frames))
        fc.keyframe_points.foreach_set("co", [c for fr, v in zip(frames, dl) for c in (fr, v[i])])
        fc.keyframe_points.foreach_set("interpolation", [1] * len(frames))
        fc.update()
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    tr = ad.nla_tracks.new()
    tr.name = "Buckle"
    st = tr.strips.new("Buckle", 1, act)
    st.action_slot = slot
    st.use_auto_blend = False
    st.blend_type = "COMBINE"
    st.extrapolation = "HOLD"
    from procedural import _bend

    def pose(fr):
        t = fr / fps
        b = w[fr]
        breath = b * 1.8 * math.sin(math.tau * t / 1.6)
        a, c = legs(DROP * b) if b > 1e-3 else (0.0, 0.0)
        return _bend(rig, {"UpperLeg.L": [((1, 0, 0), -a * LEG_SIGN)], "UpperLeg.R": [((1, 0, 0), -a * LEG_SIGN)],
                           "LowerLeg.L": [((1, 0, 0), (a + c) * LEG_SIGN)], "LowerLeg.R": [((1, 0, 0), (a + c) * LEG_SIGN)],
                           "Abdomen": [((1, 0, 0), 10 * b)], "Torso": [((1, 0, 0), 12 * b + breath)],
                           "Neck": [((1, 0, 0), -9 * b)], "Head": [((1, 0, 0), -7 * b - 0.4 * breath)],
                           "Shoulder.L": [((0, 1, 0), -7 * b)], "Shoulder.R": [((0, 1, 0), 7 * b)]})
    rigs.pose_layer(rig, frames, pose)
    # hand on the rail (IK), the one nearest the guardrail, at each 'buckle'
    for (f0, kind) in evs:
        if kind != "buckle":
            continue
        scene.frame_set(f0)
        bpy.context.view_layer.update()
        root = rig.root.matrix_world
        best = None
        for side in ("L", "R"):
            sh = rig.arm.matrix_world @ rig.arm.pose.bones[f"UpperArm.{side}"].head
            x = sh.x
            if GAP[0] - 0.05 < x < GAP[1] + 0.05:
                x = GAP[0] - 0.08 if x < sum(GAP) / 2 else GAP[1] + 0.08
            tgt = Vector((x, RAIL_Y - 0.07, RAIL_H - 0.03))       # hand over and in front of the rail
            d = (tgt - (sh + Vector((0, 0, -0.27)))).length
            if best is None or d < best[0]:
                best = (d, side, tgt, sh)
        d, side, tgt, sh = best
        if d > 1.05:
            print(f"  buckle: {prop.name} far from the guardrail ({d:.2f} m): no hand on the rail")
            continue
        P = _P()
        coll = rig.root.users_collection[0]
        target = P._empty(f"{prop.name}Rail{f0}", coll, tgt, None, 0.05)
        pole = P._empty(f"{prop.name}RailPole{f0}", coll, sh + (root.to_3x3() @ Vector((0.4 if side == "L" else -0.4, 0.2, -0.5))), None, 0.05)
        ik = P._ik(rig, side, target, pole)
        nxt = next((e for e in evs if e[0] > f0 and e[1] == "release"), None)
        f_end = nxt[0] if nxt else last
        fr_k = [1, f0 + int(0.25 * fps), f0 + int(0.7 * fps), f_end + int(0.2 * fps), f_end + int(0.8 * fps)]
        path = f'pose.bones["Palm.{side}"].constraints["{ik.name}"].influence'
        ac.write(rig.arm, path, 0, fr_k, [0.0, 0.0, 1.0, 1.0, 0.0])
        print(f"  buckle: {prop.name} grabs the rail with the {side} hand at {d:.2f} m from the shoulder (f{f0})")


def _write_scale(fps, last):
    """Scale needle: 0 until someone steps on; ~'70' (126 degrees) trembling; at the 'buckle' goes to '140' (doubles)."""
    for sc in _reg.get("scales", []):
        people = [p for p, _ in _reg["buckle"].values()]
        frames = list(range(1, last + 1, 1))
        on, ev = None, None
        for p in people:
            for fr in range(1, last + 1, 3):
                q = p.pos(fr)
                if math.hypot(q.x - sc.at[0], q.y - sc.at[1]) < 0.12:
                    on = fr
                    break
        if EVENTS:
            ev = EVENTS[0]
        vals = []
        for fr in frames:
            t = fr / fps
            if on is None or fr < on:
                a = 0.0
            else:
                a = 126.0 * _out_back((fr - on) / (0.6 * fps), 1.2) + 2.5 * math.sin(t * 9.3) + 1.2 * math.sin(t * 23.0)
                if ev and fr >= ev:
                    a += 126.0 * _out_back((fr - ev) / (0.8 * fps), 0.8)
            vals.append(-math.radians(a))
        ac.write(sc.needle, "rotation_euler", 2, frames, vals)


# --- passarela, grua, queda, serra ---

def _write_sag(fps, last):
    if not _reg["sag"]:
        return
    t = TARGETS["bridge"]
    evs = sorted(_reg["sag"])
    frames = list(range(1, last + 1))
    total, vals, vib = 0.0, [], []
    starts = []
    acc = 0.0
    for f0, dy, dur in evs:
        starts.append((f0, acc, acc + dy, dur))
        acc += dy
    for fr in frames:
        v = 0.0
        for f0, a, b, dur in starts:
            if fr >= f0:
                u = (fr - f0) / dur
                v = a + (b - a) * (_out_back(u, 0.9) if u < 1 else 1.0)
        vals.append(v)
        amp = 0.0
        for f0, a, b, dur in starts:
            if fr >= f0:
                te = (fr - f0) / fps
                amp = max(amp, 0.018 * math.exp(-te / 2.5) + 0.006)
        vib.append(amp * math.sin(math.tau * 3.1 * fr / fps) / 0.8)
    for o in (t.deck, t.cables):
        ac.write(o.data.shape_keys, 'key_blocks["Sag"].value', 0, frames, vals)
    ac.write(t.cables.data.shape_keys, 'key_blocks["Vib"].value', 0, frames, vib)
    print(f"  sag: footbridge drops {acc * 100:.0f} cm in the middle of the larger span")


def _write_bend(fps, last):
    t = TARGETS.get("crane")
    if t is None:
        return
    evs = sorted(_reg["bend"])
    frames = list(range(1, last + 1))
    L = JIB_LEN - 1.0
    bend, sw_x, sw_y, hz = [], [], [], []
    for fr in frames:
        d = 0.0
        tt = fr / fps
        swing = 0.25 * math.sin(math.tau * tt / 9.4)                 # light wind before (normal g)
        swing2 = 0.18 * math.sin(math.tau * tt / 7.3 + 1.0)
        for f0, deg, dur in evs:
            if fr >= f0:
                u = (fr - f0) / dur
                tip = L * math.tan(math.radians(deg))                 # tip deflection: the root-tip chord turns 'deg' degrees
                d = tip * (_out_back(u, 0.7) if u < 1 else 1.0)
                te = (fr - f0) / fps
                swing += 1.3 * math.sin(math.tau * te / 6.65) * math.exp(-te / 14.0) * _smooth(te / 0.8)
        bend.append(d)
        sw_x.append(math.radians(swing))
        sw_y.append(math.radians(swing2))
        hz.append(0.9 - d * ((TROLLEY_S - 1.0) / L) ** 2)
    ac.write(t.head.data.shape_keys, 'key_blocks["Bend"].value', 0, frames, bend)
    ac.write(t.hook, "rotation_euler", 1, frames, sw_x)
    ac.write(t.hook, "rotation_euler", 0, frames, sw_y)
    ac.write(t.hook, "location", 2, frames, hz)
    if evs:
        print(f"  bend: jib tip drops {max(bend):.2f} m")


def _write_falls(fps):
    """Fall with a given g (19.6): the piece slips from the hand (0.15 s), falls freely, vanishes on the ground and becomes 4 shards that
    bounce low and a spreading coffee puddle."""
    scene = bpy.context.scene
    for prop, f, g, coll in _reg["fall"]:
        o = prop.obj
        scene.frame_set(f)
        bpy.context.view_layer.update()
        W = o.matrix_world.copy()
        p0 = W.translation.copy()
        k = o.matrix_world.to_scale()[0]
        tgt_coll = o.users_collection[0]
        falling = bpy.data.objects.new(f"{o.name}_falling", o.data)
        tgt_coll.objects.link(falling)
        falling.rotation_mode = "XYZ"
        rng = random.Random(f"fall{prop.name}")
        carrier = getattr(prop, "carrier", None)
        fwd = Vector((0, 1, 0))
        if carrier is not None:
            h = carrier.rig.root.rotation_euler.z - math.pi / 2
            fwd = Vector((math.cos(h), math.sin(h), 0))
        slip = int(0.15 * fps)
        T = math.sqrt(2 * max(p0.z - 0.01, 0.05) / g)
        fi = f + slip + int(round(T * fps))
        frames = list(range(f, fi + 1))
        locs, rx = [], []
        for fr in frames:
            if fr < f + slip:
                u = (fr - f) / slip
                locs.append(p0 + fwd * (0.03 * u) + Vector((0, 0, -0.02 * u * u)))
                rx.append(math.radians(25 * u * u))
            else:
                tt = (fr - f - slip) / fps
                q = p0 + fwd * (0.03 + 0.35 * tt) + Vector((0, 0, -0.02 - 0.5 * g * tt * tt))
                q.z = max(0.0, q.z)
                locs.append(q)
                rx.append(math.radians(25 + 260 * tt))
        hd = math.atan2(fwd.y, fwd.x)
        ac.write_vec(falling, "location", [f - 1] + frames, [locs[0]] + locs)
        ac.write(falling, "rotation_euler", 0, [f - 1] + frames, [0.0] + rx)
        ac.write(falling, "rotation_euler", 2, [f - 1, f], [hd - math.pi / 2] * 2)
        ac.write_vec(falling, "scale", [1, f - 1, f, fi, fi + 1], [(0, 0, 0), (0, 0, 0), (k, k, k), (k, k, k), (0, 0, 0)])
        falling.location, falling.scale = locs[0], (0, 0, 0)
        ks = tuple(o.scale)
        ac.write_vec(o, "scale", [1, f - 1, f], [ks, ks, (0, 0, 0)])
        hit = locs[-1]
        print(f"  fall: {prop.name} falls from {p0.z:.2f} m in {T:.3f} s (g {g}) -> impact f{fi}")
        prop.impact = fi
        # shards (white ceramic) and puddle
        china = _mat("china", "#EDEBE4", 0.35, 0.4)
        coffee = _mat("coffee", "#3E2718", 0.12, 0.6)
        for j in range(4):
            bm = bmesh.new()
            for _ in range(6):
                bm.verts.new((rng.uniform(-1, 1) * 0.03, rng.uniform(-1, 1) * 0.022, rng.uniform(0, 1) * 0.02))
            bmesh.ops.convex_hull(bm, input=bm.verts)
            me = bpy.data.meshes.new(f"shard{j}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(china)
            s = bpy.data.objects.new(f"{prop.name}_shard{j}", me)
            tgt_coll.objects.link(s)
            a = rng.uniform(0, math.tau)
            v = rng.uniform(0.6, 1.3)
            vz = rng.uniform(0.5, 0.9)
            dirv = Vector((math.cos(a), math.sin(a), 0))
            fr_s, ls, rs = [], [], []
            x, z, vzz, vh = 0.0, 0.0, vz, v
            for n in range(int(0.9 * fps)):
                dt = 1.0 / fps
                vzz -= g * dt
                z += vzz * dt
                if z < 0:
                    z, vzz, vh = 0.0, -vzz * 0.25, vh * 0.45
                x += vh * dt
                vh *= 0.93 if z == 0 else 1.0
                fr_s.append(fi + n)
                ls.append(hit + dirv * x + Vector((0, 0, z + 0.004)))
                rs.append(x * 18.0)
            ac.write_vec(s, "location", fr_s, ls)
            ac.write(s, "rotation_euler", 2, fr_s, rs)
            ac.write_vec(s, "scale", [1, fi - 1, fi], [(0, 0, 0), (0, 0, 0), (1, 1, 1)])
            s.location, s.scale = ls[0], (0, 0, 0)
        n = 14
        pv = [(0, 0, 0)] + [(math.cos(math.tau * i / n) * rng.uniform(0.75, 1.15), math.sin(math.tau * i / n) * rng.uniform(0.75, 1.15) * 0.8, 0)
                            for i in range(n)]
        pf = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
        pud = _mesh(f"{prop.name}_puddle", [(pv, pf, 0)], [coffee], tgt_coll)
        pud.visible_shadow = False
        pud.location = (hit.x + fwd.x * 0.05, hit.y + fwd.y * 0.05, 0.003)
        pud.rotation_euler = (0, 0, hd)
        fr_p = list(range(fi, fi + int(0.7 * fps)))
        ac.write_vec(pud, "scale", [1, fi - 1] + fr_p,
                     [(0, 0, 0), (0, 0, 0)] + [(0.24 * (1 - (1 - (x - fi) / len(fr_p)) ** 3),) * 2 + (1,) for x in fr_p])
        pud.scale = (0, 0, 0)


def _write_slump(fps):
    """Mountain range: dust only on the peaks (big soft-edged clouds that rise and spread in ~5 s), without sliding slopes."""
    import build
    for t, f, fps_ in _reg["slump"]:
        rng = random.Random("slump")
        fr = list(range(f, f + int(6.5 * fps) + 1, 2))
        akey = [(x, 0.75 * _smooth((x - f) / (0.8 * fps)) * (1 - _smooth(((x - f) / fps - 3.0) / 3.0))) for x in fr]
        mat, pr = build._dust_material("RidgeDust", akey)
        pr.inputs["Base Color"].default_value = kit.lin("#D9CFBF")
        pr.inputs["Emission Color"].default_value = kit.lin("#D9CFBF")
        pr.inputs["Emission Strength"].default_value = 0.35
        base = bmesh.new()
        bmesh.ops.create_icosphere(base, subdivisions=2, radius=1.0)
        for v in base.verts:
            v.co *= rng.uniform(0.85, 1.12)
            if v.co.z < 0:
                v.co.z *= 0.45
        me = bpy.data.meshes.new("ridge_dust")
        base.to_mesh(me)
        base.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(mat)
        for px, py, ph, _pr in RIDGE_PEAKS[:3]:
            for j in range(8):
                o = bpy.data.objects.new(f"ridge_dust_{int(px)}_{j}", me)
                t.coll.objects.link(o)
                o.visible_shadow = False
                a = rng.uniform(0, math.tau)
                r0 = rng.uniform(0, 40)
                x0, y0 = px + r0 * math.cos(a), py + r0 * math.sin(a) * 0.6
                z0 = t.h(x0, y0) - rng.uniform(15, 35)
                size = rng.uniform(18, 34)
                delay = rng.uniform(0, 0.8)
                ls, ss = [], []
                for x in fr:
                    tt = (x - f) / fps - delay
                    if tt <= 0:
                        ls.append((x0, y0, z0)); ss.append((0, 0, 0)); continue
                    grow = 1 - (1 - min(1.0, tt / 2.5)) ** 2
                    ls.append((x0 + 10 * tt * math.cos(a), y0, z0 + 10 * grow + 2 * tt))
                    s = size * (0.25 + 1.1 * grow)
                    ss.append((s * 1.3, s, s * 0.7))
                ac.write_vec(o, "location", fr, ls)
                ac.write_vec(o, "scale", [1, f - 1] + fr, [(0, 0, 0), (0, 0, 0)] + ss)
                o.scale = (0, 0, 0)
        print(f"  slump: dust on 3 peaks of the mountain range from f{f}")


def finish(fps, last):
    """Writes the stage's curves after the cues and reactions (the cup's fall reads the hand already with the 'react')."""
    for name, (prop, evs) in _reg["buckle"].items():
        _write_buckle(prop, evs, fps, last)
    _write_scale(fps, last)
    _write_sag(fps, last)
    _write_bend(fps, last)
    _write_falls(fps)
    _write_slump(fps)
    if _reg["walkers"]:
        _animate_background(fps, last)
