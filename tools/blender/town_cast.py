"""Cast of technology-disappeared: cars (Quaternius Cars, CC0), drivers and townspeople (Quaternius Man and
Woman Casual, CC0), horse (Quaternius Horse, CC0), bicycle and cart (made here, rigid pieces).

Proportions:
- Mid-size sedan: 4.6 to 4.9 m x 1.8 m x 1.45 m; driver's hip point at ~0.5 m from the floor (SAE J1100).
- People: 1.58 to 1.85 m. Light draft horse: 1.55 m at the withers, 2.4 m from muzzle to rump (~2.7 m with the
  tail). Bicycle: 26" rim (0.66 m), wheelbase 1.05 m. 2-wheel cart: 1.2 m wheels.
Low-poly references: Quaternius's own packs (Cars Pack, Animated Animals) and Kenney Car Kit.
The downloaded files are data: we only import mesh, bones and actions.
"""

import math
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
import rigs
from town_set import mat

CAR_DIR = Path(rigs.ASSETS) / "quaternius/cars/Realistic Car Pack - Nov 2018/FBX"
CAR_SCALE = 1.1
SHIRTS = ["#2E3A52", "#8A94A6", "#6B4E3A", "#7A2E2E", "#C9A227", "#3F5A73", "#D8D2C4", "#4E6B4A", "#A85A3A"]
PANTS = ["#2A3446", "#4A4038", "#1E2228", "#6B5A44", "#3A4252"]
SKINS = ["#C8916A", "#8D5A3C", "#E0B08A", "#5E3A26", "#B07850"]
HAIRS = ["#2A1E16", "#4A3424", "#8A6A4A", "#1A1A1A", "#B8A080"]
CAR_COLORS = ["#8A94A6", "#5A2A2A", "#2F4A3A", "#C9BFA8", "#1F2E4A", "#B9C2CC", "#6B2E22"]
_cars = {}


# ---------- carros ----------

def _car_template(kind):
    if kind in _cars:
        return _cars[kind]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(CAR_DIR / f"{kind}.fbx"))
    new = [o for o in bpy.data.objects if o not in before]
    parts = {}
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        mw = o.matrix_world.copy()
        o.data.transform(mw)                                  # everything in world coordinates (FBX scale)
        o.matrix_world = Matrix.Identity(4)
        lo = Vector(map(min, *[v.co for v in o.data.vertices]))
        hi = Vector(map(max, *[v.co for v in o.data.vertices]))
        c = (lo + hi) / 2
        if "Wheel" in o.name:
            o.data.transform(Matrix.Translation(-c))          # wheel spins around its own axis
            parts[o.name.split("_")[-1]] = (o.data, c, (hi.z - lo.z) / 2)
        else:
            parts["Body"] = (o.data, Vector((0, 0, 0)), 0)
        for m in o.data.materials:
            p = kit.principled(m)
            p.inputs["Alpha"].default_value = 1.0             # 2018 FBX: Alpha 0 (invisible in Eevee)
            p.inputs["Specular IOR Level"].default_value = 0.0
            p.inputs["Roughness"].default_value = 0.6
        bpy.data.objects.remove(o, do_unlink=True)
    _cars[kind] = parts
    return parts


def _car_mats(name, color):
    return {"body": mat(f"CarPaint{color}", color, rough=0.55),
            "head": mat("Headlight", "#FFF0D0", emission="#FFE2A8", strength=6.0),
            "tail": mat("Taillight", "#5A1410", emission="#FF2A1A", strength=2.5),
            "glass": mat("CarGlass", "#141A24", rough=0.3)}


def car(name, kind, color, location, heading):
    """Car with its own root (empty), body and wheels as children; heading 0 = +x (the asset faces -y)."""
    parts = _car_template(kind)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = (0, 0, heading + math.pi / 2)
    root.scale = (CAR_SCALE,) * 3
    mats = _car_mats(name, color)
    body_names = ("Blue", "LightBlue", "White", "Material.007")
    meshes, wheels = [], []
    for key, (data, c, radius) in parts.items():
        o = bpy.data.objects.new(f"{name}{key}", data)
        bpy.context.collection.objects.link(o)
        o.parent = root
        o.location = c
        o.rotation_mode = "XYZ"
        for slot in o.material_slots:
            base = slot.material.name.split(".")[0] if slot.material else ""
            pick = ("body" if slot.material and slot.material.name in body_names else
                    "head" if base == "Headlights" else "tail" if base == "TailLights" else
                    "glass" if base == "Windows" else None)
            if pick:
                slot.link = "OBJECT"
                slot.material = mats[pick]
        meshes.append(o)
        if key != "Body":
            wheels.append((o, radius * CAR_SCALE))
    beams = []
    for side in (-0.55, 0.55):
        light = bpy.data.lights.new(f"{name}Beam", "SPOT")
        light.energy, light.color = 450.0, (1.0, 0.86, 0.66)
        light.spot_size, light.spot_blend = math.radians(55), 0.5
        light.use_shadow = False
        lo = bpy.data.objects.new(f"{name}Beam", light)
        bpy.context.collection.objects.link(lo)
        lo.parent = root
        lo.location = (side, -2.05, 0.7)
        lo.rotation_euler = (math.radians(-84), 0, 0)             # forward (-y) and slightly down
        beams.append(lo)
    return SimpleNamespace(root=root, meshes=meshes, wheels=wheels, beams=beams, heading=heading)


def roll_to_stop(c, f0, f_stop, stop_xy, speed):
    """Arrives rolling at 'speed' m/s and brakes to a stop at stop_xy on frame f_stop (constant deceleration).
    Wheels spin by distance. Keys on every frame, LINEAR."""
    d_dir = Vector((math.cos(c.heading), math.sin(c.heading), 0))
    T = (f_stop - f0) / 30.0
    D = speed * T / 2
    frames = list(range(f0, f_stop + 1))
    for f in frames:
        u = (f - f0) / max(f_stop - f0, 1)
        left = D * (1 - u) ** 2
        p = Vector((*stop_xy, c.root.location.z)) - d_dir * left
        c.root.location = p
        c.root.keyframe_insert("location", frame=f)
        for w, r in c.wheels:
            w.rotation_euler.x = (D - left) / r
            w.keyframe_insert("rotation_euler", frame=f)
    for o in (c.root, *[w for w, _ in c.wheels]):
        _linear_all(o)


def _linear_all(o):
    ad = o.animation_data
    if ad is None or ad.action is None:
        return
    for fc in rigs._fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# ---------- people ----------

def person(key, name, height, k, location=(0, 0, 0), heading=0.0):
    r = rigs.spawn(key, name, height=height, location=location, heading=heading)
    colors = {"Shirt": SHIRTS[k % len(SHIRTS)], "Pants": PANTS[(k * 3) % len(PANTS)], "Skin": SKINS[(k * 2) % len(SKINS)],
              "Hair": HAIRS[(k * 7) % len(HAIRS)], "HairBase": HAIRS[(k * 7) % len(HAIRS)], "Eyes": "#1A1410",
              "Socks": "#D8D2C4", "Shoes": "#2A2622"}
    rigs.paint(r, colors)
    return r


def segment(rig, action_key, f0, f1, a0, a1, rate=1.0):
    """NLA strip playing only the a0..a1 stretch of the action in a cycle from f0 to f1 (e.g. Sitting without the sit-down part)."""
    act = rig.t.actions[action_key]
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    st = track.strips.new(action_key, int(f0), act)
    st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.action_frame_start, st.action_frame_end = a0, a1
    st.scale = rigs.strip_scale(rate)
    st.repeat = max(1.0, (f1 - f0) / ((a1 - a0) * st.scale) + 1.0)
    st.extrapolation = "HOLD"
    return st


def bend(rig, spec):
    """{bone: [(axis, degrees), ...]} -> {bone: Quaternion} (added to the cycle by the COMBINE layer)."""
    out = {}
    for bone, rots in spec.items():
        q = None
        for axis, deg in rots:
            d = rigs.bone_delta(rig, bone, axis, deg)
            q = d if q is None else q @ d
        out[bone] = q
    return out


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def ground_sit(rig, u):
    """Fraction u (0..1) between the chair (Sitting) and sitting on the ground: knees straighten, torso goes slightly back."""
    return {"LowerLeg.L": [(X, -78 * u)], "LowerLeg.R": [(X, -70 * u)], "UpperLeg.L": [(X, -8 * u)],
            "UpperLeg.R": [(X, -12 * u)], "Abdomen": [(X, -6 * u)]}


SEAT_Z = {"NormalCar1": -0.14, "NormalCar2": -0.18, "SUV": 0.08}     # driver root (m, world) per model: head
                                                                      # below the roof (1.30 / 1.23 / 1.66 m), checked in a still


def feet_follow(rig):
    """In this asset the feet are control bones (children of the root, not of the shin): whoever bends/stretches the leg over
    the cycle must take the foot along, otherwise the foot stays on the ground and the leg goes through the car."""
    for side in ("L", "R"):
        c = rig.arm.pose.bones[f"Foot.{side}"].constraints.new("COPY_LOCATION")
        c.target, c.subtarget, c.head_tail = rig.arm, f"LowerLeg.{side}", 1.0


def driver(name, key, c, k, kind, seat=(0.36, 0.12)):
    """Driver seated in the seat (Sitting), root child of the car (moves with it in 01). Seated driver height
    1.64 / 1.58 m and seat per car model (SEAT_Z): no head goes through the roof."""
    height = 1.64 if key == "man" else 1.58
    r = person(key, name, height, k)
    r.height = height
    r.root.parent = c.root
    r.root.location = (seat[0], seat[1], SEAT_Z[kind] / CAR_SCALE)
    r.root.rotation_euler = (0, 0, 0)
    r.root.scale = (1 / CAR_SCALE,) * 3
    feet_follow(r)
    return r


def drop(r, f_fall, f_end, look_yaw=25.0):
    """Falls from the seat that vanished: 2 frames of fright (shoulders rise), fall with acceleration (root -0.39 m in 8 frames),
    impact on the exact frame (torso folds forward and back, a 3-frame bounce), and rest looking around.
    The legs stretch during the fall (arrives seated on the ground)."""
    z0 = r.root.location.z
    z_end = (0.11 - 0.409 * r.height / 1.75) / CAR_SCALE            # hip at 11 cm from the asphalt, legs stretched
    drop_m = z0 - z_end
    hit = f_fall + max(5, int(round(30 * math.sqrt(2 * drop_m * CAR_SCALE / 9.8))))   # true free fall
    frames = list(range(1, f_end + 1))
    for f in frames:
        if f < f_fall:
            z = z0
        elif f <= hit:
            u = (f - f_fall) / (hit - f_fall)
            z = z0 - drop_m * u * u
        else:
            s = f - hit
            z = z0 - drop_m + (0.035 / CAR_SCALE) * math.sin(math.pi * min(s, 3) / 3) * (1 if s <= 3 else 0)
        r.root.location.z = z
        r.root.keyframe_insert("location", index=2, frame=f)
    _linear_all(r.root)

    def pose(f):
        u = min(max((f - f_fall) / (hit - f_fall), 0.0), 1.0)
        e = u * u * (3 - 2 * u)
        spec = ground_sit(r, 1.0)                                   # legs stretched forward already in the car: they stay
        spec["Abdomen"] = [(X, -14 + 8 * e)]                       # inside the body (nothing below the floor);
                                                                    # leaning on the reclined seat (head below the roof)
        jolt = math.sin(math.pi * min(max((f - f_fall + 2) / 4, 0), 1))           # fright: shoulders rise
        s = f - hit
        squash = 14 * math.exp(-max(s, 0) / 4) * math.sin(math.pi * min(max(s, 0) / 6, 1)) if s >= 0 else 0
        look = look_yaw * min(max((f - hit - 12) / 24, 0), 1) * math.sin(math.pi * min(max((f - hit - 12) / 60, 0), 1))
        spec["Torso"] = [(X, squash - 4 * jolt)]
        spec["Neck"] = [(X, 0.6 * squash), (Z, look)]
        spec["Head"] = [(X, -6 * jolt), (Z, 0.6 * look)]
        spec["Shoulder.L"] = [(Z, 6 * jolt)]
        spec["Shoulder.R"] = [(Z, -6 * jolt)]
        return bend(r, spec)

    rigs.pose_layer(r, frames, pose)


# ---------- arms by IK (holding things) ----------

def bone_local(rig, bone, frame=None, tail=False):
    """Position of a bone (head or tip) in the character root coordinates (front = -y, right = -x)."""
    scene = bpy.context.scene
    if frame is not None:
        scene.frame_set(frame)
    bpy.context.view_layer.update()
    pb = rig.arm.pose.bones[bone]
    w = rig.arm.matrix_world @ (pb.tail if tail else pb.head)
    return rig.root.matrix_world.inverted() @ w


def empty(name, parent, location, size=0.05):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    bpy.context.collection.objects.link(e)
    e.parent = parent
    e.location = location
    return e


def arm_ik(rig, side, target, pole, pole_angle=-90.0):
    """Arm (LowerArm + Palm, the arm and forearm bones in this asset) reaches the empty 'target' (the fist); the elbow points to 'pole'."""
    ik = rig.arm.pose.bones[f"Palm.{side}"].constraints.new("IK")      # in the asset, LowerArm = arm, Palm = forearm
    ik.target = target
    ik.pole_target = pole
    ik.pole_angle = math.radians(pole_angle)
    ik.chain_count = 2
    ik.use_stretch = False
    return ik


def hold(rig, side, parent, location, pole_location, pole_parent=None, pole_angle=-90.0):
    """Shortcut: creates target (child of 'parent') and pole (child of the root) and enables the arm IK."""
    t = empty(f"{rig.name}Hand{side}", parent, location)
    p = empty(f"{rig.name}Elbow{side}", pole_parent or rig.root, pole_location)
    arm_ik(rig, side, t, p, pole_angle)
    return t, p


def walk_timed(rig, frames, speed, phase=0.0, feet=("Foot.L", "Foot.R")):
    """Walk time matched to the distance (foot planted): the cycle moves 'speed' m/s."""
    per = rigs.planted_speed(rig, "Walk", list(feet)) * rig.scale
    a0, a1 = rig.t.actions["Walk"].frame_range
    start = a0 + phase * (a1 - a0)
    rigs.timed(rig, "Walk", frames, [start + speed / 30 * (f - frames[0]) / per for f in frames])


HORSE_FEET = ("FF.L", "FFB.L")


def walk_line(rig, frames, start, heading, speed, phase=0.0, feet=("Foot.L", "Foot.R"), z=0.0):
    """Walks in a straight line from 'start' (x, y) in the heading direction (rad) at 'speed' m/s, foot planted."""
    d = Vector((math.cos(heading), math.sin(heading), 0))
    pos = [Vector((*start, z)) + d * speed * (f - frames[0]) / 30 for f in frames]
    rigs.key_root(rig, frames, pos, [heading] * len(frames))
    walk_timed(rig, frames, speed, phase, feet)


def look_up(rig, frames, pitch=30.0, yaw=0.0, sway=4.0, seed=0.0):
    """Head and neck up (the sky), with a slow sway (alive, not walking)."""
    def pose(f):
        s = math.sin(f * 0.035 + seed)
        return bend(rig, {"Neck": [(X, -0.45 * pitch), (Z, yaw * 0.5 + sway * s)],
                          "Head": [(X, -0.55 * pitch), (Z, yaw * 0.5 + sway * 0.6 * s)],
                          "Torso": [(X, -5.0)]})
    rigs.pose_layer(rig, frames, pose)


# ---------- roles ----------

def sack_carrier(rig, sack_obj):
    """Sack on the right shoulder (child of the Torso bone: follows the body) and the right hand holding it from above."""
    sh = bone_local(rig, "UpperArm.R")
    torso = bone_local(rig, "Torso")
    sack_obj.parent = rig.root
    # lying on the right shoulder, upright (30 cm thickness at the side), outside the head (~10 cm radius):
    # before it was centered on the neck and went through the face.
    sack_obj.location = Vector((sh.x - 0.1, torso.y + 0.05, sh.z + 0.2))
    sack_obj.rotation_euler = (math.radians(-12), math.radians(90), 0.0)
    _bone_parent(sack_obj, rig, "Torso")
    hold(rig, "R", sack_obj, Vector((0.0, -0.24, 0.0)), sh + Vector((-0.3, -0.2, -0.45)))


def _bone_parent(obj, rig, bone):
    """Becomes a child of the bone without changing place (at the current frame)."""
    bpy.context.view_layer.update()
    w = obj.matrix_world.copy()
    obj.parent = rig.arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = w


def bike_pusher(rig, bike_root, grips):
    """Bicycle to the right of the person (child of the root: moves along). As one really pushes it walking beside it: the
    left hand crosses in front to the nearest grip and the right holds the saddle."""
    bike_root.parent = rig.root
    bike_root.location = (-0.36, 0.06, 0.0)
    bike_root.rotation_euler = (0, 0, math.pi)                 # front of the bicycle = front of the person (-y)
    bpy.context.view_layer.update()
    sl, sr = bone_local(rig, "UpperArm.L"), bone_local(rig, "UpperArm.R")
    hold(rig, "L", bike_root, grips["R"] + Vector((0, 0, 0.02)), sl + Vector((0.35, 0.1, -0.4)))
    hold(rig, "R", bike_root, Vector((0.0, -0.2, 0.9)), sr + Vector((-0.4, -0.2, -0.3)))


def _hoe_phase(u):
    """Hoe cycle (u 0..1): rises slowly (0..0.6), drops accelerating (0.6..0.72), pulls the soil (0.72..1).
    Returns (handle angle in degrees, how much the hands rose 0..1, hand pullback in m)."""
    if u < 0.6:
        e = u / 0.6
        e = e * e * (3 - 2 * e)
        return -35 - 115 * e, e, 0.0
    if u < 0.72:
        e = (u - 0.6) / 0.12
        e = e * e
        return -150 + 115 * e, 1 - e, 0.0
    e = (u - 0.72) / 0.28
    return -35 + 6 * math.sin(math.pi * e), 0.0, 0.12 * math.sin(math.pi * e)


def hoe_worker(rig, tool, frames, period=42, phase=0.0):
    """Weeding: the hoe rises in front of the head and drops into the bed, in a cycle of 'period' frames; the torso bends
    on the drop. The hoe rotates around the hands; the hands (IK) stay attached to the handle."""
    pivot = empty(f"{rig.name}HoePivot", rig.root, Vector((0.0, -0.35, 1.0)))
    pivot.rotation_mode = "XYZ"
    tool.parent = pivot
    tool.location = (0.0, 0.0, -1.2)
    tool.rotation_euler = (0, 0, 0)
    sh = bone_local(rig, "UpperArm.R")
    hold(rig, "R", pivot, Vector((0.0, 0.0, 0.0)), sh + Vector((-0.4, 0.2, -0.3)))
    hold(rig, "L", pivot, Vector((0.0, 0.0, -0.3)), sh + Vector((0.6, 0.2, -0.3)))
    for f in frames:
        ang, up, pull = _hoe_phase(((f / period) + phase) % 1.0)
        pivot.location = (0.0, -0.38 + 0.08 * up + pull, 0.95 + 0.4 * up)
        pivot.rotation_euler = (math.radians(ang), 0, 0)
        pivot.keyframe_insert("location", frame=f)
        pivot.keyframe_insert("rotation_euler", frame=f)
    _linear_all(pivot)

    def pose(f):
        _, up, _ = _hoe_phase(((f / period) + phase) % 1.0)
        return bend(rig, {"Abdomen": [(X, 20 - 14 * up)], "Torso": [(X, 10 - 8 * up)], "Head": [(X, 10 - 14 * up)]})
    rigs.pose_layer(rig, frames, pose)
    return pivot


def knees_up(rig, u=1.0):
    """Sitting on the ground with knees up (from the chair Sitting): the thighs rise ~40 deg; the root drops
    0.29 m so the hip touches the ground."""
    return {"UpperLeg.L": [(X, 40 * u), (Z, 8 * u)], "UpperLeg.R": [(X, 38 * u), (Z, -8 * u)]}


STRIKE_PERIOD = 20
FIRE_SPOT = Vector((-0.36, -0.42, 0.0))   # within reach of the hand: at 0.55 m the targets were out of the arm's range     # pile of grass in the root coordinates of the one lighting it


def fire_starter(rig, flint_obj, knife_obj, frames, strikes):
    """Sitting on the ground (legs forward), the pile of grass in front and to the right (FIRE_SPOT): flint in the left hand, resting on the grass; the knife in the
    right goes up and down scraping the stone on each strike (frames in 'strikes'). Between strikes, hands at rest."""
    rig.arm.location.z -= 0.3                                # hip on the ground, legs forward
    feet_follow(rig)
    sh = bone_local(rig, "UpperArm.R", frames[0])
    flint_obj.scale = knife_obj.scale = (1.5, 1.5, 1.5)          # 1.5x: reads on a phone
    # Flint in the RIGHT hand, resting on the grass; knife in the LEFT, striking from above. Targets at <= 0.55 m from the
    # shoulder (arm 0.58 m): before they were at 0.7-0.8 m, the IK did not reach and the stone floated 0.5 m from the hand.
    shl = bone_local(rig, "UpperArm.L", frames[0])
    FLINT = Vector((-0.26, -0.32, 0.42))
    left = empty(f"{rig.name}KnifeHand", rig.root, Vector((-0.12, -0.30, 0.52)))
    right = empty(f"{rig.name}FlintHand", rig.root, FLINT)
    for e in (left, right):
        e.rotation_mode = "XYZ"
    arm_ik(rig, "L", left, empty(f"{rig.name}ElbowL", rig.root, shl + Vector((0.6, 0.0, -0.3))))
    arm_ik(rig, "R", right, empty(f"{rig.name}ElbowR", rig.root, sh + Vector((-0.6, 0.0, -0.3))))
    flint_obj.parent = right
    flint_obj.location = (0.0, 0.0, 0.0)
    knife_obj.parent = left
    knife_obj.location = (0.0, 0.0, 0.0)
    knife_obj.rotation_euler = (math.radians(-20), 0, math.radians(-15))
    for f in frames:
        lift, hit = 0.0, 0.0
        for s in strikes:
            d = f - s
            if -14 <= d < 0:                                 # rises (anticipation), holds at the top
                e = (d + 14) / 10
                lift = max(lift, math.sin(math.pi / 2 * min(e, 1.0)))
            elif 0 <= d < 8:                                 # strike: drops fast and returns
                hit = max(hit, 1 - d / 8)
        left.location = (-0.16 + 0.04 * lift - 0.08 * hit, -0.30, 0.52 + 0.16 * lift - 0.08 * hit)   # strike scrapes the stone
        left.keyframe_insert("location", frame=f)
        right.location = FLINT + Vector((0.0, 0.0, 0.015 * hit))
        right.keyframe_insert("location", frame=f)
    for e in (left, right):
        _linear_all(e)

    def pose(f):
        hit = max([max(0.0, 1 - (f - s) / 8) for s in strikes if 0 <= f - s < 8] or [0.0])
        spec = ground_sit(rig, 0.8)
        spec["Abdomen"] = [(X, 24)]
        spec["Torso"] = [(X, 8 + 4 * hit)]
        spec["Head"] = [(X, 22)]
        return bend(rig, spec)
    rigs.pose_layer(rig, frames, pose)
    # stone and knife attached to the hand bones (they follow the fist on each strike, even if the IK does not reach the target)
    for obj, bone in ((flint_obj, "MiddleHand.R"), (knife_obj, "MiddleHand.L")):
        bpy.context.scene.frame_set(frames[0] + 6)
        bpy.context.view_layer.update()
        pb = rig.arm.pose.bones[bone]
        grip = rig.arm.matrix_world @ pb.head.lerp(pb.tail, 0.5)
        mw = obj.matrix_world.copy()
        mw.translation = grip
        obj.parent = rig.arm
        obj.parent_type = "BONE"
        obj.parent_bone = bone
        bpy.context.view_layer.update()
        obj.matrix_world = mw
    return left, right


def pointer(rig):
    """Right arm pointing at the sky (target above and in front of the head)."""
    sh = bone_local(rig, "UpperArm.R")
    return hold(rig, "R", rig.root, sh + Vector((-0.1, -0.3, 0.42)), sh + Vector((-0.5, 0.3, -0.2)))
