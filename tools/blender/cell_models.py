"""First-person hands, glowing bacteria and the inside of the cell with mitochondria
(bacteria-disappeared script). Runs inside Blender; everything by vertices, no bpy.ops.

Measurements and colors: docs/blender/model-references.md ("Cell and mitochondrion"). Adult hand: palm ~9 cm
wide, fingers ~8 cm, skin #C8916A and flannel shirt cuff #7A2E2E. Bacterium: amber gem of 2 to 4 cm.
Cell in the Kurzgesagt style: round shapes, saturated color, separation by value, no outline.
"""

import math
import random
from types import SimpleNamespace

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import kit
from kit import LUZ, flat

SKIN, PALM, FLANNEL, FLANNEL_DARK = "#C8916A", "#DB9C7A", "#7A2E2E", "#4A1A1C"
MEMBRANE, CRISTA, MATRIX, CUT = "#E0703A", "#F7C46A", "#7A2E2A", "#F4A06A"
CYTO_DEEP, CYTO, CYTO_LIGHT = "#0F2242", "#13284A", "#172F55"
NUCLEUS, PORE, PORE_HOLE = "#2B3F7A", "#5B76C8", "#16224A"
RIBO, ER, GOLGI, VESICLE, TUBULE = "#2F5E8C", "#4E5AA8", "#C4557E", "#4A86C0", "#3F64A8"


def _mat(name, color, emission=None, strength=0.0):
    """Flat material reused by name (reset_scene wipes everything, so the cache is bpy.data itself)."""
    return bpy.data.materials.get(name) or flat(name, color, emission=emission, strength=strength)


def _part(name, geo, mats, parent, face_mats=None):
    obj = kit.mesh_object(name, geo[0], geo[1], mats, face_mats=face_mats)
    kit.fix_normals(obj)
    obj.parent = parent
    return obj


def _empty(name, location, parent=None, rotation=(0, 0, 0)):
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = rotation
    root.parent = parent
    return root


def _linear(owner, attr, pairs):
    """Linear keys (glow phase, drift): without the Bezier acceleration at the start and end."""
    edit = bpy.context.preferences.edit
    old, edit.keyframe_new_interpolation_type = edit.keyframe_new_interpolation_type, "LINEAR"
    for frame, value in pairs:
        kit.key(owner, attr, value, frame)
    edit.keyframe_new_interpolation_type = old


# ---------- first-person hands ----------

# Right hand in the hand's own space: wrist at the origin, fingers along +y, palm facing +z, thumb along +x.
# Palm sections: y, half-width, half-thickness (the knuckle line slopes down from the index to the little finger).
PALM_SECTIONS = [(-0.005, 0.029, 0.0145), (0.020, 0.037, 0.016), (0.050, 0.043, 0.0165),
                 (0.075, 0.045, 0.015), (0.092, 0.044, 0.012)]
KNUCKLE_SLOPE = 0.25
SKIN_MATS = ("HandSkin", "HandPalm")   # for specks_on_surface(..., mats=SKIN_MATS): skin without the sleeve
# Fingers from the thumb outward: base x, length, radius, spread (rad, + = toward the thumb side)
FINGERS = [(0.031, 0.074, 0.0094, 0.09), (0.010, 0.082, 0.0097, 0.02),
           (-0.011, 0.077, 0.0090, -0.06), (-0.031, 0.060, 0.0078, -0.16)]
PHALANX = (0.45, 0.30, 0.25)         # fraction of the finger in each phalanx
CURL = (0.10, 0.20, 0.14)            # bend of each joint toward the palm (relaxed hand)
THUMB = [((0.020, 0.010, 0.002), 0.016), ((0.046, 0.036, 0.010), 0.0125), ((0.065, 0.066, 0.016), 0.0108),
         ((0.077, 0.091, 0.017), 0.0094), ((0.080, 0.099, 0.015), 0.0058)]
# Poses: (wrist position in the camera for a 24 mm lens, XYZ rotation in degrees) per side (+1 right, -1 left)
RAISED = {1: ((0.10, -0.12, -0.44), (-22, -16, 17)), -1: ((-0.10, -0.12, -0.44), (-22, 16, -17))}
OPEN = {1: ((0.015, -0.16, -0.36), (-72, -6, 8)), -1: ((-0.24, -0.62, -0.42), (-22, 16, -17))}


def _knuckle_y(x):
    return 0.092 + KNUCKLE_SLOPE * x


def _palm():
    """Palm as a rounded box (super-ellipse) by sections, plus the thumb and little-finger pads."""
    rings = []
    for y, hw, ht in PALM_SECTIONS:
        ring = []
        for i in range(12):
            a = 2 * math.pi * i / 12
            c, s = math.cos(a), math.sin(a)
            x = hw * math.copysign(abs(c) ** 0.6, c)
            z = ht * math.copysign(abs(s) ** 0.6, s)
            ring.append((x, y + KNUCKLE_SLOPE * x * max(y, 0.0) / 0.092, z))
        rings.append(ring)
    thenar = kit._ico_geo(1.0, (0.022, 0.032, 0.003), (0.022, 0.034, 0.0118))
    hypothenar = kit._ico_geo(1.0, (-0.028, 0.040, 0.002), (0.016, 0.036, 0.0108))
    return [kit.loft_geo(rings), thenar, hypothenar]


def _finger(x, length, r, spread):
    """Three phalanges with the natural bend of the relaxed hand; rounded tip."""
    d = Vector((math.sin(spread), math.cos(spread), 0.0))
    axis = Vector((math.cos(spread), -math.sin(spread), 0.0))      # joint axis
    p = Vector((x, _knuckle_y(x) - 0.004, 0.0))
    pts, radii = [p - d * 0.014, p.copy()], [r * 1.08, r * 1.05]
    for k, (frac, bend) in enumerate(zip(PHALANX, CURL)):
        d = Matrix.Rotation(bend, 3, axis) @ d
        seg = frac * length
        if k < 2:
            p = p + d * seg
            pts.append(p.copy())
            radii.append(r * (0.96 if k == 0 else 0.88))             # slightly thicker joint
        else:
            pts += [p + d * seg * 0.55, p + d * (seg - 0.004), p + d * seg]
            radii += [r * 0.82, r * 0.72, r * 0.36]
    return kit.tube_geo([tuple(q) for q in pts], radii, n=7, squash=0.86)


def _thumb():
    return kit.tube_geo([p for p, _ in THUMB], [r for _, r in THUMB], n=7, squash=0.9)


def _forearm():
    pts = [(0, 0.012, 0), (0, -0.035, -0.001), (0, -0.16, -0.002), (0, -0.32, -0.002)]
    return kit.tube_geo(pts, (0.027, 0.029, 0.035, 0.037), n=8, squash=0.72)


def _sleeve():
    """Flannel shirt cuff, hollow (the forearm comes out of it), with dark plaid stripes."""
    n = 12
    # (y, radius): from outside the elbow to the edge, the folded edge and a bit inside
    rings_spec = [(-0.34, 0.052), (-0.22, 0.050), (-0.20, 0.050), (-0.12, 0.048), (-0.10, 0.047),
                  (-0.072, 0.046), (-0.062, 0.043), (-0.068, 0.037), (-0.12, 0.036)]
    rings = [[(r * math.cos(2 * math.pi * j / n), y, 0.78 * r * math.sin(2 * math.pi * j / n)) for j in range(n)]
             for y, r in rings_spec]
    geo = kit.loft_geo(rings, cap_start=False, cap_end=False)
    stripes = {1, 3}
    mats = [3 if band in stripes or j in (2, 8) else 2 for band in range(len(rings) - 1) for j in range(n)]
    return geo, mats


def _hand_object(name, side, m):
    """Hand + forearm + cuff, origin at the wrist. side = -1 mirrors (left hand: thumb along -x)."""
    sleeve, sleeve_mats = _sleeve()
    skin = [*_palm(), *[_finger(*f) for f in FINGERS], _thumb(), _forearm()]
    verts, faces, owner = kit.merge(*skin, sleeve)
    face_mats = [0] * (len(faces) - len(sleeve_mats)) + sleeve_mats
    if side < 0:
        verts = [(-x, y, z) for x, y, z in verts]
    obj = kit.mesh_object(name, verts, faces, [m.skin, m.palm, m.flannel, m.flannel_dark], face_mats=face_mats)
    kit.fix_normals(obj)
    for poly in obj.data.polygons:                     # lighter side of the palm (as on a real hand)
        if poly.material_index == 0 and poly.normal.z > 0.45:
            poly.material_index = 1
    obj.rotation_mode = "XYZ"
    return obj


def _hand_mats():
    return SimpleNamespace(skin=_mat("HandSkin", SKIN), palm=_mat("HandPalm", PALM),
                           flannel=_mat("Flannel", FLANNEL), flannel_dark=_mat("FlannelDark", FLANNEL_DARK))


def _pose(h, pose, frame=None):
    for side, hand in ((1, h.right), (-1, h.left)):
        loc, rot = pose[side]
        hand.location = Vector(loc) * h.scale
        hand.rotation_euler = [math.radians(a) for a in rot]
        if frame is not None:
            hand.keyframe_insert("location", frame=frame)
            hand.keyframe_insert("rotation_euler", frame=frame)


def hands(cam, one_hand=False):
    """Forearms and hands in front of the camera 'cam' (looks along local -z, up = local +y), palms toward the viewer.
    The positions hold for any lens: they scale with cam.data.lens / 24 (the framing stays the same).
    one_hand=True already starts in the open-palm pose (pose_open_palm). Returns SimpleNamespace(left, right, root):
    root is an Empty child of the camera (animate root.location to raise and lower both hands)."""
    m = _hand_mats()
    root = _empty("Hands", (0, 0, 0), parent=cam)
    h = SimpleNamespace(left=_hand_object("HandL", -1, m), right=_hand_object("HandR", 1, m), root=root,
                        scale=cam.data.lens / 24.0)
    h.left.parent = h.right.parent = root
    _pose(h, OPEN if one_hand else RAISED)
    return h


def pose_raised(h, frame):
    """Key of both hands raised, palms toward the camera."""
    _pose(h, RAISED, frame)


def pose_open_palm(h, frame):
    """Key of the dive pose: right hand open, palm up, at the center and low; left leaves the frame.
    For a transition, call pose_raised(h, f0) before and pose_open_palm(h, f1) after."""
    _pose(h, OPEN, frame)


def lift(h, f0, f1, drop=0.45, up=True):
    """Raises (up=True) or lowers both hands between f0 and f1, by 'drop' meters below the frame."""
    low, high = (0.0, -drop * h.scale, 0.0), (0.0, 0.0, 0.0)
    kit.ramp(h.root, "location", low if up else high, high if up else low, f0, f1)


# ---------- bacteria (amber dots) ----------

TETRA = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
TETRA_F = [(0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)]


def _speck_material(name, color, strength):
    """Emissive amber; each dot blinks in its own phase ('rnd' attribute per point).
    Returns (material, strength socket, alpha socket, phase socket)."""
    mat = flat(name, color, emission=color, strength=strength)
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    n, links = nt.nodes, nt.links
    p = kit.principled(mat)
    power = n.new("ShaderNodeValue"); power.outputs[0].default_value = strength
    phase = n.new("ShaderNodeValue"); phase.outputs[0].default_value = 0.0
    alpha = n.new("ShaderNodeValue"); alpha.outputs[0].default_value = 1.0
    seed = n.new("ShaderNodeAttribute"); seed.attribute_name = "rnd"
    spin = n.new("ShaderNodeMath"); spin.operation = "MULTIPLY_ADD"
    spin.inputs[1].default_value = 2 * math.pi
    links.new(seed.outputs["Fac"], spin.inputs[0])
    links.new(phase.outputs[0], spin.inputs[2])
    sine = n.new("ShaderNodeMath"); sine.operation = "SINE"
    links.new(spin.outputs[0], sine.inputs[0])
    twinkle = n.new("ShaderNodeMath"); twinkle.operation = "MULTIPLY_ADD"     # 0.55 + 0.45 sin
    twinkle.inputs[1].default_value = 0.45
    twinkle.inputs[2].default_value = 0.55
    links.new(sine.outputs[0], twinkle.inputs[0])
    out = n.new("ShaderNodeMath"); out.operation = "MULTIPLY"
    links.new(twinkle.outputs[0], out.inputs[0])
    links.new(power.outputs[0], out.inputs[1])
    links.new(out.outputs[0], p.inputs["Emission Strength"])
    links.new(alpha.outputs[0], p.inputs["Alpha"])
    return mat, power.outputs[0], alpha.outputs[0], phase.outputs[0]


def specks(name, points, rnd, gem=(0.02, 0.04), rise=(1.0, 4.0), drift=0.5, strength=2.5, color=LUZ):
    """A single mesh with an amber tetrahedron at each point (object coordinates).
    Shape key 'rise': each one rises 1 to 4 m with lateral drift and shrinks to 20%.
    Returns SimpleNamespace(obj, rise_key, emission_socket, alpha_socket, phase_socket)."""
    verts, faces, risen, seeds = [], [], [], []
    for c in points:
        c = Vector(c)
        r = rnd.uniform(*gem) / 2
        rot = Euler([rnd.uniform(0, 2 * math.pi) for _ in range(3)]).to_matrix()
        off = Vector((rnd.uniform(-drift, drift), rnd.uniform(-drift, drift), rnd.uniform(*rise)))
        seed, base = rnd.random(), len(verts)
        for t in TETRA:
            q = rot @ (Vector(t) * (r / math.sqrt(3)))
            verts.append(tuple(c + q))
            risen.append(c + off + q * 0.2)
            seeds.append(seed)
        faces += [tuple(base + i for i in f) for f in TETRA_F]
    mat, power, alpha, phase = _speck_material(name + "Mat", color, strength)
    obj = kit.mesh_object(name, verts, faces, [mat])
    kit.fix_normals(obj)
    obj.visible_shadow = False
    attr = obj.data.attributes.new("rnd", "FLOAT", "POINT")
    attr.data.foreach_set("value", seeds)
    obj.shape_key_add(name="Basis")
    kb = obj.shape_key_add(name="rise")
    kb.value = 0.0                                       # in Blender 5.2 the new key is born at 1
    kb.data.foreach_set("co", [c for v in risen for c in v])
    return SimpleNamespace(obj=obj, rise_key=kb, emission_socket=power, alpha_socket=alpha, phase_socket=phase)


def _keep_world(obj, parent):
    """Parents without moving it: the object's space remains the current world."""
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()


def specks_on_surface(name, obj_list, count, rnd, parent=None, mats=None, **kw):
    """Scatters 'count' dots over the faces of the objects (world, proportional to area), half-buried in the skin.
    parent: object they follow (e.g. the hand); the 'rise' lift is the world's "up" at assembly time.
    mats: only the faces with these materials (e.g. skin without the sleeve, SKIN_MATS)."""
    bpy.context.view_layer.update()
    tris = []
    for obj in obj_list:
        mw = obj.matrix_world
        nm = mw.to_3x3().inverted_safe().transposed()
        mesh = obj.data
        allowed = {i for i, m in enumerate(mesh.materials) if mats is None or m.name in mats}
        for poly in mesh.polygons:
            if poly.material_index not in allowed:
                continue
            vs = [mw @ mesh.vertices[i].co for i in poly.vertices]
            nrm = (nm @ poly.normal).normalized()
            for a, b in zip(vs[1:], vs[2:]):
                tris.append(((a - vs[0]).cross(b - vs[0]).length / 2, vs[0], a, b, nrm))
    lift_off = sum(kw.get("gem", (0.02, 0.04))) / 2 * 0.15
    points = []
    for _, p0, a, b, nrm in rnd.choices(tris, weights=[t[0] for t in tris], k=count):
        u, v = rnd.random(), rnd.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        points.append(p0 + (a - p0) * u + (b - p0) * v + nrm * lift_off)
    s = specks(name, points, rnd, **kw)
    _keep_world(s.obj, parent)
    return s


def specks_in_air(name, center, size, count, rnd, parent=None, **kw):
    """Loose dots in a box (size scalar or (sx, sy, sz)) around 'center' (world)."""
    sx, sy, sz = size if isinstance(size, (tuple, list)) else (size, size, size)
    c = Vector(center)
    points = [c + Vector((rnd.uniform(-sx, sx) / 2, rnd.uniform(-sy, sy) / 2, rnd.uniform(-sz, sz) / 2))
              for _ in range(count)]
    s = specks(name, points, rnd, **kw)
    _keep_world(s.obj, parent)
    return s


def shimmer(s, f0, f1, fps=30, speed=1.6, drift=0.006):
    """Slowly blinking glow (each in its own phase) and a minimal upward drift: there is movement already at frame f0."""
    _linear(s.phase_socket, "default_value", [(f0, 0.0), (f1, speed * 2 * math.pi * (f1 - f0) / fps)])
    _linear(s.rise_key, "value", [(f0, 0.0), (f1, drift)])


def blink_away(s, frame, frames):
    """They vanish over 'frames' frames from 'frame': glow peaks, they rise, shrink and fade out.
    The shimmer must end (f1) before 'frame', otherwise its keys pull the 'rise' back."""
    power = s.emission_socket.default_value
    kit.key(s.rise_key, "value", s.rise_key.value, frame)
    kit.key(s.rise_key, "value", 1.0, frame + frames)
    kit.key(s.emission_socket, "default_value", power, frame)
    kit.key(s.emission_socket, "default_value", power * 2.0, frame + max(1, frames // 4))
    kit.key(s.emission_socket, "default_value", 0.0, frame + frames)
    kit.key(s.alpha_socket, "default_value", 1.0, frame + frames // 3)
    kit.key(s.alpha_socket, "default_value", 0.0, frame + frames)


# ---------- mitochondrion ----------

HALF, RAD, FLATNESS = 1.5, 0.6, 0.82   # half length, radius, height / width of the section (for length = 3 m)
WALL, GAP, INNER = 0.06, 0.05, 0.05    # outer membrane, intermembrane space, inner membrane
BEND = math.radians(18)
CUT_KEEP = 0.6                         # stays at 60% of the height: the cut removes the top 40%
CRISTAE = 8
GLOW_REST = 0.4                        # resting glow of the cristae (the yellow does not turn olive in blue light)


def _stations(half, rad):
    """Positions along the axis: tips at an angle (round) and a uniform middle."""
    straight = half - rad
    caps = [straight + rad * math.sin(math.radians(a)) for a in (15, 32, 48, 62, 75, 86)]
    mid = [straight * (i / 4 - 1) for i in range(9)]
    return [-u for u in reversed(caps)] + mid + caps


def _capsule_r(u, half, rad):
    d = abs(u) - (half - rad)
    return max(rad if d <= 0 else math.sqrt(max(rad * rad - d * d, 0.0)), 0.004)


def _axis(u, half):
    """Curved axis (bean): point, tangent and side (local +y in the section) at position u."""
    rb = 2 * half / BEND
    th = u / rb
    sag = rb * (1 - math.cos(BEND / 2)) / 2
    c = Vector((rb * math.sin(th), rb * (1 - math.cos(th)) - sag, 0.0))
    return c, Vector((math.cos(th), math.sin(th), 0.0)), Vector((-math.sin(th), math.cos(th), 0.0))


def _arc(r, h, z_cut, n, reverse=False):
    """Section outline (ellipse r x h) below the cut, from one side of the cut to the other passing through the bottom."""
    a = max(math.acos(max(-1.0, min(1.0, -z_cut / h))), 0.05) if z_cut < h else math.pi * 0.995
    angs = [-a + 2 * a * i / (n - 1) for i in range(n)]
    if reverse:
        angs.reverse()
    return [(r * math.sin(t), -h * math.cos(t)) for t in angs]


def _to_world(pts, u, half):
    c, _, side = _axis(u, half)
    return [tuple(c + side * y + Vector((0.0, 0.0, z))) for y, z in pts]


def _band(half, rad, inset_out, inset_in, z_cut, n=20):
    """Membrane with thickness (hollow), cut at z_cut: the section is a U between the outer and the inner face."""
    rings = []
    for u in _stations(half, rad):
        ro = _capsule_r(u, half - inset_out, rad - inset_out)
        ri = _capsule_r(u, half - inset_in, rad - inset_in)
        pts = _arc(ro, ro * FLATNESS, z_cut, n) + _arc(ri, ri * FLATNESS, z_cut, n, reverse=True)
        rings.append(_to_world(pts, u, half))
    return kit.loft_geo(rings)


def _solid(half, rad, inset, z_top, n=20):
    """Solid body cut at z_top (matrix; or the closed mitochondrion, with z_top above everything)."""
    rings = []
    for u in _stations(half, rad):
        r = _capsule_r(u, half - inset, rad - inset)
        rings.append(_to_world(_arc(r, r * FLATNESS, z_top, n), u, half))
    return kit.loft_geo(rings)


def _cristae(half, rad, inset, z_top, thick):
    """Wavy plates alternating from one side to the other, each covering ~70% of the width."""
    parts = []
    span = half - rad * 0.55
    for k in range(CRISTAE):
        u = -span + 2 * span * (k + 0.5) / CRISTAE
        side = 1 if k % 2 else -1
        r = _capsule_r(u, half - inset, rad - inset) + 0.01      # goes slightly into the inner membrane
        h = r * FLATNESS
        lo, hi = -math.asin(0.4), math.acos(max(-1.0, -z_top / h))
        sec = [(r * math.sin(a), -h * math.cos(a)) for a in (lo + (hi - lo) * i / 9 for i in range(10))]
        tip, bevel = -0.4 * r, 0.12 * r
        sec += [(tip + bevel, z_top), (tip + bevel * 0.3, z_top - bevel * 0.3), (tip, z_top - bevel)]
        c, t, sd = _axis(u, half)
        rings = []
        for off in (-0.5, 0.5):
            # waves along the axis and thins at the tip (seen from above, the tongue tip is round)
            ring = []
            for y, z in sec:
                taper = min(1.0, (y - tip) / (0.35 * r) + 0.25) ** 0.5
                wave = 0.22 * r * math.sin(4.5 * (y - tip) / r)
                ring.append(tuple(c + sd * (side * y) + Vector((0.0, 0.0, z)) + t * (off * thick * taper + wave)))
            rings.append(ring)
        parts.append(kit.loft_geo(rings))
    return parts


def _mito_mats():
    shell = _mat("MitoShell", MEMBRANE, emission=LUZ)
    crista = _mat("MitoCrista", CRISTA, emission=LUZ, strength=GLOW_REST)
    return SimpleNamespace(shell=shell, cut=_mat("MitoCut", CUT), matrix=_mat("MitoMatrix", MATRIX), crista=crista)


def _rim_mats(obj, z_cut):
    """Faces lying in the cut plane get the cut color (index 1)."""
    for poly in obj.data.polygons:
        if all(abs(obj.data.vertices[i].co.z - z_cut) < 1e-4 for i in poly.vertices):
            poly.material_index = 1


def mitochondrion(name, location, length=3.0, cutaway=True, rotation=(0, 0, 0), rnd=None):
    """Bean 3.0 x 1.2 m curved 18° (axis along x, cut from above at +z). cutaway=False: only the outer membrane.
    Returns SimpleNamespace(root, parts, glow_socket). glow_socket is the amber emission of the cristae (or of the membrane,
    on the closed one); the material is the same on all, so they all pulse together. parts.atp are dots (specks)."""
    rnd = rnd or random.Random(hash(name) & 0xFFFF)
    m = _mito_mats()
    s = length / 3.0
    half, rad = HALF * s, RAD * s
    root = _empty(name, location, rotation=rotation)
    if not cutaway:
        shell = _part(name + "Shell", _solid(half, rad, 0.0, 10.0), [m.shell], root)
        return SimpleNamespace(root=root, parts=SimpleNamespace(shell=shell),
                               glow_socket=kit.principled(m.shell).inputs["Emission Strength"])
    z_cut = (2 * CUT_KEEP - 1) * rad * FLATNESS
    z_floor = z_cut - 0.24 * s
    inner_in = (WALL + GAP + INNER) * s
    shell = _part(name + "Shell", _band(half, rad, 0.0, WALL * s, z_cut), [m.shell, m.cut], root)
    inner = _part(name + "Inner", _band(half, rad, (WALL + GAP) * s, inner_in, z_cut), [m.shell, m.cut], root)
    for obj in (shell, inner):
        _rim_mats(obj, z_cut)
    matrix = _part(name + "Matrix", _solid(half, rad, inner_in - 0.01 * s, z_floor), [m.matrix], root)
    crista_geo = kit.merge(*_cristae(half, rad, inner_in, z_cut - 0.035 * s, 0.075 * s))
    cristae = _part(name + "Cristae", crista_geo[:2], [m.crista], root)
    pts = []
    for _ in range(12):
        u = rnd.uniform(-half + rad, half - rad)
        c, _, sd = _axis(u, half)
        pts.append(c + sd * rnd.uniform(-0.35, 0.35) * rad + Vector((0, 0, rnd.uniform(z_floor + 0.06 * s, z_cut))))
    atp = specks(name + "ATP", pts, rnd, gem=(0.05 * s, 0.08 * s), rise=(1.0 * s, 2.5 * s), drift=0.7 * s, strength=6.0)
    atp.obj.parent = root
    parts = SimpleNamespace(shell=shell, inner=inner, matrix=matrix, cristae=cristae, atp=atp)
    return SimpleNamespace(root=root, parts=parts, glow_socket=kit.principled(m.crista).inputs["Emission Strength"])


def pulse(mito, f0, f1, period=24, peak=3.0):
    """Amber glow of the cristae pulsing between f0 and f1 (one pulse every 'period' frames)."""
    sock = mito.glow_socket
    rest = sock.default_value
    kit.key(sock, "default_value", rest, f0)
    f = f0
    while f + period <= f1:
        kit.key(sock, "default_value", peak, f + period // 3)
        kit.key(sock, "default_value", rest, f + period)
        f += period


# ---------- inside of the cell ----------

def _sphere_geo(r, seg, rows, center=(0, 0, 0), scale=(1, 1, 1), rnd=None, jitter=0.0):
    """Sphere in rings (latitudes) with caps; jitter makes the radius irregular (organic membrane)."""
    rings = []
    for i in range(1, rows):
        lat = -math.pi / 2 + math.pi * i / rows
        ring = []
        for j in range(seg):
            lon = 2 * math.pi * j / seg
            k = r * (1 + (rnd.uniform(-jitter, jitter) if rnd else 0.0))
            ring.append((center[0] + k * math.cos(lat) * math.cos(lon) * scale[0],
                         center[1] + k * math.cos(lat) * math.sin(lon) * scale[1],
                         center[2] + k * math.sin(lat) * scale[2]))
        rings.append(ring)
    return kit.loft_geo(rings)


def _flip(obj):
    """Normals pointing inward (the membrane is seen from inside)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _aim(geo, origin, direction):
    """Places a piece built around +z pointing toward 'direction', at 'origin'."""
    rot = Vector((0, 0, 1)).rotation_difference(Vector(direction)).to_matrix().to_4x4()
    return kit.xform_geo(geo, Matrix.Translation(Vector(origin)) @ rot)


def _rand_dir(rnd):
    while True:
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if 0.1 < v.length <= 1:
            return v.normalized()


def _membrane(root, radius, rnd):
    mats = [_mat(f"Cyto{i}", c, emission=c, strength=0.3) for i, c in enumerate((CYTO_DEEP, CYTO, CYTO_LIGHT))]
    verts, faces = _sphere_geo(radius, 40, 20, rnd=rnd, jitter=0.012)
    face_mats = []
    for f in faces:
        z = sum(verts[i][2] for i in f) / len(f) / radius
        t = (z + 1) / 2 + rnd.uniform(-0.05, 0.05)               # lighter on top, like diffuse light
        face_mats.append(0 if t < 0.38 else 1 if t < 0.72 else 2)
    obj = _part("CellMembrane", (verts, faces), mats, root, face_mats)
    _flip(obj)
    return obj


def _nucleus(root, center, r, rnd):
    body = _sphere_geo(r, 28, 14, center, rnd=rnd, jitter=0.02)
    parts, kinds = [body], [0]
    for _ in range(46):
        d = _rand_dir(rnd)
        if d.y > 0.5:                                         # pores only on the side that shows
            continue
        base = Vector(center) + d * (r * 0.97)
        parts += [_aim(kit._prism_geo(8, 0.75, 0.6, 0.35), base, d), _aim(kit._prism_geo(8, 0.34, 0.34, 0.4), base, d)]
        kinds += [1, 2]
    verts, faces, owner = kit.merge(*parts)
    mats = [_mat("Nucleus", NUCLEUS, emission=NUCLEUS, strength=0.4), _mat("NucPore", PORE), _mat("NucHole", PORE_HOLE)]
    return _part("Nucleus", (verts, faces), mats, root, [kinds[k] for k in owner])


def _er_ribbons(center, r_nuc, rnd):
    """Reticulum: wavy ribbons around the nucleus, facing the camera; returns geometries and ribosome points."""
    parts, studs = [], []
    c = Vector(center)
    for k in range(8):
        rr = r_nuc + 1.4 + 0.9 * (k % 4)
        lift = (k - 3.5) * 1.5
        tilt = rnd.uniform(-0.3, 0.3)
        e1 = Vector((1, 0, 0))
        e2 = Matrix.Rotation(tilt, 3, "X") @ Vector((0, -1, 0))
        e3 = e1.cross(e2)
        a0 = rnd.uniform(-1.6, -0.2)
        span = rnd.uniform(1.0, 1.6)
        pts = []
        for i in range(26):
            th = a0 + span * i / 25
            ring_r = math.sqrt(max(rr * rr - lift * lift, 4.0))      # stays on the shell around the nucleus
            p = c + (e1 * math.sin(th) + e2 * math.cos(th)) * (ring_r + 0.55 * math.sin(9 * th + k)) \
                + e3 * (lift + 0.4 * math.sin(4 * th + k * 1.7))
            pts.append(tuple(p))
        radii = [0.24 * min(1.0, 0.35 + 0.65 * math.sin(math.pi * i / 25)) for i in range(26)]   # tips thin out
        parts.append(kit.tube_geo(pts, radii, n=6, squash=3.6))
        for p in pts[1:-1:2]:
            studs.append(Vector(p) + (Vector(p) - c).normalized() * 0.32)
    return parts, studs


def _golgi(center, toward):
    """Golgi complex: stack of curved discs."""
    d = Vector(toward).normalized()
    turn = Matrix.Rotation(math.atan2(d.y, d.x) + math.pi / 2, 4, "Z")      # discs sideways toward 'toward'
    parts = []
    for k in range(5):
        p = Vector(center) + Vector((0, 0, (k - 2) * 0.75)) + d * (0.35 * (k - 2) ** 2)
        disc = _sphere_geo(1.0, 14, 6, scale=(3.4 - 0.35 * abs(k - 2), 1.1, 0.26))
        parts.append(kit.xform_geo(disc, Matrix.Translation(p) @ turn))
    return parts


def cell_interior(origin=(0, 0, -500), rnd=None, radius=48.0, keep_clear=(), haze=True):
    """Cell interior seen from inside, built far from the farm. Everything is a child of root (Empty at 'origin').
    keep_clear: points (relative to the origin) where no mitochondria go (e.g. camera, cut mitochondrion).
    Has its own light (the membrane blocks the outside sun). Remember a camera with clip_end > 2 x radius.
    Returns SimpleNamespace(root, membrane, nucleus, mitochondria, lights, haze)."""
    rnd = rnd or random.Random(7)
    root = _empty("Cell", origin)
    membrane = _membrane(root, radius, rnd)
    nuc_c, nuc_r = Vector((8, 18, 2)), 11.0
    nucleus = _nucleus(root, nuc_c, nuc_r, rnd)

    er_parts, studs = _er_ribbons(nuc_c, nuc_r, rnd)
    _part("ER", kit.merge(*er_parts)[:2], [_mat("ER", ER, emission=ER, strength=0.3)], root)
    _part("Golgi", kit.merge(*_golgi(nuc_c + Vector((-17, -6, 3)), (1, 0.4, 0)))[:2],
          [_mat("Golgi", GOLGI, emission=GOLGI, strength=0.3)], root)

    for _ in range(420):                                      # free ribosomes in the cytoplasm
        p = _rand_dir(rnd) * rnd.uniform(6, radius - 4)
        if (p - nuc_c).length > nuc_r + 1.5:
            studs.append(p)
    ribo = kit.merge(*[kit._gem_geo(rnd.uniform(0.14, 0.3), oz=p.z, ox=p.x, oy=p.y) for p in studs])
    _part("Ribosomes", ribo[:2], [_mat("Ribo", RIBO, emission=RIBO, strength=0.8)], root)

    ves = []
    for _ in range(16):
        p = _rand_dir(rnd) * rnd.uniform(8, radius - 8)
        if (p - nuc_c).length > nuc_r + 3:
            ves.append(kit._ico_geo(rnd.uniform(0.7, 1.9), tuple(p)))
    _part("Vesicles", kit.merge(*ves)[:2], [_mat("Vesicle", VESICLE, emission=VESICLE, strength=0.4)], root)

    tubes = []
    for _ in range(6):                                        # microtubules from the nucleus to the edge
        d = _rand_dir(rnd)
        a = nuc_c + d * (nuc_r + 1)
        b = d * (radius - 2)
        mid = (a + b) / 2 + _rand_dir(rnd) * 3
        tubes.append(kit.tube_geo([tuple(a), tuple(mid), tuple(b)], (0.08, 0.08, 0.08), n=5))
    _part("Tubules", kit.merge(*tubes)[:2], [_mat("Tubule", TUBULE, emission=TUBULE, strength=0.5)], root)

    mitos, placed = [], [Vector(p) for p in keep_clear]
    tries = 0
    while len(mitos) < 8 and tries < 400:
        tries += 1
        p = _rand_dir(rnd) * rnd.uniform(12, radius - 9)
        if (p - nuc_c).length < nuc_r + 6 or any((p - q).length < 7 for q in placed):
            continue
        rot = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 2 * math.pi))
        mito = mitochondrion(f"Mito{len(mitos)}", tuple(p), length=rnd.uniform(3.0, 4.5), cutaway=False, rotation=rot)
        mito.root.parent = root
        mitos.append(mito)
        placed.append(p)

    lights = []
    for nm, pos, color, energy in (("CellKey", (-16, -20, 24), "#FFD7A8", 70000.0),
                                   ("CellFill", (22, -8, -14), "#7F9FFF", 40000.0),
                                   ("CellRim", (10, 36, 20), "#B08CFF", 30000.0)):
        light = bpy.data.lights.new(nm, "POINT")
        light.energy, light.color, light.shadow_soft_size = energy, kit.lin(color)[:3], 4.0
        obj = bpy.data.objects.new(nm, light)
        bpy.context.collection.objects.link(obj)
        obj.location, obj.parent = pos, root
        lights.append(obj)

    fog = None
    if haze:
        fog = kit.mesh_object("CellHaze", *_sphere_geo(radius - 1.0, 16, 8), [_haze_material()])
        fog.parent = root
    return SimpleNamespace(root=root, membrane=membrane, nucleus=nucleus, mitochondria=mitos, lights=lights, haze=fog)


def _haze_material():
    """Light blue haze inside the cell: what is far away gets lighter and bluer (depth)."""
    mat = bpy.data.materials.get("CellHaze")
    if mat:
        return mat
    mat = bpy.data.materials.new("CellHaze")
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(kit.principled(mat))
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = kit.lin("#3A5FA8")
    vol.inputs["Density"].default_value = 0.006
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat
