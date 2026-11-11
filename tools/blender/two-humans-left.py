"""Animation for the two-humans-left script: a river valley, a man and a woman, 300 years (BLOCKOUT, 2026-10-22).

Run by 'python -m ifscape blender scripts/two-humans-left.json'. Eye-level POV (1.65 m).
NEW set: valley with river, wooden bridge, cabin on the near bank (south), village on the opposite bank (north).
Timings: the timeline comes from the voice (timeline.json); actions tied to words use valley_lib.when(scene, word).
Light only changes on cuts (sky states in town_sky, reused: sky and stars are a kit piece).
Proportions: man 1.75 m, woman 1.62 m (CDC growth charts); door 2.3 m; Kenney Fantasy Town Kit (CC0) 1 panel = 2.3 m.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import kit  # noqa: E402
import rigs  # noqa: E402
import town_sky as sky  # noqa: E402
import valley_cast as cast  # noqa: E402
import valley_houses as vh  # noqa: E402
import valley_lib as vl  # noqa: E402
import valley_world as vw  # noqa: E402
from kit import key  # noqa: E402

EYE = 1.65
SCENES = tuple(f"{i:02d}" for i in range(1, 12))
LIT = 3.0                                  # emission of the lit windows (above ~4 the amber turns pale yellow)

# Light states: they only change on the cut. (sky, sun, ambient, ambient color, sun rotation, sun color, Milky Way, stars)
DUSK = dict(sky="dusk", sun=1.7, ambient=1.5, amb="#3A5285", rot=(80, 0, -20), color=(1.0, 0.62, 0.38), band=0.0,
            stars=0.0, reveal=0.0)
SUNRISE = dict(sky="sunset", sun=2.6, ambient=1.5, amb="#5A6A95", rot=(78, 0, 100), color=(1.0, 0.62, 0.36), band=0.0,
               stars=0.0, reveal=0.0)
BLUEHOUR = dict(sky="nightfall", sun=1.4, ambient=2.4, amb="#3A4F80", rot=(80, 0, -20), color=(1.0, 0.58, 0.34),
                band=0.0, stars=0.0, reveal=0.0)
NIGHT = dict(sky="night", sun=0.7, ambient=2.7, amb="#33497A", rot=(55, 0, -30), color=(0.62, 0.72, 1.0), band=0.0,
             stars=1.0, reveal=0.06)
NIGHT7 = dict(NIGHT, stars=0.25, reveal=0.0)
NIGHT10 = dict(NIGHT, stars=0.3, reveal=0.0, band=0.1)
NIGHT_MW = dict(NIGHT, band=0.32, stars=5.0, reveal=1.2)
EVENING = dict(sky="dusk", sun=2.3, ambient=1.5, amb="#4A5A8A", rot=(82, 0, -20), color=(1.0, 0.6, 0.34), band=0.0,
               stars=0.0, reveal=0.0)
EVE5 = dict(DUSK, sun=3.2, ambient=2.0, amb="#4F5F92", rot=(72, 0, -35), color=(1.0, 0.6, 0.32))
INSIDE = dict(DUSK, ambient=1.3, sun=0.35, sky_s=0.5)
LIGHT = {"01": DUSK, "02": DUSK, "03": INSIDE, "04": SUNRISE, "05": EVE5, "06": BLUEHOUR, "07": NIGHT7,
         "08": EVENING, "09": BLUEHOUR, "10": NIGHT10, "11": NIGHT_MW}


# ---------- time utilities ----------

def F(tl, sid, sec):
    """Frame of scene sid, sec seconds after its start."""
    return tl.at(sid) + int(round(sec * tl.fps))


def W(tl, sid, word, nth=0, off=0.0):
    return F(tl, sid, vl.when(sid, word, nth) + off)


class Keyed:
    """Animated value of a socket/property with hard cuts (CONSTANT) and ramps (LINEAR)."""

    def __init__(self, owner, attr, initial):
        self.owner, self.attr = owner, attr
        self.ev = {1: (initial, False)}

    def value_at(self, f):
        fs = [x for x in self.ev if x <= f]
        return self.ev[max(fs)][0]

    def cut(self, f, v):
        self.ev[f] = (v, False)

    def to(self, f0, f1, v):
        f1 = max(f1, f0 + 1)
        if f0 not in self.ev:
            self.ev[f0] = (self.value_at(f0), False)
        self.ev[f1] = (v, True)

    def apply(self):
        frames = sorted(self.ev)
        for f in frames:
            setattr(self.owner, self.attr, self.ev[f][0])
            self.owner.keyframe_insert(self.attr, frame=f)
        ad = self.owner.id_data.animation_data
        if ad is None or ad.action is None:
            return
        for fc in rigs._fcurves(ad.action):
            if fc.data_path.endswith(self.attr) and len(fc.keyframe_points) == len(frames):
                for i, kp in enumerate(fc.keyframe_points):
                    nxt = self.ev[frames[i + 1]][1] if i + 1 < len(frames) else False
                    kp.interpolation = "LINEAR" if nxt else "CONSTANT"


# ---------- sky light ----------

def lights(w, tl):
    for sid in SCENES:
        st, f = LIGHT[sid], tl.at(sid)
        for name, sock in w.factors.items():
            key(sock, "default_value", 1.0 if name == st["sky"] else 0.0, f)
        key(w.sun, "energy", st["sun"], f)
        key(w.ambient, "default_value", st["ambient"], f)
        key(w.sky, "default_value", st.get("sky_s", 1.0), f)
        key(w.ambient_color, "default_value", kit.lin(st["amb"]), f)
        key(w.sun_obj, "rotation_euler", tuple(math.radians(a) for a in st["rot"]), f)
        w.sun.color = st["color"]
        w.sun.keyframe_insert("color", frame=f)
    for owner in (w.sun, w.sun_obj, w.world.node_tree):
        vl.constant(owner)


def sky_detail(w, stars, tl):
    _, reveal, power = stars
    for sid in SCENES:
        a, b = tl.at(sid), tl.at(sid, 1.0) - 1
        for sock, k in ((power, "stars"), (reveal, "reveal"), (w.band, "band")):
            for f in (a, b):
                key(sock, "default_value", LIGHT[sid][k], f)
    for sock in (power, reveal, w.band):
        ad = sock.id_data.animation_data
        if ad and ad.action:
            for fc in rigs._fcurves(ad.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


# ---------- camera ----------

# scene: [(fraction of the scene, position, target)] ; 2 keys = smooth continuous motion.
MAN1, WOM1 = (-2.9, -10.7), (-1.6, -10.2)        # the couple in 01/02 (at 3.4 and 4.3 m from the camera)
CAM07 = (2.5, -21.0)
CAM05 = (-19.0, -28.0)
FIRE5 = (-13.55, -24.85)                           # to the right of the pole in the frame (bearing 30 degrees from the camera)
POST = (-15.62, -25.01)
BENCH = (-0.5, -12.0)                              # bench of 04, beside the bridge trail
SIT_LIFT = 0.03                                    # hip of the seated couple rises (thighs went through the seat)
SIT_FWD = 0.17                                     # couple moves forward on the seat (knees go past the edge, shins stay IN FRONT of the bench)
SIT_HEAD = 221.6                                   # gaze direction seated: toward the camera of 04
CAM04 = (-3.2, -14.4)


def _aim(pos, bearing, dist, z):
    return (pos[0] + dist * math.cos(math.radians(bearing)), pos[1] + dist * math.sin(math.radians(bearing)), z)


def camera_keys(tl):
    z = EYE
    kz = vw.height(*vw.KNOLL) + EYE
    c04, c05 = CAM04, CAM05
    return {
        "01": [(0.0, (-5.5, -14.4, 1.8), (1.2, -2.0, 0.0)), (1.0, (-5.4, -14.0, 1.8), (1.3, -2.0, 0.0))],
        "02": [(0.0, (-5.4, -14.0, 1.8), (1.3, -2.0, 0.0)), (0.55, (-5.3, -13.9, 1.8), (1.3, -2.0, 0.0)),
               (1.0, (-5.2, -13.7, 1.62), (1.3, -2.0, -0.1))],
        "03": [(0.0, (-12.6, -16.3, 1.5), (-12.6, -12.7, 0.9)), (1.0, (-12.5, -15.7, 1.5), (-12.5, -12.7, 0.9))],
        "04": [(0.0, (*c04, z), _aim(c04, 50, 10, 1.3)), (1.0, (c04[0] - 0.3, c04[1] - 0.2, z), _aim(c04, 50, 10, 1.3))],
        "05": [(0.0, (*c05, z), _aim(c05, 44, 10, 1.1)), (1.0, (c05[0] + 0.4, c05[1] + 0.3, z), _aim((c05[0] + 0.4, c05[1] + 0.3), 43, 10, 1.05))],
        "06": [(0.0, (-3.0, -36.0, kz), (-12.0, -16.0, 1.2)), (0.45, (-3.0, -36.0, kz), (-2.0, -6.0, 0.8)),
               (0.75, (-2.5, -37.0, kz), (4.0, 12.0, -1.5)), (1.0, (-2.5, -38.5, vw.height(-2.5, -38.5) + EYE),
                                                               (4.0, 34.0, -7.0))],
        "07": [(0.0, (*CAM07, z), (CAM07[0], 30.0, 15.0)), (0.72, (*CAM07, z), (CAM07[0], 30.0, 15.0)),
               (1.0, (3.2, -13.0, z), (3.2, 22.0, 2.6))],
        "08": [(0.0, (4.3, 1.0, 3.0), (4.0, 40.0, 3.0)), (1.0, (4.2, 14.0, 3.4), (4.0, 50.0, 3.8))],
        "09": [(0.0, (4.1, -8.0, z), (4.0, 40.0, 2.2)), (1.0, (4.1, 14.0, z), (4.0, 48.0, 2.2))],
        "10": [(0.0, (4.0, 16.0, z), (4.0, 56.0, 11.6)), (1.0, (4.0, 16.8, 2.0), (4.0, 56.0, 12.6))],
        "11": [(0.0, (3.6, 14.0, 1.5), (3.6, 30.0, 4.5)), (1.0, (3.6, 16.5, 1.5), (3.6, 30.0, 5.0))],
    }


LENS = {"01": 20, "02": 20, "03": 17, "04": 22, "05": 22, "06": 20, "07": 16, "08": 22, "09": 22, "10": 18, "11": 20}


def build_camera(tl):
    data = bpy.data.cameras.new("Eye")
    data.lens = 19
    data.clip_start, data.clip_end = 0.03, 4000.0
    cam = bpy.data.objects.new("Eye", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    keys = camera_keys(tl)
    prev = None
    for sid in SCENES:
        a, b = tl.scenes[sid]
        ks = keys[sid]
        for f in range(a, b):
            u = (f - a) / max(b - 1 - a, 1)
            for (ua, pa, ta), (ub, pb, tb) in zip(ks, ks[1:]):
                if ua <= u <= ub:
                    t = (u - ua) / (ub - ua)
                    t = t * t * (3 - 2 * t) if len(ks) > 2 else t * t * (3 - 2 * t) * 0.6 + t * 0.4
                    pos, target = Vector(pa).lerp(Vector(pb), t), Vector(ta).lerp(Vector(tb), t)
                    break
            sway = Vector((math.sin(f * 0.07) * 0.006 + 0.002 * math.sin(f * 0.23), math.sin(f * 0.05 + 1) * 0.004,
                           math.sin(f * 0.09 + 2) * 0.005))
            if sid in ("05", "08", "09"):
                sway.z += 0.012 * math.sin(2 * math.pi * f / 16)
            pos = pos + sway
            q = (target - pos).to_track_quat("-Z", "Y")
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q
            cam.location, cam.rotation_quaternion = pos, q
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_quaternion", frame=f)
    for sid in SCENES:
        data.lens = LENS[sid]
        data.keyframe_insert("lens", frame=tl.at(sid))
    vl.constant(data, ("lens",))
    a7, b7 = tl.scenes["07"]                      # 07: slow zoom at the end, follows the tilt to the village
    f_z = a7 + int(0.72 * (b7 - 1 - a7))
    data.lens = LENS["07"]
    data.keyframe_insert("lens", frame=f_z)
    data.lens = 19
    data.keyframe_insert("lens", frame=b7 - 1)
    for fc in rigs._fcurves(data.animation_data.action):
        for kp in fc.keyframe_points:
            if int(kp.co.x) == f_z:
                kp.interpolation = "LINEAR"
    starts = {tl.at(s) for s in SCENES}
    for fc in rigs._fcurves(cam.animation_data.action):
        if fc.data_path in ("location", "rotation_quaternion"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if (kp.co.x + 1) in starts else "LINEAR"
    return cam


# ---------- crowd points ----------

def spots(rnd, n, box, avoid=()):
    avoid = [*avoid, (*vw.FOUNTAIN, 3.2)]          # the square fountain
    out = []
    while len(out) < n:
        x, y = rnd.uniform(box[0], box[1]), rnd.uniform(box[2], box[3])
        if any((x - ax) ** 2 + (y - ay) ** 2 < ar * ar for ax, ay, ar in avoid):
            continue
        out.append((x, y))
    return out


def bank(x, side, off=9.3):
    """Point on the bank (side -1 = south, +1 = north), on the trail line."""
    return (x, vw.yc(x) + side * off)


def on_ground(objs):
    for o in objs:
        x, y = o.location.x, o.location.y
        o.location.z = vw.DECK_Z if abs(x - vw.BRIDGE_X) < 1.7 and abs(y - vw.yc(vw.BRIDGE_X)) < 10.4             else max(vw.height(x, y), 0.0)


# ---------- lanternas ----------

def lantern_set(name, points, mesh, streak=None):
    """Lanterns (scale 0 until they light up). streak: reflection mesh flattened on the water, child of the lantern (only below 5 m)."""
    out, kids = [], []
    for k, (x, y, z) in enumerate(points):
        o = vl.obj_of(f"{name}{k}", mesh, (x, y, z), (0, 0, 0), (0.0, 0.0, 0.0))
        o.visible_shadow = False
        out.append(o)
        if streak is not None and z < 5.0:
            c = vl.obj_of(f"{name}{k}Streak", streak, (0, 0, -(z + 0.37)), (0, 0, 0), (1, 1, 1))
            c.parent = o
            c.visible_shadow = False
            kids.append(c)
    return out, kids


def lantern_on(o, f, frames=5, s=1.0):
    o.scale = (0, 0, 0)
    o.keyframe_insert("scale", frame=1)
    o.keyframe_insert("scale", frame=f)
    o.scale = (s, s, s)
    o.keyframe_insert("scale", frame=f + frames)


def lantern_off(o, f, frames=5):
    o.keyframe_insert("scale", frame=max(f - 1, 1))
    o.scale = (0, 0, 0)
    o.keyframe_insert("scale", frame=f + frames)


def block_points(rnd, n, cols, x0, x1, z0, z1):
    """n lanterns in a rectangular block (cols columns) over the water: the block is an x-z wall of shallow depth."""
    rows = -(-n // cols)
    pts = []
    for r in range(rows):
        for c in range(cols):
            if len(pts) >= n:
                break
            x = x0 + (x1 - x0) * c / (cols - 1) + rnd.uniform(-0.12, 0.12)
            z = z0 + (z1 - z0) * r / max(rows - 1, 1) + rnd.uniform(-0.12, 0.12)
            pts.append((x, vw.yc(x) + rnd.uniform(-1.0, 1.0), z))
    return pts


def cloud_points(rnd, n, box, sep=0.9):
    """n loose points (no grid) in a box (x0, x1, y0, y1, z0, z1), separated by >= sep m."""
    x0, x1, y0, y1, z0, z1 = box
    pts = []
    for _ in range(20000):
        if len(pts) >= n:
            break
        p = (rnd.uniform(x0, x1), rnd.uniform(y0, y1), z0 + (z1 - z0) * rnd.random() ** 0.8)
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 > sep * sep for q in pts):
            pts.append(p)
    return pts


def drift(o, f0, f1, rise, rnd, step=4):
    """Paper lantern rising slowly (rise m/s) with slow lateral sway: LINEAR keys every 4 frames."""
    x, y, z = o.location
    ph, amp = rnd.uniform(0, 6.28), rnd.uniform(0.08, 0.2)
    for f in range(f0, f1 + 1, step):
        t = (f - f0) / 30.0
        o.location = (x + amp * math.sin(t * 0.7 + ph), y + 0.5 * amp * math.cos(t * 0.5 + ph), z + rise * t)
        o.keyframe_insert("location", frame=f)


def river_lanterns(rnd, n, x0, x1):
    """Lanterns over the river, in a group: low (0.8 to 6 m), denser near the water; y from -6 to 6 around the river."""
    pts = []
    for _ in range(n):
        x = rnd.uniform(x0, x1)
        y = vw.yc(x) + rnd.uniform(-6.5, 6.5)
        z = 0.8 + 5.4 * rnd.random() ** 2
        pts.append((x, y, z))
    return pts


def arch(n, cx, y, radius, zc):
    """n lanterns in a symmetric arc (two rows) on a constant y plane; returns points ordered from the ends to the top."""
    half = n // 2
    pts = []
    for row, r in enumerate((radius, radius * 1.1)):
        for k in range(half):
            th = math.radians(8 + 164 * (k + 0.5 * row) / (half - 0.5))
            pts.append((cx + r * math.cos(th), y + row * 1.5, zc + r * math.sin(th), abs(th - math.pi / 2)))
    pts.sort(key=lambda p: -p[3])
    return [p[:3] for p in pts]


# ---------- build ----------

def build(tl):
    rnd = random.Random(42)
    w = sky.build_world()
    stars = sky.star_field(center=(0, 0, 0))
    terrain = vw.terrain()
    water = vw.water()
    bridge = vw.bridge()
    mts = vw.mountains(random.Random(3))
    trl = vw.trails()
    cover = vw.ground_cover(random.Random(11))
    trees = vw.trees(random.Random(5), 140)
    lane = vw.plaza_and_lane()
    houses_a = vw.village(vw.VILLAGE_A, gable=True)
    houses_b = vw.village(vw.VILLAGE_B, gable=True)
    huts = vw.village(vw.HUTS)
    cabin = vh.house("cabin", vw.CABIN[1], vw.CABIN[2], math.radians(vw.CABIN[3]), 2, 2, mode="cabin")
    far = vw.far_roofs()
    grass = vw.grass_carpet(houses=[(h.pos[0], h.pos[1], max(h.size) / 2 + 0.9) for h in houses_a + houses_b + huts]
                            + [(vw.CABIN[1], vw.CABIN[2], 3.4)],
                            keep_out=[(*vw.FOUNTAIN, 2.6)])
    for o in (terrain, water, trl):
        o.visible_shadow = False
    interior, books = vw.cabin_interior(cabin)
    mill = vw.windmill(-31, 62)
    barn = vh.house("barn", -27.0, 50.0, math.radians(180), 4, 3, windows=False)
    barn2 = vh.house("barn2", 36.0, 54.0, math.radians(180), 3, 3, windows=False)
    mill += barn.objs + barn2.objs
    mill += vl.place(vl.town("cart"), (6.6, 21.5, 0.0), math.radians(100), 1.5, name="Cart")
    mill += vl.place(vl.town("stall"), (-2.3, 30.0, 0.0), math.radians(90), 1.6, name="Stall")
    mill += vl.place(vl.town("stall-bench"), (11.5, 27.5, 0.0), math.radians(-90), 1.6, name="StallB")
    lane_fence = vw.fence(0.6, 12.5, 0.6, 23.0, 2.0) + vw.fence(7.4, 12.5, 7.4, 19.5, 2.0)
    mill += lane_fence
    tops = vw.chimneys(houses_a + houses_b, 10, random.Random(9))
    garden0, garden1 = vw.garden(rnd, 0), vw.garden(rnd, 1)
    fence = vw.fence(-11.0, -22.5, -2.5, -22.5) + vw.fence(-2.5, -22.5, -2.5, -17.0)
    post, (post_lines, post_hot) = vw.carved_post(*POST)
    bpy.context.view_layer.update()
    from mathutils import Matrix
    pv_ = Vector((*POST, 0.0))
    th = math.atan2(CAM05[1] - POST[1], CAM05[0] - POST[0])
    rot_ = Matrix.Translation(pv_) @ Matrix.Rotation(th, 4, "Z") @ Matrix.Translation(-pv_)
    for o_ in post:
        o_.matrix_world = rot_ @ o_.matrix_world
    fire5, f5_sock, f5_light, _, _ = vw.fire(*FIRE5, ring=0.75, f0=tl.at("05") - 2, f1=tl.at("05", 1.0) + 2, seed=5)
    f_q = W(tl, "11", "what", off=-0.1)
    fe = tl.at("11", 1.0) - 1
    fire11, f11_sock, f11_light, f11_ember, f11_tongues = vw.fire(3.4, 24.0, 1.1, f0=tl.at("11") - 2,
                                                                  f1=tl.at("11", 1.0) + 2, seed=11,
                                                                  fade=(f_q, fe - 10))
    cam = build_camera(tl)
    lights(w, tl)
    sky_detail(w, stars, tl)
    vl.constant(w.world.node_tree)               # sky_detail set LINEAR on the same action: the sky only changes on the cut
    lantern_me, lantern_mat, _ = vw.lantern_mesh(0.2)
    kit.principled(lantern_mat).inputs["Emission Strength"].default_value = 1.4
    streak_mat = vl.mat("Streak", "#3A2A18", emission="#F5A524", strength=0.7)
    streak_me = vl.mesh_from_geo("Streak", kit._ico_geo(0.3, (0, 0, 0), (1.0, 3.2, 0.05)), streak_mat)
    houses = houses_a + houses_b + huts + [cabin]
    house_keys = {h.name: Keyed(h.power, "default_value", 0.0) for h in houses if h.power is not None}

    # --- window states (cuts) ---
    for h in houses_a:                               # 01: vila cheia, janelas acesas
        house_keys[h.name].cut(1, LIT)
    house_keys["cabin"].cut(1, LIT)
    house_keys["cabin"].cut(tl.at("03"), 0.0)
    house_keys["cabin"].cut(tl.at("05"), LIT)
    for h in huts:
        house_keys[h.name].cut(tl.at("06"), LIT)
    for sid, names in {"03": [], "04": [], "05": ["a2"], "06": ["a1", "a3", "a5", "a8", "a4"],
                       "07": ["a1", "a3", "a5", "a8", "a4"]}.items():
        for h in houses_a:
            house_keys[h.name].cut(tl.at(sid), LIT if h.name in names else 0.0)
    for h in houses_a:
        house_keys[h.name].cut(tl.at("08"), LIT)
    for h in houses_b:
        house_keys[h.name].cut(tl.at("08"), 0.0)
    for h in houses_b:                               # 08: on 'town' the whole village lights up
        house_keys[h.name].to(W(tl, "08", "town", off=0.1), W(tl, "08", "town", off=0.28), LIT)
    for h in houses_a + houses_b:
        house_keys[h.name].cut(tl.at("09"), LIT)
    f30 = W(tl, "07", "thirty", off=-0.2)            # 07: on 'Thirty' more houses light up (30 windows)
    for h in houses_a:
        if h.name in ("a2", "a6", "a7", "a9", "a11", "a12", "a10", "a13", "a14"):
            house_keys[h.name].to(f30, f30 + 6, LIT)

    # --- 01/02: crowd (35: 8 mid-shot with sway + 27 static background) and couple ---
    f_van = W(tl, "02", "vanish")
    cam01, bear01 = (-5.5, -14.4), math.radians(62)

    def in_view(x, y, half=27):
        a_ = math.atan2(y - cam01[1], x - cam01[0])
        return abs((a_ - bear01 + math.pi) % (2 * math.pi) - math.pi) < math.radians(half)

    def view_spots(n, box, avoid=(), half=26, sep=1.5, min_d=8.0):
        out_ = []
        for _try in range(4000):
            if len(out_) >= n:
                break
            x, y = rnd.uniform(box[0], box[1]), rnd.uniform(box[2], box[3])
            if not in_view(x, y, half) or any((x - ax) ** 2 + (y - ay) ** 2 < ar * ar for ax, ay, ar in avoid):
                continue
            if min_d and math.hypot(x - cam01[0], y - cam01[1]) < min_d:
                continue
            if abs(y - vw.yc(x)) < 8.4 and not (abs(x - vw.BRIDGE_X) < 1.4):
                continue
            if abs(x - vw.BRIDGE_X) < 2.2 and abs(y - vw.yc(x)) < 11.5:      # bridge corridor: free for whoever walks
                continue
            if any((x - qx) ** 2 + (y - qy) ** 2 < sep * sep for qx, qy in out_):
                continue
            out_.append((x, y))
        return out_

    keep = [(*MAN1, 1.6), (*WOM1, 1.6)]
    mid_spots = view_spots(6, (-4.0, 6.0, -10.0, -8.8), keep + [(*vw.FOUNTAIN, 3.2)])
    mid1 = cast.crowd("C1m_", mid_spots, rnd)
    on_ground(mid1)
    wspec = [(3.5, -7.0, math.pi / 2, 1.15), (4.45, 6.5, -math.pi / 2, 1.05), (3.55, -2.5, math.pi / 2, 1.2),
             (4.5, 8.8, -math.pi / 2, 1.1), (3.6, 2.0, math.pi / 2, 1.0)]
    walk_rigs = cast.walkers(wspec, 1, f_van + 40, rnd, z=vw.DECK_Z)
    walk1 = [r_.root for r_ in walk_rigs]
    walk_pos = {r_.root.name: (Vector((x_, y_, vw.DECK_Z)), Vector((math.cos(h_), math.sin(h_), 0)) * v_)
                for r_, (x_, y_, h_, v_) in zip(walk_rigs, wspec)}
    for o in mid1:
        o.rotation_euler.z = rnd.choice((0.3, 2.0, 3.4, 4.6))
    bg_spots = (view_spots(11, (-14, 24, 10.0, 12.6), keep, 40) + view_spots(10, (-12, 30, 12.6, 24.0), keep, 40, 2.0) + view_spots(8, (-4, 14, 14, 30), keep, 40)
                + view_spots(5, (2, 14, -9.0, -6.0), keep + [(*vw.FOUNTAIN, 3.2)], 40) + [(6.6, -9.4)])
    bg1 = cast.crowd("C1b_", bg_spots, rnd)
    on_ground(bg1)
    boats = []
    rowers = []
    for k, (bx, by) in enumerate(((-2.0, -2.6), (-7.0, -4.0), (-5.0, -5.8))):
        boats += vl.place(vl.nature("canoe", True), (bx, by, -0.35), math.radians(8 * k - 15), 3.4, name=f"Canoe{k}")
        rowers.append(cast.figure(f"Rower{k}", bx, by, 0.5, 1.5, k + 2, z=-0.35))
    crowd1 = mid1 + walk1 + rowers + bg1
    cast.sway(mid1 + rowers, 1, f_van, rnd)
    cam0 = Vector((-5.5, -14.4, 0.0))
    amber = vl.mat("Spark", "#F5A524", emission="#F5A524", strength=6.0)
    gem_me = vl.mesh_from_geo("SparkGem", kit._gem_geo(0.07), amber)
    sparks = []
    for o in crowd1:                                  # vanishing in waves from the background to the foreground, with sparks
        dist = (Vector((o.location.x, o.location.y, 0)) - cam0).length
        band = 3 - min(3, int(dist / 22))
        fv = f_van + band * 7 + rnd.randint(0, 3)
        loc0 = Vector(o.location)
        if o.name in walk_pos:
            p0, vel = walk_pos[o.name]
            loc0 = p0 + vel * (fv - 1) / 30.0
        o.keyframe_insert("scale", frame=max(fv - 1, 1))
        o.scale = (0, 0, 0)
        o.keyframe_insert("scale", frame=fv + 3)
        for k in range(2):
            sp = vl.obj_of(f"Spark{o.name}{k}", gem_me, (loc0.x, loc0.y, loc0.z + 1.0 + 0.4 * k),
                           (0, 0, 0), (0, 0, 0))
            sp.visible_shadow = False
            sp.scale = (0, 0, 0)
            sp.keyframe_insert("scale", frame=1)
            sp.keyframe_insert("scale", frame=fv)
            sp.scale = (1.3, 1.3, 1.3)
            sp.keyframe_insert("scale", frame=fv + 5)
            sp.keyframe_insert("location", frame=fv + 5)
            sp.location.z += 0.9 + 0.5 * k
            sp.scale = (0, 0, 0)
            sp.keyframe_insert("scale", frame=fv + 22)
            sp.keyframe_insert("location", frame=fv + 22)
            sparks.append(sp)
    for h in houses_a:                                # windows go out with the wave (farther houses first)
        d = math.hypot(h.pos[0] - cam0.x, h.pos[1] - cam0.y)
        fv = f_van + (3 - min(3, int(d / 22))) * 7
        house_keys[h.name].to(max(fv, tl.at("02")), max(fv, tl.at("02")) + 4, 0.0)
    man1 = cast.adult("man", "Man1", *MAN1, math.radians(80), tl.frames, 1)
    wom1 = cast.adult("woman", "Wom1", *WOM1, math.radians(80), tl.frames, 2)
    f_rem = W(tl, "02", "remain", off=-0.1)
    f_met = W(tl, "02", "met")
    ang_mw = math.atan2(WOM1[1] - MAN1[1], WOM1[0] - MAN1[0])
    cast.turn_to(man1, f_rem, f_rem + 26, ang_mw)                  # they turn toward each other
    cast.turn_to(wom1, f_rem + 3, f_rem + 33, ang_mw + math.pi)
    for r_ in (man1, wom1):
        r_.arm.location.z += 0.045 / r_.root.scale.z          # feet on the trail (dirt ribbon 4 cm above the ground)
    cast.step_to(man1, f_met - 14, f_met + 18, MAN1, ang_mw, 0.45)
    rim = []
    for k, (lx, ly) in enumerate(((-3.6, -6.8), (0.7, -6.8))):     # amber rim light, from behind the couple
        ld = bpy.data.lights.new(f"Rim{k}", "POINT")
        ld.color, ld.energy, ld.shadow_soft_size, ld.use_shadow = (1.0, 0.6, 0.22), 700.0, 0.4, False
        lo = bpy.data.objects.new(f"Rim{k}", ld)
        bpy.context.collection.objects.link(lo)
        lo.location = (lx, ly, 2.3)
        rim.append(lo)

    # --- 03: livros ---
    f_four = W(tl, "03", "four")
    book_keys = []
    for i, (b, sock) in enumerate(books):
        k = Keyed(sock, "default_value", 0.0)
        k.to(f_four + i * 9, f_four + i * 9 + 5, 1.2)
        book_keys.append(k)
    in_lamp = bpy.data.lights.new("InLamp", "SPOT")
    in_lamp.energy, in_lamp.color, in_lamp.shadow_soft_size, in_lamp.use_shadow = 300.0, (1.0, 0.72, 0.4), 0.3, False
    in_lamp.spot_size, in_lamp.spot_blend = math.radians(100), 0.8
    in_obj = bpy.data.objects.new("InLamp", in_lamp)
    bpy.context.collection.objects.link(in_obj)
    in_obj.location = (-12.9, -16.0, 1.5)
    in_obj.rotation_euler = (Vector((-12.0, -12.9, 1.0)) - Vector(in_obj.location)).to_track_quat("-Z", "Y").to_euler()

    # --- 04: couple seated on the bench with the baby ---
    bench = vl.mat("Bench", "#4A3424")
    bx, by = BENCH
    bv, bf = kit._box_geo(1.7, 0.42, 0.06, -0.85, -0.21, 0.36)            # seat 0.42 m: the thighs of the Sitting go on top
    legs = [kit._box_geo(0.1, 0.36, 0.36, sx_ * 0.7 - 0.05, -0.18, 0.0) for sx_ in (-1, 1)]
    legs.append(kit._box_geo(1.4, 0.06, 0.08, -0.7, -0.03, 0.12))                 # crosspiece between the feet
    bn = kit.mesh_object("Bench", *kit.merge((bv, bf), *legs)[:2], [bench], (bx, by, 0))
    bn.rotation_euler.z = math.radians(SIT_HEAD) - math.pi / 2
    ux, uy = -math.sin(math.radians(SIT_HEAD)), math.cos(math.radians(SIT_HEAD))
    fx4, fy4 = SIT_FWD * math.cos(math.radians(SIT_HEAD)), SIT_FWD * math.sin(math.radians(SIT_HEAD))
    wom4 = cast.adult_sit("woman", "Wom4", bx - 0.36 * ux + fx4, by - 0.36 * uy + fy4, math.radians(SIT_HEAD), tl.frames)
    man4 = cast.adult_sit("man", "Man4", bx + 0.30 * ux + fx4, by + 0.30 * uy + fy4, math.radians(SIT_HEAD), tl.frames)
    baby, baby_glow, baby_arm, baby_parts = cast.baby(wom4)
    cast.hold_baby(wom4, baby)
    cast.touch_baby(man4, baby)
    bn.location.z += 0.045                                # bench on the trail (ribbon 4 cm above the ground)
    for o_ in (wom4.root, man4.root):                     # couple: +SIT_LIFT so the thighs end up ON TOP of the seat
        o_.location.z += 0.045 + SIT_LIFT
    f_baby = W(tl, "04", "baby")
    r0 = tuple(baby_arm.rotation_euler)
    for i in range(-6, 75, 3):                        # on 'baby' the little hand moves (arm rotates at the shoulder, 2.5 s)
        env = math.sin(math.pi * min(max(i / 72, 0.0), 1.0))
        baby_arm.rotation_euler = (r0[0] + math.radians(28) * env * math.sin(i * 0.28), r0[1],
                                   r0[2] + math.radians(18) * env * math.sin(i * 0.19 + 1.0))
        baby_arm.keyframe_insert("rotation_euler", frame=f_baby + i)
    vl.linear(baby_arm)
    f_h = W(tl, "04", "healthy")
    gk = Keyed(baby_glow, "energy", 0.0)
    gk.to(f_h, f_h + 6, 9.0)
    mid4 = cast.crowd("P4_", [bank(-6, 1, 10.8), bank(3.0, 1, 11.0), bank(14.0, 1, 11.0), bank(24, 1, 11),
                              (4.1, 12.0), (3.2, 18.0)], rnd)
    on_ground(mid4)

    # --- 05: pole and family (couple + 6 children) ---
    lines_k = Keyed(post_lines, "default_value", 0.0)
    lines_k.to(W(tl, "05", "their"), W(tl, "05", "their") + 24, 4.0)
    hot_k = Keyed(post_hot, "default_value", 0.0)
    f_both = W(tl, "05", "both")
    hot_k.to(f_both - 4, f_both + 4, 22.0)
    fx, fy = FIRE5

    def ring(deg, r):
        a_ = math.radians(deg)
        return fx + r * math.cos(a_), fy + r * math.sin(a_), a_ + math.pi          # gaze direction: toward the bonfire

    def bearing5(x_, y_):
        return math.degrees(math.atan2(y_ - CAM05[1], x_ - CAM05[0]))

    # family outside the panel (x < 520 in the frame = bearing > 46 degrees) and the buttons (bearing < 22 degrees): only the arc there
    wx, wy, wa = ring(95, 2.0)
    mx, my, ma = ring(60, 1.8)
    wom5 = cast.adult("woman", "Wom5", wx, wy, wa, tl.frames, 2)
    man5 = cast.adult("man", "Man5", mx, my, ma, tl.frames, 1)
    wom5.root.location.z = max(vw.height(wx, wy), 0.0) + 0.045
    man5.root.location.z = max(vw.height(mx, my), 0.0) + 0.045
    kids = []
    for k, (deg, r, hgt) in enumerate(((25, 2.5, 1.3), (-5, 1.6, 0.95), (15, 1.5, 1.42), (35, 1.7, 0.85), (78, 1.75, 1.1))):    # 5 children: those at 115-150 degrees stacked behind the pole (round 5)
        x_, y_, a_ = ring(deg, r)
        assert 21.0 < bearing5(x_, y_) < 47.0, (k, bearing5(x_, y_))
        kids.append(cast.figure(f"Kid{k}", x_, y_, a_ - math.pi / 2, hgt, k + 1, z=max(vw.height(x_, y_), 0.0)))
    cast.sway(kids, tl.at("05"), tl.at("05", 1.0), rnd)
    pop5 = cast.crowd("P5_", [(-7.5, -20.1), (-5.3, -21.9)], rnd)
    on_ground(pop5)

    # --- 06: ~15 pessoas ---
    mid6 = cast.crowd("P6m_", [(0.5, -30.0), (5.5, -30.5), (-4.5, -31.0), (2.5, -25.0), (7.0, -23.0), (-10.0, -26.0),
                               (-16.0, -21.0), (4.0, -4.0)], rnd)
    bg6 = cast.crowd("P6b_", [bank(-20, 1, 10.8), bank(-6, 1, 10.8), bank(18, 1, 11), bank(33, 1, 11),
                              (4.0, 17.0), (2.5, 27.0), (-26.5, -15.0)], rnd)
    on_ground(mid6 + bg6)
    cast.sway(mid6, tl.at("06"), tl.at("06", 1.0), rnd)

    # --- 07: lanterns over the river (98 on the right, 32 on the left) with reflection ---
    l7_me, l7_mat, _ = vw.lantern_mesh(0.3)
    kit.principled(l7_mat).inputs["Emission Strength"].default_value = 1.6
    r7 = random.Random(707)
    A98, k98 = lantern_set("L98_", cloud_points(r7, 98, (3.0, 11.0, 0.0, 7.0, 6.5, 15.5), 1.0), l7_me)
    A32, k32 = lantern_set("L32_", cloud_points(r7, 32, (-11.0, -3.0, -3.0, 6.0, 13.0, 19.0), 1.1), l7_me)
    f98 = W(tl, "07", "98")
    f32 = W(tl, "07", "fewer")
    a7_, b7_ = tl.scenes["07"]
    for o in A98 + A32:
        drift(o, a7_, b7_, 0.12, r7)
        vl.linear(o)
    for i, o in enumerate(A98):
        lantern_on(o, f98 + i // 4 - 6, 5)
    for i, o in enumerate(A32):
        lantern_on(o, f32 - 20 + i // 3, 5)
    f_off0 = W(tl, "07", "fail") - 6
    order = list(range(len(A32)))
    r7.shuffle(order)
    for n_, i in enumerate(order):                    # go out one by one, in random order
        lantern_off(A32[i], f_off0 + n_ * 2, 4)
    for o in A32 + A98:
        vl.linear(o)
    bg7 = cast.crowd("P7_", [(4.6, -12.6), (5.9, -12.2), (7.2, -12.8), (8.6, -12.0), (9.9, -12.5), (11.2, -12.8),
                             bank(-30, 1, 10.8), bank(20, 1, 11)], rnd)
    on_ground(bg7)
    cast.sway(bg7[:6], tl.at("07"), tl.at("07", 1.0), rnd)
    for o in bg7[:6]:
        o.rotation_euler.z = 0.0

    # --- 08: 300-year village (25: 8 mid-shot in the alley + 17 background) ---
    mid8 = cast.crowd("P8m_", [(2.0, 20.5), (6.4, 19.0), (2.2, 25.0), (6.2, 24.0), (1.2, 30.0), (7.0, 28.0),
                               (4.0, 36.0), (6.5, 40.0)], rnd)
    bg8 = cast.crowd("P8b_", spots(rnd, 9, (-7, 14, 25.5, 38)) + spots(rnd, 4, (-45, 60, 44, 80)) +
                     [bank(-10, 1, 11), bank(20, 1, 11), (-12.0, 22), (13.0, 36)], rnd)
    on_ground(mid8 + bg8)
    cast.sway(mid8, tl.at("08"), tl.at("08", 1.0), rnd)
    # --- 09: 64 lanterns in the alley and on the bridge ---
    pole_mat = vl.mat("Pole", "#4A3A2C")
    ys = [-9.0 + 1.75 * k for k in range(32)]
    pts = []
    for y in ys:
        for sx in (-3.4, 3.4):
            pts.append((vw.LANE_X + sx * (0.5 if y < 8 else 1.0), y, 2.3 if y > 8 else vw.DECK_Z + 1.6))
    pv = []
    for (x, y, z) in pts:
        pv.append(kit._box_geo(0.08, 0.08, z - (0.0 if y > 8 else vw.DECK_Z), x - 0.04, y - 0.04,
                               0.0 if y > 8 else vw.DECK_Z))
    pole_obj = kit.mesh_object("Poles", *kit.merge(*pv)[:2], [pole_mat])
    B64, _ = lantern_set("L64_", pts, lantern_me)
    f64 = W(tl, "09", "64", off=-0.2)
    for i, o in enumerate(B64):
        lantern_on(o, f64 + i * 2, 5, 1.3)
    pop9 = cast.crowd("P9_", [(2.6, 14.0), (5.6, 22.0), (1.0, 29.0), (7.0, 33.0)] +
                      spots(rnd, 7, (-7, 14, 25.5, 38)) + [bank(-14, 1, 11), bank(22, 1, 11)], rnd)
    on_ground(pop9)
    cast.sway(pop9[:4], tl.at("09"), tl.at("09", 1.0), rnd)
    # --- 10: 98 lanterns in a symmetric arc over the village ---
    C98, _ = lantern_set("L98b_", arch(98, 4.0, 48.0, 13.0, 6.0), lantern_me)
    f_ab = W(tl, "10", "about", off=-0.1)
    for i, o in enumerate(C98):
        lantern_on(o, f_ab + i // 4, 5, 1.3)
    pop10 = cast.crowd("P10_", spots(rnd, 6, (-7, 14, 25.5, 38)) + [(2.7, 18.0), (5.5, 12.0)], rnd)
    on_ground(pop10)
    # --- 11: village at night, bonfire (12) ---
    pop11 = cast.crowd("P11_", [(3.4 + 2.5 * math.cos(a), 24.0 + 2.5 * math.sin(a)) for a in
                                [k * 2 * math.pi / 8 for k in range(8) if k != 6]] + spots(rnd, 5, (-7, 14, 27, 38)), rnd)
    on_ground(pop11)
    for o in pop11[:7]:
        o.rotation_euler.z = math.atan2(24.0 - o.location.y, 3.4 - o.location.x) - math.pi / 2
    cast.sway(pop11[:7], tl.at("11"), tl.at("11", 1.0), rnd)
    # final pause: windows dim, the flame goes out and the ember stays on the ground
    for h in houses_a + houses_b:
        house_keys[h.name].to(f_q, fe, 0.5)
    fk = Keyed(f11_sock, "default_value", 8.0)
    fk.to(f_q, fe, 0.0)
    fl = Keyed(f11_light, "energy", 260.0 * 1.1)
    fl.to(f_q, fe, 10.0)
    em = Keyed(f11_ember, "default_value", 2.5)
    em.to(f_q, fe, 1.6)
    # smoke from the chimneys (08 to 11)
    smoke = vw.smoke(tops, tl.at("08"), tl.at("11", 1.0),
                     [(tl.at("08"), "#8A90A2"), (tl.at("09"), "#6E7896"), (tl.at("10"), "#2E3A58"),
                      (tl.at("11"), "#2E3A58")])

    u5, r5 = (math.cos(math.radians(44)), math.sin(math.radians(44))), (math.sin(math.radians(44)), -math.cos(math.radians(44)))

    def in_cone5(o):
        dx, dy = o.location.x - CAM05[0], o.location.y - CAM05[1]
        fwd, lat = dx * u5[0] + dy * u5[1], dx * r5[0] + dy * r5[1]
        return (0 < fwd < 9.0 and abs(lat) < 0.55 * fwd + 1.2) or math.hypot(dx, dy) < 2.5
    near05 = [o for o in cover if (o.name.startswith(("Cover", "Bush", "Reed")) and in_cone5(o)) or
              math.hypot(o.location.x - FIRE5[0], o.location.y - FIRE5[1]) < 3.2]
    fg5 = []
    flw = [vl.nature(n, "plant") for n in ("flower_redA", "flower_yellowA", "flower_purpleA", "flower_yellowC", "flower_purpleC")]
    rks = [vl.nature(n, "stone") for n in ("rock_smallA", "stone_largeA", "rock_smallC")]
    tuft = vl.nature("grass", "green")
    rr = random.Random(77)
    for k in range(36):
        d_ = rr.uniform(1.8, 5.5)
        l_ = rr.uniform(-1.0, 1.0) * (0.4 + 0.5 * d_)
        l_ = l_ - 1.0 if l_ < 0 else l_ + 3.2
        x_, y_ = CAM05[0] + d_ * u5[0] + l_ * r5[0], CAM05[1] + d_ * u5[1] + l_ * r5[1]
        z_ = vw.height(x_, y_)
        if k % 3 == 0:
            fg5 += vl.place(rks[k % 3], (x_, y_, z_ - 0.04), rr.uniform(0, 6.28), rr.uniform(0.45, 0.8), name="FG")
        else:
            fg5 += vl.place(tuft, (x_, y_, z_ - 0.02), rr.uniform(0, 6.28), rr.uniform(0.8, 1.2), name="FG")
    # --- apply keys and visibility ---
    for k in list(house_keys.values()) + book_keys + [lines_k, hot_k, gk, fk, fl, em]:
        k.apply()
    allc = SCENES

    def show(objs, scenes):
        vl.vis(objs, scenes, tl, allc)

    def rig_objs(r):
        return rigs.all_objects(r)

    show([stars[0]], ("07", "10", "11"))
    show([o for h in houses_b for o in h.objs] + mill, ("08", "09", "10", "11"))
    show([o for h in huts for o in h.objs], ("06", "07", "08", "09", "10", "11"))
    show(garden0, ("04",))
    show(garden1, ("05", "06", "07", "08", "09", "10", "11"))
    show(fence, ("05", "06", "07", "08", "09", "10", "11"))
    show(post + fg5, ("05",))
    show(near05, tuple(s for s in SCENES if s != "05"))
    show(fire5, ("05",))
    show(fire11, ("11",))
    show(crowd1 + sparks + boats + rim, ("01", "02"))
    show([o for r_ in walk_rigs for o in rigs.all_objects(r_)], ("01", "02"))
    show(cabin.panes, tuple(s_ for s_ in SCENES if s_ != "03"))
    show(rig_objs(man1) + rig_objs(wom1), ("01", "02"))
    show([bn] + rig_objs(wom4) + rig_objs(man4) + baby_parts + mid4, ("04",))
    show(rig_objs(wom5) + rig_objs(man5) + kids + pop5, ("05",))
    show(mid6 + bg6, ("06",))
    show(A98 + A32 + k98 + k32 + bg7, ("07",))
    show(mid8 + bg8, ("08",))
    show(B64 + [pole_obj] + pop9, ("09",))
    show(C98 + pop10, ("10",))
    show(pop11, ("11",))
    show(smoke, ("08", "09", "10", "11"))
    show([in_obj], ("03",))
    return cam


kit.run(build)
