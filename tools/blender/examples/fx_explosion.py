"""Test (b): layered low-poly explosion (Eevee, no volume), tested on Blender 5.2.2.

Layers and timing (30 fps, F = flash frame):
  1. anticipation (1..F-1): hot seed that grows and contracts before bursting;
  2. flash (F..F+4): white-yellow core + point light that RISES over 4 frames (no step) and decays;
  3. fireball (F..): 9 faceted blobs (icosphere + noise + "boiling" Displace), they grow fast and
     decelerate; the color cools from white-yellow -> orange -> ember and turns into gray smoke (the same material);
  4. shock ring on the ground + dust that runs with it; ballistic debris; stretched sparks;
  5. residue: the smoke rises and spreads (mushroom), embers dying out, scorched ground.
No part of the effect casts a shadow (visible_shadow = False); only the flash light does.

    blender -b -P tools/blender/examples/fx_explosion.py -- <folder> <AgX|Standard> <frames: 5,11,22,60> [--anim]
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import fx_common as fx  # noqa: E402
import kit  # noqa: E402
from kit import lin  # noqa: E402

E = Vector((0.0, 16.0, 0.0))     # center of the explosion
F = 8                            # flash frame
END = 90
FRAMES = range(1, END + 1)


def heat(f):
    """Fire temperature 0..1: rises in 3 frames, then cools quickly and takes a while to go out."""
    if f < F:
        return 0.0
    if f < F + 3:
        return (f - F + 1) / 4
    return math.exp(-(f - F - 3) / 26)


def fire_material():
    """One material for all the blobs: the emission color comes from a temperature ramp; the edge of each
    facet (Layer Weight > Facing, which in flat shading is per face) gets cooler and darker, which gives
    faceted volume instead of a flat disc. With heat = 0 the gray base remains: it becomes smoke."""
    mat = bpy.data.materials.new("Fireball")
    nt = mat.node_tree
    n, ln = nt.nodes, nt.links
    p = kit.principled(mat)
    p.inputs["Base Color"].default_value = lin("#77727E")   # smoke lighter than the sky, otherwise it vanishes into the night
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    hv = n.new("ShaderNodeValue")
    hv.name = "Heat"
    info = n.new("ShaderNodeObjectInfo")
    jitter = n.new("ShaderNodeMapRange")                      # each blob a little hotter or colder
    jitter.inputs["To Min"].default_value, jitter.inputs["To Max"].default_value = 0.8, 1.15
    ln.new(info.outputs["Random"], jitter.inputs["Value"])
    h = n.new("ShaderNodeMath"); h.operation = "MULTIPLY"; h.use_clamp = True
    ln.new(hv.outputs[0], h.inputs[0]); ln.new(jitter.outputs[0], h.inputs[1])
    lw = n.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.45
    rim = n.new("ShaderNodeMath"); rim.operation = "MULTIPLY_ADD"     # facet temperature = h - 0.35*edge
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
    # strength = 3 * h^2: white core when hot; orange already at strength ~1 (in AgX, too strong turns salmon)
    sq = n.new("ShaderNodeMath"); sq.operation = "POWER"; sq.inputs[1].default_value = 2.0
    ln.new(rim.outputs[0], sq.inputs[0])
    st = n.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 3.0
    ln.new(sq.outputs[0], st.inputs[0])
    ln.new(st.outputs[0], p.inputs["Emission Strength"])
    fx.curve_keys(hv.outputs[0], "default_value", FRAMES, heat)
    fx.set_interp(nt)
    return mat


def fireball(rnd, mat):
    """9 blobs: the core and a crown; the upper ones rise more and spread (it becomes the mushroom in the residue)."""
    boil_tex = bpy.data.textures.new("Boil", "CLOUDS")
    boil_tex.noise_scale = 0.55
    boil = bpy.data.objects.new("BoilDriver", None)          # moving the empty = the surface boils
    bpy.context.scene.collection.objects.link(boil)
    fx.curve_keys(boil, "location", FRAMES, lambda f: (0.0, 0.0, 0.05 * f))
    fx.set_interp(boil)
    blobs = []
    for k in range(9):
        a = 2 * math.pi * k / 8
        off = Vector((0, 0, 0)) if k == 0 else Vector((math.cos(a) * 1.4, math.sin(a) * 1.0, rnd.uniform(-0.3, 1.2)))
        size = 2.6 if k == 0 else rnd.uniform(1.4, 2.1)
        v, fc = fx.ico(2, 1.0)
        b = fx.flat_obj(f"Blob{k}", fx.lumpy(v, seed=k + 1, amount=0.22, squash=0.7), fc, mat, tuple(E))
        d = b.modifiers.new("Boil", "DISPLACE")
        d.texture, d.texture_coords, d.texture_coords_object, d.strength = boil_tex, "OBJECT", boil, 0.35
        b.visible_shadow = False
        up = 1.4 + 0.8 * max(off.z, 0)                         # m per second: the upper ones rise more

        def pos(f, off=off, up=up):
            t = max(f - F, 0) / 30
            spread = 1 + 0.6 * fx.ease_out(t / 2)
            return tuple(E + Vector((off.x * spread, off.y * spread, size * 0.55 + off.z + up * t)))

        def scl(f, size=size):
            if f < F:
                return (0.0, 0.0, 0.0)
            r = size * (fx.ease_out((f - F) / 16) * 0.85 + 0.15 + 0.004 * (f - F))
            return (r, r, r * 0.9)

        fx.curve_keys(b, "location", FRAMES, pos)
        fx.curve_keys(b, "scale", FRAMES, scl)
        fx.set_interp(b)
        blobs.append(b)
    return blobs


def seed_and_flash():
    """Anticipation + flash: a seed that swells and contracts, a white core that bursts and vanishes inside the fire."""
    hot = fx.emitter("Core", "#FFF1D0", 8.0)                  # hot white on purpose (here it may go to white)
    v, fc = fx.ico(1, 1.0)
    core = fx.flat_obj("Core", fx.lumpy(v, seed=9, amount=0.15), fc, hot, tuple(E + Vector((0, 0, 1.2))))
    core.visible_shadow = False

    def scl(f):
        if f < F:                                            # 1..F-1: grows to 0.5 m and contracts to 0.25 m
            u = (f - 1) / (F - 2)
            r = 0.5 * math.sin(u * math.pi * 0.8) + 0.08
        elif f <= F + 3:
            r = 0.3 + 2.9 * fx.ease_out((f - F) / 3)
        else:
            r = max(3.2 * (1 - (f - F - 3) / 10), 0.0)
        return (r, r, r)

    fx.curve_keys(core, "scale", FRAMES, scl)
    fx.set_interp(core)
    lamp_data = bpy.data.lights.new("Flash", "POINT")
    lamp_data.color, lamp_data.shadow_soft_size = (1.0, 0.55, 0.25), 1.5
    lamp = bpy.data.objects.new("Flash", lamp_data)
    lamp.location = tuple(E + Vector((0, -1.0, 2.0)))
    bpy.context.scene.collection.objects.link(lamp)
    peak = 40000.0

    def energy(f):
        if f < F:
            return 400.0 * scl(f)[0]                         # weak glow of the seed
        if f <= F + 4:
            return peak * fx.ease_in_out((f - F + 1) / 5)    # rises in 4 to 5 frames, no step
        return peak * (0.12 + 0.88 * math.exp(-(f - F - 4) / 7)) * heat(f) / heat(F + 4)

    fx.curve_keys(lamp_data, "energy", FRAMES, energy)
    fx.set_interp(lamp_data)
    return core, lamp


def shock_ring():
    """Ring on the ground that runs outward and vanishes (alpha + strength), with dust following."""
    mat = fx.emitter("Ring", "#FFC46B", 2.0)
    mat.surface_render_method = "BLENDED"
    mat.use_transparency_overlap = False
    p = kit.principled(mat)
    seg = 48
    verts = [(math.cos(2 * math.pi * i / seg) * r, math.sin(2 * math.pi * i / seg) * r, 0)
             for r in (0.86, 1.0) for i in range(seg)]
    faces = [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    ring = fx.flat_obj("ShockRing", verts, faces, mat, tuple(E + Vector((0, 0, 0.06))))
    ring.visible_shadow = False

    def r(f):
        u = (f - F) / 14
        return 0.0 if f < F else 1.0 + 9.0 * fx.ease_out(u)        # never reaches the camera (16 m)

    fx.curve_keys(ring, "scale", FRAMES, lambda f: (r(f), r(f), 1.0))
    fx.curve_keys(p.inputs["Alpha"], "default_value", FRAMES, lambda f: 0.0 if f < F else max(0.9 * (1 - (f - F) / 16), 0))
    fx.curve_keys(p.inputs["Emission Strength"], "default_value", FRAMES,
                  lambda f: 0.0 if f < F else max(2.0 * (1 - (f - F) / 14), 0))
    fx.set_interp(ring)
    fx.set_interp(mat.node_tree)
    return ring


def dust_ring(rnd):
    """Opaque, matte dust raised by the ring (test (c) explains why opaque and not translucent)."""
    mat = fx.emitter("RingDust", "#C08A5A", 0.0, base="#9C8670")
    fx.curve_keys(kit.principled(mat).inputs["Emission Strength"], "default_value", FRAMES,
                  lambda f: 0.08 + 0.5 * heat(f))            # dust lit by the fire, goes out with it
    fx.set_interp(mat.node_tree)
    out = []
    for k in range(28):
        a = 2 * math.pi * k / 28 + rnd.uniform(-0.1, 0.1)
        d = Vector((math.cos(a), math.sin(a), 0))
        v, fc = fx.ico(1, 1.0)
        o = fx.flat_obj(f"RingDust{k}", fx.lumpy(v, seed=40 + k, amount=0.25, squash=0.5), fc, mat, tuple(E))
        o.visible_shadow = False
        size, lag = rnd.uniform(0.35, 0.7), rnd.randint(0, 3)

        def pos(f, d=d, lag=lag):
            u = fx.ease_out((f - F - lag) / 18)
            return tuple(E + d * (2.5 + 6.0 * u) + Vector((0, 0, 0.2 + 0.5 * u)))

        def scl(f, size=size, lag=lag):
            t = f - F - lag
            if t < 0:
                return (0, 0, 0)
            grow = fx.ease_out(t / 10)
            fade = 1 - fx.ease_in_out((t - 25) / 35)              # vanishes by shrinking, not by becoming transparent
            s = size * grow * fade
            return (s * 1.4, s * 1.4, s)

        fx.curve_keys(o, "location", FRAMES, pos)
        fx.curve_keys(o, "scale", FRAMES, scl)
        fx.set_interp(o)
        out.append(o)
    return out


def ballistic(rnd, name, mat, n, speed, life, geo_stretch, scale, align=False):
    """Pieces with initial velocity and gravity; they bounce once on the ground. align=True stretches along the flight direction."""
    out = []
    g = 9.8
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        v0 = Vector((math.cos(a) * rnd.uniform(*speed[0]), math.sin(a) * rnd.uniform(*speed[0]) * 0.6,
                     rnd.uniform(*speed[1])))
        geo = kit._gem_geo(1.0, stretch=geo_stretch)
        o = fx.flat_obj(f"{name}{k}", geo[0], geo[1], mat, tuple(E))
        o.visible_shadow = False
        o.rotation_mode = "QUATERNION"
        spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
        s0 = scale * rnd.uniform(0.6, 1.3)
        t_land = (v0.z + math.sqrt(v0.z ** 2 + 2 * g * 1.0)) / g     # leaves from 1 m above the ground
        for f in FRAMES:
            t = max(f - F, 0) / 30
            if t <= t_land:
                p = Vector((v0.x * t, v0.y * t, 1.0 + v0.z * t - g * t * t / 2))
                vel = Vector((v0.x, v0.y, v0.z - g * t))
            else:                                                # after the ground: drags and stops
                p_land = Vector((v0.x * t_land, v0.y * t_land, 0.0))
                drag = 1 - math.exp(-(t - t_land) * 4)
                p = p_land + Vector((v0.x, v0.y, 0)) * 0.25 * drag
                p.z = scale * 0.5
                vel = Vector((v0.x, v0.y, 0.01))
            o.location = tuple(E + p)
            o.keyframe_insert("location", frame=f)
            alive = 1.0 if life is None else max(1 - max(f - F, 0) / life, 0.0)
            s = 0.0 if f < F else s0 * alive
            o.scale = (s, s, s)
            o.keyframe_insert("scale", frame=f)
            if align:
                o.rotation_quaternion = vel.to_track_quat("Z", "Y")
            else:
                from mathutils import Quaternion
                o.rotation_quaternion = Quaternion(spin, 9.0 * min(t, t_land))
            o.keyframe_insert("rotation_quaternion", frame=f)
        fx.set_interp(o)
        out.append(o)
    return out


def scorch():
    mat = kit.flat("Scorch", "#141418", rough=1.0)
    kit.principled(mat).inputs["Specular IOR Level"].default_value = 0.0
    v, f = kit._prism_geo(14, 1.0, 1.0, 0.01)
    o = fx.flat_obj("Scorch", v, f, mat, tuple(E + Vector((0, 0, 0.005))))
    fx.curve_keys(o, "scale", FRAMES, lambda fr: (0, 0, 0) if fr < F else (6 * fx.ease_out((fr - F) / 10),) * 2 + (1,))
    fx.set_interp(o)


def build():
    scene = fx.night_scene(res=(1080, 1920), samples=32, cam_loc=(0, -2, 1.65), target=(0, 16, 5.0), lens=24)
    scene.frame_start, scene.frame_end, scene.render.fps = 1, END, 30
    rnd = random.Random(5)
    fx.props(scene, rnd, n=14, spread=13, y0=10)
    fireball(rnd, fire_material())
    seed_and_flash()
    shock_ring()
    dust_ring(rnd)
    rock = fx.emitter("Rock", "#E0611C", 0.0, base="#2A2420")
    fx.curve_keys(kit.principled(rock).inputs["Emission Strength"], "default_value", FRAMES,
                  lambda f: 0.0 if f < F else 1.0 * math.exp(-(f - F) / 25))    # embers that go out
    fx.set_interp(rock.node_tree)
    ballistic(rnd, "Debris", rock, 14, ((4, 9), (5, 11)), None, 1.0, 0.22)
    ballistic(rnd, "Spark", fx.emitter("Spark", "#FFC46B", 4.0), 26, ((6, 14), (4, 13)), 18, 5.0, 0.12, align=True)
    scorch()
    return scene


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out, transform, frames = Path(args[0]), args[1], [int(x) for x in args[2].split(",")]
    scene = build()
    fx.view(scene, transform)
    tag = transform.replace(" ", "")
    for f in frames:
        scene.frame_set(f)
        fx.render(scene, out / f"expl_{tag}_f{f:03d}.png")
    if "--anim" in args:
        scene.render.resolution_percentage = 50
        scene.eevee.taa_render_samples = 16
        scene.render.filepath = str(out / f"expl_anim_{tag}" / "f_")
        bpy.ops.render.render(animation=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"expl_{tag}.blend"))


main()
