"""People of the waterfront and wildebeest of the savanna of viruses-disappeared.

People: Quaternius Man and Woman Casual (CC0, rigs.py), palette clothes (art.md section 2: blue, terracotta, off-white,
navy; no green or amber). The sneeze (direction.md section 3, scene 01): torso and head bent (added layer), left
hand on the face by IK (target attached to the head bone) with a white handkerchief, and a cone of 40 emissive droplets
(#E8F0F4, emission 1.5, >= 5 px) coming out of the nose.

Wildebeest: lib/wildebeest.py (edited Quaternius cow). Near ones have a rig (grazing / head raised); the big herd of
12 is made of "photos" of the Walk cycle (8 phases, instanced still meshes) and, beyond ~400 m, of legless silhouettes
(art.md R8: a 1 px leg flickers).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
import rigs
import viruses_savanna as sv
import wildebeest as wb

CLOTHES = [
    {"Shirt": "#3E6A8C", "Pants": "#3A3E48", "Skin": "#C8916A", "Hair": "#2A1E16"},
    {"Shirt": "#B8653E", "Pants": "#2E3A55", "Skin": "#E0B090", "Hair": "#6A4A30"},
    {"Shirt": "#D8D2C4", "Pants": "#4A5A78", "Skin": "#8A5A3C", "Hair": "#1A1A1A"},
    {"Shirt": "#2E3A55", "Pants": "#8A7A5E", "Skin": "#C8916A", "Hair": "#8A8680"},
    {"Shirt": "#A8433A", "Pants": "#3A3E48", "Skin": "#6A4430", "Hair": "#1A1A1A"},
    {"Shirt": "#5A7EA8", "Pants": "#D8D2C4", "Skin": "#E0B090", "Hair": "#B89A6A"},
    {"Shirt": "#D8D2C4", "Pants": "#2E3A55", "Skin": "#C8916A", "Hair": "#4A3424"},
]
for c in CLOTHES:
    c.update({"Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622", "HairBase": c["Hair"]})

DROPLET = "#E8F0F4"


def person(key, name, k, height, location, heading):
    r = rigs.spawn(key, name, height=height, location=location, heading=heading)
    rigs.paint(r, CLOTHES[k % len(CLOTHES)])
    return r


def walk_line(rig, frames, start, heading, speed, z=0.0, phase=0.0):
    """Walks in a straight line with planted foot (the Walk time matches the distance)."""
    d = Vector((math.cos(heading), math.sin(heading), 0))
    pos = [Vector((start[0], start[1], z)) + d * speed * (f - frames[0]) / 30 for f in frames]
    rigs.key_root(rig, frames, pos, [heading] * len(frames))
    per = rigs.planted_speed(rig, "Walk", ["Foot.L", "Foot.R"]) * rig.scale
    a0, a1 = rig.t.actions["Walk"].frame_range
    s0 = a0 + phase * (a1 - a0)
    rigs.timed(rig, "Walk", frames, [s0 + speed / 30 * (f - frames[0]) / per for f in frames])


# ---------- espirro ----------

def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _hand_ik(r, name, side, keys_world_fn, frames, infl_frames, infl_vals):
    """Hand IK (palm) with the target on an empty child of the root; keys_world_fn(f) -> world point. Pole behind and
    below the elbow. IK influence per key (1 = hand on the target, 0 = back to the base cycle)."""
    import anim_curves as ac
    scene = bpy.context.scene
    tgt = bpy.data.objects.new(f"{name}HandTarget", None)
    scene.collection.objects.link(tgt)
    tgt.parent = r.root
    inv = r.root.matrix_world.inverted()
    locs = [inv @ keys_world_fn(f) for f in frames]
    for i in range(3):
        ac.write(tgt, "location", i, frames, [v[i] for v in locs])
    pole = bpy.data.objects.new(f"{name}Pole", None)
    scene.collection.objects.link(pole)
    pole.parent = r.root
    pole.location = (0.45 if side == "L" else -0.45, 0.25, 1.0)     # root: front = -y, left = +x
    c = r.arm.pose.bones[f"Palm.{side}"].constraints.new("IK")
    c.name = "HandIK"
    c.target, c.chain_count, c.pole_target, c.pole_angle = tgt, 3, pole, 0.0
    ac.write(r.arm, f'pose.bones["Palm.{side}"].constraints["HandIK"].influence', 0, infl_frames, infl_vals)
    return tgt


def _head_track(r, frames):
    """World matrix of the Head bone on each frame (with the pose already built)."""
    scene = bpy.context.scene
    out = {}
    for f in frames:
        scene.frame_set(f)
        out[f] = (r.arm.matrix_world @ r.arm.pose.bones["Head"].matrix).copy()
    return out


def sneezer(name, location, heading, peak, total, k=0, side="R", f_nobody=None):
    """Passerby in profile sneezing into a handkerchief. 'peak' = peak frame (frame 0 of the cover). After the peak the
    torso returns with a rebound (16 f + 14 f), the hand stays on the nose (blowing) until ~1.3 s, lowers with the handkerchief to the
    chest and, on *nobody*, puts the handkerchief in the pocket (the handkerchief vanishes into the pocket in 4 f) and drops the arm."""
    import anim_curves as ac
    r = person("man", name, k, 1.78, location, heading)
    rigs.loop(r, "Idle", 1, total, rate=0.7)

    def bend(f):
        t = f - peak
        if t <= 0:
            return 1.0
        if t < 16:
            return 1.0 - 1.15 * _ease(t / 16)
        if t < 30:
            return -0.15 * (1.0 - _ease((t - 16) / 14))
        return 0.0
    frames = list(range(1, total + 1, 2))
    rigs.pose_layer(r, frames, lambda f: {"Torso": rigs.bone_delta(r, "Torso", (1, 0, 0), 14 * bend(f)),
                                          "Neck": rigs.bone_delta(r, "Neck", (1, 0, 0), 10 * bend(f)),
                                          "Head": rigs.bone_delta(r, "Head", (1, 0, 0), 16 * bend(f))})
    bpy.context.view_layer.update()
    fwd = Vector((math.cos(heading), math.sin(heading), 0))
    lat = Vector((-fwd.y, fwd.x, 0)) * (-1 if side == "R" else 1)      # side of the hand
    f_nobody = f_nobody or peak + 200
    t_down = peak + 40                       # hand lowers from the nose
    t_chest = t_down + 14
    t_pocket = f_nobody + 12
    hfr = list(range(1, t_down + 2, 2))
    heads = _head_track(r, sorted(set(hfr + [peak])))
    scene = bpy.context.scene
    hp = heads[peak]
    nose_peak = hp.translation + fwd * 0.15 + Vector((0, 0, -0.04))
    off = hp.inverted() @ nose_peak
    base = r.root.matrix_world.translation.copy()
    chest = base + fwd * 0.28 + lat * 0.05 + Vector((0, 0, 1.18))
    pocket = base + fwd * 0.06 + lat * 0.2 + Vector((0, 0, 0.9))
    last = hfr[-1]

    def world(f):
        if f <= last:      # after the peak the hand lowers from the nose to the mouth (fingers do not rise above the face)
            e = _ease((f - peak) / 10)
            return heads[f] @ off + Vector((0, 0, -0.08 * e)) - fwd * (0.04 * e)
        nose_end = heads[last] @ off + Vector((0, 0, -0.08)) - fwd * 0.04
        if f <= t_chest:
            return nose_end.lerp(chest, _ease((f - last) / (t_chest - last)))
        if f <= f_nobody:
            return chest
        return chest.lerp(pocket, _ease((f - f_nobody) / (t_pocket - f_nobody)))
    kf = sorted(set(hfr + list(range(last, t_chest + 1, 2)) + [t_chest, f_nobody] +
                    list(range(f_nobody, t_pocket + 1, 2)) + [t_pocket]))
    tgt = _hand_ik(r, name, side, world, kf, [1, t_pocket, t_pocket + 12], [1.0, 1.0, 0.0])
    scene.frame_set(peak)
    bpy.context.view_layer.update()
    palm = r.arm.pose.bones[f"Palm.{side}"]
    hand = r.arm.matrix_world @ palm.tail
    cloth = kit.mesh_object(f"{name}Tissue", *kit._ico_geo(0.06, (0, 0, 0), (1.3, 0.7, 1.1))[:2],
                            [rigs.flat_mat("#F2F0EA")])
    for p in cloth.data.polygons:
        p.use_smooth = False
    cloth.parent, cloth.parent_type, cloth.parent_bone = r.arm, "BONE", f"Palm.{side}"
    bpy.context.view_layer.update()
    cloth.matrix_world = Matrix.Translation(hand.lerp(nose_peak, 0.6) + fwd * 0.02)
    sc0 = tuple(cloth.scale)
    for i in range(3):
        ac.write(cloth, "scale", i, [1, t_pocket - 4, t_pocket], [sc0[i], sc0[i], 0.0])
    return SimpleNamespace(rig=r, nose=nose_peak, fwd=fwd, tissue=cloth, target=tgt)


def rub_and_hold(r, name, side, f_rub0, f_colds, total):
    """2nd passerby: rubs the nose (2 cm back and forth, ~2.5 Hz) since f_rub0; on *colds* the sneeze almost comes
    (head and chest back in 6 f, holds 8), does not come (relaxes in 12 f) and the hand lowers."""
    def lean(f):
        t = f - f_colds
        if t < 0:
            return 0.0
        if t < 6:
            return _ease(t / 6)
        if t < 14:
            return 1.0
        return 1.0 - _ease((t - 14) / 12)
    frames = list(range(1, total + 1, 2))
    rigs.pose_layer(r, frames, lambda f: {"Torso": rigs.bone_delta(r, "Torso", (1, 0, 0), -6 * lean(f)),
                                          "Neck": rigs.bone_delta(r, "Neck", (1, 0, 0), -8 * lean(f)),
                                          "Head": rigs.bone_delta(r, "Head", (1, 0, 0), -12 * lean(f))})
    bpy.context.view_layer.update()
    heading = r.root.rotation_euler.z - math.pi / 2
    fwd = Vector((math.cos(heading), math.sin(heading), 0))
    lat = Vector((-fwd.y, fwd.x, 0))
    t_up = f_rub0 + 10
    t_drop = f_colds + 20
    kf = list(range(f_rub0, t_drop + 14, 2))
    heads = _head_track(r, kf)
    rest = r.root.matrix_world.translation + fwd * 0.12 + lat * (-0.22 if side == "R" else 0.22) + Vector((0, 0, 0.95))

    def world(f):
        nose = heads[f].translation + fwd * 0.13 + Vector((0, 0, -0.03))
        if f < f_colds:
            nose = nose + lat * 0.02 * math.sin(2 * math.pi * 2.5 * (f - f_rub0) / 30.0)
        if f < t_up:
            return rest.lerp(nose, _ease((f - f_rub0) / (t_up - f_rub0)))
        if f < t_drop:
            return nose
        return nose.lerp(rest, _ease((f - t_drop) / 12))
    _hand_ik(r, name, side, world, kf, [1, f_rub0, t_up, t_drop, t_drop + 12], [0.0, 0.0, 1.0, 1.0, 0.0])


def droplet_mat():
    m = kit.flat("Droplet", DROPLET, rough=0.4, emission=DROPLET, strength=1.5)
    m.surface_render_method = "BLENDED"
    return m


def droplet_cone(name, nose, fwd, rnd, count=40, length=0.95, spread=19.0, size=(0.010, 0.017), f0=1, fade=(40, 80)):
    """Cone of droplets at the sneeze peak (origin at the nose): the cone opens (x1.5), drifts forward and
    falls, and fades from f0+fade[0] to f0+fade[1] (alpha)."""
    import anim_curves as ac
    side = Vector((-fwd.y, fwd.x, 0))
    up = Vector((0, 0, 1))
    geos = []
    for i in range(count):
        t = rnd.uniform(0.08, 1.0) ** 0.8
        a = math.radians(rnd.gauss(0, spread / 2))
        b = math.radians(rnd.gauss(-6, spread / 2.5))
        d = (fwd * math.cos(a) * math.cos(b) + side * math.sin(a) + up * math.sin(b)).normalized()
        p = fwd * 0.04 + d * (t * length)
        r = rnd.uniform(*size) * (1.15 - 0.4 * t)
        geos.append(kit._ico_geo(r, tuple(p)))
    v, f, _ = kit.merge(*geos)
    mat = droplet_mat()
    o = kit.mesh_object(name, v, f, [mat], tuple(nose))
    o.visible_shadow = False
    frames = list(range(f0, f0 + fade[1] + 1, 2))
    locs, scl = [], []
    for fr in frames:
        u = (fr - f0) / 30.0
        locs.append(Vector(nose) + fwd * (0.35 * (1 - math.exp(-u * 1.5))) + Vector((0, 0, -0.18 * u * u)))
        scl.append(1.0 + 0.5 * (1 - math.exp(-u * 2.0)))
    for i in range(3):
        ac.write(o, "location", i, frames, [p[i] for p in locs])
        ac.write(o, "scale", i, frames, scl)
    p = kit.principled(mat)
    ac.write(mat.node_tree, f'nodes["{p.name}"].inputs["Alpha"].default_value', 0,
             [1, f0 + fade[0], f0 + fade[1]], [1.0, 1.0, 0.0])
    return o


# ---------- waterfront walking ----------

def stadium(center, axis, half, radius):
    """Closed track (2 straights + 2 half-turns): returns (fn(d) -> (point, heading), perimeter)."""
    a = Vector(axis).normalized()
    b = Vector((-a.y, a.x, 0))
    c = Vector(center)
    per = 4 * half + 2 * math.pi * radius
    h0 = math.atan2(a.y, a.x)

    def fn(d):
        d = d % per
        if d < 2 * half:
            return c - b * radius + a * (-half + d), h0
        d -= 2 * half
        if d < math.pi * radius:
            t = d / radius
            return c + a * half + (-b * math.cos(t) + a * math.sin(t)) * radius, h0 + t
        d -= math.pi * radius
        if d < 2 * half:
            return c + b * radius + a * (half - d), h0 + math.pi
        d -= 2 * half
        t = d / radius
        return c - a * half + (b * math.cos(t) - a * math.sin(t)) * radius, h0 + math.pi + t
    return fn, per


def walk_loop(rig, frames, center, axis, half, radius, speed, z=0.0, d0=0.0, phase=0.0):
    """Walks around a track (planted foot: the Walk time comes from the distance)."""
    fn, per = stadium(center, axis, half, radius)
    pos, hd = [], []
    for f in frames:
        p, h = fn(d0 + speed * (f - frames[0]) / 30.0)
        pos.append(Vector((p.x, p.y, z)))
        hd.append(h)
    rigs.key_root(rig, frames, pos, hd)
    per_f = rigs.planted_speed(rig, "Walk", ["Foot.L", "Foot.R"]) * rig.scale
    a0, a1 = rig.t.actions["Walk"].frame_range
    s0 = a0 + phase * (a1 - a0)
    rigs.timed(rig, "Walk", frames, [s0 + speed / 30 * (f - frames[0]) / per_f for f in frames])


def walk_then_idle(rig, start, heading, speed, dist, total, z=0.0, phase=0.0):
    """Walks 'dist' meters (brakes in the last 0.6 m) and stops in Idle (the Walk leaves by influence in 10 f)."""
    rigs.loop(rig, "Idle", 1, total, rate=0.7, phase=phase)
    d = Vector((math.cos(heading), math.sin(heading), 0))
    ds, x = [], 0.0
    brake = 0.6
    while x < dist - 1e-4 and len(ds) < total:
        ds.append(x)
        rem = dist - x
        v = speed if rem > brake else max(0.15, speed * rem / brake)
        x = min(dist, x + v / 30.0)
    ds.append(dist)
    f_stop = len(ds)
    frames = list(range(1, f_stop + 1))
    pos = [Vector((start[0], start[1], z)) + d * x for x in ds]
    rigs.key_root(rig, frames, pos, [heading] * len(frames))
    per_f = rigs.planted_speed(rig, "Walk", ["Foot.L", "Foot.R"]) * rig.scale
    a0, a1 = rig.t.actions["Walk"].frame_range
    s0 = a0 + phase * (a1 - a0)
    fr2 = frames + [f_stop + 10]
    times = [s0 + x / per_f for x in ds] + [s0 + dist / per_f]
    rigs.timed(rig, "Walk", fr2, times, influence=[1.0] * len(frames) + [0.0])
    return f_stop


# ---------- gnus ----------

def _join(parts, name, inv):
    """Joins evaluated meshes (with each one's matrix) into a single mesh, in the 'inv' space (root)."""
    verts, faces, mats, fmat = [], [], [], []
    for me, mw in parts:
        base = len(verts)
        m = inv @ mw
        verts += [tuple(m @ v.co) for v in me.vertices]
        slot0 = len(mats)
        mats += list(me.materials)
        for p in me.polygons:
            faces.append(tuple(base + i for i in p.vertices))
            fmat.append(slot0 + p.material_index)
    out = bpy.data.meshes.new(name)
    out.from_pydata(verts, [], faces)
    for m in mats:
        out.materials.append(m)
    for p, mi in zip(out.polygons, fmat):
        p.material_index = mi
        p.use_smooth = False
    out.update()
    return out


def snapshots(action="Walk", n=8, extra_graze=2):
    """Wildebeest 'photos': n phases of the 'action' cycle and grazing poses, as still meshes (origin on the ground).
    Returns SimpleNamespace(meshes, stride, yaw0): stride = meters per Walk cycle with planted foot; yaw0 =
    rotation to add to the heading so the mesh looks in the heading direction (the mesh comes out in root space)."""
    g = wb.build("GnuSnap", (0, 0, -900.0), heading=0.0, length=2.5)
    scene = bpy.context.scene
    act = g.t.actions[action]
    a0, a1 = act.frame_range
    ad = g.arm.animation_data_create()
    meshes = []
    objs = [o for o in g.root.children_recursive if o.type == "MESH"]

    def grab(label):
        dg = bpy.context.evaluated_depsgraph_get()
        parts = []
        for o in objs:
            oe = o.evaluated_get(dg)
            parts.append((bpy.data.meshes.new_from_object(oe), oe.matrix_world.copy()))
        inv = g.root.matrix_world.inverted()
        me = _join(parts, f"GnuSnap{label}", inv)
        for p, _ in parts:
            bpy.data.meshes.remove(p)
        meshes.append(me)

    ad.action, ad.action_slot = act, act.slots[0]
    keep = scene.frame_current
    for k in range(n):
        scene.frame_set(int(round(a0 + (a1 - a0) * k / n)))
        grab(f"Walk{k}")
    ad.action = None
    wb.graze(g, 10, 60)
    for k in range(extra_graze):
        scene.frame_set(14 + 9 * k)
        grab(f"Graze{k}")
    scene.frame_set(keep)
    for o in rigs.all_objects(g):
        o.hide_render = True
    stride = rigs.planted_speed(g, action, ["FrontFoot.L", "FrontFoot.R", "BackFoot.L", "BackFoot.R"]) * g.scale \
        * (a1 - a0)
    # the front of the mesh: the highest vertices are the horns (symmetric in x: the mean falls on the head axis)
    zmax = max(v.co.z for v in meshes[0].vertices)
    tops = [v.co for v in meshes[0].vertices if v.co.z > 0.9 * zmax]
    cx, cy = sum(c.x for c in tops) / len(tops), sum(c.y for c in tops) / len(tops)
    yaw0 = -math.atan2(cy, cx)          # rotation = heading + yaw0 puts the head along the heading
    return SimpleNamespace(meshes=meshes, stride=stride, yaw0=yaw0)


def blob_mesh(mat):
    """Legless wildebeest silhouette for beyond ~400 m (tall body in front + low head + dark skirt)."""
    body = kit.loft_geo([[(-1.0, -0.22, 0.35), (-1.0, 0.22, 0.35), (-1.0, 0.18, 1.0), (-1.0, -0.18, 1.0)],
                         [(0.4, -0.3, 0.3), (0.4, 0.3, 0.3), (0.4, 0.25, 1.35), (0.4, -0.25, 1.35)],
                         [(1.0, -0.2, 0.55), (1.0, 0.2, 0.55), (1.0, 0.14, 1.15), (1.0, -0.14, 1.15)]])
    head = kit._box_geo(0.5, 0.24, 0.42, 1.0, -0.12, 0.45)
    legs = kit._box_geo(1.9, 0.36, 0.38, -0.95, -0.18, 0.0)
    v, f, _ = kit.merge(body, head, legs)
    me = bpy.data.meshes.new("GnuBlob")
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    me.update()
    return me


def _place(name, mesh, x, y, heading, yaw0=0.0):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    o.location = (sv.ORIGIN.x + x, sv.ORIGIN.y + y, sv.ground_z(x, y))
    o.rotation_euler = (0, 0, heading + yaw0)
    return o


# Herd of 12 (coordinator's correction): ~70 wildebeest in total, ~6x the 11 of scene 11 ("more than five
# times bigger": 250 thousand -> 1.4 million). 7 rigged near (GNUS_12) + 14 grazing standing (already in the 1st frame) +
# 48 walking in lines that enter from the left and right edges starting at *herds*.
GRAZERS_12 = [(-20.0, 52.0), (-34.0, 75.0), (14.0, 66.0), (-6.0, 92.0), (38.0, 110.0), (-48.0, 140.0), (8.0, 160.0),
              (60.0, 190.0), (-25.0, 230.0), (90.0, 140.0), (75.0, 95.0), (52.0, 60.0), (110.0, 230.0),
              (30.0, 260.0)]
# lines: (side -1 left / +1 right, distance y, count, heading angle in degrees against the x axis, frames after
# *herds* when the first crosses the edge)
WALK_FILES = [(-1, 20.0, 7, 6, 0), (-1, 42.0, 7, 9, 10), (-1, 70.0, 6, 4, 22), (-1, 110.0, 5, 8, 4),
              (1, 26.0, 7, 7, 2), (1, 50.0, 6, 10, 14), (1, 88.0, 5, 5, 26), (1, 135.0, 5, 8, 8)]
EDGE = 0.445             # edge of the frame on the ground (x/y) with the camera of the 1st frame of 12 (measured in Blender)


def herd_12(rnd, snaps, f_start, f_herds, f_end):
    """Grazing standing (visible since the 1st frame of 12) + walking lines that enter from the edges. Walking: the root
    moves at the planted-foot speed and the 8 Walk 'photos' take turns (on/off) at the step phase; none
    is born inside the frame (the lines start outside and already walking). Returns (standing, walking roots, all objects)."""
    import anim_curves as ac
    still = []
    for k, (x, y) in enumerate(GRAZERS_12):
        me = snaps.meshes[8 + rnd.randrange(2)]
        still.append(_place(f"Herd_s{k}", me, x, y, rnd.uniform(0, 6.28), snaps.yaw0))
    walkers, every = [], list(still)
    frames = list(range(f_start, f_end + 1, 2))
    for fi, (side, Y, n, ang, lead) in enumerate(WALK_FILES):
        a = math.radians(ang) if side < 0 else math.pi - math.radians(ang)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        lead_f = f_herds + lead
        p_lead = Vector((side * (Y * EDGE + 1.4), Y, 0.0))   # the muzzle at the edge in frame 'lead'
        for i in range(n):
            speed = rnd.uniform(1.6, 1.85)           # wide migration stride
            p0 = p_lead - d * (i * rnd.uniform(2.9, 3.6)) + Vector((-d.y, d.x, 0)) * rnd.gauss(0, 1.1)
            root = bpy.data.objects.new(f"Walk{fi}_{i}", None)
            bpy.context.collection.objects.link(root)
            pos = []
            for f in frames:
                q = p0 + d * speed * (f - lead_f) / 30.0
                pos.append((q.x, q.y, sv.ground_z(q.x, q.y)))
            for c in range(3):
                ac.write(root, "location", c, frames, [p[c] for p in pos])
            root.rotation_euler = (0, 0, a + snaps.yaw0)
            # step phase: 8 photos per cycle of 'stride' meters
            ph0 = rnd.random()
            idx = [int(8 * (ph0 + speed * (f - f_start) / 30.0 / snaps.stride)) % 8 for f in range(f_start, f_end + 1)]
            change = [f_start] + [f_start + j for j in range(1, len(idx)) if idx[j] != idx[j - 1]]
            for k in range(8):
                o = bpy.data.objects.new(f"Walk{fi}_{i}_p{k}", snaps.meshes[k])
                bpy.context.collection.objects.link(o)
                o.parent = root
                ks = [1] + change
                vals = [1.0] + [0.0 if idx[f - f_start] == k else 1.0 for f in change]
                ac.write(o, "hide_render", 0, ks, vals, ac.CONSTANT)
                o.hide_render = True
                every.append(o)
            walkers.append(root)
            every.append(root)
    return still, walkers, every


# rigged wildebeest: 11 (10-12 spread out, 20-150 m) and 12 (the near ones)
GNUS_11 = [(0.7, 15.0, 200, "graze"), (-14.0, 26.0, 30, "graze"), (9.0, 34.0, 120, "idle"), (-30.0, 48.0, 80, "graze"),
           (22.0, 55.0, 250, "graze"), (-6.0, 70.0, 160, "idle"), (40.0, 90.0, 300, "graze"), (-48.0, 95.0, 10, "graze"),
           (12.0, 120.0, 210, "graze"), (-25.0, 140.0, 330, "idle"), (60.0, 150.0, 60, "graze")]
GNUS_12 = [(-8.5, 16.0, 30, "graze"), (6.5, 18.0, 260, "graze"), (-2.5, 24.0, 120, "graze"), (13.0, 30.0, 200, "graze"),
           (-16.0, 28.0, 80, "idle"), (30.0, 34.0, 150, "graze"), (9.0, 13.5, 300, "graze")]


def head_up_fn(fu, up=-10.0, rise=14):
    """Neck: grazing -> anticipates (sinks 5 deg in 4 frames) -> raises the head in 'rise' frames (ease) and stays."""
    def fn(f, down):
        if f < fu:
            return down
        if f < fu + 4:
            return down + 5.0 * ac_ease((f - fu) / 4)
        u = ac_ease((f - fu - 4) / rise)
        return down + 5.0 + (up - down - 5.0) * u
    return fn


def snort_fns(fs, up=2.0):
    """Snort: the head rises fast (6 frames) and shakes (+-9 deg, 3 beats in 12 frames, damped) and stays high."""
    def down_fn(f, down):
        if f < fs:
            return down
        return down + (up - down) * ac_ease((f - fs) / 6)

    def head_fn(f):
        if f < fs + 4 or f > fs + 18:
            return 0.0
        t = (f - fs - 4) / 14
        return 9.0 * math.sin(t * 3 * 2 * math.pi) * (1 - t)
    return down_fn, head_fn


def ac_ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def rigged_gnus(spec, prefix, f0, f1, rnd, fns=None):
    """fns = {index: (down_fn, head_fn)} for those that raise the head or snort."""
    out = []
    fns = fns or {}
    for k, (x, y, hd, mode) in enumerate(spec):
        g = wb.build(f"{prefix}{k}", (sv.ORIGIN.x + x, sv.ORIGIN.y + y, sv.ground_z(x, y)),
                     heading=math.radians(hd), length=rnd.uniform(2.35, 2.6))
        down_deg, phase = rnd.uniform(48, 60), rnd.random()
        if mode == "graze" or k in fns:
            dfn, hfn = fns.get(k, (None, None))
            wb.graze(g, f0, f1, down_deg=down_deg, phase=phase, down_fn=dfn, head_fn=hfn)
        else:
            rigs.loop(g, "Idle", f0 - 40, f1 + 40, rate=0.6, phase=phase)
        out.append(g)
    return out
