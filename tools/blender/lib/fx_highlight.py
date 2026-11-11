"""Amber ruler mark ("Instrument" identity): emissive band that sweeps a tabletop area with a soft front
edge, and a thin outline via inverted hull (Solidify with flipped normals + backface culling) on objects.
No on/off switch: the band grows and retracts by scale; the outline thickens and thins.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct; direction.md 06 and MEDIUM risk "soft edge, 1.2 s
curve, no on/off switch"). Amber emission <= 1.0 (in Standard anything above that turns the amber yellow).

band(name, x0, x1, y0, y1, z, color, strength) -> object (origin at edge x0; grows along +x via x scale)
grow_band(obj, keys) -> keys = [(frame, fraction 0..1)], ease-in-out between keys on every frame
outline(obj, mat_outline, keys) -> inverted hull with animated thickness [(frame, meters)]
"""

from lib import anim_curves as ac
import kit
import plants_models as pm
from kit import lin


def band_mat(name, color="#F5A524", strength=0.9, feather=0.1):
    """Amber emission with the front edge (high local x) fading to the table color: soft 'feather' edge."""
    mat, n, L, p = pm.node_mat(name, 0.9, 0.0)
    p.inputs["Base Color"].default_value = lin(color)
    p.inputs["Emission Color"].default_value = lin(color)
    coord = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Generated"], sep.inputs[0])
    edge = n.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value, edge.inputs["From Max"].default_value = 1.0 - feather, 1.0
    edge.inputs["To Min"].default_value, edge.inputs["To Max"].default_value = strength, 0.15
    L.new(sep.outputs["X"], edge.inputs["Value"])
    L.new(edge.outputs["Result"], p.inputs["Emission Strength"])
    return mat


def band(name, x0, x1, y0, y1, z, mat, thick=0.004):
    v, f = kit._box_geo(x1 - x0, y1 - y0, thick, 0.0, 0.0, 0.0)
    o = pm.obj_from(name, (v, f), [mat], location=(x0, y0, z))
    o.visible_shadow = False
    return o


def grow_band(obj, keys, total_first=1):
    frames = list(range(keys[0][0], keys[-1][0] + 1))
    vals = []
    for f in frames:
        i = next(i for i, k in enumerate(keys) if k[0] >= f)
        if keys[i][0] == f or i == 0:
            vals.append(keys[i][1])
        else:
            (fa, a), (fb, b) = keys[i - 1], keys[i]
            vals.append(a + (b - a) * ac.ease((f - fa) / (fb - fa), "io"))
    vals = [max(1e-3, v) for v in vals]
    ac.write(obj, "scale", 0, frames, vals)


def outline_mat(name, color="#F5A524", strength=0.95):
    mat = pm.fixed_mat(name, color, rough=0.9, emission=color, strength=strength)
    mat.use_backface_culling = True
    return mat


def outline(obj, mat, keys):
    """Inverted hull: the mesh gets the outline material in an extra slot; Solidify with material_offset."""
    obj.data.materials.append(mat)
    off = len(obj.data.materials) - 1
    mod = obj.modifiers.new("Outline", "SOLIDIFY")
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.offset = 1.0
    mod.material_offset = off
    mod.thickness = keys[0][1]
    frames = list(range(keys[0][0], keys[-1][0] + 1))
    vals = []
    for f in frames:
        i = next(i for i, k in enumerate(keys) if k[0] >= f)
        if keys[i][0] == f or i == 0:
            vals.append(keys[i][1])
        else:
            (fa, a), (fb, b) = keys[i - 1], keys[i]
            vals.append(a + (b - a) * ac.ease((f - fa) / (fb - fa), "io"))
    ac.write(obj, 'modifiers["Outline"].thickness', 0, frames, vals)
    return mod
