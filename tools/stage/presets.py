"""Ready-made stages and lights: ground with hills in the distance, sky dome, sun and automatic dressing out to the horizon.

A stage = ground + sky dome + sun + 'dress' (catalog pieces scattered in rings, so the background never looks
empty: the 'set without an empty look' rule). The light only changes slowly (no flickering sky).
"""

import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import kit  # noqa: E402
from lib import anim_curves as ac  # noqa: E402

import models  # noqa: E402
import park  # noqa: E402
import procedural  # noqa: E402
import riverside  # noqa: E402
import validate  # noqa: E402

FLAT_R = 45.0            # inside this radius the ground is flat (action stage and camera)
HILL_R = 330.0           # radius of the drawn ground
SKY_R = 1800.0

# colors: sRGB hex. ground = 3 tones alternating per face (low-poly in patches).
SETS = {
    "meadow": dict(ground=("#6C974C", "#709B4F", "#6A9449", "#73A052", "#6B954B"), far="#5F8F4A", clouds=14,
                   dress=[dict(kind="plant", tag="grass", n=420, r=(0.7, 14), h=(0.15, 0.4)),
                          dict(kind="plant", tag="grass", n=320, r=(1.2, 45), h=(0.22, 0.55)),
                          dict(kind="plant", tag="grass", n=220, r=(20, 110), h=(0.4, 0.9)),
                          dict(kind="tree", pack="quaternius/stylized-nature", n=90, r=(18, 150), h=(8, 13)),
                          dict(kind="bush", n=70, r=(8, 120), h=(0.8, 1.6)),
                          dict(kind="plant", n=140, r=(4, 70), h=(0.4, 0.9)),
                          dict(kind="rock", n=30, r=(10, 140), h=(0.8, 2.2))]),
    "savanna": dict(ground=("#B39A4E", "#AE9549", "#B7A053", "#B5A052", "#AC9449"), far="#A38C4E", clouds=8,
                    dress=[dict(kind="plant", tag="grass", n=260, r=(0.7, 14), h=(0.15, 0.45)),
                           dict(kind="plant", tag="grass", n=240, r=(1.5, 60), h=(0.3, 0.7)),
                           dict(kind="dead-tree", n=26, r=(14, 160), h=(5, 8)),
                           dict(kind="bush", n=60, r=(8, 140), h=(0.9, 1.7)),
                           dict(kind="plant", n=180, r=(3, 90), h=(0.5, 1.0)),
                           dict(kind="rock", n=40, r=(10, 170), h=(0.8, 2.6))]),
    "forest": dict(ground=("#52803C", "#56833F", "#4F7A3A", "#58853F", "#517C3B"), far="#3F6A35", clouds=10,
                   dress=[dict(kind="plant", tag="grass", n=200, r=(0.7, 14), h=(0.15, 0.4)),
                          dict(kind="plant", tag="grass", n=180, r=(1.5, 40), h=(0.25, 0.5)),
                          dict(kind="tree", pack="quaternius/stylized-nature", n=110, r=(10, 150), h=(9, 15)),
                          dict(kind="pine", n=90, r=(14, 160), h=(11, 17)),
                          dict(kind="bush", n=70, r=(5, 90), h=(0.9, 1.7)),
                          dict(kind="mushroom", n=24, r=(4, 40), h=(0.2, 0.4)),
                          dict(kind="log", n=18, r=(6, 60), h=(0.5, 0.9)),
                          dict(kind="rock", n=24, r=(8, 120), h=(0.8, 2.0))]),
    "desert": dict(ground=("#D8B97A", "#CFAE6E", "#E1C484", "#D4B375", "#DCC080"), far="#D2B578", clouds=4,
                   dress=[dict(kind="cactus", n=40, r=(10, 150), h=(1.8, 4.5)),
                          dict(kind="rock", n=60, r=(8, 190), h=(1.0, 4.0)),
                          dict(kind="dead-tree", n=10, r=(20, 160), h=(3, 5))]),
    "vacuo": dict(ground=("#10151F", "#0E131C", "#121824"), far="#0B0F17", dress=[]),
    # sea out to the horizon (procedural.build_ocean): water, wooden pier in front of the camera, islands, buoys and boats
    # far away; behind the camera, beach and hills with the dressing (land only)
    "ocean": dict(ground=("#C9B587", "#BFA97A", "#CDB98C", "#C4AF80", "#B9A374"), grass="#6E8E4E", far="#5F8F4A",
                  clouds=12, water="#2C6A84",
                  dress=[dict(kind="plant", tag="grass", n=260, r=(46, 120), h=(0.3, 0.7), land=True),
                         dict(kind="tree", pack="quaternius/stylized-nature", n=70, r=(60, 220), h=(7, 12), land=True),
                         dict(kind="palm", n=10, r=(48, 90), h=(6, 9), land=True),
                         dict(kind="bush", n=50, r=(48, 160), h=(0.8, 1.6), land=True),
                         dict(kind="rock", n=40, r=(42, 160), h=(0.6, 2.2), land=True)]),
    # city park with buildings around (park.py: lawn, paths, plaza, benches, lamp posts, streets, cars, 3 layers
    # of buildings); the dressing here is only the lawn grass ('lawn': outside paths, plaza and hedge)
    "park": dict(ground=("#6E9A4C",), far="#8C8A86", clouds=10, park=True,
                 dress=[dict(kind="plant", ids=("grass-common-short", "grass-short"), n=2200, r=(0.7, 12), h=(0.12, 0.22),
                             lawn=True, tag="grass"),     # tag grass: grows near the pieces (no smooth lawn around)
                        dict(kind="plant", ids=("grass-common-short",), n=260, r=(1.0, 16), h=(0.24, 0.34), lawn=True),
                        dict(kind="flower", pack="quaternius/stylized-nature", n=320, r=(1.0, 16), h=(0.08, 0.14), lawn=True),
                        dict(kind="plant", ids=("grass-common-short", "grass-short"), n=700, r=(6, 50), h=(0.14, 0.24),
                             lawn=True)]),
    # city riverside (riverside.py): promenade, river between quay walls, cable-stayed footbridge, crane,
    # sequoia, 3 layers of buildings and a mountain range in the back; no scattered dressing
    "riverside": dict(ground=("#B9B2A6",), far="#8C8A86", clouds=0, riverside=True, dress=[]),   # no clouds: they crossed the mountain range
}

LIGHTS = {  # sun: strength, elevation and azimuth in degrees, color; ambient; sky (zenith, horizon)
    "noon":     dict(sun=3.5, el=58, az=35, color="#FFF1DA", amb=1.3, sky=("#6FA8E8", "#D6E6F4")),
    "dawn":     dict(sun=2.2, el=12, az=70, color="#FFC48E", amb=1.4, sky=("#7690C4", "#F5C79C")),
    "dusk":     dict(sun=2.4, el=9, az=-80, color="#FF9A55", amb=1.5, sky=("#566AA2", "#F29A6A"),
                     fill=3.2, fill_color="#6A84E6"),      # cold fill from the side opposite the sun (violet shadow)
    "night":    dict(sun=0.45, el=38, az=-40, color="#A5B8FF", amb=0.4, sky=("#060A15", "#18233D"), lamp=1.0),
    "overcast": dict(sun=1.0, el=45, az=20, color="#E7EDF5", amb=2.0, sky=("#9AA6B2", "#CBD1D8")),
    "dry-noon": dict(sun=3.0, el=64, az=20, color="#FFEBC8", amb=1.0, sky=("#78B0E6", "#E9E2CC")),
    # late afternoon (sun at 22 degrees, behind and to the left of the POV camera: back facades lit, long shadows
    # forward and to the right), blue sky that warms at the horizon; weak cold fill
    "afternoon": dict(sun=2.6, el=22, az=-40, color="#FFD39C", amb=1.35, sky=("#5F8FD6", "#C9D6E4"),
                      fill=1.4, fill_color="#7C8FD8"),
    # low golden afternoon (ants-human-size scene 07): sun at 11 degrees, zenith still blue, peach horizon,
    # without the salmon veil of 'dusk' (the grass stays green, darker)
    "golden": dict(sun=2.3, el=11, az=-55, color="#FFB877", amb=1.25, sky=("#4E6FB0", "#E8B48A"),
                   fill=1.6, fill_color="#7C8FD8"),
}


for _l in LIGHTS.values():          # ambient at 78%, sun +25%: shadow and volume instead of everything flat
    _l["amb"] *= 0.78
    _l["sun"] *= 1.25

assert tuple(SETS) == validate.SETS and tuple(LIGHTS) == validate.LIGHTS, "validate.py e presets.py divergem"


def _lin(h):
    return kit.lin(h)


def set_active(set_name: str) -> None:
    """Which stage governs the ground height (ground_height) of the pieces that come next."""
    procedural.ACTIVE["ocean"] = set_name == "ocean"
    procedural.ACTIVE["park"] = set_name == "park"
    procedural.ACTIVE["riverside"] = set_name == "riverside"


def ground_height(x: float, y: float) -> float:
    """Soft hills only far from the stage (r > FLAT_R); sum of waves, no randomness (same value on every calculation).
    On the 'ocean' stage: pier top (0), the water (procedural.WATER_Z) or the beach."""
    if procedural.ACTIVE["ocean"]:
        return procedural.surface_height(x, y)
    if procedural.ACTIVE.get("riverside"):            # walkways at z = 0, sway, footbridge deck, water
        return riverside.surface_height(x, y)
    if procedural.ACTIVE.get("park"):                 # flat city: lawn, paths and sidewalk at z = 0
        return 0.0
    r = math.hypot(x, y)
    if r <= FLAT_R:
        return 0.0
    k = min(1.0, (r - FLAT_R) / 120.0)
    k = k * k * (3 - 2 * k)
    h = (math.sin(x * 0.021 + 1.3) * math.cos(y * 0.017) + 0.6 * math.sin(x * 0.047 - y * 0.039 + 2.1)
         + 0.35 * math.cos(x * 0.09 + y * 0.083)) * 9.0
    return k * max(h, -2.0)


def _ground(coll, sdef, rng):
    """Low-poly ground with per-vertex color (smooth gradient between the stage's darkest and lightest tone, in wide
    patches of coherent noise): without the straight seams of per-face colors, which looked like a badly made asset."""
    n = 180
    ocean = "water" in sdef
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = i / n * 2 - 1, j / n * 2 - 1
            # denser mesh at the center: cubic u,v concentrate vertices near the stage
            x, y = HILL_R * (u * abs(u) * 0.6 + u * 0.4), HILL_R * (v * abs(v) * 0.6 + v * 0.4)
            verts.append((x, y, procedural.terrain_height(x, y) if ocean else ground_height(x, y)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    tones = sorted((kit.lin(c) for c in sdef["ground"]), key=lambda c: c[0] + c[1] * 2 + c[2])
    lo, hi = tones[0], tones[-1]
    mat = kit.flat("ground", sdef["ground"][0], rough=1.0)
    nt = mat.node_tree
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    nt.links.new(attr.outputs["Color"], kit.principled(mat).inputs["Base Color"])
    obj = kit.mesh_object("ground", verts, faces, [mat], face_mats=[0] * len(faces))
    cols = obj.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    flat = []
    for (x, y, _z) in verts:
        t = 0.5 + 0.3 * (math.sin(x * 0.045 + 1.7) * math.cos(y * 0.037)
                         + 0.7 * math.sin(x * 0.013 - y * 0.019 + 0.6)) + rng.uniform(-0.05, 0.05)
        t = min(1.0, max(0.0, t))
        c = [lo[k] + (hi[k] - lo[k]) * t for k in range(3)]
        if ocean:                                   # sand on the beach, grass above 1.2 m
            g = kit.lin(sdef["grass"])
            w = min(1.0, max(0.0, (_z - 1.2) / 2.5))
            c = [c[k] + (g[k] * (0.9 + 0.2 * t) - c[k]) * w for k in range(3)]
        flat += c + [1.0]
    cols.data.foreach_set("color", flat)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def _dome(coll, sky_colors):
    """Inverted sphere with an emissive gradient (horizon -> zenith); casts no shadow."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=SKY_R)
    dome = bpy.context.active_object
    dome.name = "sky"
    dome.pass_index = 1
    mat = bpy.data.materials.new("skydome")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = SKY_R * 0.75
    noise = nt.nodes.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    jit = nt.nodes.new("ShaderNodeMath")
    jit.operation = "MULTIPLY_ADD"
    jit.inputs[1].default_value = 0.018        # noise amplitude (~2 levels of 8 bits in the gradient)
    jit.inputs[2].default_value = -0.009
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.name = "SkyRamp"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = _lin(sky_colors[1])
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = _lin(sky_colors[0])
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    L = nt.links
    L.new(coord.outputs["Object"], sep.inputs[0])
    L.new(sep.outputs["Z"], div.inputs[0])
    L.new(coord.outputs["Object"], noise.inputs["Vector"])
    L.new(noise.outputs["Value"], jit.inputs[0])
    L.new(div.outputs[0], add.inputs[0])
    L.new(jit.outputs[0], add.inputs[1])
    L.new(add.outputs[0], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], em.inputs["Color"])
    L.new(em.outputs[0], out.inputs["Surface"])
    dome.data.materials.append(mat)
    dome.visible_shadow = False
    for c in list(dome.users_collection):
        c.objects.unlink(dome)
    coll.objects.link(dome)
    return dome, nt


def _sun(coll, light):
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = light["sun"]
    sun.data.color = _lin(light["color"])[:3]
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = (math.radians(90 - light["el"]), 0, math.radians(light["az"]))
    coll.objects.link(sun)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))   # cold fill, no shadow
    fill.data.energy = light.get("fill", 0.0)
    fill.data.use_shadow = False
    coll.objects.link(fill)
    sun["fill"] = fill.name
    return sun


class Env:
    """Stage built: what the light needs to change slowly (sun, sky ramp) and the accumulated keys."""

    def __init__(self, sun, sky_nt, light, water=None):
        self.sun, self.sky_nt, self.light = sun, sky_nt, light
        self.keys: dict[str, list[tuple[int, float]]] = {}
        self.water = water                          # water material ('ocean' stage): the 'water' cue changes the color
        self.water_keys: list[tuple[int, tuple]] = []

    def key_water(self, f0: int, f1: int, hexa: str):
        """The water color goes slowly (smooth and monotonic) to 'hexa' between f0 and f1."""
        if self.water is None:
            return
        sock = self.water.nodes["Sea"].outputs[0]
        cur = self.water_keys[-1][1] if self.water_keys else tuple(sock.default_value)
        self.water_keys += [(f0, cur), (f1, kit.lin(hexa))]

    def key(self, frame: int, light: dict):
        """Records the light state on the frame (writing all the curves is in write_keys)."""
        zen, hor = _lin(light["sky"][0]), _lin(light["sky"][1])
        vals = {"amb": [light["amb"]], "energy": [light["sun"]], "color": list(_lin(light["color"])[:3]),
                "wcol": [(zen[i] + hor[i]) / 2 for i in range(3)],
                "rot": [math.radians(90 - light["el"]), 0.0, math.radians(light["az"])],
                "sky0": list(_lin(light["sky"][1])), "sky1": list(_lin(light["sky"][0])),
                "lamp": [light.get("lamp", 0.0)], "fill": [light.get("fill", 0.0)],
                "fcol": list(_lin(light.get("fill_color", "#8899CC"))[:3]),
                "frot": [math.radians(90 - 40), 0.0, math.radians(light["az"] + 180)]}
        for name, v in vals.items():
            for i, x in enumerate(v):
                chan = self.keys.setdefault(f"{name}{i}", [])
                if chan and chan[-1][0] == frame:
                    chan[-1] = (frame, x)
                else:
                    chan.append((frame, x))
        self.light = light

    def write_keys(self):
        """Writes the sun and sky curves (LINEAR). The world ambient is written by the build (it is global)."""
        for i in range(3):
            fr, v = zip(*self.keys[f"color{i}"]); ac.write(self.sun.data, "color", i, fr, v)
            fr, v = zip(*self.keys[f"rot{i}"]); ac.write(self.sun, "rotation_euler", i, fr, v)
        fr, v = zip(*self.keys["energy0"]); ac.write(self.sun.data, "energy", 0, fr, v)
        fill = bpy.data.objects.get(self.sun.get("fill", ""))
        if fill is not None:
            fr, v = zip(*self.keys["fill0"]); ac.write(fill.data, "energy", 0, fr, v)
            for i in range(3):
                fr, v = zip(*self.keys[f"fcol{i}"]); ac.write(fill.data, "color", i, fr, v)
                fr, v = zip(*self.keys[f"frot{i}"]); ac.write(fill, "rotation_euler", i, fr, v)
        fr, v = zip(*self.keys["lamp0"])
        for lp in procedural.LAMPS:                  # pier lamp posts: turn on and off together with the light state
            ac.write(lp.light.data, "energy", 0, fr, [x * lp.power for x in v])
            ac.write(lp.bulb.node_tree, 'nodes["Principled BSDF"].inputs["Emission Strength"].default_value', 0, fr,
                     [x * 6.0 for x in v])
        if self.water is not None and self.water_keys:
            pts = sorted(self.water_keys)
            frames = sorted({f for f, _ in pts} | set(range(pts[0][0], pts[-1][0] + 1, 3)))
            for i in range(4):
                vals = []
                for f in frames:
                    for (f0, a), (f1, b) in zip(pts, pts[1:]):
                        if f0 <= f <= f1:
                            u = (f - f0) / max(f1 - f0, 1)
                            u = u * u * (3 - 2 * u)
                            vals.append(a[i] + (b[i] - a[i]) * u)
                            break
                    else:
                        vals.append(pts[0][1][i] if f < pts[0][0] else pts[-1][1][i])
                ac.write(self.water, 'nodes["Sea"].outputs[0].default_value', i, frames, vals)
        for el, name in ((0, "sky0"), (1, "sky1")):
            for i in range(4):
                fr, v = zip(*self.keys[f"{name}{i}"])
                ac.write(self.sky_nt, f'nodes["SkyRamp"].color_ramp.elements[{el}].color', i, fr, v)


def write_world(groups):
    """World color keyed with the light (in place of the old fixed white) and distance mist in the compositor.
    The mist blends the image with the horizon color up to 45%, from 20 to 350 m (Mist), and does not reach the sky dome."""
    scene = bpy.context.scene
    names = [f"wcol{i}" for i in range(3)] + [f"sky0{i}" for i in range(3)]
    keys = {n: sorted(f_v for g in groups for f_v in g["env"].keys[n]) for n in names}
    for i in range(3):
        fr, v = zip(*keys[f"wcol{i}"])
        ac.write(scene.world.node_tree, 'nodes["Background"].inputs[0].default_value', i, fr, v)
    scene.world.mist_settings.start, scene.world.mist_settings.depth = 20.0, 330.0
    scene.world.mist_settings.falloff = "LINEAR"
    vl = scene.view_layers[0]
    vl.use_pass_mist = True
    vl.use_pass_z = True                                            # Eevee has no Object Index: the sky comes out by depth
    ng = bpy.data.node_groups["Look"]
    N, L = ng.nodes, ng.links
    rl = next(n for n in N if n.type == "R_LAYERS")
    first = rl.outputs["Image"].links[0].to_socket                  # who received the image (bloom)
    sky = N.new("ShaderNodeMath")                                   # the sky dome sits at 1,800 m; the ground ends at 330 m
    sky.operation = "GREATER_THAN"
    sky.inputs[1].default_value = 1000.0
    L.new(rl.outputs["Depth"], sky.inputs[0])
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L.new(sky.outputs[0], inv.inputs[1])                            # 1 outside the sky, 0 in the sky
    amt = N.new("ShaderNodeMath")
    amt.operation, amt.use_clamp = "MULTIPLY", True
    amt.inputs[1].default_value = 0.45
    L.new(rl.outputs["Mist"], amt.inputs[0])
    both = N.new("ShaderNodeMath")
    both.operation = "MULTIPLY"
    L.new(amt.outputs[0], both.inputs[0])
    L.new(inv.outputs[0], both.inputs[1])
    fog = N.new("ShaderNodeMix")
    fog.name = "FogMix"
    fog.data_type = "RGBA"
    L.new(both.outputs[0], fog.inputs[0])
    L.new(rl.outputs["Image"], fog.inputs[6])
    L.new(fog.outputs[2], first)
    fog.inputs[7].default_value = (0.8, 0.85, 0.9, 1.0)
    for i in range(3):
        fr, v = zip(*keys[f"sky0{i}"])
        ac.write(ng, 'nodes["FogMix"].inputs[7].default_value', i, fr, v)


def build(coll, set_name: str, light_name: str, rng: random.Random, keepout=(), span=(1, 1)):
    """Builds the stage in the collection. Returns the Env (initial light in env.light; key on the start frame belongs to build).
    span = (first, last frame) of the group of scenes (what floats rocks in it)."""
    if set_name not in SETS:
        raise ValueError(f"stage.set '{set_name}' unknown. Options: {sorted(SETS)}")
    if light_name not in LIGHTS:
        raise ValueError(f"stage.light '{light_name}' unknown. Options: {sorted(LIGHTS)}")
    sdef, light = SETS[set_name], LIGHTS[light_name]
    set_active(set_name)
    targets = {}
    if sdef.get("park"):
        park.build_park(coll, sdef, rng, keepout)
    elif sdef.get("riverside"):
        targets = riverside.build_riverside(coll, sdef, rng, keepout, span)
    else:
        _ground(coll, sdef, rng)
    water = procedural.build_ocean(coll, sdef, rng, *span) if "water" in sdef else None
    _dome_obj, sky_nt = _dome(coll, light["sky"])
    sun = _sun(coll, light)
    clouds(coll, sdef.get("clouds", 0), rng)
    dress(coll, sdef, rng, keepout)
    env = Env(sun, sky_nt, light, water)
    env.targets = targets                           # cue targets the stage creates (riverside)
    return env


def clouds(coll, count: int, rng: random.Random):
    """Low-poly clouds: groups of flattened ico-spheres, white and matte, far and high (cast no shadow).
    A single mesh, shared by all the pieces (light)."""
    if not count:
        return
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0)
    base = bpy.context.active_object
    base.name = "cloud_base"
    for p in base.data.polygons:
        p.use_smooth = False
    base.data.materials.append(kit.flat("cloud", "#D3DAE6", rough=1.0))
    for c in list(base.users_collection):
        c.objects.unlink(base)
    for k in range(count):
        a, r = rng.uniform(0, math.tau), rng.uniform(700, 1500)
        cx, cy, cz = r * math.cos(a), r * math.sin(a), rng.uniform(140, 380)
        size = rng.uniform(45, 95)
        for j in range(rng.randint(3, 5)):
            o = bpy.data.objects.new(f"cloud{k}_{j}", base.data)
            o.location = (cx + rng.uniform(-1, 1) * size * 0.9, cy + rng.uniform(-1, 1) * size * 0.4,
                          cz + rng.uniform(-0.15, 0.15) * size)
            s = size * rng.uniform(0.45, 0.9)
            o.scale = (s * 1.5, s * 0.9, s * 0.45)
            o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            o.visible_shadow = False
            coll.objects.link(o)


def dress(coll, sdef, rng, keepout=()):
    """Scatters the 'dress' pieces in rings (r0, r1), away from the stage; z follows the ground relief."""
    for spec in sdef["dress"]:
        pool = list(spec["ids"]) if spec.get("ids") else models.pool_of({**spec, "pack": spec.get("pack", "quaternius/")})
        if not pool:
            continue
        pool = rng.sample(pool, min(len(pool), 10))      # few variations per type: loads fast
        for k in range(spec["n"]):
            r0, r1 = spec["r"]
            # grass grows near the stage's pieces (forbidden zone of 15%); the rest of the dressing stays away from them
            shrink = 0.15 if spec.get("tag") == "grass" else 1.0
            for _ in range(8):
                a, r = rng.uniform(0, math.tau), math.sqrt(rng.uniform(r0 * r0, r1 * r1))
                x, y = r * math.cos(a), r * math.sin(a)
                if spec.get("land") and not procedural.is_land(x, y):
                    continue
                if spec.get("lawn") and not park.on_lawn(x, y):
                    continue
                if all(math.hypot(x - kx, y - ky) > kr * shrink for kx, ky, kr in keepout):
                    break
            else:
                if spec.get("land") or spec.get("lawn"):
                    continue
            ident = rng.choice(pool)
            obj = models.static_instance(ident, f"d_{spec['kind']}{k}", coll,
                                         height=rng.uniform(*spec["h"]))
            obj.location = (x, y, ground_height(x, y) - 0.02)
            obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
