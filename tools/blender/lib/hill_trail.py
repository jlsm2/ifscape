"""Zigzag (switchback) trail on a slope given by a height function z(x, y): ribbon of packed earth with a
dark stone border on the downhill side (reads as a trail from afar, not as a scratch), rounded curves.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Footpath 1.5-2 m wide; the dark border
(0.4 m) gives contrast with the straw (#D8C07C) at 150-260 m.

switchbacks(a, b, legs, swing) -> list of (x, y) points zigzagging from a to b
build(name, curve_pts, zf, path_mat, edge_mat, width=1.8, lift=0.2) -> (ribbon, border)
curve_pts = already-smoothed points (Vector) (e.g. rigs.smooth_path).
"""

from mathutils import Vector

import kit
import plants_models as pm


def switchbacks(a, b, legs=7, swing=16.0):
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    d = b - a
    side = Vector((-d.y, d.x, 0)).normalized()
    pts = [a]
    for k in range(1, legs):
        pts.append(a + d * (k / legs) + side * (swing if k % 2 else -swing))
    pts.append(b)
    return [(p.x, p.y) for p in pts]


def _ribbon(pts, zf, off0, off1, lift):
    verts, faces = [], []
    for i, p in enumerate(pts):
        q0, q1 = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        t = (q1 - q0)
        t.z = 0
        nrm = Vector((-t.y, t.x, 0)).normalized()
        for off in (off0, off1):
            x, y = p.x + nrm.x * off, p.y + nrm.y * off
            verts.append((x, y, zf(x, y) + lift))
    for i in range(len(pts) - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    return verts, faces


def build(name, curve_pts, zf, path_mat, edge_mat, width=1.8, lift=0.2, edge=0.45):
    pts = [Vector((p.x, p.y, 0)) for p in curve_pts]
    v, f = _ribbon(pts, zf, -width / 2, width / 2, lift)
    path = pm.obj_from(f"{name}", (v, f), [path_mat])
    v, f = _ribbon(pts, zf, width / 2, width / 2 + edge, lift + 0.05)
    v2, f2 = _ribbon(pts, zf, -width / 2 - edge, -width / 2, lift + 0.05)
    v, f, _ = kit.merge((v, f), (v2, f2))
    border = pm.obj_from(f"{name}Edge", (v, f), [edge_mat])
    for o in (path, border):
        o.visible_shadow = False
    return path, border
