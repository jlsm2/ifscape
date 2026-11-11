"""Walk with the foot planted over the asset's own cycle (IK on the legs, target held still in the world during stance).

Why: in Quaternius's Apatosaurus_Walk the hind legs sweep 7.9 units per step and the front ones only 3.6
(docs/blender/modeling.md); with the body walking, some pair always slides. Here the body walks at the
speed of the front foot (the one with less reach) and each foot goes to an empty in the world:
- in stance, the empty stays STILL (key on every frame), centered where the foot of the original cycle rested;
- in swing, it goes from the point where it left to the next stance, with the foot height taken from the original cycle;
- the foot bone copies the empty's position, and the leg (thigh + shin) reaches it by IK (2-bone chain).
Manual rule: target as an empty in the world, key on every frame, leg with enough reach (checked in the stride).
"""

import math

import bpy
from mathutils import Vector

import rigs


def _stance(pts):
    """Stance mask (foot at the lowest point of the cycle) and the mean foot y in stance."""
    zs = [p.z for p in pts]
    lo, hi = min(zs), max(zs)
    mask = [z < lo + 0.04 * (hi - lo) for z in zs]
    ys = [p.y for p, m in zip(pts, mask) if m]
    return mask, sum(ys) / len(ys), lo


def _sample(pts, u):
    i = int(math.floor(u))
    i = min(max(i, 0), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], u - i)


def walk(rig, feet, f0, f1, start_xy, heading, ground_z, rate=1.0, phase=0.0, speed_from=None, sink=0.0,
         anchor=None):
    """Walks in a straight line from start_xy in direction heading (radians, 0 = +x) from f0 to f1.
    feet: [(foot bone, shin bone)]; speed_from: feet that set the speed (default: all, the smallest).
    anchor: frame at which the body passes through start_xy (default: f0).
    sink: lowers the body (armature units) so the legs reach the stance without stretching the mesh.
    Returns the speed in m/s."""
    t = rig.t
    names = [b for b, _ in feet]
    table = rigs.foot_table(t, "Walk", names)
    st = rigs.loop(rig, "Walk", f0 - 200, f1 + 200, rate=rate, phase=phase)
    a0 = st.action_frame_start
    S = rig.scale                                         # armature -> world
    rig.arm.location.z -= sink * S
    info = {b: _stance(table[b]) for b in names}
    speeds = {}
    for b in names:
        mask, _, _ = info[b]
        pts = table[b]
        moves = [abs(pts[i + 1].y - pts[i].y) for i in range(len(pts) - 1) if mask[i] and mask[i + 1]]
        speeds[b] = sum(moves) / max(len(moves), 1)       # armature units per action frame
    v_loc = min(speeds[b] for b in (speed_from or names))
    v = v_loc * S / st.scale                              # meters per scene frame
    d = Vector((math.cos(heading), math.sin(heading), 0.0))
    p0 = Vector((*start_xy, 0.0)) - d * v * ((anchor or f0) - f0)

    def root_at(f):
        p = p0 + d * v * (f - f0)
        return Vector((p.x, p.y, ground_z(p.x, p.y)))

    rot = root_rotation(heading)

    def to_world(f, local):
        return root_at(f) + rot @ (Vector((local.x, local.y, local.z - t.box.lo.z)) * S)

    frames = list(range(f0 - 2, f1 + 3))
    rigs.key_root(rig, frames, [root_at(f) for f in frames], [heading] * len(frames))
    pad = int(2 * (st.action_frame_end - a0) * st.scale)
    for foot, shin in feet:
        mask, cy, zlo = info[foot]
        pts = table[foot]
        ext = range(f0 - pad, f1 + pad + 1)
        flags = [mask[int(round(rigs.action_frame(st, f) - a0)) % (len(pts) - 1)] for f in ext]
        runs, cur = [], None
        for f, on in zip(ext, flags):
            if on and cur is None:
                cur = [f, f]
            elif on:
                cur[1] = f
            elif cur is not None:
                runs.append(cur)
                cur = None
        if cur is not None:
            runs.append(cur)
        plants = []
        for a, b in runs:
            mid = (a + b) / 2
            lx = _sample(pts, rigs.action_frame(st, mid) - a0).x
            w = to_world(mid, Vector((lx, cy, zlo)))
            w.z = ground_z(w.x, w.y) + (zlo - t.box.lo.z) * S
            plants.append((a, b, w))
        target = bpy.data.objects.new(f"{rig.name}{foot}Target", None)
        target.empty_display_size = 0.4
        bpy.context.collection.objects.link(target)
        for f in frames:
            target.location = _foot_pos(f, plants, pts, st, a0, zlo, S, ground_z)
            target.keyframe_insert("location", frame=f)
        for fc in rigs._fcurves(target.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        pb = rig.arm.pose.bones[foot]
        c = pb.constraints.new("COPY_LOCATION")
        c.target = target
        ik = rig.arm.pose.bones[shin].constraints.new("IK")
        ik.target, ik.subtarget = rig.arm, foot
        ik.chain_count = 2
        ik.use_stretch = False
    return v * rigs.SCENE_FPS


def root_rotation(heading):
    """Rotation of the character root (the asset faces -y): heading + 90° around z."""
    from mathutils import Matrix
    return Matrix.Rotation(heading + math.pi / 2, 3, "Z")


def _foot_pos(f, plants, pts, st, a0, zlo, S, ground_z):
    for a, b, w in plants:
        if a <= f <= b:
            return tuple(w)
    prev = max((p for p in plants if p[1] < f), key=lambda p: p[1], default=None)
    nxt = min((p for p in plants if p[0] > f), key=lambda p: p[0], default=None)
    if prev is None or nxt is None:
        return tuple((prev or nxt)[2])
    s = (f - prev[1]) / (nxt[0] - prev[1])
    s = s * s * (3 - 2 * s)
    p = prev[2].lerp(nxt[2], s)
    lift = (_sample(pts, rigs.action_frame(st, f) - a0).z - zlo) * S
    return (p.x, p.y, p.z + lift)
