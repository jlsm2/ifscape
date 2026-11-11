"""Space for moon-disappeared (Plan V2-B, scenes 08, 09 and the start of 10): low-poly Earth with two-tone ocean, clean
coasts (lat/lon texture generated here from the globe.py outlines), amber cities on the night side, Fresnel
atmosphere (no ring), Sun out of frame on the right (the same light lights Earth, Moon and planets), round stars in 3
sizes, faint Milky Way with a dust lane, slow orbital camera (±12°) and the instrument ruler (vertical
dashed line, amber axis, arc and degree label) attached to the camera.

Proportions and sources (direction.md V2-B and V2-G): tilt of 23.4° (NASA Space Place), rotation from west to east,
Moon radius 0.27 of the Earth's (NSSDC), Moon orbit in the plane (≈5°). Diagram not to scale, marked.
Units: the Earth has radius 1 m and sits at the ORIGIN (SPACE_E): the instrument layer has 1 px = 0.1 mm, and far from the origin
float32 precision broke the pieces (tested: at 20 km the label and the dashed line became blocks). The pier and all its lights
are hidden in the space frames (moon-disappeared.py, hide_pier_in_space).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import globe as gl
import kit
import moon_models as mm
from kit import lin

SPACE_E = Vector((0.0, 0.0, 0.0))
LENS_SP = 50.0
F_SP = 1920 / 36 * LENS_SP             # pixels per radian at 50 mm
R_E = 1.0
C_PX = (470.0, 590.0)                  # Earth center on screen (V2-B)
ELEV = 8.0                             # camera 8° above the orbit plane
SUN_DIR = Vector((math.cos(math.radians(25)), -math.sin(math.radians(25)), 0.0))   # heading to the Sun: to the right and 25° to the side
# of the camera (round 7: with the Sun at 90° the day side was only the grazing half-moon, dark; this way ~70% of the disc reads blue-green)
AXIS_PX = 340.0                        # half axis on screen (680 px in total)
INSTR_D = 0.25                         # depth of the instrument layer (in front of the fade plane, 0.3 m)


# ---------- camera ----------

def basis(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    fwd = Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p)))
    right = Vector((math.cos(y), -math.sin(y), 0.0))
    up = Vector((-math.sin(y) * math.sin(p), -math.cos(y) * math.sin(p), math.cos(p)))
    return fwd, right, up


def proj(P, cam, yaw, pitch, f_px=F_SP):
    fwd, right, up = basis(yaw, pitch)
    d = Vector(P) - cam
    z = d.dot(fwd)
    return 540 + f_px * d.dot(right) / z, 960 - f_px * d.dot(up) / z


def cam_pose(phi, r_px):
    """(position, yaw, pitch) of the orbiting camera: azimuth phi (degrees) around the vertical through the Earth,
    elevation ELEV, distance that gives the Earth radius r_px on screen, and aim that puts the Earth's center at C_PX."""
    D = R_E / math.sin(math.atan(r_px / F_SP))
    e, p = math.radians(ELEV), math.radians(phi)
    d = Vector((math.sin(p) * math.cos(e), math.cos(p) * math.cos(e), -math.sin(e)))
    pos = SPACE_E - d * D
    yaw, pitch = phi, -ELEV
    for _ in range(12):
        x, y = proj(SPACE_E, pos, yaw, pitch)
        yaw += math.degrees(math.atan((x - C_PX[0]) / F_SP))
        pitch -= math.degrees(math.atan((y - C_PX[1]) / F_SP))
    return pos, yaw, pitch


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


class Orbit:
    """Camera orbit from f0 to f1 (a single ease-in-out across the 3 scenes): azimuth -12 -> +12 and radius 250 -> 262 px."""

    def __init__(self, f0, f1):
        self.f0, self.f1 = f0, f1

    def u(self, f):
        return smooth((f - self.f0) / (self.f1 - self.f0))

    def phi(self, f):
        return -12.0 + 24.0 * self.u(f)

    def r_px(self, f):
        return 250.0 + 12.0 * self.u(f)

    def pose(self, f):
        return cam_pose(self.phi(f), self.r_px(f))


def axis_dir(theta_deg):
    t = math.radians(theta_deg)
    return Vector((math.sin(t), 0.0, math.cos(t)))      # top tilted toward +x (right, toward the Sun)


def screen_angle(theta_deg, pose):
    """On-screen angle (degrees, clockwise from the vertical) of the 3D axis with tilt theta, seen from the pose."""
    pos, yaw, pitch = pose
    a = axis_dir(theta_deg) * (R_E * AXIS_PX / 250.0)
    x0, y0 = proj(SPACE_E - a, pos, yaw, pitch)
    x1, y1 = proj(SPACE_E + a, pos, yaw, pitch)
    return math.degrees(math.atan2(x1 - x0, -(y1 - y0)))


# ---------- Earth textures ----------

def _box_blur(a, r, axis, wrap):
    import numpy as np
    if r < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    b = np.pad(a, pad, mode="wrap" if wrap else "edge")
    c = np.cumsum(b, axis=axis, dtype=np.float64)
    hi = np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, range(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def _blur(a, r):
    for _ in range(2):
        a = _box_blur(a, r, 1, True)
        a = _box_blur(a, r, 0, False)
    return a


CITIES = [  # (lat, lon, weight): real metropolises (strongest night-light points)
    (40.7, -74.0, 1.0), (38.9, -77.0, 0.8), (42.3, -71.0, 0.8), (41.9, -87.6, 0.9), (34.0, -118.2, 1.0), (37.8, -122.4, 0.8),
    (29.8, -95.4, 0.8), (33.7, -84.4, 0.7), (25.8, -80.2, 0.7), (19.4, -99.1, 1.0), (43.7, -79.4, 0.7), (45.5, -73.6, 0.6),
    (47.6, -122.3, 0.6), (32.8, -96.8, 0.7), (-23.5, -46.6, 1.0), (-22.9, -43.2, 0.9), (-34.6, -58.4, 0.9), (-12.0, -77.0, 0.7),
    (4.7, -74.1, 0.7), (-33.4, -70.6, 0.7), (10.5, -66.9, 0.6), (51.5, -0.1, 1.0), (48.9, 2.4, 1.0), (52.5, 13.4, 0.8),
    (40.4, -3.7, 0.8), (41.9, 12.5, 0.7), (45.5, 9.2, 0.7), (50.9, 4.4, 0.7), (55.8, 37.6, 1.0), (59.9, 30.3, 0.7),
    (50.4, 30.5, 0.6), (41.0, 29.0, 0.9), (30.0, 31.2, 1.0), (6.5, 3.4, 0.9), (-26.2, 28.0, 0.8), (-1.3, 36.8, 0.6),
    (24.7, 46.7, 0.7), (25.2, 55.3, 0.7), (35.7, 51.4, 0.8), (28.6, 77.2, 1.0), (19.1, 72.9, 1.0), (12.9, 77.6, 0.8),
    (22.6, 88.4, 0.9), (23.8, 90.4, 0.9), (13.7, 100.5, 0.8), (1.35, 103.8, 0.7), (-6.2, 106.8, 0.9), (39.9, 116.4, 1.0),
    (31.2, 121.5, 1.0), (23.1, 113.3, 1.0), (30.6, 104.1, 0.7), (35.7, 139.7, 1.0), (34.7, 135.5, 0.8), (37.5, 127.0, 0.9),
    (-33.9, 151.2, 0.7), (-37.8, 145.0, 0.6), (14.6, 121.0, 0.8), (21.0, 105.8, 0.6), (33.6, 73.0, 0.7), (24.9, 67.0, 0.8),
]


def earth_textures(W=2048, H=1024):
    """(sRGB albedo, masks R=city G=land) in lat/lon (row 0 = south pole). Today's outlines from globe.py
    (rasterized with 2x2 samples: clean coast), two-tone ocean (shelf near the coasts), ocher desert in the
    subtropical interior, ice at the poles and in Greenland/Antarctica, cities as Gaussian points."""
    import numpy as np
    W2, H2 = 2 * W, 2 * H
    lon = (-180.0 + (np.arange(W2) + 0.5) * 360.0 / W2).astype(np.float64)
    lat = (-90.0 + (np.arange(H2) + 0.5) * 180.0 / H2).astype(np.float64)
    land = np.zeros((H2, W2), bool)
    icy = np.zeros((H2, W2), bool)
    for name, poly in gl.MODERN.items():
        inside = np.zeros((H2, W2), bool)
        n = len(poly)
        for i in range(n):
            (alat, alon), (blat, blon) = poly[i], poly[(i + 1) % n]
            if alon == blon:
                continue
            lo, hi = min(alon, blon), max(alon, blon)
            cols = np.where((lon >= lo) & (lon < hi))[0]
            if cols.size == 0:
                continue
            c = alat + (lon[cols] - alon) * (blat - alat) / (blon - alon)
            inside[:, cols] ^= (lat[:, None] < c[None, :])
        land |= inside
        if name in ("Antarctica", "Greenland"):
            icy |= inside
    cov = land.reshape(H, 2, W, 2).mean(axis=(1, 3)).astype(np.float32)
    ice = icy.reshape(H, 2, W, 2).mean(axis=(1, 3)).astype(np.float32)
    lat1 = (-90.0 + (np.arange(H) + 0.5) * 180.0 / H)[:, None]
    lon1 = (-180.0 + (np.arange(W) + 0.5) * 360.0 / W)[None, :]
    alat = np.abs(lat1)
    px_deg = W / 360.0
    shelf = _blur(cov, int(3.2 * px_deg))
    shelf_t = np.clip((shelf - 0.02) / 0.22, 0, 1)
    shelf_t = shelf_t * shelf_t * (3 - 2 * shelf_t)
    inland = _blur(cov, int(5.0 * px_deg))
    band = np.clip(1 - np.abs(alat - 25.0) / 13.0, 0, 1)
    desert_t = np.clip((inland - 0.86) / 0.1, 0, 1) * np.clip(band * 2.0, 0, 1)
    ice_t = np.maximum(ice, np.clip((alat - 70.0) / 3.0, 0, 1) * cov)
    sea_ice = np.clip((lat1 - 81.0) / 2.0, 0, 1)                  # Arctic pack ice (hides the pole from the UV)

    def c(h):
        return np.array(lin(h)[:3], np.float32)

    deep, shelf_c, green, ocre, icec = c("#1F4E8C"), c("#2E6DB4"), c("#4E8A3C"), c("#B59A5A"), c("#EEF3F8")
    green2 = c("#5E9446")
    rnd = np.random.default_rng(4)
    vary = _blur(rnd.random((H, W)).astype(np.float32), 12)
    vary = np.clip((vary - vary.mean()) * 8 + 0.5, 0, 1)
    landc = green[None, None, :] * (1 - vary[..., None]) + green2[None, None, :] * vary[..., None]
    landc = landc * (1 - desert_t[..., None]) + ocre[None, None, :] * desert_t[..., None]
    landc = landc * (1 - ice_t[..., None]) + icec[None, None, :] * ice_t[..., None]
    sea = deep[None, None, :] * (1 - shelf_t[..., None]) + shelf_c[None, None, :] * shelf_t[..., None]
    sea = sea * (1 - sea_ice[..., None]) + icec[None, None, :] * sea_ice[..., None]
    col = sea * (1 - cov[..., None]) + landc * cov[..., None]
    srgb = np.where(col <= 0.0031308, col * 12.92, 1.055 * np.power(np.clip(col, 0, None), 1 / 2.4) - 0.055)
    # cities: Gaussians (radius ~1°, >= 6 px on screen), plus smaller towns near each metropolis
    city = np.zeros((H, W), np.float32)
    rr = random.Random(11)
    dots = []
    for la, lo, w in CITIES:
        dots.append((la, lo, 0.9, w))
        for _ in range(3):
            dots.append((la + rr.uniform(-4, 4), lo + rr.uniform(-5, 5), 0.55, 0.45 * w))
    for la, lo, r, w in dots:
        j0, j1 = int((la - 3 * r + 90) / 180 * H), int((la + 3 * r + 90) / 180 * H) + 1
        cl = max(math.cos(math.radians(la)), 0.2)
        span = 3 * r / cl
        cols = np.arange(int((lo - span + 180) / 360 * W), int((lo + span + 180) / 360 * W) + 1) % W
        rows = np.arange(max(j0, 0), min(j1, H))
        dl = (lat1[rows, :] - la)
        dlo = ((lon1[:, cols] - lo + 180) % 360 - 180) * cl
        val = w * np.exp(-(dl * dl + dlo * dlo) / (r * r))
        sub = city[np.ix_(rows, cols)]
        city[np.ix_(rows, cols)] = np.maximum(sub, val.astype(np.float32))
    city *= np.clip(cov * 1.5, 0, 1) * (1 - ice_t)

    def to_img(name, rgb, colorspace):
        img = bpy.data.images.new(name, W, H, alpha=False)
        img.colorspace_settings.name = colorspace
        px = np.ones((H, W, 4), np.float32)
        px[..., :3] = rgb
        img.pixels.foreach_set(px.ravel())
        img.pack()
        return img

    alb = to_img("EarthAlbedo", np.clip(srgb, 0, 1), "sRGB")
    m = np.zeros((H, W, 3), np.float32)
    m[..., 0], m[..., 1] = np.clip(city, 0, 1), cov
    msk = to_img("EarthMasks", m, "Non-Color")
    return alb, msk


# ---------- Earth ----------

def _node(n, kind, **inputs):
    nd = n.new(kind)
    for k, v in inputs.items():
        nd.inputs[k].default_value = v
    return nd


def _math(n, links, op, a, b=None, clamp=False):
    m = n.new("ShaderNodeMath")
    m.operation = op
    m.use_clamp = clamp
    for k, src in enumerate((a, b)):
        if src is None:
            continue
        if isinstance(src, (int, float)):
            m.inputs[k].default_value = src
        else:
            links.new(src, m.inputs[k])
    return m.outputs[0]


def _maprange(n, links, src, a, b, c=0.0, d=1.0, smoothstep=True):
    mr = n.new("ShaderNodeMapRange")
    if smoothstep:
        mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = a, b
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = c, d
    links.new(src, mr.inputs["Value"])
    return mr.outputs["Result"]


def _sun_dot(n, links):
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(geo.outputs["Normal"], dot.inputs[0])
    dot.inputs[1].default_value = tuple(SUN_DIR)
    return dot.outputs["Value"], geo


def _mixc(n, links, fac, a, b):
    m = n.new("ShaderNodeMix")
    m.data_type = "RGBA"
    for sock, v in ((m.inputs["Factor"], fac), (m.inputs["A"], a), (m.inputs["B"], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            links.new(v, sock)
    return m.outputs["Result"]


CITY_K = 0.9            # city emission (below the bloom threshold of 1.0)


def earth(name="SpaceEarth"):
    """Earth (radius 1 m, level-4 icosphere with flat faces) with lat/lon UV per face corner (no seam).
    Returns SimpleNamespace(tilt, spin, mesh, atmo, north, south) — north/south: summer/winter tint factors."""
    alb, msk = earth_textures()
    verts, faces = gl.ico_sphere(4)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v * R_E) for v in verts], [], faces)
    uv = me.uv_layers.new(name="LatLon")
    for poly in me.polygons:
        lis = list(poly.loop_indices)
        ll = [gl.to_latlon(verts[me.loops[li].vertex_index]) for li in lis]
        lons = [lo for _, lo in ll]
        if max(lons) - min(lons) > 180:
            lons = [lo + 360 if lo < 0 else lo for lo in lons]
        for li, (la, _), lo in zip(lis, ll, lons):
            uv.data[li].uv = (lo / 360.0 + 0.5, la / 180.0 + 0.5)
        poly.use_smooth = False
    mat, n, links, out = mm.node_mat(name + "Mat")
    uvn = n.new("ShaderNodeUVMap")
    uvn.uv_map = "LatLon"
    ta, tmk = n.new("ShaderNodeTexImage"), n.new("ShaderNodeTexImage")
    for t, img in ((ta, alb), (tmk, msk)):
        t.image, t.interpolation, t.extension = img, "Linear", "REPEAT"
        links.new(uvn.outputs["UV"], t.inputs["Vector"])
    sep = n.new("ShaderNodeSeparateColor")
    links.new(tmk.outputs["Color"], sep.inputs["Color"])
    city, landm = sep.outputs[0], sep.outputs[1]
    tc = n.new("ShaderNodeTexCoord")
    sxyz = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sxyz.inputs[0])
    north = _maprange(n, links, sxyz.outputs["Z"], -0.06, 0.06)
    south = _math(n, links, "SUBTRACT", 1.0, north)
    nk, sk = n.new("ShaderNodeValue"), n.new("ShaderNodeValue")
    nk.outputs[0].default_value = sk.outputs[0].default_value = 0.0
    # summer/winter (round 7, art.md K A1-d): mixing 15% amber/blue into the base color left the ocean lilac and opaque.
    # Now the northern summer is MORE SUN (the albedo itself added as emission on the lit side: stays blue-green and
    # saturated) and the southern winter is a bit colder (9% ice-blue in the base).
    base = _mixc(n, links, _math(n, links, "MULTIPLY", south, _math(n, links, "MULTIPLY", sk.outputs[0], 0.6)),
                 ta.outputs["Color"], lin("#8EC2FF"))
    p = n.new("ShaderNodeBsdfPrincipled")
    links.new(base, p.inputs["Base Color"])
    links.new(_maprange(n, links, landm, 0.0, 1.0, 0.35, 0.9, smoothstep=False), p.inputs["Roughness"])
    p.inputs["Specular IOR Level"].default_value = 0.0            # the Sun's shine comes from the smooth-normal glossy (below)
    sd, _ = _sun_dot(n, links)
    night = _maprange(n, links, sd, 0.10, -0.20)
    lit = _maprange(n, links, sd, -0.05, 0.35)
    # night-side floor (bible 1.8): faint self-glow added to the WHOLE disc (no mask): the terminator never
    # gets darker than the night (before: floor only on the night = dark valley in the middle of the disc). Amber cities only at night.
    glow = n.new("ShaderNodeVectorMath")
    glow.operation = "MULTIPLY_ADD"
    links.new(ta.outputs["Color"], glow.inputs[0])
    glow.inputs[1].default_value = (0.12, 0.12, 0.12)
    glow.inputs[2].default_value = lin("#0E1628")[:3]
    cityc = n.new("ShaderNodeVectorMath")
    cityc.operation = "SCALE"
    links.new(_math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", city, CITY_K), night), cityc.inputs["Scale"])
    cityc.inputs[0].default_value = lin("#F5A524")[:3]
    summer = n.new("ShaderNodeVectorMath")
    summer.operation = "SCALE"
    links.new(ta.outputs["Color"], summer.inputs[0])
    links.new(_math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", north, nk.outputs[0]), _math(n, links, "MULTIPLY", lit, 2.4)),
              summer.inputs["Scale"])
    em1 = n.new("ShaderNodeVectorMath")
    em1.operation = "ADD"
    links.new(glow.outputs[0], em1.inputs[0])
    links.new(cityc.outputs[0], em1.inputs[1])
    em2 = n.new("ShaderNodeVectorMath")
    em2.operation = "ADD"
    links.new(em1.outputs[0], em2.inputs[0])
    links.new(summer.outputs[0], em2.inputs[1])
    links.new(em2.outputs[0], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.0
    # Sun shine on the ocean with a SMOOTH NORMAL (normalized sphere position -> world): a round spot, not the hexagon
    # of the facets (the facets stay in the diffuse)
    nrm = n.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    links.new(tc.outputs["Object"], nrm.inputs[0])
    vt = n.new("ShaderNodeVectorTransform")
    vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "OBJECT", "WORLD"
    links.new(nrm.outputs[0], vt.inputs[0])
    gl_ = n.new("ShaderNodeBsdfGlossy")
    gl_.inputs["Roughness"].default_value = 0.42
    links.new(vt.outputs[0], gl_.inputs["Normal"])
    lw = n.new("ShaderNodeLayerWeight")
    links.new(vt.outputs[0], lw.inputs["Normal"])
    ocean = _math(n, links, "SUBTRACT", 1.0, landm)
    ocean = _math(n, links, "MULTIPLY", ocean, _math(n, links, "POWER", _math(n, links, "SUBTRACT", 1.0, lw.outputs["Facing"]), 1.5))
    gcol = n.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        links.new(_math(n, links, "MULTIPLY", ocean, 0.05), gcol.inputs[ch])
    links.new(gcol.outputs[0], gl_.inputs["Color"])
    addsh = n.new("ShaderNodeAddShader")
    links.new(p.outputs[0], addsh.inputs[0])
    links.new(gl_.outputs[0], addsh.inputs[1])
    links.new(addsh.outputs[0], out.inputs["Surface"])
    me.materials.append(mat)
    mesh = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(mesh)
    mesh.visible_shadow = False
    tilt = bpy.data.objects.new(name + "Tilt", None)
    bpy.context.collection.objects.link(tilt)
    tilt.location = SPACE_E
    tilt.rotation_mode = "XYZ"
    spin = bpy.data.objects.new(name + "Spin", None)
    bpy.context.collection.objects.link(spin)
    spin.parent = tilt
    spin.rotation_mode = "XYZ"
    mesh.parent = spin
    atmo = atmosphere(name + "Atmo")
    atmo.parent = tilt
    return SimpleNamespace(tilt=tilt, spin=spin, mesh=mesh, atmo=atmo, north=nk.outputs[0], south=sk.outputs[0])


ATMO_R = 1.045


def atmosphere(name):
    """Additive 1.045 R shell: #8EC2FF glow that starts near the limb and fades outward (no hard outline); 1.0 on the
    Sun side and 0.25 on the night side."""
    import bmesh
    mat, n, links, out = mm.node_mat(name + "Mat")
    sd, geo = _sun_dot(n, links)
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(geo.outputs["Normal"], dot.inputs[0])
    links.new(geo.outputs["Incoming"], dot.inputs[1])
    c = _math(n, links, "ABSOLUTE", dot.outputs["Value"])
    b = _math(n, links, "MULTIPLY", _math(n, links, "SQRT", _math(n, links, "SUBTRACT", 1.0, _math(n, links, "MULTIPLY", c, c),
                                                                  clamp=True)), ATMO_R)
    inner = _maprange(n, links, b, 0.935, 1.0)
    inner = _math(n, links, "MULTIPLY", inner, inner)
    outer = _maprange(n, links, b, 0.995, ATMO_R, 1.0, 0.0)
    # Sun mask (bible 1.8, round 7): strong on the day side, almost nothing at night (with 0.12 at night the rim added to the
    # dark disc read the same on both sides: glass ball)
    side = _maprange(n, links, sd, -0.25, 0.45, 0.025, 1.1)
    k = _math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", inner, outer), side)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#8EC2FF")
    links.new(_math(n, links, "MULTIPLY", k, 1.0), em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=R_E * ATMO_R)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.visible_shadow = False
    return o


# ---------- round stars (pier and space) ----------

WARM_STAR, COLD_STAR, WHITE_STAR = "#FFE2B8", "#CFE0FF", "#E8EEFF"


def star_spec(rnd):
    """(size px, brightness, tint) of a star: 3 sizes (3, 4, 6 px), 3 brightnesses (0.35/0.6/1.0), 5% warm and 5% cool."""
    s = rnd.choices((3.0, 4.0, 6.0), (0.62, 0.28, 0.10))[0]
    b = rnd.choices((0.35, 0.6, 1.0), (0.55, 0.32, 0.13) if s < 6 else (0.1, 0.4, 0.5))[0]
    r = rnd.random()
    tint = WARM_STAR if r < 0.05 else COLD_STAR if r < 0.10 else WHITE_STAR
    return s, b, tint


def round_stars(name, center, R, pts, f_px, inner_k=0.3):
    """pts = [(direction, rank, size px, brightness, tint)]. Each star is an 8-sided disc facing the center, with
    emission falling from the center to the edge (round soft-edged dot, additive). 'rnd' = lighting order (reveal).
    Returns (object, reveal socket 0..1.2, strength socket)."""
    verts, faces, rad, rnk, bri, tints = [], [], [], [], [], []
    c = Vector(center)
    for d, rank, size, b, tint in pts:
        d = d.normalized()
        u = d.cross(Vector((0, 0, 1)))
        if u.length < 1e-3:
            u = d.cross(Vector((1, 0, 0)))
        u.normalize()
        v = d.cross(u)
        rw = size * 0.5 * 1.35 / f_px * R
        p = c + d * R
        base = len(verts)
        verts.append(tuple(p))
        for i in range(8):
            a = 2 * math.pi * i / 8
            verts.append(tuple(p + (u * math.cos(a) + v * math.sin(a)) * rw))
        for i in range(8):
            faces.append((base, base + 1 + (i + 1) % 8, base + 1 + i))
        rad += [1.0] + [0.0] * 8
        rnk += [rank] * 9
        bri += [b] * 9
        tints += [lin(tint)] * 9
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for key, vals in (("rad", rad), ("rnd", rnk), ("bri", bri)):
        at = me.attributes.new(key, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)
    ct = me.attributes.new("tint", "FLOAT_COLOR", "POINT")
    ct.data.foreach_set("color", [x for t in tints for x in t])
    mat, n, links, out = mm.node_mat(name + "Mat")
    a_rad, a_rnk, a_bri, a_tint = (n.new("ShaderNodeAttribute") for _ in range(4))
    for a_, nm in ((a_rad, "rad"), (a_rnk, "rnd"), (a_bri, "bri"), (a_tint, "tint")):
        a_.attribute_name = nm
    fall = _math(n, links, "POWER", a_rad.outputs["Fac"], 1.6)
    reveal, power = n.new("ShaderNodeValue"), n.new("ShaderNodeValue")
    reveal.outputs[0].default_value, power.outputs[0].default_value = 1.2, 1.0
    on = _maprange(n, links, _math(n, links, "SUBTRACT", reveal.outputs[0], a_rnk.outputs["Fac"]), 0.0, 0.15, smoothstep=False)
    k = _math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", fall, a_bri.outputs["Fac"]), on)
    k = _math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", k, power.outputs[0]), inner_k)
    em = n.new("ShaderNodeEmission")
    links.new(a_tint.outputs["Color"], em.inputs["Color"])
    links.new(k, em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    me.materials.append(mat)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.visible_shadow = False
    obj.visible_diffuse = obj.visible_glossy = False
    return obj, reveal.outputs[0], power.outputs[0]


def _sphere_point(rnd):
    while True:
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if 0.05 < v.length <= 1.0:
            return v.normalized()


def pier_stars(band_normal, R=1500.0, f_px=1920 / 36 * 22, count=2200, band_count=1800, seed=5):
    """Pier star dome (replaces the town_sky octahedron stars: same square confetti): same
    distribution (half above the horizon, denser Milky Way band), round discs in 3 sizes."""
    rnd = random.Random(seed)
    pts = []
    while len(pts) < count:
        d = _sphere_point(rnd)
        if d.z > -0.05:
            pts.append((d, rnd.random(), *star_spec(rnd)))
    while len(pts) < count + band_count:
        d = _sphere_point(rnd)
        if d.z > -0.05 and abs(d.dot(band_normal)) < 0.14 * rnd.random() ** 0.7:
            pts.append((d, rnd.random() * 0.8 + 0.2, *star_spec(rnd)))
    obj, reveal, power = round_stars("Stars", (0, 0, 0), R, pts, f_px)
    # origin in front of the camera (Eevee sorts translucent objects by origin; at the world origin, behind the camera, the
    # stars were drawn on top of the dark cut plane)
    off = Vector((0.0, R, 0.2 * R))
    obj.data.transform(Matrix.Translation(-off))
    obj.location = off
    return obj, reveal, power


def space_band_normal():
    """Normal of the Milky Way plane in space: the band crosses the frame diagonally (from bottom left to top
    right), passing slightly above the center."""
    pos, yaw, pitch = cam_pose(0.0, 256.0)
    fwd, right, up = basis(yaw, pitch)
    toward = (fwd + up * 0.12).normalized()
    diag = (right * 0.55 + up * 0.83).normalized()
    return toward.cross(diag).normalized()


def space_sky(band_n):
    """Space background: closed emissive sphere (radius 500 m) around the Earth, blue-black #05070F with the faint
    Milky Way (max #1C2238) and a dark dust lane in the middle; round stars only in the stretch the orbit sees."""
    mat, n, links, out = mm.node_mat("SpaceSkyMat")
    tc = n.new("ShaderNodeTexCoord")
    nrm = n.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    links.new(tc.outputs["Object"], nrm.inputs[0])
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(nrm.outputs[0], dot.inputs[0])
    dot.inputs[1].default_value = tuple(band_n)
    t = _math(n, links, "ABSOLUTE", dot.outputs["Value"])
    glow = _maprange(n, links, t, 0.0, 0.26, 1.0, 0.0)
    glow = _math(n, links, "POWER", glow, 1.6)
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 3.0, 4.0
    links.new(nrm.outputs[0], nz.inputs["Vector"])
    glow = _math(n, links, "MULTIPLY", glow, _maprange(n, links, nz.outputs["Fac"], 0.35, 0.7, 0.35, 1.0))
    # dust: narrow band, slightly off center, broken by stretched noise
    lane = _maprange(n, links, _math(n, links, "ABSOLUTE", _math(n, links, "SUBTRACT", dot.outputs["Value"], 0.012)), 0.0, 0.045,
                     1.0, 0.0)
    nz2 = n.new("ShaderNodeTexNoise")
    nz2.inputs["Scale"].default_value, nz2.inputs["Detail"].default_value = 7.0, 3.0
    links.new(nrm.outputs[0], nz2.inputs["Vector"])
    lane = _math(n, links, "MULTIPLY", lane, _maprange(n, links, nz2.outputs["Fac"], 0.35, 0.6, 0.2, 0.9))
    glow = _math(n, links, "MULTIPLY", glow, _math(n, links, "SUBTRACT", 1.0, lane, clamp=True))
    col = _mixc(n, links, glow, lin("#05070F"), lin("#1C2238"))
    em = n.new("ShaderNodeEmission")
    links.new(col, em.inputs["Color"])
    links.new(em.outputs[0], out.inputs["Surface"])
    v, f = gl.ico_sphere(3)
    shell = kit.mesh_object("SpaceSky", [tuple(SPACE_E + p * 500.0) for p in v], [tuple(reversed(x)) for x in f], [mat])
    for p in shell.data.polygons:
        p.use_smooth = True
    shell.visible_shadow = False
    shell.visible_diffuse = shell.visible_glossy = False
    # stars: azimuth -40..40 and elevation -48..14 (what the orbit sees, with margin); ~900 in frame
    rnd = random.Random(17)
    pts = []
    while len(pts) < 3400:
        az = math.radians(rnd.uniform(-40, 40))
        el = math.asin(rnd.uniform(math.sin(math.radians(-48)), math.sin(math.radians(14))))
        d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        pts.append((d, 0.0, *star_spec(rnd)))
    k = 0
    while k < 1300:
        az = math.radians(rnd.uniform(-40, 40))
        el = math.asin(rnd.uniform(math.sin(math.radians(-48)), math.sin(math.radians(14))))
        d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        if abs(d.dot(band_n)) < 0.12 * rnd.random() ** 0.7:
            pts.append((d, 0.0, *star_spec(rnd)))
            k += 1
    stars, _, power = round_stars("SpaceStars", SPACE_E, 300.0, pts, F_SP)
    power.default_value = 5.0
    return shell, stars


def sun_glow(cam):
    """Sun glow entering from the right edge: additive plane child of the camera, behind the Earth (40 m), radial
    gradient centered outside the frame (x 1250, y 560), radius 700 px, #FFE7C2 at ~18% at the frame edge."""
    d = 40.0
    s = d / F_SP
    mat, n, links, out = mm.node_mat("SunGlowMat")
    tc = n.new("ShaderNodeTexCoord")
    sub = n.new("ShaderNodeVectorMath")
    sub.operation = "DISTANCE"
    links.new(tc.outputs["Object"], sub.inputs[0])
    sub.inputs[1].default_value = (1150 - 540, -(560 - 960), 0.0)
    # round 7 (bible 1.9): warm, LIGHT core at the edge (>= #C8A070 at x 1080) and fast falloff (~400 px); before, #FFE7C2
    # at ~18% over navy blue turned into a brown stain
    fall = _maprange(n, links, sub.outputs["Value"], 0.0, 430.0, 1.0, 0.0, smoothstep=False)
    fall = _math(n, links, "POWER", fall, 3.2)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin("#FFE6C4")
    k = _math(n, links, "MULTIPLY", fall, 1.6)
    links.new(k, em.inputs["Strength"])
    add = n.new("ShaderNodeAddShader")
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    xs, ys = (0.0, 700.0), (-1100.0, 1100.0)
    verts = [(xs[0], ys[0], 0), (xs[1], ys[0], 0), (xs[1], ys[1], 0), (xs[0], ys[1], 0)]
    o = kit.mesh_object("SunGlow", verts, [(0, 1, 2, 3)], [mat])
    o.parent = cam
    o.location = (0, 0, -d)
    o.scale = (s, s, s)
    o.visible_shadow = False
    return o


# ---------- Moon, ring and planets ----------

def lit_fade(name, color, rough=0.85):
    """Principled lit by the Sun, which vanishes by alpha (BLENDED). Returns (mat, alpha socket, nodes, links, principled)."""
    mat = kit.flat(name, color, rough=rough)
    p = kit.principled(mat)
    p.inputs["Alpha"].default_value = 1.0
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True          # in the fade (alpha < 1) the lit back face showed through (B-2: no terminator)
    return mat, p.inputs["Alpha"], mat.node_tree.nodes, mat.node_tree.links, p


def dim_socket(mat):
    """Darkener (Value 0..1) on the base color and the emission of the Principled (round 7, B-2): in Eevee 5.2 a Principled with
    alpha < 1 comes out lit across the whole disc (loses the terminator). The fade becomes: the color rises from black in 6 frames and the
    alpha only changes in the 2 end frames (with the color almost at zero). Returns the Value socket."""
    nt = mat.node_tree
    p = kit.principled(mat)
    v = nt.nodes.new("ShaderNodeValue")
    v.outputs[0].default_value = 1.0
    for name in ("Base Color", "Emission Color"):
        sock = p.inputs[name]
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        if sock.is_linked:
            src = sock.links[0].from_socket
            nt.links.new(src, mx.inputs["A"])
        else:
            mx.inputs["A"].default_value = tuple(sock.default_value)
        cb = nt.nodes.new("ShaderNodeCombineColor")
        for ch in ("Red", "Green", "Blue"):
            nt.links.new(v.outputs[0], cb.inputs[ch])
        nt.links.new(cb.outputs[0], mx.inputs["B"])
        nt.links.new(mx.outputs["Result"], sock)
    return v.outputs[0]


def uv_ball(name, r, mat, seg=32, rings=16, smooth_=False):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth_
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.visible_shadow = False
    return o


def little_moon(r):
    """Gray Moon #CFCFC8 with 3 maria #9C9C96 (spots by direction, soft edge), lit by the Sun."""
    mat, alpha, n, links, p = lit_fade("SpaceMoonMat", "#CFCFC8", rough=0.95)
    tc = n.new("ShaderNodeTexCoord")
    nrm = n.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    links.new(tc.outputs["Object"], nrm.inputs[0])
    acc = None
    for d, cosr in (((-0.3, -0.85, 0.42), 0.93), ((0.25, -0.9, 0.2), 0.95), ((-0.1, -0.93, -0.3), 0.96)):
        dt = n.new("ShaderNodeVectorMath")
        dt.operation = "DOT_PRODUCT"
        links.new(nrm.outputs[0], dt.inputs[0])
        dt.inputs[1].default_value = Vector(d).normalized()
        m = _maprange(n, links, dt.outputs["Value"], cosr - 0.015, cosr + 0.01)
        acc = m if acc is None else _math(n, links, "MAXIMUM", acc, m)
    links.new(_mixc(n, links, acc, lin("#CFCFC8"), lin("#9C9C96")), p.inputs["Base Color"])
    return uv_ball("SpaceMoon", r, mat, 40, 20, smooth_=True), alpha


def ring_mesh(name, radius, tube, dashed=False, seg=180):
    """Ring in the XY plane (orbit) of radius 'radius' around the origin; dashed: 5° of dash and 3° of gap."""
    parts = []
    if not dashed:
        pts = [(radius * math.cos(2 * math.pi * i / seg), radius * math.sin(2 * math.pi * i / seg), 0.0) for i in range(seg + 1)]
        parts.append(kit.tube_geo(pts, [tube] * len(pts), n=6))
    else:
        a = 0.0
        while a < 360.0 - 1e-6:
            pts = [(radius * math.cos(math.radians(a + 5.0 * k / 4)), radius * math.sin(math.radians(a + 5.0 * k / 4)), 0.0)
                   for k in range(5)]
            parts.append(kit.tube_geo(pts, [tube] * 5, n=6))
            a += 8.0
    v, f, _ = kit.merge(*parts)
    return v, f


def banded_mat(name, colors, bands, r):
    """Horizontal bands (Jupiter) by the object's z coordinate."""
    mat, alpha, n, links, p = lit_fade(name, colors[0], rough=0.9)
    tc = n.new("ShaderNodeTexCoord")
    sxyz = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sxyz.inputs[0])
    w = _math(n, links, "SINE", _math(n, links, "MULTIPLY", sxyz.outputs["Z"], math.pi * bands / r))
    links.new(_mixc(n, links, _maprange(n, links, w, -0.25, 0.25), lin(colors[0]), lin(colors[1])), p.inputs["Base Color"])
    return mat, alpha


def ring_disc(name, r0, r1, mats_split, mat):
    """Flat Saturn ring (r0 to r1), 2 tones by distance (material with mix)."""
    seg = 64
    v = [(rr * math.cos(2 * math.pi * i / seg), rr * math.sin(2 * math.pi * i / seg), 0.0) for rr in (r0, r1) for i in range(seg)]
    f = [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    o = kit.mesh_object(name, v, f, [mat])
    o.visible_shadow = False
    return o


def saturn_ring_mat(name, r0, r1):
    mat, alpha, n, links, p = lit_fade(name, "#CDB98E", rough=0.9)
    tc = n.new("ShaderNodeTexCoord")
    ln = n.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    links.new(tc.outputs["Object"], ln.inputs[0])
    t = _maprange(n, links, ln.outputs["Value"], r0 + 0.55 * (r1 - r0), r0 + 0.6 * (r1 - r0))
    col = _mixc(n, links, t, lin("#CDB98E"), lin("#9E8A64"))
    links.new(col, p.inputs["Base Color"])
    links.new(col, p.inputs["Emission Color"])          # the Sun hits the ring at a grazing angle: a bit of self-glow to read
    p.inputs["Emission Strength"].default_value = 0.3
    mat.use_backface_culling = False
    return mat, alpha


# ---------- instrument layer (camera child, in pixels) ----------

def overlay_mat(name, color, strength=1.0):
    """Emission (<= 1, below the bloom threshold) with alpha (fac) to fade in and out."""
    return mm.fade_emitter(name, color, strength)


def instr_pivot(cam, name, px, py, d, f_px):
    """Empty child of the camera at the screen point (px, py), at d meters, with scale of 1 unit = 1 pixel."""
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.parent = cam
    s = d / f_px
    e.location = ((px - 540) * s, -(py - 960) * s, -d)
    e.scale = (s, s, s)
    e.rotation_mode = "XYZ"
    return e


def rect_geo(x0, x1, y0, y1, z=0.0):
    return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)]


def masked_arc(name, radius, width, a_max_deg=75.0, seg=120):
    """Arc in pixels: ring of 'width' px from 0° (vertical up) to a_max clockwise, and a material that only
    shows up to the angle 'theta' (animated Value). Returns (object, theta socket in degrees, fac socket)."""
    verts, faces = [], []
    for i in range(seg + 1):
        a = math.radians(a_max_deg * i / seg)
        for rr in (radius - width / 2, radius + width / 2):
            verts.append((rr * math.sin(a), rr * math.cos(a), 0.0))
    for i in range(seg):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    mat, n, links, out = mm.node_mat(name + "Mat")
    tc = n.new("ShaderNodeTexCoord")
    sxyz = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sxyz.inputs[0])
    ang = _math(n, links, "DEGREES", _math(n, links, "ARCTAN2", sxyz.outputs["X"], sxyz.outputs["Y"]))
    theta = n.new("ShaderNodeValue")
    show = _math(n, links, "LESS_THAN", ang, theta.outputs[0])
    fac = n.new("ShaderNodeValue")
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(kit.LUZ)
    em.inputs["Strength"].default_value = 1.0
    mix = n.new("ShaderNodeMixShader")
    links.new(_math(n, links, "MULTIPLY", show, fac.outputs[0]), mix.inputs["Fac"])
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    o = kit.mesh_object(name, verts, faces, [mat])
    o.visible_shadow = False
    return o, theta.outputs[0], fac.outputs[0]


def dashed_line_obj(name, length, width, color, dash=10.0, gap=7.0):
    """Dashed line in pixels along +x (0 to length), with reveal (0..1 of the length), dash offset
    (px, animated) and fac. Returns (obj, reveal, offset, fac)."""
    v, f = rect_geo(0.0, length, -width / 2, width / 2)
    mat, n, links, out = mm.node_mat(name + "Mat")
    tc = n.new("ShaderNodeTexCoord")
    sxyz = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sxyz.inputs[0])
    off = n.new("ShaderNodeValue")
    reveal = n.new("ShaderNodeValue")
    fac = n.new("ShaderNodeValue")
    x = _math(n, links, "ADD", sxyz.outputs["X"], off.outputs[0])
    ph = _math(n, links, "FRACT", _math(n, links, "DIVIDE", x, dash + gap))
    on = _math(n, links, "LESS_THAN", ph, dash / (dash + gap))
    rv = _math(n, links, "LESS_THAN", sxyz.outputs["X"], _math(n, links, "MULTIPLY", reveal.outputs[0], length))
    k = _math(n, links, "MULTIPLY", _math(n, links, "MULTIPLY", on, rv), fac.outputs[0])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    em.inputs["Strength"].default_value = 1.0
    mix = n.new("ShaderNodeMixShader")
    links.new(k, mix.inputs["Fac"])
    links.new(n.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    o = kit.mesh_object(name, v, f, [mat])
    o.visible_shadow = False
    return o, reveal.outputs[0], off.outputs[0], fac.outputs[0]


FONT_PATH = None


def label_font():
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "fonts" / "BarlowSemiCondensed-SemiBold.ttf"
    return bpy.data.fonts.load(str(p), check_existing=True)


def text_obj(name, body, size_px, mat, font):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = font
    cu.size = size_px
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.materials.append(mat)
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    o.visible_shadow = False
    return o
