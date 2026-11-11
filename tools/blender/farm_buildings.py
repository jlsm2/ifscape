"""Farm buildings for the bacteria-disappeared script: gambrel barn, house with porch, fence,
bales, trough, manure pen with mushrooms, silo and windmill.

Measurements from docs/blender/model-references.md. What makes it read "American farm": the gambrel profile,
red wall with white X doors, the hayloft door above the main one and the ridge peak.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
from kit import box, box_span, flat

BARN_RED, TRIM, ROOF, WOOD_IN = "#A3352B", "#EDE6D6", "#2A2F3A", "#6B4A32"
HOUSE_WALL, HOUSE_ROOF, CHIMNEY = "#D9D2C3", "#3A3F4A", "#6E3B2E"
FENCE, STRAW, STRAW_END, STEEL = "#8C7A64", "#D8B25A", "#B48A3A", "#7E8A99"
CONCRETE, MANURE, MUSHROOM, MUSH_STEM = "#8D8A82", "#4A3326", "#E8DCC4", "#CFC2A8"

# Gambrel profile in x (half-width 5.5): wall 3.4 m, break at 5.8 m, ridge at 7.9 m
GAMBREL = [(-5.5, 3.4), (-4.1, 5.8), (0.0, 7.9), (4.1, 5.8), (5.5, 3.4)]
DOOR_W, DOOR_H = 3.6, 4.2
WALL_T = 0.2


def _mats():
    return SimpleNamespace(red=flat("BarnRed", BARN_RED), trim=flat("Trim", TRIM), roof=flat("Roof", ROOF, rough=0.8),
                           wood=flat("BarnWoodIn", WOOD_IN))


def _profile_h(x):
    for (xa, za), (xb, zb) in zip(GAMBREL, GAMBREL[1:]):
        if xa <= x <= xb:
            return za + (zb - za) * (x - xa) / (xb - xa)
    return GAMBREL[0][1]


def _gable_piece(x0, x1, z0, y, t):
    """Piece of the gable wall between x0 and x1, from z0 to the profile, with thickness t in y."""
    top = [(x1, _profile_h(x1))] + [(x, z) for x, z in reversed(GAMBREL) if x0 < x < x1] + [(x0, _profile_h(x0))]
    outline = [(x0, z0), (x1, z0)] + top
    n = len(outline)
    verts = [(x, y, z) for x, z in outline] + [(x, y + t, z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def _inside_mats(obj, center):
    """Faces turned toward the inside of the barn are wood-colored (index 1)."""
    mw = obj.matrix_world
    for poly in obj.data.polygons:
        c = mw @ poly.center
        n = mw.to_3x3() @ poly.normal
        to_center = Vector((center.x - c.x, center.y - c.y, 0))
        poly.material_index = 1 if n.dot(to_center) > 0.3 * to_center.length else 0


def _leaf(name, x0, x1, z0, z1, y, mats, frame=0.12, out=-1):
    """Red door leaf with white frame and X on the outside (out = -1 or +1 in y), thickness 0.08."""
    ty = y - 0.05 if out < 0 else y + 0.07
    w, h = x1 - x0, z1 - z0
    parts = [kit._box_geo(w, 0.08, h, x0, y, z0)]
    kinds = [0]
    for bx0, bz0, bw, bh in ((x0, z0, frame, h), (x1 - frame, z0, frame, h), (x0, z0, w, frame), (x0, z1 - frame, w, frame)):
        parts.append(kit._box_geo(bw, 0.06, bh, bx0, ty, bz0))
        kinds.append(1)
    diag = math.hypot(w, h) - frame
    ang = math.atan2(h, w)
    for sign in (1, -1):
        g = kit._box_geo(diag, 0.06, frame, -diag / 2, -0.03, -frame / 2)
        m = Matrix.Translation(((x0 + x1) / 2, ty + 0.03, (z0 + z1) / 2)) @ Matrix.Rotation(sign * ang, 4, "Y")
        parts.append(kit.xform_geo(g, m))
        kinds.append(1)
    verts, faces, owner = kit.merge(*parts)
    obj = kit.mesh_object(name, verts, faces, [mats.red, mats.trim], face_mats=[kinds[k] for k in owner])
    return kit.fix_normals(obj)


def _roof(name, y0, y1, mats, t=0.14, eave=0.35, hood=1.0):
    """Four gambrel roof planes; the upper ones extend 'hood' meters over the hayloft door (front at y0)."""
    parts = []
    segs = list(zip(GAMBREL, GAMBREL[1:]))
    for k, ((xa, za), (xb, zb)) in enumerate(segs):
        d = Vector((xb - xa, zb - za)).normalized()
        nrm = Vector((-d.y, d.x))
        if nrm.y < 0:
            nrm = -nrm
        a, b = Vector((xa, za)), Vector((xb, zb))
        if k == 0:
            a -= d * eave
        if k == len(segs) - 1:
            b += d * eave
        upper = k in (1, 2)
        ya, yb = y0 - (hood if upper else 0.3), y1 + 0.3
        pts = [a, b, b + nrm * t, a + nrm * t]
        verts = [(p.x, ya, p.y) for p in pts] + [(p.x, yb, p.y) for p in pts]
        faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        parts.append((verts, faces))
    verts, faces, _ = kit.merge(*parts)
    return kit.fix_normals(kit.mesh_object(name, verts, faces, [mats.roof]))


def barn(cx, y0, length=14.6, rnd=None):
    """Barn with the front (gable with door) at y0, facing -y, back at y0 + length (also with a door)."""
    mats = _mats()
    y1 = y0 + length
    center = Vector((cx, (y0 + y1) / 2, 0))
    walls = []
    for y, tag in ((y0, "Front"), (y1 - WALL_T, "Back")):
        hw = DOOR_W / 2
        parts = [_gable_piece(-5.5, -hw, 0, y, WALL_T), _gable_piece(hw, 5.5, 0, y, WALL_T),
                 _gable_piece(-hw, hw, DOOR_H, y, WALL_T)]
        verts, faces, _ = kit.merge(*parts)
        walls.append(kit.mesh_object(f"Barn{tag}", verts, faces, [mats.red, mats.wood], (cx, 0, 0)))
    for side in (-1, 1):
        x0 = side * 5.5 - (WALL_T if side > 0 else 0)
        verts, faces = kit._box_geo(WALL_T, length, 3.45, x0, y0, 0)
        walls.append(kit.mesh_object(f"BarnSide{side}", verts, faces, [mats.red, mats.wood], (cx, 0, 0)))
    bpy.context.view_layer.update()
    for w in walls:
        kit.fix_normals(w)
        _inside_mats(w, center)
    roof = _roof("BarnRoof", y0, y1, mats)
    roof.location = (cx, 0, 0)
    roof.data.materials.append(mats.wood)
    bpy.context.view_layer.update()
    _inside_mats(roof, Vector((cx, center.y, 0)))

    parts = []
    hw = DOOR_W / 2
    for leaf_y, out in ((y0 - 0.1, -1), (y1 + 0.02, 1)):
        # main door open: the two leaves slid to the sides
        parts.append(_leaf("BarnDoorL", cx - hw - DOOR_W / 2 - 0.05, cx - hw - 0.05, 0.02, DOOR_H, leaf_y, mats, out=out))
        parts.append(_leaf("BarnDoorR", cx + hw + 0.05, cx + hw + DOOR_W / 2 + 0.05, 0.02, DOOR_H, leaf_y, mats, out=out))
        wall_face = y0 if out < 0 else y1
        parts.append(box_span("BarnDoorTop", cx - hw - 0.15, cx + hw + 0.15, wall_face - 0.08, wall_face + 0.08, DOOR_H, 0.18,
                              mats.trim))
        parts.append(box_span("BarnRail", cx - DOOR_W * 1.1, cx + DOOR_W * 1.1, leaf_y + out * 0.1 - 0.04,
                              leaf_y + out * 0.1 + 0.04, DOOR_H + 0.2, 0.08, mats.roof))
    # hayloft (front), closed, and the ridge peak with beam and pulley
    parts.append(_leaf("Hayloft", cx - 0.9, cx + 0.9, 4.6, 6.7, y0 - 0.1, mats))
    parts.append(box_span("HoodBeam", cx - 0.1, cx + 0.1, y0 - 1.0, y0 + 0.2, 7.25, 0.2, mats.wood))
    parts.append(kit.mesh_object("Pulley", *kit._ico_geo(0.12, (0, 0, 0))[:2], [mats.roof], (cx, y0 - 0.85, 7.05)))
    # white corners and cupola
    for sx in (-1, 1):
        for y in (y0 - 0.02, y1 - 0.08):
            parts.append(box_span("Corner", cx + sx * 5.5 - 0.12, cx + sx * 5.5 + 0.12, y - 0.04, y + 0.12, 0, 3.4, mats.trim))
    cup_y = (y0 + y1) / 2
    parts.append(box(f"Cupola", (cx, cup_y, 7.7), (1.2, 1.2, 1.0), mats.trim))
    cap = kit.prism("CupolaCap", (cx, cup_y, 8.7), 4, 1.05, 0.0, 0.8, mats.roof)
    cap.rotation_euler = (0, 0, math.pi / 4)
    parts.append(cap)
    floor = box_span("BarnFloor", cx - 5.4, cx + 5.4, y0, y1, -0.02, 0.04, flat("BarnFloor", "#7A6446"))
    parts += _barn_interior(cx, y0, y1, mats, rnd or random.Random(5))
    lamp_data = bpy.data.lights.new("BarnLamp", "POINT")
    lamp_data.energy, lamp_data.color, lamp_data.shadow_soft_size = 1700.0, (1.0, 0.74, 0.46), 0.6
    lamps = []
    for k in range(3):
        lamp = bpy.data.objects.new(f"BarnLamp{k}", lamp_data)
        lamp.location = (cx - 1.5, y0 + length * (0.2 + 0.3 * k), 3.0)
        bpy.context.collection.objects.link(lamp)
        lamps.append(lamp)
    return SimpleNamespace(walls=walls, roof=roof, parts=parts, floor=floor, lamps=lamps, mats=mats,
                           x=cx, y0=y0, y1=y1)


def _barn_interior(cx, y0, y1, mats, rnd):
    """Posts, hayloft beams, pipe dividers between the cows (-x side), stacked bales (+x side)
    and lamps: the interior stops being an empty box."""
    post, pipe = flat("BarnPost", "#4E3524"), flat("StallPipe", "#9AA3B0", metallic=0.5, rough=0.4)
    out = []
    bays = [y0 + 1.2 + k * 3.0 for k in range(int((y1 - y0 - 1.2) / 3.0) + 1)]
    for y in bays:
        for x in (-1.9, 1.9):
            out.append(box_span("Post", cx + x - 0.12, cx + x + 0.12, y - 0.12, y + 0.12, 0, 3.4, post))
        out.append(box_span("LoftBeam", cx - 5.4, cx + 5.4, y - 0.1, y + 0.1, 3.3, 0.22, post))
    # dividers: a U-shaped pipe lying between each cow, from the trough to the aisle
    for y in (19.25, 21.75, 24.25, 26.75):
        y = y0 + (y - 16.0)
        g = kit.tube_geo([(cx - 4.3, y, 0.0), (cx - 4.3, y, 1.1), (cx - 2.4, y, 1.1), (cx - 2.4, y, 0.0)],
                         (0.04, 0.04, 0.04, 0.04), n=5)
        out.append(kit.mesh_object("Stall", g[0], g[1], [pipe]))
    straw = flat("BaleSq", STRAW)
    for i in range(3):
        for j in range(3 - i):
            out.append(box_span("BaleSq", cx + 3.4, cx + 4.3, y0 + 9.5 + j * 0.48 + i * 0.24, y0 + 9.96 + j * 0.48 + i * 0.24,
                                i * 0.37, 0.36, straw))
    bulb = flat("Bulb", "#FFE2A8", emission="#FFC46B", strength=12.0)
    for k in range(2):
        y = y0 + (y1 - y0) * (0.3 + 0.4 * k)
        out.append(kit.mesh_object("Bulb", *kit._ico_geo(0.09, (cx, y, 3.05))[:2], [bulb]))
        out.append(kit.prism("Shade", (cx, y, 3.1), 8, 0.22, 0.05, 0.14, flat("Shade", "#2A2F3A")))
    return out


def trough(name, x, y0, y1, hay=True):
    """Galvanized steel trough along y, full of hay."""
    steel, dark = flat("Steel", STEEL, rough=0.5, metallic=0.4), flat("SteelIn", "#4A5260")
    outer = box_span(name, x - 0.3, x + 0.3, y0, y1, 0.0, 0.55, steel)
    inner = box_span(name + "In", x - 0.24, x + 0.24, y0 + 0.06, y1 - 0.06, 0.5, 0.06, dark)
    out = [outer, inner]
    if hay:
        rnd = random.Random(3)
        mat = flat("Hay", "#B9A453")
        parts = []
        for _ in range(int((y1 - y0) / 0.06)):                    # hay = many crooked wisps, not blocks
            y = rnd.uniform(y0 + 0.15, y1 - 0.15)
            a = rnd.uniform(0, math.tau)
            p0 = (x + rnd.uniform(-0.2, 0.2), y, rnd.uniform(0.55, 0.66))
            p1 = (p0[0] + math.cos(a) * 0.25, p0[1] + math.sin(a) * 0.25, p0[2] + rnd.uniform(-0.04, 0.06))
            parts.append(kit.tube_geo([p0, p1], (0.02, 0.012), n=3))
        v, f, _ = kit.merge(*parts)
        out.append(kit.mesh_object(f"{name}Hay", v, f, [mat]))
    return out


def round_bale(name, location, heading=0.0):
    straw, end = flat("Straw", STRAW), flat("StrawEnd", STRAW_END)
    body = kit._prism_geo(12, 0.75, 0.75, 1.5, oz=-0.75)
    rings = [kit._prism_geo(12, 0.55, 0.55, 0.02, oz=0.75), kit._prism_geo(12, 0.55, 0.55, 0.02, oz=-0.77)]
    verts, faces, owner = kit.merge(body, *rings)
    obj = kit.mesh_object(name, verts, faces, [straw, end], location, face_mats=[0 if o == 0 else 1 for o in owner])
    obj.rotation_euler = (math.pi / 2, 0, heading)
    obj.location = (location[0], location[1], 0.75)
    return obj


def fence(name, points, height=1.2, spacing=2.6):
    """Fence of three rails through a line of points (x, y)."""
    parts = []
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        seg = math.hypot(xb - xa, yb - ya)
        n = max(1, round(seg / spacing))
        ang = math.atan2(yb - ya, xb - xa)
        for i in range(n + 1):
            u = i / n
            parts.append(kit._box_geo(0.12, 0.12, height, xa + (xb - xa) * u - 0.06, ya + (yb - ya) * u - 0.06, 0))
        for z in (1.05, 0.65, 0.25):
            g = kit._box_geo(seg, 0.05, 0.09, 0, -0.025, z)
            parts.append(kit.xform_geo(g, Matrix.Translation((xa, ya, 0)) @ Matrix.Rotation(ang, 4, "Z")))
    verts, faces, _ = kit.merge(*parts)
    return kit.fix_normals(kit.mesh_object(name, verts, faces, [flat("Fence", FENCE)]))


def house(cx, cy, mats_win):
    """Two-story farmhouse, front (porch) facing +y at cy. Returns the windows to animate."""
    wall, roof, trim = flat("HouseWall", HOUSE_WALL), flat("HouseRoof", HOUSE_ROOF), flat("HouseTrim", TRIM)
    w, d, eave = 9.0, 8.0, 6.0
    body = box_span("House", cx - w / 2, cx + w / 2, cy - d, cy, 0, eave, wall)
    rise = (w / 2) * math.tan(math.radians(38))
    gable = kit.mesh_object("HouseGable", [(cx - w / 2, cy - d, eave), (cx + w / 2, cy - d, eave), (cx, cy - d, eave + rise),
                                           (cx - w / 2, cy, eave), (cx + w / 2, cy, eave), (cx, cy, eave + rise)],
                            [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1)], [wall])
    roof_parts = []
    for side in (-1, 1):
        a = Vector((cx + side * (w / 2 + 0.4), eave - 0.4 * math.tan(math.radians(38))))
        b = Vector((cx, eave + rise))
        nrm = Vector((side * math.sin(math.radians(38)), math.cos(math.radians(38))))
        pts = [a, b, b + nrm * 0.15, a + nrm * 0.15]
        verts = [(p.x, cy - d - 0.4, p.y) for p in pts] + [(p.x, cy + 0.4, p.y) for p in pts]
        roof_parts.append((verts, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    verts, faces, _ = kit.merge(*roof_parts)
    kit.fix_normals(kit.mesh_object("HouseRoof", verts, faces, [roof]))
    box("Chimney", (cx + 2.4, cy - d + 2.0, eave), (0.7, 0.7, rise + 1.4), flat("Chimney", CHIMNEY))
    windows = []
    for z in (1.2, 4.0):
        for x in (-3.0, -1.2, 1.2, 3.0):
            if z < 2 and abs(x) < 2:
                continue
            windows.append(box_span("Window", cx + x - 0.45, cx + x + 0.45, cy - 0.02, cy + 0.04, z, 1.5, mats_win))
            box_span("WinTrim", cx + x - 0.55, cx + x + 0.55, cy - 0.01, cy + 0.06, z - 0.1, 0.1, trim)
    box_span("Door", cx - 0.5, cx + 0.5, cy - 0.02, cy + 0.04, 0.5, 2.2, flat("HouseDoor", "#2F4B7C"))
    # porch: floor, pillars, single-slope roof, railing and stairs in the middle
    pd = 2.6
    box_span("Porch", cx - w / 2, cx + w / 2, cy, cy + pd, 0, 0.5, flat("PorchFloor", "#8C7A64"))
    for x in (-w / 2 + 0.2, -2.0, 2.0, w / 2 - 0.2):
        box_span("PorchPost", cx + x - 0.08, cx + x + 0.08, cy + pd - 0.25, cy + pd - 0.09, 0.5, 2.6, trim)
    pr = kit.mesh_object("PorchRoof", [(cx - w / 2 - 0.2, cy, 3.5), (cx + w / 2 + 0.2, cy, 3.5),
                                       (cx + w / 2 + 0.2, cy + pd + 0.3, 3.0), (cx - w / 2 - 0.2, cy + pd + 0.3, 3.0)],
                         [(0, 1, 2, 3)], [roof])
    pr.modifiers.new("Solid", "SOLIDIFY").thickness = 0.12
    for x0, x1 in ((-w / 2 + 0.2, -1.0), (1.0, w / 2 - 0.2)):
        box_span("PorchRail", cx + x0, cx + x1, cy + pd - 0.2, cy + pd - 0.12, 1.4, 0.08, trim)
    for i in range(3):
        box_span("Step", cx - 1.0, cx + 1.0, cy + pd + i * 0.32, cy + pd + (i + 1) * 0.32, 0, 0.5 - (i + 1) * 0.16 + 0.01,
                 flat("Step", "#8C7A64"))
    return SimpleNamespace(windows=windows, porch_z=0.5, front=cy, porch_depth=pd)


def manure_bay(cx, cy, rnd):
    """Manure pen with three walls (open toward -y), the pile (grows in z) and mushrooms (grow)."""
    conc = flat("Concrete", CONCRETE)
    box_span("BayBack", cx - 2.0, cx + 2.0, cy + 1.8, cy + 2.05, 0, 1.5, conc)
    for sx in (-1, 1):
        box_span("BaySide", cx + sx * 2.0 - 0.125, cx + sx * 2.0 + 0.125, cy - 2.0, cy + 2.05, 0, 1.5, conc)
    # pile = a main body and smaller lumps: reads as heaped manure, not as stone
    lumps = [((0, 0, 0), (1.75, 1.7, 1.0))]
    for _ in range(7):
        a = rnd.uniform(0, math.tau)
        lumps.append(((math.cos(a) * 1.0, math.sin(a) * 0.9, rnd.uniform(0.2, 0.5)), (rnd.uniform(0.5, 0.8),) * 2 + (0.45,)))
    parts = []
    for c, sc in lumps:
        v, f = kit._ico_geo(1.0, c, sc)
        parts.append(([(x + rnd.uniform(-0.06, 0.06), y + rnd.uniform(-0.06, 0.06), max(z, -0.05)) for x, y, z in v], f))
    v, f, _ = kit.merge(*parts)
    heap = kit.fix_normals(kit.mesh_object("Manure", v, f, [flat("Manure", MANURE)], (cx, cy + 0.1, 0)))
    cap, stem = flat("Mushroom", MUSHROOM), flat("MushStem", MUSH_STEM)
    mushrooms = []
    for i in range(9):
        a, r = rnd.uniform(0, math.tau), rnd.uniform(0.2, 0.75)
        dx, dy = math.cos(a) * r * 1.75, math.sin(a) * r * 1.7
        size = rnd.uniform(0.10, 0.16)
        parts = [kit._prism_geo(6, size * 0.28, size * 0.22, size * 0.9), kit._prism_geo(7, size, 0.0, size * 0.6, oz=size * 0.85)]
        verts, faces, owner = kit.merge(*parts)
        # height of the main body's surface (ellipsoid) at that point; the animator corrects it with the final scale
        top = (1 - r * r) ** 0.5
        mushrooms.append(kit.mesh_object(f"Mushroom{i}", verts, faces, [stem, cap], (cx + dx, cy + 0.1 + dy, top), face_mats=owner))
    return SimpleNamespace(heap=heap, mushrooms=mushrooms)


def silo(x, y, height=16.0, r=3.0):
    body = kit.prism("Silo", (x, y, 0), 16, r, r, height, flat("Silo", "#2F4B7C"))
    dome = kit.mesh_object("SiloDome", *kit._ico_geo(1.0, (x, y, height), (r * 1.02, r * 1.02, r * 0.8))[:2], [flat("SiloDome", "#BFB6A6")])
    band = flat("SiloBand", "#BFB6A6")
    for z in range(2, int(height), 3):
        kit.prism("SiloBand", (x, y, z), 16, r + 0.04, r + 0.04, 0.12, band)
    return body, dome


def windmill(x, y, height=10.0):
    """Farm windmill: lattice tower, 18-blade wheel and tail vane. Returns the wheel (rotates in local x)."""
    steel = flat("MillSteel", "#5A6378", metallic=0.3, rough=0.6)
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(kit.tube_geo([(sx * 1.2, sy * 1.2, 0), (sx * 0.2, sy * 0.2, height)], (0.06, 0.04), n=4))
    for k in range(1, 5):
        z = height * k / 5
        s = 1.2 - 1.0 * k / 5
        for a, b in (((-s, -s), (s, -s)), ((s, -s), (s, s)), ((s, s), (-s, s)), ((-s, s), (-s, -s))):
            parts.append(kit.tube_geo([(a[0], a[1], z), (b[0], b[1], z)], (0.03, 0.03), n=4))
    verts, faces, _ = kit.merge(*parts)
    tower = kit.mesh_object("MillTower", verts, faces, [steel], (x, y, 0))
    hub = bpy.data.objects.new("MillHub", None)
    hub.location = (x, y - 0.4, height + 0.3)
    bpy.context.collection.objects.link(hub)
    blades = []
    for i in range(18):
        g = kit._box_geo(0.05, 0.22, 1.0, -0.025, -0.11, 0.25)
        m = Matrix.Rotation(2 * math.pi * i / 18, 4, "Y") @ Matrix.Rotation(math.radians(20), 4, "Z")
        blades.append(kit.xform_geo(g, m))
    verts, faces, _ = kit.merge(*blades)
    wheel = kit.mesh_object("MillWheel", verts, faces, [flat("MillBlade", "#C9C1B4")])
    wheel.parent = hub
    vane = kit.mesh_object("MillVane", [(0, 0.3, -0.05), (0, 2.0, 0.2), (0, 2.0, -0.6), (0, 0.3, -0.25)],
                           [(0, 1, 2, 3)], [flat("MillVane", "#A3352B")], (x, y, height + 0.3))
    return SimpleNamespace(tower=tower, wheel=wheel, vane=vane)
