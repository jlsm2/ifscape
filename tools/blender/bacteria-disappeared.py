"""Continuous animation for the bacteria-disappeared script: a small farm, one year, and the dive into the cell.

Run by 'python -m ifscape blender scripts/bacteria-disappeared.json'. POV camera at eye height
(1.65 m). One continuous shot from the porch to the back of the barn; hard cuts only where time jumps far
(07: six months, at the fence; 09: top of the hillock) and in the dive into the hand (11), which passes through an amber flash.
No flickering sky in the time jumps (it looked like a defect): the light always changes slowly.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bacteria_set as bs  # noqa: E402
import cell_models as cm  # noqa: E402
import farm_animals as fa  # noqa: E402
import humans_set as hs  # noqa: E402
import kit  # noqa: E402
import land  # noqa: E402
from kit import color_ramp_socket, grow, key, ramp  # noqa: E402

EYE = 1.65
LENS = 22.0
BLINK_S = 3.9                     # seconds in scene 02 at which the bacteria vanish (line "blink")
DIVE = 0.64                       # fraction of scene 11 at which the camera crosses the skin (end of "cells,")
END_S = 6.6                       # seconds in scene 12: start of the pause before "What should I imagine next?"

DAWN = {"sky": 1.0, "ambient": 1.4, "sun": 2.0, "day": 0.35, "dusk": 0.6, "stars": 0.15}
DAY = {"sky": 1.0, "ambient": 1.3, "sun": 3.5, "day": 1.0, "dusk": 0.0, "stars": 0.0}
DUSK = {"sky": 1.0, "ambient": 1.7, "sun": 2.4, "day": 0.6, "dusk": 1.0, "stars": 0.0}


# ---------- sky ----------

def set_sky(w, state, frame):
    owners = {"sky": (w.sky, "default_value"), "ambient": (w.ambient, "default_value"), "sun": (w.sun, "energy"),
              "day": (w.day, "default_value"), "dusk": (w.dusk, "default_value"), "stars": (w.stars, "default_value")}
    for name, (owner, attr) in owners.items():
        key(owner, attr, state[name], frame)


def sky(w, tl):
    w.moon.scale = (0, 0, 0)
    sun = w.sun_obj
    # The light always changes slowly. The flickering day/night sky in the time jumps was removed on request
    # (21/10/2026): "looks like it's just buggy". The jump keeps the panel and the cut.
    set_sky(w, DAWN, 1)
    set_sky(w, DAWN, tl.at("02", 0.5))
    set_sky(w, {**DAY, "sun": 3.0, "dusk": 0.2}, tl.at("03", 0.8))
    set_sky(w, DAY, tl.at("04", 0.2))
    set_sky(w, DAY, tl.at("10", 0.0))
    set_sky(w, DUSK, tl.at("10", 0.6))
    for frame, rot, color in ((1, (80, 0, 110), (1.0, 0.70, 0.45)), (tl.at("03", 0.8), (50, 0, 60), (1.0, 0.95, 0.88)),
                              (tl.at("09", 1.0), (55, 0, 40), (1.0, 0.95, 0.88)), (tl.at("10", 0.6), (82, 0, -70),
                                                                                 (1.0, 0.62, 0.38))):
        key(sun, "rotation_euler", tuple(math.radians(a) for a in rot), frame)
        w.sun.color = color
        w.sun.keyframe_insert("color", frame=frame)


# ---------- farm ----------

def animate_cows(farm, tl, rnd):
    """Heads go down and up at the trough (eating nonstop) and the tails sway."""
    for k, c in enumerate(farm.cows):
        f, period = 1 + k * 11, int(rnd.uniform(70, 95))
        while f < tl.frames:
            fa.head_down(c, rnd.uniform(28, 36), f)
            fa.head_down(c, rnd.uniform(8, 14), f + period // 2)
            f += period
        f = 1 + k * 7
        while f < tl.frames:
            c.tail.rotation_euler = (math.radians(rnd.uniform(-14, 14)), 0, 0)
            c.tail.keyframe_insert("rotation_euler", frame=f)
            f += int(rnd.uniform(25, 45))


def xray(farm, tl):
    """Scene 05: the front cow's body becomes transparent and shows the rumen with the still grass."""
    for sock in farm.xray:
        key(sock, "default_value", 1.0, tl.at("05", 0.12))
        key(sock, "default_value", 0.22, tl.at("05", 0.3))
        key(sock, "default_value", 0.22, tl.at("05", 0.62))
        key(sock, "default_value", 1.0, tl.at("05", 0.78))
    r = farm.rumen
    for frame, sc in ((1, 0), (tl.at("05", 0.12), 0), (tl.at("05", 0.2), 1), (tl.at("05", 0.7), 1), (tl.at("05", 0.78), 0)):
        key(r, "scale", (sc, sc, sc), frame)


def manure(farm, tl, rnd):
    """Scene 06: the pile grows in steps; on the second sentence ('Only fungi...') the mushrooms sprout."""
    heap, base = farm.bay.heap, farm.bay.heap.location.copy()
    key(heap, "scale", (0.8, 0.8, 0.55), 1)
    for k, frac in enumerate((0.06, 0.18, 0.3, 0.42)):
        z = 0.55 + 0.12 * (k + 1)
        key(heap, "scale", (0.8 + 0.04 * k, 0.8 + 0.04 * k, z - 0.12), tl.at("06", frac))
        key(heap, "scale", (0.84 + 0.04 * k, 0.84 + 0.04 * k, z), tl.at("06", frac + 0.06))
    sx, sz = heap.scale.x, heap.scale.z                                   # final scale (last key)
    for m in farm.bay.mushrooms:
        off = m.location - base
        m.location = (base.x + off.x * sx, base.y + off.y * sx, off.z * sz - 0.04)
        f = tl.at("06", rnd.uniform(0.52, 0.75))
        grow(m, f, f + 8, target=rnd.uniform(2.4, 3.2))


# ---------- landscape ----------

def seasons(ld, tl):
    """Pasture and trees turn yellow from scene 07 on; at the one-year jump (10) they become gray-brown and leafless.
    The cornfield (fertilized) stays green until 10, and then blotches."""
    color_ramp_socket(ld.grass, land.GRASS, "#B7A24E", tl.at("07", 0.1), tl.at("07", 0.8))
    key(ld.grass, "default_value", kit.lin("#8C7A4E"), tl.at("10", 0.0))
    key(ld.grass, "default_value", kit.lin("#6E6656"), tl.at("10", 0.35))
    land.autumn(ld.leaves, tl.at("07", 0.1), tl.at("09", 0.2), tl.at("10", 0.35))
    rnd = random.Random(4)
    for t in ld.near:
        f = tl.at("10", rnd.uniform(0.08, 0.32))
        key(t.canopy, "scale", (1, 1, 1), f)
        key(t.canopy, "scale", (0, 0, 0), f + 10)
    for k, sock in enumerate(ld.corn.colors):
        key(sock, "default_value", kit.lin(land.CORN), tl.at("10", 0.0))
        key(sock, "default_value", kit.lin(land.CORN if k == 0 else land.CORN_DRY), tl.at("10", 0.35))
    land.animate_plumes(ld.plant.plumes, rnd, tl.frames)
    for f in range(1, tl.frames, 9):
        key(ld.plant.flame_power, "default_value", rnd.uniform(18, 34), f)


# ---------- bacteria, hands and cell ----------

def bacteria(s, h, tl, rnd):
    """Amber dots in the yard air, in the barn and on the hands; they glow from frame 1 and vanish on the 'blink'."""
    air = cm.specks_in_air("SpecksAir", (0, 9, 1.8), (22, 20, 3.6), 2600, rnd)
    walls = cm.specks_on_surface("SpecksBarn", s.farm.barn.walls + [s.farm.barn.roof], 1400, rnd)
    hand_specks = [cm.specks_on_surface(f"Specks{side}", [hand], 500, rnd, parent=hand, mats=cm.SKIN_MATS,
                                        gem=(0.003, 0.006)) for side, hand in (("L", h.left), ("R", h.right))]
    blink = tl.at("02") + tl.secs(BLINK_S)
    for sp in (air, walls, *hand_specks):
        cm.shimmer(sp, 1, blink - 1)
        cm.blink_away(sp, blink, 14)


def hands_track(h, tl):
    """Hands raised from frame 1, lowered after the 'blink'; they come back open in scene 11 and the hand 'grows'
    toward the lens (the dive into the palm), on the beat of 'tiny power plants'."""
    cm.pose_raised(h, 1)
    for hand, sx in ((h.left, -1), (h.right, 1)):
        hand.location.x += sx * 0.045 * h.scale                         # leaves room in the center for the caption
        hand.keyframe_insert("location", frame=1)
    blink = tl.at("02") + tl.secs(BLINK_S)
    for hand in (h.left, h.right):
        hand.visible_shadow = False                                      # out of frame, casts no shadow
    cm.lift(h, blink + tl.secs(0.8), blink + tl.secs(1.6), drop=0.9, up=False)
    cm.pose_open_palm(h, tl.at("11", 0.0))
    # The hand only enters after "of oxygen left.", from the left and high (the caption sits at the center, bottom);
    # the dive is on "And inside your cells," and the flash lands at the end of "cells".
    side = (-0.08 * h.scale, 0.1 * h.scale, 0)
    low = (side[0], side[1] - 0.9 * h.scale, 0)
    key(h.root, "location", low, tl.at("11", 0.3))
    key(h.root, "location", side, tl.at("11", 0.42))
    dive0, dive1 = tl.at("11", 0.57), tl.at("11", DIVE)            # fast: the palm fills the screen for only ~0.2 s
    key(h.root, "location", side, dive0)
    key(h.root, "location", (0, 0.12 * h.scale, 0.33 * h.scale), dive1)
    for name in cm.SKIN_MATS:                                            # the hand shadows itself near the lens:
        sock = kit.principled(bpy.data.materials[name]).inputs["Base Color"]   # white caption stays legible
        color = tuple(sock.default_value)
        key(sock, "default_value", color, dive0)
        key(sock, "default_value", tuple(c * 0.3 for c in color[:3]) + (1.0,), dive1)
    hidden = blink + tl.secs(1.8), tl.at("11", 0.28)
    for hand in (h.left, h.right):
        for frame, hide in ((1, False), (hidden[0], True), (hidden[1], False)):
            hand.hide_render = hide
            hand.keyframe_insert("hide_render", frame=frame)
    key(h.root, "location", (0, -2.0, 0), dive1 + 1)                  # already inside the cell: the hands leave


def flash(cam, tl):
    """Amber flash on the lens at the instant the camera crosses the skin."""
    mat, power = kit.keyed_emission("Flash", "#E0761C", "#E0761C", 0.0)
    mat.surface_render_method = "BLENDED"
    alpha = kit.principled(mat).inputs["Alpha"]
    card = kit.mesh_object("Flash", [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [(0, 1, 2, 3)], [mat],
                           (0, 0, -0.06))
    card.parent = cam
    f = tl.at("11", DIVE)
    for frame, a, p in ((f - 3, 0.0, 0.0), (f, 0.9, 1.2), (f + 3, 0.0, 0.0)):     # short and amber (the cream read as a beige screen)
        key(alpha, "default_value", a, frame)
        key(power, "default_value", p, frame)


def cell_life(s, tl):
    """Mitochondria pulse like a heart until the final pause; there they give one last strong glow and fade out slowly
    (the end of the video: "you'd last about a minute"), and the final question sits over the dark cell."""
    hero = s.cell.hero
    end = tl.at("12") + tl.secs(END_S)
    cm.pulse(hero, tl.at("11", DIVE), end - 10, period=30, peak=3.5)
    for m in s.cell.cell.mitochondria:
        cm.pulse(m, tl.at("11", DIVE), end - 10, period=30, peak=2.5)
    for m in (hero, *s.cell.cell.mitochondria):
        sock = m.glow_socket
        rest = sock.default_value
        key(sock, "default_value", rest, end - 6)
        key(sock, "default_value", 6.0, end)
        key(sock, "default_value", 0.0, end + tl.secs(1.4))
    cm.blink_away(hero.parts.atp, tl.at("12", 0.2), tl.at("12", 1.0) - tl.at("12", 0.2))


# ---------- camera ----------

def camera_path(tl):
    """(frame, position, target). Pairs at the same instant (frame and frame+1) are hard cuts."""
    c, hero = bs.CELL, bs.CELL + bs.HERO_MITO
    kx, ky, kh, _ = land.KNOLL
    top = Vector((kx, ky + 6, land.ground_z(kx, ky + 6) + EYE))           # north edge of the top: the hill drops away ahead
    cow = Vector((bs.COW_X, bs.COWS_Y[0], 1.0))
    bay = Vector((bs.BAY[0], bs.BAY[1] + 0.3, 0.6))
    porch = 0.5 + EYE
    return [
        (1, (0, 0.2, porch), (0, 16, 2.4)),                                   # edge of the porch: ceiling out of frame
        (tl.at("02", 0.0), (0, 0.28, porch), (0, 16, 2.2)),
        (tl.at("02", 0.78), (0, 0.36, porch), (0, 16, 2.0)),
        (tl.at("03", 0.1), (0, 1.7, EYE + 0.05), (0, 16, 2.0)),
        (tl.at("03", 0.75), (0.2, 8.5, EYE), (0, 18, 1.8)),
        (tl.at("04", 0.2), (0.4, 14.8, EYE), (-2.0, 21, 1.2)),
        (tl.at("04", 0.6), (0.6, 17.0, EYE), (bs.COW_X, 20.5, 0.9)),
        (tl.at("04", 1.0), (0.2, 18.2, EYE), (bs.COW_X, 19.6, 0.9)),
        (tl.at("05", 0.18), (-1.5, 19.6, 1.5), tuple(cow)),
        (tl.at("05", 0.55), (-1.75, 19.35, 1.42), tuple(cow)),
        (tl.at("05", 0.75), (0.4, 23.0, EYE), (0.2, 30, 1.5)),               # central aisle, away from the posts
        (tl.at("06", 0.0), (0.2, 26.6, EYE), (0.3, 31, 1.4)),
        (tl.at("06", 0.1), (0.4, 28.6, EYE), (0.6, 33, 1.3)),                 # through the middle of the door, looking ahead
        (tl.at("06", 0.25), (3.6, 29.1, EYE), tuple(bay)),                    # facing the stall opening
        (tl.at("06", 1.0) - 1, (4.5, 29.3, EYE), tuple(bay)),                 # (walls at x = 3 and 7, from y 30 to 34)
        (tl.at("07", 0.0), (2.0, 38.4, EYE), (2, 100, 4)),                    # cut: six months later, at the fence
        (tl.at("07", 1.0), (2.8, 38.4, EYE), (-12, 100, 5)),
        (tl.at("08", 0.35), (3.6, 38.3, EYE), (40, 40, 2.0)),
        (tl.at("08", 1.0) - 1, (4.0, 38.2, EYE), (230, 95, 26)),
        (tl.at("09", 0.0), tuple(top), (kx, 220, -42)),                       # cut: top of the hillock
        (tl.at("09", 1.0), tuple(top + Vector((0, 1.5, -0.3))), (kx, 220, -42)),
        (tl.at("10", 0.35), tuple(top + Vector((0, 1.8, -0.35))), (kx + 40, 220, -40)),
        (tl.at("10", 1.0), tuple(top + Vector((0, 1.8, -0.35))), (150, 135, -30)),
        (tl.at("11", DIVE), tuple(top + Vector((0, 1.8, -0.35))), (150, 135, -36)),
        (tl.at("11", DIVE) + 1, tuple(hero + Vector((0, -14, 2.5))), tuple(hero)),  # cut: inside the cell
        (tl.at("12", 0.0), tuple(hero + Vector((-1.0, -5.0, 2.4))), tuple(hero)),
        (tl.frames + 1, tuple(hero + Vector((4.0, -3.5, 2.6))), tuple(hero)),
    ]


def build_camera(tl):
    data = bpy.data.cameras.new("Eye")
    data.lens = LENS
    data.clip_start, data.clip_end = 0.02, 4000.0
    cam = bpy.data.objects.new("Eye", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    path = camera_path(tl)
    cuts = {fb for (fa_, _, _), (fb, _, _) in zip(path, path[1:]) if fb - fa_ <= 1}
    rnd = random.Random(7)

    def pose(f):
        for (fa_, pa, ta), (fb, pb, tb) in zip(path, path[1:]):
            if fa_ <= f <= fb:
                u = (f - fa_) / max(fb - fa_, 1)
                u = u * u * (3 - 2 * u)
                return Vector(pa).lerp(Vector(pb), u), Vector(ta).lerp(Vector(tb), u)
        return Vector(path[-1][1]), Vector(path[-1][2])

    prev = None
    frames = sorted({*range(1, tl.frames + 2, 3), *[p[0] for p in path], *[f - 1 for f in cuts]})
    for f in frames:
        pos, target = pose(f)
        sway = 0.0 if f >= tl.at("11", DIVE) else 1.0                      # in the cell, the camera floats smoothly
        pos = pos + Vector((rnd.uniform(-0.012, 0.012), rnd.uniform(-0.012, 0.012), rnd.uniform(-0.01, 0.01))) * sway
        q = (target - pos).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location = pos
        cam.rotation_quaternion = q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
    return cam


# ---------- everything ----------

def build(tl):
    rnd = random.Random(42)
    w = hs.build_world()
    s = bs.build(rnd)
    cam = build_camera(tl)
    h = cm.hands(cam)
    fill = bpy.data.objects.new("HandFill", bpy.data.lights.new("HandFill", "POINT"))
    fill.data.energy, fill.data.color, fill.data.shadow_soft_size = 25.0, (1.0, 0.8, 0.6), 0.3
    fill.location, fill.parent = (0.25, 0.3, 0.05), cam                    # warm light only on the hands (dawn)
    bpy.context.collection.objects.link(fill)
    sky(w, tl)
    animate_cows(s.farm, tl, rnd)
    xray(s.farm, tl)
    manure(s.farm, tl, rnd)
    seasons(s.land, tl)
    bacteria(s, h, tl, rnd)
    hands_track(h, tl)
    flash(cam, tl)
    cell_life(s, tl)
    wheel = s.farm.mill.wheel
    key(wheel, "rotation_euler", (0, 0, 0), 1)
    key(wheel, "rotation_euler", (0, tl.frames / 30 * 2.0, 0), tl.frames)
    for fc in wheel.animation_data.action.fcurves if hasattr(wheel.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


kit.run(build)
