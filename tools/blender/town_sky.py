"""Sky of technology-disappeared: gradient per state (day, late afternoon, sunset, dusk, night), Milky Way
band in the world itself (smooth, no twinkling) and stars as an emissive mesh (points of 2 to 4 px, never
subpixel: docs/blender/effects-and-lighting.md, section 5).

The states only change on the cut (CONSTANT keys). The stars "appear" in a slow ramp: each star has a
draw 'rnd' and lights up slowly when the reveal value passes it (no individual pop).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import kit
from kit import lin

# (horizon, middle, zenith) per state
STATES = {
    "day": ("#C9DCEC", "#86AED6", "#4A7DB6"),
    "dusk": ("#E8A256", "#4C5C86", "#141C34"),
    "sunset": ("#F2A04A", "#9A6A6A", "#2A3866"),
    "nightfall": ("#9A5C3A", "#26345A", "#0B1226"),
    "night": ("#1C2A48", "#0E1630", "#05080F"),
}
ORDER = ("day", "dusk", "sunset", "nightfall", "night")
BAND_NORMAL = Vector((0.55, -0.35, 0.76)).normalized()     # Milky Way band crossing the sky diagonally
STAR_R = 1500.0


def _ramp(n, links, z_socket, colors):
    r = n.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "EASE"
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin(colors[0])
    e[1].position, e[1].color = 0.85, lin(colors[2])
    mid = e.new(0.22)
    mid.color = lin(colors[1])
    links.new(z_socket, r.inputs["Fac"])
    return r


def _band(n, links, dir_socket):
    """Milky Way brightness: 1 - |d.n| / width, in power, blotched by noise. Returns the factor socket."""
    dot = n.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = tuple(BAND_NORMAL)
    links.new(dir_socket, dot.inputs[0])
    ab = n.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    links.new(dot.outputs["Value"], ab.inputs[0])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.0, 0.17
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    links.new(ab.outputs[0], mr.inputs["Value"])
    pw = n.new("ShaderNodeMath"); pw.operation = "POWER"
    pw.inputs[1].default_value = 1.8
    links.new(mr.outputs["Result"], pw.inputs[0])
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 4.0
    links.new(dir_socket, noise.inputs["Vector"])
    mn = n.new("ShaderNodeMapRange")
    mn.inputs["From Min"].default_value, mn.inputs["From Max"].default_value = 0.38, 0.68
    mn.inputs["To Min"].default_value, mn.inputs["To Max"].default_value = 0.15, 1.0
    links.new(noise.outputs["Fac"], mn.inputs["Value"])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    links.new(pw.outputs[0], mul.inputs[0])
    links.new(mn.outputs["Result"], mul.inputs[1])
    strength = n.new("ShaderNodeMath"); strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 0.0
    links.new(mul.outputs[0], strength.inputs[0])
    return strength


def build_world():
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    n, links = world.node_tree.nodes, world.node_tree.links
    bg = n.get("Background") or n.new("ShaderNodeBackground")
    out = n.get("World Output") or n.new("ShaderNodeOutputWorld")
    coord = n.new("ShaderNodeTexCoord")
    norm = n.new("ShaderNodeVectorMath"); norm.operation = "NORMALIZE"
    links.new(coord.outputs["Generated"], norm.inputs[0])
    sep = n.new("ShaderNodeSeparateXYZ")
    links.new(norm.outputs[0], sep.inputs[0])
    clampz = n.new("ShaderNodeMath"); clampz.operation = "MAXIMUM"
    clampz.inputs[1].default_value = 0.0
    links.new(sep.outputs["Z"], clampz.inputs[0])

    color, factors = None, {}
    for name in ORDER:
        r = _ramp(n, links, clampz.outputs[0], STATES[name])
        if color is None:
            color = r.outputs["Color"]
            continue
        m = n.new("ShaderNodeMix"); m.data_type = "RGBA"
        m.inputs["Factor"].default_value = 0.0
        links.new(color, m.inputs["A"])
        links.new(r.outputs["Color"], m.inputs["B"])
        factors[name] = m.inputs["Factor"]
        color = m.outputs["Result"]
    band = _band(n, links, norm.outputs[0])
    add = n.new("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"
    add.inputs["B"].default_value = lin("#B8C4E0")
    links.new(band.outputs[0], add.inputs["Factor"])
    links.new(color, add.inputs["A"])
    links.new(add.outputs["Result"], bg.inputs["Color"])

    ambient = n.new("ShaderNodeBackground")
    ambient.inputs["Color"].default_value = lin("#3A5285")
    ambient.inputs["Strength"].default_value = 1.0
    path = n.new("ShaderNodeLightPath")
    pick = n.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], pick.inputs["Fac"])
    links.new(ambient.outputs[0], pick.inputs[1])
    links.new(bg.outputs[0], pick.inputs[2])
    links.new(pick.outputs[0], out.inputs["Surface"])

    sun_light = bpy.data.lights.new("Sun", "SUN")
    sun_light.energy = 3.0
    sun_light.angle = math.radians(2.0)
    sun_light.shadow_maximum_resolution = 0.02   # raking late-afternoon sun: a fine shadow map cost 4 s/frame
    sun_light.shadow_filter_radius = 3.0          # blurred shadow edge: the coarse map does not alias with the camera moving
    sun = bpy.data.objects.new("Sun", sun_light)
    bpy.context.collection.objects.link(sun)
    return SimpleNamespace(world=world, factors=factors, band=band.inputs[1], sky=bg.inputs["Strength"],
                           ambient=ambient.inputs["Strength"], ambient_color=ambient.inputs["Color"],
                           sun=sun_light, sun_obj=sun)


# ---------- estrelas ----------

def _sphere_point(rnd):
    while True:
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if 0.05 < v.length <= 1.0:
            return v.normalized()


def star_field(center=(0, 0, 0), count=4600, band_count=3800, seed=5):
    """One mesh with thousands of emissive octahedra on a 1.5 km dome. Attribute 'rnd' per vertex: the order
    in which they light up. Returns (object, 'reveal' socket 0..1.2, strength socket)."""
    rnd = random.Random(seed)
    verts, faces, ranks = [], [], []
    c = Vector(center)
    pts = []
    while len(pts) < count:
        d = _sphere_point(rnd)
        if d.z > -0.05:
            pts.append((d, rnd.random()))
    while len(pts) < count + band_count:
        d = _sphere_point(rnd)
        off = d.dot(BAND_NORMAL)
        if d.z > -0.05 and abs(off) < 0.14 * rnd.random() ** 0.7:
            pts.append((d, rnd.random() * 0.8 + 0.2))
    for d, rank in pts:
        size = STAR_R * rnd.choice((0.0016, 0.0018, 0.0021, 0.0026))   # >= 2 px a 18 mm: menores cintilavam (22/10) * (1.4 if rank < 0.05 else 1.0)
        geo = kit._gem_geo(size, stretch=1.0)
        base = len(verts)
        p = c + d * STAR_R
        verts += [(p.x + x, p.y + y, p.z + z) for x, y, z in geo[0]]
        faces += [tuple(i + base for i in f) for f in geo[1]]
        ranks += [rank] * len(geo[0])
    mat = bpy.data.materials.new("StarsMat")
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#E8EEFF")
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "rnd"
    reveal = nt.nodes.new("ShaderNodeValue"); reveal.outputs[0].default_value = 1.2
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    nt.links.new(reveal.outputs[0], sub.inputs[0])
    nt.links.new(attr.outputs["Fac"], sub.inputs[1])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.0, 0.15
    nt.links.new(sub.outputs[0], ramp.inputs["Value"])
    power = nt.nodes.new("ShaderNodeValue"); power.outputs[0].default_value = 0.0
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Result"], mul.inputs[0])
    nt.links.new(power.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")        # star still off: invisible (not a black dot)
    on = nt.nodes.new("ShaderNodeMath"); on.operation = "MINIMUM"
    on.inputs[1].default_value = 1.0
    nt.links.new(mul.outputs[0], on.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(on.outputs[0], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], outn.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    obj = kit.mesh_object("Stars", verts, faces, [mat])
    a = obj.data.attributes.new("rnd", "FLOAT", "POINT")
    a.data.foreach_set("value", ranks)
    obj.visible_shadow = False
    obj.visible_diffuse = obj.visible_glossy = False
    return obj, reveal.outputs[0], power.outputs[0]
