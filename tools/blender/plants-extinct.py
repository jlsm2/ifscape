"""Set for the plants-extinct script ("What if all plants went extinct?"): Mediterranean village square, daytime.

Run by 'python -m ifscape blender scripts/plants-extinct.json [--stills 1,410,2105]' (preview: IFSCAPE_PREVIEW=1).
CURRENT STAGE (2026-10-24): look-dev of the 3 hero frames in art.md section 5 (H1 f1, H2 f410, H3 f2105). The whole set,
the 4 plant states and the light are already final; the camera only has the poses of the 3 heroes (the full blockout of the
camera choreography has not been done yet).

States (only the plant changes; they switch on the cut, CONSTANT key on the scene property "plant_state"):
  NOW 01, 02, 12 | 1 WEEK 03-07 | 1 YEAR 08, 09 | YEARS 10, 11.
Fixed light: Sun 10:30, azimuth 140 deg, elevation 55 deg, energy 3.4, angle 1.5 deg, specular 0.45; sky as fill.
POV camera at 1.65 m, 24 mm lens (36 mm sensor at the height: 1280 px per radian).
"""

import json
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

import kit  # noqa: E402
import moon_models as mm  # noqa: E402
import plants_models as pm  # noqa: E402
import plants_markers as mk  # noqa: E402
import plants_build_a as pba  # noqa: E402
import plants_build_b as pbb  # noqa: E402
import plants_set as ps  # noqa: E402
import rigs  # noqa: E402
from kit import lin  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VOICE = json.loads((ROOT / "build" / "plants-extinct" / "voice.json").read_text(encoding="utf-8"))
SCENES = tuple(f"{i:02d}" for i in range(1, 13))
STATE_OF = {"01": 0, "02": 0, "03": 1, "04": 1, "05": 1, "06": 1, "07": 1, "08": 2, "09": 2, "10": 3, "11": 3,
            "12": 0}
NOW, WEEK, YEAR, YEARS = 0, 1, 2, 3
EYE = 1.65
LENS = 24.0

# hero frame poses: (frame, position, yaw degrees (+ = right/west), pitch degrees (+ = up))
TREE = ps.TREE_POS
H3_CAM = TREE + Vector((math.sin(math.radians(135)), math.cos(math.radians(135)), 0)) * 9.0  # 9 m a noroeste
HEROES = {
    "H1": (1, Vector((0.0, 0.0, EYE)), 0.0, -2.0),
    "H2": (410, Vector((0.0, 0.0, EYE)), 4.0, -2.0),
    "H3": (2105, Vector((H3_CAM.x, H3_CAM.y, EYE)), -45.0, -1.0),
}


def W(sid, word, nth=0):
    hits = [w["start"] for w in VOICE[sid]["words"] if w["word"].strip("?.,:;").lower() == word.lower()]
    return hits[nth]


class T:
    def __init__(self, tl):
        self.tl = tl

    def f(self, sid, t):
        return self.tl.at(sid) + int(round(t * self.tl.fps))

    def first(self, sid):
        return self.tl.at(sid)

    def last(self, sid):
        return self.tl.at(sid, 1.0) - 1


def objs_of(root):
    return [root, *root.children_recursive] if hasattr(root, "children_recursive") else [root]


def show_in(tm, roots, states):
    """Turns the object (and all children) on only in the scenes whose state is in 'states' (on/off at the cut)."""
    roots = roots if isinstance(roots, (list, tuple)) else [roots]
    for root in roots:
        for o in objs_of(root):
            for sid in SCENES:
                o.hide_render = STATE_OF[sid] not in states
                o.keyframe_insert("hide_render", frame=tm.first(sid))


def show_frames(roots, ranges, total):
    """Turns on only within the frame intervals [(a, b)] (inclusive)."""
    roots = roots if isinstance(roots, (list, tuple)) else [roots]
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for root in roots:
        for o in objs_of(root):
            for f in marks:
                o.hide_render = not any(a <= f <= b for a, b in ranges)
                o.keyframe_insert("hide_render", frame=f)


def key_state(tm):
    sc = bpy.context.scene
    for sid in SCENES:
        sc[pm.STATE] = float(STATE_OF[sid])
        sc.keyframe_insert(f'["{pm.STATE}"]', frame=tm.first(sid))
    for fc in rigs._fcurves(sc.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def look_post(scene):
    """Channel recipe with the daytime strength from art.md section 2.2: bloom threshold 1.0 strength 0.15; vignette 14%."""
    ng = scene.compositing_node_group
    for nd in ng.nodes:
        if nd.bl_idname == "CompositorNodeGlare":
            nd.inputs["Strength"].default_value = 0.15
        if nd.bl_idname == "ShaderNodeMix" and nd.blend_type == "MULTIPLY":
            nd.inputs[0].default_value = 0.14


# ---------- camera (choreography of the 12 scenes, 2026-10-24) ----------
# Pose keys: (frame, position, yaw degrees (+ = right/west), pitch degrees (+ = up), easing of the segment that
# ARRIVES at this key). Frames = triggers from direction.md (v4 voice). Between keys the pose is computed in Python and
# written on EVERY frame (LINEAR): io = ease-in-out, out = ease-out, in = ease-in, lin = linear.
P0 = (0.0, 0.0, EYE)
SIDE = (2.2, 0.4, EYE)          # half a step to the right, outside the awning (x > 1.45): only from here the sky appears clean
SKY = (42.0, 45.0)              # sky bridge (02->03 and 11->12): sky only; the crown stays on the left (bearing < 19 deg), west
                                # hill on the right (bearing > 58 deg)
TOWER_VIEW = (74.0, 12.0)       # 05 "this hill": tower at the top of the west hill
C11 = Vector((3.4, 13.0, 0.0))  # 11: 5.8 m from H3, outside the dry crown (x > 2.3), branch and fungi at 5-7 m
C11_EYE = 1.2                   # half crouched: below this the parapet (0.5 m) hides the sea and the boats

CAM_KEYS = [
    # 01 cover (H1 pose)
    (1, P0, 0, -2, "lin"), (88, P0, 0, -2, "lin"),
    # 02 half step; bush 125, grass 167, sea 238; walks to the right end; So 310, mushrooms 319 (holds 0.4 s)
    # on the firewood; rises to the sky 329-359 (1.0 s; outside the awning), stopped 359-361 (02 lasts 9.1 s: last frame 361)
    (125, (-0.3, 0.1, EYE), -12, -4, "io"), (167, (-0.15, 0.15, EYE), -6, -8, "io"),
    (238, (0.0, 0.1, EYE), -3, -5, "io"), (256, (0.15, 0.12, EYE), 15, -3, "io"),
    (305, (1.9, 0.35, EYE), 13, -4, "io"), (320, SIDE, -16, -24, "out"),
    (329, SIDE, -16, -24, "lin"), (359, SIDE, *SKY, "io"), (361, SIDE, *SKY, "lin"),
    # 03 1 WEEK: same sky until later 376; descends (ease-out) and returns behind the stall; hill 395; H2 410; straw 434
    (376, SIDE, *SKY, "lin"), (405, (0.25, 0.05, EYE), 8, 0, "out"), (420, P0, 4, -2, "io"),
    (444, (0.0, 0.05, EYE), 8, -26, "io"), (480, (0.0, 0.1, 1.62), 9, -28, "io"),
    # 04 Even so 473 -> hands; breathe 512 (rises 6 cm, added); charcoal 555 -> brazier
    (500, (0.0, 0.15, 1.6), 0, -42, "io"), (558, (0.0, 0.15, 1.6), 0, -41, "lin"),
    (580, (-0.05, 0.1, 1.6), -20, -30, "io"), (626, (-0.05, 0.1, 1.6), -21, -29, "lin"),
    # 05 Both 622 opens to the square; step to the right end; billions 725 sky (crown at the bottom edge);
    # rotted 845; barely 898; climbing 963 descends 1.0 s to the tower (stopped 993); this hill 1008 push-in 3% (lens)
    (632, (-0.05, 0.1, 1.6), -21, -29, "lin"), (665, (0.2, 0.1, EYE), 3, -2, "io"),
    (710, SIDE, 8, -1, "io"),
    (735, SIDE, 25, 38, "io"), (855, SIDE, 27, 37, "io"), (908, SIDE, 28, 37.5, "io"), (973, SIDE, 28, 37, "io"),
    (1003, SIDE, *TOWER_VIEW, "io"), (1052, SIDE, *TOWER_VIEW, "lin"),
    # 06 look 1053 -> counter (right end); Of every 1096: 1 step and looks along the stall (to the left)
    (1063, SIDE, *TOWER_VIEW, "lin"), (1090, (2.25, 0.35, 1.6), -25, -40, "io"),
    (1106, (2.25, 0.35, 1.6), -25, -40, "lin"),
    (1142, (2.6, 0.45, 1.25), -55, -14, "io"), (1300, (2.42, 0.45, 1.24), -57, -15, "io"),
    (1358, (2.38, 0.45, 1.24), -57, -15, "io"),
    # 07 (revision of part A, 2026-10-24, approved): walks to the sack and bends (grain 1419); at So (1445)
    # goes to the flower bed and kneels (eye at 0.88 m); plant 1464; on the hold stands up and steps back 1.4 m to P8, stopped at 1540
    # (matched cut 07 -> 08: same matrix 1540-1564); 08 opens at P8 and pushes in to the grains
    (1415, (-1.1, 0.34, 1.55), -58, -32, "io"), (1429, (-1.55, 0.40, 1.40), -56, -38, "io"),
    (1445, (-1.55, 0.40, 1.42), -57, -37, "lin"), (1471, (-2.38, 2.22, 0.88), -36, -46, "io"),
    (1505, (-2.4, 2.24, 0.87), -36, -47, "lin"),
    (1540, (-1.6, 1.05, 1.42), -29.5, -29.5, "io"), (1564, (-1.6, 1.05, 1.42), -29.5, -29.5, "lin"),
    # 08 1 YEAR: nothing 1587 stopped; seeds 1645 push-in to the grains; too 1698 rises and turns 60 deg to the right (1.3 s)
    (1610, (-1.6, 1.05, 1.42), -29.5, -29.5, "lin"), (1670, (-1.78, 1.38, 1.3), -30, -33, "io"),
    (1708, (-1.78, 1.38, 1.3), -30, -33, "lin"),
    # 09 empty stall (empty 1749); fish 1785 pushes in to the crate; calorie 1911; whip pan to the left 1964-1969
    (1747, (-0.1, 0.0, EYE), 18, -28, "io"), (1795, (-0.1, 0.0, EYE), 18, -28, "lin"),
    (1825, (0.3, 0.35, 1.55), 31, -27.6, "io"), (1974, (0.32, 0.38, 1.55), 31, -28, "lin"),
    (1978, (0.32, 0.38, 1.55), 5, -18, "in"),
    # 10 YEARS: enters via the whip pan (ease-out 0.3 s) 9 m northwest of the trunk; tree 2014; branch 2078; H3 2105;
    # mushrooms 2118 tilts to the branch on the ground and starts walking toward it (2140)
    (1979, (H3_CAM.x, H3_CAM.y, EYE), -10, -3, "lin"), (1989, (H3_CAM.x, H3_CAM.y, EYE), -43, -1, "out"),
    (2024, (H3_CAM.x, H3_CAM.y, EYE), -44, 0, "io"), (2115, (H3_CAM.x, H3_CAM.y, EYE), -45, -1, "io"),
    (2128, (H3_CAM.x, H3_CAM.y, EYE), -45, -1, "lin"), (2150, (H3_CAM.x, H3_CAM.y, EYE), -38, -8, "io"),
    # 11 walks 5.8 m to the side of the branch and half crouches, looking along it to the sea; Some 2230; fish 2278;
    # mushrooms 2293; Nobody 2358 tilts to the sky (1.2 s), stopped 2394-2406
    (2170, tuple(H3_CAM.lerp(C11, 0.1).to_tuple()[:2]) + (EYE,), -38, -6, "in"),
    (2255, tuple(H3_CAM.lerp(C11, 0.9).to_tuple()[:2]) + (1.45,), -38, -6, "lin"),
    (2278, (C11.x, C11.y, C11_EYE), -38, -7, "out"), (2368, (C11.x, C11.y, C11_EYE), -38, -7, "lin"),
    (2404, (C11.x, C11.y, C11_EYE), *SKY, "io"), (2416, (C11.x, C11.y, C11_EYE), *SKY, "lin"),
    # 12 our world: opens on the same sky (outside the awning), descends (ease-out) to the EXACT pose of 01 by Earth 2450;
    # lost 2462 pan ~5 deg to the right to the line forest x terraces, stopped at half 2486; cools and darkens 2578-2623
    (2417, SIDE, *SKY, "lin"), (2423, SIDE, *SKY, "lin"), (2460, P0, 0, -2, "out"), (2472, P0, 0, -2, "lin"),
    (2496, P0, 5, -2, "io"), (2704, P0, 5, -2, "lin"),
]
CUTS = (362, 1554, 1979, 2417)                 # first frame of each new shot (= tm.first of the scene; 10 opens at 1979)
STILL = [(1, 1, 18), (338, 382, 0), (1536, 1572, 0), (2108, 2122, 0), (2398, 2430, 0), (410, 428, 0)]
LENS_KEYS = [(1, 24.0), (1018, 24.0), (1052, 24.72), (1063, 24.72), (1090, 24.0)]
BREATHE = (522, 555, 0.06)


def _ease(u, kind):
    u = max(0.0, min(1.0, u))
    if kind == "io":
        return u * u * (3 - 2 * u)
    if kind == "out":
        return 1 - (1 - u) ** 3
    if kind == "in":
        return u ** 3
    return u


def _sway_weight(f):
    w = 1.0
    for a, b, ramp in STILL:
        if a == b == 1:
            w = min(w, min(1.0, (f - 1) / ramp))
            continue
        r = 10
        if a <= f <= b:
            return 0.0
        if a - r < f < a:
            w = min(w, (a - f) / r)
        if b < f < b + r:
            w = min(w, (f - b) / r)
    return max(0.0, w)


def camera_poses(total):
    """Pose of each frame 1..total: (position, yaw, pitch, roll) in degrees, already with hand sway and breathing."""
    keys = CAM_KEYS
    out = {}
    dist = 0.0
    prev = None
    for f in range(1, total + 1):
        k1 = next(i for i, k in enumerate(keys) if k[0] >= f)
        if keys[k1][0] == f or k1 == 0:
            fr, pos, yaw, pitch, _ = keys[k1]
            p, y, pt = Vector(pos), yaw, pitch
        else:
            a, b = keys[k1 - 1], keys[k1]
            if b[0] in CUTS and f < b[0]:          # does not interpolate across the cut (the new shot starts at b)
                p, y, pt = Vector(a[1]), a[2], a[3]
            else:
                u = _ease((f - a[0]) / (b[0] - a[0]), b[4])
                p = Vector(a[1]).lerp(Vector(b[1]), u)
                y, pt = a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u
        # step: rises and falls 1.5 cm per 0.7 m stride when the camera walks
        if prev is not None and f not in CUTS:
            step = (p.xy - prev.xy).length
            dist += step
            v = step * 30
            p = p + Vector((0, 0, min(1.0, v / 1.0) * 0.015 * (abs(math.sin(math.pi * dist / 0.7)) - 0.5)))
        prev = Vector(p)
        if BREATHE[0] <= f <= BREATHE[1]:
            p = p + Vector((0, 0, BREATHE[2] * math.sin(math.pi * (f - BREATHE[0]) / (BREATHE[1] - BREATHE[0]))))
        t = (f - 1) / 30.0
        w = _sway_weight(f)
        y += w * (0.25 * math.sin(2 * math.pi * 0.31 * t) + 0.12 * math.sin(2 * math.pi * 0.73 * t + 1.0))
        pt += w * (0.18 * math.sin(2 * math.pi * 0.43 * t + 2.0) + 0.08 * math.sin(2 * math.pi * 0.97 * t))
        roll = w * 0.12 * math.sin(2 * math.pi * 0.27 * t + 0.5)
        out[f] = (p, y, pt, roll)
    return out


def pose_matrix(pose):
    p, yaw, pitch, roll = pose
    rot = Euler((math.radians(90 + pitch), math.radians(roll), math.radians(-yaw)), "XYZ")
    return Matrix.Translation(p) @ rot.to_matrix().to_4x4()


def _write_curve(id_data, path, index, frames, values):
    ad = id_data.animation_data or id_data.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{id_data.name}Action")
    act = ad.action
    if ad.action_slot is None:
        ad.action_slot = act.slots.new(id_type=id_data.id_type, name=id_data.name) if not act.slots else act.slots[0]
    import bpy_extras.anim_utils as au
    bag = au.action_ensure_channelbag_for_slot(act, ad.action_slot)
    fc = bag.fcurves.find(path, index=index) or bag.fcurves.new(path, index=index)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    fc.keyframe_points.foreach_set("co", [c for fv in zip(frames, values) for c in fv])
    fc.keyframe_points.foreach_set("interpolation", [rigs.LINEAR] * len(frames))
    fc.update()


def build_camera(tm, poses):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.lens = LENS
    cam.data.sensor_fit = "AUTO"
    cam.data.sensor_width = 36.0
    cam.data.clip_start, cam.data.clip_end = 0.05, 20000.0
    cam.rotation_mode = "XYZ"
    frames = sorted(poses)
    for i in range(3):
        _write_curve(cam, "location", i, frames, [poses[f][0][i] for f in frames])
    rots = [(math.radians(90 + poses[f][2]), math.radians(poses[f][3]), math.radians(-poses[f][1])) for f in frames]
    for i in range(3):
        _write_curve(cam, "rotation_euler", i, frames, [r[i] for r in rots])
    lf = list(range(1, frames[-1] + 1))
    lv = []
    for f in lf:
        k = next(i for i, k in enumerate(LENS_KEYS) if k[0] >= f) if f <= LENS_KEYS[-1][0] else None
        if k is None:
            lv.append(LENS_KEYS[-1][1])
        elif LENS_KEYS[k][0] == f or k == 0:
            lv.append(LENS_KEYS[k][1])
        else:
            a, b = LENS_KEYS[k - 1], LENS_KEYS[k]
            lv.append(a[1] + (b[1] - a[1]) * _ease((f - a[0]) / (b[0] - a[0]), "io"))
    _write_curve(cam.data, "lens", 0, lf, lv)
    # whip pan 09 -> 10: with blur (shutter at the start of the frame), the last frame of 09 must keep spinning
    # to the end of the frame, not move to the pose of 10: extra key at 1978.97 (extrapolated) and CONSTANT
    for fc in rigs._fcurves(cam.animation_data.action):
        a = fc.evaluate(1977)
        b = fc.evaluate(1978)
        kp = fc.keyframe_points.insert(1978.97, b + (b - a) * 0.97, options={"FAST"})
        kp.interpolation = "CONSTANT"
        fc.update()
    return cam


def build_passages(scene, total):
    """Passes of the jump cuts: light-leak by exposure (+0.5 EV at the peak, 6 to 8 frames) on 02->03,
    07->08 and 11->12; motion blur only on the whip pan 09->10; at the end of 12 the image cools and darkens to ~55%."""
    vs = scene.view_settings
    keys = {1: 0.0, total: 0.0}
    for c, n in ((362, 6), (1554, 6), (2417, 8)):
        half = n // 2
        for j in range(n):
            f = c - half + j
            u = (j + 0.5) / n
            keys[f] = 0.5 * math.sin(math.pi * u)
        keys[c - half - 1] = 0.0
        keys[c - half + n] = 0.0
    for f in range(2588, 2634):
        keys[f] = math.log2(1 - 0.45 * _ease((f - 2588) / 45, "io"))
    for f in range(2634, total + 1):
        keys[f] = math.log2(0.55)
    fr = sorted(keys)
    vs.exposure = 0.0
    _write_curve(scene, "view_settings.exposure", 0, fr, [keys[f] for f in fr])
    try:                                       # cool down at the end: white balance (Blender 4.3+)
        vs.use_white_balance = True
        wb = [(1, 6500.0), (2588, 6500.0), (2633, 5600.0), (total, 5600.0)]
        ff = list(range(1, total + 1))
        vals = []
        for f in ff:
            if f <= 2588:
                vals.append(6500.0)
            elif f >= 2633:
                vals.append(5600.0)
            else:
                vals.append(6500.0 - 900.0 * _ease((f - 2588) / 45, "io"))
        _write_curve(scene, "view_settings.white_balance_temperature", 0, [1, *range(2588, 2634), total],
                     [6500.0, *[vals[f - 1] for f in range(2588, 2634)], 5600.0])
    except (AttributeError, TypeError) as e:
        print("white balance unavailable:", e)
    try:                                       # blur only on the whip pan (f 1976-1981), shutter at the start of the frame
        r = scene.render
        r.motion_blur_shutter = 0.5
        r.motion_blur_position = "START"
        _write_curve(scene, "render.use_motion_blur", 0, [1, 1975, 1976, 1981, 1982, total],
                     [0, 0, 1, 1, 0, 0])
        fc = [c for c in rigs._fcurves(scene.animation_data.action) if c.data_path == "render.use_motion_blur"][0]
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    except (AttributeError, TypeError) as e:
        print("motion blur unavailable:", e)


# ---------- people ----------

COLORS = [  # clothes without green and without straw-beige (art.md section 1.2): terracotta, blue, off-white, navy
    {"Shirt": "#B8583A", "Pants": "#2A3446", "Skin": "#C8916A", "Hair": "#2A1E16", "HairBase": "#2A1E16"},
    {"Shirt": "#E8E4DA", "Pants": "#3E6A8C", "Skin": "#B07850", "Hair": "#1A1A1A", "HairBase": "#1A1A1A"},
    {"Shirt": "#2E3A60", "Pants": "#E0DCD2", "Skin": "#E0B08A", "Hair": "#4A3424", "HairBase": "#4A3424"},
    {"Shirt": "#4A7AB0", "Pants": "#2A2E3A", "Skin": "#8D5A3C", "Hair": "#1A1A1A", "HairBase": "#1A1A1A"},
    {"Shirt": "#9A3A34", "Pants": "#3A4252", "Skin": "#C8916A", "Hair": "#8A6A4A", "HairBase": "#8A6A4A"},
]
for c in COLORS:
    c.update({"Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"})


def person(key, name, k, height, location, heading):
    r = rigs.spawn(key, name, height=height, location=location, heading=heading)
    rigs.paint(r, COLORS[k % len(COLORS)])
    return r


def walk_line(rig, frames, start, heading, speed, phase=0.0):
    """Walks in a straight line (foot planted: the Walk time matches the distance), like town_cast.walk_line."""
    d = Vector((math.cos(heading), math.sin(heading), 0))
    pos = [Vector((*start, 0.0)) + d * speed * (f - frames[0]) / 30 for f in frames]
    rigs.key_root(rig, frames, pos, [heading] * len(frames))
    per = rigs.planted_speed(rig, "Walk", ["Foot.L", "Foot.R"]) * rig.scale
    a0, a1 = rig.t.actions["Walk"].frame_range
    s0 = a0 + phase * (a1 - a0)
    rigs.timed(rig, "Walk", frames, [s0 + speed / 30 * (f - frames[0]) / per for f in frames])


def walk_loop(rig, frames, center, radii, speed, phase=0.0, ccw=True, action="Walk"):
    """Walks in a closed ellipse inside the square (steps matched to the distance, like walk_line): the people stay
    in the square for the whole scene without crossing a house or leaving the paving."""
    cx, cy = center
    rx, ry = radii
    n = 400
    pts = [Vector((cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n), 0.0))
           for k in range(n + 1)]
    if not ccw:
        pts.reverse()
    acc = [0.0]
    for p, q in zip(pts, pts[1:]):
        acc.append(acc[-1] + (q - p).length)
    L = acc[-1]
    pos, hd = [], []
    j = 0
    for f in frames:
        d = (phase * L + speed * (f - frames[0]) / 30.0) % L
        j = 0 if d < acc[j] else j
        while j < n - 1 and acc[j + 1] < d:
            j += 1
        u = (d - acc[j]) / max(acc[j + 1] - acc[j], 1e-9)
        pos.append(pts[j].lerp(pts[j + 1], u))
        t = pts[j + 1] - pts[j]
        hd.append(math.atan2(t.y, t.x))
    rigs.key_root(rig, frames, pos, hd)
    per = rigs.planted_speed(rig, action, ["Foot.L", "Foot.R"]) * rig.scale
    a0, a1 = rig.t.actions[action].frame_range
    s0 = a0 + (phase * 7.0) % 1.0 * (a1 - a0)
    rigs.timed(rig, action, frames, [s0 + speed / 30 * (f - frames[0]) / per for f in frames])


# loops (center, radii, speed, direction) inside the square: outside the plane tree bed (r 2.6), the hedges, the
# firewood and the camera positions (y >= 5); nobody seated nor looking at the counter (risk of "implied hunger")
LOOPS = [
    ("woman", 0, 1.66, (4.5, 11.0), (3.5, 2.6), 1.15, True),
    ("man", 1, 1.78, (9.0, 15.5), (6.5, 2.6), 1.25, False),
    ("man", 3, 1.74, (3.0, 6.5), (4.0, 1.4), 1.1, True),
    ("woman", 2, 1.62, (-5.5, 17.6), (3.2, 1.2), 1.0, False),
]
CHILD = ("man", 4, 1.2, (12.5, 9.0), (3.0, 2.0), 2.4, True)


def build_people(tm, total):
    """NOW (01-02 and 12) and 1 WEEK (03-07): the same 4 people (same clothes) walking in loops in the square and 1 child
    running (marker: the Quaternius Man at child scale, Run action). 1 YEAR (09): 2 people going down
    to the sea along the parapet. YEARS: 1 person at the little campfire."""
    out = []
    windows = [(1, tm.last("02")), (tm.first("03"), tm.last("07")), (tm.first("12"), total)]
    for g, (a, b) in enumerate(windows):
        frames = list(range(a, b + 1))
        for j, (key, k, h, c, r, sp, ccw) in enumerate(LOOPS):
            rr = person(key, f"P{g}{j}", k, h, (*c, 0.0), 0.0)
            walk_loop(rr, frames, c, r, sp, phase=0.17 + 0.29 * j + 0.11 * g, ccw=ccw)
            show_frames(rr.root, [(a, b)], total)
            out.append(rr)
        key, k, h, c, r, sp, ccw = CHILD
        kid = person(key, f"Kid{g}", k, h, (*c, 0.0), 0.0)
        walk_loop(kid, frames, c, r, sp, phase=0.4 + 0.2 * g, ccw=ccw, action="Run")
        show_frames(kid.root, [(a, b)], total)
        out.append(kid)
    # 1 YEAR (09): two going down to the sea stairs along the parapet (baskets: still to be modeled)
    a, b = tm.first("09"), tm.last("09")
    for j, (key, k, h, y, x0, sp) in enumerate((("man", 0, 1.76, 18.7, 4.8, 1.05),
                                                ("woman", 2, 1.62, 18.95, 3.6, 1.0))):
        rr = person(key, f"Y{j}", k, h, (x0, y, 0.0), 0.0)
        walk_line(rr, list(range(a, b + 1)), (x0, y), 0.0, sp, phase=0.5 * j)
        show_frames(rr.root, [(a, b)], total)
        out.append(rr)
    # YEARS: person crouching/standing stirring the pot at the little campfire (Idle), looking at the fire
    fire = Vector((-6.5, 14.0, 0.0))
    p = person("man", "Cook", 4, 1.74, (fire.x - 0.75, fire.y - 0.35, 0.0), math.atan2(0.35, 0.75))
    rigs.loop(p, "Idle", tm.first("10") - 30, tm.last("11") + 30, rate=0.8)
    show_in(tm, p.root, (YEARS,))
    out.append(p)
    return out, fire


def build_wind(tree, total):
    """Wind in the crown (all phases: dead plant sways like the living one): slow rotation of ~0.25 deg around the foot of the
    trunk (at the top ~6 cm), two low frequencies; zero at frame 1 (cover)."""
    frames = list(range(1, total + 1, 2))
    for k, o in enumerate(tree.canopies.values()):
        o.rotation_mode = "XYZ"
        for axis, (amp, fr, ph) in enumerate(((0.25, 0.23, 0.0), (0.2, 0.17, 1.3))):
            vals = [math.radians(amp) * (math.sin(2 * math.pi * fr * (f - 1) / 30 + ph + 0.4 * k) -
                                         math.sin(ph + 0.4 * k)) for f in frames]
            _write_curve(o, "rotation_euler", axis, frames, vals)


def build_markers(tm, M, total, poses):
    """Markers (MK_*) of the pieces still to be modeled, only at the final position (plants_markers.py)."""
    # Marker groups that a final modeling module replaces: module A or B adds the group name
    # to plants_build_a.REPLACED or plants_build_b.REPLACED (groups: table_ext, shed, bed, hands, cow, tower_trail,
    # amber, leaves, hand07). Each module creates its models in build(tm, M, total, poses).
    done = set(pba.REPLACED) | set(pbb.REPLACED)
    if "table_ext" not in done:
        ext = mk.build_table_ext(M)
        show_in(tm, ext, (NOW, WEEK, YEAR))
    if "shed" not in done:
        mk.build_shed(M)
    if "bed" not in done:
        bed = mk.build_bed(M)
        show_in(tm, bed.wet[:1], (NOW, WEEK))
        show_in(tm, bed.wet[1:], (WEEK,))
        show_in(tm, bed.dry, (YEAR, YEARS))
        show_in(tm, bed.seeds, (YEAR,))
    if "hands" not in done:
        hands = mk.build_hands(M)
        show_frames(hands, [(tm.first("04"), tm.last("04"))], total)
    if "cow" not in done:
        cow = mk.build_cow()
        show_frames(cow, [(tm.first("06"), tm.last("06"))], total)
    if "tower_trail" not in done:
        mk.build_tower_trail(M)
    if "amber" not in done:
        band, ring = mk.build_amber_band(M, 1211, 1246, 1267, tm.last("06"))
        show_frames(band, [(1211, tm.last("06"))], total)
        show_frames(ring, [(1267, tm.last("06"))], total)
    if "leaves" not in done:
        leaves = mk.build_leaf_burst(Vector(SIDE), 27.0, 37.0, 855, 895, random.Random(12))
        show_frames(leaves, [(855, 895)], total)
    pba.build(tm, M, total, poses)
    pbb.build(tm, M, total, poses)
    if "hand07" in done:
        return
    # hand of 07: takes a handful from the sack (grain 1419) and buries it in the furrow (plant 1464 to 1495)
    hand = mk.build_hand_07(M)

    def rest(f):
        return pose_matrix(poses[f]) @ Vector((0.2, -0.3, -0.5))

    plan = [(1405, None), (1422, Vector((mk.SACK.x, mk.SACK.y, 0.66))), (1429, Vector((mk.SACK.x, mk.SACK.y, 0.6))),
            (1440, Vector((mk.SACK.x + 0.1, mk.SACK.y, 0.8))), (1457, None),
            (1476, Vector((mk.FURROW_X, 2.6, 0.32))), (1486, Vector((mk.FURROW_X, 2.65, 0.15))),
            (1505, Vector((mk.FURROW_X, 2.95, 0.15))), (1522, None)]
    frames, vals = list(range(1405, 1523)), []
    for f in frames:
        i = next(i for i, (k, _) in enumerate(plan) if k >= f)
        if plan[i][0] == f or i == 0:
            v = plan[i][1] if plan[i][1] is not None else rest(f)
        else:
            (fa, va), (fb, vb) = plan[i - 1], plan[i]
            va = va if va is not None else rest(f)
            vb = vb if vb is not None else rest(f)
            v = va.lerp(vb, _ease((f - fa) / (fb - fa), "io"))
        vals.append(v)
    for i in range(3):
        _write_curve(hand, "location", i, frames, [v[i] for v in vals])
    show_frames(hand, [(1408, 1520)], total)


# ---------- stall and food ----------

STALL_AT = Vector((0.0, 0.85, 0.0))


def build_stall(tm, M, rnd):
    st = pm.stall("Stall", tuple(STALL_AT), M)
    show_in(tm, st.root, (NOW, WEEK, YEAR))
    # collapsed stall: does NOT exist (final decision of 2026-10-24, option (a) of direction.md)
    top = st.top
    # 2nd row (near the vendor) and 1st row (front): fruit, cheese, ham, flour, bread
    crates = [(0.0, 1.4, 0), (0.52, 1.4, 1), (1.04, 1.4, 2), (1.56, 1.4, 3)]
    fresh, rotten, boxes = [], [], []
    for k, (x, y, kind) in enumerate(crates):
        root, fo = pm.fruit_crate(f"Crate{k}", (x, y, top), M, M["fruit"], rnd, kind=kind)
        fresh.append(fo)
        boxes += [o for o in root.children if o.name.endswith("Box")]
        _, ro = pm.fruit_crate(f"CrateRot{k}", (x, y, top), M, M["fruit_rot"], rnd, rotten=True, kind=kind)
        ro.parent.hide_render = True
        for o in ro.parent.children:
            if o is not ro:
                o.hide_render = True
                bpy.data.objects.remove(o, do_unlink=True)
        ro.parent = root
        ro.location = (0, 0, 0)
        rotten.append(ro)
    show_in(tm, fresh, (NOW,))
    show_in(tm, rotten, (WEEK,))
    show_in(tm, boxes, (NOW, WEEK))       # 1 YEAR: empty stall (only the fish crate)
    # cheese, ham, flour sack and bread (unchanged in 1 WEEK; gone in 1 YEAR)
    food = []
    cheese = pm.obj_from("Cheese", kit._prism_geo(10, 0.13, 0.13, 0.09, oz=top, ox=1.45, oy=1.1), [M["cheese"]])
    ham = pm.obj_from("Ham", kit.tube_geo([(1.75, 1.0, top + 0.07), (1.9, 1.3, top + 0.08)], [0.07, 0.04], n=7),
                      [M["ham"]])
    sack = pm.obj_from("FlourSack", kit._prism_geo(8, 0.15, 0.12, 0.3, oz=top, ox=1.0, oy=1.05), [M["sack"]])
    flour = pm.obj_from("Flour", pm.lumpy_ico(0.11, (1.0, 1.05, top + 0.31), (1, 1, 0.45), rnd, 0.05), [M["flour"]])
    beans = pm.obj_from("Beans", kit._prism_geo(10, 0.09, 0.12, 0.07, oz=top, ox=1.95, oy=1.45), [M["terracotta"]])
    bread = pm.obj_from("Bread", pm.lumpy_ico(0.08, (1.7, 1.05, top + 0.05), (1.6, 1.0, 0.6), rnd, 0.05),
                        [M["bread"]])
    food += [cheese, ham, sack, flour, beans, bread]
    show_in(tm, food, (NOW, WEEK))
    # flies on the soft fruit (1 WEEK): 4 dark 1 cm points flying low, slow noise
    flies = []
    for k in range(4):
        fly = pm.obj_from(f"Fly{k}", kit._gem_geo(0.008, stretch=0.7), [M["fly"]])
        fly.visible_shadow = False
        a, b = tm.first("03"), tm.last("07")
        c = Vector((crates[k % 2][0] + rnd.uniform(-0.15, 0.15), crates[k % 2][1] + rnd.uniform(-0.1, 0.1),
                    top + 0.16))
        ph = rnd.uniform(0, 6.28)
        for f in range(a, b + 1, 2):
            t = (f - a) / 30.0
            fly.location = c + Vector((0.09 * math.sin(2.3 * t + ph), 0.07 * math.sin(3.1 * t + 2 * ph),
                                       0.04 * math.sin(4.7 * t + ph)))
            fly.keyframe_insert("location", frame=f)
        flies.append(fly)
    show_in(tm, flies, (WEEK,))
    # fish crate (1 YEAR): in the corner of the stall
    fish = pm.fish_crate("FishCrate", (0.85, 1.25, top), M, rnd)
    show_in(tm, fish, (YEAR,))
    # table brazier (left corner): lit NOW/WEEK, weak ember 1 YEAR, cold YEARS (on the ground, fallen)
    br = pm.brazier("Brazier", (-0.6, 1.4, top), M, rnd)
    show_in(tm, br.root, (NOW, WEEK, YEAR))
    show_in(tm, br.flame, (NOW, WEEK))
    em = kit.principled(M["ember"]).inputs["Emission Strength"]
    for sid in SCENES:
        em.default_value = 0.45 if STATE_OF[sid] == YEAR else 1.0
        em.keyframe_insert("default_value", frame=tm.first(sid))
    for fc in rigs._fcurves(M["ember"].node_tree.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    return st


def build_woodpile(tm, M, rnd):
    """Firewood against the low wall, on the right behind the stall (NOW, WEEK full; YEAR half; YEARS gone)."""
    wall = kit.box_span("WoodWall", 0.55, 1.6, 2.95, 3.3, 0.0, 1.1, M["stone"])
    full = pm.woodpile("Woodpile", (1.05, 2.4, 0.0), M, rnd, rows=8, per_row=8)
    show_in(tm, full.root, (NOW, WEEK))
    half = pm.woodpile("WoodpileHalf", (1.05, 2.4, 0.0), M, random.Random(9), rows=8, per_row=8, half=True)
    show_in(tm, half.root, (YEAR,))
    stain = pm.obj_from("WoodStain", ([(0.5, 2.35, 0.005), (1.6, 2.35, 0.005), (1.6, 2.92, 0.005),
                                       (0.5, 2.92, 0.005)], [(0, 1, 2, 3)]), [pm.fixed_mat("Stain", "#8A7E6C")])
    show_in(tm, stain, (YEARS,))
    return wall


# ---------- square: flower bed, grass, hedges, pots ----------

def build_beds(tm, M, rnd, tufts):
    """Plane tree bed (0.3 m stone ring, soil, tufts) and strip of grass at the foot of the parapet."""
    out = []
    n = 16
    R = 2.6
    ring = [kit._box_geo(2 * math.pi * R / n + 0.02, 0.28, 0.32, -math.pi * R / n, -0.14, 0) for _ in range(n)]
    parts = []
    for k, g in enumerate(ring):
        a = 2 * math.pi * k / n
        parts.append(kit.xform_geo(g, Matrix.Translation((TREE.x + R * math.cos(a), TREE.y + R * math.sin(a), 0)) @
                                   Matrix.Rotation(a + math.pi / 2, 4, "Z")))
    v, f, _ = kit.merge(*parts)
    out.append(pm.obj_from("BedCurb", (v, f), [M["stone"]]))
    soil = pm.obj_from("BedSoil", kit._prism_geo(16, R - 0.1, R - 0.1, 0.24, ox=TREE.x, oy=TREE.y), [M["soil"]])
    strip = pm.obj_from("StripSoil", kit._box_geo(17.0, 0.7, 0.12, -4.5, ps.PLAZA[3] - 0.75, 0.0), [M["soil"]])
    out += [soil, strip]
    # tufts by GN (alive/dry/gray in the first 3 states; sparse stumps in YEARS)
    full = ps.scatter_group("TuftsFull", tufts, 0.16, 30.0, 3, (0.8, 1.25))
    sparse = ps.scatter_group("TuftsSparse", tufts, 0.4, 5.0, 4, (0.35, 0.6))
    for src in (soil, strip):
        c1 = ps.carrier(f"{src.name}Tufts", src, full)
        show_in(tm, c1, (NOW, WEEK, YEAR))
        c2 = ps.carrier(f"{src.name}Stubs", src, sparse)
        show_in(tm, c2, (YEARS,))
    # hedge on the east side of the square and in the left corner of the stall
    hedges = []
    for k, (x, y, sx, sy) in enumerate(((-8.2, 1.0, 0.9, 8.0), (-3.6, 6.4, 1.2, 2.4))):
        geos = []
        nb = int(max(sx, sy) / 0.55)
        for j in range(nb):
            u = (j + 0.5) / nb
            c = (x + (u - 0.5) * sx if sx > sy else x, y + (u - 0.5) * sy if sy >= sx else y, 0.45)
            geos.append(pm.lumpy_ico(0.5, c, (1.0, 1.0, 0.95), rnd, 0.22))
        v, f, _ = kit.merge(*geos)
        h = pm.obj_from(f"Hedge{k}", (v, f), [M["hedge"]])
        hedges.append(h)
    # pots with flowers near the houses and at the ends of the parapet
    pots = [pm.pot(f"Pot{k}", p, M, rnd) for k, p in enumerate(((-8.5, 6.2, 0), (-8.6, -2.4, 0), (-6.8, 12.6, 0),
                                                                 (17.0, 12.6, 0), (-9.6, 15.6, 0)))]
    return out, hedges, pots


# ---------- sea, boats, background ----------

def build_boats(tm, M):
    out = []
    specs = {  # estado: [(x, y, heading graus)]
        (NOW, WEEK, YEAR): [(85.0, 720.0, 0.0), (215.0, 820.0, 180.0)],
        (YEARS,): [(-296.0, 528.0, 200.0), (-262.0, 612.0, 20.0)],
    }
    for states, boats in specs.items():
        for k, (x, y, hd) in enumerate(boats):
            b = mm.boat(f"Boat{states[0]}{k}")
            b.em.default_value = 0.0
            b.light.energy = 0.0
            b.root.location = (x, y, ps.SEA_Z - 0.6)
            b.root.rotation_euler = (0, 0, math.radians(hd))
            b.root.scale = (1.5, 1.5, 1.5)
            wk = mm.wake(f"Wake{states[0]}{k}", M["foam"])
            wk.parent = b.root
            wk.location = (0, 0, 0.5)
            wk.scale = (1.0, 1.6, 1.0)
            show_in(tm, b.root, states)
            out.append(b)
    return out


def build_cover(tm, M, rnd, hill):
    """Forest and trees on the slopes by GN: broadleaf (NOW, WEEK) and bare (YEAR, YEARS); fallen trunks (YEARS)."""
    trees = ps.tree_models(M, rnd)
    # east hill: forest on top (x < -150) and olive/loose trees on the terraces
    g_top = ps.scatter_group("HillForest", trees.leafy, 7.0, 0.02, 11, (0.9, 1.3), xmax=-150.0, zmin=ps.SEA_Z + 4)
    g_mid = ps.scatter_group("HillTrees", trees.leafy, 18.0, 0.003, 12, (0.6, 0.9), xmin=-150.0, zmin=ps.SEA_Z + 4)
    b_top = ps.scatter_group("HillBare", trees.bare, 7.0, 0.02, 11, (0.9, 1.3), xmax=-150.0, zmin=ps.SEA_Z + 4)
    b_mid = ps.scatter_group("HillBareMid", trees.bare, 18.0, 0.003, 12, (0.6, 0.9), xmin=-150.0, zmin=ps.SEA_Z + 4)
    fall = ps.scatter_group("HillFallen", trees.fallen, 14.0, 0.004, 13, (0.8, 1.1), xmin=-160.0, zmin=ps.SEA_Z + 6)
    for name, ng, states in (("HillForestC", g_top, (NOW, WEEK)), ("HillTreesC", g_mid, (NOW, WEEK)),
                             ("HillBareC", b_top, (YEAR, YEARS)), ("HillBareMidC", b_mid, (YEAR, YEARS)),
                             ("HillFallenC", fall, (YEARS,))):
        c = ps.carrier(name, hill, ng)
        show_in(tm, c, states)
    return trees


def build_headland_forest(tm, M, rnd, head, trees):
    # dense forest only on the stretch the camera sees (x -900 to the line); the rest of the headland keeps the forest floor
    g = ps.scatter_group("HeadForest", trees.leafy, 12.0, 0.006, 21, (1.4, 2.0), xmax=ps.HEAD_LINE_X,
                         xmin=-900.0, zmin=ps.SEA_Z + 3)
    b = ps.scatter_group("HeadBare", trees.bare, 12.0, 0.006, 21, (1.4, 2.0), xmax=ps.HEAD_LINE_X,
                         xmin=-900.0, zmin=ps.SEA_Z + 3)
    c1 = ps.carrier("HeadForestC", head, g)
    show_in(tm, c1, (NOW, WEEK))
    c2 = ps.carrier("HeadBareC", head, b)
    show_in(tm, c2, (YEAR, YEARS))


def build_fire(tm, M, fire):
    """Little campfire of 10 (Kenney nature-kit campfire_stones, CC0) + logs + pot + amber ember and thin smoke."""
    root = pm._empty("Campfire", tuple(fire))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(pm.ASSETS / "kenney/nature-kit/Models/GLTF format/campfire_stones.glb"))
    for o in [o for o in bpy.data.objects if o not in before]:
        if o.type == "MESH":
            o.parent = root
            o.location = (0, 0, 0.04)
            o.scale = (1.6, 1.6, 1.6)
            o.material_slots[0].material = M["stone"]
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    logs = kit.merge(*[kit.tube_geo([(0.22 * math.cos(a), 0.22 * math.sin(a), 0.03), (0.02 * math.cos(a), 0.02 *
                                                                                       math.sin(a), 0.14)],
                                    [0.035, 0.025], n=6) for a in (0.3, 2.4, 4.4)])
    pm.obj_from("FireLogs", logs[:2], [M["logbark"]], parent=root)
    pm.obj_from("FireCoal", kit.merge(*[kit._gem_geo(0.04, oz=0.06, ox=0.05 * math.cos(a), oy=0.05 * math.sin(a))
                                        for a in (0, 2, 4)])[:2], [M["ember"]], parent=root)
    flame = pm.obj_from("FireFlame", kit._prism_geo(5, 0.07, 0.0, 0.22, oz=0.06), [M["flame"]], parent=root)
    flame.visible_shadow = False
    # pot over two stones
    pot = kit.loft_geo([[(r * math.cos(2 * math.pi * i / 10), r * math.sin(2 * math.pi * i / 10), z) for i in range(10)]
                        for r, z in ((0.11, 0.0), (0.14, 0.04), (0.14, 0.17), (0.13, 0.18))])
    pm.obj_from("FirePot", kit.xform_geo(pot, Matrix.Translation((0, 0, 0.26))), [M["metal"]], parent=root)
    # thin smoke: opaque matte column that rises and lies over with the wind (from west to east = -x), widening
    rs = random.Random(5)
    puffs = []
    for k in range(12):
        u = k / 11
        c = (-0.55 * u ** 1.6 + rs.uniform(-0.03, 0.03), rs.uniform(-0.03, 0.03), 0.4 + 1.5 * u)
        puffs.append(pm.lumpy_ico(0.035 + 0.1 * u, c, (1, 1, 0.9), rs, 0.25))    # bolotas sobrepostas, afinando
    sm = pm.obj_from("FireSmoke", kit.merge(*puffs)[:2], [M["smoke"]], parent=root)
    sm.visible_shadow = False
    # fishing basket nearby (sign of people living off the sea)
    bk = kit.loft_geo([[(r * math.cos(2 * math.pi * i / 10), r * math.sin(2 * math.pi * i / 10), z) for i in range(10)]
                       for r, z in ((0.17, 0.0), (0.22, 0.28), (0.23, 0.3))], cap_end=False)
    pm.obj_from("Basket", kit.xform_geo(bk, Matrix.Translation((0.55, -0.6, 0.0))),
                [pm.fixed_mat("Basket", "#8A6A44", rough=0.95)], parent=root)
    show_in(tm, root, (YEARS,))
    return root


def build_debris(tm, M, rnd):
    """Signs of "years later" in the square (YEARS): dry twigs fallen from the crown around the plane tree, loose and
    lifted paving stones, soil brought by the wind in the joints, pot shards. The square stays free of human
    litter (people live there)."""
    sticks, pavers, dirt = [], [], []
    dead = pm.fixed_mat("DeadTwig", "#7A7066", var=(0.85, 1.1))
    for k in range(26):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(2.8, 6.5)
        c = TREE + Vector((r * math.cos(a), r * math.sin(a), 0.03))
        if (c - H3_CAM).length < 4.5 or c.y > ps.PLAZA[3] - 0.4:
            continue
        ln, hd = rnd.uniform(0.35, 1.3), rnd.uniform(0, math.pi)
        d = Vector((math.cos(hd), math.sin(hd), 0)) * ln / 2
        mid = (c + Vector((0.1 * math.sin(hd), -0.1 * math.cos(hd), 0.01)))
        mid = mid + Vector((0.12 * rnd.uniform(-1, 1), 0.12 * rnd.uniform(-1, 1), 0))
        sticks.append(kit.tube_geo([tuple(c - d), tuple(mid), tuple(c + d)], [0.022, 0.017, 0.008], n=4))
        for j in range(rnd.randint(1, 3)):
            u = rnd.uniform(-0.3, 0.6)
            b0 = c + d * u
            a2 = hd + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.1)
            tip = b0 + Vector((0.35 * math.cos(a2), 0.35 * math.sin(a2), 0.02))
            sticks.append(kit.tube_geo([tuple(b0), tuple(tip)], [0.01, 0.004], n=4))
    v, f, _ = kit.merge(*sticks)
    tw = pm.obj_from("Twigs", (v, f), [dead])
    for k in range(14):
        x, y = rnd.uniform(-7, 9), rnd.uniform(4, 16.5)
        if (Vector((x, y, 0)) - TREE).length < 3.0:
            continue
        g = kit._box_geo(0.42, 0.22, 0.08, -0.21, -0.11, -0.04)
        m = Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(rnd.uniform(0, 3.1), 4, "Z") @ \
            Matrix.Rotation(rnd.uniform(0.08, 0.22), 4, "X")
        pavers.append(kit.xform_geo(g, m))
        # soil in the joints: irregular patch flush with the ground (+4 mm, nothing coplanar)
        n = 13
        rr = [rnd.uniform(0.18, 0.4) for _ in range(n)]
        ring = [(x + 0.3 + rr[i] * math.cos(2 * math.pi * i / n), y + 0.2 + rr[i] * math.sin(2 * math.pi * i / n),
                 0.004) for i in range(n)]
        dirt.append((ring, [tuple(range(n))]))
    v, f, _ = kit.merge(*pavers)
    pv = pm.obj_from("LoosePavers", (v, f), [M["paving"]])
    v, f, _ = kit.merge(*dirt)
    dirt_mat = pm.fixed_mat("Dirt", "#BFAE8E", rough=1.0)
    dt = pm.obj_from("DirtPatches", (v, f), [dirt_mat])
    # loose soil brought by the wind (no roots, the hill soil blows away): low 3 to 6 cm mounds next to the bed,
    # by the low walls and in front of the camera of 10
    fwd = Vector((math.sin(math.radians(-45)), math.cos(math.radians(-45)), 0))
    rgt = Vector((fwd.y, -fwd.x, 0))
    spots = [H3_CAM + fwd * rnd.uniform(2.6, 6.0) + rgt * rnd.uniform(-2.2, 2.2) for _ in range(7)]
    spots += [TREE + Vector((math.cos(a), math.sin(a), 0)) * 2.95 for a in (-2.2, -1.5, -0.6, 0.3, 2.6)]
    mounds = []
    for k, c in enumerate(spots):
        r = rnd.uniform(0.35, 0.9)
        mounds.append(pm.lumpy_ico(r, (c.x, c.y, -r * 0.02), (1.0, rnd.uniform(0.5, 0.9), 0.055), rnd, 0.18))
    v, f, _ = kit.merge(*mounds)
    md = pm.obj_from("DustDrifts", (v, f), [dirt_mat])
    show_in(tm, [tw, pv, dt, md], (YEARS,))


def build_tree(tm, M, rnd):
    t = pm.plane_tree("Plane", tuple(TREE), M, rnd)
    show_in(tm, t.canopies["now"], (NOW,))
    show_in(tm, t.canopies["week"], (WEEK,))
    show_in(tm, t.canopies["year"], (YEAR,))
    show_in(tm, t.trunk_fungi, (NOW, WEEK, YEAR, YEARS))
    # branch: attached until the crack of 10; falls from "branch" on impact (end of "falls") and stays on the ground
    br = t.branch
    br.rotation_mode = "QUATERNION"
    f_snap = tm.f("10", W("10", "branch"))
    f_hit = f_snap + 25                               # direction.md: impact at f ~2103 (0.7 s fall + anticipation)
    base0 = Vector(br.location)
    d = t.branch_dir
    land_dir = Vector((0.063, 0.997, 0.0)).normalized()      # falls to the northwest: to the right of the trunk seen from 10
    q_land = Vector((d.x, d.y, d.z)).rotation_difference(land_dir)
    base_land = Vector((0.85, 0.6, 0.26))                  # foot of the branch on the ground, next to the trunk (tree location)
    q0 = Quaternion((1, 0, 0, 0))
    for f in range(f_snap - 4, f_hit + 8):
        if f < f_snap:
            u, q, p = 0.0, q0, base0 + Vector((0, 0, -0.03 * (f - f_snap + 4) / 4))     # anticipation: gives 3 cm
        elif f <= f_hit:
            u = (f - f_snap) / (f_hit - f_snap)
            e = u * u
            q = q0.slerp(q_land, e)
            p = base0.lerp(base_land, e)
        else:
            s = f - f_hit
            bounce = math.radians(3) * math.exp(-s / 2.5) * math.sin(math.pi * min(s, 6) / 6)
            q = Quaternion(land_dir.cross(Vector((0, 0, 1))).normalized(), bounce) @ q_land
            p = base_land
        br.rotation_quaternion = q
        br.location = p
        br.keyframe_insert("rotation_quaternion", frame=f)
        br.keyframe_insert("location", frame=f)
    for fc in rigs._fcurves(br.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    # before 10 the branch stays attached (rest position); frame 1 also at rest
    br.rotation_quaternion = q0
    br.location = base0
    br.keyframe_insert("rotation_quaternion", frame=1)
    br.keyframe_insert("location", frame=1)
    return t


# ---------- montagem ----------

def build(tl):
    tm = T(tl)
    scene = bpy.context.scene
    total = tl.frames
    look_post(scene)
    rnd = random.Random(42)
    key_state(tm)
    ps.build_world()
    ps.build_sun()
    M = ps.make_mats()
    ps.clouds(pm.fixed_mat("Cloud", "#F2F5F8", rough=1.0, emission="#F2F5F8", strength=0.25), random.Random(8))
    g = ps.build_ground(M)
    show_in(tm, [g.parapet[2], g.parapet[4]], (NOW, WEEK, YEAR))
    show_in(tm, g.rubble, (YEARS,))
    ps.build_houses(M, rnd)
    whill = ps.build_west_hill(M)
    tufts = ps.tuft_models(M, rnd)
    build_beds(tm, M, rnd, tufts)
    trees = build_cover(tm, M, rnd, g.hill)
    # west hill (05): sparse trees on the terraces, broadleaf (NOW, WEEK) and bare (YEAR, YEARS)
    for name, col, states in (("WestTreesC", trees.leafy, (NOW, WEEK)), ("WestBareC", trees.bare, (YEAR, YEARS))):
        ng = ps.scatter_group(name[:-1], col, 14.0, 0.004, 31, (0.7, 1.0), xmin=40.0, zmin=ps.SEA_Z + 4)
        show_in(tm, ps.carrier(name, whill, ng), states)
    build_headland_forest(tm, M, rnd, g.headland, trees)
    tree = build_tree(tm, M, rnd)
    build_wind(tree, total)
    build_debris(tm, M, random.Random(31))
    build_stall(tm, M, rnd)
    build_woodpile(tm, M, rnd)
    build_boats(tm, M)
    _, fire = build_people(tm, total)
    build_fire(tm, M, fire)
    poses = camera_poses(total)
    build_camera(tm, poses)
    build_markers(tm, M, total, poses)
    build_passages(scene, total)


kit.run(build)
