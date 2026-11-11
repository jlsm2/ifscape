"""Common pieces of the effects examples (fx_*.py): night test scene, faceted icosphere and color management.

Tested on Blender 5.2.2 (Eevee) on 2026-10-21. Research: docs/blender/effects-and-lighting.md.
The examples are short on purpose: copy the function you need into the set's script.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bpy  # noqa: E402
from mathutils import Vector, noise  # noqa: E402

import kit  # noqa: E402
from kit import lin  # noqa: E402

NAVY_SKY = "#0E1626"       # navy-blue night sky (close to Vacuum #0B0F17, slightly lighter)
NAVY_FILL = "#3A5285"      # ambient light (the same tone as humans_set)


def view(scene, transform="AgX", look="None", exposure=0.0):
    """Color management. Valid names in 5.2: 'AgX', 'Standard', 'Khronos PBR Neutral', 'ACES 2.0', 'Filmic'
    (obsolete); AgX looks: 'AgX - Punchy', 'AgX - Base Contrast', 'AgX - Medium High Contrast'..."""
    scene.view_settings.view_transform = transform
    scene.view_settings.look = look
    scene.view_settings.exposure = exposure


def ico(subdiv=2, radius=1.0):
    """Icosphere (20 * 4**subdiv faces) in plain lists: (verts, faces)."""
    t = (1 + 5 ** 0.5) / 2
    verts = [Vector(v).normalized() for v in ((-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                                              (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1))]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
             (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache, out = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                verts.append(((verts[a] + verts[b]) / 2).normalized())
                cache[k] = len(verts) - 1
            return cache[k]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = out
    return [tuple(v * radius) for v in verts], faces


def lumpy(verts, seed=0, amount=0.25, freq=1.6, squash=1.0):
    """Deforms the icosphere with noise (irregular silhouette, not a smooth ball). squash < 1 flattens the bottom."""
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    out = []
    for v in verts:
        p = Vector(v)
        n = noise.noise(p * freq + off)                      # -1..1, continuous: neighbors move together
        p = p * (1 + amount * n)
        if p.z < 0:
            p.z *= squash
        out.append(tuple(p))
    return out


def flat_obj(name, verts, faces, mat, location=(0, 0, 0)):
    """Flat-shaded mesh with no shadow of its own by default, for effects."""
    obj = kit.mesh_object(name, verts, faces, [mat], location)
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def emitter(name, color, strength, base="#000000"):
    """Effect material: dark base + emission. Black base = the color comes only from the emission (it does not add to the diffuse)."""
    mat = kit.flat(name, base, rough=1.0, emission=color, strength=strength)
    kit.principled(mat).inputs["Specular IOR Level"].default_value = 0.0
    return mat


def night_scene(res=(540, 960), samples=32, cam_loc=(0, -9, 1.6), target=(0, 0, 1.4), lens=30):
    """Night test scene: navy-blue ground, flat sky, blue ambient, weak moon sun, vertical camera."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.eevee.taa_render_samples = samples
    world = bpy.data.worlds.new("Night")
    scene.world = world
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs["Color"].default_value = lin(NAVY_SKY)
    bg.inputs["Color"].default_value = lin(NAVY_FILL)
    bg.inputs["Strength"].default_value = 0.6
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs["Surface"])

    moon = bpy.data.lights.new("Moon", "SUN")
    moon.energy, moon.color, moon.angle = 0.8, (0.65, 0.75, 1.0), math.radians(3)
    mo = bpy.data.objects.new("Moon", moon)
    mo.rotation_euler = (math.radians(60), 0, math.radians(-30))
    scene.collection.objects.link(mo)

    ground = kit.flat("Ground", "#24324A", rough=1.0)
    kit.principled(ground).inputs["Specular IOR Level"].default_value = 0.0
    kit.mesh_object("Ground", [(-60, -20, 0), (60, -20, 0), (60, 100, 0), (-60, 100, 0)], [(0, 1, 2, 3)], [ground])

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = cam_loc
    cam.rotation_euler = (Vector(target) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def props(scene, rnd, n=10, spread=8.0, y0=4.0):
    """A few low-poly boxes and trees in the background, just to see the effect's light hitting the set."""
    wall = kit.flat("PropWall", "#3B4A63", rough=1.0)
    leaf = kit.flat("PropLeaf", "#2E5A45", rough=1.0)
    for k in range(n):
        x, y = rnd.uniform(-spread, spread), y0 + rnd.uniform(0, 8)
        if k % 2:
            kit.box(f"Box{k}", (x, y, 0), (rnd.uniform(1, 2.5), rnd.uniform(1, 2.5), rnd.uniform(1.5, 4)), wall)
        else:
            kit.prism(f"Tree{k}", (x, y, 0), 6, 0.9, 0.0, rnd.uniform(2.5, 4.0), leaf)


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def screen_xy(scene, point):
    """Pixel (x, y from the top) of a world point in the rendered image."""
    from bpy_extras.object_utils import world_to_camera_view
    bpy.context.view_layer.update()                     # without this the camera matrix is still the identity
    co = world_to_camera_view(scene, scene.camera, Vector(point))
    w, h = scene.render.resolution_x, scene.render.resolution_y
    return int(co.x * w), int((1 - co.y) * h)


# ---------- effect animation: dense, LINEAR keys (no Bezier overshoot) ----------

def ease_out(u, power=3):
    """Fast at the start and slow at the end: the look of an explosion (energy spent early)."""
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** power


def ease_in_out(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def fcurves(idblock):
    """F-curves of an owner (object, light, material node_tree). Blender 5 stores the action in layers."""
    ad = getattr(idblock, "animation_data", None)
    act = ad.action if ad else None
    if act is None:
        return []
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


def set_interp(idblock, mode="LINEAR"):
    for fc in fcurves(idblock):
        for kp in fc.keyframe_points:
            kp.interpolation = mode


def curve_keys(owner, attr, frames, fn):
    """One key per frame with the value fn(frame). Combine with set_interp(..., 'LINEAR')."""
    for f in frames:
        setattr(owner, attr, fn(f))
        owner.keyframe_insert(attr, frame=f)
