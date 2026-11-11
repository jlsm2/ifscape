"""Prehistoric clothing over Quaternius's Man and Woman Casual (pangaea-never-split, scene 08: Homo sapiens
300,000 years ago walking across the plain).

Chosen approach: dress the mesh that already has a rig and the measured walk (1.25 m/s, planted foot), instead of
swapping to the Universal Base Characters. The UBC comes textured (a "superhero" body with color map,
normal and roughness); swapping would require repainting the texture, re-measuring the foot speed and matching 43
animations to another skeleton, only to end up with the same doll. Here everything is the asset's own mesh:
- per-face repaint (material per face on each person's mesh copy): t-shirt becomes a one-shoulder tunic
  (or bare chest), shorts and pants become a loincloth or tunic hem with a cut-out edge, shoes and socks become bare
  feet, irregular dark patches on the animal skin;
- relief by extruding regions of the mesh itself (short cape on the shoulders, long hair down to the nape, beard):
  the new vertices inherit the bone weights from where they came, so they bend with the body and do not clip
  through anything in the walk; the extrusion walls close the edge (no gap or thin shell);
- the bundle on the back is geometry added to the same mesh with full weight on the Torso bone.
Nothing is a loose object: it switches on and off with the character.

Costume references (low-poly, flat colors): "Caveman" and "Prehistoric" from the Quaternius and Poly
Pizza packs; reconstructions of Middle Paleolithic hunter-gatherers (animal skin tied on one shoulder, short
cape, bare feet). Body proportions: the asset's own (1.58 to 1.85 m in the set).
"""

import math
import random

import bmesh
from mathutils import Vector

import rigs

LEATHER = "#3A2A1E"         # leather ties of the bundle
EYES = "#241A14"
HEAD_GROUPS = ("Head", "Neck")
SKIN, HIDE, PATCH_I, HAIR, EYE, CAPE, CAPE_PATCH, LEATHER_I = range(8)


def _shade(hex_color, k):
    """Same color, darker (k < 1): the animal-skin patch is the same tone, not a black hole."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % (int(r * k), int(g * k * 0.95), int(b * k * 0.9))


def _lum(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _wave(p, seed, f=38.0):
    """Smooth deterministic noise (-1..1) on the normalized coordinates: irregular hems and patches."""
    return (math.sin(p.x * f + seed) + math.sin(p.y * f * 1.3 + 2.1 * seed) + math.sin(p.z * f * 0.9 + 3.7 * seed)) / 3


class _Frame:
    """Normalized coordinates of the template: x to the character's left, y to the back (the asset faces
    -y), h = height / body height (0 at the feet, 1 at the top). T-pose: arms horizontal at h ~0.8."""

    def __init__(self, rig):
        t = rig.t
        m = t.meshes[0]
        self.M = m.matrix_world.copy()
        self.Minv = self.M.inverted()
        self.origin = t.arm.matrix_world.translation.copy()
        self.s = t.base_scale
        self.lo = t.box.lo.z
        self.H = t.box.size.z
        self.meter = self.H / 1.7 * self.s / self.M.to_scale().x      # 1 m (on a 1.7 m body) in local units

    def norm(self, co):
        p = (self.M @ co - self.origin) / self.s
        return Vector((p.x / self.H, p.y / self.H, (p.z - self.lo) / self.H))

    def local(self, n):
        p = Vector((n.x * self.H, n.y * self.H, n.z * self.H + self.lo)) * self.s + self.origin
        return self.Minv @ p


def _dominant(face, deform, names):
    acc = {}
    for v in face.verts:
        for g, w in v[deform].items():
            acc[g] = acc.get(g, 0.0) + w
    return names.get(max(acc, key=acc.get)) if acc else None


def _strap_line(x):
    """Edge of the one-shoulder tunic: from the base of the neck on the left side to the right armpit."""
    return 0.70 + (x + 0.12) / 0.18 * 0.16


def _cloth_class(base, g, c, look):
    if base in ("Hair", "HairBase"):
        return HAIR
    if base == "Eyes" and g in HEAD_GROUPS:
        return EYE
    if base in ("Eyes", "Shoes", "Socks", "Skin"):
        return SKIN                                            # shoes and socks become bare feet
    if base == "Shirt":
        if look["top"] == "bare":
            return SKIN
        if g in ("UpperArm.R", "LowerArm.R") or (c.x < 0.06 and c.z > _strap_line(c.x)):
            return SKIN
        return HIDE
    if base == "Pants":
        if look["top"] == "tunic":                             # slanted, jagged hem: tied skin, not shorts
            hem = 0.395 + 0.05 * (c.x + 0.1) / 0.2 + 0.03 * _wave(c, look["seed"], 90)
        else:                                                  # loincloth: cut out at the sides
            hem = 0.445 + 0.055 * min(max((abs(c.x) - 0.035) / 0.06, 0.0), 1.0) + 0.015 * _wave(c, look["seed"], 90)
        return HIDE if c.z > hem else SKIN
    return SKIN


def _patches(faces, centers, rng, n, seed, mat):
    """Two or three dark patches with an irregular outline (animal skin), no stripes."""
    if not faces:
        return
    picks = rng.sample(range(len(faces)), min(n, len(faces)))
    spots = [(centers[faces[i]], rng.uniform(0.035, 0.055)) for i in picks]
    for f in faces:
        c = centers[f]
        for p, r in spots:
            if (c - p).length < r * (1 + 0.35 * _wave(c, seed + 5, 90)):
                f.material_index = mat


def _cape_face(g, c, cls, seed):
    if cls in (HAIR, EYE) or g in ("Head",) or c.z > 0.845:
        return False
    if g in ("UpperArm.L", "UpperArm.R"):
        return abs(c.x) < 0.155 and c.z > 0.80                 # only the top of the shoulder (outside the armpit)
    if g not in ("Torso", "Shoulder.L", "Shoulder.R", "Neck", "Abdomen"):
        return False
    if c.y > 0.0:                                              # back: goes down to the shoulder blade, cut-out edge
        return c.z > 0.675 + 0.03 * _wave(c, seed, 45) and (abs(c.x) < 0.105 or c.z > 0.79)
    return c.z > 0.775 + 0.015 * _wave(c, seed, 45) and abs(c.x) > 0.05   # front: only the top of the shoulders


def _hair_face(g, c, cls, look):
    if cls == HAIR:
        return True
    if cls == EYE or g not in ("Head", "Neck", "Torso"):
        return False
    low = look["hair_low"] + 0.015 * _wave(c, look["seed"] + 2, 70)
    if g == "Head":
        return (c.y > 0.0 and c.z > 0.88) or c.z > look["hairline"]     # nape, sides and fringe
    return c.y > 0.03 and c.z > low and abs(c.x) < (0.07 if c.z > 0.85 else 0.055)


def _beard_face(g, c, cls):
    if g not in HEAD_GROUPS or cls in (HAIR, EYE):
        return False
    if g == "Neck":
        return c.y < -0.015 and c.z > 0.865 and abs(c.x) < 0.045       # under the chin
    return c.y < 0.005 and 0.87 < c.z < (0.918 if abs(c.x) < 0.03 else 0.94)


def _raise(bm, faces, mat, thick, fr, rough, seed, deform=None):
    """Extrudes the region outward (average normal by position, without tearing at the seams), with the thickness varying
    slightly per vertex (rough) so the hair and animal skin do not look smooth. The walls take the piece's
    material; the top keeps the color (and patches) already painted."""
    if not faces:
        return
    key = lambda co: (round(co.x, 6), round(co.y, 6), round(co.z, 6))
    normals = {}
    for f in faces:
        for v in f.verts:
            normals[key(v.co)] = normals.get(key(v.co), Vector()) + f.normal * f.calc_area()
    res = bmesh.ops.extrude_face_region(bm, geom=list(faces), use_keep_orig=False)
    new_verts = {e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)}
    for v in new_verts:
        n = normals.get(key(v.co))
        if n is None or n.length == 0:
            continue
        c = fr.norm(v.co)
        d = thick * (1 + rough * _wave(c, seed, 160))
        v.co += n.normalized() * d * fr.meter
    for f in (e for e in res["geom"] if isinstance(e, bmesh.types.BMFace)):
        if not all(v in new_verts for v in f.verts):
            f.material_index = mat
        f.smooth = False


def _bundle(bm, fr, deform, torso):
    """Bundle of rolled skin on the back, from the left shoulder to the right side of the waist, attached to the Torso."""
    a, b = Vector((0.055, 0.118, 0.80)), Vector((-0.06, 0.118, 0.62))
    axis = (b - a).normalized()
    side = axis.cross(Vector((0, 1, 0))).normalized()
    back = side.cross(axis).normalized()
    r, n = 0.032, 7
    rings = []
    for k, (u, rr) in enumerate(((0.0, 0.8), (0.06, 1.0), (0.2, 1.0), (0.24, 1.12), (0.3, 1.0), (0.7, 1.0),
                                 (0.76, 1.12), (0.82, 1.0), (0.94, 1.0), (1.0, 0.8))):
        c = a.lerp(b, u)
        ring = []
        for i in range(n):
            ang = 2 * math.pi * i / n
            p = c + (side * math.cos(ang) + back * math.sin(ang)) * r * rr
            v = bm.verts.new(fr.local(p))
            v[deform][torso] = 1.0
            ring.append(v)
        rings.append(ring)
    for k in range(len(rings) - 1):
        band = k in (2, 3, 5, 6)                               # two leather ties
        for i in range(n):
            f = bm.faces.new((rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]))
            f.material_index = LEATHER_I if band else CAPE
            f.smooth = False
    for ring in (rings[0], rings[-1]):
        f = bm.faces.new(ring)
        f.material_index = CAPE
        f.smooth = False
    made = list({f for ring in rings for v in ring for f in v.link_faces})
    bmesh.ops.recalc_face_normals(bm, faces=made)


def dress(rig, look):
    """Dresses a person (rig from rigs.spawn, Man or Woman Casual). look: skin, hide, cape (color or None), hair,
    beard, bundle, top ('tunic' or 'bare'), hair_low (normalized height where the hair ends), seed."""
    obj = rig.meshes[0]
    obj.data = obj.data.copy()
    me = obj.data
    names = {g.index: g.name for g in obj.vertex_groups}
    old = [m.name.split(".")[0] if m else "" for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)                                           # before swapping the materials (clear resets the indices)
    me.materials.clear()
    hide = look["hide"]
    if abs(_lum(hide) - _lum(look["skin"])) < 0.12:          # tunic that would vanish into the skin: swap to light ochre
        hide = "#A88250" if _lum(look["skin"]) < 0.45 else "#4A3424"
    cape = look["cape"] or "#A8834F"
    for col in (look["skin"], hide, _shade(hide, 0.68), look["hair"], EYES, cape, _shade(cape, 0.7), LEATHER):
        me.materials.append(rigs.flat_mat(col))
    fr = _Frame(rig)
    rng = random.Random(look["seed"])
    bm.normal_update()
    deform = bm.verts.layers.deform.active
    info = {}
    for f in bm.faces:
        g = _dominant(f, deform, names)
        c = fr.norm(f.calc_center_median())
        cls = _cloth_class(old[f.material_index], g, c, look)
        f.material_index = cls
        info[f] = (g, c, cls)
    centers = {f: c for f, (g, c, cls) in info.items()}
    _patches([f for f in bm.faces if f.material_index == HIDE], centers, rng, 3, look["seed"], PATCH_I)
    hair = [f for f, (g, c, cls) in info.items() if _hair_face(g, c, cls, look)]
    beard = [f for f, (g, c, cls) in info.items() if look["beard"] and _beard_face(g, c, cls) and f not in hair]
    taken = set(hair) | set(beard)
    cape = [f for f, (g, c, cls) in info.items() if look["cape"] and f not in taken and _cape_face(g, c, cls, look["seed"])]
    for f in hair + beard:
        f.material_index = HAIR
    for f in cape:
        f.material_index = CAPE
    _patches(cape, centers, rng, 2, look["seed"] + 11, CAPE_PATCH)
    _raise(bm, cape, CAPE, 0.022, fr, 0.35, look["seed"])
    _raise(bm, beard, HAIR, 0.014, fr, 0.6, look["seed"] + 3)
    _raise(bm, hair, HAIR, 0.022, fr, 0.7, look["seed"] + 7)
    if look["bundle"]:
        _bundle(bm, fr, deform, obj.vertex_groups["Torso"].index)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return obj
