"""Dense LINEAR keys via the channelbag (Blender 5: layered actions; no action.fcurves).

SOURCE: procedural (Ifscape, 2026-10-24). Same recipe as _write_curve in plants-extinct.py, made reusable.
"""

import bpy
import bpy_extras.anim_utils as au

LINEAR = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
CONSTANT = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["CONSTANT"].value


def bag(id_data):
    ad = id_data.animation_data or id_data.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{id_data.name}Action")
    if ad.action_slot is None:
        act = ad.action
        ad.action_slot = act.slots[0] if act.slots else act.slots.new(id_type=id_data.id_type, name=id_data.name)
    return au.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)


def write(id_data, path, index, frames, values, interp=LINEAR):
    """A whole curve at once (replaces any existing one)."""
    b = bag(id_data)
    fc = b.fcurves.find(path, index=index) or b.fcurves.new(path, index=index)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    fc.keyframe_points.foreach_set("co", [c for fv in zip(frames, values) for c in fv])
    fc.keyframe_points.foreach_set("interpolation", [interp] * len(frames))
    fc.update()
    return fc


def write_vec(id_data, path, frames, vectors, size=3):
    for i in range(size):
        write(id_data, path, i, frames, [v[i] for v in vectors])


def visible_ranges(objs, ranges, total):
    """Shows (hide_render False) only inside the intervals [(a, b)] inclusive; CONSTANT."""
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for o in objs:
        write(o, "hide_render", 0, marks, [0.0 if any(a <= f <= b for a, b in ranges) else 1.0 for f in marks],
              CONSTANT)
        o.hide_render = not any(a <= 1 <= b for a, b in ranges)


def ease(u, kind="io"):
    u = max(0.0, min(1.0, u))
    if kind == "io":
        return u * u * (3 - 2 * u)
    if kind == "out":
        return 1 - (1 - u) ** 3
    if kind == "in":
        return u ** 3
    return u
