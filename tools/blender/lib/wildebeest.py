"""Low-poly blue wildebeest (Connochaetes taurinus) with rig, adapted from the Quaternius cow (same bones and actions).

SOURCE: Quaternius, "LowPoly Animated Farm Animal Pack" (Cow.fbx), CC0 1.0 (assets/quaternius/farm-animals/SOURCE.txt;
see lib/cow_quaternius.py). The mesh is an edited COPY (the cow's stays intact) + procedural horns, mane and beard
attached to the Head and Neck bones.
Proportions (https://en.wikipedia.org/wiki/Blue_wildebeest; direction.md §4): withers 1.15–1.45 m, body 1.7–2.4 m;
tall, deep front, back sloping down to the narrow rump, long square head, horns that come out to the
sides, drop and hook upward, black upright mane, hanging black beard, long black tail, dark vertical stripes
on the neck and shoulders. Palette (art.md §2): back #5A5E66, stripes #3E4248, mane/beard/face #1E1E22.
Low-poly references: Quaternius Animated Animal Pack (antelopes), Poly Pizza "Wildebeest" (silhouette).

What sets it apart from the cow in silhouette (risk R3): withers ~25% above the rump, thin legs, long low head,
hooked horns to the sides, black beard and mane; no udder or patches.

Usage: build(name, location, heading, length=2.5) -> rigs.py rig; graze(rig, f0, f1), walk/idle via rigs.loop.
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
import rigs
import cow_quaternius  # noqa: F401  (registers the "cow" SPEC)
from kit import lin

BODY, STRIPE, DARK, LEGS, HOOF = "#5A5E66", "#3E4248", "#1E1E22", "#4C5058", "#18181A"
_TEMPLATE = {}


def _smooth(a, b, x):
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def _body_mat():
    """Blue-gray with dark vertical stripes at the front (Generated coordinate = rest pose: the stripe does not
    slide when the bone bends)."""
    if "body" in _TEMPLATE:
        return _TEMPLATE["body"]
    mat = bpy.data.materials.new("GnuBody")
    if not mat.node_tree:
        mat.use_nodes = True
    n, L = mat.node_tree.nodes, mat.node_tree.links
    p = kit.principled(mat)
    p.inputs["Roughness"].default_value = 0.95
    p.inputs["Specular IOR Level"].default_value = 0.0
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Generated"], sep.inputs[0])
    # stripes: sine along the body (generated y: 0 = muzzle, 1 = tail), only on the front half and on top
    wv = n.new("ShaderNodeMath"); wv.operation = "MULTIPLY"
    L.new(sep.outputs["Y"], wv.inputs[0]); wv.inputs[1].default_value = 2 * math.pi * 26.0
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 6.0
    L.new(tc.outputs["Generated"], nz.inputs["Vector"])
    wob = n.new("ShaderNodeMath"); wob.operation = "MULTIPLY_ADD"
    L.new(nz.outputs["Fac"], wob.inputs[0]); wob.inputs[1].default_value = 2.5
    L.new(wv.outputs[0], wob.inputs[2])
    sn = n.new("ShaderNodeMath"); sn.operation = "SINE"
    L.new(wob.outputs[0], sn.inputs[0])
    st = n.new("ShaderNodeMapRange")
    st.inputs["From Min"].default_value, st.inputs["From Max"].default_value = 0.35, 0.75
    L.new(sn.outputs[0], st.inputs["Value"])
    front = n.new("ShaderNodeMapRange")
    front.inputs["From Min"].default_value, front.inputs["From Max"].default_value = 0.52, 0.4
    L.new(sep.outputs["Y"], front.inputs["Value"])
    high = n.new("ShaderNodeMapRange")
    high.inputs["From Min"].default_value, high.inputs["From Max"].default_value = 0.42, 0.62
    L.new(sep.outputs["Z"], high.inputs["Value"])
    m1 = n.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
    L.new(st.outputs["Result"], m1.inputs[0]); L.new(front.outputs["Result"], m1.inputs[1])
    m2 = n.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    L.new(m1.outputs[0], m2.inputs[0]); L.new(high.outputs["Result"], m2.inputs[1])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(m2.outputs[0], mix.inputs["Factor"])
    mix.inputs["A"].default_value = lin(BODY)
    mix.inputs["B"].default_value = lin(STRIPE)
    # belly and legs a shade darker (color shadow, not light)
    low = n.new("ShaderNodeMapRange")
    low.inputs["From Min"].default_value, low.inputs["From Max"].default_value = 0.3, 0.5
    low.inputs["To Min"].default_value, low.inputs["To Max"].default_value = 0.8, 1.0
    L.new(sep.outputs["Z"], low.inputs["Value"])
    hsv = n.new("ShaderNodeHueSaturation")
    L.new(mix.outputs["Result"], hsv.inputs["Color"])
    L.new(low.outputs["Result"], hsv.inputs["Value"])
    L.new(hsv.outputs["Color"], p.inputs["Base Color"])
    _TEMPLATE["body"] = mat
    return mat


def _bone_world(arm, bone):
    b = arm.data.bones[bone]
    return arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local


def _edit_mesh(src, arm):
    """Edited copy of the cow mesh (asset units; -y = front, z = up, ground at z ~0)."""
    me = src.data.copy()
    me.name = "GnuMesh"
    groups = {g.index: g.name for g in src.vertex_groups}
    hh, ht = _bone_world(arm, "Head")
    head_axis = (ht - hh).normalized()
    # udder (pink faces on the rear half): the vertices rise into the belly
    pink = {i for i, m in enumerate(src.data.materials) if m and m.name.split(".")[0] == "Pink"}
    udder = {vi for poly in src.data.polygons if poly.material_index in pink
             for vi in poly.vertices if src.data.vertices[vi].co.y > -1.0}
    for v in me.vertices:
        p = v.co.copy()
        w = {groups[g.group]: g.weight for g in v.groups}
        main = max(w, key=w.get) if w else ""
        legish = any(k in main for k in ("UpLeg", "LowLeg", "Foot"))
        headish = main in ("Head",)
        neckish = main in ("Neck",)
        if v.index in udder:
            p.z = max(p.z, 2.45)
            p.x *= 0.5
        if not legish and not headish and not neckish:
            # back: high withers (peak at y -1.6) ramping down to the low rump. Hump lower and wider
            # than in the 1st look-dev (0.85 / 1.5): that one read as a bison (hero review, 2026-10-24)
            hump = 0.55 * math.exp(-((p.y + 1.5) / 2.0) ** 2) + 0.4 * (1 - _smooth(-2.0, 1.2, p.y))
            prof = hump - 0.62 * _smooth(-0.2, 2.9, p.y)
            p.z += prof * _smooth(2.7, 3.8, p.z)
            # high belly (long leg showing: a deep body with a short leg read as a bison) and more
            # tucked up at the back
            p.z += 0.32 * _smooth(0.2, 2.2, p.y) * (1 - _smooth(2.1, 2.9, p.z))
            # narrow rump, broad chest
            p.x *= 1.0 - 0.24 * _smooth(0.4, 2.6, p.y)
            p.x *= 1.0 + 0.08 * (1 - _smooth(-2.4, -0.6, p.y))
        if not headish and not neckish and not any(k in main for k in ("LowLeg", "Foot", "Tail")):
            # belly and top of the thighs rise (less deep body, longer leg showing): a deep body
            # with a short leg read as a bison (hero review, 2026-10-24)
            p.z += 0.32 * _smooth(1.5, 2.3, p.z) * (1 - _smooth(2.6, 3.3, p.z))
        if neckish:
            p.z += 0.55 * _smooth(3.3, 4.3, p.z)       # neck comes out high from the hump
        if headish:
            d = p - hh
            along = d.dot(head_axis)
            p = p + head_axis * max(0.0, along) * 0.28  # long face
            p.x *= 1.0 + 0.14 * _smooth(0.6, 1.6, along)  # broad, square muzzle
        if legish:
            cx = 0.9 if p.x > 0 else -0.88
            p.x = cx + (p.x - cx) * 0.7
        v.co = p
    me.update()
    return me


def _part_obj(name, geo, mat, arm, bone):
    o = kit.mesh_object(name, geo[0], geo[1], [mat])
    for poly in o.data.polygons:
        poly.use_smooth = False
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = bone
    # geometry in asset coordinates: compensate for the bone tip matrix (parent BONE attaches at the tail)
    b = arm.data.bones[bone]
    m = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    o.matrix_parent_inverse = m.inverted()
    return o


def _horns_geo():
    """Hooked horns: they come out to the sides, drop and rise inward (tapering section)."""
    geos = []
    for s in (1, -1):
        pts = [(0.3 * s, -4.05, 4.95), (0.95 * s, -3.95, 5.0), (1.4 * s, -3.9, 4.7), (1.45 * s, -3.95, 5.25),
               (1.15 * s, -4.05, 5.65)]
        geos.append(kit.tube_geo(pts, [0.26, 0.22, 0.17, 0.11, 0.03], n=6))
    # horn bases (boss) on top of the head
    geos.append(kit._prism_geo(6, 0.3, 0.22, 0.2, oz=4.78, oy=-4.05, sx=1.4))
    v, f, _ = kit.merge(*geos)
    return v, f


def _mane_geo():
    """Upright mane along the neck (from the nape to the withers)."""
    pts = [(0.0, -4.0, 5.0), (0.0, -3.5, 4.85), (0.0, -3.0, 4.6), (0.0, -2.4, 4.35), (0.0, -1.8, 4.15)]
    rings = []
    for k, (x, y, z) in enumerate(pts):
        h = 0.62 - 0.07 * k
        z += 0.25 * min(k, 2) + (0.55 if k >= 3 else 0.0)
        rings.append([(x - 0.08, y, z - 0.15), (x + 0.08, y, z - 0.15), (x + 0.04, y, z + h), (x - 0.04, y, z + h)])
    return kit.loft_geo(rings)


def _beard_geo():
    """Black beard hanging under the neck and throat (wedge-shaped fringe)."""
    pts = [(-4.6, 3.75), (-4.1, 3.55), (-3.5, 3.35), (-2.9, 3.05), (-2.4, 2.85)]
    rings = []
    for k, (y, z) in enumerate(pts):
        drop = 0.85 + 0.15 * math.sin(k * 1.7)
        rings.append([(-0.12, y, z + 0.1), (0.12, y, z + 0.1), (0.06, y + 0.08, z - drop), (-0.06, y + 0.08, z - drop)])
    return kit.loft_geo(rings)


def _tail_tuft_geo():
    return kit.tube_geo([(0, 3.62, 2.6), (0, 3.62, 1.9), (0, 3.6, 1.15)], [0.1, 0.22, 0.05], n=6)


def template():
    """Hidden wildebeest template: cow armature (shared data) + edited mesh + parts. Registered in rigs
    under the key "gnu" (rigs.spawn('gnu', ...) copies it like any asset)."""
    if "gnu" in rigs._templates:
        return rigs._templates["gnu"]
    cow = rigs.template("cow")
    arm = cow.arm.copy()
    arm.name = "GnuTemplateRig"
    bpy.context.collection.objects.link(arm)
    arm.animation_data_clear()
    src = cow.meshes[0]
    body = bpy.data.objects.new("GnuTemplateBody", _edit_mesh(src, cow.arm))
    bpy.context.collection.objects.link(body)
    for g in src.vertex_groups:
        body.vertex_groups.new(name=g.name)
    # weights: copied vertex by vertex (copying the mesh data already carries the weights; the groups must exist)
    body.parent = arm
    body.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    body.matrix_world = src.matrix_world.copy()
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    # materials: striped body, dark face and hooves (per face, in the rest pose)
    me = body.data
    me.materials.clear()
    for m in (_body_mat(), rigs.flat_mat(DARK), rigs.flat_mat(LEGS), rigs.flat_mat(HOOF)):
        me.materials.append(m)
    groups = {g.index: g.name for g in body.vertex_groups}
    hh, _ = _bone_world(cow.arm, "Head")
    for poly in me.polygons:
        c = sum((me.vertices[i].co for i in poly.vertices), Vector()) / len(poly.vertices)
        names = [groups[g.group] for i in poly.vertices for g in me.vertices[i].groups if g.weight > 0.5]
        idx = 0
        if "Head" in names and c.y < hh.y - 0.45:
            idx = 1                                     # face (front of the head) almost black
        elif any("LowLeg" in nm or "Foot" in nm for nm in names):
            idx = 3 if c.z < 0.45 else 2                # shin and hoof
        elif any("Tail3" == nm or "Tail4" == nm for nm in names):
            idx = 1
        poly.material_index = idx
        poly.use_smooth = False
    parts = [
        _part_obj("GnuTemplateHorns", _horns_geo(), rigs.flat_mat("#2C2A28"), arm, "Head"),
        _part_obj("GnuTemplateMane", _mane_geo(), rigs.flat_mat(DARK), arm, "Neck"),
        _part_obj("GnuTemplateBeard", _beard_geo(), rigs.flat_mat(DARK), arm, "Neck"),
        _part_obj("GnuTemplateTuft", _tail_tuft_geo(), rigs.flat_mat(DARK), arm, "Tail4"),
    ]
    for o in (arm, body, *parts):
        o.hide_render = True
    t = SimpleNamespace(key="gnu", arm=arm, meshes=[body], parts=parts, actions=cow.actions, base_scale=cow.base_scale,
                        rot=cow.rot, box=cow.box)
    rigs._templates["gnu"] = t
    return t


def build(name, location, heading=0.0, length=2.5):
    """Wildebeest of 'length' meters (muzzle to tail tip, like the cow's box); heading in radians (0 = +x)."""
    t = template()
    g = rigs.spawn("gnu", name, length=length, location=location, heading=heading)
    for part in t.parts:
        c = part.copy()
        c.name = f"{name}{part.name.replace('GnuTemplate', '')}"
        bpy.context.collection.objects.link(c)
        c.parent = g.arm
        c.parent_type = "BONE"
        c.parent_bone = part.parent_bone
        c.matrix_parent_inverse = part.matrix_parent_inverse.copy()
        c.hide_render = False
    return g


def graze(g, f0, f1, down_deg=55.0, rate=0.6, phase=0.0, down_fn=None, head_fn=None):
    """Grazing: slow Idle + low neck and head chewing (the same recipe as the cow). down_fn(f, down_deg)
    returns the neck angle at frame f (raising the head, snorting); head_fn(f) adds degrees to the head. Keys on
    every frame when there is a down_fn (fast movement), otherwise every 2nd."""
    rigs.loop(g, "Idle", f0 - 40, f1 + 40, rate=rate, phase=phase)
    frames = list(range(f0 - 2, f1 + 3, 1 if down_fn else 2))

    def pose(f):
        d = down_fn(f, down_deg) if down_fn else down_deg
        k = max(0.0, min(1.0, d / max(down_deg, 1e-6)))           # chews only with the head down
        chew = 4.0 * k * math.sin(2 * math.pi * 1.1 * f / 30 + phase * 6)
        extra = head_fn(f) if head_fn else 0.0
        return {"Neck": rigs.bone_delta(g, "Neck", (1, 0, 0), d),
                "Head": rigs.bone_delta(g, "Head", (1, 0, 0), 0.45 * d + chew + extra)}
    rigs.pose_layer(g, frames, pose)
    return g


def head_up(g, f0, f1, down_deg=-12.0):
    """Head raised and alert (ears forward): the neck goes up."""
    rigs.loop(g, "Idle", f0 - 40, f1 + 40, rate=0.6)
    frames = list(range(f0 - 2, f1 + 3, 2))
    rigs.pose_layer(g, frames, lambda f: {"Neck": rigs.bone_delta(g, "Neck", (1, 0, 0), down_deg)})
    return g
