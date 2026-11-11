"""Oak of scenes 08 and 09 of viruses-disappeared (final model, stage 8; replaces the oak_marker of stage 6).

Same place and size as the approved marker (trunk at viruses_set.OAK, 0.7 m; crown ~9 m at 6-12 m height,
burlap band at 1.15-1.55 m), now with: furrowed-bark trunk and roots, limbs, crown in faceted masses
(2 tones + sparse outbreak patches), 2 low branches with lobed leaves (lib/oak.py) and spongy moth caterpillars
walking (lib/caterpillar.py):
- 08 (trunk at ~3.2 m): ~30 on the bark and the burlap; 10 COME OUT from under the burlap flap over scenes 08-09
  (the in-view count only grows, nobody is born in frame); line on the low branch going to the leaves.
- 09 (branch at 0.45-0.9 m): caterpillars on the branch and the leaves; the HERO LEAF is eaten in 4 bites starting at
  *boom* (boolean with 4 cutters that enter in 2 frames, steps of 6; clean edge without mesh fold, hence
  boolean and not shape key); the edge caterpillar arrives walking earlier and lunges at each bite.
Composition of 09 in pixels of the camera of 09 (approved position and heading): everything above y 858 or to the right of x 543
(outside the panel) and above the caption.
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import kit
import anim_curves as ac
import caterpillar as cp
import oak as ok
import plants_models as pm

TRUNK_H, TRUNK_R0, TRUNK_R1 = 5.6, 0.36, 0.24
BAND_Z0, BAND_Z1, BAND_R = 1.15, 1.55, 0.385
TRUNK_CAT_SCALE = 1.25        # those on the trunk (08, at 3.2 m) are the biggest of the outbreak (~65 mm): they read as hairy blotches


def cam_space(pos, heading, pitch):
    """Function (px, py, depth) -> world point for the camera (1080x1920, 24 mm, sensor 36 at the height)."""
    h, p = math.radians(heading), math.radians(pitch)
    f = Vector((math.sin(h) * math.cos(p), math.cos(h) * math.cos(p), math.sin(p)))
    r = Vector((math.cos(h), -math.sin(h), 0.0))
    u = r.cross(f)
    c = Vector(pos)

    def P(px, py, d):
        return c + f * d + r * ((px - 540) / 1280 * d) + u * ((960 - py) / 1280 * d)
    P.f, P.r, P.u, P.c = f, r, u, c
    return P


# ---------- tree ----------

def _blocks(c, r, rays):
    """Does the mass (center c, radius r) cut any sun ray (point, direction)?"""
    for p, s in rays:
        t = (c - p).dot(s)
        if t > 0 and (p + s * t - c).length < r * 1.3:
            return True
    return False


def _crown(base, rnd, mats, rays=()):
    """Crown in ~17 faceted masses (lumpy ico) at the ends of the limbs, 3 materials (full, light, sparse).
    rays: sun rays that must get through (light clearing on the low branch of 09)."""
    x, y = base.x, base.y
    geos, fmats = [], []
    centers = []
    while len(centers) < 17:
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.0, 1.0) ** 0.6
        c = Vector((x + 0.1 + math.cos(a) * 4.0 * rr, y + 0.3 + math.sin(a) * 3.4 * rr,
                    8.8 + rnd.uniform(-1.6, 2.2) - 0.8 * rr))
        r = rnd.uniform(1.3, 2.2)
        if _blocks(c, r, rays):
            continue
        centers.append((c, r))
    for k, (c, r) in enumerate(centers):
        g = pm.lumpy_ico(r, tuple(c), (1.0, 1.0, 0.78), rnd, 0.22)
        geos.append(g)
        fmats.append(2 if k % 6 == 5 else 1 if k % 3 == 1 else 0)
    v, f, own = kit.merge(*geos)
    o = kit.mesh_object("OakCrown", v, f, mats, face_mats=[fmats[i] for i in own])
    return o, centers


def build_tree(rnd, mats, base, rays=()):
    bark = mats["bark"]
    trunk = kit.mesh_object("OakTrunk", *ok.trunk_geo(tuple(base), TRUNK_H, TRUNK_R0, TRUNK_R1, rnd,
                                                     lean=(0.15, 0.25)), [bark])
    crown, centers = _crown(base, rnd, [mats["crown"], mats["crown2"], mats["crown_thin"]], rays)
    # limbs: from the top of the trunk to the largest masses
    top = base + Vector((0.15, 0.25, TRUNK_H - 0.3))
    limbs = []
    big = sorted(centers, key=lambda cr: -cr[1])[:6]
    for c, r in big:
        mid = top.lerp(c, 0.5) + Vector((0, 0, 0.5))
        g, _, _ = ok.limb_geo([tuple(top), tuple(mid), tuple(c)], [0.17, 0.11, 0.05], rnd, n=7)
        limbs.append(g)
    v, f, _ = kit.merge(*limbs)
    lim = kit.mesh_object("OakLimbs", v, f, [bark])
    return trunk, crown, lim


BAND_PROFILE = ((BAND_Z0, BAND_R - 0.012), (BAND_Z0 + 0.15, BAND_R - 0.004), (BAND_Z0 + 0.2, BAND_R - 0.01),
                (BAND_Z0 + 0.22, BAND_R + 0.006), (BAND_Z1 - 0.03, BAND_R), (BAND_Z1, BAND_R - 0.02))


def band_radius(z):
    """Outer radius of the burlap at height z (+ 4 mm clearance for the ring noise)."""
    pr = BAND_PROFILE
    for (za, ra), (zb, rb) in zip(pr, pr[1:]):
        if za <= z <= zb:
            return ra + (rb - ra) * (z - za) / (zb - za) + 0.004
    return pr[-1][1] + 0.004


def band(mats, base):
    """Burlap band (flap folded over the twine): thick bark of 2 rings, no hole for the trunk."""
    rnd = random.Random(4)
    rings = []
    n = 20
    for z, rr in BAND_PROFILE:
        rings.append([(base.x + (rr + rnd.uniform(-0.004, 0.004)) * math.cos(2 * math.pi * i / n),
                       base.y + (rr + rnd.uniform(-0.004, 0.004)) * math.sin(2 * math.pi * i / n),
                       z + rnd.uniform(-0.006, 0.006)) for i in range(n)])
    v, f = kit.loft_geo(rings)
    o = kit.mesh_object("OakJute", v, f, [mats["jute"]])
    # barbante
    v2, f2 = kit._prism_geo(20, BAND_R + 0.002, BAND_R + 0.002, 0.012, oz=BAND_Z0 + 0.19, ox=base.x, oy=base.y)
    s = kit.mesh_object("OakTwine", v2, f2, [mats["twine"]])
    return [o, s]


def rosette(p, d, rnd, toward, n=5, size=(0.10, 0.15), cols=1, droop=0.45, spread=55.0):
    """Bundle of leaves at the tip of a twig: n leaves fanned around direction d, hanging, with the face
    turned up and toward 'toward' (the viewer)."""
    d = Vector(d).normalized()
    geos = []
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    for i in range(n):
        a = math.radians(-spread + 2 * spread * (i + rnd.uniform(-0.3, 0.3)) / max(n - 1, 1))
        dir_ = (d * math.cos(a) + side * math.sin(a) + Vector((0, 0, -droop * rnd.uniform(0.6, 1.4)))).normalized()
        nrm = (Vector((0, 0, 1)) + (Vector(toward) - p).normalized() * 0.9).normalized()
        L = rnd.uniform(*size)
        g = ok.leaf_geo(L, L * 0.62, rnd, rows=18 if cols == 1 else 26, cols=cols, fold=0.18, curl=0.12)
        m = ok.leaf_matrix(p + dir_ * 0.012, dir_, nrm, roll=rnd.uniform(-0.4, 0.4))
        geos.append(ok.xform(g, m))
        # petiole
        geos.append(kit.tube_geo([tuple(p), tuple(p + dir_ * 0.014)], [0.0016, 0.0013], n=4))
    return geos


def twig(a, b, r0, r1):
    v, f = kit.tube_geo([tuple(a), tuple(b)], [r0, r1], n=5)
    return v, f, "twig"


def _spray(name, geos, mats):
    """Joins leaves (leaf material) and twigs (bark) into a single mesh."""
    parts = [(g[0], g[1]) for g in geos]
    v, f, own = kit.merge(*parts)
    kinds = [1 if len(g) > 2 else 0 for g in geos]
    return kit.mesh_object(name, v, f, [mats["leaf"], mats["bark"]], face_mats=[kinds[i] for i in own])


def _poly_at(pts, rad, s):
    """Point, tangent and radius at s meters along the polyline."""
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        L = (b - a).length
        if acc + L >= s or i == len(pts) - 2:
            t = max(0.0, min(1.0, (s - acc) / L))
            return a.lerp(b, t), (b - a).normalized(), rad[i] + (rad[i + 1] - rad[i]) * t
        acc += L
    return Vector(pts[-1]), Vector((1, 0, 0)), rad[-1]


def _poly_len(pts):
    return sum((Vector(pts[i + 1]) - Vector(pts[i])).length for i in range(len(pts) - 1))


# ---------- lagartas ----------

def trunk_frame(base, z, theta, alpha, out=0.004):
    """Caterpillar on the bark: height z, angle theta around the trunk, heading alpha (0 = up, + = turns)."""
    r = ok.radius_at(z, TRUNK_H, TRUNK_R0, TRUNK_R1)
    t = z / TRUNK_H
    c = Vector((base.x + 0.15 * t * t, base.y + 0.25 * t * t, base.z + z))
    nrm = Vector((math.cos(theta), math.sin(theta), 0.0))
    circ = Vector((-math.sin(theta), math.cos(theta), 0.0))
    fwd = Vector((0, 0, 1)) * math.cos(alpha) + circ * math.sin(alpha)
    return c + nrm * (r + out), fwd, nrm


class Crawler:
    """Caterpillar that walks on the bark (helix) from (z0, theta0) at frame f0."""

    def __init__(self, base, z0, th0, alpha, f0, radius_fn=None, out=0.004):
        self.base, self.z0, self.th0, self.alpha, self.f0, self.out = base, z0, th0, alpha, f0, out
        self.radius_fn = radius_fn

    def matrix(self, f):
        s = cp.SPEED * (f - self.f0) / 30.0
        z = self.z0 + s * math.cos(self.alpha)
        r = self.radius_fn(z) if self.radius_fn else ok.radius_at(z, TRUNK_H, TRUNK_R0, TRUNK_R1)
        th = self.th0 + s * math.sin(self.alpha) / r
        pos, fwd, nrm = (trunk_frame(self.base, z, th, self.alpha, self.out) if self.radius_fn is None else
                         self._band_frame(z, th, r))
        return cp.frame_matrix(pos, fwd, nrm)

    def _band_frame(self, z, th, r):
        nrm = Vector((math.cos(th), math.sin(th), 0.0))
        circ = Vector((-math.sin(th), math.cos(th), 0.0))
        fwd = Vector((0, 0, 1)) * math.cos(self.alpha) + circ * math.sin(self.alpha)
        return Vector((self.base.x, self.base.y, self.base.z + z)) + nrm * (r + self.out), fwd, nrm


def trunk_caterpillars(base, meshes, rnd, f0, f1, cam_xy):
    """~30 on the bark and the burlap on the camera side of 08 + 10 that come out from under the burlap flap (going up)."""
    face = math.atan2(cam_xy[1] - base.y, cam_xy[0] - base.x)
    out = []
    frames = list(range(f0, f1 + 1, 2))
    specs = []
    # on the burlap: walk ~14 cm without leaving the band (up, down or around)
    travel = cp.SPEED * (f1 - f0) / 30.0
    for k in range(22):
        al = math.radians(rnd.choice((rnd.uniform(-75, 75), 180 + rnd.uniform(-50, 50))))
        dz = travel * math.cos(al)
        lo = BAND_Z0 + 0.03 + max(0.0, -dz) + (cp.LENGTH * max(0.0, -math.cos(al)))
        hi = BAND_Z1 - 0.03 - max(0.0, dz) - cp.LENGTH * max(0.0, math.cos(al))
        specs.append(("band", rnd.uniform(lo, max(lo, hi)), face + rnd.uniform(-1.0, 1.0), al))
    # bark below the burlap: climb slowly and stop before the band (final z < 1.08)
    for k in range(7):
        specs.append(("bark", rnd.uniform(0.72, 0.88), face + rnd.uniform(-1.25, 1.25), math.radians(rnd.uniform(-25, 25))))
    # bark above the burlap
    for k in range(13):
        specs.append(("bark", rnd.uniform(1.62, 3.1), face + rnd.uniform(-1.3, 1.3), math.radians(rnd.uniform(-30, 30))))
    # coming out from under the flap: start hidden (head at z < 1.55 - 0.01) and cross the edge at different times
    total_s = cp.SPEED * (f1 - f0) / 30.0
    for k in range(10):
        cross = f0 + int((f1 - f0) * (0.05 + 0.85 * k / 9))          # frame when the head passes the edge
        z_head0 = BAND_Z1 + 0.003 - cp.SPEED * (cross - f0) / 30.0
        specs.append(("under", z_head0 - cp.LENGTH, face + rnd.uniform(-0.9, 0.9), math.radians(rnd.uniform(-12, 12))))
    bandr = band_radius
    for k, (kind, z0, th, al) in enumerate(specs):
        if kind == "under":
            cr = Crawler(base, z0, th, al, f0, out=0.004)        # between the trunk and the burlap (radius < BAND_R)
        elif kind == "band":
            cr = Crawler(base, z0, th, al, f0, radius_fn=bandr, out=0.0)
        else:
            cr = Crawler(base, z0, th, al, f0, out=0.009)
        o = cp.instance(f"Cat{k}", meshes[k % len(meshes)])
        o.scale = (TRUNK_CAT_SCALE,) * 3
        cp.key_path(o, frames, cr.matrix)
        out.append(o)
    return out


def branch_caterpillars(pts, rad, meshes, rnd, f0, f1, toward, n=9, s_range=(0.25, 0.95), prefix="BCat"):
    """Line on the low branch walking to the tip (to the leaves), on top and on the viewer's side."""
    L = _poly_len(pts)
    out = []
    frames = list(range(f0, f1 + 1, 2))
    for k in range(n):
        s0 = L * (s_range[0] + (s_range[1] - s_range[0]) * k / max(n - 1, 1)) + rnd.uniform(-0.02, 0.02)
        beta = math.radians(rnd.uniform(-35, 55))

        def fn(f, s0=s0, beta=beta):
            s = min(s0 + cp.SPEED * (f - f0) / 30.0, L - cp.LENGTH - 0.01)
            p, t, r = _poly_at(pts, rad, s)
            a_, _, _ = _poly_at(pts, rad, max(0.0, s - 0.04))      # average tangent (no jump at the breaks)
            b_, _, _ = _poly_at(pts, rad, min(L, s + cp.LENGTH + 0.04))
            t = (b_ - a_).normalized()
            up = Vector((0, 0, 1))
            n0 = (up - t * up.dot(t)).normalized()
            side = (Vector(toward) - p)
            side = (side - t * side.dot(t)).normalized()
            nrm = (n0 * math.cos(beta) + side * math.sin(beta)).normalized()
            return cp.frame_matrix(p + nrm * (r * 0.92), t, nrm)
        o = cp.instance(f"{prefix}{k}", meshes[k % len(meshes)])
        cp.key_path(o, frames, fn)
        out.append(o)
    return out


# ---------- eaten leaf (09) ----------

def leaf_object(name, length, width, matrix, mat, rnd, rows=34, cols=7, fold=0.12, curl=0.10):
    v, f = ok.leaf_geo(length, width, rnd, rows=rows, cols=cols, fold=fold, curl=curl)
    o = kit.mesh_object(name, v, f, [mat])
    o.matrix_world = matrix
    weld = o.modifiers.new("Weld", "WELD")              # base and tip of the grid have repeated vertices: without the
    weld.merge_threshold = 0.0002                       # weld the EXACT boolean returns the empty leaf
    sol = o.modifiers.new("Thick", "SOLIDIFY")
    sol.thickness, sol.offset = 0.0007, 0.0
    return o


def cutter(name, leaf, center_local, radius, h=0.04):
    v, f = kit._prism_geo(18, radius, radius, h, oz=-h / 2)
    o = kit.mesh_object(name, v, f, [])
    o.parent = leaf
    o.location = center_local
    o.hide_render = True
    o.display_type = "WIRE"
    mod = leaf.modifiers.new(name, "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", o
    return o


def leaf_surface_z(x, y, length, fold, curl):
    return fold * abs(y) - curl * length * (x / length - 0.45) ** 2


def hero_leaf(P, mat, rnd, f_boom, f_without, f_end, eater_mesh):
    """Hero leaf of 09 and the edge caterpillar. The caterpillar arrives walking along the leaf (tail from x 0.03 to 0.06) and
    stops with its head at the right margin; from *boom* the leaf tip vanishes in 4 bites (every 6
    frames): each cutter is born touching (from inside) the previous cut and grows to the final disc in
    2 frames, always inside it (the eaten area only grows). Returns (leaf, cutters, caterpillar, matrix)."""
    Lf, Wf, fold, curl = 0.165, 0.11, 0.10, 0.08
    base = P(600, 455, 0.50)
    tipp = P(790, 860, 0.44)
    d = (tipp - base).normalized()
    nrm = (-P.f + Vector((0, 0, 0.55))).normalized()
    M = ok.leaf_matrix(base, d, nrm)
    r5 = random.Random(5)
    r5.uniform(-0.08, 0.08)
    ph1 = 0.5 + r5.uniform(-0.08, 0.08)
    leaf = leaf_object("HeroLeaf", Lf, Wf, M, mat, random.Random(5), fold=fold, curl=curl)

    def w(u):
        return ok._leaf_halfwidth(u, 3.5, ph1, 0.55) * Wf * 0.5
    bites = [(Vector((0.128, w(0.776) + 0.004, 0)), 0.020), (Vector((0.140, w(0.85) - 0.012, 0)), 0.020),
             (Vector((0.152, -0.004, 0)), 0.020), (Vector((0.130, -0.016, 0)), 0.019)]
    cuts = []
    for k, (c, rb) in enumerate(bites):
        n_out = Vector((0, 1, 0)) if k < 2 else (bites[k - 1][0] - c).normalized()
        co = cutter(f"HeroBite{k}", leaf, c, rb)
        fb = f_boom + 6 * k
        far = c + Vector((0, 0, 0.3))
        frames = [1, fb, fb + 1, fb + 2]
        locs = [far, far, c + n_out * rb * 0.45, c]
        scl = [0.55, 0.55, 0.55, 1.0]
        for i in range(3):
            ac.write(co, "location", i, frames, [v[i] for v in locs])
        for i in range(2):
            ac.write(co, "scale", i, frames, scl)
        cuts.append(co)
    y_body = 0.016
    arrive = f_boom - 4
    n_per = max(1, (arrive - f_without - 2) // cp.PERIOD)
    start = arrive - n_per * cp.PERIOD
    x_end = 0.06
    x_start = x_end - n_per * cp.STEP

    def local(x, y):
        return Vector((x, y, leaf_surface_z(x, y, Lf, fold, curl) + 0.0005))

    def yaw_at(f):
        """Head turning toward the current bite (limit 25 deg), in 2 frames."""
        tail = Vector((x_end, y_body, 0))
        yaws = [0.0]
        for c, _ in bites:
            v = c - tail
            yaws.append(max(-25.0, min(25.0, math.degrees(math.atan2(v.y, v.x)))) * 0.8)
        yaw = 0.0
        for k in range(4):
            fb = f_boom + 6 * k - 2
            if f >= fb:
                u = min(1.0, (f - fb) / 2)
                yaw = yaws[k] + (yaws[k + 1] - yaws[k]) * u
        return yaw

    def fn(f):
        x = x_start + cp.SPEED * (min(max(f, start), arrive) - start) / 30.0
        yaw, lunge = yaw_at(f), 0.0
        for k in range(4):
            fb = f_boom + 6 * k
            if fb <= f < fb + 6:
                lunge = [0.4, 1.0, 0.8, 0.5, 0.25, 0.05][f - fb]
        tail = local(x, y_body)
        a = math.radians(yaw)
        head = local(x + math.cos(a) * cp.LENGTH, y_body + math.sin(a) * cp.LENGTH)
        fwd_l = (head - tail).normalized()
        tail = tail + fwd_l * (0.003 * lunge)
        R3 = M.to_3x3()
        m = cp.frame_matrix(M @ tail, R3 @ fwd_l, R3 @ Vector((0, 0, 1)))
        if lunge:
            m = m @ Matrix.Rotation(math.radians(-7 * lunge), 4, "Y")
        return m
    eater = cp.instance("EaterCat", eater_mesh)
    frames = list(range(f_without - 4, f_end + 2))
    cp.key_path(eater, frames, fn)
    # walk only while walking: shape keys of the edge caterpillar's own mesh
    vals = {k: [] for k in range(cp.N_KEYS)}
    for f in frames:
        ph = ((min(max(f, start), arrive) - start) / cp.PERIOD) % 1.0
        x = ph * cp.N_KEYS
        i, fr = int(x) % cp.N_KEYS, x - int(x)
        for k in range(cp.N_KEYS):
            vals[k].append((1 - fr) if k == i else fr if k == (i + 1) % cp.N_KEYS else 0.0)
    for k in range(cp.N_KEYS):
        ac.write(eater_mesh.shape_keys, f'key_blocks["W{k}"].value', 0, frames, vals[k])
    return leaf, cuts, eater, M


def ragged(leaf, rnd, n=3, rb=(0.012, 0.02), Lf=0.14, Wf=0.09):
    """Already eaten leaf (1 DAY state): 2-3 fixed cuts on the margin."""
    cuts = []
    for k in range(n):
        u = rnd.uniform(0.3, 0.85)
        s = rnd.choice((-1, 1))
        w = ok._leaf_halfwidth(u, 3.5, 0.5, 0.55) * Wf * 0.5
        c = Vector((u * Lf, s * (w + rnd.uniform(-0.01, 0.006)), 0))
        cuts.append(cutter(f"{leaf.name}Cut{k}", leaf, c, rnd.uniform(*rb)))
    return cuts


# ---------- montagem ----------

def build(cam9, cam8_xy, frames, base, sun=None):
    """cam9 = (position, heading, tilt) of the camera of 09 on the 1st frame; frames = SimpleNamespace(f08, without,
    boom, end09); base = foot of the trunk (viruses_set.OAK)."""
    rnd = random.Random(61)
    base = Vector(base)
    mats = {"bark": ok.bark_mat(), "crown": pm.fixed_mat("OakCrownMat", "#4F7A3C", rough=0.9, var=(0.9, 1.08)),
            "crown2": pm.fixed_mat("OakCrownMat2", "#5E8A46", rough=0.9, var=(0.9, 1.08)),
            "crown_thin": pm.fixed_mat("OakCrownThin", "#8A9A5A", rough=0.9),
            "jute": pm.fixed_mat("Jute", "#B89A6A", rough=0.98), "twine": pm.fixed_mat("Twine", "#6A5A44"),
            "soil": pm.fixed_mat("TreePit", "#4A3C30", rough=0.98), "leaf": ok.leaf_mat()}
    pit = kit.box_span("OakPit", base.x - 0.8, base.x + 0.8, base.y - 0.8, base.y + 0.8, 0.0, 0.03, mats["soil"])
    P = cam_space(*cam9)
    rays = [(P(px, py, d), Vector(sun).normalized()) for px, py, d in
            ((680, 650, 0.47), (430, 470, 0.72), (760, 560, 0.62), (150, 340, 0.9), (900, 640, 0.66))] if sun else []
    trunk, crown, limbs = build_tree(rnd, mats, base, rays)
    jute = band(mats, base)
    cam_pos = P.c
    # low branch of 09: leaves the trunk at 2.95 m toward the camera of 09 and descends to the front of it
    to_cam = (cam_pos - base)
    to_cam.z = 0
    to_cam.normalize()
    j = Vector((base.x, base.y, 2.95)) + to_cam * (ok.radius_at(2.95, TRUNK_H, TRUNK_R0, TRUNK_R1) - 0.05)
    pts9 = [tuple(j), tuple(P(-260, 120, 1.25)), tuple(P(120, 330, 0.95)), tuple(P(430, 470, 0.72)),
            tuple(P(760, 560, 0.62)), tuple(P(905, 630, 0.64))]
    rad9 = [0.085, 0.05, 0.03, 0.018, 0.010, 0.004]
    g9, bpts, brad = ok.limb_geo(pts9, rad9, random.Random(9), n=8, kink=0.06)
    # 2nd low branch (08: leaves at the upper left of the trunk)
    side = Vector((-to_cam.y, to_cam.x, 0))
    j2 = Vector((base.x, base.y, 3.35)) - side * 0.2
    pts2 = [tuple(j2), tuple(j2 - side * 1.0 + to_cam * 0.6 + Vector((0, 0, 0.1))),
            tuple(j2 - side * 1.9 + to_cam * 1.1 - Vector((0, 0, 0.3))),
            tuple(j2 - side * 2.6 + to_cam * 1.4 - Vector((0, 0, 0.75)))]
    g2, bpts2, brad2 = ok.limb_geo(pts2, [0.09, 0.05, 0.03, 0.014], random.Random(10), n=7, kink=0.1)
    v, f, _ = kit.merge(g9, g2)
    branch = kit.mesh_object("OakBranch", v, f, [mats["bark"]])
    # leaves: bundles on branch 2 (cheap) and on the branch of 09 (fine grid near the camera)
    geos = []
    L2 = _poly_len(bpts2)
    for k in range(14):
        p, t, r = _poly_at(bpts2, brad2, L2 * (0.35 + 0.65 * k / 13))
        q = p + Vector((rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), rnd.uniform(-0.05, 0.12)))
        geos.append(twig(p, q, 0.006, 0.003))
        geos += rosette(q, t + Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 0)), rnd,
                        Vector(cam8_xy) .to_3d() + Vector((0, 0, 1.65)), n=6, size=(0.11, 0.16))
    spray2 = _spray("OakSpray08", geos, mats)
    # branch of 09: twigs with bundles (some already eaten), in pixels of the camera of 09
    geos = []
    leaves9 = []
    for (px, py, dd), (qx, qy, qd), nleaf in (((300, 400, 0.85), (330, 230, 0.8), 5),
                                              ((520, 495, 0.70), (660, 300, 0.75), 4),
                                              ((760, 560, 0.62), (900, 640, 0.66), 5),
                                              ((640, 525, 0.66), (560, 640, 0.6), 3),
                                              ((150, 340, 0.9), (60, 520, 0.95), 4)):
        a, b = P(px, py, dd), P(qx, qy, qd)
        geos.append(twig(a, b, 0.006, 0.0035))
        geos += rosette(b, b - a, rnd, cam_pos, n=nleaf, size=(0.11, 0.15), cols=4, droop=0.5)
    spray9 = _spray("OakSpray09", geos, mats)
    # loose eaten leaves (fixed cuts) near the camera
    for k, ((bx, by, bd), (tx, ty, td)) in enumerate((((880, 600, 0.6), (980, 900, 0.62)),
                                                     ((470, 470, 0.68), (380, 700, 0.66)),
                                                     ((240, 360, 0.82), (180, 640, 0.86)))):
        a, b = P(bx, by, bd), P(tx, ty, td)
        Lk = 0.14
        nrm = (-P.f + Vector((0, 0, 0.5))).normalized()
        o = leaf_object(f"RaggedLeaf{k}", Lk, Lk * 0.64, ok.leaf_matrix(a, b - a, nrm), mats["leaf"],
                        random.Random(20 + k), rows=26, cols=4)
        ragged(o, random.Random(30 + k), n=2 + k % 2, Lf=Lk, Wf=Lk * 0.64)
        leaves9.append(o)
    # lagartas
    cmats = cp.materials()
    meshes = cp.phase_meshes("CatMesh", cmats, groups=4)
    eater_mesh = cp.make_mesh("CatEater", cmats)
    f0, f1 = frames.f08 - 2, frames.end09 + 2
    cp.crawl_keys(meshes, f0, f1)
    cats = trunk_caterpillars(base, meshes, random.Random(62), f0, f1, cam8_xy)
    bcats = branch_caterpillars(bpts, brad, meshes, random.Random(63), f0, f1, cam_pos, n=11, s_range=(0.2, 0.93))
    bcats += branch_caterpillars(bpts2, brad2, meshes, random.Random(64), f0, f1, Vector(cam8_xy).to_3d(), n=5,
                                 s_range=(0.1, 0.6), prefix="B2Cat")
    hero, cuts, eater, M = hero_leaf(P, mats["leaf"], rnd, frames.boom, frames.without, f1, eater_mesh)
    # two caterpillars standing eating on the eaten leaves (short walk)
    lcats = []
    for k, o in enumerate(leaves9[:2]):
        mw = o.matrix_world.copy()
        R3 = mw.to_3x3()

        def fn(f, mw=mw, R3=R3, k=k):
            x = 0.03 + cp.SPEED * (f - f0) / 30.0 * 0.5
            p = mw @ Vector((x, -0.008 + 0.01 * k, 0.004))
            return cp.frame_matrix(p, R3 @ Vector((1, 0.15, 0)), R3 @ Vector((0, 0, 1)))
        c = cp.instance(f"LeafCat{k}", meshes[(k + 1) % 4])
        cp.key_path(c, list(range(f0, f1 + 1, 2)), fn)
        lcats.append(c)
    allobj = [pit, trunk, crown, limbs, *jute, branch, spray2, spray9, *leaves9, hero, eater, *cats, *bcats, *lcats]
    for o in allobj:
        if o.type == "MESH":
            for poly in o.data.polygons:
                poly.use_smooth = False
    tip = Vector(pts9[-1])
    return SimpleNamespace(trunk=trunk, band=jute[0], crown=crown, branch=branch, objects=allobj, cats=cats,
                           branch_cats=bcats, hero=hero, cuts=cuts, eater=eater, tip=tip, bite=hero,
                           leaves=[spray2, spray9, *leaves9, hero], pts9=pts9)
