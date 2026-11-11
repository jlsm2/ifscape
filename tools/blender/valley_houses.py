"""Wooden houses of the valley (two-humans-left), own low-poly model (final round, 2026-10-22).

Replaces the Kenney Fantasy Town Kit panels, which read as black boxes with gaps. Proportions of a rural
wooden house (references: Kenney Fantasy Town Kit and Quaternius Medieval Village, CC0, only as a silhouette guide):
module S = 2.3 m, wall 2.5 m, door 0.95 x 2.0 m, window 0.75 x 0.95 m with sill at 0.9 m, gable roof
at ~37 degrees with 0.4 m eaves, 0.4 m stone foundation. A 1.75 m person hits the doorframe at ~0.25 m.

Pieces: stone foundation, walls with real openings (box cells, 15 cm thick), corner posts and
darker wall plate, windows with frame, crossbar and open shutters, glass that lights up (ONE material per house: the scene
animates the strength and lights/unlights the whole house), plank door with step, gables, roof with thickness, fascia and
ridge. Nothing coplanar: frames intrude 2 cm into the opening, shutters sit 5 mm off the wall.
"""

import math
import zlib

import bpy

import kit
import valley_lib as vl

S = 2.3                     # plan module (m)
H = 2.5                     # wall height
T = 0.15                    # wall thickness
GLOW = "#FFB347"
WIN_W, WIN_H, SILL = 0.75, 0.95, 0.9
DOOR_W, DOOR_H = 0.95, 2.0

WALLS = ["#5E4330", "#6E5440", "#8C7A60", "#4F5A50", "#735038"]        # dark wood, worn, dirty whitewash, gray-green
ROOFS = ["#4A3326", "#3A4450", "#5A4636", "#465238", "#5E3428"]
SHUTTERS = ["#3E5466", "#4A5A3A", "#6A4A30", "#5A3A30"]
_mats = {}


def _m(name, color, **kw):
    if name not in _mats:
        _mats[name] = vl.mat(name, color, **kw)
    return _mats[name]


def _pick(name, seq, salt=0):
    return seq[(zlib.crc32(name.encode()) + salt) % len(seq)]


class House:
    def __init__(self, name):
        self.name = name
        self.objs = []
        self.panes = []
        self.power = None
        self.pos = (0.0, 0.0)
        self.windows = 0


def _wall_side(L, holes, place):
    """Wall of length L (u from -L/2 to L/2), height H, with openings [(u0, u1, z0, z1)]: boxes per cell of the grid
    formed by the edges of the openings. place(u, t, z) -> local (x, y, z) (t = 0 outer face, T inner face)."""
    us = sorted({-L / 2, L / 2, *[c for h in holes for c in h[:2]]})
    zs = sorted({0.0, H, *[c for h in holes for c in h[2:]]})
    parts = []
    for ua, ub in zip(us, us[1:]):
        for za, zb in zip(zs, zs[1:]):
            cu, cz = (ua + ub) / 2, (za + zb) / 2
            if any(h[0] < cu < h[1] and h[2] < cz < h[3] for h in holes):
                continue
            parts.append(_cell(ua, ub, 0.0, T, za, zb, place))
    return parts


def _cell(ua, ub, ta, tb, za, zb, place):
    v = [place(u, t, z) for z in (za, zb) for t in (ta, tb) for u in (ua, ub)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return v, f


def _opening(u0, u1, z0, z1, place, frame, glass, bars, shutters, door=False):
    """Frame (4 rails that intrude 2 cm into the opening), recessed glass (or plank door), crossbar and open shutters."""
    fw = 0.08
    frame += [_cell(u0 - fw, u0 + 0.02, -0.05, 0.12, z0 - (0 if door else fw), z1 + fw, place),
              _cell(u1 - 0.02, u1 + fw, -0.05, 0.12, z0 - (0 if door else fw), z1 + fw, place),
              _cell(u0 - fw, u1 + fw, -0.05, 0.12, z1 - 0.02, z1 + fw, place)]
    if not door:
        frame.append(_cell(u0 - fw - 0.04, u1 + fw + 0.04, -0.09, 0.12, z0 - fw, z0 + 0.02, place))   # peitoril
        glass.append(_cell(u0, u1, 0.07, 0.09, z0, z1, place))
        um, zm = (u0 + u1) / 2, (z0 + z1) / 2
        bars.append(_cell(um - 0.025, um + 0.025, 0.03, 0.075, z0, z1, place))
        bars.append(_cell(u0, u1, 0.03, 0.075, zm - 0.025, zm + 0.025, place))
        if shutters:
            w = (u1 - u0) / 2 + 0.02
            shutters.append(_cell(u0 - fw - w, u0 - fw - 0.01, -0.045, -0.005, z0, z1, place))
            shutters.append(_cell(u1 + fw + 0.01, u1 + fw + w, -0.045, -0.005, z0, z1, place))
    else:
        glass.append(_cell(u0, u1, 0.05, 0.09, z0, z1, place))          # door (door material, not glass)


def _slab(L, y_e, y_r, z_e, z_r, th, up=0.0, x0=None, x1=None):
    """Sloped roof slab between the eave (y_e, z_e) and the ridge (y_r, z_r), thickness th, length L."""
    dy, dz = y_r - y_e, z_r - z_e
    n = math.hypot(dy, dz)
    ny, nz = -dz / n * (1 if y_r > y_e else -1), dy / n * (1 if y_r > y_e else -1)
    if nz < 0:
        ny, nz = -ny, -nz
    x0 = -L / 2 if x0 is None else x0
    x1 = L / 2 if x1 is None else x1
    top = [(y_e + ny * up, z_e + nz * up), (y_r + ny * up, z_r + nz * up)]
    bot = [(y - ny * th, z - nz * th) for y, z in top]
    v = []
    for (y, z) in (bot[0], bot[1], top[0], top[1]):
        v += [(x0, y, z), (x1, y, z)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def house(name, x, y, rotz, nx=2, ny=2, windows=True, ridge_x=True, lit_mat=None, wall_set=None, mode=True, gable=False):
    """House centered at (x, y), rotated rotz (the front, with the door, looks toward local +y). nx x ny modules of S."""
    h = House(name)
    h.pos = (x, y)
    W, D = nx * S, ny * S
    cabin = mode == "cabin"
    wall_m = _m(f"HWall{name}", "#5A3E2A" if cabin else _pick(name, WALLS))
    trim_m = _m("HTrim", "#3A2A1E")
    stone_m = _m("HStone", "#6E6A62")
    door_m = _m("HDoor", "#4A3022")
    bar_m = _m("HBar", "#2E241C")
    shut_m = _m(f"HShut{name}", _pick(name, SHUTTERS, 3))
    roof_m = _m(f"HRoof{name}", "#4A3326" if cabin else _pick(name, ROOFS, 1))
    if lit_mat is None:
        glass_m, sock = vl.glow_mat(f"{name}Glow", GLOW, 0.0)
        kit.principled(glass_m).inputs["Base Color"].default_value = kit.lin("#1C2230")
        h.power = sock
    else:
        glass_m = lit_mat
    h.glow_mat = glass_m

    walls, frame, glass, doors, bars, shut, stone = [], [], [], [], [], [], []
    # sides: (length, place, name, how many modules)
    sides = {
        "N": (W, lambda u, t, z: (u, D / 2 - t, z), nx),
        "S": (W, lambda u, t, z: (-u, -D / 2 + t, z), nx),
        "E": (D - 2 * T, lambda u, t, z: (W / 2 - t, -u, z), ny),
        "W": (D - 2 * T, lambda u, t, z: (-W / 2 + t, u, z), ny),
    }
    for side, (L, place, n) in sides.items():
        holes = []
        for k in range(n):
            uc = (k - (n - 1) / 2) * S
            if side == "N" and k == n // 2:
                holes.append((uc - DOOR_W / 2, uc + DOOR_W / 2, 0.0, DOOR_H, "door"))
            elif windows:
                holes.append((uc - WIN_W / 2, uc + WIN_W / 2, SILL, SILL + WIN_H, "win"))
        walls += _wall_side(L, [hh[:4] for hh in holes], place)
        for u0, u1, z0, z1, kind in holes:
            if kind == "door":
                _opening(u0, u1, z0, z1, place, frame, doors, None, None, door=True)
                stone.append(_cell(u0 - 0.25, u1 + 0.25, -0.55, 0.0, -0.2, 0.14, place))       # stone step
            else:
                _opening(u0, u1, z0, z1, place, frame, glass, bars, shut)
                h.windows += 1
    # foundation, corner posts, wall plate
    stone.append(kit._box_geo(W + 0.16, D + 0.16, 0.5, -W / 2 - 0.08, -D / 2 - 0.08, -0.38))
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(kit._box_geo(0.24, 0.24, H, sx * W / 2 - 0.12 - sx * 0.03, sy * D / 2 - 0.12 - sy * 0.03, 0.0))
    frame.append(kit._box_geo(W + 0.08, 0.1, 0.16, -W / 2 - 0.04, D / 2 - 0.06, H - 0.17))
    frame.append(kit._box_geo(W + 0.08, 0.1, 0.16, -W / 2 - 0.04, -D / 2 - 0.04, H - 0.17))

    # roof (in the ridge frame: length along a, span along b) and gables
    span, length = (D, W) if ridge_x else (W, D)
    rise = span * 0.38
    ov_e, ov_g = 0.4, 0.3
    zr = H + rise
    k_e = rise / (span / 2)
    roof, ends, attic = [], [], []
    Lr = length + 2 * ov_g
    for sgn in (-1, 1):
        ye = sgn * (span / 2 + ov_e)
        ze = H - ov_e * k_e
        roof.append(_slab(Lr, ye, 0.0, ze, zr, 0.13, up=0.05))
        for gx in (-1, 1):                                                   # fascia (gable boards)
            a0 = gx * Lr / 2
            ends.append(_slab(Lr, ye, 0.0, ze, zr, 0.26, up=0.08, x0=min(a0 - 0.03 * gx, a0 + 0.05 * gx),
                              x1=max(a0 - 0.03 * gx, a0 + 0.05 * gx)))
    ends.append(kit._box_geo(Lr + 0.1, 0.18, 0.16, -Lr / 2 - 0.05, -0.09, zr + 0.02))          # cumeeira
    gables = []
    for gx in (-1, 1):                                                       # gable: wall triangle
        a_out = gx * length / 2
        a_in = gx * (length / 2 - T)
        v = [(a_out, -span / 2, H - 0.01), (a_out, span / 2, H - 0.01), (a_out, 0.0, zr - 0.05),
             (a_in, -span / 2, H - 0.01), (a_in, span / 2, H - 0.01), (a_in, 0.0, zr - 0.05)]
        f = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
        gables.append((v, f))
        if gable and windows:                                                # attic window (lights up with the house)
            zc = H + rise * 0.35
            attic.append(([(a_out + gx * 0.025, -0.28, zc - 0.3), (a_out + gx * 0.025, 0.28, zc - 0.3),
                           (a_out + gx * 0.025, 0.28, zc + 0.3), (a_out + gx * 0.025, -0.28, zc + 0.3),
                           (a_out + gx * 0.01, -0.36, zc - 0.38), (a_out + gx * 0.01, 0.36, zc - 0.38),
                           (a_out + gx * 0.01, 0.36, zc + 0.38), (a_out + gx * 0.01, -0.36, zc + 0.38)],
                          [(0, 1, 2, 3)]))
            h.windows += 1

    def ridge_frame(geo):
        v, f = geo
        if ridge_x:
            return v, f
        return [(b, a, z) for a, b, z in v], [tuple(reversed(t)) for t in f]

    def obj(nm, geos, mat, flip=False):
        if not geos:
            return None
        v, f, _ = kit.merge(*geos)
        o = kit.mesh_object(f"{name}{nm}", v, f, [mat], (x, y, 0.0))
        o.rotation_euler.z = rotz
        kit.fix_normals(o)
        h.objs.append(o)
        return o

    obj("Walls", walls + [ridge_frame(g) for g in gables], wall_m)
    obj("Trim", frame + [ridge_frame(g) for g in ends], trim_m)
    obj("Stone", stone, stone_m)
    obj("Door", doors, door_m)
    obj("Bars", bars, bar_m)
    obj("Shut", shut, shut_m)
    obj("Roof", [ridge_frame(g) for g in roof], roof_m)
    if attic:                                                                # attic frame (plate behind the glass)
        obj("AtticFrame", [ridge_frame(((v[4:]), [(0, 1, 2, 3)])) for v, _ in attic], trim_m)
    p = obj("Glass", glass + [ridge_frame((v[:4], f)) for v, f in attic], glass_m)
    if p is not None:
        p.visible_shadow = False
        h.panes.append(p)
    h.size = (W, D)
    h.rot, h.ridge_x = rotz, ridge_x
    h.height = zr
    return h
