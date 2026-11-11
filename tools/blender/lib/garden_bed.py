"""Vegetable garden bed 1 x 2 m: loose soil with a furrow (damp) or soil cracked into plates (dry), stone border,
wooden stake with a label, dark grains in the furrow. Low-poly; the cracked soil is a material (distorted Voronoi,
10-25 cm plates, wide dark cracks, light dust on top of the plates) over a low relief.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Proportions: direction.md §5 item 9 (bed 1 x 2 m, furrow
1.6 m x 5 cm, stake 0.6 m); art.md §1.3 (cracked soil: 5-9-sided polygons of 10-25 cm, cracks #4A3C2E >= 4 px).

soil(name, x0, x1, y0, y1, furrow_x, mat, depth, rnd) -> object (mesh with the furrow dug out)
border(name, x0, x1, y0, y1, mat, rnd) -> object (stones)
cracked_mat(name, plate, crack, dust) -> material
stake(name, location, wood, label_mat) -> object (stake root)
seeds(name, points, mat, rnd) -> object
"""

import math

from mathutils import Vector, noise

import kit
import plants_models as pm
from kit import lin

TOP = 0.12           # top of the soil (the bed is slightly raised above the paving)


def _columns(x0, x1, fx, w):
    xs = [x0 + (x1 - x0) * i / 10 for i in range(11)]
    xs += [fx - w * 1.6, fx - w * 0.5, fx, fx + w * 0.5, fx + w * 1.6]
    return sorted(set(round(x, 4) for x in xs if x0 <= x <= x1))


def soil(name, x0, x1, y0, y1, furrow_x, mat, rnd, depth=0.045, width=0.05, ridge=0.015, f_y0=None, f_y1=None,
         lump=0.012, furrow_mat=None):
    """Soil grid with the furrow running along y at furrow_x (V profile with the soil pushed toward the edges)."""
    f_y0 = y0 + 0.2 if f_y0 is None else f_y0
    f_y1 = y1 - 0.2 if f_y1 is None else f_y1
    xs = _columns(x0, x1, furrow_x, width)
    ny = 24
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    verts = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            z = TOP + lump * noise.noise(Vector((x * 7.0, y * 7.0, 0.4)))
            if i in (0, len(xs) - 1) or j in (0, ny):
                z = TOP - 0.04                                       # low edge (disappears under the stones)
            d = abs(x - furrow_x)
            inside = f_y0 <= y <= f_y1
            taper = 1.0 if inside else 0.0
            if inside:
                taper = min(1.0, (y - f_y0) / 0.08, (f_y1 - y) / 0.08)
            if d < width * 0.6:
                z -= depth * taper * (1 - d / (width * 0.6))
            elif d < width * 1.7:
                z += ridge * taper * math.sin(math.pi * (d - width * 0.6) / (width * 1.1))
            verts.append((x, y, z))
    nx = len(xs)
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(ny) for i in range(nx - 1)]
    fm = None
    if furrow_mat is not None:                     # furrow bottom in another color (freshly opened soil)
        fm = []
        for fc in faces:
            cx = sum(verts[q][0] for q in fc) / 4
            cy = sum(verts[q][1] for q in fc) / 4
            fm.append(1 if abs(cx - furrow_x) < width * 0.6 and f_y0 + 0.04 < cy < f_y1 - 0.04 else 0)
    # side skirt down to the ground (the bed does not float)
    base = len(verts)
    ring = [(x, y0) for x in xs] + [(x1, y) for y in ys[1:]] + [(x, y1) for x in reversed(xs[:-1])] + \
           [(x0, y) for y in reversed(ys[1:-1])]
    for x, y in ring:
        verts += [(x, y, TOP - 0.04), (x, y, 0.0)]
    m = len(ring)
    faces += [(base + 2 * k, base + 2 * ((k + 1) % m), base + 2 * ((k + 1) % m) + 1, base + 2 * k + 1)
              for k in range(m)]
    if fm is not None:
        fm += [0] * (len(faces) - len(fm))
    o = pm.obj_from(name, (verts, faces), [mat] + ([furrow_mat] if furrow_mat is not None else []), face_mats=fm)
    return o


def border(name, x0, x1, y0, y1, mat, rnd, size=0.11):
    """Rounded stones all around (half their height buried), ~16 to 20 stones."""
    geos = []
    per = 2 * ((x1 - x0) + (y1 - y0))
    n = int(per / (size * 1.9))
    for k in range(n):
        d = per * k / n
        if d < x1 - x0:
            p = (x0 + d, y0)
        elif d < (x1 - x0) + (y1 - y0):
            p = (x1, y0 + d - (x1 - x0))
        elif d < 2 * (x1 - x0) + (y1 - y0):
            p = (x1 - (d - (x1 - x0) - (y1 - y0)), y1)
        else:
            p = (x0, y1 - (d - 2 * (x1 - x0) - (y1 - y0)))
        s = size * rnd.uniform(0.8, 1.15)
        v, f = pm.lumpy_ico(s, (p[0], p[1], s * 0.35), (1.15, 1.0, 0.7), rnd, 0.15)
        geos.append((v, f))
    v, f, _ = kit.merge(*geos)
    return pm.obj_from(name, (v, f), [mat])


def cracked_mat(name, plate="#7E6A50", crack="#4A3C2E", dust="#968266", scale=6.0):
    """Cracked soil: Voronoi (distance to edge) with noise distortion; crack = edge < threshold; each plate varies
    ±7% and the middle of the plate lightens (dust); bump in the cracks for shadow."""
    mat, n, L, p = pm.node_mat(name, 0.95, 0.1)
    coord = n.new("ShaderNodeTexCoord")
    warp = n.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 3.0
    warp.inputs["Detail"].default_value = 2.0
    L.new(coord.outputs["Object"], warp.inputs["Vector"])
    mixv = n.new("ShaderNodeMix"); mixv.data_type = "VECTOR"
    mixv.inputs["Factor"].default_value = 0.06
    L.new(coord.outputs["Object"], mixv.inputs["A"])
    L.new(warp.outputs["Color"], mixv.inputs["B"])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = scale
    vor.inputs["Randomness"].default_value = 0.9
    L.new(mixv.outputs["Result"], vor.inputs["Vector"])
    cell = n.new("ShaderNodeTexVoronoi")              # color per plate
    cell.inputs["Scale"].default_value = scale
    cell.inputs["Randomness"].default_value = 0.9
    L.new(mixv.outputs["Result"], cell.inputs["Vector"])
    edge = n.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value, edge.inputs["From Max"].default_value = 0.035, 0.05
    L.new(vor.outputs["Distance"], edge.inputs["Value"])
    mid = n.new("ShaderNodeMapRange")
    mid.inputs["From Min"].default_value, mid.inputs["From Max"].default_value = 0.06, 0.25
    L.new(vor.outputs["Distance"], mid.inputs["Value"])
    dcol = n.new("ShaderNodeMix"); dcol.data_type = "RGBA"
    L.new(mid.outputs["Result"], dcol.inputs["Factor"])
    dcol.inputs["A"].default_value = lin(plate)
    dcol.inputs["B"].default_value = lin(dust)
    var = n.new("ShaderNodeMapRange")
    var.inputs["To Min"].default_value, var.inputs["To Max"].default_value = 0.93, 1.07
    sep = n.new("ShaderNodeSeparateColor")
    L.new(cell.outputs["Color"], sep.inputs[0])
    L.new(sep.outputs[0], var.inputs["Value"])
    hsv = n.new("ShaderNodeHueSaturation")
    L.new(dcol.outputs["Result"], hsv.inputs["Color"])
    L.new(var.outputs["Result"], hsv.inputs["Value"])
    fin = n.new("ShaderNodeMix"); fin.data_type = "RGBA"
    L.new(edge.outputs["Result"], fin.inputs["Factor"])
    fin.inputs["A"].default_value = lin(crack)
    L.new(hsv.outputs["Color"], fin.inputs["B"])
    L.new(fin.outputs["Result"], p.inputs["Base Color"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.01
    L.new(edge.outputs["Result"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], p.inputs["Normal"])
    return mat


def stake(name, location, wood, label_mat, h=0.6):
    """3 x 3 cm stake with a point and a label (12 x 7 cm tag with 2 strokes of 'writing')."""
    x, y, z = location
    parts = [kit._box_geo(0.03, 0.03, h - 0.03, -0.015, -0.015, 0.0),
             ([(-0.015, -0.015, h - 0.03), (0.015, -0.015, h - 0.03), (0.015, 0.015, h - 0.03),
               (-0.015, 0.015, h - 0.03), (0, 0, h)], [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)])]
    v, f, _ = kit.merge(*parts)
    root = pm.obj_from(name, (v, f), [wood], location=(x, y, z))
    lab = kit._box_geo(0.12, 0.012, 0.07, -0.06, -0.03, h * 0.62)
    ink = [kit._box_geo(0.08, 0.002, 0.008, -0.045, -0.0315, h * 0.62 + z0) for z0 in (0.042, 0.022)]
    v, f, own = kit.merge(lab, *ink)
    pm.obj_from(f"{name}Label", (v, f), [label_mat, pm.fixed_mat(f"{name}Ink", "#3A3430")], parent=root,
                face_mats=[0 if k == 0 else 1 for k in own])
    return root


def seeds(name, points, mat, rnd, length=0.018):
    geos = []
    for (x, y, z) in points:
        v, f = kit._gem_geo(length / 2, oz=0.0, stretch=1.0)
        a = rnd.uniform(0, math.pi)
        sq = []
        for (px, py, pz) in v:                                     # flattened capsule: long along local x
            px, py, pz = px, py * 0.55, pz * 0.45
            sq.append((x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a), z + pz))
        geos.append((sq, f))
    v, f, _ = kit.merge(*geos)
    return pm.obj_from(name, (v, f), [mat])


def surface_z(x, y, lump=0.012, depth=0.045, width=0.05, furrow_x=0.0):
    """Soil height at a point inside the furrow (same formula as the grid, without the border)."""
    z = TOP + lump * noise.noise(Vector((x * 7.0, y * 7.0, 0.4)))
    d = abs(x - furrow_x)
    if d < width * 0.6:
        z -= depth * (1 - d / (width * 0.6))
    return z
