"""Pieces made in code for the data-driven stage (no file in assets/) and the 'ocean' stage.

Written for oceans-no-salt: there was no boat, animated gull or ice in
CC0 among the downloaded assets (catalog.json). All low-poly, flat, 3 to 6 colors per piece.

Proportion references (real numbers):
- Open 4 m fishing dinghy (wood/fiberglass skiff, "13 ft"): beam 1.5 to 1.6 m, depth 0.7 m, draft 0.3 m, freeboard
  0.45 m; small outboard motor (2 to 6 hp) with a 0.4 m cowl. Style: low-poly boats from Kenney Watercraft and
  Quaternius Ships (hull in sections, colored band at the gunwale, red antifouling bottom).
- Yellow-legged gull (Larus michahellis): 0.6 m long, 1.4 m wingspan, gray mantle #9AA4AE,
  black wingtip (same recipe as tools/blender/lib/gull.py, plants-extinct); gliding flight
  ~8 m/s, shallow surface dive (plunge) from 3 to 6 m.
- Wooden fishing pier: 2.5 to 3 m deck, 25 to 30 cm posts every 3 m, top ~0.8 m above calm
  water; ice fishing hole of 20 to 30 cm (8 to 10 in auger); ice safe to walk on >= 10 cm.
- Fisherman: the catalog's 'man' (Quaternius, CC0); rod of 2.4 to 2.7 m (ice rod, 0.7 to 0.9 m); 20 L bucket
  (0.36 m high) turned over serves as a stool.

The 'ocean' stage (presets.SETS) calls build_ocean: faceted water out to the horizon (Geometry Nodes waves with the
scene time, amplitude that fades with distance so it does not shimmer), pier in front of the camera, islands in the back,
buoys and boats far away. Piece heights: pier top at z = 0, water at WATER_Z (surface_height).
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

WATER_Z = -0.8                   # water level (m); the pier top sits at z = 0
SHORE_Y = -40.0                  # the beach (behind the camera, which looks toward +y, the sea)
PIER = (-1.2, 1.6, -49.0, 5.2)   # x0, x1, y0, y1 of the pier top
ICE_TOP = 0.07                   # top of the ice above the water (the 'z' of whoever stands on it)
POST_ROWS = 3.0                  # posts every 3 m
FLOATERS = []                    # pieces that float (boat, buoy): sway written in finish()
ACTIVE = {"ocean": False, "park": False, "riverside": False}
LAMPS = []                       # pier lamp post lights (turn on only in the light that asks: LIGHTS[...]['lamp'])
_mats = {}


def sea_group(hexa="#2C6A84"):
    """Sea color in a node group (an animatable RGB): the water uses it directly and the ice mixes 28% of it, so the
    'water' cue darkens the water and, lightly, the ice on top (the sea darkening under the ice)."""
    ng = bpy.data.node_groups.get("SeaColor")
    if ng is None:
        ng = bpy.data.node_groups.new("SeaColor", "ShaderNodeTree")
        ng.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
        rgb = ng.nodes.new("ShaderNodeRGB")
        rgb.name = "Sea"
        rgb.outputs[0].default_value = kit.lin(hexa)
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rgb.outputs[0], out.inputs[0])
    return ng


def _sea_mix(material, amount):
    nt = material.node_tree
    p = kit.principled(material)
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = sea_group()
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[0].default_value = amount
    mix.inputs[6].default_value = p.inputs["Base Color"].default_value
    nt.links.new(g.outputs[0], mix.inputs[7])
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])


def mat(name, hexa, rough=0.85, spec=0.2):
    key = (name, hexa)
    if key not in _mats:
        m = kit.flat(f"P_{name}", hexa, rough=rough)
        kit.principled(m).inputs["Specular IOR Level"].default_value = spec
        _mats[key] = m
    return _mats[key]


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ---------- relief of the 'ocean' stage ----------

def terrain_height(x, y):
    """Sea floor (under the water, -3 m) rising to the beach and the hills behind the camera (y < SHORE_Y)."""
    d = SHORE_Y - y                                   # > 0 on land
    t = _smooth((d + 10.0) / 22.0)
    z = -3.0 + 3.9 * t
    k = _smooth((d - 12.0) / 120.0)
    h = (math.sin(x * 0.021 + 1.3) * math.cos(y * 0.017) + 0.6 * math.sin(x * 0.047 - y * 0.039 + 2.1)
         + 0.35 * math.cos(x * 0.09 + y * 0.083)) * 9.0
    return z + k * max(h + 4.0, 0.0)


def in_pier(x, y, pad=0.0):
    return PIER[0] - pad <= x <= PIER[1] + pad and PIER[2] - pad <= y <= PIER[3] + pad


def surface_height(x, y):
    """Where a piece stands: pier top (0), the water (WATER_Z) or the beach ground."""
    if in_pier(x, y):
        return 0.0
    return max(terrain_height(x, y), WATER_Z)


def is_land(x, y):
    return terrain_height(x, y) > WATER_Z + 0.4


def pier_posts():
    """Posts that extend past the top (where the boat ties up): the two at the end of the pier."""
    x0, x1, _y0, y1 = PIER
    return [Vector((x1 - 0.1, y1 - 0.2, 0.85)), Vector((x0 + 0.1, y1 - 0.2, 0.85))]


# ---------- geometria ----------

def _mesh(name, parts, mats, coll, location=(0, 0, 0), recalc=True):
    """parts: [(verts, faces, material index)] in a single flat mesh."""
    verts, faces, fm = [], [], []
    for v, f, mi in parts:
        base = len(verts)
        verts += [tuple(p) for p in v]
        faces += [tuple(i + base for i in face) for face in f]
        fm += [mi] * len(f) if isinstance(mi, int) else list(mi)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    for poly, idx in zip(me.polygons, fm):
        poly.material_index = idx
        poly.use_smooth = False
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    coll.objects.link(obj)
    return obj


def _box(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return v, f


def _cyl(n, r0, r1, z0, z1, cx=0.0, cy=0.0, rot=0.0):
    v = [(cx + r * math.cos(rot + math.tau * i / n), cy + r * math.sin(rot + math.tau * i / n), z)
         for z, r in ((z0, r0), (z1, r1)) for i in range(n)]
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def _empty(name, coll, location=(0, 0, 0), parent=None, size=0.1):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    coll.objects.link(e)
    e.parent = parent
    e.location = location
    return e


def _tube_y(n=6, r0=0.02, r1=0.02, length=1.0):
    """Tube along +y from 0 to 'length' (rod, line, rope)."""
    v = [(r * math.cos(math.tau * i / n), y, r * math.sin(math.tau * i / n)) for y, r in ((0.0, r0), (length, r1))
         for i in range(n)]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return v, f


def stretch_line(name, coll, parent, local, target, radius, material):
    """Straight line (rope, fishing line) leaving 'local' (on the parent) and stretching to the empty 'target' (Stretch To:
    follows the parent and the target every frame, no keys)."""
    v, f = _tube_y(5, radius, radius, 1.0)
    o = _mesh(name, [(v, f, 0)], [material], coll)
    o.parent = parent
    o.location = local
    c = o.constraints.new("STRETCH_TO")
    c.target = target
    c.rest_length = 1.0
    c.volume = "NO_VOLUME"
    c.keep_axis = "PLANE_X"
    o.visible_shadow = False
    return o


# ---------- barco ----------

_BOAT = [  # x (m, stern -> bow), half-beam, gunwale above the water, draft
    (-2.00, 0.62, 0.42, 0.22), (-1.50, 0.72, 0.42, 0.28), (-0.80, 0.78, 0.43, 0.30), (0.00, 0.78, 0.46, 0.30),
    (0.80, 0.70, 0.52, 0.28), (1.40, 0.50, 0.60, 0.22), (1.80, 0.26, 0.68, 0.13), (2.00, 0.03, 0.74, 0.06)]
_boat_mesh = {}


def _profile(b, s, k):
    """Hull section (lateral y, z): from the left gunwale to the right, with a chine at the waterline (z = 0)."""
    yz = lambda z: -(0.93 * b + (0.985 * b - 0.93 * b) * z / (s - 0.09))
    hi, lo = SALT_BAND
    side = [(-b, s), (-0.985 * b, s - 0.09), (yz(hi + 0.07), hi + 0.07), (yz(hi), hi), (yz(lo), lo),
            (-0.66 * b, -0.72 * k)]
    return side + [(0.0, -k)] + [(-py, pz) for py, pz in reversed(side)]


SALT_BAND = (0.06, 0.0)          # dry salt crust on the hull (m above the old waterline): sinks in "lower"


def _boat_parts():
    WHITE, BLUE, RED, WOOD, DARK, GREY, NAVY, SALT = range(8)
    out = []
    rings = [[(x, py, pz) for py, pz in _profile(b, s, k)] for x, b, s, k in _BOAT]
    # blue gunwale, light side, dark boot stripe (wet), white salt crust, waterline, red bottom
    half = [BLUE, WHITE, NAVY, SALT, RED, RED]
    band = half + list(reversed(half))
    v, f, m = [], [], []
    n = len(rings[0])
    for ring in rings:
        v += ring
    for i in range(len(rings) - 1):
        for j in range(n - 1):
            f.append((i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j))
            m.append(band[j])
    out.append((v, f, m))
    out.append((rings[0], [tuple(range(n))], WHITE))                      # transom
    t = 0.045                                                             # thickness of the side
    inner = []
    for idx, (x, b, s, k) in enumerate(_BOAT[:6]):
        xi = -2.0 + t if idx == 0 else x
        inner.append([(xi, py, pz) for py, pz in _profile(b - t, s, k - t)])
    v = [p for ring in inner for p in ring]
    f = [(i * n + j + 1, i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1) for i in range(len(inner) - 1) for j in range(n - 1)]
    out.append((v, f, WOOD))
    out.append((inner[0], [tuple(range(n - 1, -1, -1))], WOOD))
    out.append((inner[-1], [tuple(range(n))], WOOD))                      # bow bulkhead
    # gunwale (tar): connects the outer top to the inner one, on both sides
    for side in (0, n - 1):
        v, f = [], []
        for i in range(len(inner)):
            v += [rings[i][side], inner[i][side]]
        f = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) for i in range(len(inner) - 1)]
        out.append((v, f, DARK))
    out.append(([rings[0][0], rings[0][-1], inner[0][-1], inner[0][0]], [(0, 1, 2, 3)], DARK))
    # bow deck (from x = 1.4 to the wheel)
    v = []
    for i in range(5, len(rings)):
        v += [rings[i][0], rings[i][-1]]
    f = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range((len(v) // 2) - 1)]
    out.append((v, f, DARK))
    # benches, floorboard and outboard motor
    for x in (-0.95, 0.45):
        b = 0.74 if x < 0 else 0.70
        out.append((*_box(x - 0.12, x + 0.12, -b + 0.06, b - 0.06, 0.25, 0.29), DARK))
    out.append((*_box(-1.7, 1.15, -0.32, 0.32, -0.215, -0.19), WOOD))
    out.append((*_box(-2.34, -2.03, -0.14, 0.14, 0.30, 0.66), GREY))
    out.append((*_box(-2.30, -2.07, -0.12, 0.12, 0.66, 0.72), WHITE))
    out.append((*_box(-2.23, -2.15, -0.035, 0.035, -0.42, 0.30), GREY))
    out.append((*_box(-2.28, -2.10, -0.012, 0.012, -0.46, -0.34), GREY))
    out.append((*_box(-2.03, -1.62, -0.02, 0.02, 0.50, 0.54), GREY))
    return out


def build_boat(name, coll):
    mats = [mat("hull", "#E8E2D4", 0.7), mat("stripe", "#2E5B88", 0.7), mat("bottom", "#8E3B2F", 0.8),
            mat("wood", "#A87B4F", 0.9), mat("darkwood", "#6E4E33", 0.9), mat("motor", "#3A3F46", 0.6),
            mat("boot", "#26384C", 0.8), mat("salt", "#F7F5EE", 1.0, 0.05)]
    if "boat" not in _boat_mesh:
        o = _mesh(name, _boat_parts(), mats, coll, recalc=False)
        _boat_mesh["boat"] = o.data
        return o
    o = bpy.data.objects.new(name, _boat_mesh["boat"])
    coll.objects.link(o)
    return o


def spawn_boat(name, coll, spec, x, y, heading, start, end, fps, rng, ropes=True):
    """'len' m dinghy (hull), at the waterline; tied by two ropes to the nearest pier posts (< 4 m)."""
    boat = build_boat(name, coll)
    k = float(spec.get("len", 4.0)) / 4.0
    boat.scale = (k, k, k)
    boat.location = (x, y, WATER_Z)
    boat.rotation_euler = (0, 0, heading)
    left = Vector((-math.sin(heading), math.cos(heading), 0))
    if ropes and ACTIVE["ocean"]:
        rope = mat("rope", "#C9B48A", 0.9)
        side = 1.0 if left.x * ((PIER[0] + PIER[1]) / 2 - x) > 0 else -1.0
        bpy.context.view_layer.update()
        for n, (lx, ly, lz) in enumerate(((1.3, 0.55, 0.62), (-1.7, 0.6, 0.46))):
            local = Vector((lx, ly * side, lz))
            p = boat.matrix_world @ local
            near = min(pier_posts(), key=lambda q: (q - p).length)
            if (near - p).length > 4.0:
                continue
            tgt = _empty(f"{name}Post{n}", coll, near)
            stretch_line(f"{name}Rope{n}", coll, boat, local, tgt, 0.02 / k, rope)
    FLOATERS.append(SimpleNamespace(obj=boat, start=start, end=end, env=[(start, 1.0)], seed=rng.random() * 10,
                                    heave=0.01 if ropes and ACTIVE["ocean"] else 0.035, roll=1.4 if ropes else 2.2,
                                    pitch=0.6 if ropes else 0.9, period=4.6, moored=bool(ropes and ACTIVE["ocean"]),
                                    foot=(x, y, 2.05 * k, 0.8 * k, heading)))
    return SimpleNamespace(obj=boat, height=1.04 * k)


# ---------- gaivota ----------

def build_gull(name, coll, scale=1.0):
    white, grey, black = mat("gull_white", "#F1F0EA", 0.8), mat("gull_grey", "#9AA4AE", 0.8), mat("gull_black", "#26292E", 0.8)
    beak = mat("gull_beak", "#E8B83A", 0.7)
    root = _empty(name, coll)
    root.scale = (scale,) * 3
    bv, bf = kit.tube_geo([(-0.3, 0, 0.0), (-0.18, 0, 0.0), (0.05, 0, 0.01), (0.2, 0, 0.03), (0.27, 0, 0.03)],
                          [0.02, 0.055, 0.07, 0.05, 0.03], n=6)
    tail = ([(-0.22, -0.06, 0.0), (-0.36, -0.07, 0.0), (-0.36, 0.07, 0.0), (-0.22, 0.06, 0.0)], [(0, 1, 2, 3)])
    bk = ([(0.27, -0.02, 0.04), (0.27, 0.02, 0.04), (0.27, 0.0, 0.01), (0.35, 0.0, 0.025)],
          [(0, 1, 3), (1, 2, 3), (2, 0, 3), (0, 2, 1)])
    body = _mesh(f"{name}Body", [(bv, bf, 0), (*tail, 0), (*bk, 1)], [white, beak], coll, recalc=False)
    body.parent = root
    wings = []
    for side in (1, -1):
        sh = _empty(f"{name}Sh{side}", coll, (0.03, 0.05 * side, 0.03), root, 0.05)
        sh.rotation_mode = "XYZ"
        arm = ([(0.06, 0, 0), (-0.08, 0, 0), (-0.06, 0.34 * side, 0.0), (0.06, 0.34 * side, 0.0)], [(0, 1, 2, 3)])
        a = _mesh(f"{name}Arm{side}", [(*arm, 0)], [grey], coll, recalc=False)
        a.parent = sh
        wr = _empty(f"{name}Wr{side}", coll, (0.0, 0.34 * side, 0.0), sh, 0.05)
        wr.rotation_mode = "XYZ"
        hand = ([(0.06, 0, 0), (-0.06, 0, 0), (-0.12, 0.3 * side, 0.0), (-0.02, 0.36 * side, 0.0)], [(0, 1, 2, 3)])
        tip = ([(-0.08, 0.2 * side, 0.002), (-0.12, 0.3 * side, 0.002), (-0.02, 0.36 * side, 0.002),
                (0.02, 0.24 * side, 0.002)], [(0, 1, 2, 3)])
        h = _mesh(f"{name}Hand{side}", [(*hand, 0), (*tip, 1)], [grey, black], coll, recalc=False)
        h.parent = wr
        wings.append((sh, wr, side))
    for o in [root, *root.children_recursive]:
        if o.type == "MESH":
            o.visible_shadow = False
    return SimpleNamespace(root=root, wings=wings)


def _splash(name, coll, size=1.0):
    """Dive splash, low-poly and matte (no transparency): foam crown with tips that rises in 3 frames and
    falls, ring that opens on the water and 6 faceted drops in a parabola. Created hidden (scale 0); keys in _key_splash."""
    foam = mat("foam", "#F4F7F7", 1.0, 0.0)
    n = 10
    v = [(0.16 * math.cos(math.tau * i / n), 0.16 * math.sin(math.tau * i / n), 0.0) for i in range(n)]
    v += [(0.3 * math.cos(math.tau * (i + 0.5 * (i % 2)) / n), 0.3 * math.sin(math.tau * (i + 0.5 * (i % 2)) / n),
           0.55 if i % 2 == 0 else 0.32) for i in range(n)]
    fc = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    crown = _mesh(f"{name}Crown", [(v, fc, 0)], [foam], coll, recalc=False)
    rv, rf = _cyl(12, 0.42, 0.3, -0.02, 0.05)
    ring = _mesh(f"{name}Ring", [(rv, rf, 0)], [foam], coll)
    drops = []
    for j in range(6):
        dv = [(0.04, 0, 0), (-0.03, 0.03, 0), (-0.03, -0.03, 0), (0, 0, 0.05), (0, 0, -0.04)]
        df = [(0, 1, 3), (1, 2, 3), (2, 0, 3), (1, 0, 4), (2, 1, 4), (0, 2, 4)]
        drops.append(_mesh(f"{name}Drop{j}", [(dv, df, 0)], [foam], coll))
    for o in [crown, ring, *drops]:
        o.visible_shadow = False
        o.scale = (0, 0, 0)
    return SimpleNamespace(crown=crown, ring=ring, drops=drops, size=size)


def _key_splash(sp, at, f, fps, rng):
    s = sp.size
    sp.crown.location = sp.ring.location = at
    fr = [f - 1, f, f + 3, f + 8, f + 14]
    for i, vals in enumerate(([0, 0.5, 1.0, 1.15, 0.0], [0, 0.5, 1.0, 1.15, 0.0], [0, 0.6, 1.0, 0.55, 0.0])):
        ac.write(sp.crown, "scale", i, fr, [x * s for x in vals])
    fr = [f - 1, f, f + 6, f + 20, f + 30]
    for i, vals in enumerate(([0, 0.4, 1.0, 1.6, 0.0], [0, 0.4, 1.0, 1.6, 0.0], [0, 1.0, 1.0, 0.6, 0.0])):
        ac.write(sp.ring, "scale", i, fr, [x * s for x in vals])
    for j, d in enumerate(sp.drops):
        a = math.tau * j / len(sp.drops) + rng.uniform(-0.3, 0.3)
        vxy, vz = rng.uniform(0.8, 1.4) * s, rng.uniform(2.2, 3.2) * s
        frames = list(range(f, f + 18))
        pts = []
        for fr_ in frames:
            t = (fr_ - f) / fps
            pts.append(Vector((at.x + vxy * t * math.cos(a), at.y + vxy * t * math.sin(a),
                               at.z + 0.1 + vz * t - 4.9 * t * t)))
        ac.write_vec(d, "location", frames, pts)
        for i in range(3):
            ac.write(d, "scale", i, [f - 1, f, f + 12, f + 17], [0, s, s * 0.8, 0])


GULLS = []                       # gulls: trajectory written in finish() (the 'dive' cue marks the dive time)


def spawn_gull(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Gull that circles 3 to 5 m from the water ('alt'), around x, y (radius 'radius'), gliding with short flaps and
    dives once in the scene (descends accelerating with wings in a V, touches the water with a splash and climbs flapping its wings):
    comes back with nothing in its beak. With "dive": "cue", it only dives on the 'dive' cue (otherwise, at a random instant); with
    "dive": "here", it dives on the cue and touches the water exactly at 'at' (the circle shifts)."""
    length = float(spec.get("len", 0.6))
    g = build_gull(name, coll, length / 0.6)
    R = float(spec.get("radius", 0)) or rng.uniform(3.0, 5.5)
    v = rng.uniform(4.5, 6.0)
    w = v / R * rng.choice((-1, 1))
    if spec.get("radius"):
        w = math.copysign(min(abs(w), 1.1), w)               # small circle: slower
    a0 = rng.uniform(0, math.tau)
    alt = float(spec.get("alt", 0)) or rng.uniform(3.0, 4.6)
    dur = (end - start) / fps
    td = None if spec.get("dive") in ("cue", "here") else rng.uniform(0.18, 0.8) * dur
    sp = _splash(f"{name}Splash", coll, size=max(0.7, length / 0.6))
    ns = SimpleNamespace(g=g, x=x, y=y, R=R, w=w, a0=a0, alt=alt, td=td, start=start, end=end, fps=fps,
                         flap_seed=rng.uniform(0, 3), splash=sp, rng=rng, name=name, here=spec.get("dive") == "here")
    GULLS.append(ns)
    p0 = Vector((x + R * math.cos(a0), y + R * math.sin(a0), WATER_Z + alt))
    g.root.location = p0
    return SimpleNamespace(obj=g.root, height=0.25 * length / 0.6, positions=[(start, p0)], gull=ns)


def gull_dive(obj, f, delay=0.0):
    """Cue 'dive': the gull starts to descend at frame f (+ 'delay' s)."""
    for ns in GULLS:
        if ns.g.root is obj:
            ns.td = (f - ns.start) / ns.fps + delay
            return True
    return False


def _animate_gull(ns):
    g, fps, start, end = ns.g, ns.fps, ns.start, ns.end
    x, y, R, w, a0, alt, td = ns.x, ns.y, ns.R, ns.w, ns.a0, ns.alt, ns.td
    down, touch, up = 0.75, 0.25, 1.3
    frames = list(range(start, end + 1))
    pts, dives = [], []
    ang = a0
    for fr in frames:
        t = (fr - start) / fps
        dz, slow, fold, climb = 0.0, 1.0, 0.0, 0.0
        if td is not None and td <= t < td + down:
            u = (t - td) / down
            dz, slow, fold = -(alt - 0.1) * u * u, 0.6, _smooth(u * 3)
        elif td is not None and td + down <= t < td + down + touch:
            dz, slow, fold = -(alt - 0.1), 0.25, 1.0 - _smooth((t - td - down) / touch)
        elif td is not None and td + down + touch <= t < td + down + touch + up:
            u = (t - td - down - touch) / up
            dz, slow, climb = -(alt - 0.1) * (1 - _smooth(u)), 0.6, 1.0
        ang += w * slow / fps
        p = Vector((x + R * math.cos(ang), y + R * math.sin(ang), WATER_Z + alt + 0.35 * math.sin(t * 0.8 + a0) + dz))
        pts.append(p)
        dives.append((fold, climb))
    if td is not None and ns.here:                     # "dive": "here": the circle shifts to touch the water at x, y
        ft = start + int((td + down) * fps)
        if ft < end:
            off = Vector((x - pts[ft - start].x, y - pts[ft - start].y, 0.0))
            pts = [p + off for p in pts]
    if td is not None:
        ft = start + int((td + down) * fps)
        if ft < end:
            i = ft - start
            _key_splash(ns.splash, Vector((pts[i].x, pts[i].y, WATER_Z)), ft, fps, ns.rng)
    locs, rots = [], []
    prev_yaw = None
    for i, p in enumerate(pts):
        q, r = pts[min(i + 1, len(pts) - 1)], pts[max(i - 1, 0)]
        d = q - r
        yaw = math.atan2(d.y, d.x)
        if prev_yaw is not None:
            yaw = prev_yaw + (yaw - prev_yaw + math.pi) % math.tau - math.pi
        prev_yaw = yaw
        bank = -math.copysign(0.35, w) * (1 - dives[i][0])
        pitch = -math.atan2(d.z, max(d.to_2d().length, 1e-4))
        locs.append(p)
        rots.append((bank, max(-1.2, min(1.2, pitch)), yaw))
    step = frames[::2] + ([frames[-1]] if len(frames) % 2 == 0 else [])
    idx = [f - start for f in step]
    ac.write_vec(g.root, "location", step, [locs[i] for i in idx])
    ac.write_vec(g.root, "rotation_euler", step, [rots[i] for i in idx])
    for sh, wr, side in g.wings:
        a_sh, a_wr = [], []
        for i in idx:
            t = i / fps
            fold, climb = dives[i]
            cyc = (t + ns.flap_seed) % 3.2                     # glide with two flaps every 3.2 s
            glide = math.sin(2 * math.pi * 3.0 * cyc) * _smooth(min(cyc, 0.66 - cyc) * 10) if cyc < 0.66 else 0.0
            flap = climb * math.sin(2 * math.pi * 3.4 * t) + (1 - climb) * (1 - fold) * glide
            a_sh.append(side * (math.radians(10 + 50 * fold) + math.radians(38) * flap))
            a_wr.append(side * (math.radians(-14 - 40 * fold) + math.radians(-22) * flap))
        ac.write(sh, "rotation_euler", 0, step, a_sh)
        ac.write(wr, "rotation_euler", 0, step, a_wr)


# ---------- gelo ----------

def _pip(pt, poly):
    x, y = pt
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0:
            inside = not inside
    return inside


def _blocked(poly, cx, cy):
    """Does the plate hit the pier or a boat? (vertices, center and edge midpoints; and the pier line inside it)."""
    pts = list(poly) + [(cx, cy)] + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(poly, poly[1:] + poly[:1])]
    if ACTIVE["ocean"]:
        if any(in_pier(px, py, 0.12) for px, py in pts):
            return True
        mx = (PIER[0] + PIER[1]) / 2
        yy = PIER[2]
        while yy <= PIER[3]:
            for xx in (PIER[0], mx, PIER[1]):
                if _pip((xx, yy), poly):
                    return True
            yy += 0.5
    for fl in FLOATERS:
        fx, fy, half_l, half_b, hd = fl.foot
        c, s = math.cos(hd), math.sin(hd)
        for px, py in pts:
            lx, ly = (px - fx) * c + (py - fy) * s, -(px - fx) * s + (py - fy) * c
            if abs(lx) < half_l + 0.12 and abs(ly) < half_b + 0.12:
                return True
        if _pip((fx, fy), poly):
            return True
    return False


def spawn_ice(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Bay frozen in plates (rings around the fishing hole at x, y, of radius 0.16 m), with cracks that
    show the water; no plate crosses the pier or the boat. Each plate is an object with the pivot at its own center:
    the 'grow' cue opens the plates from near to far (the water freezing in sheets)."""
    spread = float(spec.get("spread", 110.0))
    root = _empty(name, coll, (x, y, WATER_Z))
    tones = [mat("ice_a", "#E6EEF1", 0.35, 0.3), mat("ice_b", "#D3E0E7", 0.4, 0.3), mat("ice_c", "#C6D6DF", 0.45, 0.3),
             mat("ice_snow", "#F1F4F5", 0.8, 0.15)]
    for t in tones:
        if not t.get("sea"):
            _sea_mix(t, 0.08 if t.name.endswith("snow") else 0.28)
            _tone_jitter(t, 0.08)
            t["sea"] = 1
    edges = [0.16, 0.8]
    while edges[-1] < spread:
        edges.append(edges[-1] * rng.uniform(1.22, 1.4))
    parts = []
    z0, z1 = -0.03, ICE_TOP
    for ri, (ra, rb) in enumerate(zip(edges, edges[1:])):
        n = max(6, int(round(math.tau * (ra + rb) / 2 / (rb - ra) * 0.85)))
        off = rng.uniform(0, math.tau)
        for si in range(n):
            a0, a1 = off + math.tau * si / n, off + math.tau * (si + 1) / n
            am = (a0 + a1) / 2
            size = rb - ra
            jit = lambda: rng.uniform(-0.22, 0.22) * size
            ring = [(ra, a0), (ra, am), (ra, a1), (rb, a1), (rb, am), (rb, a0)] if size > 1.2 else \
                [(ra, a0), (ra, a1), (rb, a1), (rb, a0)]
            poly = []
            for r, a in ring:
                jr = 0.0 if ri == 0 and r == ra else jit()          # the edge of the hole stays round
                poly.append((x + (r + jr) * math.cos(a) + (0 if ri == 0 else jit() * 0.5),
                             y + (r + jr) * math.sin(a) + (0 if ri == 0 else jit() * 0.5)))
            d_c = (ra + rb) / 2
            gap = 0.985 if ri == 0 else (0.99 if d_c < 25 else 0.975)     # bay: thin gap (1%) near the pier
            # a plate that hits the pier or the boat becomes 4 pieces (up to 2 times): no big gaps of water next to them
            queue, depth_of = [(poly, 0)], 2 if ri else 0
            while queue:
                pl, dep = queue.pop()
                cx, cy = sum(p[0] for p in pl) / len(pl), sum(p[1] for p in pl) / len(pl)
                shr = [(cx + (px - cx) * gap, cy + (py - cy) * gap) for px, py in pl]
                if _blocked(shr, cx, cy):
                    if dep < depth_of:
                        n_ = len(pl)
                        mids = [((pl[i][0] + pl[(i + 1) % n_][0]) / 2, (pl[i][1] + pl[(i + 1) % n_][1]) / 2) for i in range(n_)]
                        for i in range(n_):
                            queue.append(([mids[i - 1], pl[i], mids[i], (cx, cy)], dep + 1))
                    continue
                m = len(shr)
                v = [(px - cx, py - cy, z) for z in (z0, z1) for px, py in shr]
                fc = [tuple(range(m - 1, -1, -1)), tuple(range(m, 2 * m))] + [(i, (i + 1) % m, m + (i + 1) % m, m + i) for i in range(m)]
                tone = rng.randrange(3)
                snow = 3 if math.hypot(cx - x, cy - y) < 16 and rng.random() < 0.8 else tone   # neve rala no topo, perto
                o = _mesh(f"{name}P{ri}_{si}", [(v, fc, [tone, snow] + [tone] * m)], tones, coll, (cx, cy, WATER_Z))
                o.visible_shadow = ri > 1          # big plates cast shadows; the hole's do not (no shadow acne)
                parts.append((o, math.hypot(cx - x, cy - y)))
    _hole_kit(name, coll, x, y, tones, rng)
    ICE_FROM.append(start)
    return SimpleNamespace(obj=root, height=ICE_TOP, parts=parts)


ICE_FROM = []                    # first frame of each ice (the waves stop at the cut)
HOLES = []                       # fishing holes in the ice (plug, chips and auger for the 'drill' gesture)


def _tone_jitter(material, amount):
    """Each plate with its own value (+-amount), through the Object Info Random: the repeating 3-tone pattern disappears."""
    nt = material.node_tree
    p = kit.principled(material)
    link = next((l for l in nt.links if l.to_socket == p.inputs["Base Color"]), None)
    info = nt.nodes.new("ShaderNodeObjectInfo")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1 - amount, 1 + amount
    nt.links.new(info.outputs["Random"], mr.inputs["Value"])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    if link is not None:
        nt.links.new(link.from_socket, sc.inputs[0])
    else:
        sc.inputs[0].default_value = p.inputs["Base Color"].default_value[:3]
    nt.links.new(mr.outputs["Result"], sc.inputs["Scale"])
    nt.links.new(sc.outputs[0], p.inputs["Base Color"])


def _hole_kit(name, coll, x, y, tones, rng):
    """Ice plug over the hole (disappears when the auger comes out), ring of white chips (grow on the turn) and a hand
    auger standing beside it (steel shaft, dark bit, T crank with a wooden handle)."""
    top = WATER_Z + ICE_TOP
    pv, pf = _cyl(12, 0.17, 0.17, -0.03, ICE_TOP)
    plug = _mesh(f"{name}Plug", [(pv, pf, 0)], tones[:1], coll, (x, y, WATER_Z))
    plug.visible_shadow = False
    chip = mat("ice_chip", "#F6F8F9", 0.9, 0.1)
    chips = []
    for j in range(26):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(0.2, 0.42)
        sz = rng.uniform(0.025, 0.05)
        cv = [(sz * math.cos(b), sz * math.sin(b) * rng.uniform(0.6, 1.0), 0.0) for b in (0.0, 2.1, 4.2)] +              [(0.0, 0.0, sz * rng.uniform(0.5, 0.9))]
        cf = [(0, 1, 3), (1, 2, 3), (2, 0, 3), (2, 1, 0)]
        c = _mesh(f"{name}Chip{j}", [(cv, cf, 0)], [chip], coll, (x + r * math.cos(a), y + r * math.sin(a), top))
        c.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        c.visible_shadow = False
        c.scale = (0.01, 0.01, 0.01)
        chips.append(c)
    steel, dark, wood = mat("auger_steel", "#9EA6AD", 0.4, 0.5), mat("auger_bit", "#3A3F46", 0.5), mat("auger_grip", "#B5532E", 0.8)
    parts = [(*_cyl(8, 0.075, 0.075, 0.0, 0.42), 1), (*_cyl(6, 0.016, 0.016, 0.42, AUGER_H), 0),
             (*_box(-0.012, 0.13, -0.012, 0.012, AUGER_H - 0.012, AUGER_H + 0.012), 0),
             (*_cyl(6, 0.022, 0.022, AUGER_H - 0.02, AUGER_H + 0.11, 0.11, 0.0), 2),
             (*_box(-0.13, 0.0, -0.012, 0.012, AUGER_H - 0.012, AUGER_H + 0.012), 0)]
    for z in (0.08, 0.2, 0.32):                         # auger bit flanges (suggested spiral)
        parts.append((*_cyl(8, 0.1, 0.1, z, z + 0.025), 1))
    aug = _mesh(f"{name}Auger", parts, [steel, dark, wood], coll)
    aug.rotation_mode = "XYZ"
    aug.location = (x - 0.05, y + 0.45, top)            # standing on the ice beside the hole (+y): without sweeping the body
    aug.rotation_euler = (0.0, 0.0, 0.0)
    HOLES.append(SimpleNamespace(x=x, y=y, plug=plug, chips=chips, auger=aug))


def grow_parts(parts, f, end, fps, a, b, dur, stagger, keep, origin):
    """'grow' of a piece with plates: the inner one (up to 'keep' m from the pivot) is already done at the cut; the others open in
    order of distance over 'stagger' s, each in 'dur' s. Returns the frame function of each distance."""
    dmax = max((d for _o, d in parts), default=1.0)

    def when(d):
        if d <= keep:
            return None
        return f + int(stagger * fps * (d - keep) / max(dmax - keep, 1e-3))
    for o, d in parts:
        f0 = when(d)
        if f0 is None:
            continue
        f1 = f0 + max(1, int(dur * fps))
        frames = [f0 - 1, f0, f0 + (f1 - f0) // 2, f1]
        frames[0] = max(frames[0], 0)
        vals = [a, a, a + (b - a) * 0.75, b]
        for i in range(2):
            ac.write(o, "scale", i, frames, vals)
        o.scale = (a, a, 1.0)
    return when


def freeze_floaters(origin, when, cut, fps, radius=130.0):
    """What floats inside the ice stops rocking when the plate at its distance closes (or already at the cut)."""
    for fl in FLOATERS:
        d = math.hypot(fl.foot[0] - origin.x, fl.foot[1] - origin.y)
        if d > radius:
            continue
        f0 = when(d)
        if f0 is None:
            still(fl.obj, cut, 0, fps, immediate=True)
        else:
            still(fl.obj, f0, 1.5, fps)


def still(obj, f, dur, fps, immediate=False):
    for fl in FLOATERS:
        if fl.obj is obj:
            cur = _amp(fl.env, f)
            if immediate:
                fl.env += [(f - 1, cur), (f, 0.0)]
            else:
                fl.env += [(f, cur), (f + max(1, int(dur * fps)), 0.0)]
            fl.env.sort()
            return True
    return False


def _amp(env, f):
    if f <= env[0][0]:
        return env[0][1]
    for (f0, a0), (f1, a1) in zip(env, env[1:]):
        if f0 <= f <= f1:
            return a0 + (a1 - a0) * (f - f0) / max(f1 - f0, 1)
    return env[-1][1]


def finish(fps):
    """Sway of the pieces that float (delta: does not fight the 'move' or the position): heave, roll and pitch
    slow, with periods prime to each other; amplitude by the envelope (the ice locks). Also closes rods, buoys and gulls."""
    for ns in GULLS:
        _animate_gull(ns)
    _finish_kits()
    _finish_fish()
    for fl in FLOATERS:
        frames = list(range(fl.start, fl.end + 1, 2))
        hz, rl, pt = [], [], []
        for f in frames:
            t = f / fps
            a = _amp(fl.env, f)
            hz.append(a * fl.heave * math.sin(math.tau * t / fl.period + fl.seed))
            rl.append(a * math.radians(fl.roll) * math.sin(math.tau * t / (fl.period * 1.37) + fl.seed * 1.7))
            pt.append(a * math.radians(fl.pitch) * math.sin(math.tau * t / (fl.period * 0.83) + fl.seed * 0.6))
        ac.write(fl.obj, "delta_location", 2, frames, hz)
        ac.write(fl.obj, "delta_rotation_euler", 0, frames, rl)
        ac.write(fl.obj, "delta_rotation_euler", 1, frames, pt)


# ---------- fisherman (rod, line, bucket, gestures) ----------

def _bone_local(rig, bone, frame=None):
    if frame is not None:
        bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    w = rig.arm.matrix_world @ rig.arm.pose.bones[bone].head
    return rig.root.matrix_world.inverted() @ w


def _ik(rig, side, target, pole, pole_angle=-90.0):
    ik = rig.arm.pose.bones[f"Palm.{side}"].constraints.new("IK")      # in this asset: LowerArm = arm, Palm = forearm
    ik.target, ik.pole_target = target, pole
    ik.pole_angle = math.radians(pole_angle)
    ik.chain_count = 2
    ik.use_stretch = False
    return ik


def _rod_dir(pitch, yaw):
    """Direction of the rod in the root coordinates (front = -y, left = +x, up = +z)."""
    p, w = math.radians(pitch), math.radians(yaw)
    return Vector((math.cos(p) * math.sin(w), -math.cos(p) * math.cos(w), math.sin(p)))


def _bucket(name, coll, parent, local, upside=False, crate=0.0):
    wood, pail, rim = mat("crate", "#8C6A45", 0.9), mat("bucket", "#5F7F95", 0.6), mat("bucket_rim", "#3E5566", 0.6)
    parts = []
    if crate:
        parts.append((*_box(-0.22, 0.22, -0.16, 0.16, 0.0, crate), 0))
    h = 0.34 if upside else 0.30
    r0, r1 = (0.15, 0.12) if upside else (0.11, 0.14)
    parts.append((*_cyl(10, r0, r1, crate, crate + h), 1))
    parts.append((*_cyl(10, r1 + 0.008, r1 + 0.008, crate + h - 0.03, crate + h + 0.003), 2) if not upside else
                 (*_cyl(10, r0 + 0.008, r0 + 0.008, crate - 0.003, crate + 0.03), 2))
    if not upside:                                            # water inside the bucket (dark), below the rim
        parts.append((*_cyl(10, r1 - 0.01, r1 - 0.01, crate + h - 0.08, crate + h - 0.07), 3))
    o = _mesh(name, parts, [wood, pail, rim, mat("bucket_water", "#244E62", 0.3, 0.4)], coll)
    o.parent = parent
    o.location = local
    return o


KITS = []                        # rods: handle rotation and float path written in finish()


def fisher_kit(prop, spec, coll, start, end, fps, sitting, cam_at=(0.0, 0.0)):
    """Rod in one hand (IK to the 'grip' target, child of the root), line stretched to the float in the water, bucket. Standing, the free hand
    (the one that drinks) stays on the camera side and the bucket on a crate in front of it; seated, the rod stays on the camera side
    and the overturned bucket is the stool. Root coordinates: front = -y, left = +x (mirrored by 'm')."""
    rig = prop.rig
    root = rig.root
    length = float(spec["rod"])
    h = root.rotation_euler.z - math.pi / 2
    left = Vector((-math.sin(h), math.cos(h)))
    cam_left = left.dot(Vector((cam_at[0] - root.location.x, cam_at[1] - root.location.y))) > 0
    rod_side = ("L" if cam_left else "R") if sitting else ("R" if cam_left else "L")
    free = "R" if rod_side == "L" else "L"
    m = 1.0 if rod_side == "L" else -1.0
    M = lambda v: Vector((v.x * m, v.y, v.z))
    sh_rod = _bone_local(rig, f"UpperArm.{rod_side}", start + 1)
    sh_free = _bone_local(rig, f"UpperArm.{free}", start + 1)
    if sitting:
        grip_at, pitch, yaw = M(Vector((0.16, -0.16, 0.62))), -30.0, -6.0 * m
        _bucket(f"{prop.name}Seat", coll, root, Vector((0.0, 0.2, 0.0)), upside=True)
    else:
        grip_at, pitch, yaw = M(Vector((0.2, -0.3, 1.0))), 35.0, 10.0 * m
        _bucket(f"{prop.name}Bucket", coll, root, M(Vector((-0.34, -0.3, 0.0))), crate=0.48)
    grip = _empty(f"{prop.name}Grip", coll, grip_at, root, 0.05)
    grip.rotation_mode = "QUATERNION"
    grip.rotation_quaternion = _rod_dir(pitch, yaw).to_track_quat("Y", "Z")
    pole_l = _empty(f"{prop.name}Elbow{rod_side}", coll, sh_rod + M(Vector((0.45, 0.15, -0.35))), root, 0.05)
    _ik(rig, rod_side, grip, pole_l)
    rod_mats = [mat("rod", "#2B2F36", 0.5), mat("rod_grip", "#7A5A3A", 0.9)]
    # rod in 3 sections (handle, middle, tip) with the pivot at the joint: the tip bends on the bite
    tip_len, mid_len = 0.35 * length, 0.30 * length
    butt_len = length - tip_len - mid_len
    hold = min(0.4, butt_len)
    v1, f1 = _tube_y(6, 0.016, 0.013, hold)
    v2, f2 = _tube_y(5, 0.012, 0.011, butt_len - hold)
    v2 = [(a, b + hold, c) for a, b, c in v2]
    rod = _mesh(f"{prop.name}Rod", [(v1, f1, 1), (v2, f2, 0)], rod_mats, coll)
    rod.parent = grip
    rod.location = (0, -0.3, 0)                       # 30 cm of handle behind the hand
    rod_mid = _mesh(f"{prop.name}RodMid", [(*_tube_y(5, 0.011, 0.0085, mid_len), 0)], rod_mats, coll)
    rod_mid.parent, rod_mid.location, rod_mid.rotation_mode = rod, (0, butt_len, 0), "XYZ"
    rod_tip = _mesh(f"{prop.name}RodTip", [(*_tube_y(5, 0.0085, 0.005, tip_len), 0)], rod_mats, coll)
    rod_tip.parent, rod_tip.location, rod_tip.rotation_mode = rod_mid, (0, mid_len, 0), "XYZ"
    bpy.context.view_layer.update()
    tip_local = Vector((0, tip_len, 0))               # in the tip's space
    tip = rod_tip.matrix_world @ tip_local
    flt = _empty(f"{prop.name}Float", coll, (tip.x, tip.y, WATER_Z), None, 0.05)
    red, white = mat("float", "#D9432F", 0.6), mat("float_top", "#F2EFE6", 0.6)
    b = _mesh(f"{prop.name}Bobber", [(*_cyl(8, 0.05, 0.012, 0.0, 0.07), 0), (*_cyl(8, 0.012, 0.0, 0.07, 0.1), 1),
                                     (*_cyl(8, 0.0, 0.05, -0.045, 0.0), 0)], [red, white], coll)
    b.parent = flt
    b.visible_shadow = False
    lmat = mat("line", "#F4F1E8", 0.6)
    slack = float(spec.get("slack", 0.0))
    if slack > 0:                                     # slack line: 3 stretches, belly of 'slack' m (parabola)
        tip_e = _empty(f"{prop.name}LineTip", coll, tip_local, rod_tip, 0.02)
        pts = []
        for j, u in enumerate((1 / 3, 2 / 3)):
            mid = _empty(f"{prop.name}LineMid{j}", coll, (0, 0, 0), None, 0.02)
            c1 = mid.constraints.new("COPY_LOCATION")
            c1.target = tip_e
            c2 = mid.constraints.new("COPY_LOCATION")
            c2.target, c2.influence = flt, u
            pts.append(_empty(f"{prop.name}LineSag{j}", coll, (0, 0, -4 * slack * u * (1 - u)), mid, 0.02))
        line = stretch_line(f"{prop.name}Line", coll, rod_tip, tip_local, pts[0], 0.009, lmat)
        stretch_line(f"{prop.name}Line1", coll, pts[0], (0, 0, 0), pts[1], 0.009, lmat)
        stretch_line(f"{prop.name}Line2", coll, pts[1], (0, 0, 0), flt, 0.009, lmat)
    else:
        line = stretch_line(f"{prop.name}Line", coll, rod_tip, tip_local, flt, 0.009, lmat)
    if in_pier(tip.x, tip.y, 0.1) and ACTIVE["ocean"]:
        kit.problem(f"{prop.name}: the rod's line falls on the pier (tip at x {tip.x:.2f}, y {tip.y:.2f}); turn the piece ('face')")
    hand_r = _empty(f"{prop.name}Hand{free}", coll, _bone_local(rig, f"Palm.{free}", start + 1), root, 0.05)
    pole_r = _empty(f"{prop.name}Elbow{free}", coll, sh_free + M(Vector((-0.4, -0.15, -0.35))), root, 0.05)
    ik_r = _ik(rig, free, hand_r, pole_r)
    ik_r.influence = 0.0
    seed = random.Random(prop.name).uniform(0, 6)
    mug = None
    if not sitting:                                   # tin mug (light enamel, blue rim) attached to the free fist
        enamel, rimc = mat("mug", "#ECEEEA", 0.5), mat("mug_rim", "#2E5B88", 0.5)
        hv, hf = _box(-0.012, 0.012, 0.045, 0.075, 0.02, 0.075)
        mug = _mesh(f"{prop.name}Mug", [(*_cyl(10, 0.042, 0.045, -0.045, 0.045), 0),
                                        (*_cyl(10, 0.047, 0.047, 0.036, 0.047), 1), (hv, hf, 0)], [enamel, rimc], coll)
        mug.visible_shadow = False
        mug.scale = (0, 0, 0)
    prop.kit = SimpleNamespace(grip=grip, rod=rod, rod_mid=rod_mid, rod_tip=rod_tip, bobber=b, line=line, mug=mug,
                               pitch=pitch, yaw=yaw, flt=flt, hand_r=hand_r, ik_r=ik_r, rig=rig,
                               sitting=sitting, shr=sh_free, start=start, end=end, tip_local=tip_local, seed=seed, fps=fps,
                               free=free, m=m, bend_keys=[(start, 0.0)], twist=[],
                               pitch_keys=[(start, 0.0)], float_keys=[(start, Vector(flt.location))], infl=[],
                               name=prop.name)
    KITS.append(prop.kit)
    if sitting:                                       # breathes and watches the float, slowly (nothing still for 10 s)
        def life(f):
            t = f / fps
            return _bend(rig, {"Torso": [((1, 0, 0), 1.6 * math.sin(t * 1.6))],
                               "Neck": [((1, 0, 0), 14.0), ((0, 0, 1), 7.0 * math.sin(t * 0.33 + seed))],
                               "Head": [((1, 0, 0), 12.0 + 2.0 * math.sin(t * 0.7))]})
        rigs.pose_layer(rig, list(range(start, end + 1, 2)), life)
    return prop.kit


REST_MODES = ("leaned", "down")


def rest_kit(prop, spec, coll, start, end, fps, sitting, cam_at=(0.0, 0.0)):
    """Gave up fishing: no line, no float, nothing in hand. "rod": "leaned" leans the 2.6 m rod on the
    nearest mooring post (foot on the top, support at the top of the post); "down" lays the rod on the pier top, beside him.
    Seated ('Sitting'): sits on a crate and the empty bucket stays on the top beside him, head down looking at the water.
    Standing: the empty bucket stays on the crate beside him (as in fishing) and he looks at the sea, head slightly down."""
    rig = prop.rig
    root = rig.root
    h = root.rotation_euler.z - math.pi / 2
    left = Vector((-math.sin(h), math.cos(h)))
    cam_left = left.dot(Vector((cam_at[0] - root.location.x, cam_at[1] - root.location.y))) > 0
    m = 1.0 if cam_left else -1.0                         # local +x on the camera side (the bucket stays in view)
    wood = mat("crate", "#8C6A45", 0.9)
    if sitting:
        crate = _mesh(f"{prop.name}Crate", [(*_box(-0.22, 0.22, 0.04, 0.36, 0.0, 0.36), 0)], [wood], coll)
        crate.parent, crate.location = root, (0, 0, 0)
        _bucket(f"{prop.name}Bucket", coll, root, Vector((0.48 * m, -0.12, 0.0)))
    else:
        _bucket(f"{prop.name}Bucket", coll, root, Vector((0.36 * m, -0.3, 0.0)), crate=0.48)
    rod_mats = [mat("rod", "#2B2F36", 0.5), mat("rod_grip", "#7A5A3A", 0.9)]
    length = 2.6
    v1, f1 = _tube_y(6, 0.016, 0.013, 0.4)
    v2, f2 = _tube_y(5, 0.012, 0.005, length - 0.4)
    v2 = [(a, b + 0.4, c) for a, b, c in v2]
    rod = _mesh(f"{prop.name}RestRod", [(v1, f1, 1), (v2, f2, 0)], rod_mats, coll)
    bpy.context.view_layer.update()
    me = root.matrix_world.translation
    mode = str(spec.get("rod"))
    if mode == "leaned":
        ref = Vector(spec["rod_at"]) if spec.get("rod_at") else me.to_2d()     # "rod_at": [x, y] escolhe a estaca
        post = min(pier_posts(), key=lambda q: (q.to_2d() - ref).length)
        inward = Vector(((PIER[0] + PIER[1]) / 2 - post.x, -0.6, 0.0)).normalized()
        butt = Vector((post.x, post.y, 0.0)) + inward * 0.42
        rest = Vector((post.x, post.y, post.z - 0.03)) + inward * 0.15     # leans on the side of the top of the post
        d = (rest - butt).normalized()
    else:                                                 # lying on the top, beside him, parallel to the pier
        side = root.matrix_world.to_3x3() @ Vector((-0.75 * m, 0.1, 0.0))
        butt = me + side + Vector((0, -1.1, 0.0))
        butt.z = 0.016
        d = Vector((0.0, 1.0, 0.0))
    rod.matrix_world = Matrix.Translation(butt) @ d.to_track_quat("Y", "Z").to_matrix().to_4x4()
    tip = butt + d * length
    if mode == "down" and not in_pier(tip.x, tip.y):
        kit.problem(f"{prop.name}: the lying rod goes off the pier (tip at {tip.x:.2f}, {tip.y:.2f})")
    seed = random.Random(prop.name).uniform(0, 6)
    if sitting:                                           # slumped: torso fallen, head down, breathes slowly
        def life(f):
            t = f / fps
            return _bend(rig, {"Abdomen": [((1, 0, 0), 8.0)],
                               "Torso": [((1, 0, 0), 10.0 + 1.6 * math.sin(t * 1.3))],
                               "Neck": [((1, 0, 0), 24.0), ((0, 0, 1), 5.0 * math.sin(t * 0.27 + seed))],
                               "Head": [((1, 0, 0), 20.0 + 2.0 * math.sin(t * 0.6))]})
    else:                                                 # standing, looks at the sea, head slightly down, turns slowly
        def life(f):
            t = f / fps
            return _bend(rig, {"Neck": [((1, 0, 0), 10.0), ((0, 0, 1), 9.0 * math.sin(t * 0.22 + seed))],
                               "Head": [((1, 0, 0), 9.0 + 1.5 * math.sin(t * 0.5))]})
    rigs.pose_layer(rig, list(range(start, end + 1, 2)), life)
    return SimpleNamespace(rod=rod)


def carry_kit(prop, coll, frame, bucket=True):
    """Going home: 2.6 m rod in the left hand, pointing up and back (child of the bone: sways with the
    arm), and the empty bucket hanging from the right hand (follows the fist, stays upright: Copy Location + Copy Rotation)."""
    rig = prop.rig
    scene = bpy.context.scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    rod_mats = [mat("rod", "#2B2F36", 0.5), mat("rod_grip", "#7A5A3A", 0.9)]
    v1, f1 = _tube_y(6, 0.016, 0.013, 0.4)
    v2, f2 = _tube_y(5, 0.012, 0.005, 2.2)
    v2 = [(a, b + 0.4, c) for a, b, c in v2]
    rod = _mesh(f"{prop.name}CarryRod", [(v1, f1, 1), (v2, f2, 0)], rod_mats, coll)
    pb = rig.arm.pose.bones["Palm.L"]
    bone_m = rig.arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    grip = rig.arm.matrix_world @ pb.tail
    heading = rig.root.matrix_world.to_euler().z - math.pi / 2
    fwd = Vector((math.cos(heading), math.sin(heading), 0))
    d = (Vector((0, 0, 1)) * math.cos(math.radians(62)) - fwd * math.sin(math.radians(62))).normalized()
    world = Matrix.Translation(grip - d * 0.25) @ d.to_track_quat("Y", "Z").to_matrix().to_4x4()
    rod.parent, rod.parent_type, rod.parent_bone = rig.arm, "BONE", "Palm.L"
    rod.matrix_parent_inverse = Matrix.Identity(4)
    rod.matrix_basis = bone_m.inverted() @ world
    if not bucket:                                       # "carry": "rod": only the rod (the bucket in hand looked odd)
        return SimpleNamespace(rod=rod, bucket=None)
    pail, rim, handle = mat("bucket", "#5F7F95", 0.6), mat("bucket_rim", "#3E5566", 0.6), mat("rod", "#2B2F36", 0.5)
    hv = [(-0.29, 0, -0.18), (-0.09, 0, -0.05), (-0.01, 0, -0.05), (-0.01, 0, -0.18)]
    ox = -0.15                                           # the bucket hangs outward from the right leg
    parts = [(*_cyl(10, 0.11, 0.14, -0.48, -0.18, ox), 0), (*_cyl(10, 0.148, 0.148, -0.21, -0.178, ox), 1)]
    for a_, b_ in zip(hv, hv[1:]):                       # wire handle
        parts.append((*_box(min(a_[0], b_[0]), max(a_[0], b_[0]) + 0.008, -0.005, 0.005,
                            min(a_[2], b_[2]), max(a_[2], b_[2]) + 0.008), 2))
    tilt = Matrix.Rotation(math.radians(20), 3, "Y")   # hangs tilted outward (away from the leg while walking)
    parts = [([tuple(tilt @ Vector(v_)) for v_ in vv], ff, mi) for vv, ff, mi in parts]
    b = _mesh(f"{prop.name}CarryBucket", parts, [pail, rim, handle], coll)
    c1 = b.constraints.new("COPY_LOCATION")
    c1.target, c1.subtarget, c1.head_tail = rig.arm, "Palm.R", 1.0
    c2 = b.constraints.new("COPY_ROTATION")
    c2.target = rig.root
    return SimpleNamespace(rod=rod, bucket=b)


def _bend(rig, spec):
    out = {}
    for bone, rots in spec.items():
        if bone not in rig.arm.pose.bones:
            continue
        q = None
        for axis, deg in rots:
            d = rigs.bone_delta(rig, bone, axis, deg)
            q = d if q is None else q @ d
        out[bone] = q
    return out


GESTURES = ("drink", "cast", "bite", "drill")


def _ease_keys(points, frames):
    """points [(frame, value)] -> value at each frame of 'frames', smoothed between points (holds at the ends)."""
    points = sorted(points, key=lambda kv: kv[0])
    out = []
    for f in frames:
        if f <= points[0][0]:
            out.append(points[0][1])
            continue
        for (f0, a), (f1, b) in zip(points, points[1:]):
            if f0 <= f <= f1:
                out.append(a + (b - a) * _smooth((f - f0) / max(f1 - f0, 1)))
                break
        else:
            out.append(points[-1][1])
    return out


def gesture(prop, name, f, fps, cue=None):
    """Fisherman gestures (the piece needs 'rod'):
    drink = picks the tin mug inside the bucket, brings it to the mouth turning the face to the camera, drinks, holds it to the chest,
    takes a second sip on the next line and returns the mug to the bucket (~12 s in total);
    cast = throws (the rod rises backward and whips; the float flies in a parabola to 'to' [x, y] or 1.8 m farther);
    bite = the float sinks fully twice, the rod tip bends ~15 degrees, and the line goes slack;
    drill = (seated, on the ice) turns the auger in the hole: white chips around, the hole opens when the auger comes out."""
    k = getattr(prop, "kit", None)
    if k is None:
        kit.problem(f"gesture '{name}' on '{prop.name}': the piece needs 'rod' for the fishing gestures")
        return
    rig = prop.rig
    s = fps / 30.0
    F = lambda n: f + int(round(n * s))
    if name == "drink":
        if k.mug is None:
            kit.problem(f"gesture 'drink' on '{prop.name}': standing only (seated has no mug)")
            return
        M = lambda v: Vector((v.x * k.m, v.y, v.z))
        rest = _bone_local(rig, f"Palm.{k.free}", f)
        bucket = M(Vector((-0.34, -0.3, 0.72)))
        dip = bucket + M(Vector((0.03, 0.02, -0.06)))
        up = M(Vector((-0.24, -0.36, 1.12)))
        mouth = M(Vector((-0.06, -0.24, 1.45)))
        chest = M(Vector((-0.2, -0.34, 1.12)))
        reach = M(Vector((-0.36, -0.36, 0.95)))
        keys = [(f, rest), (F(10), reach), (F(20), bucket), (F(28), dip), (F(38), up), (F(50), mouth),
                (F(74), mouth + Vector((0.0, 0.02, 0.02))), (F(88), chest), (F(276), chest), (F(290), mouth),
                (F(304), mouth), (F(318), chest), (F(332), reach), (F(344), dip), (F(356), reach), (F(370), rest)]
        frames = list(range(f - 2, F(372) + 1))
        for i in range(3):
            ac.write(k.hand_r, "location", i, frames, _ease_keys([(a, v[i]) for a, v in keys], frames))
        tilt = [(f, 0.0), (F(50), 0.0), (F(57), -68.0), (F(72), -68.0), (F(84), 0.0), (F(290), 0.0), (F(295), -60.0),
                (F(303), -60.0), (F(313), 0.0)]
        k.hand_r.rotation_mode = "XYZ"
        ac.write(k.hand_r, "rotation_euler", 0, frames, [math.radians(v) for v in _ease_keys(tilt, frames)])
        k.infl += [(f - 2, 0.0), (F(6), 1.0), (F(358), 1.0), (F(370), 0.0)]
        for i in range(3):
            ac.write(k.mug, "scale", i, [f, F(24), F(25), F(345), F(346)], [0, 0, 1, 1, 0])
        k.mug.parent = k.hand_r
        k.mug.location = M(Vector((-0.02, -0.05, 0.05)))
        bend = dict(zip(frames, _ease_keys([(f, 0.0), (F(18), 1.0), (F(28), 1.0), (F(46), 0.0), (F(330), 0.0),
                                            (F(340), 1.0), (F(348), 1.0), (F(362), 0.0)], frames)))
        drink = dict(zip(frames, _ease_keys([(F(46), 0.0), (F(57), 1.0), (F(74), 1.0), (F(90), 0.0), (F(288), 0.0),
                                             (F(296), 1.0), (F(304), 1.0), (F(316), 0.0)], frames)))
        turn = dict(zip(frames, _ease_keys([(F(30), 0.0), (F(52), 1.0), (F(100), 1.0), (F(130), 0.0)], frames)))
        tw = k.m * TWIST_SIGN
        rigs.pose_layer(rig, frames, lambda fr: _bend(rig, {
            "Abdomen": [((1, 0, 0), 26 * bend[fr]), ((0, 0, 1), 10 * tw * turn[fr])],
            "Torso": [((1, 0, 0), 12 * bend[fr] - 6 * drink[fr]), ((0, 0, 1), 14 * tw * turn[fr])],
            "Neck": [((1, 0, 0), 8 * bend[fr] - 10 * drink[fr]), ((0, 0, 1), 18 * tw * turn[fr])],
            "Head": [((1, 0, 0), 10 * bend[fr] - 16 * drink[fr]), ((0, 0, 1), 16 * tw * turn[fr])]}))
        sh = k.shr + Vector((0.0, -0.28, -0.14))       # shoulder with the torso bent
        kit.require_reach(f"{prop.name} drinks from the bucket", rig.root.matrix_world @ sh, rig.root.matrix_world @ bucket)
        return
    if name == "drill":
        _drill(prop, k, f, fps, F)
        return
    loc = _vec_at(k.float_keys, f)
    if name == "cast":
        k.pitch_keys += [(f, 0.0), (F(10), 34.0), (F(14), 34.0), (F(20), -14.0), (F(30), 0.0)]
        k.bend_keys += [(f, 0.0), (F(12), 6.0), (F(18), -10.0), (F(26), 3.0), (F(34), 0.0)]
        root = rig.root.matrix_world.translation
        if cue and cue.get("to"):
            far = Vector((float(cue["to"][0]), float(cue["to"][1]), WATER_Z))
        else:
            out = Vector((loc.x - root.x, loc.y - root.y, 0)).normalized()
            far = Vector((loc.x, loc.y, WATER_Z)) + out * 1.8
        lift = loc + Vector((0, 0, 1.0))
        k.float_keys += [(f, loc), (F(8), lift)]
        n = max(2, F(34) - F(8))
        for i in range(1, n + 1):                      # parabolic flight (key on every frame: no stopping midway)
            u = i / n
            p = lift.lerp(far, u)
            p.z = lift.z + (far.z - lift.z) * u + 2.2 * 4 * u * (1 - u)
            k.float_keys.append((F(8) + i, p))
        k.float_keys.append((F(40), far.copy()))
        if in_pier(far.x, far.y, 0.1) and ACTIVE["ocean"]:
            kit.problem(f"{prop.name}: o arremesso cai no cais ({far.x:.2f}, {far.y:.2f})")
    elif name == "bite":
        k.pitch_keys += [(f, 0.0), (F(3), -9.0), (F(7), 0.0), (F(10), -12.0), (F(15), 0.0), (F(24), 2.0), (F(34), 0.0)]
        k.bend_keys += [(f, 0.0), (F(3), -14.0), (F(7), -3.0), (F(10), -17.0), (F(16), -2.0), (F(26), 1.5), (F(36), 0.0)]
        k.float_keys += [(f, loc), (F(2), loc + Vector((0, 0, -0.2))), (F(7), loc + Vector((0, 0, -0.04))),
                         (F(10), loc + Vector((0, 0, -0.26))), (F(17), loc), (F(36), loc)]


TWIST_SIGN = -1.0                # direction of the torso twist toward the free-hand side (measured on a still)
AUGER_H = 0.95                   # height of the auger crank above the tip


def _drill(prop, k, f, fps, F):
    """Auger in the nearest hole (from spawn_ice): goes standing to the hole, turns 2 s sinking with the free hand
    on the crank, releases the chips in a ring, comes out and goes back to the side; the plug disappears when the auger comes out (hole open) and the
    float drops from the rod tip into the hole."""
    if not k.sitting or not HOLES:
        kit.problem(f"gesture 'drill' on '{prop.name}': must be seated ('Sitting') and needs an 'ice' in the scene")
        return
    root = prop.rig.root
    hole = min(HOLES, key=lambda h: (Vector((h.x, h.y)) - root.matrix_world.translation.to_2d()).length)
    aug = hole.auger
    top = WATER_Z + ICE_TOP
    lay_loc = Vector(aug.location)
    lay_rot = tuple(aug.rotation_euler)
    up_loc = Vector((hole.x, hole.y, top))
    f0, f1, f2, f3, f4 = F(0), F(10), F(70), F(80), F(92)
    frames = list(range(f0 - 1, f4 + 1))
    locs, rots = [], []
    for fr in frames:
        if fr <= f1:                                    # takes the auger standing to the hole, in a short arc
            u = _smooth((fr - f0) / max(f1 - f0, 1))
            p = lay_loc.lerp(up_loc + Vector((0, 0, 0.05)), u) + Vector((0, 0, 0.12 * math.sin(math.pi * u)))
            r = (lay_rot[0] * (1 - u), lay_rot[1] * (1 - u), lay_rot[2])
        elif fr <= f2:                                  # gira afundando
            u = (fr - f1) / max(f2 - f1, 1)
            p = up_loc + Vector((0, 0, 0.05 - 0.23 * u))
            r = (0.0, 0.0, lay_rot[2] + math.tau * 3.0 * u)
        elif fr <= f3:                                  # pulls out
            u = _smooth((fr - f2) / max(f3 - f2, 1))
            p = up_loc + Vector((0, 0, -0.18 + 0.42 * u))
            r = (0.0, 0.0, lay_rot[2] + math.tau * 3.0)
        else:                                           # goes back to the side of the hole, standing
            u = _smooth((fr - f3) / max(f4 - f3, 1))
            p = (up_loc + Vector((0, 0, 0.24))).lerp(lay_loc, u)
            r = (0.0, 0.0, lay_rot[2] + math.tau * 3.0)
        locs.append(p)
        rots.append(r)
    ac.write_vec(aug, "location", frames, locs)
    ac.write_vec(aug, "rotation_euler", frames, rots)
    for i in range(3):
        ac.write(hole.plug, "scale", i, [f0, f3 - 1, f3], [1, 1, 0])
    rng = random.Random(prop.name + "chips")
    for c in hole.chips:                               # chips: appear during the turn, in random order
        c0 = rng.randint(f1 + 4, f2 - 6)
        for i in range(3):
            ac.write(c, "scale", i, [f0, c0, c0 + 4], [0.01, 0.01, 1.0])   # 0.01 and not 0: rotation defined
    # free hand on the crank (target follows the turning crank; child of the root)
    inv = root.matrix_world.inverted()
    hand = []
    for p, r in zip(locs, rots):
        crank = Matrix.Translation(p) @ Matrix.Rotation(r[2], 4, "Z") @ Matrix.Rotation(r[1], 4, "Y") \
            @ Matrix.Rotation(r[0], 4, "X") @ Vector((0.11, 0.0, AUGER_H))
        hand.append(inv @ crank)
    rest = _bone_local(prop.rig, f"Palm.{k.free}", f0)
    pre = [rest.lerp(hand[0], _smooth(i / 8)) for i in range(8)]
    hf = list(range(f0 - 9, f0 - 1)) + frames + list(range(f4 + 1, f4 + 11))
    post = [hand[-1].lerp(rest, _smooth(i / 10)) for i in range(1, 11)]
    allp = pre + hand + post
    for i in range(3):
        ac.write(k.hand_r, "location", i, hf, [v[i] for v in allp])
    k.infl += [(f0 - 9, 0.0), (f0, 1.0), (f4 - 4, 1.0), (f4 + 10, 0.0)]
    lean = dict(zip(hf, _ease_keys([(f0 - 9, 0.0), (f0 + 2, 1.0), (f4 - 6, 1.0), (f4 + 10, 0.0)], hf)))
    rigs.pose_layer(prop.rig, hf, lambda fr: _bend(prop.rig, {"Abdomen": [((1, 0, 0), 20 * lean[fr])],
                                                            "Torso": [((1, 0, 0), 12 * lean[fr])]}))
    kit.require_reach(f"{prop.name} gira o trado", root.matrix_world @ k.shr, root.matrix_world @ hand[len(hand) // 2])
    # line: pulled in at the rod tip until the hole opens; then the float goes down into the hole
    bpy.context.view_layer.update()
    tip = k.rod_tip.matrix_world @ k.tip_local
    k.float_keys[:] = [(k.start, tip.copy()), (F(84), tip.copy()), (F(100), Vector((hole.x, hole.y, WATER_Z + 0.02))),
                       (F(110), Vector((hole.x, hole.y, WATER_Z)))]
    for i in range(3):
        ac.write(k.bobber, "scale", i, [k.start, F(84), F(88)], [0.0, 0.0, 1.0])
    k.hide_line = (k.start, F(84))


def _vec_at(keys, f):
    keys = sorted(keys, key=lambda kv: kv[0])
    if f <= keys[0][0]:
        return keys[0][1].copy()
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            return a.lerp(b, _smooth((f - f0) / max(f1 - f0, 1)))
    return keys[-1][1].copy()


def _finish_kits():
    for k in KITS:
        frames = list(range(k.start, k.end + 1))
        d = _ease_keys(k.pitch_keys, frames)
        sub = frames[::2]
        qs = {f: _rod_dir(k.pitch + d[f - k.start], k.yaw).to_track_quat("Y", "Z") for f in sub}
        for i in range(4):
            ac.write(k.grip, "rotation_quaternion", i, sub, [qs[f][i] for f in sub])
        bend = _ease_keys(k.bend_keys, frames)          # rod tip: 40% of the curve in the middle, 60% in the tip
        ac.write(k.rod_mid, "rotation_euler", 0, frames, [math.radians(0.4 * b) for b in bend])
        ac.write(k.rod_tip, "rotation_euler", 0, frames, [math.radians(0.6 * b) for b in bend])
        locs = []
        for f in sub:
            p = _vec_at(k.float_keys, f)
            if k.sitting:                                # in the ice hole: still water, only a slight up and down
                if abs(p.z - WATER_Z) < 0.021:
                    p.z += 0.008 * math.sin(f / k.fps * 1.3 + k.seed)
            elif abs(p.z - WATER_Z) < 0.02 or p.z < WATER_Z:   # in the water: follows the wave (without disappearing at the crest)
                sfps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base   # GN time is the scene's
                p.z += wave_height(p.x, p.y, f / sfps) + 0.008 * math.sin(f / k.fps * 1.3 + k.seed)
            locs.append(p)
        ac.write_vec(k.flt, "location", sub, locs)
        path = f'pose.bones["Palm.{k.free}"].constraints["{k.ik_r.name}"].influence'
        pts = sorted([(k.start, 0.0)] + k.infl + [(k.end, 0.0)], key=lambda kv: kv[0])
        fr = sorted({p[0] for p in pts} | set(range(pts[0][0], pts[-1][0] + 1, 2)))
        ac.write(k.rig.arm, path, 0, fr, _ease_keys(pts, fr))


# ---------- floating fish, live fish and foam (oceans-no-salt-text) ----------
# References: herring (Clupea harengus, 25-30 cm, thin body, blue-gray back, silvery flank), sea bream
# (Diplodus, 20-35 cm, tall body, bronze-gray flank) and mackerel (Scomber, 30-40 cm, dark blue back);
# height/length 0.2 (herring), 0.35 (sea bream), 0.22 (mackerel). Exaggerated to 0.3 to 0.6 m (reads in the POV).
# Low-poly in the style of the Quaternius fish (6-sided spindle, forked tail, triangular dorsal). Dead: on its side or
# belly up, rises from the bottom (hidden under the water) and floats with the wave (wave_height, the same math as the GN).
# No blood or wound: only the pose says "dead".

FISH_VARIANTS = {   # name: (relative height, (back, flank, belly))
    "herring": (1.0, ("#5F7686", "#C8D3DA", "#EEF0EC")),
    "bream": (1.55, ("#7D7660", "#CBC4A6", "#ECE8DA")),
    "mackerel": (1.1, ("#2F5470", "#A3B7C3", "#F0F0EA")),
}
FISH = []                        # fish (dead and alive) and foam: keys written in finish()
_fish_mesh = {}


def _fish_data(variant):
    """Mesh 1 m long (x = snout), body flattened sideways; back/flank/belly materials by height."""
    if variant in _fish_mesh:
        return _fish_mesh[variant]
    hk, (back, flank, belly) = FISH_VARIANTS[variant]
    xs = [0.5, 0.42, 0.28, 0.08, -0.14, -0.32, -0.42, -0.46]
    rs = [0.004, 0.045, 0.085, 0.105, 0.09, 0.05, 0.022, 0.012]
    v, f = kit.tube_geo([(x, 0.0, 0.0) for x in xs], [r * 1.05 for r in rs], n=6)
    v = [(x, y * 0.42 / hk, z * hk) for x, y, z in v]
    th = 0.16 * min(hk, 1.2)
    tail = ([(-0.44, 0.0, 0.0), (-0.62, 0.0, th), (-0.55, 0.0, 0.0), (-0.62, 0.0, -th)], [(0, 1, 2), (0, 2, 3)])
    dz = 0.1 * hk
    dorsal = ([(0.12, 0.0, dz * 0.95), (-0.14, 0.0, dz * 0.85), (-0.06, 0.0, dz + 0.11)], [(0, 1, 2)])
    pect = ([(0.26, 0.0, -0.03), (0.16, 0.0, -0.03), (0.13, 0.0, -0.1 * hk)], [(0, 1, 2)])
    mats = [mat(f"fish_back_{variant}", back, 0.5, 0.4), mat(f"fish_flank_{variant}", flank, 0.32, 0.75),
            mat(f"fish_belly_{variant}", belly, 0.45, 0.5), mat("fish_fin", "#8C98A0", 0.6, 0.3)]
    face_mats = []
    for face in f:
        cz = sum(v[i][2] for i in face) / len(face)
        face_mats.append(0 if cz > 0.045 * hk else (2 if cz < -0.035 * hk else 1))
    o = _mesh(f"fishmesh_{variant}", [(v, f, face_mats), (*tail, 3), (*dorsal, 0), (*pect, 3)], mats,
              bpy.context.scene.collection, recalc=False)
    data = o.data
    bpy.data.objects.remove(o)
    _fish_mesh[variant] = data
    return data


def _foam_data(rng, k):
    key = f"foam{k}"
    if key not in _fish_mesh:
        n = 13
        pts = []
        for i in range(n):                               # ragged edge: lobes and recesses (not a smooth polygon)
            r = rng.uniform(0.8, 1.0) if i % 2 == 0 else rng.uniform(0.58, 0.78)
            pts.append((math.cos(math.tau * i / n) * r, math.sin(math.tau * i / n) * r * 0.7, 0.0))
        o = _mesh(key, [([(0.0, 0.0, 0.01)] + pts, [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)], 0)],
                  [mat("dirty_foam", "#ADA383", 1.0, 0.05)], bpy.context.scene.collection, recalc=False)
        data = o.data
        bpy.data.objects.remove(o)
        _fish_mesh[key] = data
    return _fish_mesh[key]


def _blocked_water(x, y, pad=0.35):
    """Point on the pier, inside a boat or on land: fish does not float there."""
    if in_pier(x, y, pad) or is_land(x, y):
        return True
    for fl in FLOATERS:
        bx, by, hl, hb, hd = fl.foot
        dx, dy = x - bx, y - by
        u, w = dx * math.cos(hd) + dy * math.sin(hd), -dx * math.sin(hd) + dy * math.cos(hd)
        if abs(u) < hl + pad and abs(w) < hb + pad:
            return True
    return False


def _free_spot(x, y, rng, pad=0.35):
    if not _blocked_water(x, y, pad):
        return x, y
    for k in range(80):
        r = 0.4 + 0.08 * k
        a = rng.uniform(0, math.tau)
        if not _blocked_water(x + r * math.cos(a), y + r * math.sin(a), pad):
            return x + r * math.cos(a), y + r * math.sin(a)
    return x, y


def _length(spec, rng, default):
    ln = spec.get("len", default)
    return rng.uniform(*ln) if isinstance(ln, list) else float(ln)


def spawn_fish_dead(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Small dead fish, on its side or belly up, floating with the wave ('len' m). Silver, 3 shapes ('variant'
    draws one if missing). 'ready' (0 to 1): fraction that already floats at the cut; the others rise to the surface when the 'grow' cue
    calls them (with 'stagger', each at its own instant). Without a cue, all already float."""
    x, y = _free_spot(x, y, rng)
    variant = spec.get("variant") or rng.choice(list(FISH_VARIANTS))
    length = _length(spec, rng, 0.45)
    o = bpy.data.objects.new(name, _fish_data(variant))
    coll.objects.link(o)
    o.scale = (length,) * 3
    o.rotation_mode = "QUATERNION"
    o.location = (x, y, WATER_Z)
    o.visible_shadow = False
    roll = math.radians(rng.choice((rng.uniform(78, 100), rng.uniform(-100, -78), rng.uniform(160, 200))))
    ns = SimpleNamespace(obj=o, kind="dead", x=x, y=y, yaw=rng.uniform(0, math.tau), roll=roll, length=length,
                         start=start, end=end, fps=fps, rise=None,
                         ready=rng.random() < float(spec.get("ready", 1.0)), seed=rng.uniform(0, 10),
                         twitch=rng.random() < 0.45, drift=(rng.uniform(-0.02, 0.02), rng.uniform(-0.01, 0.025)))
    FISH.append(ns)
    return SimpleNamespace(obj=o, height=0.1, positions=[(start, Vector((x, y, WATER_Z)))])


def spawn_fish_live(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Live fish (tolerant species) swimming close to the surface in a loop around 'at' (back and fin out of the
    water, tail beating); jumps once in the scene ('jump': false turns it off), with a splash on exit and entry."""
    R = float(spec.get("radius", 1.3))
    x, y = _free_spot(x, y, rng, R * 1.4 + 0.4)
    variant = spec.get("variant") or "mackerel"
    length = _length(spec, rng, 0.4)
    o = bpy.data.objects.new(name, _fish_data(variant))
    coll.objects.link(o)
    o.scale = (length,) * 3
    o.rotation_mode = "QUATERNION"
    o.visible_shadow = False
    sp = _splash(f"{name}Splash", coll, size=0.45)
    sp2 = _splash(f"{name}Splash2", coll, size=0.4)
    dur = (end - start) / fps
    ns = SimpleNamespace(obj=o, kind="live", x=x, y=y, R=R, length=length, start=start, end=end, fps=fps,
                         seed=rng.uniform(0, 10), dirn=rng.choice((-1, 1)),
                         jump=None if spec.get("jump") is False else rng.uniform(0.25, 0.7) * dur,
                         splash=(sp, sp2), rng=rng)
    FISH.append(ns)
    if ns.jump is not None:
        print(f"  live fish {name}: jump at frame {start + int(ns.jump * fps)}")
    o.location = (x + R, y, WATER_Z)
    return SimpleNamespace(obj=o, height=0.1, positions=[(start, Vector((x, y, WATER_Z)))])


def spawn_foam(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Patch of dirty foam (matte beige) floating with the wave, 'len' m wide."""
    x, y = _free_spot(x, y, rng, 0.2)
    o = bpy.data.objects.new(name, _foam_data(rng, rng.randrange(4)))
    coll.objects.link(o)
    w = _length(spec, rng, 1.0)
    o.scale = (w * 0.5, w * 0.5, 1.0)
    o.rotation_mode = "QUATERNION"
    o.visible_shadow = False
    FISH.append(SimpleNamespace(obj=o, kind="foam", x=x, y=y, yaw=rng.uniform(0, math.tau), roll=0.0, length=w,
                                start=start, end=end, fps=fps, rise=None, ready=True, seed=rng.uniform(0, 10),
                                twitch=False, drift=(0.0, 0.0)))
    return SimpleNamespace(obj=o, height=0.02, positions=[(start, Vector((x, y, WATER_Z)))])


def fish_rise(obj, f, dur):
    """Cue 'grow' on a dead fish: it rises to the surface at frame f (in 'dur' s), turning on its side."""
    for ns in FISH:
        if ns.obj is obj and ns.kind == "dead":
            if not ns.ready:
                ns.rise = (f, max(6, int(dur * ns.fps)))
            return True
    return False


def is_fish(obj):
    return any(ns.obj is obj for ns in FISH)


def _surface_quat(x, y, t, yaw, roll, pitch=0.0):
    """Orientation of whatever floats: tilts with the wave slope, then turns (yaw), rears up (pitch) and lies down (roll)."""
    e = 0.25
    gx = (wave_height(x + e, y, t) - wave_height(x - e, y, t)) / (2 * e)
    gy = (wave_height(x, y + e, t) - wave_height(x, y - e, t)) / (2 * e)
    n = Vector((-gx, -gy, 1.0)).normalized()
    tilt = Vector((0, 0, 1)).rotation_difference(n)
    return tilt @ Matrix.Rotation(yaw, 4, "Z").to_quaternion() @ Matrix.Rotation(pitch, 4, "Y").to_quaternion() \
        @ Matrix.Rotation(roll, 4, "X").to_quaternion()


def _write_quats(obj, frames, qs):
    prev = None
    for q in qs:
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q
    for i in range(4):
        ac.write(obj, "rotation_quaternion", i, frames, [q[i] for q in qs])


def _animate_floater_fish(ns, sfps):
    far = math.hypot(ns.x, ns.y) > 32
    step = 6 if far else 2
    frames = list(range(ns.start, ns.end + 1, step))
    if frames[-1] != ns.end:
        frames.append(ns.end)
    if ns.rise:
        frames = sorted(set(frames) | set(range(max(ns.start, ns.rise[0] - 2), min(ns.end, ns.rise[0] + ns.rise[1] + 40) + 1, 2)))
    float_z = 0.012 if ns.kind == "foam" else 0.02 * ns.length / 0.45
    locs, qs = [], []
    for f in frames:
        t = f / sfps
        el = (f - ns.start) / ns.fps
        x, y = ns.x + ns.drift[0] * el, ns.y + ns.drift[1] * el
        z = WATER_Z + wave_height(x, y, t) + float_z
        roll, pitch = ns.roll, 0.0
        if ns.rise:
            f0, d = ns.rise
            if f < f0:
                z, roll = WATER_Z - 0.5, 0.0
            elif f < f0 + d:
                u = (f - f0) / d
                z = WATER_Z - 0.5 + (z - WATER_Z + 0.5) * (1 - (1 - u) ** 3)
                roll = ns.roll * _smooth(u)
            elif ns.twitch and f < f0 + d + 36:          # last spasms: two shakes that die out
                u = (f - f0 - d) / 36
                roll += math.radians(22) * math.sin(math.tau * 3.2 * u) * (1 - u)
                pitch = math.radians(10) * math.sin(math.tau * 3.2 * u + 1) * (1 - u)
        if ns.kind != "foam":
            roll += math.radians(4) * math.sin(t * 0.9 + ns.seed)
        locs.append(Vector((x, y, z)))
        qs.append(_surface_quat(x, y, t, ns.yaw + 0.05 * math.sin(t * 0.4 + ns.seed), roll, pitch))
    ac.write_vec(ns.obj, "location", frames, locs)
    _write_quats(ns.obj, frames, qs)
    if ns.rise:                                          # hidden (scale 0) while on the bottom
        sx = tuple(ns.obj.scale)
        for i in range(3):
            ac.write(ns.obj, "scale", i, [ns.start, ns.rise[0]], [0.0, sx[i]], ac.CONSTANT)


def _animate_live_fish(ns, sfps):
    frames = list(range(ns.start, ns.end + 1))
    speed = 0.7
    w = ns.dirn * speed / ns.R
    jf = ns.start + int(ns.jump * ns.fps) if ns.jump is not None else None
    jd = int(0.75 * ns.fps)
    locs, qs = [], []
    for f in frames:
        t = f / sfps
        el = (f - ns.start) / ns.fps
        a = ns.seed + w * el
        x, y = ns.x + ns.R * math.cos(a) * 1.4, ns.y + ns.R * math.sin(a)
        vx, vy = -1.4 * math.sin(a) * w, math.cos(a) * w
        yaw = math.atan2(vy, vx) + math.radians(12) * math.sin(math.tau * 2.6 * el)
        z = WATER_Z + wave_height(x, y, t) - 0.035 * ns.length / 0.4
        pitch = 0.0
        if jf is not None and jf <= f <= jf + jd:
            u = (f - jf) / jd
            z += 0.55 * 4 * u * (1 - u) + 0.04
            pitch = -math.atan(0.55 * 4 * (1 - 2 * u) / (speed * 1.8 * 0.75))    # o nariz segue o arco
        locs.append(Vector((x, y, z)))
        qs.append(_surface_quat(x, y, t, yaw, 0.0, pitch))
    ac.write_vec(ns.obj, "location", frames, locs)
    _write_quats(ns.obj, frames, qs)
    if jf is not None and jf + jd < ns.end:
        for sp, fr in zip(ns.splash, (jf, jf + jd)):
            p = locs[fr - ns.start]
            _key_splash(sp, Vector((p.x, p.y, WATER_Z)), fr, ns.fps, ns.rng)


def _finish_fish():
    sfps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base   # GN time is the scene's
    for ns in FISH:
        if ns.kind == "live":
            _animate_live_fish(ns, sfps)
        else:
            _animate_floater_fish(ns, sfps)


# ---------- 'ocean' stage ----------

WAVES = [  # (kx, ky, omega rad/s, amplitude m, radius where it fades m): long swell, medium and ripple
    (0.045, 0.205, 1.43, 0.080, 320.0), (-0.42, 0.56, 2.62, 0.045, 70.0), (0.98, 1.0, 3.7, 0.026, 26.0),
    (-1.25, 0.55, 3.75, 0.016, 18.0)]


CALM = []                        # (x, y) of the moored boats: the pier shelters, waves fall to 20% next to the hull
CALM_R = (2.4, 6.4, 0.2)         # inner radius, outer (m) and minimum factor


def _calm(x, y):
    f = 1.0
    for cx, cy in CALM:
        d = math.hypot(x - cx, y - cy)
        u = max(0.0, min(1.0, (d - CALM_R[0]) / (CALM_R[1] - CALM_R[0])))
        f = min(f, CALM_R[2] + (1 - CALM_R[2]) * u)
    return f


def wave_height(x, y, t):
    """Wave height (m, above WATER_Z) at the point and time t (s): the same math as the Geometry Nodes 'OceanWaves'
    (the fishing float rises and falls with it, without sinking at the crest)."""
    r = math.hypot(x, y)
    z = sum(math.sin(kx * x + ky * y + w * t) * amp * max(1 - r / fade, 0.0) for kx, ky, w, amp, fade in WAVES)
    return z * _calm(x, y)


def _waves_group():
    ng = bpy.data.node_groups.new("OceanWaves", "GeometryNodeTree")
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
    for kx, ky, w, amp, fade in WAVES:
        ph = m("ADD", m("ADD", m("MULTIPLY", sep.outputs["X"], kx), m("MULTIPLY", sep.outputs["Y"], ky)),
               m("MULTIPLY", tm.outputs["Seconds"], w))
        fall = m("MAXIMUM", m("SUBTRACT", 1.0, m("DIVIDE", ln.outputs["Value"], fade)), 0.0)
        term = m("MULTIPLY", m("MULTIPLY", m("SINE", ph), amp), fall)
        total = term if total is None else m("ADD", total, term)
    for cx, cy in CALM:                                    # shelter next to the moored boat
        dv = N.new("ShaderNodeVectorMath")
        dv.operation = "DISTANCE"
        L.new(pos.outputs[0], dv.inputs[0])
        dv.inputs[1].default_value = (cx, cy, 0.0)
        u = m("MINIMUM", m("MAXIMUM", m("DIVIDE", m("SUBTRACT", dv.outputs["Value"], CALM_R[0]), CALM_R[1] - CALM_R[0]),
                                    0.0), 1.0)
        total = m("MULTIPLY", total, m("ADD", m("MULTIPLY", u, 1 - CALM_R[2]), CALM_R[2]))
    still = N.new("ShaderNodeValue")                       # 1 = open sea; 0 = frozen bay (falls at the ice cut)
    still.name = "WaveScale"
    still.outputs[0].default_value = 1.0
    total = m("MULTIPLY", total, still.outputs[0])
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(total, comb.inputs["Z"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs[0], sp.inputs["Geometry"])
    L.new(comb.outputs[0], sp.inputs["Offset"])
    L.new(sp.outputs[0], go.inputs[0])
    return ng


def build_water(coll, color, rng, radius=1700.0, n=220):
    """Faceted sea out to the horizon: triangulated grid denser near the camera (0.5 m) and wide far away (18 m),
    vertices with a slight offset (irregular facets). Waves by scene time, fading with distance."""
    a = 0.97
    verts, faces = [], []
    step = []
    for i in range(n + 1):
        u = i / n * 2 - 1
        step.append(radius * (a * u ** 3 + (1 - a) * u))
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = step[i], step[j]
            dx = (step[min(i + 1, n)] - step[max(i - 1, 0)]) / 2
            dy = (step[min(j + 1, n)] - step[max(j - 1, 0)]) / 2
            if 0 < i < n and 0 < j < n:
                x += rng.uniform(-0.28, 0.28) * dx
                y += rng.uniform(-0.28, 0.28) * dy
            verts.append((x, y, 0.0))
    for j in range(n):
        for i in range(n):
            p = j * (n + 1) + i
            q = p + n + 1
            if (i + j) % 2:
                faces += [(p, p + 1, q + 1), (p, q + 1, q)]
            else:
                faces += [(p, p + 1, q), (p + 1, q + 1, q)]
    water = kit.flat("ocean_water", color, rough=0.3)
    p = kit.principled(water)
    p.inputs["Specular IOR Level"].default_value = 0.35
    sea_group(color).nodes["Sea"].outputs[0].default_value = kit.lin(color)
    g = water.node_tree.nodes.new("ShaderNodeGroup")
    g.node_tree = sea_group()
    water.node_tree.links.new(g.outputs[0], p.inputs["Base Color"])
    _boat_mask(water, [fl.obj for fl in FLOATERS if getattr(fl, "moored", False)])
    CALM[:] = [(fl.foot[0], fl.foot[1]) for fl in FLOATERS if getattr(fl, "moored", False)]
    o = _mesh("ocean", [(verts, faces, 0)], [water], coll, (0, 0, WATER_Z), recalc=False)
    mod = o.modifiers.new("Waves", "NODES")
    mod.node_group = _waves_group()
    if ICE_FROM:                     # under the ice the water does not ripple (the crest covered the plates: dark patches)
        f0 = min(ICE_FROM)
        ac.write(mod.node_group, 'nodes["WaveScale"].outputs[0].default_value', 0, [f0 - 1, f0], [1.0, 0.0])
    o.visible_shadow = False
    return o, water


def _boat_mask(water, boats):
    """Alpha 0 of the water inside the hull of each moored boat (boat's own coordinates: follows the sway).
    Shape: ellipse at the bow, almost rectangular at the stern (exponent 5), slightly inside the hull's waterline."""
    nt = water.node_tree
    N, L = nt.nodes, nt.links

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
    alpha, contact = None, None
    for boat in boats:
        tc = N.new("ShaderNodeTexCoord")
        tc.object = boat
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(tc.outputs["Object"], sep.inputs[0])
        x, y = sep.outputs["X"], sep.outputs["Y"]
        p = m("ADD", m("MULTIPLY", m("LESS_THAN", x, 0.0), 3.0), 2.0)
        ex = m("POWER", m("DIVIDE", m("ABSOLUTE", x), 1.97), p)
        ey = m("POWER", m("DIVIDE", m("ABSOLUTE", y), 0.68), 2.0)
        e = m("ADD", ex, ey)
        keep = m("GREATER_THAN", e, 1.0)
        alpha = keep if alpha is None else m("MULTIPLY", alpha, keep)
        if contact is None:          # hull contact: darker water around and a thread of foam stuck to it
            contact = (m("MINIMUM", m("MAXIMUM", m("DIVIDE", m("SUBTRACT", 1.55, e), 0.4), 0.0), 1.0),
                       m("MINIMUM", m("MAXIMUM", m("DIVIDE", m("SUBTRACT", 1.24, e), 0.08), 0.0), 1.0))
    if contact is not None:
        p = kit.principled(water)
        base = next(l.from_socket for l in L if l.to_socket == p.inputs["Base Color"])
        dark = N.new("ShaderNodeMix")
        dark.data_type = "RGBA"
        dark.blend_type = "MULTIPLY"
        L.new(m("MULTIPLY", contact[0], 0.55), dark.inputs[0])
        L.new(base, dark.inputs[6])
        dark.inputs[7].default_value = (0.35, 0.42, 0.48, 1.0)
        foam = N.new("ShaderNodeMix")
        foam.data_type = "RGBA"
        L.new(m("MULTIPLY", contact[1], 0.0), foam.inputs[0])          # foam thread turned off: it read as salt
        L.new(dark.outputs[2], foam.inputs[6])
        foam.inputs[7].default_value = (0.82, 0.86, 0.87, 1.0)
        L.new(foam.outputs[2], p.inputs["Base Color"])
    if alpha is not None:
        L.new(alpha, kit.principled(water).inputs["Alpha"])
        water.surface_render_method = "DITHERED"


def build_pier(coll, rng):
    """Wooden pier from the beach to 5 m in front of the camera: 24 cm boards in 3 tones (no gap: nothing thin that would
    shimmer), stringers, crossbeams and posts every 3 m; three posts extend past the top (mooring)."""
    x0, x1, y0, y1 = PIER
    tones = [mat("plank_a", "#8A6A48", 0.9), mat("plank_b", "#7B5E40", 0.9), mat("plank_c", "#967553", 0.9),
             mat("beam", "#5A4632", 0.95), mat("post", "#4E3D2C", 0.95)]
    planks = []
    y = y1
    while y > y0:
        ya = max(y0, y - 0.24)
        e0, e1 = rng.uniform(-0.035, 0.0), rng.uniform(0.0, 0.035)
        planks.append((*_box(x0 + e0, x1 + e1, ya, y, -0.07, rng.uniform(-0.004, 0.004)), rng.randrange(3)))
        y = ya
    _mesh("pier_deck", planks, tones, coll)
    beams = []
    for bx in (x0 + 0.15, (x0 + x1) / 2, x1 - 0.15):
        beams.append((*_box(bx - 0.08, bx + 0.08, y0, y1 - 0.05, -0.3, -0.065), 3))
    posts = []
    yy = y1 - 0.2
    while yy > y0:
        if terrain_height(0.0, yy) < -0.1:
            beams.append((*_box(x0 - 0.05, x1 + 0.05, yy - 0.09, yy + 0.09, -0.42, -0.29), 3))
            for px in (x0 + 0.1, x1 - 0.1):
                top = -0.06
                for q in pier_posts():
                    if abs(q.x - px) < 0.01 and abs(q.y - yy) < 0.01:
                        top = q.z
                posts.append((*_cyl(8, 0.14, 0.13, terrain_height(px, yy) - 0.3, top, px, yy, 0.2), 4))
        yy -= POST_ROWS
    _mesh("pier_frame", beams + posts, tones, coll)
    bulb = kit.flat("lamp_glass", "#FFE2A8", rough=0.4, emission="#FFC46B", strength=0.0)
    metal = mat("lamp_metal", "#2C3036", 0.6)
    for k, ly in enumerate((-1.5, -13.5, -25.5)):
        lx = x0 + 0.1
        parts = [(*_box(lx - 0.05, lx + 0.05, ly - 0.05, ly + 0.05, 0.0, 2.5), 0),
                 (*_box(lx - 0.04, lx + 0.42, ly - 0.03, ly + 0.03, 2.42, 2.48), 0),
                 (*_box(lx + 0.28, lx + 0.48, ly - 0.1, ly + 0.1, 2.40, 2.43), 0),
                 (*_box(lx + 0.31, lx + 0.45, ly - 0.07, ly + 0.07, 2.18, 2.40), 1)]
        _mesh(f"pier_lamp{k}", parts, [metal, bulb], coll)
        light = bpy.data.objects.new(f"pier_lamp{k}_light", bpy.data.lights.new(f"pier_lamp{k}_light", "POINT"))
        light.data.color = kit.lin("#FFC46B")[:3]
        light.data.shadow_soft_size = 0.15
        light.data.energy = 0.0
        light.data.use_shadow = k == 0
        light.location = (lx + 0.38, ly, 2.12)
        coll.objects.link(light)
        LAMPS.append(SimpleNamespace(light=light, bulb=bulb, power=220.0 if k == 0 else 160.0))


def build_islands(coll, rng, count=6):
    """Low islands on the horizon (layers in the back, no city): faceted mounds of 20 to 70 m at 450-1100 m."""
    rock, green = mat("island_rock", "#7A776C", 1.0, 0.0), mat("island_green", "#5E7656", 1.0, 0.0)
    for k in range(count):
        a = math.radians(rng.uniform(22, 158))
        if abs(math.degrees(a) - 90) < 10:
            a += math.radians(14) * (1 if a > math.pi / 2 else -1)
        r = rng.uniform(450, 1100)
        cx, cy = r * math.cos(a), r * math.sin(a)
        R, H = rng.uniform(60, 190), rng.uniform(18, 70)
        n = 11
        rings = [(0.0, H), (0.3, 0.86 * H), (0.62, 0.5 * H), (0.9, 0.14 * H), (1.08, -4.0)]
        v = [(cx, cy, WATER_Z + H + rng.uniform(-3, 3))]
        for rr, hh in rings[1:]:
            for i in range(n):
                ang = math.tau * i / n + rng.uniform(-0.12, 0.12)
                v.append((cx + R * rr * math.cos(ang) * rng.uniform(0.85, 1.15) * 1.4,
                          cy + R * rr * math.sin(ang) * rng.uniform(0.85, 1.15), WATER_Z + hh * rng.uniform(0.8, 1.15)))
        f, mi = [], []
        for i in range(n):
            f.append((0, 1 + i, 1 + (i + 1) % n))
            mi.append(1)
        for ri in range(len(rings) - 2):
            a0, b0 = 1 + ri * n, 1 + (ri + 1) * n
            for i in range(n):
                f.append((a0 + i, b0 + i, b0 + (i + 1) % n, a0 + (i + 1) % n))
                mi.append(1 if ri < 1 else 0)
        o = _mesh(f"island{k}", [(v, f, mi)], [rock, green], coll)
        o.visible_shadow = False


def build_buoys(coll, rng, start, end):
    red, white = mat("buoy_red", "#C8432F", 0.7), mat("buoy_white", "#EDEBE4", 0.7)
    for k, (x, y) in enumerate(((-9.0, 24.0), (14.0, 38.0), (-22.0, 55.0))):
        parts = [(*_cyl(8, 0.32, 0.26, -0.25, 0.25), 1), (*_cyl(8, 0.18, 0.02, 0.25, 0.95), 0)]
        o = _mesh(f"buoy{k}", parts, [red, white], coll, (x, y, WATER_Z))
        FLOATERS.append(SimpleNamespace(obj=o, start=start, end=end, env=[(start, 1.0)], seed=rng.random() * 10,
                                        heave=0.06, roll=6.0, pitch=5.0, period=3.4, foot=(x, y, 0.35, 0.35, 0.0)))


def build_ocean(coll, sdef, rng, start, end):
    """Fixed pieces of the 'ocean' stage. Returns the sea color node group (the 'water' cue animates the RGB 'Sea')."""
    _o, _water = build_water(coll, sdef["water"], rng)
    build_pier(coll, rng)
    build_islands(coll, rng)
    build_buoys(coll, rng, start, end)
    for k, (x, y, hd) in enumerate(((-140.0, 210.0, 0.4), (190.0, 330.0, 2.2))):
        spawn_boat(f"farboat{k}", coll, {"len": 5.0}, x, y, hd, start, end, 30, rng, ropes=False)
    return sea_group()


SPAWN = {"boat": spawn_boat, "gull": spawn_gull, "ice": spawn_ice, "fish_dead": spawn_fish_dead,
         "fish_live": spawn_fish_live, "foam": spawn_foam}
import ant  # noqa: E402  (formiga e formigueiro: tools/stage/ant.py)

SPAWN["anthill"] = ant.spawn_anthill
SPAWN["antnest"] = ant.spawn_antnest
import park  # noqa: E402  (park stage and picnic pieces: tools/stage/park.py)

SPAWN.update({"blanket": park.spawn_blanket, "basket": park.spawn_basket, "cooler": park.spawn_cooler,
              "bench": park.spawn_bench, "turf": park.spawn_turf, "crumbs": park.spawn_crumbs})
import riverside  # noqa: E402  (riverside stage: sway)

SPAWN["scale"] = riverside.spawn_scale
DEFAULT_FACE = {"boat": 90.0}


def has(ident):
    return ident in SPAWN
