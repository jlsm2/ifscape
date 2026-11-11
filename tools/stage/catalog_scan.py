"""Scans assets/ inside Blender and writes tools/stage/catalog.json (CC0 models usable by the stage builder).

    blender -b -P tools/stage/catalog_scan.py -- [--only kenney/nature-kit] [--limit 20] [--out caminho.json]

For each model: unique id, file, pack, type (kind), tags, box in meters (width x depth x height),
triangles, whether it has a skeleton, and the actions. The builder scales each piece to the height asked for in the script, so
each pack's native scale (Kenney ~1 m, Quaternius FBX in cm) does not matter: only the proportion and the type.
Written for lean mode, phase 1.
"""

import json
import re
import sys
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
EXTS = (".glb", ".gltf", ".fbx")
# glTF counts for more than FBX, which counts for more than OBJ (the same model comes in several formats in the Quaternius packs)
PREFER = {".glb": 0, ".gltf": 1, ".fbx": 2}
# Typical height in meters by type (the script may ask for another). Serves as the builder's default.
DEFAULT_HEIGHT = {"tree": 9.0, "dead-tree": 7.0, "pine": 12.0, "palm": 8.0, "bush": 1.2, "plant": 0.6, "grass": 0.5,
                  "flower": 0.4, "mushroom": 0.25, "rock": 1.2, "pebble": 0.15, "cliff": 6.0, "cactus": 2.0,
                  "log": 0.5, "building": 7.0, "wall": 3.0, "roof": 2.0, "fence": 1.2, "prop": 1.0, "bridge": 3.0,
                  "road": 0.1, "vehicle": 1.6, "person": 1.7, "animal": 1.2, "bird": 0.7, "dino": 4.0, "terrain": 1.0,
                  "water": 0.2, "part": 0.3, "tent": 2.5, "furniture": 1.0, "accessory": 0.3, "other": 1.0,
                  "food": 0.08, "street": 4.5}

# Whole packs with their own type: picnic food must not fall into the 'plant' draw (corn, leek)
# and the city kit buildings are 'building' (not 'wall').
PACK_KIND = {"kenney/food-kit": ("food", ["food", "picnic"])}
CITY_PACKS = ("kenney/city-kit-commercial", "kenney/city-kit-suburban", "kenney/city-kit-roads")

# (regex on the lowercase name, type, tags): the first rule that matches wins
RULES = [
    (r"^(debris|wheel|blade|eyebrows|hair|hanging|ual|petal)", "part", ["part"]),
    (r"^(superhero)", "part", ["needs-retarget"]),
    (r"^(character|animatedhuman|man$|woman|superhero)", "person", ["human"]),
    (r"^(aid|wheelchair)", "accessory", ["health"]),
    (r"(apatosaurus|parasaurolophus|stegosaurus|trex|triceratops|velociraptor)", "dino", ["dinosaur"]),
    (r"^eagle$", "bird", ["bird", "animal"]),
    (r"^chicken$", "bird", ["bird", "animal", "farm"]),     # made by us: tools/blender/chicken_model.py
    (r"^(cow|horse|llama|pig|pug|sheep|zebra|fox|raccoon|rat)$", "animal", ["animal"]),
    (r"deadtree|dead_tree|tree_dead|treedead", "dead-tree", ["tree", "dead"]),
    (r"palmtree|palm_?tree|tree_palm", "palm", ["tree", "tropical"]),
    (r"pine", "pine", ["tree", "conifer"]),
    (r"(tree|oak|birch|willow|trunk_)", "tree", ["tree"]),
    (r"cactus", "cactus", ["desert"]),
    (r"(bush|shrub|hedge)", "bush", ["plant"]),
    (r"grass", "plant", ["plant", "grass"]),
    (r"(clover|fern|plant|crop|leaf|petal)", "plant", ["plant"]),
    (r"(flower|tulip|daisy)", "flower", ["plant"]),
    (r"(corn|wheat)", "plant", ["crop"]),
    (r"(statue|pot-|windmill|cone)", "prop", []),
    (r"mushroom", "mushroom", ["plant"]),
    (r"(pebble|stone_small|rockpath)", "pebble", ["rock"]),
    (r"(cliff|mountain|hill)", "cliff", ["rock", "terrain"]),
    (r"(rock|stone|boulder)", "rock", ["rock"]),
    (r"(log|stump|branch|twig)", "log", ["wood"]),
    (r"bridge", "bridge", []),
    (r"(road|path|ground|terrain|tile|platform)", "road", []),
    (r"(water|lily|river)", "water", []),
    (r"(tent|campfire|canoe|boat)", "tent", ["camp"]),
    (r"(roof|chimney)", "roof", ["building"]),
    (r"(wall|window|door|tower|balcony|stairs|overhang|pillar|house|building|barn|silo)", "wall", ["building"]),
    (r"(fence|gate|poles|planks)", "fence", []),
    (r"(ambulance|firetruck|police|taxi|truck|van|suv|sedan|hatchback|car|race|kart|tractor|delivery|cop|sportscar)",
     "vehicle", ["vehicle"]),
    (r"(bed|chair|table|bench|crate|barrel|cart|box|sign|banner|lantern|fountain|well|stall)", "furniture", []),
]


def classify(stem: str) -> tuple[str, list[str]]:
    low = stem.lower()
    for pattern, kind, tags in RULES:
        if re.search(pattern, low):
            return kind, list(tags)
    return "other", []


def candidates(only: str | None) -> list[Path]:
    """One file per model: if there is a glb and an fbx of the same name in the same pack, the preferred format stays."""
    best: dict[tuple[str, str], Path] = {}
    base = ASSETS / only if only else ASSETS
    for p in sorted(base.rglob("*")):
        if p.suffix.lower() not in EXTS or "preview" in p.stem.lower():
            continue
        parts = p.relative_to(ASSETS).parts
        key = ("/".join(parts[:2]), p.stem.lower())
        if key not in best or PREFER[p.suffix.lower()] < PREFER[best[key].suffix.lower()]:
            best[key] = p
    return sorted(best.values())


def clear() -> None:
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images,
                 bpy.data.actions, bpy.data.cameras, bpy.data.lights):
        for item in list(coll):
            coll.remove(item)


def measure(path: Path) -> dict:
    clear()
    before_actions = set(bpy.data.actions)
    if path.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False)
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi, tris = [1e9] * 3, [-1e9] * 3, 0
    for o in meshes:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        tris += sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
        for v in me.vertices:
            w = oe.matrix_world @ v.co
            for i in range(3):
                lo[i], hi[i] = min(lo[i], w[i]), max(hi[i], w[i])
        oe.to_mesh_clear()
    actions = sorted({a.name.split("|")[-1] for a in bpy.data.actions if a not in before_actions and "|" in a.name}
                     or {a.name for a in bpy.data.actions if a not in before_actions})
    size = [round(hi[i] - lo[i], 4) for i in range(3)] if meshes else [0, 0, 0]
    return {"size": size, "tris": tris, "rigged": bool(armatures), "actions": actions,
            "materials": len({s.material.name for o in meshes for s in o.material_slots if s.material})}


def unique_id(stem: str, pack: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    if base not in taken:
        return base
    return f"{pack.split('/')[-1]}-{base}"


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = lambda name: args[args.index(name) + 1] if name in args else None
    out = Path(opt("--out") or ROOT / "tools" / "stage" / "catalog.json")
    limit = int(opt("--limit") or 0)
    files = candidates(opt("--only"))
    if limit:
        files = files[:limit]
    items, taken, failed, t0 = [], set(), [], time.time()
    # ids already used by scripts do not change in a new scan (a new pack that sorts earlier does not steal 'fence')
    old = {}
    if out.exists():
        old = {i["file"]: i["id"] for i in json.loads(out.read_text(encoding="utf-8"))["items"]}
        taken |= set(old.values())
    for n, path in enumerate(files, 1):
        rel = path.relative_to(ASSETS)
        pack = "/".join(rel.parts[:2])
        try:
            info = measure(path)
        except Exception as exc:  # a broken model does not bring down the scan
            failed.append({"file": rel.as_posix(), "error": str(exc)[:160]})
            continue
        kind, tags = classify(path.stem)
        if info["rigged"] and kind == "other":
            kind = "animal"
        if pack in PACK_KIND:
            kind, tags = PACK_KIND[pack][0], list(PACK_KIND[pack][1])
        elif pack in CITY_PACKS:
            tags = tags + ["city"]
            if path.stem.startswith(("building", "low-detail-building")):
                kind = "building"
            elif kind in ("other", "road", "furniture", "prop") or path.stem.startswith(("light-", "traffic", "electricity")):
                kind = "street" if not path.stem.startswith(("road", "tile")) else "road"
        ident = old.get(rel.as_posix()) or unique_id(path.stem, pack, taken)
        taken.add(ident)
        items.append({"id": ident, "file": rel.as_posix(), "pack": pack, "kind": kind, "tags": tags,
                      "height_m": DEFAULT_HEIGHT[kind], **info})
        if n % 50 == 0:
            print(f"  {n}/{len(files)} ({time.time() - t0:.0f} s)", flush=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import procedural_items                                  # pieces made in code (boat, gull, ice)
    if not opt("--only"):
        scanned = {i["id"] for i in items}
        items += [dict(i) for i in procedural_items.ITEMS if i["id"] not in scanned]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d"), "count": len(items), "failed": failed,
                               "items": items}, indent=1, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for it in items:
        kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
    print(f"catalogo: {len(items)} modelos, {len(failed)} falhas, {time.time() - t0:.0f} s -> {out}")
    print("by type:", dict(sorted(kinds.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
