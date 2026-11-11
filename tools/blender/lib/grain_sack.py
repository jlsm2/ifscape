"""Low-poly burlap sack: open (mouth folded outward and grain showing) or closed (tied at the top).

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Proportion: 25 kg grain sack ~0.4 m in diameter x
0.55 m tall when full (common 50 x 80 cm sacking when empty). ~90 triangles the open one, ~70 the closed one.

open_sack(name, location, mats, rnd)  -> object (materials: sack, grain)
closed_sack(name, location, mats, rnd, lying=False, heading=0) -> object
"""

import math

from mathutils import Matrix, Vector

import kit
import plants_models as pm


def _ring(r, z, n=9, rnd=None, jit=0.0, sx=1.0):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1.0 + (rnd.uniform(-jit, jit) if rnd else 0.0)
        out.append((r * k * sx * math.cos(a), r * k * math.sin(a), z))
    return out


def open_sack(name, location, mats, rnd, h=0.55, r=0.2):
    rings = [_ring(r * 0.86, 0.0, rnd=rnd, jit=0.03), _ring(r, 0.12, rnd=rnd, jit=0.05),
             _ring(r * 1.04, h * 0.55, rnd=rnd, jit=0.05), _ring(r * 0.97, h * 0.9, rnd=rnd, jit=0.04),
             _ring(r * 1.08, h + 0.03, rnd=rnd, jit=0.06),            # mouth folded outward (flap)
             _ring(r * 1.16, h - 0.05, rnd=rnd, jit=0.06)]
    body = kit.loft_geo(rings, cap_start=True, cap_end=False)
    # grain: low mound inside the mouth (2-ring dome), slightly below the rim
    top = h * 0.93
    gr = [_ring(r * 0.95, top - 0.02, rnd=rnd, jit=0.03), _ring(r * 0.6, top + 0.03, rnd=rnd, jit=0.08),
          _ring(r * 0.2, top + 0.05, n=9)]
    grain = kit.loft_geo(gr, cap_start=False, cap_end=True)
    v, f, own = kit.merge(body, grain)
    o = pm.obj_from(name, (v, f), [mats["sack"], mats["grain"]], location=location,
                    face_mats=[0 if k == 0 else 1 for k in own])
    return o


def closed_sack(name, location, mats, rnd, h=0.6, r=0.21, lying=False, heading=0.0):
    rings = [_ring(r * 0.85, 0.0, rnd=rnd, jit=0.04), _ring(r, 0.1, rnd=rnd, jit=0.05),
             _ring(r * 1.05, h * 0.5, rnd=rnd, jit=0.06), _ring(r * 0.9, h * 0.82, rnd=rnd, jit=0.05),
             _ring(r * 0.35, h * 0.97, n=9), _ring(r * 0.08, h * 1.0, n=9),
             _ring(r * 0.22, h * 1.12, n=9)]                          # knot and the tied end
    v, f = kit.loft_geo(rings, cap_start=True, cap_end=True)
    m = Matrix.Rotation(heading, 4, "Z")
    if lying:                                                          # lying down, flattened by the weight
        m = m @ Matrix.Translation((0, 0, r * 0.75)) @ Matrix.Rotation(math.pi / 2, 4, "Y") @ \
            Matrix.Scale(0.75, 4, Vector((1, 0, 0))) @ Matrix.Translation((0, 0, -h / 2))
    else:
        m = m @ Matrix.Scale(0.85, 4, Vector((0, 1, 0)))
    v = [tuple(m @ Vector(p)) for p in v]
    return pm.obj_from(name, (v, f), [mats["sack"]], location=location)
