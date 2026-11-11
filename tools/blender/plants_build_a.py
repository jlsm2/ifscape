"""Final modeling, part A of plants-extinct: people and animals: cow, child, first-person hands (scene 04 and the hand of 07), person climbing the trail, people on the beach in 11, baskets of 09.

Models (tools/blender/lib/, index in lib/README.md):
- cow: lib/cow_quaternius.py (Quaternius Farm Animals, CC0), grazing on the terrace (06, "animals");
- child: lib/kid.py (Quaternius Man, CC0, with bigger head and narrow torso), applied to the Kid* copies
  that plants-extinct.build_people already created (we run after it, in build_markers);
- hands: lib/fp_hands.py (procedural, from cell_models) + sleeve that stretches to the shoulder (Stretch To);
- person climbing the trail (05): stays in module B (plants_build_b.build_tower_trail), attached to its trail.
All frames come from the timeline (tm) and the trigger words (W), never from a fixed number.
"""

import json
import os
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import kit  # noqa: E402
import rigs  # noqa: E402
import cow_quaternius as cq  # noqa: E402
import fp_hands as fh  # noqa: E402
import kid as kidmod  # noqa: E402
import plants_markers as mk  # noqa: E402
import plants_set as ps  # noqa: E402

# Marker groups (plants_markers) that this module replaces; see build_markers in plants-extinct.py.
# Possible groups: table_ext, shed, bed, hands, cow, tower_trail, amber, leaves, hand07.
ENABLED = os.environ.get("PLANTS_A", "1") == "1"   # PLANTS_A=0 turns off part A (back to the markers)
REPLACED: set[str] = {"hands", "cow", "hand07"} if ENABLED else set()

ROOT = Path(__file__).resolve().parents[2]
_VOICE = None
SLEEVE = ("#3E6A8C", "#36607F")        # blue sleeve (clothes without green or straw-beige, art.md section 1.2)
SKIN = "#C8916A"                        # = COLORS[0] of the people in the square
GRAIN = "#DCC27A"


def W(sid, word, nth=0):
    global _VOICE
    if _VOICE is None:
        _VOICE = json.loads((ROOT / "build" / "plants-extinct" / "voice.json").read_text(encoding="utf-8"))
    hits = [w["start"] for w in _VOICE[sid]["words"] if w["word"].strip("?.,:;").lower() == word.lower()]
    return hits[nth]


def _objs(roots):
    roots = roots if isinstance(roots, (list, tuple)) else [roots]
    out = []
    for r in roots:
        out += [r, *r.children_recursive]
    return out


def show_frames(roots, ranges, total):
    """Turns on only within the intervals [(a, b)] (inclusive), the object and all children (as in the set)."""
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for o in _objs(roots):
        for f in marks:
            o.hide_render = not any(a <= f <= b for a, b in ranges)
            o.keyframe_insert("hide_render", frame=f)


def _linear_all(obj):
    ad = obj.animation_data
    if ad and ad.action:
        for fc in rigs._fcurves(ad.action):
            if fc.data_path != "hide_render":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _cam_matrix(pose):
    p, yaw, pitch, roll = pose
    rot = Euler((math.radians(90 + pitch), math.radians(roll), math.radians(-yaw)), "XYZ")
    return Matrix.Translation(p) @ rot.to_matrix().to_4x4()


def _shoulder(pose, side):
    """Shoulder in the world: below and behind the eye, turning only with the camera heading (out of frame)."""
    p, yaw = Vector(pose[0]), math.radians(pose[1])
    fwd = Vector((math.sin(yaw), math.cos(yaw), 0.0))
    right = Vector((math.cos(yaw), -math.sin(yaw), 0.0))
    return p + right * (0.19 * side) - fwd * 0.12 + Vector((0, 0, -0.30))


# ---------- hands ----------

def _arm_sleeve(name, hand_obj, shoulder, sleeve):
    """Arm sleeve: 1 m tube along +y, child of the hand at the sleeve cuff, stretched to the shoulder (Stretch To).
    Covers the hollow mouth of the cuff and connects the hand to the body out of frame."""
    n = 8
    rings = [[(r * math.cos(2 * math.pi * j / n), y, 0.8 * r * math.sin(2 * math.pi * j / n)) for j in range(n)]
             for y, r in ((0.0, 0.046), (0.35, 0.052), (1.0, 0.058))]
    v, f = kit.loft_geo(rings)[:2]
    o = kit.mesh_object(name, v, f, [fh._mat(f"FPSleeve{sleeve}", sleeve)])
    kit.fix_normals(o)
    o.parent = hand_obj
    o.location = (0.0, -0.30, 0.0)
    c = o.constraints.new("STRETCH_TO")
    c.target = shoulder
    c.rest_length = 1.0
    c.volume = "NO_VOLUME"
    c.keep_axis = "PLANE_Z"
    return o


def _shoulder_empty(name, location):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = location
    return e


def hands_04(M=None, eye=(0.0, 0.15, 1.6), top=0.9, edge_y=0.85):
    """Hands of 04 resting on the back edge of the tabletop (palm down, fingers over the board), arms to the shoulders.
    Still in the world: the camera breathes and the hands stay on the table."""
    out = []
    for side, x in ((1, -0.05), (-1, -0.34)):        # to the left of the bread (B puts the bread at x ~0.15-0.45)
        h = fh.hand(f"Hand04{'R' if side > 0 else 'L'}", side, skin=SKIN, sleeve=SLEEVE[0], sleeve_dark=SLEEVE[1])
        wrist = Vector((x, edge_y + 0.03, top + 0.035))
        fingers = Vector((-0.22 * side, 1.0, -0.13))
        fh.place(h, wrist, fingers, (0.0, 0.25, -1.0))
        sh = _shoulder_empty(f"Shoulder04{side}", _shoulder((Vector(eye), 0.0, -40.0, 0.0), side))
        _arm_sleeve(f"Arm04{side}", h, sh, SLEEVE[0])
        out += [h, sh]
    return out


def _grains(name, parent, rnd_seed=4):
    """Handful of grains (12 grains of 7 mm in a heap) in the hollow of the palm (hand axes: palm +z, fingers +y)."""
    import random
    rnd = random.Random(rnd_seed)
    geos = []
    for k in range(18):
        a, r = rnd.uniform(0, 2 * math.pi), 0.026 * math.sqrt(rnd.random())
        c = (r * math.cos(a), 0.050 + r * math.sin(a), 0.020 + 0.014 * (1 - r / 0.026) + rnd.uniform(0, 0.006))
        geos.append(kit._ico_geo(1.0, c, (0.0062, 0.0048, 0.004)))
    v, f, _ = kit.merge(*geos)
    o = kit.mesh_object(name, v, f, [fh._mat("FPGrain", GRAIN)])
    o.parent = parent
    return o


def hand_07(tm, poses, total, sack, furrow_x, furrow_y0, bed_top):
    """Right hand of 07: takes a handful from the sack ('grain'), brings it palm up ('So'), turns and lets it fall into the
    furrow ('plant') and covers it by dragging the soil until t 4.88 of the scene; returns out of frame.
    sack = mouth of the sack (x, y, z of the top); the furrow runs along +y from (furrow_x, furrow_y0)."""
    g = tm.f("07", W("07", "grain"))
    s = tm.f("07", W("07", "So"))
    p = tm.f("07", W("07", "plant"))
    f_end = tm.f("07", 4.88)
    sack = Vector(sack)
    furrow_a = Vector((furrow_x, furrow_y0, bed_top))
    n_before = len(kit._problems)
    kit.require_reach("hand 07 (sack)", _shoulder(poses[g], 1), sack + Vector((0, 0, 0.15)))
    kit.require_reach("hand 07 (furrow)", _shoulder(poses[p + 17], 1), furrow_a)
    if len(kit._problems) > n_before:
        return None
    h = fh.hand("Hand07", 1, skin=SKIN, sleeve=SLEEVE[0], sleeve_dark=SLEEVE[1])
    down = Vector((0, 0, -1))

    def toward(f, target):
        d = Vector(target) - Vector(poses[f][0])
        d.z = 0
        return d.normalized()

    def rest(f, palm_up=False):
        m = _cam_matrix(poses[f])
        wrist = m @ Vector((0.16, -0.95, -0.22))          # below the frame edge (out, ~67 deg below the axis)
        fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
        return wrist, fwd, (Vector((0, 0, 1)) if palm_up else Vector((0, 0, -1)))

    # (frame, function -> (fist, fingers, palm normal))
    def carry(f):
        """Handful in the palm, hand in the lower half of the frame (moves along with the camera)."""
        m = _cam_matrix(poses[f])
        fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
        return m @ Vector((0.10, -0.30, -0.48)), fwd + down * 0.35, Vector((0, 0, 1)) - fwd * 0.5

    up = Vector((0, 0, 1))
    plan = [
        (tm.first("07"), lambda f: rest(f)),
        (g - 26, lambda f: rest(f)),
        (g - 8, lambda f: (sack + Vector((0, 0, 0.25)) - toward(f, sack) * 0.05, toward(f, sack) + down * 1.6,
                           -toward(f, sack))),
        (g, lambda f: (sack + Vector((0, 0, 0.15)) - toward(f, sack) * 0.03, toward(f, sack) + down * 1.3,
                       -toward(f, sack) + down * 0.3)),
        (g + 12, lambda f: (sack + Vector((0, 0, 0.28)) - toward(f, sack) * 0.16, toward(f, sack) + down * 0.5,
                            up - toward(f, sack) * 0.5)),
        (s + 2, carry),
        (p - 4, carry),
        (p + 3, lambda f: (furrow_a + Vector((0.07, -0.10, 0.17)), toward(f, furrow_a) + down * 0.45,
                           up - toward(f, furrow_a) * 0.4)),
        (p + 10, lambda f: (furrow_a + Vector((0.07, -0.06, 0.11)), toward(f, furrow_a) + down * 0.3,
                            Vector((-0.9, 0, 0.3)))),
        (p + 17, lambda f: (furrow_a + Vector((0.02, 0.0, 0.035)), toward(f, furrow_a) + down * 0.15, down)),
        (f_end, lambda f: (furrow_a + Vector((0.02, 0.32, 0.035)), toward(f, furrow_a) + down * 0.15, down)),
        (f_end + 20, lambda f: rest(f)),
        (tm.last("07"), lambda f: rest(f)),
    ]
    frames = list(range(plan[0][0], plan[-1][0] + 1))
    for f in frames:
        i = next(i for i, (k, _) in enumerate(plan) if k >= f)
        if plan[i][0] == f or i == 0:
            w, d, n = plan[i][1](f)
        else:
            (fa, pa), (fb, pb) = plan[i - 1], plan[i]
            u = _ease((f - fa) / (fb - fa))
            wa, da, na = pa(f)
            wb, db, nb = pb(f)
            w = wa.lerp(wb, u)
            qa, qb = fh.frame_quat(da, na), fh.frame_quat(db, nb)
            if qa.dot(qb) < 0:
                qb.negate()
            h.location = w
            h.rotation_quaternion = qa.slerp(qb, u)
            h.keyframe_insert("location", frame=f)
            h.keyframe_insert("rotation_quaternion", frame=f)
            continue
        fh.place(h, w, d, n, frame=f)
    _linear_all(h)
    sh = _shoulder_empty("Shoulder07", _shoulder(poses[frames[0]], 1))
    for f in frames[::2] + [frames[-1]]:
        sh.location = _shoulder(poses[f], 1)
        sh.keyframe_insert("location", frame=f)
    _linear_all(sh)
    _arm_sleeve("Arm07", h, sh, SLEEVE[0])
    grains = _grains("Grains07", h)
    # grains: appear at the grab (inside the sack, hidden by the hand), vanish pouring into the furrow (p+9 .. p+16)
    for f, sc in ((g - 2, 0.0), (g + 1, 1.0), (p + 9, 1.0), (p + 16, 0.0)):
        grains.scale = (sc,) * 3
        grains.keyframe_insert("scale", frame=f)
    _linear_all(grains)
    show_frames([h, sh], [(tm.first("07"), tm.last("07"))], total)
    return h


# ---------- vaca ----------

def build_cow(tm, total):
    """Cow on the east hill terrace (06, 'animals'): grazes head down, side-on to the camera."""
    hd = math.radians(40)
    fwd, side = Vector((math.cos(hd), math.sin(hd), 0)), Vector((-math.sin(hd), math.cos(hd), 0))
    hooves = [mk.COW + fwd * a + side * b for a in (0.75, -0.75) for b in (0.22, -0.22)]
    z = max(ps.hill_z(h.x, h.y) for h in hooves)
    c = cq.build("Cow06", (mk.COW.x, mk.COW.y, z), heading=hd, length=2.3)  # 3/4 side view, head to the right
    a, b = tm.first("06"), tm.last("06")
    cq.graze(c, a, b)
    show_frames(c.root, [(a, b)], total)
    return c


# ---------- child ----------

def fix_kids():
    """Child: the copies Kid0..Kid2 (Man at 1.2 m with Run) get a bigger head and narrow torso."""
    n = 0
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o.name.startswith("Kid") and o.name.endswith("Rig"):
            kidmod.childlike(SimpleNamespace(arm=o))
            n += 1
    return n


def build(tm, M, total, poses):
    if not ENABLED:
        return
    build_cow(tm, total)
    fix_kids()
    hands = hands_04(M)
    show_frames(hands, [(tm.first("04"), tm.last("04"))], total)
    hand_07(tm, poses, total, (mk.SACK.x, mk.SACK.y, 0.58), mk.FURROW_X, 2.55, 0.12)
