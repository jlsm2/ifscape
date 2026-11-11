"""Low-poly Holstein cow (bacteria-disappeared script), with a "thin" shape key to make it skinny.

Real proportions (docs/blender/model-references.md): withers 1.42 m, barrel 55% of the height,
straight back and high square rump, low wedge-shaped head, ears out to the sides, zigzag hock.
Front along +x, origin on the ground under the center. Body, head (with neck) and tail are separate objects:
the head lowers to eat and the tail sways.
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
from kit import flat

WHITE, BLACK, PINK, HOOF, HORN = "#E9E4DA", "#1E1F24", "#C99A93", "#2A2622", "#D8CDB0"

# Barrel sections (front to back): x, half-width, top, bottom
SECTIONS = [(0.86, 0.20, 1.36, 0.92), (0.72, 0.25, 1.40, 0.82), (0.45, 0.30, 1.42, 0.68),
            (0.10, 0.33, 1.42, 0.62), (-0.25, 0.32, 1.43, 0.66), (-0.50, 0.29, 1.45, 0.76),
            (-0.72, 0.26, 1.46, 0.92), (-0.88, 0.19, 1.43, 1.06), (-0.94, 0.11, 1.38, 1.14)]
RING = 16          # points per section
HIP = 5            # hip-bone section (shows on the skinny cow)
NECK_BASE = Vector((0.80, 0.0, 1.20))
TAIL_HEAD = Vector((-0.92, 0.0, 1.40))
# Black patches: groups of circles (x, z, radius) on the flank plane, per side (+1 = +y). Irregular shapes,
# large, and belly always white (which makes it read "Holstein" and not "zebra").
PATCHES = {1: [(0.70, 1.22, 0.16), (0.54, 1.32, 0.14), (0.60, 1.06, 0.10),
               (0.05, 1.22, 0.20), (-0.16, 1.06, 0.15), (0.16, 1.34, 0.12),
               (-0.70, 1.33, 0.13), (-0.82, 1.20, 0.09)],
           -1: [(0.46, 1.16, 0.18), (0.30, 1.32, 0.13), (0.82, 1.24, 0.09),
                (-0.30, 1.26, 0.21), (-0.50, 1.10, 0.14), (-0.12, 1.02, 0.11)]}
BELLY = 0.13      # white band above the barrel's bottom line
INTERP = 2        # extra rings between two sections (patch resolution)


def _ring(x, hw, top, bot, thin, k_sec):
    """Section ring: super-ellipse (rounded-box look). On the skinny one, bones and spine stand out."""
    mid, half = (top + bot) / 2, (top - bot) / 2
    last = len(SECTIONS) - 1
    pts = []
    for i in range(RING):
        a = 2 * math.pi * i / RING                       # 0 = top, turning toward +y
        s, c = math.sin(a), math.cos(a)
        y = hw * math.copysign(abs(s) ** 0.7, s)
        z = mid + half * math.copysign(abs(c) ** 0.8, c)
        if thin:
            if i == 0:
                z += 0.035                               # spine ridge
            if k_sec == HIP and i in (2, RING - 2):
                z += 0.08                                # hip bones ("coat hanger")
                y *= 1.10
            if k_sec >= last - 1 and i in (2, RING - 2):
                z += 0.04                                # pointed ischia
            if k_sec >= last - 1 and i == 0:
                z -= 0.07                                # tail base sinks: the U becomes a V
        pts.append((x, y, z))
    return pts


def _barrel(thin):
    """Barrel through the sections, with intermediate rings (patches and bones with more resolution)."""
    base = []
    for k, (x, hw, top, bot) in enumerate(SECTIONS):
        if thin:
            hw *= 0.84
            lift = 0.17 if k in (4, 5) else 0.09        # deep flank behind the ribs
            bot += lift if 1 < k < len(SECTIONS) - 1 else 0.03
        base.append(_ring(x, hw, top, bot, thin, k))
    rings = []
    for ra, rb in zip(base, base[1:]):
        for j in range(INTERP + 1):
            u = j / (INTERP + 1)
            rings.append([tuple(pa[c] + (pb[c] - pa[c]) * u for c in range(3)) for pa, pb in zip(ra, rb)])
    rings.append(base[-1])
    return kit.loft_geo(rings)


def _limbs():
    """Volume of the thigh (behind) and the shoulder (in front) outside the barrel: removes the table-with-legs look."""
    parts = []
    for side in (1, -1):
        parts.append(kit.tube_geo([(-0.60, side * 0.17, 1.28), (-0.60, side * 0.19, 1.05), (-0.54, side * 0.18, 0.80)],
                                  (0.14, 0.17, 0.11), n=7))
        parts.append(kit.tube_geo([(0.64, side * 0.15, 1.24), (0.66, side * 0.17, 1.00), (0.63, side * 0.17, 0.74)],
                                  (0.11, 0.13, 0.09), n=7))
    return parts


def _legs():
    front = [[(0.62, 0.0, 0.95), (0.62, 0.0, 0.48), (0.63, 0.0, 0.12)],
             [(0.62, 0.0, 0.12), (0.64, 0.0, 0.0)]]
    hind = [[(-0.55, 0.0, 0.95), (-0.70, 0.0, 0.50), (-0.66, 0.0, 0.12)],
            [(-0.66, 0.0, 0.12), (-0.66, 0.0, 0.0)]]
    legs, hooves = [], []
    for side in (0.17, -0.17):
        for (leg, hoof), radii in ((front, (0.085, 0.055, 0.05)), (hind, (0.11, 0.058, 0.05))):
            pts = [(x, side, z) for x, _, z in leg]
            legs.append(kit.tube_geo(pts, radii, n=6))
            hpts = [(x, side, z) for x, _, z in hoof]
            hooves.append(kit.tube_geo(hpts, (0.06, 0.068), n=6))
    return legs, hooves


def _udder():
    parts = [kit._ico_geo(1.0, (-0.42, 0.0, 0.66), (0.20, 0.17, 0.13))]
    for dx in (0.06, -0.06):
        for dy in (0.06, -0.06):
            parts.append(kit.tube_geo([(-0.42 + dx, dy, 0.56), (-0.42 + dx, dy, 0.47)], (0.022, 0.016), n=5))
    return parts


def _patch_mats(verts, faces, floor):
    """Material per face: 1 (black) inside the patches on the face's side, 0 (white) outside and on the belly."""
    out = []
    for face in faces:
        cx, cy, cz = (sum(verts[i][c] for i in face) / len(face) for c in range(3))
        side = 1 if cy >= 0 else -1
        black = cz > floor + BELLY and any((cx - px) ** 2 + (cz - pz) ** 2 < r * r for px, pz, r in PATCHES[side])
        out.append(int(black))
    return out


def _mesh(name, geo, mats, face_mats):
    obj = kit.mesh_object(name, geo[0], geo[1], mats, face_mats=face_mats)
    kit.fix_normals(obj)
    return obj


def body_object(name, m):
    """Whole body minus head and tail; 'thin' shape key (same topology, other positions)."""
    def geo(thin):
        legs, hooves = _legs()
        groups = [("coat", [_barrel(thin), *_limbs()]), ("white", legs), ("hoof", hooves),
                  ("pink", _udder())]
        parts = [g for _, gs in groups for g in gs]
        kinds = [kind for kind, gs in groups for _ in gs]
        verts, faces, owner = kit.merge(*parts)
        return verts, faces, [kinds[k] for k in owner]

    verts, faces, kinds = geo(False)
    patch = _patch_mats(verts, faces, floor=0.62)
    index = {"white": 0, "hoof": 2, "pink": 3}
    face_mats = [patch[i] if kind == "coat" else index[kind] for i, kind in enumerate(kinds)]
    obj = _mesh(name, (verts, faces), [m.white, m.black, m.hoof, m.pink], face_mats)
    obj.shape_key_add(name="Basis")
    thin = obj.shape_key_add(name="thin")
    thin.value = 0.0                                     # in Blender 5.2 the new key is born at 1
    for i, v in enumerate(geo(True)[0]):
        thin.data[i].co = v
    return obj


def head_object(name, m):
    """Neck + head with origin at the base of the neck (rotates in y to lower to the trough)."""
    poll, muzzle = Vector((1.12, 0, 1.18)), Vector((1.50, 0, 0.80))
    d = (muzzle - poll).normalized()
    neck = kit.tube_geo([tuple(NECK_BASE), (0.98, 0, 1.16), tuple(poll - d * 0.04)], (0.24, 0.19, 0.15), n=7)
    dewlap = kit.tube_geo([(0.86, 0, 1.00), (1.02, 0, 0.98)], (0.07, 0.04), n=4, squash=0.4, twist=math.pi / 2)
    head = kit.tube_geo([tuple(poll - d * 0.06), tuple(poll + d * 0.08), tuple(poll + d * 0.30),
                         tuple(muzzle - d * 0.05)], (0.10, 0.135, 0.115, 0.10), n=6, squash=1.1)
    snout = kit.tube_geo([tuple(muzzle - d * 0.07), tuple(muzzle + d * 0.07)], (0.115, 0.105), n=6, squash=1.15)
    blaze = kit.tube_geo([tuple(poll + d * 0.04 + Vector((0.035, 0, 0.06))),
                          tuple(muzzle - d * 0.06 + Vector((0.075, 0, 0.04)))], (0.045, 0.04), n=4, squash=0.35)
    parts, kinds = [neck, dewlap, head, snout, blaze], [1, 1, 1, 3, 0]
    for side in (1, -1):
        ear0 = poll + Vector((0.0, side * 0.10, -0.03))
        ear1 = ear0 + Vector((-0.02, side * 0.22, -0.06))
        parts.append(kit.tube_geo([tuple(ear0), tuple((ear0 + ear1) / 2), tuple(ear1)], (0.03, 0.065, 0.02),
                                  n=4, squash=0.35))
        kinds.append(1)
        horn0 = poll + Vector((-0.02, side * 0.10, 0.06))
        parts.append(kit.tube_geo([tuple(horn0), tuple(horn0 + Vector((0.02, side * 0.07, 0.07)))], (0.03, 0.008), n=5))
        kinds.append(4)
        eye = poll + d * 0.20 + Vector((0.0, side * 0.125, 0.04))
        parts.append(kit._ico_geo(0.026, tuple(eye)))
        kinds.append(2)
    verts, faces, owner = kit.merge(*parts)
    verts = [tuple(Vector(v) - NECK_BASE) for v in verts]
    mats = [m.white, m.black, m.hoof, m.pink, m.horn]
    obj = _mesh(name, (verts, faces), mats, [kinds[k] for k in owner])
    obj.location = NECK_BASE
    return obj


def tail_object(name, m):
    pts = [(0.0, 0, 0.0), (-0.04, 0, -0.30), (-0.03, 0, -0.62), (-0.02, 0, -0.78)]
    tail = kit.tube_geo(pts, (0.035, 0.025, 0.02, 0.018), n=5)
    tuft = kit._ico_geo(1.0, (-0.02, 0, -0.86), (0.06, 0.06, 0.11))
    verts, faces, owner = kit.merge(tail, tuft)
    obj = _mesh(name, (verts, faces), [m.white, m.black], owner)
    obj.location = TAIL_HEAD
    return obj


_MATS = None


def materials():
    global _MATS
    if _MATS is None:
        _MATS = SimpleNamespace(white=flat("CowWhite", WHITE), black=flat("CowBlack", BLACK), pink=flat("CowPink", PINK),
                                hoof=flat("CowHoof", HOOF), horn=flat("CowHorn", HORN))
    return _MATS


def cow(name, location, heading=0.0, scale=1.0):
    """Builds a cow. Returns SimpleNamespace(root, body, head, tail); root is an Empty (position and direction)."""
    m = materials()
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = (0, 0, heading)
    root.scale = (scale,) * 3
    body, head, tail = body_object(name + "Body", m), head_object(name + "Head", m), tail_object(name + "Tail", m)
    for part in (body, head, tail):
        part.parent = root
    return SimpleNamespace(root=root, body=body, head=head, tail=tail)


def set_thin(c, value, frame):
    kb = c.body.data.shape_keys.key_blocks["thin"]
    kb.value = value
    kb.keyframe_insert("value", frame=frame)


def head_down(c, angle, frame):
    """Lowers (positive angle) the head by rotating the neck at the base."""
    c.head.rotation_euler = (0, math.radians(angle), 0)
    c.head.keyframe_insert("rotation_euler", frame=frame)
