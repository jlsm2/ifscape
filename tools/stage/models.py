"""Catalog models in Blender: a static piece becomes a light instance (shared mesh); with a skeleton, rigs.py.

Static: imports the file once, joins the meshes into one (baked transforms), feet at z = 0 and center at
x = y = 0. Each instance is a new object with the same mesh, scaled to the height asked for in meters: the pack's
native scale (Kenney ~1 m, Quaternius FBX in cm) does not matter.
"""

import json
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import kit  # noqa: E402
import rigs  # noqa: E402

CATALOG = {i["id"]: i for i in json.loads((ROOT / "tools" / "stage" / "catalog.json").read_text(encoding="utf-8"))["items"]}
ASSETS = ROOT / "assets"
# Typical length (m) of rigged four-legged walkers, or height (people): the script may ask for another with len/h.
DEFAULT_LEN = {"chicken": 0.45, "trex": 12.0, "apatosaurus": 21.0, "triceratops": 8.0, "stegosaurus": 8.0, "velociraptor": 2.0,
               "parasaurolophus": 9.0, "cow": 2.4, "farm-animals-horse": 2.4, "horse": 2.4, "zebra": 2.3, "llama": 1.8,
               "pig": 1.5, "sheep": 1.3, "pug": 0.7, "fox": 0.8, "raccoon": 0.7, "rat": 0.3, "ant": 1.7}
HUMANS = {"man", "womancasual", "animatedhuman"}
RIG_KEY = {"man": "man", "womancasual": "woman", "animatedhuman": "human", "fox": "fox", "rat": "rat", "horse": "horse",
           "trex": "trex", "apatosaurus": "apatosaurus"}      # keys rigs.py already knew; the rest is registered here
_static: dict[str, SimpleNamespace] = {}


SEASONAL = ("autumn", "snow", "twistedtree", "plant-7")   # autumn, snow and the red-leaf trees only come out if the script asks


def pool_of(spec: dict) -> list[str]:
    """Catalog ids that match kind (+ pack, tag, season); without 'season', only the green version, no autumn or snow."""
    season = spec.get("season")
    out = []
    for i in CATALOG.values():
        if i["kind"] != spec["kind"] or (spec.get("pack") and spec["pack"] not in i["pack"]):
            continue
        if spec.get("tag") and spec["tag"] not in i["tags"]:
            continue
        seasonal = [w for w in SEASONAL if w in i["id"]]
        if (season and season not in i["id"]) or (not season and seasonal):
            continue
        out.append(i["id"])
    return sorted(out)


def resolve(spec: dict, rng: random.Random) -> str:
    """Catalog id for a props item: 'id' (text or list) or 'kind' (+ 'pack', 'tag', 'season') drawn at random."""
    if "id" in spec:
        ident = rng.choice(spec["id"]) if isinstance(spec["id"], list) else spec["id"]
    else:
        pool = pool_of(spec)
        if not pool:
            raise ValueError(f"props: no model of type '{spec['kind']}' (pack={spec.get('pack')}, tag={spec.get('tag')})")
        ident = rng.choice(pool)
    if ident not in CATALOG:
        raise ValueError(f"props: '{ident}' is not in tools/stage/catalog.json")
    return ident


def is_rigged(ident: str) -> bool:
    item = CATALOG[ident]
    return bool(item["rigged"]) and item["actions"] != [] and item["kind"] in ("animal", "bird", "dino", "person", "insect") \
        and item["pack"] != "kenney/mini-characters"


def _import(path: Path):
    before = set(bpy.data.objects)
    if path.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False)
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def static_template(ident: str) -> SimpleNamespace:
    """Single mesh of the model, feet at z = 0, centered on x and y. Creates once and keeps it."""
    if ident in _static:
        return _static[ident]
    new = _import(ASSETS / CATALOG[ident]["file"])
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise ValueError(f"'{ident}' has no mesh")
    for o in meshes:
        o.data.transform(o.matrix_world)                  # bakes parent, rotation and scale into the mesh
        o.parent = None
        o.matrix_world = o.matrix_world.__class__.Identity(4)
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    joined = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=joined, selected_editable_objects=meshes, selected_objects=meshes):
            bpy.ops.object.join()
    me = joined.data
    import kit
    for m in me.materials:                                  # old FBX files arrive with Alpha 0 (invisible in Eevee)
        p = kit.principled(m) if m and m.node_tree else None
        if p is not None and not p.inputs["Alpha"].is_linked:
            p.inputs["Alpha"].default_value = 1.0
    xs, ys, zs = zip(*(v.co for v in me.vertices))
    cx, cy, z0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
    me.transform(__import__("mathutils").Matrix.Translation((-cx, -cy, -z0)))
    height = max(zs) - z0
    me.name = f"stage_{ident}"
    for p in me.polygons:
        p.use_smooth = False
    bpy.data.objects.remove(joined, do_unlink=True)      # only the mesh stays; the instances use it
    tpl = SimpleNamespace(mesh=me, height=height, width=max(max(xs) - min(xs), max(ys) - min(ys)))
    _static[ident] = tpl
    return tpl


VARIED = {"tree", "dead-tree", "pine", "palm", "bush", "plant", "flower", "cactus", "mushroom", "rock", "log"}
_tinted: set = set()


def _make_tintable(mesh):
    """Multiplies each material's base color by the object's color (Object Info), once per mesh: each instance
    can have its own tone without a new material."""
    for mat in mesh.materials:
        if mat is None or mat.name in _tinted or not mat.use_nodes:
            continue
        _tinted.add(mat.name)
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        sock = bsdf.inputs["Base Color"]
        info = nt.nodes.new("ShaderNodeObjectInfo")
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        if sock.links:
            nt.links.new(sock.links[0].from_socket, mix.inputs[6])
        else:
            mix.inputs[6].default_value = sock.default_value
        nt.links.new(info.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], sock)


def static_instance(ident: str, name: str, collection, height: float | None = None, scale: float | None = None):
    tpl = static_template(ident)
    obj = bpy.data.objects.new(name, tpl.mesh)
    collection.objects.link(obj)
    k = scale if scale else (height or CATALOG[ident]["height_m"]) / max(tpl.height, 1e-6)
    obj.scale = (k, k, k)
    obj.rotation_mode = "XYZ"
    if CATALOG[ident]["kind"] in VARIED:
        rng = random.Random(f"{ident}{name}")             # deterministic: the still and the video come out the same
        obj.scale = (k * rng.uniform(0.88, 1.12), k * rng.uniform(0.88, 1.12), k * rng.uniform(0.9, 1.16))
        _make_tintable(tpl.mesh)
        g = rng.uniform(0.9, 1.1)
        obj.color = (rng.uniform(0.9, 1.08) * g, g, rng.uniform(0.82, 1.04) * g, 1.0)
    return obj


# Packs without color (the Eagle FBX comes all gray 0.8): repaints by material name when the piece is created.
RECOLOR = {"eagle": {"Wings": "#4B3626", "Head": "#EDE8DC", "Beak": "#E3A91F", "Claws": "#2A2623"}}


def _recolor(ident: str, rig):
    for o in rigs.all_objects(rig):
        for slot in getattr(o, "material_slots", []):
            hexa = RECOLOR.get(ident, {}).get(slot.material.name.split(".")[0] if slot.material else "")
            if hexa:
                slot.material = kit.flat(f"{ident}_{slot.material.name.split('.')[0]}", hexa, rough=0.9)


def rig_spawn(ident: str, name: str, collection, length: float | None = None, height: float | None = None):
    """Rig from rigs.py (copies the template, brings the actions). Moves the created objects to the scene collection."""
    key = RIG_KEY.get(ident, ident)
    if CATALOG[ident]["file"] == "procedural:ant":           # ant made in code (ant.py): template registered in rigs
        import ant
        ant.ensure_template()
    if key not in rigs.SPECS:
        rigs.SPECS[key] = CATALOG[ident]["file"]
    if ident in HUMANS:
        rig = rigs.spawn(key, name, height=height or 1.75)
    else:
        rig = rigs.spawn(key, name, length=length or DEFAULT_LEN.get(ident, 1.5))
    _recolor(ident, rig)
    for o in rigs.all_objects(rig):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collection.objects.link(o)
    return rig


def feet_of(rig) -> list[str]:
    """Foot bones of the skeleton, to calibrate the step: leaves of the leg chain ('Foot', 'LowLeg_end'...).
    If any name has 'foot', only those; otherwise the 'leg' leaves. Without a leg (eagle), an empty list."""
    leaves = [b.name for b in rig.t.arm.data.bones if not b.children]
    legs = [n for n in leaves if any(k in n.lower() for k in ("foot", "leg", "paw", "hoof"))]
    feet = [n for n in legs if "foot" in n.lower()] or legs
    return [n for n in feet if "up" not in n.lower()]


def pick_action(rig, wanted: str) -> str:
    """Action name in the template by suffix, case-insensitive ('walk' finds 'Walk', 'Velociraptor_Walk')."""
    names = list(rig.t.actions)
    low = wanted.lower()
    for n in names:
        if n.lower() == low:
            return n
    for n in names:
        if n.lower().endswith("_" + low) or n.lower().startswith(low + "."):
            return n
    for n in names:
        if low in n.lower():
            return n
    raise KeyError(f"'{rig.key}' does not have the action '{wanted}'. It has: {sorted(names)}")


def ground_z_of(obj_or_rig) -> float:
    return 0.0


def facing(a, b) -> float:
    """Direction (radians, 0 = +x) from a to b (points x, y)."""
    return math.atan2(b[1] - a[1], b[0] - a[0])
