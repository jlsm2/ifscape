"""Showcase of part A of plants-extinct (people and animals), isolated from the set.

Usage: blender -b -P tools/blender/lib/preview_a.py -- <cow|kid|hands|hand07|climber|all> <ABSOLUTE folder>
Render 540x960 (or 960x540), Eevee, daylight similar to the square's (sun 140°/55°).
"""

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import kit  # noqa: E402


def stage():
    kit.reset_scene(200, 30)
    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = kit.lin("#8FB4DA")
    bg.inputs["Strength"].default_value = 0.9
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.4
    sun.data.angle = math.radians(1.5)
    az, el = math.radians(140), math.radians(55)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = d.to_track_quat("Z", "Y")
    bpy.context.collection.objects.link(sun)
    kit.box("Ground", (0, 0, -0.05), (60, 60, 0.05), kit.flat("Paving", "#B8A58A"))


def camera():
    cam = bpy.context.scene.camera
    if cam is None:
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        bpy.context.collection.objects.link(cam)
        bpy.context.scene.camera = cam
        cam.data.sensor_fit = "VERTICAL"
        cam.data.sensor_height = 36.0
    return cam


def pose_cam(pos, yaw, pitch, lens=24.0):
    """Same convention as plants-extinct.pose_matrix (yaw + = right/west, pitch + = up)."""
    cam = camera()
    cam.data.lens = lens
    cam.rotation_mode = "XYZ"
    cam.location = pos
    cam.rotation_euler = Euler((math.radians(90 + pitch), 0, math.radians(-yaw)), "XYZ")
    return cam


def aim(pos, target, lens=50.0):
    cam = camera()
    cam.data.lens = lens
    cam.location = pos
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y")


def shot(out, name, res=(540, 960), frame=None):
    sc = bpy.context.scene
    if frame is not None:
        sc.frame_set(frame)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def p_cow(out):
    import cow_quaternius as cq
    c = cq.build("Cow", (0, 0, 0), heading=0.0, length=2.3)
    cq.graze(c, 1, 120)
    a = cq.build("CowIdle", (0, 3.0, 0), heading=0.0, length=2.3)
    import rigs
    rigs.loop(a, "Idle", 1, 120)
    for f in (10, 30):
        aim((0.3, -6.5, 1.3), (0.3, 1.5, 0.8), lens=40)
        shot(out, f"cow_side_f{f}", res=(960, 540), frame=f)
    aim((5.5, -3.0, 1.65), (0, 1.0, 0.7), lens=40)
    shot(out, "cow_34", res=(960, 540), frame=30)
    aim((-5.5, -2.5, 1.65), (0, 1.0, 0.7), lens=40)
    shot(out, "cow_back34", res=(960, 540), frame=30)


def p_kid(out):
    import rigs
    import kid
    adult = rigs.spawn("man", "Adult", height=1.74, location=(-0.8, 0, 0), heading=-math.pi / 2)
    rigs.paint(adult, {"Shirt": "#B8583A", "Pants": "#2A3446", "Skin": "#C8916A", "Hair": "#2A1E16",
                       "HairBase": "#2A1E16", "Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"})
    rigs.loop(adult, "Walk", 1, 120)
    k0 = rigs.spawn("man", "KidRaw", height=1.2, location=(0.2, 0, 0), heading=-math.pi / 2)
    rigs.loop(k0, "Run", 1, 120)
    k1 = rigs.spawn("man", "KidFix", height=1.2, location=(1.1, 0, 0), heading=-math.pi / 2)
    rigs.paint(k1, {"Shirt": "#9A3A34", "Pants": "#3A4252", "Skin": "#C8916A", "Hair": "#8A6A4A",
                    "HairBase": "#8A6A4A", "Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"})
    kid.childlike(k1)
    rigs.loop(k1, "Run", 1, 120)
    for f in (5, 12):
        aim((0.2, -5.0, 1.0), (0.2, 0, 0.8), lens=40)
        shot(out, f"kid_front_f{f}", res=(960, 540), frame=f)
    aim((5.0, -0.3, 1.0), (0.2, 0, 0.8), lens=40)
    shot(out, "kid_side", res=(960, 540), frame=8)
    aim((1.1, -16.0, 1.65), (1.1, 0, 0.7), lens=24)
    shot(out, "kid_far_eye", frame=8)


def stall_scene():
    import plants_models as pm
    import plants_set as ps
    bpy.context.scene[pm.STATE] = 1.0
    M = ps.make_mats()
    pm.stall("Stall", (0.0, 0.85, 0.0), M)
    return M


def p_hands(out):
    import plants_build_a as pba
    M = stall_scene()
    pba.hands_04(M)
    pose_cam((0.0, 0.15, 1.6), 0, -42)
    shot(out, "hands04_pov")
    pose_cam((-0.05, 0.1, 1.6), -20, -30)
    shot(out, "hands04_charcoal")
    aim((1.4, 0.2, 1.3), (0.0, 0.8, 0.92), lens=35)
    shot(out, "hands04_side", res=(960, 540))


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    model, out = args[0], Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    stage()
    {"cow": p_cow, "kid": p_kid, "hands": p_hands}[model](out)


main()
