"""Tested example (Blender 5.2.2, background): 3-bone armature + mesh with automatic weights + 30-frame
action + render.

  blender -b --factory-startup -P tools/blender/examples/rig_three_bones.py -- <output_folder> [--render]

Measured result: parent_set(type='ARMATURE_AUTO') returns FINISHED WITHOUT a window and without temp_override
(just select the mesh and the armature and leave the armature active); 0 of 104 vertices without weight.
If automatic weighting fails ("Bone Heat Weighting: failed to find solution for one or more bones"),
use type='ARMATURE_ENVELOPE' (also tested) or vertex groups by hand (see walk_biped_ik.build_body).
"""
import math
import os
import sys

import bpy
import bpy_extras.anim_utils as au


def column(name, n=8, rings=13, height=3.0, radius=0.3):
    """Column with rings: the mesh needs loops along its length in order to bend."""
    verts = [(radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n), height * k / (rings - 1))
             for k in range(rings) for i in range(n)]
    faces = [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i)
             for k in range(rings - 1) for i in range(n)]
    faces += [tuple(range(n - 1, -1, -1)), tuple(range((rings - 1) * n, rings * n))]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    mat = bpy.data.materials.new(name)
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.4, 0.05, 1)
    me.materials.append(mat)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def chain(name, count=3, length=1.0):
    """Armature with stacked, connected bones. Edit bones only exist in EDIT mode."""
    arm = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    prev = None
    for i in range(count):
        eb = arm.edit_bones.new(f"B{i}")
        eb.head, eb.tail, eb.roll = (0, 0, i * length), (0, 0, (i + 1) * length), 0.0
        if prev:
            eb.parent, eb.use_connect = prev, True
        prev = eb
    bpy.ops.object.mode_set(mode="OBJECT")          # leaving EDIT writes the bones to armature.bones
    return rig


def skin_auto(mesh, rig):
    """Automatic weights (bone heat). Selection: mesh + armature, armature ACTIVE."""
    for o in bpy.context.scene.objects:
        o.select_set(False)
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    result = bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    empty_verts = sum(1 for v in mesh.data.vertices if not v.groups)
    print("ARMATURE_AUTO:", result, "| vertices without weight:", empty_verts)
    return empty_verts == 0


def wave(rig, frames=30):
    """Action of 'frames' frames via keyframe_insert: Blender creates the action, the slot and the channelbag by itself."""
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    for f in range(1, frames + 1, 2):
        a = math.radians(35) * math.sin(2 * math.pi * (f - 1) / frames)
        for k, pb in enumerate(rig.pose.bones):
            pb.rotation_euler = (a * (1 + 0.3 * k), 0, 0)
            pb.keyframe_insert("rotation_euler", frame=f)
    bag = au.animdata_get_channelbag_for_assigned_slot(rig.animation_data)   # in place of action.fcurves
    for fc in bag.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    act = rig.animation_data.action
    print("action:", act.name, "| slot:", rig.animation_data.action_slot.identifier, "| f-curves:", len(bag.fcurves))


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = args[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end, sc.render.fps = 1, 30, 30
    mesh, rig = column("Col"), chain("Rig")
    skin_auto(mesh, rig)
    wave(rig)
    sc.frame_set(8)
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())       # DEFORMED mesh: only via the depsgraph
    top = max(ev.data.vertices, key=lambda v: v.co.z)
    print("deformed top at frame 8:", tuple(round(c, 2) for c in top.co))
    if "--render" in args:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import render_setup
        render_setup.side_view(sc, center=(0, 0, 1.5), dist=7)
        sc.render.filepath = os.path.join(out, "rig_")
        bpy.ops.render.render(animation=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "rig.blend"))


if __name__ == "__main__":
    main()
