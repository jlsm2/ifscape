"""Final models for moon-disappeared (rural pier at night): owl, mice, fishing boat, lantern, crate, Moon with
maria, Sun with halo, globe, water-reflection materials. Importable by the scene (moon-disappeared.py) and by the showcase
(preview_models.py moon).

Proportions (direction.md, section 5, and low-poly references):
- Owl: great horned owl (Bubo virginianus) 0.30 m seated, rust-colored facial disc, ear tufts, yellow eyes;
  in the scene x2 (0.6 m, exaggeration marked by the director). Ref.: https://en.wikipedia.org/wiki/Great_horned_owl and
  Quaternius's low-poly owl (Animals pack, poly.pizza) for the flat-plane silhouette.
- Mouse: body 8 to 10 cm + tail ~8 cm, hip height ~2 cm. Ref.: https://en.wikipedia.org/wiki/House_mouse;
  Quaternius's Rat (assets/polypizza/quaternius-animals) for the big ear and thin snout.
- Coastal fishing boat (small trawler) of 8 m: wheelhouse toward the bow, gantry at the stern, mast with light.
  Ref.: https://en.wikipedia.org/wiki/Fishing_trawler and Kenney Watercraft Kit (silhouette).
- Globe: today's continents from globe.py (hand-drawn outlines), ocean, ice; 25% emissive + atmosphere ring.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
from kit import lin


# ---------- materials ----------

def node_mat(name):
    """Material with a clean node tree (output only). Returns (mat, nodes, links, output)."""
    mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes") and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return mat, nt.nodes, nt.links, out


def fade_emitter(name, color, strength=1.0):
    """Emission that vanishes by transparency (no black disc): Mix(Transparent, Emission, fac). Returns
    (mat, strength socket, fac 0..1 socket)."""
    mat, n, links, out = node_mat(name)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    em.inputs["Strength"].default_value = strength
    clear = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 1.0
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    return mat, em.inputs["Strength"], mix.inputs["Fac"]


def lit(name, color, rough=0.9, glow=0.0):
    """Flat color with a bit of its own color as emission (night readability without changing the scene light)."""
    return kit.flat(name, color, rough=rough, emission=color if glow else None, strength=glow)


def _math(n, links, op, a, b=None, value=None):
    m = n.new("ShaderNodeMath")
    m.operation = op
    for k, src in enumerate((a, b)):
        if src is None:
            continue
        if isinstance(src, (int, float)):
            m.inputs[k].default_value = src
        else:
            links.new(src, m.inputs[k])
    if value is not None:
        m.inputs[1].default_value = value
    return m.outputs[0]


def _madd(n, links, a, b, c):
    """a * b + c with b and c numbers (the 3-argument _math overwrites the multiplier with the additive)."""
    m = n.new("ShaderNodeMath")
    m.operation = "MULTIPLY_ADD"
    links.new(a, m.inputs[0])
    m.inputs[1].default_value, m.inputs[2].default_value = b, c
    return m.outputs[0]


def glitter_mat(name, color, sigma0, sigma_k, far0, far1, seed=0.0, near_fade=None, density=0.56, lat_freq=0.55,
                rise=None, soft=0.08, ragged=0.0, true_sigma=False):
    """Light reflection on the sea (silver path of the Moon, amber column of the lamp and the boat), in object coordinates:
    origin at the observer, +y along the reflection. Gaussian band (width sigma0 + sigma_k*y) cut into horizontal
    glints (stretched 4D noise: narrow in depth, wide sideways) that merge into a continuous band from
    far0 to far1 m (near the horizon). Additive (Transparent + Emission). Returns (mat, strength, noise W phase).
    lat_freq: lateral noise frequency (smaller = stripes wider than the column); rise=(y0, y1): fades in smoothly from 0 to 1
    between y0 and y1 (no straight edge at the tip near the observer)."""
    mat, n, links, out = node_mat(name)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    x, y = sep.outputs["X"], sep.outputs["Y"]
    ya = _math(n, links, "MAXIMUM", y, value=0.5)
    # (legacy: with true_sigma=False sigma comes out as ya*sigma0, the band is limited only by the mesh; the Moon and the boat were approved
    # like this. true_sigma=True gives a real sigma0 + sigma_k*y, with a Gaussian edge: used on the lamp)
    sig = _madd(n, links, ya, sigma_k, sigma0) if true_sigma else _math(n, links, "MULTIPLY_ADD", ya, sigma_k, sigma0)
    lny = _math(n, links, "LOGARITHM", ya, value=math.e)
    if ragged:                                       # each stripe with its own width and offset: edges without a straight line
        def row_noise(z):
            cb = n.new("ShaderNodeCombineXYZ")
            cb.inputs["X"].default_value = 3.7 * z
            links.new(_math(n, links, "MULTIPLY", lny, value=16.0), cb.inputs["Y"])
            cb.inputs["Z"].default_value = seed + z
            nz = n.new("ShaderNodeTexNoise")
            nz.noise_dimensions = "3D"
            nz.inputs["Scale"].default_value = 1.0
            nz.inputs["Detail"].default_value = 0.0
            links.new(cb.outputs[0], nz.inputs["Vector"])
            return nz.outputs["Fac"]
        wf = _madd(n, links, row_noise(11.0), 2.0 * ragged, 1.0 - ragged)                          # 1 +- ragged
        shift = _math(n, links, "MULTIPLY", _math(n, links, "SUBTRACT", row_noise(23.0), value=0.5), sig)
        shift = _math(n, links, "MULTIPLY", shift, value=1.2 * ragged)
        xs = _math(n, links, "SUBTRACT", x, shift)
        lat = _math(n, links, "DIVIDE", xs, _math(n, links, "MULTIPLY", sig, wf))
    else:
        lat = _math(n, links, "DIVIDE", x, sig)
    lat2 = _math(n, links, "MULTIPLY", lat, lat)
    core = _math(n, links, "EXPONENT", _math(n, links, "MULTIPLY", lat2, value=-0.5))
    # glints: noise with y in log (the bands shrink with distance like waves) and x in sigma units
    comb = n.new("ShaderNodeCombineXYZ")
    links.new(_math(n, links, "MULTIPLY", lat, value=lat_freq), comb.inputs["X"])
    links.new(_math(n, links, "MULTIPLY", lny, value=16.0), comb.inputs["Y"])
    comb.inputs["Z"].default_value = seed
    noise = n.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 1.0
    noise.inputs["Roughness"].default_value = 0.4
    links.new(comb.outputs[0], noise.inputs["Vector"])
    phase = noise.inputs["W"]
    glint = n.new("ShaderNodeMapRange")
    glint.inputs["From Min"].default_value, glint.inputs["From Max"].default_value = density, density + soft
    links.new(noise.outputs["Fac"], glint.inputs["Value"])
    far = n.new("ShaderNodeMapRange")
    far.inputs["From Min"].default_value, far.inputs["From Max"].default_value = far0, far1
    far.inputs["To Min"].default_value, far.inputs["To Max"].default_value = 0.0, 0.8
    links.new(ya, far.inputs["Value"])
    g = _math(n, links, "MAXIMUM", glint.outputs["Result"], far.outputs["Result"])
    mask = _math(n, links, "MULTIPLY", g, core)
    if near_fade:                                    # short column (lamp, boat): fades far away
        nf = n.new("ShaderNodeMapRange")
        nf.inputs["From Min"].default_value, nf.inputs["From Max"].default_value = near_fade
        nf.inputs["To Min"].default_value, nf.inputs["To Max"].default_value = 1.0, 0.0
        links.new(ya, nf.inputs["Value"])
        mask = _math(n, links, "MULTIPLY", mask, nf.outputs["Result"])
    if rise:                                         # fades in smoothly (no straight cut at the near tip)
        rs = n.new("ShaderNodeMapRange")
        rs.inputs["From Min"].default_value, rs.inputs["From Max"].default_value = rise
        rs.inputs["To Min"].default_value, rs.inputs["To Max"].default_value = 0.0, 1.0
        links.new(ya, rs.inputs["Value"])
        mask = _math(n, links, "MULTIPLY", mask, rs.outputs["Result"])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    strength = n.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    links.new(mask, strength.inputs[0])
    strength.inputs[1].default_value = 1.0
    links.new(strength.outputs[0], em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    clear = n.new("ShaderNodeBsdfTransparent")
    links.new(clear.outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    return mat, strength.inputs[1], phase


def halo(name, color, radius, location, power=3.0):
    """Soft additive halo around a light: sphere without a back face whose emission falls with the angle between the normal and the
    view (strong center, zero edge), no shadow. Returns (object, strength socket)."""
    mat, n, links, out = node_mat(name)
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(geo.outputs["Normal"], dot.inputs[0])
    links.new(geo.outputs["Incoming"], dot.inputs[1])
    f = _math(n, links, "ABSOLUTE", dot.outputs["Value"])
    f = _math(n, links, "POWER", f, value=power)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    k = _math(n, links, "MULTIPLY", f, value=1.0)
    links.new(k, em.inputs["Strength"])
    mulnode = k.node
    add = n.new("ShaderNodeAddShader")
    clear = n.new("ShaderNodeBsdfTransparent")
    links.new(clear.outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = location
    o.visible_shadow = False
    bpy.context.collection.objects.link(o)
    return o, mulnode.inputs[1]


def strip_mesh(name, y0, y1, half_w, mat, steps=40, z=0.0):
    """Flat strip along +y (from y0 to y1, geometric spacing) with half-width half_w(y)."""
    verts, faces = [], []
    for i in range(steps + 1):
        y = y0 * (y1 / y0) ** (i / steps)
        w = half_w(y)
        verts += [(-w, y, z), (w, y, z)]
    for i in range(steps):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    o = kit.mesh_object(name, verts, faces, [mat])
    o.visible_shadow = False
    return o


# ---------- owl ----------

OWL_BODY = "#8A6A48"
OWL_WING = "#5E4732"
OWL_TIP = "#3E2F22"
OWL_BELLY = "#C9B79A"          # chest (art.md C)
OWL_BAR = "#B7A483"
OWL_SPOT = "#6B5440"           # V-shaped chest spots
OWL_BACK2 = "#76593C"          # second tone of the back
OWL_DISC = "#C8935A"
OWL_RIM = "#3A2A1C"


def _body_rings(spec, n=12):
    """spec = [(z, yc, rx, ry)] -> elliptical rings (n points) for loft_geo."""
    rings = []
    for z, yc, rx, ry in spec:
        rings.append([(rx * math.cos(2 * math.pi * i / n + math.pi / n), yc + ry * math.sin(2 * math.pi * i / n + math.pi / n), z)
                      for i in range(n)])
    return rings


OWL_SPEC = [(0.004, 0.006, 0.040, 0.032), (0.022, 0.0, 0.062, 0.050), (0.048, -0.006, 0.075, 0.060),
            (0.080, -0.008, 0.079, 0.064), (0.112, -0.006, 0.076, 0.062), (0.142, -0.002, 0.068, 0.057),
            (0.170, 0.002, 0.060, 0.053), (0.195, 0.004, 0.054, 0.048), (0.218, 0.004, 0.042, 0.040)]


def _owl_rx(z):
    pts = OWL_SPEC
    if z <= pts[0][0]:
        return pts[0][2], pts[0][3], pts[0][1]
    for a, b in zip(pts, pts[1:]):
        if a[0] <= z <= b[0]:
            u = (z - a[0]) / (b[0] - a[0])
            return a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u, a[1] + (b[1] - a[1]) * u
    return pts[-1][2], pts[-1][3], pts[-1][1]


def _wing_geo(side):
    """Folded wing: plate with feather outline (primary tips zigzagging) glued to the side of the body."""
    outline = [(-0.030, 0.165), (0.004, 0.186), (0.046, 0.160), (0.074, 0.105), (0.080, 0.040), (0.070, -0.012),
               (0.060, -0.050), (0.046, -0.022), (0.036, -0.056), (0.022, -0.020), (0.010, -0.040), (0.000, 0.000),
               (-0.022, 0.050), (-0.036, 0.110)]
    outer, inner = [], []
    for yy, zz in outline:
        rx, ry, yc = _owl_rx(min(max(zz, 0.004), 0.21))
        t = (yy - yc) / ry if ry else 0
        xs = rx * math.sqrt(max(0.0, 1 - min(t * t, 0.92))) if abs(t) < 1 else rx * 0.28
        x = max(xs, 0.018) + 0.007
        outer.append((side * x, yy, zz))
        inner.append((side * (x - 0.012), yy, zz))
    cy, cz = sum(p[0] for p in outline) / len(outline), 0.07
    rx, _, _ = _owl_rx(cz)
    c_out, c_in = (side * (rx + 0.008), cy, cz), (side * (rx - 0.004), cy, cz)
    verts = outer + inner + [c_out, c_in]
    k = len(outline)
    co, ci = 2 * k, 2 * k + 1
    faces = []
    for i in range(k):
        j = (i + 1) % k
        faces.append((co, i, j) if side > 0 else (co, j, i))
        faces.append((ci, k + j, k + i) if side > 0 else (ci, k + i, k + j))
        faces.append((i, k + i, k + j, j))
    return verts, faces


def owl(name="Owl"):
    """Seated owl (0.30 m; the scene scales x2). Origin at the feet, face toward -y. Head = child with pivot at the neck
    (z 0.2), with eyelids (children) to blink. Returns SimpleNamespace(root, neck, lids)."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    m_body, m_wing, m_tip = lit(name + "Body", OWL_BODY, glow=0.18), lit(name + "Wing", OWL_WING, glow=0.15), \
        lit(name + "Tip", OWL_TIP, glow=0.1)
    m_belly, m_bar = lit(name + "Belly", OWL_BELLY, glow=0.2), lit(name + "Bar", OWL_BAR, glow=0.18)
    m_spot, m_back2 = lit(name + "Spot", OWL_SPOT, glow=0.1), lit(name + "Back2", OWL_BACK2, glow=0.15)
    m_claw = kit.flat(name + "Claw", "#2B2724", rough=0.5)
    # body: loft; front faces in light belly with bars
    v, f = kit.loft_geo(_body_rings(OWL_SPEC))
    mats = []
    for face in f:
        c = [sum(v[i][k] for i in face) / len(face) for k in range(3)]
        front = c[1] < -0.022 and 0.015 < c[2] < 0.185 and abs(c[0]) < 0.06
        if front:
            row = int((c[2] - 0.015) / 0.018)
            mats.append(4 if row % 2 else 3)
        else:
            row = int((c[2] + 0.01) / 0.03)
            mats.append(6 if row % 2 else 0)               # back in 2 tones, in wide bands
    wl, wr = _wing_geo(-1), _wing_geo(1)
    tail = ([(-0.03, 0.035, 0.02), (0.03, 0.035, 0.02), (0.022, 0.07, -0.05), (0.0, 0.075, -0.06), (-0.022, 0.07, -0.05)],
            [(0, 1, 2, 3, 4)])
    tail2 = ([(x, y + 0.006, z) for x, y, z in tail[0]], [(4, 3, 2, 1, 0)])
    parts = [(v, f), wl, wr, tail, tail2]
    allv, allf, own = kit.merge(*parts)
    face_mats = mats + [1 if c[2] > 0.0 else 2 for c in
                        ([sum(allv[i][k] for i in face) / len(face) for k in range(3)] for face in allf[len(f):])]
    # V-shaped spots on the chest: 2 rows of dark chevrons glued to the front of the body (2 mm outward)
    def chest_pt(x, z):
        rx, ry, yc = _owl_rx(z)
        t = min(abs(x) / rx, 0.95)
        return (x, yc - ry * math.sqrt(1 - t * t) - 0.002, z)

    chev = []
    for zr, xs in ((0.125, (-0.03, -0.01, 0.01, 0.03)), (0.098, (-0.04, -0.02, 0.0, 0.02, 0.04)), (0.071, (-0.03, -0.01, 0.01, 0.03))):
        for xc in xs:
            for sx in (-1, 1):                         # each arm of the V is a thin strip
                a0, a1 = (xc, zr - 0.006), (xc + sx * 0.008, zr + 0.002)
                p0, p1 = chest_pt(*a0), chest_pt(*a1)
                w_ = 0.0022
                chev.append(([(p0[0], p0[1], p0[2] - w_), (p1[0], p1[1], p1[2] - w_), (p1[0], p1[1], p1[2] + w_),
                              (p0[0], p0[1], p0[2] + w_)], [(0, 1, 2, 3)]))
    cv, cf, _ = kit.merge(*chev)
    allv2 = allv + cv
    allf2 = allf + [tuple(i + len(allv) for i in fc) for fc in cf]
    body = kit.mesh_object(name + "BodyMesh", allv2, allf2, [m_body, m_wing, m_tip, m_belly, m_bar, m_spot, m_back2],
                           face_mats=face_mats + [5] * len(cf))
    kit.fix_normals(body)
    body.parent = root
    # feet: short feathered leg + 3 talons in front gripping the edge of the post (+1 behind)
    feet = []
    for sx in (-1, 1):
        x0 = sx * 0.028
        feet.append((kit._prism_geo(6, 0.017, 0.014, 0.034, oz=-0.002, ox=x0, oy=-0.012), 0))
        for k, dx in enumerate((-0.012, 0.0, 0.012)):
            pts = [(x0 + dx, -0.018, 0.006), (x0 + dx * 1.2, -0.031, 0.005), (x0 + dx * 1.25, -0.037, -0.004),
                   (x0 + dx * 1.25, -0.034, -0.013)]
            feet.append((kit.tube_geo(pts, [0.0045, 0.0038, 0.003, 0.0012], n=5), 1))
        pts = [(x0, -0.004, 0.005), (x0, 0.012, 0.004), (x0, 0.02, -0.006)]
        feet.append((kit.tube_geo(pts, [0.004, 0.003, 0.0012], n=5), 1))
    fv, ff, fo = kit.merge(*[g for g, _ in feet])
    kinds = [feet[o][1] for o in fo]
    kit.mesh_object(name + "Feet", fv, ff, [m_belly, m_claw], face_mats=kinds).parent = root
    # head
    neck = bpy.data.objects.new(name + "Head", None)
    bpy.context.collection.objects.link(neck)
    neck.parent = root
    neck.location = (0, 0, 0.2)
    neck.rotation_mode = "XYZ"
    m_disc, m_rim = lit(name + "Disc", OWL_DISC, glow=0.25), lit(name + "Rim", OWL_RIM, glow=0.05)
    m_eye = kit.flat(name + "Eye", "#F2C230", emission="#F2C230", strength=1.4)
    m_pupil, m_beak = kit.flat(name + "Pupil", "#0C0C0A", rough=0.3), kit.flat(name + "Beak", "#3B3530", rough=0.5)
    hp0 = [(kit._ico_geo(1.0, (0, 0, 0.062), (0.064, 0.057, 0.058)), 0),                       # skull
          (kit._ico_geo(1.0, (0, -0.036, 0.060), (0.056, 0.018, 0.050)), 2),                  # dark rim of the disc
          (kit._ico_geo(1.0, (0, -0.041, 0.060), (0.050, 0.016, 0.045)), 1),                  # facial disc
          (kit._ico_geo(1.0, (-0.022, -0.054, 0.068), (0.017, 0.009, 0.017)), 3),             # eyes
          (kit._ico_geo(1.0, (0.022, -0.054, 0.068), (0.017, 0.009, 0.017)), 3),
          (kit._ico_geo(1.0, (-0.022, -0.061, 0.068), (0.0085, 0.004, 0.0095)), 4),           # pupils
          (kit._ico_geo(1.0, (0.022, -0.061, 0.068), (0.0085, 0.004, 0.0095)), 4),
          (kit._ico_geo(1.0, (0, -0.053, 0.088), (0.026, 0.008, 0.007)), 2),                  # V-shaped brow
          (kit.tube_geo([(0, -0.055, 0.062), (0, -0.066, 0.053), (0, -0.063, 0.040)], [0.0085, 0.0055, 0.0012], n=5), 5),
          (kit.tube_geo([(-0.030, -0.012, 0.100), (-0.040, -0.008, 0.128), (-0.050, -0.002, 0.152)],
                        [0.014, 0.009, 0.0015], n=5, squash=0.5), 0),                         # ear tufts
          (kit.tube_geo([(0.030, -0.012, 0.100), (0.040, -0.008, 0.128), (0.050, -0.002, 0.152)],
                        [0.014, 0.009, 0.0015], n=5, squash=0.5), 0)]
    S, DZ = 1.1, -0.016                                   # head 10% bigger and sunk into the body
    hp = [(([(x * S, y * S, z * S + DZ) for x, y, z in g[0]], g[1]), k) for g, k in hp0]
    v, f, own = kit.merge(*[g for g, _ in hp])
    head = kit.mesh_object(name + "HeadMesh", v, f, [m_body, m_disc, m_rim, m_eye, m_pupil, m_beak],
                           face_mats=[hp[o][1] for o in own])
    head.parent = neck
    lids = []
    for sx in (-1, 1):
        # eyelid: half sphere that comes down from the top of the eye (origin at the top; z scale 0.05 = open, 1 = closed)
        g = kit._ico_geo(1.0, (0, 0, -0.0175), (0.0185, 0.0105, 0.0185))
        g = ([(x * 1.1, y * 1.1, z * 1.1) for x, y, z in g[0]], g[1])
        lid = kit.mesh_object(f"{name}Lid{sx}", g[0], g[1], [m_disc], (sx * 0.022 * 1.1, -0.0545 * 1.1, 0.0855 * 1.1 - 0.016))
        lid.parent = neck
        lid.scale = (1, 1, 0.05)
        lids.append(lid)
    return SimpleNamespace(root=root, neck=neck, lids=lids, head=head, body=body)


# ---------- mouse ----------

MOUSE_FUR = "#8E8073"          # gray-brown field mouse (art.md C: the white one was a lab mouse)
MOUSE_BELLY = "#B9AE9F"
MOUSE_PINK = "#C9A49A"

# body profile along +y (front): (y, half-width, top z, bottom z) in real meters (10 cm body)
MOUSE_PROFILE = [(-0.052, 0.006, 0.020, 0.012), (-0.046, 0.016, 0.030, 0.008), (-0.034, 0.023, 0.037, 0.007),
                 (-0.016, 0.024, 0.038, 0.008), (0.002, 0.021, 0.035, 0.010), (0.018, 0.017, 0.031, 0.012),
                 (0.030, 0.015, 0.031, 0.013), (0.040, 0.014, 0.030, 0.012), (0.050, 0.010, 0.026, 0.012),
                 (0.058, 0.006, 0.021, 0.013), (0.064, 0.002, 0.017, 0.014)]
MOUSE_HIP_Z = 0.016
MOUSE_LEGS = {"LF": (-0.012, 0.026), "RF": (0.012, 0.026), "LH": (-0.016, -0.030), "RH": (0.016, -0.030)}


def _mouse_rings(n=8):
    rings = []
    for y, hw, zt, zb in MOUSE_PROFILE:
        zc, hz = (zt + zb) / 2, (zt - zb) / 2
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            z = zc + hz * math.sin(a)
            x = hw * math.cos(a) * (0.86 if math.sin(a) < 0 else 1.0)       # flatter belly
            ring.append((x, y, z))
        rings.append(ring)
    return rings


def mouse(name, s=1.5, glow=0.1):
    """Low-poly mouse (continuous body with head, ears, eyes, nose), scale s. Legs and tail are children with
    the pivot at the joint (hip and shoulder on the side of the body; tail base). Front = local +y. Returns SimpleNamespace."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.scale = (s, s, s)
    fur = kit.flat(name + "Fur", MOUSE_FUR, rough=0.95, emission=MOUSE_FUR, strength=glow)
    pink = kit.flat(name + "Pink", MOUSE_PINK, rough=0.8, emission=MOUSE_PINK, strength=glow * 0.8)
    eye = kit.flat(name + "Eye", "#0A0A0C", rough=0.2)
    belly = kit.flat(name + "Belly", MOUSE_BELLY, rough=0.95, emission=MOUSE_BELLY, strength=glow)
    shine = kit.flat(name + "Shine", "#FFFFFF", emission="#F4F6F8", strength=0.8)
    pivot = bpy.data.objects.new(name + "Body", None)          # body sway (rises and falls, breathes)
    bpy.context.collection.objects.link(pivot)
    pivot.parent = root
    v, f = kit.loft_geo(_mouse_rings())
    ears = []
    for sx in (-1, 1):
        ears.append(kit._ico_geo(1.0, (sx * 0.011, 0.038, 0.037), (0.010, 0.0035, 0.011)))
        ears.append(kit._ico_geo(1.0, (sx * 0.011, 0.0365, 0.037), (0.0065, 0.002, 0.0075)))   # pink inside
    eyes = [kit._ico_geo(1.0, (sx * 0.0085, 0.050, 0.023), (0.0032, 0.0032, 0.0032)) for sx in (-1, 1)]
    nose = kit._ico_geo(1.0, (0, 0.065, 0.0165), (0.0032, 0.003, 0.003))
    glints = [kit._ico_geo(1.0, (sx * 0.0098, 0.0528, 0.0245), (0.0011, 0.0011, 0.0011)) for sx in (-1, 1)]   # 1 glint in the eye
    parts = [(v, f), ears[0], ears[1], ears[2], ears[3], eyes[0], eyes[1], nose, glints[0], glints[1]]
    kinds = [0, 0, 1, 0, 1, 2, 2, 1, 4, 4]
    allv, allf, own = kit.merge(*parts)
    fm = []
    for face, o in zip(allf, own):
        k = kinds[o]
        if o == 0:                                       # body: light belly (bottom faces)
            zc = sum(allv[i][2] for i in face) / len(face)
            yc = sum(allv[i][1] for i in face) / len(face)
            if zc < 0.0165 and yc < 0.055:
                k = 3
        fm.append(k)
    body = kit.mesh_object(name + "Mesh", allv, allf, [fur, pink, eye, belly, shine], face_mats=fm)
    kit.fix_normals(body)
    body.parent = pivot
    legs = {}
    for key, (x, y) in MOUSE_LEGS.items():
        hind = key.endswith("H")
        L = MOUSE_HIP_Z
        top = 0.0065 if hind else 0.0045
        geo = kit.tube_geo([(0, 0, 0.004), (0, 0, -L * 0.5), (0, 0.0, -L + 0.0015)], [top, top * 0.6, 0.0022], n=5)
        foot = kit._ico_geo(1.0, (0, 0.004, -L + 0.0012), (0.0028, 0.0055, 0.0016))
        lv, lf, lo = kit.merge(geo, foot)
        leg = kit.mesh_object(f"{name}Leg{key}", lv, lf, [fur, pink], face_mats=[0 if o == 0 else 1 for o in lo],
                              location=(x, y, MOUSE_HIP_Z))
        leg.rotation_mode = "XYZ"
        leg.parent = root
        legs[key] = leg
    # tail in two segments (pivot at the base and in the middle), almost on the ground
    t1 = kit.mesh_object(name + "Tail1", *kit.tube_geo([(0, 0, 0), (0, -0.022, -0.006), (0, -0.042, -0.010)],
                                                        [0.0032, 0.0026, 0.0021], n=5), [pink], (0, -0.049, 0.016))
    t1.parent = root
    t2 = kit.mesh_object(name + "Tail2", *kit.tube_geo([(0, 0, 0), (0, -0.02, -0.002), (0, -0.04, 0.0)],
                                                        [0.0021, 0.0016, 0.0008], n=5), [pink], (0, -0.042, -0.010))
    t2.parent = t1
    for o in (t1, t2):
        o.rotation_mode = "XYZ"
    return SimpleNamespace(root=root, pivot=pivot, body=body, legs=legs, tail=(t1, t2), s=s)


def animate_mouse(m, frames, fps, seed=0):
    """frames = [(frame, x, y, z, heading)] in the world. Marches in lateral sequence (LH, LF, RH, RF) with phase by
    distance walked (planted foot: in stance the foot moves back at the same speed as the body), turning counts as steps, body
    rises and falls, tail sways with a delay; still: breathes and moves the tail slowly."""
    duty, stride = 0.62, 0.050                    # stance fraction; stride (real m) per cycle
    E = stride * duty                             # foot excursion in stance
    offs = {"LH": 0.0, "LF": 0.25, "RH": 0.5, "RF": 0.75}
    s = m.s
    dist, prev, phase_amp = 0.0, None, 0.0
    rnd = random.Random(seed)
    tail_seed = rnd.uniform(0, 6)
    for k, (f, x, y, z, h) in enumerate(frames):
        if prev is not None:
            _, px, py, _, ph = prev
            step = math.hypot(x - px, y - py) / s
            turn = abs((h - ph + math.pi) % (2 * math.pi) - math.pi) * 0.022
            dist += step + turn
            speed = (step + turn) * fps
        else:
            speed = 0.0
        prev = (f, x, y, z, h)
        target = min(1.0, speed / 0.04)
        phase_amp += (target - phase_amp) * 0.35
        t = f / fps
        phase = dist / stride
        m.root.location = (x, y, z)
        m.root.rotation_euler = (0, 0, h)
        m.root.keyframe_insert("location", frame=f)
        m.root.keyframe_insert("rotation_euler", index=2, frame=f)
        for key, leg in m.legs.items():
            c = (phase + offs[key]) % 1.0
            if c < duty:
                xr, lift = E / 2 - E * (c / duty), 0.0
            else:
                w = (c - duty) / (1 - duty)
                xr, lift = -E / 2 + E * (w * w * (3 - 2 * w)), math.sin(math.pi * w)
            xr *= phase_amp
            lift *= phase_amp
            L = MOUSE_HIP_Z
            leg.rotation_euler = (math.asin(max(-0.9, min(0.9, xr / L))), 0, 0)
            leg.scale = (1, 1, 1 - 0.3 * lift)
            leg.keyframe_insert("rotation_euler", index=0, frame=f)
            leg.keyframe_insert("scale", index=2, frame=f)
        bob = 0.0012 * abs(math.sin(2 * math.pi * phase)) * phase_amp
        breath = 0.012 * math.sin(2 * math.pi * t * 1.6) * (1 - phase_amp)
        m.pivot.location = (0, 0, bob)
        m.pivot.rotation_euler = (0.04 * math.sin(2 * math.pi * phase) * phase_amp, 0, 0)
        m.pivot.scale = (1 + breath, 1, 1 + breath)
        m.pivot.keyframe_insert("location", index=2, frame=f)
        m.pivot.keyframe_insert("rotation_euler", index=0, frame=f)
        m.pivot.keyframe_insert("scale", frame=f)
        sw = 0.35 * math.sin(2 * math.pi * (phase * 0.5) + tail_seed) * phase_amp + 0.22 * math.sin(t * 2.1 + tail_seed)
        sw2 = 0.35 * math.sin(2 * math.pi * (phase * 0.5) + tail_seed - 1.1) * phase_amp + 0.3 * math.sin(t * 2.1 + tail_seed - 1.0)
        m.tail[0].rotation_euler = (0, 0, sw)
        m.tail[1].rotation_euler = (0, 0, sw2)
        m.tail[0].keyframe_insert("rotation_euler", index=2, frame=f)
        m.tail[1].keyframe_insert("rotation_euler", index=2, frame=f)


# ---------- boat ----------

def _hull_geo():
    """Hull by sections (stern x=-4 to bow x=+4.2): keel, bilge, waterline, strake, gunwale (rises at the bow)."""
    st = [(-4.0, 1.22, 1.15, -0.45), (-3.0, 1.30, 1.15, -0.55), (-1.5, 1.32, 1.18, -0.60), (0.0, 1.30, 1.26, -0.60),
          (1.5, 1.16, 1.40, -0.55), (2.7, 0.88, 1.60, -0.38), (3.6, 0.48, 1.82, 0.0), (4.2, 0.06, 2.0, 0.85)]
    rings = []
    for x, hw, zs, kz in st:
        half = [(0.0, kz), (0.78 * hw, kz * 0.45 + 0.0), (0.97 * hw, 0.0), (hw, 0.45), (1.02 * hw, zs)]
        pts = half + [(-y, z) for y, z in reversed(half[1:])]
        rings.append([(x, y, z) for y, z in pts])
    # the loft closes the ring along the gunwale: the last side (from +gunwale to -gunwale) becomes the deck
    return kit.loft_geo(rings), st


def boat(name="Boat"):
    """8 m fishing boat (bow toward +x). Children: Hull (sway), spinning radar, amber lights (wheelhouse windows, mast
    light, gantry floodlights), point light that lights the deck and the water. Returns SimpleNamespace."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    body = bpy.data.objects.new(name + "Sway", None)
    bpy.context.collection.objects.link(body)
    body.parent = root
    body.rotation_mode = "XYZ"
    white = kit.flat(name + "White", "#D6DBE0", rough=0.7, emission="#D6DBE0", strength=0.06)
    band = kit.flat(name + "Band", "#1E3550", rough=0.7)
    deckm = kit.flat(name + "Deck", "#6B5A48", rough=0.9)
    metal = kit.flat(name + "Metal", "#3A3E44", rough=0.6)
    (hv, hf), _ = _hull_geo()
    fm, ring_n, n_side = [], 9, 9 * 7
    for k, face in enumerate(hf):
        c = [sum(hv[i][kk] for i in face) / len(face) for kk in range(3)]
        if k < n_side and k % ring_n == 4:          # side of the ring between the two gunwales = deck
            fm.append(2)
        elif c[2] > 0.5:
            fm.append(0)
        else:
            fm.append(1)
    hull = kit.mesh_object(name + "Hull", hv, hf, [white, band, deckm], face_mats=fm)
    kit.fix_normals(hull)
    hull.parent = body
    mat, em = kit.keyed_emission(name + "Light", "#2A2116", kit.LUZ, 6.0)
    parts, lights = [], []
    # wheelhouse (forward of the middle), roof with overhang, windows
    parts.append(kit._box_geo(2.0, 1.9, 1.7, 0.2, -0.95, 1.25))
    parts.append(kit._box_geo(2.3, 2.1, 0.14, 0.1, -1.05, 2.95))
    for k in range(3):                                   # front windows
        lights.append(kit._box_geo(0.05, 0.48, 0.42, 2.2, -0.82 + 0.58 * k, 2.25))
    for sy in (-1, 1):                                   # side windows
        for k in range(2):
            lights.append(kit._box_geo(0.6, 0.05, 0.42, 0.45 + 0.8 * k, sy * 0.95 - (0.05 if sy < 0 else 0), 2.25))
    # mast with yard and light at the top
    mast = [kit._prism_geo(6, 0.14, 0.11, 3.4, oz=3.05, ox=1.4, oy=0.0), kit._box_geo(0.16, 1.8, 0.14, 1.32, -0.9, 5.3)]
    lights.append(kit._box_geo(0.34, 0.34, 0.34, 1.23, -0.17, 6.45))
    # stern gantry (A-frame) with two floodlights
    gantry = [kit._box_geo(0.24, 0.24, 2.6, -3.75, -1.12, 1.1), kit._box_geo(0.24, 0.24, 2.6, -3.75, 0.88, 1.1),
              kit._box_geo(0.24, 2.24, 0.24, -3.75, -1.12, 3.7)]
    for sy in (-0.6, 0.6):
        lights.append(kit._box_geo(0.3, 0.32, 0.26, -3.55, sy - 0.16, 3.44))
    # low bulwarks
    rail = [kit._box_geo(4.2, 0.08, 0.35, -4.0, sy * 1.18 - 0.04, 1.15) for sy in (-1, 1)]
    wv, wf, wo = kit.merge(*parts)
    house = kit.mesh_object(name + "House", wv, wf, [white])
    house.parent = body
    mv, mf, _ = kit.merge(*mast, *gantry, *rail)
    kit.mesh_object(name + "Rig", mv, mf, [metal]).parent = body
    lv, lf, _ = kit.merge(*lights)
    lamps = kit.mesh_object(name + "Lamps", lv, lf, [mat])
    lamps.parent = body
    lamps.visible_shadow = False
    # radar on the roof (always spinning)
    radar = kit.mesh_object(name + "Radar", *kit._box_geo(1.5, 0.22, 0.14, -0.75, -0.11, 0.0), [metal], (1.0, 0.0, 3.32))
    radar.parent = body
    radar.rotation_mode = "XYZ"
    kit.mesh_object(name + "RadarPost", *kit._prism_geo(6, 0.07, 0.07, 0.25, oz=3.09, ox=1.0), [metal]).parent = body
    # light that lights the deck, the hull and the water around (no shadow)
    ld = bpy.data.lights.new(name + "Glow", "POINT")
    ld.color, ld.energy, ld.shadow_soft_size = (1.0, 0.68, 0.32), 1500.0, 0.5
    ld.use_shadow = False
    ld.specular_factor = 0.0                 # no blown-out white spot on the water (the reflection is the amber column)
    lo = bpy.data.objects.new(name + "Glow", ld)
    bpy.context.collection.objects.link(lo)
    lo.location = (-1.5, 0.0, 4.2)
    lo.parent = body
    return SimpleNamespace(root=root, sway=body, em=em, radar=radar, light=ld, lamps=lamps)


def wake(name, mat):
    """V-shaped wake behind the stern (scene 07): strips of foam that open backward, on the water."""
    parts = []
    for sy in (-1, 1):
        for k in range(10):
            x0 = -4.2 - 2.6 * k
            w = 0.9 - 0.05 * k
            y0 = sy * (1.1 + 0.42 * 2.6 * k)
            parts.append(([(x0, y0 - w / 2, 0), (x0 - 2.4, y0 + sy * 1.0 - w / 2, 0), (x0 - 2.4, y0 + sy * 1.0 + w / 2, 0),
                           (x0, y0 + w / 2, 0)], [(0, 1, 2, 3) if sy > 0 else (3, 2, 1, 0)]))
    parts.append(([(-4.0, -1.0, 0), (-12.0, -0.7, 0), (-12.0, 0.7, 0), (-4.0, 1.0, 0)], [(0, 1, 2, 3)]))
    v, f, _ = kit.merge(*parts)
    o = kit.mesh_object(name, v, f, [mat])
    kit.fix_normals(o)
    o.visible_shadow = False
    return o


# ---------- lantern and crate ----------

def lantern(name, center, glass_mat):
    """Pier lantern: emissive amber glass, four columns and dark metal roof, arm to the post (-x)."""
    cx, cy, cz = center
    metal = kit.flat(name + "Metal", "#24211E", rough=0.5)
    glass = kit.mesh_object(name + "Glass", *kit._box_geo(0.11, 0.11, 0.15, cx - 0.055, cy - 0.055, cz - 0.075), [glass_mat])
    glass.visible_shadow = False
    parts = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            parts.append(kit._box_geo(0.018, 0.018, 0.16, cx + dx * 0.058 - 0.009, cy + dy * 0.058 - 0.009, cz - 0.08))
    parts.append(kit._box_geo(0.15, 0.15, 0.022, cx - 0.075, cy - 0.075, cz - 0.1))                 # base
    roof_v = [(cx - 0.085, cy - 0.085, cz + 0.075), (cx + 0.085, cy - 0.085, cz + 0.075), (cx + 0.085, cy + 0.085, cz + 0.075),
              (cx - 0.085, cy + 0.085, cz + 0.075), (cx, cy, cz + 0.15)]
    parts.append((roof_v, [(3, 2, 1, 0), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]))
    parts.append(kit._box_geo(0.16, 0.025, 0.025, cx - 0.2, cy - 0.0125, cz + 0.09))             # arm
    parts.append(kit._box_geo(0.025, 0.025, 0.07, cx - 0.0125, cy - 0.0125, cz + 0.08))
    v, f, _ = kit.merge(*parts)
    frame = kit.mesh_object(name + "Frame", v, f, [metal])
    kit.fix_normals(frame)
    frame.visible_shadow = False
    return glass, frame


def crate(name, center, size=(0.4, 0.4, 0.32)):
    """Slatted wooden crate (dark gaps), with corner brackets and plank lid."""
    sx, sy, sz = size
    cx, cy, cz = center
    wood = kit.flat(name + "Wood", "#7A6040", rough=1.0)
    wood2 = kit.flat(name + "Wood2", "#6A5234", rough=1.0)
    dark = kit.flat(name + "Inside", "#1C140C", rough=1.0)
    x0, y0 = cx - sx / 2, cy - sy / 2
    core = kit.mesh_object(name, *kit._box_geo(sx - 0.03, sy - 0.03, sz - 0.01, x0 + 0.015, y0 + 0.015, cz), [dark])
    parts, kinds = [], []
    n = 3
    h = (sz - 0.02) / n
    for k in range(n):
        z = cz + 0.01 + k * h + 0.006
        for geo in (kit._box_geo(sx - 0.04, 0.016, h - 0.014, x0 + 0.02, y0, z), kit._box_geo(sx - 0.04, 0.016, h - 0.014, x0 + 0.02, y0 + sy - 0.016, z),
                    kit._box_geo(0.016, sy - 0.04, h - 0.014, x0, y0 + 0.02, z), kit._box_geo(0.016, sy - 0.04, h - 0.014, x0 + sx - 0.016, y0 + 0.02, z)):
            parts.append(geo)
            kinds.append(k % 2)
    for dx in (0, sx - 0.04):
        for dy in (0, sy - 0.04):
            parts.append(kit._box_geo(0.04, 0.04, sz, x0 + dx, y0 + dy, cz))
            kinds.append(1)
    for k in range(4):
        parts.append(kit._box_geo(sx, sy / 4 - 0.012, 0.018, x0, y0 + k * sy / 4 + 0.006, cz + sz - 0.004))
        kinds.append(k % 2)
    v, f, own = kit.merge(*parts)
    slats = kit.mesh_object(name + "Slats", v, f, [wood, wood2], face_mats=[kinds[o] for o in own])
    slats.parent = core
    slats.location = (0, 0, 0)
    return core


# ---------- Moon, Sun, globe ----------

MARIA = [(-0.30, 0.42, 0.20), (-0.60, 0.12, 0.24), (-0.44, -0.08, 0.17), (0.20, 0.40, 0.13), (0.33, 0.15, 0.15),
         (0.67, 0.33, 0.09), (0.55, -0.10, 0.12), (0.33, -0.24, 0.08), (-0.18, -0.38, 0.12), (-0.46, -0.42, 0.08),
         (-0.25, 0.71, 0.07), (0.02, 0.73, 0.07), (0.25, 0.69, 0.06)]


def moon_disc(name, radius, location, toward_cam, right, up):
    """Low-poly full Moon with maria (darker faces at the positions of the visible side). Emission that vanishes by
    transparency (fac). Returns (obj, fac)."""
    mat, n, links, out = node_mat(name + "Mat")
    attr = n.new("ShaderNodeAttribute")
    attr.attribute_name = "mare"
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = lin("#F2F0E6")
    mix.inputs["B"].default_value = lin("#C8C5BB")
    links.new(attr.outputs["Fac"], mix.inputs["Factor"])
    em = n.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    links.new(mix.outputs["Result"], em.inputs["Color"])
    clear = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = 1.0
    links.new(clear.outputs[0], mx.inputs[1])
    links.new(em.outputs[0], mx.inputs[2])
    links.new(mx.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    vals = []
    for v in me.vertices:                     # maria per vertex with a soft edge (interpolated, no pixel step)
        c = v.co.normalized()
        a, b = c.dot(right), c.dot(up)
        dark = 0.0
        if c.dot(toward_cam) > 0:
            for ma, mb, r in MARIA:
                dd = math.hypot(a - ma, b - mb) / r
                dark = max(dark, min(1.0, max(0.0, (1.25 - dd) / 0.5)))
        vals.append(dark)
    for p in me.polygons:
        p.use_smooth = False
    at = me.attributes.new("mare", "FLOAT", "POINT")
    at.data.foreach_set("value", vals)
    o = bpy.data.objects.new(name, me)
    o.location = location
    bpy.context.collection.objects.link(o)
    o.visible_shadow = False
    return o, mx.inputs["Fac"]


def disc_geo(r, n=40, ring=None):
    """Disc (or ring from r to ring) in the local x-z plane, facing -y."""
    if ring is None:
        v = [(0, 0, 0)] + [(r * math.cos(2 * math.pi * i / n), 0, r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        f = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
        return v, f
    v = [(rr * math.cos(2 * math.pi * i / n), 0, rr * math.sin(2 * math.pi * i / n)) for rr in (r, ring) for i in range(n)]
    f = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def sun_disc(name, r_core, r_halo):
    """Diagram Sun: warm disc with soft edge and additive halo (radial gradient), in the local x-z plane."""
    core_m, _, _ = fade_emitter(name + "CoreMat", "#FFF3D2", 7.0)
    core = kit.mesh_object(name, *disc_geo(r_core, 40), [core_m])
    core.visible_shadow = False
    mat, n, links, out = node_mat(name + "HaloMat")
    tc = n.new("ShaderNodeTexCoord")
    ln = n.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    links.new(tc.outputs["Object"], ln.inputs[0])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = r_core * 0.92, r_halo
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    links.new(ln.outputs["Value"], mr.inputs["Value"])
    sq = _math(n, links, "POWER", mr.outputs["Result"], value=2.2)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#FFE2A0")
    st = _math(n, links, "MULTIPLY", sq, value=2.4)
    links.new(st, em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    clear = n.new("ShaderNodeBsdfTransparent")
    links.new(clear.outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    halo = kit.mesh_object(name + "Halo", *disc_geo(r_halo, 48), [mat])
    halo.visible_shadow = False
    halo.parent = core
    halo.location = (0, r_core * 0.02, 0)                 # slightly behind the disc (no coplanar faces)
    return core, halo


def earth(name, rnd):
    """Today's globe (globe.py, radius 10) with 25% emission (does not vanish against the Milky Way). The scene scales x0.05."""
    import globe as gl
    g = gl.globe(name, (0, 0, 0), rnd, pangaea=False, levels=4)
    for o in [g.root, *g.root.children_recursive]:
        if o.type != "MESH":
            continue
        o.visible_shadow = False
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.get("glow_done"):
                continue
            p = kit.principled(m)
            p.inputs["Emission Color"].default_value = p.inputs["Base Color"].default_value
            p.inputs["Emission Strength"].default_value = 0.3
            m["glow_done"] = True
    return g


def rim_ring(name, r_in, r_out, color="#8EC2FF", strength=1.6):
    """Atmosphere ring (light outline) in the local x-z plane; the scene orients it toward the camera."""
    mat = kit.flat(name + "Mat", "#000000", emission=color, strength=strength)
    o = kit.mesh_object(name, *disc_geo(r_in, 64, ring=r_out), [mat])
    o.visible_shadow = False
    return o
