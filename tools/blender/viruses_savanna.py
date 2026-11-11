"""Savanna of northern Serengeti (dry season, August, 10:30) of viruses-disappeared, scenes 11 (1960s) and 12 (1970s).

A single viewpoint, BEFORE and AFTER (direction.md sections 2-3): the same terrain, the 2 old acacias and the kopje in the same
place; on cut 11->12 only the state changes (tall dry grass with burn patches -> short light grass without
burn, big herd, young acacias).

LOCAL coordinates (added to ORIGIN = origin: the savanna occupies the same space as the waterfront and each place only shows in its
stretch; at 60 km float precision streaked the shadows): camera on the ground at (0, 0); +y = where the camera looks in 11 (southwest), +x = right. Sun to the north = behind-right of the camera
(135 deg to the right of the front), elevation 55 deg, shadows front-left (art.md section 1).

Palette (art.md section 2): grass 11 #B0904E / shadow #6A5634 / tips #D0B470; grass 12 #C8B482 / #8A7A58, trails
#A8704A; burn #2A2622, stumps #1E1A18, ash #5A5450; old acacia trunk #4A3E34 crown #5C6E3A; young #6E8A40;
kopje #7E8AA0 (air 45%). Sky horizon #CFD3CC (slightly dusty, no haze).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector, noise

import kit
import plants_models as pm
import plants_set as ps
import viruses_set as vs
from kit import lin

ORIGIN = Vector((0.0, 0.0, 0.0))     # same space as the waterfront (on/off on the cut)
SUN_DIR = Vector((math.sin(math.radians(135)) * math.cos(math.radians(55)),
                  math.cos(math.radians(135)) * math.cos(math.radians(55)), math.sin(math.radians(55))))
OLD_ACACIAS = [(-13.3, 58.5, 8.0), (14.8, 119.0, 8.5)]
YOUNG_ACACIAS = [(2.4, 7.8, 2.1), (3.7, 9.6, 1.6), (3.9, 7.9, 2.4), (9.5, 21.0, 2.2), (-5.5, 26.0, 1.6),
                 (13.0, 34.0, 2.6)]
BURNS = [((-2.5, 7.6), 2.2, 3.8), ((-7.5, 13.0), 2.4, 1.9), ((1.8, 16.5), 1.5, 1.2), ((-11.0, 19.0), 2.0, 1.4)]
KOPJE = (-200.0, 3000.0)


def ground_z(x, y):
    """Nearly flat plain: undulation that grows with distance (zero near the camera)."""
    r = math.hypot(x, y)
    amp = min(1.0, max(0.0, (r - 8.0) / 300.0))
    z = amp * (1.4 * noise.noise(Vector((x * 0.004, y * 0.004, 0.7))) + 0.5 * noise.noise(Vector((x * 0.02, y * 0.02, 1.3))))
    z += 0.04 * noise.noise(Vector((x * 0.4, y * 0.4, 2.2))) * (1 - amp)
    return z


def _axis(lo, hi, near, step, far_steps):
    vals = [v for v in [near[0] + step * k for k in range(int((near[1] - near[0]) / step) + 1)]]
    out = set(round(v, 3) for v in vals)
    out |= {v for v in far_steps if lo <= v <= hi}
    out |= {lo, hi}
    return sorted(out)


def terrain_mesh(name, mats):
    xs = _axis(-4000, 4000, (-80, 120), 2.5, [-4000, -2500, -1600, -1100, -800, -600, -450, -340, -260, -200, -160,
                                               -130, -105, 140, 170, 210, 260, 330, 420, 540, 700, 900, 1200, 1700,
                                               2500, 4000])
    ys = _axis(-200, 7000, (-20, 160), 2.5, [-200, -120, -60, -40, 190, 230, 280, 340, 420, 520, 650, 800, 1000, 1250,
                                             1600, 2000, 2500, 3100, 3800, 4800, 6000, 7000])
    # LOCAL vertices and object at ORIGIN: texture by object coordinate near 60 km loses precision and streaks
    verts = [(x, y, ground_z(x, y)) for y in ys for x in xs]
    nx = len(xs)
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(len(ys) - 1) for i in range(nx - 1)]
    return kit.mesh_object(name, verts, faces, mats, tuple(ORIGIN))


def _distance_haze(n, L, col, k_far=0.45, d0=150.0, d1=4000.0, horizon=vs.SAV_HORIZON):
    cam = n.new("ShaderNodeCameraData")
    m = n.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = d0, d1
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = 0.0, k_far
    L.new(cam.outputs["View Distance"], m.inputs["Value"])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(m.outputs["Result"], mix.inputs["Factor"])
    L.new(col, mix.inputs["A"])
    mix.inputs["B"].default_value = lin(horizon)
    return mix.outputs["Result"]


def ground_mat(name, base, dark, light, trails=None, streak=3.0, near=None):
    """Grass ground seen from afar: tuft patches (stretched noise), 2 tones + light tips, and (12) trails of
    packed earth in winding strips. Atmospheric perspective by distance (no haze)."""
    mat, n, L, p = pm.node_mat(name, 0.95, 0.12)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, streak, 1.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 0.35
    tex.inputs["Detail"].default_value = 2.0
    L.new(mp.outputs[0], tex.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.32, lin(dark)
    e[1].position, e[1].color = 0.7, lin(light)
    mid = e.new(0.5); mid.color = lin(base)
    L.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.012
    L.new(tc.outputs["Object"], big.inputs["Vector"])
    bm = n.new("ShaderNodeMapRange")
    bm.inputs["To Min"].default_value, bm.inputs["To Max"].default_value = 0.9, 1.1
    L.new(big.outputs["Fac"], bm.inputs["Value"])
    col = pm._value_mul(n, L, col, bm.outputs["Result"])
    if trails:
        tn = n.new("ShaderNodeTexNoise")
        tn.inputs["Scale"].default_value = 0.035
        tn.inputs["Detail"].default_value = 2.0
        L.new(tc.outputs["Object"], tn.inputs["Vector"])
        band = n.new("ShaderNodeMapRange")
        band.inputs["From Min"].default_value, band.inputs["From Max"].default_value = 0.0, 0.006
        band.inputs["To Min"].default_value, band.inputs["To Max"].default_value = 0.75, 0.0
        dist = n.new("ShaderNodeMath"); dist.operation = "ABSOLUTE"
        sub = n.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
        L.new(tn.outputs["Fac"], sub.inputs[0]); sub.inputs[1].default_value = 0.5
        L.new(sub.outputs[0], dist.inputs[0])
        L.new(dist.outputs[0], band.inputs["Value"])
        tm = n.new("ShaderNodeMix"); tm.data_type = "RGBA"
        L.new(band.outputs["Result"], tm.inputs["Factor"])
        L.new(col, tm.inputs["A"])
        tm.inputs["B"].default_value = lin(trails)
        col = tm.outputs["Result"]
    if near:
        # near the camera the ground between the tufts is the deep shadow of the tall grass (not bare earth showing)
        cam = n.new("ShaderNodeCameraData")
        nm = n.new("ShaderNodeMapRange")
        nm.inputs["From Min"].default_value, nm.inputs["From Max"].default_value = 12.0, 45.0
        nm.inputs["To Min"].default_value, nm.inputs["To Max"].default_value = 1.0, 0.0
        L.new(cam.outputs["View Distance"], nm.inputs["Value"])
        mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"
        L.new(nm.outputs["Result"], mx.inputs["Factor"])
        L.new(col, mx.inputs["A"])
        mx.inputs["B"].default_value = lin(near)
        col = mx.outputs["Result"]
    col = _distance_haze(n, L, col)
    L.new(col, p.inputs["Base Color"])
    return mat


def grass_mat(name, base, tip, shadow, height, gust_tip=None):
    """Grass tuft: dark base -> light tip by height, +-10% per instance. gust_tip: color of the tips when
    the gust passes (instance attribute 'gust', 0..1)."""
    mat, n, L, p = pm.node_mat(name, 0.9, 0.15)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    g = n.new("ShaderNodeMapRange")
    g.inputs["From Min"].default_value, g.inputs["From Max"].default_value = 0.0, height
    L.new(sep.outputs["Z"], g.inputs["Value"])
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, lin(shadow)
    e[1].position, e[1].color = 1.0, lin(tip)
    m = e.new(0.45); m.color = lin(base)
    L.new(g.outputs["Result"], ramp.inputs["Fac"])
    col = pm._value_mul(n, L, ramp.outputs["Color"], pm._rand_factor(n, L, 0.88, 1.1))
    if gust_tip:
        at = n.new("ShaderNodeAttribute")
        at.attribute_type, at.attribute_name = "INSTANCER", "gust"
        tipk = n.new("ShaderNodeMath"); tipk.operation = "MULTIPLY"
        L.new(at.outputs["Fac"], tipk.inputs[0]); L.new(g.outputs["Result"], tipk.inputs[1])
        gm = n.new("ShaderNodeMix"); gm.data_type = "RGBA"
        L.new(tipk.outputs[0], gm.inputs["Factor"])
        L.new(col, gm.inputs["A"])
        gm.inputs["B"].default_value = lin(gust_tip)
        col = gm.outputs["Result"]
    col = _distance_haze(n, L, col)
    L.new(col, p.inputs["Base Color"])
    return mat


def burn_mat():
    """Old burn: black #2A2622 blotched with ash gray #5A5450 (noise), matte."""
    mat, n, L, p = pm.node_mat("Burn", 0.98, 0.1)
    tc = n.new("ShaderNodeTexCoord")
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 1.8
    tex.inputs["Detail"].default_value = 3.0
    L.new(tc.outputs["Object"], tex.inputs["Vector"])
    r = n.new("ShaderNodeValToRGB")
    e = r.color_ramp.elements
    e[0].position, e[0].color = 0.45, lin("#2A2622")
    e[1].position, e[1].color = 0.72, lin("#5A5450")
    L.new(tex.outputs["Fac"], r.inputs["Fac"])
    L.new(r.outputs["Color"], p.inputs["Base Color"])
    return mat


def make_mats():
    M = {}
    # BEFORE/AFTER pair (art R1): grass of 12 is 20 to 35 levels above that of 11 in gray (measured in the 1st frame)
    M["ground11"] = ground_mat("SavGround11", "#A88C4C", "#7A663E", "#C4A866", streak=1.6, near="#8A7448")
    M["ground12"] = ground_mat("SavGround12", "#C2AE7E", "#A8966A", "#D0C090", trails="#A8704A", streak=1.3,
                               near="#A89464")
    M["tall"] = grass_mat("TallGrass", "#BC9C58", "#D8BC78", "#8A7244", 0.75, gust_tip="#EEDCA8")
    M["tall_far"] = grass_mat("TallGrassFar", "#A88A4C", "#C8AC6A", "#7A6440", 0.9)
    M["short"] = grass_mat("ShortGrass", "#B4A070", "#C4B486", "#9A8A5E", 0.08)
    M["burn"] = burn_mat()
    M["ash"] = pm.fixed_mat("Ash", "#4A4440", rough=0.98)
    M["stump"] = pm.fixed_mat("Stump", "#1E1A18", rough=0.95)
    M["trunk"] = pm.fixed_mat("AcaciaTrunk", "#4A3E34", rough=0.92)
    M["crown_old"] = pm.fixed_mat("AcaciaCrownOld", "#5C6E3A", rough=0.88, var=(0.88, 1.1))
    M["crown_young"] = pm.fixed_mat("AcaciaCrownYoung", "#6E8A40", rough=0.85, var=(0.9, 1.1))
    M["kopje"] = pm.fixed_mat("Kopje", vs.hazed("#8E8A82", 0.45, vs.SAV_HORIZON), rough=0.95, var=(0.92, 1.06))
    M["far_hill"] = pm.fixed_mat("FarHillSav", vs.hazed("#7A7058", 0.55, vs.SAV_HORIZON), rough=0.95)
    M["far_tree"] = pm.fixed_mat("FarAcacia", vs.hazed("#5C6E3A", 0.3, vs.SAV_HORIZON), rough=0.9, var=(0.85, 1.1))
    M["herd_far"] = pm.fixed_mat("HerdFar", "#3E4248", rough=0.95)
    M["cloud"] = pm.fixed_mat("SavCloud", "#F2F4F2", rough=1.0, emission="#F2F4F2", strength=0.25)
    return M


# ---------- grass (Geometry Nodes, instances) ----------

def tuft_mesh(name, rnd, height, radius, blades, width, lean=0.18, arc=1.0):
    """Voluminous tuft: blades in a 4-sided cone (base >= 4 cm: >= 4 px at 10 m), leaning outward. arc < 1:
    blades only in one sector (crooked clump, not a star)."""
    geos = []
    a0 = rnd.uniform(0, 2 * math.pi) if arc < 1.0 else 0.0
    for j in range(blades):
        a = a0 + arc * 2 * math.pi * j / blades + rnd.uniform(-0.4, 0.4)
        rr = radius * rnd.uniform(0.2, 1.0)
        h = height * rnd.uniform(0.7, 1.15)
        tilt = Vector((math.cos(a) * lean * h, math.sin(a) * lean * h, 0))
        v, f = kit._prism_geo(4, width * rnd.uniform(0.8, 1.2), 0.0, h, ox=math.cos(a) * rr, oy=math.sin(a) * rr)
        v = [tuple(Vector(p) + tilt * (p[2] / h) ** 1.5) for p in v]
        geos.append((v, f))
    v, f, _ = kit.merge(*geos)
    o = kit.mesh_object(name, v, f, [])
    for p in o.data.polygons:
        p.use_smooth = False
    return o


def scatter_ng(name, collection, distance, density, seed, scale=(0.8, 1.2), keep=None, wind=None, rot_jitter=0.0,
               zscale=None, noise_density=None, gust=None):
    """Poisson scatter on faces of the 'carrier', with region cut-out (keep(x, y) -> True keeps, done by a
    vertex mask 'keep' on the carrier's own mesh) and optional wind (x/y rotation by sine of the frame)."""
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = distance
    dist.inputs["Density Max"].default_value = density
    dist.inputs["Seed"].default_value = seed
    L.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    attr = N.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "keep"
    dens = attr.outputs["Attribute"]
    if noise_density:
        # denser and sparser patches (breaks the repeated pattern of tuft equal to tuft)
        nscale, lo, hi = noise_density
        npos = N.new("GeometryNodeInputPosition")
        ntex = N.new("ShaderNodeTexNoise")
        ntex.inputs["Scale"].default_value = nscale
        ntex.inputs["Detail"].default_value = 1.5
        L.new(npos.outputs[0], ntex.inputs["Vector"])
        nmap = N.new("ShaderNodeMapRange")
        nmap.inputs["From Min"].default_value, nmap.inputs["From Max"].default_value = 0.38, 0.62
        nmap.inputs["To Min"].default_value, nmap.inputs["To Max"].default_value = lo, hi
        L.new(ntex.outputs["Fac"], nmap.inputs["Value"])
        nmul = N.new("ShaderNodeMath"); nmul.operation = "MULTIPLY"
        L.new(dens, nmul.inputs[0]); L.new(nmap.outputs["Result"], nmul.inputs[1])
        dens = nmul.outputs[0]
    L.new(dens, dist.inputs["Density Factor"])
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = collection
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rr = N.new("FunctionNodeRandomValue"); rr.data_type = "FLOAT_VECTOR"
    rr.inputs["Min"].default_value = (-rot_jitter, -rot_jitter, 0)
    rr.inputs["Max"].default_value = (rot_jitter, rot_jitter, 2 * math.pi)
    rr.inputs["Seed"].default_value = seed + 1
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"
    rs.inputs["Min"].default_value, rs.inputs["Max"].default_value = scale
    rs.inputs["Seed"].default_value = seed + 2
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    L.new(dist.outputs["Points"], inst.inputs["Points"])
    L.new(info.outputs["Instances"], inst.inputs["Instance"])
    rot = rr.outputs["Value"]
    if wind:
        # slow lean (<= 0.5 Hz) that runs through space: sin(2 pi f t - k x); the frame comes by driver
        amp, hz, k = wind
        pos = N.new("GeometryNodeInputPosition")
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(pos.outputs[0], sep.inputs[0])
        tval = N.new("ShaderNodeValue"); tval.name = "WindTime"
        fc = tval.outputs[0].driver_add("default_value")
        fc.driver.expression = f"frame / 30.0 * {2 * math.pi * hz:.5f}"
        ph = N.new("ShaderNodeMath"); ph.operation = "MULTIPLY_ADD"
        L.new(sep.outputs["X"], ph.inputs[0]); ph.inputs[1].default_value = k
        L.new(tval.outputs[0], ph.inputs[2])
        sn = N.new("ShaderNodeMath"); sn.operation = "SINE"
        L.new(ph.outputs[0], sn.inputs[0])
        am = N.new("ShaderNodeMath"); am.operation = "MULTIPLY"
        L.new(sn.outputs[0], am.inputs[0]); am.inputs[1].default_value = amp
        comb = N.new("ShaderNodeCombineXYZ")
        lean = am.outputs[0]
        if gust:
            # gust (11, *cleared*): gaussian pulse that runs along x (right -> left on screen) and lays the grass
            # toward -x; the frame comes by driver (simple expression, no Python)
            f0, xs, v, g_amp, width = gust
            x0 = N.new("ShaderNodeValue"); x0.name = "GustX"
            d = x0.outputs[0].driver_add("default_value")
            d.driver.expression = f"{xs:.3f} - {v:.3f} * (frame - {f0}) / 30.0"
            on = N.new("ShaderNodeValue"); on.name = "GustOn"
            d = on.outputs[0].driver_add("default_value")
            d.driver.expression = f"min(max((frame - {f0}) / 6.0, 0.0), 1.0)"
            dx = N.new("ShaderNodeMath"); dx.operation = "SUBTRACT"
            L.new(sep.outputs["X"], dx.inputs[0]); L.new(x0.outputs[0], dx.inputs[1])
            dw = N.new("ShaderNodeMath"); dw.operation = "DIVIDE"
            L.new(dx.outputs[0], dw.inputs[0]); dw.inputs[1].default_value = width
            sq = N.new("ShaderNodeMath"); sq.operation = "MULTIPLY"
            L.new(dw.outputs[0], sq.inputs[0]); L.new(dw.outputs[0], sq.inputs[1])
            ngt = N.new("ShaderNodeMath"); ngt.operation = "MULTIPLY"
            L.new(sq.outputs[0], ngt.inputs[0]); ngt.inputs[1].default_value = -1.0
            ex = N.new("ShaderNodeMath"); ex.operation = "EXPONENT"
            L.new(ngt.outputs[0], ex.inputs[0])
            pulse = N.new("ShaderNodeMath"); pulse.operation = "MULTIPLY"
            L.new(ex.outputs[0], pulse.inputs[0]); L.new(on.outputs[0], pulse.inputs[1])
            pa = N.new("ShaderNodeMath"); pa.operation = "MULTIPLY_ADD"
            L.new(pulse.outputs[0], pa.inputs[0]); pa.inputs[1].default_value = -g_amp
            L.new(am.outputs[0], pa.inputs[2])
            lean = pa.outputs[0]
        L.new(lean, comb.inputs["Y"])
        e2r = N.new("FunctionNodeEulerToRotation")
        L.new(comb.outputs[0], e2r.inputs[0])
        base = N.new("FunctionNodeEulerToRotation")
        L.new(rr.outputs["Value"], base.inputs[0])
        rot_by = N.new("FunctionNodeRotateRotation")
        rot_by.rotation_space = "GLOBAL"
        L.new(base.outputs[0], rot_by.inputs["Rotation"])
        L.new(e2r.outputs[0], rot_by.inputs["Rotate By"])
        rot = rot_by.outputs[0]
    L.new(rot, inst.inputs["Rotation"])
    if zscale:
        # own height per tuft (besides the general scale): short grass is not all the same height
        rz = N.new("FunctionNodeRandomValue"); rz.data_type = "FLOAT"
        rz.inputs["Min"].default_value, rz.inputs["Max"].default_value = zscale
        rz.inputs["Seed"].default_value = seed + 3
        mz = N.new("ShaderNodeMath"); mz.operation = "MULTIPLY"
        L.new(rs.outputs["Value"], mz.inputs[0]); L.new(rz.outputs["Value"], mz.inputs[1])
        cs = N.new("ShaderNodeCombineXYZ")
        L.new(rs.outputs["Value"], cs.inputs["X"]); L.new(rs.outputs["Value"], cs.inputs["Y"])
        L.new(mz.outputs[0], cs.inputs["Z"])
        L.new(cs.outputs[0], inst.inputs["Scale"])
    else:
        L.new(rs.outputs["Value"], inst.inputs["Scale"])
    out_geo = inst.outputs["Instances"]
    if wind and gust:
        store = N.new("GeometryNodeStoreNamedAttribute")
        store.data_type, store.domain = "FLOAT", "INSTANCE"
        store.inputs["Name"].default_value = "gust"
        L.new(out_geo, store.inputs["Geometry"])
        L.new(pulse.outputs[0], store.inputs["Value"])
        out_geo = store.outputs["Geometry"]
    L.new(out_geo, gout.inputs["Geometry"])
    return ng


def patch(name, x0, x1, y0, y1, cell, keep):
    """Support mesh (carrier) glued to the ground, with the per-vertex attribute 'keep' (0..1) for the scatter."""
    nx, ny = max(2, int((x1 - x0) / cell)), max(2, int((y1 - y0) / cell))
    verts, kv = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny
            verts.append((x, y, ground_z(x, y)))
            kv.append(keep(x, y))
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    o = kit.mesh_object(name, verts, faces, [], tuple(ORIGIN))
    a = o.data.attributes.new("keep", "FLOAT", "POINT")
    a.data.foreach_set("value", kv)
    o.visible_shadow = False
    return o


def _in_view(x, y, lo=-40.0, hi=52.0, rmin=1.2):
    """Inside the view wedge of scenes 11-12 (heading -40 deg to +52 deg: 11 looks at 0 deg, the drift of 12 goes to +20 deg)."""
    if y < 0.5 or math.hypot(x, y) < rmin:
        return 0.0
    b = math.degrees(math.atan2(x, y))
    return 1.0 if lo <= b <= hi else 0.0


def _burn_keep(x, y):
    for (cx, cy), rx, ry in BURNS:
        if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1.3:
            return 0.0
    return 1.0


def build_grass(M, rnd, gust=None):
    tall_col = ps.model_collection("TallTufts")
    for k in range(3):
        o = tuft_mesh(f"TallTuft{k}", rnd, 0.72, 0.2, 12 + k, 0.032, lean=0.24)
        o.data.materials.append(M["tall"])
        ps._link_only(tall_col, o)
    far_col = ps.model_collection("TallFarTufts")
    for k in range(2):
        o = tuft_mesh(f"TallFarTuft{k}", rnd, 0.8, 0.45, 7, 0.09, lean=0.15)
        o.data.materials.append(M["tall_far"])
        ps._link_only(far_col, o)
    short_col = ps.model_collection("ShortTufts")
    # 7 shapes (review of the heroes, 2026-10-24: 3 identical 6-blade stars read as "rosettes" at 2-5 m):
    # different height, radius, number of blades, lean and sector, plus scale and height per instance and patches
    for k, (h, r, nb, w, lean, arc) in enumerate(((0.07, 0.06, 6, 0.014, 0.3, 1.0), (0.11, 0.05, 4, 0.012, 0.22, 0.45),
                                                  (0.05, 0.08, 9, 0.013, 0.45, 1.0), (0.09, 0.03, 3, 0.012, 0.15, 0.3),
                                                  (0.06, 0.1, 7, 0.015, 0.5, 0.6), (0.13, 0.04, 5, 0.011, 0.25, 0.5),
                                                  (0.04, 0.05, 5, 0.016, 0.55, 1.0))):
        o = tuft_mesh(f"ShortTuft{k}", rnd, h, r, nb, w, lean=lean, arc=arc)
        o.data.materials.append(M["short"])
        ps._link_only(short_col, o)
    near = patch("TallNear", -45.0, 70.0, 0.0, 60.0, 2.0,
                 lambda x, y: _in_view(x, y) * _burn_keep(x, y))
    near.modifiers.new("Tall", "NODES").node_group = scatter_ng("TallScatter", tall_col, 0.3, 9.0, 3, (0.85, 1.2),
                                                                 wind=(0.07, 0.35, 0.25), gust=gust)
    mid = patch("TallMid", -180.0, 320.0, 50.0, 330.0, 6.0,
                lambda x, y: _in_view(x, y) * (1.0 if math.hypot(x, y) > 58 else 0.0))
    mid.modifiers.new("TallMid", "NODES").node_group = scatter_ng("TallMidScatter", far_col, 1.1, 0.8, 5, (0.9, 1.3))
    short = patch("ShortNear", -16.0, 24.0, 0.0, 20.0, 1.0, lambda x, y: _in_view(x, y))
    short.modifiers.new("Short", "NODES").node_group = scatter_ng("ShortScatter", short_col, 0.065, 190.0, 9,
                                                                   (0.45, 1.1), wind=(0.04, 0.4, 0.3), rot_jitter=0.28,
                                                                   zscale=(0.55, 1.6), noise_density=(0.45, 0.4, 1.0))
    return SimpleNamespace(tall=[near, mid], short=[short])


# ---------- queimada ----------

def burns(M, rnd):
    """Black patches of old burn (only in 11): irregular black plate glued to the ground (+3 cm), ash edge and
    stumps of burnt grass."""
    geos, ash, stumps = [], [], []
    for (cx, cy), rx, ry in BURNS:
        n = 18
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            k = 1.0 + 0.22 * noise.noise(Vector((math.cos(a) * 2 + cx, math.sin(a) * 2 + cy, 0.5)))
            ring.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
        c = (cx, cy)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            tri = [(p[0], p[1], ground_z(*p) + 0.035) for p in (c, a, b)]
            geos.append((tri, [(0, 1, 2)]))
            a2 = (cx + (a[0] - cx) * 1.06, cy + (a[1] - cy) * 1.06)
            b2 = (cx + (b[0] - cx) * 1.06, cy + (b[1] - cy) * 1.06)
            quad = [(p[0], p[1], ground_z(*p) + 0.03) for p in (a, a2, b2, b)]
            ash.append((quad, [(0, 3, 2, 1)]))
        for _ in range(int(rx * ry * 5)):
            u, w = rnd.uniform(-0.85, 0.85), rnd.uniform(-0.85, 0.85)
            if u * u + w * w > 0.7:
                continue
            x, y = cx + u * rx, cy + w * ry
            h = rnd.uniform(0.06, 0.18)
            v, f = kit._prism_geo(4, 0.025, 0.012, h, oz=ground_z(x, y), ox=x, oy=y)
            stumps.append((v, f))
    v, f, _ = kit.merge(*geos)
    b = kit.mesh_object("Burns", v, f, [M["burn"]], tuple(ORIGIN))
    v, f, _ = kit.merge(*ash)
    a = kit.mesh_object("BurnAsh", v, f, [M["ash"]], tuple(ORIGIN))
    v, f, _ = kit.merge(*stumps)
    s = kit.mesh_object("BurnStumps", v, f, [M["stump"]], tuple(ORIGIN))
    for o in (b, a, s):
        kit.fix_normals(o)
        for p in o.data.polygons:
            if p.normal.z < 0:
                p.flip()
    return [b, a, s]


# ---------- trees, kopje and horizon ----------

def acacias(M, rnd):
    import acacia
    mats_old = {"trunk": M["trunk"], "crown": M["crown_old"]}
    mats_young = {"trunk": M["trunk"], "crown": M["crown_young"]}
    old = []
    for k, (x, y, h) in enumerate(OLD_ACACIAS):
        t, c = acacia.old(f"AcaciaOld{k}", (ORIGIN.x + x, ORIGIN.y + y, ground_z(x, y)), mats_old, random.Random(20 + k),
                          height=h)
        old.append((t, c))
    young = []
    for k, (x, y, h) in enumerate(YOUNG_ACACIAS):
        t, c = acacia.young(f"AcaciaYoung{k}", (ORIGIN.x + x, ORIGIN.y + y, ground_z(x, y)), mats_young,
                            random.Random(40 + k), height=h)
        young.append((t, c))
    # distant acacias scattered on the plain (flat silhouettes), the same in both scenes
    far = []
    base_t, base_c = acacia.old("AcaciaFarModel", (0, 0, -500), {"trunk": M["far_tree"], "crown": M["far_tree"]},
                                random.Random(77), height=8.0)
    for k in range(70):
        b = math.radians(rnd.uniform(-70, 80))
        d = rnd.uniform(250, 2600)
        x, y = math.sin(b) * d, math.cos(b) * d
        o = bpy.data.objects.new(f"AcaciaFar{k}", base_t.data)
        bpy.context.collection.objects.link(o)
        o.location = (ORIGIN.x + x, ORIGIN.y + y, ground_z(x, y))
        o.scale = (rnd.uniform(0.8, 1.3),) * 3
        o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
        oc = bpy.data.objects.new(f"AcaciaFar{k}Crown", base_c.data)
        bpy.context.collection.objects.link(oc)
        oc.parent = o
        far.append(o)
    base_t.hide_render = True
    base_c.hide_render = True
    return SimpleNamespace(old=old, young=young, far=far)


def kopje(M, rnd):
    """Kopje (granite inselberg): pile of rounded boulders of 10 to 45 m, ~70 m high, at ~3 km."""
    cx, cy = KOPJE
    geos = []
    for k in range(14):
        r = rnd.uniform(14, 45) * (1.0 if k < 5 else 0.6)
        x = cx + rnd.uniform(-150, 150)
        y = cy + rnd.uniform(-60, 60)
        z = ground_z(cx, cy) + r * rnd.uniform(0.2, 0.9) * (1.6 if abs(x - cx) < 60 else 0.8)
        geos.append(pm.lumpy_ico(r, (ORIGIN.x + x, ORIGIN.y + y, z), (1.2, 1.0, 0.8), rnd, 0.15))
    v, f, _ = kit.merge(*geos)
    o = kit.mesh_object("Kopje", v, f, [M["kopje"]])
    return o


def far_hills(M):
    """Low hills on the horizon (bluish, 45-55% air), so the horizon line is not ruler-straight."""
    def hz(x, y):
        return 40.0 + 45.0 * noise.noise(Vector((x * 0.0009, 0.3, 0.2))) + 35.0 * math.exp(-((x - 1500) / 1600) ** 2)
    o = ps.grid("SavFarHills", ORIGIN.x - 9000, ORIGIN.x + 9000, ORIGIN.y + 6500, ORIGIN.y + 7600, 300.0,
                lambda x, y: hz(x - ORIGIN.x, y) - 0.05 * abs(y - ORIGIN.y - 7000), [M["far_hill"]])
    o.visible_shadow = False
    return o


def build(rnd, gust=None):
    M = make_mats()
    t11 = terrain_mesh("SavTerrain11", [M["ground11"]])
    t12 = bpy.data.objects.new("SavTerrain12", t11.data.copy())
    bpy.context.collection.objects.link(t12)
    t12.location = t11.location
    t12.data.materials.clear()
    t12.data.materials.append(M["ground12"])
    grass = build_grass(M, rnd, gust=gust)
    burn = burns(M, rnd)
    ac = acacias(M, rnd)
    kp = kopje(M, rnd)
    hills = far_hills(M)
    cl = vs.clouds(M["cloud"], random.Random(9), center=ORIGIN, yaw0=0.0)
    return SimpleNamespace(M=M, t11=t11, t12=t12, grass=grass, burns=burn, acacias=ac, kopje=kp, hills=hills,
                           clouds=cl)
