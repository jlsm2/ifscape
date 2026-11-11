"""Models for plants-extinct (Mediterranean village square): plane tree in 4 states, stall with awning, brazier, pile of
firewood with bracket fungi, fish crate, whitewashed houses, materials by state.

Plant state = scene property "plant_state" (0 NOW, 1 1 WEEK, 2 1 YEAR, 3 YEARS), read in the materials by the
Attribute node (View Layer) and switched only on the cut (CONSTANT key). Master rule of art.md: ONLY the plant changes; sky, sea,
roof tile, wall, shutter, awning, clothes and fungus use fixed materials.

Proportions and sources:
- Plane tree (Platanus orientalis): 15 m tall, crown 14 m (wider than tall), trunk 1.2 m, 3 limbs below the
  crown (direction.md section 4; https://en.wikipedia.org/wiki/Platanus_orientalis). Mottled bark when alive (art.md section 1.3).
- Bracket fungus (Laetiporus sulphureus), fans of 5 to 30 cm on hardwood
  (https://mushroomexpert.com/fungionwood/poroid%20fungi/species%20pages/Laetiporus%20sulphureus.htm); mesh from
  Quaternius "Stylized Nature MegaKit" (CC0, assets/quaternius/stylized-nature-megakit/License_Standard.txt), with
  its own flat material.
- Stall 2.4 x 0.8 m, top at 0.9 m; fish crate 0.5 x 0.35 x 0.15 m; firewood 0.5 m x 10-15 cm (direction.md section 4).
- Low-poly references: Kenney Fantasy Town Kit (stall, houses), Quaternius Stylized Nature (tree in masses).
"""

import math
import random
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
from kit import lin

ASSETS = Path(__file__).resolve().parents[2] / "assets"
STATE = "plant_state"
HORIZON = "#B8D4EA"

# ---------- palette (art.md section 1.2): (NOW, 1 WEEK, 1 YEAR, YEARS) ----------
GRASS = ("#6FA83A", "#D4BC80", "#9E978A", "#8C8478")
GRASS_TIP = ("#86BC4C", "#E6D29C", "#A8A194", "#968E82")
LEAF = ("#4F8A3C", "#9C6A36", "#6B5A48", "#6B5A48")
LEAF_EDGE = ("#6FA84A", "#A8703A", "#6B5A48", "#6B5A48")
HEDGE = ("#3E7A34", "#7A5A34", "#7E786E", "#6E6A64")
FLOWER = ("#D86A8A", "#8A6A50", "#7E786E", "#6E6A64")
FLOWER2 = ("#E8D27A", "#8A6A50", "#7E786E", "#6E6A64")
VINE = ("#5C8F3A", "#8A6A3C", "#8C877C", "#8F7656")
WHEAT = ("#8DB04A", "#D8C07C", "#8C877C", "#8F7656")
FOREST = ("#4A7A55", "#A08A62", "#8E8A80", "#8A847A")
FOREST_FLOOR = ("#3E6A48", "#8E7A56", "#8A867C", "#867F74")   # forest floor (shade of the crowns), one tone below
FIELD_FAR = ("#A8C070", "#C2AA74", "#908676", "#8E7A60")
PLOWED = ("#9A7A55", "#B89A6A", "#908676", "#8E7A60")
SOIL = ("#5E4A36", "#6E5840", "#8A7356", "#8F7656")
OLIVE = ("#6E8A5A", "#9A8458", "#8A857A", "#7A766E")

# fixos
WALL = "#E6DFD0"
ROOF = "#B5643C"
SHUTTER = "#3E6A8C"
STONE = "#C9BFA8"
AWNING = "#C8553D"
AWNING2 = "#E6DFD0"
WOOD = "#9A6E46"
FUNGUS_TOP, FUNGUS_EDGE, FUNGUS_UNDER = "#E8A030", "#F2C64A", "#F2D8A0"
LUZ = "#F5A524"


def hazed(colors, k):
    """Atmospheric perspective without fog (art.md section 2.1): each color already mixed k toward the sky horizon."""
    h = lin(HORIZON)
    out = []
    for c in colors:
        a = lin(c)
        mix = [a[i] + (h[i] - a[i]) * k for i in range(3)]
        out.append("#" + "".join(f"{round(255 * (x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055)):02X}"
                                 for x in mix))
    return tuple(out)


# ---------- materiais ----------

def node_mat(name, rough=0.9, spec=0.2):
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    p = kit.principled(mat)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    return mat, mat.node_tree.nodes, mat.node_tree.links, p


def _state_value(n, L):
    a = n.new("ShaderNodeAttribute")
    a.attribute_type = "VIEW_LAYER"
    a.attribute_name = STATE
    m = n.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = 0.0, 4.0
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = 0.02, 1.02
    L.new(a.outputs["Fac"], m.inputs["Value"])
    return m.outputs["Result"]


def state_ramp(n, L, colors):
    """Color that switches on the cut: CONSTANT ramp with 4 stops (NOW, WEEK, YEAR, YEARS)."""
    r = n.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "CONSTANT"
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin(colors[0])
    e[1].position, e[1].color = 0.25, lin(colors[1])
    for pos, c in ((0.5, colors[2]), (0.75, colors[3])):
        x = e.new(pos)
        x.color = lin(c)
    L.new(_state_value(n, L), r.inputs["Fac"])
    return r.outputs["Color"]


def _value_mul(n, L, color, factor_socket):
    hsv = n.new("ShaderNodeHueSaturation")
    L.new(color, hsv.inputs["Color"])
    L.new(factor_socket, hsv.inputs["Value"])
    return hsv.outputs["Color"]


def _rand_factor(n, L, lo=0.9, hi=1.1):
    info = n.new("ShaderNodeObjectInfo")
    m = n.new("ShaderNodeMapRange")
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = lo, hi
    L.new(info.outputs["Random"], m.inputs["Value"])
    return m.outputs["Result"]


def plant_mat(name, colors, rough=0.85, var=(0.9, 1.1), haze=0.0, tip=None, height=1.0, noise_scale=0.0,
              sun_side=None, sun_dir=None):
    """Plant material by state: ramp color x variation per object/instance (+-10%) and, with 'tip', gradient
    base->tip (base 25% darker). noise_scale > 0 blotches the color by noise (2 tones per mass)."""
    mat, n, L, p = node_mat(name, rough, 0.2)
    cols = hazed(colors, haze) if haze else colors
    col = state_ramp(n, L, cols)
    if tip is not None:
        tcol = state_ramp(n, L, hazed(tip, haze) if haze else tip)
        coord = n.new("ShaderNodeTexCoord")
        sep = n.new("ShaderNodeSeparateXYZ")
        L.new(coord.outputs["Object"], sep.inputs[0])
        g = n.new("ShaderNodeMapRange")
        g.inputs["From Min"].default_value, g.inputs["From Max"].default_value = 0.0, height
        L.new(sep.outputs["Z"], g.inputs["Value"])
        mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
        L.new(g.outputs["Result"], mix.inputs["Factor"])
        L.new(col, mix.inputs["A"]); L.new(tcol, mix.inputs["B"])
        dark = n.new("ShaderNodeMapRange")
        dark.inputs["From Min"].default_value, dark.inputs["From Max"].default_value = 0.0, height
        dark.inputs["To Min"].default_value, dark.inputs["To Max"].default_value = 0.75, 1.0
        L.new(sep.outputs["Z"], dark.inputs["Value"])
        col = _value_mul(n, L, mix.outputs["Result"], dark.outputs["Result"])
    if noise_scale:
        tex = n.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 1.0
        coord = n.new("ShaderNodeTexCoord")
        L.new(coord.outputs["Object"], tex.inputs["Vector"])
        m = n.new("ShaderNodeMapRange")
        m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = 0.35, 0.65
        m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = 0.88, 1.12
        L.new(tex.outputs["Fac"], m.inputs["Value"])
        col = _value_mul(n, L, col, m.outputs["Result"])
    if sun_side is not None:          # sun side with another ramp color (1 WEEK crown: #A8703A in the sun)
        scol = state_ramp(n, L, sun_side)
        geo = n.new("ShaderNodeNewGeometry")
        dot = n.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
        L.new(geo.outputs["Normal"], dot.inputs[0])
        dot.inputs[1].default_value = tuple(sun_dir)
        fac = n.new("ShaderNodeMapRange")
        fac.inputs["From Min"].default_value, fac.inputs["From Max"].default_value = 0.05, 0.55
        L.new(dot.outputs["Value"], fac.inputs["Value"])
        mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
        L.new(fac.outputs["Result"], mix.inputs["Factor"])
        L.new(col, mix.inputs["A"]); L.new(scol, mix.inputs["B"])
        col = mix.outputs["Result"]
    if var:
        col = _value_mul(n, L, col, _rand_factor(n, L, *var))
    L.new(col, p.inputs["Base Color"])
    return mat


def fixed_mat(name, color, rough=0.9, spec=0.2, var=None, emission=None, strength=0.0):
    mat, n, L, p = node_mat(name, rough, spec)
    p.inputs["Base Color"].default_value = lin(color)
    if var:
        L.new(_value_mul(n, L, _const(n, color), _rand_factor(n, L, *var)), p.inputs["Base Color"])
    if emission:
        p.inputs["Emission Color"].default_value = lin(emission)
        p.inputs["Emission Strength"].default_value = strength
    return mat


def _const(n, color):
    rgb = n.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = lin(color)
    return rgb.outputs[0]


def bark_mat(name):
    """Bark: alive = mottled (3 colors by large noise); dead (YEAR, YEARS) = 1 color with vertical cracks."""
    mat, n, L, p = node_mat(name, 0.9, 0.15)
    coord = n.new("ShaderNodeTexCoord")
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 1.1
    tex.inputs["Detail"].default_value = 1.5
    L.new(coord.outputs["Object"], tex.inputs["Vector"])
    r = n.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "CONSTANT"
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin("#A39A80")
    e[1].position, e[1].color = 0.6, lin("#C9BF9C")
    x = e.new(0.36); x.color = lin("#8A8C6C")
    x = e.new(0.45); x.color = lin("#A39A80")
    L.new(tex.outputs["Fac"], r.inputs["Fac"])
    # dead: gray with cracks (Voronoi stretched 1:6 vertically)
    sc = n.new("ShaderNodeMapping")
    sc.inputs["Scale"].default_value = (7.0, 7.0, 1.0)
    L.new(coord.outputs["Object"], sc.inputs["Vector"])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 1.4
    vor.inputs["Randomness"].default_value = 0.8
    L.new(sc.outputs[0], vor.inputs["Vector"])
    crack = n.new("ShaderNodeMapRange")
    crack.inputs["From Min"].default_value, crack.inputs["From Max"].default_value = 0.012, 0.03
    L.new(vor.outputs["Distance"], crack.inputs["Value"])
    # only some of the edges become cracks (noise mask): no paving look
    msk = n.new("ShaderNodeTexNoise")
    msk.inputs["Scale"].default_value = 2.5
    L.new(coord.outputs["Object"], msk.inputs["Vector"])
    mm = n.new("ShaderNodeMapRange")
    mm.inputs["From Min"].default_value, mm.inputs["From Max"].default_value = 0.45, 0.55
    L.new(msk.outputs["Fac"], mm.inputs["Value"])
    keep = n.new("ShaderNodeMath"); keep.operation = "MAXIMUM"
    L.new(crack.outputs["Result"], keep.inputs[0]); L.new(mm.outputs["Result"], keep.inputs[1])
    dead = n.new("ShaderNodeMix"); dead.data_type = "RGBA"
    L.new(keep.outputs[0], dead.inputs["Factor"])
    dead.inputs["A"].default_value = lin("#4E4B47")
    L.new(state_ramp(n, L, ("#8C8A84", "#8C8A84", "#8F8A80", "#8C8A84")), dead.inputs["B"])
    pick = n.new("ShaderNodeMix"); pick.data_type = "RGBA"
    st = _state_value(n, L)
    gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.45
    L.new(st, gt.inputs[0])
    L.new(gt.outputs[0], pick.inputs["Factor"])
    L.new(r.outputs["Color"], pick.inputs["A"])
    L.new(dead.outputs["Result"], pick.inputs["B"])
    L.new(pick.outputs["Result"], p.inputs["Base Color"])
    return mat


def wood_mat(name, color=WOOD, aged=None):
    """Wood with grain (stretched noise) and per-board variation (+-8%); 'aged' = color of the YEARS state."""
    mat, n, L, p = node_mat(name, 0.85, 0.15)
    base = state_ramp(n, L, (color, color, color, aged or color))
    coord = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 14.0, 14.0)
    L.new(coord.outputs["Object"], mp.inputs["Vector"])
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 3.0
    L.new(mp.outputs[0], tex.inputs["Vector"])
    m = n.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = 0.3, 0.7
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = 0.9, 1.08
    L.new(tex.outputs["Fac"], m.inputs["Value"])
    col = _value_mul(n, L, base, m.outputs["Result"])
    col = _value_mul(n, L, col, _rand_factor(n, L, 0.92, 1.08))
    L.new(col, p.inputs["Base Color"])
    return mat


def stone_mat(name, color=STONE, scale=1.6, mortar="#9A9282", dark_base=False):
    """Stone/paving: blocks with +-8% variation (Brick) and darker joint."""
    mat, n, L, p = node_mat(name, 0.92, 0.15)
    coord = n.new("ShaderNodeTexCoord")
    b = n.new("ShaderNodeTexBrick")
    b.inputs["Scale"].default_value = scale
    b.inputs["Mortar Size"].default_value = 0.025
    b.inputs["Brick Width"].default_value = 0.6
    b.inputs["Row Height"].default_value = 0.3
    b.inputs["Bias"].default_value = 0.0
    c = lin(color)
    b.inputs["Color1"].default_value = tuple(x * 0.9 for x in c[:3]) + (1,)
    b.inputs["Color2"].default_value = tuple(min(1, x * 1.08) for x in c[:3]) + (1,)
    b.inputs["Mortar"].default_value = lin(mortar)
    b.offset = 0.5
    L.new(coord.outputs["Object"], b.inputs["Vector"])
    L.new(b.outputs["Color"], p.inputs["Base Color"])
    return mat


# ---------- geometria auxiliar ----------

def obj_from(name, geo, mats, location=(0, 0, 0), face_mats=None, parent=None):
    v, f = geo[0], geo[1]
    o = kit.mesh_object(name, v, f, mats, location, face_mats)
    if parent is not None:
        o.parent = parent
    return o


def lumpy_ico(r, center, scale=(1, 1, 1), rnd=None, amp=0.18):
    v, f = kit._ico_geo(r, center, scale)
    rnd = rnd or random.Random(0)
    c = Vector(center)
    out = []
    for p in v:
        d = Vector(p) - c
        k = 1.0 + rnd.uniform(-amp, amp)
        out.append(tuple(c + d * k))
    return out, f


def _empty(name, location=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.3
    bpy.context.collection.objects.link(e)
    e.location = location
    if parent is not None:
        e.parent = parent
    return e


# ---------- bracket fungus (Laetiporus) ----------

_fungus = {}


def fungus_mesh():
    """Procedural bracket fungus (Laetiporus): 3 stacked fans, half-ellipse with 4 cm thick edge (relative to
    1 m width), slightly domed top. Base on the wood at y = 0, the fan grows toward -y. The Quaternius mesh
    (Mushroom_Laetiporus.fbx) came out thin and pale at 9 m; kept only as a shape reference."""
    if "mesh" in _fungus:
        return _fungus["mesh"]
    rnd = random.Random(17)
    geos = []
    for k, (z, r) in enumerate(((0.0, 0.5), (0.2, 0.42), (0.38, 0.32))):
        n = 11
        top, bot = [], []
        for i in range(n):
            a = math.pi * i / (n - 1)
            rr = r * (1.0 + rnd.uniform(-0.08, 0.08)) * (0.75 + 0.25 * math.sin(a))
            x, y = -math.cos(a) * r * 1.1, -math.sin(a) * rr
            th = 0.09 * (0.4 + 0.6 * math.sin(a))
            top.append((x, y, z + 0.08 + 0.05 * math.sin(a) - 0.06 * (rr / r) ** 2))
            bot.append((x, y, z + 0.08 - th + 0.03 * math.sin(a)))
        base_t = [(x * 0.85, 0.0, z + 0.1) for x in (-r * 1.1, r * 1.1)]
        # fan: top (center of base -> edge), bottom, and the edge between top and bottom
        v = top + bot + [(0.0, 0.0, z + 0.12), (0.0, 0.0, z - 0.02)]
        ct, cb = 2 * n, 2 * n + 1
        f = [(ct, i + 1, i) for i in range(n - 1)] + [(cb, n + i, n + i + 1) for i in range(n - 1)]
        f += [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
        f += [(ct, 0, n, cb), (ct, cb, 2 * n - 1, n - 1)]
        geos.append((v, f))
    v, f, _ = kit.merge(*geos)
    me = bpy.data.meshes.new("Laetiporus")
    me.from_pydata(v, [], f)
    me.update()
    me.materials.append(fungus_mat())
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    _fungus["mesh"] = me
    return me


def fungus_mat():
    """Top #E8A030, edge #F2C64A (side faces), bottom #F2D8A0 (normal pointing down). Fixed in the 4 states."""
    if "mat" in _fungus:
        return _fungus["mat"]
    mat, n, L, p = node_mat("Fungus", 0.8, 0.2)
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sep.inputs[0])
    r = n.new("ShaderNodeValToRGB")
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.15, lin(FUNGUS_UNDER)
    e[1].position, e[1].color = 0.85, lin(FUNGUS_TOP)
    x = e.new(0.5); x.color = lin(FUNGUS_EDGE)
    m = n.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = -1.0, 1.0
    L.new(sep.outputs["Z"], m.inputs["Value"])
    L.new(m.outputs["Result"], r.inputs["Fac"])
    L.new(r.outputs["Color"], p.inputs["Base Color"])
    _fungus["mat"] = mat
    return mat


def fungus(name, location, size, normal=(0, -1, 0), parent=None, spin=0.0):
    """Bracket fungus fan of 'size' meters, growing out of the wood in the 'normal' direction."""
    o = bpy.data.objects.new(name, fungus_mesh())
    bpy.context.collection.objects.link(o)
    nrm = Vector(normal).normalized()
    # base of the fan against the wood; the fan "lies" outward (local y axis -> normal)
    flat = Vector((nrm.x, nrm.y, 0))
    q = Vector((0, -1, 0)).rotation_difference(flat.normalized() if flat.length > 0.05 else Vector((0, -1, 0)))
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = q @ Matrix.Rotation(spin, 4, "Z").to_quaternion()
    o.scale = (size, size, size)
    o.location = location
    if parent is not None:
        o.parent = parent
    return o


# ---------- plane tree ----------

TREE_H = 15.0
FORK_Z = 3.1
LIMB_AZ = (25.0, 145.0, 262.0)     # pernadas (graus, 0 = +x local)


def _limb_points(az_deg, tilts, lengths, start):
    az = math.radians(az_deg)
    pts = [Vector(start)]
    for t, ln in zip(tilts, lengths):
        t = math.radians(t)
        d = Vector((math.cos(az) * math.sin(t), math.sin(az) * math.sin(t), math.cos(t)))
        pts.append(pts[-1] + d * ln)
    return pts


def plane_tree(name, location, mats, rnd=None):
    """Plane tree: trunk with flared foot, 3 limbs and secondary branches (one mesh), crown in 7 masses.
    States per object: living crown (NOW), dry curled crown ~70% of the volume (WEEK), 5-10% of the leaves (YEAR), no
    leaves (YEARS). The falling branch (10) is a separate object, child of the trunk, pivot at the joint."""
    rnd = rnd or random.Random(7)
    root = _empty(name, location)
    parts = []
    trunk_pts = [(0, 0, 0), (0, 0, 0.35), (0.04, 0.02, 1.4), (0.08, 0.05, 2.5), (0.1, 0.05, FORK_Z)]
    parts.append(kit.tube_geo(trunk_pts, [1.0, 0.8, 0.75, 0.71, 0.66], n=10))
    # contact roots (3 low bumps at the foot)
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        parts.append(kit.tube_geo([(0.35 * math.cos(a), 0.35 * math.sin(a), 0.25),
                                   (0.95 * math.cos(a), 0.95 * math.sin(a), 0.02)], [0.26, 0.1], n=6))
    tips, sub_tips = [], []
    branch_spec = None
    for i, az in enumerate(LIMB_AZ):
        pts = _limb_points(az, (50, 44, 36, 28), (2.0, 2.0, 1.8, 1.5), (0.1, 0.05, FORK_Z - 0.3))
        parts.append(kit.tube_geo([tuple(p) for p in pts], [0.5, 0.38, 0.27, 0.17, 0.09], n=8))
        tips.append(pts[-1])
        for j, (k, side, ln) in enumerate(((1, 55, 3.4), (2, -60, 3.0), (3, 40, 2.4))):
            base = pts[k]
            sp = _limb_points(az + side, (62, 50, 40), (ln * 0.4, ln * 0.35, ln * 0.25), base)
            if i == 2 and j == 0:
                branch_spec = (sp, az + side)     # this one becomes the falling branch (5 m, 25 cm at the base)
                continue
            parts.append(kit.tube_geo([tuple(p) for p in sp], [0.17 - 0.03 * k, 0.11, 0.07, 0.04], n=6))
            sub_tips.append(sp[-1])
    v, f, _ = kit.merge(*parts)
    wood = obj_from(f"{name}Wood", (v, f), [mats["bark"]], parent=root)
    kit.fix_normals(wood)

    # falling branch: own piece, pivot at the joint (base), 5 m
    sp, baz = branch_spec
    base = sp[0]
    d = (sp[-1] - base).normalized()
    pts = [base + d * 0.0, base + d * 1.6 + Vector((0, 0, 0.25)), base + d * 3.3 + Vector((0, 0, 0.35)),
           base + d * 5.0 + Vector((0, 0, 0.2))]
    def tw(p, az, up, ln):
        a = math.radians(baz + az)
        q = p + Vector((math.cos(a), math.sin(a), up)).normalized() * ln
        return [p, (p + q) / 2 + Vector((0, 0, 0.1)), q]
    twigs = [(tw(pts[1], 70, 0.5, 1.6), 0.09), (tw(pts[2], -60, 0.4, 1.3), 0.07), (tw(pts[2], 50, 0.6, 1.0), 0.05),
             (tw(pts[1] * 0.5 + pts[2] * 0.5, -75, 0.3, 1.1), 0.06), (tw(pts[3], 35, 0.5, 0.8), 0.035)]
    local = [p - base for p in pts]
    bgeo = kit.merge(kit.tube_geo([tuple(p) for p in local], [0.27, 0.19, 0.11, 0.045], n=8),
                     *[kit.tube_geo([tuple(p - base) for p in t], [r, r * 0.6, r * 0.3], n=5) for t, r in twigs])
    branch = obj_from(f"{name}Branch", bgeo[:2], [mats["bark"]], location=tuple(base), parent=root)
    kit.fix_normals(branch)
    sub_tips.append(pts[-1])
    # fungi on the branch (upper side, already before the fall) and on the trunk
    up = Vector((0, 0, 1))
    side = d.cross(up).normalized()
    for k, (u, s, sz) in enumerate(((0.35, 1, 0.24), (0.5, -1, 0.2), (0.62, 1, 0.17), (0.78, -1, 0.14))):
        p = Vector(local[0]).lerp(Vector(local[3]), u)
        r = 0.22 - 0.15 * u
        fungus(f"{name}BFungus{k}", tuple(p + side * s * r * 0.8 + up * r * 0.55), sz, normal=tuple(side * s + up * 0.4),
               parent=branch, spin=rnd.uniform(-0.4, 0.4))
    trunk_fungi = []
    for k, (a, z, sz) in enumerate(((math.radians(-70), 1.6, 0.38), (math.radians(-35), 2.25, 0.3))):
        nrm = Vector((math.cos(a), math.sin(a), 0))
        trunk_fungi.append(fungus(f"{name}TFungus{k}", tuple(nrm * 0.7 + Vector((0, 0, z))), sz, normal=tuple(nrm),
                                  parent=root))

    # wide dome crown (14 m, from ~4.8 to 14.5 m): 6 masses in the lower ring, 5 in the middle, 2 at the top, with gaps
    centers = []
    r0 = random.Random(21)
    for k in range(6):
        a = 2 * math.pi * k / 6 + r0.uniform(-0.2, 0.2) + 0.3
        centers.append((Vector((4.5 * math.cos(a), 4.5 * math.sin(a), 7.2 + r0.uniform(-0.4, 0.5))), 2.6))
    for k in range(5):
        a = 2 * math.pi * k / 5 + r0.uniform(-0.25, 0.25)
        centers.append((Vector((3.0 * math.cos(a), 3.0 * math.sin(a), 10.0 + r0.uniform(-0.3, 0.4))), 2.8))
    centers += [(Vector((0.8, 0.3, 12.4)), 2.5), (Vector((-0.9, -0.4, 12.2)), 2.4)]
    canopies = {}
    for state, scale, amp, keep in (("now", 1.0, 0.16, 1.0), ("week", 0.85, 0.3, 0.72)):
        r2 = random.Random(11)
        geos = []
        for c, r in centers:
            for k in range(2):
                off = Vector((r2.uniform(-1, 1), r2.uniform(-1, 1), r2.uniform(-0.4, 0.4))) * r * 0.35
                if k and r2.random() > keep:
                    continue
                rr = r * r2.uniform(0.78, 0.95) * scale
                geos.append(lumpy_ico(rr, tuple(c + off * scale), (1.0, 1.0, 0.82), r2, amp))
        v, f, _ = kit.merge(*geos)
        canopies[state] = obj_from(f"{name}Canopy{state.title()}", (v, f), [mats[f"leaf_{state}"]], parent=root)
    # 1 YEAR: 5-10% of the leaves, small tufts at the tips
    r3 = random.Random(5)
    geos = []
    for p in sub_tips + tips:
        for k in range(2):
            geos.append(lumpy_ico(r3.uniform(0.25, 0.4), tuple(p + Vector((r3.uniform(-.4, .4), r3.uniform(-.4, .4),
                                                                              r3.uniform(-.2, .3)))), (1, 1, 0.7), r3, 0.3))
    v, f, _ = kit.merge(*geos)
    canopies["year"] = obj_from(f"{name}CanopyYear", (v, f), [mats["leaf_week"]], parent=root)
    return SimpleNamespace(root=root, wood=wood, branch=branch, canopies=canopies, trunk_fungi=trunk_fungi,
                           branch_base=Vector(base), branch_dir=d)


# ---------- stall ----------

def awning_mat():
    """Striped awning #C8553D / #E6DFD0 (0.3 m stripes along local x). Fixed."""
    mat, n, L, p = node_mat("Awning", 0.85, 0.15)
    coord = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Object"], sep.inputs[0])
    w = n.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.bands_direction = "X"
    w.inputs["Scale"].default_value = 1.0 / 0.6 * 0.5
    L.new(coord.outputs["Object"], w.inputs["Vector"])
    g = n.new("ShaderNodeMath"); g.operation = "GREATER_THAN"
    g.inputs[1].default_value = 0.5
    L.new(w.outputs["Fac"], g.inputs[0])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(g.outputs[0], mix.inputs["Factor"])
    mix.inputs["A"].default_value = lin(AWNING)
    mix.inputs["B"].default_value = lin(AWNING2)
    L.new(mix.outputs["Result"], p.inputs["Base Color"])
    return mat


def stall(name, location, mats, width=2.4, depth=0.8, top=0.9):
    """Market stall: top of boards, legs, 4 posts and sloped awning with scalloped valance at the front.
    Origin at the middle of the back edge of the top (vendor side); front toward +y."""
    root = _empty(name, location)
    wood = mats["wood"]
    parts = []
    hw = width / 2
    # top: 6 boards with 1 cm gap
    n_pl = 6
    for k in range(n_pl):
        y0 = depth * k / n_pl
        parts.append(kit._box_geo(width, depth / n_pl - 0.01, 0.04, -hw, y0, top - 0.04))
    parts.append(kit._box_geo(width, 0.03, 0.22, -hw, depth - 0.03, top - 0.26))     # front apron
    for x in (-hw + 0.05, hw - 0.1):
        for y in (0.05, depth - 0.1):
            parts.append(kit._box_geo(0.06, 0.06, top - 0.04, x, y, 0))
    parts.append(kit._box_geo(width - 0.1, depth - 0.1, 0.03, -hw + 0.05, 0.05, 0.25))  # lower shelf
    v, f, _ = kit.merge(*parts)
    table = obj_from(f"{name}Table", (v, f), [wood], parent=root)
    # posts and awning
    posts = []
    for x in (-hw - 0.02, hw - 0.04):
        for y, h in ((-0.9, 3.12), (0.98, 2.94)):
            posts.append(kit._box_geo(0.06, 0.06, h, x, y, 0))
    v, f, _ = kit.merge(*posts)
    obj_from(f"{name}Posts", (v, f), [wood], parent=root)
    y0, y1, z0, z1 = -1.0, 1.05, 3.15, 2.96
    ext = 0.25
    verts, faces = [], []
    nx = 16
    for i in range(nx + 1):
        x = -hw - ext + (width + 2 * ext) * i / nx
        verts += [(x, y0, z0), (x, y1, z1), (x, y0, z0 + 0.02), (x, y1, z1 + 0.02)]
    for i in range(nx):
        a, b = 4 * i, 4 * (i + 1)
        faces += [(a, b, b + 1, a + 1), (a + 3, b + 3, b + 2, a + 2)]
    # valance: rounded teeth (half-moon) hanging at the front, slightly wavy (wind)
    teeth = 10
    tw = (width + 2 * ext) / teeth
    for t in range(teeth):
        cx = -hw - ext + tw * (t + 0.5)
        base_i = len(verts)
        ring = []
        for k in range(7):
            a = math.pi * k / 6
            ring.append((cx - tw / 2 * math.cos(a), y1 + 0.01 * math.sin(t * 1.7), z1 - 0.06 - 0.16 * math.sin(a)))
        top_l, top_r = (cx - tw / 2, y1 + 0.01 * math.sin(t * 1.7), z1 + 0.01), (cx + tw / 2, y1 + 0.01 * math.sin(t * 1.7), z1 + 0.01)
        verts += [top_l] + ring + [top_r]
        faces.append(tuple(range(base_i, base_i + 9)))
    aw = kit.mesh_object(f"{name}Awning", verts, faces, [mats["awning"]])
    aw.parent = root
    aw.data.polygons.foreach_set("use_smooth", [False] * len(aw.data.polygons))
    return SimpleNamespace(root=root, table=table, awning=aw, top=top, depth=depth, width=width)


def collapsed_stall(name, location, mats, rnd):
    """Collapsed stall (YEARS): boards and posts on the ground, crooked, old-wood color."""
    root = _empty(name, location)
    parts = []
    for k in range(9):
        L_ = rnd.uniform(1.2, 2.4)
        g = kit._box_geo(L_, 0.13, 0.035, -L_ / 2, -0.065, 0)
        m = Matrix.Translation((rnd.uniform(-1.0, 1.0), rnd.uniform(-0.2, 1.4), 0.02 + 0.03 * (k % 3))) @ \
            Matrix.Rotation(rnd.uniform(-0.5, 0.5), 4, "Z") @ Matrix.Rotation(rnd.uniform(-0.08, 0.08), 4, "X")
        parts.append(kit.xform_geo(g, m))
    for k in range(3):
        g = kit._box_geo(0.06, 0.06, 2.4, -0.03, -0.03, 0)
        m = Matrix.Translation((rnd.uniform(-1.2, 1.2), rnd.uniform(0.0, 1.5), 0.05)) @ \
            Matrix.Rotation(rnd.uniform(0, 3), 4, "Z") @ Matrix.Rotation(math.radians(88), 4, "X")
        parts.append(kit.xform_geo(g, m))
    # one leg still standing and the top half propped up
    parts.append(kit._box_geo(0.06, 0.06, 0.86, 0.9, 0.0, 0))
    g = kit._box_geo(1.3, 0.8, 0.04, -0.65, -0.4, 0)
    parts.append(kit.xform_geo(g, Matrix.Translation((0.5, 0.35, 0.42)) @ Matrix.Rotation(math.radians(-24), 4, "X")
                               @ Matrix.Rotation(math.radians(18), 4, "Y")))
    v, f, _ = kit.merge(*parts)
    return obj_from(f"{name}Planks", (v, f), [mats["wood"]], parent=root)


# ---------- food on the stall ----------

def fruit_crate(name, location, mats, fruit_mats, rnd, rotten=False, kind=0):
    """Shallow crate (0.5 x 0.35 x 0.12) full of fruit (icospheres of 80 faces). rotten: Z 0.7, sunken (color in the material)."""
    root = _empty(name, location)
    parts = [kit._box_geo(0.5, 0.35, 0.02, -0.25, -0.175, 0)]
    for (x, y, sx, sy) in ((-0.25, -0.175, 0.5, 0.015), (-0.25, 0.16, 0.5, 0.015), (-0.25, -0.175, 0.015, 0.35),
                           (0.235, -0.175, 0.015, 0.35)):
        parts.append(kit._box_geo(sx, sy, 0.12, x, y, 0))
    v, f, _ = kit.merge(*parts)
    obj_from(f"{name}Box", (v, f), [mats["wood"]], parent=root)
    fr = []
    r = (0.042, 0.038, 0.05, 0.035)[kind % 4]
    nx, ny = int(0.46 / (2 * r)), int(0.31 / (2 * r))
    for layer in range(2):
        for i in range(nx - layer):
            for j in range(ny - layer):
                x = -0.23 + r + (i + 0.5 * layer) * 2 * r + rnd.uniform(-0.004, 0.004)
                y = -0.155 + r + (j + 0.5 * layer) * 2 * r + rnd.uniform(-0.004, 0.004)
                z = 0.02 + r * (0.7 if rotten else 1.0) + layer * r * (1.2 if rotten else 1.6)
                sz = (1.0, 1.0, 0.7) if rotten else (1.0, 1.0, 1.0 if kind != 3 else 1.25)
                if rotten:
                    z -= 0.01 * layer
                fr.append(lumpy_ico(r * rnd.uniform(0.92, 1.06), (x, y, z), sz, rnd, 0.07 if not rotten else 0.14))
    v, f, _ = kit.merge(*fr)
    fo = obj_from(f"{name}Fruit", (v, f), [fruit_mats[kind % len(fruit_mats)]], parent=root)
    return root, fo


def rotten_fruit_mat(name, color):
    """Soft fruit (art.md section 1.3): -35% value, -40% saturation, matte, 2-3 dark #3A2A22 blotches per fruit."""
    mat, n, L, p = node_mat(name, 0.85, 0.1)
    hsv = n.new("ShaderNodeHueSaturation")
    hsv.inputs["Color"].default_value = lin(color)
    hsv.inputs["Saturation"].default_value = 0.6
    hsv.inputs["Value"].default_value = 0.65
    brown = n.new("ShaderNodeMix"); brown.data_type = "RGBA"
    brown.inputs["Factor"].default_value = 0.3
    L.new(hsv.outputs["Color"], brown.inputs["A"])
    brown.inputs["B"].default_value = lin("#5A3E26")
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 11.0
    coord = n.new("ShaderNodeTexCoord")
    L.new(coord.outputs["Object"], vor.inputs["Vector"])
    spot = n.new("ShaderNodeMapRange")
    spot.inputs["From Min"].default_value, spot.inputs["From Max"].default_value = 0.17, 0.23
    L.new(vor.outputs["Distance"], spot.inputs["Value"])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(spot.outputs["Result"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = lin("#3A2A22")
    L.new(brown.outputs["Result"], mix.inputs["B"])
    L.new(mix.outputs["Result"], p.inputs["Base Color"])
    return mat


def brazier(name, location, mats, rnd):
    """Table brazier: 0.42 m metal bowl on 3 short legs, charcoal with emissive amber ember and mesh flame
    (stable, no point light). Returns (root, ember, flame) for the states."""
    root = _empty(name, location)
    ring = []
    n = 12
    rings = [[(0.12 * math.cos(2 * math.pi * i / n), 0.12 * math.sin(2 * math.pi * i / n), 0.1) for i in range(n)],
             [(0.2 * math.cos(2 * math.pi * i / n), 0.2 * math.sin(2 * math.pi * i / n), 0.2) for i in range(n)],
             [(0.21 * math.cos(2 * math.pi * i / n), 0.21 * math.sin(2 * math.pi * i / n), 0.24) for i in range(n)],
             [(0.18 * math.cos(2 * math.pi * i / n), 0.18 * math.sin(2 * math.pi * i / n), 0.235) for i in range(n)],
             [(0.11 * math.cos(2 * math.pi * i / n), 0.11 * math.sin(2 * math.pi * i / n), 0.14) for i in range(n)]]
    bowl = kit.loft_geo(rings, cap_start=True, cap_end=True)
    parts = [bowl]
    for k in range(3):
        a = 2 * math.pi * k / 3
        parts.append(kit.tube_geo([(0.12 * math.cos(a), 0.12 * math.sin(a), 0.12),
                                   (0.2 * math.cos(a), 0.2 * math.sin(a), 0.0)], [0.015, 0.015], n=5))
    v, f, _ = kit.merge(*parts)
    obj_from(f"{name}Bowl", (v, f), [mats["metal"]], parent=root)
    coal = []
    for k in range(16):
        a, rr = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 0.13)
        coal.append(kit._gem_geo(rnd.uniform(0.03, 0.045), oz=0.2 + rnd.uniform(0, 0.03), stretch=0.8,
                                 ox=rr * math.cos(a), oy=rr * math.sin(a)))
    v, f, own = kit.merge(*coal)
    # dark charcoal with 5 glowing pieces (amber, emission 1.0: in Standard above that it turns yellow)
    coals = obj_from(f"{name}Coal", (v, f), [mats["coal"], mats["ember"]], parent=root,
                     face_mats=[1 if o % 3 == 0 else 0 for o in own])
    fl = []
    for k, (dx, dy, r, h) in enumerate(((0.0, 0.0, 0.03, 0.09), (0.05, 0.03, 0.02, 0.05))):
        v, f = lumpy_ico(r, (dx, dy, 0.23 + h * 0.35), (1, 1, h / r * 0.6), rnd, 0.12)
        fl.append((v, f))
    v, f, _ = kit.merge(*fl)
    flame = obj_from(f"{name}Flame", (v, f), [mats["flame"]], parent=root)
    flame.visible_shadow = False
    coals.visible_shadow = True
    return SimpleNamespace(root=root, coal=coals, flame=flame)


def woodpile(name, location, mats, rnd, rows=4, per_row=7, half=False):
    """Pile of firewood against a low wall: 0.5 m x 10-15 cm logs, light ends with rings, dark bark; 5
    bracket fungi on the ends (same in the NOW/WEEK states). Front of the ends toward -y (toward the camera)."""
    root = _empty(name, location)
    bark, ends = [], []
    logs = []
    for r in range(rows if not half else rows // 2):
        n = per_row - (r % 2)
        for k in range(n):
            rad = rnd.uniform(0.055, 0.075)
            x = -0.5 + (k + 0.5 * (r % 2) + 0.5) * (1.0 / per_row) + rnd.uniform(-0.01, 0.01)
            z = rad + r * 0.125
            y0, y1 = rnd.uniform(-0.04, 0.03), 0.5 + rnd.uniform(-0.03, 0.04)
            g = kit._prism_geo(7, rad, rad, y1 - y0)
            m = Matrix.Translation((x, y0, z)) @ Matrix.Rotation(-math.pi / 2, 4, "X") @ \
                Matrix.Rotation(rnd.uniform(0, 1), 4, "Z")
            v, f = kit.xform_geo(g, m)
            bark.append((v, f[2:]))
            ends.append((v, f[:2]))
            logs.append((x, y0, z, rad))
    v, f, _ = kit.merge(*bark)
    b = obj_from(f"{name}Bark", (v, f), [mats["logbark"]], parent=root)
    v, f, _ = kit.merge(*ends)
    e = obj_from(f"{name}Ends", (v, f), [mats["logend"]], parent=root)
    kit.fix_normals(b)
    kit.fix_normals(e)
    fungi = []
    # on the upper rows and the left side (what shows above the counter, seen from the stall)
    up = sorted([lg for lg in logs if lg[2] > 0.5 and lg[0] < 0.05], key=lambda lg: (lg[0] * 3 + lg[2]))
    picks = up[::max(1, len(up) // 5)][:5]
    for k, (x, y0, z, rad) in enumerate(picks):
        fungi.append(fungus(f"{name}Fungus{k}", (x + rad * 0.3, y0 - 0.01, z + rad * 0.5), rnd.uniform(0.1, 0.15),
                            normal=(0.2, -1, 0.2), parent=root, spin=rnd.uniform(-0.5, 0.5)))
    return SimpleNamespace(root=root, fungi=fungi)


def fish_crate(name, location, mats, rnd):
    """Fish crate 0.5 x 0.35 x 0.15 with dark wet cloth and 5 silvery 25 cm fish (no ice)."""
    root = _empty(name, location)
    parts = [kit._box_geo(0.5, 0.35, 0.02, -0.25, -0.175, 0)]
    for (x, y, sx, sy) in ((-0.25, -0.175, 0.5, 0.015), (-0.25, 0.16, 0.5, 0.015), (-0.25, -0.175, 0.015, 0.35),
                           (0.235, -0.175, 0.015, 0.35)):
        parts.append(kit._box_geo(sx, sy, 0.15, x, y, 0))
    v, f, _ = kit.merge(*parts)
    obj_from(f"{name}Box", (v, f), [mats["wood"]], parent=root)
    cloth = kit.water_grid(f"{name}Cloth", -0.24, 0.24, -0.165, 0.165, 0.0, mats["cloth"], cell=0.06, amp=0.01, seed=3)
    cloth.location = (0, 0, 0.05)
    cloth.parent = root
    fish = []
    for k in range(5):
        y = -0.12 + 0.06 * k
        pts = [(-0.12, y, 0.07), (-0.06, y, 0.075), (0.06, y, 0.075), (0.11, y, 0.07)]
        body = kit.tube_geo(pts, [0.008, 0.026, 0.02, 0.006], n=6, squash=0.55)
        tail = ([(0.11, y, 0.07), (0.15, y - 0.025, 0.07), (0.15, y + 0.025, 0.07)], [(0, 1, 2)])
        fish.append(kit.xform_geo(kit.merge(body, tail)[:2], Matrix.Rotation(rnd.uniform(-0.15, 0.15), 4, "Z")))
    v, f, _ = kit.merge(*fish)
    obj_from(f"{name}Fish", (v, f), [mats["fish"]], parent=root)
    return root


# ---------- casas caiadas ----------

def house(name, location, size, mats, rnd, heading=0.0, roof="hip"):
    """Whitewashed stone house (sx, sy, sz): hip or shed terracotta roof with eaves, windows with
    open blue shutters, wooden door. Front toward -y (toward the square)."""
    sx, sy, sz = size
    root = _empty(name, location)
    root.rotation_euler = (0, 0, heading)
    obj_from(f"{name}Walls", kit._box_geo(sx, sy, sz, -sx / 2, -sy / 2, 0), [mats["wall"]], parent=root)
    ov = 0.35
    if roof == "hip":
        h = min(sx, sy) * 0.32
        v = [(-sx / 2 - ov, -sy / 2 - ov, sz), (sx / 2 + ov, -sy / 2 - ov, sz), (sx / 2 + ov, sy / 2 + ov, sz),
             (-sx / 2 - ov, sy / 2 + ov, sz)]
        ridge = max(sx - sy, 0) / 2
        v += [(-ridge, 0, sz + h), (ridge, 0, sz + h)]
        f = [(0, 1, 5, 4), (1, 2, 5), (2, 3, 4, 5), (3, 0, 4), (0, 3, 2, 1)]
    else:
        h = sy * 0.18
        v = [(-sx / 2 - ov, -sy / 2 - ov, sz + h), (sx / 2 + ov, -sy / 2 - ov, sz + h), (sx / 2 + ov, sy / 2 + ov, sz),
             (-sx / 2 - ov, sy / 2 + ov, sz)]
        v += [(x, y, z - 0.12) for x, y, z in v]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj_from(f"{name}Roof", (v, f), [mats["roof"]], parent=root)
    # windows (dark recess + 2 open shutters) and door, at the front (-y) and on the +x side
    parts_dark, parts_sh, parts_door = [], [], []
    floors = max(1, int(sz // 2.8))
    for fl in range(floors):
        z = 1.1 + fl * 2.8
        nwin = max(1, int(sx // 2.2))
        for k in range(nwin):
            x = -sx / 2 + sx * (k + 0.5) / nwin
            if fl == 0 and k == nwin // 2:
                parts_door.append(kit._box_geo(0.95, 0.06, 2.0, x - 0.475, -sy / 2 - 0.04, 0.0))
                continue
            parts_dark.append(kit._box_geo(0.7, 0.04, 1.0, x - 0.35, -sy / 2 - 0.02, z))
            ang = rnd.uniform(0.2, 0.9)
            for s in (-1, 1):
                g = kit._box_geo(0.36, 0.04, 1.02, 0 if s > 0 else -0.36, -0.02, 0)
                m = Matrix.Translation((x + s * 0.35, -sy / 2 - 0.03, z - 0.01)) @ Matrix.Rotation(s * ang, 4, "Z")
                parts_sh.append(kit.xform_geo(g, m))
    for k in range(max(1, int(sy // 3))):
        y = -sy / 2 + sy * (k + 0.5) / max(1, int(sy // 3))
        for fl in range(floors):
            parts_dark.append(kit._box_geo(0.04, 0.6, 0.9, sx / 2 - 0.02, y - 0.3, 1.2 + fl * 2.8))
            parts_sh.append(kit._box_geo(0.05, 0.32, 0.92, sx / 2 - 0.01, y - 0.62, 1.19 + fl * 2.8))
            parts_sh.append(kit._box_geo(0.05, 0.32, 0.92, sx / 2 - 0.01, y + 0.3, 1.19 + fl * 2.8))
    if parts_dark:
        v, f, _ = kit.merge(*parts_dark)
        obj_from(f"{name}Win", (v, f), [mats["window"]], parent=root)
    if parts_sh:
        v, f, _ = kit.merge(*parts_sh)
        obj_from(f"{name}Shutters", (v, f), [mats["shutter"]], parent=root)
    if parts_door:
        v, f, _ = kit.merge(*parts_door)
        obj_from(f"{name}Door", (v, f), [mats["door"]], parent=root)
    return root


def pot(name, location, mats, rnd, flowers=True):
    """Clay pot (0.4 m) with a tuft of plant and flowers (colors by state)."""
    root = _empty(name, location)
    rings = [[(r * math.cos(2 * math.pi * i / 8), r * math.sin(2 * math.pi * i / 8), z) for i in range(8)]
             for r, z in ((0.13, 0), (0.2, 0.32), (0.22, 0.36), (0.19, 0.36))]
    obj_from(f"{name}Pot", kit.loft_geo(rings), [mats["terracotta"]], parent=root)
    obj_from(f"{name}Bush", lumpy_ico(0.24, (0, 0, 0.52), (1, 1, 0.8), rnd, 0.25), [mats["hedge"]], parent=root)
    if flowers:
        fl = [kit._ico_geo(0.045, (0.18 * math.cos(a), 0.18 * math.sin(a), 0.62 + rnd.uniform(-0.05, 0.08)))
              for a in [rnd.uniform(0, 6.28) for _ in range(7)]]
        v, f, _ = kit.merge(*fl)
        obj_from(f"{name}Flowers", (v, f), [mats["flower" if rnd.random() < 0.6 else "flower2"]], parent=root)
    return root
