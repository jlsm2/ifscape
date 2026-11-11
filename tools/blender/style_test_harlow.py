"""STYLE test of the season "The Harlow Outbreak": the same scene in 3D (Eevee) and in flat 2.5D.

Not production. Main street of a small town at dusk, unbranded pharmacy, Sam (pharmacist, lab coat) on the
sidewalk looking to the right, a hunched gray-green infected in the background on the right.
Assets: Kenney City Kit Commercial/Suburban and Car Kit (CC0), Quaternius Man and Animated Human (CC0, Poly Pizza).

blender -b -P tools/blender/style_test_harlow.py -- <ABSOLUTE folder> <3d|25d|both> [percent]
"""

import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools" / "stage"))
import kit  # noqa: E402
import rigs  # noqa: E402
import models  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0]) if argv else ROOT / "build" / "zombie-outbreak-1" / "style-test"
MODE = argv[1] if len(argv) > 1 else "both"
PCT = int(argv[2]) if len(argv) > 2 else 100
OUT.mkdir(parents=True, exist_ok=True)

scene = kit.reset_scene(30, 30)
col = scene.collection
scene.render.resolution_percentage = PCT


def box(name, x0, x1, y0, y1, z0, z1, color, rough=0.9):
    return kit.box(name, ((x0 + x1) / 2, (y0 + y1) / 2, z0), (x1 - x0, y1 - y0, z1 - z0), kit.flat(name, color, rough))


# ---------- ground: street along x, north sidewalk (pharmacy) at y 0..3.5, south sidewalk at y -10.5..-8 ----------
box("Asphalt", -80, 140, -8, 0, -0.2, 0.0, "#3A3A40")
box("WalkN", -80, 140, 0, 3.5, -0.2, 0.15, "#9C958C")
box("WalkS", -80, 140, -10.5, -8, -0.2, 0.15, "#9C958C")
box("CurbN", -80, 140, -0.12, 0.0, -0.2, 0.16, "#B8B0A4")
box("Ground", -200, 300, -200, 300, -0.4, -0.21, "#5C5A4E")
for i in range(-30, 70):                                   # faixa central tracejada amarela
    box(f"Dash{i}", i * 3.0, i * 3.0 + 1.6, -4.08, -3.92, 0.0, 0.012, "#D9B23A")
for i in range(-40, 70):                                   # sidewalk joints
    box(f"Joint{i}", i * 1.5, i * 1.5 + 0.03, 0.05, 3.45, 0.15, 0.152, "#857F76")


# ---------- buildings ----------
def place(ident, x, y, h, rot_deg, name=None):
    o = models.static_instance(ident, name or f"{ident}_{x:.0f}_{y:.0f}", col, height=h)
    o.location = (x, y, 0.15 if abs(y) < 40 else 0.0)
    o.rotation_euler = (0, 0, math.radians(rot_deg))
    return o


def dims(ident, h):
    tpl = models.static_template(ident)
    xs = [v.co.x for v in tpl.mesh.vertices]
    ys = [v.co.y for v in tpl.mesh.vertices]
    k = h / tpl.height
    return (max(xs) - min(xs)) * k, (max(ys) - min(ys)) * k


def width_of(ident, h):
    return dims(ident, h)[0]


FRONT_ROT = 180          # Kenney: facade toward -y after this turn (checked in the still)

# north row (pharmacy side): pharmacy at x = 0
north = ["building-d", "building-h", "PHARMACY", "building-b", "building-g", "building-c", "building-f",
         "building-a", "building-e", "building-h", "building-d", "building-b", "building-g", "building-c"]
x = -24.0
pharmacy_x = None
for i, ident in enumerate(north):
    pid = "building-a" if ident == "PHARMACY" else ident
    h = 7.6 if ident == "PHARMACY" else (6.5 + (i * 37 % 5) * 0.6)
    w = width_of(pid, h)
    o = place(pid, x + w / 2, 3.5 + dims(pid, h)[1] / 2, h, FRONT_ROT, "Pharmacy" if ident == "PHARMACY" else None)
    if ident == "PHARMACY":
        pharmacy_x = x + w / 2
        pw = w
    x += w + (2.4 if ident == "PHARMACY" else 0.2)        # alley to the right of the pharmacy
# south row (across the street, seen in 3D)
x = -20.0
for i, ident in enumerate(["building-e", "building-c", "building-type-a", "building-f", "building-b",
                           "building-type-c", "building-d", "building-g", "building-a", "building-h"]):
    h = 6.8 + (i * 29 % 4) * 0.7
    w = width_of(ident, h)
    place(ident, x + w / 2, -10.5 - dims(ident, h)[1] / 2, h, 0)
    x += w + 0.4
# back row (shows above the front one): taller, farther
x = -30.0
for i, ident in enumerate(["low-detail-building-a", "low-detail-building-c", "low-detail-building-e",
                           "low-detail-building-g", "low-detail-building-i", "low-detail-building-b",
                           "low-detail-building-d", "low-detail-building-wide-a", "low-detail-building-f"]):
    h = 10.5 + (i * 13 % 4) * 1.2
    w = width_of(ident, h)
    place(ident, x + w / 2, 26.0, h, FRONT_ROT)
    x += w + 1.0

# real facade of the pharmacy (ray): the sign and the awning touch it
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()


def wall_y(x, z):
    hit, loc, *_ = scene.ray_cast(dg, Vector((x, -5.0, z)), Vector((0, 1, 0)))
    return loc.y if hit else 3.5


fy_low, fy_up = wall_y(pharmacy_x, 1.2), wall_y(pharmacy_x + 1.0, 4.6)
print("FACADE", fy_low, fy_up, "pw", pw)
# green and white striped awning (tilted boxes) over the display window
aw_w, aw_d = pw * 0.86, 1.3
stripes = 12
for i in range(stripes):
    x0 = pharmacy_x - aw_w / 2 + i * aw_w / stripes
    o = kit.box(f"Awning{i}", (x0 + aw_w / stripes / 2, fy_low - aw_d / 2, 3.05), (aw_w / stripes, aw_d, 0.06),
                kit.flat(f"AwningM{i % 2}", "#2E7D55" if i % 2 == 0 else "#ECE8DE"))
    o.dimensions = o.dimensions
    o.scale.z = 0.3 / 0.06
    o.location.z = 2.75
sign_y = min(fy_up, fy_low) - 0.06
box("SignBoard", pharmacy_x - 0.6, pharmacy_x + 2.4, sign_y - 0.08, sign_y + 0.05, 3.55, 4.3, "#F2EEE4")
cross_m = kit.flat("Cross", "#2F9E5B", emission="#2F9E5B", strength=1.5)
for sx, sz in ((0.16, 0.5), (0.5, 0.16)):
    kit.box("Cross", (pharmacy_x - 0.25, sign_y - 0.1, 3.925 - sz / 2), (sx, 0.04, sz), cross_m)
txt = bpy.data.curves.new("SignText", "FONT")
txt.body = "PHARMACY"
txt.size = 0.36
txt.align_x, txt.align_y = "CENTER", "CENTER"
txt.extrude = 0.01
t_obj = bpy.data.objects.new("SignText", txt)
col.objects.link(t_obj)
t_obj.location = (pharmacy_x + 1.1, sign_y - 0.1, 3.925)
t_obj.rotation_euler = (math.radians(90), 0, 0)
t_obj.data.materials.append(kit.flat("SignInk", "#1F5E3A"))

# blade sign (perpendicular to the facade): this is what reads in 3D, from the side
bx = pharmacy_x + pw / 2 - 0.3
box("BladeArm", bx - 0.03, bx + 0.03, fy_up - 1.15, fy_up, 4.55, 4.6, "#2A2A2E")
box("Blade", bx - 0.04, bx + 0.04, fy_up - 1.1, fy_up - 0.15, 3.55, 4.5, "#F2EEE4")
for sx_, sz_ in ((0.12, 0.42), (0.42, 0.12)):
    kit.box("BladeCross", (bx - 0.06, fy_up - 0.62, 4.2 - sz_ / 2), (0.02, sx_, sz_), cross_m)
bt = bpy.data.curves.new("BladeText", "FONT")
bt.body = "PHARMACY"
bt.size = 0.15
bt.align_x, bt.align_y = "CENTER", "CENTER"
bt.extrude = 0.005
bo = bpy.data.objects.new("BladeText", bt)
col.objects.link(bo)
bo.location = (bx - 0.06, fy_up - 0.62, 3.8)
bo.rotation_euler = (math.radians(90), 0, math.radians(-90))
bo.data.materials.append(kit.flat("SignInk2", "#1F5E3A"))

# pole, car, hydrant
pole = place("light-square", pharmacy_x + 6.6, 0.45, 5.2, 0, "StreetLight")
pole.rotation_euler = (0, 0, math.radians(-90))
place("sedan", pharmacy_x + 19.0, -1.35, 1.45, 0, "Car")
place("suv", pharmacy_x + 16.0, -6.6, 1.7, 180, "Car2")
place("taxi", pharmacy_x + 30.0, -1.4, 1.5, 0, "Car3")
box("Hydrant", pharmacy_x + 4.2, pharmacy_x + 4.5, 0.6, 0.9, 0.15, 0.85, "#B8412E")


# ---------- people ----------
sam = rigs.spawn("man", "Sam", height=1.78, location=(pharmacy_x + 0.4, 1.4, 0.15), heading=math.radians(-48))
print("SAM MATS", [s.material.name for o in sam.meshes for s in o.material_slots if s.material])
rigs.paint(sam, {"Shirt": "#F4F2EC", "Pants": "#3B4250", "Shoes": "#2A2A2E", "Skin": "#D9A27E", "Hair": "#3A2A20",
                 "Hair.001": "#3A2A20"})
rigs.loop(sam, "Idle", 1, 60)

INF3D = Vector((pharmacy_x + 10.2, 0.4, 0.15))
INF25 = Vector((pharmacy_x + pw / 2 + 0.7, 6.0, 0.15))      # in 2.5D (ortho, narrow frame): at the mouth of the alley
inf = rigs.spawn("human", "Infected", height=1.72, location=INF3D, heading=math.radians(190))
print("INF MATS", [s.material.name for o in inf.meshes for s in o.material_slots if s.material])
print("INF BONES", [b.name for b in inf.arm.data.bones])
print("INF ACTS", list(inf.t.actions))
for o in inf.meshes:
    for slot in o.material_slots:
        slot.link = "OBJECT"
        nm = slot.material.name.lower() if slot.material else ""
        slot.material = rigs.flat_mat("#5E6B57")
walk = "Walk" if "Walk" in inf.t.actions else next(iter(inf.t.actions))
rigs.loop(inf, walk, 1, 60, rate=0.5)
spine = [b for b in inf.arm.data.bones if any(k in b.name.lower() for k in ("spine", "chest", "abdomen", "torso"))]
neck = [b for b in inf.arm.data.bones if any(k in b.name.lower() for k in ("neck", "head"))]
bends = {b.name: rigs.bone_delta(inf, b.name, (1, 0, 0), 14) for b in spine[:3]}
bends.update({b.name: rigs.bone_delta(inf, b.name, (1, 0, 0), 18) for b in neck[:1]})
if bends:
    rigs.pose_layer(inf, list(range(1, 31)), lambda f: bends)


# ---------- dusk light ----------
world = bpy.data.worlds.new("Dusk")
scene.world = world
world.use_nodes = True
nt = world.node_tree
N, L = nt.nodes, nt.links
N.clear()
tc, sep, ramp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeSeparateXYZ"), N.new("ShaderNodeValToRGB")
bg, outw = N.new("ShaderNodeBackground"), N.new("ShaderNodeOutputWorld")
L.new(tc.outputs["Generated"], sep.inputs[0])
L.new(sep.outputs["Z"], ramp.inputs[0])
els = ramp.color_ramp.elements
els[0].position, els[0].color = 0.0, kit.lin("#F7A64C")
els[1].position, els[1].color = 0.62, kit.lin("#3A2B5C")
mid = els.new(0.13)
mid.color = kit.lin("#EE8350")
mid2 = els.new(0.32)
mid2.color = kit.lin("#B35C78")
L.new(ramp.outputs[0], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
L.new(bg.outputs[0], outw.inputs[0])

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 3.2
sun_d.color = kit.lin("#FFB070")[:3]
sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("Sun", sun_d)
col.objects.link(sun)
sun.rotation_euler = (math.radians(84), 0, math.radians(81))      # low sun at the end of the street (+x), raking light on the facades

# light lit windows: a warm area light inside the pharmacy display window
shop = bpy.data.lights.new("ShopGlow", "AREA")
shop.energy, shop.size, shop.color = 120, 3.0, kit.lin("#FFD9A0")[:3]
so = bpy.data.objects.new("ShopGlow", shop)
col.objects.link(so)
so.location = (pharmacy_x, 3.0, 1.6)
so.rotation_euler = (math.radians(90), 0, 0)


# ---------- cameras ----------
SAM = Vector((pharmacy_x + 0.4, 1.4, 0.15))
cam3 = bpy.data.objects.new("Cam3D", bpy.data.cameras.new("Cam3D"))
col.objects.link(cam3)
cam3.data.lens = 32
cam3.data.shift_y = 0.08
cam3.data.clip_end = 600
cam3.location = SAM + Vector((-4.5, -1.9, 1.5))
cam3.rotation_euler = (math.radians(90), 0, math.radians(-90 + 13))     # looks down the street (+x), 9 deg into the sidewalk

cam2 = bpy.data.objects.new("Cam25D", bpy.data.cameras.new("Cam25D"))
col.objects.link(cam2)
cam2.data.type = "ORTHO"
cam2.data.ortho_scale = 8.8
cam2.data.clip_end = 400
cam2.location = (SAM.x + 1.0, -7.5, 8.8 / 2 - 0.45)
cam2.rotation_euler = (math.radians(90), 0, 0)


def render(name, cam):
    scene.camera = cam
    scene.frame_set(12)
    scene.render.filepath = str(OUT / name)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDER {name}: {time.time() - t0:.1f} s")


def to_flat():
    """2.5D: every material becomes Emission of its base color (texture or value), with a slight dusk tint;
    black outline by Freestyle; world unchanged (sky in bands)."""
    tint = kit.lin("#FFD7B8")
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        nt = m.node_tree
        p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if p is None or out is None:
            continue
        em = nt.nodes.new("ShaderNodeEmission")
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        src = p.inputs["Base Color"]
        if src.links:
            nt.links.new(src.links[0].from_socket, mix.inputs[6])
        else:
            mix.inputs[6].default_value = src.default_value
        mix.inputs[7].default_value = tint
        # flat depth haze (paper layers): far tends toward the purple of the sky
        cd = nt.nodes.new("ShaderNodeCameraData")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 12.0, 45.0
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.0, 0.55
        nt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
        fog = nt.nodes.new("ShaderNodeMix")
        fog.data_type = "RGBA"
        nt.links.new(mr.outputs["Result"], fog.inputs[0])
        nt.links.new(mix.outputs[2], fog.inputs[6])
        fog.inputs[7].default_value = kit.lin("#B9708A")
        nt.links.new(fog.outputs[2], em.inputs["Color"])
        emis_on = p.inputs["Emission Strength"].default_value > 0
        em.inputs["Strength"].default_value = 1.4 if emis_on else 1.0
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    for lt in bpy.data.lights:
        lt.energy = 0.0
    # sky in 4 flat bands
    ramp.color_ramp.interpolation = "CONSTANT"
    try:
        scene.render.use_freestyle = True
        scene.render.line_thickness_mode = "ABSOLUTE"
        scene.render.line_thickness = 1.6 * PCT / 100 + 0.4
        vl = scene.view_layers[0]
        vl.use_freestyle = True
        ls = vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new("L")
        ls.select_by_visibility = True
        ls.select_silhouette = ls.select_border = ls.select_crease = True
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.new("Ink")
        ls.linestyle.color = (0.04, 0.03, 0.05)
        ls.linestyle.thickness = 1.6
        vl.freestyle_settings.crease_angle = math.radians(120)
    except Exception as exc:                                  # noqa: BLE001
        print("FREESTYLE unavailable:", exc)
    scene.view_settings.view_transform = "Standard"


if MODE in ("3d", "both"):
    render("3d.png", cam3)
if MODE in ("25d", "both"):
    inf.root.location = INF25
    sam.root.rotation_euler.z = math.radians(-8) + math.pi / 2       # profile to the right in the front view
    inf.root.rotation_euler.z = math.radians(-140) + math.pi / 2
    to_flat()
    render("25d.png", cam2)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "style_test.blend"))
