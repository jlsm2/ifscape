"""Low-poly seagull for a background sky: white fusiform body, "M" wings (arm and hand, pivot at the shoulder and wrist)
gray on top with black tips, short tail. Glides in wide arcs with short wing beats. ~60 triangles.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Proportions of a yellow-legged gull (Larus
michahellis): length 0.6 m, wingspan 1.4 m; white body, gray mantle #9AA4AE, black tips.

build(name, mats) -> SimpleNamespace(root, wings=[(shoulder, wrist), ...]); root faces local +x.
animate(g, frames, path_fn, flap_ranges) -> position/heading on every frame; wings glide (dihedral) and beat at 3.2 Hz
inside flap_ranges.
"""

import math
from types import SimpleNamespace

from mathutils import Vector

import kit
import plants_models as pm
from lib import anim_curves as ac


def build(name, mats, scale=1.0):
    root = pm._empty(name)
    root.scale = (scale,) * 3
    body = kit.tube_geo([(-0.3, 0, 0.0), (-0.18, 0, 0.0), (0.05, 0, 0.01), (0.2, 0, 0.03), (0.3, 0, 0.03)],
                        [0.02, 0.055, 0.07, 0.05, 0.015], n=6)
    tail = ([(-0.22, -0.06, 0.0), (-0.36, -0.07, 0.0), (-0.36, 0.07, 0.0), (-0.22, 0.06, 0.0)], [(0, 1, 2, 3)])
    v, f, own = kit.merge(body, tail)
    pm.obj_from(f"{name}Body", (v, f), [mats["white"]], parent=root)
    wings = []
    for side in (1, -1):
        sh = pm._empty(f"{name}Sh{side}", (0.03, 0.05 * side, 0.03), parent=root)
        arm = ([(0.06, 0, 0), (-0.08, 0, 0), (-0.06, 0.34 * side, 0.0), (0.06, 0.34 * side, 0.0)], [(0, 1, 2, 3)])
        pm.obj_from(f"{name}Arm{side}", arm, [mats["grey"]], parent=sh)
        wr = pm._empty(f"{name}Wr{side}", (0.0, 0.34 * side, 0.0), parent=sh)
        hand = ([(0.06, 0, 0), (-0.06, 0, 0), (-0.12, 0.3 * side, 0.0), (-0.02, 0.36 * side, 0.0)], [(0, 1, 2, 3)])
        tip = ([(-0.08, 0.2 * side, 0.002), (-0.12, 0.3 * side, 0.002), (-0.02, 0.36 * side, 0.002),
                (0.02, 0.24 * side, 0.002)], [(0, 1, 2, 3)])
        v, f, own = kit.merge(hand, tip)
        pm.obj_from(f"{name}Hand{side}", (v, f), [mats["grey"], mats["black"]], parent=wr,
                    face_mats=[0 if k == 0 else 1 for k in own])
        wings.append((sh, wr, side))
    for o in [root, *root.children_recursive]:
        if o.type == "MESH":
            o.visible_shadow = False
    return SimpleNamespace(root=root, wings=wings)


def animate(g, frames, path_fn, flap_ranges=(), hz=3.2):
    locs, rots = [], []
    n = len(frames)
    for i, f in enumerate(frames):
        u = i / max(1, n - 1)
        p = path_fn(u)
        q = path_fn(min(1.0, u + 1.0 / max(1, n - 1)))
        r = path_fn(max(0.0, u - 1.0 / max(1, n - 1)))
        d = q - r
        yaw = math.atan2(d.y, d.x)
        bank = 0.0
        if 0 < i < n - 1:                                        # leans into the curve
            a = (p - r).to_2d().angle_signed((q - p).to_2d(), 0.0) if (p - r).length and (q - p).length else 0
            bank = max(-0.5, min(0.5, -a * 12.0))
        locs.append(p)
        rots.append((bank, -math.atan2(d.z, d.to_2d().length), yaw))
    ac.write_vec(g.root, "location", frames, locs)
    ac.write_vec(g.root, "rotation_euler", frames, rots)
    for sh, wr, side in g.wings:
        a_sh, a_wr = [], []
        for f in frames:
            flap = 0.0
            for fa, fb in flap_ranges:
                if fa <= f <= fb:
                    w = min(1.0, (f - fa) / 6.0, (fb - f) / 6.0)
                    flap = w * math.sin(2 * math.pi * hz * (f - fa) / 30.0)
            a_sh.append(side * (math.radians(10) + math.radians(38) * flap))      # gliding dihedral + beat
            a_wr.append(side * (math.radians(-14) + math.radians(-22) * flap))    # wrist bends (M wing)
        ac.write(sh, "rotation_euler", 0, frames, a_sh)
        ac.write(wr, "rotation_euler", 0, frames, a_wr)
