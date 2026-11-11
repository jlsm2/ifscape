"""Low-poly red oak (Quercus rubra): trunk with furrowed bark, limbs, crown in masses and lobed leaves.

SOURCE: procedural (Ifscape, viruses-disappeared, 2026-10-24).
Proportions: Quercus rubra 20-28 m, trunk 0.5-1 m; leaf 12-20 cm, 7-11 pointed lobes (with bristle), notches down to
half the distance to the midrib (https://en.wikipedia.org/wiki/Quercus_rubra). Small-town street tree:
here ~14 m with a 9-10 m crown (fits in H1 above the shop roof). Low-poly references: Quaternius
Stylized Nature MegaKit (crown in faceted masses, 2 tones), Kenney Nature Kit (chamfered trunk with root).
Colors (art.md §2): bark #6E665C with vertical cracks (noise 1:6), leaf #5A8A3C.

Parts:
- leaf_geo(length, width, rnd, rows, cols): lobed leaf in a grid (base at the origin, tip at +x, face at +z, V fold
  along the midrib and curve); cols = 1 for cheap background leaves.
- leaf_matrix(base, direction, normal): places the leaf.
- trunk_geo(...): trunk with furrows and roots; limb_geo = gnarled branch (tube_geo with kinks).
- bark_mat(), leaf_mat(): materials.
"""

import math

import bpy
from mathutils import Matrix, Vector

import kit
from kit import lin


# ---------- leaf ----------

def _leaf_halfwidth(u, lobes, phase, depth=0.5):
    """Half width at u (0 = base, 1 = tip): oval envelope x pointed lobes (peak = lobe tip)."""
    env = math.sin(math.pi * min(1.0, u ** 0.85)) ** 0.75
    if u > 0.9:                                        # lobe at the tip tapering
        env *= (1.0 - u) / 0.1 * 0.6 + 0.4 * (1.0 - u) / 0.1
    x = u * lobes + phase
    t = abs(2 * (x - math.floor(x)) - 1)               # 1 at the middle of the notch, 0 at the lobe tip
    lobe = 1.0 - depth * t ** 0.7
    if u < 0.12:
        lobe = 1.0 - depth * 0.6
    return max(0.0, env * lobe)


def leaf_uv_rows(lobes=3.5, rows=36):
    """Stations along the leaf including the lobe tips and notches (the outline does not cut the peak)."""
    us = {i / rows for i in range(rows + 1)}
    for k in range(int(lobes * 2) + 2):
        u = k / (2 * lobes)
        if 0 < u < 1:
            us.add(u)
    return sorted(us)


def leaf_geo(length, width, rnd=None, rows=30, cols=5, fold=0.16, curl=0.10, lobes=3.5, depth=0.55):
    """Grid (rows x 2*cols+1) of the leaf; sides with slightly offset lobes. Returns verts, faces."""
    import random
    rnd = rnd or random.Random(0)
    ph = (rnd.uniform(-0.08, 0.08), 0.5 + rnd.uniform(-0.08, 0.08))
    us = leaf_uv_rows(lobes, rows)
    verts, faces = [], []
    n = 2 * cols + 1
    for u in us:
        wl = _leaf_halfwidth(u, lobes, ph[0], depth) * width * 0.5
        wr = _leaf_halfwidth(u, lobes, ph[1], depth) * width * 0.5
        for j in range(-cols, cols + 1):
            v = (j / cols) * (wr if j > 0 else wl)
            x = u * length
            z = fold * abs(v) - curl * length * (u - 0.45) ** 2
            verts.append((x, v, z))
    for i in range(len(us) - 1):
        for j in range(n - 1):
            a = i * n + j
            faces.append((a, a + 1, a + 1 + n, a + n))
    return verts, faces


def leaf_matrix(base, direction, normal, roll=0.0):
    x = Vector(direction).normalized()
    z = Vector(normal)
    z = (z - x * z.dot(x)).normalized()
    if roll:
        z = (Matrix.Rotation(roll, 3, x) @ z)
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(base)
    return m


def xform(geo, m):
    v, f = geo[0], geo[1]
    return [tuple(m @ Vector(p)) for p in v], f


def leaf_mat(name="OakLeaf", color="#5A8A3C", back="#8DB04E", mix=0.28):
    """Matte leaf with a little translucency (backlight from the sky and sun lights up the leaf), double-sided."""
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    p = kit.principled(mat)
    p.inputs["Roughness"].default_value = 0.75
    p.inputs["Specular IOR Level"].default_value = 0.15
    # tone variation per object/face (±8%)
    info = n.new("ShaderNodeObjectInfo")
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.88, 1.08
    L.new(info.outputs["Random"], mr.inputs["Value"])
    rgb = n.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = lin(color)
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L.new(rgb.outputs[0], mul.inputs["A"])
    L.new(mr.outputs["Result"], mul.inputs["B"])
    L.new(mul.outputs["Result"], p.inputs["Base Color"])
    tr = n.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = lin(back)
    mx = n.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = mix
    out = next(nd for nd in n if nd.type == "OUTPUT_MATERIAL")
    L.new(p.outputs[0], mx.inputs[1])
    L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


# ---------- bark and trunk ----------

def bark_mat(name="OakBark", color="#8A847A", crack="#4A443E"):
    """Red oak bark: long light vertical ridges (Voronoi stretched 1:12) between dark furrows
    and large ±10% patches."""
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    p = kit.principled(mat)
    p.inputs["Roughness"].default_value = 0.95
    p.inputs["Specular IOR Level"].default_value = 0.1
    coord = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (12.0, 12.0, 1.0)
    L.new(coord.outputs["Object"], mp.inputs["Vector"])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 2.4
    vor.inputs["Randomness"].default_value = 0.9
    L.new(mp.outputs[0], vor.inputs["Vector"])
    cr = n.new("ShaderNodeMapRange")
    cr.inputs["From Min"].default_value, cr.inputs["From Max"].default_value = 0.03, 0.12
    L.new(vor.outputs["Distance"], cr.inputs["Value"])
    noi = n.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 1.6
    L.new(coord.outputs["Object"], noi.inputs["Vector"])
    nm = n.new("ShaderNodeMapRange")
    nm.inputs["To Min"].default_value, nm.inputs["To Max"].default_value = 0.86, 1.1
    L.new(noi.outputs["Fac"], nm.inputs["Value"])
    a = n.new("ShaderNodeRGB")
    a.outputs[0].default_value = lin(crack)
    b = n.new("ShaderNodeRGB")
    b.outputs[0].default_value = lin(color)
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(cr.outputs["Result"], mix.inputs["Factor"])
    L.new(a.outputs[0], mix.inputs["A"])
    L.new(b.outputs[0], mix.inputs["B"])
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L.new(mix.outputs["Result"], mul.inputs["A"])
    L.new(nm.outputs["Result"], mul.inputs["B"])
    L.new(mul.outputs["Result"], p.inputs["Base Color"])
    return mat


def trunk_geo(base, height, r0, r1, rnd, n=16, rings=9, lean=(0.0, 0.0), ridge=0.05, flare=1.45):
    """Trunk with furrows (radius alternates 1 / 1 - ridge, with noise) and roots at the base (flare). Origin at the foot."""
    bx, by, bz = base
    out_rings = []
    offs = [rnd.uniform(-0.02, 0.02) for _ in range(n)]
    for k in range(rings + 1):
        t = k / rings
        z = height * t
        r = r0 + (r1 - r0) * t
        if t < 0.12:
            r *= 1.0 + (flare - 1.0) * (1.0 - t / 0.12) ** 2
        cx, cy = bx + lean[0] * t * t, by + lean[1] * t * t
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r * (1.0 - (ridge if i % 2 else 0.0) + offs[i])
            if t < 0.12 and i % 4 == 0:                # root emerging
                rr *= 1.0 + 0.35 * (1.0 - t / 0.12)
            ring.append((cx + rr * math.cos(a), cy + rr * math.sin(a), bz + z - (0.02 if k == 0 else 0.0)))
        out_rings.append(ring)
    return kit.loft_geo(out_rings, cap_start=False)


def radius_at(z, height, r0, r1, ridge=0.05):
    """Outer radius (ridge) of the trunk at height z (without the base flare)."""
    t = max(0.0, min(1.0, z / height))
    return r0 + (r1 - r0) * t


def limb_geo(points, radii, rnd, n=7, kink=0.12):
    """Gnarled branch: breaks each segment into 2 with a lateral offset (oak zigzag)."""
    pts, rad = [], []
    for k in range(len(points) - 1):
        a, b = Vector(points[k]), Vector(points[k + 1])
        pts.append(tuple(a))
        rad.append(radii[k])
        d = b - a
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        up = side.cross(d).normalized()
        m = a.lerp(b, 0.5) + side * d.length * rnd.uniform(-kink, kink) + up * d.length * rnd.uniform(-kink, kink) * 0.6
        pts.append(tuple(m))
        rad.append(0.5 * (radii[k] + radii[k + 1]))
    pts.append(tuple(points[-1]))
    rad.append(radii[-1])
    return kit.tube_geo(pts, rad, n=n), pts, rad
