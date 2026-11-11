"""Animation for the pangaea-never-split script: the globe (space scenes) and a single ground spot across six epochs.

Run by 'python -m ifscape blender scripts/pangaea-never-split.json'. In space, a slow orbital camera circles
a low-poly globe far above the ground (G); on the ground, an eye-level POV (1.65 m) always in the same place, at the edge
of the desert. Each scene change is a hard cut (a jump of millions of years); the light only changes on cuts, never flickers.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

import globe as gl  # noqa: E402
import humans_set as hs  # noqa: E402
import kit  # noqa: E402
import pangaea_cast as cast  # noqa: E402
import pangaea_fx as pfx  # noqa: E402
import pangaea_ground as pg  # noqa: E402
from kit import key  # noqa: E402

EYE = 1.65
G = Vector((5000.0, 0.0, 0.0))                  # globe center, far from the ground (out of reach of the ground camera)
ORBIT = ("01", "02", "05", "10", "11", "12")
SCENES = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")

# Light states per scene (they only change on cuts). sky/day/dusk/stars: sky; sun: strength; rot: sun direction.
HOT_DAY = {"sky": 1.0, "ambient": 2.3, "sun": 4.0, "day": 1.0, "dusk": 0.15, "stars": 0.0, "rot": (40, 0, 110),
           "color": (1.0, 0.9, 0.75)}
DAY = {"sky": 1.0, "ambient": 2.3, "sun": 3.5, "day": 1.0, "dusk": 0.0, "stars": 0.0, "rot": (45, 0, 140),
       "color": (1.0, 0.95, 0.88)}
DUSK = {"sky": 1.0, "ambient": 2.0, "sun": 2.2, "day": 0.5, "dusk": 1.0, "stars": 0.0, "rot": (80, 0, -60),
        "color": (1.0, 0.6, 0.38)}
BLUE = {"sky": 1.0, "ambient": 3.2, "sun": 2.2, "day": 0.35, "dusk": 0.9, "stars": 0.0, "rot": (82, 0, -50),
        "color": (1.0, 0.66, 0.45)}
DAWN = {"sky": 1.0, "ambient": 2.8, "sun": 2.4, "day": 0.45, "dusk": 0.7, "stars": 0.0, "rot": (78, 0, 70),
        "color": (1.0, 0.72, 0.48)}
NIGHT = {"sky": 1.0, "ambient": 1.1, "sun": 0.6, "day": 0.0, "dusk": 0.0, "stars": 1.0, "rot": (60, 0, -30),
         "color": (0.65, 0.75, 1.0)}
SPACE = {"sky": 1.0, "ambient": 0.9, "sun": 4.5, "day": 0.0, "dusk": 0.0, "stars": 0.0, "rot": None,
         "color": (1.0, 0.95, 0.9)}
LIGHT = {"01": SPACE, "02": SPACE, "03": HOT_DAY, "04": DAY, "05": SPACE, "06": DUSK, "07": BLUE, "08": DAWN,
         "09": NIGHT, "10": SPACE, "11": SPACE, "12": SPACE}


def lights(w, tl):
    """Each scene holds its state from start to end (CONSTANT keys): the light only changes on the cut."""
    w.moon.scale = (0, 0, 0)
    owners = {"sky": (w.sky, "default_value"), "ambient": (w.ambient, "default_value"), "sun": (w.sun, "energy"),
              "day": (w.day, "default_value"), "dusk": (w.dusk, "default_value"), "stars": (w.stars, "default_value")}
    starts = {sid: Vector(keys[0][1]) for sid, keys in camera_keys(tl).items()}
    for sid in SCENES:
        f = tl.at(sid)
        st = LIGHT[sid]
        for name, (owner, attr) in owners.items():
            key(owner, attr, st[name], f)
        rot = space_sun(starts[sid]) if st["rot"] is None else tuple(math.radians(a) for a in st["rot"])
        key(w.sun_obj, "rotation_euler", rot, f)
        w.sun.color = st["color"]
        w.sun.keyframe_insert("color", frame=f)
    if True:                                                        # moon only on tonight's scene
        w.moon.location = (-60, 900, 260)
        for sid in SCENES:
            key(w.moon, "scale", (1, 1, 1) if sid == "09" else (0, 0, 0), tl.at(sid))
    for data in (w.sun, w.sun_obj, w.moon, bpy.context.scene.world.node_tree):
        constant(data)


def space_sun(cam_pos):
    """Sun of the orbital scenes comes from behind and to the left of the scene camera: the visible side stays lit.
    (A fixed sun left the land in shadow when the camera followed the spin, QA of 2026-10-21.)"""
    d = (cam_pos - G).normalized()
    s = Quaternion((0, 0, 1), math.radians(-35)) @ d
    s.z += 0.45
    return tuple((-s.normalized()).to_track_quat("-Z", "Y").to_euler())


def constant(owner, paths=None):
    """CONSTANT on the owning object's f-curves; with paths, only on those (the rest of the motion stays smooth)."""
    ad = getattr(owner, "animation_data", None)
    if ad is None or ad.action is None:
        return
    for fc in gl._fcurves_of(ad.action):
        if paths and fc.data_path not in paths:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def linear(owner, paths=("rotation_quaternion",)):
    ad = getattr(owner, "animation_data", None)
    for fc in gl._fcurves_of(ad.action if ad else None):
        if fc.data_path in paths:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def visible(objs, scenes, tl):
    """Shows the objects only in the listed scenes (hide_render with CONSTANT keys)."""
    for o in objs:
        for sid in SCENES:
            o.hide_render = sid not in scenes
            o.keyframe_insert("hide_render", frame=tl.at(sid))
        constant(o, ("hide_render",))       # only the on/off; CONSTANT on everything froze the motion in steps


WHITE = (0.40, 0.46, 0.495, 0.60)     # scene 06: wave arrives, peak, starts to open, open (short peak: the caption vanishes into the white)


def hide_from(objs, frame):
    """Hides from 'frame' on (in the middle of a scene; use only under the white screen)."""
    for o in objs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=frame)
        constant(o, ("hide_render",))


def whiteout(cam, tl):
    """Scene 06: the shock wave turns the screen white (warm cream, so the white caption with shadow still reads)
    and the white slowly opens up, showing the world after the impact."""
    mat, power = kit.keyed_emission("Whiteout", "#D9BE96", "#D9BE96", 0.0)
    mat.surface_render_method = "BLENDED"
    alpha = kit.principled(mat).inputs["Alpha"]
    card = kit.mesh_object("Whiteout", [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [(0, 1, 2, 3)], [mat],
                           (0, 0, -0.06))
    card.parent = cam
    card.visible_shadow = False
    a, b, c, d = (tl.at("06", u) for u in WHITE)
    for frame, al, pw in ((1, 0.0, 0.0), (a, 0.0, 0.0), (b, 0.8, 1.0), (c, 0.8, 1.0), (d, 0.0, 0.0)):   # 85%: white caption still reads   # Standard: strength 1 gives the exact cream (4 blew out to pure white)
        key(alpha, "default_value", al, frame)
        key(power, "default_value", pw, frame)
    visible([card], ("06",), tl)
    return card


def all_children(root):
    return [root, *root.children_recursive]


# ---------- space ----------

def build_space(tl, rnd):
    pan = gl.globe("Pan", tuple(G), rnd, pangaea=True)
    mod = gl.globe("Mod", tuple(G), rnd, pangaea=False)
    sky = gl.space(tuple(G), rnd)
    rift = gl.rift_line("Rift", tuple(G), pan.plates["Pangaea"])
    # Pangaea: scenes 01, 02 and 05 (right); today: 05 (left), 10, 11, 12.
    visible(all_children(pan.root), ("01", "02", "05"), tl)
    visible(all_children(mod.root), ("05", "10", "11", "12"), tl)
    visible([sky.shell, sky.stars], ORBIT, tl)
    visible([rift.obj], ("02",), tl)
    face_africa = Quaternion((0, 0, 1), math.radians(25))           # the Africa/Atlantic side facing front
    for sid in SCENES:
        f = tl.at(sid)
        if sid == "05":
            key(pan.root, "location", tuple(G + Vector((0, 2.5, -9.5))), f)
            key(mod.root, "location", tuple(G + Vector((0, -5.5, 9.5))), f)
            for r in (pan.root, mod.root):
                key(r, "scale", (0.92, 0.92, 0.92), f)
        else:
            for r in (pan.root, mod.root):
                key(r, "location", tuple(G), f)
                key(r, "scale", (1, 1, 1), f)
    for r in (pan.root, mod.root):
        constant(r, ("location", "scale"))
    # Continuous slow spin of each globe (0.8 deg/s), with Africa facing front.
    for r in (pan.root, mod.root):
        r.rotation_quaternion = face_africa
        for f in range(1, tl.frames + 2, 30):
            key(r, "rotation_quaternion", face_africa @ Quaternion((0, 0, 1), math.radians(0.8 * f / tl.fps)), f)
        linear(r)                                                     # Bezier on every key made the speed pulse
    # Crack (02): appears at "tear apart", disappears at "never does".
    for frame, p in ((tl.at("02", 0.30), 0.0), (tl.at("02", 0.42), 0.0), (tl.at("02", 0.55), 8.0),
                     (tl.at("02", 0.70), 8.0), (tl.at("02", 0.88), 0.0)):
        key(rift.power, "default_value", p, frame)
    # Today's plates: 05 leave together and spread out; 10 join in Pangaea Ultima; 11 stay together; 12 return.
    for plate, obj in mod.plates.items():
        ult = gl.ultima_rotation(plate)
        key(obj, "rotation_quaternion", ult, 1)
        key(obj, "rotation_quaternion", ult, tl.at("05", 0.1))
        key(obj, "rotation_quaternion", Quaternion(), tl.at("05", 0.6))
        key(obj, "rotation_quaternion", Quaternion(), tl.at("10", 0.12))
        key(obj, "rotation_quaternion", ult, tl.at("10", 0.95))
        key(obj, "rotation_quaternion", ult, tl.at("11", 1.0) - 1)
        key(obj, "rotation_quaternion", Quaternion(), tl.at("12"))
    heat(mod, tl)
    globe_animals(pan, mod, tl)
    return pan, mod, sky


def globe_animals(pan, mod, tl):
    """Scene 05: a different animal on each of today's continents; the same Apatosaurus repeated on Pangaea
    (Quaternius assets with Idle; pangaea_cast.globe_animals)."""
    for r in cast.globe_animals(pan, mod, tl, gl.R):
        visible(all_children(r.root), ("05",), tl)


def heat(mod, tl):
    """Scene 11: the interior of the supercontinent turns orange and glows; the coast turns slightly green."""
    for k, mat in enumerate(mod.mats[:4]):
        p = kit.principled(mat)
        p.inputs["Emission Color"].default_value = kit.lin("#E0611C")
        s = p.inputs["Emission Strength"]
        peak = (0.15, 0.6, 1.1, 1.1)[k]                       # too strong washes out to salmon (AgX)
        key(s, "default_value", 0.0, tl.at("11", 0.0))
        key(s, "default_value", peak, tl.at("11", 0.6))
        key(s, "default_value", peak, tl.at("11", 1.0) - 1)
        key(s, "default_value", 0.0, tl.at("12"))


# ---------- ground ----------

def build_ground(tl, rnd):
    ground = pg.terrain(rnd)
    herd_path_x = -34.0
    keep = [(0, 0, 3.0), (herd_path_x, 0, 0)]
    flora = pg.mesozoic_flora(rnd, keep + [(herd_path_x, y, 6) for y in range(-120, 121, 6)])
    visible(flora, ("03", "04", "06", "07"), tl)
    visible(pg.monsoon_clouds(rnd), ("03",), tl)

    # Cast with the Quaternius CC0 assets (pangaea_cast.py): the rnd draws are the same as before.
    for r in cast.herd(tl, rnd, pg.ground_z, herd_path_x):
        visible(all_children(r.root), ("04",), tl)
    flash = tl.at("06", 0.32)
    for r in cast.dusk_pair(tl, pg.ground_z, tuple(pfx.E[:2]), flash):
        # No animated fall (rejected on review, 2026-10-21): the flash makes the two raise their heads and look;
        # the shock wave turns the screen white and, when the white opens, they are no longer there.
        visible(all_children(r.root), ("06",), tl)
        hide_from(all_children(r.root), tl.at("06", WHITE[1]))
    for sid, r in cast.rats(tl, pg.ground_z):                   # with the whole body (children): nothing loose
        visible(all_children(r.root), (sid,), tl)

    late = pg.grass(rnd) + pg.savanna_trees(rnd, keep + [(2, 30, 8)])
    visible(late, ("08", "09"), tl)
    for r in cast.people(tl, rnd, pg.ground_z):
        visible(all_children(r.root), ("08",), tl)
    road = pg.highway(rnd) + pg.town(rnd)
    car, beam = pg.car("Car")
    car.rotation_euler.z = math.pi                                   # comes along the camera lane, head-on
    key(car, "location", (pg.ROAD_X - 1.8, 40, pg.ground_z(pg.ROAD_X, 40)), tl.at("09", 0.0))
    key(car, "location", (pg.ROAD_X - 1.8, -20, pg.ground_z(pg.ROAD_X, -20)), tl.at("09", 0.6))
    linear(car, ("location",))
    visible(road + [car, beam], ("09",), tl)
    pieces, lamp = pfx.impact(tl)
    visible([*pieces, lamp], ("06",), tl)
    return ground


# ---------- camera ----------

def orbit_point(lat, lon, dist):
    return tuple(G + gl.to_vec(lat, lon, dist))


def facing(lat, lon, dist, frame, fps):
    """Camera facing (lat, lon) of the globe, compensating for its spin (25 deg + 0.8 deg/s)."""
    return orbit_point(lat, lon + 25 + 0.8 * frame / fps, dist)


def camera_path(tl):
    """Segments ((frame, position, target, lens), (frame, ...)). Every scene change is a hard cut."""
    p = []
    for sid, keys in camera_keys(tl).items():
        frames = [tl.at(sid, u) if u < 1 else tl.at(sid, 1.0) - 1 for u in (k[0] for k in keys)]
        for (fa, ka), (fb, kb) in zip(zip(frames, keys), zip(frames[1:], keys[1:])):
            p.append(((fa, *ka[1:]), (fb, *kb[1:])))
    return p


def camera_keys(tl):
    """{scene: [(fraction, position, target, lens), ...]}."""
    o = tuple(G)
    out = {}

    def scene(sid, a, b, *mid):
        out[sid] = [(0.0, *a), *mid, (1.0, *b)]

    lift = tuple(G + Vector((0, 0, 3.0)))                            # 01: globe lower, clear of the title
    scene("01", (orbit_point(16, -25, 66), lift, 50), (orbit_point(14, -18, 58), lift, 50))
    scene("02", (orbit_point(14, -35, 60), o, 50), (orbit_point(10, -28, 56), o, 50))
    # 03: at the edge of the desert looking at the dunes; on "Monsoons" turns to the clouds to the west, on "Inland" turns back.
    def dune(x, y):
        return (x, y, pg.ground_z(x, y) + EYE)
    scene("03", (dune(38, -4), (120, 14, 8), 22), (dune(40, -1.5), (120, -10, 8), 22),
          (0.47, dune(39, -3), (120, -4, 8), 22), (0.50, dune(39, -3), (30, 120, 8), 22),
          (0.53, dune(39, -3), (-120, 40, 12), 22), (0.64, dune(39.2, -2.6), (-120, 30, 12), 22),
          (0.67, dune(39.2, -2.6), (30, 120, 8), 22), (0.70, dune(39.4, -2.2), (120, 6, 8), 22))
    scene("04", ((0, -4, EYE), (-34, -10, 6), 22), ((0, -2, EYE), (-34, 14, 6), 22))
    scene("05", (tuple(G + Vector((90, 0, 4))), o, 50), (tuple(G + Vector((86, 0, 3))), o, 50))
    scene("06", ((0, 0, EYE), (10, 120, 12), 22), ((0, 0.4, EYE), (14, 120, 14), 22))
    scene("07", ((0, 0, EYE), (-14, 30, 1.2), 22), ((0.2, 0.3, EYE), (-2, 30, 0.8), 22))
    walk08 = 1.25 * (tl.at("08", 1.0) - tl.at("08")) / tl.fps
    scene("08", ((3.6, 3.0, EYE), (-0.4, 9.5, 1.1), 22), ((3.6, 3.0 + walk08, EYE), (-0.4, 9.5 + walk08, 1.1), 22))
    scene("09", ((pg.ROAD_X - 5.5, -8, EYE), (pg.ROAD_X - 4, 60, 2.0), 22),
          ((pg.ROAD_X - 5.5, -7.5, EYE), (pg.ROAD_X + 60, 26, 1.0), 22))
    fps = tl.fps
    scene("10", (facing(24, -28, 62, tl.at("10"), fps), o, 50), (facing(24, -18, 58, tl.at("10", 1.0), fps), o, 50))
    scene("11", (facing(22, -12, 58, tl.at("11"), fps), o, 50), (facing(20, -6, 54, tl.at("11", 1.0), fps), o, 50))
    scene("12", (facing(18, -30, 60, tl.at("12"), fps), o, 50), (facing(18, -22, 64, tl.at("12", 1.0), fps), o, 50))
    return out


def shake(tl, f):
    """Shake of the impact wave: strong at 0.35 of scene 06 and fading out until 0.65 (frame by frame)."""
    a, b = tl.at("06", 0.35), tl.at("06", 0.65)
    if not a <= f <= b:
        return 0.0
    return 0.12 * (1 - (f - a) / (b - a)) ** 2


def build_camera(tl):
    data = bpy.data.cameras.new("Eye")
    data.clip_start, data.clip_end = 0.05, 4000.0
    cam = bpy.data.objects.new("Eye", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    path = camera_path(tl)
    rnd = random.Random(7)
    prev = None
    for (fa, pa, ta, la), (fb, pb, tb, lb) in path:
        ground = la < 30
        dense = set(range(tl.at("06", 0.34), tl.at("06", 0.7))) & set(range(fa, fb + 1))
        for f in sorted({*range(fa, fb + 1, 3), fb, *dense}):
            u = (f - fa) / max(fb - fa, 1)
            u = u * u * (3 - 2 * u)
            pos, target = Vector(pa).lerp(Vector(pb), u), Vector(ta).lerp(Vector(tb), u)
            quake = shake(tl, f)
            if quake:
                pos += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * quake
            if ground:                                               # light hand at eye height
                pos += Vector((rnd.uniform(-0.006, 0.006), rnd.uniform(-0.006, 0.006), rnd.uniform(-0.005, 0.005)))
            q = (target - pos).to_track_quat("-Z", "Y")
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q
            key(cam, "location", tuple(pos), f)
            key(cam, "rotation_quaternion", q, f)
            key(data, "lens", la, f)
    return cam


def build(tl):
    rnd = random.Random(42)
    w = hs.build_world()
    lights(w, tl)
    build_space(tl, rnd)
    build_ground(tl, rnd)
    cam = build_camera(tl)
    whiteout(cam, tl)


kit.run(build)
