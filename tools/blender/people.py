"""Articulated people who really walk (pangaea-never-split, scene 08).

Torso and head in one object; legs and arms are objects with the pivot at the hip and shoulder, children of a root.
The walk uses the same principle as the sauropods (dinos.walk): in stance the foot stays still on the ground (the
leg angle comes from the foot position), in swing the leg shortens and the foot lifts; the arms swing opposite to the legs.
Front along +y, feet at z = 0, no face.
"""

import math
from types import SimpleNamespace

import bpy

import dinos
import kit

HIP_Z = 0.92
SHOULDER_Z = 1.42
LEG_LEN = 0.88
DUTY = 0.6                 # fraction of the cycle with the foot on the ground


def _ring(z, hw, hd, n=8, dy=0.0):
    return [(hw * math.cos(2 * math.pi * i / n), dy + hd * math.sin(2 * math.pi * i / n), z) for i in range(n)]


def _limb(points, radii, n=6):
    """Vertical tube (leg or arm) without twist: ring locked to the x axis."""
    from mathutils import Vector
    pts = [Vector(p) for p in points]
    side = Vector((1, 0, 0))
    rings = []
    for k, (p, r) in enumerate(zip(pts, radii)):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        up = t.cross(side).normalized()
        rings.append([tuple(p + side * (r * math.cos(2 * math.pi * i / n)) + up * (r * math.sin(2 * math.pi * i / n)))
                      for i in range(n)])
    return kit.loft_geo(rings)


def walker(name, location, skin, hide, heading=0.0, spear=None):
    """One person: root (empty) + torso with head + articulated legs and arms. 'hide' is the animal-skin color at the
    waist and chest; 'spear' (material) puts a spear in the right hand."""
    root = bpy.data.objects.new(name, None)
    root.location, root.rotation_euler = location, (0, 0, heading)
    bpy.context.collection.objects.link(root)
    skin_mat, hide_mat = kit.flat(f"{name}Skin", skin), kit.flat(f"{name}Hide", hide)
    torso = kit.loft_geo([_ring(0.86, 0.15, 0.1), _ring(1.0, 0.16, 0.11), _ring(1.18, 0.17, 0.11),
                          _ring(1.36, 0.2, 0.11), _ring(1.46, 0.19, 0.1), _ring(1.53, 0.06, 0.06)])
    head = kit._ico_geo(0.115, (0, 0.01, 1.66), (0.9, 0.95, 1.1))
    v, f, owner = kit.merge(torso, head)
    mats = [1 if o == 0 and (sum(v[i][2] for i in face) / len(face) < 1.02 or
                             1.2 < sum(v[i][2] for i in face) / len(face) < 1.4) else 0 for face, o in zip(f, owner)]
    body = dinos._part(f"{name}Body", (v, f), [skin_mat, hide_mat], root, face_mats=mats)
    legs, arms = {}, {}
    for side, sx in (("L", -1), ("R", 1)):
        hip = (sx * 0.09, 0, HIP_Z)
        leg = kit.merge(_limb([hip, (sx * 0.09, 0.02, 0.5), (sx * 0.09, 0, 0.07)], [0.075, 0.06, 0.045]),
                        kit._box_geo(0.09, 0.22, 0.07, sx * 0.09 - 0.045, -0.05, 0.0))[:2]
        legs[side] = dinos._part(f"{name}Leg{side}", leg, [skin_mat], root, pivot=hip)
        sh = (sx * 0.22, 0, SHOULDER_Z)
        arm = _limb([sh, (sx * 0.24, -0.02, 1.16), (sx * 0.25, 0.03, 0.92)], [0.055, 0.045, 0.04])
        arms[side] = dinos._part(f"{name}Arm{side}", arm, [skin_mat], root, pivot=sh)
    if spear is not None:
        geo = kit._prism_geo(4, 0.02, 0.012, 1.6)
        s = kit.mesh_object(f"{name}Spear", *geo[:2], [spear], location=(0.03, 0.06, -0.5))
        s.parent = arms["R"]
        s.rotation_euler = (math.radians(-10), 0, 0)
    return SimpleNamespace(root=root, body=body, legs=legs, arms=arms)


def _foot(u, reach):
    """Foot ahead of the hip (m) and how much it lifts, at cycle fraction u (stance: moves back with the ground)."""
    if u < DUTY:
        return reach - 2 * reach * u / DUTY, 0.0
    v = (u - DUTY) / (1 - DUTY)
    e = v * v * (3 - 2 * v)
    return -reach + 2 * reach * e, math.sin(math.pi * v)


def walk(p, f0, f1, speed, ground_z, cycle=1.05, phase=0.0, fps=30):
    """Walk along local +y with the foot planted; arm and torso swing; keys every 2 frames, LINEAR."""
    from mathutils import Vector
    start = p.root.location.copy()
    h = p.root.rotation_euler.z
    fwd = Vector((-math.sin(h), math.cos(h), 0))
    reach = speed * cycle * DUTY / 2
    for f in range(f0, f1 + 1, 2):
        t = (f - f0) / fps
        for side, o in (("L", 0.0), ("R", 0.5)):
            u = (t / cycle + o + phase) % 1.0
            y, lift = _foot(u, reach)
            kit.key(p.legs[side], "rotation_euler", (math.asin(max(-0.9, min(0.9, y / LEG_LEN))), 0, 0), f)
            kit.key(p.legs[side], "scale", (1, 1, 1 - 0.12 * lift), f)
            kit.key(p.arms[side], "rotation_euler", (-1.1 * math.asin(max(-0.9, min(0.9, y / LEG_LEN))), 0, 0), f)
        pos = start + fwd * speed * t
        pos.z = ground_z(pos.x, pos.y) + 0.025 * math.cos(4 * math.pi * (t / cycle + phase))
        kit.key(p.root, "location", tuple(pos), f)
        kit.key(p.body, "rotation_euler", (0, 0, math.radians(4) * math.sin(2 * math.pi * (t / cycle + phase))), f)
    for obj in (p.root, p.body, *p.legs.values(), *p.arms.values()):
        for fc in dinos._fcurves(obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
