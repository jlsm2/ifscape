"""Animation for the technology-disappeared script: a main street of a small American town, a year without technology.

Run by 'python -m ifscape blender scripts/technology-disappeared.json'. Eye-level POV (1.65 m).
01-03: one continuous take on the sidewalk (phone in hand, cars at the light, everything vanishes); 04-05: cut to night and the
camera rises to the sky; 06 kitchen; 07 grocery; 08 street by day; 09 the street became a vegetable garden; 10 water tower hill;
11 the flaked stone in the hand; 12 the fire. The light only changes on cuts (no flickering sky).
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import cell_models as cm  # noqa: E402
import kit  # noqa: E402
import town_cast as tc  # noqa: E402
import town_far as tf  # noqa: E402
import town_farm as tfarm  # noqa: E402
import town_interiors as ti  # noqa: E402
import town_scenes as sc  # noqa: E402
import town_fx as fx  # noqa: E402
import town_set as ts  # noqa: E402
import town_sky as sky  # noqa: E402
from kit import key  # noqa: E402

EYE = 1.65
WALK_Z = 0.15 + EYE                  # eyes on the sidewalk
SCENES = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
VANISH_02 = 2.86                     # s in scene 02: "vanishes" (the phone dissolves)
VANISH_03 = 1.0                      # s in scene 03: "vanish" (the cars vanish)
LIGHTS_03 = (1.75, 4.55)             # s in scene 03: "Every streetlight goes dark" (one by one, near -> far, ~2.8 s)

# Light states (they only change on the cut; CONSTANT keys on the 1st frame of each scene)
DUSK = dict(sky="dusk", sun=1.6, ambient=1.5, amb="#3A5285", rot=(86, 0, -75), color=(1.0, 0.62, 0.38), band=0.0,
            stars=0.0, reveal=0.0)
NIGHT = dict(sky="night", sun=0.7, ambient=2.7, amb="#33497A", rot=(55, 0, -30), color=(0.62, 0.72, 1.0), band=0.32,
             stars=5.0, reveal=1.2)
DAY = dict(sky="day", sun=3.6, ambient=1.6, amb="#7F95B8", rot=(42, 0, 135), color=(1.0, 0.95, 0.88), band=0.0,
           stars=0.0, reveal=0.0)
SUNSET = dict(sky="sunset", sun=2.6, ambient=1.5, amb="#5A6A95", rot=(82, 0, -95), color=(1.0, 0.6, 0.36), band=0.0,
              stars=0.0, reveal=0.0)
NIGHTFALL = dict(sky="nightfall", sun=0.9, ambient=1.2, amb="#34497A", rot=(84, 0, -90), color=(1.0, 0.55, 0.32),
                 band=0.0, stars=3.0, reveal=0.35)
DAY_IN = dict(DAY, ambient=0.6, sun=2.6, sky_s=0.6)   # window without blowout: sky and sun lower outside    # indoors: the world ambient is not blocked by the walls in Eevee
LIGHT = {"01": DUSK, "02": DUSK, "03": DUSK, "04": NIGHT, "05": NIGHT, "06": DAY_IN, "07": DAY_IN, "08": DAY, "09": DAY,
         "10": SUNSET, "11": NIGHTFALL, "12": NIGHT}


# ---------- utilidades ----------

def constant(owner, paths=None):
    ad = getattr(owner, "animation_data", None)
    if ad is None or ad.action is None:
        return
    for fc in tc.rigs._fcurves(ad.action):
        if paths and fc.data_path not in paths:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def visible(objs, scenes, tl):
    """On/off per scene (hide_render only on the cut, CONSTANT keys)."""
    for o in objs:
        for sid in SCENES:
            o.hide_render = sid not in scenes
            o.keyframe_insert("hide_render", frame=tl.at(sid))
        constant(o, ("hide_render",))


def all_children(root):
    return [root, *root.children_recursive]


def scene_of(tl, f):
    for sid in SCENES:
        a, b = tl.scenes[sid]
        if a <= f < b:
            return sid
    return SCENES[-1]


def secs(tl, sid, s):
    return tl.at(sid) + tl.secs(s)


# ---------- light ----------

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
        constant(owner)


def held(sock, tl, values, ramps=None):
    """Value per scene, held from the 1st to the last frame of the scene (the switch falls between two frames: on the cut).
    ramps: {scene: [(fraction, value), ...]} to rise slowly within the scene (stars appearing)."""
    for sid in SCENES:
        a, b = tl.at(sid), tl.at(sid, 1.0) - 1
        pts = (ramps or {}).get(sid) or [(0.0, values[sid]), (1.0, values[sid])]
        for u, v in pts:
            key(sock, "default_value", v, min(max(int(round(a + (b - a) * u)), a), b))


def sky_detail(w, stars, tl):
    """Stars and Milky Way: in scene 04 they appear slowly while the camera rises ("by the thousands")."""
    _, reveal, power = stars
    held(power, tl, {sid: LIGHT[sid]["stars"] for sid in SCENES})
    held(reveal, tl, {sid: LIGHT[sid]["reveal"] for sid in SCENES},
         {"04": [(0.0, 0.03), (0.45, 0.06), (0.95, 1.2), (1.0, 1.2)]})
    held(w.band, tl, {sid: LIGHT[sid]["band"] for sid in SCENES},
         {"04": [(0.0, 0.0), (1.0, 0.0)], "05": [(0.0, 0.0), (0.45, 0.26), (1.0, 0.32)]})   # Milky Way only in 05


# ---------- camera ----------

def camera_path(tl):
    """(frame, position, target). Pairs on consecutive frames are hard cuts."""
    a = lambda sid, u: tl.at(sid, u)
    end = lambda sid: tl.at(sid, 1.0) - 1
    street = (-1.5, 70.0, 5.2)
    kt = lambda p: tuple(ti.KITCHEN_M @ Vector(p))
    g = ti.GROCERY_VIEW
    hill0, hill1 = (-6.0, 166.0), (-6.0, 178.0)
    hz = lambda x, y: tf.ground_z(x, y) + EYE
    return [
        (1, (7.65, -1.3, WALK_Z), street),
        (46, (7.55, -0.5, WALK_Z), (-1.2, 70.0, 5.0)),                     # 1.5 s: faster step at the start
        (a("02", 0.0), (7.5, -0.3, WALK_Z), (-1.0, 70.0, 4.8)),
        (a("02", 0.3), (7.45, -0.1, WALK_Z), (10.5, 8.0, 0.4)),            # turns slowly (2 s) to the hand
        (a("02", 0.9), (7.42, 0.0, WALK_Z), (10.5, 8.2, 0.45)),            # after "from your hand": goes back
        (a("03", 0.17), (7.3, 0.2, WALK_Z), (-0.5, 40.0, 1.6)),            # back to the street: the cars vanish
        (end("03"), (7.2, 1.2, WALK_Z), (-0.8, 60.0, 3.0)),
        (a("04", 0.0), (3.6, 13.0, EYE), (0.0, 60.0, 3.0)),                # cut: an hour later, in the middle of the street
        (a("04", 0.5), (3.6, 13.3, EYE), (0.0, 60.0, 5.0)),
        (end("04"), (3.6, 13.6, EYE), (1.0, 40.0, 28.0)),
        (a("05", 0.0), (3.6, 13.6, EYE), (1.0, 40.0, 29.0)),
        (end("05"), (3.6, 13.8, EYE), (-1.0, 32.0, 40.0)),                 # almost at the zenith, turning slowly
        (a("06", 0.0), kt((0.1, 0.25, 1.64)), kt((0.0, 1.9, 0.72))),       # cut: the kitchen (sink and the two openings)
        (a("06", 0.073), kt((0.1, 0.3, 1.64)), kt((0.0, 1.9, 0.74))),
        (a("06", 0.19), kt((0.06, 1.12, 1.55)), kt((0.02, 1.85, 0.98))),   # leaning on the sink: the faucet at ~0.65 m from the
        (a("06", 0.52), kt((0.06, 1.14, 1.55)), kt((0.02, 1.85, 1.0))),    # shoulder, the arm reads normal
        (end("06"), kt((0.03, 1.4, 1.6)), kt((0.0, 6.0, 2.7))),            # pushes in to the window: the water tower
        (a("07", 0.0), (g.x0, g.y, 1.6), (g.x1 + 10, g.y - 3.0, -0.4)),    # cut: the grocery (little ceiling)
        (end("07"), (g.x1, g.y, 1.6), (g.x1 + 20, g.y + 0.5, 0.2)),
        (a("08", 0.0), (7.3, 37.6, WALK_Z), (-2.2, 50.0, 0.7)),            # cut: the street by day (cast to the right
        (end("08"), (7.3, 37.5, WALK_Z), (-3.4, 45.5, 0.6)),               # of the panel, the person in front large)
        (a("09", 0.0), (1.0, 8.5, EYE + 0.03), (-0.2, 45.0, 0.9)),          # cut: a year later, on the dirt road
        (a("09", 0.6), (1.0, 10.6, EYE + 0.03), (-0.6, 40.0, 0.9)),
        (end("09"), (1.05, 11.4, EYE + 0.03), (-2.4, 20.0, 0.9)),           # the cart passes by
        (a("10", 0.0), (*hill0, hz(*hill0)), (6.0, 222.0, 40.0)),           # cut: climbing the hill, the water tower
        (a("10", 0.38), (*hill1, hz(*hill1)), (6.0, 222.0, 38.0)),
        (a("10", 0.5), (*hill1, hz(*hill1)), (-40.0, 176.0, 9.0)),         # pans across the horizon (without looking at the sky)
        (a("10", 0.62), (*hill1, hz(*hill1)), (0.0, 40.0, -14.0)),          # turns: the city of gardens below
        (end("10"), (hill1[0], hill1[1] + 1.5, hz(hill1[0], hill1[1] + 1.5)), (0.0, 30.0, -16.0)),
        (a("11", 0.0), (2.4, 14.0, EYE), (0.0, 90.0, 9.0)),                # cut: dusk, the stone
        (end("11"), (2.4, 14.4, EYE), (0.0, 90.0, 9.5)),
        (a("12", 0.0), (1.9, 25.2, 1.55), (-0.5, 31.0, 0.35)),             # cut: the night (fire at center-right,
        (tl.frames + 1, (1.5, 27.6, 1.4), (-0.3, 31.2, 0.3)),             # above the caption)
    ]


WALKING = ("07", "09")
LENS = {"04": 18, "05": 18, "06": 18, "10": 36}


def build_camera(tl):
    data = bpy.data.cameras.new("Eye")
    data.lens = 22
    data.clip_start, data.clip_end = 0.03, 4000.0
    cam = bpy.data.objects.new("Eye", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    path = camera_path(tl)
    cuts = {fb for (fa, _, _), (fb, _, _) in zip(path, path[1:]) if fb - fa <= 1}
    rnd = random.Random(7)

    def pose(f):
        for (fa, pa, ta), (fb, pb, tb) in zip(path, path[1:]):
            if fa <= f <= fb:
                u = (f - fa) / max(fb - fa, 1)
                u = u * u * (3 - 2 * u)
                return Vector(pa).lerp(Vector(pb), u), Vector(ta).lerp(Vector(tb), u)
        return Vector(path[-1][1]), Vector(path[-1][2])

    prev = None
    last = path[-1][0] - 1
    frames = list(range(1, last + 1))          # key on every frame, LINEAR: with a key every 2 frames the camera
                                               # alternated fast/slow and the facades "flickered" on the turns
    for f in frames:
        pos, target = pose(f)
        sway = Vector((math.sin(f * 0.07) * 0.006 + 0.002 * math.sin(f * 0.23), math.sin(f * 0.05 + 1) * 0.004,
                       math.sin(f * 0.09 + 2) * 0.005))
        if scene_of(tl, f) in WALKING:                         # step: the body rises and falls twice per cycle
            sway.z += 0.012 * math.sin(2 * math.pi * f / 16)
        pos = pos + sway
        q = (target - pos).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location = pos
        cam.rotation_quaternion = q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
    for sid in SCENES:                                          # lens per scene (switches only on the cut)
        data.lens = LENS.get(sid, 22)
        data.keyframe_insert("lens", frame=tl.at(sid))
    constant(data, ("lens",))      # object and camera share the same action in Blender 5: only the lens stays stepped
    for fc in tc.rigs._fcurves(cam.animation_data.action):
        if fc.data_path in ("location", "rotation_quaternion"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if kp.co.x + 1 in cuts else "LINEAR"
    return cam


# ---------- scenes 01-03: phone, cars, vanishing ----------

def phone(hand):
    """Phone (7.5 x 15.5 x 0.9 cm) lying in the palm, screen up: dark body, lit screen with blocks."""
    body = ts.mat("PhoneBody", "#16181E", rough=0.5)
    screen = ts.mat("PhoneScreen", "#4A6A96", emission="#8FB4E6", strength=0.75)
    ui = ts.mat("PhoneUI", "#F5A524", emission="#F5A524", strength=0.9)
    parts = [kit._box_geo(0.075, 0.155, 0.009, -0.0375, -0.0775, 0.0),
             kit._box_geo(0.067, 0.143, 0.002, -0.0335, -0.0715, 0.009)]
    for k in range(4):
        parts.append(kit._box_geo(0.05 - 0.012 * (k % 2), 0.012, 0.0015, -0.025, 0.035 - 0.026 * k, 0.0108))
    v, f, owner = kit.merge(*parts)
    obj = kit.mesh_object("Phone", v, f, [body, screen, ui], face_mats=[min(o, 2) for o in owner])
    kit.fix_normals(obj)
    obj.parent = hand
    obj.location = (0.004, 0.072, 0.03)
    obj.rotation_euler = (math.radians(-4), 0, math.radians(3))
    glow = bpy.data.lights.new("PhoneGlow", "POINT")
    glow.energy, glow.color, glow.shadow_soft_size = 1.2, (0.75, 0.85, 1.0), 0.05
    glow.use_shadow = False                    # light stuck to the lens: shadow cost 9 s/frame
    lo = bpy.data.objects.new("PhoneGlow", glow)
    bpy.context.collection.objects.link(lo)
    lo.parent = obj
    lo.location = (0, 0, 0.06)
    return obj, glow


PHONE_POSE = ((0.085, -0.20, -0.40), (-38, -14, 18))       # right hand at the bottom right, palm toward the camera
CLOSE_POSE = ((0.03, -0.12, -0.33), (-48, -8, 10))         # scene 02: the hand rises close, in the center


def hand_track(h, tl, ph, glow):
    hand = h.right
    s = h.scale

    def put(pose, f):
        loc, rot = pose
        hand.location = Vector(loc) * s
        hand.rotation_euler = [math.radians(a) for a in rot]
        hand.keyframe_insert("location", frame=f)
        hand.keyframe_insert("rotation_euler", frame=f)

    put(PHONE_POSE, 1)
    put(((0.083, -0.17, -0.385), (-46, -8, 12)), 24)                 # 0.8 s: raises and tilts the phone to look at it
    put(((0.086, -0.185, -0.39), (-41, -11, 16)), tl.at("01", 1.0))
    put(CLOSE_POSE, tl.at("02", 0.3))
    put(((0.032, -0.118, -0.33), (-50, -6, 9)), tl.at("02", 0.9))
    put(((0.06, -0.62, -0.36), (-30, -10, 14)), tl.at("03", 0.12))             # the empty hand lowers
    f_break = secs(tl, "02", VANISH_02)
    fx.make_dissolvable([ph])
    fx.vanish([ph], f_break, 10)
    fx.light_off(glow, "energy", glow.energy, f_break, 5)
    rnd = random.Random(3)
    bits = cm.specks_on_surface("PhoneBits", [ph], 120, rnd, gem=(0.012, 0.024), rise=(0.06, 0.2), drift=0.09,
                                strength=4.0)
    for frame, a in ((1, 0.0), (f_break, 0.0), (f_break + 2, 1.0)):
        key(bits.alpha_socket, "default_value", a, frame)
    cm.blink_away(bits, f_break + 2, 22)
    flash = bpy.data.lights.new("PhoneFlash", "POINT")
    flash.color, flash.shadow_soft_size = (1.0, 0.7, 0.35), 0.1
    flash.use_shadow = False
    fo = bpy.data.objects.new("PhoneFlash", flash)
    bpy.context.collection.objects.link(fo)
    fo.parent = hand
    fo.location = (0, 0.08, 0.12)
    for f, e in ((1, 0.0), (f_break, 0.0), (f_break + 4, 6.0), (f_break + 12, 2.0), (f_break + 26, 0.0)):
        key(flash, "energy", e, f)
    return [ph, bits.obj, fo]


CARS = (  # (type, color, x, y of stop, direction, stop frame, driver)
    ("NormalCar1", 0, 2.0, 26.4, 90, 52, "man"),
    ("SUV", 5, 2.0, 19.9, 90, 58, "woman"),
    ("NormalCar2", 1, 2.0, 13.6, 90, 64, "man"),
    ("NormalCar1", 4, 2.0, 7.2, 90, 70, "woman"),
    ("SUV", 2, -2.0, 56.4, -90, 46, "man"),
    ("NormalCar2", 3, -2.0, 63.2, -90, 56, "woman"),
    ("NormalCar1", 6, -2.0, 71.4, -90, 66, None),
)


def traffic(tl):
    """Cars arriving and stopping at the red light already at frame 1; they vanish in 03 and the drivers fall onto the asphalt."""
    out, drivers = [], []
    f_v = secs(tl, "03", VANISH_03)
    for k, (kind, color, x, y, hdg, stop, who) in enumerate(CARS):
        c = tc.car(f"Car{k}", kind, tc.CAR_COLORS[color], (x, y, 0.0), math.radians(hdg))
        tc.roll_to_stop(c, 1, stop, (x, y), speed=3.2 + 0.3 * (k % 3))
        fk = f_v + (k * 2) % 5
        fx.make_dissolvable(c.meshes)
        fx.vanish(c.meshes, fk, 12)
        for b in c.beams:
            fx.light_off(b.data, "energy", b.data.energy, fk + 2, 5)
        out.append(c)
        if who:
            d = tc.driver(f"Driver{k}", who, c, k, kind)
            tc.segment(d, "Sitting", 1, tl.at("03", 1.0) + 2, 30, 190, rate=1.0)
            tc.drop(d, fk + 5, tl.at("03", 1.0) + 2, look_yaw=(20 if k % 2 else -24))   # falls when the seat vanishes
            drivers.append(d)
    return out, drivers


def tech_bits(tech_objs, tl, rnd):
    """Residue: little amber dots rising from the cars, signs and traffic lights when they vanish."""
    f_v = secs(tl, "03", VANISH_03)
    bits = cm.specks_on_surface("TechBits", tech_objs, 1400, rnd, gem=(0.03, 0.06), rise=(0.4, 1.6), drift=0.4,
                                strength=3.0)
    for frame, a in ((1, 0.0), (f_v + 3, 0.0), (f_v + 5, 1.0)):
        key(bits.alpha_socket, "default_value", a, frame)
    cm.blink_away(bits, f_v + 5, 26)
    return bits.obj


def street_off(street, tl):
    """Signs and traffic light vanish with the cars; poles and windows go out one by one, from near to far."""
    f_v = secs(tl, "03", VANISH_03)
    fx.make_dissolvable(street.signs + street.signals)
    fx.vanish(street.signs + street.signals, f_v + 1, 12)
    a, b = secs(tl, "03", LIGHTS_03[0]), secs(tl, "03", LIGHTS_03[1])
    ahead = [l for l in street.lamps if l.y > 2]
    behind = [l for l in street.lamps if l.y <= 2]
    for lamp in behind:                                             # behind the camera: they go out with the first
        fx.light_off(lamp.power, "default_value", lamp.power.default_value, a, 4)
        fx.light_off(lamp.light, "energy", lamp.light.energy, a, 4)
    for k, lamp in enumerate(ahead):                                # one pole every ~5 frames, to the horizon
        f = int(a + (b - a) * k / max(len(ahead) - 1, 1))
        fx.light_off(lamp.power, "default_value", lamp.power.default_value, f, 3)
        fx.light_off(lamp.light, "energy", lamp.light.energy, f, 3)
    jitter = random.Random(21)
    for bld in street.buildings:                                    # windows: each building on its frame, between the poles
        y = (bld.y0 + bld.y1) / 2
        u = min(max((y - 2) / 140, 0), 1)
        f = int(a + 6 + (b - a - 6) * u + jitter.randint(-4, 4))
        sock = kit.principled(bld.lit).inputs["Emission Strength"]
        fx.light_off(sock, "default_value", sock.default_value, f, 3)


def long_sleeve(hand):
    """Continuation of the sleeve (the arm up to the shoulder): the hand, wrist and sleeve are one piece attached to the camera and the arm
    always leaves through the bottom edge of the frame, even with the hand far (scene 06)."""
    flannel = bpy.data.materials.get("Flannel") or ts.mat("Flannel", "#7A2E2E")
    rings = []
    for y, r in ((-0.30, 0.050), (-0.55, 0.056), (-0.85, 0.062), (-1.15, 0.066)):
        rings.append([(r * math.cos(2 * math.pi * j / 10), y, 0.78 * r * math.sin(2 * math.pi * j / 10) - 0.004)
                      for j in range(10)])
    v, f = kit.loft_geo(rings, cap_start=False, cap_end=True)
    obj = kit.fix_normals(kit.mesh_object("HandSleeve", v, f, [flannel]))
    obj.parent = hand
    obj.visible_shadow = False
    return obj


# ---------- everything ----------

def build(tl):
    rnd = random.Random(42)
    w = sky.build_world()
    stars = sky.star_field()
    street = ts.build(rnd)
    far = tf.build(rnd)
    farm = tfarm.build(random.Random(8))
    grocery_bld = next(b for b in street.buildings if b.side < 0 and abs(b.y0 - ts.GROCERY[1]) < 0.01)
    store = ti.grocery(grocery_bld, random.Random(4))
    ti.GROCERY_VIEW.set(store)
    kitchen = ti.kitchen()
    cam = build_camera(tl)
    h = cm.hands(cam, one_hand=True)
    h.left.hide_render = True
    sleeve = long_sleeve(h.right)
    ph, glow = phone(h.right)
    fill = bpy.data.objects.new("HandFill", bpy.data.lights.new("HandFill", "POINT"))
    fill.data.energy, fill.data.color, fill.data.shadow_soft_size = 18.0, (1.0, 0.78, 0.55), 0.3
    fill.data.use_shadow = False
    fill.location, fill.parent = (0.3, 0.25, 0.1), cam
    bpy.context.collection.objects.link(fill)
    phone_fx = hand_track(h, tl, ph, glow)
    for f in range(1, tl.frames + 2, 4):                       # breathing: the hand is never frozen on screen
        key(h.root, "location", (0.0015 * math.sin(f * 0.11), 0.003 * math.sin(f * 0.07 + 1.0), 0.0), f)
    stone = sc.stone_hand(h, tl)
    cars, drivers = traffic(tl)
    tech = [m for c in cars for m in c.meshes] + street.signs + street.signals
    bits = tech_bits(tech, tl, rnd)
    street_off(street, tl)
    fx.light_off(store.lamp_power, "default_value", store.lamp_power.default_value, secs(tl, "03", LIGHTS_03[0]) + 8, 4)
    lights(w, tl)
    sky_detail(w, stars, tl)
    crowd = sc.crowd(tl)
    k_hand = sc.kitchen_pov(h, kitchen, tl)
    k_drops = sc.drops(kitchen, tl)
    walkers = sc.foot_traffic(tl)
    farmers = sc.farm_life(tl)
    fire = sc.fire_scene(tl, random.Random(12))
    fade = sc.darken(cam, tl, 6.6, 8.8, 0.88)        # final pause: darkens slowly until the question

    visible([stars[0]], ("04", "05", "11", "12"), tl)
    visible([h.right, sleeve, fill], ("01", "02", "03", "06", "11"), tl)
    visible(phone_fx, ("01", "02", "03"), tl)
    visible(stone, ("11",), tl)
    for c in cars:
        visible([m for m in c.meshes] + c.beams, ("01", "02", "03"), tl)
    for d in drivers:
        visible(tc.rigs.all_objects(d), ("01", "02", "03"), tl)
    visible([bits] + street.signs + street.signals, ("01", "02", "03"), tl)
    visible(crowd, ("04", "05"), tl)
    visible(kitchen.objs + k_hand + k_drops, ("06",), tl)
    visible([store.day], ("07",), tl)
    visible(walkers, ("08",), tl)
    visible(farm, ("09", "10", "11", "12"), tl)
    visible(farmers, ("09",), tl)
    visible(fire, ("12",), tl)
    visible([fade], ("12",), tl)
    return far


kit.run(build)
