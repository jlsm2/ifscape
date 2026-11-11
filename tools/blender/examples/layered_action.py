"""Tested example (Blender 5.2.2, background): layered actions (slotted actions, since 4.4; in 5.x it is the
only format: Action.fcurves, Action.groups and Action.id_root no longer exist).

  blender -b --factory-startup -P tools/blender/examples/layered_action.py -- <output_folder>

Structure: Action -> slots (WHO it animates) + layers -> strips (KEYFRAME) -> channelbag per slot -> fcurves.
Shows: writing f-curves without keyframe_insert, reading f-curves from any action, one action with two slots,
NLA with a slot, and applying an action imported from glTF to another armature.
"""
import math
import os
import sys

import bpy
import bpy_extras.anim_utils as au

LINEAR = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value


def fcurves_of(action, slot=None):
    """Replaces the old action.fcurves (same as the project's globe._fcurves_of, with a slot filter)."""
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                if slot is None or bag.slot == slot:
                    out += list(bag.fcurves)
    return out


def write_curve(bag, data_path, index, frames, values, group=""):
    """Creates a whole f-curve at once: keyframe_points.add + foreach_set (fast, no operator)."""
    fc = bag.fcurves.new(data_path, index=index, group_name=group)   # .ensure() if it may already exist
    fc.keyframe_points.add(len(frames))
    fc.keyframe_points.foreach_set("co", [c for fv in zip(frames, values) for c in fv])
    fc.keyframe_points.foreach_set("interpolation", [LINEAR] * len(frames))
    fc.update()                                                     # recalculates handles and sorts
    return fc


def make_action(name, slot_name, id_type="OBJECT"):
    act = bpy.data.actions.new(name)
    slot = act.slots.new(id_type=id_type, name=slot_name)          # identifier becomes "OB" + name
    bag = au.action_ensure_channelbag_for_slot(act, slot)          # creates layer + strip + channelbag
    return act, slot, bag


def assign(obj, action, slot=None):
    """Assigns action and slot. Without an explicit slot Blender picks by name/last used slot; it may not find one."""
    ad = obj.animation_data or obj.animation_data_create()
    ad.action = action
    if slot is not None:
        ad.action_slot = slot
    elif ad.action_slot is None:
        ad.action_slot = au.action_get_first_suitable_slot(action, "OBJECT")
    return ad.action_slot


def demo_write_read():
    rig_data = bpy.data.armatures.new("Rig")
    rig = bpy.data.objects.new("Rig", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for i, name in enumerate(("Base", "Mid", "Top")):
        eb = rig_data.edit_bones.new(name)
        eb.head, eb.tail = (0, 0, i), (0, 0, i + 1)
        if i:
            eb.parent, eb.use_connect = rig_data.edit_bones[i - 1], True
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"                                    # must match the curves' data_path

    act, slot, bag = make_action("Wave", "Rig")
    frames = list(range(1, 31, 3))
    for k, bone in enumerate(("Base", "Mid", "Top")):
        vals = [math.radians(25) * math.sin(2 * math.pi * (f - 1) / 30 + 0.6 * k) for f in frames]
        write_curve(bag, f'pose.bones["{bone}"].rotation_euler', 1, frames, vals, group=bone)
    print("slot:", assign(rig, act).identifier)

    fc = bag.fcurves.find('pose.bones["Mid"].rotation_euler', index=1)
    print("read: keys", len(fc.keyframe_points), "| value at frame 8:", round(fc.evaluate(8), 3),
          "| total de f-curves:", len(fcurves_of(act)))

    # one action, two owners: each object uses its own slot
    cube = bpy.data.objects.new("Marker", None)
    bpy.context.scene.collection.objects.link(cube)
    cslot = act.slots.new(id_type="OBJECT", name="Marker")
    write_curve(act.layers[0].strips[0].channelbag(cslot, ensure=True), "location", 2, [1, 30], [0.0, 2.0])
    assign(cube, act, cslot)
    bpy.context.scene.frame_set(30)
    print("Marker z at 30:", round(cube.matrix_world.translation.z, 2), "| slots:", [s.identifier for s in act.slots])
    return rig, act


def demo_nla(rig, act):
    """NLA: the strip holds the action AND the slot. repeat = repeated cycle; blend_type ADD adds on top."""
    ad = rig.animation_data
    ad.action = None                                                # the active action would sit on top of the NLA
    track = ad.nla_tracks.new()
    track.name = "Walk"
    strip = track.strips.new("Wave", 1, act)
    strip.action_slot = act.slots["OBRig"]
    strip.repeat = 3.0
    strip.blend_in = strip.blend_out = 4
    print("NLA:", track.name, strip.frame_start, "->", strip.frame_end, "| slot", strip.action_slot.identifier)
    track2 = ad.nla_tracks.new()
    extra = track2.strips.new("Wave+", 20, act)
    extra.action_slot = act.slots["OBRig"]
    extra.blend_type, extra.influence = "ADD", 0.5
    for t in list(ad.nla_tracks):                                   # clear for the glTF test
        ad.nla_tracks.remove(t)
    ad.action = act


def demo_gltf(rig, out):
    """Exports and re-imports: the importer creates new actions (one per animation, with its own slot).
    WARNING 1: the exporter takes ALL the actions in the file that fit the object.
    WARNING 2: glTF animates rotation_quaternion; the target bone needs rotation_mode='QUATERNION'."""
    for o in bpy.context.scene.objects:
        o.select_set(o == rig)
    path = os.path.join(out, "rig.glb")
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_animations=True, export_format="GLB")
    before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [a for a in bpy.data.actions if a not in before]
    print("imported:", [(a.name, [s.identifier for s in a.slots]) for a in imported])

    other = rig.copy()
    other.data = rig.data.copy()
    other.name = "OtherRig"
    bpy.context.scene.collection.objects.link(other)
    other.animation_data_clear()
    act = imported[0]
    missing = {fc.data_path.split('"')[1] for fc in fcurves_of(act) if fc.data_path.startswith("pose.bones")} \
        - set(other.pose.bones.keys())
    assert not missing, f"bones without a match in the target: {missing} (rename the f-curves or the bones)"
    for pb in other.pose.bones:
        pb.rotation_mode = "QUATERNION"
    print("OtherRig uses", act.name, "slot", assign(other, act).identifier)
    bpy.context.scene.frame_set(8)
    q = other.pose.bones["Mid"].rotation_quaternion
    print("OtherRig Mid at frame 8 (quaternion):", [round(c, 3) for c in q], "| moves:", abs(q.w - 1) > 1e-3)


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig, act = demo_write_read()
    demo_nla(rig, act)
    demo_gltf(rig, out)


if __name__ == "__main__":
    main()
