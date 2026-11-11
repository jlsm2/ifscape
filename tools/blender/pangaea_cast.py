"""Cast of pangaea-never-split with the Quaternius CC0 assets (rigs.py): Apatosaurus herd (scene 04),
the dusk pair that raise their heads at the flash (06), the small mammals (Rat; 06 and 07), the people
in animal skins with spears (08) and the animals on the globes (05).

Proportions:
- Apatosaurus louisae: ~21 to 23 m long, hip at ~4.5 m (Taylor 2010; Wedel & Taylor 2013,
  "Neural spine bifurcation in sauropod dinosaurs"); in the video, 22 m. The neck rises ~20 to 30 deg above the
  horizontal (neutral posture estimated between horizontal and 40 deg, Taylor, Wedel & Naish 2009, "Head and neck
  posture in sauropod dinosaurs inferred from extant animals", Acta Palaeontologica Polonica 54: 213-220).
- Shrew-like Mesozoic mammal (Morganucodon ~10 cm; Repenomamus ~1 m): the rat is 0.7 m with the
  tail, big enough to read at 3 m from the camera (like the old model).
- People: 1.62 to 1.78 m.
Low-poly references: Quaternius's own packs (Animated Dinosaurs, Animals, Ultimate Animated
Characters) and the Kenney Nature Kit (flat palette, 3 to 5 colors per animal).
"""

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

import caveman
import kit
import plant
import rigs

APATO_FEET = [("FrontFoot.L", "FrontLowLeg.L"), ("FrontFoot.R", "FrontLowLeg.R"),
              ("BackFoot.L", "BackLowLeg.L"), ("BackFoot.R", "BackLowLeg.R")]
APATO_TINTS = ("#76875A", "#6C7D52", "#808C5E", "#72825A", "#7A8A5C")
APATO_BELLY = "#B4B48A"
RAT_COLORS = {"Grey": "#6B5544", "Pink": "#B88A7C"}
DARK = "#16181C"
SKINS = ["#A87650", "#C0946A", "#7E563C"]          # 3 items: rnd.choice(SKINS) draws as before
HIDES = ["#5E4430", "#6E5034", "#4E3826"]          # tunic and loincloth: browns (3 items, same draw)
# Prehistoric costume of each person in scene 08 (caveman.dress): bare chest with loincloth or one-shoulder tunic,
# short fur cape (ochre or brown), long hair, beard on two men, bundle on the back of one.
LOOKS = (dict(top="bare", cape="#B8945C", hair="#3A2A1E", beard=True, bundle=False, hair_low=0.82, hairline=0.97),
         dict(top="tunic", cape="#957552", hair="#2E2218", beard=False, bundle=False, hair_low=0.77, hairline=0.975),
         dict(top="tunic", cape=None, hair="#4A3424", beard=True, bundle=True, hair_low=0.81, hairline=0.97),
         dict(top="tunic", cape="#C9A46A", hair="#33261A", beard=False, bundle=False, hair_low=0.78, hairline=0.975),
         dict(top="bare", cape="#9C8064", hair="#3E2C1E", beard=False, bundle=False, hair_low=0.82, hairline=0.97))


def apatosaurus(name, length, tint, location=(0, 0, 0), heading=0.0):
    r = rigs.spawn("apatosaurus", name, length=length, location=location, heading=heading)
    rigs.paint(r, {"Brown": tint, "Material": APATO_BELLY, "LightBrown": "#5A5040", "Black": DARK})
    return r


def _neck(rig, pitch, yaw=0.0):
    """Neck raised (pitch > 0) and turned (yaw > 0 = to the animal's left), split among the bones; the
    head compensates part of the pitch so the snout does not point at the sky."""
    out = {}
    for bone, kp, ky in (("Shoulders", 0.6, 0.45), ("Neck", 0.4, 0.4), ("Head", -0.6, 0.15)):
        out[bone] = rigs.bone_delta(rig, bone, (0, 0, 1), yaw * ky) @ rigs.bone_delta(rig, bone, (1, 0, 0), -pitch * kp)
    return out


# ---------- scene 04: herd ----------

def herd(tl, rnd, ground_z, path_x=-34.0):
    """Five Apatosaurus walking along +y on the x = -34 path, each at its own pace, neck raised (COMBINE layer
    over the Walk) and feet planted (plant.walk). The rnd draws are the same as the old herd
    (in the same order), so the rest of the set that uses the same generator does not change."""
    draws = [(rnd.uniform(-3, 3), rnd.uniform(0.85, 1.05)) for _ in range(5)]
    necks = [rnd.uniform(-5, 10) for _ in range(5)]
    f0, f1 = tl.at("04") - 2, tl.at("04", 1.0) + 2
    mid = tl.at("04", 0.5)
    y_mid = (12.0, -16.0, 38.0, -42.0, 62.0)                 # mid-scene: one in the center, the others entering
    out = []
    for k, ((dx, sc), neck) in enumerate(zip(draws, necks)):
        r = apatosaurus(f"Herd{k}", 22.0 * sc, APATO_TINTS[k])
        plant.walk(r, APATO_FEET, f0, f1, (path_x + dx, y_mid[k]), math.pi / 2, ground_z, rate=1.5 + 0.05 * k,
                   phase=(0.37 * k) % 1.0, speed_from=["FrontFoot.L", "FrontFoot.R"], sink=0.2, anchor=mid)
        up = _neck(r, 22 + neck)
        rigs.pose_layer(r, [f0, f1], lambda f, up=up: up)
        out.append(r)
    return out


# ---------- scene 06: the dusk pair ----------

def dusk_pair(tl, ground_z, impact_xy, flash_frame):
    """Two Apatosaurus grazing (Idle), one on each side of the impact (which stays clear in the middle), three-quarter view. At the flash: a start (the head lowers
    4 frames), then rises and turns to the fire with ease-out, slightly past it, and settles."""
    specs = (((-6.0, 36.0), math.radians(160), 20.0, APATO_TINTS[0], 0.0),
             ((17.0, 48.0), math.radians(125), 17.0, APATO_TINTS[2], 0.45))
    a, b = tl.at("06") - 2, tl.at("06", 1.0) + 2
    out = []
    for k, ((x, y), h, length, tint, phase) in enumerate(specs):
        r = apatosaurus(f"Dusk{k}", length, tint, (x, y, ground_z(x, y)), h)
        r.arm.location.z -= 0.15 * r.scale
        rigs.loop(r, "Idle", a, b, rate=0.8, phase=phase)
        aim = math.atan2(impact_xy[1] - y, impact_xy[0] - x)
        yaw = math.degrees((aim - h + math.pi) % (2 * math.pi) - math.pi)
        r0 = flash_frame + 3 + 2 * k                              # reaction time, one after the other

        def pose(f, r=r, r0=r0, yaw=yaw):
            if f < r0:
                return _neck(r, 0.0)
            if f < r0 + 4:
                return _neck(r, -4.0 * math.sin(math.pi * (f - r0) / 8))
            u = (f - r0 - 4) / 16
            e = 1 - (1 - min(u, 1.0)) ** 3                        # ease-out
            over = 1.0 + 0.06 * math.sin(math.pi * min(max((u - 0.6) / 0.6, 0), 1))
            return _neck(r, -4.0 * (1 - min(u * 3, 1)) + 26.0 * e * over, yaw * e * over)

        rigs.pose_layer(r, list(range(a, b + 1)), pose)
        out.append(r)
    return out


# ---------- scenes 06 and 07: mammals ----------

RAT_RUNS = (("06", [(1.2, 3.5), (0.4, 2.8), (-0.6, 2.4), (-1.8, 2.9)], 0.60, 0.97),
            ("07", [(2.5, 4.0), (1.5, 3.6), (0.8, 4.4)], 0.15, 0.55),
            ("07", [(-2.0, 3.2), (-1.0, 3.8), (0.2, 4.6), (1.4, 5.0)], 0.40, 0.88))


def _profile(u):
    """Distance traveled (0..1) at time u (0..1): accelerates in the first 20%, constant, brakes in the last 20%."""
    a = 0.2
    vmax = 1 / (1 - a)
    if u <= a:
        return vmax * u * u / (2 * a)
    if u >= 1 - a:
        w = 1 - u
        return 1 - vmax * w * w / (2 * a)
    return vmax * (u - a / 2)


def rats(tl, ground_z, length=0.7):
    """Quaternius Rat: Idle standing, then Run along the same path as the old mammal (smooth curve, turns toward
    the movement). The Run time follows the distance traveled: the step matches the speed,
    including when accelerating; the Run strip comes in over the Idle according to speed."""
    out = []
    for k, (sid, pts, u0, u1) in enumerate(RAT_RUNS):
        r = rigs.spawn("rat", f"Shrew{k}", length=length)
        rigs.paint(r, RAT_COLORS)
        curve, total = rigs.smooth_path(pts)
        a, b = tl.at(sid) - 2, tl.at(sid, 1.0) + 2
        g0, g1 = tl.at(sid, u0), tl.at(sid, u1)
        frames = list(range(a, b + 1))
        dist = [total * _profile(min(max((f - g0) / (g1 - g0), 0.0), 1.0)) for f in frames]
        pos, head = [], []
        for d in dist:
            p, h = rigs.along(curve, total, d)
            pos.append(Vector((p.x, p.y, ground_z(p.x, p.y))))
            head.append(h)
        rigs.key_root(r, frames, pos, head)
        rigs.loop(r, "Idle", a, b, phase=0.3 * k)
        per_action_frame = rigs.planted_speed(r, "Run", ["FrontFoot.L", "BackFoot.L"]) * r.scale
        a0 = r.t.actions["Run"].frame_range[0]
        times, t = [], a0
        peak = max(dist[i + 1] - dist[i] for i in range(len(dist) - 1))
        weight = []
        for i, d in enumerate(dist):
            step = dist[i] - dist[i - 1] if i else 0.0
            t += step / per_action_frame
            times.append(t)
            weight.append(min(step / (0.35 * peak), 1.0))
        rigs.timed(r, "Run", frames, times, influence=weight)
        out.append((sid, r))
    return out


# ---------- scene 08: people ----------

def _spear(name):
    wood = rigs.flat_mat("#5A4632")
    stone = rigs.flat_mat("#5E5A52")
    shaft = kit._prism_geo(5, 0.022, 0.018, 2.0, oz=-0.8)
    tip = kit._gem_geo(0.05, oz=1.27, stretch=1.9)
    v, f, owner = kit.merge(shaft, tip)
    return kit.mesh_object(name, v, f, [wood, stone], face_mats=owner)


def _hold(rig, bone, obj, frame, lean_deg):
    """Attaches the spear to the hand bone (child of the bone: follows the hand in everything), upright and leaning forward,
    passing through the palm at the reference frame."""
    scene = bpy.context.scene
    scene.frame_set(frame)
    pb = rig.arm.pose.bones[bone]
    tail = rig.arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    grip = rig.arm.matrix_world @ pb.tail
    heading = rig.root.matrix_world.to_euler().z - math.pi / 2
    fwd = Vector((math.cos(heading), math.sin(heading), 0))
    up = (Vector((0, 0, 1)) * math.cos(math.radians(lean_deg)) + fwd * math.sin(math.radians(lean_deg))).normalized()
    world = Matrix.Translation(grip) @ up.to_track_quat("Z", "Y").to_matrix().to_4x4()
    obj.parent = rig.arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = tail.inverted() @ world


def people(tl, rnd, ground_z, speed=1.25):
    """Five Homo sapiens from 300,000 years ago (Man and Woman Casual dressed by caveman.dress) walking away
    along +y, two with spears.
    The Walk time follows the distance (foot planted at the group's speed). The rnd draws repeat those of the old
    group, in the same order (the city of scene 09 uses the same generator afterward)."""
    a, b = tl.at("08") - 2, tl.at("08", 1.0) + 2
    frames = list(range(a, b + 1))
    out = []
    for k in range(5):
        x, y = rnd.uniform(-1.8, 1.8), 5 + k * 1.6 + rnd.uniform(-0.4, 0.4)
        skin, hide = rnd.choice(SKINS), rnd.choice(HIDES)
        size, phase = rnd.uniform(0.98, 1.12), rnd.random()
        woman = k in (1, 3)
        r = rigs.spawn("woman" if woman else "man", f"Walker{k}", height=(1.58 if woman else 1.66) * size)
        caveman.dress(r, dict(LOOKS[k], skin=skin, hide=hide, seed=11 + 7 * k))
        pos = [Vector((x, y + speed * (f - tl.at("08")) / 30, 0.0)) for f in frames]
        for p in pos:
            p.z = ground_z(p.x, p.y)
        rigs.key_root(r, frames, pos, [math.pi / 2] * len(frames))
        per_action_frame = rigs.planted_speed(r, "Walk", ["Foot.L", "Foot.R"]) * r.scale
        a0, a1 = r.t.actions["Walk"].frame_range
        start = a0 + phase * (a1 - a0)
        rigs.timed(r, "Walk", frames, [start + speed / 30 * (f - a) / per_action_frame for f in frames])
        if k in (0, 4):
            spear = _spear(f"Walker{k}Spear")
            _hold(r, "Palm.R", spear, tl.at("08", 0.5), 10.0)
        out.append(r)
    return out


# ---------- scene 05: animals on the globes ----------

def _on_globe(rig, plate, lat, lon, radius, heading):
    """Standing on the plate (spins with it), head pointing out of the globe."""
    from globe import to_vec
    n = to_vec(lat, lon)
    rig.root.parent = plate
    rig.root.location = tuple(n * (radius + 0.05))
    rig.root.rotation_mode = "QUATERNION"
    rig.root.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(n) @ Quaternion((0, 0, 1), heading + math.pi / 2)


def globe_animals(pan, mod, tl, radius):
    """Pangaea: the same Apatosaurus repeated three times; today: a different animal on each continent (fox in
    Africa, T-Rex in North America, rat in South America). All in Idle (alive, not walking in place)."""
    a, b = tl.at("05") - 2, tl.at("05", 1.0) + 2
    out = []
    for k, (lat, lon, h) in enumerate(((38, -40, 0.4), (-32, -48, 2.2), (6, -14, 1.3))):
        r = apatosaurus(f"PanDino{k}", 5.8, APATO_TINTS[k])
        _on_globe(r, pan.plates["Pangaea"], lat, lon, radius, h)
        out.append(r)
    for key, name, plate, (lat, lon), length, h in (
            ("fox", "ModFox", "Africa", (12, -4), 4.2, 0.6), ("trex", "ModTRex", "NorthAmerica", (44, -78), 5.0, 2.0),
            ("rat", "ModRat", "SouthAmerica", (-28, -60), 4.0, 1.0)):
        r = rigs.spawn(key, name, length=length)
        if key == "rat":
            rigs.paint(r, RAT_COLORS)
        _on_globe(r, mod.plates[plate], lat, lon, radius, h)
        out.append(r)
    for k, r in enumerate(out):
        rigs.loop(r, "Idle", a, b, phase=0.23 * k)
    return out
