"""Main street of a generic small American town (technology-disappeared): asphalt, sidewalks with curbs,
2-story brick townhouses with shops, signs without text, poles, traffic light.

Axes: the main street runs along y (the camera looks toward +y, the water tower sits on the hill to the north), x = 0 in the middle.
13 m roadway (two lanes + parking), 3.5 m sidewalks, facades at |x| = 10. Cross street at y = 45.

Proportions (real and low-poly references):
- 2-story commercial townhouse ("two-part commercial block", American Main Street, 1880-1930): 7 to 12 m
  frontage, 8 to 10 m high, shop ground floor with 3.5 to 4 m ceiling, display window on a ~0.5 m low wall,
  sign band between the ground floor and the 2nd floor, tall narrow windows (~1.1 x 1.8 m) and cornice at the top.
  Source: National Park Service, "Main Street Commercial Buildings" (Preservation Brief / Longstreth, "The
  Buildings of Main Street", 1987).
- Main street: 12 to 14 m between curbs, 3 to 4 m sidewalk, 15 cm curb. Pole of 7 to 8 m.
- Low-poly references: Kenney "City Kit (Commercial)" and Quaternius "Town/Buildings": simple volumes, windows
  as recessed panels with light frame, flat colors.
No brand, no legible sign: the signs are amber panels with abstract bars.
"""

import math
import random
from types import SimpleNamespace

import bpy

import kit
from kit import lin

ROAD_HALF = 6.5
FRONT = 10.0                 # fachada a |x| = 10
DEPTH = 16.0
CROSS_Y = 45.0
CROSS_HALF = 6.0
SOUTH = (-60.0, 35.5)        # south block (y of the facades)
NORTH = (54.5, 140.0)
GROCERY = (-1, 60.0, 74.0)   # west side, y0, y1
GROCERY_DEPTH = 13.0
FLOOR1 = 3.7                 # ground floor ceiling height
BRICKS = ["#7A3B2E", "#8C4A36", "#6B3A30", "#9A5A3E", "#B9A588", "#6E5A4E", "#84503C"]
TRIM = ["#D8CDB8", "#C9BFA8", "#3A4252", "#B8AE98"]
AWNINGS = ["#2F4A3A", "#5A2A2A", "#1F2E4A", "#6B5A2E"]
ASPHALT, CONCRETE, CURB, MARK, YELLOW = "#262B35", "#5F6672", "#6E7480", "#C8CCD2", "#C9A227"
GLASS = "#131A26"

_mats = {}


def mat(name, color, rough=0.95, emission=None, strength=0.0):
    """Flat material, no specular shine (in Standard the reflection blows out), reused by name."""
    if name not in _mats or _mats[name].name not in bpy.data.materials:
        m = kit.flat(name, color, rough=rough, emission=emission, strength=strength)
        kit.principled(m).inputs["Specular IOR Level"].default_value = 0.0
        _mats[name] = m
    return _mats[name]


class Geo:
    """Accumulates boxes and loose meshes into a single mesh with several materials (one object per building = light render)."""

    def __init__(self):
        self.parts, self.idx, self.mats = [], [], []

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def add(self, geo, m):
        self.parts.append(geo)
        self.idx.append(self._mi(m))

    def box(self, x0, x1, y0, y1, z0, z1, m):
        xa, xb = min(x0, x1), max(x0, x1)
        ya, yb = min(y0, y1), max(y0, y1)
        self.add(kit._box_geo(xb - xa, yb - ya, z1 - z0, xa, ya, z0), m)

    def dbox(self, x0, x1, y0, y1, z0, z1, m, eps=0.01):
        """Detail box (frame, glass, cornice) 1 cm larger on every side: sinks into the wall and the neighboring pieces,
        so no face is coplanar with another (no z-fighting on the windows, QA of 2026-10-22)."""
        self.box(min(x0, x1) - eps, max(x0, x1) + eps, min(y0, y1) - eps, max(y0, y1) + eps, z0 - eps, z1 + eps, m)

    def build(self, name):
        if not self.parts:
            return None
        verts, faces, owner = kit.merge(*self.parts)
        obj = kit.mesh_object(name, verts, faces, self.mats, face_mats=[self.idx[k] for k in owner])
        return kit.fix_normals(obj)


# ---------- ground ----------

def ground(g):
    """Asphalt, sidewalks, curbs and lane markings. Everything with thickness; nothing coplanar (markings 1 cm above)."""
    asphalt, concrete, curb = mat("Asphalt", ASPHALT), mat("Sidewalk", CONCRETE), mat("Curb", CURB)
    g.box(-ROAD_HALF, ROAD_HALF, -80, 150, -0.2, 0.0, asphalt)
    g.box(-160, 160, CROSS_Y - CROSS_HALF, CROSS_Y + CROSS_HALF, -0.2, 0.0, asphalt)
    for s in (1, -1):
        for y0, y1 in ((-80, CROSS_Y - CROSS_HALF), (CROSS_Y + CROSS_HALF, 150)):
            g.box(s * (ROAD_HALF + 0.2), s * FRONT, y0, y1, -0.2, 0.15, concrete)
            g.box(s * ROAD_HALF, s * (ROAD_HALF + 0.2), y0, y1, -0.2, 0.16, curb)
        for y0, y1 in ((CROSS_Y - CROSS_HALF - 3.5, CROSS_Y - CROSS_HALF), (CROSS_Y + CROSS_HALF, CROSS_Y + CROSS_HALF + 3.5)):
            g.box(s * FRONT, s * 160, y0, y1, -0.2, 0.15, concrete)
    line = mat("Marking", MARK)
    yellow = mat("Yellow", YELLOW)
    for y0, y1 in ((-80, CROSS_Y - CROSS_HALF - 3), (CROSS_Y + CROSS_HALF + 3, 150)):
        for dx in (-0.12, 0.12):
            g.box(dx - 0.06, dx + 0.06, y0, y1, 0.0, 0.012, yellow)
    g.box(0.2, ROAD_HALF - 2.6, CROSS_Y - CROSS_HALF - 2.6, CROSS_Y - CROSS_HALF - 2.2, 0.0, 0.012, line)
    g.box(-ROAD_HALF + 2.6, -0.2, CROSS_Y + CROSS_HALF + 2.2, CROSS_Y + CROSS_HALF + 2.6, 0.0, 0.012, line)
    for y in (CROSS_Y - CROSS_HALF - 1.6, CROSS_Y + CROSS_HALF + 1.6):          # crosswalks
        for k in range(-5, 6):
            x = k * 1.1
            g.box(x - 0.3, x + 0.3, y - 1.2, y + 1.2, 0.0, 0.012, line)


# ---------- sobrados ----------

def _x(s, d):
    """x of the facade on side s advancing d meters into the street (d < 0 = into the building)."""
    return s * (FRONT - d)


def _window(g, s, y0, y1, z0, z1, glass, trim):
    """Window: glass recessed 4 cm, frame protruding 12 cm, sill and lintel."""
    g.dbox(_x(s, 0), _x(s, 0.04), y0, y1, z0, z1, glass)
    for a, b in ((y0 - 0.1, y0), (y1, y1 + 0.1)):
        g.dbox(_x(s, 0), _x(s, 0.12), a, b, z0, z1, trim)
    g.dbox(_x(s, 0), _x(s, 0.12), y0, y1, z1, z1 + 0.1, trim)
    g.dbox(_x(s, 0), _x(s, 0.2), y0 - 0.18, y1 + 0.18, z0 - 0.14, z0, trim)
    g.dbox(_x(s, 0), _x(s, 0.14), y0 - 0.16, y1 + 0.16, z1 + 0.1, z1 + 0.3, trim)


def _storefront(g, s, y0, y1, glass, trim, dark, hollow=False):
    """Shop ground floor: pilasters, low wall, display window with mullions, recessed door and sign band."""
    w = y1 - y0
    for a, b in ((y0, y0 + 0.5), (y1 - 0.5, y1)):
        g.dbox(_x(s, 0), _x(s, 0.22), a, b, 0.15, FLOOR1, trim)
    door = y0 + 0.5 + (w - 1.0) * 0.62
    g.dbox(_x(s, 0), _x(s, 0.14), y0 + 0.5, y1 - 0.5, FLOOR1 - 0.75, FLOOR1, trim)      # sign band
    g.dbox(_x(s, 0), _x(s, 0.16), y0, y1, FLOOR1, FLOOR1 + 0.16, trim)                 # cinta
    for a, b in ((y0 + 0.5, door), (door + 1.15, y1 - 0.5)):
        if b - a < 0.4:
            continue
        g.dbox(_x(s, 0), _x(s, 0.12), a, b, 0.15, 0.7, dark)                           # mureta
        if not hollow:
            g.dbox(_x(s, -0.05), _x(s, 0.03), a, b, 0.7, FLOOR1 - 0.75, glass)
        g.dbox(_x(s, 0), _x(s, 0.09), a, b, 0.7, 0.8, trim)
        g.dbox(_x(s, 0), _x(s, 0.09), a, b, FLOOR1 - 0.85, FLOOR1 - 0.75, trim)
        n = max(1, int((b - a) / 1.6))
        for k in range(1, n):
            m = a + (b - a) * k / n
            g.dbox(_x(s, 0), _x(s, 0.09), m - 0.05, m + 0.05, 0.8, FLOOR1 - 0.85, trim)
    if not hollow:
        g.dbox(_x(s, -0.4), _x(s, -0.3), door, door + 1.15, 0.15, 2.4, dark)            # recessed door
        g.dbox(_x(s, -0.42), _x(s, -0.33), door + 0.15, door + 1.0, 1.1, 2.2, glass)
    g.dbox(_x(s, -0.5), _x(s, 0.05), door - 0.06, door + 1.21, 2.4, FLOOR1 - 0.75, trim)
    return door


def _awning(g, s, y0, y1, color):
    """Tilted awning with thickness and valance."""
    m = mat(f"Awning{color}", color)
    z_top, z_low, reach = FLOOR1 - 0.8, FLOOR1 - 1.35, 1.4
    v = []
    for y in (y0 + 0.6, y1 - 0.6):
        v += [(_x(s, 0.02), y, z_top), (_x(s, reach), y, z_low), (_x(s, reach), y, z_low - 0.06), (_x(s, 0.02), y, z_top - 0.06)]
    f = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (0, 3, 2, 1), (4, 5, 6, 7)]
    g.add((v, f), m)
    g.dbox(_x(s, reach - 0.04), _x(s, reach + 0.02), y0 + 0.6, y1 - 0.6, z_low - 0.32, z_low, m)


def building(name, s, y0, y1, height, rnd, hollow=False):
    """Two-story brick townhouse with shop. Returns SimpleNamespace(obj, sign, lit, sign_box, door_y)."""
    g = Geo()
    brick = mat(f"Brick{name}", rnd.choice(BRICKS))
    trim = mat(f"Trim{rnd.randrange(len(TRIM))}", TRIM[rnd.randrange(len(TRIM))])
    dark = mat("DarkWood", "#2A2622")
    glass = mat("Glass", GLASS, rough=0.4)
    lit = mat(f"Lit{name}", "#2A2410", emission=rnd.choice(("#F5A524", "#FFB347", "#E8963A")), strength=1.0)
    depth = GROCERY_DEPTH if hollow else DEPTH
    z_body = FLOOR1 if hollow else 0.0
    g.box(_x(s, -depth), _x(s, 0), y0, y1, z_body, height, brick)
    if hollow:
        g.box(_x(s, -0.3), _x(s, 0), y0, y1, FLOOR1 - 0.75, FLOOR1, brick)
    door = _storefront(g, s, y0, y1, lit if not hollow else glass, trim, dark, hollow)
    n = max(2, int((y1 - y0) / 2.7))
    for k in range(n):
        c = y0 + (y1 - y0) * (k + 0.5) / n
        _window(g, s, c - 0.55, c + 0.55, FLOOR1 + 0.9, FLOOR1 + 2.8, lit if rnd.random() < 0.4 else glass, trim)
    g.dbox(_x(s, -0.0), _x(s, 0.3), y0, y1, height - 0.75, height - 0.45, trim)            # cornija
    g.dbox(_x(s, -0.0), _x(s, 0.18), y0, y1, height - 0.45, height + 0.25, brick)          # platibanda
    g.dbox(_x(s, -depth), _x(s, 0.24), y0, y1, height + 0.25, height + 0.37, trim)
    if rnd.random() < 0.45 and not hollow:
        _awning(g, s, y0, y1, rnd.choice(AWNINGS))
    obj = g.build(name)
    sign_box = (_x(s, 0.18), _x(s, 0.26), y0 + 0.9, y1 - 0.9, FLOOR1 - 0.68, FLOOR1 - 0.1)
    return SimpleNamespace(obj=obj, lit=lit, sign_box=sign_box, door_y=door, side=s, y0=y0, y1=y1, height=height)


def _bars_geo(x0, x1, y0, y1, z0, z1, rnd):
    """Abstract sign bars (no letters): blocks of varied heights."""
    parts, y = [], y0 + 0.2
    while y < y1 - 0.4:
        w = rnd.uniform(0.18, 0.5)
        h = (z1 - z0) * rnd.choice((0.35, 0.55, 0.7))
        zc = (z0 + z1) / 2
        parts.append(kit._box_geo(abs(x1 - x0) + 0.02, w, h, min(x0, x1) - 0.01, y, zc - h / 2))
        y += w + rnd.uniform(0.1, 0.22)
    return parts


def sign(name, b, rnd):
    """Lit sign over the shop: dark amber panel with light emissive bars. Own object (vanishes)."""
    x0, x1, y0, y1, z0, z1 = b.sign_box
    panel = kit._box_geo(abs(x1 - x0), y1 - y0, z1 - z0, min(x0, x1), y0, z0)
    bars = _bars_geo(x0 + b.side * 0.0, x1 + b.side * 0.02, y0, y1, z0 + 0.06, z1 - 0.06, rnd)
    base = rnd.choice(("#3A2410", "#1F2E4A", "#4A1C1C", "#203A2C"))
    glow = rnd.choice(("#FFC46B", "#F5A524", "#FFE2A8"))
    m0 = mat(f"SignPanel{base}", base, emission=base, strength=0.6)
    m1 = mat(f"SignGlow{glow}", "#FFE9C0", emission=glow, strength=1.4)
    v, f, owner = kit.merge(panel, *bars)
    obj = kit.mesh_object(name, v, f, [m0, m1], face_mats=[0 if k == 0 else 1 for k in owner])
    return kit.fix_normals(obj)


def blocks(rnd):
    """Townhouses on both sides, in both blocks. The grocery (hollow inside) is on the west side, north."""
    out = []
    for s in (1, -1):
        for y0, y1 in (SOUTH, NORTH):
            y = y0
            while y < y1 - 4:
                w = min(rnd.uniform(7.5, 12.0), y1 - y)
                if s == GROCERY[0] and y < GROCERY[2] and y + w > GROCERY[1]:
                    if y < GROCERY[1]:
                        w = GROCERY[1] - y
                    else:
                        w = GROCERY[2] - GROCERY[1]
                hollow = s == GROCERY[0] and abs(y - GROCERY[1]) < 0.01
                h = 8.6 if hollow else rnd.uniform(7.6, 10.2)
                out.append(building(f"Bldg{'E' if s > 0 else 'W'}{len(out)}", s, y, y + w, h, rnd, hollow=hollow))
                y += w
    return out


# ---------- poles and traffic light ----------

def streetlight(name, x, y, s):
    """7.5 m pole with an arm over the roadway (s = side: +1 east, arm toward -x). Returns (objects, emission
    socket, light)."""
    g = Geo()
    pole = mat("Pole", "#2E333C", rough=0.7)
    g.add(kit._prism_geo(8, 0.13, 0.09, 7.3, oz=0.15, ox=x, oy=y), pole)
    g.add(kit._prism_geo(8, 0.2, 0.17, 0.5, oz=0.15, ox=x, oy=y), pole)
    g.box(x, x - s * 1.6, y - 0.06, y + 0.06, 7.2, 7.32, pole)
    g.box(x - s * 1.25, x - s * 2.0, y - 0.22, y + 0.22, 7.05, 7.3, pole)
    body = g.build(name)
    lamp_mat = bpy.data.materials.new(f"{name}Lamp")
    kit.principled(lamp_mat).inputs["Base Color"].default_value = lin("#E8D8B0")
    kit.principled(lamp_mat).inputs["Emission Color"].default_value = lin("#FFC46B")
    power = kit.principled(lamp_mat).inputs["Emission Strength"]
    power.default_value = 6.0
    lens = kit.mesh_object(f"{name}Lens", *kit._box_geo(0.66, 0.36, 0.06, x - s * 1.27 - (0.66 if s > 0 else 0), y - 0.18, 7.0),
                           [lamp_mat])
    light = bpy.data.lights.new(f"{name}Light", "SPOT")
    light.energy, light.color = 900.0, (1.0, 0.72, 0.42)
    light.spot_size, light.spot_blend = math.radians(120), 0.6
    light.shadow_soft_size = 0.25
    light.use_shadow = False                  # 20 poles with heavy shadows weighed down the render; the pool of light is enough
    lobj = bpy.data.objects.new(f"{name}Light", light)
    lobj.location = (x - s * 1.6, y, 6.9)
    bpy.context.collection.objects.link(lobj)
    return [body, lens, lobj], power, light


def streetlights():
    """Alternating poles every 18 m on both sides; returned in order of distance from the camera (to turn them off one
    by one to the horizon)."""
    out = []
    for k, y in enumerate(range(-24, 146, 17)):
        if abs(y - CROSS_Y) < CROSS_HALF + 1:
            continue
        s = 1 if k % 2 == 0 else -1
        objs, power, light = streetlight(f"Lamp{k}", s * (ROAD_HALF + 0.6), y, s)
        out.append(SimpleNamespace(objs=objs, power=power, light=light, y=y))
    out.sort(key=lambda l: l.y)
    return out


def traffic_light(name, x, y, s, facing_south=True):
    """Arm traffic light over the roadway, with three lamps; the red lit. Returns (objects, sockets)."""
    g = Geo()
    pole = mat("SignalPole", "#3A3F48", rough=0.7)
    g.add(kit._prism_geo(8, 0.16, 0.12, 6.2, oz=0.15, ox=x, oy=y), pole)
    g.box(x, x - s * 4.6, y - 0.08, y + 0.08, 5.9, 6.06, pole)
    head = mat("SignalHead", "#1E2228", rough=0.6)
    hx = x - s * 3.6
    g.box(hx - 0.22, hx + 0.22, y - 0.2, y + 0.2, 4.7, 5.9, head)
    dy = -0.21 if facing_south else 0.21
    for k, z in enumerate((5.55, 5.2, 4.85)):
        g.box(hx - 0.24, hx + 0.24, y + dy - (0.03 if facing_south else 0), y + dy + (0 if facing_south else 0.03),
              z - 0.16, z - 0.12, head)                                                       # pala
    body = g.build(name)
    red = bpy.data.materials.new(f"{name}Red")
    kit.principled(red).inputs["Base Color"].default_value = lin("#5A1410")
    kit.principled(red).inputs["Emission Color"].default_value = lin("#FF3A1E")
    kit.principled(red).inputs["Emission Strength"].default_value = 5.0
    off = mat("SignalOff", "#2A2E24", rough=0.5)
    lenses = []
    for k, z in enumerate((5.55, 5.2, 4.85)):
        geo = kit._prism_geo(8, 0.13, 0.13, 0.04, ox=0, oy=0)
        o = kit.mesh_object(f"{name}Lens{k}", *geo, [red if k == 0 else off], (hx, y + dy, z))
        o.rotation_euler = (math.radians(90 if facing_south else -90), 0, 0)
        lenses.append(o)
    return [body, *lenses]


def build(rnd):
    g = Geo()
    ground(g)
    street = g.build("Street")
    bl = blocks(rnd)
    signs = []
    srnd = random.Random(9)
    for b in bl:
        if srnd.random() < 0.8:
            signs.append(sign(f"Sign{b.obj.name}", b, srnd))
    lamps = streetlights()
    signals = traffic_light("SignalE", ROAD_HALF + 0.7, CROSS_Y - CROSS_HALF - 1.0, 1) + \
        traffic_light("SignalW", -(ROAD_HALF + 0.7), CROSS_Y + CROSS_HALF + 1.0, -1, facing_south=False)
    return SimpleNamespace(street=street, buildings=bl, signs=signs, lamps=lamps, signals=signals)
