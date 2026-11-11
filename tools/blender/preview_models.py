"""Model showcase: builds a model with daylight and renders views to check proportion and readability.

Usage: blender -b -P tools/blender/preview_models.py -- <model> <output folder>
Models: ant (stage ant), cow, farm, cell, dino, globe, moon (moon-disappeared), cast (Quaternius assets of pangaea-never-split), people (the five
prehistoric people of scene 08, dressed by caveman.dress), town (cast and objects of technology-disappeared: sack on the shoulder,
bicycle, hoe, horse with reins, cart, driver on the ground, fire with flint), street (the main street)
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import dinos  # noqa: E402
import farm_animals as fa  # noqa: E402
import globe as gl  # noqa: E402
import kit  # noqa: E402


def stage():
    kit.reset_scene(1, 30)
    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = kit.lin("#6F86A8")
    bg.inputs["Strength"].default_value = 1.0
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(-40))
    bpy.context.collection.objects.link(sun)
    kit.box("Ground", (0, 0, -0.05), (40, 40, 0.05), kit.flat("Grass", "#4F6B3E"))


def camera():
    cam = bpy.context.scene.camera
    if cam is None:
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        bpy.context.collection.objects.link(cam)
        bpy.context.scene.camera = cam
    return cam


def aim(pos, target, lens=50):
    cam = camera()
    cam.data.lens = lens
    cam.location = pos
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y")
    return cam


def shoot(out, name, pos, target, lens=50, res=(1080, 1080)):
    aim(pos, target, lens)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def preview_cow(out):
    fat = fa.cow("Fat", (0, 1.4, 0))
    thin = fa.cow("Thin", (0, -1.4, 0))
    fa.set_thin(thin, 1.0, 1)
    fa.head_down(thin, 35, 1)
    shoot(out, "cow_side", (0.2, -9.0, 1.2), (0.2, 0, 0.9), lens=45)
    shoot(out, "cow_34", (4.5, -6.5, 2.2), (0, 0, 0.9), lens=40)
    shoot(out, "cow_back", (-6.0, -3.5, 2.6), (0, 0, 0.9), lens=40)


def preview_farm(out):
    import random
    import farm_buildings as fb
    rnd = random.Random(1)
    b = fb.barn(0, 16)
    fb.trough("Trough", -4.6, 19, 28)
    for i, y in enumerate((20.5, 23.0, 25.5)):
        c = fa.cow(f"Cow{i}", (-3.2, y, 0), heading=math.pi)
        fa.head_down(c, 30 + 8 * i, 1)
    win = kit.flat("Win", "#2A2410", emission="#F5A524", strength=3.0)
    fb.house(0, -2, win)
    fb.fence("Fence", [(-14, 4), (-6, 4)])
    fb.fence("Fence2", [(6, 4), (14, 4), (14, 34)])
    fb.round_bale("Bale", (8, 10, 0), 0.4)
    fb.round_bale("Bale2", (9.6, 11.2, 0), 1.2)
    fb.manure_bay(6, 36, rnd)
    fb.silo(-9, 22)
    fb.windmill(-12, 8)
    shoot(out, "farm_wide", (18, -16, 9), (0, 14, 3), lens=28)
    shoot(out, "farm_porch", (0, 0.2, 2.1), (0, 16, 2.6), lens=24)
    shoot(out, "barn_in", (0.5, 15.0, 1.7), (-3.2, 23, 0.9), lens=22)
    shoot(out, "barn_back", (2, 31.6, 1.7), (6, 36, 0.8), lens=24)


def preview_cell(out):
    import random
    import cell_models as cm
    rnd = random.Random(3)
    origin = Vector((0, 0, -500))
    hero_at = Vector((-3, -24, -3))
    cell = cm.cell_interior(tuple(origin), keep_clear=[(0, -38, 4), tuple(hero_at)])
    hero = cm.mitochondrion("Hero", tuple(origin + hero_at), rotation=(0, 0, math.radians(-25)))
    cm.pulse(hero, 1, 60)
    cam = camera()
    cam.data.clip_end = 1000
    shoot(out, "cell_mito", tuple(origin + hero_at + Vector((2.6, -3.4, 2.9))), tuple(origin + hero_at), lens=35)
    shoot(out, "cell_wide", tuple(origin + Vector((0, -38, 4))), tuple(origin + Vector((4, 18, 0))), lens=24,
          res=(1080, 1920))
    cell.root.hide_render = True
    for obj in cell.root.children_recursive + hero.root.children_recursive:
        obj.hide_render = True

    # first-person hands, out there
    pos, target = (0, -6, 1.65), (0, 4, 1.0)
    aim(pos, target, lens=24)
    h = cm.hands(cam)
    sl = cm.specks_on_surface("SpecksL", [h.left], 400, rnd, parent=h.left, mats=cm.SKIN_MATS, gem=(0.006, 0.012))
    sr = cm.specks_on_surface("SpecksR", [h.right], 400, rnd, parent=h.right, mats=cm.SKIN_MATS, gem=(0.006, 0.012))
    cm.specks_in_air("SpecksAir", (0, 0, 1.0), (8, 8, 1.5), 300, rnd, gem=(0.02, 0.04), rise=(0.5, 1.5))
    for s in (sl, sr):
        cm.shimmer(s, 1, 90)
    shoot(out, "hands_raised", pos, target, lens=24, res=(1080, 1920))
    cm.pose_open_palm(h, 1)
    shoot(out, "hands_palm", pos, target, lens=24, res=(1080, 1920))
    cm.blink_away(sr, 2, 12)
    bpy.context.scene.frame_set(8)
    shoot(out, "hands_blink", pos, target, lens=24, res=(1080, 1920))


def preview_dino(out):
    dinos.sauropod("Brachio", (0, 0, 0), heading=math.radians(90))
    dinos.mammal("Shrew", (3.0, -4.0, 0), heading=math.radians(200), scale=4.0)
    shoot(out, "dino_side", (32, 6, 6), (0, 0, 6), lens=35)
    shoot(out, "dino_front", (10, 26, 4), (0, 0, 6), lens=35)
    shoot(out, "dino_eye", (8, -14, 1.65), (0, 2, 7), lens=22, res=(1080, 1920))


def preview_globe(out):
    import random
    rnd = random.Random(3)
    p = gl.globe("Pan", (0, -14, 0), rnd, pangaea=True)
    m = gl.globe("Mod", (0, 14, 0), rnd, pangaea=False)
    for root in (p.root, m.root):
        root.rotation_quaternion = (0.966, 0, 0, -0.259)
    bpy.data.objects["Ground"].hide_render = True
    shoot(out, "globe_pair", (75, 0, 8), (0, 0, 0), lens=35, res=(1080, 1920))
    shoot(out, "globe_pan", (60, -14, 10), (0, -14, 0), lens=50, res=(1080, 1920))


def preview_cast(out):
    """Cast of pangaea-never-split: Apatosaurus walking (foot planted, neck raised), rat, people with spear."""
    import types
    import pangaea_cast as pc
    import plant
    import rigs
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 200
    tl = types.SimpleNamespace(at=lambda sid, u=0.0: int(1 + 160 * u), fps=30)
    flat = lambda x, y: 0.0
    d = pc.apatosaurus("Apato", 22.0, pc.APATO_TINTS[0])
    plant.walk(d, pc.APATO_FEET, 1, 200, (0, 0), math.pi / 2, flat, rate=1.5,
               speed_from=["FrontFoot.L", "FrontFoot.R"], sink=0.2, anchor=100)
    up = pc._neck(d, 26)
    rigs.pose_layer(d, [1, 200], lambda f: up)
    rat = rigs.spawn("rat", "Rat", length=0.7, location=(4.0, -1.0, 0), heading=math.radians(200))
    rigs.paint(rat, pc.RAT_COLORS)
    rigs.loop(rat, "Run", 1, 200)
    for k, (key, x) in enumerate((("man", 6.0), ("woman", 7.2))):
        p = rigs.spawn(key, f"P{k}", height=1.7, location=(x, 0, 0), heading=math.pi / 2)
        rigs.paint(p, {"Shirt": pc.HIDES[k], "Pants": pc.HIDES[2], "Skin": pc.SKINS[k], "Hair": "#2A1E16",
                       "Eyes": "#33261C", "Socks": "#4A3626", "HairBase": "#2A1E16", "Shoes": "#33261C"})
        rigs.loop(p, "Walk", 1, 200)
        if key == "man":
            pc._hold(p, "Palm.R", pc._spear("Spear"), 100, 10.0)
    bpy.data.objects["Ground"].scale = (8, 8, 1)
    bpy.data.objects["Ground"].location.x -= 160
    bpy.data.objects["Ground"].location.y -= 160
    scene.frame_set(100)
    c = d.root.matrix_world.translation
    shoot(out, "cast_dino_side", tuple(c + Vector((-34, 0, 3))), tuple(c + Vector((0, 0, 4))), lens=30)
    shoot(out, "cast_dino_front", tuple(c + Vector((-6, 30, 2))), tuple(c + Vector((0, 0, 4))), lens=30)
    shoot(out, "cast_dino_eye", tuple(c + Vector((-20, -14, 1.65))), tuple(c + Vector((0, 2, 5))), lens=22,
          res=(1080, 1920))
    shoot(out, "cast_small_side", (14.0, -1.0, 1.0), (5.5, 0, 0.6), lens=35)
    shoot(out, "cast_small_eye", (9.5, -4.0, 1.65), (5.5, 1.0, 0.8), lens=22, res=(1080, 1920))
    shoot(out, "cast_rat_close", (4.0, -2.6, 0.5), (4.0, -1.0, 0.15), lens=35)


def preview_people(out):
    """The five people of scene 08 side by side, mid-step (Walk in place): front, side, back and
    close-up (a man and a woman), at eye level."""
    import caveman
    import pangaea_cast as pc
    import rigs
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 120
    for k, look in enumerate(pc.LOOKS):
        key = "woman" if k in (1, 3) else "man"
        p = rigs.spawn(key, f"P{k}", height=1.58 if key == "woman" else 1.70, location=(1.1 * (k - 2), 0, 0),
                       heading=-math.pi / 2)
        caveman.dress(p, dict(look, skin=pc.SKINS[k % 3], hide=pc.HIDES[(k + 1) % 3], seed=11 + 7 * k))
        rigs.loop(p, "Walk", 1, 120, phase=0.13 * k)
        if k in (0, 4):
            pc._hold(p, "Palm.R", pc._spear(f"Spear{k}"), 40, 10.0)
    scene.frame_set(40)
    shoot(out, "people_front", (0, -8.5, 1.5), (0, 0, 0.95), lens=40, res=(1600, 900))
    shoot(out, "people_back", (0, 8.5, 1.5), (0, 0, 0.95), lens=40, res=(1600, 900))
    shoot(out, "people_side", (9.0, -0.3, 1.5), (0, 0, 0.95), lens=40, res=(1600, 900))
    people = [bpy.data.objects[f"P{k}"] for k in range(5)]
    for k in range(5):
        for j, root in enumerate(people):                      # one at a time: the neighbors do not enter the frame
            for o in (root, *root.children_recursive):
                o.hide_render = j != k
        x = 1.1 * (k - 2)
        for tag, pos in (("front", (x + 0.4, -3.4, 1.6)), ("side", (x + 3.4, 0.2, 1.5)), ("back", (x - 0.4, 3.4, 1.6))):
            shoot(out, f"person{k}_{tag}", pos, (x, 0, 0.95), lens=35, res=(800, 1000))


def preview_town(out):
    """Cast of technology-disappeared posed mid-action (frame 30 of a cycle), side by side."""
    import random
    import rigs
    import town_cast as tc
    import town_props as tp
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 120
    frames = list(range(1, 121))
    a = tc.person("man", "Sacker", 1.78, 0, heading=-math.pi / 2, location=(-4.0, 0, 0))
    tc.walk_timed(a, frames, 1.2)
    tc.sack_carrier(a, tp.sack("SackA"))
    b = tc.person("woman", "Biker", 1.66, 1, heading=-math.pi / 2, location=(-2.2, 0, 0))
    tc.walk_timed(b, frames, 1.2, phase=0.4)
    bike, wheels, grips = tp.bicycle("Bike")
    tc.bike_pusher(b, bike, grips)
    c = tc.person("man", "Hoer", 1.8, 2, heading=-math.pi / 2, location=(0.0, 0, 0))
    rigs.loop(c, "Idle", 1, 120)
    tc.hoe_worker(c, tp.hoe("Hoe"), frames)
    d = tc.person("man", "Fire", 1.76, 3, heading=-math.pi / 2, location=(2.0, 0, 0))
    tc.segment(d, "Sitting", 1, 120, 30, 190)
    tc.fire_starter(d, tp.flint("Flint"), tp.knife("Knife"), frames, [30, 60, 90])
    d.root.location.z = 0.0
    tp.tinder("Tinder", random.Random(1)).location = (2.0 - 0.5, -0.55, 0)
    e = tc.person("woman", "Point", 1.64, 4, heading=-math.pi / 2, location=(4.0, 0, 0))
    rigs.loop(e, "Idle", 1, 120)
    tc.look_up(e, frames, 35)
    tc.pointer(e)
    h = rigs.spawn("horse", "Horse", length=2.7, location=(7.5, 0.8, 0), heading=-math.pi / 2)
    g = tc.person("man", "Ground", 1.78, 5, heading=-math.pi / 2, location=(6.0, -2.5, -0.3))
    tc.segment(g, "Sitting", 1, 120, 30, 190)
    rigs.pose_layer(g, [1, 120], lambda f: tc.bend(g, tc.ground_sit(g, 1.0)))
    rigs.loop(h, "Walk", 1, 120)
    cart = tp.cart("Cart")
    cart.location = (-7.5, 0, 0)
    for f, name in ((20, "a"), (30, "b"), (36, "c")):
        scene.frame_set(f)
        shoot(out, f"town_front_{name}", (0, -11, 1.6), (0, 0, 0.9), lens=26, res=(1800, 900))
    scene.frame_set(30)
    shoot(out, "town_side", (14, -2, 1.6), (0, 0, 0.9), lens=30, res=(1800, 900))
    shoot(out, "town_close_fire", (2.6, -2.6, 1.2), (2.0, -0.4, 0.5), lens=35, res=(1000, 1000))
    shoot(out, "town_close_bike", (-1.0, -3.6, 1.6), (-2.4, 0, 0.9), lens=35, res=(1000, 1000))
    shoot(out, "town_close_hoe", (1.5, -3.2, 1.6), (0, -0.4, 0.9), lens=35, res=(1000, 1000))


def preview_street(out):
    """The main street of technology-disappeared by day: townhouses, signs, poles, traffic light, cars and the water tower;
    from the front (eye level), from the side (facades) and from above (the hill and the fields)."""
    import random
    import town_cast as tc
    import town_far as tf
    import town_set as ts
    bpy.data.objects["Ground"].hide_render = True
    rnd = random.Random(42)
    ts.build(rnd)
    tf.build(rnd)
    for k, (x, y, h) in enumerate(((2.0, 18.0, 90), (-2.0, 30.0, -90))):
        tc.car(f"Car{k}", ("NormalCar1", "SUV")[k], tc.CAR_COLORS[k + 1], (x, y, 0.0), math.radians(h))
    cam = camera()
    cam.data.clip_end = 3000
    shoot(out, "street_eye", (7.6, -1.0, 1.8), (-1.5, 70, 5.2), lens=22, res=(1080, 1920))
    shoot(out, "street_facades", (-4.0, 20.0, 2.5), (10.0, 28.0, 4.0), lens=24, res=(1600, 900))
    shoot(out, "street_tower", (0.0, 200.0, 8.0), (6.0, 298.0, 35.0), lens=30, res=(1080, 1920))
    shoot(out, "street_aerial", (60.0, -120.0, 90.0), (0.0, 80.0, 0.0), lens=24, res=(1600, 900))


def preview_valley(out):
    """People of two-humans-left: frozen poses and clothes (adults and children), seated couple with the baby in their lap."""
    import random
    import valley_cast as vc
    x = -6.0
    for k in range(12):
        hgt = 1.74 if k % 2 == 0 else 1.62
        vc.figure(f"F{k}", x, 0, math.pi, hgt, k)
        x += 0.75
    for k in range(4):
        vc.figure(f"K{k}", x, 0, math.pi, (1.1, 1.3, 0.95, 1.2)[k], k + 3)
        x += 0.65
    import town_cast as tc
    bench = kit.flat("Bench", "#4A3424")
    kit.mesh_object("Bench", *kit.merge(kit._box_geo(1.7, 0.42, 0.07, -0.85, -0.21, 0.4))[:2], [bench], (0, -3.0, 0))
    wom = vc.adult_sit("woman", "Wom4", 0.36, -3.0, -math.pi / 2, 60)
    man = vc.adult_sit("man", "Man4", -0.36, -3.0, -math.pi / 2, 60)
    body, glow, arm, parts = vc.baby(wom)
    vc.hold_baby(wom, body)
    vc.touch_baby(man, body)
    bpy.context.scene.frame_set(20)
    shoot(out, "valley_people", (0.0, -12.0, 1.0), (0.0, 0, 0.85), lens=30, res=(1800, 600))
    shoot(out, "valley_sit_front", (0.0, -5.6, 1.3), (0.0, -3.0, 0.7), lens=40)
    shoot(out, "valley_sit_side", (2.6, -3.6, 1.2), (0.2, -3.1, 0.7), lens=40)
    shoot(out, "valley_baby", (0.6, -4.4, 1.35), (0.35, -3.3, 0.72), lens=60)


def preview_vhouse(out):
    """Houses of the valley (two-humans-left): variants, window lit and unlit, roof with eaves."""
    import valley_houses as vh
    hs = [vh.house("a1", -7.5, 0, 0.0, 2, 2, gable=True), vh.house("b2", 0.0, 0, 0.0, 3, 2, gable=True),
          vh.house("c3", 8, 0, math.pi / 2, 2, 2, ridge_x=False, gable=True)]
    for h in hs[:2]:
        h.power.default_value = 6.0
    vh.house("cabin", 0, -9, math.pi, 2, 2, mode="cabin")
    bpy.data.worlds[0].node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    shoot(out, "vhouse_front", (0.5, 17.0, 2.0), (0.5, 0, 2.2), lens=24, res=(1600, 900))
    shoot(out, "vhouse_34", (12.0, 10.0, 3.0), (1.0, 0, 2.0), lens=24, res=(1600, 900))
    shoot(out, "vhouse_cabin", (3.0, -18.0, 1.7), (0, -9, 2.0), lens=24, res=(1600, 900))


def preview_moon(out):
    """Models of moon-disappeared: owl (x2, as in the scene), walking rat, fishing boat, globe with ring,
    lantern, crate, Sun with halo and Moon with maria. Views from the front, side and at eye level."""
    import random
    import moon_models as mm
    bpy.data.objects["Ground"].location.z = -0.0502
    post = kit.box("Post", (0, 0, 0), (0.12, 0.12, 1.0), kit.flat("PostW", "#6A4E34"))
    ow = mm.owl()
    ow.root.location = (0, 0, 1.0)
    ow.root.scale = (2, 2, 2)
    for lid in ow.lids:
        lid.scale = (1, 1, 0.05)
    shoot(out, "moon_owl_front", (0, -1.9, 1.35), (0, 0, 1.28), lens=50)
    shoot(out, "moon_owl_side", (1.9, -0.3, 1.35), (0, 0, 1.28), lens=50)
    ow.neck.rotation_euler = (0, 0.15, math.radians(80))
    shoot(out, "moon_owl_turn", (0.9, -1.6, 1.25), (0, 0, 1.28), lens=50)
    for o in [ow.root, *ow.root.children_recursive, post]:
        o.hide_render = True
    ms = [mm.mouse(f"M{k}", 1.5) for k in range(3)]
    for k, m in enumerate(ms):
        fr = [(f, -0.3 + 0.012 * f * (k == 1), 0.25 * k - 0.25, 0, 0.0 if k != 2 else math.radians(-90)) for f in range(0, 20)]
        mm.animate_mouse(m, fr, 30)
    bpy.context.scene.frame_set(12)
    shoot(out, "moon_mouse_side", (0.9, 0.0, 0.18), (-0.25, 0.0, 0.03), lens=50)
    shoot(out, "moon_mouse_eye", (-0.2, -1.1, 0.5), (-0.2, 0.0, 0.02), lens=50)
    for o in bpy.data.objects:
        if o.name.startswith("M") and o.name[1:2].isdigit():
            o.hide_render = True
    b = mm.boat()
    b.root.location = (0, 20, 0)
    shoot(out, "moon_boat_side", (0, 4, 2.2), (0, 20, 2.0), lens=35, res=(1600, 900))
    shoot(out, "moon_boat_34", (12, 8, 4.0), (0, 20, 1.8), lens=35, res=(1600, 900))
    gl = mm.earth("Earth", random.Random(3))
    gl.root.location, gl.root.scale = (0, -6, 2.0), (0.05, 0.05, 0.05)
    ring = mm.rim_ring("Rim", 0.5, 0.53)
    ring.location = (0, -6, 2.0)
    shoot(out, "moon_globe", (0, -9.5, 2.0), (0, -6, 2.0), lens=50)
    lg, lf = mm.lantern("Lan", (3, -6, 1.6), kit.flat("LanG", "#000000", emission=kit.LUZ, strength=8))
    mm.crate("Crate", (3.3, -6.3, 0.0))
    shoot(out, "moon_lantern_crate", (3.5, -7.4, 1.1), (3.15, -6.1, 0.8), lens=30)


def preview_plants(out):
    """Models of plants-extinct: plane tree in the 4 states (front, side, eye), stall with awning, living and soft fruit,
    brazier, pile of firewood with bracket fungi, fish crate, whitewashed house, pot, fallen branch with fungi."""
    import random
    import plants_models as pm
    import plants_set as ps
    sc = bpy.context.scene
    sc[pm.STATE] = 0.0
    M = ps.make_mats()
    rnd = random.Random(3)
    sun = bpy.data.objects["Sun"]
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = ps.sun_vector().to_track_quat("Z", "Y")
    t = pm.plane_tree("Tree", (0, 0, 0), M, rnd)
    states = {0: ("now",), 1: ("week",), 2: ("year",), 3: ()}
    for s, keep in states.items():
        sc[pm.STATE] = float(s)
        for k, o in t.canopies.items():
            o.hide_render = k not in keep
        shoot(out, f"plants_tree_s{s}_front", (0, -30, 7.5), (0, 0, 7.0), lens=35, res=(900, 1100))
        if s in (0, 3):
            shoot(out, f"plants_tree_s{s}_side", (30, 0, 7.5), (0, 0, 7.0), lens=35, res=(900, 1100))
            shoot(out, f"plants_tree_s{s}_eye", (5, -11, 1.65), (0, 0, 5.0), lens=24, res=(900, 1100))
    for o in [t.root, *t.root.children_recursive]:
        o.hide_render = True
    sc[pm.STATE] = 0.0
    st = pm.stall("Stall", (20, 0, 0), M)
    for k, x in enumerate((-0.8, -0.25, 0.3, 0.85)):
        pm.fruit_crate(f"Crate{k}", (20 + x, 0.45, 0.9), M, M["fruit"], rnd, kind=k)
    br = pm.brazier("Braz", (21.6, 0.3, 0.0), {**M, "ember": M["ember"]}, rnd)
    br.root.location.z = 0.0
    kit.box("Mureta", (23.2, 1.6, 0), (1.6, 0.3, 0.8), M["stone"])
    pm.woodpile("Wood", (23.2, 0.9, 0.0), M, rnd)
    pm.fish_crate("Fish", (19.0, 0.35, 0.9), M, rnd)
    shoot(out, "plants_stall_front", (20.8, 4.5, 1.9), (20.8, 0.4, 1.2), lens=30, res=(1100, 900))
    shoot(out, "plants_stall_pov", (20.3, -0.6, 1.65), (20.3, 1.2, 1.0), lens=24, res=(900, 1100))
    shoot(out, "plants_woodpile", (23.0, -1.0, 0.9), (23.2, 0.9, 0.35), lens=40, res=(1100, 900))
    sc[pm.STATE] = 1.0
    for o in list(bpy.data.objects):
        if o.name.startswith("Crate") and o.name.endswith("Fruit"):
            o.hide_render = True
    for k, x in enumerate((-0.8, -0.25, 0.3, 0.85)):
        pm.fruit_crate(f"Rot{k}", (20 + x, 0.45, 0.9), M, M["fruit_rot"], rnd, rotten=True, kind=k)
    for o in list(bpy.data.objects):
        if o.name.startswith("Rot") and o.name.endswith("Box"):
            o.hide_render = True
    shoot(out, "plants_stall_week", (20.3, -0.6, 1.65), (20.3, 1.2, 1.0), lens=24, res=(900, 1100))
    pm.house("House", (0, 30, 0), (7, 6, 6.5), M, rnd)
    pm.house("House2", (9, 30, 0), (5, 6, 5.5), M, rnd, roof="mono")
    for k in range(3):
        pm.pot(f"Pot{k}", (-1.0 + k * 0.8, 25.5, 0), M, rnd)
    shoot(out, "plants_house", (4, 14, 2.5), (4, 30, 3.5), lens=30, res=(1100, 900))
    # fallen branch with fungi (close-up of 11)
    t2 = pm.plane_tree("T2", (0, -40, 0), M, rnd)
    for o in [t2.root, *t2.root.children_recursive]:
        o.hide_render = o is not t2.branch and o.parent is not t2.branch
    t2.branch.parent = None
    t2.branch.location = (0, -40, 0.25)
    t2.branch.rotation_mode = "QUATERNION"
    d = t2.branch_dir
    t2.branch.rotation_quaternion = d.rotation_difference(Vector((d.x, d.y, 0)).normalized())
    sc[pm.STATE] = 3.0
    shoot(out, "plants_branch", (2.5, -44.0, 1.2), (1.5, -40.8, 0.3), lens=35, res=(1100, 900))


def preview_gnu(out):
    """viruses-disappeared: wildebeest (edited Quaternius cow) next to the original cow (heading +x, seen from the side)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
    import cow_quaternius as cq
    import wildebeest as wb
    import rigs
    scene = bpy.context.scene
    cow = cq.build("Cow", (4.5, 0, 0), heading=0.0, length=2.4)
    gnus = [wb.build("Gnu", (1.5, 0, 0), heading=0.0, length=2.5),
            wb.build("GnuGraze", (-1.5, 0, 0), heading=0.0, length=2.5),
            wb.build("GnuWalk", (-4.5, 0, 0), heading=0.0, length=2.5)]
    rigs.loop(cow, "Idle", 1, 200, rate=0.6)
    rigs.loop(gnus[0], "Idle", 1, 200, rate=0.6)
    wb.graze(gnus[1], 1, 200)
    rigs.loop(gnus[2], "Walk", 1, 200)
    scene.frame_set(20)
    shoot(out, "gnu_side", (0.0, -14.0, 1.0), (0.0, 0.0, 0.8), lens=35, res=(1400, 700))
    shoot(out, "gnu_front34", (9.0, -7.0, 1.4), (0.5, 0.0, 0.8), lens=35, res=(1200, 900))
    shoot(out, "gnu_eye", (-14.0, -12.0, 1.65), (0.0, 0.0, 0.7), lens=45, res=(1200, 900))


def preview_caterpillar(out):
    """viruses-disappeared: spongy moth caterpillar (3 phases of the walking wave) in a row, and an oak leaf
    next to it. Real scale: 52 mm caterpillar, 16.5 cm leaf; light background to read the silhouette."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
    import random
    import caterpillar as cp
    import oak as ok
    bpy.data.objects["Ground"].data.materials[0] = kit.flat("Paper", "#D8D2C4")
    mats = cp.materials()
    for k, y in enumerate((0.05, 0.0, -0.05)):
        o = cp.instance(f"Cat{k}", cp.make_mesh(f"CatV{k}", mats))
        o.location = (-0.03, y, 0.0)
        o.data.shape_keys.key_blocks[f"W{3 * k + 1}"].value = 1.0
    v, f = ok.leaf_geo(0.165, 0.11, random.Random(5), rows=34, cols=7, fold=0.1, curl=0.0)
    lo = kit.mesh_object("Leaf", v, f, [ok.leaf_mat()], (0.06, -0.02, 0.003))
    lo.rotation_euler = (0, 0, math.radians(80))
    bpy.data.objects["Sun"].rotation_euler = (math.radians(40), 0, math.radians(-30))
    shoot(out, "cat_top", (0.0, -0.02, 0.30), (0.0, 0.0, 0.0), lens=50, res=(1200, 900))
    shoot(out, "cat_side", (0.0, -0.30, 0.03), (0.0, 0.0, 0.006), lens=50, res=(1200, 600))
    shoot(out, "cat_eye", (0.14, -0.17, 0.10), (-0.01, 0.0, 0.0), lens=50, res=(1200, 900))


def preview_chicken(out):
    """Chicken from the stage builder (assets/procedural/chicken, tools/blender/chicken_model.py): standing (Idle),
    walking (Walk with the step matched to the planted foot) and pecking (Peck), from the side, front and at eye level,
    plus 8 consecutive frames (0.1 s) of the side walk with a ruler on the ground to check whether the foot slides."""
    import rigs
    rigs.SPECS["chicken"] = "procedural/chicken/Chicken.fbx"
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 200
    bpy.data.objects["Ground"].data.materials[0] = kit.flat("Dirt", "#8C7A5E")
    idle = rigs.spawn("chicken", "Idle", length=0.45, location=(-0.7, 0, 0), heading=-math.pi / 2 + 0.5)
    rigs.loop(idle, "Idle", 1, 200)
    peck = rigs.spawn("chicken", "Peck", length=0.45, location=(0.7, 0, 0), heading=-math.pi / 2 - 0.5)
    rigs.loop(peck, "Peck", 1, 200)
    walker = rigs.spawn("chicken", "Walker", length=0.45, location=(0, 0, 0), heading=0.0)
    rigs.loop(walker, "Walk", 1, 200)
    feet = [b.name for b in walker.t.arm.data.bones if not b.children and "foot" in b.name.lower()]
    v = rigs.planted_speed(walker, "Walk", feet) * walker.scale * rigs.ASSET_FPS      # m/s
    print(f"chicken: planted foot of the Walk = {v:.3f} m/s (len 0.45 m)")
    frames = list(range(1, 201))
    rigs.key_root(walker, frames, [(-1.2 + v * (f - 1) / 30, 0.0, 0.0) for f in frames], [0.0] * len(frames))
    for k in range(14):                                   # ruler on the ground: mark every 5 cm
        kit.box(f"Tick{k}", (-0.95 + 0.05 * k, 0.12, 0.001), (0.004, 0.02, 0.001), kit.flat("Tick", "#F5F0E6"))
    f_peck = 13 * 30 // 24 + 1                            # beak on the ground (frame 12 of the action)
    scene.frame_set(f_peck)
    shoot(out, "chicken_trio_eye", (0.0, -2.3, 0.45), (0.0, 0.0, 0.18), lens=40, res=(1400, 800))
    scene.frame_set(30)
    shoot(out, "chicken_idle_side", (-0.7 - 1.3, 0.0, 0.25), (-0.7, 0.0, 0.2), lens=50, res=(900, 900))
    shoot(out, "chicken_idle_front", (-0.7 - 0.6, -1.15, 0.3), (-0.7, 0.0, 0.2), lens=50, res=(900, 900))
    scene.frame_set(f_peck)
    shoot(out, "chicken_peck_side", (0.7 + 1.2, -0.3, 0.2), (0.7, 0.0, 0.15), lens=50, res=(900, 900))
    for o in rigs.all_objects(idle) + rigs.all_objects(peck):
        o.hide_render = True
    f0 = 60
    for k in range(8):
        f = f0 + 3 * k
        scene.frame_set(f)
        cx = -1.2 + v * (f0 - 1) / 30 + 0.08              # still camera: the planted foot must not move along the ruler
        shoot(out, f"chicken_walk_{k}", (cx, -1.3, 0.18), (cx, 0.0, 0.16), lens=50, res=(900, 600))
    scene.frame_set(70)
    shoot(out, "chicken_walk_front34", (walker.root.location.x + 0.9, -0.8, 0.3),
          (walker.root.location.x, 0.0, 0.18), lens=50, res=(900, 900))


def preview_ant(out):
    """Ant from the stage builder (tools/stage/ant.py): from the side, front, at eye level and a close-up of the head,
    with the 1.75 m 'man' as a ruler; Rise -> Tremble -> Sag in 6 frames; 8 consecutive frames (0.1 s) of the walk with a
    ruler on the ground (the planted foot must not move)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage"))
    import ant
    import rigs
    ant.ensure_template()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 400
    L = 1.7
    a = rigs.spawn("ant", "Ant", length=L, location=(0, 0, 0), heading=0.0)
    rigs.loop(a, "Idle", 1, 400)
    man = rigs.spawn("man", "Man", height=1.75, location=(0, 1.6, 0), heading=-math.pi / 2)
    rigs.loop(man, "Idle", 1, 400)
    scene.frame_set(20)
    shoot(out, "ant_side", (0.0, -4.6, 0.55), (0.0, 0.5, 0.55), lens=40, res=(900, 1100))
    shoot(out, "ant_front", (3.2, -0.9, 0.5), (0.0, 0.0, 0.3), lens=50, res=(900, 900))
    shoot(out, "ant_eye", (2.4, -3.4, 1.65), (0.0, 0.3, 0.35), lens=40, res=(900, 1100))
    shoot(out, "ant_head", (1.75, -0.75, 0.55), (0.75, 0.0, 0.3), lens=50, res=(900, 900))
    for o in rigs.all_objects(man):
        o.hide_render = True
    ant.play(a, "Rise", 30)
    ant.play(a, "Tremble", 160)
    ant.play(a, "Sag", 200)
    for k, f in enumerate((30, 90, 150, 172, 250, 320)):
        scene.frame_set(f)
        shoot(out, f"ant_seq_{k}_{f}", (0.3, -4.2, 0.6), (0.0, 0.0, 0.35), lens=40, res=(800, 700))
    for o in rigs.all_objects(a):
        o.hide_render = True
    w = rigs.spawn("ant", "Walker", length=L, location=(0, 0, 0), heading=0.0)
    rigs.loop(w, "Walk", 1, 400)
    feet = [b.name for b in w.t.arm.data.bones if not b.children and "foot" in b.name.lower()]
    v = rigs.planted_speed(w, "Walk", feet) * w.scale * rigs.ASSET_FPS
    print(f"ant: planted foot of the Walk = {v:.3f} m/s (len {L} m)")
    frames = list(range(1, 401))
    rigs.key_root(w, frames, [(-1.0 + v * (f - 1) / 30, 0.0, 0.0) for f in frames], [0.0] * len(frames))
    for k in range(30):
        kit.box(f"Tick{k}", (-0.5 + 0.1 * k, -0.9, 0.003), (0.01, 0.06, 0.003), kit.flat("Tick", "#F5F0E6"))
    f0 = 60
    for k in range(8):
        f = f0 + 3 * k
        scene.frame_set(f)
        cx = -1.0 + v * (f0 - 1) / 30
        shoot(out, f"ant_walk_{k}", (cx, -3.4, 0.7), (cx, 0.0, 0.25), lens=40, res=(900, 600))


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    model, out = args[0], Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    stage()
    {"plants": preview_plants, "cow": preview_cow, "farm": preview_farm, "cell": preview_cell, "dino": preview_dino, "globe": preview_globe, "cast": preview_cast, "people": preview_people, "town": preview_town, "street": preview_street, "valley": preview_valley, "vhouse": preview_vhouse, "moon": preview_moon, "gnu": preview_gnu, "caterpillar": preview_caterpillar, "chicken": preview_chicken, "ant": preview_ant}[model](out)


main()
