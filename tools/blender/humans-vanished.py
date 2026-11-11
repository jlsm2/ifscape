"""Continuous animation for the humans-vanished script: a street corner seen from above, ten thousand years.

Run by 'python -m ifscape blender scripts/humans-vanished.json'. Each change happens inside
its scene's time window (timeline.json). Panoramic (drone) camera.
The time jumps have a "time-lapse": the sky flickers between day and night, faster at each jump.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import humans_set as hs  # noqa: E402
import kit  # noqa: E402
import traffic  # noqa: E402
from kit import color_ramp_socket, grow, key, lin, ramp, switch_off, vanish  # noqa: E402

NIGHT = {"sky": 1.0, "ambient": 1.6, "sun": 1.2, "day": 0.0, "stars": 1.0}
DAY = {"sky": 1.0, "ambient": 1.3, "sun": 3.5, "day": 1.0, "stars": 0.0}


# ---------- sky ----------

def world_owners(w):
    return {"sky": (w.sky, "default_value"), "ambient": (w.ambient, "default_value"), "sun": (w.sun, "energy"),
            "day": (w.day, "default_value"), "stars": (w.stars, "default_value")}


def set_sky(w, state, frame):
    for name, (owner, attr) in world_owners(w).items():
        key(owner, attr, state[name], frame)


def timelapse(w, f0, f1, cycles, end=NIGHT, start=NIGHT):
    """Sky alternating day and night between f0 and f1: the visual sign that time jumped."""
    step = (f1 - f0) / cycles
    set_sky(w, start, f0)
    for i in range(cycles):
        set_sky(w, DAY, int(f0 + step * (i + 0.5)))
        set_sky(w, NIGHT if i < cycles - 1 else end, int(f0 + step * (i + 1)))


# ---------- small explosions: sparks and dust ----------

_SPARK = None


def spark_mesh():
    global _SPARK
    if _SPARK is None:
        v, f = kit._box_geo(0.12, 0.12, 0.12, -0.06, -0.06, -0.06)
        _SPARK = bpy.data.meshes.new("Spark")
        _SPARK.from_pydata(v, [], f)
        _SPARK.materials.append(kit.flat("SparkMat", kit.LUZ, emission=kit.LUZ, strength=8.0))
    return _SPARK


def burst(rnd, pos, frame, count, spread, rise, life):
    """Amber sparks that leave 'pos' and vanish."""
    for _ in range(count):
        s = kit.instance("Spark", spark_mesh(), pos)
        target = (pos[0] + rnd.uniform(-spread, spread), pos[1] + rnd.uniform(-spread, spread),
                  pos[2] + rnd.uniform(0.3, rise))
        key(s, "scale", (0, 0, 0), 1)
        key(s, "scale", (0, 0, 0), max(1, frame - 1))
        key(s, "scale", (1, 1, 1), frame)
        key(s, "location", pos, frame)
        key(s, "location", target, frame + life)
        key(s, "scale", (0, 0, 0), frame + life)


def dust_cloud(rnd, pos, frame, count, size, spread, rise, life):
    for _ in range(count):
        p = hs.puff("Dust", (pos[0] + rnd.uniform(-spread, spread), pos[1] + rnd.uniform(-spread, spread), pos[2]),
                    size * rnd.uniform(0.6, 1.2))
        grow(p, frame, frame + int(life * 0.3), target=rnd.uniform(1.0, 1.6))
        loc = tuple(p.location)
        key(p, "location", loc, frame)
        key(p, "location", (loc[0], loc[1], loc[2] + rise * rnd.uniform(0.6, 1.2)), frame + life)
        vanish(p, frame + int(life * 0.5), frame + life)


# ---------- first seconds: people and cars ----------

def animate_people(s, tl, rnd):
    v0 = vanish_start(tl)
    for p in s.people:
        x0, y0 = p.start
        vf = vanish_frame(v0, x0, y0)
        fx, fy = traffic.forward(p.heading)
        for f in range(1, vf + 1, 3):
            t = (f - 1) / tl.fps
            x, y = x0 + fx * p.speed * t, y0 + fy * p.speed * t
            bob = 0.035 * abs(math.sin(t * p.speed * 5.5))
            key(p.obj, "location", (x, y, hs.surface_z(x, y) + bob), f)
        pos = tuple(p.obj.location)
        key(p.flash, "default_value", 0.0, 1)
        key(p.flash, "default_value", 0.0, vf - 4)
        key(p.flash, "default_value", 14.0, vf)
        key(p.obj, "scale", (1, 1, 1), 1)
        key(p.obj, "scale", (1, 1, 1), vf - 1)
        key(p.obj, "scale", (0.55, 0.55, 1.35), vf + 2)
        key(p.obj, "scale", (0, 0, 0), vf + 6)
        burst(rnd, (pos[0], pos[1], pos[2] + 1.0), vf + 2, 10, 1.0, 2.4, 20)


def simulate_traffic(tl):
    vanish_t = (vanish_start(tl) - 1) / tl.fps
    cars, obstacles = traffic.scenario(vanish_t)
    seconds = (tl.at("04", 1.0) - 1) / tl.fps
    tracks, events = traffic.simulate(cars, obstacles, seconds)
    bad = traffic.audit(tracks)
    if bad:
        print(f"aviso: carros sobrepostos {bad}")
    return tracks, events


def vanish_start(tl):
    """The vanishing happens in the first second, with the question still on screen (first-second rule)."""
    return tl.at("01", 0.35)


def vanish_frame(v0, x, y):
    return v0 + int(min(math.hypot(x, y), 45) / 45 * 36)    # vanishing wave starting from the intersection


STATIC_BLOCKS = [                                    # (x0, x1, y0, y1) of solid objects on the sidewalk
    (hs.STAIR[0] - 0.3, hs.STAIR[1] + 0.3, hs.STAIR[2] - 0.5, hs.STAIR[3] + 0.3),
    (hs.STATUE_XY[0] - 1.4, hs.STATUE_XY[0] + 1.4, hs.STATUE_XY[1] - 1.4, hs.STATUE_XY[1] + 1.4),
    (-10.9, -10.1, -23.0, -21.0), (-10.8, -10.0, -18.0, -13.6), (10.0, 10.8, -16.4, -15.6),
    (8.9, 11.0, 30.8, 41.2),                          # cafe tables and window
]
STATIC_POINTS = [hs.HYDRANT_XY, (-7.6, 26.0), (-7.7, 5.7), (-7.6, 20), (7.6, -14), (-7.6, 46), (7.6, 34), (-7.6, -10)]


def person_checker(tl, tracks):
    """Approves a pedestrian's route only if, until they vanish, it does not cross a car, another person or an object."""
    from traffic import corners
    v0 = vanish_start(tl)
    accepted = []

    def inside(px, py, poly):
        sign = None
        for i in range(4):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
            c = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
            if sign is None:
                sign = c > 0
            elif (c > 0) != sign:
                return False
        return True

    def ok(x0, y0, heading, speed):
        fx, fy = traffic.forward(heading)
        vf = vanish_frame(v0, x0, y0)
        samples = []
        for f in range(1, vf + 1, 3):
            t = (f - 1) / tl.fps
            x, y = x0 + fx * speed * t, y0 + fy * speed * t
            if any(a < x < b and c < y < d for a, b, c, d in STATIC_BLOCKS):
                return False
            if any(math.hypot(x - px, y - py) < 0.55 for px, py in STATIC_POINTS):
                return False
            if abs(x) > hs.EDGE - 0.3 and abs(y) > hs.STREET_HALF + hs.SIDEWALK - 0.3:
                return False                           # would enter a building
            for track in tracks.values():
                if f - 1 < len(track):
                    cx, cy, ch = track[f - 1]
                    if abs(cx - x) < 4 and abs(cy - y) < 4 and inside(x, y, corners(cx, cy, ch, margin=0.45)):
                        return False
            for other in accepted:
                if f in other and math.hypot(other[f][0] - x, other[f][1] - y) < 0.7:
                    return False
            samples.append((f, (x, y)))
        accepted.append(dict(samples))
        return True

    return ok


def animate_cars(s, tl, rnd, tracks, events):
    models = hs.build_cars(list(tracks), rnd)
    for name, track in tracks.items():
        obj = models[name].obj
        for i in range(0, len(track), 2):
            x, y, h = track[i]
            key(obj, "location", (x, y, hs.surface_z(x, y)), i + 1)
            key(obj, "rotation_euler", (0, 0, h), i + 1)
    parked = models["parked"]
    parked.obj.location = (4.4, 24.0, 0.0)
    parked.obj.rotation_euler = (0, 0, math.pi)
    parked.obj.parent = s.ground.slab
    parked.obj.matrix_parent_inverse = s.ground.slab.matrix_world.inverted()
    parked.head.default_value = 0.0
    parked.tail.default_value = 0.0
    for name, m in models.items():
        if name != "parked":
            switch_off(m.head, "default_value", m.head.default_value, tl.at("06", 0.06))
            switch_off(m.tail, "default_value", m.tail.default_value, tl.at("06", 0.06))
    for e in events:
        frame = e["frame"] + 1
        burst(rnd, (e["x"], e["y"], 0.7), frame, 10, 1.6, 1.4, 14)
        dust_cloud(rnd, (e["x"], e["y"], 0.3), frame, 4, 0.5, 0.8, 1.2, 36)
        if "hydrant" in e["cars"]:
            knock_hydrant(s, tl, frame)
    return models


def knock_hydrant(s, tl, frame):
    """The car knocks down the hydrant."""
    h = s.props.hydrant
    key(h, "rotation_euler", (0, 0, 0), 1)
    key(h, "rotation_euler", (0, 0, 0), frame)
    key(h, "rotation_euler", (math.radians(80), 0, math.radians(-30)), frame + 5)


# ---------- night: blackout ----------

def traffic_cycle(t, off):
    phases = (("green", 60, (0.24, 0.86, 0.52)), ("amber", 20, lin(kit.LUZ)[:3]), ("red", 50, (1.0, 0.23, 0.18)))
    for sock in t.lamps.values():
        key(sock, "default_value", 0.0, 1)
    f = 1
    while f < off:
        for name, length, color in phases:
            end = min(f + length, off)
            sock = t.lamps[name]
            key(sock, "default_value", 0.0, max(1, f - 1))
            key(sock, "default_value", 12.0, f)
            key(sock, "default_value", 12.0, end - 1)
            key(sock, "default_value", 0.0, end)
            t.glow.color = color
            t.glow.keyframe_insert("color", frame=f)
            t.glow.keyframe_insert("color", frame=max(f, end - 1))
            f = end
            if f >= off:
                break
    switch_off(t.glow, "energy", t.glow.energy, off)


def blackout(s, tl):
    f0, f1 = tl.at("04", 0.12), tl.at("04", 0.6)
    far = max(b["dist"] for b in s.city) or 1
    for b in s.city:
        closeness = 1 - min(b["dist"] / far, 1)
        power = b["power"].outputs[0]
        switch_off(power, "default_value", power.default_value, int(f0 + closeness * (f1 - f0)), flicker=closeness > 0.7)
    for i, sl in enumerate(s.streetlights):
        frame = tl.at("04", 0.64) + i * 3
        switch_off(sl.head, "default_value", sl.head.default_value, frame, flicker=True)
        switch_off(sl.light, "energy", sl.light.energy, frame, flicker=True)
    switch_off(s.statue.spot, "energy", s.statue.spot.energy, tl.at("04", 0.66), flicker=True)
    switch_off(s.stair.globe, "default_value", s.stair.globe.default_value, tl.at("04", 0.68))
    switch_off(s.stair.glow, "energy", s.stair.glow.energy, tl.at("04", 0.68))
    switch_off(s.cafe.window, "default_value", s.cafe.window.default_value, tl.at("04", 0.62))
    traffic_cycle(s.traffic, tl.at("04", 0.72))


# ---------- buildings collapsing ----------

def collapse(b, f0, rnd, rubble):
    """The top blocks topple and fall in a pile; a broken stump remains. Dust at the base."""
    secs = b["sections"]
    keep = 1 if len(secs) < 4 else 2
    cx, cy = b["center"]
    angle = math.atan2(cy, cx) + rnd.uniform(-0.6, 0.6)   # away from the intersection, never toward the street
    dx, dy = math.cos(angle), math.sin(angle)
    for j, sec in enumerate(secs):
        loc0 = tuple(sec.location)
        if j < keep:
            if j == keep - 1:
                key(sec, "scale", (1, 1, 1), 1)
                key(sec, "scale", (1, 1, 1), f0)
                key(sec, "scale", (1, 1, rnd.uniform(0.5, 0.8)), f0 + 10)
            continue
        start = f0 + (len(secs) - 1 - j) * 2
        drop = j - keep
        target = (loc0[0] + dx * (drop + 1) * rnd.uniform(1.5, 3.0), loc0[1] + dy * (drop + 1) * rnd.uniform(1.5, 3.0),
                  0.5 * drop)
        tilt = math.radians(rnd.uniform(15, 40) if j < len(secs) - 1 else rnd.uniform(50, 80))
        rot = (tilt * dy, -tilt * dx, rnd.uniform(-0.3, 0.3))
        mid = tuple(a + (c - a) * 0.25 for a, c in zip(loc0, target))
        for attr, v0, v1, vm in (("location", loc0, target, mid),
                                 ("rotation_euler", (0, 0, 0), rot, tuple(r * 0.4 for r in rot))):
            key(sec, attr, v0, 1)
            key(sec, attr, v0, start)
            key(sec, attr, vm, start + 6)                  # starts slowly and accelerates (gravity)
            key(sec, attr, v1, start + 11)
        key(sec, "scale", (1, 1, 1), 1)
        key(sec, "scale", (1, 1, 1), start + 10)
        key(sec, "scale", (1, 1, 0.45), start + 13)       # crumples on the ground
        sx, sy = b["size"][0], b["size"][1]
        rubble.append((min(target[0], target[0] - sy) - 2, max(target[0] + sx, target[0] + sy) + 2,
                       min(target[1], target[1] - sx) - 2, max(target[1] + sy, target[1] + sx) + 2))
    dust_cloud(rnd, (cx, cy, 1.0), f0 + 8, 6, 3.0, b["size"][0] * 0.5, 8.0, 50)


def rise_by_steps(water, f0, f1, cross=3):
    """Water rises stopping in the middle of each step and crossing the edge in a few frames.
    Rising slowly and straight, it ran flush with the top of each step and flickered (z-fighting)."""
    x, y, _ = water.location
    levels = [-hs.STAIR_DEPTH + hs.STEP_RISE / 2 + hs.STEP_RISE * k for k in range(hs.STAIR_STEPS + 1)]
    hold = (f1 - f0) / len(levels)
    key(water, "location", (x, y, levels[0]), 1)
    for k, z in enumerate(levels):
        start = int(f0 + k * hold)
        key(water, "location", (x, y, z), start + cross)
        if k + 1 < len(levels):
            key(water, "location", (x, y, z), int(f0 + (k + 1) * hold))


def ride_slab(slab, objs):
    """Cracks and weeds that touch the collapsing stretch sink with the slab (otherwise they float in the hole)."""
    x0, x1, y0, y1 = hs.COLLAPSE
    bpy.context.view_layer.update()
    inverse = slab.matrix_world.inverted()
    for obj in objs:
        # Without the scale: cracks and weeds already have a scale-0 key (they grow later), which would hide the extent.
        mw = Matrix.Translation(obj.location) @ obj.rotation_euler.to_matrix().to_4x4()
        if any(x0 < p.x < x1 and y0 < p.y < y1 for p in (mw @ v.co for v in obj.data.vertices)):
            obj.parent = slab
            obj.matrix_parent_inverse = inverse


def sink(obj, f0, f1, depth):
    """Sinks the block into the ground (covered by the forest), without flattening: toppled blocks do not become blades."""
    loc = tuple(obj.location)
    obj.keyframe_insert("location", frame=f0)
    key(obj, "location", (loc[0], loc[1], loc[2] - depth), f1)


# ---------- panoramic camera ----------

def _on_key_grid(frame):
    """Frame closest to the form 1 + 4k (the grid on which build_camera already puts keys)."""
    return 1 + 4 * round((frame - 1) / 4)


def camera_path(tl, head):
    """(frame, camera position, point it looks at). 38 mm lens: straight buildings, filmed-miniature look.
    The camera only passes over the streets or well above the buildings."""
    px, py = hs.POT_XY
    sx, sy = hs.STATUE_XY
    hx, hy, hz = head
    return [
        (1, (-3, -30, 9), (0, 4, 1.2)),                           # low, close to the people on the crosswalk
        (tl.at("02", 0.0), (-2.5, -27, 8.5), (0, 3, 1.0)),
        (tl.at("02", 0.5), (-3, -31, 12), (0, 0, 0.5)),           # rises while the cars crash
        (tl.at("02", 1.0), (-4, -35, 16), (1, 0, 0)),
        (tl.at("03", 1.0), (-3, -34, 15), (-3, 3, 1)),            # the traffic light still changes
        (tl.at("04", 1.0), (0, -62, 34), (0, 25, 10)),            # the city goes dark: wide, with the horizon
        (tl.at("05", 0.3), (0, 0, 11), (-9.3, 14, 0)),            # the subway stairs flooding
        (tl.at("05", 1.0), (-1, 2, 10), (-8.5, 14.5, 0)),
        (tl.at("06", 0.15), (4, -22, 20), (-1, 1, 0)),            # cracks at the intersection
        (tl.at("06", 1.0), (3, -20, 18), (-1, 2, 0)),
        (tl.at("07", 0.3), (2, -8, 20), (0, 23, 0)),              # the avenue collapses
        (tl.at("07", 1.0), (1, -6, 19), (0, 23, -1)),
        (tl.at("08", 1.0), (3, -2, 16), (0, 23, -2)),
        (tl.at("09", 0.05), (-2, -70, 50), (0, 30, 8)),           # wide open: buildings falling, forest
        (tl.at("09", 0.4), (-2, -55, 42), (0, 25, 5)),
        (tl.at("09", 0.62), (-5.4, 13.0, 1.6), (px, py, 0.15)),   # dive to the pot
        (tl.at("09", 1.0), (-5.6, 13.2, 1.4), (px, py, 0.1)),
        # Rises vertically before heading south: going straight, the low camera crossed what is south
        # of the pot (4 frames of flat screen, QA). Frame on the 4-by-4 grid of the keys
        # (1 + 4k), so as not to change the camera-shake draw in the rest of the video.
        # Leaves the pot heading to the middle of the avenue and turning soon to the northeast (forest). West of the
        # pot there is a toppled building block (x up to -5.2): rising straight, the camera went through it, and
        # rising while looking at the pot it swept the screen like a blue wall. Looking at the ground, the screen filled
        # with flat lawn.
        # The turn is spread over ~30 frames, with the target going from the pot to the forest gradually (in 9
        # frames, with the old target 1.5 m away, the camera turned 15 to 35° per frame: whip, QA).
        (_on_key_grid(tl.at("09", 1.0) + 16), (-2.0, 12.4, 4.0), (px + 2.0, py + 7.0, 1.0)),
        (_on_key_grid(tl.at("09", 1.0) + 32), (0.0, 11.5, 12.0), (5, 25, 4)),
        (tl.at("10", 0.35), (0, -40, 40), (5, 25, 4)),            # rises above the forest
        (tl.at("10", 1.0), (-12, 13, 16), (sx, sy, 2.5)),         # and goes to the clearing
        (tl.at("11", 0.85), (3, 13, 5), (sx, sy, 2.8)),
        (tl.at("12", 0.0), (6.5, 13, 4.2), (hx, hy, hz - 0.1)),
        (tl.at("12", 1.0), (hx - 2.0, hy - 1.7, hz - 0.15), (hx + 0.1, hy, hz - 0.25)),   # three quarters: hand on the chin
    ]


def build_camera(tl, head):
    data = bpy.data.cameras.new("Drone")
    data.lens = 38
    data.shift_y = 0.12                                  # subject slightly below center (caption in the sky)
    cam = bpy.data.objects.new("Drone", data)
    cam.rotation_mode = "QUATERNION"
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    path = camera_path(tl, head)
    rnd = random.Random(7)

    def pose(f):
        for (fa, pa, ta), (fb, pb, tb) in zip(path, path[1:]):
            if fa <= f <= fb:
                u = (f - fa) / max(fb - fa, 1)
                u = u * u * (3 - 2 * u)
                return Vector(pa).lerp(Vector(pb), u), Vector(ta).lerp(Vector(tb), u)
        return Vector(path[-1][1]), Vector(path[-1][2])

    prev = None
    frames = sorted({*range(1, tl.frames + 2, 4), *[p[0] for p in path]})
    for f in frames:
        pos, target = pose(f)
        pos = pos + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(-0.02, 0.02)))
        q = (target - pos).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()                                    # no 360° jumps between keys
        prev = q
        cam.location = pos
        cam.rotation_quaternion = q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
    key(data, "lens", 38.0, 1)
    ramp(data, "lens", 38.0, 55.0, tl.at("12", 0.0), tl.at("12", 1.0))


# ---------- whole timeline ----------

def urban_parts(s):
    parts = list(s.stair.parts) + list(s.cafe.parts) + list(s.props.parts) + list(s.traffic.parts)
    parts.append(s.props.hydrant)
    for sl in s.streetlights:
        parts += sl.parts
    return parts


def to_hex(rgba):
    def srgb(c):
        return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return "#" + "".join(f"{round(max(0, min(1, srgb(c))) * 255):02X}" for c in rgba[:3])


def animate(s, tl):
    rnd = random.Random(3)
    w = s.world
    set_sky(w, NIGHT, 1)

    # 01-02: the people vanish, the cars crash.
    animate_people(s, tl, rnd)
    cars = animate_cars(s, tl, rnd, *s.traffic_sim)

    # 04: two days later, the city goes dark.
    timelapse(w, tl.at("04", 0.0), tl.at("04", 0.1), 2)
    blackout(s, tl)

    # 05: the water rises up the stairs, step by step.
    rise_by_steps(s.stair.water, tl.at("05", 0.2), tl.at("05", 0.6))

    # 06: six months. The cracks open across the asphalt; weeds in them.
    timelapse(w, tl.at("06", 0.0), tl.at("06", 0.12), 4)
    f0, f1 = tl.at("06", 0.12), tl.at("06", 0.75)
    for group in s.growth.cracks:
        for i, seg in enumerate(group):
            f = int(f0 + (f1 - f0) * i / len(group))
            key(seg, "scale", (1, 0, 1), 1)
            ramp(seg, "scale", (1, 0, 1), (1, 1, 1), f, f + 5)
    for weed in s.growth.weeds:
        a = int(rnd.uniform(tl.at("06", 0.4), tl.at("06", 0.9)))
        grow(weed, a, a + 10)

    # 07: twenty years. Grass, saplings, rust; the avenue collapses into the subway.
    f0, f1 = tl.at("07", 0.0), tl.at("07", 0.18)
    timelapse(w, f0, f1, 6)
    for patch in s.growth.patches:
        a = int(rnd.uniform(f0, f1 - 4))
        grow(patch, a, a + 8)
    first, second = s.forest

    def near_car(tree):
        return any(math.hypot(tree.location.x - cx, tree.location.y - cy) < 3.2 for cx, cy in s.car_final)

    early = [tr for tr in first if not tr["in_building"] and not near_car(tr)]
    for tree in early:
        a = int(rnd.uniform(f0, f1 - 4))
        grow(tree, a, a + 8, target=rnd.uniform(0.25, 0.4))
    for m in cars.values():
        color = tuple(m.paint.default_value)
        key(m.paint, "default_value", color, 1)
        ramp(m.paint, "default_value", color, lin("#5A3A26"), f0, f1)
    color_ramp_socket(s.statue.bronze, hs.BRONZE, "#56603F", f0, f1)
    slab = s.ground.slab
    ride_slab(slab, [seg for group in s.growth.cracks for seg in group] + list(s.growth.weeds))
    loc = tuple(slab.location)
    key(slab, "location", loc, 1)
    key(slab, "rotation_euler", (0, 0, 0), 1)
    key(slab, "location", loc, tl.at("07", 0.5))
    key(slab, "rotation_euler", (0, 0, 0), tl.at("07", 0.5))
    key(slab, "location", (loc[0], loc[1], -0.35), tl.at("07", 0.56))
    key(slab, "rotation_euler", (math.radians(2), 0, 0), tl.at("07", 0.56))
    key(slab, "location", (loc[0], loc[1], -6.6), tl.at("07", 0.74))
    key(slab, "rotation_euler", (math.radians(9), math.radians(-4), 0), tl.at("07", 0.74))
    for puff in s.ground.dust:
        start = int(rnd.uniform(tl.at("07", 0.55), tl.at("07", 0.62)))
        grow(puff, start, start + tl.secs(0.5), target=rnd.uniform(1.0, 1.6))
        p = tuple(puff.location)
        key(puff, "location", p, start)
        key(puff, "location", (p[0], p[1], p[2] + rnd.uniform(1.5, 3.0)), start + tl.secs(2.4))
        vanish(puff, start + tl.secs(1.2), start + tl.secs(2.4))

    # 08: the stream runs again in the hole.
    stream = s.ground.stream
    sl = tuple(stream.location)
    key(stream, "location", sl, 1)
    ramp(stream, "location", sl, (sl[0], sl[1], -0.65), tl.at("08", 0.0), tl.at("08", 0.6))
    for bank in s.ground.banks:                                           # weed banks begin to close in
        key(bank, "scale", (0, 1, 0), 1)
        ramp(bank, "scale", (0, 1, 0), (0.6, 1, 1), tl.at("08", 0.3), tl.at("08", 0.95))

    # 09: five hundred years, by day. The buildings collapse, the forest grows, the pots remain.
    f0, f1 = tl.at("09", 0.0), tl.at("09", 0.15)
    timelapse(w, f0, f1, 8, end=DAY)
    for bank in s.ground.banks:                                           # the weeds close in on the stream banks
        ramp(bank, "scale", (0.6, 1, 1), (1, 1, 1), f0, f1)
    # The subway stairs vanish under soil and weeds in the middle of the time-lapse (swap hidden by the day/night flicker).
    swap = (f0 + f1) // 2
    st = s.stair
    for obj, hidden in ((st.lid, False), (st.water, True)):
        obj.hide_render = not hidden
        obj.keyframe_insert("hide_render", frame=1)
        obj.keyframe_insert("hide_render", frame=swap - 1)
        obj.hide_render = hidden
        obj.keyframe_insert("hide_render", frame=swap)
    for b in s.city:
        ramp(b["glass"].outputs[0], "default_value", 1.0, 0.1, f0, f1)     # ruin: concrete without glass
    near = [b for b in s.city if b["dist"] < 160 and not b["sections"][0].name.startswith("Tower")]
    rubble = []
    for b in near:
        collapse(b, int(rnd.uniform(f0 + 4, tl.at("09", 0.4))), rnd, rubble)

    def blocked(tree):
        x, y = tree.location.x, tree.location.y
        return tree["in_building"] or any(a < x < b_ and c < y < d for a, b_, c, d in rubble)

    early_set = set(early)
    mid = [tr for tr in first + second if tr not in early_set and not blocked(tr)]
    late = [tr for tr in first + second if tr not in early_set and blocked(tr)]
    for tree in early:
        tree.keyframe_insert("scale", frame=f0)
        key(tree, "scale", (rnd.uniform(0.9, 1.3),) * 3, int(rnd.uniform(f0 + 4, f1 + 10)))
    for tree in mid:                                   # cars already gone at f1
        a = int(rnd.uniform(f1, f1 + 8))
        grow(tree, a, a + 10, target=rnd.uniform(0.3, 0.5))
    for part in urban_parts(s):
        vanish(part, int(rnd.uniform(f0, f1 - 4)), f1)
    for m in cars.values():
        vanish(m.obj, int(rnd.uniform(f0, f1 - 4)), f1)
    for mat, color in zip(s.ground.mats, (hs.FOREST_FLOOR, hs.MOSS, hs.MOSS, hs.MOSS)):
        sock = kit.principled(mat).inputs["Base Color"]
        color_ramp_socket(sock, to_hex(sock.default_value), color, f0, f1)
    ramp(s.statue.bronze, "default_value", lin("#56603F"), lin(hs.VERDIGRIS), f0, f1)
    for name, color in (("Plaza", "#3B4A3A"), ("Pedestal", "#56605A")):
        sock = kit.principled(bpy.data.materials[name]).inputs["Base Color"]
        color_ramp_socket(sock, to_hex(sock.default_value), color, f0, f1)
    for part in s.pot:
        grow(part, f1 - 6, f1, target=tuple(part.scale))
    vanish(w.moon, f0, f1)

    # 10: ten thousand years. The stumps and towers vanish into the forest; dusk.
    f0, f1 = tl.at("10", 0.0), tl.at("10", 0.2)
    timelapse(w, f0, f1, 10, start=DAY, end=DAY)
    for b in s.city:
        for sec in b["sections"]:
            sink(sec, f0, f1, b["size"][2] + 30)
    for tree in early + mid:
        tree.keyframe_insert("scale", frame=f0)
        key(tree, "scale", (rnd.uniform(1.1, 1.6),) * 3, int(rnd.uniform(f0 + 4, f1)))
    for tree in late:
        a = int(rnd.uniform(f1, f1 + 10))
        grow(tree, a, a + 12, target=rnd.uniform(1.1, 1.6))
    for walk in s.ground.walks:
        key(walk, "scale", (1, 1, 1), 1)
        ramp(walk, "scale", (1, 1, 1), (1, 1, 0.05), f0, f1)
    for part in s.pot:
        vanish(part, f0, f1)
    d0, d1 = f1, f1 + tl.secs(1.5)
    key(w.dusk, "default_value", 0.0, 1)
    ramp(w.dusk, "default_value", 0.0, 1.0, d0, d1)
    color_ramp_socket(w.ambient_color, "#3A5285", "#6A5A62", d0, d1)
    sun = w.sun_obj
    key(sun, "rotation_euler", tuple(sun.rotation_euler), 1)
    ramp(sun, "rotation_euler", tuple(sun.rotation_euler), (math.radians(76), 0, math.radians(-90)), d0, d1)
    w.sun.keyframe_insert("color", frame=1)
    w.sun.keyframe_insert("color", frame=tl.at("09", 0.0))
    w.sun.color = (1.0, 0.95, 0.88)
    w.sun.keyframe_insert("color", frame=tl.at("09", 0.15))
    w.sun.keyframe_insert("color", frame=d0)
    w.sun.color = (1.0, 0.68, 0.42)
    w.sun.keyframe_insert("color", frame=d1)
    key(w.sun, "energy", DAY["sun"], d0)
    key(w.sun, "energy", 2.6, d1)
    key(w.ambient, "default_value", DAY["ambient"], d0)
    key(w.ambient, "default_value", 2.0, d1)


def build(tl):
    tracks, events = simulate_traffic(tl)
    s = hs.build(person_ok=person_checker(tl, tracks))
    s.traffic_sim = (tracks, events)
    s.car_final = [track[-1][:2] for track in tracks.values()]
    print(f"pedestres aprovados: {len(s.people)}")
    build_camera(tl, s.statue.head)
    animate(s, tl)


kit.run(build)
