"""FINAL set for the moon-disappeared script: the tip of a rural wooden pier, at night, over the sea.

Run by 'python -m ifscape blender scripts/moon-disappeared.json' (preview: IFSCAPE_PREVIEW=1).
POV camera at 4.6 m (deck at +3.0 m above mean level). Camera, positions, timing and light from the approved blockout;
final models in moon_models.py (owl, mice, boat, lantern, crate, Moon with maria, Sun with halo, globe).
Times of the trigger words: read from build/moon-disappeared/voice.json (W(scene, word)).
Units: meters; +Y is the sea; yaw 0 looks toward +Y and grows to the right (+X); positive pitch looks up.
Proportions: ruler post 0.30 m, board 0.35 x 2.1 m with 0.30 m stripes (NOAA, tide gauge), deck boards
0.15 m (shoreprotect.com/piers/wood-pier), owl 0.30 m (barn owl), mouse 0.08 m (x1.5 to read).
Light: no flickering sky; the light changes only at cuts or in a ramp of 0.3 to 1 s.
"""

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import kit  # noqa: E402
import moon_models as mm  # noqa: E402
import moon_space as ms  # noqa: E402
import town_sky as sky  # noqa: E402
from kit import lin  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VOICE = json.loads((ROOT / "build" / "moon-disappeared" / "voice.json").read_text(encoding="utf-8"))
SCENES = tuple(f"{i:02d}" for i in range(1, 13))
F_PX = 1920 / 36 * 22                      # pixels per radian (22 mm lens, 36 mm sensor on the height)
EYE = 4.6
DECK = 3.0

# extra sky states
sky.STATES["dawn"] = ("#F0A890", "#9A7A9A", "#3A4A7E")
sky.STATES["winter"] = ("#7A4A58", "#1C2442", "#05080F")
sky.ORDER = ("day", "dusk", "sunset", "nightfall", "night", "dawn", "winter")


# ---------- time ----------

def W(sid, word, nth=0):
    """Second (within the scene) at which the word starts, from voice.json."""
    hits = [w["start"] for w in VOICE[sid]["words"] if w["word"].strip("?.,:").lower() == word.lower()]
    return hits[nth]


class T:
    def __init__(self, tl):
        self.tl = tl

    def f(self, sid, t):
        return self.tl.at(sid) + int(round(t * self.tl.fps))

    def last(self, sid):
        return self.tl.at(sid, 1.0) - 1

    def dur(self, sid):
        return (self.last(sid) - self.tl.at(sid)) / self.tl.fps


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u


def track(tm, owner, attr, sid, pts, ease=True):
    """Dense keys (one per frame in the stretches that change). pts = [(seconds in the scene, value)]; holds the 1st value
    until the 1st point and the last until the end of the scene."""
    a, b = tm.f(sid, 0), tm.last(sid)
    pts = sorted(pts, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts = [(0.0, pts[0][1])] + pts
    pts = pts + [((b - a) / tm.tl.fps + 0.0, pts[-1][1])]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        f0, f1 = min(max(tm.f(sid, t0), a), b), min(max(tm.f(sid, t1), a), b)
        if v0 == v1 or f1 <= f0 + 1:
            kit.key(owner, attr, v0, f0)
            if f1 > f0:
                kit.key(owner, attr, v1, f1)
            continue
        for f in range(f0, f1 + 1):
            u = (f - f0) / (f1 - f0)
            kit.key(owner, attr, lerp(v0, v1, smooth(u) if ease else u), f)


def hold(tm, owner, attr, values, default=0.0):
    for sid in SCENES:
        v = values.get(sid, default)
        track(tm, owner, attr, sid, [(0.0, v)])


def vis(tm, root, scenes):
    objs = [root, *root.children_recursive] if hasattr(root, "children_recursive") else [root]
    for o in objs:
        for sid in SCENES:
            o.hide_render = sid not in scenes
            o.keyframe_insert("hide_render", frame=tm.tl.at(sid))


def hide_at(tm, root, sid, t):
    """Hides root and children from second t of scene sid (cut within the scene)."""
    for o in [root, *root.children_recursive]:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=tm.f(sid, t))


# ---------- camera ----------

def basis(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    fwd = Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p)))
    right = Vector((math.cos(y), -math.sin(y), 0.0))
    up = right.cross(fwd) * -1
    up = Vector((-math.sin(y) * math.sin(p), -math.cos(y) * math.sin(p), math.cos(p)))
    return fwd, right, up


def px_dir(px, py, yaw, pitch):
    fwd, right, up = basis(yaw, pitch)
    return (fwd + right * ((px - 540) / F_PX) - up * ((py - 960) / F_PX)).normalized()


NOM = dict(yaw=0.0, pitch=6.8, pos=Vector((0.0, 0.0, EYE)))       # base pose: horizon at y 1100
RULER = Vector((2.2, 6.7, 0.0))
CAM05 = Vector((2.4, 0.5, 4.0))      # 05/06: at the right edge, 1.3 m outside the railing, looking down at the post
MOON_PX = (790, 1010)                # Moon center in 01 and 12 (pixels)
PITCH10 = 25.0                       # 10 after the cut: horizon at y ~1500
CUT10 = round(W("10", "then") * 30) / 30     # cut of 10 (globe -> noon), in seconds of the scene


def proj(P, cam, yaw, pitch, f_px=F_PX):
    """Pixel (x, y) of a world point for the camera (cam, yaw, pitch)."""
    fwd, right, up = basis(yaw, pitch)
    d = Vector(P) - cam
    z = d.dot(fwd)
    return 540 + f_px * d.dot(right) / z, 960 - f_px * d.dot(up) / z


# 05/06 (V2-C2, board 1.6x): 300 px/m, 0.0 m of the board at y 830 and +1.6 m at y 350, post at x 700. The lens and pitch come out
# of a calculation (the plan's 35 mm lens would give ~265 px/m with the camera where it is; the calculation asks for ~38 mm).
BOARD_PX = {"y0": 830.0, "y1": 350.0, "x": 700.0, "top": 1.6}


def pose05():
    """(yaw, pitch, f_px) of camera CAM05 for the 4 targets of BOARD_PX."""
    d = RULER - CAM05
    u = Vector((-d.x, -d.y, 0.0)).normalized()
    front = RULER + u * 0.26                  # front plane of the board (0.2 m from the post + 0.06 m): it is what measures the water
    az = math.degrees(math.atan2(front.x - CAM05.x, front.y - CAM05.y))
    f = F_PX * 1.6
    yaw, p = az, -30.0
    for _ in range(6):
        yaw = az - math.degrees(math.atan((BOARD_PX["x"] - 540) / f))
        best = None
        for k in range(-8000, -500):                        # pitch -80 to -5 degrees, step 0.01
            pp = k / 100.0
            fwd, _, up = basis(yaw, pp)
            a0 = (Vector((front.x, front.y, 0.0)) - CAM05)
            a1 = (Vector((front.x, front.y, BOARD_PX["top"])) - CAM05)
            r0, r1 = a0.dot(up) / a0.dot(fwd), a1.dot(up) / a1.dot(fwd)
            if r0 <= 0:
                continue
            err = abs(r1 / r0 - (960 - BOARD_PX["y1"]) / (960 - BOARD_PX["y0"]))
            if best is None or err < best[0]:
                best = (err, pp, (960 - BOARD_PX["y0"]) / r0)
        _, p, f = best
    return yaw, p, f


def camera_poses(tm):
    """scene -> [(seconds, pos, yaw, pitch)]"""
    y5, p5, _ = pose05()
    P = lambda x, y, z=EYE: Vector((x, y, z))
    t_its, t_us = W("02", "its"), W("02", "us")
    y02 = lambda t: 0.4 + 0.15 * t / 9.0          # slow drift of the position, as before (0.4 -> 0.55 in 9 s)
    cut10 = CUT10
    f = 1.0 / 30
    return {
        "01": [(0, P(0, 0), 0, 6.8), (9, P(0, 0.4), 0, 7.3)],
        # 02 (V2-A, version A2): the camera follows the last light that arrived: from the empty point in the sky, across the black sea, to the boards
        # without the railing stripes. Pitch 7 -> -9 between "Its" (q116) and "us" (q153) with ease-in-out (each stretch is smooth);
        # 03 starts from -9 and rises with ease-in-out (its last frames already arrive still: ease-out of the 03>04 cut).
        "02": [(0, P(0, 0.4), 0, 7.3), (t_its, P(0, y02(t_its)), 0, 7.0), (t_us, P(0, y02(t_us)), 0, -9.0),
               (9, P(0, y02(9)), 0, -9.0)],
        "03": [(0, P(0, 0.55), 0, -9.0), (tm.dur("03"), P(0, 0.55), 0, 40.0)],
        "04": [(0, P(-0.2, 1.0, 3.9), -8, -6.0), (9, P(-0.2, 1.1, 3.9), -8, -6.0)],
        "05": [(0, CAM05, y5, p5), (9, CAM05 + Vector((0, 0.05, 0)), y5, p5 + 0.3)],
        "06": [(0, CAM05, y5, p5), (9, CAM05 + Vector((0, 0.05, 0)), y5, p5 + 0.3)],
        "07": [(0, P(0, 0.4), 7, 6.8), (9, P(0, 1.6), 7, 6.8)],
        "08": [(0, P(0, 0.4), 0, 6.8), (9, P(0, 0.6), 0, 6.8)],
        "09": [(0, P(0, 0.6), 0, 6.8), (9, P(0, 0.8), 0, 6.8)],
        # 10: opens with the globe (same pose as 09), cuts on "Then" to noon; FIXED pitch 25 after the cut
        "10": [(0, P(0, 0.75), 0, 6.8), (cut10 - f, P(0, 0.75), 0, 6.8), (cut10, P(0, 0.5), 0, PITCH10),
               (20, P(0, 0.6), 0, PITCH10)],
        "11": [(0, P(0, 0.6), 0, 6.8), (9, P(0, 2.0), 0, 6.8)],
        "12": [(0, P(0, 0), 0, 6.8), (9, P(0, 0.4), 0, 7.3)],
    }


SMOOTH_SCENES = ("03",)          # scenes with 2 poses that still use ease-in-out
LENS = 22.0


def seg_u(sid, pts, t0, t1, t):
    smooth_on = len(pts) > 2 or sid in SMOOTH_SCENES
    u = (t - t0) / max(t1 - t0, 1e-6)
    return min(max(smooth(u) if smooth_on else u, 0.0), 1.0)


def cut_pitch(tm, sid, f):
    """Camera match of the 06>07 cut (V2-D): 06 raises the gaze +4 degrees in q807-815 with ease-in and 07 opens 4 degrees
    below and rises with ease-out until q823: the movement crosses the cut (same direction and angular speed)."""
    if sid == "06":
        f0 = tm.last("06") - 8
        return 4.0 * min(max((f - f0) / 8.0, 0.0), 1.0) ** 2
    if sid == "07":
        u = (f - tm.f("07", 0)) / 7.0
        v = -4.0 * (1.0 - u) ** 2 if 0.0 <= u < 1.0 else 0.0
        # 07>08 (place jump, V2-B): the gaze rises +6 degrees with ease-in in q1067-1075, toward the amber line (child of the camera)
        f1 = tm.last("07")
        return v + 6.0 * min(max((f - (f1 - 8)) / 8.0, 0.0), 1.0) ** 2
    return 0.0


def space_range(tm):
    """Space frames (V2-B): from the 1st of 08 to the last before the "Then" cut of 10 (q1076-1557)."""
    return tm.f("08", 0), tm.f("10", CUT10) - 1


def build_camera(tm):
    data = bpy.data.cameras.new("Eye")
    data.lens = LENS
    data.clip_start, data.clip_end = 0.05, 6000.0
    cam = bpy.data.objects.new("Eye", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    poses = camera_poses(tm)
    f_px05 = pose05()[2]
    sp0, sp1 = space_range(tm)
    orbit = ms.Orbit(sp0, sp1)
    prev = None
    for sid in SCENES:
        pts = poses[sid]
        a, b = tm.f(sid, 0), tm.last(sid)
        lens = f_px05 * 36.0 / 1920.0 if sid in ("05", "06") else LENS       # 05/06: 1.6x board lens (pose05)
        keys = [(a, lens), (b, lens)]
        if sid in ("08", "09"):                                            # space: 50 mm (Earth of 250 px without distortion)
            keys = [(a, ms.LENS_SP), (b, ms.LENS_SP)]
        elif sid == "10":
            keys = [(a, ms.LENS_SP), (sp1, ms.LENS_SP), (sp1 + 1, LENS), (b, LENS)]
        for fk, lv in keys:
            data.lens = lv
            data.keyframe_insert("lens", frame=fk)
        for f in range(a, b + 1):
            if sp0 <= f <= sp1:                       # slow orbit, no handheld sway (V2-B)
                pos, yaw, pit = orbit.pose(f)
                q = ms.basis(yaw, pit)[0].to_track_quat("-Z", "Y")
                if prev is not None and prev.dot(q) < 0:
                    q.negate()
                prev = q
                cam.location = pos
                cam.rotation_quaternion = q
                cam.keyframe_insert("location", frame=f)
                cam.keyframe_insert("rotation_quaternion", frame=f)
                continue
            t = (f - a) / tm.tl.fps
            for (t0, p0, y0, q0), (t1, p1, y1, q1) in zip(pts, pts[1:]):
                if t0 <= t <= t1 or (t1 == pts[-1][0] and t > t1):
                    u = seg_u(sid, pts, t0, t1, t)
                    pos, yaw, pit = p0.lerp(p1, u), lerp(y0, y1, u), lerp(q0, q1, u)
                    break
            pit += cut_pitch(tm, sid, f)
            sway = Vector((0.004 * math.sin(f * 0.07), 0.003 * math.sin(f * 0.05 + 1), 0.004 * math.sin(f * 0.09 + 2)))
            fwd, _, up = basis(yaw + 0.12 * math.sin(f * 0.043), pit + 0.12 * math.sin(f * 0.061 + 1))
            pos = pos + sway
            q = (pos + fwd - pos).to_track_quat("-Z", "Y")
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q
            cam.location = pos
            cam.rotation_quaternion = q
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_quaternion", frame=f)
    return cam


# ---------- auxiliary geometry ----------

def uv_sphere(name, r, loc, mat, seg=16, rings=9, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.scale = scale
    bpy.context.collection.objects.link(o)
    return o


def emitter(name, color, strength):
    mat = kit.flat(name, "#000000", emission=color, strength=strength)
    return mat, kit.principled(mat).inputs["Emission Strength"]


SNOW = []
RULER_MATS = {}


GRAIN = {"x": (1.2, 22.0, 22.0), "y": (22.0, 1.2, 22.0), "z": (14.0, 14.0, 1.0)}


def wood(name, color, ice=False, grain="x"):
    """Wood with smooth grain (noise stretched along the piece, low contrast and low frequency so it does not
    shimmer from afar) and snow mix (factor animated in scenes 10 and 11)."""
    mat = kit.flat(name, color, rough=0.95)
    nt = mat.node_tree
    p = kit.principled(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = GRAIN[grain]
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 1.5
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value, rng.inputs["From Max"].default_value = 0.3, 0.7
    rng.inputs["To Min"].default_value, rng.inputs["To Max"].default_value = 0.86, 1.1
    nt.links.new(nz.outputs["Fac"], rng.inputs["Value"])
    veined = nt.nodes.new("ShaderNodeMix")
    veined.data_type = "RGBA"
    veined.blend_type = "MULTIPLY"
    veined.inputs["Factor"].default_value = 1.0
    veined.inputs["A"].default_value = lin(color)
    nt.links.new(rng.outputs["Result"], veined.inputs["B"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(veined.outputs["Result"], mix.inputs["A"])
    mix.inputs["B"].default_value = lin("#CFE0EC" if ice else "#E6ECF4")
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    SNOW.append(mix.inputs["Factor"])
    return mat


def hexc(h):
    return lin(h)


# ---------- pier ----------

PILE_ROWS = (-12, -9, -6, -3, 0, 3, 6)


def build_pier():
    """Pier: boards in three tones with staggered ends and nails (only near the camera), side beam (fascia),
    crossbeams and X bracing between the piles, posts with caps, railing with hand board."""
    tones = [wood("Deck", "#7A5C3C"), wood("Deck2", "#6C5034"), wood("Deck3", "#86663F")]
    pile = wood("Pile", "#4A3A2A", ice=True, grain="z")
    beam = wood("Beam", "#55402C", grain="y")
    railw = wood("RailWood", "#7A5C3C", grain="y")
    postw = wood("PostWood", "#6E5236", grain="z")
    nail_m = kit.flat("Nail", "#3E342B", rough=0.5, metallic=0.3)
    rnd = random.Random(7)
    root = bpy.data.objects.new("Pier", None)
    bpy.context.collection.objects.link(root)
    parts, kinds, nails = [], [], []
    y = -14.0
    while y < 6.0:
        a, b = rnd.uniform(-0.03, 0.0), rnd.uniform(0.0, 0.03)
        parts.append(kit._box_geo(2.4 + b - a, 0.15, 0.12, -1.2 + a, y, DECK - 0.12))
        kinds.append(rnd.choice((0, 0, 1, 2)))
        if -1.5 < y < 3.6:        # large nails (4 cm, >= 5 px) and only up to ~3.6 m depth: no 3 px dotting
            for x in (-1.0, 1.0):
                nails.append(kit._box_geo(0.04, 0.04, 0.008, x - 0.02, y + 0.075 - 0.02, DECK - 0.001))
        y += 0.16
    v, f, own = kit.merge(*parts)
    kit.fix_normals(kit.mesh_object("Planks", v, f, tones, face_mats=[kinds[o] for o in own])).parent = root
    v, f, _ = kit.merge(*nails)
    nl = kit.mesh_object("Nails", v, f, [nail_m])
    nl.parent = root
    nl.visible_shadow = False
    under = kit.box("Underlay", (0, -4, DECK - 0.2), (2.4, 20.0, 0.1), kit.flat("Under", "#1A130D"))
    under.parent = root
    # fascia (side beam) and crossbeams over the piles
    bm = [kit._box_geo(0.06, 20.06, 0.25, 1.2, -14.0, DECK - 0.28), kit._box_geo(0.06, 20.06, 0.25, -1.26, -14.0, DECK - 0.28),
          kit._box_geo(2.52, 0.06, 0.25, -1.26, 6.0, DECK - 0.28)]
    for yy in PILE_ROWS:
        yc = min(yy, 5.8)
        bm.append(kit._box_geo(2.4, 0.16, 0.16, -1.2, yc - 0.08, DECK - 0.36))
    v, f, _ = kit.merge(*bm)
    kit.fix_normals(kit.mesh_object("Beams", v, f, [beam])).parent = root
    rail, braces = [], []
    for yy in PILE_ROWS:
        yc = min(yy, 5.8)
        for x in (-1.15, 1.15):
            parts_p = kit._prism_geo(8, 0.14, 0.14, 6.0, oz=-3.0, ox=x * 0.9, oy=yc)
            o = kit.mesh_object(f"Pile{x}{yy}", *parts_p, [pile])
            o.parent = root
            rail.append(kit._box_geo(0.12, 0.12, 1.0, x - 0.06, min(yy, 5.9) - 0.06, DECK))
            rail.append(kit._box_geo(0.15, 0.15, 0.02, x - 0.075, min(yy, 5.9) - 0.075, DECK + 1.0))   # cap
        for s in (-1, 1):                                    # X bracing
            braces.append(kit.tube_geo([(-1.035 * s, yc + 0.1, 0.5), (1.035 * s, yc + 0.1, 2.55)], [0.05, 0.05], n=4))
    rail.append(kit._box_geo(0.12, 0.12, 1.0, -1.21, 4.44, DECK))
    rail.append(kit._box_geo(0.15, 0.15, 0.02, -1.225, 4.425, DECK + 1.0))
    v, f, _ = kit.merge(*braces)
    kit.fix_normals(kit.mesh_object("Braces", v, f, [pile])).parent = root
    v, f, _ = kit.merge(*rail)
    kit.fix_normals(kit.mesh_object("Posts", v, f, [postw])).parent = root
    hand = [kit._box_geo(0.07, 20.0, 0.09, -1.18, -14.0, DECK + 0.9), kit._box_geo(0.07, 19.97, 0.09, 1.11, -14.0, DECK + 0.9),
            kit._box_geo(0.07, 20.0, 0.07, -1.18, -14.0, DECK + 0.45), kit._box_geo(0.07, 19.97, 0.07, 1.11, -14.0, DECK + 0.45),
            kit._box_geo(2.4, 0.07, 0.09, -1.2, 5.93, DECK + 0.9), kit._box_geo(2.4, 0.07, 0.07, -1.2, 5.93, DECK + 0.45),
            kit._box_geo(0.11, 19.9, 0.022, -1.2, -14.0, DECK + 0.99), kit._box_geo(0.11, 19.9, 0.022, 1.09, -14.0, DECK + 0.99),
            kit._box_geo(2.2, 0.11, 0.022, -1.1, 5.91, DECK + 0.99)]
    v, f, _ = kit.merge(*hand)
    kit.fix_normals(kit.mesh_object("Rails", v, f, [railw])).parent = root
    return root


def build_lamp():
    root = bpy.data.objects.new("Lamp", None)
    bpy.context.collection.objects.link(root)
    mat, em = emitter("LampMat", kit.LUZ, 8.0)
    glass, frame = mm.lantern("Lantern", (-1.0, 5.9, DECK + 0.66), mat)
    glass.parent = root
    frame.parent = root
    light = bpy.data.lights.new("LampLight", "POINT")
    light.color, light.energy, light.shadow_soft_size = (1.0, 0.65, 0.28), 60.0, 0.1
    lo = bpy.data.objects.new("LampLight", light)
    bpy.context.collection.objects.link(lo)
    lo.location = (-0.95, 5.8, DECK + 0.7)
    lo.parent = root
    LAMP_OBJ.append(lo)
    return root, em, light


LAMP_OBJ = []
WATER_OBJS = ('SeaNear', 'SeaFar', 'SeaPad', 'PierReflection')     # water: no diffuse light from the lantern (the ice in 11 receives it)
HALO_K = 0.42            # lantern halo strength
LAMP_GLIT = 1.2          # strength of the lamp reflection column


def link_lamp_light():
    """Light linking (Blender 5.2): the lantern's diffuse light lights deck, posts, railing, animal and crate, NOT the sea
    (flat patches with slat shadow and a straight edge on the sea; the water only shows the reflection, see LampGlitter).
    Water = SeaNear, SeaFar, SeaPad and the dark reflection of the pier; the ice in 11 receives the light (it is a solid surface)."""
    coll = bpy.data.collections.new("LampReceivers")           # out of the scene: only serves as a list of receivers
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE") and o.name not in WATER_OBJS:
            coll.objects.link(o)
    LAMP_OBJ[0].light_linking.receiver_collection = coll


def build_ruler(cam_pos):
    """Ruler post with LIGHT board (#D8D2C0, 1.0 x 2.2 m, from -0.6 to +1.6 m; V2-C2: 300 px/m in 05/06): dark wet band from 0 to +1.2 m in the
    middle, amber line at the top of the band (+1.2 m) and amber line of the new tide (+0.4 m); stripes on the edges every 0.3 m."""
    root = bpy.data.objects.new("Ruler", None)
    bpy.context.collection.objects.link(root)
    wood_m = wood("RulerWood", "#5A4632", ice=True)
    pile = kit.mesh_object("RulerPile", *kit._prism_geo(10, 0.15, 0.15, 7.0, oz=-3.0, ox=RULER.x, oy=RULER.y), [wood_m])
    pile.parent = root
    cap_m = kit.flat("SnowCap", "#F2F5F8", rough=0.95)
    cap = kit.mesh_object("SnowCap", *kit._prism_geo(10, 0.2, 0.2, 0.14, oz=4.0, ox=RULER.x, oy=RULER.y), [cap_m])
    cap.parent = root
    u = (cam_pos - RULER)
    u = Vector((u.x, u.y, 0)).normalized()
    board = bpy.data.objects.new("RulerBoard", None)
    bpy.context.collection.objects.link(board)
    RULER_BOARD.append(board)
    board.location = (RULER.x + u.x * 0.2, RULER.y + u.y * 0.2, 0)
    board.rotation_euler.z = math.atan2(u.x, -u.y)
    board.parent = root
    light, dark = kit.flat("BoardLight", "#D8D2C0", rough=0.8), kit.flat("BoardDark", "#2A2A33", rough=0.8)
    band = kit.flat("WetBand", "#1E1A1A", rough=0.4)
    kit.mesh_object("BoardMesh", *kit._box_geo(1.0, 0.04, 2.2, -0.5, -0.04, -0.6), [light]).parent = board     # top at +1.6 m
    parts = []
    for i in range(0, 7, 2):                                   # 0.3 m stripes on both edges (up to +1.5 m)
        z0 = -0.6 + 0.3 * i
        parts.append(kit._box_geo(0.08, 0.012, 0.3, -0.5, -0.052, z0))
        parts.append(kit._box_geo(0.08, 0.012, 0.3, 0.42, -0.052, z0))
    v, f, _ = kit.merge(*parts)
    kit.fix_normals(kit.mesh_object("BoardTicks", v, f, [dark])).parent = board
    # wet band 0 to +1.2 m in 3 equal thirds: the bottom third (0 to +0.4 m) is BLUE (water color): "the water covers the blue third"
    low = kit.flat("WetLow", "#4F3C4E", rough=0.4)
    RULER_MATS["low"] = low
    kit.mesh_object("WetBand", *kit._box_geo(0.76, 0.012, 0.8, -0.38, -0.052, 0.4), [band]).parent = board
    kit.mesh_object("WetBandLow", *kit._box_geo(0.76, 0.012, 0.4, -0.38, -0.052, 0.0), [low]).parent = board
    ring_old, em_old = emitter("RingOld", kit.LUZ, 1.5)
    ro = kit.box("RingOld", (0, -0.06, 1.175), (0.96, 0.014, 0.05), ring_old)
    ro.parent = board
    ring_new, em_new = emitter("RingNew", kit.LUZ, 1.5)
    rn = kit.box("RingNew", (0, -0.06, 0.375), (0.96, 0.014, 0.05), ring_new)
    rn.parent = board
    for o in (ro, rn):
        o.visible_shadow = False
    # two 8 cm light ticks just above +0.4 and +0.8 m, crossing the band and the edges (the water stops at the base of the 1st): the band reads as
    # 3 equal parts; dark when the band lightens (the color is animated in build)
    trace_m = kit.flat("Trace", "#F2F4F6", rough=0.8, emission="#F2F4F6", strength=1.0)
    v, f, _ = kit.merge(*[kit._box_geo(0.86, 0.008, 0.08, -0.43, -0.059, z) for z in (0.4, 0.8)])
    trace = kit.mesh_object("Traces", v, f, [trace_m])
    trace.parent = board
    trace.visible_shadow = False
    # IRREGULAR foam on the waterline (round 7, A2): U-shaped strip on the water around the front and sides of the board, outer edge
    # cut out (width 1.5 to 8 cm varying slowly), broken by noise and denser next to the wood; before it was a
    # straight white plate. Origin 0.3 m behind the board: Eevee draws the foam BEFORE the ghost wave (order by origin).
    foam = ragged_foam(board)
    return root, band, em_old, em_new, rn, cap, trace_m, foam


def ragged_foam(board):
    rnd = random.Random(41)
    path = [(-0.53, 0.10), (-0.53, 0.02)] + [(-0.53 + 1.06 * i / 40, -0.065) for i in range(41)] + [(0.53, 0.02), (0.53, 0.10)]
    ph = [rnd.uniform(0, 6.3) for _ in range(3)]
    verts, faces, edge = [], [], []
    for i, (x, y) in enumerate(path):
        if i == 0 or i == len(path) - 1:
            nx_, ny_ = 0.0, 0.0
        if abs(y + 0.065) < 1e-6:
            nx_, ny_ = 0.0, -1.0
        else:
            nx_, ny_ = (-1.0 if x < 0 else 1.0), 0.0
        s_ = i / (len(path) - 1)
        w = 0.042 + 0.022 * math.sin(6.3 * s_ * 2.0 + ph[0]) + 0.012 * math.sin(6.3 * s_ * 5.3 + ph[1]) + rnd.uniform(-0.006, 0.006)
        w = max(0.015, w)
        verts += [(x - 0.012 * nx_, y - 0.012 * ny_ - 0.3, 0.0), (x + w * nx_, y + w * ny_ - 0.3, 0.0)]
        edge += [1.0, 0.0]
    for i in range(len(path) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    me = bpy.data.meshes.new("Foam")
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("edge", "FLOAT", "POINT")
    at.data.foreach_set("value", edge)
    mat, n, links, out = mm.node_mat("FoamMat")
    M = lambda op, a_, b_=None, clamp=False: ms._math(n, links, op, a_, b_, clamp)
    ed = n.new("ShaderNodeAttribute")
    ed.attribute_name = "edge"
    tc = n.new("ShaderNodeTexCoord")
    sx = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sx.inputs[0])
    cb = n.new("ShaderNodeCombineXYZ")
    links.new(M("MULTIPLY", sx.outputs["X"], 9.0), cb.inputs["X"])
    links.new(M("MULTIPLY", sx.outputs["Y"], 14.0), cb.inputs["Y"])
    nz = n.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 1.0, 2.0
    links.new(cb.outputs[0], nz.inputs["Vector"])
    PAD_PHASE.append((nz.inputs["W"], 1.7))
    brk = ms._maprange(n, links, nz.outputs["Fac"], 0.36, 0.56)
    a_ = M("MULTIPLY", M("POWER", ed.outputs["Fac"], 0.8), M("ADD", M("MULTIPLY", brk, 0.75), 0.25))
    a_ = M("MULTIPLY", a_, 0.92, clamp=True)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#E4D8E2")
    em.inputs["Strength"].default_value = 0.9
    mix = n.new("ShaderNodeMixShader")
    links.new(a_, mix.inputs["Fac"])
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    me.materials.append(mat)
    o = bpy.data.objects.new("Foam", me)
    bpy.context.collection.objects.link(o)
    o.parent = board
    o.location = (0.0, 0.3, 0.0)
    o.visible_shadow = False
    o.visible_diffuse = o.visible_glossy = False
    return o


def board_under(driver):
    """SUBMERGED part of the ruler board (round 7, A2): the front of the board from 0 to 0.45 m below the waterline, projected onto the
    surface by the CAM05 camera ray (like the reflection of the piles), dark and fading with depth; wavy edge
    by the same Displace as the waves. Moves with the tide (key_tide). Origin behind the board (drawn before the foam and the wave)."""
    board = RULER_BOARD[0]
    rz = board.rotation_euler.z
    c, s_ = math.cos(rz), math.sin(rz)
    bl = Vector(board.location)
    H = CAM05.z
    nx_, nz_ = 13, 8
    verts, dep = [], []
    for j in range(nz_ + 1):
        d = 0.45 * j / nz_
        for i in range(nx_ + 1):
            lx = -0.5 + 1.0 * i / nx_
            wx, wy = bl.x + c * lx - s_ * (-0.042), bl.y + s_ * lx + c * (-0.042)
            t = H / (H + d)
            verts.append((CAM05.x + (wx - CAM05.x) * t, CAM05.y + (wy - CAM05.y) * t, 0.0))
            dep.append(j / nz_)
    faces = [(j * (nx_ + 1) + i, j * (nx_ + 1) + i + 1, (j + 1) * (nx_ + 1) + i + 1, (j + 1) * (nx_ + 1) + i)
             for j in range(nz_) for i in range(nx_)]
    org = Vector((bl.x, bl.y + 0.6, 0.0))
    me = bpy.data.meshes.new("BoardUnder")
    me.from_pydata([(x - org.x, y - org.y, z) for x, y, z in verts], [], faces)
    at = me.attributes.new("depth", "FLOAT", "POINT")
    at.data.foreach_set("value", dep)
    mat, n, links, out = mm.node_mat("BoardUnderMat")
    M = lambda op, a_, b_=None, clamp=False: ms._math(n, links, op, a_, b_, clamp)
    dp = n.new("ShaderNodeAttribute")
    dp.attribute_name = "depth"
    a_ = M("MULTIPLY", M("POWER", M("SUBTRACT", 1.0, dp.outputs["Fac"], clamp=True), 1.4), 0.82)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#2A1F2C")
    em.inputs["Strength"].default_value = 1.0
    mix = n.new("ShaderNodeMixShader")
    links.new(a_, mix.inputs["Fac"])
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    me.materials.append(mat)
    o = bpy.data.objects.new("BoardUnder", me)
    bpy.context.collection.objects.link(o)
    o.location = (org.x, org.y, 0.0)
    o.visible_shadow = False
    o.visible_diffuse = o.visible_glossy = False
    tex = bpy.data.textures.new("UnderWobble", "CLOUDS")
    tex.noise_scale = 0.5
    mod = o.modifiers.new("Wobble", "DISPLACE")
    mod.texture, mod.texture_coords, mod.texture_coords_object = tex, "OBJECT", driver
    mod.direction, mod.strength, mod.mid_level = "X", 0.035, 0.5
    return o



RULER_BOARD = []

# ---------- sea, sky, boat ----------

def build_sea():
    mat = kit.flat("Sea", "#10223A", rough=0.3)
    near = kit.water_grid("SeaNear", -45, 45, -16, 72, 0.0, mat, cell=1.0, amp=0.03, seed=3)
    # sea seam (art.md E2): faceting and Displace drop to ZERO from y 45 to 72, where the grid meets the distant sea
    # (smooth plane with the top 2 cm below): no height or normal step, no horizontal line on the sea.
    vg = near.vertex_groups.new(name="SeamFade")
    for v in near.data.vertices:
        k = 1.0 - smooth((v.co.y - 45.0) / 27.0)
        v.co.z *= k
        vg.add([v.index], k, "REPLACE")
    far = kit.box_span("SeaFar", -3000, 3000, 72, 3500, 0.0, 0.05, mat)             # starts where the grid ends
    far.data.transform(Matrix.Translation((0.0, 0.0, -0.07)))                          # top at -0.02 (key_tide rewrites location.z)
    tex = bpy.data.textures.new("Waves", "CLOUDS")
    tex.noise_scale = 4.0
    em = bpy.data.objects.new("WaveDriver", None)
    bpy.context.collection.objects.link(em)
    mod = near.modifiers.new("Waves", "DISPLACE")
    mod.texture, mod.texture_coords, mod.texture_coords_object = tex, "OBJECT", em
    mod.strength, mod.mid_level = 0.06, 0.5
    mod.vertex_group = "SeamFade"
    # stretch of water around the ruler post (05 and 06). Round 7 (art.md K A2, bible 3 "Water"): ripples = noise STRETCHED
    # horizontally (1:4; the camera looks toward +y, so x is the screen horizontal) in 2 scales, crests at the high values
    # (horizontal strokes), broken by a 2nd slow mask, and TROUGHS darker than the base at the low values (before:
    # contour line of isotropic noise = closed marble veins). Dawn color darker and mauve, the same
    # family as the water near the pier in 07 (before: light, opaque lilac). Calm within a radius of ~1.2 m of the board.
    pad_m = kit.flat("SeaPad", PAD_BASE, rough=0.25)
    nt = pad_m.node_tree
    M = lambda op, a_, b_=None, clamp=False: ms._math(nt.nodes, nt.links, op, a_, b_, clamp)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sxyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sxyz.inputs[0])
    px_, py_ = sxyz.outputs["X"], sxyz.outputs["Y"]

    def stretched(sx, sy, w0, detail=2.0):
        cb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(M("MULTIPLY", px_, sx), cb.inputs["X"])
        nt.links.new(M("MULTIPLY", py_, sy), cb.inputs["Y"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 1.0, detail
        nz.inputs["W"].default_value = w0
        nt.links.new(cb.outputs[0], nz.inputs["Vector"])
        PAD_PHASE.append((nz.inputs["W"], w0))
        return nz.outputs["Fac"]

    n1 = stretched(1.5, 6.0, 0.0)                 # strokes of ~0.7 x 0.17 m
    n2 = stretched(3.2, 12.8, 7.3)                # smaller scale, weaker
    brk = stretched(0.45, 0.9, 3.1, detail=1.0)   # slow mask that breaks the crests into loose stretches
    cr1 = ms._maprange(nt.nodes, nt.links, n1, 0.60, 0.70)
    cr2 = M("MULTIPLY", ms._maprange(nt.nodes, nt.links, n2, 0.62, 0.72), 0.6)
    crest = M("MULTIPLY", M("MAXIMUM", cr1, cr2), ms._maprange(nt.nodes, nt.links, brk, 0.42, 0.58))
    valley = ms._maprange(nt.nodes, nt.links, n1, 0.42, 0.30)
    off = nt.nodes.new("ShaderNodeVectorMath")
    off.operation = "SUBTRACT"
    off.inputs[1].default_value = (RULER.x, RULER.y, 0.0)
    nt.links.new(tc.outputs["Object"], off.inputs[0])
    flat2 = nt.nodes.new("ShaderNodeVectorMath")
    flat2.operation = "MULTIPLY"
    flat2.inputs[1].default_value = (1.0, 1.0, 0.0)
    nt.links.new(off.outputs[0], flat2.inputs[0])
    hyp = nt.nodes.new("ShaderNodeVectorMath")
    hyp.operation = "LENGTH"
    nt.links.new(flat2.outputs[0], hyp.inputs[0])
    calm = ms._maprange(nt.nodes, nt.links, hyp.outputs["Value"], 1.1, 2.3)
    col = ms._mixc(nt.nodes, nt.links, M("MULTIPLY", valley, M("ADD", M("MULTIPLY", calm, 0.6), 0.4)), lin(PAD_BASE), lin(PAD_VALLEY))
    col = ms._mixc(nt.nodes, nt.links, M("MULTIPLY", crest, calm), col, lin(PAD_CREST))
    pp = kit.principled(pad_m)
    nt.links.new(col, pp.inputs["Base Color"])
    # the water around the post is almost all in the pier's shadow (the low sun comes from behind the pier): a constant emission of the
    # color itself guarantees the tone in both scenes, without depending on the shadow (the light of 05/06 does not change: it does not flicker)
    nt.links.new(col, pp.inputs["Emission Color"])
    pp.inputs["Emission Strength"].default_value = PAD_EMIT
    pad = kit.water_grid("SeaPad", RULER.x - 8, RULER.x + 8, -3, 40, 0.0, pad_m, cell=0.8, amp=0.004, seed=5)
    pad.visible_shadow = False
    REFL.append(pier_reflection(em))         # moves with the tide like the pad (not a child: sits 9 mm above it)
    return near, far, em, pad


PAD_PHASE = []
PAD_BASE = "#4F3C4E"          # round 7: dark pinkish mauve, same family as the water of 07 (before #4E4466, light lilac)
PAD_VALLEY = "#2E2230"
PAD_CREST = "#88707F"
PAD_EMIT = 0.85
SEA_DAWN = "#3A3354"
REFL = []


def pier_reflection(driver):
    """Dark reflection of the pier on the still water of scenes 05/06, seen from camera CAM05: each pier point P (height z
    above the water) appears on the water at C + s(P' - C), s = H/(H+z) (mirror). Edge made wavy by a Displace in X
    (same moving texture as the waves). Stays outside the area of the ruler board."""
    H = CAM05.z

    def mirror(x, y, z):
        s = H / (H + z)
        return (CAM05.x + s * (x - CAM05.x), CAM05.y + s * (y - CAM05.y), 0.0)

    polys = []
    for yy in (0, 3, 6):                                        # piles on the right of the pier (the ones that enter the frame and the still stretch)
        y = min(yy, 5.8)
        a, b = mirror(1.035, y, 0.0), mirror(1.035, y, 2.7)
        polys.append([(a[0] - 0.15, a[1], 0), (a[0] + 0.15, a[1], 0), (b[0] + 0.11, b[1], 0), (b[0] - 0.11, b[1], 0)])
    # (the railing posts, above the deck, came out as a loose tip separate from the pile's reflection: removed)
    verts, faces = [], []
    for poly in polys:
        base = len(verts)
        verts += poly
        faces.append(tuple(range(base, base + len(poly))))
    me = bpy.data.meshes.new("PierReflection")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=10, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    mat = kit.flat("PierReflection", "#241B28", rough=0.3)
    me.materials.append(mat)
    o = bpy.data.objects.new("PierReflection", me)
    bpy.context.collection.objects.link(o)
    o.location = (0, 0, 0.009)
    o.visible_shadow = False
    tex = bpy.data.textures.new("ReflWobble", "CLOUDS")
    tex.noise_scale = 0.6
    mod = o.modifiers.new("Wobble", "DISPLACE")
    mod.texture, mod.texture_coords, mod.texture_coords_object = tex, "OBJECT", driver
    mod.direction, mod.strength, mod.mid_level = "X", 0.06, 0.5
    return o


CYCLE = 0.9          # 06: period of each tide (V2-C): peaks at q666/693/720/747


def tide(sid, t):
    if sid in ("01", "02", "03", "04", "12"):
        return 1.2
    if sid == "05":                       # opens at 0.0 (mean level, whole board at y 350-830) and rises 0.4 m
        u = smooth((t - W("05", "high")) / 1.0)
        return 0.4 * u
    if sid == "06":
        if t < 3 * CYCLE:                 # 3 cycles of +-0.4 m: starts and ends at the +0.4 peak (same as the end of 05)
            return 0.4 * math.cos(2 * math.pi * t / CYCLE)
        big = W("06", "little")
        if t < big - 0.3:
            return 0.4
        if t < big + 0.1:
            return 0.4 + 0.3 * smooth((t - (big - 0.3)) / 0.4)
        return 0.7 - 0.3 * smooth((t - (big + 0.1)) / 0.5)
    return 0.1 * math.sin(t * 0.9)


def key_tide(tm, objs):
    """objs = [(object, offset, offset in scenes 05/06)]. In 05/06 the water of the still stretch (pad) sits EXACTLY at the
    tide height (the board really measures); the sea underneath drops 9 cm so the waves do not cover it."""
    for sid in SCENES:
        a, b = tm.f(sid, 0), tm.last(sid)
        dense = sid in ("05", "06", "07", "08", "09", "10", "11")
        for f in range(a, b + 1, 1 if dense else max(b - a, 1)):
            z = tide(sid, (f - a) / tm.tl.fps)
            for o, off, off56 in objs:
                o.location.z = z + (off56 if sid in ("05", "06") else off)
                o.keyframe_insert("location", index=2, frame=f)
        if not dense:
            for o, off, off56 in objs:
                o.location.z = tide(sid, 0) + off
                o.keyframe_insert("location", index=2, frame=a)
                o.keyframe_insert("location", index=2, frame=b)


def moon_world():
    d = px_dir(MOON_PX[0], MOON_PX[1], NOM["yaw"], NOM["pitch"])
    return d


def build_moon_and_path(tm):
    d = moon_world()
    dist = 900.0
    _, right, up = basis(NOM["yaw"], NOM["pitch"])
    moon, em = mm.moon_disc("Moon", dist * math.tan(math.radians(4.2)), NOM["pos"] + d * dist, -d, right, up)
    # silver path: additive strip on the water, horizontal glints that change slowly (4D noise) and merge near the
    # horizon; origin at the observer, local +y toward the Moon
    az = math.atan2(d.x, d.y)
    # art.md B1 (item 4): core <= #E8EEFF (color #9AA9CC + the facet specular), disc width at the horizon opening
    # near the camera, dark gaps between the glints (density 0.48), wide stripes (lat_freq 0.9, soft 0.26) and
    # broken edges (ragged) like the lamp column. The Moon's specular (0.45) stays: without it the path becomes a staircase.
    pm, em_path, phase = mm.glitter_mat("MoonGlitter", "#9AA9CC", 0.9, 0.034, 60.0, 260.0, seed=1.0, density=0.48,
                                        lat_freq=0.9, soft=0.26, ragged=0.3, true_sigma=True, rise=(8.0, 14.0))
    path = mm.strip_mesh("SilverPath", 8.0, 900.0, lambda y: 3.0 * (0.9 + 0.034 * y) + 0.3, pm)
    path.rotation_euler.z = -az
    GLITTER_PHASES.append(phase)
    # Moon halo (art.md B1): additive sphere 1.8x the disc, falloff |N.I|^4, #CFDAF2 (bloom alone barely shows on a phone)
    halo, halo_k = mm.halo("MoonHalo", "#CFDAF2", dist * math.tan(math.radians(4.2)) * 1.8, tuple(moon.location), power=4.0)
    MOON_HALO.extend([halo, halo_k])
    return moon, em, path, em_path, d


GLITTER_PHASES = []
PATH12_SPEC, PATH12_EM = 0.02, 0.62
MOON_HALO = []
MOON_HALO_K = 0.15


def build_boat():
    """Final fishing boat (moon_models.boat) + amber column of the lights on the water (child that points at the camera) +
    wake (only in 07)."""
    b = mm.boat("Boat")
    gm, gem, gphase = mm.glitter_mat("BoatGlitter", kit.LUZ, 0.5, 0.02, 1e4, 2e4, seed=7.0, near_fade=(4.0, 45.0),
                                     density=0.5)
    GLITTER_PHASES.append(gphase)
    glit = mm.strip_mesh("BoatGlitter", 2.5, 45.0, lambda y: 3.0 * (0.5 + 0.02 * y) + 0.2, gm, steps=24, z=0.1)
    glit.parent = b.root
    glit.rotation_mode = "XYZ"
    foam = kit.flat("Wake", "#E8EEF4", rough=0.9, emission="#E8EEF4", strength=0.25)
    wk = mm.wake("BoatWake", foam)
    wk.parent = b.root
    wk.location.z = 0.07
    return b, gem, glit, wk


def build_cape():
    dark = kit.flat("Cape", "#0A0E16", rough=1.0)
    v, f = kit._prism_geo(5, 1.0, 0.25, 40.0, sx=260.0, sy=40.0)
    o = kit.mesh_object("Cape", v, f, [dark], (-330, 900, -5))
    o.visible_shadow = False
    return o


FADE_STEPS = {-4: 0.0, -3: 0.48, -2: 0.79, -1: 0.97, 0: 0.97, 1: 0.79, 2: 0.48, 3: 0.0}


def build_cut_fade(tm, cam):
    """Fade 4+4 through dark at the jump cuts (V2-D): a black frame in front of the lens (child of the camera) darkens the
    image in 4 frames (equal steps ON SCREEN), swaps in the dark and the new one rises in 4. Cuts: 04>05 (q466), 10>11 (q1646),
    11>12 (q1941) and the internal cut of 10 on "Then" (globe -> noon). Frame N is the 1st of the new scene: the two darkest
    are at N-1 and N (the swap falls between them)."""
    mat, _, fac = mm.fade_emitter("CutFade", "#030509", 1.0)
    # The mesh sits 0.3 m in front of the lens, but the ORIGIN sits 40 m behind the camera: Eevee sorts the translucent pieces
    # by origin, and the glint strips on the water (origin at the observer, behind the camera) and the stars were drawn
    # on top of the dark (measured at q1646: stars at 253 with the plane at 0.99).
    verts = [(-0.5, -0.7, -40.3), (0.5, -0.7, -40.3), (0.5, 0.7, -40.3), (-0.5, 0.7, -40.3)]
    pl = kit.mesh_object("CutFade", verts, [(0, 1, 2, 3)], [mat])
    pl.parent = cam
    pl.location = (0.0, 0.0, 40.0)
    pl.visible_shadow = False
    # alphas per cut, measured so the mean-brightness jump stays <= 40 levels per frame (the day drops more slowly at the start)
    day_out = {-4: 0.0, -3: 0.42, -2: 0.70, -1: 0.92, 0: 1.0, 1: 0.79, 2: 0.48, 3: 0.0}     # -1: 0.88 gave 45 levels
    then_in = {**FADE_STEPS, 1: 0.82, 2: 0.50}
    # round 7 (M-6): the 2 middle frames of the darks with the lamp in frame (04>05, 11>12) stay at 1.0: with 0.97 the lantern
    # (emission 8) still came through at ~150 in the dark
    lamp_cut = {**FADE_STEPS, -1: 1.0, 0: 1.0}
    # round 7 (M-1): 06>07 with a 3+3 fade through dark (simple version of the plan), over the pitch match that already exists
    # (06 rises +4 degrees with ease-in, 07 opens 4 degrees below); alphas for steps <= 40 between the lilac (70) and the pink (95)
    fade33 = {-3: 0.0, -2: 0.55, -1: 0.9, 0: 0.9, 1: 0.55, 2: 0.0}
    cuts = [(tm.f("05", 0), lamp_cut), (tm.f("07", 0), fade33), (tm.f("08", 0), FADE_STEPS), (tm.f("10", CUT10), then_in),
            (tm.f("11", 0), day_out), (tm.f("12", 0), lamp_cut)]
    # alphas chosen so the brightness ON SCREEN falls/rises in equal steps: the blend is linear and the screen is ~gamma 2.2
    kit.key(fac, "default_value", 0.0, 1)
    hides = [(1, True)]
    for f_cut, steps in cuts:
        for d, a in steps.items():
            kit.key(fac, "default_value", a, f_cut + d)
        hides += [(f_cut - 4, False), (f_cut + 4, True)]
    kit.key(fac, "default_value", 0.0, tm.tl.frames)
    for f, h in hides:
        pl.hide_render = h
        pl.keyframe_insert("hide_render", frame=f)
    return pl


# ---------- ghost waves of 05 and 06 (V2-C1) ----------

def ghost_state(tm, sid, t):
    """(top height in m, body alpha). 05: the blade rises from the real water (+0.4) to +1.2 between "That" and "Sun", holds
    until "Moon", drops to +0.4 on "together" and vanishes (q625-640). 06: on "never" it leaves the water, rises only to +0.8 on "back",
    holds until q733, falls and vanishes by q745 (the wave that does not reach the +1.2 mark)."""
    q = lambda frame: (frame - tm.f(sid, 0)) / tm.tl.fps
    if sid == "05":
        t0, t1, t2, t3 = W("05", "that"), W("05", "sun"), W("05", "moon"), W("05", "together")
        if t < t0:
            return 0.4, 0.0
        if t < t1:
            top = 0.4 + 0.8 * smooth((t - t0) / (t1 - t0))
        elif t < t2:
            top = 1.2
        elif t < t3:
            top = 1.2 - 0.8 * smooth((t - t2) / (t3 - t2))
        else:
            top = 0.4
        al = 0.35 * min(1.0, (t - t0) / 0.1) * (1.0 - min(max((t - q(625)) / (q(640) - q(625)), 0.0), 1.0))
        return top, al
    tn, tb, th = W("06", "never"), W("06", "back"), q(733)
    if t < tn or t > q(745):
        return 0.4, 0.0
    if t < tb:
        base = tide("06", tn)
        top = base + (0.8 - base) * smooth((t - tn) / (tb - tn))
    elif t < th:
        top = 0.8
    else:
        top = 0.8 + (tide("06", q(745)) - 0.8) * smooth((t - th) / (q(745) - th))
    al = 0.29 * min(1.0, (t - tn) / 0.1) * (1.0 - min(max((t - th) / (q(745) - th), 0.0), 1.0))
    return max(top, tide("06", t)), al


def ghost_water_mat(name):
    """Ghost water (V2-C1, round 2): blade of the dawn water color, semitransparent, with a wavy top and a
    soft edge, a broken foam waterline and sides that fade (no straight frame or glass box).
    Object coordinates = the board's (x sideways, z up, in meters). Returns (mat, top socket, alpha socket, W phase)."""
    mat, n, links, out = mm.node_mat(name)
    M = lambda op, a, b=None, clamp=False: ms._math(n, links, op, a, b, clamp)
    tc = n.new("ShaderNodeTexCoord")
    sx = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sx.inputs[0])
    x, z = sx.outputs["X"], sx.outputs["Z"]
    top, alpha = n.new("ShaderNodeValue"), n.new("ShaderNodeValue")
    # round 7 (A2): WAVY top (2 noise waves along x, amplitude ~8 cm), CONTINUOUS foam crest (no noise
    # that breaks it into strokes; only the thickness varies), sides that fade within the board's width (1.2 m blade against
    # the board's 1.0 m; before 1.7 m going past both sides), body in the mauve water color at ~60%
    cb = n.new("ShaderNodeCombineXYZ")
    links.new(M("MULTIPLY", x, 2.2), cb.inputs["X"])
    nz = n.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 1.0, 1.0
    links.new(cb.outputs[0], nz.inputs["Vector"])
    cb2 = n.new("ShaderNodeCombineXYZ")
    links.new(M("MULTIPLY", x, 6.0), cb2.inputs["X"])
    cb2.inputs["Y"].default_value = 5.0
    nz2 = n.new("ShaderNodeTexNoise")
    nz2.noise_dimensions = "4D"
    nz2.inputs["Scale"].default_value, nz2.inputs["Detail"].default_value = 1.0, 0.0
    links.new(cb2.outputs[0], nz2.inputs["Vector"])
    wob = M("ADD", M("MULTIPLY", M("SUBTRACT", nz.outputs["Fac"], 0.5), 0.26), M("MULTIPLY", M("SUBTRACT", nz2.outputs["Fac"], 0.5), 0.07))
    topw = M("ADD", top.outputs[0], wob)
    rel = M("SUBTRACT", z, topw)                                   # < 0 inside the water
    body = ms._maprange(n, links, rel, -0.06, -0.005, 1.0, 0.0)
    side = ms._maprange(n, links, M("ABSOLUTE", x), 0.34, 0.60, 1.0, 0.0)
    # continuous foam: strip just below the top, 1.4 to 2.6 cm (the thickness varies slowly with the wide noise)
    thick = ms._maprange(n, links, nz.outputs["Fac"], 0.3, 0.7, 0.014, 0.026)
    fz = M("ABSOLUTE", M("ADD", rel, 0.012))
    foam = M("SUBTRACT", 1.0, M("DIVIDE", fz, thick), clamp=True)
    foam = M("POWER", foam, 0.7)
    # body with light horizontal veins (water, not glass): noise stretched in x
    cb3 = n.new("ShaderNodeCombineXYZ")
    links.new(M("MULTIPLY", x, 2.0), cb3.inputs["X"])
    links.new(M("MULTIPLY", z, 16.0), cb3.inputs["Y"])
    nz3 = n.new("ShaderNodeTexNoise")
    nz3.noise_dimensions = "4D"
    nz3.inputs["Scale"].default_value, nz3.inputs["Detail"].default_value = 1.0, 1.0
    links.new(cb3.outputs[0], nz3.inputs["Vector"])
    streak = ms._maprange(n, links, nz3.outputs["Fac"], 0.35, 0.7, 0.0, 0.5)
    col = ms._mixc(n, links, streak, lin("#5E4A60"), lin("#7A6280"))
    col = ms._mixc(n, links, foam, col, lin("#EDE4EE"))
    a_body = M("MULTIPLY", body, 1.0)
    a_all = M("MAXIMUM", a_body, M("MULTIPLY", foam, 1.5))
    a_all = M("MULTIPLY", M("MULTIPLY", a_all, side), alpha.outputs[0], clamp=True)
    em = n.new("ShaderNodeEmission")
    links.new(col, em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    mix = n.new("ShaderNodeMixShader")
    links.new(a_all, mix.inputs["Fac"])
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    for w_ in (nz, nz2, nz3):
        PAD_PHASE.append((w_.inputs["W"], 0.0))
    return mat, top.outputs[0], alpha.outputs[0]


def build_ghost(tm):
    """Ghost water blade in front of the board (see ghost_water_mat): 35% in 05 and 25% in 06. The REAL water (SeaPad) does not
    move: the ruler does not lie. The lower part stays under the real water (hidden)."""
    board = RULER_BOARD[0]
    mat, top, alpha = ghost_water_mat("GhostWater")
    v, f = ms.rect_geo(-0.62, 0.62, 0.15, 1.45)
    verts = [(x, -0.078, y) for x, y, _ in v]
    sheet = kit.mesh_object("GhostWater", verts, f, [mat])
    sheet.parent = board
    sheet.visible_shadow = False
    for sid in SCENES:
        a, b = tm.f(sid, 0), tm.last(sid)
        for f_ in range(a, b + 1) if sid in ("05", "06") else (a, b):
            tp, al = ghost_state(tm, sid, (f_ - a) / tm.tl.fps) if sid in ("05", "06") else (0.4, 0.0)
            top.default_value, alpha.default_value = tp, min(1.0, al / 0.35 * 0.6)      # ~60% in 05, ~43% in 06
            top.keyframe_insert("default_value", frame=f_)
            alpha.keyframe_insert("default_value", frame=f_)
    vis(tm, sheet, ("05", "06"))
    return sheet


# ---------- winter (10 and 11) ----------

def _floe(rnd, cx, cy, r, top, bot, n=None):
    """Ice plate of 5 to 9 sides, with its own rotation and uneven sides (art.md C: no honeycomb)."""
    n = n or rnd.randint(5, 9)
    rot = rnd.uniform(0, 2 * math.pi)
    pts = []
    for i in range(n):
        a = rot + 2 * math.pi * (i + rnd.uniform(-0.3, 0.3)) / n
        rr = r * rnd.uniform(0.7, 1.15)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    v = [(x, y, top) for x, y in pts] + [(x, y, bot) for x, y in pts]
    f = [tuple(range(n))] + [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return v, f


def sea_ice(tm, near, far):
    """Sea freezing in 11: flat ice plates near the pier (children of the near sea, rise and fall with the
    tide) and an ice field around the boat (~250 m) with loose plates in the way. Size grows with distance
    (each plate >= ~6 px on screen). White top, bluish side."""
    rnd = random.Random(21)
    top_m = kit.flat("IceTop", "#DCE4EE", rough=0.9, emission="#DCE4EE", strength=0.05)
    side_m = kit.flat("IceSide", "#9FB9CC", rough=0.5)
    top_b = kit.flat("IceTopB", "#B8C6D8", rough=0.9, emission="#B8C6D8", strength=0.05)
    top_s = kit.flat("IceTopSnow", "#EEF3F8", rough=1.0, emission="#EEF3F8", strength=0.05)
    tone = lambda: rnd.choices((0, 2, 3), (0.5, 0.3, 0.2))[0]          # 2 tones + 20% with snow on top
    placed, parts = [], []

    def ok(x, y, r):
        return all(math.hypot(x - a, y - b) > (r + rb) * 0.85 for a, b, rb in placed)

    placed.append((RULER.x, RULER.y, 0.9))
    parts.append(_floe(rnd, RULER.x, RULER.y, 0.9, 0.09, -0.06, n=9))       # ice collar on the ruler post
    tones = [3]
    for _ in range(900):
        y = 6.5 + 64 * rnd.random() ** 1.6
        x = rnd.uniform(-45, 50)
        if abs(x) < 1.6 and y < 6.4:
            continue
        r = (0.5 + 0.07 * math.hypot(x, y)) * rnd.uniform(0.6, 1.3) * rnd.choice((0.6, 1.0, 1.0, 1.8))
        if ok(x, y, r):
            placed.append((x, y, r))
            parts.append(_floe(rnd, x, y, r, 0.09, -0.06))
            tones.append(tone())
    for x in (-1.9, 1.9):                                                       # along the pier
        for k in range(10):
            y = -6 + 1.3 * k + rnd.uniform(-0.3, 0.3)
            r = rnd.uniform(0.4, 0.7)
            parts.append(_floe(rnd, x + rnd.uniform(-0.3, 0.3) * (1 if x > 0 else -1), y, r * rnd.choice((0.6, 1.0, 1.5)), 0.09, -0.06))
            tones.append(tone())
    v, f, own = kit.merge(*parts)
    mats = []
    for face, ow in zip(f, own):
        mats.append(tones[ow] if len({round(v[i][2], 3) for i in face}) == 1 else 1)
    ice_n = kit.mesh_object("SeaIceNear", v, f, [top_m, side_m, top_b, top_s], face_mats=mats)
    kit.fix_normals(ice_n)
    ice_n.parent = near
    # pack ice around the boat and to the horizon (boat stuck in the ice): loose plates of 66 to ~98 m and, from there on,
    # a continuous sheet of ice in cells (polar grid: fixed angle, rows x1.22 in distance; no gaps, no
    # overlap) in two tones of white. The distant sea has its origin at the corner (far.location): the child compensates.
    ox, oy = far.location.x, far.location.y
    parts, placed, tones = [], [], []
    for _ in range(260):
        y = rnd.uniform(66, 98)
        x = rnd.uniform(-60, 60)
        r = (0.07 * math.hypot(x, y)) * rnd.uniform(0.6, 1.2) * rnd.choice((0.6, 1.0, 1.0, 1.8))
        if ok(x, y, r):
            placed.append((x, y, r))
            parts.append(_floe(rnd, x, y, r, 0.20, -0.05))
            tones.append(tone())
    v, f, own = kit.merge(*parts)
    mats = [tones[ow] if len({round(v[i][2], 3) for i in face}) == 1 else 1 for face, ow in zip(f, own)]
    ice_f = kit.mesh_object("SeaIceFar", [(x - ox, y - oy, z) for x, y, z in v], f, [top_m, side_m, top_b, top_s], face_mats=mats)
    kit.fix_normals(ice_f)
    ice_f.parent = far
    top2_m = kit.flat("IceTop2", "#DCE7F0", rough=0.6, emission="#DCE7F0", strength=0.07)
    ys = [100.0 * 1.22 ** k for k in range(19)]                       # 100 m ... ~4 km
    ncol, amax = 100, math.radians(72)
    angs = [-amax + 2 * amax * j / ncol for j in range(ncol + 1)]
    verts, faces, kinds = [], [], []
    z_top, z_bot = 0.16, -0.05
    for k, yk in enumerate(ys):
        for j, a_ in enumerate(angs):
            jit = rnd.uniform(-9.0, 12.0) if k == 0 else 0.0           # irregular edge at the front
            verts.append((yk * math.tan(a_) - ox, yk + jit - oy, z_top))
    for k in range(len(ys) - 1):
        for j in range(ncol):
            i0 = k * (ncol + 1) + j
            faces.append((i0, i0 + 1, i0 + ncol + 2, i0 + ncol + 1))
            kinds.append(rnd.choice((0, 0, 1)) if k <= 5 else 0)
    # skirt of the front edge (bluish side) so the plate does not float
    base = len(verts)
    for j, a_ in enumerate(angs):
        x, y, _ = verts[j]
        verts.append((x, y, z_bot))
    for j in range(ncol):
        faces.append((j, base + j, base + j + 1, j + 1))
        kinds.append(2)
    sheet = kit.mesh_object("SeaIceSheet", verts, faces, [top_m, top2_m, side_m], face_mats=kinds)
    kit.fix_normals(sheet)
    sheet.parent = far
    for o in (ice_n, ice_f, sheet):
        o.visible_shadow = False
        vis(tm, o, ("11",))


def snow_layers(tm):
    """Real snow (10 from "colder", and 11): 10 cm layer on the deck with a visible edge, crests on the
    railings and mounds on the posts (grow by z scale from 2 mm INSIDE the wood: hidden before);
    icicles on the railings and the fascia (only in 11)."""
    rnd = random.Random(33)
    snow = kit.flat("Snow", "#E6ECF4", rough=1.0, emission="#E6ECF4", strength=0.04)     # matte (art.md C): no plastic shine
    kit.principled(snow).inputs["Specular IOR Level"].default_value = 0.2
    # variation (round 7, M-3): wide patches slightly colder/darker (wind tracks), no fine texture that shimmers
    snt = snow.node_tree
    stc = snt.nodes.new("ShaderNodeTexCoord")
    snz = snt.nodes.new("ShaderNodeTexNoise")
    snz.inputs["Scale"].default_value, snz.inputs["Detail"].default_value = 0.9, 2.0
    snt.links.new(stc.outputs["Object"], snz.inputs["Vector"])
    smix = ms._mixc(snt.nodes, snt.links, ms._maprange(snt.nodes, snt.links, snz.outputs["Fac"], 0.42, 0.62), lin("#E6ECF4"), lin("#C9D2E2"))
    snt.links.new(smix, kit.principled(snow).inputs["Base Color"])
    ice = kit.flat("Icicle", "#CFE6F2", rough=0.3, emission="#CFE6F2", strength=0.12)
    # deck: grid with irregular top (8 to 12 cm) and skirt down to the edge
    xs = [-1.27 + 2.54 * i / 10 for i in range(11)]
    ys = [-14.0 + 20.08 * j / 60 for j in range(61)]
    verts, faces = [], []
    nx = len(xs)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            edge = i in (0, nx - 1) or j == len(ys) - 1
            drift = 0.03 * math.sin(0.9 * y + 1.3 * x) + 0.02 * math.sin(2.3 * y - 0.7 * x + 1.0)   # snow mounds (not a slab)
            verts.append((x, y, (0.075 if edge else max(0.06, rnd.uniform(0.09, 0.115) + drift)) + 0.002))
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    base = len(verts)
    border = [j * nx for j in range(len(ys))] + [(len(ys) - 1) * nx + i for i in range(1, nx)] + \
        [j * nx + nx - 1 for j in range(len(ys) - 2, -1, -1)]
    for k in border:
        x, y, _ = verts[k]
        verts.append((x, y, 0.0))
    for k in range(len(border) - 1):
        faces.append((border[k], border[k + 1], base + k + 1, base + k))
    deck = kit.mesh_object("SnowDeck", verts, faces, [snow], (0, 0, DECK - 0.002))
    kit.fix_normals(deck)
    # railings (flattened crest) and posts (mound), origin 2 mm below the top of the wood
    top = DECK + 1.010
    parts = []
    for x in (-1.145, 1.145):
        parts.append(kit.tube_geo([(x, -14.0, 0.004), (x, 5.95, 0.004)], [0.06, 0.06], n=6, squash=0.45))
    parts.append(kit.tube_geo([(-1.15, 5.965, 0.004), (1.15, 5.965, 0.004)], [0.06, 0.06], n=6, squash=0.45))
    for yy in PILE_ROWS:
        for x in (-1.15, 1.15):
            parts.append(kit._ico_geo(1.0, (x, min(yy, 5.9), 0.012), (0.085, 0.085, 0.045)))
    v, f, _ = kit.merge(*parts)
    rails = kit.mesh_object("SnowRails", v, f, [snow], (0, 0, top))
    parts = []
    for x in (-1.145, 1.145):
        parts.append(kit.tube_geo([(x, -14.0, 0.004), (x, 5.95, 0.004)], [0.05, 0.05], n=6, squash=0.4))
    parts.append(kit.tube_geo([(-1.15, 5.965, 0.004), (1.15, 5.965, 0.004)], [0.05, 0.05], n=6, squash=0.4))
    v, f, _ = kit.merge(*parts)
    mid = kit.mesh_object("SnowRailsMid", v, f, [snow], (0, 0, DECK + 0.518))
    c = W("10", "colder")
    for o in (deck, rails, mid):
        o.visible_shadow = True
        bv = o.modifiers.new("Bevel", "BEVEL")           # 2 cm chamfered edge: the layer reads as volume
        bv.width, bv.segments, bv.limit_method = 0.02, 1, "ANGLE"
        for sid in SCENES:
            track(tm, o, "scale", sid, [(0, (1, 1, 1) if sid == "11" else (1, 1, 0.001))])
        track(tm, o, "scale", "10", [(0, (1, 1, 0.001)), (c + 0.1, (1, 1, 0.001)), (min(c + 0.76, tm.dur("10")), (1, 1, 1))])
        vis(tm, o, ("10", "11"))
    # icicles (11): hanging under the top and middle railings and under the fascia at the tip
    cones = []

    def hang(x, y, z, L, r):
        cones.append(kit._prism_geo(5, 0.002, r, L, oz=z - L, ox=x, oy=y))

    def L(base):                       # length 40-160% (sometimes a very long one), groups and gaps (art.md C)
        k = rnd.uniform(0.4, 1.6) * (1.9 if rnd.random() < 0.08 else 1.0)
        return base * k

    def step(base):
        return base * rnd.uniform(0.65, 1.35) * (2.6 if rnd.random() < 0.15 else 1.0)

    for x in (-1.145, 1.145):
        y = -4.0
        while y < 5.9:
            if rnd.random() > 0.2:
                hang(x, y, DECK + 0.9, L(0.12), rnd.uniform(0.010, 0.022))
            if rnd.random() < 0.5:
                hang(x, y + rnd.uniform(0.02, 0.08), DECK + 0.45, L(0.08), rnd.uniform(0.009, 0.016))
            y += step(0.18)
    x = -1.1
    while x < 1.1:
        if rnd.random() > 0.2:
            hang(x, 5.965, DECK + 0.9, L(0.13), rnd.uniform(0.010, 0.022))
        if rnd.random() < 0.6:
            hang(x + rnd.uniform(0.0, 0.06), 5.965, DECK + 0.45, L(0.09), rnd.uniform(0.009, 0.016))
        if rnd.random() > 0.25:
            hang(x + rnd.uniform(0.0, 0.05), 6.03, DECK - 0.28, L(0.19), rnd.uniform(0.012, 0.026))
        x += step(0.15)
    v, f, _ = kit.merge(*cones)
    icic = kit.mesh_object("Icicles", v, f, [ice])
    kit.fix_normals(icic)
    icic.visible_shadow = False
    vis(tm, icic, ("11",))


# ---------- animals ----------

OWL_POST = (-1.15, 3.0, DECK + 1.02)        # top of the post cap
MOUSE_WAIT = (0.0, 2.5)
MOUSE_S = 2.3                               # mice 1.5x (mouse 1 ~250 px long; mouse 2 the same size in the world)


def build_owl(post):
    """Final owl (moon_models.owl) at 2x (0.6 m, marked exaggeration) on top of the post."""
    o = mm.owl("Owl")
    o.root.location = post
    o.root.scale = (2.0, 2.0, 2.0)
    return o


def head_angle(x_from, y_from, x_to, y_to):
    """Z angle of the head (face along local -y) to look from point 'from' to point 'to'."""
    return math.atan2(x_to - x_from, -(y_to - y_from))


PITCH_OWL = 0.6


def animate_owl(tm, o):
    """Head: looks outward; on 'spot' turns quickly to the mouse (overshoots 8 degrees and comes back) and tilts curiously; on
    'Without' turns to the opposite side. Slow micro-movement while waiting, blinks and body breathing."""
    ox, oy = OWL_POST[0], OWL_POST[1]
    idle = math.radians(-40)
    to_mouse = head_angle(ox, oy, MOUSE_WAIT[0], MOUSE_WAIT[1])
    away = math.radians(-100)
    t_spot, t_wo = W("04", "spot"), W("04", "without")
    over = math.radians(8)

    t_turn = t_spot - 0.42            # turns on "can" and is already looking at the mouse when it says "spot"
    f1 = 1.0 / 30
    turn_sign = 1.0 if (away - to_mouse) > 0 else -1.0
    antic = math.radians(5) * turn_sign

    def settle(t):                    # body follows the turn by 2 degrees, 6 frames late, with a slight overshoot, and settles
        u = (t - (t_wo - 0.03 + 6 * f1)) / 0.4
        if u <= 0:
            return 0.0
        return turn_sign * math.radians(2.0) * (smooth(u) + 0.25 * math.sin(math.pi * min(u, 1.0)))

    def yaw(t):
        if t < t_turn:
            return idle
        if t < t_spot - 0.08:
            return lerp(idle, to_mouse + over, smooth((t - t_turn) / (t_spot - 0.08 - t_turn)))
        if t < t_spot + 0.2:
            return lerp(to_mouse + over, to_mouse, smooth((t - t_spot + 0.08) / 0.28))
        if t < t_wo - 0.03 - 2 * f1:
            return to_mouse
        if t < t_wo - 0.03:                # anticipation (art.md D8): 2 frames, the head pulls back 5 degrees before turning
            return lerp(to_mouse, to_mouse - antic, smooth((t - (t_wo - 0.03 - 2 * f1)) / (2 * f1)))
        if t < t_wo + 0.3:
            return lerp(to_mouse - antic, away - over, smooth((t - t_wo + 0.03) / 0.33))
        if t < t_wo + 0.55:
            return lerp(away - over, away, smooth((t - t_wo - 0.3) / 0.25))
        return away

    def tilt(t):
        on = smooth((t - t_spot + 0.1) / 0.3) * (1 - smooth((t - t_wo) / 0.3))
        return 0.2 * on

    def pitch(t):                     # head down, toward the mouse (under the post), until it turns on "Without"
        on = smooth((t - t_turn) / 0.4) * (1 - smooth((t - t_wo + 0.03) / 0.33))
        return PITCH_OWL * on

    blinks = [0.75, t_spot + 0.55, t_wo + 0.75]
    a, b = tm.f("04", 0), tm.last("04")
    for f in range(a, b + 1):
        t = (f - a) / tm.tl.fps
        o.neck.rotation_euler = (pitch(t) + 0.03 * math.sin(t * 1.3), tilt(t) + 0.02 * math.sin(t * 0.9 + 1), yaw(t) + 0.025 * math.sin(t * 1.7))
        o.neck.keyframe_insert("rotation_euler", frame=f)
        lid = 0.05
        for tb in blinks:
            k = abs(t - tb) * tm.tl.fps
            if k < 3:
                lid = max(lid, 1.0 - 0.32 * max(0.0, k - 0.5))
        for l_ in o.lids:
            l_.scale = (1, 1, lid)
            l_.keyframe_insert("scale", index=2, frame=f)
        o.body.scale = (1, 1, 1 + 0.012 * math.sin(t * 2 * math.pi / 2.2))
        o.body.keyframe_insert("scale", index=2, frame=f)
        o.body.rotation_euler.z = settle(t)
        o.body.keyframe_insert("rotation_euler", index=2, frame=f)


# Caption occupies y 1250-1330 (1080x1920): no mouse passes through that strip. Mouse 1 stays in the lower strip (top of the silhouette at y >= 1350),
# standing still with its back turned and then walking sideways/diagonally to the left; mouse 2 comes out from behind the crate (higher up, base at y <= 1200).
MOUSE1 = [(0.0, 2.3), (-0.15, 2.3), (-0.34, 2.3)]      # stops before the @ (x 72-300, y 1440-1480): the mouse does not pass behind it
MOUSE2 = [(0.6, 4.8), (0.3, 4.62), (0.18, 4.35), (0.12, 4.05)]
CRATE = (0.50, 4.35)


def build_crate():
    """Slatted crate (0.4 x 0.4 x 0.32 m) near the right railing: mouse 2 comes out from behind it."""
    return mm.crate("Crate", (CRATE[0], CRATE[1], DECK))


def walk(tm, m, pts, t0, t1, h0=None):
    """Route along the polyline pts (x, y) from t0 to t1 (seconds of scene 04), with smooth acceleration and braking; still
    before and after. The heading follows the direction, smoothed. The legs come from mm.animate_mouse (planted foot)."""
    P = [Vector((x, y, 0)) for x, y in pts]
    seglen = [(b - a).length for a, b in zip(P, P[1:])]
    tot = sum(seglen)

    def at(u):
        d = u * tot
        for a, b, l in zip(P, P[1:], seglen):
            if d <= l:
                return a.lerp(b, d / l), (b - a)
            d -= l
        return P[-1], P[-1] - P[-2]

    head, omega = None, 0.0
    a, b = tm.f("04", 0), tm.last("04")
    frames = []
    for f in range(a, b + 1):
        t = (f - a) / tm.tl.fps
        u = smooth((t - t0) / (t1 - t0))
        p, dirv = at(u)
        target = math.atan2(-dirv.x, dirv.y) if (t > t0 or h0 is None) else h0
        if head is None:
            head = target if h0 is None else h0
        diff = (target - head + math.pi) % (2 * math.pi) - math.pi
        # turn with a nearly critical spring (round 7, B-1): starts slowly and settles without overshoot (before: 22% of the turn in the 1st frame)
        omega += 0.035 * diff - 0.37 * omega
        head += omega
        frames.append((f, p.x, p.y, DECK + 0.002, head))
    mm.animate_mouse(m, frames, tm.tl.fps, seed=len(pts))


# ---------- globe, axis, arcs ----------

def build_globe(tm, loc):
    tilt = bpy.data.objects.new("GlobeTilt", None)
    bpy.context.collection.objects.link(tilt)
    tilt.location = loc
    earth = mm.earth("Earth", random.Random(3))          # today's continents (globe.py), 25% emissive
    g = earth.root
    g.parent = tilt
    g.location = (0, 0, 0)
    g.scale = (0.05, 0.05, 0.05)                        # radius 10 -> 0.5 m
    g.rotation_mode = "XYZ"
    amber, _ = emitter("AxisMat", kit.LUZ, 2.0)
    axis = kit.box("Axis", (0, 0, 0), (0.025, 0.025, 1.4), amber)
    axis.location = (-0.0125, -0.0125, -0.7)
    axis.parent = tilt
    axis.visible_shadow = False
    return tilt, g, axis


def arc_object(name, radius, color, strength, tube=0.9, n=36, parent=None):
    mat, em = emitter(name + "Mat", color, strength)
    pts = [(radius * math.cos(math.pi * i / n), radius * math.sin(math.pi * i / n), 0.0) for i in range(n + 1)]
    v, f = kit.tube_geo(pts, [tube] * len(pts), n=4)
    o = kit.mesh_object(name, v, f, [mat])
    o.visible_shadow = False
    return o, em


def horizon_glow(name, R=3700.0):
    """Cylindrical band (radius R, from -60 to +60 degrees around the +y heading) with additive emission by height: amber core on the
    horizon line and warm gradient that fades at 3 degrees. Returns (object, alpha socket 0..1)."""
    H = R * math.tan(math.radians(3.0))
    verts, faces, n = [], [], 64
    for i in range(n + 1):
        a = math.radians(-60 + 120 * i / n)
        for z in (-8.0, H):
            verts.append((R * math.sin(a), R * math.cos(a), z))
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    mat, n_, links, out = mm.node_mat(name + "Mat")
    tc = n_.new("ShaderNodeTexCoord")
    sx = n_.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sx.inputs[0])
    g = ms._maprange(n_, links, sx.outputs["Z"], 0.0, H, 0.0, 1.0, smoothstep=False)
    warm = ms._maprange(n_, links, g, 0.0, 1.0, 1.0, 0.0)
    warm = ms._math(n_, links, "POWER", warm, 1.6)
    col = ms._mixc(n_, links, g, lin("#E08A4A"), lin("#7A3A4A"))
    k = ms._math(n_, links, "MULTIPLY", warm, 0.42)
    # core (round 7, M-3): center at +12 m and half-width 12 m (~3.8 px at 3.7 km) with a soft edge: stays WHOLE above the
    # ice edge (which cuts everything below z ~0 at that distance). Before: center at 3 m, +-6.5 m, half cut = 1 px thread
    core = ms._math(n_, links, "ABSOLUTE", ms._math(n_, links, "SUBTRACT", sx.outputs["Z"], 12.0))
    core = ms._maprange(n_, links, core, 0.0, 12.0, 1.0, 0.0)
    em1 = n_.new("ShaderNodeEmission")
    links.new(col, em1.inputs["Color"])
    em2 = n_.new("ShaderNodeEmission")
    em2.inputs["Color"].default_value = lin(kit.LUZ)
    alpha = n_.new("ShaderNodeValue")
    links.new(ms._math(n_, links, "MULTIPLY", k, alpha.outputs[0]), em1.inputs["Strength"])
    links.new(ms._math(n_, links, "MULTIPLY", ms._math(n_, links, "MULTIPLY", core, 0.5), alpha.outputs[0]), em2.inputs["Strength"])
    add = n_.new("ShaderNodeAddShader")
    links.new(em1.outputs[0], add.inputs[0])
    links.new(em2.outputs[0], add.inputs[1])
    add2 = n_.new("ShaderNodeAddShader")
    links.new(n_.new("ShaderNodeBsdfTransparent").outputs[0], add2.inputs[0])
    links.new(add.outputs[0], add2.inputs[1])
    links.new(add2.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    o = kit.mesh_object(name, verts, faces, [mat])
    o.visible_shadow = False
    return o, alpha.outputs[0]


def add_dust_lane(w):
    """Dark dust lane in the middle of the Milky Way of the pier sky (art.md B6, item 6): multiplies the band's brightness by
    1 - 0.8 x (narrow band slightly off center, broken by stretched noise)."""
    nt = w.world.node_tree
    strength = w.band.node
    src = strength.inputs[0].links[0].from_socket
    dot = next(nd for nd in nt.nodes if nd.bl_idname == "ShaderNodeVectorMath" and nd.operation == "DOT_PRODUCT")
    nrm = next(nd for nd in nt.nodes if nd.bl_idname == "ShaderNodeVectorMath" and nd.operation == "NORMALIZE")
    n, links = nt.nodes, nt.links
    lane = ms._maprange(n, links, ms._math(n, links, "ABSOLUTE", ms._math(n, links, "SUBTRACT", dot.outputs["Value"], 0.01)),
                        0.0, 0.03, 1.0, 0.0)
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 9.0, 3.0
    links.new(nrm.outputs[0], nz.inputs["Vector"])
    lane = ms._math(n, links, "MULTIPLY", lane, ms._maprange(n, links, nz.outputs["Fac"], 0.35, 0.6, 0.25, 0.85))
    keep = ms._math(n, links, "SUBTRACT", 1.0, lane, clamp=True)
    links.new(ms._math(n, links, "MULTIPLY", src, keep), strength.inputs[0])


# ---------- light ----------

def sun_dir_quat(d):
    return Vector(d).normalized().to_track_quat("Z", "Y").to_euler()


AMB_K, SUN_K = 0.65, 1.25      # look of 23/10 (art.md B): fill x0.65 and key (moonlight, sun) x1.25: the key rules


def lights(tm, w, d_moon):
    w.sun.specular_factor = 0.45                  # no blown-out shards on the sea facets (zero becomes a staircase of bars)
    moon_rot = tuple(sun_dir_quat(d_moon))
    dawn_rot = tuple(sun_dir_quat((-0.45, -0.55, 0.45)))
    star_rot = tuple(sun_dir_quat((0.2, 0.3, 1.0)))
    day_rot = tuple(sun_dir_quat((0.1, 0.5, 0.85)))
    space_rot = tuple(sun_dir_quat(tuple(ms.SUN_DIR)))
    base = dict(sky="night", sun=0.0, color=(0.80, 0.86, 0.96), rot=star_rot, amb=2.2, ambc="#33497A", skys=1.0)
    st = {
        "01": dict(base, sun=0.8, rot=moon_rot),
        "02": dict(base, amb=0.9),
        "03": dict(base, amb=0.9),
        "04": dict(base, amb=0.9),
        "05": dict(base, sky="dawn", sun=1.3, color=(1.0, 0.72, 0.62), rot=dawn_rot, amb=1.4, ambc="#7A6A8E"),
        "06": dict(base, sky="dawn", sun=1.3, color=(1.0, 0.72, 0.62), rot=dawn_rot, amb=1.4, ambc="#7A6A8E"),
        "07": dict(base, sky="dawn", sun=1.3, color=(1.0, 0.72, 0.62), rot=dawn_rot, amb=1.4, ambc="#7A6A8E"),
        # space (V2-B, art.md B6): Sun out of frame on the right (3.0, warm white), fill only 0.15 #1B2333
        "08": dict(base, sun=3.0 / SUN_K, color=(1.0, 0.97, 0.92), rot=space_rot, amb=0.15 / AMB_K, ambc="#1B2333"),
        "09": dict(base, sun=3.0 / SUN_K, color=(1.0, 0.97, 0.92), rot=space_rot, amb=0.15 / AMB_K, ambc="#1B2333"),
        "10": dict(base, sky="day", sun=3.4, color=(1.0, 0.95, 0.88), rot=day_rot, amb=1.6, ambc="#7F95B8"),
        "11": dict(base, sky="winter", amb=0.75, ambc="#343E5C"),     # round 7: less navy blue on the railing (was #2A3A66)
        "12": dict(base, sun=0.8, rot=moon_rot),
    }
    for sid in SCENES:
        s = st[sid]
        for name, sock in w.factors.items():
            track(tm, sock, "default_value", sid, [(0, 1.0 if name == s["sky"] else 0.0)])
        track(tm, w.sky, "default_value", sid, [(0, s["skys"])])
        track(tm, w.ambient_color, "default_value", sid, [(0, lin(s["ambc"]))])
        w.sun.color = s["color"]
        w.sun.keyframe_insert("color", frame=tm.f(sid, 0))
        w.sun.keyframe_insert("color", frame=tm.last(sid))
        track(tm, w.ambient, "default_value", sid, [(0, s["amb"] * AMB_K)])
        track(tm, w.sun, "energy", sid, [(0, s["sun"] * SUN_K)])
        track(tm, w.sun_obj, "rotation_euler", sid, [(0, s["rot"])])
    # light specular: 0.45 in the video; 0.1 with the Moon (01, 12): the Moon's reflection on the facets blew the path out to white
    # (measured at q1: 0.45 -> 4320 saturated px; 0.1 -> 1362, only in the core next to the horizon; 0 becomes loose glints only)
    for sid in SCENES:
        track(tm, w.sun, "specular_factor", sid, [(0, 0.1 if sid in ("01", "12") else 0.45)])
    # 01: the Moon vanishes (count reaches 0 at 1.68 s): moonlight and ambient drop in 0.3 s
    t0, t1 = 1.68, 1.98
    track(tm, w.sun, "energy", "01", [(0, 0.8 * SUN_K), (t0, 0.8 * SUN_K), (t1, 0.0)])
    track(tm, w.ambient, "default_value", "01", [(0, 2.2 * AMB_K), (t0, 2.2 * AMB_K), (t1, 0.9 * AMB_K)])
    # 12: the Moon returns in 1.2 s
    track(tm, w.sun, "energy", "12", [(0, 0.0), (1.2, 0.8 * SUN_K)])
    track(tm, w.ambient, "default_value", "12", [(0, 0.75 * AMB_K), (1.2, 2.2 * AMB_K)])
    # 10: opens at night (globe and axis, like 09) and cuts to noon on "Then"; the Sun drops on "colder"
    tc, f1, c = CUT10, 1.0 / 30, W("10", "colder")
    for name, sock in w.factors.items():
        a_, b_ = (1.0 if name == "night" else 0.0), (1.0 if name == "day" else 0.0)
        track(tm, sock, "default_value", "10", [(0, a_), (tc - f1, a_), (tc, b_)])
    track(tm, w.ambient, "default_value", "10", [(0, 0.15), (tc - f1, 0.15), (tc, 1.6 * AMB_K)])
    track(tm, w.ambient_color, "default_value", "10", [(0, lin("#1B2333")), (tc - f1, lin("#1B2333")), (tc, lin("#7F95B8"))])
    track(tm, w.sun, "energy", "10", [(0, 3.0), (tc - f1, 3.0), (tc, 3.4 * SUN_K), (c, 3.4 * SUN_K), (c + 0.9, 2.2 * SUN_K)])
    track(tm, w.sun_obj, "rotation_euler", "10", [(0, space_rot), (tc - f1, space_rot), (tc, day_rot)])
    w.sun.color = (1.0, 0.97, 0.92)
    w.sun.keyframe_insert("color", frame=tm.f("10", 0))
    w.sun.keyframe_insert("color", frame=tm.f("10", tc) - 1)
    w.sun.color = (1.0, 0.95, 0.88)
    w.sun.keyframe_insert("color", frame=tm.f("10", tc))


def build_sky_detail(tm, w, stars):
    _, reveal, power = stars
    hold(tm, power, "default_value", {sid: 5.0 for sid in SCENES})
    full = 1.2
    hold(tm, reveal, "default_value", {"01": 0.12, "02": 0.15, "04": full, "08": full, "09": full, "10": full, "11": full, "12": 0.12})
    track(tm, reveal, "default_value", "03", [(0, 0.05), (W("03", "brighter"), 0.05), (tm.dur("03"), full)])
    track(tm, reveal, "default_value", "12", [(0, full), (1.2, 0.12)])
    hold(tm, w.band, "default_value", {"03": 0.26, "04": 0.3, "08": 0.3, "09": 0.3, "10": 0.3, "11": 0.32, "02": 0.0})
    track(tm, w.band, "default_value", "10", [(0, 0.3), (CUT10 - 1 / 30, 0.3), (CUT10, 0.0)])
    # 02>03 (V2-D): the Milky Way enters at 0% at the cut and rises along with the stars, from "brighter" to the end of 03
    track(tm, w.band, "default_value", "03", [(0, 0.0), (W("03", "brighter"), 0.0), (tm.dur("03"), 0.26)])


# ---------- lamp reflection column ----------

def cam_pos_at(poses, tm, sid, f):
    """Camera position (without the sway) at frame f of scene sid: same interpolation as build_camera."""
    pts = poses[sid]
    t = (f - tm.f(sid, 0)) / tm.tl.fps
    pos = pts[0][1]
    for (t0, p0, _y0, _q0), (t1, p1, _y1, _q1) in zip(pts, pts[1:]):
        if t0 <= t <= t1 or (t1 == pts[-1][0] and t > t1):
            return p0.lerp(p1, seg_u(sid, pts, t0, t1, t))
    return pos


def place_lamp_column(tm, glit):
    """The column leaves the camera and points at the lamp (-1; 5.9): one per frame (the camera moves in 07, 11 and 04)."""
    poses = camera_poses(tm)
    for sid in ("01", "02", "03", "04", "07", "12"):
        a, b = tm.f(sid, 0), tm.last(sid)
        for f in range(a, b + 1):
            c = cam_pos_at(poses, tm, sid, f)
            glit.location.x, glit.location.y = c.x, c.y
            glit.rotation_euler.z = -math.atan2(-1.0 - c.x, 5.9 - c.y)
            glit.keyframe_insert("location", index=0, frame=f)
            glit.keyframe_insert("location", index=1, frame=f)
            glit.keyframe_insert("rotation_euler", index=2, frame=f)


# ---------- space (V2-B: 08, 09 and 10 up to "Then") ----------

def hermite(p0, p1, m0, m1, s):
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def tilt_deg(tm, f):
    """REAL axis tilt (degrees) at frame f. 08: 23. 09: from 'push' (q1351) to 'Too' (q1393) moves faster
    (23 -> 37.5), from there until q1460 it drags (37.5 -> 42, ease-out) and oscillates +-1 degree (fades at the end). 10: 42 until 'lean'
    (q1523), 42 -> 62 with ease-out until q1548, still at 62."""
    fp, ft, fe = tm.f("09", W("09", "push")), tm.f("09", W("09", "too")), tm.last("09") - 6
    fl = tm.f("10", W("10", "lean"))
    if f < fp:
        return 23.0
    if f <= fe:
        v1 = 0.12                                                 # degrees per frame on "Too": the speed drops
        if f <= ft:
            base = hermite(23.0, 37.5, 0.0, v1 * (ft - fp), (f - fp) / (ft - fp))
        else:
            base = hermite(37.5, 42.0, v1 * (fe - ft), 0.0, (f - ft) / (fe - ft))
        env = math.sin(math.pi * (f - fp) / (fe - fp))
        return base + 1.0 * env * math.sin(2 * math.pi * (f - fp) / (1.6 * 30))
    if f < fl:
        return 42.0
    u = min((f - fl) / 25.0, 1.0)
    return 42.0 + 20.0 * (1 - (1 - u) ** 3)


def build_space(tm, cam):
    """Plan V2-B space: Earth (moon_space.earth) with an axis fixed in space spinning from west to east (1 turn in
    6 s), Sun out of frame on the right, Moon and ring in 08, planets and force lines in 09, instrument ruler
    (vertical, axis, arc, label) attached to the camera; the amber line of 07 is the same axis as 08 (cut bridge)."""
    sp0, sp1 = space_range(tm)
    orbit = ms.Orbit(sp0, sp1)
    fcut = sp1 + 1
    S3 = ("08", "09", "10")

    def vis_space(o):
        vis(tm, o, S3)
        hide_at(tm, o, "10", CUT10)

    band_n = ms.space_band_normal()
    shell, sstars = ms.space_sky(band_n)
    glow = ms.sun_glow(cam)
    E = ms.earth()
    for o in (shell, sstars, glow, E.tilt):
        vis_space(o)
    # Earth: tilt, spin, rise (scale 0.95 -> 1 in q1076-1084), summer/winter tints in 08
    phase0 = math.radians(-138.0)                 # at q1100 meridian 0 faces the camera: Africa and Europe in the sun, the Americas in the night
    for f in range(sp0, sp1 + 1):
        E.tilt.rotation_euler = (0.0, math.radians(tilt_deg(tm, f)), 0.0)
        E.tilt.keyframe_insert("rotation_euler", index=1, frame=f)
        E.spin.rotation_euler.z = phase0 + 2 * math.pi * (f - sp0) / (6.0 * tm.tl.fps)
        E.spin.keyframe_insert("rotation_euler", index=2, frame=f)
        k = 0.95 + 0.05 * smooth((f - sp0) / 8.0)
        E.tilt.scale = (k, k, k)
        E.tilt.keyframe_insert("scale", frame=f)
    f_su, f_wi, f_ea = (tm.f("08", W("08", w_)) for w_ in ("summer", "winter", "earth"))
    for sock, f_on in ((E.north, f_su), (E.south, f_wi)):
        for fr, v in ((sp0, 0.0), (f_on, 0.0), (f_on + 6, 0.15), (f_ea - 8, 0.15), (f_ea, 0.0)):
            kit.key(sock, "default_value", v, fr)

    # Moon of 08 (0.27 R, on the ring of 1.7 R = 425 px) and amber ring -> dashed ghost
    ring_r, tube = 1.7, 0.007
    moon, m_alpha = ms.little_moon(0.245)            # ~68 px (0.27 of the Earth's radius on screen, slightly closer)
    a_m = math.radians(235.0)                         # on the left and in front: x ~120 px, without touching the Earth or the edge
    moon.location = ms.SPACE_E + Vector((ring_r * math.cos(a_m), ring_r * math.sin(a_m), 0.0))
    f_m1 = sp0 + 24                                   # vanishes by q1100 (0.8 s)
    m_dim = ms.dim_socket(bpy.data.materials["SpaceMoonMat"])
    for fr, v in ((sp0, 1.0), (f_m1 - 2, 1.0), (f_m1, 0.0)):         # alpha only at the ends (see ms.dim_socket)
        kit.key(m_alpha, "default_value", v, fr)
    for fr, v in ((sp0, 1.0), (sp0 + 8, 1.0), (f_m1 - 1, 0.0)):
        kit.key(m_dim, "default_value", v, fr)
    vis(tm, moon, ("08",))
    rings = {}
    for nm, col, dashed in (("RingAmber", kit.LUZ, False), ("RingGhost", "#8A94A6", True), ("RingGhostAmber", kit.LUZ, True)):
        mat, _, fac = mm.fade_emitter(nm + "Mat", col, 1.0)
        v_, f_ = ms.ring_mesh(nm, ring_r, tube, dashed)
        o = kit.mesh_object(nm, [tuple(ms.SPACE_E + Vector(p)) for p in v_], f_, [mat])
        o.visible_shadow = False
        rings[nm] = (o, fac)
    f_mo, f_st = tm.f("08", W("08", "moon's")), tm.f("08", W("08", "steady"))
    end09 = tm.last("09")
    seq = {
        "RingAmber": [(sp0, 1.0), (sp0 + 8, 1.0), (f_m1, 0.0)],
        "RingGhost": [(sp0, 0.0), (sp0 + 8, 0.0), (f_m1, 0.25), (f_mo, 0.25), (f_mo + 9, 0.0), (f_st, 0.0), (f_st + 18, 0.25),
                      (end09 - 6, 0.25), (end09, 0.0)],
        "RingGhostAmber": [(sp0, 0.0), (f_mo, 0.0), (f_mo + 9, 0.6), (f_st, 0.6), (f_st + 18, 0.0)],
    }
    for nm, pts in seq.items():
        o, fac = rings[nm]
        for fr, v in pts:
            kit.key(fac, "default_value", v, fr)
        vis(tm, o, ("08",) if nm != "RingGhost" else ("08", "09"))

    # planets of 09: rotate with the camera around the Earth (stay in the same place on the screen); in the orbit plane
    piv = bpy.data.objects.new("PlanetPivot", None)
    bpy.context.collection.objects.link(piv)
    piv.location = ms.SPACE_E
    piv.rotation_mode = "XYZ"
    f_ref = tm.f("09", 3.0)
    pos0, yaw0, pit0 = ms.cam_pose(0.0, orbit.r_px(f_ref))
    planets = []
    specs = [("Venus", (150, 780), 20), ("Jupiter", (850, 330), 45), ("Saturn", (170, 240), 30)]
    for nm, (px, py), rpx in specs:
        fwd, right, up = ms.basis(yaw0, pit0)
        d = (fwd + right * ((px - 540) / ms.F_SP) - up * ((py - 960) / ms.F_SP)).normalized()
        t = (ms.SPACE_E.z - pos0.z) / d.z
        P = pos0 + d * t
        r = rpx / ms.F_SP * (P - pos0).dot(fwd)
        if nm == "Venus":
            mat, alpha, *_ = ms.lit_fade("VenusMat", "#EAD9A8", rough=0.9)
        elif nm == "Jupiter":
            mat, alpha = ms.banded_mat("JupiterMat", ("#C9A27A", "#E8D3B0"), 4.5, r)
        else:
            mat, alpha, *_ = ms.lit_fade("SaturnMat", "#D8C08A", rough=0.9)
        o = ms.uv_ball(nm, r, mat, 32, 16, smooth_=True)
        o.parent = piv
        o.location = P - ms.SPACE_E
        alphas, dims = [alpha], [ms.dim_socket(mat)]
        if nm == "Saturn":
            rm, ra = ms.saturn_ring_mat("SaturnRingMat", 1.35 * r, 2.2 * r)
            ring = ms.ring_disc("SaturnRing", 1.35 * r, 2.2 * r, None, rm)
            ring.parent = o
            ring.rotation_euler = (math.radians(22), math.radians(-12), 0)     # open ellipse (normal tilted toward the camera)
            alphas.append(ra)
            dims.append(ms.dim_socket(rm))
        f_w = tm.f("09", 0)
        # fade (round 7, B-2): the color rises from black in 6 frames with the right shading; the alpha only in the 2 end frames
        for al in alphas:
            for fr, v in ((f_w, 0.0), (f_w + 2, 1.0), (end09 - 2, 1.0), (end09, 0.0)):
                kit.key(al, "default_value", v, fr)
        for dm in dims:
            for fr, v in ((f_w, 0.0), (f_w + 6, 1.0), (end09 - 6, 1.0), (end09 - 1, 0.0)):
                kit.key(dm, "default_value", v, fr)
        vis(tm, o, ("09",))
        planets.append((nm, px, py, rpx))
    for f in range(tm.f("09", 0), tm.last("09") + 1):
        piv.rotation_euler.z = -math.radians(orbit.phi(f))
        piv.keyframe_insert("rotation_euler", index=2, frame=f)

    # ---- instrument layer (camera child; 1 unit = 1 px) ----
    f07 = tm.f("07", 0)
    instr = ms.instr_pivot(cam, "Instr", ms.C_PX[0], ms.C_PX[1], ms.INSTR_D, ms.F_SP)
    s_sp, s_07 = ms.INSTR_D / ms.F_SP, ms.INSTR_D / F_PX
    for fr, s in ((f07, s_07), (tm.last("07"), s_07), (sp0, s_sp), (sp1, s_sp)):
        instr.location = ((ms.C_PX[0] - 540) * s, -(ms.C_PX[1] - 960) * s, -ms.INSTR_D)
        instr.scale = (s, s, s)
        instr.keyframe_insert("location", frame=fr)
        instr.keyframe_insert("scale", frame=fr)
    # amber axis 8 x 680 px
    ax_m, _, ax_fac = ms.overlay_mat("AxisBarMat", kit.LUZ, 1.0)
    v_, f_ = ms.rect_geo(-4, 4, -ms.AXIS_PX, ms.AXIS_PX, z=-6e5)
    axis = kit.mesh_object("AxisBar", v_, f_, [ax_m])
    axis.parent = instr
    axis.location = (0.0, 0.0, 6e5)          # origin well behind the camera (> 40 m): drawn ON TOP of the dark of the 07>08 cut
    axis.rotation_mode = "XYZ"
    axis.visible_shadow = False
    # dashed reference vertical (4 px, from the center up to y 250)
    parts, y = [], 0.0
    while y < ms.AXIS_PX - 1:
        parts.append(ms.rect_geo(-2, 2, y, min(y + 14, ms.AXIS_PX)))
        y += 24
    v_, f_, _ = kit.merge(*parts)
    vt_m, _, vt_fac = ms.overlay_mat("VertRefMat", "#8A94A6", 0.9)
    vert = kit.mesh_object("VertRef", v_, f_, [vt_m])
    vert.parent = instr
    vert.visible_shadow = False
    # amber arc (radius 300 px, 3 px) from the vertical to the axis
    arc, arc_theta, arc_fac = ms.masked_arc("TiltArc", 300.0, 3.0)
    arc.parent = instr
    # labels 23..62 degrees (one visible per frame) with soft shadow
    font = ms.label_font()
    lab_m, _, lab_fac = ms.overlay_mat("LabelMat", kit.LUZ, 1.0)
    sh_m, _, sh_fac = ms.overlay_mat("LabelShadowMat", "#0B0F17", 1.0)
    labels = {}
    for nval in range(23, 63):
        h = math.radians(nval / 2.0)
        x, y = 370 * math.sin(h), 370 * math.cos(h)
        t1 = ms.text_obj(f"Tilt{nval}", f"{nval}°", 64, lab_m, font)
        t1.parent = instr
        t1.location = (x, y, 0.0)
        t2 = ms.text_obj(f"TiltSh{nval}", f"{nval}°", 64, sh_m, font)
        t2.parent = instr
        t2.location = (x + 3, y - 4, -2.0)
        labels[nval] = (t1, t2)
    f_tilt07, f_e07 = tm.f("07", W("07", "tilt")), tm.f("07", W("07", "earth's"))
    f_tilt08 = tm.f("08", W("08", "tilt"))
    # fades: the line enters on "Earth's" (q1026) until "tilt" (q1041) in 07 and crosses the dark of the cut; vertical, arc and
    # label enter on "tilt" of 08 (0.3 s); everything leaves together with the dark of "Then" (1 - alpha of the black plane)
    out_k = [(fcut - 4, 1.0), (fcut - 3, 0.52), (fcut - 2, 0.21), (fcut - 1, 0.03)]
    for fr, v in [(1, 0.0), (f_e07, 0.0), (f_tilt07, 1.0)] + out_k:
        kit.key(ax_fac, "default_value", v, fr)
    for sock in (vt_fac, arc_fac, lab_fac):
        for fr, v in [(1, 0.0), (f_tilt08, 0.0), (f_tilt08 + 9, 1.0)] + out_k:
            kit.key(sock, "default_value", v, fr)
    for fr, v in [(1, 0.0), (f_tilt08, 0.0), (f_tilt08 + 9, 0.55)] + [(a_, b_ * 0.55) for a_, b_ in out_k]:
        kit.key(sh_fac, "default_value", v, fr)
    # on-screen angle: in 07 the axis of 08 (23 degrees); in space, the projection of the 3D axis (the ruler does not lie)
    for f in range(f07, sp1 + 1):
        if f < sp0:
            ang = 23.0
        else:
            ang = ms.screen_angle(tilt_deg(tm, f), orbit.pose(f))
        axis.rotation_euler.z = -math.radians(ang)
        axis.keyframe_insert("rotation_euler", index=2, frame=f)
        arc_theta.default_value = ang
        arc_theta.keyframe_insert("default_value", frame=f)
    for sid in SCENES:                       # only the axis (no recursion: the labels have their own keys)
        axis.hide_render = sid not in ("07", "08", "09", "10")
        axis.keyframe_insert("hide_render", frame=tm.tl.at(sid))
    axis.hide_render = True
    axis.keyframe_insert("hide_render", frame=fcut)
    for o in (vert, arc):
        vis_space(o)
    # label: the number is the REAL angle (integer); only one visible per frame
    shown = None
    for t1, t2 in labels.values():
        for o in (t1, t2):
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=1)
    peak = 23
    for f in range(f_tilt08, sp1 + 2):
        # MONOTONIC label (round 7, M-2): locks at the maximum already reached; the +-1 degree oscillation stays only on the axis and the arc
        peak = max(peak, int(round(tilt_deg(tm, f))))
        nval = None if f > sp1 else min(62, peak)
        if nval != shown:
            if shown is not None:
                for o in labels[shown]:
                    o.hide_render = True
                    o.keyframe_insert("hide_render", frame=f)
            if nval is not None:
                for o in labels[nval]:
                    o.hide_render = False
                    o.keyframe_insert("hide_render", frame=f)
            shown = nval

    # force lines of 09 (3 px, dashed, from the planet to the edge of the globe; dashes move toward the planet)
    f_tug = tm.f("09", W("09", "tugs"))
    r_mid = orbit.r_px(f_ref)
    for nm, px, py, rpx in planets:
        dx, dy = px - ms.C_PX[0], -(py - ms.C_PX[1])
        L0 = math.hypot(dx, dy)
        ux, uy = dx / L0, dy / L0
        start = (dx - ux * rpx * 1.25, dy - uy * rpx * 1.25)
        end = (ux * (r_mid + 6), uy * (r_mid + 6))
        L = math.hypot(end[0] - start[0], end[1] - start[1])
        o, rv, off, fac = ms.dashed_line_obj(f"Tug{nm}", L, 3.0, kit.LUZ)
        o.parent = instr
        o.location = (start[0], start[1], 0.0)
        o.rotation_euler = (0, 0, math.atan2(end[1] - start[1], end[0] - start[0]))
        for fr, v in ((1, 0.0), (f_tug, 0.0), (f_tug + 12, 1.0)):
            kit.key(rv, "default_value", v, fr)
        for fr, v in ((1, 0.0), (f_tug, 1.0), (tm.f("09", 0) + 158, 1.0), (end09 - 6, 0.0)):
            kit.key(fac, "default_value", v, fr)
        kit.key(off, "default_value", 0.0, f_tug)
        kit.key(off, "default_value", 20.0 * (end09 - f_tug) / tm.tl.fps, end09)
        vis(tm, o, ("09",))


SPACE_KEEP = set()


def obj_fcurve(o, path):
    ad = o.animation_data
    if not ad or not ad.action:
        return None
    for layer in ad.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    if fc.data_path == path:
                        return fc
    return None


def hide_pier_in_space(tm, cam):
    """Space stays at the origin (instrument layer precision): in frames q1076-1557 everything that is not space
    (pier, sea, sky, lamp and boat lights) is hidden; the camera, the fade plane and the Sun stay."""
    sp0, sp1 = space_range(tm)
    keep = set(SPACE_KEEP) | {cam.name, "CutFade", "Sun"}
    for o in bpy.data.objects:
        if o.name in keep or o.type in ("CAMERA",):
            continue
        fc = obj_fcurve(o, "hide_render")
        after = bool(fc.evaluate(sp1 + 1) > 0.5) if fc else o.hide_render
        prior = bool(fc.evaluate(sp0 - 1) > 0.5) if fc else o.hide_render
        o.hide_render = prior
        o.keyframe_insert("hide_render", frame=sp0 - 1)
        inside = [int(round(k.co.x)) for k in fc.keyframe_points if sp0 <= k.co.x <= sp1] if fc else []
        for fr in set(inside) | {sp0}:
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=fr)
        o.hide_render = after
        o.keyframe_insert("hide_render", frame=sp1 + 1)
        fc = obj_fcurve(o, "hide_render")
        if fc:
            for k in fc.keyframe_points:
                k.interpolation = "CONSTANT"


# ---------- build ----------

def sky_reflection(w):
    """Sky reflected in the water (art.md B1): the world shows the sky gradient also for reflection rays
    (Is Camera Ray MAX Is Glossy Ray on the world's Mix Shader factor). REQUIRED together: use_sun_shadow = False
    (otherwise Eevee extracts a "sun" from the sky, the shadow buffer overflows 4226/4096 and the frame goes from 0.6 to 4.2 s)."""
    nt = w.world.node_tree
    ms = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeMixShader")
    lp = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeLightPath")
    src = ms.inputs[0].links[0].from_socket
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(src, mx.inputs[0])
    nt.links.new(lp.outputs["Is Glossy Ray"], mx.inputs[1])
    nt.links.new(mx.outputs[0], ms.inputs[0])
    w.world.use_sun_shadow = False


def build(tl):
    tm = T(tl)
    sky.STATES  # noqa: B018
    w = sky.build_world()
    sky_reflection(w)
    add_dust_lane(w)
    stars = ms.pier_stars(sky.BAND_NORMAL)            # round stars in 3 sizes (art.md B6, item 6)
    near, far, wave, pad = build_sea()
    pier = build_pier()
    lamp, lamp_em, lamp_light = build_lamp()
    ruler, band, em_old, em_new, ring_new, snow_cap, trace_m, foam = build_ruler(CAM05)
    moon, moon_em, path, path_em, d_moon = build_moon_and_path(tm)
    bt, boat_glit_em, boat_glit, boat_wake = build_boat()
    boat, boat_em = bt.root, bt.em
    cape = build_cape()
    # lamp reflection column on the water (beyond the pier tip), origin AT THE OBSERVER, +y toward the lamp (like the boat's
    # boat): narrow strip (sigma 0.16 m + 0.4% of the distance), broken into wide horizontal stripes like the column, fades in
    # smoothly (no straight edge near), becomes continuous glow near the horizon (no sub-pixel dots) and fades far away.
    lgm, lamp_glit_em, lphase = mm.glitter_mat("LampGlitter", kit.LUZ, 0.15, 0.0035, 70.0, 260.0, seed=3.0,
                                               near_fade=(120.0, 650.0), density=0.45, lat_freq=0.9, rise=(9.0, 15.0), soft=0.26,
                                               ragged=0.35, true_sigma=True)
    GLITTER_PHASES.append(lphase)
    lamp_glit = mm.strip_mesh("LampGlitter", 8.0, 900.0, lambda y: 4.0 * (0.15 + 0.0035 * y) + 0.15, lgm, steps=24)
    # soft (additive) halo around the lantern
    halo, halo_k = mm.halo("LampHalo", kit.LUZ, 0.7, (-1.0, 5.9, DECK + 0.66), power=7.0)
    cam = build_camera(tm)
    build_cut_fade(tm, cam)

    # sea: tides and waves
    under = board_under(wave)
    key_tide(tm, [(near, 0.0, -0.09), (far, 0.0, -0.09), (pad, 0.09, 0.0), (path, 0.11, 0.11), (lamp_glit, 0.11, 0.11),
                  (REFL[0], 0.099, 0.009), (under, 0.105, 0.006)])
    vis(tm, under, ("05", "06"))
    vis(tm, pad, ("05", "06"))
    vis(tm, REFL[0], ("05", "06"))
    vis(tm, lamp_glit, ("01", "02", "03", "04", "07", "12"))
    place_lamp_column(tm, lamp_glit)
    HALO_SCENES = {"01": 1.0, "02": 1.0, "03": 1.0, "04": 1.0, "05": 0.0, "06": 0.0, "07": 0.35, "08": 0.0, "09": 0.0, "10": 0.0,
                   "11": 0.0, "12": 1.0}
    for sid in SCENES:
        track(tm, halo_k, "default_value", sid, [(0, HALO_K * HALO_SCENES[sid])])
    for ph in GLITTER_PHASES:                    # glints changing slowly (noise W, linear)
        kit.key(ph, "default_value", 0.0, 1)
        kit.key(ph, "default_value", 0.5 * tl.frames / tl.fps, tl.frames)
    for ph, w0 in PAD_PHASE:                      # 05/06 ripples moving slowly (noise W, linear)
        kit.key(ph, "default_value", w0, 1)
        kit.key(ph, "default_value", w0 + 0.2 * tl.frames / tl.fps, tl.frames)
    wave.location = (0, 0, 0)
    kit.key(wave, "location", (0, 0, 0), 1)
    kit.key(wave, "location", (0.6, -9.0, 0), tl.frames)

    lights(tm, w, d_moon)
    build_sky_detail(tm, w, stars)

    # moonlight: Moon, path and stripes vanish together in 0.3 s (01) and return in 1.2 s (12)
    hold(tm, moon_em, "default_value", {"01": 1.0, "12": 1.0})
    track(tm, moon_em, "default_value", "01", [(0, 1.0), (1.68, 1.0), (1.98, 0.0)])
    track(tm, moon_em, "default_value", "12", [(0, 0.0), (1.2, 1.0)])
    track(tm, path_em, "default_value", "01", [(0, 1.0), (1.68, 1.0), (1.98, 0.0)])
    track(tm, path_em, "default_value", "12", [(0, 0.0), (1.2, 1.0)])
    mh, mhk = MOON_HALO
    hold(tm, mhk, "default_value", {"01": MOON_HALO_K, "12": MOON_HALO_K})
    track(tm, mhk, "default_value", "01", [(0, MOON_HALO_K), (1.68, MOON_HALO_K), (1.98, 0.0)])
    track(tm, mhk, "default_value", "12", [(0, 0.0), (1.2, MOON_HALO_K)])
    vis(tm, mh, ("01", "12"))
    vis(tm, moon, ("01", "12"))
    vis(tm, path, ("01", "12"))
    # (the Moon and the path vanish by transparency/emission; no hiding in the middle of the scene)

    # lamp and boat: always lit; in 11 they light on "life"; in 12 the lamp goes out in the pause
    for sid in SCENES:
        v = 8.0
        track(tm, lamp_em, "default_value", sid, [(0, v)])
        track(tm, lamp_light, "energy", sid, [(0, 60.0)])
        track(tm, boat_em, "default_value", sid, [(0, 6.0)])
        track(tm, boat_glit_em, "default_value", sid, [(0, 0.9)])
        track(tm, lamp_glit_em, "default_value", sid, [(0, LAMP_GLIT)])
        track(tm, bt.light, "energy", sid, [(0, 1500.0)])
    t_on = W("11", "holds")     # lamp and boat off in 11 (winter, boat stuck in the ice); they light on "holds on"
    track(tm, lamp_em, "default_value", "11", [(0, 0.0), (t_on, 0.0), (t_on + 0.4, 8.0)])
    # on snow (albedo ~0.8, 5x the wood) 60 W blew the pool out to white: 24 W gives the center ~#F5D8A8 (art.md B5)
    track(tm, lamp_light, "energy", "11", [(0, 0.0), (t_on, 0.0), (t_on + 0.4, 24.0)])
    track(tm, boat_em, "default_value", "11", [(0, 0.0), (t_on, 0.0), (t_on + 0.4, 6.0)])
    track(tm, bt.light, "energy", "11", [(0, 0.0), (t_on, 0.0), (t_on + 0.4, 1500.0)])
    t_off = W("12", "comment")
    track(tm, lamp_em, "default_value", "12", [(0, 8.0), (t_off, 8.0), (t_off + 2.0, 0.0)])
    track(tm, lamp_light, "energy", "12", [(0, 60.0), (t_off, 60.0), (t_off + 2.0, 0.0)])
    track(tm, lamp_glit_em, "default_value", "12", [(0, LAMP_GLIT), (t_off, LAMP_GLIT), (t_off + 2.0, 0.0)])
    track(tm, halo_k, "default_value", "12", [(0, HALO_K), (t_off, HALO_K), (t_off + 2.0, 0.0)])
    track(tm, halo_k, "default_value", "11", [(0, 0.0), (t_on, 0.0), (t_on + 0.4, HALO_K)])

    # boat: position per scene (x in meters at 130 m), follows the tide; sways slowly (less in 11, stuck in the ice);
    # radar always spins; the amber column on the water points at the camera; wake only in 07
    bx = {"01": 6.6, "02": 6.6, "03": 6.6, "04": 6.6, "05": 6.6, "06": 6.6, "08": 40.0, "09": 40.0, "10": 40.0,
          "11": 40.0, "12": 6.6}
    poses = camera_poses(tm)
    for sid in SCENES:
        a_, b_ = tm.f(sid, 0), tm.last(sid)
        cy = poses[sid][0][1].y
        for f in range(a_, b_ + 1):
            t = (f - a_) / tl.fps
            x = lerp(22.7, 50.0, t / tm.dur(sid)) if sid == "07" else bx[sid]
            z = tide(sid, t) + (-0.09 if sid in ("05", "06") else 0.0)
            boat.location = (x, 130.0, z)
            boat.keyframe_insert("location", frame=f)
            k = 0.15 if sid == "11" else 1.0
            T_ = f / tl.fps
            bt.sway.rotation_euler = (k * 0.035 * math.sin(2 * math.pi * T_ / 4.1), k * 0.02 * math.sin(2 * math.pi * T_ / 3.3 + 1), 0)
            bt.sway.keyframe_insert("rotation_euler", frame=f)
            bt.radar.rotation_euler.z = 2.4 * T_
            bt.radar.keyframe_insert("rotation_euler", index=2, frame=f)
            boat_glit.rotation_euler.z = math.atan2(x, cy - 130.0)
            boat_glit.keyframe_insert("rotation_euler", index=2, frame=f)
    vis(tm, boat_glit, tuple(sid for sid in SCENES if sid != "11"))
    vis(tm, boat_wake, ("07",))
    sea_ice(tm, near, far)
    # 11 (round 7, M-3): ice gaps at ~#0E1830 (the reflected winter sky left the water wine-colored): dark base and
    # low specular only in 11; faint pinkish outline coming from the horizon (low sun light, no shadow, only in 11)
    sea_p = kit.principled(near.active_material)
    for sid in SCENES:
        track(tm, sea_p.inputs["Specular IOR Level"], "default_value", sid, [(0, 0.02 if sid == "11" else 0.5)])
        track(tm, sea_p.inputs["IOR"], "default_value", sid, [(0, 1.02 if sid == "11" else 1.5)])    # no grazing Fresnel
        track(tm, sea_p.inputs["Emission Strength"], "default_value", sid, [(0, 1.0 if sid == "11" else 0.0)])
    sea_p.inputs["Emission Color"].default_value = lin("#0E1830")     # ice gap ~#0E1830 without depending on the light
    rim = bpy.data.lights.new("RimSun", "SUN")
    rim.color, rim.energy, rim.angle = (0.92, 0.6, 0.64), 0.0, math.radians(3)
    rim.use_shadow = False
    rim.specular_factor = 0.0          # no shine on the water/ice: the Sun is below the horizon (only the diffuse outline)
    rim_o = bpy.data.objects.new("RimSun", rim)
    bpy.context.collection.objects.link(rim_o)
    rim_o.rotation_euler = sun_dir_quat((0.0, 1.0, 0.12))
    for sid in SCENES:
        track(tm, rim, "energy", sid, [(0, 0.6 if sid == "11" else 0.0)])
    snow_layers(tm)
    # snowy cable in 11 (lighter silhouette, blue-gray under the winter light)
    ccol = kit.principled(cape.active_material).inputs["Base Color"]
    for sid in SCENES:
        track(tm, ccol, "default_value", sid, [(0, lin("#7D8898") if sid == "11" else lin("#0A0E16"))])

    # snow (wood factor): ramp in 10 ("colder"), full in 11
    hold(tm, SNOW[0], "default_value", {"11": 1.0})
    for sock in SNOW:
        hold(tm, sock, "default_value", {"11": 1.0})
        c = W("10", "colder")
        track(tm, sock, "default_value", "10", [(0, 0.0), (c + 0.1, 0.0), (min(c + 0.76, tm.dur("10")), 1.0)])
    # post: wet band, rings
    bcol = band.node_tree.nodes["Principled BSDF"].inputs["Base Color"] if hasattr(band, "node_tree") else None
    dark, pale = lin("#1E1A1A"), lin("#9A8468")
    lcol = kit.principled(RULER_MATS["low"]).inputs["Base Color"]
    blue = lin("#4F3C4E")                     # bottom third: "water-colored" (dawn pink, V2-C4)
    for sid in SCENES:
        pl = sid in ("06", "07", "08", "09", "10", "11")
        track(tm, bcol, "default_value", sid, [(0, pale if pl else dark)])
        track(tm, lcol, "default_value", sid, [(0, pale if pl else blue)])
    t0, t1 = W("05", "line", 0), (572 - tm.f("05", 0)) / tl.fps      # the band lightens from "line." (q545) to q572, BEFORE the ghost wave (q574)
    track(tm, bcol, "default_value", "05", [(0, dark), (t0, dark), (t1, pale)])
    track(tm, lcol, "default_value", "05", [(0, blue), (t0, blue), (t1, pale)])
    # ruler ticks: light on the dark band, dark after the band lightens
    tcol = kit.principled(trace_m).inputs["Base Color"]
    t_lt, t_dk = lin("#F2F4F6"), lin("#15151C")
    for sid in SCENES:
        track(tm, tcol, "default_value", sid, [(0, t_dk if sid in ("06", "07", "08", "09", "10", "11") else t_lt)])
    track(tm, tcol, "default_value", "05", [(0, t_lt), (t0, t_lt), (t1, t_dk)])
    tem = kit.principled(trace_m).inputs["Emission Strength"]       # glow only while the band is dark
    for sid in SCENES:
        track(tm, tem, "default_value", sid, [(0, 0.0 if sid in ("06", "07", "08", "09", "10", "11") else 1.0)])
    track(tm, tem, "default_value", "05", [(0, 1.0), (t0, 1.0), (t1, 0.0)])
    # foam on the board's waterline (05 and 06): follows the tide; outside them it stays hidden
    for sid in ("05", "06"):
        a_, b_ = tm.f(sid, 0), tm.last(sid)
        for f in range(a_, b_ + 1):
            foam.location.z = tide(sid, (f - a_) / tl.fps) + 0.012
            foam.keyframe_insert("location", index=2, frame=f)
    vis(tm, foam, ("05", "06"))
    build_ghost(tm)
    # sea: dawn-pink color in scenes 05 and 06 (07 picks up the pink of the reflected sky; 05/06 do not show the sky)
    scol = kit.principled(near.active_material).inputs["Base Color"]
    for sid in SCENES:
        track(tm, scol, "default_value", sid, [(0, lin(SEA_DAWN) if sid in ("05", "06") else lin("#0E1830") if sid == "11" else lin("#10223A"))])
    for sid in SCENES:
        track(tm, em_old, "default_value", sid, [(0, 1.5 if sid in ("01", "02", "03", "04", "05", "12") else 0.0)])
        track(tm, em_new, "default_value", sid, [(0, 1.5)])
    tb = W("06", "big")
    track(tm, em_old, "default_value", "06", [(0, 0.0), (tb, 0.0), (tb + 0.2, 3.5), (tb + 0.8, 3.5), (tb + 1.0, 0.0)])
    ts_, tm_ = W("05", "sun"), W("05", "moon")            # 05: while the ghost wave holds at +1.2, the old ring pulses
    track(tm, em_old, "default_value", "05", [(0, 1.5), (ts_, 1.5), ((ts_ + tm_) / 2, 3.0), (tm_, 1.5)])
    vis(tm, ring_new, ("06", "07", "08", "09", "10", "11"))

    # stars
    vis(tm, stars[0], ("01", "02", "03", "04", "11", "12"))      # 08-10: space has its own stars
    vis(tm, cape, tuple(SCENES))

    # 02 (V2-A, A2): no yellow line; the camera lowers its gaze from the empty Moon point to the boards (see camera_poses)

    # 04: owl still on the post and mouse
    owl_ = build_owl(OWL_POST)
    animate_owl(tm, owl_)
    m1 = mm.mouse("Mouse", MOUSE_S)
    walk(tm, m1, MOUSE1, W("04", "without"), min(W("04", "without") + 2.0, tm.dur("04")), h0=0.0)   # standing still with its back turned until "Without"
    m2 = mm.mouse("Mouse2", MOUSE_S * 1.35)          # farther away (~3.3 m): slightly larger to read (~100 px)
    walk(tm, m2, MOUSE2, W("04", "mice", 1) - 14 / 30, min(W("04", "mice", 1) + 1.6, tm.dur("04")), h0=math.radians(165))  # "mice come out more"
    crate = build_crate()
    vis(tm, crate, ("04",))
    vis(tm, owl_.root, ("04",))
    vis(tm, m1.root, ("04",))
    vis(tm, m2.root, ("04",))

    # 07 (amber line attached to the camera), 08, 09 and 10 up to "Then": space (V2-B)
    before = set(bpy.data.objects)
    build_space(tm, cam)
    SPACE_KEEP.update(o.name for o in set(bpy.data.objects) - before)

    # 10 (after the cut): Sun arc seen from the side as a curve, with a ghost trace of the previous height (the ruler).
    # Diagram on a plane perpendicular to the camera, at 400 m: 16.7 px per degree of elevation from the horizon (y 1500).
    D10, PXDEG = 400.0, 16.7
    cam10 = Vector((0, 0.55, EYE))
    fwd10, right10, up10 = basis(0, PITCH10)
    dc = px_dir(540, 1500, 0, PITCH10)
    pc = cam10 + dc * (D10 / dc.dot(fwd10))
    qrot = Matrix((right10, fwd10, up10)).transposed().to_quaternion()
    EMAX = 75.0

    ghost_fac = {}

    # round 7 (M-5): each arc is the path of one day, from horizon to horizon INSIDE the frame (rises and sets on the line
    # y 1500), wider the higher it is (summer: rises more to the side). The arcs are nested (they do not cross: no "M" and
    # V above the horizon). At most 2 on screen: the current arc and the ghost of the previous height (the ruler).
    def hw(e):
        return 400.0 + 100.0 * e / EMAX

    def arc_pts(e, half_px):
        """Ribbon of half-thickness half_px (on screen, perpendicular to the curve) for elevation e: (top, base) in meters."""
        top, bot = [], []
        h, w_ = PXDEG * e, hw(e)
        for i in range(65):
            sp = -1.0 + 2.0 * i / 64
            xpx, ypx = sp * w_, h * (1 - sp * sp)
            tx, ty = w_, -2.0 * h * sp                         # tangent (d/ds)
            ln = math.hypot(tx, ty)
            nx_, ny_ = -ty / ln, tx / ln
            k = D10 / F_PX
            top.append((k * (xpx + nx_ * half_px), 0.0, k * (ypx + ny_ * half_px)))
            bot.append((k * (xpx - nx_ * half_px), 0.0, k * (ypx - ny_ * half_px)))
        return top, bot

    def arc_curve(name, color, strength, half_px, e):
        mat, _, fac = mm.fade_emitter(name + "Mat", color, strength)      # vanishes by transparency (no pop)
        ghost_fac[name] = fac
        t_, b_ = arc_pts(e, half_px)
        o = kit.mesh_object(name, t_ + b_, [(i, i + 1, 65 + i + 1, 65 + i) for i in range(64)], [mat], tuple(pc))
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = qrot
        o.visible_shadow = False
        return o

    # main arc: 9 px RIBBON with elevation shape key (base = 0 degrees on the horizon line, "Elev" = EMAX degrees)
    t0_, b0_ = arc_pts(0.0, 4.5)
    t1_, b1_ = arc_pts(EMAX, 4.5)
    rv = t0_ + b0_
    rf = [(i, i + 1, 65 + i + 1, 65 + i) for i in range(64)]
    arc10 = kit.mesh_object("SunArc", rv, rf, [emitter("SunArcMat", kit.LUZ, 2.2)[0]], tuple(pc))
    arc10.rotation_mode = "QUATERNION"
    arc10.rotation_quaternion = qrot
    arc10.visible_shadow = False
    arc10.shape_key_add(name="Basis")
    kb = arc10.shape_key_add(name="Elev")
    for i, co in enumerate(t1_ + b1_):
        kb.data[i].co = co
    kb.slider_max = 1.0
    ghost60 = arc_curve("Ghost60", "#FFE0A0", 1.0, 2.0, 60.0)
    ghost75 = arc_curve("Ghost75", "#FFE0A0", 1.0, 2.0, 75.0)
    disc, _halo = mm.sun_disc("SunDisc", D10 * 34.0 / F_PX, D10 * 66.0 / F_PX)   # 34 px disc + soft halo up to 66 px
    disc.rotation_mode = "QUATERNION"
    disc.rotation_quaternion = qrot
    h10, c10 = W("10", "hotter"), W("10", "colder")

    def elev10(t):
        if t < h10:
            return 60.0
        if t < h10 + 0.8:
            return lerp(60.0, 75.0, smooth((t - h10) / 0.8))
        if t < c10:
            return 75.0
        return lerp(75.0, 20.0, smooth((t - c10) / 0.9))

    a10, b10 = tm.f("10", 0), tm.last("10")
    f_cut = tm.f("10", CUT10)
    for f in range(a10, b10 + 1):
        t = (f - a10) / tl.fps
        on = f >= f_cut
        e_ = elev10(t)
        arc10.scale = (1, 1, 1) if on else (0.001,) * 3
        arc10.keyframe_insert("scale", frame=f)
        kb.value = e_ / EMAX
        kb.keyframe_insert("value", frame=f)
        disc.location = pc + up10 * (D10 * PXDEG * e_ / F_PX)
        disc.scale = (1, 1, 1) if on else (0.001,) * 3
        disc.keyframe_insert("location", frame=f)
        disc.keyframe_insert("scale", frame=f)
        g75 = min(1.0, max(0.0, (t - c10) * tl.fps / 6.0))           # the summer becomes a ghost when the Sun goes down
        for nm, v in (("Ghost60", (1.0 - g75) if f >= f_cut else 0.0), ("Ghost75", g75)):
            fac = ghost_fac[nm]
            fac.default_value = 0.75 * v
            fac.keyframe_insert("default_value", frame=f)
    for o in (arc10, ghost60, ghost75, disc):
        vis(tm, o, ("10",))

    # snow on the post: white cap that grows on "colder" (10) and stays in 11
    for sid in SCENES:
        track(tm, snow_cap, "scale", sid, [(0, (1, 1, 1) if sid == "11" else (1, 1, 0.001))])
    track(tm, snow_cap, "scale", "10", [(0, (1, 1, 0.001)), (c10, (1, 1, 0.001)), (min(c10 + 1.0, tm.dur("10")), (1, 1, 1))])
    # 11: Sun glow just below the horizon (art.md B5, item 6): 3-degree gradient strip (#E08A4A at 40% on the line ->
    # #7A3A4A at 20% -> nothing) with an amber core of 3-4 px and soft edge, in place of the 1 px amber thread (read as interface)
    band11, b11_alpha = horizon_glow("HorizonGlow")
    ts = W("11", "sunrise")
    track(tm, b11_alpha, "default_value", "11", [(0, 0.0), (ts, 0.0), (ts + 0.8, 1.0)])
    vis(tm, band11, ("11",))

    # 12: short amber arc and the shrinking Moon. Round 7 (M-4): the arc was a 1.5 px thread; now a ~6.5 px ribbon with an
    # arrowhead (the Moon MOVES AWAY), and the "4 centimeters" tick crosses the arc near the tip (~7 x 20 px)
    mat12, _ = emitter("DriftMat", kit.LUZ, 1.1)          # <= ~1: amber of the mark, no yellowish bloom
    mp = moon.location
    arc_pts = [(0.55 * 66 * 4 * u, 0.0, 0.35 * 66 * 4 * u * u) for u in [i / 16 for i in range(17)]]
    v, f = kit.tube_geo(arc_pts, [2.5] * len(arc_pts), n=6)
    arc12 = kit.mesh_object("DriftArc", v, f, [mat12], tuple(mp))
    arc12.visible_shadow = False
    td, te = W("12", "drifting"), W("12", "drifting") + 2.3
    track(tm, arc12, "scale", "12", [(0, (0.001,) * 3), (td, (0.001,) * 3), (te, (1, 1, 1))])
    vis(tm, arc12, ("12",))
    end = Vector(arc_pts[-1])
    tan = (Vector(arc_pts[-1]) - Vector(arc_pts[-2])).normalized()
    nrm = Vector((-tan.z, 0.0, tan.x))
    L_, Wd = 15.0, 6.0                                         # 20 x 16 px tip (at 900 m, 1 px ~ 0.77 m)
    head = [tuple(-nrm * Wd - Vector((0, 0.5, 0))), tuple(tan * L_ - Vector((0, 0.5, 0))), tuple(nrm * Wd - Vector((0, 0.5, 0))),
            tuple(-nrm * Wd + Vector((0, 0.5, 0))), tuple(tan * L_ + Vector((0, 0.5, 0))), tuple(nrm * Wd + Vector((0, 0.5, 0)))]
    arrow = kit.mesh_object("DriftArrow", head, [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], [mat12],
                            tuple(Vector(mp) + end - tan * 1.5))
    arrow.visible_shadow = False
    track(tm, arrow, "scale", "12", [(0, (0.001,) * 3), (te - 0.25, (0.001,) * 3), (te, (1, 1, 1))])
    vis(tm, arrow, ("12",))
    um = Vector(arc_pts[13])
    tick = kit.mesh_object("DriftTick", *kit._box_geo(2.6, 2.6, 16.0, -1.3, -1.3, -8.0), [mat12], tuple(Vector(mp) + um))
    tick.rotation_euler = (0.0, math.atan2(nrm.x, nrm.z), 0.0)
    tick.visible_shadow = False
    tt = W("12", "centimeters")
    track(tm, tick, "scale", "12", [(0, (0.001,) * 3), (tt, (0.001,) * 3), (tt + 0.15, (1, 1, 1))])
    vis(tm, tick, ("12",))
    # moonlight path in 12 (bible 1.7, M-4): core <= #E8EEFF (the final call sits over it): less Moon specular
    # on the facets and slightly smaller glitter brightness only in 12
    track(tm, w.sun, "specular_factor", "12", [(0, PATH12_SPEC)])
    track(tm, path_em, "default_value", "12", [(0, 0.0), (1.2, PATH12_EM)])
    track(tm, moon, "scale", "12", [(0, (1, 1, 1)), (td, (1, 1, 1)), (te, (0.94,) * 3)])

    # all linear (dense keys); visibility in steps
    for act in bpy.data.actions:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for kp in fc.keyframe_points:
                            kp.interpolation = "CONSTANT" if fc.data_path == "hide_render" else "LINEAR"

    # objects without per-scene visibility are always visible
    link_lamp_light()
    hide_pier_in_space(tm, cam)
    return None


kit.run(build)
