"""Rigid objects of technology-disappeared, made from vertices: grocery sack, loaded bicycle, hoe,
spade, two-wheel cart, flint, steel knife, flaked stone, pile of grass and twigs.

Real proportions: 25 kg grain sack ~0.45 x 0.7 m; bicycle 26" rim (0.66 m wheel), wheelbase 1.05 m,
handlebar at ~1.0 m; hoe with 1.4 m handle and 15 cm blade; light two-wheel cart (1.2 m wheels, 1.6 x 1.1 m
box, 2.4 m shafts); 20 cm knife; ~6 cm flint; Lomekwi flake of 5 to 10 cm (gray stone,
sharp edge, face with flaking scars).
"""

import math
import random

import bpy
from mathutils import Euler, Matrix, Vector

import kit
from town_set import mat


def _obj(name, parts, mats, face_mats=None, location=(0, 0, 0)):
    v, f, owner = kit.merge(*parts)
    obj = kit.mesh_object(name, v, f, mats, location, face_mats=face_mats or owner)
    return kit.fix_normals(obj)


def sack(name, size=(0.42, 0.62, 0.3), color="#B8A27A"):
    """Bulging cloth sack (flattened icosphere) with the mouth tied; origin at the center."""
    sx, sy, sz = size
    body = kit._ico_geo(1.0, (0, 0, 0), (sx / 2, sy / 2, sz / 2))
    neck = kit._prism_geo(6, 0.07, 0.05, 0.1, oz=0, ox=0, oy=0)
    neck = ([(x, y + sy / 2 - 0.02, z) for x, z, y in [(p[0], p[1], p[2]) for p in neck[0]]], neck[1])
    return _obj(name, [body, neck], [mat(f"Sack{color}", color), mat("SackTie", "#6B5A44")])


def wheel_geo(r, width, spokes=8, rim=0.035, hub=0.05):
    """Wheel in the yz plane (x axis): ring rim, spokes and hub."""
    n, parts = 20, []
    outer = [(0, r * math.cos(2 * math.pi * k / n), r + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for k in range(n):
        a, b = outer[k], outer[(k + 1) % n]
        mid_r = r - rim
        ia = (0, mid_r * math.cos(2 * math.pi * k / n), r + mid_r * math.sin(2 * math.pi * k / n))
        ib = (0, mid_r * math.cos(2 * math.pi * (k + 1) / n), r + mid_r * math.sin(2 * math.pi * (k + 1) / n))
        v = [(x - width / 2, y, z) for x, y, z in (a, b, ib, ia)] + [(x + width / 2, y, z) for x, y, z in (a, b, ib, ia)]
        f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        parts.append((v, f))
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        parts.append(kit.tube_geo([(0, 0, r), (0, (r - rim) * math.cos(a), r + (r - rim) * math.sin(a))],
                                  [0.012 * (r / 0.33), 0.01 * (r / 0.33)], n=4))
    parts.append(kit._prism_geo(8, hub, hub, width * 1.6, oz=0, ox=0, oy=0))
    parts[-1] = ([(z - width * 0.8, y, x + r) for x, y, z in parts[-1][0]], parts[-1][1])
    return parts


def _wheel_obj(name, r, width, color, spokes=8):
    parts = wheel_geo(r, width, spokes)
    m = mat(f"Wheel{color}", color, rough=0.8)
    v, f, _ = kit.merge(*parts)
    v = [(x, y, z - r) for x, y, z in v]                   # origem no eixo
    obj = kit.mesh_object(name, v, f, [m])
    return kit.fix_normals(obj)


def bicycle(name, color="#3F5A73"):
    """Bicycle facing +y, resting on the ground (z = 0), with two sacks on the rack and one on the frame.
    Returns (root, wheels, grip points in root space)."""
    r = 0.33
    frame_m, dark = mat(f"Bike{color}", color, rough=0.6), mat("BikeDark", "#1E2228", rough=0.7)
    rear, front = Vector((0, -0.52, r)), Vector((0, 0.53, r))
    crank = Vector((0, -0.05, 0.3))
    seat = Vector((0, -0.2, 0.82))
    head = Vector((0, 0.42, 0.86))
    bars = []
    for a, b in ((rear, crank), (crank, seat), (seat, head), (crank, head), (rear, seat), (head, front)):
        bars.append(kit.tube_geo([tuple(a), tuple(b)], [0.022, 0.022], n=5))
    bars.append(kit.tube_geo([tuple(head), (0, 0.4, 1.0)], [0.02, 0.02], n=5))
    bars.append(kit.tube_geo([(-0.28, 0.38, 1.0), (0.28, 0.38, 1.0)], [0.018, 0.018], n=5))
    seat_g = kit._box_geo(0.13, 0.24, 0.05, -0.065, -0.32, 0.83)
    rack = kit._box_geo(0.3, 0.42, 0.03, -0.15, -0.72, 0.66)
    root = _obj(name, [*bars, seat_g, rack], [frame_m, frame_m, dark], face_mats=None)
    for poly in root.data.polygons:
        poly.material_index = 0
    wheels = []
    for k, c in enumerate((rear, front)):
        w = _wheel_obj(f"{name}Wheel{k}", r, 0.045, "#1E2228", spokes=10)
        w.parent = root
        w.location = c
        w.rotation_mode = "XYZ"
        wheels.append((w, r))
    for k, (loc, rot, size) in enumerate((((0.0, -0.55, 0.86), (0, 0, 0.1), (0.36, 0.5, 0.26)),
                                          ((0.0, -0.62, 1.08), (0.2, 0, -0.1), (0.32, 0.46, 0.22)),
                                          ((0.0, 0.1, 0.62), (math.pi / 2, 0, 0), (0.2, 0.48, 0.22)))):
        s = sack(f"{name}Sack{k}", size, ("#B8A27A", "#A8946C", "#C2B08A")[k])
        s.parent = root
        s.location, s.rotation_euler = loc, rot
    grips = {"L": Vector((0.24, 0.38, 1.0)), "R": Vector((-0.24, 0.38, 1.0))}
    return root, wheels, grips


def hoe(name):
    """Hoe: 1.4 m handle along +z from the origin (at the bottom end is the blade, facing +y)."""
    wood, steel = mat("ToolWood", "#8A6A44"), mat("ToolSteel", "#5E6672", rough=0.6)
    handle = kit._prism_geo(6, 0.018, 0.016, 1.45, oz=0.0)
    blade = kit._box_geo(0.16, 0.02, 0.15, -0.08, 0.0, -0.13)
    neck = kit._box_geo(0.03, 0.06, 0.03, -0.015, -0.02, -0.02)
    return _obj(name, [handle, blade, neck], [wood, steel, steel])


def shovel(name):
    wood, steel = mat("ToolWood", "#8A6A44"), mat("ToolSteel", "#5E6672", rough=0.6)
    handle = kit._prism_geo(6, 0.018, 0.016, 1.2, oz=0.25)
    grip = kit._box_geo(0.14, 0.03, 0.03, -0.07, -0.015, 1.45)
    blade = kit._box_geo(0.22, 0.03, 0.28, -0.11, -0.015, 0.0)
    return _obj(name, [handle, grip, blade], [wood, wood, steel])


def cart(name):
    """Two-wheel cart: plank box, shafts forward (+y), 1.2 m wheels. Origin on the axle, on the ground."""
    wood, dark = mat("CartWood", "#8A6A44"), mat("CartDark", "#5A4632")
    parts = [kit._box_geo(1.1, 1.6, 0.06, -0.55, -0.8, 0.72)]
    for x in (-0.58, 0.52):
        parts.append(kit._box_geo(0.06, 1.6, 0.42, x, -0.8, 0.78))
    for y in (-0.82, 0.76):
        parts.append(kit._box_geo(1.16, 0.06, 0.42, -0.58, y, 0.78))
    for x in (-0.45, 0.45):
        parts.append(kit.tube_geo([(x, 0.6, 0.78), (x * 0.75, 2.9, 0.95)], [0.04, 0.035], n=5))
    body = _obj(name, parts, [wood, wood, wood, wood, wood, dark, dark])
    for k, x in enumerate((-0.68, 0.68)):
        w = _wheel_obj(f"{name}Wheel{k}", 0.6, 0.07, "#5A4632", spokes=10)
        w.parent = body
        w.location = (x, 0, 0.6)
        w.rotation_mode = "XYZ"
    load = [sack(f"{name}Load{k}", (0.4, 0.6, 0.3), ("#B8A27A", "#A8946C", "#C2B08A")[k % 3]) for k in range(3)]
    for k, s in enumerate(load):
        s.parent = body
        s.location = (-0.25 + 0.5 * (k % 2), -0.4 + 0.5 * k, 0.95)
    veg = kit._ico_geo(1.0, (0, 0.35, 0.92), (0.4, 0.25, 0.18))
    greens = _obj(f"{name}Greens", [veg], [mat("Greens", "#4C7A3E")])
    greens.parent = body
    return body


def flint(name):
    """Flint: dark stone with irregular facets (~6 cm)."""
    rnd = random.Random(11)
    v, f = kit._ico_geo(1.0, (0, 0, 0), (0.035, 0.025, 0.022))
    v = [(x * rnd.uniform(0.8, 1.15), y * rnd.uniform(0.8, 1.15), z * rnd.uniform(0.8, 1.1)) for x, y, z in v]
    return _obj(name, [(v, f)], [mat("Flint", "#3A3A40", rough=0.55)])


def knife(name):
    """20 cm steel knife: light blade (back up) and wooden handle; origin at the handle, blade along +y."""
    steel, wood = mat("KnifeSteel", "#B9C2CC", rough=0.35), mat("KnifeWood", "#5A4632")
    blade = ([(-0.004, 0.0, 0.0), (0.004, 0.0, 0.0), (0.004, 0.12, 0.012), (-0.004, 0.12, 0.012),
              (-0.004, 0.0, 0.03), (0.004, 0.0, 0.03), (0.004, 0.11, 0.03), (-0.004, 0.11, 0.03)],
             [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
    handle = kit._box_geo(0.018, 0.1, 0.026, -0.009, -0.1, 0.002)
    return _obj(name, [blade, handle], [steel, wood])


def chipped_stone(name):
    """Gray stone flake (~9 x 6 cm): one convex face with flaking scars (large facets) and the other
    nearly flat; the edge on one side is thin and sharp (the cutting edge)."""
    rnd = random.Random(23)
    ring, n = [], 9
    for k in range(n):
        a = 2 * math.pi * k / n
        r = rnd.uniform(0.85, 1.1)
        ring.append((0.048 * r * math.cos(a), 0.032 * r * math.sin(a)))
    top = [(x, y, 0.016 * (1 - 0.6 * max(x / 0.048, 0)) + rnd.uniform(-0.002, 0.002)) for x, y in ring]
    bot = [(x, y, -0.006 + rnd.uniform(-0.001, 0.001)) for x, y in ring]
    edge = [(x * 1.04, y * 1.04, 0.0 if x > 0 else 0.004) for x, y in ring]
    v = top + edge + bot + [(-0.008, 0.002, 0.022), (0.0, 0.0, -0.008)]
    ct, cb = 3 * n, 3 * n + 1
    f = []
    for k in range(n):
        a, b = k, (k + 1) % n
        f += [(ct, a, b), (a, n + a, n + b, b), (n + a, 2 * n + a, 2 * n + b, n + b), (cb, 2 * n + b, 2 * n + a)]
    v = [(x * 1.4, y * 1.4, z * 1.4) for x, y, z in v]                 # 13 x 9 cm: reads in the hand
    owner = []
    for k in range(n):
        thin = ring[k][0] > 0                                           # thin side = cutting edge
        owner += [0, 1 if thin else 0, 1 if thin else 0, 0]
    obj = kit.mesh_object(name, v, f, [mat("Stone", "#7E7C78", rough=0.75), mat("StoneEdge", "#D8D2C4", rough=0.45)],
                          face_mats=owner)
    return kit.fix_normals(obj)


def tinder(name, rnd):
    """Pile of dry grass with crossed twigs on top (~40 cm)."""
    grass, sticks = mat("DryGrass", "#C9A86A"), mat("Sticks", "#6B5034")
    parts, owner = [], []
    for k in range(26):
        a, l = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.12, 0.24)
        base = (rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0.0)
        tip = (base[0] + l * math.cos(a) * 0.8, base[1] + l * math.sin(a) * 0.8, rnd.uniform(0.06, 0.14))
        parts.append(kit.tube_geo([base, tip], [0.025, 0.006], n=3))
    for k in range(7):
        a = 2 * math.pi * k / 7 + rnd.uniform(-0.2, 0.2)
        p0 = (0.26 * math.cos(a), 0.26 * math.sin(a), 0.0)
        p1 = (-0.02 * math.cos(a), -0.02 * math.sin(a), 0.2)
        parts.append(kit.tube_geo([p0, p1], [0.018, 0.012], n=5))
    v, f, own = kit.merge(*parts)
    obj = kit.mesh_object(name, v, f, [grass, sticks], face_mats=[0 if o < 26 else 1 for o in own])
    return kit.fix_normals(obj)


def rope(name, start_obj, end_obj, color="#6B5A44"):
    """Rein: thin box (2.5 cm) along +y, attached to start_obj and stretched to end_obj (Stretch To)."""
    v, f = kit._box_geo(0.025, 1.0, 0.025, -0.0125, 0.0, -0.0125)
    obj = kit.mesh_object(name, v, f, [mat("Rope", color)])
    obj.parent = start_obj
    c = obj.constraints.new("STRETCH_TO")
    c.target = end_obj
    c.rest_length = 1.0
    c.volume = "NO_VOLUME"
    return obj
