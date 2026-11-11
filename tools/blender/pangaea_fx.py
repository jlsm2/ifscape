"""Scene 06 of pangaea-never-split: the asteroid falls on the horizon (~1.5 km from the camera) and the layered explosion.

Recipe tested in tools/blender/examples/fx_explosion.py (docs/blender/effects-and-lighting.md), here at
horizon scale (U = 45x the example, including the debris gravity, so the flight looks the same):
  1. anticipation: the streak lights up in a ramp, the head swells and the sky light rises a bit and recedes before the impact;
  2. flash (F..F+4): white core that bursts and vanishes inside the fire; event light rises in 5 frames;
  3. fireball: faceted blobs boiling (Displace), growing fast and slowing down; the material cools from
     white-yellow to orange and ember and turns into smoke (the same material); the upper ones rise more (mushroom);
  4. shock ring running along the ground + matte, opaque dust that comes with it and vanishes shrinking (no
     translucent bubble), ballistic debris and stretched sparks;
  5. aftermath: smoke mushroom, embers at the base and a wall of dust on the horizon.
No piece casts a shadow; none gets past 60% of the distance to the camera. Dense keys and LINEAR.
Names start with "Impact"/"Asteroid" (the motion audit recognizes the event and the layers by name).
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "examples"))

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

import fx_common as fx  # noqa: E402
import kit  # noqa: E402
from kit import lin  # noqa: E402

E = Vector((160.0, 1500.0, 0.0))       # impact point (on the horizon, north of the camera)
U = 45.0                               # scale relative to the example (16 m from the camera -> 1.5 km)
TAU = 60.0                             # frames for the fire to cool to 37% (the example uses 26; here it is much larger)
SKY_LOW = "#B86A3C"                    # dusk sky color near the horizon (the dust fades into it)
GROW = 1.15                            # fireball bigger than in the example: at 1.5 km it must fill the screen


def heat(f, F):
    """Temperature 0..1: rises in 3 frames, then cools slowly."""
    if f < F:
        return 0.0
    if f < F + 3:
        return (f - F + 1) / 4
    return math.exp(-(f - F - 3) / TAU)


def _shadowless(objs):
    for o in objs:
        o.visible_shadow = False
    return objs


def asteroid(tl, frames, f0, F):
    """Amber streak crossing the sky: lights up in a 5-frame ramp (no pop) and the head swells before the impact."""
    trail_mat, trail_pw = kit.keyed_emission("AsteroidTrail", "#FFD08A", "#FFB04A", 0.0)
    trail = kit.mesh_object("AsteroidTrail", *kit._gem_geo(1.0, stretch=1.0)[:2], [trail_mat])
    trail.scale = (6, 6, 90)
    trail.rotation_euler = (math.radians(-10), math.radians(60), 0)
    start, end = Vector((560, 1300, 520)), Vector((160, 1500, 30))

    def along(f):
        return start.lerp(end, min(max((f - f0) / (F - f0), 0.0), 1.0))

    fx.curve_keys(trail, "location", frames, lambda f: tuple(along(f)))
    fx.curve_keys(trail_pw, "default_value", frames,
                  lambda f: 0.0 if f < f0 or f > F + 3 else 30.0 * min((f - f0 + 1) / 5, 1.0, (F + 4 - f) / 4))
    head_mat, head_pw = kit.keyed_emission("AsteroidHead", "#000000", "#FFC070", 0.0)
    hv, hf = fx.ico(2, 14.0)
    head = fx.flat_obj("AsteroidHead", hv, hf, head_mat)
    fx.curve_keys(head, "location", frames, lambda f: tuple(along(f) + Vector((-40, -10, 40)) * max(1 - (f - f0) / (F - f0), 0)))

    def head_scale(f):
        if f < f0:
            return (0.0, 0.0, 0.0)
        s = 1.0 + 0.8 * fx.ease_in_out((f - (F - 8)) / 8)      # anticipation: swells in the last 8 frames
        s *= min((f - f0 + 1) / 4, 1.0) * max(1 - (f - F) / 3, 0.0) if f > F else min((f - f0 + 1) / 4, 1.0)
        return (s, s, s)

    fx.curve_keys(head, "scale", frames, head_scale)
    fx.curve_keys(head_pw, "default_value", frames,
                  lambda f: 0.0 if f < f0 or f > F else 3.0 * min((f - f0 + 1) / 5, 1.0))
    for o in (trail, head):
        fx.set_interp(o)
    for m in (trail_mat, head_mat):
        fx.set_interp(m.node_tree)
    return _shadowless([trail, head])


def fire_material():
    """Temperature ramp (the example's): cooler facet edge (Layer Weight > Facing), strength 3*h^2.
    In Standard the core cuts to yellow-white and the edge is orange; with no heat only smoke is left."""
    mat = bpy.data.materials.new("ImpactFire")
    nt = mat.node_tree
    n, ln = nt.nodes, nt.links
    p = kit.principled(mat)
    p.inputs["Base Color"].default_value = lin("#6E625A")      # smoke lighter than the dark sky above
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    hv = n.new("ShaderNodeValue")
    hv.name = "Heat"
    info = n.new("ShaderNodeObjectInfo")
    jitter = n.new("ShaderNodeMapRange")
    jitter.inputs["To Min"].default_value, jitter.inputs["To Max"].default_value = 0.8, 1.15
    ln.new(info.outputs["Random"], jitter.inputs["Value"])
    h = n.new("ShaderNodeMath"); h.operation = "MULTIPLY"; h.use_clamp = True
    ln.new(hv.outputs[0], h.inputs[0]); ln.new(jitter.outputs[0], h.inputs[1])
    lw = n.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.45
    rim = n.new("ShaderNodeMath"); rim.operation = "MULTIPLY_ADD"
    rim.inputs[1].default_value = -0.35
    ln.new(lw.outputs["Facing"], rim.inputs[0]); ln.new(h.outputs[0], rim.inputs[2])
    ramp = n.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, lin("#2A0C04")
    els[1].position, els[1].color = 1.0, lin("#FFF2CC")
    for pos, hx in ((0.30, "#B8300A"), (0.55, "#FF5A00"), (0.80, "#FFA830")):
        e = els.new(pos); e.color = lin(hx)
    ln.new(rim.outputs[0], ramp.inputs["Fac"])
    ln.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    sq = n.new("ShaderNodeMath"); sq.operation = "POWER"; sq.inputs[1].default_value = 2.0
    ln.new(rim.outputs[0], sq.inputs[0])
    st = n.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 3.0
    ln.new(sq.outputs[0], st.inputs[0])
    floor = n.new("ShaderNodeMath"); floor.operation = "ADD"; floor.inputs[1].default_value = 0.04
    ln.new(st.outputs[0], floor.inputs[0])                      # the base of the smoke stays a bit warm
    ln.new(floor.outputs[0], p.inputs["Emission Strength"])
    return mat, hv.outputs[0]


def fireball(rnd, frames, F, mat):
    """Core, crown, column and cap: blobs that grow fast, rise and open (mushroom)."""
    tex = bpy.data.textures.new("ImpactBoil", "CLOUDS")
    tex.noise_scale = 0.55
    boil = bpy.data.objects.new("FxBoilDriver", None)       # moving the empty = the surface boils
    bpy.context.collection.objects.link(boil)
    boil.scale = (U, U, U)
    fx.curve_keys(boil, "location", frames, lambda f: (0.0, 0.0, 0.05 * U * f))
    fx.set_interp(boil)
    parts = [(Vector((0, 0, 0)), 2.6, 1.4, 1.0)]                # (offset, radius, rise m/s / U, opening)
    for k in range(8):                                           # coroa
        a = 2 * math.pi * k / 8 + rnd.uniform(-0.2, 0.2)
        parts.append((Vector((math.cos(a) * 1.5, math.sin(a) * 1.1, rnd.uniform(-0.3, 0.6))),
                      rnd.uniform(1.4, 2.0), 1.2, 1.6))
    cap_z, cap_up = 4.2, 3.5
    for k in range(7):                                           # column: rises with the cap, blobs
        frac = (k + 1) / 8                                       # always overlapping (no "string of pearls")
        parts.append((Vector((rnd.uniform(-0.15, 0.15), 0, cap_z * frac)), 1.5 - 0.3 * frac, cap_up * frac, 1.0))
    for k in range(7):                                           # cap
        a = 2 * math.pi * k / 7 + 0.3
        parts.append((Vector((math.cos(a) * 1.3, math.sin(a) * 0.9, cap_z)), rnd.uniform(1.5, 2.1), cap_up, 2.4))
    blobs = []
    for k, (off, size, up, spread_to) in enumerate(parts):
        v, fc = fx.ico(2, 1.0)
        b = fx.flat_obj(f"ImpactSmoke{k}", fx.lumpy(v, seed=k + 1, amount=0.22, squash=0.7), fc, mat, tuple(E))
        d = b.modifiers.new("Boil", "DISPLACE")
        d.texture, d.texture_coords, d.texture_coords_object, d.strength = tex, "OBJECT", boil, 0.35
        delay = 0 if k == 0 else (1 if k < 9 else 2)

        def pos(f, off=off, up=up, spread_to=spread_to, size=size):
            t = max(f - F, 0) / 30
            spread = 1 + (spread_to - 1) * fx.ease_out(t / 2.5)
            o = off * U * GROW
            return tuple(E + Vector((o.x * spread, o.y * spread, (size * 0.5 + off.z) * GROW * U * fx.ease_out(t / 0.6)
                                     + up * U * 0.6 * t)))

        def scl(f, size=size, delay=delay):
            if f < F + delay:
                return (0.0, 0.0, 0.0)
            r = size * U * GROW * (fx.ease_out((f - F - delay) / 16) * 0.85 + 0.15 + 0.004 * (f - F))
            return (r, r, r * 0.9)

        fx.curve_keys(b, "location", frames, pos)
        fx.curve_keys(b, "scale", frames, scl)
        fx.set_interp(b)
        blobs.append(b)
    return _shadowless(blobs)


def flash(frames, F):
    """White core (may go to white: it is the flash) that bursts in 3 frames and vanishes inside the fire."""
    hot = fx.emitter("ImpactCoreMat", "#FFF1D0", 8.0)
    v, fc = fx.ico(1, 1.0)
    core = fx.flat_obj("ImpactCore", fx.lumpy(v, seed=9, amount=0.15), fc, hot, tuple(E + Vector((0, 0, 0.8 * U))))

    def scl(f):
        if f < F:
            return (0.0, 0.0, 0.0)
        if f <= F + 3:
            r = 0.3 + 3.4 * fx.ease_out((f - F) / 4)          # born small: rises in 4 frames
        else:
            r = max(3.7 * (1 - (f - F - 3) / 12), 0.0)
        return (r * U, r * U, r * U * 0.8)

    fx.curve_keys(core, "scale", frames, scl)
    fx.set_interp(core)
    return _shadowless([core])


def event_light(frames, F, end):
    """Event light: an orange sun coming from the impact. Anticipation (rises a little and recedes), flash in a
    5-frame ramp, falls with the temperature and holds a bit of ember until the cut."""
    data = bpy.data.lights.new("ImpactLight", "SUN")
    data.color = (1.0, 0.58, 0.28)
    data.angle = math.radians(4)
    lamp = bpy.data.objects.new("ImpactLight", data)
    lamp.rotation_euler = Vector((-0.1, -1.0, -0.12)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(lamp)
    peak = 4.0

    def energy(f):
        if f < F - 8:
            return 0.0
        if f < F - 2:
            return 0.5 * fx.ease_in_out((f - F + 8) / 6)        # the sky lights up as the asteroid enters
        if f < F:
            return 0.5 - 0.15 * (f - F + 2)                      # recedes (anticipation)
        if f <= F + 4:
            return 0.2 + (peak - 0.2) * fx.ease_in_out((f - F + 1) / 5)
        return max(peak * heat(f, F) / heat(F + 4, F), 0.9 * (1 - (f - F) / max(end - F, 1)) + 0.1)

    fx.curve_keys(data, "energy", frames, energy)
    fx.set_interp(data)
    return lamp


def shock_ring(frames, F):
    """Ring with thickness (low wall) that runs along the ground and lowers until it vanishes: no transparency."""
    mat = fx.emitter("ImpactRingMat", "#FFC46B", 1.4, base="#3A2A20")
    seg = 64
    verts = [(math.cos(2 * math.pi * i / seg) * r, math.sin(2 * math.pi * i / seg) * r, z)
             for z in (0.0, 1.0) for r in (0.93, 1.0) for i in range(seg)]

    def vid(z, ring, i):
        return z * 2 * seg + ring * seg + i % seg

    faces = []
    for i in range(seg):
        faces.append((vid(0, 1, i), vid(0, 1, i + 1), vid(1, 1, i + 1), vid(1, 1, i)))       # outer wall
        faces.append((vid(0, 0, i + 1), vid(0, 0, i), vid(1, 0, i), vid(1, 0, i + 1)))       # inner wall
        faces.append((vid(1, 0, i), vid(1, 1, i), vid(1, 1, i + 1), vid(1, 0, i + 1)))       # top
    ring = fx.flat_obj("ImpactShockRing", verts, faces, mat, tuple(E + Vector((0, 0, 2.0))))

    def scl(f):
        if f < F + 1:
            return (0.0, 0.0, 0.0)
        u = (f - F - 1) / 28
        r = 60 + 790 * fx.ease_out(u)                            # stops at ~850 m: 56% of the way to the camera
        h = 45 * (1 - fx.ease_in_out((f - F - 6) / 26)) * min((f - F) / 3, 1.0)
        return (r, r, max(h, 0.0))

    fx.curve_keys(ring, "scale", frames, scl)
    fx.set_interp(ring)
    return _shadowless([ring])


def shock_dust(rnd, frames, F, end):
    """Matte, opaque dust kicked up by the ring, on the side running toward the camera: grows, moves with the ring and vanishes
    shrinking while it fades to the low sky color."""
    mat = kit.flat("ImpactShockDustMat", "#B08A66", rough=1.0)
    p = kit.principled(mat)
    p.inputs["Specular IOR Level"].default_value = 0.0
    p.inputs["Emission Color"].default_value = lin("#FF7A2A")
    fx.curve_keys(p.inputs["Base Color"], "default_value", frames,
                  lambda f: tuple(a + (b - a) * fx.ease_in_out((f - F - 20) / 70)
                                  for a, b in zip(lin("#B08A66"), lin(SKY_LOW))))
    fx.curve_keys(p.inputs["Emission Strength"], "default_value", frames, lambda f: 0.35 * heat(f, F))
    fx.set_interp(mat.node_tree)
    out = []
    for k in range(22):
        a = math.radians(-90) + rnd.uniform(-1.0, 1.0) * (1.4 if k % 3 else 0.5)
        d = Vector((math.cos(a), math.sin(a), 0))
        v, fc = fx.ico(1, 1.0)
        o = fx.flat_obj(f"ImpactShockDust{k}", fx.lumpy(v, seed=40 + k, amount=0.25, squash=0.5), fc, mat, tuple(E))
        size, lag, life = rnd.uniform(22, 45), rnd.randint(0, 4), rnd.uniform(35, 60)

        def pos(f, d=d, lag=lag):
            u = fx.ease_out((f - F - 1 - lag) / 28)
            return tuple(E + d * (60 + 760 * u) + Vector((0, 0, 8 + 25 * u)))

        def scl(f, size=size, lag=lag, life=life):
            t = f - F - 2 - lag
            if t < 0:
                return (0.0, 0.0, 0.0)
            s = size * fx.ease_out(t / 10) * (1 - fx.ease_in_out((t - 18) / life))
            return (s * 1.5, s * 1.2, s * 0.8)

        fx.curve_keys(o, "location", frames, pos)
        fx.curve_keys(o, "scale", frames, scl)
        fx.set_interp(o)
        out.append(o)
    return _shadowless(out)


def ballistic(rnd, name, mat, n, speed, life, stretch, size, frames, F, align=False):
    """Pieces with velocity and gravity at the U scale (same flight design as the example); they drag and stop."""
    g = 9.8 * U
    out = []
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        v0 = Vector((math.cos(a) * rnd.uniform(*speed[0]), math.sin(a) * rnd.uniform(*speed[0]) * 0.6,
                     rnd.uniform(*speed[1]))) * U
        geo = kit._gem_geo(1.0, stretch=stretch)
        o = fx.flat_obj(f"{name}{k}", geo[0], geo[1], mat, tuple(E))
        o.rotation_mode = "QUATERNION"
        spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
        s0 = size * U * rnd.uniform(0.6, 1.3)
        h0 = 1.0 * U
        t_land = (v0.z + math.sqrt(v0.z ** 2 + 2 * g * h0)) / g
        for f in frames:
            t = max(f - F, 0) / 30
            if t <= t_land:
                p = Vector((v0.x * t, v0.y * t, h0 + v0.z * t - g * t * t / 2))
                vel = Vector((v0.x, v0.y, v0.z - g * t))
            else:
                drag = 1 - math.exp(-(t - t_land) * 4)
                p = Vector((v0.x * t_land, v0.y * t_land, 0.0)) + Vector((v0.x, v0.y, 0)) * 0.25 * drag
                p.z = s0 * 0.5
                vel = Vector((v0.x, v0.y, 0.01))
            o.location = tuple(E + p)
            o.keyframe_insert("location", frame=f)
            alive = 1.0 if life is None else max(1 - max(f - F, 0) / life, 0.0)
            s = 0.0 if f < F else s0 * alive * min((f - F + 1) / 4, 1.0)    # born in 4 frames, no pop
            o.scale = (s, s, s)
            o.keyframe_insert("scale", frame=f)
            o.rotation_quaternion = vel.to_track_quat("Z", "Y") if align else Quaternion(spin, 9.0 * min(t, t_land))
            o.keyframe_insert("rotation_quaternion", frame=f)
        fx.set_interp(o)
        out.append(o)
    return _shadowless(out)


def embers(rnd, frames, F, end):
    """Aftermath: embers at the base (an irregular strip of low blocks that light up and go out slowly)."""
    mat = fx.emitter("ImpactEmberMat", "#E0611C", 0.0, base="#2A1E18")
    fx.curve_keys(kit.principled(mat).inputs["Emission Strength"], "default_value", frames,
                  lambda f: 0.0 if f < F else 1.0 * min((f - F) / 6, 1.0) * (0.45 + 0.55 * math.exp(-(f - F) / 60)))
    fx.set_interp(mat.node_tree)
    out = []
    for k in range(14):
        x = (k - 6.5) / 6.5 * 420 + rnd.uniform(-25, 25)
        v, fc = fx.ico(1, 1.0)
        o = fx.flat_obj(f"ImpactEmber{k}", fx.lumpy(v, seed=80 + k, amount=0.3, squash=0.4), fc, mat,
                        tuple(E + Vector((x, rnd.uniform(-60, 60), 0))))
        r = rnd.uniform(30, 55) * (1 - abs(x) / 600)
        lag = int(abs(x) / 40)
        fx.curve_keys(o, "scale", frames,
                      lambda f, r=r, lag=lag: (0, 0, 0) if f < F + 2 + lag else
                      (r * 1.8 * fx.ease_out((f - F - 2 - lag) / 12),) * 2 + (r * 0.5 * fx.ease_out((f - F - 2 - lag) / 12),))
        fx.set_interp(o)
        out.append(o)
    return _shadowless(out)


def dust_wall(rnd, frames, F):
    """Wall of dust on the horizon: matte, opaque blocks that rise after the ring passes and stay."""
    mat = kit.flat("ImpactDustWallMat", "#A07C5E", rough=1.0)
    kit.principled(mat).inputs["Specular IOR Level"].default_value = 0.0
    out = []
    for k in range(16):
        x = (k - 7.5) / 7.5 * 900 + rnd.uniform(-40, 40)
        v, fc = fx.ico(1, 1.0)
        o = fx.flat_obj(f"ImpactDustWall{k}", fx.lumpy(v, seed=120 + k, amount=0.3, squash=0.5), fc, mat,
                        tuple(E + Vector((x, rnd.uniform(-150, -60), -20))))
        r = rnd.uniform(90, 150) * (1 - 0.4 * abs(x) / 900)
        lag = 6 + int(abs(x) / 60)

        def scl(f, r=r, lag=lag):
            t = f - F - lag
            if t < 0:
                return (0.0, 0.0, 0.0)
            g = fx.ease_out(t / 40)
            return (r * 1.6 * g, r * 0.8 * g, r * (0.3 + 0.3 * g) * g)

        fx.curve_keys(o, "scale", frames, scl)
        fx.set_interp(o)
        out.append(o)
    return _shadowless(out)


def impact(tl, scene_id="06", f0_frac=0.08, impact_frac=0.32):
    """Builds the whole event; returns all pieces (for the scene's on/off)."""
    rnd = random.Random(66)
    a, b = tl.at(scene_id), tl.at(scene_id, 1.0)
    frames = range(a - 1, b + 2)
    f0, F = tl.at(scene_id, f0_frac), tl.at(scene_id, impact_frac)
    fire, heat_socket = fire_material()
    fx.curve_keys(heat_socket, "default_value", frames, lambda f: heat(f, F))
    fx.set_interp(fire.node_tree)
    pieces = asteroid(tl, frames, f0, F)
    pieces += flash(frames, F)
    pieces += fireball(rnd, frames, F, fire)
    pieces += shock_ring(frames, F)
    pieces += shock_dust(rnd, frames, F, b)
    rock = fx.emitter("ImpactDebrisMat", "#E0611C", 0.0, base="#2A2420")
    fx.curve_keys(kit.principled(rock).inputs["Emission Strength"], "default_value", frames,
                  lambda f: 0.0 if f < F else 1.0 * math.exp(-(f - F) / 25))
    fx.set_interp(rock.node_tree)
    pieces += ballistic(rnd, "ImpactDebris", rock, 14, ((4, 9), (5, 11)), None, 1.0, 0.22, frames, F)
    pieces += ballistic(rnd, "ImpactSpark", fx.emitter("ImpactSparkMat", "#FFC46B", 4.0), 26, ((6, 14), (4, 13)),
                        18, 5.0, 0.12, frames, F, align=True)
    pieces += embers(rnd, frames, F, b)
    pieces += dust_wall(rnd, frames, F)
    lamp = event_light(frames, F, b)
    return pieces, lamp
