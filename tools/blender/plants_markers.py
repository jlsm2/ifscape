"""plants-extinct: disposable MARKERS for the "camera and keyframes" step (2026-10-24).

Each marker is a simple box at the final place and size, just so the camera and framing make
sense. All are named "MK_*" and are replaced by the final model in the modeling stage. Nothing here is look.
"""

import math

import bpy
from mathutils import Vector

import kit
import plants_models as pm
import plants_set as ps

# final positions (meters; +y south/sea, +x west/right of the camera; z 0 = paving)
SHED = (-5.4, -2.4, -1.5, 1.5)          # grain shed 3 x 3 x 2.6 m, door on the east face (x = -2.4)
SACK = Vector((-2.0, 0.55, 0.0))       # open sack at the shed door (07, "grain")
BED = (-3.2, -2.2, 1.9, 3.9)             # flower bed 1 x 2 m south of the shed
FURROW_X = -2.7                          # 1.6 m furrow along y, in the middle of the bed
TUTOR = Vector((-2.7, 3.75, 0.0))        # 0.6 m stake with label, at the south end of the furrow
COW = Vector((-15.0, 10.6, 0.0))         # cow on the east hill terrace (06, "animals")
TOWER = Vector((254.0, 54.0, 0.0))       # mill tower on the west hill (05), ~100 m above the square
TABLE_EXT = (1.2, 2.1)                   # tabletop extension (the food went past the end of the 2.4 m top)


def _mat(name, color, emission=None, strength=0.0):
    m = pm.fixed_mat(f"MK_{name}", color, rough=0.9, emission=emission, strength=strength)
    return m


def _box(name, x0, x1, y0, y1, z0, h, mat):
    return kit.box_span(f"MK_{name}", x0, x1, y0, y1, z0, h, mat)


def build_table_ext(M):
    """Extra 0.9 m top at the right end of the stall, at the same height (cheese, ham and the 4th crate were
    in mid-air beyond x = 1.2). Disappears with the stall (NOW, WEEK, YEAR)."""
    x0, x1 = TABLE_EXT
    top = kit.box_span("MK_TableExt", x0, x1, 0.85, 1.65, 0.86, 0.04, M["wood"])
    legs = [kit.box_span(f"MK_TableExtLeg{k}", x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, 0.86, M["wood"])
            for k, (x, y) in enumerate(((x1 - 0.06, 0.9), (x1 - 0.06, 1.6)))]
    return [top, *legs]


def build_shed(M):
    """Stone shed (box) with dark door on the east face and an open sack at the door."""
    x0, x1, y0, y1 = SHED
    walls = _box("Shed", x0, x1, y0, y1, 0.0, 2.6, M["stone"])
    door = _box("ShedDoor", x1, x1 + 0.03, 0.0, 1.0, 0.0, 2.0, _mat("Door", "#3A2E24"))
    sack = _box("Sack", SACK.x - 0.2, SACK.x + 0.2, SACK.y - 0.15, SACK.y + 0.15, 0.0, 0.55, M["sack"])
    grain = _box("SackGrain", SACK.x - 0.17, SACK.x + 0.17, SACK.y - 0.12, SACK.y + 0.12, 0.55, 0.03,
                 _mat("Grain", "#C8A860"))
    return [walls, door, sack, grain]


def build_bed(M):
    """Flower bed: damp soil (NOW, WEEK) with dark furrow; lighter cracked soil in 1 YEAR and in YEARS; stake
    with label the same in all; 5 dark grains uncovered in 1 YEAR (08, "seeds")."""
    x0, x1, y0, y1 = BED
    wet = _box("BedWet", x0, x1, y0, y1, 0.0, 0.12, _mat("BedWet", "#5E4A36"))
    furrow = _box("Furrow", FURROW_X - 0.04, FURROW_X + 0.04, y0 + 0.2, y1 - 0.2, 0.12, 0.006, _mat("Furrow", "#3A2C20"))
    dry = _box("BedCracked", x0, x1, y0, y1, 0.0, 0.12, _mat("BedCracked", "#7E6A50"))
    cracks = []
    for k in range(5):           # cracks = thin dark streaks (Voronoi texture marker)
        y = y0 + 0.3 + 0.35 * k
        cracks.append(_box(f"Crack{k}", x0 + 0.08, x1 - 0.08, y, y + 0.02, 0.12, 0.004, _mat("Crack", "#4A3C2E")))
    grains = [_box(f"Seed{k}", FURROW_X - 0.012 + 0.03 * (k % 2), FURROW_X + 0.012 + 0.03 * (k % 2),
                   2.6 + 0.12 * k, 2.62 + 0.12 * k, 0.12, 0.012, _mat("Seed", "#3A2A1E")) for k in range(5)]
    tutor = _box("Tutor", TUTOR.x - 0.015, TUTOR.x + 0.015, TUTOR.y - 0.015, TUTOR.y + 0.015, 0.0, 0.6, M["wood"])
    label = _box("TutorLabel", TUTOR.x - 0.06, TUTOR.x + 0.06, TUTOR.y - 0.03, TUTOR.y - 0.015, 0.42, 0.08,
                 _mat("Label", "#E6DFD0"))
    return SimpleNS(wet=[wet, furrow], dry=[dry, *cracks], seeds=grains, fixed=[tutor, label])


class SimpleNS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def build_hands(M):
    """First-person hands (04): two skin-colored boxes resting on the back edge of the tabletop."""
    skin = _mat("Skin", "#C8916A")
    return [_box(f"Hand{k}", x - 0.05, x + 0.05, 0.86, 1.04, 0.9, 0.04, skin) for k, x in enumerate((-0.22, 0.22))]


def build_hand_07(M):
    """Hand of 07 (takes the handful, buries it in the furrow): a box animated by the set."""
    return _box("Hand07", -0.05, 0.05, -0.09, 0.09, -0.02, 0.04, _mat("Skin07", "#C8916A"))


def build_cow():
    """Cow (06): 2.2 x 0.8 x 1.4 m box on the terrace, head down eating straw."""
    z = ps.hill_z(COW.x, COW.y)
    body = _box("Cow", COW.x - 1.1, COW.x + 1.1, COW.y - 0.4, COW.y + 0.4, z + 0.6, 0.8, _mat("Cow", "#E8E4DA"))
    head = _box("CowHead", COW.x + 1.0, COW.x + 1.5, COW.y - 0.2, COW.y + 0.2, z + 0.25, 0.45, _mat("CowH", "#2A2622"))
    legs = _box("CowLegs", COW.x - 0.9, COW.x + 0.9, COW.y - 0.3, COW.y + 0.3, z - 0.3, 0.9, _mat("CowL", "#2A2622"))
    return [body, head, legs]


def build_tower_trail(M):
    """Mill tower (8 m diameter, 10 m + dark conical roof) on top of the west hill and the zigzag
    trail up to it (strips of light earth 1.4 m wide), with 1 person climbing (05, "this hill")."""
    zt = ps.west_hill_z(TOWER.x, TOWER.y)
    body = kit.prism("MK_Tower", (TOWER.x, TOWER.y, zt - 1.0), 10, 4.0, 3.6, 11.0, M["stone"])
    roof = kit.prism("MK_TowerRoof", (TOWER.x, TOWER.y, zt + 10.0), 10, 4.6, 0.0, 4.5, _mat("Roof", "#4A4038"))
    a = Vector((24.0, 9.0, 0))
    b = TOWER + Vector((-6.0, -3.0, 0))
    d = (b - a)
    side = Vector((-d.y, d.x, 0)).normalized()
    legs = 7
    pts = [a]
    for k in range(1, legs):
        pts.append(a + d * (k / legs) + side * (16.0 if k % 2 else -16.0))
    pts.append(b)
    segs = []
    for p, q in zip(pts, pts[1:]):
        n = max(2, int((q - p).length / 6))
        for j in range(n):
            u0, u1 = j / n, (j + 1) / n
            s0, s1 = p.lerp(q, u0), p.lerp(q, u1)
            t = (s1 - s0)
            w = Vector((-t.y, t.x, 0)).normalized() * 0.7
            z0 = ps.west_hill_z(s0.x, s0.y) + 0.25
            z1 = ps.west_hill_z(s1.x, s1.y) + 0.25
            segs.append(([(s0.x - w.x, s0.y - w.y, z0), (s0.x + w.x, s0.y + w.y, z0), (s1.x + w.x, s1.y + w.y, z1),
                          (s1.x - w.x, s1.y - w.y, z1)], [(0, 1, 2, 3)]))
    v, f, _ = kit.merge(*segs)
    trail = pm.obj_from("MK_Trail", (v, f), [_mat("Trail", "#D9C9A4")])
    trail.visible_shadow = False
    c = pts[4].lerp(pts[5], 0.4)
    zc = ps.west_hill_z(c.x, c.y)
    climber = _box("Climber", c.x - 0.3, c.x + 0.3, c.y - 0.3, c.y + 0.3, zc, 1.75, _mat("Climber", "#B8583A"))
    return [body, roof, trail, climber]


def build_amber_band(M, f_sweep, f_sweep_end, f_ham, f_off):
    """Amber strip of the 83% (06): thin emissive plate over the storable food, growing from left to right
    at 'straight' in 1.2 s; thin outline on the cheeses/ham at 'ham'. Disappears at the end of 06."""
    amber = _mat("Amber", "#F5A524", emission="#F5A524", strength=0.8)
    band = _box("AmberBand", -0.3, 1.32, 0.95, 1.6, 1.03, 0.012, amber)
    band.visible_shadow = False
    # grows by x scale from the left edge (kit.box puts the origin at the bottom corner)
    for f, s in ((f_sweep - 1, 0.001), (f_sweep, 0.001), (f_sweep_end, 1.0)):
        band.scale = (s, 1, 1)
        band.keyframe_insert("scale", frame=f)
    ring = []
    for k, (x0, x1, y0, y1) in enumerate(((1.30, 1.60, 0.96, 1.24), (1.67, 1.96, 0.95, 1.34))):
        for j, (a0, a1, b0, b1) in enumerate(((x0, x1, y0, y0 + 0.015), (x0, x1, y1 - 0.015, y1),
                                              (x0, x0 + 0.015, y0, y1), (x1 - 0.015, x1, y0, y1))):
            o = _box(f"Contour{k}{j}", a0, a1, b0, b1, 1.05, 0.012, amber)
            o.visible_shadow = False
            ring.append(o)
    return band, ring


def build_leaf_burst(origin, yaw, pitch, f0, f1, rnd):
    """Gust of 05 ("rotted"): 14 dry leaves (plates) crossing the sky from right to left at ~9 m."""
    mat = _mat("Leaf", "#8A5A2B")
    ya, pa = math.radians(yaw), math.radians(pitch)
    fwd = Vector((math.sin(ya) * math.cos(pa), math.cos(ya) * math.cos(pa), math.sin(pa)))
    right = Vector((math.cos(ya), -math.sin(ya), 0))
    up = right.cross(fwd).normalized()
    leaves = []
    for k in range(14):
        c = origin + fwd * rnd.uniform(7.5, 10.5) + up * rnd.uniform(-2.5, 3.0)
        start = c + right * (3.2 + rnd.uniform(0, 1.5))
        end = c - right * (3.5 + rnd.uniform(0, 1.5)) + up * rnd.uniform(-0.8, 0.4)
        o = _box(f"Leaf{k}", -0.07, 0.07, -0.05, 0.05, -0.006, 0.012, mat)
        o.visible_shadow = False
        for f in range(f0, f1 + 1, 2):
            u = (f - f0) / (f1 - f0)
            o.location = start.lerp(end, u)
            o.rotation_euler = (2.0 * u * math.pi + k, 1.3 * u * math.pi, 0.7 * k)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        leaves.append(o)
    return leaves
