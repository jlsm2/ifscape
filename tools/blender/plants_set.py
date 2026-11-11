"""Set of plants-extinct: Mediterranean village square on a hill shoulder facing south (direction.md section 1).

Units in meters. Origin = vendor's eye on the ground (camera at 1.65 m); +y = south (toward the sea), +x = west (right
of someone looking at the sea), z = 0 at the paving. Sun at 10:30 at ~38 deg N: azimuth 140 deg (southeast, front-left), elevation 55 deg.

Layers: stall (vendor) -> square with the plane tree and people -> whitewashed houses climbing the east hill (left) ->
sea of the cove below -> headland on the other side (forest on the left, terraces on the right, sharp line) -> horizon.

Number changes relative to the plan, for geometry (noted in NOTES.md):
- the square sits 35 m above the sea (the plan says ~150 m): at 150 m the parapet hides the near sea and the boats at 400 m
  are hidden behind it (angle of 20 deg downward); at 35 m they appear at ~25 px.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector, noise

import kit
import plants_models as pm
from kit import lin

SEA_Z = -35.0
SUN_AZ, SUN_EL = 140.0, 55.0
TREE_POS = Vector((-2.4, 13.6, 0.0))
PLAZA = (-9.0, 18.0, -6.0, 19.6)       # x0, x1, y0, y1


def sun_vector():
    a, e = math.radians(SUN_AZ), math.radians(SUN_EL)
    # compass -> scene: north = -y, east = -x
    return Vector((-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


# ---------- materiais ----------

def make_mats():
    M = {}
    M["bark"] = pm.bark_mat("Bark")
    M["leaf_now"] = pm.plant_mat("LeafNow", pm.LEAF, rough=0.8, var=None, noise_scale=0.35)
    # dry crown: #8A5A2B in shade and #A8703A on the sun side (separates from the green in deuteranopia);
    # alive and 1 YEAR follow the single ramp color
    sun_side = (pm.LEAF[0], pm.LEAF_EDGE[1], pm.LEAF[2], pm.LEAF[3])
    M["leaf_week"] = pm.plant_mat("LeafWeek", pm.LEAF, rough=0.8, var=None, noise_scale=0.6, sun_side=sun_side,
                                   sun_dir=sun_vector())
    M["grass"] = pm.plant_mat("GrassTuft", pm.GRASS, tip=pm.GRASS_TIP, height=0.3)
    M["hedge"] = pm.plant_mat("Hedge", pm.HEDGE, noise_scale=2.0)
    M["flower"] = pm.plant_mat("Flower", pm.FLOWER, var=(0.95, 1.05))
    M["flower2"] = pm.plant_mat("Flower2", pm.FLOWER2, var=(0.95, 1.05))
    M["soil"] = pm.plant_mat("Soil", pm.SOIL, var=None, noise_scale=3.0)
    M["wood"] = pm.wood_mat("Wood", pm.WOOD, aged="#8E8478")
    M["logbark"] = pm.fixed_mat("LogBark", "#6E5A44", var=(0.85, 1.15))
    M["logend"] = pm.fixed_mat("LogEnd", "#D9A766", var=(0.9, 1.1))
    M["awning"] = pm.awning_mat()
    M["metal"] = pm.fixed_mat("Metal", "#3A3A3C", rough=0.6, spec=0.3)
    M["ember"] = pm.fixed_mat("Ember", "#3A2010", emission=pm.LUZ, strength=1.0)
    M["coal"] = pm.fixed_mat("Coal", "#2E2622", rough=0.95)
    M["flame"] = pm.fixed_mat("Flame", "#3A2010", emission="#F5A524", strength=1.1)
    M["cold_coal"] = pm.fixed_mat("ColdCoal", "#3A3634")
    M["wall"] = pm.fixed_mat("Wall", pm.WALL, rough=0.95, var=(0.96, 1.03))
    M["roof"] = pm.fixed_mat("Roof", pm.ROOF, rough=0.85, var=(0.9, 1.08))
    M["shutter"] = pm.fixed_mat("Shutter", pm.SHUTTER, rough=0.8)
    M["window"] = pm.fixed_mat("Window", "#26303A", rough=0.6)
    M["door"] = pm.fixed_mat("Door", "#6A4A30", rough=0.85)
    M["stone"] = pm.stone_mat("Stone")
    M["paving"] = pm.stone_mat("Paving", "#D2C6AA", scale=2.2, mortar="#B4A88E")
    M["terracotta"] = pm.fixed_mat("Terracotta", "#B8653E", rough=0.9)
    M["cloth"] = pm.fixed_mat("WetCloth", "#7A8088", rough=0.35, spec=0.5)
    M["fish"] = pm.fixed_mat("Fish", "#B8C2CC", rough=0.3, spec=0.5)
    M["ham"] = pm.fixed_mat("Ham", "#B0605A", rough=0.7)
    M["cheese"] = pm.fixed_mat("Cheese", "#E8D9A0", rough=0.75)
    M["sack"] = pm.fixed_mat("Sack", "#C9B48A", rough=0.95)
    M["flour"] = pm.fixed_mat("Flour", "#F0EBE0", rough=0.95)
    M["bread"] = pm.fixed_mat("Bread", "#C08A4A", rough=0.9)
    M["fly"] = pm.fixed_mat("Fly", "#141414", rough=0.5)
    M["fruit"] = [pm.fixed_mat("Apple", "#B8322A", rough=0.45, spec=0.4),
                  pm.fixed_mat("Lemon", "#E6CF3A", rough=0.45, spec=0.4),
                  pm.fixed_mat("Fig", "#5A2E5A", rough=0.45, spec=0.4),
                  pm.fixed_mat("Pear", "#A8B848", rough=0.45, spec=0.4)]
    M["fruit_rot"] = [pm.rotten_fruit_mat("AppleRot", "#B8322A"), pm.rotten_fruit_mat("LemonRot", "#E6CF3A"),
                      pm.rotten_fruit_mat("FigRot", "#5A2E5A"), pm.rotten_fruit_mat("PearRot", "#A8B848")]
    M["boat_white"] = pm.fixed_mat("BoatWhite", "#D9D6CC", rough=0.6)
    M["foam"] = pm.fixed_mat("Foam", "#E8EEF2", rough=0.9, emission="#E8EEF2", strength=0.15)
    M["smoke"] = pm.fixed_mat("Smoke", "#B4B0A8", rough=1.0, emission="#B4B0A8", strength=0.2)
    return M


# ---------- sky and light ----------

def build_world():
    """Sky: gradient zenith #3F7FC8 -> horizon #B8D4EA for the camera and for reflections (Is Camera Ray MAX Is
    Glossy Ray; the sea reflects the sky); for the diffuse light, a blue ambient that gives ~40% shadow pulled toward blue."""
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    world.use_sun_shadow = False
    n, L = world.node_tree.nodes, world.node_tree.links
    bg = n.get("Background") or n.new("ShaderNodeBackground")
    out = n.get("World Output") or n.new("ShaderNodeOutputWorld")
    coord = n.new("ShaderNodeTexCoord")
    norm = n.new("ShaderNodeVectorMath"); norm.operation = "NORMALIZE"
    L.new(coord.outputs["Generated"], norm.inputs[0])
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(norm.outputs[0], sep.inputs[0])
    clampz = n.new("ShaderNodeMath"); clampz.operation = "MAXIMUM"
    clampz.inputs[1].default_value = 0.0
    L.new(sep.outputs["Z"], clampz.inputs[0])
    r = n.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "EASE"
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin("#B8D4EA")
    e[1].position, e[1].color = 0.75, lin("#3F7FC8")
    m = e.new(0.12); m.color = lin("#8DB6E0")
    L.new(clampz.outputs[0], r.inputs["Fac"])
    L.new(r.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    amb = n.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = lin("#8FA8CC")
    amb.inputs["Strength"].default_value = 1.0
    path = n.new("ShaderNodeLightPath")
    mx = n.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    L.new(path.outputs["Is Camera Ray"], mx.inputs[0])
    L.new(path.outputs["Is Glossy Ray"], mx.inputs[1])
    pick = n.new("ShaderNodeMixShader")
    L.new(mx.outputs[0], pick.inputs["Fac"])
    L.new(amb.outputs[0], pick.inputs[1])
    L.new(bg.outputs[0], pick.inputs[2])
    L.new(pick.outputs[0], out.inputs["Surface"])
    return SimpleNamespace(world=world, ambient=amb.inputs["Strength"], sky=bg.inputs["Strength"])


def build_sun(energy=3.4):
    ld = bpy.data.lights.new("Sun", "SUN")
    ld.energy = energy
    ld.color = (1.0, 0.95, 0.88)
    ld.angle = math.radians(1.5)
    ld.specular_factor = 0.45
    o = bpy.data.objects.new("Sun", ld)
    bpy.context.collection.objects.link(o)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = sun_vector().to_track_quat("Z", "Y")
    return o


def clouds(mat, rnd):
    """A few flat clouds in the southwest (the same ones throughout the video), far and high, low-poly."""
    out = []
    for k, (yaw, el, dist, w) in enumerate(((19, 16, 2600, 260), (34, 11, 3200, 380), (48, 19, 2400, 300),
                                            (62, 9, 3600, 420), (-55, 22, 3000, 260))):
        a, e = math.radians(yaw), math.radians(el)
        c = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))) * dist
        geos = []
        for j in range(5):
            off = Vector((rnd.uniform(-0.5, 0.5) * w, rnd.uniform(-0.15, 0.15) * w, rnd.uniform(0, 0.12) * w))
            rr = w * rnd.uniform(0.18, 0.3)
            geos.append(pm.lumpy_ico(rr, tuple(c + off), (1.0, 0.7, 0.42), rnd, 0.12))
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"Cloud{k}", (v, f), [mat])
        o.visible_shadow = False
        out.append(o)
    return out


# ---------- ground ----------

def hill_z(x, y):
    """East hill (left): rises from x = -9 and descends to the sea to the south."""
    d = max(0.0, -x - 9.0)
    z = 0.45 * min(d, 40.0) + 0.6 * max(0.0, min(d, 190.0) - 40.0)
    z += 2.0 * noise.noise(Vector((x * 0.02, y * 0.02, 0.3)))
    if y > 28.0:
        z -= 0.22 * (y - 28.0) + 0.0016 * (y - 28.0) ** 2
    if x > -9.6:
        z = min(z, -0.5)            # nothing crosses the paving at the edge of the square
    return z


def grid(name, x0, x1, y0, y1, cell, zf, mats, face_mat=None):
    nx, ny = max(2, int((x1 - x0) / cell)), max(2, int((y1 - y0) / cell))
    verts = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny
            verts.append((x, y, zf(x, y)))
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    fm = None
    if face_mat:
        fm = [face_mat(*[sum(verts[k][c] for k in f) / 4 for c in range(3)]) for f in faces]
    return kit.mesh_object(name, verts, faces, mats, face_mats=fm)


def terrace_mat(name, colors_a, colors_b, wall="#B8AE96", band=3.0, haze=0.0, forest=None, line_x=None,
                forest_side=-1):
    """Terraced slope: strips by height (step of 'band' m) alternating crop A/B, with the line of the stone
    wall (fixed) at the foot of each step. With 'forest', the side x < line_x (forest_side -1) becomes forest floor."""
    mat, n, L, p = pm.node_mat(name, 0.9, 0.15)
    ca = pm.state_ramp(n, L, pm.hazed(colors_a, haze) if haze else colors_a)
    cb = pm.state_ramp(n, L, pm.hazed(colors_b, haze) if haze else colors_b)
    coord = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Object"], sep.inputs[0])
    # slow deformation of the strip so it does not look ruler-straight
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.02
    L.new(coord.outputs["Object"], nz.inputs["Vector"])
    warp = n.new("ShaderNodeMath"); warp.operation = "MULTIPLY_ADD"
    L.new(nz.outputs["Fac"], warp.inputs[0])
    warp.inputs[1].default_value = band * 1.2
    L.new(sep.outputs["Z"], warp.inputs[2])
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"
    L.new(warp.outputs[0], div.inputs[0])
    div.inputs[1].default_value = band
    fr = n.new("ShaderNodeMath"); fr.operation = "FRACT"
    L.new(div.outputs[0], fr.inputs[0])
    fl = n.new("ShaderNodeMath"); fl.operation = "FLOOR"
    L.new(div.outputs[0], fl.inputs[0])
    half = n.new("ShaderNodeMath"); half.operation = "PINGPONG"
    half.inputs[1].default_value = 1.0
    L.new(fl.outputs[0], half.inputs[0])
    ab = n.new("ShaderNodeMix"); ab.data_type = "RGBA"
    L.new(half.outputs[0], ab.inputs["Factor"])
    L.new(ca, ab.inputs["A"]); L.new(cb, ab.inputs["B"])
    wl = n.new("ShaderNodeMath"); wl.operation = "LESS_THAN"
    wl.inputs[1].default_value = 0.14
    L.new(fr.outputs[0], wl.inputs[0])
    wm = n.new("ShaderNodeMix"); wm.data_type = "RGBA"
    L.new(wl.outputs[0], wm.inputs["Factor"])
    L.new(ab.outputs["Result"], wm.inputs["A"])
    wm.inputs["B"].default_value = lin(pm.hazed((wall,), haze)[0] if haze else wall)
    col = wm.outputs["Result"]
    if forest is not None:
        fc = pm.state_ramp(n, L, pm.hazed(forest, haze) if haze else forest)
        side = n.new("ShaderNodeMath"); side.operation = "LESS_THAN" if forest_side < 0 else "GREATER_THAN"
        L.new(sep.outputs["X"], side.inputs[0])
        side.inputs[1].default_value = line_x
        fm = n.new("ShaderNodeMix"); fm.data_type = "RGBA"
        L.new(side.outputs[0], fm.inputs["Factor"])
        L.new(col, fm.inputs["A"]); L.new(fc, fm.inputs["B"])
        col = fm.outputs["Result"]
    L.new(col, p.inputs["Base Color"])
    return mat


HEAD_LINE_X = 95.0          # forest x terraces line on the headland (~5 deg to the right of the center of 01)


def headland_z(x, y):
    """Headland on the other side of the cove: 200 m ridge (x < -150) that descends to ~40 m at the tip (x 260)."""
    if x < -150:
        h = 200.0 + 30 * noise.noise(Vector((x * 0.003, 0.5, 0.1)))
    else:
        u = min(1.0, (x + 150) / 410.0)
        h = 200.0 * (1 - u) + 40.0 * u
    yc = 1500.0 + 0.12 * x
    prof = max(0.0, 1.0 - ((y - yc) / 520.0) ** 2)
    end = max(0.0, min(1.0, (300.0 - x) / 60.0))
    z = SEA_Z - 6.0 + (h + 6.0) * prof ** 0.7 * end
    z += 6.0 * noise.noise(Vector((x * 0.01, y * 0.01, 1.7)))
    return z


def build_ground(M):
    out = SimpleNamespace()
    x0, x1, y0, y1 = PLAZA
    # paving of the square (0.4 m slab) and the retaining wall of the south edge
    out.plaza = kit.box_span("Plaza", x0 - 4, x1, y0, y1, -0.4, 0.4, M["paving"])
    out.retaining = kit.box_span("PlazaWall", -9.6, x1, y1 - 0.01, y1 + 0.5, -8.0, 7.6, M["stone"])
    # low parapet (0.5 m) in segments (YEARS: 2 fall)
    out.parapet, out.rubble = [], []
    segs = [(-9.6, -2.5), (-2.5, 1.5), (1.5, 5.5), (5.5, 9.5), (9.5, 13.5), (13.5, 18.0)]
    for k, (a, b) in enumerate(segs):
        out.parapet.append(kit.box_span(f"Parapet{k}", a, b, y1 - 0.05, y1 + 0.45, 0.0, 0.5, M["stone"]))
    rnd = random.Random(4)
    for k in (2, 4):
        a, b = segs[k]
        geos = []
        for j in range(9):
            s = rnd.uniform(0.18, 0.32)
            geos.append(kit._box_geo(s * 1.4, s, s * 0.8, rnd.uniform(a, b - 0.4), y1 + rnd.uniform(-0.6, 0.5),
                                     0.0 if j < 6 else rnd.uniform(0.1, 0.2)))
        geos.append(kit._box_geo(b - a - 0.6, 0.4, 0.18, a + 0.3, y1 - 0.05, 0.0))
        v, f, _ = kit.merge(*geos)
        out.rubble.append(pm.obj_from(f"Rubble{k}", (v, f), [M["stone"]]))
    # east hill with terraces (vineyard / wheat) and forest on top
    M["hill"] = terrace_mat("HillTerr", pm.VINE, pm.WHEAT, band=3.0, forest=pm.FOREST, line_x=-150.0)
    out.hill = grid("EastHill", -330.0, -8.0, -60.0, 360.0, 6.0, hill_z, [M["hill"]])
    # headland and sea
    M["head"] = terrace_mat("HeadTerr", pm.FIELD_FAR, pm.PLOWED, wall="#B8AE96", band=8.0, haze=0.12,
                            forest=pm.FOREST_FLOOR, line_x=HEAD_LINE_X)
    out.headland = grid("Headland", -2600.0, 320.0, 800.0, 2300.0, 30.0, headland_z, [M["head"]])
    out.sea = build_sea()
    return out


def west_hill_z(x, y):
    """West hill (right), the "this hill" of 05 (2026-10-24, camera and keyframes): rises to the west from
    the end of the square (x 18) to ~100 m at the tower (254, 54) and descends to the sea to the south. It only exists more than ~58 deg to the
    right of the center of 01 (bearing seen from the stall): so it does not enter H1/H2, the sea of 02 or the sky bridge."""
    if x <= 18.0:
        return -45.0
    d = math.hypot(x - 254.0, y - 54.0)            # hill with the peak at the tower (concave cone)
    rise = 104.0 * max(0.0, 1.0 - d / 260.0) ** 1.4 + 2.0 * noise.noise(Vector((x * 0.02, y * 0.02, 2.1)))
    bearing = math.degrees(math.atan2(x, y))
    u = max(0.0, min(1.0, (bearing - 50.0) / 28.0))
    k = u * u * (3 - 2 * u)
    z = k * rise + (1 - k) * -45.0
    if y > 40.0:
        z -= 0.22 * (y - 40.0) + 0.0016 * (y - 40.0) ** 2
    return z


def build_west_hill(M):
    return grid("WestHill", 18.0, 520.0, -80.0, 330.0, 6.0, west_hill_z, [M["hill"]])


def build_sea():
    """Sea: dark Principled (roughness 0.2) that reflects the sky; small crests by noise stretched 1:4 broken up."""
    mat, n, L, p = pm.node_mat("Sea", 0.22, 0.28)
    coord = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.05, 0.2, 1.0)
    L.new(coord.outputs["Object"], mp.inputs["Vector"])
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 3.0
    tex.inputs["Detail"].default_value = 3.0
    L.new(mp.outputs[0], tex.inputs["Vector"])
    crest = n.new("ShaderNodeMapRange")
    crest.inputs["From Min"].default_value, crest.inputs["From Max"].default_value = 0.66, 0.72
    L.new(tex.outputs["Fac"], crest.inputs["Value"])
    brk = n.new("ShaderNodeTexNoise")
    brk.inputs["Scale"].default_value = 0.05
    L.new(coord.outputs["Object"], brk.inputs["Vector"])
    bm = n.new("ShaderNodeMapRange")
    bm.inputs["From Min"].default_value, bm.inputs["From Max"].default_value = 0.5, 0.6
    L.new(brk.outputs["Fac"], bm.inputs["Value"])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    L.new(crest.outputs["Result"], mul.inputs[0])
    L.new(bm.outputs["Result"], mul.inputs[1])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(mul.outputs[0], mix.inputs["Factor"])
    # dark near, lighter far (the sky Fresnel does the rest)
    dist = n.new("ShaderNodeCameraData")
    far = n.new("ShaderNodeMapRange")
    far.inputs["From Min"].default_value, far.inputs["From Max"].default_value = 300.0, 4000.0
    L.new(dist.outputs["View Distance"], far.inputs["Value"])
    near_far = n.new("ShaderNodeMix"); near_far.data_type = "RGBA"
    L.new(far.outputs["Result"], near_far.inputs["Factor"])
    near_far.inputs["A"].default_value = lin("#2B66A8")
    near_far.inputs["B"].default_value = lin("#1E4F8A")
    L.new(near_far.outputs["Result"], mix.inputs["A"])
    mix.inputs["B"].default_value = lin("#D8E2EA")
    L.new(mix.outputs["Result"], p.inputs["Base Color"])
    sea = kit.mesh_object("Sea", [(-6000, -200, 0), (6000, -200, 0), (6000, 12000, 0), (-6000, 12000, 0)],
                          [(0, 1, 2, 3)], [mat], (0, 0, SEA_Z))
    return sea


# ---------- espalhamento (Geometry Nodes) ----------

def scatter_group(name, collection, distance, density, seed, scale=(0.8, 1.2), zmin=None, zmax=None, xmax=None,
                  xmin=None, ymax=None, align=False):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = distance
    dist.inputs["Density Max"].default_value = density
    dist.inputs["Seed"].default_value = seed
    L.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    pts = dist.outputs["Points"]
    # only on upward-facing faces (nothing grows on the flower bed wall nor on a steep bank)
    nsep = N.new("ShaderNodeSeparateXYZ")
    L.new(dist.outputs["Normal"], nsep.inputs[0])
    steep = N.new("ShaderNodeMath"); steep.operation = "LESS_THAN"
    steep.inputs[1].default_value = 0.5
    L.new(nsep.outputs["Z"], steep.inputs[0])
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(pos.outputs[0], sep.inputs[0])
    conds = [steep.outputs[0]]
    for axis, lim, op in (("Z", zmin, "LESS_THAN"), ("Z", zmax, "GREATER_THAN"), ("X", xmax, "GREATER_THAN"),
                          ("X", xmin, "LESS_THAN"), ("Y", ymax, "GREATER_THAN")):
        if lim is None:
            continue
        c = N.new("ShaderNodeMath"); c.operation = op
        L.new(sep.outputs[axis], c.inputs[0])
        c.inputs[1].default_value = lim
        conds.append(c.outputs[0])
    if conds:
        acc = conds[0]
        for c in conds[1:]:
            mx = N.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
            L.new(acc, mx.inputs[0]); L.new(c, mx.inputs[1])
            acc = mx.outputs[0]
        dele = N.new("GeometryNodeDeleteGeometry")
        dele.domain = "POINT"
        L.new(pts, dele.inputs["Geometry"])
        L.new(acc, dele.inputs["Selection"])
        pts = dele.outputs["Geometry"]
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = collection
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rr = N.new("FunctionNodeRandomValue"); rr.data_type = "FLOAT_VECTOR"
    rr.inputs["Max"].default_value = (0, 0, 2 * math.pi)
    rr.inputs["Seed"].default_value = seed + 1
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"
    rs.inputs["Min"].default_value, rs.inputs["Max"].default_value = scale
    rs.inputs["Seed"].default_value = seed + 2
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    L.new(pts, inst.inputs["Points"])
    L.new(info.outputs["Instances"], inst.inputs["Instance"])
    L.new(rr.outputs["Value"], inst.inputs["Rotation"])
    L.new(rs.outputs["Value"], inst.inputs["Scale"])
    L.new(inst.outputs["Instances"], gout.inputs["Geometry"])
    return ng


def carrier(name, src, ng):
    """Object that only carries instances (copy of the mesh of 'src'): on/off by state with hide_render."""
    o = bpy.data.objects.new(name, src.data)
    bpy.context.collection.objects.link(o)
    o.location = src.location
    mod = o.modifiers.new(ng.name, "NODES")
    mod.node_group = ng
    return o


def model_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    bpy.context.view_layer.layer_collection.children[name].exclude = True
    return col


def _link_only(col, obj):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)


def tree_models(M, rnd):
    """Models for the forest and the slopes: 3 broadleaf trees (crown in masses) and 3 bare ones (trunk + branches),
    1 fallen trunk. Origin at the foot."""
    leafy, bare, fallen = model_collection("LeafyTrees"), model_collection("BareTrees"), model_collection("Fallen")
    forest_leaf = pm.plant_mat("ForestLeaf", pm.FOREST, rough=0.85, var=(0.85, 1.12))
    trunk = pm.fixed_mat("ForestTrunk", "#6A5E50")
    dead = pm.fixed_mat("DeadTrunk", "#8A857C", var=(0.9, 1.1))
    for k, (h, r) in enumerate(((7.0, 2.8), (9.0, 3.4), (5.5, 2.4))):
        g1 = kit._prism_geo(6, 0.22, 0.14, h * 0.55)
        geos = [pm.lumpy_ico(r * u, (dx, dy, h * 0.55 + r * 0.55 + dz), (1, 1, 0.8), rnd, 0.2)
                for u, dx, dy, dz in ((0.8, 0, 0, 0), (0.6, r * 0.5, 0.2, -0.3), (0.6, -r * 0.45, -0.3, -0.2),
                                      (0.55, 0.1, 0.2, r * 0.45))]
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"Leafy{k}", (v, f), [forest_leaf])
        t = pm.obj_from(f"Leafy{k}Trunk", g1, [trunk])
        t.parent = o
        _link_only(leafy, o); _link_only(leafy, t)
        # bare: trunk + 4 branches
        parts = [kit.tube_geo([(0, 0, 0), (0, 0, h * 0.5), (0.1, 0, h * 0.8)], [0.24, 0.18, 0.1], n=6)]
        for j in range(4):
            a = 2 * math.pi * j / 4 + rnd.uniform(-0.3, 0.3)
            base = (0, 0, h * rnd.uniform(0.45, 0.65))
            tip = (math.cos(a) * r * 0.8, math.sin(a) * r * 0.8, h * rnd.uniform(0.85, 1.05))
            parts.append(kit.tube_geo([base, tip], [0.1, 0.03], n=5))
        v, f, _ = kit.merge(*parts)
        b = pm.obj_from(f"Bare{k}", (v, f), [dead])
        _link_only(bare, b)
    fl = kit.tube_geo([(0, 0, 0.3), (6.5, 0.2, 0.25), (8.5, 0.1, 0.22)], [0.32, 0.22, 0.1], n=6)
    v, f, _ = kit.merge(fl, kit.tube_geo([(4.0, 0.1, 0.3), (5.5, 1.6, 0.6)], [0.1, 0.04], n=5),
                        kit._box_geo(0.6, 0.7, 0.9, -0.3, -0.35, -0.2))
    o = pm.obj_from("FallenTrunk", (v, f), [dead])
    _link_only(fallen, o)
    return SimpleNamespace(leafy=leafy, bare=bare, fallen=fallen)


def tuft_models(M, rnd):
    """Grass tufts (5 to 7 cones of 4-6 cm root, 20-32 cm), never thin blades (art.md section 1.1)."""
    col = model_collection("Tufts")
    for k in range(3):
        geos = []
        for j in range(6 + k):
            a = 2 * math.pi * j / (6 + k) + rnd.uniform(-0.3, 0.3)
            rr = rnd.uniform(0.03, 0.07)
            h = rnd.uniform(0.2, 0.32)
            tilt = Vector((math.cos(a) * 0.08, math.sin(a) * 0.08, 0))
            v, f = kit._prism_geo(4, rnd.uniform(0.035, 0.05), 0.0, h, ox=math.cos(a) * rr, oy=math.sin(a) * rr)
            v = [tuple(Vector(p) + tilt * (p[2] / h)) for p in v]
            geos.append((v, f))
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"Tuft{k}", (v, f), [M["grass"]])
        _link_only(col, o)
    return col


# ---------- casas ----------

HOUSES = [  # (x, y, sx, sy, sz, heading degrees, roof)
    (-13.5, 3.0, 7.0, 6.0, 6.5, -90, "hip"),     # east side of the square
    (-14.0, -6.0, 6.0, 6.5, 8.5, -90, "hip"),
    (-12.5, 19.0, 6.0, 7.0, 6.5, 0, "hip"),
    (-12.5, 28.0, 5.0, 6.0, 5.5, 0, "mono"),
    (-19.0, 26.0, 6.5, 6.0, 7.0, 10, "hip"),
    (-26.0, 18.0, 6.0, 7.0, 6.0, -5, "hip"),
    (-30.0, 34.0, 7.0, 6.0, 7.5, 15, "mono"),
    (-38.0, 22.0, 6.0, 6.0, 6.0, 0, "hip"),
    (-44.0, 40.0, 8.0, 6.0, 7.0, 5, "hip"),
    (-52.0, 26.0, 6.0, 7.0, 6.5, -10, "mono"),
    (-58.0, 48.0, 7.0, 6.0, 6.0, 0, "hip"),
    (-66.0, 34.0, 6.0, 6.0, 7.0, 12, "hip"),
    (-21.0, 9.0, 6.0, 6.0, 7.0, -90, "hip"),
    (-30.0, 2.0, 7.0, 6.0, 8.0, -90, "hip"),
]


def build_houses(M, rnd):
    out = []
    for k, (x, y, sx, sy, sz, hd, roof) in enumerate(HOUSES):
        z = hill_z(x, y) if x < -9.5 else 0.0
        if x >= -15 and y < 14:
            z = 0.0
        out.append(pm.house(f"House{k}", (x, y, z - 0.6), (sx, sy, sz + 0.6), M, rnd, math.radians(hd), roof))
    return out
