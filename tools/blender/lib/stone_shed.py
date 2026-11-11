"""Mediterranean stone shed (little grain house): thick stone walls, plank door open outward,
wooden lintel, single-pitch roof in terracotta channel tile with eaves. Flat low-poly, ~260 triangles.

SOURCE: procedural (Ifscape, 2026-10-24, plants-extinct). Proportions: 3 x 3 m rural shed, ceiling height 2.6 m
(direction.md §5 item 9), door 1 x 2 m, 0.3 m walls (typical dry stone masonry), channel tile ~0.2 m.

build(name, x0, x1, y0, y1, mats, door=(y_a, y_b), height=2.6) -> SimpleNamespace(root, walls, door, roof, inside)
The door is on the east face (x = x1), between y_a and y_b, hinged at y_a, with the leaf open ~105° outward.
mats: {"stone", "wood", "roof", "dark"}.
"""

import math
from types import SimpleNamespace

from mathutils import Matrix, Vector

import kit
import plants_models as pm


def build(name, x0, x1, y0, y1, mats, door=(0.0, 1.0), height=2.6, door_h=2.0, wall=0.3, open_deg=105.0):
    root = pm._empty(name, ((x0 + x1) / 2, (y0 + y1) / 2, 0.0))
    cx, cy = root.location.x, root.location.y
    ya, yb = door
    hf, hb = height + 0.1, height - 0.25          # front (east) wall higher: roof slopes down to the west

    def B(xa, xb, ya_, yb_, za, zb):
        return kit._box_geo(xb - xa, yb_ - ya_, zb - za, xa - cx, ya_ - cy, za)

    parts = []
    # north and south walls (sloped top: one quad per wall with an inclined top)
    for (ya_, yb_) in ((y0, y0 + wall), (y1 - wall, y1)):
        v = [(x0 - cx, ya_ - cy, 0), (x1 - cx, ya_ - cy, 0), (x1 - cx, yb_ - cy, 0), (x0 - cx, yb_ - cy, 0),
             (x0 - cx, ya_ - cy, hb), (x1 - cx, ya_ - cy, hf), (x1 - cx, yb_ - cy, hf), (x0 - cx, yb_ - cy, hb)]
        f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        parts.append((v, f))
    # west wall (back)
    parts.append(B(x0, x0 + wall, y0 + wall, y1 - wall, 0, hb))
    # east wall with the door opening: two pillars and the upper panel
    parts.append(B(x1 - wall, x1, y0 + wall, ya, 0, hf))
    parts.append(B(x1 - wall, x1, yb, y1 - wall, 0, hf))
    parts.append(B(x1 - wall, x1, ya, yb, door_h + 0.12, hf))
    # stone threshold
    parts.append(B(x1 - wall, x1 + 0.12, ya - 0.05, yb + 0.05, 0, 0.06))
    v, f, _ = kit.merge(*parts)
    walls = pm.obj_from(f"{name}Walls", (v, f), [mats["stone"]], parent=root)
    # dark packed-earth floor inside (the interior stays in shadow; no bright emptiness)
    floor = pm.obj_from(f"{name}Floor", B(x0 + wall, x1 - wall, y0 + wall, y1 - wall, 0.0, 0.02),
                        [mats["dark"]], parent=root)
    # wooden lintel over the door, and door frame
    lint = [B(x1 - 0.04, x1 + 0.04, ya - 0.12, yb + 0.12, door_h, door_h + 0.12)]
    for y in (ya - 0.06, yb):
        lint.append(B(x1 - 0.02, x1 + 0.04, y, y + 0.06, 0.06, door_h))
    v, f, _ = kit.merge(*lint)
    pm.obj_from(f"{name}Lintel", (v, f), [mats["wood"]], parent=root)
    # door leaf: 4 planks + 2 crossbars, pivot at the hinge (child of the root; rotates on z)
    hinge = pm._empty(f"{name}Hinge", (x1 - cx, ya - cy, 0.06), parent=root)
    w = yb - ya
    planks = []
    for k in range(4):
        planks.append(kit._box_geo(0.04, w / 4 - 0.008, door_h - 0.08, -0.04, k * w / 4, 0.0))
    for z in (0.3, door_h - 0.5):
        planks.append(kit._box_geo(0.03, w - 0.1, 0.12, 0.0, 0.05, z))
    v, f, _ = kit.merge(*planks)
    leaf = pm.obj_from(f"{name}Door", (v, f), [mats["wood"]], parent=hinge)
    hinge.rotation_euler = (0, 0, -math.radians(open_deg))
    # roof: inclined slab with eaves + rows of channel tile (half-prisms) running down to the west
    ov = 0.28
    za, zb = hf + 0.02, hb + 0.02
    run = (x1 + ov) - (x0 - ov)
    slope = math.atan2(za - zb, x1 - x0)
    roof_parts = []
    slab = kit._box_geo(run / math.cos(slope), (y1 - y0) + 2 * ov, 0.08, 0.0, -(y1 - y0) / 2 - ov, 0.0)
    rows = []
    n_rows = int(((y1 - y0) + 2 * ov) / 0.24)
    for r in range(n_rows):
        y = -(y1 - y0) / 2 - ov + 0.12 + r * 0.24
        tile = kit.xform_geo(kit._prism_geo(6, 0.1, 0.1, run / math.cos(slope) + 0.06, oz=-0.03),
                             Matrix.Translation((0.0, y, 0.1)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        # only the top half of the prism shows (the bottom half is inside the slab)
        rows.append(tile)
    roof_parts += [slab, *rows]
    v, f, _ = kit.merge(*roof_parts)
    # the slab starts at the east eave and slopes down to the west
    m = Matrix.Translation((x1 + ov - cx, 0.0, za + ov * math.tan(slope))) @ Matrix.Rotation(math.pi, 4, "Z") @ \
        Matrix.Rotation(slope, 4, "Y")
    v = [tuple(m @ Vector(p)) for p in v]
    roof = pm.obj_from(f"{name}Roof", (v, f), [mats["roof"]], parent=root)
    return SimpleNamespace(root=root, walls=walls, door=leaf, hinge=hinge, roof=roof, floor=floor,
                           inside=(x0 + wall, x1 - wall, y0 + wall, y1 - wall))
