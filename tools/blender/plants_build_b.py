"""Final modeling, part B of plants-extinct: buildings and effects.

Replaces the MK_* markers of plants_markers (same place, same size): shed with door and sacks (shed),
damp/cracked flower bed with furrow, grains and stake (bed), smoothed west hill + mill + trail + person climbing
(tower_trail), 83/17 arrangement of the stall + amber strip and outline (amber), tabletop extension (table_ext), leaves
of 05 (leaves). Adds: motion in the sky of 05 (low clouds that move, 2 gulls, drifting leaves), dust
in the air of 1 YEAR, smoke from the brazier (NOW and 1 WEEK).

Timings: only from tm.first/last(sid) and the trigger word (voice.json), never a fixed frame.
Reusable models in tools/blender/lib/ (see lib/README.md).
"""

import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector, noise

import kit
import plants_markers as mk
import plants_models as pm
import plants_set as ps
import rigs
from lib import anim_curves as ac
from lib import fx_drift, fx_highlight, fx_leaves, garden_bed, grain_sack, gull, hill_trail, stone_shed
from lib import windmill_tower

# Marker groups (plants_markers) that this module replaces; see build_markers in plants-extinct.py.
REPLACED: set[str] = {"table_ext", "shed", "bed", "tower_trail", "amber", "leaves"}

ROOT = Path(__file__).resolve().parents[2]
VOICE = json.loads((ROOT / "build" / "plants-extinct" / "voice.json").read_text(encoding="utf-8"))
SCENES = tuple(f"{i:02d}" for i in range(1, 13))
STATE_OF = {"01": 0, "02": 0, "03": 1, "04": 1, "05": 1, "06": 1, "07": 1, "08": 2, "09": 2, "10": 3, "11": 3,
            "12": 0}
NOW, WEEK, YEAR, YEARS = 0, 1, 2, 3
SIDE = Vector((2.2, 0.4, 1.65))          # viewpoint of 05 (sky and tower), same as plants-extinct.py
BRAZIER = Vector((-0.6, 1.4, 0.9))       # table brazier (build_stall): base on the tabletop
TOP = 0.9                                 # height of the stall top


def W(sid, word, nth=0):
    hits = [w["start"] for w in VOICE[sid]["words"] if w["word"].strip("?.,:;").lower() == word.lower()]
    return hits[nth]


def F(tm, sid, word, nth=0):
    """Frame of the trigger word."""
    return tm.f(sid, W(sid, word, nth))


def _all(objs):
    out = []
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        out += [o, *o.children_recursive]
    return out


def show_states(tm, objs, states):
    """Turns the object and all children on only in the scenes whose state is in 'states' (switch on the cut)."""
    for o in _all(objs):
        for sid in SCENES:
            o.hide_render = STATE_OF[sid] not in states
            o.keyframe_insert("hide_render", frame=tm.first(sid))


def show_frames(objs, ranges, total):
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for o in _all(objs):
        for f in marks:
            o.hide_render = not any(a <= f <= b for a, b in ranges)
            o.keyframe_insert("hide_render", frame=f)


def mat(name, color, **kw):
    return pm.fixed_mat(f"B_{name}", color, **kw)


def state_mat(name, colors, rough=0.9):
    m, n, L, p = pm.node_mat(f"B_{name}", rough, 0.15)
    L.new(pm.state_ramp(n, L, colors), p.inputs["Base Color"])
    return m


# ---------- tabletop extension ----------

def build_table_ext(tm, M):
    """Auxiliary table against the right end of the stall (x 1.2 to 2.1), same height and the same 6 boards with
    gap, apron in front, 2 legs at the end and crosspiece: reads as a joined table, not a loose plank."""
    x0, x1 = mk.TABLE_EXT
    y0, depth = 0.85, 0.8
    parts = []
    for k in range(6):
        parts.append(kit._box_geo(x1 - x0 - 0.01, depth / 6 - 0.01, 0.04, x0 + 0.01, y0 + depth * k / 6, TOP - 0.04))
    parts.append(kit._box_geo(x1 - x0 - 0.01, 0.03, 0.22, x0 + 0.01, y0 + depth - 0.03, TOP - 0.26))   # saia
    for y in (y0 + 0.05, y0 + depth - 0.1):
        parts.append(kit._box_geo(0.06, 0.06, TOP - 0.04, x1 - 0.08, y, 0.0))                          # legs
    parts.append(kit._box_geo(0.04, depth - 0.12, 0.08, x1 - 0.07, y0 + 0.06, 0.3))                     # travessa
    v, f, _ = kit.merge(*parts)
    o = pm.obj_from("TableExt", (v, f), [M["wood"]])
    show_states(tm, o, (NOW, WEEK, YEAR))
    return o


# ---------- 83/17 arrangement of the stall (06) ----------

FOOD_SHIFT = -0.12           # crates 12 cm to the left (the end stays free for cheese and ham)
BAND_X = (-0.37, 1.66)       # 83% of the food line (-0.37 to 2.07): storable plant
CHEESE_AT = Vector((1.79, 1.06))
HAM_LINE = ((2.0, 0.96), (2.0, 1.32))


def arrange_stall(tm, M):
    """Storable plant in the left 83% (fruit, flour, bread, beans, olive oil), animal product in the 17% at the end (cheese
    and ham), in the front row that the camera of 06 sees. Only moves the objects of build_stall."""
    objs = bpy.data.objects
    for k in range(4):
        c = objs.get(f"Crate{k}")
        if c:
            c.location.x += FOOD_SHIFT
    moves = {"Bread": (0.55 - 1.7, 0.0), "Beans": (0.18 - 1.95, 1.05 - 1.45),
             "Cheese": (CHEESE_AT.x - 1.45, CHEESE_AT.y - 1.1)}
    for name, (dx, dy) in moves.items():
        o = objs.get(name)
        if o:
            o.location = (dx, dy, 0.0)
    ham = objs.get("Ham")
    if ham:                       # ham lying along y at the end, same profile (rebuilds the mesh)
        (ax, ay), (bx, by) = HAM_LINE
        v, f = kit.tube_geo([(ax, ay, TOP + 0.07), (bx, by, TOP + 0.08)], [0.07, 0.045], n=7)
        me = ham.data
        me.clear_geometry()
        me.from_pydata(v, [], f)
        me.update()
    # olive oil: clay jug with cork lid (storable plant), in the front row
    jx, jy = 0.76, 0.98
    jar = kit.loft_geo([[(r * math.cos(2 * math.pi * i / 9) + jx, r * math.sin(2 * math.pi * i / 9) + jy, TOP + z)
                         for i in range(9)] for r, z in ((0.05, 0.0), (0.075, 0.07), (0.07, 0.15), (0.035, 0.2),
                                                         (0.035, 0.24))])
    cork = kit._prism_geo(7, 0.03, 0.026, 0.035, oz=TOP + 0.24, ox=jx, oy=jy)
    v, f, own = kit.merge(jar, cork)
    oil = pm.obj_from("OilJar", (v, f), [M["terracotta"], mat("Cork", "#B08A5A")],
                      face_mats=[0 if k == 0 else 1 for k in own])
    # rice: low wooden bowl with a white mound (storable plant), between the flour and the cheese
    bowl = kit.loft_geo([[(r * math.cos(2 * math.pi * i / 10) + 1.42, r * math.sin(2 * math.pi * i / 10) + 1.04,
                           TOP + z) for i in range(10)] for r, z in ((0.07, 0.0), (0.12, 0.05), (0.13, 0.07))],
                        cap_end=False)
    rice = pm.lumpy_ico(0.11, (1.42, 1.04, TOP + 0.05), (1, 1, 0.38), random.Random(4), 0.06)
    v, f, own = kit.merge(bowl, rice)
    rb = pm.obj_from("RiceBowl", (v, f), [M["wood"], mat("Rice", "#EEEAE0", rough=0.95)],
                     face_mats=[0 if k == 0 else 1 for k in own])
    show_states(tm, [oil, rb], (NOW, WEEK))
    return oil


def build_amber(tm, M, total):
    f_sw = F(tm, "06", "straight")
    f_sw1 = f_sw + 36                                   # sweeps in 1.2 s
    f_ham, f_cheese = F(tm, "06", "ham"), F(tm, "06", "cheese")
    f_end = tm.last("06")
    bm = fx_highlight.band_mat("B_AmberBand", strength=1.0, feather=0.07)
    band = fx_highlight.band("AmberBand", BAND_X[0], BAND_X[1], 0.87, 1.63, TOP + 0.001, bm)
    fx_highlight.grow_band(band, [(f_sw - 1, 0.0), (f_sw, 0.0), (f_sw1, 1.0), (f_end - 18, 1.0), (f_end, 0.0)])
    show_frames(band, [(f_sw, f_end)], total)
    om = fx_highlight.outline_mat("B_AmberOutline")
    rings = []
    for name, f0 in (("Ham", f_ham), ("Cheese", f_cheese)):
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        fx_highlight.outline(o, om, [(f0 - 1, 0.0), (f0, 0.002), (f0 + 9, 0.006), (f_end - 12, 0.006),
                                     (f_end - 3, 0.0)])
        rings.append(o)
    return band, rings


# ---------- shed and sacks ----------

def build_shed(tm, M, rnd):
    x0, x1, y0, y1 = mk.SHED
    sm = {"stone": M["stone"], "wood": M["wood"], "roof": M["roof"], "dark": mat("ShedFloor", "#3A3028")}
    shed = stone_shed.build("Shed", x0, x1, y0, y1, sm, door=(0.0, 1.0))
    sk = {"sack": M["sack"], "grain": mat("Grain", "#C8A860", rough=0.95)}
    ix0, ix1, iy0, iy1 = shed.inside
    full, kept = [], []
    # piles of sacks lying along the back and the north wall, up to ~1.8 m (NOW, 1 WEEK); in 1 YEAR 3 remain
    k = 0
    for layer in range(5):
        for j in range(4 - (layer > 2)):
            y = iy0 + 0.3 + j * 0.56 + (0.28 if layer % 2 else 0.0)
            o = grain_sack.closed_sack(f"ShedSack{k}", (ix0 + 0.35, y, layer * 0.33), sk, rnd, lying=True,
                                       heading=math.pi / 2 + rnd.uniform(-0.08, 0.08))
            (kept if layer == 0 and j < 3 else full).append(o)
            k += 1
    for j in range(3):                                    # standing against the south wall, near the door
        o = grain_sack.closed_sack(f"ShedSackUp{j}", (ix0 + 0.9 + j * 0.42, iy1 - 0.3, 0.0), sk, rnd,
                                   heading=rnd.uniform(0, 6.28))
        full.append(o)
    show_states(tm, full, (NOW, WEEK))
    show_states(tm, kept, (NOW, WEEK, YEAR, YEARS))
    door_sack = grain_sack.open_sack("SackOpen", tuple(mk.SACK), sk, rnd)
    show_states(tm, door_sack, (NOW, WEEK))
    return shed


# ---------- canteiro ----------

def build_bed(tm, M, rnd):
    x0, x1, y0, y1 = mk.BED
    wet = garden_bed.soil("BedWet", x0, x1, y0, y1, mk.FURROW_X, state_mat("BedWet", ("#5E4A36", "#6E5840",
                                                                                         "#6E5840", "#6E5840")),
                          rnd, depth=0.05, width=0.055, ridge=0.018, furrow_mat=mat("Furrow", "#463626"))
    dry = garden_bed.soil("BedCracked", x0, x1, y0, y1, mk.FURROW_X, garden_bed.cracked_mat("B_Cracked"),
                          rnd, depth=0.022, width=0.06, ridge=0.006, lump=0.008)
    stones = garden_bed.border("BedStones", x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04, M["stone"], rnd)
    label = state_mat("Label", ("#E6DFD0", "#E6DFD0", "#C9BFAA", "#BDB4A2"))
    tutor = garden_bed.stake("Tutor", tuple(mk.TUTOR), M["wood"], label)
    seed_pts = []
    for y in (2.62, 2.71, 2.8, 2.93, 3.03):
        x = mk.FURROW_X + rnd.uniform(-0.012, 0.012)
        z = garden_bed.surface_z(x, y, lump=0.008, depth=0.022, width=0.06, furrow_x=mk.FURROW_X)
        seed_pts.append((x, y, z + 0.016))     # above the terrain (the grid is linear between vertices)
    seeds = garden_bed.seeds("Seeds", seed_pts, mat("Seed", "#C8A860", rough=0.6, spec=0.3), rnd, length=0.032)
    show_states(tm, [wet], (NOW, WEEK))
    show_states(tm, [dry], (YEAR, YEARS))
    show_states(tm, seeds, (YEAR,))
    return stones, tutor


# ---------- smoothed west hill, mill and trail ----------

HILL_GRID = (18.0, 520.0, -80.0, 330.0, 6.0)        # same as plants_set.build_west_hill


def _smin(a, b, k):
    m = min(a, b)
    return m - k * math.log(math.exp(-(a - m) / k) + math.exp(-(b - m) / k))


def west_z_soft(x, y):
    """West hill with a natural left flank: instead of the cut by bearing (straight wall), the hill is bounded by
    an ANGLE ceiling seen from the stall that rises with the bearing (-6 deg to 50 deg, ~25 deg to 78 deg) and has spurs from noise. So it
    stays hidden below ~50 deg of bearing (H1, H2, sea of 02, sky bridge) and rises in a ridge to the tower.
    Meets the square at the paving level (-0.3 m), descending to the sea to the south."""
    base = -0.3 - 1.4 * max(0.0, y - 19.6)
    base = max(base, -45.0)
    d = math.hypot(x - 254.0, y - 54.0)
    rise = 104.0 * max(0.0, 1.0 - d / 260.0) ** 1.4 + 2.0 * noise.noise(Vector((x * 0.02, y * 0.02, 2.1)))
    dx, dy = x - SIDE.x, y - SIDE.y
    dist = math.hypot(dx, dy)
    b = math.degrees(math.atan2(dx, dy))
    cap_deg = -6.0 + 1.1 * (b - 50.0) + 3.0 * noise.noise(Vector((x * 0.015, y * 0.015, 7.3)))
    cap_deg = max(-60.0, min(60.0, cap_deg))
    cap = SIDE.z + dist * math.tan(math.radians(cap_deg))
    z = _smin(rise, cap, 5.0)
    z = max(base, z)
    if y > 40.0:
        z -= 0.22 * (y - 40.0) + 0.0016 * (y - 40.0) ** 2
    if x < 18.6:
        z = min(z, -0.3)
    return max(z, -45.0)


def soften_west_hill():
    o = bpy.data.objects.get("WestHill")
    if o is None:
        return None
    me = o.data
    co = [0.0] * (len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    for i in range(0, len(co), 3):
        co[i + 2] = west_z_soft(co[i], co[i + 1])
    me.vertices.foreach_set("co", co)
    me.update()
    return o


def _grid_z(x, y):
    """Height of the grid mesh (what the render shows), not of the function: maximum of the two triangulations of the quad
    (the trail ribbon never sinks into the ground)."""
    gx0, gx1, gy0, gy1, cell = HILL_GRID
    nx, ny = max(2, int((gx1 - gx0) / cell)), max(2, int((gy1 - gy0) / cell))
    dx, dy = (gx1 - gx0) / nx, (gy1 - gy0) / ny
    i = min(nx - 1, max(0, int((x - gx0) / dx)))
    j = min(ny - 1, max(0, int((y - gy0) / dy)))
    xa, ya = gx0 + i * dx, gy0 + j * dy
    u, v = (x - xa) / dx, (y - ya) / dy
    z00, z10 = west_z_soft(xa, ya), west_z_soft(xa + dx, ya)
    z01, z11 = west_z_soft(xa, ya + dy), west_z_soft(xa + dx, ya + dy)
    ta = z00 + u * (z10 - z00) + v * (z11 - z10) if u > v else z00 + v * (z01 - z00) + u * (z11 - z01)
    tb = z00 + u * (z10 - z00) + v * (z01 - z00) if u + v < 1 else z11 + (1 - u) * (z01 - z11) + (1 - v) * (z10 - z11)
    return max(ta, tb)


TRAIL_A = (30.0, -6.0)                    # foot of the trail: behind the west end of the square (out of frame of 05)
TRAIL_B = (246.0, 50.0)                   # reaches the mill door


def build_tower_trail(tm, M, total):
    soften_west_hill()
    T = mk.TOWER
    ring = [_grid_z(T.x + 4.2 * math.cos(a), T.y + 4.2 * math.sin(a)) for a in [k * math.pi / 4 for k in range(8)]]
    zb = min(ring)
    facing = math.atan2(SIDE.y - T.y, SIDE.x - T.x) + math.radians(10)
    wm = {"wall": M["wall"], "roof": mat("TowerRoof", "#4A4038", rough=0.85), "dark": mat("TowerDark", "#2A2622"),
          "wood": mat("SailWood", "#5A4632"), "sail": mat("Sail", "#EDE6D6", rough=0.95)}
    mill = windmill_tower.build("Windmill", (T.x, T.y, zb), wm, facing, radius=4.0, height=10.0,
                                sink=1.5 + max(ring) - zb)
    # blades turning slowly (1 turn every ~14 s), throughout the video
    frames = list(range(1, total + 1, 2))
    ac.write(mill.sails, "rotation_euler", 0, frames, [2 * math.pi * (f - 1) / (30 * 14.0) for f in frames])
    # trilha
    pts = hill_trail.switchbacks(TRAIL_A, TRAIL_B, legs=7, swing=17.0)
    curve, length = rigs.smooth_path(pts, samples=420)
    path, edge = hill_trail.build("Trail", curve, _grid_z, mat("Trail", "#DCD0B6", rough=1.0),
                                  mat("TrailEdge", "#7A6A55", rough=1.0), width=1.9, lift=0.25, edge=0.5)
    # person climbing (Quaternius Man, CC0), all of 05 and 06 until leaving the tower
    a, b = tm.first("05"), tm.last("06")
    climber = rigs.spawn("man", "Climber", height=1.74)
    rigs.paint(climber, {"Shirt": "#B8583A", "Pants": "#2A3446", "Skin": "#C8916A", "Hair": "#2A1E16",
                         "HairBase": "#2A1E16", "Eyes": "#1A1410", "Socks": "#D8D2C4", "Shoes": "#2A2622"})
    speed = 0.95
    d0 = length * 0.36 - speed * (F(tm, "05", "climbing") - a) / 30.0   # ~1/3 of the climb at the tower
    fr = list(range(a - 2, b + 3))
    pos, hd = [], []
    for f in fr:
        p, h = rigs.along(curve, length, d0 + speed * (f - a) / 30.0)
        pos.append(Vector((p.x, p.y, _grid_z(p.x, p.y) + 0.28)))
        hd.append(h)
    rigs.key_root(climber, fr, pos, hd)
    per = rigs.planted_speed(climber, "Walk", ["Foot.L", "Foot.R"]) * climber.scale
    a0, _ = climber.t.actions["Walk"].frame_range
    rigs.timed(climber, "Walk", fr, [a0 + speed / 30 * (f - fr[0]) / per for f in fr])
    show_frames(rigs.all_objects(climber), [(a - 2, b + 2)], total)
    return mill, path


# ---------- sky of 05: low clouds that move, gulls, leaves ----------

def _dir(bearing, elev):
    a, e = math.radians(bearing), math.radians(elev)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def build_sky_life(tm, M, total, rnd):
    cloud_mat = bpy.data.materials.get("Cloud") or pm.fixed_mat("Cloud", "#F2F5F8", rough=1.0, emission="#F2F5F8",
                                                                 strength=0.25)
    # low clouds (cumulus at ~1.4 km), above 40 deg elevation: outside H1/H2 (top of frame at ~35 deg);
    # move with the wind to the west (+x, right in 05) at ~7 m/s: ~0.3 deg/s, noticeable in the still sky of 05
    clouds = []
    wind = Vector((7.0, -1.0, 0.0))
    for k, (bearing, elev, dist, w) in enumerate(((6, 47, 1500, 150), (30, 58, 1300, 120), (40, 43, 1700, 190),
                                                  (18, 64, 1250, 110))):
        c = SIDE + _dir(bearing, elev) * dist
        geos = []
        for j in range(5):
            off = Vector((rnd.uniform(-0.5, 0.5) * w, rnd.uniform(-0.2, 0.2) * w, rnd.uniform(0, 0.12) * w))
            geos.append(pm.lumpy_ico(w * rnd.uniform(0.18, 0.3), tuple(off), (1.0, 0.75, 0.45), rnd, 0.12))
        v, f, _ = kit.merge(*geos)
        o = pm.obj_from(f"CloudLow{k}", (v, f), [cloud_mat])
        o.visible_shadow = False
        fr = [1, total]
        mid = tm.f("05", W("05", "rotted"))           # composition position in the middle of 05
        ac.write_vec(o, "location", fr, [c + wind * (f - mid) / 30.0 for f in fr])
        clouds.append(o)
    # gulls: 2 gliding in wide circles in the sky of 05 (only 05; out of frame at entry and exit)
    gm = {"white": mat("GullWhite", "#EEF0F0", rough=0.9), "grey": mat("GullGrey", "#8E979F", rough=0.9),
          "black": mat("GullBlack", "#22262A", rough=0.9)}
    a, b = tm.first("05"), tm.last("05")
    gulls = []
    for k, (bearing, elev, dist, rad, w, cw) in enumerate(((32, 44, 40, 9, 0.85, 1), (14, 55, 52, 12, 0.6, -1))):
        g = gull.build(f"Gull{k}", gm, scale=1.0)
        c = SIDE + _dir(bearing, elev) * dist
        ph = rnd.uniform(0, 6.28)
        n = b - a

        def path(u, c=c, rad=rad, w=w, cw=cw, ph=ph, n=n):
            t = u * n / 30.0
            ang = ph + cw * (9.0 / rad) * t                     # ~9 m/s on the lap
            return c + Vector((rad * math.cos(ang), rad * 0.7 * math.sin(ang), 1.2 * math.sin(0.5 * t)))
        fr = list(range(a, b + 1))
        flaps = [(a + int(30 * s), a + int(30 * s) + 22) for s in ((1.5, 5.8, 10.2) if k == 0 else (3.4, 8.6, 12.0))]
        gull.animate(g, fr, path, flaps)
        show_frames(g.root, [(a, b)], total)
        gulls.append(g)
    return clouds, gulls


def build_leaves(tm, M, total, rnd):
    """Leaves of 05: 3 drifting before the gust, gust of 16 at 'rotted' (leave the right edge of the crown and
    cross the sky to the right), 3 after. All are born INSIDE the crown (nothing appears in mid-air) and leave the frame."""
    lm = [mat("LeafDry1", "#9C6A36", rough=0.85), mat("LeafDry2", "#A8703A", rough=0.85),
          mat("LeafDry3", "#8A5A2B", rough=0.85)]
    f_rot = F(tm, "05", "rotted")
    f_bil = F(tm, "05", "billions")
    f_cl = F(tm, "05", "climbing")
    leaves = []

    def make(k, f0, dur, start, end, sway=1.0, drop=0.0, land=False):
        o = pm.obj_from(f"Leaf{k}", fx_leaves.leaf_geo(rnd.uniform(0.24, 0.32)), [lm[k % 3]])
        o.visible_shadow = False
        S, E = Vector(start), Vector(end)
        ctrl = S.lerp(E, 0.45) + Vector((0, 0, rnd.uniform(0.5, 1.6)))

        def path(u):
            # quadratic Bezier: leaves up-right with the gust, then falls
            return S * (1 - u) ** 2 + ctrl * 2 * u * (1 - u) + E * u * u - Vector((0, 0, drop * u ** 2))
        fr = list(range(f0, f0 + dur + 1))
        fx_leaves.fly(o, fr, path, rnd, spin=sway, tumble=sway)
        if land:            # slow leaf lands on the paving and stays until the end of 1 WEEK (nothing vanishes mid-scene)
            fe = f0 + dur
            o.location = (E.x, E.y, 0.03)
            o.rotation_euler = (0.0, 0.0, rnd.uniform(0, 6.28))
            o.keyframe_insert("location", frame=fe + 5)
            o.keyframe_insert("rotation_euler", frame=fe + 5)
            show_frames(o, [(f0, tm.last("07"))], total)
        else:
            show_frames(o, [(f0, f0 + dur)], total)
        leaves.append(o)

    def canopy_pt():
        return (rnd.uniform(2.6, 4.2), rnd.uniform(10.5, 14.0), rnd.uniform(8.5, 12.5))

    k = 0
    for j in range(3):                                   # slow drift before the gust
        f0 = f_bil + 10 + j * int((f_rot - f_bil - 60) / 3)
        s = canopy_pt()
        make(k, f0, 150, s, (s[0] + 12 + rnd.uniform(0, 2), s[1] - rnd.uniform(1, 3), 0.3), 0.7, land=True)
        k += 1
    for j in range(16):                                  # rajada
        f0 = f_rot + int(j * 1.2)
        s = canopy_pt()
        make(k, f0, rnd.randint(70, 90), s,
             (s[0] + rnd.uniform(18, 24), s[1] - rnd.uniform(0, 4), s[2] + rnd.uniform(-5.5, -2.0)), 1.3)
        k += 1
    for j in range(3):                                   # after: slow drift until the camera descends
        f0 = f_rot + 60 + j * 14
        s = canopy_pt()
        make(k, f0, max(60, f_cl - f0 - 5), s, (s[0] + 12 + rnd.uniform(0, 2), s[1] - rnd.uniform(1, 3), 0.3), 0.7,
             land=True)
        k += 1
    return leaves


# ---------- dust of 1 YEAR and smoke from the brazier ----------

def build_dust(tm, M, total, rnd):
    dm = mat("Dust", "#857258", rough=1.0)
    a, b = tm.first("08"), tm.last("09")
    objs = fx_drift.dust("Dust", (-5.0, 5.0, 0.6, 9.0, 0.05, 2.4), dm, rnd, 60, (a, b), wind=(-0.6, 0.1, 0.0),
                         size=(0.008, 0.013))
    show_frames(objs, [(a, b)], total)
    return objs


def build_smoke(tm, M, total, rnd):
    """Thread of smoke from the brazier (NOW and 1 WEEK: scenes 01-07 and 12), lying to the west (+x) with the gust wind
    of 05. Comes off the flame of the table brazier (top of the flame ~1.2 m)."""
    sm = mat("BrazierSmoke", "#D2D0CA", rough=1.0, emission="#D2D0CA", strength=0.15)
    src = BRAZIER + Vector((0.0, 0.0, 0.31))
    out = []
    for name, (a, b) in (("SmokeA", (1, tm.last("07"))), ("SmokeB", (tm.first("12"), total))):
        o = fx_drift.smoke_wisp(name, src, sm, (a, b), height=0.62, lean=0.2)
        show_frames(o, [(a, b)], total)
        out.append(o)
    return out


# ---------- montagem ----------

def build(tm, M, total, poses):
    rnd = random.Random(2410)
    build_table_ext(tm, M)
    arrange_stall(tm, M)
    build_amber(tm, M, total)
    build_shed(tm, M, rnd)
    build_bed(tm, M, rnd)
    build_tower_trail(tm, M, total)
    build_sky_life(tm, M, total, random.Random(5))
    build_leaves(tm, M, total, random.Random(12))
    build_dust(tm, M, total, random.Random(8))
    # build_smoke(tm, M, total, rnd)  # disabled: the thread at 1.5 m from the camera changes the cover (H1); see NOTES
