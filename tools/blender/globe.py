"""Low-poly globe for pangaea-never-split: faceted ocean, continents as plates that rotate around the center.

Each continent is its own mesh cut from a dense icosphere by the latitude/longitude outline; the origin
sits at the center of the Earth, so "continental drift" is just rotating the object (rotation_quaternion). Faces change
color by distance from the coast: green at the edge, savanna in the middle, amber desert at the heart (the dry interior of
Pangaea, Kutzbach & Gallimore 1989).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Quaternion, Vector

import kit

R = 10.0
OCEAN = "#1D4E7E"
OCEAN_DEEP = "#1A4673"
COAST = "#4C7A3E"
SCRUB = "#8E8A4A"
DESERT = "#C98B3C"
DUNE = "#BF7E35"
ICE = "#DCE6EE"

# Outlines (lat, lon), simplified by hand from paleogeographic maps (Pangaea, ~200 Ma, Africa at the center)
# and from the current map. Enough to read at a glance on a phone; they are not a plate reconstruction.
PANGAEA = [
    (74, -62), (80, -25), (79, 15), (76, 55), (71, 95), (63, 125), (52, 140), (40, 136), (31, 121), (26, 102),
    (29, 82), (23, 63), (15, 47), (6, 33), (-4, 44), (-9, 66), (-17, 92), (-25, 114), (-34, 130), (-49, 136),
    (-63, 122), (-76, 84), (-83, 25), (-79, -28), (-70, -60), (-55, -76), (-40, -71), (-21, -66), (-5, -62),
    (6, -80), (20, -101), (35, -111), (50, -116), (62, -106), (70, -86),
]
RIFT = [(66, -26), (52, -30), (38, -33), (24, -32), (9, -27), (-6, -27), (-22, -30), (-40, -36), (-56, -46)]

MODERN = {
    "NorthAmerica": [(70, -165), (72, -140), (69, -100), (74, -80), (62, -62), (47, -53), (43, -66), (35, -76),
                     (25, -80), (30, -89), (21, -97), (15, -88), (8, -78), (15, -93), (22, -106), (32, -117),
                     (40, -124), (50, -128), (60, -147), (58, -158), (65, -168)],
    "Greenland": [(83, -35), (78, -18), (70, -22), (60, -43), (70, -55), (78, -70)],
    "SouthAmerica": [(12, -72), (8, -60), (0, -50), (-5, -35), (-23, -41), (-35, -55), (-55, -68), (-50, -75),
                     (-40, -73), (-18, -71), (-5, -81), (5, -77)],
    "Africa": [(35, -6), (37, 10), (31, 32), (12, 43), (11, 51), (-5, 40), (-25, 35), (-34, 20), (-28, 15),
               (-17, 12), (-5, 12), (5, 8), (4, -8), (15, -17), (28, -13)],
    "Eurasia": [(36, -9), (43, -9), (48, -5), (58, 5), (71, 25), (70, 60), (77, 105), (70, 140), (66, 179),
                (60, 165), (52, 157), (40, 140), (35, 129), (22, 120), (10, 107), (1, 104), (8, 98), (22, 90),
                (8, 77), (22, 68), (25, 57), (13, 45), (30, 32), (37, 27), (40, 20), (45, 13), (38, 15), (37, -2)],
    "Australia": [(-11, 132), (-12, 142), (-25, 153), (-38, 147), (-35, 137), (-32, 116), (-22, 114), (-15, 124)],
    "Antarctica": [(-66, -180), (-70, -90), (-65, 0), (-68, 90), (-66, 180), (-90, 180), (-90, -180)],
}
# Pangaea Ultima (Farnsworth et al. 2023): the Atlantic closes and the Americas meet Africa and Europe;
# Australia rises to Asia; Antarctica rises to the south of the Indian Ocean. (centroid from, centroid to).
ULTIMA_MOVES = {
    "NorthAmerica": ((47, -100), (42, -36)),
    "Greenland": ((72, -40), (66, -4)),
    "SouthAmerica": ((-17, -60), (-8, -14)),
    "Africa": ((5, 20), (2, 22)),
    "Eurasia": ((50, 80), (50, 82)),
    "Australia": ((-25, 135), (4, 112)),
    "Antarctica": ((-80, 0), (-48, 55)),
}


def to_vec(lat, lon, r=1.0):
    la, lo = math.radians(lat), math.radians(lon)
    return Vector((r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la)))


def to_latlon(v):
    v = v.normalized()
    return math.degrees(math.asin(max(-1.0, min(1.0, v.z)))), math.degrees(math.atan2(v.y, v.x))


def ico_sphere(levels):
    """Unit icosphere subdivided 'levels' times (vertices, faces)."""
    t = (1 + 5 ** 0.5) / 2
    base = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
            (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
             (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    verts = [Vector(v).normalized() for v in base]
    for _ in range(levels):
        cache, out = {}, []

        def mid(a, b):
            k = (a, b) if a < b else (b, a)
            if k not in cache:
                verts.append((verts[a] + verts[b]).normalized())
                cache[k] = len(verts) - 1
            return cache[k]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = out
    return verts, faces


def _inside(lat, lon, poly):
    """Point in polygon in latitude/longitude (ray crossing)."""
    hit, n = False, len(poly)
    for i in range(n):
        (a_lat, a_lon), (b_lat, b_lon) = poly[i], poly[(i + 1) % n]
        if (a_lon > lon) != (b_lon > lon):
            cross = a_lat + (lon - a_lon) * (b_lat - a_lat) / (b_lon - a_lon)
            if lat < cross:
                hit = not hit
    return hit


def _coast_points(poly, step=3.0):
    """Coast points every ~step degrees, as unit vectors (to measure distance to the sea)."""
    out = []
    for i in range(len(poly)):
        a, b = to_vec(*poly[i]), to_vec(*poly[(i + 1) % len(poly)])
        n = max(1, int(math.degrees(a.angle(b)) / step))
        out += [a.slerp(b, k / n) if hasattr(a, "slerp") else (a.lerp(b, k / n)).normalized() for k in range(n)]
    return out


def _materials(prefix):
    names = (("Coast", COAST), ("Scrub", SCRUB), ("Desert", DESERT), ("Dune", DUNE), ("Ice", ICE))
    return [kit.flat(f"{prefix}{n}", c, rough=0.95) for n, c in names]


def land_mesh(name, poly, levels, rnd, mats, lift=0.14, desert=12.0, ice=False, sphere=None):
    """Mesh of one continent (origin at the center of the Earth). desert = minimum distance from the coast (degrees) to become
    desert (0 = no desert). Faces inside the outline rise slightly
    (faceted relief); edge faces drop to almost sea level, so the coast does not become a step."""
    verts, faces = sphere or ico_sphere(levels)
    land = []
    for f in faces:
        c = (verts[f[0]] + verts[f[1]] + verts[f[2]]).normalized()
        if _inside(*to_latlon(c), poly):
            land.append((f, c))
    coast = _coast_points(poly)
    used, edge_count = {}, {}
    for f, _ in land:
        for k in range(3):
            e = tuple(sorted((f[k], f[(k + 1) % 3])))
            edge_count[e] = edge_count.get(e, 0) + 1
    border = {v for e, n in edge_count.items() if n == 1 for v in e}
    out_v, out_f, face_mats = [], [], []
    for f, c in land:
        idx = []
        for v in f:
            if v not in used:
                p = verts[v]
                h = 0.012 * R if v in border else lift * (0.9 + 0.2 * rnd.random())
                used[v] = len(out_v)
                out_v.append(tuple(p * (R + h)))
            idx.append(used[v])
        out_f.append(tuple(idx))
        dist = min(math.degrees(c.angle(q)) for q in coast)
        lat = abs(to_latlon(c)[0])
        if ice or lat > 72:
            face_mats.append(4)
        elif desert and lat < 38 and dist > desert:            # desert: subtropics, far from the sea
            face_mats.append(3 if rnd.random() < 0.12 else 2)
        elif desert and lat < 50 and dist > desert * 0.6:
            face_mats.append(1)
        else:
            face_mats.append(0)
    return kit.mesh_object(name, out_v, out_f, mats, face_mats=face_mats)


def ocean(name, levels, rnd, center):
    verts, faces = ico_sphere(levels)
    mats = [kit.flat(f"{name}A", OCEAN, rough=0.45), kit.flat(f"{name}B", OCEAN_DEEP, rough=0.45)]
    v = [tuple(p * (R + rnd.uniform(-0.015, 0.015))) for p in verts]
    obj = kit.mesh_object(name, v, faces, mats, location=center, face_mats=[rnd.random() < 0.4 for _ in faces])
    return obj


def rift_line(name, center, parent):
    """Amber line along the seam of the future Atlantic (scene 02): glows, opens a little and vanishes."""
    mat, power = kit.keyed_emission(name, kit.LUZ, kit.LUZ, 0.0)
    pts = []
    for (a, b) in zip(RIFT, RIFT[1:]):
        va, vb = to_vec(*a), to_vec(*b)
        n = 6
        pts += [(va.lerp(vb, k / n)).normalized() * (R + 0.2) for k in range(n)]
    pts.append(to_vec(*RIFT[-1]) * (R + 0.2))
    geo = kit.tube_geo([tuple(p) for p in pts], [0.09] * len(pts), n=5)
    obj = kit.mesh_object(name, geo[0], geo[1], [mat])
    obj.parent = parent
    return SimpleNamespace(obj=obj, power=power)


def space(center, rnd):
    """Space backdrop for the orbital scenes only: navy-blue shell with stars (the ground sky is left out)."""
    shell_v, shell_f = ico_sphere(2)
    mat = kit.flat("SpaceShell", "#000000", emission="#0B0F17", strength=1.0)
    kit.principled(mat).inputs["Specular IOR Level"].default_value = 0.0   # emission only: the sun does not light the shell
    v = [tuple(Vector(center) + p * 900) for p in shell_v]
    shell = kit.mesh_object("SpaceShell", v, [tuple(reversed(f)) for f in shell_f], [mat])
    star = kit.flat("Star", "#FFFFFF", emission="#F4F6F8", strength=6.0)
    pts = []
    for _ in range(700):
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        pts.append(kit._gem_geo(rnd.uniform(0.6, 1.6), ox=center[0] + d.x * 850, oy=center[1] + d.y * 850,
                                oz=center[2] + d.z * 850))
    sv, sf, _ = kit.merge(*pts)
    stars = kit.mesh_object("Stars", sv, sf, [star])
    for o in (shell, stars):
        o.visible_shadow = False                  # the closed shell must not block the globe's sun
    return SimpleNamespace(shell=shell, stars=stars)


def _empty(name, location):
    e = bpy.data.objects.new(name, None)
    e.location = location
    e.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(e)
    return e


def globe(name, center, rnd, pangaea=True, levels=6):
    """A globe: ocean + (Pangaea as a single block) or (today's continents, one object per plate)."""
    root = _empty(name, center)
    sea = ocean(f"{name}Ocean", 4, rnd, center)
    sea.parent, sea.location = root, (0, 0, 0)
    sphere = ico_sphere(levels)
    plates = {}
    if pangaea:
        mats = _materials(f"{name}P")
        obj = land_mesh(f"{name}Pangaea", PANGAEA, levels, rnd, mats, sphere=sphere)
        plates["Pangaea"] = obj
    else:
        mats = _materials(f"{name}M")
        for k, (plate, poly) in enumerate(MODERN.items()):
            obj = land_mesh(f"{name}{plate}", poly, levels, rnd, mats, lift=0.14 + 0.012 * k,
                            desert=6.0 if plate in ("Africa", "Eurasia", "Australia") else 0, ice=plate in ("Antarctica", "Greenland"),
                            sphere=sphere)
            plates[plate] = obj
    for obj in plates.values():
        obj.rotation_mode = "QUATERNION"
        obj.parent, obj.location = root, (0, 0, 0)
    return SimpleNamespace(root=root, sea=sea, plates=plates, mats=mats)


def ultima_rotation(plate):
    """Rotation that takes the plate's present-day centroid to its position in Pangaea Ultima."""
    src, dst = ULTIMA_MOVES[plate]
    a, b = to_vec(*src), to_vec(*dst)
    axis = a.cross(b)
    if axis.length < 1e-6:
        return Quaternion()
    return Quaternion(axis.normalized(), a.angle(b))


def spin(root, frame0, frame1, deg_per_s, fps, axis=(0, 0, 1)):
    """Globe rotating slowly and steadily (rotation around the axis, linear)."""
    a0 = 0.0
    a1 = math.radians(deg_per_s * (frame1 - frame0) / fps)
    kit.key(root, "rotation_quaternion", Quaternion(axis, a0), frame0)
    kit.key(root, "rotation_quaternion", Quaternion(axis, a1), frame1)
    for fc in _fcurves(root):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _fcurves(obj):
    return _fcurves_of(obj.animation_data.action if obj.animation_data else None)


def _fcurves_of(act):
    """F-curves of an action (Blender 5 keeps them in layers/channels; older versions, directly in fcurves)."""
    if act is None:
        return []
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out
