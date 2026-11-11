"""Low-poly chicken with skeleton and actions (Idle, Walk, Peck) for the stage builder. Made by us, CC0.

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P tools/blender/chicken_model.py [-- --blend x.blend]

Writes assets/procedural/chicken/Chicken.fbx (+ SOURCE.txt, License.txt). FBX and not glb: the glTF importer
converts time by the fps of the scene it imports into (30 on the stage), while the FBX one brings the file's fps (24 = ASSET_FPS).

Reference (2026-10-25): adult laying hen ~40 cm tall up to the comb, ~45 cm from beak to tail, back at
~30 cm, visible leg (feathered thigh + yellow shin) ~15 cm; style of Quaternius's animals (Farm Animals,
Animal Pack): faceted, 4 to 6 flat colors, no texture. Chicken walk: short step (~16 cm per cycle),
cadence ~1.5 Hz, head stabilized in the world and "punched" forward at each step (head-bobbing).

Catalog conventions (rigs.spawn): the animal faces -y, z up, feet at z = 0; actions at 24 frames/s in
a loop (last frame = first); foot bones with 'Foot' in the name (models.feet_of), Foot bone head at the ankle,
still on the ground during stance (rigs.planted_speed measures its speed).

Pose: for each frame I compute the desired matrix of each bone in armature space (rigid body, neck
pointing at the head target, leg by analytic 2-bone IK with the knee backward) and convert it to
local location + rotation_quaternion: B = (P_parent @ R_parent^-1 @ R_bone)^-1 @ P_bone. Key on every frame, LINEAR.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
import bpy_extras.anim_utils as au
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "procedural" / "chicken"
FPS = 24

COLORS = {"Feather": "#F1EADB", "Wing": "#E2D5BC", "Tail": "#E9DFCB", "Comb": "#C8302A", "Beak": "#E8B23A",
          "Eye": "#151515"}

# ---------- bones (head, tail, parent), meters, facing -y ----------
SIDE_X = 0.045
HIP, ANKLE, FOOT, TOE = (0.03, 0.16), (0.05, 0.085), (0.03, 0.014), (-0.03, 0.014)   # (y, z)
BONES = {
    "Body": ((0, 0.08, 0.20), (0, -0.06, 0.20), None),
    "Neck": ((0, -0.095, 0.24), (0, -0.125, 0.335), "Body"),
    "Head": ((0, -0.125, 0.335), (0, -0.13, 0.41), "Neck"),
    "Tail": ((0, 0.12, 0.24), (0, 0.20, 0.33), "Body"),
}
for s, sx in (("L", 1), ("R", -1)):
    x = SIDE_X * sx
    BONES[f"Wing.{s}"] = ((0.09 * sx, -0.05, 0.225), (0.09 * sx, 0.12, 0.225), "Body")
    BONES[f"UpperLeg.{s}"] = ((x, *HIP), (x, *ANKLE), "Body")
    BONES[f"LowerLeg.{s}"] = ((x, *ANKLE), (x, *FOOT), f"UpperLeg.{s}")
    BONES[f"Foot.{s}"] = ((x, *FOOT), (x, *TOE), f"LowerLeg.{s}")
ORDER = ["Body", "Neck", "Head", "Tail", "Wing.L", "Wing.R", "UpperLeg.L", "LowerLeg.L", "Foot.L",
         "UpperLeg.R", "LowerLeg.R", "Foot.R"]
PIVOT = Vector((0, HIP[0], HIP[1]))          # the body tilts around the hip


# ---------- mesh ----------

class Mesh:
    def __init__(self):
        self.verts, self.faces, self.mats, self.weights = [], [], [], []

    def add(self, verts, faces, mat, weights):
        base = len(self.verts)
        self.verts += [Vector(v) for v in verts]
        self.weights += weights if isinstance(weights, list) else [weights] * len(verts)
        for f in faces:
            self.faces.append([base + i for i in f])
            self.mats.append(mat)


def ring_frame(t):
    t = Vector(t).normalized()
    x = Vector((1, 0, 0))
    u = t.cross(x)
    if u.length < 1e-6:
        u = Vector((0, 1, 0))
    return x, u.normalized()


def loft(m, sections, n, mat, weights, offset=0.0, caps=True):
    """sections: (center, tangent, rx, ru). Ring perpendicular to the tangent, x axis sideways. weights: dict per
    ring (list) or a single dict."""
    verts, faces, wts = [], [], []
    for k, (c, t, rx, ru) in enumerate(sections):
        x, u = ring_frame(t)
        for j in range(n):
            a = 2 * math.pi * j / n + offset
            verts.append(Vector(c) + x * rx * math.cos(a) + u * ru * math.sin(a))
            wts.append(weights[k] if isinstance(weights, list) else weights)
    for k in range(len(sections) - 1):
        for j in range(n):
            a, b = k * n + j, k * n + (j + 1) % n
            faces.append([a, b, b + n, a + n])
    if caps:
        faces.append(list(range(n))[::-1])
        last = (len(sections) - 1) * n
        faces.append([last + j for j in range(n)])
    m.add(verts, faces, mat, wts)


def path_loft(m, pts, radii, n, mat, weights, offset=0.0, caps=True):
    """Loft along a line of points (tangent from the neighbors' difference); radii = (rx, ru) per point."""
    secs = []
    for i, p in enumerate(pts):
        a, b = Vector(pts[max(i - 1, 0)]), Vector(pts[min(i + 1, len(pts) - 1)])
        secs.append((p, b - a, *radii[i]))
    loft(m, secs, n, mat, weights, offset, caps)


def slab(m, cols, x0, x1, mat, weight, bulge=0.0):
    """Flat piece in the yz plane: cols = (y, z_low, z_high); thickness from x0 to x1 (bulge pushes the middle of the
    outer face)."""
    verts, faces = [], []
    n = len(cols)
    for i, col in enumerate(cols):
        y, zb, zt = col[:3]
        a, b = (col[3], col[4]) if len(col) > 3 else (x0, x1)
        mid = math.sin(math.pi * i / (n - 1)) * bulge
        for x in (a, b + mid if b > a else b - mid):
            verts += [(x, y, zb), (x, y, zt)]
    flip = (cols[0][4] < cols[0][3]) if len(cols[0]) > 3 else (x1 < x0)
    # index: column i, side s (0 = x0, 1 = x1), z (0 low, 1 high) -> 4i + 2s + z
    v = lambda i, s, z: 4 * i + 2 * s + z
    for i in range(n - 1):
        faces.append([v(i, 0, 0), v(i, 0, 1), v(i + 1, 0, 1), v(i + 1, 0, 0)])      # x0 side
        faces.append([v(i, 1, 0), v(i + 1, 1, 0), v(i + 1, 1, 1), v(i, 1, 1)])      # x1 side
        faces.append([v(i, 0, 1), v(i, 1, 1), v(i + 1, 1, 1), v(i + 1, 0, 1)])      # top
        faces.append([v(i, 0, 0), v(i + 1, 0, 0), v(i + 1, 1, 0), v(i, 1, 0)])      # base
    faces.append([v(0, 0, 0), v(0, 1, 0), v(0, 1, 1), v(0, 0, 1)])
    last = n - 1
    faces.append([v(last, 0, 0), v(last, 0, 1), v(last, 1, 1), v(last, 1, 0)])
    if flip:
        faces = [f[::-1] for f in faces]
    m.add(verts, faces, mat, weight)


def body_halfwidth(body, y, z):
    """Half width of the body (loft of sections (y, zc, rx, rz)) at height z, interpolating between sections."""
    secs = sorted(body)
    for (y0, *a), (y1, *b) in zip(secs, secs[1:]):
        if y0 <= y <= y1:
            u = (y - y0) / (y1 - y0)
            zc, rx, rz = (p + (q - p) * u for p, q in zip(a, b))
            return rx * math.sqrt(max(0.0, 1 - ((z - zc) / rz) ** 2))
    return 0.02


def ellipsoid(m, c, r, mat, weight, n=6, rings=4):
    c = Vector(c)
    secs = []
    for k in range(rings + 1):
        a = -math.pi / 2 + math.pi * k / rings
        secs.append((c + Vector((0, r[1] * math.sin(a), 0)), (0, 1, 0), max(r[0] * math.cos(a), 1e-4),
                     max(r[2] * math.cos(a), 1e-4)))
    loft(m, secs, n, mat, weight, offset=math.pi / n, caps=False)


def build_mesh():
    m = Mesh()
    F, W, T, C, B, E = range(6)
    # body: tilted egg, fuller at the chest, rising toward the tail
    body = [(0.165, 0.255, 0.02, 0.02), (0.13, 0.24, 0.06, 0.062), (0.07, 0.22, 0.088, 0.093),
            (0.0, 0.205, 0.095, 0.10), (-0.065, 0.205, 0.088, 0.096), (-0.105, 0.222, 0.064, 0.072),
            (-0.13, 0.24, 0.03, 0.035)]
    loft(m, [((0, y, z), (0, -1, 0), rx, rz) for y, z, rx, rz in body], 8, F, {"Body": 1.0}, offset=math.pi / 8)
    # neck: rings with weight blended body -> neck -> head (smooth bend)
    neck = [(0, -0.075, 0.215), (0, -0.103, 0.268), (0, -0.118, 0.305), (0, -0.128, 0.34), (0, -0.136, 0.37)]
    nr = [(0.058, 0.058), (0.053, 0.053), (0.046, 0.046), (0.039, 0.039), (0.028, 0.028)]
    nw = [{"Body": 1.0}, {"Body": 0.5, "Neck": 0.5}, {"Neck": 1.0}, {"Neck": 0.35, "Head": 0.65}, {"Head": 1.0}]
    path_loft(m, neck, nr, 8, F, nw, offset=math.pi / 8)
    # head
    head = [(-0.102, 0.372, 0.014, 0.016), (-0.116, 0.373, 0.03, 0.034), (-0.138, 0.372, 0.035, 0.037),
            (-0.158, 0.368, 0.03, 0.031), (-0.172, 0.364, 0.017, 0.019)]
    loft(m, [((0, y, z), (0, -1, 0), rx, rz) for y, z, rx, rz in head], 8, F, {"Head": 1.0}, offset=math.pi / 8)
    # beak: 4-sided pyramid, slightly curved downward
    base = [(0.012, -0.166, 0.368), (-0.012, -0.166, 0.368), (-0.011, -0.166, 0.352), (0.011, -0.166, 0.352)]
    tip = (0, -0.203, 0.354)
    m.add(base + [tip], [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [3, 2, 1, 0]], B, {"Head": 1.0})
    # comb: 4 points along the top line of the head
    comb = [(-0.168, 0.385, 0.402), (-0.16, 0.39, 0.425), (-0.15, 0.393, 0.41), (-0.14, 0.394, 0.437),
            (-0.13, 0.394, 0.415), (-0.12, 0.392, 0.432), (-0.11, 0.388, 0.41), (-0.1, 0.383, 0.418),
            (-0.094, 0.378, 0.392)]
    slab(m, comb, -0.0075, 0.0075, C, {"Head": 1.0})
    # wattle: two drops under the beak
    for sx in (1, -1):
        ellipsoid(m, (0.008 * sx, -0.163, 0.333), (0.009, 0.012, 0.019), C, {"Head": 1.0})
    # eyes
    for sx in (1, -1):
        ellipsoid(m, (0.031 * sx, -0.148, 0.38), (0.008, 0.008, 0.008), E, {"Head": 1.0})
    # wings: drop-shaped plate glued to the flank (the inner side follows the body width), thinning at the tips
    wing = [(-0.075, 0.198, 0.23), (-0.045, 0.172, 0.25), (0.0, 0.16, 0.257), (0.05, 0.166, 0.255),
            (0.095, 0.186, 0.248), (0.13, 0.21, 0.242), (0.152, 0.228, 0.238)]
    for s, sx in (("L", 1), ("R", -1)):
        cols = []
        for i, (y, zb, zt) in enumerate(wing):
            inner = 0.86 * body_halfwidth(body, y, (zb + zt) / 2)
            t = 0.005 + 0.015 * math.sin(math.pi * i / (len(wing) - 1))
            cols.append((y, zb, zt, inner * sx, (inner + t) * sx))
        slab(m, cols, None, None, W, {f"Wing.{s}": 1.0})
    # tail: 3 flat feathers in a fan, the middle one taller
    for x, tipy, tipz, w in ((0.0, 0.235, 0.365, 1.0), (0.034, 0.226, 0.335, 0.9), (-0.034, 0.226, 0.335, 0.9)):
        p0, p3 = Vector((x * 0.4, 0.11, 0.225)), Vector((x, tipy, tipz))
        pts = [p0.lerp(p3, k / 3) + Vector((0, -0.012 * math.sin(math.pi * k / 3), 0.0)) for k in range(4)]
        rad = [(0.017, 0.036 * w), (0.016, 0.042 * w), (0.013, 0.035 * w), (0.008, 0.014 * w)]
        path_loft(m, pts, rad, 4, T, {"Tail": 1.0}, offset=math.pi / 4)
    # legs
    for s, sx in (("L", 1), ("R", -1)):
        x = SIDE_X * sx
        hip, ank, ft = Vector((x, *HIP)), Vector((x, *ANKLE)), Vector((x, *FOOT))
        # feathered thigh (goes up into the body)
        path_loft(m, [hip + Vector((0, -0.005, 0.02)), hip.lerp(ank, 0.5), ank + (ank - hip).normalized() * 0.006],
                  [(0.03, 0.03), (0.026, 0.026), (0.015, 0.015)], 6, F, {f"UpperLeg.{s}": 1.0})
        # yellow shin
        d = (ft - ank).normalized()
        path_loft(m, [ank - d * 0.012, ank.lerp(ft, 0.5), ft + d * 0.002], [(0.0095, 0.0095), (0.0085, 0.0085),
                  (0.008, 0.008)], 6, B, {f"LowerLeg.{s}": 1.0})
        # toes: 3 forward, 1 backward
        for ang, ln in ((-28, 0.045), (0, 0.052), (28, 0.045), (180, 0.022)):
            a = math.radians(ang)
            dvec = Vector((math.sin(a) * sx, -math.cos(a), 0.0))
            p0 = Vector((x, FOOT[0], 0.008))
            p1 = p0 + dvec * ln + Vector((0, 0, -0.002))
            path_loft(m, [p0, p0.lerp(p1, 0.5), p1], [(0.0065, 0.0045), (0.006, 0.0042), (0.004, 0.0035)], 4, B,
                      {f"Foot.{s}": 1.0}, offset=math.pi / 4)
    return m


def material(name, hexa):
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    h = hexa.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    p = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*lin, 1.0)
    p.inputs["Roughness"].default_value = 0.9
    p.inputs["Specular IOR Level"].default_value = 0.0
    mat.diffuse_color = (*lin, 1.0)
    return mat


def make_objects():
    arm_data = bpy.data.armatures.new("ChickenArmature")
    arm = bpy.data.objects.new("ChickenArmature", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name in ORDER:
        head, tail, parent = BONES[name]
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    m = build_mesh()
    me = bpy.data.meshes.new("Chicken")
    me.from_pydata([tuple(v) for v in m.verts], [], m.faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)       # outward normals on each closed piece
    bm.to_mesh(me)
    bm.free()
    for name, hexa in COLORS.items():
        me.materials.append(material(name, hexa))
    for p, mi in zip(me.polygons, m.mats):
        p.material_index = mi
        p.use_smooth = False
    obj = bpy.data.objects.new("Chicken", me)
    bpy.context.collection.objects.link(obj)
    groups = {b: obj.vertex_groups.new(name=b) for b in ORDER}
    for i, w in enumerate(m.weights):
        for b, val in w.items():
            groups[b].add([i], val, "REPLACE")
    obj.parent = arm
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return arm, obj


# ---------- pose ----------

def rot4(q):
    return q.to_matrix().to_4x4()


def rigid(M, rest, q=None):
    """Desired matrix of a bone that moves with the body (M) and rotates q around its own head."""
    h = rest.translation
    loc = Matrix.Translation(h) @ (rot4(q) if q else Matrix.Identity(4)) @ Matrix.Translation(-h)
    return M @ loc @ rest


def aimed(head, rest, new_dir, q_extra=None):
    """Bone with its head at head and its axis pointing to new_dir (minimal rotation from rest)."""
    rest_dir = (rest.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = rest_dir.rotation_difference(new_dir.normalized())
    if q_extra:
        q = q_extra @ q
    r = rest.to_3x3().to_4x4()
    return Matrix.Translation(head) @ rot4(q) @ r


def body_matrix(lift=0.0, pitch=0.0, roll=0.0, yaw=0.0, dy=0.0):
    """Rigid body: tilts (pitch > 0 = beak down), rolls and turns around the hip, rises/falls by lift."""
    r = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(roll, 4, "Y") @ Matrix.Rotation(pitch, 4, "X")
    return Matrix.Translation(PIVOT + Vector((0, dy, lift))) @ r @ Matrix.Translation(-PIVOT)


class Pose:
    def __init__(self, arm):
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.len = {b.name: b.length for b in arm.data.bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}

    def solve(self, M, head_target, head_rot, feet, foot_pitch, wing=(0.0, 0.0), tail=0.0):
        """Desired matrices of all the bones. head_target = desired head base (the neck points there
        and keeps its length); head_rot = absolute head rotation; feet = {side: ankle point}."""
        R, P = self.rest, {}
        P["Body"] = M @ R["Body"]
        nb = M @ R["Neck"].translation
        ndir = (Vector(head_target) - nb).normalized()
        P["Neck"] = aimed(nb, R["Neck"], ndir)
        hb = nb + ndir * self.len["Neck"]
        P["Head"] = Matrix.Translation(hb) @ rot4(head_rot) @ R["Head"].to_3x3().to_4x4()
        P["Tail"] = rigid(M, R["Tail"], Quaternion((1, 0, 0), tail))
        for s, sx in (("L", 1), ("R", -1)):
            P[f"Wing.{s}"] = rigid(M, R[f"Wing.{s}"], Quaternion((0, 1, 0), wing[0] * sx) @
                                   Quaternion((1, 0, 0), wing[1]))
            hip = M @ R[f"UpperLeg.{s}"].translation
            ft = Vector(feet[s])
            l1, l2 = self.len[f"UpperLeg.{s}"], self.len[f"LowerLeg.{s}"]
            d = ft - hip
            dist = d.length
            if dist > (l1 + l2) * 0.998:
                raise RuntimeError(f"perna {s} esticada demais: {dist:.4f} m > {l1 + l2:.4f} m")
            dn = d.normalized()
            pole = Vector((0, 1, 0))                       # the visible joint (ankle) bends backward
            perp = (pole - dn * pole.dot(dn)).normalized()
            ca = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
            a = math.acos(max(-1.0, min(1.0, ca)))
            knee = hip + dn * (l1 * math.cos(a)) + perp * (l1 * math.sin(a))
            P[f"UpperLeg.{s}"] = aimed(hip, R[f"UpperLeg.{s}"], knee - hip)
            P[f"LowerLeg.{s}"] = aimed(knee, R[f"LowerLeg.{s}"], ft - knee)
            P[f"Foot.{s}"] = Matrix.Translation(ft) @ Matrix.Rotation(foot_pitch[s], 4, "X") @ \
                R[f"Foot.{s}"].to_3x3().to_4x4()
        return P

    def basis(self, P):
        out = {}
        for b in ORDER:
            pa = self.parent[b]
            ref = self.rest[b] if pa is None else P[pa] @ self.rest[pa].inverted() @ self.rest[b]
            out[b] = ref.inverted() @ P[b]
        return out


def write_action(arm, name, frames_basis):
    """frames_basis: list (frame, {bone: Matrix}) -> action with location and rotation_quaternion, LINEAR."""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    slot = act.slots.new(id_type="OBJECT", name=arm.name)
    bag = au.action_ensure_channelbag_for_slot(act, slot)
    lin = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
    prev = {}
    table = {b: [] for b in ORDER}
    for f, bas in frames_basis:
        for b in ORDER:
            loc, q, _ = bas[b].decompose()
            if b in prev and prev[b].dot(q) < 0:
                q = -q
            prev[b] = q
            table[b].append((f, loc, q))
    for b in ORDER:
        for path, n, get in (("location", 3, lambda r, i: r[1][i]), ("rotation_quaternion", 4, lambda r, i: r[2][i])):
            for i in range(n):
                fc = bag.fcurves.new(f'pose.bones["{b}"].{path}', index=i, group_name=b)
                rows = table[b]
                fc.keyframe_points.add(len(rows))
                fc.keyframe_points.foreach_set("co", [c for r in rows for c in (r[0], get(r, i))])
                fc.keyframe_points.foreach_set("interpolation", [lin] * len(rows))
                fc.update()
    return act, slot


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def track(keys, f):
    """Interpolates keys [(frame, value or tuple)] with smoothstep between neighbors."""
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            u = smooth((f - f0) / max(f1 - f0, 1e-9))
            if isinstance(v0, (tuple, list)):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return keys[-1][1]


HEAD_BASE = Vector(BONES["Head"][0])
REST_FEET = {"L": Vector((SIDE_X, *FOOT)), "R": Vector((-SIDE_X, *FOOT))}
TIP_OFF = Vector((0, -0.203, 0.354)) - HEAD_BASE          # beak tip relative to the head base


# ---------- actions ----------

WALK_N, WALK_DUTY, WALK_STEP, WALK_LIFT = 16, 10 / 16, 0.10, 0.034


def walk(pose):
    """Walk in place: the planted foot goes backward at constant v (= body speed in the world); the head stays
    still in the world for 5 frames and punches forward in 3 (at each step); body rises on single support and sways."""
    n, duty, L = WALK_N, WALK_DUTY, WALK_STEP
    v = L / (duty * n)                                       # per frame
    out = []
    for f in range(n + 1):
        feet, pitch = {}, {}
        for s, ph in (("L", 0.0), ("R", 0.5)):
            p = (f / n + ph) % 1.0
            x = REST_FEET[s].x
            y_front = HIP[0] - L / 2
            if p < duty:
                y, z, tp = y_front + p / duty * L, FOOT[1], 0.0
            else:
                u = (p - duty) / (1 - duty)
                sw = (p - duty) * n                           # frames since the foot left
                if sw <= 1:                                   # 1st frame in the air: the foot still pushes backward at v
                    y = y_front + L + v * sw
                else:                                         # then goes back forward (Hermite)
                    w = (sw - 1) / ((1 - duty) * n - 1)
                    y0, y1 = y_front + L + v, y_front
                    m = v * ((1 - duty) * n - 1) * 0.6           # leaves and lands already following the ground
                    h00, h10 = 2 * w ** 3 - 3 * w ** 2 + 1, w ** 3 - 2 * w ** 2 + w
                    h01, h11 = -2 * w ** 3 + 3 * w ** 2, w ** 3 - w ** 2
                    y = h00 * y0 + h10 * m + h01 * y1 + h11 * m
                z = FOOT[1] + WALK_LIFT * math.sin(math.pi * u)
                tp = math.radians(40) * math.sin(math.pi * u) ** 1.5      # toes fold in the air
            feet[s], pitch[s] = Vector((x, y, z)), tp
        c = 2 * math.pi * (f - 5) / (n / 2)                   # high in the middle of single support (f 5 and 13)
        lift = -0.009 + 0.004 * math.cos(c)
        roll = math.radians(3.0) * math.sin(2 * math.pi * f / n)
        bp = math.radians(1.5) * math.cos(c)
        M = body_matrix(lift=lift, pitch=bp, roll=roll)
        q = f % (n / 2)                                       # head: still 5 f, punches 3 f
        hold = 5
        if q <= hold:
            off = -v * hold / 2 + v * q
        else:
            off = v * hold / 2 - v * hold * smooth((q - hold) / (n / 2 - hold))
        ht = HEAD_BASE + Vector((0, off - 0.006, -0.004))
        head_rot = Quaternion((0, 0, 1), roll * 0.3)
        wing = (math.radians(2.5) * math.sin(2 * math.pi * f / n), math.radians(1.5) * math.cos(c))
        tail = math.radians(4) * math.cos(c - 0.8)
        out.append((f, pose.basis(pose.solve(M, ht, head_rot, feet, pitch, wing, tail))))
    return out


def idle(pose):
    """Idle: breathes (body rises 2 mm), looks to one side and the other with quick chicken turns."""
    n = 48
    look = [(0, (0, 0, 0)), (7, (0, 0, 0)), (10, (38, 10, 4)), (21, (38, 10, 4)), (24, (-30, -8, -3)),
            (35, (-30, -8, -3)), (38, (0, 0, 0)), (48, (0, 0, 0))]
    out = []
    for f in range(n + 1):
        b = math.sin(2 * math.pi * 2 * f / n)
        M = body_matrix(lift=-0.004 + 0.002 * b, pitch=math.radians(1.0) * b)
        yaw, roll, pitch = (math.radians(a) for a in track(look, f))
        ht = HEAD_BASE + Vector((0, 0.002 * b, 0.003 * math.cos(2 * math.pi * f / n)))
        head_rot = Quaternion((0, 0, 1), yaw) @ Quaternion((0, 1, 0), roll) @ Quaternion((1, 0, 0), -pitch)
        feet = {"L": REST_FEET["L"] + Vector((0, -0.01, 0)), "R": REST_FEET["R"] + Vector((0, 0.01, 0))}
        wing = (math.radians(1.5) * b, 0.0)
        tail = math.radians(2) * math.sin(2 * math.pi * f / n + 1.0)
        out.append((f, pose.basis(pose.solve(M, ht, head_rot, feet, {"L": 0.0, "R": 0.0}, wing, tail))))
    return out


def peck_target(M, psi, tip_z=0.006):
    """Head base for the beak tip to touch the ground with the head tilted psi (neck of fixed length)."""
    nb = M @ Vector(BONES["Neck"][0])
    ln = (Vector(BONES["Neck"][1]) - Vector(BONES["Neck"][0])).length
    off = Matrix.Rotation(psi, 3, "X") @ TIP_OFF
    hz = tip_z - off.z
    dz = nb.z - hz
    if abs(dz) >= ln:
        raise RuntimeError(f"peck: neck cannot reach the ground (short by {abs(dz) - ln:.4f} m)")
    return Vector((0, nb.y - math.sqrt(ln * ln - dz * dz), hz))


def peck(pose):
    """Pecks the ground twice: anticipates (head back), dives accelerating, touches, rises a little, pecks
    again, comes back and settles with a small step of the foot."""
    n = 36
    # (frame, body tilt, head tilt, body drop, 0 = free target / 1 = beak on the ground)
    keys = [(0, (0, 0, 0, 0)), (3, (0, 0, 0, 0)), (6, (-5, -12, 0, 0)), (11, (30, 80, -0.01, 1)),
            (13, (30, 80, -0.01, 1)), (16, (26, 60, -0.008, 0.55)), (19, (30, 80, -0.01, 1)), (21, (30, 80, -0.01, 1)),
            (28, (-3, -4, 0, 0)), (32, (0, 0, 0, 0)), (36, (0, 0, 0, 0))]
    ground = peck_target(body_matrix(lift=-0.01, pitch=math.radians(30)), math.radians(80))
    out = []
    for f in range(n + 1):
        bp, psi, lift, down = track(keys, f)
        M = body_matrix(lift=lift, pitch=math.radians(bp))
        free = HEAD_BASE + Vector((0, 0.01 * min(bp, 0) / 5, 0))
        if down >= 1:
            ht = peck_target(M, math.radians(psi))            # beak exactly on the ground
        else:
            ht = free.lerp(ground, down)
        head_rot = Quaternion((1, 0, 0), math.radians(psi))
        wing = (math.radians(4) * max(bp, 0) / 30, 0.0)
        tail = math.radians(-6) * max(bp, 0) / 30
        out.append((f, pose.basis(pose.solve(M, ht, head_rot, dict(REST_FEET), {"L": 0.0, "R": 0.0}, wing, tail))))
    return out


def check_ground(arm, body, acts):
    """No vertex below the ground in any frame; support foot touching (toes within 4 mm)."""
    scene = bpy.context.scene
    ad = arm.animation_data_create()
    for act, slot in acts:
        ad.action, ad.action_slot = act, slot
        lows = []
        for f in range(int(act.frame_range[0]), int(act.frame_range[1]) + 1):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            oe = body.evaluated_get(dg)
            me = oe.to_mesh()
            lows.append(min((oe.matrix_world @ v.co).z for v in me.vertices))
            oe.to_mesh_clear()
        print(f"chicken: {act.name} lowest vertex {min(lows) * 1000:.1f} a {max(lows) * 1000:.1f} mm")
        if min(lows) < -0.003:
            raise RuntimeError(f"{act.name}: mesh goes into the ground ({min(lows) * 1000:.1f} mm)")
        if max(lows) > 0.004:
            raise RuntimeError(f"{act.name}: no foot on the ground in a frame ({max(lows) * 1000:.1f} mm above)")
    ad.action = None


def main():
    args =sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = FPS, 1.0
    arm, body = make_objects()
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    pose = Pose(arm)
    acts = []
    for name, fn in (("Idle", idle), ("Walk", walk), ("Peck", peck)):
        acts.append(write_action(arm, name, fn(pose)))
    ad = arm.animation_data_create()
    for act, slot in acts:                                  # one NLA strip per action (the exporter finds them)
        tr = ad.nla_tracks.new()
        tr.name = act.name
        st = tr.strips.new(act.name, int(act.frame_range[0]), act)
        st.action_slot = slot
        tr.mute = True
    check_ground(arm, body, acts)
    ad.action, ad.action_slot = acts[0]
    scene.frame_start, scene.frame_end = 0, 48
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "Chicken.fbx"
    bpy.ops.export_scene.fbx(filepath=str(path), object_types={"ARMATURE", "MESH"}, use_selection=False,
                             add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True,
                             bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                             bake_anim_simplify_factor=0.0, bake_anim_step=1.0, primary_bone_axis="Y",
                             secondary_bone_axis="X", apply_unit_scale=True, mesh_smooth_type="FACE")
    if "--blend" in args:
        bpy.ops.wm.save_as_mainfile(filepath=args[args.index("--blend") + 1])
    (OUT / "SOURCE.txt").write_text(
        "Chicken.fbx: low-poly chicken with skeleton (Body, Neck, Head, Tail, Wing.L/R, UpperLeg/LowerLeg/Foot.L/R)\n"
        "and actions Idle, Walk, Peck at 24 fps. Made by us (Ifscape) on 2026-10-25, generated by\n"
        "tools/blender/chicken_model.py (blender -b -P tools/blender/chicken_model.py). CC0 1.0.\n", encoding="utf-8")
    (OUT / "License.txt").write_text("CC0 1.0 Universal (public domain). https://creativecommons.org/publicdomain/zero/1.0/\n",
                                     encoding="utf-8")
    print(f"chicken: {len(body.data.vertices)} vertices, {len(body.data.polygons)} faces, "
          f"actions {[a.name for a, _ in acts]} -> {path}")


main()
