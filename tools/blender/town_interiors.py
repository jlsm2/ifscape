"""Interiors of technology-disappeared: the kitchen of scene 06 (fridge and stove openings, faucet, window to
the water tower) and the grocery of scene 07 (nearly empty shelving, door open to the street).

Proportions: American kitchen counter 0.91 m high and 0.61 m deep; 30" stove opening (0.76 m); 36" fridge
opening (0.91 m) x 1.78 m; sink 0.8 m. Grocery shelving: 1.5 to 1.8 m high, 0.9 m deep,
shelves every ~0.4 m; aisle 1.2 to 1.5 m. Low-poly references: Kenney "Furniture Kit" (simple blocks
with dark handles) and the kitchens of Quaternius "Ultimate House Interior".
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
import town_set as ts
from town_set import Geo, mat

KITCHEN_AT = (-118.0, 150.0)          # outside the neighboring houses (the kitchen only shows from the inside)
KITCHEN_FACING = math.atan2(222.0 - KITCHEN_AT[1], 6.0 - KITCHEN_AT[0]) - math.pi / 2      # local +y points to the water tower
W, D, H = 4.4, 3.8, 2.7          # width (x), depth (y), ceiling height
WIN = (-0.46, 0.46, 0.95, 2.35)  # window on the back wall (+y): x0, x1, z0, z1
COUNTER_Z, COUNTER_D = 0.91, 0.62
STOVE_GAP = (-1.25, -0.49)
SINK = (-0.4, 0.4)
SINK_DEPTH = 0.17
FAUCET = 1.45                     # faucet larger than the real one: reads on a phone
FRIDGE_GAP = (0.49, 1.4)
KITCHEN_M = Matrix.Translation((*KITCHEN_AT, 0.0)) @ Matrix.Rotation(KITCHEN_FACING, 4, "Z")


class _View:
    """Camera path in the grocery aisle (filled in by grocery())."""
    x0 = x1 = y = 0.0

    def set(self, store):
        self.x0, self.x1, self.y = store.x_back + 1.2, store.x_front - 4.8, store.aisle_y


GROCERY_VIEW = _View()


def _kitchen_geo():
    g = Geo()
    wall, floor_m = mat("KitchenWall", "#A99E88"), mat("KitchenFloor", "#625244")
    clean = mat("KitchenFloorClean", "#B8A88A")
    grime = mat("Grime", "#2E261E")
    cab, top = mat("Cabinet", "#5E7A8A"), mat("Countertop", "#C9C2B4")
    knob, steel = mat("Knob", "#2A2E36"), mat("SinkSteel", "#9AA3AE", rough=0.45)
    wx, wy, t = W / 2, D / 2, 0.15
    g.box(-wx - t, wx + t, -wy - t, wy + t, -0.1, 0.0, floor_m)
    g.box(-wx - t, wx + t, -wy - t, wy + t, H, H + 0.12, wall)
    g.box(-wx - t, -wx, -wy, wy, 0, H, wall)
    g.box(wx, wx + t, -wy, wy, 0, H, wall)
    g.box(-wx - t, wx + t, -wy - t, -wy, 0, H, wall)
    x0, x1, z0, z1 = WIN
    for a, b, c, d in ((-wx, x0, 0, H), (x1, wx, 0, H), (x0, x1, 0, z0), (x0, x1, z1, H)):  # window wall
        g.box(a, b, wy, wy + t, c, d, wall)
    frame = mat("WindowFrame", "#D8D2C4")
    e = 0.012                                    # frame advances into the opening: no plane in common with the wall (z-fighting)
    for a, b, c, d in ((x0 - 0.06, x0 + e, z0 - e, z1 + e), (x1 - e, x1 + 0.06, z0 - e, z1 + e),
                       (x0 - e, x1 + e, z0 - 0.06, z0 + e), (x0 - e, x1 + e, z1 - e, z1 + 0.06)):
        g.box(a, b, wy - 0.045, wy + 0.045, c, d, frame)
    g.box(x0 - 0.1, x1 + 0.1, wy - 0.16, wy - 0.045, z0 - 0.07, z0 + 0.006, frame)       # peitoril interno                       # peitoril interno
    cy0 = wy - COUNTER_D
    for a, b in ((-wx, STOVE_GAP[0]), (STOVE_GAP[1], SINK[0]), (SINK[1], FRIDGE_GAP[0]), (FRIDGE_GAP[1], wx)):
        g.box(a, b, cy0, wy, 0.1, COUNTER_Z - 0.04, cab)
        g.box(a - 0.01, b + 0.01, cy0 - 0.03, wy, COUNTER_Z - 0.04, COUNTER_Z, top)
        g.box(a, b, cy0 + 0.05, wy, 0.0, 0.1, knob)                                        # recessed baseboard
        for k in range(max(1, int((b - a) / 0.5))):
            m = a + (b - a) * (k + 0.5) / max(1, int((b - a) / 0.5))
            g.box(m - 0.06, m + 0.06, cy0 - 0.02, cy0, COUNTER_Z - 0.16, COUNTER_Z - 0.13, knob)
    # sink: the counter opens a hole; the basin is a deep box underneath
    d = SINK_DEPTH
    g.box(SINK[0], SINK[1], cy0, wy, 0.1, COUNTER_Z - d, cab)
    g.box(SINK[0], SINK[1], cy0 - 0.03, cy0 + 0.06, COUNTER_Z - d, COUNTER_Z, top)
    g.box(SINK[0], SINK[1], wy - 0.1, wy, COUNTER_Z - d, COUNTER_Z, top)
    g.box(SINK[0], SINK[0] + 0.05, cy0, wy, COUNTER_Z - d, COUNTER_Z, top)
    g.box(SINK[1] - 0.05, SINK[1], cy0, wy, COUNTER_Z - d, COUNTER_Z, top)
    g.box(SINK[0] + 0.05, SINK[1] - 0.05, cy0 + 0.06, wy - 0.1, COUNTER_Z - d, COUNTER_Z - d + 0.02, steel)
    g.add(kit._prism_geo(8, 0.03, 0.03, 0.004, oz=COUNTER_Z - d + 0.02, ox=0.0, oy=(cy0 + wy) / 2), knob)  # ralo
    # openings: lighter floor where the appliance stood; outlet and gas pipe on the wall
    for (a, b), y0 in ((STOVE_GAP, cy0), (FRIDGE_GAP, wy - 0.78)):
        g.box(a + 0.02, b - 0.02, y0, wy - 0.02, 0.0, 0.006, clean)
        for xa, xb, ya, yb in ((a + 0.02, b - 0.02, y0, y0 + 0.03), (a + 0.02, a + 0.05, y0, wy - 0.02),
                               (b - 0.05, b - 0.02, y0, wy - 0.02)):
            g.box(xa, xb, ya, yb, 0.0, 0.009, grime)                                    # dirt edge
    ghost = mat("WallClean", "#D8CFBA")
    g.box(STOVE_GAP[0] + 0.03, STOVE_GAP[1] - 0.03, wy - 0.008, wy, 0.0, 0.93, ghost)
    g.box(FRIDGE_GAP[0] + 0.04, FRIDGE_GAP[1] - 0.04, wy - 0.008, wy, 0.0, 1.78, ghost)
    pipe = mat("GasPipe", "#B08A3A", rough=0.5)
    g.add(kit.tube_geo([((STOVE_GAP[0] + STOVE_GAP[1]) / 2, wy, 0.32), ((STOVE_GAP[0] + STOVE_GAP[1]) / 2, wy - 0.12, 0.32)],
                       [0.025, 0.025], n=6), pipe)
    for gx in ((STOVE_GAP[0] + STOVE_GAP[1]) / 2 + 0.2, (FRIDGE_GAP[0] + FRIDGE_GAP[1]) / 2):
        g.box(gx - 0.045, gx + 0.045, wy - 0.02, wy, 0.42, 0.55, mat("Outlet", "#F4F0E6"))
    # tall cabinets
    for a, b in ((-wx, x0 - 0.15), (FRIDGE_GAP[1], wx)):
        g.box(a, b, wy - 0.34, wy, 1.5, 2.3, cab)
    g.box(FRIDGE_GAP[0], FRIDGE_GAP[1], wy - 0.62, wy, 2.0, 2.3, cab)
    return g


def faucet(parent):
    """Single-lever faucet: base, curved spout over the basin; the lever is its own object (rotates)."""
    chrome = mat("Chrome", "#C9D0D8", rough=0.3)
    wy = D / 2
    bx, by, k = 0.0, wy - 0.07, FAUCET
    spout = kit.tube_geo([(bx, by, COUNTER_Z), (bx, by, COUNTER_Z + 0.26 * k), (bx, by - 0.08 * k, COUNTER_Z + 0.3 * k),
                          (bx, by - 0.2 * k, COUNTER_Z + 0.24 * k)], [0.022 * k, 0.02 * k, 0.016 * k, 0.014 * k], n=8)
    base = kit._prism_geo(8, 0.035 * k, 0.03 * k, 0.04, oz=COUNTER_Z, ox=bx, oy=by)
    v, f, owner = kit.merge(spout, base)
    body = kit.fix_normals(kit.mesh_object("Faucet", v, f, [chrome]))
    body.parent = parent
    lv = kit.tube_geo([(0, 0, 0), (0.0, -0.16, 0.05)], [0.02, 0.014], n=6)
    lever = kit.fix_normals(kit.mesh_object("FaucetLever", *lv, [chrome]))
    lever.parent = parent
    lever.location = (bx + 0.035 * k, by, COUNTER_Z + 0.2 * k)
    lever.rotation_mode = "XYZ"
    tip = Vector((bx, by - 0.2 * k, COUNTER_Z + 0.22 * k))
    return body, lever, tip


def kitchen():
    """Kitchen on an empty rotated so the window faces the water tower. Returns SimpleNamespace with root, pieces,
    lever, spout tip (kitchen coordinates) and the to_world function."""
    root = bpy.data.objects.new("Kitchen", None)
    bpy.context.collection.objects.link(root)
    root.location = (*KITCHEN_AT, 0.0)
    root.rotation_euler = (0, 0, KITCHEN_FACING)
    room = _kitchen_geo().build("KitchenRoom")
    room.parent = root
    body, lever, tip = faucet(root)
    light = bpy.data.lights.new("KitchenDay", "AREA")
    light.energy, light.size, light.color = 45.0, 1.6, (0.92, 0.95, 1.0)
    lo = bpy.data.objects.new("KitchenDay", light)
    bpy.context.collection.objects.link(lo)
    lo.parent = root
    lo.location = (0.0, D / 2 - 0.3, 2.5)
    lo.rotation_euler = (math.radians(35), 0, 0)
    fill = bpy.data.lights.new("KitchenFill", "AREA")
    fill.energy, fill.size = 30.0, 3.0
    fo = bpy.data.objects.new("KitchenFill", fill)
    bpy.context.collection.objects.link(fo)
    fo.parent = root
    fo.location = (0.0, -0.5, H - 0.05)
    m = Matrix.Translation((*KITCHEN_AT, 0.0)) @ Matrix.Rotation(KITCHEN_FACING, 4, "Z")
    return SimpleNamespace(root=root, objs=[root, room, body, lever, lo, fo], lever=lever, tip=tip,
                           to_world=lambda p: m @ Vector(p))


# ---------- mercadinho ----------

def grocery(bld, rnd):
    """Grocery interior (hollow building 'bld', west side): floor, back wall, ceiling with light fixtures, three
    nearly empty shelves, wall shelf, crate and the open door. Returns SimpleNamespace(objs, aisle_y,
    lamps, door_x)."""
    g = Geo()
    x_front, x_back = -ts.FRONT, -ts.FRONT - ts.GROCERY_DEPTH
    y0, y1 = bld.y0, bld.y1
    floor_m, wall = mat("StoreFloor", "#B8B2A4"), mat("StoreWall", "#C9C2AE")
    shelf, metal = mat("Shelf", "#8A94A6", rough=0.7), mat("ShelfDark", "#4A5262", rough=0.7)
    back, strip = mat("ShelfBack", "#5E6878", rough=0.8), mat("PriceStrip", "#6B5A2E", rough=0.8)
    g.box(x_back, x_front, y0, y1, -0.1, 0.15, floor_m)
    g.box(x_back - 0.2, x_back, y0, y1, 0.15, ts.FLOOR1, wall)
    for ya, yb in ((y0, y0 + 0.2), (y1 - 0.2, y1)):
        g.box(x_back, x_front - 0.3, ya, yb, 0.15, ts.FLOOR1, wall)
    g.box(x_back, x_front, y0, y1, ts.FLOOR1 - 0.12, ts.FLOOR1 - 0.02, mat("StoreCeiling", "#D8D2C4"))
    aisle = bld.door_y + 0.575
    rows = [aisle - 1.55, aisle + 1.55, aisle - 4.65]
    rows = [r for r in rows if y0 + 1.0 < r < y1 - 1.0]
    for r in rows:
        xa, xb = x_back + 2.0, x_front - 3.2
        g.box(xa, xb, r - 0.45, r + 0.45, 0.15, 0.3, metal)
        g.box(xa, xb, r - 0.05, r + 0.05, 0.3, 1.75, back)                       # back of the shelving
        for xe in (xa - 0.05, xb):
            g.box(xe, xe + 0.05, r - 0.47, r + 0.47, 0.15, 1.8, metal)           # cabeceiras
        for z in (0.32, 0.72, 1.12, 1.52):
            g.box(xa, xb, r - 0.45, r + 0.45, z, z + 0.035, shelf)
            for side in (-1, 1):
                g.box(xa, xb, r + side * 0.45 - 0.012, r + side * 0.45 + 0.012, z - 0.04, z + 0.035, strip)
    g.box(x_back + 0.02, x_back + 0.5, y0 + 0.3, y1 - 0.3, 0.15, 0.3, metal)
    for z in (0.32, 0.8, 1.28, 1.76):
        g.box(x_back + 0.02, x_back + 0.5, y0 + 0.3, y1 - 0.3, z, z + 0.035, shelf)
    g.box(x_front - 2.4, x_front - 1.6, aisle - 3.6, aisle - 1.2, 0.15, 1.05, mat("Counter", "#6B4E3A"))
    room = g.build("GroceryRoom")
    cans = _cans(rows, x_back, x_front, y0, y1, rnd)
    door = _open_door(bld)
    lamps_mat = mat("StoreLamp", "#C8C4BA", emission="#FFF0D0", strength=1.6)
    lv, lf, _ = kit.merge(*[kit._box_geo(0.3, 1.2, 0.02, x - 0.15, y - 0.6, ts.FLOOR1 - 0.14)
                            for x in (x_back + 3, x_back + 7) for y in (aisle - 3, aisle + 1.5)])
    lamps = kit.mesh_object("StoreLamps", lv, lf, [lamps_mat])
    day = bpy.data.lights.new("StoreDay", "AREA")
    day.energy, day.size, day.color = 160.0, 4.0, (0.95, 0.96, 1.0)
    do = bpy.data.objects.new("StoreDay", day)
    bpy.context.collection.objects.link(do)
    do.location = (x_front - 1.2, aisle, ts.FLOOR1 - 0.3)
    do.rotation_euler = (0, math.radians(-60), 0)
    return SimpleNamespace(objs=[room, cans, door, lamps, do], lamp_power=kit.principled(lamps_mat).inputs["Emission Strength"],
                           aisle_y=aisle, x_back=x_back, x_front=x_front, day=do)


def _cans(rows, x_back, x_front, y0, y1, rnd):
    """A few leftover cans and boxes (one shelf almost entirely empty)."""
    colors = ["#A83A2A", "#C9A227", "#3F5A73", "#D8D2C4", "#4E6B4A"]
    parts, owner = [], []
    spots = [(r, z) for r in rows for z in (0.355, 0.755, 1.155)] + [(None, z) for z in (0.355, 0.835)]
    for r, z in spots:
        for _ in range(rnd.randint(1, 4)):
            if r is None:
                x, y = x_back + 0.25, rnd.uniform(y0 + 1, y1 - 1)
            else:
                x, y = rnd.uniform(x_back + 2.3, x_front - 3.5), r + rnd.choice((-0.25, 0.25))
            if rnd.random() < 0.7:
                parts.append(kit._prism_geo(8, 0.065, 0.065, 0.17, oz=z, ox=x, oy=y))
            else:
                parts.append(kit._box_geo(0.26, 0.1, 0.34, x - 0.13, y - 0.05, z))
            owner.append(rnd.randrange(len(colors)))
    v, f, own = kit.merge(*parts)
    mats = [mat(f"Can{c}", c, rough=0.6) for c in colors]
    obj = kit.mesh_object("Cans", v, f, mats, face_mats=[owner[o] for o in own])
    return kit.fix_normals(obj)


def _open_door(bld):
    """Glass door with dark frame, open inward (~100 deg), hinge on the south side of the opening."""
    s = bld.side
    hinge = (s * (ts.FRONT + 0.1), bld.door_y, 0.15)
    frame, glass = mat("DarkWood", "#2A2622"), mat("Glass", ts.GLASS, rough=0.4)
    parts = [kit._box_geo(0.05, 1.1, 0.12, -0.025, 0.0, 0.0), kit._box_geo(0.05, 1.1, 0.12, -0.025, 0.0, 2.1),
             kit._box_geo(0.05, 0.1, 2.22, -0.025, 0.0, 0.0), kit._box_geo(0.05, 0.1, 2.22, -0.025, 1.0, 0.0),
             kit._box_geo(0.02, 0.9, 1.98, -0.01, 0.1, 0.12)]
    v, f, owner = kit.merge(*parts)
    obj = kit.mesh_object("GroceryDoor", v, f, [frame, glass], hinge, face_mats=[0 if o < 4 else 1 for o in owner])
    obj.rotation_euler = (0, 0, math.radians(100) if s < 0 else math.radians(-100))
    return kit.fix_normals(obj)
