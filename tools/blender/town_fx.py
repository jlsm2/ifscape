"""Effects of technology-disappeared: the amber vanishing of everything that has a plug, battery or motor.

Layered vanishing (docs/blender/effects-and-lighting.md):
1. light: the object lights up amber all over (rise in 4 frames) and its light (headlight, pole) goes out in a ramp;
2. mass: the surface dissolves by noise blotches (all-or-nothing alpha, Dithered) with a bright amber edge;
3. residue: little amber dots rise from the object, shrink and go out (cell_models.specks_on_surface);
4. reaction: whoever depended on the object falls or looks (in the cast).
The timing of each object is the 'vanish' property of the object itself (0 = whole, 1 = gone), read by the material:
a shared material serves objects that vanish on different frames.
"""

import bpy

import kit
from kit import lin

AMBER = "#F5A524"
_done = set()


def dissolvable(mat_):
    """Switches the material output to: transparent <- (original + amber emission) by the noise mask."""
    if mat_ is None or mat_.name in _done:
        return
    _done.add(mat_.name)
    nt = mat_.node_tree
    n, links = nt.nodes, nt.links
    out = next(x for x in n if x.type == "OUTPUT_MATERIAL" and x.is_active_output)
    original = out.inputs["Surface"].links[0].from_socket
    attr = n.new("ShaderNodeAttribute"); attr.attribute_type = "OBJECT"; attr.attribute_name = "vanish"
    coord = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 3.0
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    spread = n.new("ShaderNodeMapRange")                 # noise (0.3..0.7) -> 0..1
    spread.inputs["From Min"].default_value, spread.inputs["From Max"].default_value = 0.32, 0.68
    links.new(noise.outputs["Fac"], spread.inputs["Value"])
    t = n.new("ShaderNodeMapRange")                      # vanish 0,25..1 -> limiar -0,05..1,05
    t.inputs["From Min"].default_value, t.inputs["From Max"].default_value = 0.25, 1.0
    t.inputs["To Min"].default_value, t.inputs["To Max"].default_value = -0.05, 1.05
    links.new(attr.outputs["Fac"], t.inputs["Value"])
    keep = n.new("ShaderNodeMath"); keep.operation = "GREATER_THAN"
    links.new(spread.outputs["Result"], keep.inputs[0])
    links.new(t.outputs["Result"], keep.inputs[1])
    edge_d = n.new("ShaderNodeMath"); edge_d.operation = "SUBTRACT"
    links.new(spread.outputs["Result"], edge_d.inputs[0])
    links.new(t.outputs["Result"], edge_d.inputs[1])
    edge = n.new("ShaderNodeMapRange")                   # edge: 0..0.1 above the threshold -> 1..0
    edge.inputs["From Min"].default_value, edge.inputs["From Max"].default_value = 0.0, 0.1
    edge.inputs["To Min"].default_value, edge.inputs["To Max"].default_value = 1.0, 0.0
    links.new(edge_d.outputs[0], edge.inputs["Value"])
    glow = n.new("ShaderNodeMapRange")                   # overall glow: rises from 0 to 0.25
    glow.inputs["From Min"].default_value, glow.inputs["From Max"].default_value = 0.0, 0.25
    glow.inputs["To Max"].default_value = 0.9
    links.new(attr.outputs["Fac"], glow.inputs["Value"])
    edge_w = n.new("ShaderNodeMath"); edge_w.operation = "MULTIPLY"
    edge_w.inputs[1].default_value = 5.0
    links.new(edge.outputs["Result"], edge_w.inputs[0])
    active = n.new("ShaderNodeMath"); active.operation = "GREATER_THAN"     # the edge only exists while vanishing
    active.inputs[1].default_value = 0.2
    links.new(attr.outputs["Fac"], active.inputs[0])
    edge_on = n.new("ShaderNodeMath"); edge_on.operation = "MULTIPLY"
    links.new(edge_w.outputs[0], edge_on.inputs[0])
    links.new(active.outputs[0], edge_on.inputs[1])
    total = n.new("ShaderNodeMath"); total.operation = "ADD"
    links.new(edge_on.outputs[0], total.inputs[0])
    links.new(glow.outputs["Result"], total.inputs[1])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(AMBER)
    links.new(total.outputs[0], em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    links.new(original, add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    clear = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    links.new(keep.outputs[0], mix.inputs["Fac"])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(add.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat_.surface_render_method = "DITHERED"


def make_dissolvable(objs):
    for o in objs:
        if o.type != "MESH":
            continue
        o["vanish"] = 0.0
        for slot in o.material_slots:
            dissolvable(slot.material)


def vanish(objs, frame, frames=12):
    """Vanishes from 'frame' to 'frame + frames': lights up (0 -> 0.25 in 4 frames), dissolves up to 1. LINEAR keys."""
    for o in objs:
        if "vanish" not in o:
            continue
        for f, v in ((1, 0.0), (frame, 0.0), (frame + 4, 0.25), (frame + frames, 1.0)):
            o["vanish"] = v
            o.keyframe_insert('["vanish"]', frame=f)
        _linear(o, '["vanish"]')


def _linear(owner, path):
    ad = owner.animation_data
    if ad is None or ad.action is None:
        return
    for layer in ad.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    if fc.data_path == path:
                        for kp in fc.keyframe_points:
                            kp.interpolation = "LINEAR"


def light_off(owner, attr, on, frame, frames=4, start=1):
    """Light on until 'frame' and going out in a ramp of 'frames' frames (no step, no flicker)."""
    kit.key(owner, attr, on, start)
    kit.key(owner, attr, on, frame)
    kit.key(owner, attr, 0.0, frame + frames)
