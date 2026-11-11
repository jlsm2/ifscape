"""Ant ('ant', with its own skeleton and actions) and anthill ('anthill') made in code for the data-driven stage.

Written for ants-human-size: there is no CC0 rigged ant in assets/.

Proportions (Camponotus worker, the "textbook" ant): Shattuck 2005, Camponotus densopilus, minor worker
(https://treatment.plazi.org/id/7882910D-FB89-A9D3-0E76-49AC5BFD5741): head 1.7 to 2.1 mm long and
1.6 to 1.9 mm wide, mesosoma 2.9 to 3.0 mm, middle tibia 2.0 to 2.2 mm; with the petiole (~0.5 mm) and gaster
(~3.5 mm), the body comes to ~9 mm. In fractions of the body (L = 1, from the front of the head to the end of the gaster): head 0.22
(width 0.21), mesosoma 0.32 (width 0.14), petiole 0.07, gaster 0.41 (width 0.27); front leg 0.66,
middle 0.73, back 0.91 (femur + tibia + tarsus); antenna scape 0.21 (extends past the head) and funiculus 0.25.
Thickness (the point of the video: legs too thin for the body): femur 0.035 in diameter, tibia 0.024, tarsus 0.013.
Style: faceted, flat, 5 colors (like the Quaternius low-poly animals).

The template is registered in rigs._templates['ant'] (mesh and armature shared by the copies; the actions too):
models.rig_spawn treats the ant like any animal with a skeleton (step calibrated by the planted foot, Idle with a
random phase, 'grow' and 'action' cues). The armature sits on the ground (z = 0) and the 'Body' bone goes up and down: the foot
tips ('Foot.*', leaves) stay still on the support, which is what rigs.planted_speed measures.

Actions (24 f/s, like the Quaternius ones): Idle (2 s loop: antennae, gaster breathing), Walk (tripod gait,
0.48 L/s), Run (1.56 L/s, for the small ant), Rise (4 s: from normal standing to raised, legs stretching, front
raised), Tremble (1 s, only after Rise), Sag (3.83 s, too much weight: legs tremble and give way 25% in 1.5 s, the
left side first; body falls in 0.7 s with the feet sliding outward; gaster rebound; legs settle; starts from the
raised pose; if the ant did not rise, plays 'SagStand', which starts from the normal pose), SagIdle (3 s loop lying down:
antennae slow, gaster breathing; chains at the end of Sag or serves as the 'action' of an already-lying prop). Rise,
Tremble and Sag play once and hold the final pose (rig.t.once; build.py calls play()).
"""

import math
import random
from types import SimpleNamespace

import bpy
import bmesh
import bpy_extras.anim_utils as au
from mathutils import Matrix, Quaternion, Vector

import kit
import rigs

KEY = "ant"
FPS = rigs.ASSET_FPS
H0 = 0.17                          # height of the mesosoma center (Body bone) standing, in L
H_RISE = 0.41                      # erguida
H_SAG = 0.085                      # fallen (belly on the ground; measured on the posed mesh)
BODY0 = Vector((0.0, -0.13, H0))
NECK = Vector((0.0, -0.285, H0 + 0.01))
WAIST = Vector((0.0, 0.006, H0 - 0.004))
SOCKET = Vector((0.032, -0.462, H0 + 0.032))      # left antenna socket (x > 0 is the ant's left side)
SCAPE, FLAG = 0.21, 0.25
# legs: coxa on the body (x, y, z relative to H0), foot tip still (x, y), (femur, tibia, tarsus)
LEG_DEF = {
    "1": (Vector((0.055, -0.235, -0.062)), (0.37, -0.60), (0.24, 0.22, 0.20)),
    "2": (Vector((0.062, -0.125, -0.060)), (0.57, -0.07), (0.26, 0.25, 0.22)),
    "3": (Vector((0.062, -0.045, -0.060)), (0.47, 0.40), (0.31, 0.30, 0.29)),
}
LEGS = [f"{s}{n}" for s in "LR" for n in "123"]
TRIPOD_A = {"L1", "R2", "L3"}
COLORS = {"body": "#57281C", "gaster": "#3E1C15", "band": "#6B3725", "leg": "#7C4632", "eye": "#140E0C",
          "mandible": "#341710"}
ONCE = ("Rise", "Tremble", "Sag", "SagStand", "SagIdle")    # play by play() (SagIdle loops, but without blending)
_state = {}


def _side(leg_or_side):
    return 1.0 if leg_or_side[0] == "L" else -1.0


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _smoother(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


# ---------- pose (parameters) -> bone matrices in armature space ----------

def base_pose():
    feet = {}
    for leg in LEGS:
        _c, tip, _l = LEG_DEF[leg[1]]
        feet[leg] = Vector((_side(leg) * tip[0], tip[1], 0.0))
    return dict(pos=BODY0.copy(), pitch=0.0, roll=0.0, yaw=0.0, nod=0.0, lift=0.0, breath=1.0, feet=feet,
                tarsus=math.radians(40), tars_off={leg: 0.0 for leg in LEGS}, pole=0.3,
                ant={"L": [42.0, 28.0, -18.0, 38.0], "R": [42.0, 28.0, -18.0, 38.0]})


def _copy(p):
    q = dict(p)
    q["pos"] = p["pos"].copy()
    q["feet"] = {k: v.copy() for k, v in p["feet"].items()}
    q["tars_off"] = dict(p["tars_off"])
    q["ant"] = {k: list(v) for k, v in p["ant"].items()}
    return q


def _mix(a, b, t, feet_t=None):
    """Pose between a and b (t from 0 to 1); feet_t: {leg: t} specific to each foot."""
    p = _copy(a)
    p["pos"] = a["pos"].lerp(b["pos"], t)
    for k in ("pitch", "roll", "yaw", "nod", "lift", "breath", "tarsus", "pole"):
        p[k] = a[k] + (b[k] - a[k]) * t
    for leg in LEGS:
        tl = feet_t[leg] if feet_t else t
        p["feet"][leg] = a["feet"][leg].lerp(b["feet"][leg], tl)
        p["tars_off"][leg] = a["tars_off"][leg] + (b["tars_off"][leg] - a["tars_off"][leg]) * tl
    for s in "LR":
        p["ant"][s] = [x + (y - x) * t for x, y in zip(a["ant"][s], b["ant"][s])]
    return p


def _frames(p):
    R = Matrix.Rotation(p["yaw"], 4, "Z") @ Matrix.Rotation(-p["pitch"], 4, "X") @ Matrix.Rotation(p["roll"], 4, "Y")
    F = Matrix.Translation(p["pos"]) @ R @ Matrix.Translation(-BODY0)
    Hm = F @ Matrix.Translation(NECK) @ Matrix.Rotation(p["nod"], 4, "X") @ Matrix.Translation(-NECK)
    Gm = F @ Matrix.Translation(WAIST) @ Matrix.Rotation(p["lift"], 4, "X") @ Matrix.Translation(-WAIST)
    return F, Hm, Gm


def _leg(p, leg, F):
    """Coxa, knee, ankle and foot tip (armature space). Tarsus at the given angle down to the ground; femur and tibia
    by 2-bone IK with the knee up (pole 0) or outward (pole 1)."""
    coxa, _tip, (f, t, ta) = LEG_DEF[leg[1]]
    sx = _side(leg)
    c = F @ Vector((sx * coxa.x, coxa.y, H0 + coxa.z))
    tip = p["feet"][leg]
    a = p["tarsus"] + p["tars_off"][leg]
    h = Vector((tip.x - c.x, tip.y - c.y, 0.0))
    h = h.normalized() if h.length > 1e-6 else Vector((sx, 0.0, 0.0))
    ankle = tip + Vector((-h.x * ta * math.cos(a), -h.y * ta * math.cos(a), ta * math.sin(a)))
    v = ankle - c
    d = max(v.length, 1e-6)
    u = v / d
    pv = Vector((0, 0, 1)).lerp(h, p["pole"]).normalized()
    w = pv - u * pv.dot(u)
    w = w.normalized() if w.length > 1e-6 else h
    if d >= f + t - 1e-5:
        knee, ank = c + u * f, c + u * (f + t)
    else:
        cos_t = max(-1.0, min(1.0, (f * f + d * d - t * t) / (2 * f * d)))
        th = math.acos(cos_t)
        knee, ank = c + f * (math.cos(th) * u + math.sin(th) * w), ankle
    return c, knee, ank, tip


def _adir(el, az, sx):
    el, az = math.radians(el), math.radians(az)
    return Vector((sx * math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def _antenna(p, side, Hm):
    sx = _side(side)
    sc_el, sc_az, fl_el, fl_az = p["ant"][side]
    hq = Hm.to_quaternion()
    s = Hm @ Vector((sx * SOCKET.x, SOCKET.y, SOCKET.z))
    e = s + SCAPE * (hq @ _adir(sc_el, sc_az, sx))
    tip = e + FLAG * (hq @ _adir(fl_el, fl_az, sx))
    return s, e, tip, hq


def joints(p):
    """Points of each bone (head, tail) in the pose: used to build the skeleton in the rest pose."""
    F, Hm, _Gm = _frames(p)
    out = {"Body": (BODY0, BODY0 + Vector((0, -0.1, 0))), "Head": (NECK, NECK + Vector((0, -0.15, -0.02))),
           "Gaster": (WAIST, WAIST + Vector((0, 0.3, -0.03)))}
    for leg in LEGS:
        c, k, a, tip = _leg(p, leg, F)
        out[f"Fem.{leg}"], out[f"Tib.{leg}"], out[f"Tar.{leg}"] = (c, k), (k, a), (a, tip)
        out[f"Foot.{leg}"] = (tip, tip + (tip - a).normalized() * 0.03)
    for s in "LR":
        so, e, tip, _hq = _antenna(p, s, Hm)
        out[f"Scape.{s}"], out[f"Flag.{s}"] = (so, e), (e, tip)
    return out


PARENT = {"Body": None, "Head": "Body", "Gaster": "Body"}
for _l in LEGS:
    PARENT.update({f"Fem.{_l}": "Body", f"Tib.{_l}": f"Fem.{_l}", f"Tar.{_l}": f"Tib.{_l}", f"Foot.{_l}": f"Tar.{_l}"})
for _s in "LR":
    PARENT.update({f"Scape.{_s}": "Head", f"Flag.{_s}": f"Scape.{_s}"})
BONES = list(PARENT)


def _orient(head, d, q_frame, rest):
    base = q_frame @ rest.to_quaternion()
    q = (base @ Vector((0, 1, 0))).rotation_difference(d.normalized())
    m = (q @ base).to_matrix().to_4x4()
    m.translation = head
    return m


def _mats(p, rest):
    F, Hm, Gm = _frames(p)
    rq = F.to_quaternion()
    M = {"Body": F @ rest["Body"], "Head": Hm @ rest["Head"], "Gaster": Gm @ rest["Gaster"]}
    for leg in LEGS:
        c, k, a, tip = _leg(p, leg, F)
        M[f"Fem.{leg}"] = _orient(c, k - c, rq, rest[f"Fem.{leg}"])
        M[f"Tib.{leg}"] = _orient(k, a - k, rq, rest[f"Tib.{leg}"])
        M[f"Tar.{leg}"] = _orient(a, tip - a, rq, rest[f"Tar.{leg}"])
        M[f"Foot.{leg}"] = _orient(tip, tip - a, rq, rest[f"Foot.{leg}"])
    for s in "LR":
        so, e, tip, hq = _antenna(p, s, Hm)
        M[f"Scape.{s}"] = _orient(so, e - so, hq, rest[f"Scape.{s}"])
        M[f"Flag.{s}"] = _orient(e, tip - e, hq, rest[f"Flag.{s}"])
    return M


def _basis(M, rest):
    out = {}
    for b in BONES:
        par = PARENT[b]
        if par is None:
            m = rest[b].inverted() @ M[b]
        else:
            m = (rest[par].inverted() @ rest[b]).inverted() @ M[par].inverted() @ M[b]
        out[b] = (m.to_quaternion(), m.to_translation())
    return out


# ---------- mesh (rest pose, armature space) ----------

class _Geo:
    def __init__(self):
        self.v, self.f, self.m, self.g = [], [], [], []

    def add(self, verts, faces, mats, group):
        b = len(self.v)
        self.v += [tuple(p) for p in verts]
        self.g += [group] * len(verts)
        self.f += [tuple(i + b for i in fc) for fc in faces]
        self.m += mats if isinstance(mats, list) else [mats] * len(faces)


def _loft(rings, n=8, row_mats=None, mat=0):
    """Rings (y, half-width, half-height, z) along y; caps at the ends."""
    verts, faces = [], []
    for y, hw, hh, z in rings:
        for j in range(n):
            a = math.tau * j / n + math.pi / n
            verts.append((hw * math.cos(a), y, z + hh * math.sin(a)))
    mats = []
    for i in range(len(rings) - 1):
        for j in range(n):
            faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
            mats.append(row_mats[i] if row_mats else mat)
    faces += [tuple(range(n)), tuple(range(len(verts) - 1, len(verts) - n - 1, -1))]
    mats += [mats[0], mats[-1]]
    return verts, faces, mats


def _tube(points, radii, n=6):
    """Tube along a polyline (parallel transport of the reference axis), caps at the ends."""
    pts = [Vector(p) for p in points]
    verts, faces = [], []
    ref = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if ref is None:
            ref = t.cross(Vector((0, 0, 1)))
            if ref.length < 1e-4:
                ref = t.cross(Vector((1, 0, 0)))
        ref = (ref - t * ref.dot(t)).normalized()
        side = t.cross(ref)
        for j in range(n):
            a = math.tau * j / n
            verts.append(tuple(p + radii[i] * (math.cos(a) * ref + math.sin(a) * side)))
    for i in range(len(pts) - 1):
        for j in range(n):
            faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
    faces += [tuple(range(n)), tuple(range(len(verts) - 1, len(verts) - n - 1, -1))]
    return verts, faces


def _ellipsoid(center, radii, subdiv=1):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    verts = [Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2])) + Vector(center) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return verts, faces


def _off(rings, dz):
    return [(y, hw, hh, z + dz) for y, hw, hh, z in rings]


def build_mesh(rest_joints):
    g = _Geo()
    # head (back to front; the front drops a little: mouth down)
    head = [(-0.272, 0.034, 0.030, 0.006), (-0.292, 0.080, 0.066, 0.012), (-0.330, 0.104, 0.082, 0.010),
            (-0.385, 0.105, 0.079, 0.002), (-0.435, 0.090, 0.066, -0.008), (-0.470, 0.064, 0.047, -0.018),
            (-0.492, 0.032, 0.024, -0.024)]
    g.add(*_loft(_off(head, H0), 8, mat=0), "Head")
    for sx in (1, -1):
        g.add(*_ellipsoid((sx * 0.094, -0.362, H0 + 0.034), (0.020, 0.030, 0.024)), 4, "Head")
        z = H0 - 0.040 if sx > 0 else H0 - 0.046                   # both mandibles closed, one over the other
        pts = [(sx * 0.046, -0.462, z), (sx * 0.040, -0.508, z - 0.010), (sx * 0.014, -0.534, z - 0.014),
               (-sx * 0.014, -0.536, z - 0.014)]
        g.add(*_tube(pts, [0.017, 0.013, 0.008, 0.003], 5), 5, "Head")
    # mesosoma (tall pronotum, thin waist before the petiole)
    meso = [(-0.300, 0.030, 0.026, 0.000), (-0.282, 0.058, 0.052, 0.006), (-0.240, 0.072, 0.068, 0.018),
            (-0.190, 0.064, 0.060, 0.014), (-0.140, 0.048, 0.048, 0.004), (-0.100, 0.044, 0.042, 0.002),
            (-0.060, 0.050, 0.050, 0.004), (-0.022, 0.040, 0.044, 0.000), (0.006, 0.018, 0.020, -0.004)]
    g.add(*_loft(_off(meso, H0), 8, mat=0), "Body")
    for leg in LEGS:                                                   # coxae (part of the body)
        coxa, _t, _l = LEG_DEF[leg[1]]
        sx = _side(leg)
        r = 0.030 if leg[1] == "1" else 0.025
        g.add(*_tube([(sx * 0.022, coxa.y, H0 - 0.028), (sx * coxa.x, coxa.y, H0 + coxa.z)], [r, r * 0.75], 6), 0,
              "Body")
    # petiole (upright scale) and gaster with the segment bands
    pet = [(0.000, 0.015, 0.015, -0.004), (0.020, 0.022, 0.020, 0.000), (0.038, 0.024, 0.046, 0.020),
           (0.056, 0.020, 0.022, 0.000), (0.084, 0.016, 0.016, -0.004)]
    g.add(*_loft(_off(pet, H0), 6, mat=0), "Gaster")
    gas = [(0.076, 0.022, 0.020, -0.004), (0.104, 0.086, 0.076, 0.000), (0.150, 0.118, 0.103, -0.003),
           (0.162, 0.121, 0.106, -0.004), (0.236, 0.136, 0.118, -0.010), (0.248, 0.136, 0.118, -0.011),
           (0.318, 0.130, 0.112, -0.016), (0.330, 0.128, 0.110, -0.017), (0.395, 0.104, 0.091, -0.022),
           (0.455, 0.068, 0.060, -0.026), (0.492, 0.024, 0.023, -0.028)]
    rows = [1, 1, 2, 1, 2, 1, 2, 1, 1, 1]
    g.add(*_loft(_off(gas, H0), 10, row_mats=rows), "Gaster")
    # legs: thick femur in the middle, thin tibia and tarsus
    for leg in LEGS:
        c, k = rest_joints[f"Fem.{leg}"]
        _k, a = rest_joints[f"Tib.{leg}"]
        _a, tip = rest_joints[f"Tar.{leg}"]
        g.add(*_tube([c, c.lerp(k, 0.45), k], [0.016, 0.019, 0.0135], 6), 3, f"Fem.{leg}")
        g.add(*_tube([k, k.lerp(a, 0.5), a], [0.0125, 0.011, 0.0095], 6), 3, f"Tib.{leg}")
        g.add(*_tube([a, a.lerp(tip, 0.5), tip], [0.0085, 0.0072, 0.0058], 5), 3, f"Tar.{leg}")
    # elbowed antennae: long scape and funiculus with a thicker tip
    for s in "LR":
        so, e = rest_joints[f"Scape.{s}"]
        _e, tip = rest_joints[f"Flag.{s}"]
        g.add(*_tube([so, so.lerp(e, 0.5), e], [0.0062, 0.0066, 0.0074], 5), 0, f"Scape.{s}")
        mid = e.lerp(tip, 0.55) + Vector((0, 0, 0.012))
        g.add(*_tube([e, mid, e.lerp(tip, 0.85) + Vector((0, 0, 0.004)), tip], [0.0068, 0.0072, 0.0092, 0.005], 5),
              0, f"Flag.{s}")
    me = bpy.data.meshes.new("stage_ant")
    me.from_pydata(g.v, [], g.f)
    for key in ("body", "gaster", "band", "leg", "eye", "mandible"):
        m = kit.flat(f"Ant_{key}", COLORS[key], rough=0.62 if key != "eye" else 0.35)
        kit.principled(m).inputs["Specular IOR Level"].default_value = 0.25
        me.materials.append(m)
    for poly, mi in zip(me.polygons, g.m):
        poly.material_index = mi
        poly.use_smooth = False
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me, g.g


# ---------- actions ----------

def _write_action(name, rest, poses, slot_name="AntRig"):
    act = bpy.data.actions.new(f"Ant_{name}")
    act.use_fake_user = True
    slot = act.slots.new(id_type="OBJECT", name=slot_name)
    bag = au.action_ensure_channelbag_for_slot(act, slot)
    frames = list(range(len(poses)))
    table = [_basis(_mats(p, rest), rest) for p in poses]
    lin = rigs.LINEAR
    for b in BONES:
        qs, prev = [], None
        for row in table:
            q = row[b][0].copy()
            if prev is not None and q.dot(prev) < 0:
                q.negate()
            prev = q
            qs.append(q)
        chans = [("rotation_quaternion", 4, [[q[i] for q in qs] for i in range(4)])]
        if b == "Body":
            chans.append(("location", 3, [[row[b][1][i] for row in table] for i in range(3)]))
        if b == "Gaster":
            chans.append(("scale", 3, [[p["breath"] for p in poses]] * 3))
        for prop, n, vals in chans:
            for i in range(n):
                fc = bag.fcurves.new(f'pose.bones["{b}"].{prop}', index=i, group_name=b)
                fc.keyframe_points.add(len(frames))
                fc.keyframe_points.foreach_set("co", [c for f, v in zip(frames, vals[i]) for c in (f, v)])
                fc.keyframe_points.foreach_set("interpolation", [lin] * len(frames))
                fc.update()
    return act


def _idle(n=48):
    out = []
    for k in range(n + 1):
        t = k / n
        p = base_pose()
        p["breath"] = 1.0 + 0.022 * math.sin(math.tau * t)
        p["pos"].z += 0.0025 * math.sin(math.tau * t)
        p["nod"] = math.radians(1.5) * math.sin(math.tau * t + 0.8)
        p["ant"]["L"] = [42 + 7 * math.sin(math.tau * t), 28 + 12 * math.sin(math.tau * t + 0.6),
                         -18 + 8 * math.sin(math.tau * 2 * t + 1.0), 38 + 6 * math.sin(math.tau * t + 2.0)]
        p["ant"]["R"] = [42 + 7 * math.sin(math.tau * t + 2.4), 28 + 12 * math.sin(math.tau * t + 3.3),
                         -18 + 8 * math.sin(math.tau * 2 * t + 2.7), 38 + 6 * math.sin(math.tau * t + 4.4)]
        out.append(p)
    return out


def _gait(n, duty, stride, lift, bob):
    """Tripod gait: L1, R2, L3 together, half a cycle later R1, L2, R3. A foot on the support moves backward at constant
    speed (stride / (duty * n) per frame): it is the body speed so nothing skates."""
    out = []
    for k in range(n + 1):
        t = k / n
        p = base_pose()
        for leg in LEGS:
            x0, y0 = p["feet"][leg].x, p["feet"][leg].y
            u = (t + (0.0 if leg in TRIPOD_A else 0.5)) % 1.0
            if u < duty:
                s = u / duty
                y, z, dx = y0 - stride / 2 + stride * s, 0.0, 0.0
            else:
                s = (u - duty) / (1 - duty)
                y, z, dx = y0 + stride / 2 - stride * _smooth(s), lift * math.sin(math.pi * s), 0.02 * math.sin(math.pi * s)
            p["feet"][leg] = Vector((x0 + _side(leg) * dx, y, z))
        p["pos"].z += bob * math.cos(2 * math.tau * t)
        p["roll"] = math.radians(1.6) * math.sin(math.tau * t)
        p["yaw"] = math.radians(1.3) * math.sin(math.tau * t + 0.5)
        p["nod"] = math.radians(1.5) * math.sin(2 * math.tau * t)
        p["ant"]["L"] = [40 + 5 * math.sin(math.tau * t), 26 + 10 * math.sin(math.tau * t), -16 + 6 * math.sin(math.tau * t + 1), 34]
        p["ant"]["R"] = [40 - 5 * math.sin(math.tau * t), 26 - 10 * math.sin(math.tau * t), -16 - 6 * math.sin(math.tau * t + 1), 34]
        out.append(p)
    return out


def risen_pose():
    p = base_pose()
    p["pos"].z = H_RISE
    p["pitch"] = math.radians(13)
    p["nod"] = -0.16
    p["lift"] = 0.12
    p["tarsus"] = math.radians(62)
    p["ant"] = {"L": [52.0, 22.0, -8.0, 30.0], "R": [52.0, 22.0, -8.0, 30.0]}
    return p


SAG_FRONT = {"L": (0.66, -0.33), "R": (0.65, -0.31)}    # fallen front foot: to the side (a little behind the old
                                                          # line), not forward next to the antennae


SAG_SPREAD = {"1": 1.0, "2": 1.36, "3": 1.45}   # feet away from the body in the fallen pose (fraction of the normal support)


def sagged_pose():
    p = base_pose()
    p["pos"].z = H_SAG
    p["pitch"] = math.radians(-2.5)
    p["roll"] = math.radians(2.5)
    p["nod"] = 0.0
    p["lift"] = 0.115                  # gaster touching the ground (0.10 sank 0.003 L)
    # legs spread and almost straight, knee outward: with 1.16 and pole 0.55 the back knee rose
    # 0.22 L and, from eye level, the lying ant looked like it was standing
    p["tarsus"] = math.radians(10)
    p["pole"] = 0.85
    for leg in LEGS:
        coxa = LEG_DEF[leg[1]][0]
        c = Vector((_side(leg) * coxa.x, coxa.y, 0.0))
        p["feet"][leg] = c + (p["feet"][leg] - c) * SAG_SPREAD[leg[1]]
    for s, (x, y) in SAG_FRONT.items():
        p["feet"][f"{s}1"] = Vector((_side(s) * x, y, 0.0))
    # relaxed antennae: scape slightly outward, funiculus drooping forward and down (elbow visible)
    p["ant"] = {"L": [18.0, 44.0, -26.0, 10.0], "R": [15.0, 38.0, -24.0, 14.0]}
    return p


def _rise(n=96):
    a, b = base_pose(), risen_pose()
    out = []
    for k in range(n + 1):
        u = k / n
        e = _smoother(u)
        p = _mix(a, b, e)
        p["pitch"] = b["pitch"] * _smoother((u - 0.12) / 0.88)
        p["ant"] = _mix(a, b, _smoother(u / 0.6))["ant"]
        if u < 0.2:                                   # crouches a little before pushing
            p["pos"].z -= 0.014 * math.sin(math.pi * u / 0.2)
        out.append(p)
    return out


def _tremble(n=24):
    base = risen_pose()
    out = []
    for k in range(n + 1):
        u = k / n
        env = math.sin(math.pi * u) ** 2
        p = _copy(base)
        p["pos"].z += env * (0.006 * math.sin(math.tau * 8 * u) - 0.008)
        p["roll"] += env * math.radians(1.3) * math.sin(math.tau * 6 * u + 0.7)
        for i, leg in enumerate(LEGS):
            p["tars_off"][leg] = env * math.radians(3.0) * math.sin(math.tau * 9 * u + i * 1.3)
        for s, ph in (("L", 0.0), ("R", 1.9)):
            p["ant"][s][0] += env * 5 * math.sin(math.tau * 7 * u + ph)
        out.append(p)
    return out


SAG_A, SAG_B = 1.5, 0.7            # s: legs tremble and give way 25% of the height; then the body falls (ease-in) until the impact
SAG_IMPACT = SAG_A + SAG_B
SAG_N = 92                         # 3,83 s a 24 q/s


def _bump(t, t0, dur):
    """Half sine from 0 to 1 to 0 between t0 and t0 + dur (zero outside)."""
    if t <= t0 or t >= t0 + dur:
        return 0.0
    return math.sin(math.pi * (t - t0) / dur)


def _sag_height(t):
    """Fraction of the descent (0 = starting pose, 1 = belly on the ground). Gives way slowly (25% in SAG_A, starting still),
    then falls with constant acceleration from the speed it already had, until the impact at SAG_IMPACT."""
    if t <= SAG_A:
        u = t / SAG_A
        return 0.25 * (2 * u * u - u ** 3)
    if t >= SAG_IMPACT:
        return 1.0
    v0 = 0.25 / SAG_A
    acc = 2 * (0.75 - v0 * SAG_B) / SAG_B ** 2
    s = t - SAG_A
    return 0.25 + v0 * s + 0.5 * acc * s * s


def _sag(start, n=SAG_N):
    """Too much weight, not pain: the legs tremble and give way slowly (the left side first), the body falls fast with the feet
    sliding outward, the gaster lags in the fall and rebounds ~0.015 L after the impact, and the legs still
    settle a little. Ends exactly at sagged_pose() (SagIdle starts from it)."""
    b = sagged_pose()
    side_delay = {"L": 0.0, "R": 0.18}
    settle = {"R2": (2.75, 0.94, 0.16), "L3": (3.05, 0.96, 0.14)}   # foot that still slides a little at the end
    out = []
    for k in range(n + 1):
        t = k / FPS
        fh = _sag_height(t)
        ft = {}
        for i, leg in enumerate(LEGS):
            g = _smoother((t - 1.30 - side_delay[leg[0]]) / 1.05)
            if leg in settle:
                t0, part, dur = settle[leg]
                g = g * part + (1 - part) * _smooth((t - t0) / dur)
            ft[leg] = g
        p = _mix(start, b, fh, ft)
        # the tarsus only lowers with the body (the per-foot blend above would follow the sliding)
        for leg in LEGS:
            p["tars_off"][leg] = start["tars_off"][leg] + (b["tars_off"][leg] - start["tars_off"][leg]) * fh
        p["pitch"] = start["pitch"] + (b["pitch"] - start["pitch"]) * fh ** 0.85
        p["pole"] = start["pole"] + (b["pole"] - start["pole"]) * _smooth(t / SAG_IMPACT)
        # leg tremor at the start (fades before the fall)
        env = _smooth(t / 0.25) * (1 - _smooth((t - 1.0) / 0.6))
        p["pos"].z += env * 0.004 * math.sin(math.tau * 6 * t)
        for i, leg in enumerate(LEGS):
            p["tars_off"][leg] += env * math.radians(3.0) * math.sin(math.tau * 7 * t + i * 1.3)
        # asymmetry: the left side (x > 0; roll + lowers this side) gives way first, the right catches up in the fall
        p["roll"] = (start["roll"] + (b["roll"] - start["roll"]) * fh
                     + math.radians(4.5) * _smooth(t / 1.4) * (1 - _smooth((t - 1.6) / 0.8))
                     + env * math.radians(0.8) * math.sin(math.tau * 5 * t + 0.7))
        # impact: the body bounces a little, the head lifts and returns
        p["pos"].z += 0.0045 * _bump(t, SAG_IMPACT, 0.2) + 0.0012 * _bump(t, SAG_IMPACT + 0.2, 0.15)
        p["nod"] = start["nod"] + (b["nod"] - start["nod"]) * fh - 0.03 * _bump(t, SAG_IMPACT, 0.22)
        # gaster: lags in the fall (stays high), touches 2 frames after the body and rebounds ~2.5 cm at 1.7 m
        tg = SAG_IMPACT + 0.08
        p["lift"] = (start["lift"] + (b["lift"] - start["lift"]) * fh
                     + 0.07 * _bump(t, SAG_A, tg - SAG_A)
                     + 0.035 * _bump(t, tg, 0.24) + 0.008 * _bump(t, tg + 0.24, 0.16))
        # front left leg still settles (knee bends and returns)
        p["tars_off"]["L1"] += math.radians(7) * _bump(t, 2.9, 0.25)
        # antennae: tremble with the legs, rise in the fall (delay) and drop relaxed afterward
        a = _mix(start, b, _smoother((t - 1.7) / 1.6))["ant"]
        for s, ph in (("L", 0.0), ("R", 1.9)):
            a[s][0] += env * 4 * math.sin(math.tau * 6 * t + ph) + 10 * _bump(t, SAG_A, 0.9)
            a[s][2] += 8 * _bump(t, SAG_A + 0.15, 0.9)
        p["ant"] = a
        out.append(p)
    return out


def _sag_idle(n=72):
    """Lying down in a 3 s loop, starting exactly from sagged_pose(): antennae slow and slight, the gaster rises and falls
    (breathing; only upward, never goes into the ground), the body does not lift."""
    out = []
    for k in range(n + 1):
        t = k / n
        p = sagged_pose()
        br = 0.5 - 0.5 * math.cos(math.tau * t)
        p["lift"] += 0.012 * br
        p["breath"] = 1.0 + 0.012 * br
        for s, ph, sg in (("L", 0.0, 1.0), ("R", 1.0, -1.0)):
            p["ant"][s][0] += 3.0 * math.sin(math.tau * t) * sg
            p["ant"][s][1] += 5.0 * math.sin(math.tau * t + ph) - 5.0 * math.sin(ph)
            p["ant"][s][2] += 3.0 * math.sin(math.tau * 2 * t) * sg
            p["ant"][s][3] += 6.0 * math.sin(math.tau * t + ph + 0.8) - 6.0 * math.sin(ph + 0.8)
        out.append(p)
    return out


# ---------- template (registered in rigs._templates) ----------

def ensure_template():
    if KEY in rigs._templates:
        return rigs._templates[KEY]
    scene = bpy.context.scene
    rest_pose = base_pose()
    J = joints(rest_pose)
    arm_data = bpy.data.armatures.new("AntRig")
    arm = bpy.data.objects.new("AntRig", arm_data)
    scene.collection.objects.link(arm)
    keep_active = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in BONES:
        eb = arm_data.edit_bones.new(b)
        eb.head, eb.tail = J[b]
        eb.roll = 0.0
        ebs[b] = eb
    for b, par in PARENT.items():
        if par:
            ebs[b].parent = ebs[par]
            ebs[b].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = keep_active
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    rest = {b.name: b.matrix_local.copy() for b in arm_data.bones}
    me, groups = build_mesh(J)
    body = bpy.data.objects.new("AntBody", me)
    scene.collection.objects.link(body)
    vg = {b: body.vertex_groups.new(name=b) for b in BONES}
    by = {}
    for i, name in enumerate(groups):
        by.setdefault(name, []).append(i)
    for name, idx in by.items():
        vg[name].add(idx, 1.0, "REPLACE")
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    body.parent = arm
    for o in (arm, body):
        o.hide_render = True
    actions = {
        "Idle": _write_action("Idle", rest, _idle()),
        "Walk": _write_action("Walk", rest, _gait(20, 0.55, 0.22, 0.07, 0.004)),
        "Run": _write_action("Run", rest, _gait(8, 0.5, 0.26, 0.06, 0.003)),
        "Rise": _write_action("Rise", rest, _rise()),
        "Tremble": _write_action("Tremble", rest, _tremble()),
        "Sag": _write_action("Sag", rest, _sag(risen_pose())),
        "SagStand": _write_action("SagStand", rest, _sag(base_pose())),
        "SagIdle": _write_action("SagIdle", rest, _sag_idle()),
    }
    lo = Vector((-0.62, -0.62, 0.0))
    box = SimpleNamespace(lo=lo, hi=Vector((0.62, 0.38, 0.30)), size=Vector((1.24, 1.0, 0.30)))
    t = SimpleNamespace(key=KEY, arm=arm, meshes=[body], actions=actions, base_scale=1.0, rot=Quaternion(),
                        box=box, once=ONCE)
    rigs._templates[KEY] = t
    rigs.SPECS.setdefault(KEY, "procedural:ant")
    return t


def play(rig, key, f, blend_in=4):
    """One-shot action (Rise, Tremble, Sag) on an NLA strip on top, holding the final pose. 'Sag' without the
    ant raised before becomes 'SagStand' (starts from the normal pose: no jump)."""
    st_ = _state.setdefault(rig.name, "stand")
    if key == "Sag" and st_ != "risen":
        key = "SagStand"
    if key == "SagIdle" and st_ == "lying":
        # already lying in a loop (piece with 'span' that crosses the cut): the NLA strip continues; another strip at the cut
        # would only restart the loop (antennae jumping on the scene's 1st frame)
        return None
    act = rig.t.actions[key]
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = f"{key}{len(ad.nla_tracks)}"
    st = track.strips.new(key, int(f), act)
    if st.action_slot is None:
        st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.scale = rigs.strip_scale(1.0)
    st.repeat = 1.0
    st.blend_in = blend_in
    st.extrapolation = "HOLD_FORWARD"
    if key == "SagIdle":
        # lying loop: starts at the final pose of Sag (no blend: at the cut the ant is already lying on the 1st frame)
        st.repeat = 400.0
        st.blend_in = 0               # HOLD_FORWARD (above): nothing before the cue
    _state[rig.name] = {"Rise": "risen", "Tremble": "risen", "SagIdle": "lying"}.get(key, "down")
    return st


CRUMB_COLORS = ("#E8CF9A", "#D9B57A", "#C99A5C")


def carry_crumb(rig, coll, rng, size=1.0):
    """Crumb held in the mandibles (child of the Head bone: goes along in the step and in the root's 'vanish'). 'size' 1 = ~0.2 L
    in diameter (real ants carry crumbs the size of the head). For ants-human-size: the macro trail."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in bm.verts:
        v.co.x *= rng.uniform(0.85, 1.25)
        v.co.y *= rng.uniform(0.8, 1.15)
        v.co.z *= rng.uniform(0.6, 0.85)
    me = bpy.data.meshes.new(f"{rig.name}_crumb")
    bm.to_mesh(me)
    bm.free()
    m0 = kit.flat(f"AntCrumb{rng.randrange(3)}", rng.choice(CRUMB_COLORS), rough=0.9)
    me.materials.append(m0)
    for poly in me.polygons:
        poly.use_smooth = False
    o = bpy.data.objects.new(f"{rig.name}_crumb", me)
    coll.objects.link(o)
    o.parent = rig.arm
    o.parent_type = "BONE"
    o.parent_bone = "Head"
    bone = rig.arm.data.bones["Head"]
    tail = bone.matrix_local @ Matrix.Translation((0.0, bone.length, 0.0))
    r = 0.1 * size * rng.uniform(0.85, 1.15)
    want = Matrix.Translation((rng.uniform(-0.01, 0.01), -0.535 - r * 0.7, H0 - 0.05)) @ \
        Matrix.Rotation(rng.uniform(0, math.tau), 4, "Z") @ Matrix.Diagonal((r, r, r, 1.0))
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = tail.inverted() @ want
    return o


# ---------- formigueiro ----------

SOIL = ("#7A5A3B", "#6D4F33", "#856443", "#735537")
HOLE = "#1F150F"
_hill_mats = []


def _hill_materials():
    if not _hill_mats:
        for k, hexa in enumerate(SOIL + (HOLE,)):
            m = kit.flat(f"Anthill_{k}", hexa, rough=1.0)
            kit.principled(m).inputs["Specular IOR Level"].default_value = 0.1
            _hill_mats.append(m)
    return _hill_mats


def anthill_mesh(name, diameter, height, rng):
    """Faceted earth mound: dome with a crater at the top (dark mouth), an entrance on the slope (+x side, which faces
    the camera) and loose clods of earth around the base."""
    R, H = diameter / 2, height
    nr, ns = 7, 16
    verts, faces, mats = [(0.0, 0.0, H * 0.80)], [], []
    for i in range(1, nr + 1):
        r = R * i / nr
        for j in range(ns):
            a = math.tau * j / ns + (0.5 * math.tau / ns if i % 2 else 0.0)
            q = r / R
            z = H * max(0.0, 1 - q * q) ** 0.75
            if q < 0.2:
                z = H * 0.80 + (H * 0.92 - H * 0.80) * (q / 0.2)       # crater rim
            z += rng.uniform(-0.05, 0.05) * H * (1 - q * 0.6)
            rr = r * (1 + rng.uniform(-0.06, 0.06))
            if i == nr:
                z = -0.03
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for j in range(ns):
        faces.append((0, 1 + j, 1 + (j + 1) % ns))
        mats.append(4)
    for i in range(nr - 1):
        b0, b1 = 1 + i * ns, 1 + (i + 1) * ns
        for j in range(ns):
            j2 = (j + 1) % ns
            faces.append((b0 + j, b1 + j, b1 + j2, b0 + j2))
            mats.append(rng.randrange(4))
    # entrance on the slope: the ring 3 faces turned toward +x stay dark and sink
    for fi, fc in enumerate(faces):
        cx = sum(verts[v][0] for v in fc) / len(fc)
        cy = sum(verts[v][1] for v in fc) / len(fc)
        rr = math.hypot(cx, cy)
        if 0.38 * R < rr < 0.58 * R and abs(math.atan2(cy, cx)) < 0.33:
            mats[fi] = 4
    for vi, v in enumerate(verts):
        rr = math.hypot(v[0], v[1])
        if 0.4 * R < rr < 0.56 * R and abs(math.atan2(v[1], v[0])) < 0.25:
            verts[vi] = (v[0] * 0.93, v[1], v[2] - 0.06 * H)
    # clods of earth at the base
    for k in range(26):
        a, r = rng.uniform(0, math.tau), R * rng.uniform(0.95, 1.5)
        s = diameter * rng.uniform(0.012, 0.03)
        ev, ef = _ellipsoid((r * math.cos(a), r * math.sin(a), s * 0.25), (s, s * rng.uniform(0.7, 1.1), s * 0.6), 0)
        b = len(verts)
        verts += [tuple(p) for p in ev]
        faces += [tuple(i + b for i in f) for f in ef]
        mats += [rng.randrange(4)] * len(ef)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in _hill_materials():
        me.materials.append(m)
    for poly, mi in zip(me.polygons, mats):
        poly.material_index = mi
        poly.use_smooth = False
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def spawn_anthill(name, coll, spec, x, y, heading, start, end, fps, rng):
    """'len' = base diameter (default 1.6 m); 'h' = height (default 0.3 x diameter). 'scale_with_ants': the 'grow' cue
    of the ants also grows the mound (true = same factor; number = final factor). 'trail': [[x, y], ...] packed-earth
    trail leaving the mound (child of the mound: grows along)."""
    ln = spec.get("len", 1.6)
    d = rng.uniform(*ln) if isinstance(ln, list) else float(ln)
    h = spec.get("h")
    h = float(h) if h else 0.3 * d
    me = anthill_mesh(f"{name}_mesh", d, h, random.Random(f"hill{name}"))
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    import presets
    o.location = (x, y, presets.ground_height(x, y))
    o.rotation_euler = (0, 0, heading)
    if spec.get("trail"):
        tr = _trail(f"{name}_trail", [(x, y)] + [tuple(p[:2]) for p in spec["trail"]], random.Random(f"trail{name}"),
                    presets.ground_height)
        coll.objects.link(tr)
        tr.parent = o                                   # grows along with the mound ('scale_with_ants')
        tr.matrix_parent_inverse = Matrix.Translation(o.location) @ Matrix.Rotation(heading, 4, "Z")
        tr.matrix_parent_inverse.invert()
    return SimpleNamespace(obj=o, height=h, positions=None)


NEST_SOIL = ("#8E6A45", "#A37D55", "#6E4F33", "#B8946A")      # grains: 2 medium, 1 dark (damp), 1 light (dry, rim)


def spawn_antnest(name, coll, spec, x, y, heading, start, end, fps, rng):
    """Real anthill mouth for the MACRO (ants-human-size scene 07: "the small ants that
    loosened this soil are gone"): ring of loose earth grains (3 sizes, the upper ones lighter and drier), 3 empty
    tunnels (dark mouth with a funnel), still seeds and, with 'puddle' [dx, dy, r] (m, relative to 'at'), a shallow
    still puddle on the packed soil (mirrors the sky, no drops). 'len' = mound diameter (default 0.16 m). 'seeds' = how many."""
    D = float(spec.get("len", 0.16))
    R = D / 2
    H = R * 0.32
    parts, mats = [], []                       # (verts, faces) per material
    soil = [kit.flat(f"Nest_soil{k}", h, rough=1.0) for k, h in enumerate(NEST_SOIL)]
    dark = kit.flat("Nest_hole", "#120B07", rough=1.0)
    bare = kit.flat("Nest_bare", "#6A5038", rough=1.0)
    seedm = [kit.flat("Nest_seed0", "#5A3B22", rough=0.6), kit.flat("Nest_seed1", "#C8A666", rough=0.6)]
    all_mats = soil + [dark, bare] + seedm
    verts, faces, fmat = [], [], []

    def add(vs, fs, mi):
        b = len(verts)
        verts.extend(vs)
        faces.extend(tuple(i + b for i in f) for f in fs)
        fmat.extend([mi] * len(fs))

    def profile(r):                            # mound height: ring with a crater in the middle
        return H * math.exp(-((r - R * 0.42) / (R * 0.38)) ** 2) * (0.35 if r < R * 0.12 else 1.0)

    # bare earth ground under the mound (irregular disc, 1 mm above the grass)
    ring = [(R * 1.55 * rng.uniform(0.85, 1.12) * math.cos(a), R * 1.55 * rng.uniform(0.85, 1.12) * math.sin(a), 0.001)
            for a in [math.tau * k / 18 for k in range(18)]]
    add([(0, 0, 0.001)] + ring, [(0, 1 + k, 1 + (k + 1) % 18) for k in range(18)], 5)
    holes = [(0.0, 0.0, R * 0.11)] + [(R * 0.62 * math.cos(a), R * 0.62 * math.sin(a), R * 0.07)
                                      for a in (rng.uniform(-2.6, -2.0), rng.uniform(-1.0, -0.5))]
    # grains: pile under the profile; more grains on the crest; the ones on top are the light ones
    n = int(spec.get("grains", 700))
    for _k in range(n):
        r = R * 1.25 * math.sqrt(rng.random())
        a = rng.uniform(0, math.tau)
        gx, gy = r * math.cos(a), r * math.sin(a)
        if any(math.hypot(gx - hx, gy - hy) < hr * 1.05 for hx, hy, hr in holes):
            continue
        top = profile(r)
        s = rng.choice((0.0012, 0.0019, 0.003)) * rng.uniform(0.8, 1.25)
        gz = rng.uniform(0.55, 1.0) * top + s * 0.6
        ev, ef = _ellipsoid((gx, gy, gz), (s, s * rng.uniform(0.75, 1.1), s * rng.uniform(0.6, 0.9)), 0)
        lit = gz > top * 0.85 and rng.random() < 0.6
        add([tuple(p) for p in ev], ef, 3 if lit else (2 if rng.random() < 0.18 else rng.randrange(2)))
    # empty tunnels: dark funnel sunk in place of each mouth
    for hx, hy, hr in holes:
        z0 = profile(math.hypot(hx, hy)) * 0.7 + 0.001
        m = 10
        vs = [(hx, hy, z0 - hr * 1.2)] + [(hx + hr * math.cos(math.tau * k / m) * rng.uniform(0.85, 1.1),
                                            hy + hr * math.sin(math.tau * k / m) * rng.uniform(0.85, 1.1), z0)
                                           for k in range(m)]
        add(vs, [(0, 1 + (k + 1) % m, 1 + k) for k in range(m)], 4)
    # still seeds (elongated ellipsoids of 3 to 5 mm)
    for _k in range(int(spec.get("seeds", 6))):
        a, r = rng.uniform(0, math.tau), R * rng.uniform(1.0, 1.9)
        L = rng.uniform(0.003, 0.005)
        ev, ef = _ellipsoid((0, 0, 0), (L * 0.42, L, L * 0.36), 1)
        rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z")
        c = Vector((r * math.cos(a), r * math.sin(a), L * 0.3))
        add([tuple(rot @ Vector(p) + c) for p in ev], ef, 6 + (_k % 2))
    me = bpy.data.meshes.new(f"{name}_mesh")
    me.from_pydata(verts, [], faces)
    for m_ in all_mats:
        me.materials.append(m_)
    for poly, mi in zip(me.polygons, fmat):
        poly.material_index = mi
        poly.use_smooth = False
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    import presets
    o.location = (x, y, presets.ground_height(x, y))
    o.rotation_euler = (0, 0, heading)
    if spec.get("puddle"):
        px, py, pr = spec["puddle"]
        m = 24
        ph1, ph2 = rng.uniform(0, math.tau), rng.uniform(0, math.tau)

        def rr(a):                                       # organic edge (no star): sum of sines
            return pr * 1.18 * (1 + 0.13 * math.sin(2 * a + ph1) + 0.07 * math.sin(3 * a + ph2))
        rim = [(px + rr(math.tau * k / m) * math.cos(math.tau * k / m),
                py + 0.8 * rr(math.tau * k / m) * math.sin(math.tau * k / m), 0.0015) for k in range(m)]
        wet = kit.flat("Nest_wet", "#3B2A1C", rough=0.5)
        water = kit.flat("Nest_water", "#1E1A16", rough=0.04)
        p_ = kit.principled(water)
        p_.inputs["Specular IOR Level"].default_value = 1.0
        p_.inputs["IOR"].default_value = 1.33
        # the stage sky is a dome (not the World) and Eevee here does not trace rays: the sky reflection comes by emission,
        # from blue (above) to the horizon's peach (grazing), through the Layer Weight; the puddle stays still, no drops
        nt = water.node_tree
        tc = nt.nodes.new("ShaderNodeTexCoord")          # near the camera (-y) reflects the top of the sky; far away, the horizon
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        lw = nt.nodes.new("ShaderNodeMapRange")
        lw.inputs["From Min"].default_value, lw.inputs["From Max"].default_value = py - pr, py + pr * 0.9
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        nt.links.new(sep.outputs["Y"], lw.inputs["Value"])
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.inputs["A"].default_value = kit.lin(spec.get("sky_top", "#6F86BE"))
        mixc.inputs["B"].default_value = kit.lin(spec.get("sky_low", "#E9B98E"))
        nt.links.new(lw.outputs["Result"], mixc.inputs["Factor"])
        nt.links.new(mixc.outputs["Result"], p_.inputs["Emission Color"])
        p_.inputs["Emission Strength"].default_value = 0.85
        pv = [(px, py, 0.0015)] + rim
        pm = bpy.data.meshes.new(f"{name}_wet")
        pm.from_pydata(pv, [], [(0, 1 + k, 1 + (k + 1) % m) for k in range(m)])
        pm.materials.append(wet)
        w_o = bpy.data.objects.new(f"{name}_wet", pm)
        coll.objects.link(w_o)
        w_o.parent = o
        inner = [(px + (v[0] - px) * 0.78, py + (v[1] - py) * 0.78, 0.0028) for v in rim]
        wm = bpy.data.meshes.new(f"{name}_puddle")
        wm.from_pydata([(px, py, 0.0028)] + inner, [], [(0, 1 + k, 1 + (k + 1) % m) for k in range(m)])
        wm.materials.append(water)
        for poly in wm.polygons:
            poly.use_smooth = True
        p_o = bpy.data.objects.new(f"{name}_puddle", wm)
        coll.objects.link(p_o)
        p_o.parent = o
        for ob in (w_o, p_o):
            ob.visible_shadow = False
        # 2 seeds and 1 grain floating still (the water does not flow: the rain does not enter the soil)
        fl = []
        for k in range(3):
            a, r = rng.uniform(0, math.tau), pr * rng.uniform(0.2, 0.6)
            L = rng.uniform(0.003, 0.0045)
            ev, ef = _ellipsoid((0, 0, 0), (L * 0.42, L, L * 0.3), 1)
            rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z")
            c = Vector((px + r * math.cos(a), py + 0.8 * r * math.sin(a), 0.0031))
            fl.append(([tuple(rot @ Vector(q) + c) for q in ev], ef))
        fv, ff = [], []
        for vs, fs in fl:
            b = len(fv)
            fv += vs
            ff += [tuple(i + b for i in f) for f in fs]
        fm = bpy.data.meshes.new(f"{name}_float")
        fm.from_pydata(fv, [], ff)
        fm.materials.append(seedm[1])
        f_o = bpy.data.objects.new(f"{name}_float", fm)
        coll.objects.link(f_o)
        f_o.parent = o
    return SimpleNamespace(obj=o, height=H, positions=None)


def _trail(name, pts, rng, ground, width=0.11):
    """Packed-earth trail (the one ants open in the grass): thin faceted ribbon along the points (world), 1 mm
    above the ground (no z-fighting), width that varies a little; starts at the base of the mound."""
    dense = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.22))
        dense += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    dense.append(pts[-1])
    verts, faces = [], []
    for i, (x, y) in enumerate(dense):
        a, b = dense[max(i - 1, 0)], dense[min(i + 1, len(dense) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        w = width * rng.uniform(0.75, 1.25) / 2
        sh = rng.uniform(-0.02, 0.02)
        for sgn in (-1, 1):
            px, py = x + nx * (sgn * w + sh), y + ny * (sgn * w + sh)
            verts.append((px, py, ground(px, py) + 0.001))
    for i in range(len(dense) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    m = kit.flat("Anthill_trail", "#8C7550", rough=1.0)
    kit.principled(m).inputs["Specular IOR Level"].default_value = 0.05
    me.materials.append(m)
    for poly in me.polygons:
        poly.use_smooth = False
        if poly.normal.z < 0:
            poly.flip()
    me.update()
    o = bpy.data.objects.new(name, me)
    o.visible_shadow = False
    return o
