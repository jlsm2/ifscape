"""Mediterranean tower windmill (Mykonos / Alentejo type): whitewashed cylindrical tower, slightly conical, dark
conical roof, door and 2 dark windows, shaft with 4 canvas sails (rectangular) that turn slowly.
Made to be read from afar (~250 m): thick shapes, nothing thinner than ~0.25 m. ~300 triangles.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Proportions: Mykonos windmills are ~6-8 m in diameter
and 8-12 m of wall height, sails of ~8 m radius (art.md §1.1: >= 14 px wide in the frame of 05; 8 m
diameter with a dark conical roof). Visual reference: Kato Mili windmills (Mykonos), Kenney windmill (the sail only).

build(name, base, mats, facing, radius=4.0, height=10.0) -> SimpleNamespace(root, sails)
base = (x, y, ground z); facing = heading (radians, 0 = +x) toward which the sails face.
mats: {"wall", "roof", "dark", "wood", "sail"}.
"""

import math
from types import SimpleNamespace

from mathutils import Matrix

import kit
import plants_models as pm


def build(name, base, mats, facing, radius=4.0, height=10.0, sink=1.5):
    root = pm._empty(name, base)
    root.rotation_euler = (0, 0, facing)
    n = 14
    body = kit._prism_geo(n, radius, radius * 0.92, height + sink, oz=-sink)
    pm.obj_from(f"{name}Body", body, [mats["wall"]], parent=root)
    # eaves (ring) and conical roof
    eave = kit._prism_geo(n, radius * 1.02, radius * 1.02, 0.35, oz=height)
    roof = kit._prism_geo(n, radius * 1.1, 0.15, radius * 1.05, oz=height + 0.35)
    v, f, _ = kit.merge(eave, roof)
    pm.obj_from(f"{name}Roof", (v, f), [mats["roof"]], parent=root)
    # door (heading -60° from the axis) and windows: dark plates slightly outside the wall (no coplanar faces)
    holes = []
    for ang, z0, w, h in ((-0.9, 0.0, 1.3, 2.3), (0.35, height * 0.55, 0.8, 1.1), (-0.4, height * 0.3, 0.8, 1.1)):
        r = radius * (1 - 0.08 * (z0 + h / 2) / height) + 0.06
        g = kit._box_geo(0.1, w, h, r - 0.05, -w / 2, z0)
        holes.append(kit.xform_geo(g, Matrix.Rotation(ang, 4, "Z")))
    v, f, _ = kit.merge(*holes)
    pm.obj_from(f"{name}Openings", (v, f), [mats["dark"]], parent=root)
    # sail shaft leaving the roof along local +x, tilted slightly up
    hub_z = height - 0.2
    hub = pm._empty(f"{name}Hub", (radius * 0.98, 0.0, hub_z), parent=root)
    hub.rotation_euler = (0, math.radians(-8), 0)
    axle = kit.xform_geo(kit._prism_geo(8, 0.35, 0.3, 1.6, oz=-0.6), Matrix.Rotation(math.pi / 2, 4, "Y"))
    pm.obj_from(f"{name}Axle", axle, [mats["wood"]], parent=hub)
    sails = pm._empty(f"{name}Sails", (0.9, 0.0, 0.0), parent=hub)
    spars, cloth = [], []
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        rot = Matrix.Rotation(a, 4, "X")
        spars.append(kit.xform_geo(kit._box_geo(0.22, 0.24, 8.2, -0.11, -0.12, 0.0), rot))
        # 1.7 m rectangular sail beside the spar, from 2.2 to 7.8 m, twisted 12° (windmill blade)
        sv = [(-0.05, 0.12, 2.2), (-0.05, 1.82, 2.2), (0.3, 1.82, 7.8), (0.05, 0.12, 7.8)]
        sail_geo = (sv + [(x + 0.08, y, z) for x, y, z in sv], [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                                                              (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
        cloth.append(kit.xform_geo(sail_geo, rot))
    v, f, own = kit.merge(*spars, *cloth)
    so = pm.obj_from(f"{name}Blades", (v, f), [mats["wood"], mats["sail"]], parent=sails,
                     face_mats=[0 if k < 4 else 1 for k in own])
    return SimpleNamespace(root=root, sails=sails, blades=so)
