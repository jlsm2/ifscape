"""Dry plane-tree leaf (palmate, 5 points, folded along the midrib) and a leaf flying in the wind: drift with sway
(leaf falling in a zigzag, "falling leaf"), spin about its own axis and tumble. ~12 triangles per leaf.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Platanus x hispanica leaf: 12-25 cm, 3-5 pointed
lobes, long petiole; dry = curled (fold of ~35° along the midrib).

leaf_geo(size) -> (verts, faces) around the origin, XY plane, tip at +y
fly(obj, frames, path_fn, rnd, spin=1.0) -> writes location/rotation on every frame (LINEAR)
"""

import math

from mathutils import Euler, Vector

import kit
from lib import anim_curves as ac


def leaf_geo(size=0.18, fold=0.6):
    s = size / 2
    # outline: petiole, lobes (5 points) and notches, from bottom to top along the right side
    right = [(0.0, -1.0), (0.18, -0.55), (0.75, -0.35), (0.5, -0.05), (0.95, 0.35), (0.42, 0.42), (0.25, 1.0)]
    pts = [(0.0, -1.15)] + right[1:] + [(0.0, 1.05)] + [(-x, y) for x, y in reversed(right[1:])]
    verts = [(0.0, -0.1 * s, 0.0)]                          # center (on the midrib): fan out to the outline
    for x, y in pts:
        verts.append((x * s, y * s, abs(x) * s * fold * 0.5))      # fold at the midrib: the halves rise
    m = len(pts)
    faces = [(0, 1 + k, 1 + (k + 1) % m) for k in range(m)]
    return verts, faces


def fly(obj, frames, path_fn, rnd, spin=1.0, tumble=1.0):
    """path_fn(u) -> Vector position (u from 0 to 1 along the frames). Lateral sway and spin on top."""
    n = len(frames)
    ph = rnd.uniform(0, 6.28)
    fr = rnd.uniform(1.1, 1.8)                    # sway oscillations per second
    locs, rots = [], []
    for i, f in enumerate(frames):
        u = i / max(1, n - 1)
        t = (f - frames[0]) / 30.0
        p = path_fn(u)
        sw = math.sin(2 * math.pi * fr * t + ph)
        p = p + Vector((0.0, 0.0, 0.08 * sw))
        locs.append(p)
        rots.append(Euler((tumble * (0.9 * sw + 0.6 * t), spin * 2.4 * t + ph, 0.5 * math.cos(2 * math.pi * fr * t + ph)),
                          "XYZ"))
    ac.write_vec(obj, "location", frames, locs)
    ac.write_vec(obj, "rotation_euler", frames, rots)
