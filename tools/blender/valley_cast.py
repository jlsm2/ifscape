"""People of the valley: instanced crowd (low-poly capsules, 1 mesh per clothing color), the couple (Quaternius Man and
WomanCasual, CC0, with Idle/Walk), baby and children (small capsules). Proportion: man 1.75 m, woman 1.62 m,
8-year-old child ~1.25 m, baby ~0.5 m (CDC growth charts).
"""

import math
import random

import bpy
from mathutils import Vector

import kit
import rigs
import town_cast as tc
import valley_lib as vl

# Village clothes (earth tones + the blue of the palette), no pure white or saturated color; skin in 4 tones; hair in 5.
SHIRT = ["#8C3B30", "#3F6FA8", "#B08A3A", "#4C7A52", "#7A8496", "#6A4A7A", "#C9BFA8", "#2E3A52", "#8A5A32",
         "#4A6A78", "#A0643A", "#5A6A3A"]
PANT = ["#2A3446", "#4A4038", "#3A3226", "#5A4A36", "#3A4A3A"]
SKIN = ["#C8916A", "#8D5A3C", "#E0B08A", "#A8724E"]
HAIR = ["#2A1E16", "#4A3424", "#8A6A4A", "#1A1A1A", "#9A8060"]

# Static poses taken from the asset's own actions (action, fraction of the cycle): mid-shot and background.
POSES = {"idle": ("Idle", 0.0), "rest": ("Idle", 0.6), "walk": ("Walk", 0.3), "hands": ("Clapping", 0.0),
         "sit": ("Sitting", 0.6)}
STAND = ("idle", "rest", "hands", "rest")
_baked, _outfits = {}, {}


def _bake(key, pose, kid=False):
    """Man/WomanCasual mesh (CC0, Quaternius) frozen in a pose: 1.0 m tall standing, feet at z 0,
    front toward +y. kid: head 22% larger (proportion of a 6 to 10 year old child), the rest the same."""
    k = (key, pose, kid)
    if k in _baked:
        return _baked[k]
    act_name, frac = POSES[pose]
    r = rigs.spawn(key, f"Bake{key}{pose}", height=1.0, location=(0, 0, 0), heading=math.pi / 2)
    act = r.t.actions[act_name]
    a0, a1 = act.frame_range
    ad = r.arm.animation_data_create()
    st = ad.nla_tracks.new().strips.new(act_name, 1, act)
    st.action_slot = act.slots[0]
    st.action_frame_start = a0 + frac * (a1 - a0)
    st.action_frame_end = st.action_frame_start + 1
    scene = bpy.context.scene
    keep = scene.frame_current
    scene.frame_set(1)
    dg = bpy.context.evaluated_depsgraph_get()
    m = r.meshes[0]
    me = bpy.data.meshes.new_from_object(m.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    me.transform(m.matrix_world)
    if kid:
        for v in me.vertices:
            z = v.co.z
            u = min(max((z - 0.835) / 0.035, 0.0), 1.0)
            s = 1.0 + 0.22 * u * u * (3 - 2 * u)
            v.co.x *= s
            v.co.y = 0.0 + (v.co.y - 0.0) * s
            v.co.z = 0.835 + (z - 0.835) * s if z > 0.835 else z
    for p in me.polygons:
        p.use_smooth = False
    me.name = f"Baked{key}{pose}{'Kid' if kid else ''}"
    me.use_fake_user = True
    for o in rigs.all_objects(r):
        bpy.data.objects.remove(o, do_unlink=True)
    scene.frame_set(keep)
    _baked[k] = me
    return me


def outfit(k, key):
    """Colors of a person (clothes, trousers, skin, hair) from index k."""
    hair = HAIR[(k * 7) % len(HAIR)]
    return {"Shirt": SHIRT[k % len(SHIRT)], "Pants": PANT[(k * 3) % len(PANT)], "Skin": SKIN[(k * 5) % len(SKIN)],
            "Hair": hair, "HairBase": hair, "Eyes": "#1A1410", "Socks": PANT[(k * 3) % len(PANT)], "Shoes": "#2A2622"}


def person_mesh(key, pose, k, kid=False):
    """Frozen mesh + clothes k (copy of the mesh with the palette materials; cache per combination)."""
    ck = (key, pose, k % 24, kid)
    if ck not in _outfits:
        base = _bake(key, pose, kid)
        me = base.copy()
        me.name = f"{base.name}_{k % 24}"
        cols = outfit(k % 24, key)
        for i, m in enumerate(list(me.materials)):
            nm = m.name.split(".")[0] if m else None
            if nm in cols:
                me.materials[i] = rigs.flat_mat(cols[nm])
        _outfits[ck] = me
    return _outfits[ck]


def figure(name, x, y, heading, height=1.7, k=0, z=0.0, pose=None):
    """Mid-shot or background person (static posed mesh, front = local +y rotated by heading).
    Below 1.45 m becomes a child (proportionally bigger head)."""
    key = "woman" if k % 2 else "man"
    kid = height < 1.45
    pose = pose or (STAND[(k // 2) % 4] if not kid else ("idle", "rest")[(k // 2) % 2])
    me = person_mesh(key, pose, k, kid)
    s = height / (1.035 if kid else 1.0)
    return vl.obj_of(name, me, (x, y, z), (0, 0, heading), (s, s, s))


def crowd(prefix, spots, rnd, height=(1.55, 1.78), poses=None):
    """spots: list of (x, y). Returns the figures (each with angle, clothes and pose drawn at random)."""
    out = []
    for k, (x, y) in enumerate(spots):
        out.append(figure(f"{prefix}{k}", x, y, rnd.uniform(0, 6.28), rnd.uniform(*height), rnd.randrange(60),
                          pose=rnd.choice(poses) if poses else None))
    return out


def walkers(specs, f0, f1, rnd=None, z=0.0):
    """People really walking (rig with Walk and planted foot): specs = [(x, y, heading rad, speed m/s), ...].
    Returns the rigs."""
    import town_cast as tc_
    rnd = rnd or random.Random(1)
    out = []
    for i, (x, y, hd, sp) in enumerate(specs):
        key = "woman" if i % 2 else "man"
        r = rigs.spawn(key, f"Walker{i}", height=1.62 if key == "woman" else 1.74, location=(x, y, 0), heading=hd)
        rigs.paint(r, outfit(i * 5 + 3, key))
        frames = list(range(f0, f1 + 1))
        tc_.walk_line(r, frames, (x, y), hd, sp, phase=rnd.random(), z=z)
        out.append(r)
    return out


# ---------- o casal (assets) ----------

COUPLE = {"man": {"Shirt": "#4F7DB5", "Pants": "#3A3226", "Skin": "#C8916A", "Hair": "#2A1E16", "HairBase": "#2A1E16",
                  "Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"},
          "woman": {"Shirt": "#E6D9B8", "Pants": "#5A4A36", "Skin": "#C8916A", "Hair": "#4A3424", "HairBase": "#4A3424",
                    "Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"}}


def adult(key, name, x, y, heading, frames, k=0):
    """Man or WomanCasual with Idle in a cycle; heading in radians (0 = looks at +x). Same clothes and skin in all
    scenes (COUPLE); k only offsets the Idle phase."""
    height = 1.75 if key == "man" else 1.62
    r = rigs.spawn(key, name, height=height, location=(x, y, 0.0), heading=heading)
    rigs.paint(r, COUPLE[key])
    rigs.loop(r, "Idle", 1, frames, rate=1.0, phase=(k * 0.37) % 1.0)
    return r


def adult_sit(key, name, x, y, heading, frames):
    """Seated on a 45 cm bench (Sitting of the asset, stretch 30..190, without the sit-down part); same clothes as the couple."""
    height = 1.75 if key == "man" else 1.62
    r = rigs.spawn(key, name, height=height, location=(x, y, 0.0), heading=heading)
    rigs.paint(r, COUPLE[key])
    tc.segment(r, "Sitting", 1, frames, 30, 190)
    return r


def sway(figs, f0, f1, rnd, step=24):
    """Slight sway in place (+-5 degree turn and 1 cm rise), no walking: mid-shot figure."""
    for o in figs:
        z0, r0 = o.location.z, o.rotation_euler.z
        ph = rnd.uniform(0, 6.28)
        n = int((f1 - f0) / step) + 1
        for i in range(n + 1):
            f = f0 + i * step
            o.rotation_euler.z = r0 + math.radians(5) * math.sin(ph + i * 0.9)
            o.location.z = z0 + 0.012 * abs(math.sin(ph + i * 1.3))
            o.keyframe_insert("rotation_euler", index=2, frame=f)
            o.keyframe_insert("location", index=2, frame=f)
        vl.linear(o)


def step_to(r, f0, f1, start, heading, speed=1.2):
    """Walks from f0 to f1 in a straight line (Walk with planted foot) and stays still after; before f0 stays at 'start'."""
    frames = list(range(f0, f1 + 1))
    d = Vector((math.cos(heading), math.sin(heading), 0.0))
    pos = [Vector((*start, 0.0)) + d * speed * (f - f0) / 30 for f in frames]
    rigs.key_root(r, frames, pos, [heading] * len(frames))
    per = rigs.planted_speed(r, "Walk", ["Foot.L", "Foot.R"]) * r.scale
    a0, a1 = r.t.actions["Walk"].frame_range
    infl = [min(1.0, (f - f0) / 4, (f1 - f) / 4) for f in frames]
    rigs.timed(r, "Walk", frames, [a0 + speed / 30 * (f - f0) / per for f in frames], influence=infl)


def turn_to(r, f0, f1, heading, shuffle=True):
    """Turns in place from the current heading to the new one: turn with acceleration and braking (key on every frame) and, with
    shuffle, two little steps of the Walk over the Idle (influence rises and falls): the feet follow the turn."""
    cur = r.root.rotation_euler.z
    tgt = heading + math.pi / 2
    tgt = cur + (tgt - cur + math.pi) % (2 * math.pi) - math.pi
    frames = list(range(f0, f1 + 1))
    for f in frames:
        u = (f - f0) / (f1 - f0)
        r.root.rotation_euler.z = cur + (tgt - cur) * u * u * (3 - 2 * u)
        r.root.keyframe_insert("rotation_euler", index=2, frame=f)
    vl.linear(r.root)
    if shuffle:
        a0, a1 = r.t.actions["Walk"].frame_range
        n = len(frames) - 1
        rigs.timed(r, "Walk", frames, [a0 + (a1 - a0) * 0.9 * i / n for i in range(n + 1)],
                   influence=[0.55 * math.sin(math.pi * i / n) for i in range(n + 1)])


def baby(parent_rig, pos=(-0.07, -0.24, 0.68)):
    """Baby of ~0.5 m (CDC) wrapped in a cloth, lying in the mother's lap, head to her left (local +x of the baby):
    spindle body (loft), cloth hood around the face, head, two little sleeved arms with tiny hands on top of the
    cloth. Child of the mother's root. Returns (body, glow light, right arm with pivot at the shoulder, list of parts)."""
    cloth = vl.mat("Swaddle", "#D9CDB0")
    fold = vl.mat("SwaddleFold", "#B8A988")
    skin = vl.mat("BabySkin", "#D8A47E")
    rings = []
    prof = [(-0.21, 0.03), (-0.19, 0.06), (-0.13, 0.08), (-0.04, 0.088), (0.04, 0.085), (0.09, 0.07)]
    for x, r in prof:
        rings.append([(x, r * math.cos(2 * math.pi * i / 8), 0.85 * r * math.sin(2 * math.pi * i / 8)) for i in range(8)])
    body = vl.obj_of("Baby", vl.mesh_from_geo("BabyBody", kit.loft_geo(rings), cloth), (0, 0, 0))
    kit.fix_normals(body)
    # hood: half-shell of cloth behind and below the head; the face stays up (local +z)
    hood = vl.obj_of("BabyHood", vl.mesh_from_geo("BabyHood", kit._ico_geo(0.078, (0.168, 0.012, -0.028), (1.0, 1.05, 0.75)),
                                                  fold), (0, 0, 0))
    hood.parent = body
    head = vl.obj_of("BabyHead", vl.mesh_from_geo("BabyHead", kit._ico_geo(0.068, (0.15, -0.012, 0.045)), skin), (0, 0, 0))
    head.parent = body
    arms = []
    for side in (1, -1):
        sv, sf = kit.tube_geo([(0, 0, 0), (0.025, -0.02 * side, 0.012), (0.048, -0.03 * side, 0.016)],
                              [0.022, 0.02, 0.018], n=6)
        a = vl.obj_of(f"BabyArm{side}", vl.mesh_from_geo(f"BabyArm{side}", (sv, sf), cloth), (0.02, 0.055 * side, 0.055))
        kit.fix_normals(a)
        hv, hf = kit._ico_geo(0.022, (0.062, -0.034 * side, 0.018))
        h = vl.obj_of(f"BabyHand{side}", vl.mesh_from_geo(f"BabyHand{side}", (hv, hf), skin), (0, 0, 0))
        h.parent = a
        a.parent = body
        arms.append(a)
    ld = bpy.data.lights.new("BabyGlow", "POINT")
    ld.color, ld.energy, ld.shadow_soft_size, ld.use_shadow = (1.0, 0.65, 0.25), 0.0, 0.3, False
    lo = bpy.data.objects.new("BabyGlow", ld)
    bpy.context.collection.objects.link(lo)
    lo.parent = body
    lo.location = (0.0, 0.0, 0.35)
    body.parent = parent_rig.root
    body.location = pos
    body.rotation_euler = (math.radians(-25), math.radians(-14), 0)
    for o in [body, *body.children_recursive]:
        o.visible_shadow = o.type != "LIGHT"
    return body, ld, arms[0], [body, *body.children_recursive]


def hold_baby(wom, baby_body):
    """Mother's arms by IK: left hand under the baby's head, right under the legs; elbows out and back."""
    import town_cast as tc_
    tl_, pl = tc_.hold(wom, "L", baby_body, (0.10, 0.08, -0.06), (0.45, 0.35, 0.55))
    tr_, pr = tc_.hold(wom, "R", baby_body, (-0.12, 0.08, -0.07), (-0.45, 0.35, 0.55))
    return [tl_, pl, tr_, pr]


def touch_baby(man, baby_body, lap=(0.21, 0.14, 0.5)):
    """The father (seated to the mother's right) rests his left hand on his knee (target on the father's root, in 'lap'): arm
    close to the body, hand visible. (Trying to reach the baby's feet gave an arm stretched behind the torso.)"""
    import town_cast as tc_
    t, p = tc_.hold(man, "L", man.root, lap, (0.45, -0.25, 0.9))
    return [t, p]
