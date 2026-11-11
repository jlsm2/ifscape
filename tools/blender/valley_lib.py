"""Parts of the two-humans-left valley: import GLB as a mold and instantiate (shared mesh), materials, voice.

Proportions: adult 1.75 m (man) and 1.62 m (woman), CDC growth charts; door 2 m; Kenney brick/panel = 1 unit.
Assets: Kenney Fantasy Town Kit and Nature Kit (CC0), Quaternius people (CC0).
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

import kit

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
TOWN = ASSETS / "kenney/fantasy-town-kit/Models/GLB format"
NATURE = ASSETS / "kenney/nature-kit/Models/GLTF format"
_cache = {}


_imgs = {}


def _pixels(img):
    import numpy as np
    if img.name not in _imgs:
        w, h = img.size
        a = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        _imgs[img.name] = (a.reshape(h, w, 4), w, h)
    return _imgs[img.name]


def _remap(r, g, b, mode=True):
    """Brand palette. mode True/'wood': salmon/orange/brown becomes warm dark brown wood, lilac becomes stone;
    'green': only greens and turquoises become field green; 'stone': everything becomes warm gray stone; 'plant': greens
    and turquoises become green, the rest stays."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if mode == "cabin":
        return colorsys.hsv_to_rgb(0.075, 0.5, 0.16 + v * 0.30)
    if mode == "stone":
        return colorsys.hsv_to_rgb(0.09, 0.10, 0.28 + v * 0.40)
    if mode in ("green", "plant"):
        if 0.22 < h < 0.56 and s > 0.15:
            return colorsys.hsv_to_rgb(0.27, min(0.55, s * 0.7), v * 0.62)
        return r, g, b
    if s > 0.18 and (h < 0.115 or h > 0.93):
        return colorsys.hsv_to_rgb(0.07, min(0.6, s * 0.7), v * 0.5)
    if 0.68 < h < 0.93 and s > 0.15:
        return colorsys.hsv_to_rgb(0.6, 0.07, v * 0.8)
    return r, g, b


def recolor(me, mode=True):
    """Replaces the Kenney colormap with flat materials (one per color), per polygon, going through _remap."""
    uv = me.uv_layers.active.data if me.uv_layers.active else None
    new, slots = [], {}
    old_mats = [m for m in me.materials]
    for p in me.polygons:
        old = old_mats[p.material_index] if p.material_index < len(old_mats) else None
        img = None
        if old is not None and old.node_tree:
            for n in old.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    img = n.image
        if img is None:                                   # material without texture: remaps the base color
            base = None
            if old is not None and old.node_tree:
                for n in old.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED":
                        base = tuple(n.inputs["Base Color"].default_value)[:3]
            if base is None:
                key = ("old", p.material_index)
                if key not in slots:
                    slots[key] = len(new)
                    new.append(old)
                p.material_index = slots[key]
                continue
            srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in base]
            r, g, b = _remap(*srgb, mode)
        else:
            a, w, h = _pixels(img)
            u = sum(uv[i].uv[0] for i in p.loop_indices) / p.loop_total if uv else 0.5
            v = sum(uv[i].uv[1] for i in p.loop_indices) / p.loop_total if uv else 0.5
            px = a[min(max(int(v * h), 0), h - 1), min(max(int(u * w), 0), w - 1)]
            r, g, b = _remap(float(px[0]), float(px[1]), float(px[2]), mode)
        hexc = "#%02X%02X%02X" % (int(r * 255 + .5) // 8 * 8, int(g * 255 + .5) // 8 * 8, int(b * 255 + .5) // 8 * 8)
        key = ("c", hexc)
        if key not in slots:
            slots[key] = len(new)
            new.append(mat(f"K{hexc}", hexc))
        p.material_index = slots[key]
    me.materials.clear()
    for m in new:
        me.materials.append(m)
    me.update()


def tmpl(path, paint=True):
    """Imports the GLB once and stores (mesh, local matrix, name) of each piece; deletes the imported objects.
    paint: replaces the Kenney colormap with flat palette colors (recolor)."""
    path = str(path)
    if (path, paint) in _cache:
        return _cache[(path, paint)]
    before = set(bpy.data.objects)
    scene = bpy.context.scene
    keep = (scene.render.fps, scene.frame_start, scene.frame_end)
    bpy.ops.import_scene.gltf(filepath=path)
    scene.render.fps, scene.frame_start, scene.frame_end = keep
    new = [o for o in bpy.data.objects if o not in before]
    parts = []
    for o in new:
        if o.type == "MESH":
            parts.append((o.data, o.matrix_world.copy(), o.name))
    for o in new:
        if o.type == "MESH":
            if paint:
                recolor(o.data, paint)
            o.data.use_fake_user = True
        bpy.data.objects.remove(o, do_unlink=True)
    _cache[(path, paint)] = parts
    return parts


def town(name, mode=True):
    return tmpl(TOWN / f"{name}.glb", mode)


def nature(name, paint=False):
    return tmpl(NATURE / f"{name}.glb", paint)


def place(parts, loc=(0, 0, 0), rotz=0.0, scale=1.0, name="P", sz=None, parent=None):
    """Light copies (same mesh) of a mold; scale `scale` (or (sx,sy,sz)). Returns the list of objects."""
    s = (scale, scale, scale if sz is None else sz) if not isinstance(scale, tuple) else scale
    m = Matrix.Translation(loc) @ Euler((0, 0, rotz)).to_matrix().to_4x4() @ Matrix.Diagonal((*s, 1.0))
    out = []
    for mesh, local, nm in parts:
        o = bpy.data.objects.new(f"{name}_{nm}", mesh)
        bpy.context.collection.objects.link(o)
        o.matrix_world = m @ local
        if parent is not None:
            o.parent = parent
            o.matrix_parent_inverse = parent.matrix_world.inverted()
        out.append(o)
    return out


def mat(name, color, rough=0.95, emission=None, strength=0.0):
    m = kit.flat(name, color, rough=rough, emission=emission, strength=strength)
    kit.principled(m).inputs["Specular IOR Level"].default_value = 0.0
    return m


def glow_mat(name, color="#F5A524", strength=0.0):
    """Emissive material with its own strength (one per group that lights/unlights together). Returns (material, socket)."""
    m = mat(name, "#2A2018", emission=color, strength=strength)
    return m, kit.principled(m).inputs["Emission Strength"]


def mesh_from_geo(name, geo, material):
    me = bpy.data.meshes.new(name)
    me.from_pydata(geo[0], [], geo[1])
    me.materials.append(material)
    me.update()
    return me


def obj_of(name, mesh, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    o.location, o.rotation_euler, o.scale = loc, rot, scale
    return o


# ---------- voz: palavras-gatilho ----------

_voice = None


def voice():
    global _voice
    if _voice is None:
        p = ROOT / "build/two-humans-left/voice.json"
        _voice = json.loads(p.read_text(encoding="utf-8"))
    return _voice


def when(sid, word, nth=0):
    """Second (within the scene) when the word starts; nth counts repetitions. Word without punctuation, lowercase."""
    hits = [w["start"] for w in voice()[sid]["words"] if w["word"].lower().strip(".,?!") == word.lower()]
    return hits[nth]


def vis(objs, scenes, tl, all_scenes):
    """On/off per scene (hide_render only on the cuts)."""
    for o in objs:
        for sid in all_scenes:
            o.hide_render = sid not in scenes
            o.keyframe_insert("hide_render", frame=tl.at(sid))
        constant(o, ("hide_render",))


def constant(owner, paths=None):
    ad = getattr(owner, "animation_data", None)
    if ad is None or ad.action is None:
        return
    import rigs
    for fc in rigs._fcurves(ad.action):
        if paths and fc.data_path not in paths:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def linear(owner):
    ad = getattr(owner, "animation_data", None)
    if ad is None or ad.action is None:
        return
    import rigs
    for fc in rigs._fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
