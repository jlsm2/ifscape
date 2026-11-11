"""Corner set for the humans-vanished script: builds everything and returns the pieces to animate.

Axes: north-south avenue at x = 0 (width 14 m), east-west cross street at y = 0 (10 m).
Sidewalks 4 m wide. The camera is panoramic (drone), so the south block exists too.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import kit
from kit import LUZ, WARM, box, box_span, flat, gem, keyed_emission, lin, prism, rect_with_holes

AVENUE_HALF = 7.0
STREET_HALF = 5.0
SIDEWALK = 4.0
EDGE = AVENUE_HALF + SIDEWALK
FLOOR = 3.4                               # height of one floor (window grid)
COLLAPSE = (-6.2, 6.2, 16.0, 30.0)        # stretch of the avenue that collapses into the subway (x0, x1, y0, y1)
STAIR = (-10.3, -8.3, 11.4, 16.6)         # subway stairs on the west sidewalk
STAIR_DEPTH = 3.3
STAIR_STEPS = 10
STEP_RISE = 0.3
STEP_RUN = 0.5
STATUE_XY = (EDGE + 4, STREET_HALF + SIDEWALK + 4)
STATUE_TOP = 1.59                         # top of the pedestal
STATUE_SCALE = 1.25
POT_XY = (-7.9, 14.8)
HYDRANT_XY = (7.7, -7.0)                  # the drifting car knocks this one down (traffic.py)
WALLS = ["#2A3446", "#333E52", "#3B4458", "#283041", "#3F3A44"]
ASPHALT, CONCRETE, CURB, MARKING = "#1C2230", "#3A4252", "#4A5366", "#8A94A6"
MOSS, FOREST_FLOOR = "#2E4A30", "#26381F"
RAIL_GREEN, BRONZE, VERDIGRIS = "#1F4D3A", "#6B4A2B", "#4E8C74"
LEAVES = ["#2F5D3A", "#3E6E44", "#4C7A3E", "#2B4F35"]
CLOTHES = ["#2E3A52", "#5A6378", "#8A94A6", "#3F5A73", "#6B4E3A", "#C9A227", "#7A2E2E", "#D8D2C4"]


def on_sidewalk(x, y):
    ax, ay = abs(x), abs(y)
    return (AVENUE_HALF < ax < EDGE and ay > STREET_HALF) or (STREET_HALF < ay < STREET_HALF + SIDEWALK and ax > AVENUE_HALF)


def surface_z(x, y):
    return 0.15 if on_sidewalk(x, y) else 0.0


# ---------- sky and light ----------

def build_world():
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    n, links = world.node_tree.nodes, world.node_tree.links
    bg = n.get("Background") or n.new("ShaderNodeBackground")
    out = n.get("World Output") or n.new("ShaderNodeOutputWorld")
    coord = n.new("ShaderNodeTexCoord")
    norm = n.new("ShaderNodeVectorMath"); norm.operation = "NORMALIZE"
    sep = n.new("ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Generated"], norm.inputs[0])
    links.new(norm.outputs[0], sep.inputs[0])

    def sky_ramp(horizon, zenith):
        r = n.new("ShaderNodeValToRGB")
        r.color_ramp.interpolation = "EASE"
        r.color_ramp.elements[0].color = lin(horizon)
        r.color_ramp.elements[1].color = lin(zenith)
        r.color_ramp.elements[1].position = 0.85
        links.new(sep.outputs["Z"], r.inputs["Fac"])
        return r

    def mix(a, b):
        m = n.new("ShaderNodeMix"); m.data_type = "RGBA"
        m.inputs["Factor"].default_value = 0.0
        links.new(a, m.inputs["A"])
        links.new(b, m.inputs["B"])
        return m

    night, day, dusk = sky_ramp("#1A2742", "#060A14"), sky_ramp("#A9C8E8", "#3E6FA8"), sky_ramp("#C77A3A", "#1A2440")
    to_day = mix(night.outputs["Color"], day.outputs["Color"])
    to_dusk = mix(to_day.outputs["Result"], dusk.outputs["Color"])

    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 300.0
    links.new(coord.outputs["Generated"], vor.inputs["Vector"])
    star = n.new("ShaderNodeMath"); star.operation = "LESS_THAN"
    star.inputs[1].default_value = 0.05
    links.new(vor.outputs["Distance"], star.inputs[0])
    star_strength = n.new("ShaderNodeMath"); star_strength.operation = "MULTIPLY"
    star_strength.inputs[1].default_value = 1.0
    links.new(star.outputs[0], star_strength.inputs[0])
    stars = n.new("ShaderNodeMix"); stars.data_type = "RGBA"
    stars.inputs["B"].default_value = (0.9, 0.9, 1.0, 1)
    links.new(star_strength.outputs[0], stars.inputs["Factor"])
    links.new(to_dusk.outputs["Result"], stars.inputs["A"])
    links.new(stars.outputs["Result"], bg.inputs["Color"])

    # The camera sees the sky; the scene is lit by a separate environment (lighter and controllable).
    ambient = n.new("ShaderNodeBackground")
    ambient.inputs["Color"].default_value = lin("#3A5285")
    ambient.inputs["Strength"].default_value = 1.6
    path = n.new("ShaderNodeLightPath")
    pick = n.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], pick.inputs["Fac"])
    links.new(ambient.outputs[0], pick.inputs[1])
    links.new(bg.outputs[0], pick.inputs[2])
    links.new(pick.outputs[0], out.inputs["Surface"])

    sun_light = bpy.data.lights.new("Sun", "SUN")
    sun_light.energy = 1.2
    sun_light.color = (0.65, 0.75, 1.0)
    sun_light.angle = math.radians(1.0)
    sun = bpy.data.objects.new("Sun", sun_light)
    sun.rotation_euler = (math.radians(55), 0, math.radians(-35))
    bpy.context.collection.objects.link(sun)

    moon = prism("Moon", (170, 260, 150), 10, 11.0, 11.0, 1.0, flat("Moon", "#E9E4D4", emission="#F3EEDD", strength=6.0))
    moon.rotation_euler = (math.radians(90), 0, math.radians(-30))
    return SimpleNamespace(day=to_day.inputs["Factor"], dusk=to_dusk.inputs["Factor"],
                           stars=star_strength.inputs[1], sky=bg.inputs["Strength"],
                           ambient=ambient.inputs["Strength"], ambient_color=ambient.inputs["Color"],
                           sun=sun_light, sun_obj=sun, moon=moon)


# ---------- ground, streets, subway ----------

def water_material(name):
    """Stylized water: blue-green, controlled roughness, restrained shine (does not become a pale slab)."""
    return flat(name, "#25596B", rough=0.35, emission="#2C6B80", strength=0.12)


_DUST_MAT = None


def puff(name, location, radius):
    """Low-poly dust ball (icosphere)."""
    global _DUST_MAT
    if _DUST_MAT is None:
        _DUST_MAT = flat("Dust", "#9AA3B5", rough=1.0)
        kit.principled(_DUST_MAT).inputs["Alpha"].default_value = 0.35      # translucent dust
        if hasattr(_DUST_MAT, "surface_render_method"):
            _DUST_MAT.surface_render_method = "BLENDED"
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(_DUST_MAT)
    return obj


def build_ground():
    asphalt, concrete, curb = flat("Asphalt", ASPHALT), flat("Concrete", CONCRETE), flat("Curb", CURB)
    marking = flat("Marking", MARKING, rough=0.6)
    holes = [COLLAPSE, STAIR]
    ground = rect_with_holes("Ground", -260, 260, -260, 380, -0.05, 0.05, holes, asphalt)
    walks = []
    reach = 400
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * AVENUE_HALF, sx * EDGE))
            ya, yb = sorted((sy * STREET_HALF, sy * (STREET_HALF + reach)))
            walks += rect_with_holes("Walk", xa, xb, ya, yb, 0, 0.15, holes, concrete)
            ya, yb = sorted((sy * STREET_HALF, sy * (STREET_HALF + SIDEWALK)))
            xa, xb = sorted((sx * EDGE, sx * (EDGE + reach)))
            walks.append(box_span("Walk", xa, xb, ya, yb, 0, 0.15, concrete))

    slab = box_span("CollapseSlab", *COLLAPSE, -0.05, 0.05, asphalt)
    for lane_x in (-3.5, 0.0, 3.5):
        for y in range(-300, 300, 9):
            if abs(y) < STREET_HALF + 4:
                continue
            dash = box("Dash", (lane_x, y, 0.0), (0.18 if lane_x else 0.3, 3.0, 0.02), marking)
            # Includes the strips that only touch the stretch (3 m long): otherwise a stump is left at the edge.
            if COLLAPSE[0] < lane_x < COLLAPSE[1] and COLLAPSE[2] - 1.5 < y < COLLAPSE[3] + 1.5:
                dash.parent = slab
                dash.matrix_parent_inverse = slab.matrix_world.inverted()
    for x in list(range(-300, -14, 9)) + list(range(14, 300, 9)):
        box("Dash", (x, 0.0, 0.0), (3.0, 0.18, 0.02), marking)
    for i in range(9):
        a = -AVENUE_HALF + 0.9 + i * 1.55
        for y in (STREET_HALF + 1.6, -STREET_HALF - 1.6):
            box("Zebra", (a, y, 0.0), (0.8, 2.6, 0.02), marking)
    for i in range(6):
        b = -STREET_HALF + 0.9 + i * 1.6
        for x in (AVENUE_HALF + 1.6, -AVENUE_HALF - 1.6):
            box("Zebra", (x * 1.0 + (0.4 if x > 0 else -0.4), b, 0.0), (2.6, 0.8, 0.02), marking)

    pit = flat("Tunnel", "#4A5366")
    rnd = random.Random(9)
    x0, x1, y0, y1 = COLLAPSE
    box_span("PitFloor", x0, x1, y0, y1, -7.0, 0.1, pit)
    for a, b, c, d in ((x0 - 0.2, x0, y0, y1), (x1, x1 + 0.2, y0, y1), (x0, x1, y0 - 0.2, y0), (x0, x1, y1, y1 + 0.2)):
        box_span("PitWall", a, b, c, d, -7.0, 6.95, pit)
    stream = kit.water_grid("Stream", x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, -7.2, water_material("StreamWater"),
                            cell=1.2, amp=0.07)
    banks = build_banks(x0, x1, y0, y1, flat("Bank", "#3E6E44"), random.Random(21))

    dust = [puff("Dust", (rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(0.0, 0.8)), rnd.uniform(0.5, 1.1))
            for _ in range(18)]
    return SimpleNamespace(ground=ground, walks=walks, slab=slab, stream=stream, dust=dust, banks=banks,
                           mats=[asphalt, concrete, curb, marking])


BANK_TOP = 0.02                           # banks at street level: hide walls and the edge of the hole (water at -0.65)
BANK_LIP = 0.3                            # how far the bank goes past the wall to cover the edge


def build_banks(x0, x1, y0, y1, mat, rnd):
    """Two weed banks with an irregular inner edge: the hole becomes a winding stream.
    Origin at the wall on each side, to grow sideways (x scale from 0 to 1) from it."""
    steps = int(y1 - y0)
    mid = (x0 + x1) / 2
    phase = rnd.uniform(0, math.tau)
    centers = [mid + 1.6 * math.sin(phase + j * 0.55) for j in range(steps + 1)]
    halves = [rnd.uniform(0.9, 1.7) for _ in range(steps + 1)]
    banks = []
    for side, wall in ((-1, x0), (1, x1)):
        verts, faces = [], []
        for j in range(steps + 1):
            y = y0 - BANK_LIP + (y1 - y0 + 2 * BANK_LIP) * j / steps
            inner = centers[j] + side * halves[j] - wall
            verts += [(side * BANK_LIP, y, 0), (inner, y, 0), (inner, y, -0.75)]
        for j in range(steps):
            a, b = 3 * j, 3 * (j + 1)
            top = (a, a + 1, b + 1, b) if side < 0 else (a, b, b + 1, a + 1)
            edge = (a + 1, a + 2, b + 2, b + 1) if side < 0 else (a + 1, b + 1, b + 2, a + 2)
            faces += [top, edge]
        bank = kit.mesh_object(f"Bank{'W' if side < 0 else 'E'}", verts, faces, [mat], (wall, 0, BANK_TOP))
        bank.scale = (0, 1, 0)                 # invisible (no green streak on the wall) until it grows
        banks.append(bank)
    return banks


def build_stairwell():
    tile = flat("StairTile", "#2C333F")
    rail = flat("Rail", RAIL_GREEN, rough=0.5, metallic=0.4)
    x0, x1, y0, y1 = STAIR
    # Each step occupies only its own strip (before, all went to y1 and the top one covered the well: the stairs
    # became a shallow floor and the water appeared all at once). The last goes to the bottom of the stairs.
    wall = 0.1
    for i in range(STAIR_STEPS):
        top = -STEP_RISE * (i + 1)
        ya = y0 + STEP_RUN * i
        yb = y1 if i == STAIR_STEPS - 1 else y0 + STEP_RUN * (i + 1)
        box_span("Step", x0 + wall, x1 - wall, ya, yb, -STAIR_DEPTH, STAIR_DEPTH + top, tile)
    # Walls inside the hole and top 1 cm below the sidewalk: on the plane of the sidewalk and asphalt cut-out, the
    # materials fought and the stair edge flickered (z-fighting, QA).
    wall_h = STAIR_DEPTH + 0.14
    for a, b in ((x0, x0 + wall), (x1 - wall, x1)):
        box_span("StairWall", a, b, y0, y1, -STAIR_DEPTH, wall_h, tile)
    box_span("StairBack", x0 + wall, x1 - wall, y1 - wall, y1, -STAIR_DEPTH, wall_h, tile)
    parts = []
    for dx in (x0 - 0.05, x1 + 0.05):
        parts.append(box("RailSide", (dx, (y0 + y1) / 2, 1.0), (0.06, y1 - y0, 0.06), rail))
        for py in (y0 + 0.1, (y0 + y1) / 2, y1 - 0.1):
            parts.append(box("RailPost", (dx, py, 0.15), (0.06, 0.06, 0.9), rail))
    parts.append(box("RailBack", ((x0 + x1) / 2, y1, 1.0), (x1 - x0 + 0.1, 0.06, 0.06), rail))
    globe_mat, globe_power = keyed_emission("Globe", "#2E6B4F", "#7FE0A8", 1.5)
    for dx in (x0 - 0.05, x1 + 0.05):
        parts.append(prism("GlobePost", (dx, y0 - 0.1, 0.15), 6, 0.05, 0.05, 1.9, rail))
        parts.append(gem("Globe", (dx, y0 - 0.1, 2.2), 0.2, globe_mat))
    water = kit.water_grid("StairWater", x0, x1, y0, y1, -STAIR_DEPTH - 0.05, water_material("StairWater"),
                           cell=1.0, amp=0.0)
    flood = kit.water_grid("Flood", -EDGE, -AVENUE_HALF, 9.0, 19.5, -0.3, water_material("FloodWater"),
                           cell=1.0, amp=0.0)
    # Out of the render: at -0.3 it coincided with the top of the step and, rising, ended up 3 cm from the sidewalk;
    # in both cases the water flickered (z-fighting). The stairs' water alone tells the flood.
    flood.hide_render = True
    glow = bpy.data.lights.new("StairGlow", "POINT")
    glow.energy = 120
    glow.color = (0.55, 0.7, 1.0)
    glow_obj = bpy.data.objects.new("StairGlow", glow)
    glow_obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0.6)
    bpy.context.collection.objects.link(glow_obj)
    # Soil and weeds that close the stairs in the 500 and 10,000-year jumps (shows in the time-lapse).
    lid = box_span("StairLid", x0 - 0.15, x1 + 0.15, y0 - 0.15, y1 + 0.15, 0.1, 0.1, flat("StairLid", "#3E6E44"))
    lid.hide_render = True
    return SimpleNamespace(parts=parts, rail=rail, water=water, flood=flood, globe=globe_power, glow=glow, lid=lid)


# ---------- block buildings (to really collapse) ----------

def building(name, rnd, cx, cy, sx, sy, height, dist):
    floors = max(2, round(height / FLOOR))
    mat, power, _wall, glass = kit.window_material(name, rnd.choice(WALLS), rnd.random() * 1000)
    n_sections = max(1, min(6, floors // 3))
    per = [floors // n_sections + (1 if i < floors % n_sections else 0) for i in range(n_sections)]
    sections, z = [], 0.0
    for i, f in enumerate(per):
        h = f * FLOOR
        sec = box(f"{name}_{i}", (cx, cy, z), (sx, sy, h), mat)
        sec["win_z"] = z
        sections.append(sec)
        z += h
    return {"sections": sections, "power": power, "glass": glass, "dist": dist, "center": (cx, cy),
            "size": (sx, sy, z)}


def build_city(rnd):
    blds = []
    for side in (-1, 1):
        y = STREET_HALF + SIDEWALK                     # north: taller in the background
        while y < 320:
            width, depth = rnd.uniform(10, 22), rnd.uniform(14, 24)
            height = rnd.uniform(12, 45) if y < 60 else rnd.uniform(30, 140)
            if not (side == 1 and y < STREET_HALF + SIDEWALK + 16):          # statue plaza
                blds.append(building(f"N{side}_{int(y)}", rnd, side * (EDGE + depth / 2), y + width / 2,
                                     depth, width, height, y))
            y += width + rnd.uniform(0, 1.5)
        y = -(STREET_HALF + SIDEWALK)                  # south: low near the camera (the drone passes over)
        while y > -220:
            width, depth = rnd.uniform(10, 20), rnd.uniform(14, 22)
            height = rnd.uniform(6, 14) if y > -70 else rnd.uniform(15, 60)
            blds.append(building(f"S{side}_{int(-y)}", rnd, side * (EDGE + depth / 2), y - width / 2,
                                 depth, width, height, abs(y)))
            y -= width + rnd.uniform(0, 1.5)
        for x in range(38, 200, 18):
            blds.append(building(f"CN{side}_{x}", rnd, side * (x + 9), STREET_HALF + SIDEWALK + 10, 16, 20,
                                 rnd.uniform(10, 60), math.hypot(x, 20)))
            blds.append(building(f"CS{side}_{x}", rnd, side * (x + 9), -(STREET_HALF + SIDEWALK + 10), 16, 20,
                                 rnd.uniform(8, 30), math.hypot(x, 20)))
    for i in range(14):
        y = rnd.uniform(220, 380)
        x = rnd.choice((-1, 1)) * rnd.uniform(55, 130)       # outside the avenue and its buildings (|x| < 40)
        blds.append(building(f"Tower{i}", rnd, x, y, rnd.uniform(18, 30), rnd.uniform(18, 30),
                             rnd.uniform(120, 230), y))
    return blds


# ---------- street: poles, traffic light, cafe, objects ----------

def build_streetlight(name, pos, facing):
    pole = flat("Pole", "#2B3140", rough=0.5, metallic=0.6)
    x, y = pos
    parts = [prism(f"{name}Pole", (x, y, 0.15), 8, 0.12, 0.09, 7.0, pole)]
    arm_x = x + facing * 1.2
    parts.append(box(f"{name}Arm", ((x + arm_x) / 2, y, 7.05), (1.4, 0.12, 0.12), pole))
    head_mat, head_power = keyed_emission(f"{name}HeadMat", "#2B3140", LUZ, 8.0)
    parts.append(box(f"{name}Head", (arm_x, y, 6.8), (0.7, 0.35, 0.22), head_mat))
    light = bpy.data.lights.new(f"{name}Light", "SPOT")
    light.energy = 2500
    light.color = lin(LUZ)[:3]
    light.spot_size = math.radians(110)
    light.spot_blend = 0.6
    obj = bpy.data.objects.new(f"{name}Light", light)
    obj.location = (arm_x, y, 6.65)
    bpy.context.collection.objects.link(obj)
    return SimpleNamespace(parts=parts, head=head_power, light=light)


def build_traffic_light(pos):
    pole = flat("TLPole", "#2B3140", rough=0.5, metallic=0.6)
    x, y = pos
    parts = [prism("TLPole", (x, y, 0.15), 8, 0.11, 0.11, 5.2, pole),
             box("TLHousing", (x, y - 0.2, 3.45), (0.45, 0.35, 1.3), flat("TLBox", "#1A1F29"))]
    lamps = {}
    for i, (name, color) in enumerate((("red", "#FF3B2F"), ("amber", LUZ), ("green", "#3DDC84"))):
        mat, power = keyed_emission(f"TL_{name}", "#111111", color, 0.0)
        parts.append(gem(f"TL_{name}", (x, y - 0.4, 4.5 - i * 0.4), 0.13, mat))
        lamps[name] = power
    glow = bpy.data.lights.new("TLGlow", "POINT")
    glow.energy = 60
    glow_obj = bpy.data.objects.new("TLGlow", glow)
    glow_obj.location = (x, y - 0.8, 4.05)
    bpy.context.collection.objects.link(glow_obj)
    return SimpleNamespace(parts=parts, lamps=lamps, glow=glow)


def build_cafe(x, y, facing):
    awning = flat("Awning", LUZ, rough=0.8)
    table = flat("Table", "#C9CED8", rough=0.5)
    window_mat, window_power = keyed_emission("CafeWindow", kit.GLASS, WARM, 0.9)
    parts = [box("CafeWindow", (x + facing * 0.05, y, 0.3), (0.1, 8, 2.4), window_mat),
             box("Awning", (x + facing * 1.2, y, 3.0), (2.4, 10, 0.15), awning)]
    tx = x + facing * 1.6
    for i, dy in enumerate((-3, 0, 3)):
        parts.append(prism(f"TableLeg{i}", (tx, y + dy, 0.15), 6, 0.04, 0.04, 0.72, table))
        parts.append(prism(f"TableTop{i}", (tx, y + dy, 0.87), 8, 0.4, 0.4, 0.04, table))
        for side in (-0.6, 0.6):
            parts.append(box(f"Chair{i}", (tx, y + dy + side, 0.15), (0.4, 0.4, 0.45), flat("Chair", "#7A5638")))
    return SimpleNamespace(parts=parts, window=window_power)


def hydrant(name, xy):
    mat = flat("Hydrant", "#8C2F2A", rough=0.6)
    x, y = xy
    body = prism(name, (x, y, 0.15), 8, 0.18, 0.16, 0.65, mat)
    cap = gem(name + "Cap", (0, 0, 0.72), 0.17, mat)
    cap.parent = body
    return body


def build_props():
    """Objects always on the sidewalks (never on the roadway)."""
    parts = [hydrant("Hydrant2", (-7.6, 26.0))]
    knocked = hydrant("HydrantHit", HYDRANT_XY)
    can = flat("TrashCan", "#2E3A2F", rough=0.7)
    parts += [prism("TrashCan", (-10.4, -14.0, 0.15), 8, 0.3, 0.33, 0.95, can),
              prism("TrashCan", (10.4, -16.0, 0.15), 8, 0.3, 0.33, 0.95, can),
              box("NewsBox", (-10.4, -17.5, 0.15), (0.45, 0.5, 1.1), flat("NewsBox", "#2E4A6B", rough=0.5))]
    bench = flat("Bench", "#5B4632")
    parts += [box("BenchSeat", (-10.5, -22.0, 0.6), (0.5, 1.8, 0.08), bench),
              box("BenchBack", (-10.75, -22.0, 0.68), (0.06, 1.8, 0.5), bench)]
    # No water jet: the parked car hid the base and the jet read as an antenna sticking out of the roof (QA).
    return SimpleNamespace(parts=parts, hydrant=knocked)


# ---------- cars ----------

def build_cars(names, rnd):
    """One low-poly car per simulation name (plus one parked), origin at the center and front along +y."""
    palette = ["#6B2E2E", "#2E4A6B", "#8A94A6", "#3C3C44", "#C9A227", "#D8D2C4", "#3F5A3A"]
    glass, tire = flat("CarGlass", "#141A24", rough=0.2), flat("Tire", "#0E0F12")
    cars = {}
    for name in [*names, "parked"]:
        body = flat(f"Paint_{name}", rnd.choice(palette), rough=0.4, metallic=0.3)
        head, head_power = keyed_emission(f"Head_{name}", "#FFFFFF", "#FFE7B0", 5.0)
        tail, tail_power = keyed_emission(f"Tail_{name}", "#5A1010", "#FF2A1A", 3.0)
        parts = [kit._box_geo(1.9, 4.4, 0.62, -0.95, -2.2, 0.28), kit._box_geo(1.65, 2.2, 0.55, -0.825, -1.3, 0.9)]
        for wx in (-0.98, 0.7):
            for wy in (-1.45, 1.15):
                parts.append(kit._box_geo(0.28, 0.66, 0.6, wx, wy, 0.02))
        parts += [kit._box_geo(0.38, 0.06, 0.16, -0.8, 2.18, 0.6), kit._box_geo(0.38, 0.06, 0.16, 0.42, 2.18, 0.6),
                  kit._box_geo(0.38, 0.06, 0.14, -0.8, -2.24, 0.62), kit._box_geo(0.38, 0.06, 0.14, 0.42, -2.24, 0.62)]
        verts, faces, owner = kit.merge(*parts)
        part_mat = [0, 1, 2, 2, 2, 2, 3, 3, 4, 4]
        obj = kit.mesh_object(f"Car_{name}", verts, faces, [body, glass, tire, head, tail], (0, 0, 0),
                              [part_mat[o] for o in owner])
        cars[name] = SimpleNamespace(obj=obj, paint=kit.principled(body).inputs["Base Color"],
                                     head=head_power, tail=tail_power)
    return cars


# ---------- people ----------

def person_mesh():
    """Person in a walking step (front along +y), low-poly organic mesh."""
    joints = [(0, 0, 0.95), (0, 0, 1.35), (0, 0, 1.52), (0, 0, 1.66),
              (-0.1, 0.12, 0.5), (-0.1, 0.25, 0.06), (0.1, -0.08, 0.5), (0.1, -0.22, 0.06),
              (-0.19, 0, 1.42), (-0.22, -0.08, 1.15), (-0.22, -0.12, 0.9),
              (0.19, 0, 1.42), (0.22, 0.08, 1.15), (0.22, 0.12, 0.9)]
    edges = [(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (0, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13)]
    radii = [0.15, 0.17, 0.06, 0.11, 0.07, 0.06, 0.07, 0.06, 0.07, 0.05, 0.045, 0.07, 0.05, 0.045]
    body = kit.skin_mesh("PersonBody", joints, edges, radii, subdivide=1, decimate=0.45)
    return kit.with_parts(body, kit._ico_geo(0.115, (0, 0.01, 1.68), (0.9, 0.95, 1.1)))


def build_people(rnd, count=80, accept=None):
    """Pedestrians on the sidewalks and crosswalks, each walking in a straight line. 'accept(x, y, heading, speed)'
    rejects routes that would cross cars, other people or objects; the rejected route is drawn again."""
    mesh = person_mesh()
    people = []
    tries = 0
    while len(people) < count and tries < 4000:
        tries += 1
        kind = rnd.random()
        if kind < 0.35:                                    # avenue sidewalks
            x = rnd.choice((-1, 1)) * rnd.uniform(AVENUE_HALF + 0.6, EDGE - 0.6)
            y = rnd.choice((rnd.uniform(-40, -7), rnd.uniform(7, 40)))
            heading = rnd.choice((0.0, math.pi))
        elif kind < 0.7:                                   # cross street sidewalks
            y = rnd.choice((-1, 1)) * rnd.uniform(STREET_HALF + 0.6, STREET_HALF + SIDEWALK - 0.6)
            x = rnd.choice((rnd.uniform(-40, -12), rnd.uniform(12, 40)))
            heading = rnd.choice((math.pi / 2, -math.pi / 2))
        else:                                              # crossing the avenue on the crosswalk
            y = rnd.choice((-1, 1)) * (STREET_HALF + 1.6) + rnd.uniform(-0.8, 0.8)
            x = rnd.uniform(-AVENUE_HALF, AVENUE_HALF)
            heading = rnd.choice((math.pi / 2, -math.pi / 2))
        if STAIR[0] - 0.6 < x < STAIR[1] + 0.6 and STAIR[2] - 1.5 < y < STAIR[3] + 1:
            continue
        if math.hypot(x - STATUE_XY[0], y - STATUE_XY[1]) < 2.0:
            continue
        speed = rnd.uniform(1.1, 1.6)
        if accept is not None and not accept(x, y, heading, speed):
            continue
        mat, flash = keyed_emission(f"Clothes{len(people)}", rnd.choice(CLOTHES), LUZ, 0.0)
        obj = kit.instance(f"Person{len(people)}", mesh, (x, y, surface_z(x, y)), mat, (0, 0, heading))
        people.append(SimpleNamespace(obj=obj, flash=flash, start=(x, y), heading=heading, speed=speed))
    return people


# ---------- statue ----------

THINKER_SCALE = 1.3
THINKER_HEAD = (0.0, 0.44, 0.80)          # head in the figure's local system (front along +y)


def build_statue():
    """Miniature replica of Rodin's The Thinker (bronze, public domain), seated on a rock,
    chin resting on the right hand, facing west."""
    x, y = STATUE_XY
    stone = flat("Pedestal", "#5A5F6B")
    bronze = flat("Bronze", BRONZE, rough=0.65, metallic=0.85)          # matte: at 0.42 it looked like jade
    box("Plaza", (x, y, 0.15), (14, 14, 0.04), flat("Plaza", "#454C5C"))
    box("PedestalBase", (x, y, 0.19), (2.4, 2.4, 0.4), stone)
    box("Pedestal", (x, y, 0.59), (1.6, 1.6, 1.0), stone)

    # Skeleton seated and leaning forward: right elbow on the right thigh, hand on the chin.
    # (With the elbow on the left thigh, as in the original, the forearm went straight up the middle of the chest
    # and, from the front, became a vertical tube at the center of the body; the arm looked odd.)
    joints = [(0, 0, 0.10), (0, 0.10, 0.40), (0, 0.22, 0.62), (0, 0.34, 0.74), (0, 0.42, 0.79),
              (-0.14, 0.45, 0.12), (-0.16, 0.50, -0.40), (0.14, 0.45, 0.12), (0.18, 0.42, -0.40),
              (0.21, 0.20, 0.64), (0.16, 0.47, 0.22), (0.06, 0.55, 0.66),
              (-0.21, 0.20, 0.64), (-0.29, 0.36, 0.30), (-0.20, 0.55, 0.14)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (0, 7), (7, 8),
             (2, 9), (9, 10), (10, 11), (2, 12), (12, 13), (13, 14)]
    radii = [0.18, 0.2, 0.22, 0.08, 0.1, 0.095, 0.08, 0.095, 0.08, 0.095, 0.075, 0.08, 0.095, 0.07, 0.06]
    body = kit.skin_mesh("ThinkerBody", joints, edges, radii, subdivide=2, decimate=0.4)
    hx, hy, hz = THINKER_HEAD
    figure = kit.with_parts(body, kit._ico_geo(0.13, (hx, hy, hz), (0.9, 0.98, 1.1)),
                            kit._gem_geo(0.03, oz=hz - 0.02, stretch=1.5, ox=hx, oy=hy + 0.13))
    rock_mat = flat("ThinkerRock", "#4A4F57", rough=0.9)
    rock = kit._ico_geo(0.5, (0, 0.05, -0.32), (1.0, 0.95, 0.6))
    step = kit._ico_geo(0.4, (0, 0.48, -0.5), (1.1, 0.7, 0.3))

    root = bpy.data.objects.new("StatueRoot", None)
    root.location = (x, y, STATUE_TOP + 0.62 * THINKER_SCALE)
    root.rotation_euler = (0, 0, math.radians(90))          # local front +y becomes -x (west)
    root.scale = (THINKER_SCALE,) * 3
    bpy.context.collection.objects.link(root)
    pieces = [kit.instance("Thinker", figure, (0, 0, 0), bronze),
              kit.mesh_object("ThinkerRock", rock[0], rock[1], [rock_mat]),
              kit.mesh_object("ThinkerStep", step[0], step[1], [rock_mat])]
    for piece in pieces:
        piece.parent = root
    spot = bpy.data.lights.new("StatueSpot", "SPOT")
    spot.energy = 900
    spot.color = lin(WARM)[:3]
    spot.spot_size = math.radians(35)
    obj = bpy.data.objects.new("StatueSpot", spot)
    obj.location = (x - 3.5, y - 3.5, 0.3)
    obj.rotation_euler = (Vector((x, y, 2.6)) - Vector(obj.location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(obj)
    # Head in the world: the local front (+y) points to -x.
    head = (x - hy * THINKER_SCALE, y, root.location.z + hz * THINKER_SCALE)
    return SimpleNamespace(bronze=kit.principled(bronze).inputs["Base Color"], spot=spot, head=head)


# ---------- nature: cracks, weeds, trees, pot ----------

def crack(rnd, start, angle, segments, z, mat, width=(0.12, 0.35)):
    """Irregular crack: trapezoidal segments of variable width, each with its origin at the start
    (grows by stretching from there). Returns (segments, path points)."""
    x, y = start
    w0 = rnd.uniform(*width)
    segs, points = [], [(x, y)]
    for _ in range(segments):
        length = rnd.uniform(0.6, 1.4)
        angle += rnd.uniform(-0.55, 0.55)
        w1 = max(0.05, w0 * rnd.uniform(0.7, 1.15))
        v = [(-w0 / 2, 0, 0), (w0 / 2, 0, 0), (w1 / 2, length, 0), (-w1 / 2, length, 0)]
        seg = kit.mesh_object("Crack", v, [(0, 1, 2, 3)], [mat], (x, y, z))
        seg.rotation_euler = (0, 0, angle)
        segs.append(seg)
        x, y = x - math.sin(angle) * length, y + math.cos(angle) * length
        points.append((x, y))
        w0 = w1
    return segs, points


def build_overgrowth(rnd):
    crack_mat = flat("Crack", "#07090D", rough=1.0)
    weed_mat = flat("Weed", "#5C8A3E")
    cracks, weeds = [], []
    starts = [((-6.5, -3.0), -1.2, 0.006), ((3.0, -4.5), 0.4, 0.006), ((-2.0, 4.0), 2.2, 0.006),
              ((6.0, 2.0), 1.9, 0.006), ((0.5, -14.0), 0.1, 0.006), ((-3.0, 10.0), -0.2, 0.006),
              ((-9.0, -8.0), 0.2, 0.156), ((9.0, -12.0), 0.1, 0.156), ((-9.4, 6.0), -0.1, 0.156)]
    for (sx, sy), ang, z in starts:
        main, pts = crack(rnd, (sx, sy), ang, rnd.randint(9, 14), z, crack_mat)
        group = list(main)
        for px, py in pts[2::4]:                           # branches
            br, _ = crack(rnd, (px, py), ang + rnd.choice((-1, 1)) * rnd.uniform(0.7, 1.3), rnd.randint(3, 6), z,
                          crack_mat, width=(0.06, 0.16))
            group += br
        cracks.append(group)
        for px, py in pts[1::2]:
            for _ in range(rnd.randint(2, 4)):
                weeds.append(prism("Weed", (px + rnd.uniform(-0.2, 0.2), py + rnd.uniform(-0.2, 0.2), z), 5,
                                   0.08, 0.0, rnd.uniform(0.25, 0.55), weed_mat))
    grass_mat = flat("Grass", "#3E6E44")
    patches = []
    for _ in range(140):
        x, y = rnd.uniform(-25, 30), rnd.uniform(-30, 60)
        if STAIR[0] - 0.5 < x < STAIR[1] + 0.5 and STAIR[2] - 0.5 < y < STAIR[3] + 0.5:
            continue
        if COLLAPSE[0] - 0.8 < x < COLLAPSE[1] + 0.8 and COLLAPSE[2] - 0.8 < y < COLLAPSE[3] + 0.8:
            continue
        r = rnd.uniform(0.5, 1.8)
        patches.append(prism("GrassPatch", (x, y, surface_z(x, y)), 7, r, r * 0.6, 0.2, grass_mat))
    return SimpleNamespace(cracks=cracks, weeds=weeds, patches=patches)


def build_pot():
    """Stainless steel pot with a plastic handle (open, dark inside), and a second one toppled beside it."""
    steel = flat("StainlessPot", "#C7CCD3", rough=0.28, metallic=0.9)
    inside = flat("PotInside", "#3A3F47", rough=0.5)
    plastic = flat("PlasticHandle", "#2A2A30", rough=0.35)
    px, py = POT_XY
    z = surface_z(px, py)
    pot = [prism("Pot", (px, py, z), 20, 0.24, 0.25, 0.24, steel),
           prism("PotLip", (px, py, z + 0.24), 20, 0.265, 0.265, 0.02, steel),
           prism("PotInside", (px, py, z + 0.2), 20, 0.22, 0.22, 0.065, inside),
           box("PotHandle", (px + 0.48, py, z + 0.19), (0.44, 0.07, 0.06), plastic)]
    tipped = prism("Pot2", (0, 0, 0), 20, 0.17, 0.18, 0.2, steel)
    tipped.location = (px - 0.5, py + 0.45, z + 0.18)
    tipped.rotation_euler = (math.radians(82), 0, math.radians(35))
    handle2 = box("Pot2Handle", (px - 0.78, py + 0.75, z), (0.32, 0.06, 0.05), plastic)
    handle2.rotation_euler = (0, 0, math.radians(35))
    return pot + [tipped, handle2]


def tree(name, xy, rnd, trunk_mat, leaf_mats):
    h = rnd.uniform(3.5, 6.5)
    trunk = kit._prism_geo(6, 0.22, 0.16, h * 0.45)
    if rnd.random() < 0.45:
        crown = kit.merge(kit._prism_geo(7, h * 0.32, 0.0, h * 0.5, oz=h * 0.3),
                          kit._prism_geo(7, h * 0.24, 0.0, h * 0.45, oz=h * 0.55))[:2]
    else:
        crown = kit._gem_geo(h * 0.3, oz=h * 0.62, stretch=1.1)
    verts, faces, owner = kit.merge(trunk, crown)
    obj = kit.mesh_object(name, verts, faces, [trunk_mat, rnd.choice(leaf_mats)], (xy[0], xy[1], 0.0), owner)
    obj.rotation_euler = (0, 0, rnd.uniform(0, math.tau))
    return obj


def build_forest(rnd, footprints=()):
    trunk = flat("Trunk", "#4A3A2A")
    leaves = [flat(f"Leaves{i}", c, rough=0.95) for i, c in enumerate(LEAVES)]
    sx, sy = STATUE_XY

    def free(x, y):
        if math.hypot(x - sx, y - sy) < 6.5:
            return False                                          # statue clearing
        if -14 < x < sx and abs(y - 13.0) < 3.0:
            return False                                          # camera path to the statue
        if math.hypot(x - POT_XY[0], y - POT_XY[1]) < 3.0:
            return False                                          # pot close-up
        if COLLAPSE[0] - 0.5 < x < COLLAPSE[1] + 0.5 and COLLAPSE[2] - 0.5 < y < COLLAPSE[3] + 0.5:
            return False                                          # stream
        if STAIR[0] - 1.0 < x < STAIR[1] + 1.0 and STAIR[2] - 1.0 < y < STAIR[3] + 1.0:
            return False                                          # subway stairs
        return True

    def in_building(x, y):
        return any(x0 - 1.0 < x < x1 + 1.0 and y0 - 1.0 < y < y1 + 1.0 for x0, x1, y0, y1 in footprints)

    first, second = [], []
    far = []
    while len(far) < 380:
        x, y = rnd.uniform(-240, 240), rnd.uniform(-200, 360)
        if abs(x) > 60 or y > 130 or y < -60:
            far.append(tree(f"FarTree{len(far)}", (x, y), rnd, trunk, leaves))
            far[-1]["in_building"] = in_building(x, y)
    second += far
    for batch, count in ((first, 200), (second, 260)):
        placed = 0
        while placed < count:
            x, y = rnd.uniform(-60, 60), rnd.uniform(-60, 130)
            if free(x, y):
                batch.append(tree(f"Tree{len(first) + len(second)}", (x, y), rnd, trunk, leaves))
                batch[-1]["in_building"] = in_building(x, y)
                placed += 1
    return first, second


def build(person_ok=None):
    rnd = random.Random(42)
    world = build_world()
    ground = build_ground()
    stair = build_stairwell()
    city = build_city(rnd)
    streetlights = [build_streetlight(n, p, f) for n, p, f in (
        ("SL1", (-AVENUE_HALF - 0.6, 20), 1), ("SL2", (AVENUE_HALF + 0.6, -14), -1),
        ("SL3", (-AVENUE_HALF - 0.6, 46), 1), ("SL4", (AVENUE_HALF + 0.6, 34), -1),
        ("SL5", (-AVENUE_HALF - 0.6, -10), 1))]
    traffic = build_traffic_light((-AVENUE_HALF - 0.7, STREET_HALF + 0.7))
    statue = build_statue()
    cafe = build_cafe(EDGE, 36.0, -1)
    props = build_props()
    people = build_people(rnd, accept=person_ok)
    footprints = [(b["center"][0] - b["size"][0] / 2, b["center"][0] + b["size"][0] / 2,
                   b["center"][1] - b["size"][1] / 2, b["center"][1] + b["size"][1] / 2) for b in city]
    forest = build_forest(rnd, footprints)
    growth = build_overgrowth(rnd)
    pot = build_pot()
    return SimpleNamespace(world=world, ground=ground, stair=stair, city=city, streetlights=streetlights,
                           traffic=traffic, statue=statue, cafe=cafe, props=props, people=people,
                           forest=forest, growth=growth, pot=pot, rnd=rnd)
