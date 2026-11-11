"""Ground of pangaea-never-split: a single spot at the edge of the desert in the interior of Pangaea, seen across 200 million
years. Green plain with a river to the west (x < 0), dune desert to the east (x > 20). The flora changes with the epoch:
Mesozoic (araucarias, cycads, ferns; no grass yet), then grass and broadleaf trees, and today
a highway with a small invented town.
"""

import math
from types import SimpleNamespace

import kit

SAND = "#C98B3C"
SAND_DARK = "#B5702E"
SCRUB = "#8E8A4A"
PLAIN = "#5B7A44"
MUD = "#6E5A3E"
RIVER_X = -9.0
DESERT_X = 22.0
ROAD_X = 6.0
SIZE = 260.0
CELL = 4.0


def ground_z(x, y):
    """Terrain: nearly flat plain, river bed and wave-like dunes in the desert. Under the highway the ground is
    flat across (the asphalt follows only y): the terrain does not poke through the asphalt nor fight it."""
    if abs(x - ROAD_X) < 6:
        x = ROAD_X
    z = 0.25 * math.sin(x * 0.05 + 1.3) * math.cos(y * 0.04)
    d = abs(x - RIVER_X)
    if d < 4.5:
        z -= 0.7 * (1 - d / 4.5) ** 0.7
    if x > DESERT_X:
        k = min(1.0, (x - DESERT_X) / 30)
        z += k * (1.6 * max(0.0, math.sin(x * 0.11 + y * 0.03)) ** 2 + 0.6 * math.sin(y * 0.07 + x * 0.02))
    return z


def terrain(rnd):
    n = int(SIZE / CELL)
    x0 = -SIZE / 2
    verts = [(x0 + i * CELL + rnd.uniform(-0.8, 0.8), x0 + j * CELL + rnd.uniform(-0.8, 0.8), 0.0)
             for j in range(n + 1) for i in range(n + 1)]
    verts = [(x, y, ground_z(x, y)) for x, y, _ in verts]
    faces, mats = [], []
    for j in range(n):
        for i in range(n):
            a, b = j * (n + 1) + i, j * (n + 1) + i + 1
            c, d = a + n + 1, b + n + 1
            for tri in ((a, b, d), (a, d, c)):
                cx = sum(verts[v][0] for v in tri) / 3
                faces.append(tri)
                if cx > DESERT_X + 6:
                    mats.append(3 if rnd.random() < 0.3 else 2)
                elif cx > DESERT_X - 6:
                    mats.append(1 if rnd.random() < 0.6 else 2)
                elif abs(cx - RIVER_X) < 3.5:
                    mats.append(4)
                else:
                    mats.append(5 if rnd.random() < 0.35 else 0)
    plain = kit.flat("Plain", PLAIN)
    obj = kit.mesh_object("Ground", verts, faces,
                          [plain, kit.flat("Scrub", SCRUB), kit.flat("Sand", SAND), kit.flat("SandDark", SAND_DARK),
                           kit.flat("Mud", MUD), kit.flat("Plain2", "#668A4C")], face_mats=mats)
    water = kit.water_grid("River", RIVER_X - 3.2, RIVER_X + 3.2, -SIZE / 2, SIZE / 2, -0.35,
                           kit.flat("RiverWater", "#2E5E7E", rough=0.25), cell=1.6, amp=0.04)
    return SimpleNamespace(obj=obj, plain=kit.principled(plain).inputs["Base Color"], water=water)


# ---------- Mesozoic flora ----------

def araucaria(name, xy, rnd, mats, h=None):
    """Araucaria: straight tall trunk, crown in flattened tiers at the top (typical Jurassic conifer)."""
    h = h or rnd.uniform(9, 16)
    trunk = kit._prism_geo(6, 0.28, 0.16, h * 0.82)
    tiers = []
    for k in range(4):
        z = h * (0.55 + 0.11 * k)
        r = h * (0.24 - 0.045 * k)
        tiers.append(kit._prism_geo(7, r, r * 0.25, h * 0.08, oz=z))
    tiers.append(kit._prism_geo(6, h * 0.05, 0.0, h * 0.12, oz=h * 0.9))
    v, f, owner = kit.merge(trunk, *tiers)
    return kit.mesh_object(name, v, f, mats, location=(xy[0], xy[1], ground_z(*xy) - 0.1),
                           face_mats=[0 if o == 0 else 1 for o in owner])


def cycad(name, xy, rnd, mats):
    """Cycad: short thick trunk with a crown of long palm-like leaves."""
    h = rnd.uniform(0.8, 1.6)
    parts = [kit._prism_geo(7, 0.3, 0.24, h)]
    for k in range(9):
        a = 2 * math.pi * k / 9 + rnd.uniform(-0.2, 0.2)
        L = rnd.uniform(1.4, 2.0)
        tip = (math.cos(a) * L, math.sin(a) * L, h + 0.5)
        side = (-math.sin(a) * 0.22, math.cos(a) * 0.22, 0)
        mid = (math.cos(a) * L * 0.5, math.sin(a) * L * 0.5, h + 0.75)
        parts.append(([(0, 0, h), (mid[0] + side[0], mid[1] + side[1], mid[2]), tip,
                       (mid[0] - side[0], mid[1] - side[1], mid[2])], [(0, 1, 2, 3)]))
    v, f, owner = kit.merge(*parts)
    obj = kit.mesh_object(name, v, f, mats, location=(xy[0], xy[1], ground_z(*xy) - 0.05),
                          face_mats=[0 if o == 0 else 1 for o in owner])
    obj.rotation_euler.z = rnd.uniform(0, 6.28)
    return obj


def fern(name, xy, rnd, mat, scale=1.0):
    """Fern: 6 to 8 fronds that rise and arch outward, each with alternating leaflets that
    shrink toward the tip (the feather shape that reads at a glance)."""
    parts = []
    for k in range(rnd.randint(6, 8)):
        a = 2 * math.pi * k / 7 + rnd.uniform(-0.3, 0.3)
        L = rnd.uniform(0.8, 1.2) * scale
        c, s = math.cos(a), math.sin(a)
        rise = rnd.uniform(0.5, 0.75) * scale
        steps = 7
        spine = []
        for i in range(steps + 1):
            u = i / steps
            spine.append((c * L * u, s * L * u, 0.04 + rise * math.sin(u * math.pi * 0.8)))
        for i in range(steps):
            p0, p1 = spine[i], spine[i + 1]
            w = 0.28 * scale * (1 - i / steps) + 0.06
            for side in (1, -1):
                tip = ((p0[0] + p1[0]) / 2 - s * w * side, (p0[1] + p1[1]) / 2 + c * w * side,
                       (p0[2] + p1[2]) / 2 - 0.04 * scale)
                parts.append(([p0, tip, p1], [(0, 1, 2)]))
    v, f, _ = kit.merge(*parts)
    obj = kit.mesh_object(name, v, f, [mat], location=(xy[0], xy[1], ground_z(*xy)))
    obj.rotation_euler.z = rnd.uniform(0, 6.28)
    return obj


def mesozoic_flora(rnd, keep_out):
    """Groves of araucarias, cycads and ferns on the plain (x < DESERT_X). keep_out: (x, y, radius)."""
    trunk, needles = kit.flat("ArauTrunk", "#5A4632"), kit.flat("ArauNeedles", "#2F4F3A")
    cyc_trunk, fronds = kit.flat("CycTrunk", "#6B5A3E"), kit.flat("CycFronds", "#4E7A3A")
    fern_mat = kit.flat("Fern", "#5E8C40")
    objs = []

    def free(x, y, r=2.0):
        return all(math.hypot(x - kx, y - ky) > kr + r for kx, ky, kr in keep_out) and abs(x - RIVER_X) > 4

    tries = 0
    while len(objs) < 160 and tries < 3000:
        tries += 1
        x, y = rnd.uniform(-120, DESERT_X - 2), rnd.uniform(-120, 120)
        if not free(x, y, 3):
            continue
        kind = rnd.random()
        if kind < 0.35 and (x < -14 or math.hypot(x, y) > 30):
            objs.append(araucaria(f"Arau{len(objs)}", (x, y), rnd, [trunk, needles]))
        elif kind < 0.6:
            objs.append(cycad(f"Cycad{len(objs)}", (x, y), rnd, [cyc_trunk, fronds]))
        else:
            objs.append(fern(f"Fern{len(objs)}", (x, y), rnd, fern_mat, rnd.uniform(0.8, 1.4)))
    for k in range(60):                                    # ferns near the camera (foreground)
        a, r = rnd.uniform(0, 6.28), rnd.uniform(2.5, 12)
        x, y = r * math.cos(a), r * math.sin(a)
        if free(x, y, 0.5) and x < DESERT_X - 4:
            objs.append(fern(f"FernNear{k}", (x, y), rnd, fern_mat, rnd.uniform(0.7, 1.2)))
    return objs


# ---------- human epoch ----------

def grass(rnd, count=900):
    """Tufts of grass (grass only spreads long after the dinosaurs)."""
    mat = kit.flat("GrassTuft", "#8A9A4E")
    parts = []
    for _ in range(count):
        x, y = rnd.uniform(-60, DESERT_X - 3), rnd.uniform(-60, 80)
        if abs(x - RIVER_X) < 4:
            continue
        z = ground_z(x, y)
        for k in range(3):
            a = rnd.uniform(0, 6.28)
            h = rnd.uniform(0.35, 0.7)
            parts.append(([(x + 0.06 * math.cos(a + 1.6), y + 0.06 * math.sin(a + 1.6), z),
                           (x - 0.06 * math.cos(a + 1.6), y - 0.06 * math.sin(a + 1.6), z),
                           (x + 0.15 * math.cos(a), y + 0.15 * math.sin(a), z + h)], [(0, 1, 2)]))
    v, f, _ = kit.merge(*parts)
    return [kit.mesh_object("Grass", v, f, [mat])]


def broadleaf(name, xy, rnd, mats):
    h = rnd.uniform(5, 8)
    trunk = kit._prism_geo(6, 0.22, 0.15, h * 0.6)
    crown = kit._ico_geo(h * 0.32, (0, 0, h * 0.72), (1.1, 1.1, 0.8))
    v, f, owner = kit.merge(trunk, crown)
    return kit.mesh_object(name, v, f, mats, location=(xy[0], xy[1], ground_z(*xy) - 0.1),
                           face_mats=[0 if o == 0 else 1 for o in owner])


def savanna_trees(rnd, keep_out):
    mats = [kit.flat("OakTrunk", "#5A4632"), kit.flat("OakLeaves", "#4C7A3E")]
    objs = []
    while len(objs) < 45:
        x, y = rnd.uniform(-110, DESERT_X - 5), rnd.uniform(-100, 120)
        if abs(x - RIVER_X) < 5 or any(math.hypot(x - kx, y - ky) < kr + 3 for kx, ky, kr in keep_out):
            continue
        objs.append(broadleaf(f"Oak{len(objs)}", (x, y), rnd, mats))
    return objs


# ---------- hoje: rodovia e cidadezinha ----------

def highway(rnd):
    asphalt, line = kit.flat("Asphalt", "#2A2D33", rough=0.8), kit.flat("RoadLine", "#E8C46A", emission="#E8C46A",
                                                                           strength=0.6)
    objs = []
    n = 80
    verts, faces = [], []
    for k in range(n + 1):
        y = -SIZE / 2 + SIZE * k / n
        for x in (ROAD_X - 3.6, ROAD_X + 3.6):
            verts.append((x, y, ground_z(ROAD_X, y) + 0.06))
    for k in range(n):
        faces.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2))
    objs.append(kit.mesh_object("Road", verts, faces, [asphalt]))
    dashes = []
    for k in range(int(SIZE / 6)):
        y = -SIZE / 2 + k * 6
        z = ground_z(ROAD_X, y) + 0.08
        dashes.append(([(ROAD_X - 0.08, y, z), (ROAD_X + 0.08, y, z), (ROAD_X + 0.08, y + 3, z),
                        (ROAD_X - 0.08, y + 3, z)], [(0, 1, 2, 3)]))
    v, f, _ = kit.merge(*dashes)
    objs.append(kit.mesh_object("RoadDashes", v, f, [line]))
    sign_post, sign_face = kit.flat("SignPost", "#8A94A6", metallic=0.6, rough=0.4), kit.flat("SignFace", "#2F6B4A")
    objs.append(kit.box("SignPostL", (ROAD_X - 4.6, 14, ground_z(ROAD_X - 4.6, 14)), (0.08, 0.08, 3.6), sign_post))
    objs.append(kit.box("SignFace", (ROAD_X - 4.55, 14, ground_z(ROAD_X - 4.6, 14) + 2.4), (0.1, 2.2, 1.2), sign_face))
    lamp_on = kit.flat("LampGlow", kit.WARM, emission=kit.WARM, strength=8.0)
    for k, y in enumerate(range(-60, 120, 30)):
        z = ground_z(ROAD_X + 4.4, y)
        objs.append(kit.box(f"LampPost{k}", (ROAD_X + 4.4, y, z), (0.12, 0.12, 7.0), sign_post))
        objs.append(kit.box(f"LampHead{k}", (ROAD_X + 3.6, y, z + 7.0), (1.4, 0.4, 0.2), lamp_on))
    return objs


def town(rnd):
    """Small invented town west of the highway: low houses and shops with lit windows."""
    objs = []
    walls = ["#3B4458", "#4A4E5C", "#55505A", "#3F4A5A"]
    for k in range(14):
        x = rnd.uniform(-24, ROAD_X - 11)
        y = 12 + k * 6 + rnd.uniform(-1.5, 1.5)
        sx, sy, sz = rnd.uniform(6, 12), rnd.uniform(6, 12), rnd.uniform(3.5, 8)
        mat, _, _, _ = kit.window_material(f"TownWall{k}", rnd.choice(walls), seed=k + 3)
        objs.append(kit.box(f"Town{k}", (x, y, ground_z(x, y) - 0.3), (sx, sy, sz), mat))
    return objs


def car(name):
    body, glass = kit.flat("CarBody", "#9AA3B5", metallic=0.3, rough=0.5), kit.flat("CarGlass", "#121826", rough=0.2)
    head = kit.flat("Headlight", "#FFF3D6", emission="#FFF3D6", strength=25.0)
    tail = kit.flat("Taillight", "#C0392B", emission="#E0412F", strength=12.0)
    v, f, owner = kit.merge(kit._box_geo(1.8, 4.4, 0.75, -0.9, -2.2, 0.3), kit._box_geo(1.6, 2.2, 0.6, -0.8, -1.2, 1.05),
                            kit._box_geo(0.5, 0.06, 0.26, -0.85, 2.2, 0.7), kit._box_geo(0.5, 0.06, 0.26, 0.35, 2.2, 0.7),
                            kit._box_geo(0.35, 0.05, 0.15, -0.8, -2.25, 0.78), kit._box_geo(0.35, 0.05, 0.15, 0.45, -2.25, 0.78))
    obj = kit.mesh_object(name, v, f, [body, glass, head, tail],
                          face_mats=[{0: 0, 1: 1, 2: 2, 3: 2, 4: 3, 5: 3}[o] for o in owner])
    import bpy
    beam = bpy.data.objects.new(f"{name}Beam", bpy.data.lights.new(f"{name}Beam", "SPOT"))
    beam.data.energy, beam.data.spot_size, beam.data.color = 4000.0, math.radians(50), (1.0, 0.92, 0.8)
    beam.location, beam.rotation_euler, beam.parent = (0, 2.4, 0.8), (math.radians(-80), 0, 0), obj
    bpy.context.collection.objects.link(beam)
    return obj, beam


# ---------- monsoon sky (scene 03) ----------

def monsoon_clouds(rnd):
    """Wall of dark clouds on the western horizon (toward the coast), with curtains of rain."""
    cloud = kit.flat("MonsoonCloud", "#3C4352", rough=1.0)
    rain = kit.flat("Rain", "#7A8496", rough=1.0)
    parts, sheets = [], []
    for k in range(60):
        y = -380 + 760 * k / 59 + rnd.uniform(-8, 8)
        x = rnd.uniform(-420, -360)
        r = rnd.uniform(34, 52)
        parts.append(kit._ico_geo(r, (x, y, rnd.uniform(60, 80)), (1.0, 1.0, 0.45)))
        if k % 3 == 0:
            sheets.append(([(x + 20, y - 18, -5), (x + 20, y + 18, -5), (x + 6, y + 18, 62), (x + 6, y - 18, 62)],
                           [(0, 1, 2, 3)]))
    v, f, _ = kit.merge(*parts)
    return [kit.mesh_object("Monsoon", v, f, [cloud])]
