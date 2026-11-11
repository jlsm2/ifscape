"""Minimal scene for the examples: side camera, sun, ground and dark background, small Eevee render.

In Blender 5.x the world and materials are born with nodes already: world.color does NOT paint the render
background; you have to change the Background node.
"""
import math

import bpy
from mathutils import Vector


def side_view(scene, center=(0, 0, 1), dist=6, res=(270, 480), samples=8):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    c = Vector(center)
    cam.location = c + Vector((dist, 0, 0.3))
    cam.rotation_euler = (Vector(center) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(60))
    sun.data.energy = 3.0

    ground = bpy.data.meshes.new("Ground")
    ground.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 40, 0), (-20, 40, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new("Ground")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.16, 0.22, 1)
    ground.materials.append(mat)
    scene.collection.objects.link(bpy.data.objects.new("Ground", ground))

    world = bpy.data.worlds.new("World")
    scene.world = world
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.01, 0.012, 0.02, 1)

    scene.render.engine = "BLENDER_EEVEE"           # in 5.x it is the only Eevee id ("BLENDER_EEVEE_NEXT" is gone)
    scene.eevee.taa_render_samples = samples
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.image_settings.file_format = "PNG"
    return cam
