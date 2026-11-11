"""Rigged CC0 assets (Quaternius) in the sets: import once, copy per character, play the asset's actions
on the NLA, add a pose layer (COMBINE) and match the stride to the speed (animated strip time).

Sources and licenses (all CC0 1.0, commercial use without attribution; SOURCE.txt in each assets/ folder):
- Apatosaurus, T-Rex: Quaternius, "Animated LowPoly Dinosaurs" (Dec 2018), https://quaternius.com/packs/animateddinosaurs.html
- Rat, Fox: Quaternius via Poly Pizza, https://poly.pizza/m/iltq5bVNaV , https://poly.pizza/m/Bc97C66HKi
- Man, Woman Casual, Animated Human: Quaternius via Poly Pizza, https://poly.pizza/m/HMnuH5geEG ,
  https://poly.pizza/m/jpKRgGDxhk , https://poly.pizza/m/c3Ibh9I3udk
- Horse: Quaternius via Poly Pizza, https://poly.pizza/m/qvTrSG9pZF (technology-disappeared, 2026-10-22)
Research: docs/blender/modeling.md (import pitfalls and measured speeds).

The downloaded files are data: we only import mesh, bones and actions (no script inside them runs).
"""

import math
from pathlib import Path
from types import SimpleNamespace

import bpy
import bpy_extras.anim_utils as au
from mathutils import Matrix, Quaternion, Vector

import kit

ASSETS = Path(__file__).resolve().parents[2] / "assets"
SCENE_FPS = 30
ASSET_FPS = 24                     # all the Quaternius actions were made at 24 frames/s
LINEAR = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value

DINO_DIR = "quaternius/animated-dinosaurs/Dinosaur Animated Pack - Dec 2018/FBX"
SPECS = {
    "apatosaurus": f"{DINO_DIR}/Apatosaurus.fbx",
    "trex": f"{DINO_DIR}/Trex.fbx",
    "rat": "polypizza/quaternius-animals/Rat.glb",
    "fox": "polypizza/quaternius-animals/Fox.glb",
    "man": "polypizza/quaternius-people/Man.glb",
    "woman": "polypizza/quaternius-people/WomanCasual.glb",
    "human": "polypizza/quaternius-people/AnimatedHuman.glb",
    "horse": "polypizza/quaternius-horse/Horse.glb",
}
_templates = {}
_mats = {}


# ---------- import ----------

def _import(path):
    """Imports an FBX/glTF without touching the scene fps or frame range; returns new objects and actions."""
    scene = bpy.context.scene
    keep = (scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end, scene.frame_current)
    objs, acts = set(bpy.data.objects), set(bpy.data.actions)
    if path.suffix.lower() in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False)
    scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end = keep[:4]
    scene.frame_current = keep[4]
    return [o for o in bpy.data.objects if o not in objs], [a for a in bpy.data.actions if a not in acts]


def _short(action_name):
    """'Armature|Armature|Apatosaurus_Walk' -> 'Walk'; 'RatArmature|Rat_Run' -> 'Run'; 'HumanArmature|Man_Walk'
    -> 'Walk'. glTF actions without '|' are copies of the NLA tracks: they are left out."""
    if "|" not in action_name:
        return None
    last = action_name.split("|")[-1]
    return last.split("_", 1)[1] if "_" in last and last.split("_")[0] in (
        "Apatosaurus", "TRex", "Rat", "Man", "Female", "Stegosaurus") else last


def _fcurves(action):
    return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


def _clean_action(action):
    """Removes the object's own curves (armature location/rotation/scale): they would fight the position and
    scale the set gives. Only the bone curves stay."""
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in [fc for fc in bag.fcurves if not fc.data_path.startswith("pose.bones")]:
                    bag.fcurves.remove(fc)


def _mirror_missing(action, bone_r="UpperArm.R", bone_l="UpperArm.L"):
    """The WomanCasual Idle action (Quaternius) has no curve for UpperArm.R: the right arm stays in the
    rest (T) pose, always open (bug seen 2026-10-23). Creates the curve by mirroring the left arm's
    (w, x, -y, -z, with w > 0 so it interpolates without flipping sign)."""
    bags = [bag for layer in action.layers for strip in layer.strips for bag in strip.channelbags]
    have = lambda b: any(f'"{b}"' in fc.data_path and fc.data_path.endswith("rotation_quaternion")
                         for bag in bags for fc in bag.fcurves)
    if have(bone_r) or not have(bone_l):
        return False
    bag = bags[0]
    src = {fc.array_index: fc for bk in bags for fc in bk.fcurves
           if f'"{bone_l}"' in fc.data_path and fc.data_path.endswith("rotation_quaternion")}
    frames = [kp.co[0] for kp in src[0].keyframe_points]
    dp = f'pose.bones["{bone_r}"].rotation_quaternion'
    new = {i: bag.fcurves.new(dp, index=i) for i in range(4)}
    for f in frames:
        q = [src[i].evaluate(f) for i in range(4)]
        if q[0] < 0:
            q = [-v for v in q]
        q = [q[0], q[1], -q[2], -q[3]]
        for i in range(4):
            new[i].keyframe_points.insert(f, q[i], options={"FAST"}).interpolation = "LINEAR"
    for fc in new.values():
        fc.update()
    return True


def template(key):
    """Imports the asset once (hidden): armature, meshes with the Armature modifier and the actions by short
    name. Removes the 'RootNode' empty, the bone-display 'Icosphere' and the glTF '*_end' empties."""
    if key in _templates:
        return _templates[key]
    new, acts = _import(ASSETS / SPECS[key])
    arm = next(o for o in new if o.type == "ARMATURE")
    meshes = [o for o in new if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    world = arm.matrix_world.copy()
    for o in new:
        if o is not arm and o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    arm.parent = None
    arm.matrix_world = world
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"           # the action curves are rotation_quaternion
    actions = {}
    for a in acts:
        _clean_action(a)
        if key == "woman" and a.name.endswith("Idle"):
            _mirror_missing(a)
        name = _short(a.name)
        if name and name not in actions:
            actions[name] = a
    for m in {s.material for o in meshes for s in o.material_slots if s.material}:
        p = kit.principled(m) if m.node_tree else None
        if p is not None and not p.inputs["Alpha"].is_linked:
            p.inputs["Alpha"].default_value = 1.0  # 2018 FBX files arrive with Alpha 0 (invisible in Eevee)
    for o in (arm, *meshes):
        o.hide_render = True                      # the template stays hidden in the render; the copies show up
    # glTF: the Y-up -> Z-up conversion comes as an armature rotation; it stays, and everything else works in an
    # "upright" frame (world axes, no scale): z up, the animal facing -y.
    t = SimpleNamespace(key=key, arm=arm, meshes=meshes, actions=actions, base_scale=arm.matrix_world.to_scale().x,
                        rot=arm.matrix_world.to_quaternion())
    t.box = _posed_box(t, "Walk" if "Walk" in actions else next(iter(actions)))
    _templates[key] = t
    return t


def _posed_box(t, action_key):
    """Box of the mesh posed at the action's first frame, in the upright frame (world axes, armature units)."""
    arm = t.arm
    ad = arm.animation_data_create()
    act = t.actions[action_key]
    ad.action = act
    ad.action_slot = act.slots[0]
    scene = bpy.context.scene
    keep = scene.frame_current
    scene.frame_set(int(act.frame_range[0]))
    dg = bpy.context.evaluated_depsgraph_get()
    origin, s = arm.matrix_world.translation.copy(), t.base_scale
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in t.meshes:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        for v in me.vertices:
            p = (oe.matrix_world @ v.co - origin) / s
            lo, hi = Vector(map(min, lo, p)), Vector(map(max, hi, p))
        oe.to_mesh_clear()
    ad.action = None
    scene.frame_set(keep)
    return SimpleNamespace(lo=lo, hi=hi, size=hi - lo)


# ---------- character ----------

def spawn(key, name, length=None, height=None, location=(0, 0, 0), heading=0.0):
    """Copy of the asset with its own root (an empty the set animates). length = length along y (animal),
    height = height (people). heading in radians in the set's convention (0 = facing +x): the
    Quaternius assets face -y, so the root rotates heading + 90°. The mesh is shared (light copy)."""
    t = template(key)
    k = length / t.box.size.y if length else height / t.box.size.z if height else 1.0
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.3
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = (0, 0, heading + math.pi / 2)
    arm = t.arm.copy()
    arm.name = f"{name}Rig"
    bpy.context.collection.objects.link(arm)
    arm.parent = root
    arm.matrix_parent_inverse = Matrix.Identity(4)
    arm.rotation_mode = "QUATERNION"
    arm.location, arm.rotation_quaternion = (0, 0, -t.box.lo.z * k), t.rot
    arm.scale = (k,) * 3
    arm.animation_data_clear()
    meshes = []
    for m in t.meshes:
        c = m.copy()
        c.name = f"{name}Body"
        bpy.context.collection.objects.link(c)
        c.parent = arm
        for mod in c.modifiers:
            if mod.type == "ARMATURE":
                mod.object = arm
        meshes.append(c)
    for o in (arm, *meshes):
        o.hide_render = False
    return SimpleNamespace(key=key, name=name, root=root, arm=arm, meshes=meshes, t=t, scale=k)


def flat_mat(color, rough=0.95):
    """Flat palette material, no specular shine (in Standard the reflection blows out)."""
    if color not in _mats:
        m = kit.flat(f"Rig{color}", color, rough=rough)
        kit.principled(m).inputs["Specular IOR Level"].default_value = 0.0
        _mats[color] = m
    return _mats[color]


def paint(rig, colors):
    """Swaps the asset materials for the palette ones, per character (slot linked to the object).
    colors: {original material name without suffix: '#hex'}."""
    for o in rig.meshes:
        for slot in o.material_slots:
            base = slot.material.name.split(".")[0] if slot.material else None
            if base in colors:
                slot.link = "OBJECT"
                slot.material = flat_mat(colors[base])


def all_objects(rig):
    return [rig.root, *rig.root.children_recursive]


# ---------- NLA ----------

def strip_scale(rate=1.0):
    """Strip scale to play the 24 fps action in the 30 fps scene, times the requested speed."""
    return SCENE_FPS / ASSET_FPS / rate


def loop(rig, action_key, start, end, rate=1.0, phase=0.0, blend_in=0, blend_out=0, extend="HOLD"):
    """Cycle repeated on its own NLA track from start to end. phase (0..1) shifts the cycle (a herd out of
    sync). Returns the strip; the action frame at f is a0 + ((f - strip.frame_start) / scale) mod L."""
    act = rig.t.actions[action_key]
    a0, a1 = act.frame_range
    s = strip_scale(rate)
    first = int(math.floor(start - phase * (a1 - a0) * s)) - 1
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = f"{action_key}{len(ad.nla_tracks)}"
    st = track.strips.new(f"{action_key}", first, act)
    if st.action_slot is None:
        st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.scale = s
    st.repeat = max(1.0, (end - first) / ((a1 - a0) * s) + 1.0)
    st.blend_in, st.blend_out = blend_in, blend_out
    st.extrapolation = extend
    return st


def action_frame(st, f):
    """Action frame that the strip (with repeat) plays at scene frame f."""
    a0, a1 = st.action_frame_start, st.action_frame_end
    return a0 + math.fmod((f - st.frame_start) / st.scale, a1 - a0)


def timed(rig, action_key, frames, times, influence=None):
    """NLA track with the action time given frame by frame (times[i] = action frame at frames[i], grows
    without limit and wraps around the cycle). This is what matches the stride to the body's speed, including accelerating.
    influence: list of the same length (0..1) to blend in and out over the lower track."""
    act = rig.t.actions[action_key]
    a0, a1 = act.frame_range
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = f"{action_key}T{len(ad.nla_tracks)}"
    st = track.strips.new(f"{action_key}", int(frames[0]), act)
    if st.action_slot is None:
        st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.repeat = max(1.0, (frames[-1] - frames[0]) / (a1 - a0) + 1.0)
    st.extrapolation = "HOLD_FORWARD" if influence is None else "NOTHING"
    st.use_animated_time = True
    st.use_animated_time_cyclic = True
    _write(st.fcurves.find("strip_time"), frames, times)
    if influence is not None:
        st.use_animated_influence = True
        _write(st.fcurves.find("influence"), frames, influence)
    return st


def _write(fc, frames, values):
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    fc.keyframe_points.foreach_set("co", [c for fv in zip(frames, values) for c in fv])
    fc.keyframe_points.foreach_set("interpolation", [LINEAR] * len(frames))
    fc.update()


# ---------- added pose layer (COMBINE) ----------

def bone_delta(rig, bone, axis, degrees):
    """Rotation about an axis of the upright frame (x = side, z = up), written in the bone's local rest
    space (the space in which COMBINE adds the rotation)."""
    rest = rig.arm.data.bones[bone].matrix_local.to_quaternion()
    axis_arm = rig.t.rot.inverted() @ Vector(axis).normalized()
    q = Quaternion(axis_arm, math.radians(degrees))
    return rest.inverted() @ q @ rest


def pose_layer(rig, frames, poses):
    """Layer added on top of the cycle: top NLA track in COMBINE (quaternions multiply). poses(f) returns
    {bone: Quaternion} for each frame in frames; LINEAR keys on every frame. It lives in the NLA (not as the
    active action) so the set's on/off switch (hide_render) can have its own action."""
    act = bpy.data.actions.new(f"{rig.name}Pose")
    slot = act.slots.new(id_type="OBJECT", name=rig.arm.name)
    bag = au.action_ensure_channelbag_for_slot(act, slot)
    table = [poses(f) for f in frames]
    for bone in table[0]:
        path = f'pose.bones["{bone}"].rotation_quaternion'
        for i in range(4):
            fc = bag.fcurves.new(path, index=i, group_name=bone)
            fc.keyframe_points.add(len(frames))
            fc.keyframe_points.foreach_set("co", [c for f, q in zip(frames, table) for c in (f, q[bone][i])])
            fc.keyframe_points.foreach_set("interpolation", [LINEAR] * len(frames))
            fc.update()
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = "Pose"
    st = track.strips.new("Pose", int(frames[0]), act)
    st.action_slot = slot
    st.use_auto_blend = False
    st.blend_type = "COMBINE"
    st.extrapolation = "HOLD"
    return act


# ---------- trajectory ----------

def key_root(rig, frames, positions, headings):
    """Walking root: position and heading (radians, 0 = +x) on every frame, LINEAR (no Bezier overshoot).
    The heading is unwrapped (no 360° jump)."""
    root = rig.root
    prev = None
    for f, p, h in zip(frames, positions, headings):
        z = h + math.pi / 2
        if prev is not None:
            z = prev + (z - prev + math.pi) % (2 * math.pi) - math.pi
        prev = z
        root.location = tuple(p)
        root.keyframe_insert("location", frame=f)
        root.rotation_euler = (0, 0, z)
        root.keyframe_insert("rotation_euler", frame=f)
    ad = root.animation_data
    for fc in _fcurves(ad.action):
        if fc.data_path in ("location", "rotation_euler"):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def smooth_path(points, samples=200):
    """Catmull-Rom curve through the (x, y) points, resampled by length: returns (points, length)."""
    pts = [Vector((p[0], p[1], 0.0)) for p in points]
    ext = [pts[0] * 2 - pts[1], *pts, pts[-1] * 2 - pts[-2]]
    dense = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(40):
            t = k / 40
            dense.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    dense.append(pts[-1])
    acc = [0.0]
    for a, b in zip(dense, dense[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    out, j = [], 0
    for k in range(samples + 1):
        d = total * k / samples
        while j < len(acc) - 2 and acc[j + 1] < d:
            j += 1
        u = (d - acc[j]) / max(acc[j + 1] - acc[j], 1e-9)
        out.append(dense[j].lerp(dense[j + 1], u))
    return out, total


def along(curve, total, d):
    """Point and heading (radians) at d meters from the start of the resampled curve."""
    n = len(curve) - 1
    x = min(max(d / total, 0.0), 1.0) * n
    i = min(int(x), n - 1)
    p = curve[i].lerp(curve[i + 1], x - i)
    a, b = curve[max(i - 3, 0)], curve[min(i + 4, n)]
    return p, math.atan2(b.y - a.y, b.x - a.x)


def planted_speed(rig, action_key, feet):
    """Speed of the planted foot (armature units per action frame), averaged over the given feet: this is the
    speed the body must travel so the foot does not skate."""
    t = rig.t
    table = foot_table(t, action_key, feet)
    speeds = []
    for pts in table.values():
        zs = [p.z for p in pts]
        lo, hi = min(zs), max(zs)
        moves = [abs(pts[i + 1].y - pts[i].y) for i in range(len(pts) - 1) if zs[i] < lo + 0.06 * (hi - lo)]
        speeds.append(sum(moves) / max(len(moves), 1))
    return sum(speeds) / len(speeds)


_tables = {}


def foot_table(t, action_key, feet):
    """Head position of each upright bone at every whole frame of the action, in the upright frame (no scale)."""
    k = (t.key, action_key, tuple(feet))
    if k in _tables:
        return _tables[k]
    arm = t.arm
    ad = arm.animation_data_create()
    act = t.actions[action_key]
    ad.action = act
    ad.action_slot = act.slots[0]
    scene = bpy.context.scene
    keep = scene.frame_current
    a0, a1 = (int(x) for x in act.frame_range)
    out = {b: [] for b in feet}
    for f in range(a0, a1 + 1):
        scene.frame_set(f)
        for b in feet:
            out[b].append(t.rot @ arm.pose.bones[b].head)
    ad.action = None
    scene.frame_set(keep)
    _tables[k] = out
    return out
