"""Magnifying lens of viruses-disappeared: an abstract circle attached to the camera with a micro scene inside.

SOURCE: procedural (art.md §2 "Lens"; direction.md §3 scenes 02, 04, 05, 07). Geometry attached to the camera (opaque disc +
objects), NEVER a 2nd render with a mask (it would double the cost, art.md §5).

Measurements in pixels of 1080x1920 (24 mm lens, 36 mm sensor on the height: 1280 px per radian). The lens sits D meters
from the camera; 1 px = D / 1280 m on that plane. Everything inside it is pure emission (no scene light, no shadow): the "light from
above" comes from the shader (normal in camera space), the same at any camera angle.

Palette (art.md): background #0B1A2C (bottom) -> #16324E (top); amber ring #F5A524 of 10 px, dark inner edge of
4 px, soft 12 px shadow outside; diatom #7FA040 live, #4E5E3A dim (A), #66803E at ~60% (B); bubbles
#E6F0F4 with a rim, >= 6 px. Maximum 12 objects per lens.

Usage: lens = build("LensA", cam, (300, 560), 400); diatoms(lens, rnd, ...); bubbles(lens, rnd, ...).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import kit
from kit import lin

F_PX = 1280.0
DIST = 0.25          # m from the camera to the lens background plane

BG_LOW, BG_TOP = "#0B1A2C", "#16324E"
RING = "#F5A524"
DIATOM_LIVE, DIATOM_OFF, DIATOM_LOW = "#7FA040", "#4E5E3A", "#66803E"
BUBBLE = "#E6F0F4"


def _px(p, d=DIST):
    return p * d / F_PX


def _cam_xy(px, py, d=DIST):
    """Pixel (x, y from the top) -> coordinate in camera space at d meters (camera looks along -z, y up)."""
    return Vector(((px - 540.0) * d / F_PX, -(py - 960.0) * d / F_PX, -d))


# ---------- materials (pure emission) ----------

def _emit_mat(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree if mat.node_tree else None
    if nt is None:
        mat.use_nodes = True
        nt = mat.node_tree
    n, L = nt.nodes, nt.links
    for nd in list(n):
        if nd.type != "OUTPUT_MATERIAL":
            n.remove(nd)
    out = next(nd for nd in n if nd.type == "OUTPUT_MATERIAL")
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    em.inputs["Strength"].default_value = strength
    L.new(em.outputs[0], out.inputs["Surface"])
    return mat, n, L, em


def lit_mat(name, color, top=1.2, bottom=0.62, rim=0.3):
    """Matte object with volume, lit "from above" in camera space (no scene light). Returns the material and the
    color RGB node (to animate the brightness: write to .outputs[0].default_value)."""
    mat, n, L, em = _emit_mat(name, color)
    geo = n.new("ShaderNodeNewGeometry")
    vt = n.new("ShaderNodeVectorTransform")
    vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
    L.new(geo.outputs["Normal"], vt.inputs[0])
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(vt.outputs[0], sep.inputs[0])
    shade = n.new("ShaderNodeMapRange")
    shade.inputs["From Min"].default_value, shade.inputs["From Max"].default_value = -1.0, 1.0
    shade.inputs["To Min"].default_value, shade.inputs["To Max"].default_value = bottom, top
    L.new(sep.outputs["Y"], shade.inputs["Value"])
    # weak backlight at the edge (low facing = edge)
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    edge = n.new("ShaderNodeMath"); edge.operation = "MULTIPLY_ADD"
    L.new(lw.outputs["Facing"], edge.inputs[0])
    edge.inputs[1].default_value = rim
    L.new(shade.outputs["Result"], edge.inputs[2])
    rgb = n.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = lin(color)
    mul = n.new("ShaderNodeVectorMath"); mul.operation = "SCALE"
    L.new(rgb.outputs[0], mul.inputs[0])
    L.new(edge.outputs[0], mul.inputs["Scale"])
    L.new(mul.outputs[0], em.inputs["Color"])
    for o in (mat,):
        o.use_backface_culling = False
    return mat, rgb


def _bg_mat(name, radius):
    """Lens background: vertical gradient (light at the top, 'sun through the surface') and darkened near the edge."""
    mat, n, L, em = _emit_mat(name, BG_LOW)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    g = n.new("ShaderNodeMapRange")
    g.inputs["From Min"].default_value, g.inputs["From Max"].default_value = -radius, radius
    L.new(sep.outputs["Y"], g.inputs["Value"])
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin(BG_LOW)
    e[1].position, e[1].color = 1.0, lin("#1E4466")
    mid = e.new(0.6); mid.color = lin(BG_TOP)
    L.new(g.outputs["Result"], ramp.inputs["Fac"])
    # very faint light rays from above (wide, soft bands)
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.inputs["Scale"].default_value = 3.0 / radius
    wave.inputs["Distortion"].default_value = 2.0
    L.new(tc.outputs["Object"], wave.inputs["Vector"])
    wm = n.new("ShaderNodeMapRange")
    wm.inputs["To Min"].default_value, wm.inputs["To Max"].default_value = 0.96, 1.06
    L.new(wave.outputs["Fac"], wm.inputs["Value"])
    mul = n.new("ShaderNodeVectorMath"); mul.operation = "SCALE"
    L.new(ramp.outputs["Color"], mul.inputs[0])
    L.new(wm.outputs["Result"], mul.inputs["Scale"])
    L.new(mul.outputs[0], em.inputs["Color"])
    return mat


def _shadow_mat(name, r0, r1, alpha=0.45):
    """Soft shadow outside the ring: transparent black that fades from r0 to r1 (BLENDED, no cast shadow)."""
    mat = bpy.data.materials.new(name)
    if not mat.node_tree:
        mat.use_nodes = True
    n, L = mat.node_tree.nodes, mat.node_tree.links
    for nd in list(n):
        if nd.type != "OUTPUT_MATERIAL":
            n.remove(nd)
    out = next(nd for nd in n if nd.type == "OUTPUT_MATERIAL")
    tc = n.new("ShaderNodeTexCoord")
    ln = n.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"
    L.new(tc.outputs["Object"], ln.inputs[0])
    fall = n.new("ShaderNodeMapRange")
    fall.interpolation_type = "SMOOTHSTEP"
    fall.inputs["From Min"].default_value, fall.inputs["From Max"].default_value = r0, r1
    fall.inputs["To Min"].default_value, fall.inputs["To Max"].default_value = alpha, 0.0
    L.new(ln.outputs["Value"], fall.inputs["Value"])
    tr = n.new("ShaderNodeBsdfTransparent")
    blk = n.new("ShaderNodeEmission")
    blk.inputs["Color"].default_value = lin("#05080C")
    mix = n.new("ShaderNodeMixShader")
    L.new(fall.outputs["Result"], mix.inputs["Fac"])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(blk.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    return mat


# ---------- geometry ----------

def _disc_geo(r, n=96, z=0.0):
    v = [(0.0, 0.0, z)] + [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    f = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    return v, f


def _annulus_geo(r0, r1, n=96, z=0.0):
    v = []
    for r in (r0, r1):
        v += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    f = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def _obj(name, geo, mat, parent, loc=(0, 0, 0)):
    o = kit.mesh_object(name, geo[0], geo[1], [mat], loc)
    o.parent = parent
    o.visible_shadow = False
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
        if hasattr(o, attr):
            setattr(o, attr, False)
    return o


def build(name, cam, center_px, diameter_px, dist=DIST):
    """Lens attached to the camera: root (empty) at the center, background, dark edge, amber ring and shadow. The root scales from 0 to 1
    to open/close (grow/vanish from the kit). Returns SimpleNamespace(root, r, px, objs)."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.parent = cam
    root.location = _cam_xy(*center_px, d=dist)
    root.empty_display_size = 0.02
    r = _px(diameter_px / 2, dist)
    ring_w, inner_w, shadow_w = _px(10, dist), _px(4, dist), _px(12, dist)
    objs = [
        _obj(f"{name}Bg", _disc_geo(r), _bg_mat(f"{name}BgMat", r), root),
        _obj(f"{name}Inner", _annulus_geo(r - inner_w, r, z=_px(0.4, dist)),
             _emit_mat(f"{name}InnerMat", "#060B12")[0], root),
        _obj(f"{name}Ring", _annulus_geo(r, r + ring_w, z=_px(0.6, dist)),
             _emit_mat(f"{name}RingMat", RING, 1.0)[0], root),
        _obj(f"{name}Shadow", _annulus_geo(r + ring_w, r + ring_w + shadow_w, z=_px(0.2, dist)),
             _shadow_mat(f"{name}ShadowMat", r + ring_w, r + ring_w + shadow_w), root),
    ]
    return SimpleNamespace(name=name, root=root, r=r, dist=dist, px=lambda p: _px(p, dist), objs=objs)


def _lens_xy(lens, x_px, y_px, depth_px):
    """Position inside the lens in pixels relative to the center (y up), in front of the background."""
    return (lens.px(x_px), lens.px(y_px), lens.px(depth_px))


def _cell_geo(length, width, n=8, cap=0.25):
    """Diatom cell (frustule as a 'little box'): flattened octagonal prism with chamfered caps, x axis."""
    rings = []
    for x, k in ((-length / 2, 1 - cap), (-length / 2 + length * 0.12, 1.0), (length / 2 - length * 0.12, 1.0),
                 (length / 2, 1 - cap)):
        ring = []
        for i in range(n):
            a = 2 * math.pi * (i + 0.5) / n
            ring.append((x, width / 2 * k * math.cos(a), width / 2 * k * math.sin(a) * 0.7))
        rings.append(ring)
    return kit.loft_geo(rings)


def diatoms(lens, rnd, chains, color=DIATOM_LIVE, name="Diatom"):
    """Chains of diatoms: chains = [(x_px, y_px, angle degrees, number of cells)]. One mesh per chain
    (≤ 12 objects per lens). Returns (objects, color RGB node to animate the brightness)."""
    mat, rgb = lit_mat(f"{lens.name}{name}Mat", color)
    band_mat = lit_mat(f"{lens.name}{name}BandMat", "#3E4E2A")[0]
    out = []
    for k, (x, y, ang, cells) in enumerate(chains):
        L, Wd = rnd.uniform(26, 32), rnd.uniform(19, 23)
        geos, owner_mat = [], []
        for c in range(cells):
            cx = (c - (cells - 1) / 2) * (L + 3)
            v, f = _cell_geo(lens.px(L), lens.px(Wd))
            geos.append(([(p[0] + lens.px(cx), p[1], p[2]) for p in v], f))
            owner_mat.append(0)
            # girdle (frustule band) darker in the middle of the cell
            v2, f2 = _cell_geo(lens.px(4), lens.px(Wd * 1.04), cap=0.0)
            geos.append(([(p[0] + lens.px(cx), p[1], p[2]) for p in v2], f2))
            owner_mat.append(1)
        v, f, own = kit.merge(*geos)
        o = kit.mesh_object(f"{lens.name}{name}{k}", v, f, [mat, band_mat],
                            _lens_xy(lens, x, y, 14), face_mats=[owner_mat[i] for i in own])
        o.parent = lens.root
        o.rotation_euler = (0, 0, math.radians(ang))
        o.visible_shadow = False
        out.append(o)
    return out, rgb


def bubble_mat(name):
    """Bubble with a rim: light edge, translucent bluish center (no glass: emission + transparency)."""
    mat = bpy.data.materials.new(name)
    if not mat.node_tree:
        mat.use_nodes = True
    n, L = mat.node_tree.nodes, mat.node_tree.links
    for nd in list(n):
        if nd.type != "OUTPUT_MATERIAL":
            n.remove(nd)
    out = next(nd for nd in n if nd.type == "OUTPUT_MATERIAL")
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    rim = n.new("ShaderNodeMapRange")
    rim.inputs["From Min"].default_value, rim.inputs["From Max"].default_value = 0.25, 0.7
    L.new(lw.outputs["Facing"], rim.inputs["Value"])
    em_rim = n.new("ShaderNodeEmission")
    em_rim.inputs["Color"].default_value = lin(BUBBLE)
    em_in = n.new("ShaderNodeEmission")
    em_in.inputs["Color"].default_value = lin("#5A7A9A")
    mix = n.new("ShaderNodeMixShader")
    L.new(rim.outputs["Result"], mix.inputs["Fac"])
    L.new(em_in.outputs[0], mix.inputs[1])
    L.new(em_rim.outputs[0], mix.inputs[2])
    out_mix = n.new("ShaderNodeMixShader")
    tr = n.new("ShaderNodeBsdfTransparent")
    al = n.new("ShaderNodeMapRange")
    al.inputs["To Min"].default_value, al.inputs["To Max"].default_value = 0.55, 1.0
    L.new(rim.outputs["Result"], al.inputs["Value"])
    L.new(al.outputs["Result"], out_mix.inputs["Fac"])
    L.new(tr.outputs[0], out_mix.inputs[1])
    L.new(mix.outputs[0], out_mix.inputs[2])
    L.new(out_mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    return mat


def bubbles(lens, points, name="Bubble"):
    """O2 bubbles: points = [(x_px, y_px, diameter_px)]. A single mesh (all together) to stay within the
    object ceiling. Returns the object."""
    mat = bubble_mat(f"{lens.name}{name}Mat")
    geos = [kit._ico_geo(lens.px(d / 2), (lens.px(x), lens.px(y), 0.0)) for x, y, d in points]
    v, f, _ = kit.merge(*geos)
    o = kit.mesh_object(f"{lens.name}{name}s", v, f, [mat], (0, 0, lens.px(24)))
    o.parent = lens.root
    o.visible_shadow = False
    return o


def set_brightness(rgb_node, color, k):
    """Brightness of the diatom color (k = 1 live); use with keys on the RGB node's default_value."""
    c = lin(color)
    rgb_node.outputs[0].default_value = (c[0] * k, c[1] * k, c[2] * k, 1.0)
