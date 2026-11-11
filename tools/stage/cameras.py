"""Ready-made stage cameras: eye-level POV, dolly, truck, orbit, crane and static.

Each scene gives {"preset", "at": [x, y], "look": prop-name | [x, y, z], ...}. The camera always looks at the target
(which may walk). Keys every 3 frames, LINEAR; the last frame of the scene is CONSTANT, so the cut between scenes is
hard. Light hand sway in the POV. Impact shake comes from the cues ('shake').
"""

import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
from lib import anim_curves as ac  # noqa: E402

EYE = 1.65
STEP = 3
PRESETS = ("pov", "static", "dolly_in", "dolly_out", "truck", "orbit", "crane", "path", "macro")
DEFAULTS = {"pov": dict(sway=0.5, dist=0.0), "static": dict(sway=0.0, dist=0.0),
            "dolly_in": dict(sway=0.25, dist=8.0), "dolly_out": dict(sway=0.25, dist=8.0),
            "truck": dict(sway=0.15, dist=10.0), "orbit": dict(sway=0.0, dist=60.0),
            "crane": dict(sway=0.0, dist=6.0), "path": dict(sway=0.0, dist=0.0),
            "macro": dict(sway=0.06, dist=0.0)}
MACRO_Z, MACRO_LENS = 0.15, 45      # macro: camera still close to the ground (1 cm ants), hand sway in mm
LAST: dict = {}        # final camera state of the previous scene (pos, target, lens): 'prev' on a pass-through point


import validate  # noqa: E402

assert PRESETS == validate.CAMERAS, "validate.py e cameras.py divergem"


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def target_point(look, frame, props):
    """Point (Vector) the camera looks at in the frame: the prop's position (at 55% of the height) or a coordinate."""
    if isinstance(look, str):
        name, _, dz = look.partition("^")       # "witness^0.5": 0.5 m above the piece's foot (the piece falls in the bottom third)
        pos_fn, height = props[name]
        p = pos_fn(frame)
        return Vector((p.x, p.y, p.z + (float(dz) if dz else height * 0.55)))
    return Vector(look)


def _catmull(p0, p1, p2, p3, u):
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def _waypoints(spec, start, end, fps):
    """Pass-through points [(frame, pos, look, lens)] already resolved; 'prev' inherits the end of the previous scene."""
    pts = []
    for n, w in enumerate(spec["path"]):
        f = start + int(float(w["t"]) * fps) if "t" in w else start + int(float(w.get("frac", n / max(len(spec["path"]) - 1, 1))) * (end - start))
        f = max(start, min(end, f))
        if w.get("prev"):
            if not LAST:
                raise ValueError("camera.path: 'prev' in the first scene (there is no previous camera)")
            pts.append((f, LAST["pos"].copy(), list(LAST["tgt"]), LAST["lens"]))
        else:
            at = w["at"]
            pts.append((f, Vector((at[0], at[1], float(w.get("z", EYE)))), w["look"], float(w.get("lens", spec.get("lens", 24)))))
    if pts[0][0] > start:       # holds the first point from the start of the scene
        pts.insert(0, (start, *pts[0][1:]))
    if pts[-1][0] < end:        # and the last one until the end
        pts.append((end, *pts[-1][1:]))
    return pts


def plan_path(spec, start, end, props, shakes, fps):
    pts = _waypoints(spec, start, end, fps)
    rng = random.Random(start)
    frames = list(range(start, end + 1, STEP))
    if frames[-1] != end:
        frames.append(end)
    out, prev_q, seg = [], None, 0
    for f in frames:
        while seg < len(pts) - 2 and f > pts[seg + 1][0]:
            seg += 1
        a, b = pts[seg], pts[min(seg + 1, len(pts) - 1)]
        u = _ease((f - a[0]) / max(b[0] - a[0], 1)) if b[0] > a[0] else 1.0
        lin = (f - a[0]) / max(b[0] - a[0], 1) if b[0] > a[0] else 1.0
        p0, p3 = pts[max(seg - 1, 0)][1], pts[min(seg + 2, len(pts) - 1)][1]
        if (b[1] - a[1]).length < 1e-4:       # still stretch (two equal points): holds (the curve overshot the point)
            pos = a[1].copy()
        else:
            pos = Vector([_catmull(p0[i], a[1][i], b[1][i], p3[i], max(0.0, min(1.0, lin))) for i in range(3)])
        ta, tb = target_point(a[2], f, props), target_point(b[2], f, props)
        tgt = ta.lerp(tb, u)
        lens = a[3] + (b[3] - a[3]) * u
        for fs, amp in shakes:
            if fs <= f <= fs + int(0.7 * fps):
                k = amp * (1 - (f - fs) / (0.7 * fps))
                pos += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * k
        q = (tgt - pos).to_track_quat("-Z", "Y")
        if prev_q is not None and q.dot(prev_q) < 0:
            q.negate()
        prev_q = q
        out.append((f, pos, q, lens))
        LAST.update(pos=pos.copy(), tgt=tuple(tgt), lens=lens)
    return out


def sink_offset(f, sinks, z0, fps):
    """Camera cue 'sink' (gravity-doubled): the eye drops from z0 to 'z' in 'dur' (ease-out with
    a slight overshoot of the target and a small bounce that fades in 0.6 s) and stays there until the end of the scene."""
    off = 0.0
    for fs, dur, zto in sinks:
        if f < fs:
            continue
        u = min(1.0, (f - fs) / max(dur, 1)) - 1.0
        e = 1 + 2.3 * u ** 3 + 1.3 * u ** 2
        te = (f - fs) / fps
        bounce = 0.012 * math.sin(math.tau * 5.5 * te) * max(0.0, 1 - te / 0.6)
        off = (zto - z0) * e - bounce
    return off


def plan(spec: dict, start: int, end: int, props: dict, shakes: list[tuple[int, float]], fps: int, sinks=()):
    """Samples (frame, position, quaternion, lens) of the scene's camera. 'sinks': [(frame, frames, z)] of the 'sink'."""
    kind = spec.get("preset", "pov")
    if kind not in PRESETS:
        raise ValueError(f"camera.preset '{kind}' unknown. Options: {list(PRESETS)}")
    if kind == "path":
        return plan_path(spec, start, end, props, shakes, fps)
    d = {**DEFAULTS[kind], **{k: v for k, v in spec.items() if k in ("sway", "dist")}}
    arc = float(spec.get("arc", d["dist"] if kind == "orbit" else 60))
    z0 = float(spec.get("z", MACRO_Z if kind == "macro" else EYE))
    at = Vector((spec["at"][0], spec["at"][1], z0))
    lens = float(spec.get("lens", MACRO_LENS if kind == "macro" else 24))
    rng = random.Random(start)
    frames = list(range(start, end + 1, STEP))
    if frames[-1] != end:
        frames.append(end)
    out, prev_q = [], None
    for f in frames:
        u = _ease((f - start) / max(end - start, 1))
        tgt = target_point(spec["look"], f, props)
        flat = Vector((tgt.x - at.x, tgt.y - at.y, 0.0))
        fwd = flat.normalized() if flat.length > 1e-6 else Vector((1, 0, 0))
        side = Vector((-fwd.y, fwd.x, 0.0))
        pos = at.copy()
        if kind == "dolly_in":
            pos = at + fwd * (d["dist"] * u)
        elif kind == "dolly_out":
            pos = at - fwd * (d["dist"] * u)
        elif kind == "truck":
            pos = at + side * (d["dist"] * (u - 0.5))
        elif kind == "crane":
            pos = Vector((at.x, at.y, z0 + d["dist"] * u))
        elif kind == "orbit":
            r = flat.length
            a0 = math.atan2(at.y - tgt.y, at.x - tgt.x)
            a = a0 + math.radians(arc) * u
            pos = Vector((tgt.x + r * math.cos(a), tgt.y + r * math.sin(a), z0))
        if sinks:
            pos.z += sink_offset(f, sinks, z0, fps)
        if d["sway"]:
            t = (f - start) / fps
            pos += Vector((math.sin(t * 1.9) * 0.025, math.sin(t * 1.3 + 1) * 0.03, math.sin(t * 2.7) * 0.018)) * d["sway"] * 2
        for fs, amp in shakes:
            if fs <= f <= fs + int(0.7 * fps):
                k = amp * (1 - (f - fs) / (0.7 * fps))
                pos += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * k
        q = (tgt - pos).to_track_quat("-Z", "Y")
        if prev_q is not None and q.dot(prev_q) < 0:
            q.negate()
        prev_q = q
        out.append((f, pos, q, lens))
        LAST.update(pos=pos.copy(), tgt=tuple(tgt), lens=lens)
    return out


def key_camera(cam, samples: list[tuple[int, Vector, Quaternion, float]], scene_ends: set[int]):
    """Writes all the keys (of all scenes) at once. The last frame of each scene stays CONSTANT."""
    frames = [s[0] for s in samples]
    cam.rotation_mode = "QUATERNION"
    for i, axis in enumerate("xyz"):
        ac.write(cam, "location", i, frames, [s[1][i] for s in samples])
    for i in range(4):
        ac.write(cam, "rotation_quaternion", i, frames, [s[2][i] for s in samples])
    ac.write(cam.data, "lens", 0, frames, [s[3] for s in samples])
    for owner in (cam, cam.data):
        for fc in ac.bag(owner).fcurves:
            for kp in fc.keyframe_points:
                if int(kp.co[0]) in scene_ends:
                    kp.interpolation = "CONSTANT"
            fc.update()
