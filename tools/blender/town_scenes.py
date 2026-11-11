"""Content of scenes 04 to 12 of technology-disappeared (people, animals and effects of each time window).
Each function returns the objects for the per-scene on/off (the main script calls visible())."""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import cell_models as cm
import kit
import rigs
import town_cast as tc
import town_props as tp
import town_set as ts
from kit import key


def secs(tl, sid, s):
    return tl.at(sid) + tl.secs(s)


def span(tl, sid, pad=2):
    return list(range(tl.at(sid) - pad, tl.at(sid, 1.0) + pad))


def objs_of(*rigs_):
    return [o for r in rigs_ for o in rigs.all_objects(r)]


# ---------- 04: people on the street looking at the sky ----------

CROWD = (("man", -1.6, 19.0, 80), ("woman", 1.2, 21.5, 100), ("man", 3.4, 17.5, 120), ("woman", -4.0, 23.5, 70),
         ("man", 2.2, 26.0, 95), ("woman", -0.6, 28.5, 85), ("man", 4.6, 24.0, 135), ("woman", -3.0, 16.0, 60),
         ("man", 0.4, 33.0, 90))


def crowd(tl):
    frames = span(tl, "04") + span(tl, "05")[2:]
    frames = list(range(frames[0], frames[-1] + 1))
    out = []
    for k, (key_, x, y, hdg) in enumerate(CROWD):
        r = tc.person(key_, f"Crowd{k}", (1.78 if key_ == "man" else 1.65) + 0.04 * ((k * 5) % 3 - 1), k + 2,
                      location=(x, y, 0.0), heading=math.radians(hdg))
        rigs.loop(r, "Idle", frames[0], frames[-1], phase=0.17 * k)
        tc.look_up(r, frames, pitch=26 + 6 * (k % 3), yaw=(-12, 8, 0)[k % 3], seed=k)
        if k in (1, 4):
            tc.pointer(r)
        out.append(r)
    return objs_of(*out)


# ---------- 06: torneira ----------

KITCHEN_T = dict(step=(0.35, 0.75), reach=(0.35, 0.8), turn=(0.85, 1.2), trickle=(0.95, 1.45), drops=(1.6, 2.15),
                 release=(2.4, 2.85))          # seconds in scene 06 ("your tap runs dry" from 0.6 to 1.4 s)


def _smooth(t, a, b):
    u = min(max((t - a) / (b - a), 0.0), 1.0)
    return u * u * (3 - 2 * u)


def kitchen_pov(h, kt, tl):
    """The camera's right hand (the same as in scenes 01-03) rises from the bottom edge, grabs the top lever, turns 45 deg
    and goes back down (28 deg turn). The grab pose is computed in the world (on the lever) and carried to camera space frame by
    frame; the lever turns with it."""
    from mathutils import Euler, Matrix
    import town_interiors as ti
    hand, root = h.right, h.root
    scene = bpy.context.scene
    piv = Vector(kt.lever.location)
    r_hand = Euler((math.radians(-10), math.radians(180), math.radians(4)), "XYZ").to_matrix().to_4x4()
    grip = Matrix.Translation((0.0, -0.27, 0.075))
    T = KITCHEN_T
    a0, a1 = tl.at("06"), tl.at("06", 1.0)
    prev = None
    for f in range(a0, a1 + 1):
        t = (f - a0) / tl.fps
        ang = math.radians(28) * _smooth(t, *T["turn"])
        w = _smooth(t, *T["reach"]) * (1 - _smooth(t, *T["release"]))
        world = ti.KITCHEN_M @ Matrix.Translation(piv) @ Matrix.Rotation(ang, 4, "Z") @ grip @ r_hand
        scene.frame_set(f)
        local = root.matrix_world.inverted() @ world
        loc_g, rot_g, _ = local.decompose()
        loc_a = loc_g + Vector((0.14, -0.45, 0.1))                     # below the frame and close to the lens
        rot = rot_g
        loc = loc_a.lerp(loc_g, w)
        eul = rot.to_euler("XYZ", prev) if prev else rot.to_euler("XYZ")
        prev = eul
        hand.location = loc
        hand.rotation_euler = eul
        hand.keyframe_insert("location", frame=f)
        hand.keyframe_insert("rotation_euler", frame=f)
        kt.lever.rotation_euler = (0, 0, ang)
        kt.lever.keyframe_insert("rotation_euler", frame=f)
    return []


def drops(kt, tl):
    """A weak stream that thins out (KITCHEN_T trickle) and two last drops (KITCHEN_T drops) falling into the basin."""
    import town_interiors as ti
    water = ts.mat("Water", "#CFE6F7", rough=0.1)
    tip = kt.tip
    bottom = ti.COUNTER_Z - ti.SINK_DEPTH + 0.02
    stream_geo = kit._prism_geo(6, 0.006, 0.006, tip.z - bottom, oz=-(tip.z - bottom))
    stream = kit.mesh_object("WaterStream", *stream_geo, [water])
    stream.parent = kt.root
    stream.location = tip
    s0, s1 = secs(tl, "06", KITCHEN_T["trickle"][0]), secs(tl, "06", KITCHEN_T["trickle"][1])
    for f, sc in ((1, 0.0), (s0, 0.0), (s0 + 4, 1.0), (s1 - 6, 0.6), (s1, 0.0)):
        key(stream, "scale", (sc, sc, 1.0 if sc > 0 else 0.0), f)
    out = [stream]
    for k, t0 in enumerate(KITCHEN_T["drops"]):
        drop = kit.mesh_object(f"Drop{k}", *kit._gem_geo(0.011, stretch=1.5), [water])
        drop.parent = kt.root
        f0 = secs(tl, "06", t0)
        fall = math.sqrt(2 * (tip.z - bottom) / 9.8) * 30
        for f in range(1, int(f0 + fall + 8)):
            if f < f0 - 10:
                p, sc = tip, 0.0
            elif f < f0:
                p, sc = tip + Vector((0, 0, -0.004)), (f - f0 + 10) / 10        # the drop swells at the mouth of the spout
            elif f <= f0 + fall:
                tt = (f - f0) / 30
                p, sc = tip + Vector((0, 0, -0.5 * 9.8 * tt * tt)), 1.0
            else:
                p, sc = Vector((tip.x, tip.y, bottom + 0.01)), max(0.0, 1 - (f - f0 - fall) / 6) * 1.6
            drop.location = p
            drop.scale = (sc, sc, sc * (0.6 if f > f0 + fall else 1.0))
            drop.keyframe_insert("location", frame=f)
            drop.keyframe_insert("scale", frame=f)
        out.append(drop)
    return out


# ---------- 08: food on foot, by bicycle, by horse ----------

def foot_traffic(tl):
    frames = span(tl, "08", 4)
    speed, hdg = 1.15, -math.pi / 2
    out = []
    a = tc.person("man", "Carrier0", 1.8, 3, heading=hdg)
    tc.walk_line(a, frames, (4.4, 44.6), hdg, speed, 0.1)        # passes large, close to the camera
    tc.sack_carrier(a, tp.sack("Carrier0Sack"))
    b = tc.person("woman", "Biker", 1.66, 6, heading=hdg)
    tc.walk_line(b, frames, (2.7, 47.8), hdg, speed, 0.55)
    bike, wheels, grips = tp.bicycle("Bike")
    tc.bike_pusher(b, bike, grips)
    spin(wheels, frames, speed)
    c = tc.person("woman", "Carrier1", 1.62, 4, heading=hdg)
    tc.walk_line(c, frames, (-3.6, 54.0), hdg, speed, 0.8)
    tc.sack_carrier(c, tp.sack("Carrier1Sack", color="#A8946C"))
    lead, horse, rope = horse_and_leader(frames, (-0.9, 50.2), hdg, speed, "Lead8", 1)
    out = [a, b, c, lead]
    return objs_of(*out) + objs_of(horse) + [rope]


def spin(wheels, frames, speed):
    for w, r in wheels:
        for f in (frames[0], frames[-1]):
            w.rotation_euler.x = -speed * (f - frames[0]) / 30 / r
            w.keyframe_insert("rotation_euler", frame=f)
        tc._linear_all(w)


def horse_and_leader(frames, lead_xy, hdg, speed, name, k):
    """Person in front pulling the horse by the rein (rope stretched from hand to halter); both at the same pace."""
    lead = tc.person("man", name, 1.76, k + 7, heading=hdg)
    tc.walk_line(lead, frames, lead_xy, hdg, speed, 0.3)
    d = Vector((math.cos(hdg), math.sin(hdg), 0))
    side = Vector((-d.y, d.x, 0))
    hx = Vector(lead_xy) - d.xy * 2.1 - side.xy * 0.7
    horse = rigs.spawn("horse", f"{name}Horse", length=2.7, heading=hdg)
    tc.walk_line(horse, frames, tuple(hx), hdg, speed, 0.0, feet=tc.HORSE_FEET)
    sh = tc.bone_local(lead, "UpperArm.R", frames[0])
    hand, _ = tc.hold(lead, "R", lead.root, sh + Vector((-0.12, 0.22, -0.55)), sh + Vector((-0.4, -0.2, -0.3)))
    halter = tc.empty(f"{name}Halter", horse.arm, (0, 0, 0))
    halter.parent_type = "BONE"
    halter.parent_bone = "Head"
    halter.location = (0, 0, 0)
    rope = tp.rope(f"{name}Rope", hand, halter)
    return lead, horse, rope


# ---------- 09: the street became a garden ----------

def farm_life(tl):
    frames = span(tl, "09", 4)
    out = []
    for k, (x, y, hdg, who) in enumerate(((4.7, 17.5, math.pi, "man"), (-4.8, 23.5, 0.0, "woman"),
                                          (2.45, 29.5, math.pi, "woman"), (-2.45, 35.5, 0.2, "man"))):
        r = tc.person(who, f"Digger{k}", 1.74 if who == "man" else 1.64, k + 9, location=(x, y, 0.29),
                      heading=hdg)
        rigs.loop(r, "Idle", frames[0], frames[-1], phase=0.2 * k)
        tc.hoe_worker(r, tp.hoe(f"Hoe{k}") if k != 3 else tp.shovel(f"Shovel{k}"), frames, period=42 + 5 * k,
                      phase=0.27 * k)
        out.append(r)
    hdg, speed = -math.pi / 2, 1.05
    lead, horse, rope = horse_and_leader(frames, (-0.1, 18.9), hdg, speed, "Lead9", 2)   # passes beside the camera
    body = tp.cart("Cart")
    body.parent = horse.root
    body.location = (0.0, 2.75, 0.0)                     # behind the horse (the horse faces -y at the root)
    body.rotation_euler = (0, 0, math.pi)
    wheels = [(c, 0.6) for c in body.children if c.name.startswith("CartWheel")]
    spin(wheels, frames, speed)
    return objs_of(*out, lead) + objs_of(horse) + [rope] + [body, *body.children_recursive]


# ---------- 11: the flaked stone in the hand ----------

STONE_POSE = ((0.03, -0.05, -0.37), (-52, -4, 8))     # hand above the caption


def stone_hand(h, tl):
    hand = h.right
    stone = tp.chipped_stone("ChippedStone")
    stone.parent = hand
    stone.location = (0.0, 0.06, 0.03)
    stone.rotation_euler = (0, 0, math.radians(20))
    s = h.scale
    a, b = tl.at("11"), tl.at("11", 1.0)
    for f, roll, yaw in ((a, -18, 6), (a + (b - a) // 2, 14, -4), (b, -10, 8)):
        loc, rot = STONE_POSE
        hand.location = Vector(loc) * s
        hand.rotation_euler = (math.radians(rot[0]), math.radians(rot[1] + roll), math.radians(rot[2] + yaw))
        hand.keyframe_insert("location", frame=f)
        hand.keyframe_insert("rotation_euler", frame=f)
    glint = bpy.data.lights.new("LastLight", "POINT")
    glint.energy, glint.color, glint.shadow_soft_size = 16.0, (1.0, 0.62, 0.3), 0.2
    glint.use_shadow = False
    go = bpy.data.objects.new("LastLight", glint)
    bpy.context.collection.objects.link(go)
    go.parent = h.root.parent
    go.location = (-0.45, 0.05, -0.15)                    # the amber sunset light catches the edge from the left
    return [stone, go]


# ---------- 12: the fire ----------

FIRE_PERSON = (0.7, 31.0)


def fire_scene(tl, rnd):
    frames = span(tl, "12", 4)
    strikes = [secs(tl, "12", t) for t in (2.6, 3.4, 4.2, 5.0)]
    catch = secs(tl, "12", 5.25)
    r = tc.person("man", "FireMaker", 1.76, 11, location=(*FIRE_PERSON, 0.0), heading=-math.pi / 2)
    tc.segment(r, "Sitting", frames[0], frames[-1], 30, 190)
    flint, knife = tp.flint("Flint"), tp.knife("Knife")
    tc.fire_starter(r, flint, knife, frames, strikes)
    spot = Vector(FIRE_PERSON + (0.0,)) + tc.FIRE_SPOT
    pile = tp.tinder("Tinder", rnd)
    pile.location = spot
    out = objs_of(r) + [flint, knife, pile]
    out += sparks(tl, strikes, spot, rnd)
    out += flame(tl, catch, spot, rnd)
    return out


def sparks(tl, strikes, spot, rnd):
    out = []
    for k, f in enumerate(strikes):
        c = spot + Vector((0.12, 0.05, 0.42))
        s = cm.specks_in_air(f"Spark{k}", tuple(c), 0.05, 34 + 6 * k, rnd, gem=(0.02, 0.035), rise=(-0.45, -0.2),
                             drift=0.35, strength=8.0, color="#FFB347")
        for frame, a in ((1, 0.0), (f, 0.0), (f + 1, 1.0)):
            key(s.alpha_socket, "default_value", a, frame)
        cm.blink_away(s, f + 1, 12)
        s.obj.visible_shadow = False
        out.append(s.obj)
    return out


def flame(tl, catch, spot, rnd):
    """Ember (before), faceted flame in three layers that grows in ~1 s and flickers softly (sum of sines), orange
    light that rises in 6 frames and a light little smoke rising."""
    # tongues of fire: 4 outer orange, 3 amber, 2 light cores, each in its own phase (wide base, tips)
    tongues = [("#E0611C", 0.07, 0.34, a, 0.07) for a in (0.3, 1.9, 3.5, 5.0)] +               [("#F5A524", 0.05, 0.26, a, 0.035) for a in (1.0, 3.0, 5.2)] + [("#FFE2A8", 0.03, 0.15, a, 0.01) for a in (0.0, 3.1)]
    out = []
    for k, (color, r, h, ang, off) in enumerate(tongues):
        m = ts.mat(f"Flame{color}", color, emission=color, strength={"#E0611C": 2.5, "#F5A524": 3.5}.get(color, 5.0))
        geo = kit._gem_geo(r, stretch=h / r)
        o = kit.mesh_object(f"FlameCore{k}", *geo, [m])
        o.location = spot + Vector((off * math.cos(ang), off * math.sin(ang), 0.05 + h * 0.5))
        o.rotation_euler = (0.25 * math.sin(ang) * off * 10, 0.25 * math.cos(ang) * off * 10, ang)
        o.visible_shadow = False
        for f in range(1, tl.frames + 2, 2):
            if f < catch:
                sc = 0.0
            else:
                u = min((f - catch - 2 * (k % 4)) / 15, 1.0)    # ~0.5 s to catch, tongue by tongue
                grow = 1 - (1 - max(u, 0.0)) ** 2
                w = 1 + 0.12 * math.sin(f * 0.9 + 1.7 * k) + 0.07 * math.sin(f * 1.7 + 2 * k)
                sc = grow * w
            sc = max(sc, 0.001)                              # scale 0 leaves the rotation undefined
            o.scale = (sc, sc, sc * (1 + 0.18 * math.sin(f * 1.3 + 2.3 * k)))
            o.keyframe_insert("scale", frame=f)
        tc._linear_all(o)
        out.append(o)
    ember = kit.mesh_object("Ember", *kit._gem_geo(0.035, stretch=0.6), [ts.mat("Ember", "#E0611C", emission="#E0611C", strength=3.0)])
    ember.location = spot + Vector((0, 0, 0.05))
    ember.visible_shadow = False
    for f, sc in ((1, 0.0), (catch - 26, 0.0), (catch - 18, 0.6), (catch, 1.0)):
        key(ember, "scale", (sc, sc, sc), f)
    out.append(ember)
    light = bpy.data.lights.new("FireLight", "POINT")
    light.color, light.shadow_soft_size = (1.0, 0.55, 0.25), 0.15
    light.use_custom_distance, light.cutoff_distance = True, 9.0      # does not light up background windows
    lo = bpy.data.objects.new("FireLight", light)
    bpy.context.collection.objects.link(lo)
    lo.location = spot + Vector((0, 0, 0.35))
    for f in range(1, tl.frames + 2, 2):
        if f < catch - 18:
            e = 0.0
        elif f < catch:
            e = 4.0 * (f - catch + 18) / 18                    # ember
        else:
            u = min((f - catch) / 15, 1.0)
            e = 4.0 + 76.0 * u * (1 + 0.1 * math.sin(f * 0.8) + 0.06 * math.sin(f * 1.9))
        light.energy = e
        light.keyframe_insert("energy", frame=f)
    out.append(lo)
    smoke_m = ts.mat("Smoke", "#7E8796")
    for k in range(6):
        p = kit.mesh_object(f"FireSmoke{k}", *kit._gem_geo(0.018, stretch=4.0), [smoke_m])
        p.visible_shadow = False
        t0 = catch + 10 + k * 14
        for f in range(1, tl.frames + 2, 2):
            u = (f - t0) / 60
            if u < 0 or u > 1:
                sc, z = 0.0, 0.5
            else:
                sc, z = math.sin(math.pi * u) * (1 - 0.4 * u), 0.5 + 0.8 * u
            p.location = spot + Vector((0.04 * math.sin(k + f * 0.06), 0.015 * (k % 3), z))
            p.scale = (sc, sc, sc)
            p.keyframe_insert("location", frame=f)
            p.keyframe_insert("scale", frame=f)
        tc._linear_all(p)
        out.append(p)
    return out


def darken(cam, tl, start_s, end_s, amount=0.75):
    """The image darkens slightly in the final pause (black card in front of the lens, alpha in a slow ramp)."""
    m = ts.mat("EndFade", "#000000")
    kit.principled(m).inputs["Alpha"].default_value = 0.0
    m.surface_render_method = "BLENDED"
    card = kit.mesh_object("EndFade", [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [(0, 1, 2, 3)], [m],
                           (0, 0, -0.05))
    card.parent = cam
    card.visible_shadow = False
    alpha = kit.principled(m).inputs["Alpha"]
    f0 = secs(tl, "12", start_s)
    for f, a in ((1, 0.0), (f0, 0.0), (secs(tl, "12", end_s), amount), (tl.frames, amount)):
        key(alpha, "default_value", a, f)
    return card
