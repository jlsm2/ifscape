"""Animals of pangaea-never-split: brachiosaurus (raised-neck sauropod) and a small mammal.

Proportions of Giraffatitan/Brachiosaurus (~22 m long, shoulder ~5.8 m, head ~12 m above the ground,
front legs longer than the hind ones, short tail for a sauropod). Front along +x, feet at z = 0.
Moving parts (neck, legs, tail) are objects with the pivot at the joint, children of a root.
"""

import math
from types import SimpleNamespace

import bpy

import kit

# (x, half-width, top, bottom) of the trunk, from rump to withers
TRUNK = [(-3.7, 0.55, 5.1, 3.9), (-3.0, 1.05, 5.5, 3.2), (-1.8, 1.45, 5.8, 2.8), (-0.2, 1.55, 6.1, 2.7),
         (1.4, 1.45, 6.5, 2.9), (2.6, 1.2, 6.8, 3.4), (3.3, 0.8, 6.8, 4.3)]
NECK = [(3.0, 0, 6.3), (3.9, 0, 7.9), (4.7, 0, 9.4), (5.3, 0, 10.7), (5.7, 0, 11.8), (5.95, 0, 12.5)]
NECK_R = [0.85, 0.6, 0.47, 0.38, 0.32, 0.3]
TAIL = [(-3.5, 0, 4.8), (-5.2, 0, 4.4), (-7.0, 0, 3.8), (-8.8, 0, 3.0), (-10.4, 0, 2.3)]
TAIL_R = [0.78, 0.58, 0.36, 0.18, 0.05]
LEGS = {"FL": (2.3, 0.95, 4.4, 0.42), "FR": (2.3, -0.95, 4.4, 0.42),     # x, y, pivot height, radius
        "HL": (-2.3, 1.0, 4.0, 0.52), "HR": (-2.3, -1.0, 4.0, 0.52)}
SKIN = "#7C8F62"
BELLY = "#A9B48C"
MAMMAL = "#6B4E3A"


def _ellipse_ring(x, hw, top, bot, n=10):
    cz, hz = (top + bot) / 2, (top - bot) / 2
    return [(x, hw * math.cos(2 * math.pi * i / n), cz + hz * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _tube_xz(points, radii, n=8, squash=1.0):
    """Tube through points in the xz plane with the ring locked to the y axis (no twist, unlike tube_geo)."""
    from mathutils import Vector
    pts = [Vector(p) for p in points]
    side = Vector((0, 1, 0))
    rings = []
    for k, (p, r) in enumerate(zip(pts, radii)):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        up = t.cross(side).normalized()
        rings.append([tuple(p + side * (r * squash * math.cos(a)) + up * (r * math.sin(a))) for a in _angles(n)])
    return kit.loft_geo(rings)


def _part(name, geo, mats, parent, pivot=(0, 0, 0), face_mats=None):
    """Child object with the origin at the pivot (geometry comes in the animal's coordinates)."""
    v = [(x - pivot[0], y - pivot[1], z - pivot[2]) for x, y, z in geo[0]]
    obj = kit.mesh_object(name, v, geo[1], mats, location=pivot, face_mats=face_mats)
    obj.parent = parent
    kit.fix_normals(obj)
    return obj


def _materials(tint):
    skin = kit.flat(f"Sauro{tint}", tint, rough=0.95)
    belly = kit.flat(f"SauroBelly{tint}", BELLY, rough=0.95)
    eye = kit.flat("SauroEye", "#11151C", rough=0.4)
    return skin, belly, eye


def sauropod(name, location, heading=0.0, scale=1.0, tint=SKIN):
    root = bpy.data.objects.new(name, None)
    root.location, root.rotation_euler, root.scale = location, (0, 0, heading), (scale,) * 3
    bpy.context.collection.objects.link(root)
    skin, belly, eye = _materials(tint)

    rings = [_ellipse_ring(*s) for s in TRUNK]
    trunk = kit.loft_geo(rings)
    tail = _tube_xz(TAIL, TAIL_R, n=8, squash=0.85)
    v, f, owner = kit.merge(trunk, tail)
    mats = [1 if all(v[i][2] < 3.6 for i in face) else 0 for face in f]       # lighter belly
    body = _part(f"{name}Body", (v, f), [skin, belly], root, face_mats=mats)

    neck_geo = _tube_xz(NECK, NECK_R, n=8, squash=0.8)
    hx, hz = NECK[-1][0], NECK[-1][2]
    head = kit.loft_geo([[(hx - 0.25, 0.3 * math.cos(a), hz + 0.32 * math.sin(a)) for a in _angles(8)],
                         [(hx + 0.25, 0.27 * math.cos(a), hz + 0.12 + 0.38 * math.sin(a)) for a in _angles(8)],
                         [(hx + 0.75, 0.2 * math.cos(a), hz - 0.05 + 0.2 * math.sin(a)) for a in _angles(8)],
                         [(hx + 1.0, 0.12 * math.cos(a), hz - 0.08 + 0.12 * math.sin(a)) for a in _angles(8)]])
    eyes = [kit._gem_geo(0.07, oz=hz + 0.2, ox=hx + 0.35, oy=s * 0.27) for s in (1, -1)]
    nv, nf, nowner = kit.merge(neck_geo, head, *eyes)
    neck = _part(f"{name}Neck", (nv, nf), [skin, eye], root, pivot=NECK[0],
                 face_mats=[1 if o >= 2 else 0 for o in nowner])

    legs = {}
    for leg, (x, y, top, r) in LEGS.items():
        bend = 0.18 if leg[0] == "F" else -0.22                     # elbow backward, knee forward
        pts = [(x, y, top), (x - bend * 0.3, y, top * 0.72), (x + bend, y, top * 0.42), (x + 0.02, y, 0.32),
               (x + 0.12, y, 0.0)]
        tube = _tube_xz(pts, [r * 1.45, r * 1.15, r * 0.95, r * 0.85, r * 1.2], n=8)
        pad = kit._prism_geo(8, r * 1.4, r * 1.25, 0.22, ox=x + 0.14, oy=y)      # shoe: the ground contact
        pv, pf, _ = kit.merge(tube, pad)
        geo = (pv, pf)
        legs[leg] = _part(f"{name}{leg}", geo, [skin], root, pivot=(x, y, top))
    return SimpleNamespace(root=root, body=body, neck=neck, legs=legs, scale=scale)


def _angles(n):
    return [2 * math.pi * i / n for i in range(n)]


DUTY = 0.65          # fraction of the cycle with the foot on the ground (slow sauropod step)


def _foot_offset(u, reach):
    """Foot position ahead of the pivot (m) and how much it lifts, at cycle fraction u. In stance the foot moves back
    at constant speed, equal to the body's: it stays still on the ground. In swing it lifts and returns to the front."""
    if u < DUTY:
        return reach - 2 * reach * u / DUTY, 0.0
    v = (u - DUTY) / (1 - DUTY)
    e = v * v * (3 - 2 * v)
    return -reach + 2 * reach * e, math.sin(math.pi * v)


def walk(s, f0, f1, speed, stride_s=1.8, fps=30):
    """Diagonal gait (FL with HR, FR with HL) with the foot planted: the leg angle comes from the foot position
    (asin), so the foot does not slide; in swing the leg shortens a little (scale in length) and the foot
    lifts ~25 cm. Keys every 2 frames, LINEAR. Body walking 'speed' m/s along local +x."""
    import mathutils
    start = s.root.location.copy()
    fwd = mathutils.Vector((math.cos(s.root.rotation_euler.z), math.sin(s.root.rotation_euler.z), 0))
    reach = speed * stride_s * DUTY / 2 / s.scale        # in animal units (the root has a scale)
    for f in range(f0, f1 + 1, 2):
        t = (f - f0) / fps
        for leg, o in (("FL", 0.0), ("HR", 0.0), ("FR", 0.5), ("HL", 0.5)):
            top = LEGS[leg][2]
            u = (t / stride_s + o) % 1.0
            x, lift = _foot_offset(u, reach)
            theta = -math.asin(max(-0.9, min(0.9, x / top)))
            kit.key(s.legs[leg], "rotation_euler", (0, theta, 0), f)
            kit.key(s.legs[leg], "scale", (1, 1, 1 - 0.25 * lift / top), f)
        kit.key(s.root, "location", start + fwd * speed * t, f)
        kit.key(s.body, "location", (0, 0, 0.05 * math.cos(4 * math.pi * t / stride_s)), f)
    for obj in (s.root, s.body, *s.legs.values()):
        for fc in _fcurves(obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def _fcurves(obj):
    import globe
    return globe._fcurves(obj)


def collapse(s, f0, f1, dust_mat=None):
    """Fall in stages, from f0 to f1 (the impact lands at ~80%):
    0–30% the legs give way and the body sinks; 30–80% topples sideways accelerating (gravity); 80–92% hits and
    bounces slightly; the neck collapses late and hits after the body. Kicks up dust on impact.
    Returns the dust objects (to show only in the scene)."""
    from mathutils import Vector
    sc = s.scale
    d = f1 - f0

    def at(u):
        return int(round(f0 + d * u))

    loc = s.root.location.copy()
    rx, ry, rz = s.root.rotation_euler
    for leg in s.legs.values():
        for u, k in ((0.0, 1.0), (0.3, 0.55), (0.8, 0.5)):
            kit.key(leg, "scale", (1, 1, k), at(u))
    roll = ((0.0, 0), (0.3, 4), (0.45, 14), (0.6, 34), (0.72, 62), (0.8, 88), (0.85, 72), (0.91, 84), (1.0, 80))
    sink = ((0.0, 0), (0.3, -1.9), (0.6, -1.0), (0.8, 0.5), (0.85, 1.1), (0.91, 0.55), (1.0, 0.6))
    for (u, a), (_, z) in zip(roll, sink):
        kit.key(s.root, "rotation_euler", (math.radians(a), ry, rz), at(u))
        kit.key(s.root, "location", (loc.x, loc.y, loc.z + z * sc), at(u))
    pitch = ((0.0, -12), (0.5, -12), (0.78, 30), (0.9, 52), (0.95, 46), (1.0, 48))
    for u, a in pitch:
        kit.key(s.neck, "rotation_euler", (0, math.radians(a), math.radians(25)), at(u))
    side = Vector((math.sin(rz), -math.cos(rz), 0))                  # where the body falls (local -y)
    hit = loc + side * 4.4 * sc
    puffs = []
    if dust_mat is not None:
        import random
        rnd = random.Random(int(loc.x * 7 + loc.y))
        fwd = Vector((math.cos(rz), math.sin(rz), 0))
        for k in range(9):
            p = hit + fwd * rnd.uniform(-9, 9) * sc + side * rnd.uniform(-1.5, 2.5) * sc
            v, fc = kit._ico_geo(1.0, (0, 0, 0))
            o = kit.mesh_object(f"{s.root.name}Dust{k}", v, fc, [dust_mat], location=(p.x, p.y, loc.z + 0.4))
            r = rnd.uniform(0.6, 1.1) * sc
            t0 = at(0.8) + rnd.randint(0, 3)
            kit.key(o, "scale", (0, 0, 0), 1)
            kit.key(o, "scale", (0, 0, 0), t0 - 1)
            kit.key(o, "scale", (r, r, r * 0.6), t0 + 6)
            kit.key(o, "scale", (r * 2.2, r * 2.2, r * 1.3), t0 + 35)
            kit.key(o, "scale", (0, 0, 0), t0 + 75)                     # the dust dissipates
            kit.key(o, "location", (p.x, p.y, loc.z + 0.4), t0)
            kit.key(o, "location", (p.x, p.y, loc.z + 1.6 * sc), t0 + 40)
            puffs.append(o)
    return puffs


def topple(s, f0, f1):
    """Topples sideways (rotates 82° around the body axis) and settles on the ground: the fall of the giants."""
    rx = s.root.rotation_euler
    kit.key(s.root, "rotation_euler", tuple(rx), f0)
    kit.key(s.root, "rotation_euler", (math.radians(82), rx.y, rx.z), f1)
    z = s.root.location.z
    kit.key(s.root, "location", tuple(s.root.location), f0)
    s.root.location.z = z + 0.4 * s.scale
    kit.key(s.root, "location", tuple(s.root.location), f1)


def neck_pose(s, pitch_deg, frame, yaw_deg=0.0):
    """Neck tilts forward (pitch > 0 lowers the head) or turns sideways (yaw)."""
    kit.key(s.neck, "rotation_euler", (0, math.radians(pitch_deg), math.radians(yaw_deg)), frame)


def mammal(name, location, heading=0.0, scale=1.0):
    """Small Mesozoic mammal (shrew type): ~25 cm, thin snout, round ears, long tail."""
    mat = kit.flat(f"Mammal{name}", MAMMAL, rough=0.95)
    dark = kit.flat("MammalDark", "#2A1E16", rough=0.6)
    body = kit.loft_geo([[(x, hw * math.cos(a), cz + hz * math.sin(a)) for a in _angles(8)]
                         for x, hw, cz, hz in ((-0.11, 0.025, 0.055, 0.025), (-0.06, 0.05, 0.065, 0.045),
                                               (0.03, 0.048, 0.07, 0.042), (0.09, 0.035, 0.075, 0.032),
                                               (0.14, 0.012, 0.07, 0.012))])
    tail = _tube_xz([(-0.1, 0, 0.055), (-0.2, 0, 0.04), (-0.3, 0, 0.03)], [0.012, 0.008, 0.003], n=5)
    ears = [kit._ico_geo(0.018, (0.085, s * 0.025, 0.105), (0.4, 1, 1)) for s in (1, -1)]
    eyes = [kit._gem_geo(0.007, oz=0.085, ox=0.11, oy=s * 0.018) for s in (1, -1)]
    v, f, owner = kit.merge(body, tail, *ears, *eyes)
    obj = kit.mesh_object(name, v, f, [mat, dark], location=location, face_mats=[1 if o >= 4 else 0 for o in owner])
    obj.rotation_euler, obj.scale = (0, 0, heading), (scale,) * 3
    kit.fix_normals(obj)
    # Articulated legs (pivot at shoulder/hip): without them the animal slid like a single rigid piece (audit).
    names = []
    for k, (x, y) in enumerate(((0.06, 0.03), (0.06, -0.03), (-0.06, 0.03), (-0.06, -0.03))):
        leg = _part(f"{name}Leg{k}", kit._prism_geo(5, 0.012, 0.008, 0.05, ox=x, oy=y, oz=-0.01), [mat], obj,
                    pivot=(x, y, 0.045))
        names.append(leg.name)
    obj["legs"] = ",".join(names)                 # Blender property: text (a list becomes an array without append)
    return obj


def scurry(obj, points, f0, f1, hop=0.03):
    """Hops along a list of points (x, y, z), turning toward the direction of movement."""
    from mathutils import Vector
    pts = [Vector(p) for p in points]
    n = len(pts) - 1
    kit.key(obj, "location", tuple(pts[0]), 1)
    for f in range(f0, f1 + 1, 2):
        u = (f - f0) / max(f1 - f0, 1) * n
        k = min(int(u), n - 1)
        p = pts[k].lerp(pts[k + 1], u - k)
        p.z += hop * abs(math.sin((f - f0) * math.pi / 6))          # smooth hop (alternating every 2 frames jittered)
        d = pts[k + 1] - pts[k]
        kit.key(obj, "location", tuple(p), f)
        kit.key(obj, "rotation_euler", (0, 0, math.atan2(d.y, d.x)), f)
        for k, leg in enumerate(n for n in obj.get("legs", "").split(",") if n):                   # gallop: diagonal pairs alternating
            swing = math.radians(40) * math.sin((f - f0) * math.pi / 3 + (math.pi if k in (1, 2) else 0))
            kit.key(bpy.data.objects[leg], "rotation_euler", (0, swing, 0), f)
