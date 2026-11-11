"""Drifting particles without simulation (dense LINEAR keys computed in Python):

- dust(): large, sparse dust grains that cross a box with the wind, wrapping around and
  shrinking to zero near the box edges (nothing is born or vanishes suddenly). art.md §1.3: >= 6 px, never a veil.
- smoke_loop(): thin brazier smoke in matte, opaque blobs that are born at the flame, rise, lean with the wind,
  grow and then shrink until they vanish (docs/blender/effects-and-lighting.md: matte smoke, no translucency).
  Each blob is recycled in a loop (fixed life, born with zero scale).

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct).
"""

import math

from mathutils import Vector

import kit
import plants_models as pm
from lib import anim_curves as ac


def _wrap(v, lo, hi):
    return lo + (v - lo) % (hi - lo)


def dust(name, box, mat, rnd, count, frames, wind=(-0.5, 0.0, 0.0), size=(0.025, 0.045), step=1):
    """box = (x0, x1, y0, y1, z0, z1). Returns the list of objects."""
    x0, x1, y0, y1, z0, z1 = box
    W = Vector(wind)
    out = []
    fr = list(range(frames[0], frames[1] + 1, step))
    if fr[-1] != frames[1]:
        fr.append(frames[1])
    for k in range(count):
        v, f = kit._gem_geo(rnd.uniform(*size), stretch=0.6)
        o = pm.obj_from(f"{name}{k}", (v, f), [mat])
        o.visible_shadow = False
        p0 = Vector((rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(z0, z1)))
        sp = rnd.uniform(0.7, 1.3)
        ph = rnd.uniform(0, 6.28)
        locs, scs, rots = [], [], []
        for f_ in fr:
            t = (f_ - frames[0]) / 30.0
            p = p0 + W * sp * t + Vector((0.0, 0.12 * math.sin(0.7 * t + ph), 0.1 * math.sin(1.1 * t + 2 * ph)))
            p = Vector((_wrap(p.x, x0, x1), _wrap(p.y, y0, y1), max(z0, min(z1, p.z))))
            edge = min(p.x - x0, x1 - p.x, p.y - y0, y1 - p.y) / 0.6
            s = max(0.0, min(1.0, edge))
            s = s * s * (3 - 2 * s)
            locs.append(p)
            scs.append((s, s, s))
            rots.append((t * 1.7 + ph, t * 1.1, ph))
        # the wrap makes the position jump from one edge to the other: the scale is already zero there, but the LINEAR key between the
        # two frames would drag the grain across the whole box: at the jump, the jump frame becomes two (CONSTANT)
        ac.write_vec(o, "location", fr, locs)
        ac.write_vec(o, "scale", fr, scs)
        ac.write_vec(o, "rotation_euler", fr, rots)
        for fc in ac.bag(o).fcurves:
            if fc.data_path != "location":
                continue
            pts = fc.keyframe_points
            for i in range(len(pts) - 1):
                if abs(pts[i + 1].co[1] - pts[i].co[1]) > 0.5 * max(x1 - x0, y1 - y0) * 0.5:
                    pts[i].interpolation = "CONSTANT"
        out.append(o)
    return out


def smoke_loop(name, source, mat, rnd, frames, n=10, life=66, rise=0.55, drift=(0.28, 0.0, 0.0),
               r0=0.012, r1=0.05):
    """Looping blobs leaving 'source' (Vector) between frames=(a, b). Returns the objects."""
    a, b = frames
    out = []
    D = Vector(drift)
    for k in range(n):
        v, f = pm.lumpy_ico(1.0, (0, 0, 0), (1, 1, 0.85), rnd, 0.2)
        o = pm.obj_from(f"{name}{k}", (v, f), [mat])
        o.visible_shadow = False
        off = k * life / n
        jx, jy = rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01)
        fr = list(range(a, b + 1))
        locs, scs = [], []
        for f_ in fr:
            u = ((f_ - a + off) % life) / life                  # 0..1 over the blob's life
            h = rise * (1 - (1 - u) ** 1.6)                      # rises fast and decelerates
            p = source + Vector((jx, jy, h)) + D * (u ** 1.5) * (life / 30.0)
            p += Vector((0.015 * math.sin(6.0 * u + k), 0.012 * math.cos(5.0 * u + k), 0.0))
            grow = r0 + (r1 - r0) * min(1.0, u / 0.6)
            fade = 1.0 if u < 0.55 else max(0.0, 1 - (u - 0.55) / 0.45)
            birth = min(1.0, u / 0.08)
            s = grow * (fade ** 0.8) * birth
            locs.append(p)
            scs.append((s, s, s))
        ac.write_vec(o, "location", fr, locs)
        ac.write_vec(o, "scale", fr, scs)
        # when the loop restarts the blob returns to the flame with zero scale: CONSTANT on the jump frame
        for fc in ac.bag(o).fcurves:
            if fc.data_path != "location":
                continue
            pts = fc.keyframe_points
            for i in range(len(pts) - 1):
                if abs(pts[i + 1].co[1] - pts[i].co[1]) > 0.05:
                    pts[i].interpolation = "CONSTANT"
        out.append(o)
    return out


def smoke_wisp(name, source, mat, frames, height=0.6, lean=0.18, radii=(0.003, 0.007, 0.01, 0.012, 0.012, 0.01,
                                                                          0.007, 0.004, 0.0), rise_speed=0.22,
               sway=0.09, seed=3):
    """Continuous smoke wisp (tapering tube, leaning with the wind) that undulates as it rises: two Displace (X and Y) with
    cloud texture in the coordinates of an empty that rises at constant speed (the wave pattern climbs the wisp);
    weighted by height (the base stays pinned to the flame). Matte and opaque, no loose blobs."""
    import bpy
    n = len(radii)
    pts = []
    for k in range(n):
        h = height * k / (n - 1)
        u = h / height
        pts.append((source.x + lean * u ** 1.6, source.y, source.z + h))
    v, f = kit.tube_geo(pts, list(radii), n=6)
    o = pm.obj_from(name, (v, f), [mat])
    o.visible_shadow = False
    vg = o.vertex_groups.new(name="sway")
    for i, p in enumerate(o.data.vertices):
        u = max(0.0, min(1.0, (p.co.z - source.z) / height))
        vg.add([i], u ** 1.3, "REPLACE")
    a, b = frames
    for axis, off in (("X", 0.0), ("Y", 5.0)):
        tex = bpy.data.textures.new(f"{name}Tex{axis}", "CLOUDS")
        tex.noise_scale = 0.16
        e = pm._empty(f"{name}Drive{axis}", (source.x + off, source.y + off, source.z))
        mod = o.modifiers.new(f"Sway{axis}", "DISPLACE")
        mod.texture = tex
        mod.texture_coords = "OBJECT"
        mod.texture_coords_object = e
        mod.direction = axis
        mod.strength = sway * (1.0 if axis == "X" else 0.6)
        mod.mid_level = 0.5
        mod.vertex_group = "sway"
        fr = [a, b]
        ac.write(e, "location", 2, fr, [source.z - rise_speed * (f_ - a) / 30.0 * -1.0 for f_ in fr])
    return o
