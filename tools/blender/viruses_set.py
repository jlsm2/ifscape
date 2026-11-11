"""Waterfront set of viruses-disappeared: generic small New England town (~43 deg N) at the end of May.

Units in meters. Origin = camera's foot on the pier sidewalk (eye at 1.65 m); +y = SOUTH (toward the cove), +x = WEST
(right of someone looking south), z = 0 at the paving. Water at z = -1.5. Sun (art.md section 1): NOW 10:30 azimuth 120 deg /
elevation 55 deg (front-left); 1 DAY 145 deg / 62 deg. Compass -> scene: north = -y, east = -x.

Layers (direction.md section 1): low wall on the left -> pier with step and orange buoy -> boats -> lighthouse at the tip -> hill of
oaks (100 m, at ~800 m, across the cove) -> ridge at 4 km. On the right, the corner shop with the facade
to the north (in shadow all day: it is the dark background of the sneeze droplets, art.md R7) and the clapboard houses.

Change relative to the plan (for geometry, noted in NOTES.md): the hill is at the center-left of H1 (heading ~3 deg),
not "on the right": on the right the corner shop blocks the background, and it is what gives the shaded door behind the sneeze.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector, noise

import kit
import plants_models as pm
import plants_set as ps
from kit import lin

WATER_Z = -1.5
SKY_ZENITH = "#3F7FC8"
ORLA_HORIZON = "#B8D4EA"
SAV_HORIZON = "#CFD3CC"
SUN_NOW = (120.0, 55.0)
SUN_DAY = (145.0, 62.0)
SHOP_Y = 11.0                    # north facade of the corner shop
DOCK_STEP = Vector((-1.1, 7.3, 0.0))
BUOY = Vector((-7.5, 11.5, WATER_Z))   # stage 6: at (-5.4; 13.6) it was under the deck
CORNER_X1, CORNER_Y1 = 6.0, 26.0     # south corner of the pier (behind the shop): x -0.6..6, y 18.4..26
OAK = Vector((1.8, 22.4, 0.0))       # oak at the end of the sidewalk (08 and 09)


def sun_vector(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def hazed(color, k, horizon=ORLA_HORIZON):
    """Atmospheric perspective without haze (art.md): the color already mixed k toward the sky horizon."""
    a, h = lin(color), lin(horizon)
    mix = [a[i] + (h[i] - a[i]) * k for i in range(3)]
    return "#" + "".join(f"{round(255 * (x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055)):02X}"
                         for x in mix)


# ---------- sky and sun (switch only on the cut) ----------

def build_world():
    """Gradient sky zenith #3F7FC8 -> horizon (waterfront #B8D4EA, savanna #CFD3CC: the 'place' factor switches on cut 09->11).
    For the diffuse light, a blue ambient (shadow ~40% pulled toward blue). Is Camera Ray MAX Is Glossy Ray: the sea
    reflects the same sky the camera sees."""
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    if not world.node_tree:
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
    ramps = []
    for hz, mid in ((ORLA_HORIZON, "#8DB6E0"), (SAV_HORIZON, "#9DB8D6")):
        r = n.new("ShaderNodeValToRGB")
        r.color_ramp.interpolation = "EASE"
        e = r.color_ramp.elements
        e[0].position, e[0].color = 0.0, lin(hz)
        e[1].position, e[1].color = 0.75, lin(SKY_ZENITH)
        m = e.new(0.12); m.color = lin(mid)
        L.new(clampz.outputs[0], r.inputs["Fac"])
        ramps.append(r)
    place = n.new("ShaderNodeMix"); place.data_type = "RGBA"; place.name = "Place"
    place.inputs["Factor"].default_value = 0.0
    L.new(ramps[0].outputs["Color"], place.inputs["A"])
    L.new(ramps[1].outputs["Color"], place.inputs["B"])
    L.new(place.outputs["Result"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    amb = n.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = lin("#8FA8CC")
    amb.inputs["Strength"].default_value = 0.85        # shadow ~40% of the sunlit face (measured in H1: 2.5:1)
    path = n.new("ShaderNodeLightPath")
    mx = n.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    L.new(path.outputs["Is Camera Ray"], mx.inputs[0])
    L.new(path.outputs["Is Glossy Ray"], mx.inputs[1])
    pick = n.new("ShaderNodeMixShader")
    L.new(mx.outputs[0], pick.inputs["Fac"])
    L.new(amb.outputs[0], pick.inputs[1])
    L.new(bg.outputs[0], pick.inputs[2])
    L.new(pick.outputs[0], out.inputs["Surface"])
    return SimpleNamespace(world=world, place=place.inputs["Factor"], ambient=amb.inputs["Strength"])


def build_sun():
    ld = bpy.data.lights.new("Sun", "SUN")
    ld.energy = 3.4
    ld.color = (1.0, 0.95, 0.88)            # #FFF2E0
    ld.angle = math.radians(1.5)
    ld.specular_factor = 0.45
    o = bpy.data.objects.new("Sun", ld)
    bpy.context.collection.objects.link(o)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = sun_vector(*SUN_NOW).to_track_quat("Z", "Y")
    return o


def clouds(mat, rnd, center=Vector((0, 0, 0)), yaw0=0.0):
    """Flat cumulus, still, far and high (the same ones throughout the video)."""
    out = []
    for k, (yaw, el, dist, w) in enumerate(((-30, 13, 2600, 300), (-8, 18, 3000, 380), (14, 10, 3400, 420),
                                            (32, 16, 2500, 300), (55, 12, 3200, 360), (-60, 20, 2800, 260))):
        a, e = math.radians(yaw + yaw0), math.radians(el)
        c = center + Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))) * dist
        geos = []
        for j in range(5):
            off = Vector((rnd.uniform(-0.5, 0.5) * w, rnd.uniform(-0.15, 0.15) * w, rnd.uniform(0, 0.12) * w))
            geos.append(pm.lumpy_ico(w * rnd.uniform(0.18, 0.3), tuple(c + off), (1.0, 0.7, 0.42), rnd, 0.12))
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"Cloud{k}", (v, f), [mat])
        o.visible_shadow = False
        out.append(o)
    return out


# ---------- materiais ----------

def clapboard_mat(name, color="#E6DFD0", board=0.16):
    """Lapped clapboard: horizontal strips with a thin edge shadow (Wave in z), +-5% variation per object."""
    mat, n, L, p = pm.node_mat(name, 0.92, 0.15)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"
    L.new(sep.outputs["Z"], div.inputs[0]); div.inputs[1].default_value = board
    fr = n.new("ShaderNodeMath"); fr.operation = "FRACT"
    L.new(div.outputs[0], fr.inputs[0])
    edge = n.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value, edge.inputs["From Max"].default_value = 0.0, 0.16
    edge.inputs["To Min"].default_value, edge.inputs["To Max"].default_value = 0.78, 1.0
    L.new(fr.outputs[0], edge.inputs["Value"])
    col = pm._value_mul(n, L, pm._const(n, color), edge.outputs["Result"])
    col = pm._value_mul(n, L, col, pm._rand_factor(n, L, 0.95, 1.05))
    L.new(col, p.inputs["Base Color"])
    return mat


def sea_mat():
    """Sea: dark near (#2B66A8), darker far (#1E4F8A), crests by stretched noise 1:4 broken up; the
    low roughness reflects the sky (Fresnel)."""
    mat, n, L, p = pm.node_mat("Sea", 0.22, 0.28)
    coord = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.25, 1.0, 1.0)
    L.new(coord.outputs["Object"], mp.inputs["Vector"])
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 1.2
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
    L.new(crest.outputs["Result"], mul.inputs[0]); L.new(bm.outputs["Result"], mul.inputs[1])
    dist = n.new("ShaderNodeCameraData")
    far = n.new("ShaderNodeMapRange")
    far.inputs["From Min"].default_value, far.inputs["From Max"].default_value = 40.0, 1500.0
    L.new(dist.outputs["View Distance"], far.inputs["Value"])
    near_far = n.new("ShaderNodeMix"); near_far.data_type = "RGBA"
    L.new(far.outputs["Result"], near_far.inputs["Factor"])
    near_far.inputs["A"].default_value = lin("#2B66A8")
    near_far.inputs["B"].default_value = lin("#1E4F8A")
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(mul.outputs[0], mix.inputs["Factor"])
    L.new(near_far.outputs["Result"], mix.inputs["A"])
    mix.inputs["B"].default_value = lin("#C8D8E4")
    L.new(mix.outputs["Result"], p.inputs["Base Color"])
    # fine undulation in the relief (the sky reflection breaks into facets)
    rip_map = n.new("ShaderNodeMapping")
    rip_map.inputs["Scale"].default_value = (0.6, 1.6, 1.0)
    L.new(coord.outputs["Object"], rip_map.inputs["Vector"])
    rip = n.new("ShaderNodeTexNoise")
    rip.inputs["Scale"].default_value = 1.4
    rip.inputs["Detail"].default_value = 2.0
    L.new(rip_map.outputs[0], rip.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.2
    L.new(rip.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], p.inputs["Normal"])
    return mat


def make_mats():
    M = {}
    M["sea"] = sea_mat()
    M["paving"] = pm.stone_mat("QuayPaving", "#B4AEA2", scale=2.8, mortar="#948E86")
    M["granite"] = pm.stone_mat("Granite", "#A8A49C", scale=0.9, mortar="#7E7A74")
    M["quayface"] = pm.stone_mat("QuayFace", "#7E7A72", scale=0.7, mortar="#5A5650")
    M["clap"] = clapboard_mat("Clapboard")
    M["clap_b"] = clapboard_mat("ClapboardBlue", "#B8C4CC")
    M["clap_y"] = clapboard_mat("ClapboardYellow", "#E2CF9A")
    M["roof"] = pm.fixed_mat("ShingleRoof", "#8C8A84", rough=0.9, var=(0.9, 1.08))
    M["trim"] = pm.fixed_mat("Trim", "#F2EEE6", rough=0.85)
    M["navy"] = pm.fixed_mat("Navy", "#2E4A6A", rough=0.8)
    M["red"] = pm.fixed_mat("RedTrim", "#A8433A", rough=0.85)
    M["door"] = pm.fixed_mat("ShadowDoor", "#3A3430", rough=0.9)
    M["glass"] = pm.fixed_mat("ShopGlass", "#26303A", rough=0.35, spec=0.35)
    M["wood"] = pm.wood_mat("DockWood", "#8A6A4A")
    M["pile"] = pm.fixed_mat("Pile", "#5A4A3A", rough=0.95)
    M["wetpile"] = pm.fixed_mat("WetPile", "#2E2A26", rough=0.6)
    M["buoy"] = pm.fixed_mat("Buoy", "#D9562E", rough=0.6, spec=0.3)
    M["metal"] = pm.fixed_mat("Metal", "#2E3236", rough=0.6, spec=0.3)
    M["hull_w"] = pm.fixed_mat("HullWhite", "#E2E2DC", rough=0.6)
    M["hull_r"] = pm.fixed_mat("HullRed", "#A8433A", rough=0.6)
    M["hull_g"] = pm.fixed_mat("HullGreen", "#3E5E4A", rough=0.6)
    M["bottom"] = pm.fixed_mat("HullBottom", "#6A2E2A", rough=0.7)
    M["rope"] = pm.fixed_mat("Rope", "#C8B48A", rough=0.95)
    M["trap"] = pm.fixed_mat("TrapWire", "#4E6A5A", rough=0.8)
    M["trap_y"] = pm.fixed_mat("TrapYellow", "#C8A43A", rough=0.8)
    M["planter"] = pm.fixed_mat("Planter", "#6A4A34", rough=0.9)
    M["shrub"] = pm.fixed_mat("Shrub", "#4F7A3C", rough=0.85, var=(0.85, 1.1))
    M["flower"] = pm.fixed_mat("Flowers", "#C8506A", rough=0.8)
    M["bench"] = pm.fixed_mat("Bench", "#4A5A4E", rough=0.85)
    M["rock"] = pm.fixed_mat("ShoreRock", "#7E7A74", rough=0.95, var=(0.85, 1.1))
    M["lh_white"] = pm.fixed_mat("LighthouseWhite", "#EEEAE2", rough=0.85)
    M["cloud"] = pm.fixed_mat("Cloud", "#F2F5F8", rough=1.0, emission="#F2F5F8", strength=0.25)
    # other side of the cove (atmospheric perspective 25%) and ridge (45%)
    M["far_land"] = pm.fixed_mat("FarLand", hazed("#5E7A44", 0.25), rough=0.95)
    M["oak"] = pm.fixed_mat("FarOak", hazed("#4F7A3C", 0.22), rough=0.9, var=(0.86, 1.1))
    M["oak_thin"] = pm.fixed_mat("FarOakThin", hazed("#8A9A5A", 0.22), rough=0.9, var=(0.9, 1.08))
    M["far_trunk"] = pm.fixed_mat("FarTrunk", hazed("#5A5048", 0.25))
    M["far_house"] = pm.fixed_mat("FarHouse", hazed("#E6DFD0", 0.2), rough=0.9, var=(0.92, 1.05))
    M["far_roof"] = pm.fixed_mat("FarRoof", hazed("#6E6C68", 0.2), rough=0.9)
    M["ridge"] = pm.fixed_mat("Ridge", hazed("#4F6A48", 0.45), rough=0.95)
    M["far_rock"] = pm.fixed_mat("FarRock", hazed("#8A8680", 0.25))
    return M


# ---------- ground, pier and water ----------

def build_quay(M):
    out = SimpleNamespace(walls=[])
    out.water = kit.mesh_object("Sea", [(-6000, -300, 0), (6000, -300, 0), (6000, 9000, 0), (-6000, 9000, 0)],
                                [(0, 1, 2, 3)], [M["sea"]], (0, 0, WATER_Z))
    out.water.visible_shadow = False
    # pier slab (granite paving) and the stone face that goes down to the water
    out.quay = kit.box_span("Quay", -0.6, 70.0, -50.0, 19.0, -3.2, 3.2, M["paving"])
    out.face_e = kit.box_span("QuayFaceE", -1.12, -0.6, -50.0, CORNER_Y1, -3.2, 3.15, M["quayface"])
    out.face_s = kit.box_span("QuayFaceS", CORNER_X1, 70.0, 19.0, 19.5, -3.2, 3.15, M["quayface"])
    # south corner of the pier behind the shop (stage 6, 2026-10-24): sidewalk with the oak of scenes 08 and 09, hidden
    # by the shop in all other shots (the oak must not block the sneeze door in H1)
    out.corner = kit.box_span("QuayCorner", -0.6, CORNER_X1, 19.0, CORNER_Y1 - 0.5, -3.2, 3.2, M["paving"])
    out.corner_s = kit.box_span("QuayCornerFaceS", -1.12, CORNER_X1 + 0.5, CORNER_Y1 - 0.5, CORNER_Y1, -3.2, 3.15,
                                M["quayface"])
    out.corner_w = kit.box_span("QuayCornerFaceW", CORNER_X1, CORNER_X1 + 0.5, 19.0, CORNER_Y1, -3.2, 3.15,
                                M["quayface"])
    # low wall (0.55 m) with the opening of the pier step (y 6.1 to 8.5)
    for k, (a, b) in enumerate(((-50.0, 6.1), (8.5, SHOP_Y + 0.4), (18.4, CORNER_Y1))):
        out.walls.append(kit.box_span(f"SeaWall{k}", -1.12, -0.6, a, b, 0.0, 0.55, M["granite"]))
    out.walls.append(kit.box_span("SeaWallS", CORNER_X1 + 0.5, 70.0, 19.0, 19.5, 0.0, 0.55, M["granite"]))
    out.walls.append(kit.box_span("SeaWallCornerS", -0.6, CORNER_X1 + 0.5, CORNER_Y1 - 0.5, CORNER_Y1, 0.0, 0.55,
                                  M["granite"]))
    out.walls.append(kit.box_span("SeaWallCornerW", CORNER_X1, CORNER_X1 + 0.5, 19.0, CORNER_Y1 - 0.5, 0.0, 0.55,
                                  M["granite"]))
    # pier step: two granite steps going down to the deck
    out.steps = [kit.box_span("DockStep0", -1.12, -0.6, 6.1, 8.5, -0.2, 0.2, M["granite"])]
    return out


def build_dock(M):
    """Wooden deck from the step outward (heading -40 deg), 22 m x 2.4 m, 0.4 m below the pier, with piles,
    cleats and ropes. Origin at the step."""
    rnd = random.Random(5)
    d = Vector((-math.sin(math.radians(40)), math.cos(math.radians(40)), 0))
    side = Vector((d.y, -d.x, 0))
    origin = Vector((-1.12, 7.3, 0))
    L, Wd, z = 22.0, 2.4, -0.42
    planks = []
    n = int(L / 0.22)
    for k in range(n):
        a = origin + d * (k * 0.22)
        corners = [a - side * Wd / 2, a + side * Wd / 2, a + side * Wd / 2 + d * 0.2, a - side * Wd / 2 + d * 0.2]
        dz = rnd.uniform(-0.008, 0.008)
        top = [(c.x, c.y, z + dz) for c in corners]
        bot = [(c.x, c.y, z - 0.08) for c in corners]
        planks.append((top + bot, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    v, f, _ = kit.merge(*planks)
    deck = kit.mesh_object("DockDeck", v, f, [M["wood"]])
    # beams and piles (dark and wet at the waterline)
    geos, wet = [], []
    for k in range(0, int(L) + 1, 3):
        for s in (-1, 1):
            c = origin + d * k + side * s * (Wd / 2 + 0.05)
            geos.append(kit._prism_geo(7, 0.16, 0.15, 0.6 + (z + 0.5) - WATER_Z, oz=WATER_Z - 0.6, ox=c.x, oy=c.y))
            wet.append(kit._prism_geo(7, 0.165, 0.165, 0.5, oz=WATER_Z - 0.2, ox=c.x, oy=c.y))
    v, f, _ = kit.merge(*geos)
    piles = kit.mesh_object("DockPiles", v, f, [M["pile"]])
    v, f, _ = kit.merge(*wet)
    wetp = kit.mesh_object("DockPilesWet", v, f, [M["wetpile"]])
    # cleats (black) and ropes tied at the edge
    cleats = []
    for k in (4, 10, 16):
        c = origin + d * k + side * (Wd / 2 - 0.15)
        cleats.append(kit._box_geo(0.12, 0.3, 0.1, c.x - 0.06, c.y - 0.15, z))
    v, f, _ = kit.merge(*cleats)
    cl = kit.mesh_object("DockCleats", v, f, [M["metal"]])
    return SimpleNamespace(deck=deck, piles=piles, wet=wetp, cleats=cl, origin=origin, d=d, side=side, z=z)


def buoy(M, location=BUOY):
    """Orange-red mooring buoy (#D9562E): rounded body of 0.7 m + dark ring, half out of the water."""
    v1, f1 = kit._ico_geo(0.38, (0, 0, 0.12), (1.0, 1.0, 0.8))
    v2, f2 = kit._prism_geo(10, 0.39, 0.39, 0.08, oz=0.05)
    v3, f3 = kit._prism_geo(6, 0.05, 0.04, 0.25, oz=0.38)
    o = kit.mesh_object("Buoy", *kit.merge((v1, f1))[:2], [M["buoy"]], tuple(location))
    ring = kit.mesh_object("BuoyRing", v2, f2, [M["metal"]])
    ring.parent = o
    eye = kit.mesh_object("BuoyEye", v3, f3, [M["metal"]])
    eye.parent = o
    for x in (o, ring, eye):
        for p in x.data.polygons:
            p.use_smooth = False
    return o


def _hull_rings(length, beam, depth, n_sec=9):
    rings = []
    for i in range(n_sec + 1):
        u = i / n_sec
        x = -length / 2 + length * u
        w = beam / 2 * (math.sin(math.pi * min(1.0, u * 1.25)) ** 0.6 if u < 0.8 else
                        math.sin(math.pi * 0.95) ** 0.6 * (1 - (u - 0.8) / 0.2 * 0.85))
        w = max(w, 0.04)
        sheer = 0.35 * u ** 2
        rings.append([(x, -w, depth + sheer), (x, -w * 0.8, 0.25), (x, 0.0, -0.05 + 0.1 * u), (x, w * 0.8, 0.25),
                      (x, w, depth + sheer)])
    return rings


def lobster_boat(name, location, heading_deg, M, hull="hull_w", length=9.0):
    """Lobster boat (bow toward local +x): wedge hull with high edge at the bow, wheelhouse forward, mast."""
    beam, depth = length * 0.34, 1.1
    rings = _hull_rings(length, beam, depth)
    verts = [p for r in rings for p in r]
    n = 5
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n - 1):
            a = i * n + j
            faces.append((a, a + 1, a + n + 1, a + n))
    faces.append(tuple(range(n - 1, -1, -1)))
    last = (len(rings) - 1) * n
    faces.append(tuple(range(last, last + n)))
    deck = [tuple(i * n + j for i in range(len(rings))) for j in (0,)]
    del deck
    o = kit.mesh_object(name, verts, faces, [M[hull], M["bottom"]], location)
    for k, p in enumerate(o.data.polygons):
        c = sum((o.data.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices)
        p.material_index = 1 if c.z < 0.12 else 0
        p.use_smooth = False
    kit.fix_normals(o)
    o.rotation_euler = (0, 0, math.radians(heading_deg))
    parts = [kit._box_geo(length * 0.22, beam * 0.6, 1.5, length * 0.05, -beam * 0.3, depth - 0.1),
             kit._box_geo(length * 0.26, beam * 0.7, 0.1, length * 0.03, -beam * 0.35, depth + 1.4),
             kit._prism_geo(6, 0.05, 0.03, 3.2, oz=depth + 1.4, ox=length * 0.15)]
    v, f, own = kit.merge(*parts)
    cab = kit.mesh_object(name + "Cabin", v, f, [M["trim"], M["navy"]], face_mats=[0 if k < 2 else 1 for k in own])
    cab.parent = o
    # inner deck (bottom of the cockpit) so the sea is not seen through the hull
    dv, df = kit._box_geo(length * 0.7, beam * 0.8, 0.05, -length * 0.38, -beam * 0.4, depth - 0.45)
    dk = kit.mesh_object(name + "Floor", dv, df, [M["wood"]])
    dk.parent = o
    return o


def lighthouse(M, location):
    """White lighthouse with red band (#A8433A) on rocks, 20 m (legible at ~700 m: ~10 px wide)."""
    x, y, z = location
    geos = [kit._prism_geo(8, 3.0, 2.1, 17.0, oz=z, ox=x, oy=y)]
    band = [kit._prism_geo(8, 2.6, 2.45, 3.0, oz=z + 8.5, ox=x, oy=y),
            kit._prism_geo(8, 2.4, 2.4, 2.2, oz=z + 17.0, ox=x, oy=y),
            kit._prism_geo(8, 2.6, 0.3, 1.8, oz=z + 19.2, ox=x, oy=y)]
    v, f, _ = kit.merge(*geos)
    t = kit.mesh_object("Lighthouse", v, f, [M["lh_white"]])
    v, f, _ = kit.merge(*band)
    b = kit.mesh_object("LighthouseBand", [(p[0] * 1.0, p[1], p[2]) for p in v], f, [M["red"]])
    # rocks at the tip
    rnd = random.Random(12)
    rocks = [pm.lumpy_ico(rnd.uniform(6, 11), (x + rnd.uniform(-14, 14), y + rnd.uniform(-10, 10), WATER_Z - 2),
                          (1.3, 1.0, 0.45), rnd, 0.2) for _ in range(9)]
    v, f, _ = kit.merge(*rocks)
    r = kit.mesh_object("LighthouseRocks", v, f, [M["far_rock"]])
    return t, b, r


# ---------- casas ----------

def gable_house(name, x0, x1, y0, y1, wall_h, roof_h, M, wall="clap", ridge_axis="x", parent=None):
    """Clapboard house with gable roof (gray wood shingle) and eaves."""
    geos = [kit._box_geo(x1 - x0, y1 - y0, wall_h, x0, y0, 0.0)]
    body = kit.mesh_object(name, geos[0][0], geos[0][1], [M[wall]])
    e = 0.3
    if ridge_axis == "x":
        ym = (y0 + y1) / 2
        v = [(x0 - e, y0 - e, wall_h - 0.1), (x1 + e, y0 - e, wall_h - 0.1), (x1 + e, ym, wall_h + roof_h),
             (x0 - e, ym, wall_h + roof_h), (x0 - e, y1 + e, wall_h - 0.1), (x1 + e, y1 + e, wall_h - 0.1)]
        f = [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)]
        gab = [(x0, y0, wall_h), (x0, y1, wall_h), (x0, ym, wall_h + roof_h - 0.05)]
        gab2 = [(x1, y0, wall_h), (x1, ym, wall_h + roof_h - 0.05), (x1, y1, wall_h)]
    else:
        xm = (x0 + x1) / 2
        v = [(x0 - e, y0 - e, wall_h - 0.1), (xm, y0 - e, wall_h + roof_h), (xm, y1 + e, wall_h + roof_h),
             (x0 - e, y1 + e, wall_h - 0.1), (x1 + e, y0 - e, wall_h - 0.1), (x1 + e, y1 + e, wall_h - 0.1)]
        f = [(0, 1, 2, 3), (1, 4, 5, 2), (0, 3, 1), (4, 1, 5)]
        gab = [(x0, y0, wall_h), (xm, y0, wall_h + roof_h - 0.05), (x1, y0, wall_h)]
        gab2 = [(x0, y1, wall_h), (x1, y1, wall_h), (xm, y1, wall_h + roof_h - 0.05)]
    roof = kit.mesh_object(name + "Roof", v, [f[0], f[1]], [M["roof"]])
    # roof thickness (underside) so it is not a thin plane
    rv = [(p[0], p[1], p[2] - 0.18) for p in v]
    under = kit.mesh_object(name + "RoofUnder", rv, [tuple(reversed(f[0])), tuple(reversed(f[1]))], [M["trim"]])
    g = kit.mesh_object(name + "Gable", gab + gab2, [(0, 1, 2), (3, 4, 5)], [M[wall]])
    kit.fix_normals(g)
    for o in (roof, under, g):
        o.parent = body
    if parent is not None:
        body.parent = parent
    return body


def windows_on(name, face, M, xs, z0, z1, depth=0.12, width=0.9, trim=0.08):
    """Windows (dark glass + white frame) on a facade. face = ('y', y_facade, sign) or ('x', x, sign)."""
    axis, c, s = face
    geos_g, geos_t = [], []
    for x in xs:
        if axis == "y":
            geos_t.append(kit._box_geo(width + 2 * trim, 0.06, z1 - z0 + 2 * trim, x - width / 2 - trim,
                                       c - (0.06 if s < 0 else 0), z0 - trim))
            geos_g.append(kit._box_geo(width, 0.07, z1 - z0, x - width / 2, c - (0.07 if s < 0 else 0) + s * 0.01, z0))
        else:
            geos_t.append(kit._box_geo(0.06, width + 2 * trim, z1 - z0 + 2 * trim, c - (0.06 if s < 0 else 0),
                                       x - width / 2 - trim, z0 - trim))
            geos_g.append(kit._box_geo(0.07, width, z1 - z0, c - (0.07 if s < 0 else 0) + s * 0.01, x - width / 2, z0))
    v, f, _ = kit.merge(*geos_t)
    t = kit.mesh_object(name + "Trim", v, f, [M["trim"]])
    v, f, _ = kit.merge(*geos_g)
    g = kit.mesh_object(name + "Glass", v, f, [M["glass"]])
    return t, g


def corner_shop(M):
    """Corner shop (facade to the north, in shadow): clapboard wall with false front, recessed double door in
    shadow (#3A3430) behind the sneeze, dark display windows, red sign without text, navy awning."""
    x0, x1, y0, y1 = -1.12, 13.0, SHOP_Y, 18.4
    body = gable_house("Shop", x0, x1, y0 + 0.4, y1, 4.0, 2.4, M, wall="clap", ridge_axis="x")
    # false front (straight parapet) at the front
    ff = kit.box_span("ShopFront", x0, x1, y0, y0 + 0.4, 0.0, 5.3, M["clap"])
    cornice = kit.box_span("ShopCornice", x0 - 0.15, x1 + 0.15, y0 - 0.15, y0 + 0.45, 5.3, 0.22, M["trim"])
    # recessed double door (the opening is dark) with frame
    door_x0, door_x1 = -0.1, 2.1
    frame = kit.box_span("ShopDoorFrame", door_x0 - 0.12, door_x1 + 0.12, y0 - 0.05, y0 + 0.02, 0.0, 2.55, M["trim"])
    recess = kit.box_span("ShopDoor", door_x0, door_x1, y0 - 0.06, y0 + 0.03, 0.0, 2.42, M["door"])
    panes = kit.box_span("ShopDoorGlass", door_x0 + 0.18, door_x1 - 0.18, y0 - 0.08, y0 - 0.05, 1.1, 1.1, M["glass"])
    # vitrines
    vt, vg = windows_on("ShopWin", ("y", y0, -1), M, [3.9, 6.6, 9.3, 11.8], 0.75, 2.45, width=2.1)
    sign = kit.box_span("ShopSign", -0.6, 12.4, y0 - 0.12, y0, 2.95, 0.8, M["red"])
    signtrim = kit.box_span("ShopSignTrim", -0.7, 12.5, y0 - 0.1, y0 + 0.01, 2.85, 1.0, M["trim"])
    # navy awning over the display windows (tilted)
    aw = kit.mesh_object("ShopAwning", [(2.7, y0, 2.75), (12.6, y0, 2.75), (12.6, y0 - 1.1, 2.3), (2.7, y0 - 1.1, 2.3)],
                         [(0, 1, 2, 3)], [M["navy"]])
    aws = kit.mesh_object("ShopAwningSkirt", [(2.7, y0 - 1.1, 2.3), (12.6, y0 - 1.1, 2.3), (12.6, y0 - 1.12, 2.05),
                                              (2.7, y0 - 1.12, 2.05)], [(0, 1, 2, 3)], [M["navy"]])
    for o in (ff, cornice, frame, recess, panes, vt, vg, sign, signtrim, aw, aws):
        o.parent = body
    # planter and bench on the sidewalk in front
    pl = kit.box_span("ShopPlanter", 7.3, 8.5, y0 - 0.9, y0 - 0.35, 0.0, 0.5, M["planter"])
    sh = pm.obj_from("ShopShrub", pm.lumpy_ico(0.42, (7.9, y0 - 0.62, 0.72), (1.4, 0.7, 0.6), random.Random(3)),
                     [M["shrub"]])
    fl = pm.obj_from("ShopFlowers", pm.lumpy_ico(0.25, (7.6, y0 - 0.75, 0.95), (1.2, 0.8, 0.5), random.Random(4)),
                     [M["flower"]])
    return SimpleNamespace(body=body, door=(door_x0, door_x1), parts=[pl, sh, fl])


def street_houses(M):
    """Clapboard houses to the right of the shop and behind it (silhouette), and the row on the north side, behind the camera."""
    out = []
    specs = [(14.0, 22.0, 9.5, 17.0, 6.0, 3.0, "clap_b", "x"), (23.0, 30.0, 10.5, 18.0, 6.5, 3.2, "clap", "x"),
             (31.0, 38.0, 9.0, 17.0, 5.5, 3.0, "clap_y", "x"), (16.0, 22.0, -8.0, -1.0, 6.5, 3.0, "clap", "y"),
             (4.0, 11.0, -12.0, -4.0, 6.0, 3.0, "clap_b", "y")]
    for k, (x0, x1, y0, y1, h, rh, w, ax) in enumerate(specs):
        out.append(gable_house(f"House{k}", x0, x1, y0, y1, h, rh, M, wall=w, ridge_axis=ax))
    return out


# ---------- other side of the cove ----------

def far_z(x, y):
    """South shore of the cove (~600 m) rising to the oak hill (peak ~100 m at (40, 820)) and low hills
    to the west; the lighthouse point on the left (x ~ -75)."""
    shore = 600.0 + 0.06 * (x + 200.0)
    s = y - shore
    if s < 0:
        return WATER_Z - 4.0 + s * 0.05
    z = min(s * 0.3, 18.0)
    z += 100.0 * math.exp(-(((x + 200.0) / 210.0) ** 2 + ((y - 830.0) / 200.0) ** 2))
    z += 60.0 * math.exp(-(((x - 180.0) / 240.0) ** 2 + ((y - 900.0) / 240.0) ** 2))
    z += 40.0 * math.exp(-(((x - 800.0) / 300.0) ** 2 + ((y - 980.0) / 260.0) ** 2))
    z += 6.0 * noise.noise(Vector((x * 0.01, y * 0.01, 0.4)))
    if x < -300:
        z *= max(0.0, 1.0 - (-300 - x) / 40.0)
    return z + WATER_Z


def far_shore(M):
    land = ps.grid("FarShore", -380.0, 1600.0, 540.0, 1500.0, 20.0, far_z, [M["far_land"]])
    def ridge_z(x, y):
        h = 180.0 + 120.0 * noise.noise(Vector((x * 0.0012, y * 0.002, 3.1))) + 90.0 * math.exp(-((x - 600.0) / 1400.0) ** 2)
        k = (min(1.0, max(0.0, (y - 3400.0) / 500.0)) * min(1.0, max(0.0, (x + 2600.0) / 900.0))
             * min(1.0, max(0.0, (4200.0 - x) / 900.0)))
        return WATER_Z - 8.0 + (h + 8.0) * k ** 0.7     # descends to the water at the front and at the ends (nothing floats)
    ridge = ps.grid("Ridge", -2600.0, 4200.0, 3400.0, 4800.0, 120.0, ridge_z, [M["ridge"]])
    ridge.visible_shadow = False
    return land, ridge


def oak_models(M, rnd):
    """Distant oaks (crown in masses) in 2 colors: dense #4F7A3C and sparse #8A9A5A (outbreak year). Origin at the foot."""
    col = ps.model_collection("FarOaks")
    for k, (h, r, mat) in enumerate(((14.0, 5.5, "oak"), (17.0, 6.5, "oak"), (12.0, 4.8, "oak"), (15.0, 5.8, "oak_thin"))):
        geos = [pm.lumpy_ico(r * u, (dx, dy, h * 0.55 + r * 0.5 + dz), (1, 1, 0.8), rnd, 0.2)
                for u, dx, dy, dz in ((0.85, 0, 0, 0), (0.6, r * 0.5, 0.2, -0.3), (0.62, -r * 0.45, -0.3, -0.2),
                                      (0.55, 0.1, 0.2, r * 0.45))]
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"FarOak{k}", (v, f), [M[mat]])
        ps._link_only(col, o)
    return col


def far_houses(M, rnd):
    """Little white houses at the foot of the hill and on the shore (instances of 2 meshes)."""
    a = kit.mesh_object("FarHouseA", *kit._box_geo(9, 7, 6, -4.5, -3.5, 0), [M["far_house"]])
    roof_v = [(-5, -4, 6), (5, -4, 6), (5, 0, 9), (-5, 0, 9), (-5, 4, 6), (5, 4, 6)]
    r = kit.mesh_object("FarHouseARoof", roof_v, [(0, 1, 2, 3), (3, 2, 5, 4)], [M["far_roof"]])
    r.parent = a
    out = [a]
    for k in range(34):
        x = rnd.uniform(-290, 900)
        y = 600.0 + 0.06 * (x + 200.0) + rnd.uniform(14, 70)
        z = far_z(x, y)
        if z < WATER_Z + 1.0:
            continue
        o = bpy.data.objects.new(f"FarHouse{k}", a.data)
        bpy.context.collection.objects.link(o)
        o.location = (x, y, z - 0.5)
        o.rotation_euler = (0, 0, rnd.uniform(-0.3, 0.3))
        ro = bpy.data.objects.new(f"FarHouse{k}Roof", r.data)
        bpy.context.collection.objects.link(ro)
        ro.parent = o
        out.append(o)
    a.location = (-150, 640, far_z(-150, 640) - 0.5)
    return out


def build_far(M, rnd):
    land, ridge = far_shore(M)
    oaks = oak_models(M, rnd)
    ng = ps.scatter_group("FarOakScatter", oaks, 9.0, 0.012, 7, (0.8, 1.25), zmin=WATER_Z + 3.0, xmax=700.0)
    forest = ps.carrier("FarOakForest", land, ng)
    forest.visible_shadow = True
    lh = lighthouse(M, (-300.0, 600.0, WATER_Z + 2.0))
    houses = far_houses(M, rnd)
    return SimpleNamespace(land=land, ridge=ridge, forest=forest, lighthouse=lh, houses=houses)


# ---------- pier objects ----------

def quay_props(M, rnd):
    """Light poles (dark, >= 2 px), bollards, stacked lobster traps, bench."""
    out = []
    for k, (x, y) in enumerate(((-0.3, -6.0), (9.4, 9.6), (14.0, 8.6))):
        geos = [kit._prism_geo(8, 0.07, 0.05, 3.8, ox=x, oy=y), kit._prism_geo(8, 0.16, 0.16, 0.25, oz=3.8, ox=x, oy=y),
                kit._prism_geo(8, 0.14, 0.02, 0.2, oz=4.05, ox=x, oy=y)]
        v, f, _ = kit.merge(*geos)
        out.append(kit.mesh_object(f"Lamp{k}", v, f, [M["metal"]]))
    # mooring bollards on the edge
    for k, y in enumerate((-3.0, 5.6, -9.0)):
        v, f = kit._prism_geo(8, 0.16, 0.12, 0.45, ox=-0.3, oy=y)
        out.append(kit.mesh_object(f"Bollard{k}", v, f, [M["metal"]]))
    # lobster traps (wire boxes) stacked near the step, with colored buoys
    geos, cols = [], []
    for k, (x, y, z) in enumerate(((4.3, 9.7, 0.0), (5.15, 9.75, 0.0), (4.7, 9.7, 0.48), (4.3, 10.35, 0.0))):
        geos.append(kit._box_geo(0.82, 0.62, 0.46, x, y, z))
        cols.append(0 if k % 2 == 0 else 1)
    v, f, own = kit.merge(*geos)
    out.append(kit.mesh_object("Traps", v, f, [M["trap"], M["trap_y"]], face_mats=[cols[o] for o in own]))
    # bench facing the water
    geos = [kit._box_geo(1.8, 0.45, 0.06, 0.0, -2.6, 0.45), kit._box_geo(1.8, 0.06, 0.4, 0.0, -2.2, 0.5),
            kit._box_geo(0.06, 0.4, 0.45, 0.1, -2.6, 0.0), kit._box_geo(0.06, 0.4, 0.45, 1.64, -2.6, 0.0)]
    v, f, _ = kit.merge(*geos)
    out.append(kit.mesh_object("Bench", v, f, [M["bench"]]))
    return out


def boats(M):
    """Boats anchored in the cove (the red one leaves on 1 DAY: returned in .red for the on/off)."""
    red = lobster_boat("BoatRed", (-15.0, 34.0, WATER_Z - 0.2), 70, M, hull="hull_r", length=9.0)
    others = [lobster_boat("BoatW1", (-34.0, 62.0, WATER_Z - 0.2), 95, M, length=10.0),
              lobster_boat("BoatG", (-20.0, 72.0, WATER_Z - 0.2), 120, M, hull="hull_g", length=9.0),
              lobster_boat("BoatW2", (-48.0, 135.0, WATER_Z - 0.2), 80, M, length=11.0),
              lobster_boat("BoatW3", (-28.0, 195.0, WATER_Z - 0.2), 100, M, length=10.0),
              lobster_boat("BoatW4", (-75.0, 260.0, WATER_Z - 0.2), 60, M, length=10.0)]
    return SimpleNamespace(red=red, others=others)


def oak_marker(M, cam_dir=Vector((0.25, -1.0, 0.0))):
    """MARKER of stage 6 (the final model is for stage 8): ~13 m red oak at the south corner of the pier, 0.7 m trunk
    with burlap band (#B89A6A) at 1.15-1.55 m and 'caterpillars' (#4A4038, 5 cm) on the band; low branch with
    leaves for the detail of 09 (tip at BRANCH_TIP). cam_dir: from which side the camera of 08 sees the trunk."""
    rnd = random.Random(61)
    bark = pm.fixed_mat("OakBark", "#6E665C", rough=0.95)
    jute = pm.fixed_mat("Jute", "#B89A6A", rough=0.98)
    cat = pm.fixed_mat("Caterpillar", "#4A4038", rough=0.95)
    leaf = pm.fixed_mat("OakLeaf", "#5A8A3C", rough=0.8, var=(0.85, 1.1))
    soil = pm.fixed_mat("TreePit", "#4A3C30", rough=0.98)
    x, y = OAK.x, OAK.y
    pit = kit.box_span("OakPit", x - 0.8, x + 0.8, y - 0.8, y + 0.8, 0.0, 0.03, soil)
    trunk = kit.mesh_object("OakTrunk", *kit.tube_geo([(x, y, 0.0), (x, y, 2.5), (x + 0.1, y + 0.1, 5.0),
                                                       (x + 0.2, y + 0.3, 6.5)], [0.36, 0.32, 0.28, 0.2], n=10)[:2],
                            [bark])
    limbs = [kit.tube_geo([(x + 0.1, y + 0.1, 4.5), (x + s * 1.6, y + 0.4, 6.4), (x + s * 2.6, y + 0.6, 7.6)],
                          [0.16, 0.12, 0.07], n=7) for s in (-1, 1)]
    v, f, _ = kit.merge(*limbs)
    lim = kit.mesh_object("OakLimbs", v, f, [bark])
    crown_geos = [pm.lumpy_ico(r, (x + dx, y + dy, z), (1.0, 1.0, 0.8), rnd, 0.2)
                  for r, dx, dy, z in ((3.6, 0, 0.3, 9.0), (2.6, 2.4, 0.4, 7.8), (2.7, -2.3, 0.2, 7.9),
                                       (2.4, 0.4, 1.8, 11.0), (2.2, -0.6, -1.6, 8.6))]
    v, f, _ = kit.merge(*crown_geos)
    crown = kit.mesh_object("OakCrown", v, f, [M["shrub"]])
    band = kit.mesh_object("OakJute", *kit._prism_geo(12, 0.375, 0.375, 0.4, oz=1.15, ox=x, oy=y), [jute])
    d = cam_dir.normalized()
    base = math.atan2(d.y, d.x)
    cats = []
    for k in range(22):
        a = base + rnd.uniform(-1.3, 1.3)
        z = rnd.uniform(1.2, 1.5) if k < 18 else rnd.uniform(1.7, 2.6)
        r = 0.39 if k < 18 else 0.34
        g = kit._box_geo(0.05, 0.013, 0.013, -0.025, -0.0065, -0.0065)
        o = kit.mesh_object(f"Cat{k}", *g, [cat], (x + r * math.cos(a), y + r * math.sin(a), z))
        o.rotation_euler = (0, rnd.uniform(-0.6, 0.6) + math.pi / 2 * (k % 2), a + math.pi / 2)
        cats.append(o)
    # low branch of 09: leaves the trunk toward the camera side, leaves at the tip
    tip = Vector(BRANCH_TIP)
    br = kit.mesh_object("OakBranch", *kit.tube_geo([(x + 0.1, y - 0.2, 2.9), (2.3, 21.6, 2.35), tuple(tip)],
                                                    [0.075, 0.045, 0.022], n=7)[:2], [bark])
    leaves = []
    for k in range(9):
        p = tip + Vector((rnd.uniform(-0.18, 0.12), rnd.uniform(-0.15, 0.2), rnd.uniform(-0.12, 0.1)))
        g = kit._box_geo(0.12, 0.065, 0.004, 0.0, -0.0325, -0.002)
        o = kit.mesh_object(f"OakLeaf{k}", *g, [leaf], tuple(p))
        o.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 6.28))
        leaves.append(o)
    bite = leaves[0]
    bite.location = tip + Vector((-0.04, -0.1, 0.03))
    bite.rotation_euler = (0.9, 0.0, math.radians(-30))
    bcats = []
    for k in range(7):
        u = k / 7
        p = Vector((2.3, 21.6, 2.35)).lerp(tip, 0.3 + 0.7 * u) + Vector((0, 0, 0.03))
        g = kit._box_geo(0.05, 0.012, 0.012, -0.025, -0.006, 0.0)
        o = kit.mesh_object(f"BranchCat{k}", *g, [cat], tuple(p))
        o.rotation_euler = (0, 0, math.atan2(tip.y - 21.6, tip.x - 2.3) + rnd.uniform(-0.4, 0.4))
        bcats.append(o)
    for o in (pit, trunk, lim, crown, band, br, *cats, *leaves, *bcats):
        for poly in o.data.polygons:
            poly.use_smooth = False
    return SimpleNamespace(trunk=trunk, band=band, crown=crown, branch=br, leaves=leaves, bite=bite, cats=cats,
                           branch_cats=bcats, tip=tip)


BRANCH_TIP = (2.55, 21.05, 2.05)


def build_orla(M, rnd):
    q = build_quay(M)
    dock = build_dock(M)
    b = buoy(M)
    shop = corner_shop(M)
    houses = street_houses(M)
    far = build_far(M, rnd)
    props = quay_props(M, rnd)
    bt = boats(M)
    oak = None                       # final oak: viruses_oak.build (assembled by the video script)
    return SimpleNamespace(quay=q, dock=dock, buoy=b, shop=shop, houses=houses, far=far, props=props, boats=bt,
                           oak=oak)
