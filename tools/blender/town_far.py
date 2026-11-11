"""Surroundings of the main street (technology-disappeared): terrain with the water tower hill to the north, the water tower
on legs, the road to the hill, houses on the neighboring streets, trees and the fields around the town.

Proportions:
- American municipal legged water tower ("multi-leg elevated tank", Chicago Bridge & Iron type): tank of
  12 to 15 m diameter, 30 to 40 m total height, 4 to 6 slanted legs with X braces and a central
  pipe (riser). Source: AWWA D100 (elevated steel tanks) and photos of Midwest towns.
- Small-town house: 8 x 10 m, 1 or 2 stories, gable roof of 30 to 40 deg.
- Low-poly references: Kenney "City Kit (Suburban)" and Quaternius "Ultimate Nature" (trees with faceted crowns).
"""

import math
import random
from types import SimpleNamespace

import bpy

import kit
from town_set import Geo, mat

HILL = (6.0, 222.0, 24.0, 68.0)            # x, y, height, radius (hill just past the end of the street, at y ~155)
TOWER_XY = (6.0, 222.0)
HOUSE_WALLS = ["#B8A68C", "#8FA3B0", "#B88A6A", "#B5AC9C", "#9AA38A", "#B2946E", "#7E8C9A"]
ROOFS = ["#3E434E", "#5A3A30", "#4A4F44", "#2F3542"]
LEAVES = ["#3E5E34", "#4C6B38", "#36552F", "#5A7340"]
GRASS = "#55663A"


def ground_z(x, y):
    hx, hy, h, rad = HILL
    r = math.hypot(x - hx, y - hy) / rad
    z = h * (1 - r * r) ** 2 if r < 1 else 0.0          # zero outside the radius: the town stays flat
    z += 9.0 * math.exp(-((x + 160) ** 2 + (y - 520) ** 2) / (2 * 90 * 90))           # hills in the background
    z += 7.0 * math.exp(-((x - 220) ** 2 + (y - 480) ** 2) / (2 * 80 * 80))
    return z - 0.05


def terrain():
    """10 m grid following ground_z (the hill and the hills), flat grass."""
    step, xs, ys = 10.0, range(-600, 601, 10), range(-400, 801, 10)
    nx, ny = len(xs), len(ys)
    verts = [(x, y, ground_z(x, y) - 0.03) for y in ys for x in xs]
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(ny - 1) for i in range(nx - 1)]
    obj = kit.mesh_object("Terrain", verts, faces, [mat("Grass", GRASS)])
    return obj


def water_tower():
    """Water tower with 6 slanted legs, braces, central pipe, tank with conical roof and catwalk."""
    g = Geo()
    tx, ty = TOWER_XY
    base = ground_z(tx, ty)
    leg, tank, dark = mat("TowerLeg", "#7D8794", rough=0.8), mat("Tank", "#B9C2CC", rough=0.8), mat("TankDark", "#5E6874")
    top, n = 25.0, 6
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        r0, r1 = 7.0, 5.2
        p0 = (tx + r0 * math.cos(a), ty + r0 * math.sin(a), base - 0.5)
        p1 = (tx + r1 * math.cos(a), ty + r1 * math.sin(a), base + top)
        g.add(kit.tube_geo([p0, p1], [0.32, 0.28], n=6), leg)
        b = 2 * math.pi * (k + 1.5) / n
        for z0, z1 in ((0.08, 0.45), (0.45, 0.82)):
            q0 = [tx + (r0 + (r1 - r0) * z0) * math.cos(a), ty + (r0 + (r1 - r0) * z0) * math.sin(a), base + top * z0]
            q1 = [tx + (r0 + (r1 - r0) * z1) * math.cos(b), ty + (r0 + (r1 - r0) * z1) * math.sin(b), base + top * z1]
            g.add(kit.tube_geo([q0, q1], [0.1, 0.1], n=5), leg)
            q2 = [tx + (r0 + (r1 - r0) * z1) * math.cos(a), ty + (r0 + (r1 - r0) * z1) * math.sin(a), base + top * z1]
            q3 = [tx + (r0 + (r1 - r0) * z0) * math.cos(b), ty + (r0 + (r1 - r0) * z0) * math.sin(b), base + top * z0]
            g.add(kit.tube_geo([q2, q3], [0.1, 0.1], n=5), leg)
    g.add(kit._prism_geo(10, 0.7, 0.7, top + 1, oz=base - 0.5, ox=tx, oy=ty), dark)
    z = base + top
    g.add(kit._prism_geo(20, 2.0, 6.6, 2.4, oz=z, ox=tx, oy=ty), tank)                    # funnel bottom
    g.add(kit._prism_geo(20, 6.6, 6.6, 5.4, oz=z + 2.4, ox=tx, oy=ty), tank)
    g.add(kit._prism_geo(20, 6.9, 6.9, 0.25, oz=z + 2.3, ox=tx, oy=ty), dark)             # passarela
    g.add(kit._prism_geo(20, 6.65, 0.6, 2.6, oz=z + 7.8, ox=tx, oy=ty), tank)             # conical roof
    g.add(kit._prism_geo(8, 0.5, 0.15, 1.4, oz=z + 10.4, ox=tx, oy=ty), dark)
    g.add(kit._prism_geo(20, 6.62, 6.62, 0.5, oz=z + 5.0, ox=tx, oy=ty), dark)            # faixa escura
    return g.build("WaterTower")


def _road_strip(g, x0, x1, y0, y1, m, step=5.0):
    n = max(1, int((y1 - y0) / step))
    v, f = [], []
    for k in range(n + 1):
        y = y0 + (y1 - y0) * k / n
        for x in (x0, x1):
            v.append((x, y, ground_z(x, y) + 0.06))
    for k in range(n):
        f.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2))
    g.add((v, f), m)


def house(g, x, y, rnd, facing):
    """Gable house (facing = direction of the front: 'x+', 'x-', 'y+', 'y-')."""
    w, d = rnd.uniform(7, 9), rnd.uniform(8, 11)
    if facing in ("x+", "x-"):
        w, d = d, w
    h = rnd.choice((3.2, 3.4, 5.8))
    z = ground_z(x, y)
    wall = mat(f"House{rnd.randrange(len(HOUSE_WALLS))}", HOUSE_WALLS[rnd.randrange(len(HOUSE_WALLS))])
    roof = mat(f"Roof{rnd.randrange(len(ROOFS))}", ROOFS[rnd.randrange(len(ROOFS))])
    g.box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z - 0.4, z + h, wall)
    rise = 2.2
    along_y = facing in ("x+", "x-")
    hw = (w if not along_y else d) / 2 + 0.4
    L = (d if not along_y else w) / 2 + 0.4
    v = []
    for t in (-L, L):
        for u, zz in ((-hw, z + h), (0, z + h + rise), (hw, z + h)):
            v.append((x + u, y + t, zz) if not along_y else (x + t, y + u, zz))
    pts = v
    f = [(0, 1, 4, 3), (1, 2, 5, 4), (0, 3, 5, 2)]
    thick = [(p[0], p[1], p[2] + 0.15) for p in pts]
    g.add((pts + thick, f + [tuple(i + 6 for i in q) for q in f]), roof)
    gable = []
    for t in (-L + 0.4, L - 0.4):                            # gables in the wall color, inside the eaves
        for u, zz in ((-hw + 0.4, z + h), (0, z + h + rise - 0.25), (hw - 0.4, z + h)):
            gable.append((x + u, y + t, zz) if not along_y else (x + t, y + u, zz))
    g.add((gable, [(0, 1, 2), (3, 5, 4)]), wall)


def tree_meshes(rnd):
    out = []
    for k in range(4):
        trunk = kit._prism_geo(6, 0.25, 0.18, 2.6)
        crown = kit._ico_geo(1.0, (0, 0, 4.2), (2.4 + 0.3 * k, 2.4 + 0.2 * k, 2.6 + 0.4 * k))
        v, f, owner = kit.merge(trunk, crown)
        mesh = bpy.data.meshes.new(f"TreeMesh{k}")
        mesh.from_pydata(v, [], f)
        mesh.materials.append(mat("Bark", "#4A3A2C"))
        mesh.materials.append(mat(f"Leaf{k}", LEAVES[k]))
        for poly, o in zip(mesh.polygons, owner):
            poly.material_index = o
        mesh.update()
        out.append(mesh)
    return out


def neighborhood(rnd):
    """Houses on the parallel streets (x = +-45 and +-80) and on the road to the hill; trees in the yards."""
    g = Geo()
    asphalt = mat("Asphalt", "#262B35")
    for sx in (-80, -45, 45, 80):
        g.box(sx - 3.5, sx + 3.5, -120, 150, -0.2, 0.02, asphalt)
    _road_strip(g, -3.5, 3.5, 150, 170, asphalt)
    spots = []
    for sx in (-80, -45, 45, 80):
        for side in (-1, 1):
            hx = sx + side * 11
            if abs(hx) < 27:
                continue
            for y in range(-110, 145, 14):
                if abs(y - 45) < 10:
                    continue
                spots.append((hx, y + rnd.uniform(-2, 2), "x-" if side > 0 else "x+"))
    for x, y, facing in spots:
        house(g, x, y, rnd, facing)
    obj = g.build("Neighborhood")
    trees = []
    meshes = tree_meshes(rnd)
    for k in range(260):
        x, y = rnd.uniform(-130, 130), rnd.uniform(-140, 330)
        if abs(x) < 30 and y < 150:
            continue                                     # nothing behind the townhouses that shows above the roofs
        if abs(x) < 9 and y < 260:
            continue
        kx, ky = -118.0, 150.0                           # the kitchen of scene 06 and the view from its window
        tx, ty = TOWER_XY
        t = ((x - kx) * (tx - kx) + (y - ky) * (ty - ky)) / ((tx - kx) ** 2 + (ty - ky) ** 2)
        in_view = 0 < t < 1 and math.hypot(x - kx - t * (tx - kx), y - ky - t * (ty - ky)) < 18
        if math.hypot(x - tx, y - ty) < 75 or in_view or math.hypot(x - kx, y - ky) < 20:
            continue                                     # top of the hill and its view of the town free
        s = rnd.uniform(0.8, 1.4)
        t = kit.instance(f"Tree{k}", meshes[k % 4], (x, y, ground_z(x, y) - 0.2), rotation=(0, 0, rnd.uniform(0, 6.28)))
        t.scale = (s, s, s)
        trees.append(t)
    return obj, trees


def field_material(name, a, b, scale):
    m = mat(name, a)
    nt = m.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(coord.outputs["Object"], wave.inputs["Vector"])
    step = nt.nodes.new("ShaderNodeMath"); step.operation = "GREATER_THAN"
    step.inputs[1].default_value = 0.5
    nt.links.new(wave.outputs["Fac"], step.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = kit.lin(a)
    mix.inputs["B"].default_value = kit.lin(b)
    nt.links.new(step.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], kit.principled(m).inputs["Base Color"])
    return m


def fields(rnd):
    """Plowed and cropped fields around the town (furrows by strip material, 1.6 m wide)."""
    kinds = [field_material("FieldPlowed", "#6B4E34", "#57402C", 0.62),
             field_material("FieldCrop", "#6E7A3A", "#55602E", 0.62),
             field_material("FieldStubble", "#9A8A5A", "#857548", 0.62)]
    out = []
    for k, (cx, cy) in enumerate([(x, y) for x in (-330, -250, -170, 170, 250, 330) for y in (-230, -140, -50, 40, 130, 220)]
                                 + [(x, -230) for x in (-90, 0, 90)] + [(x, -320) for x in (-90, 0, 90)]
                                 + [(x, -150) for x in (-90, 0, 90)] + [(x, y) for x in (-118, 118) for y in (-60, 30)]):
        w, d = rnd.uniform(66, 76), rnd.uniform(80, 86)
        nx, ny = 8, 8
        v = [(-w / 2 + w * i / nx, -d / 2 + d * j / ny, 0.0) for j in range(ny + 1) for i in range(nx + 1)]
        f = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
        obj = kit.mesh_object(f"Field{k}", v, f, [kinds[rnd.randrange(3)]], (cx, cy, 0))
        obj.rotation_euler.z = rnd.choice((0, math.pi / 2)) + rnd.uniform(-0.05, 0.05)
        for p in obj.data.vertices:
            wx = cx + p.co.x * math.cos(obj.rotation_euler.z) - p.co.y * math.sin(obj.rotation_euler.z)
            wy = cy + p.co.x * math.sin(obj.rotation_euler.z) + p.co.y * math.cos(obj.rotation_euler.z)
            p.co.z = ground_z(wx, wy) + (0.04 if k < 42 else 0.09)    # new fields on top (no coplanar faces)
        out.append(obj)
    return out


def build(rnd):
    t = terrain()
    tower = water_tower()
    nb, trees = neighborhood(rnd)
    return SimpleNamespace(terrain=t, tower=tower, neighborhood=nb, trees=trees, fields=fields(rnd))
