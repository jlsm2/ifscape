"""Lenses of viruses-disappeared (scenes 02, 04, 05 and 07): content and animation, over lib/fx_lens.py.

SOURCE: procedural (direction.md section 3; art.md section 2 "Lens"). Scales (direction.md section 5): phage ~1/8 of the rod; diatom
in 07 is another lens (another scale). Palette: virus #D8D2E8 (light lilac), phage #C9CCD2, rod #C9B98A with
dark nucleus, nutrient #F5A524 emission 1.2, droplet #A8C4D6, bubble #E6F0F4.

Timing: every key arrives ready in frames (computed by kit.W in the video script). Dense LINEAR keys.
Open/close = scale of the lens root (0 -> 1 in 8 frames, smooth exit); the lens only shows in its own window.
"""

import math
import random
from types import SimpleNamespace

import bpy

import anim_curves as ac
import fx_lens
import kit
from kit import lin

VIRUS, PHAGE, ROD, ROD_CORE, NUTRIENT, DROP = "#D8D2E8", "#C9CCD2", "#C9B98A", "#8E7E58", "#F5A524", "#A8C4D6"
OPEN = 8                       # frames to open or close
TINY = 0.001


def _ease_out(u):
    return ac.ease(u, "out")


def _mesh(lens, name, geo, mat, x, y, depth, rot=0.0):
    o = kit.mesh_object(f"{lens.name}{name}", geo[0], geo[1], [mat] if not isinstance(mat, list) else mat,
                        fx_lens._lens_xy(lens, x, y, depth))
    o.parent = lens.root
    o.rotation_euler = (0, 0, math.radians(rot))
    o.visible_shadow = False
    for p in o.data.polygons:
        p.use_smooth = False
    return o


def objs(lens):
    return [lens.root, *lens.root.children_recursive]


def open_close(lens, f_open, f_close, total, f_show=None):
    """Lens root: opens at f_open (0 -> 1 in OPEN frames) and closes at f_close (1 -> 0). f_close None = stays
    open until the end of the window. f_show: frame at which the lens already shows open (no opening animation)."""
    frames, vals = [], []
    if f_show is not None:
        frames, vals = [f_show], [1.0]
        start = f_show
    else:
        start = f_open
        for k in range(OPEN + 1):
            frames.append(f_open + k)
            vals.append(max(TINY, _ease_out(k / OPEN)))
    end = f_close + OPEN if f_close is not None else total
    if f_close is not None:
        for k in range(OPEN + 1):
            frames.append(f_close + k)
            vals.append(max(TINY, 1.0 - ac.ease(k / OPEN, "in")))
    for i in range(3):
        ac.write(lens.root, "scale", i, frames, vals)
    ac.visible_ranges(objs(lens), [(start, end)], total)
    return start, end


def _scale_keys(o, frames, vals):
    for i in range(3):
        ac.write(o, "scale", i, frames, [max(TINY, v) for v in vals])


# ---------- 02: droplets with viruses ----------

def lens_02(cam, f_every, f_vanish, f_stay, total):
    """Droplets (3) with icosahedral viruses (2 or 3 per droplet). On *vanishes* the viruses shrink to 0 in 8 frames and the
    droplets stay."""
    L = fx_lens.build("Lens02", cam, (610, 650), 560)
    drop_mat = fx_lens.lit_mat("Lens02DropMat", DROP, top=1.15, bottom=0.7, rim=0.45)[0]
    vir_mat = fx_lens.lit_mat("Lens02VirusMat", VIRUS, top=1.25, bottom=0.65)[0]
    drops = [(-95, 70, 92), (110, 105, 70), (20, -120, 78)]
    viruses = []
    rnd = random.Random(2)
    for k, (x, y, r) in enumerate(drops):
        _mesh(L, f"Drop{k}", kit._ico_geo(L.px(r), (0, 0, 0), (1.0, 1.0, 0.55)), drop_mat, x, y, 10)
        for j in range(3 if k == 0 else 2):
            a = rnd.uniform(0, 2 * math.pi)
            rr = r * rnd.uniform(0.25, 0.6)
            viruses.append(_mesh(L, f"Virus{k}{j}", kit._ico_geo(L.px(rnd.uniform(13, 16)), (0, 0, 0)), vir_mat,
                                 x + rr * math.cos(a), y + rr * math.sin(a), 70, rot=rnd.uniform(0, 60)))
    for v in viruses:
        fr = [f_vanish - 1] + [f_vanish + k for k in range(OPEN + 1)]
        _scale_keys(v, fr, [1.0] + [1.0 - ac.ease(k / OPEN, "in") for k in range(OPEN + 1)])
    open_close(L, f_every, f_stay, total)
    return L


# ---------- 04 e 05: bastonetes, fagos e o estouro ----------

RODS = [(-150, 120, 20), (-10, 150, -35), (140, 110, 60), (-170, -5, 80), (0, 15, 10), (155, -20, -50),
        (-120, -135, -15), (25, -150, 40), (150, -150, 75)]
BURST = (1, 4, 6)              # indices of the 3 rods that burst (one at a time)


def _rod_geo(lens, length=86, width=34):
    return fx_lens._cell_geo(lens.px(length), lens.px(width), n=10, cap=0.45)


def _rods(L, prefix):
    mat = fx_lens.lit_mat(f"{L.name}{prefix}RodMat", ROD, top=1.2, bottom=0.6)[0]
    core = fx_lens.lit_mat(f"{L.name}{prefix}CoreMat", ROD_CORE, top=1.0, bottom=0.6)[0]
    out = []
    for k, (x, y, a) in enumerate(RODS):
        o = _mesh(L, f"{prefix}Rod{k}", _rod_geo(L), mat, x, y, 14, rot=a)
        c = _mesh(L, f"{prefix}Core{k}", fx_lens._cell_geo(L.px(46), L.px(14), n=8, cap=0.5), core, 0, 0, 0)
        c.parent = o
        c.location = (0, 0, L.px(9))
        c.rotation_euler = (0, 0, 0)
        out.append(o)
    return out


def _phage_geo(lens):
    """Simplified T4 phage: icosahedral head, tail, 3 legs (on the local -y axis: the tail points down)."""
    h = kit._ico_geo(lens.px(9), (0, lens.px(12), 0), (0.85, 1.15, 0.85))
    t = kit._prism_geo(5, lens.px(2.6), lens.px(2.6), lens.px(12), oz=0.0)
    t = ([(p[0], -p[2] + lens.px(4), p[1]) for p in t[0]], t[1])
    legs = []
    for s in (-1, 0, 1):
        legs.append(kit._box_geo(lens.px(1.6), lens.px(7), lens.px(1.6), lens.px(1.6 * s * 2.2) - lens.px(0.8),
                                 -lens.px(14), 0))
    v, f, _ = kit.merge(h, t, *legs)
    return v, f


def lens_04(cam, f_open, f_third, f_spilled, total, f_end):
    """9 rods; 6 phages land on 3 of them; on *third* the 3 burst one at a time (8 frames between them) releasing
    amber dots; on *spilled* the dots spread out."""
    L = fx_lens.build("Lens04", cam, (610, 650), 560)
    rods = _rods(L, "A")
    ph_mat = fx_lens.lit_mat("Lens04PhageMat", PHAGE, top=1.25, bottom=0.6)[0]
    nut_mat = fx_lens._emit_mat("Lens04NutMat", NUTRIENT, 1.2)[0]
    rnd = random.Random(4)
    land0, land1 = f_open + OPEN + 2, f_open + OPEN + 32
    for n, bi in enumerate(BURST):
        x, y, a = RODS[bi]
        fb = f_third + 8 * n                                  # estouro deste bastonete
        phages = []
        for j, side in enumerate((-1, 1)):
            # landing point on the rod's edge (in lens pixels) and the fall from above
            ang = math.radians(a)
            px = x + math.cos(ang) * side * 22 - math.sin(ang) * 17
            py = y + math.sin(ang) * side * 22 + math.cos(ang) * 17
            o = _mesh(L, f"Phage{n}{j}", _phage_geo(L), ph_mat, px, py + 160, 40, rot=a + rnd.uniform(-15, 15))
            fr = list(range(land0 + 4 * j, land1 + 4 * j + 1))
            ys = [L.px(py + 160 * (1 - _ease_out((f - fr[0]) / (fr[-1] - fr[0])))) for f in fr]
            ac.write(o, "location", 1, fr, ys)
            phages.append(o)
        # the rod swells and vanishes; the phages vanish with it
        fr = [fb - 1, fb + 2, fb + 4]
        _scale_keys(rods[bi], fr, [1.0, 1.25, 0.0])
        for o in phages:
            _scale_keys(o, [fb - 1, fb + 3], [1.0, 0.0])
        # amber dots: born in place of the rod and, on *spilled*, spread out
        for j in range(7):
            ang = 2 * math.pi * j / 7 + rnd.uniform(-0.3, 0.3)
            r0, r1 = rnd.uniform(6, 22), rnd.uniform(60, 105)
            o = _mesh(L, f"Nut{n}{j}", kit._ico_geo(L.px(rnd.uniform(5.5, 7.5)), (0, 0, 0)), nut_mat,
                      x + r0 * math.cos(ang), y + r0 * math.sin(ang), 30)
            _scale_keys(o, [fb + 1, fb + 5], [0.0, 1.0])
            fr = list(range(f_spilled, f_spilled + 31))
            for i, base in ((0, x), (1, y)):
                trig = math.cos(ang) if i == 0 else math.sin(ang)
                ac.write(o, "location", i, fr,
                         [L.px(base + (r0 + (r1 - r0) * _ease_out((f - fr[0]) / 30)) * trig) for f in fr])
    open_close(L, f_open, None, total)
    ac.visible_ranges(objs(L), [(f_open, f_end)], total)
    return L


def lens_05(cam, f_show, f_close, total):
    """Same lens, a day later: 9 whole rods, no phage or amber. Closes on *cove*."""
    L = fx_lens.build("Lens05", cam, (610, 650), 560)
    _rods(L, "B")
    open_close(L, None, f_close, total, f_show=f_show)
    return L


# ---------- 07: as duas respostas ----------

CHAINS = [(-70, 70, 22, 5), (60, -30, -14, 4), (-50, -105, 8, 3), (85, 105, -32, 3)]
LIVE = 1.15                         # "alive" glow (multiplies the linear color)
B_LOW = 0.6 ** 2.2                  # B: ~60% of the perceived brightness (linear factor)
A_OFF = "#2E332B"                   # A: dark green almost gray


def _bubbles(L, f0, f1, specs, speed_fn, alive_fn):
    """Bubbles rising inside the lens. specs = [(x_px, phase 0..1, diameter_px)]; speed_fn(f) in px/frame;
    alive_fn(k, f) in 0..1 (vanishes shrinking). Rises from -150 to +150 px; scale 0 at the ends (the wrap-around does not show)."""
    mat = fx_lens.bubble_mat(f"{L.name}BubbleMat")
    out = []
    frames = list(range(f0, f1 + 1))
    travel, acc = [], 0.0
    for f in frames:
        travel.append(acc)
        acc += speed_fn(f)
    for k, (x, ph, d) in enumerate(specs):
        o = _mesh(L, f"Bubble{k}", kit._ico_geo(L.px(d / 2), (0, 0, 0)), mat, x, -150, 24)
        ys, ss = [], []
        for f, t in zip(frames, travel):
            u = (ph + t / 300.0) % 1.0
            ys.append(L.px(-150 + 300 * u))
            ss.append(max(TINY, math.sin(math.pi * u) ** 0.35 * alive_fn(k, f)))
        ac.write(o, "location", 1, frames, ys)
        _scale_keys(o, frames, ss)
        out.append(o)
    return out


def _anim_rgb(rgb, frames, colors):
    nt = rgb.id_data
    path = f'nodes["{rgb.name}"].outputs[0].default_value'
    for i in range(4):
        ac.write(nt, path, i, frames, [c[i] for c in colors])


def _scaled(hex_color, k):
    c = lin(hex_color)
    return (c[0] * k, c[1] * k, c[2] * k, 1.0)


def _mix(a, b, u):
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def _ring_dim(L, f0, n=12):
    """Amber ring fades (color -> dark grayish amber) along with the green."""
    mat = bpy.data.materials[f"{L.name}RingMat"]
    em = next(nd for nd in mat.node_tree.nodes if nd.type == "EMISSION")
    nt = mat.node_tree
    a, b = lin(fx_lens.RING), lin("#6E5A3A")
    frames = list(range(f0, f0 + n + 1))
    cols = [_mix(a, b, ac.ease((f - f0) / n)) for f in frames]
    for i in range(4):
        ac.write(nt, f'nodes["{em.name}"].inputs[0].default_value', i, frames, [c[i] for c in cols])


def lenses_07(cam, f_a, f_stops, f_b, f_drops, f_end, total):
    """Lens A (300, 560) and B (720, 560), diameter 400. A: alive with bubbles; on *stops* the bubbles stop (shrink) and the
    green fades in 12 frames (dark, almost gray) and the amber ring fades. B: opens on *One model*; on *drops* the
    brightness falls to ~60% (perceived) and half the bubbles vanish; the others rise more slowly."""
    A = fx_lens.build("LensA", cam, (300, 560), 400)
    B = fx_lens.build("LensB", cam, (720, 560), 400)
    _, rgbA = fx_lens.diatoms(A, random.Random(21), CHAINS, color=fx_lens.DIATOM_LIVE)
    chainsB, rgbB = fx_lens.diatoms(B, random.Random(21), CHAINS, color=fx_lens.DIATOM_LIVE)
    # B (model without viruses): on *drops* 2 of the 4 streams vanish ("fewer sea microbes", 2026-10-25)
    for k in (1, 3):
        _scale_keys(chainsB[k], [f_drops, f_drops + 12], [1.0, 0.0])
    live = _scaled(fx_lens.DIATOM_LIVE, LIVE)
    off = _scaled(A_OFF, 1.0)
    low = _scaled(fx_lens.DIATOM_LIVE, LIVE * B_LOW)
    n = 12
    fr = [f_a] + list(range(f_stops, f_stops + n + 1))
    _anim_rgb(rgbA, fr, [live] + [_mix(live, off, ac.ease((f - f_stops) / n)) for f in fr[1:]])
    fr = [f_b] + list(range(f_drops, f_drops + n + 1))
    _anim_rgb(rgbB, fr, [live] + [_mix(live, low, ac.ease((f - f_drops) / n)) for f in fr[1:]])
    _ring_dim(A, f_stops, n)
    specs = [(-110, 0.05, 14), (-40, 0.55, 12), (20, 0.3, 16), (75, 0.8, 13), (110, 0.15, 12), (-80, 0.7, 15)]
    # A: rises at 2.2 px/frame; on *stops* it stops and shrinks in 12 frames
    _bubbles(A, f_a, f_end, specs, lambda f: 2.2 if f < f_stops else 2.2 * max(0.0, 1 - (f - f_stops) / 6),
             lambda k, f: 1.0 - ac.ease((f - f_stops) / n) if f >= f_stops else 1.0)
    # B: half vanish on *drops*; the others rise at 60% of the speed
    _bubbles(B, f_b, f_end, specs, lambda f: 2.2 if f < f_drops else 2.2 * (1 - 0.4 * ac.ease((f - f_drops) / n)),
             lambda k, f: (1.0 - ac.ease((f - f_drops) / n)) if (f >= f_drops and k % 2 == 1) else 1.0)
    open_close(A, f_a, None, total)
    open_close(B, f_b, None, total)
    ac.visible_ranges(objs(A), [(f_a, f_end)], total)
    ac.visible_ranges(objs(B), [(f_b, f_end)], total)
    return SimpleNamespace(A=A, B=B)
