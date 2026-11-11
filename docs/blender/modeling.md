# Low-poly modeling and animation in Blender + CC0 assets (2026-10-21)

The owner asked for this research because "the models look weird" and the animations were bad: legs that come loose, stiff falls and people walking like dolls. The main conclusion is **use ready-made, already-animated CC0 assets** (Quaternius and Kenney) for animals, people and cars, and leave script modeling for scenery and simple parts. Everything below was downloaded and tested in Blender 5.2.2 in the background.

- Previews: `build/asset-preview/*.png` (1080x1080) and the sheet `build/asset-preview/_contact-sheet.png`.
- Script rig demo: `build/asset-preview/rig-demo-skin-ik.png`.
- Tested scripts: local research notes (`asset_test.py`, `demo_rig.py`, `plant_speed.py`).

---

## Part 2 (priority): ready-made CC0 assets

All are **CC0 1.0** (public domain, commercial use with no attribution). Each folder has a `SOURCE.txt` with the URL, license and date, plus the package's original `License.txt`. Quaternius's site Google Drive had its quota exceeded, so the packages came from itch.io ("No thanks, just take me to the downloads"). From Poly Pizza came standalone GLBs (`https://static.poly.pizza/<ResourceID>.glb`); each model's license was checked in the page JSON.

Total on disk: about 335 MB in `assets/`. `.blend` and OBJ files were discarded: only FBX, glTF/GLB, textures and texts were kept.

### Table of recommended assets

| Asset | License | Rig and animations | Tris | Local path |
| --- | --- | --- | --- | --- |
| **Apatosaurus** (Quaternius, Animated Dinosaurs) | CC0 | 39 bones. Attack, Idle, Jump, Run, Walk and "Stegosaurus_Death" (it is the Apatosaurus death with the name swapped) | 1,442 | `assets/quaternius/animated-dinosaurs/Dinosaur Animated Pack - Dec 2018/FBX/Apatosaurus.fbx` |
| T-Rex, Velociraptor, Stegosaurus, Triceratops, Parasaurolophus (same pack) | CC0 | Idle, Walk, Run, Attack, Jump, Death | 1,250 to 1,820 | same folder (`Trex.fbx`, `Velociraptor.fbx`…) |
| **Fox** (Quaternius, via Poly Pizza) | CC0 | 51 bones. Walk, Gallop, Idle, Idle_2_HeadLow, Eating, Attack, Death, Jump… (12) | 1,848 | `assets/polypizza/quaternius-animals/Fox.glb` |
| **Rat** (Quaternius, via Poly Pizza) | CC0 | 31 bones. Walk, Run, Idle, Jump, Attack, Death | 4,004 | `assets/polypizza/quaternius-animals/Rat.glb` |
| Raccoon (Quaternius, via Poly Pizza) | CC0 | Walk, Run, Idle, Idle_Eating, Death… (8) | 2,876 | `assets/polypizza/quaternius-animals/Raccoon.glb`. Voxel style: clashes |
| **Man / Woman Casual** (Quaternius, via Poly Pizza) | CC0 | 31 bones. Walk, Run, Idle, Death, Sitting, Standing, Jump, Clapping, Punch… (11) | 1,850 / 2,780 | `assets/polypizza/quaternius-people/Man.glb`, `WomanCasual.glb` |
| Animated Human (Quaternius, via Poly Pizza) | CC0 | Walk, Run, Idle, Death, Jump, Punch, Working | 1,578 | `assets/polypizza/quaternius-people/AnimatedHuman.glb` (white, no clothes: a good base to paint) |
| **Universal Animation Library** (Quaternius) | CC0 | 65-bone human skeleton, **43 animations**: Walk_Loop, Walk_Formal_Loop, Jog_Fwd_Loop, Sprint_Loop, Idle_Loop, Idle_Talking_Loop, Death01, Sitting_*, Crouch_*, Push_Loop, PickUp_Table, Driving_Loop, Swim_*… | 13,700 (mannequin) | `assets/quaternius/universal-animation-library/…/Unreal-Godot/UAL1_Standard.glb` (`_RM` = with root motion) |
| Universal Base Characters (Quaternius) | CC0 | The same 65-bone skeleton, **no animation of its own**. The UAL animations fit directly (tested) | 14,300 | `assets/quaternius/universal-base-characters/…/Base Characters/Godot - UE/Superhero_*_FullBody.gltf` + hair |
| Mini Characters (Kenney) | CC0 | 7 bones, **32 animations** (walk, sprint, idle, die, sit, drive, pick-up…) | ~720 | `assets/kenney/mini-characters/Models/GLB format/character-*.glb` (chibi, huge head) |
| **Car Kit** (Kenney) | CC0 | No rig; wheels as separate objects | ~2,000 | `assets/kenney/car-kit/Models/GLB format/sedan.glb`, `suv.glb`, `taxi.glb`, `police.glb`, `truck.glb`, `van.glb`… (45 models + wreckage: `debris-*.glb`) |
| Cars Pack (Quaternius) | CC0 | No rig | ~2,950 | `assets/quaternius/cars/Realistic Car Pack - Nov 2018/FBX/NormalCar1.fbx` (+ SUV, Taxi, Cop, SportsCar) |
| **Stylized Nature MegaKit** (Quaternius, free version 68/116) | CC0 | No rig | Pine 3,900; Fern 288; Rock 340 | `assets/quaternius/stylized-nature-megakit/glTF/` (Pine_1–5, CommonTree, DeadTree, TwistedTree, Fern_1, Plant_*, Bush, Rock_Medium, Pebble, Grass, Mushroom) |
| Ultimate Nature Pack (Quaternius) | CC0 | No rig | Pine 1,920; Palm 1,770 | `assets/quaternius/ultimate-nature/FBX/` (150 models: PineTree, PalmTree, Plant, Rock, Rock_Moss, Bush, CommonTree_Dead, BirchTree…) |
| Nature Kit (Kenney) | CC0 | No rig | 80 to 300 | `assets/kenney/nature-kit/Models/GLTF format/` (tree_pine*, tree_palm*, rock_*, plant_bush*, log, cliff_*): much simpler, good for the background |
| Fern and Palm Tree (Quaternius, via Poly Pizza) | CC0 | No rig | 288 / 3,100 | `assets/polypizza/quaternius-plants/` |

### What does not exist as CC0 and what to use instead

- **Raised-neck sauropod (Brachiosaurus):** there is none in CC0 with a rig. The closest is the **Quaternius Apatosaurus**, which walks with its neck almost horizontal. The rig has bones in the neck, so the neck can be raised by script, adding a rotation to the neck bones on top of the walk (see "Layers" below). The Poly Pizza Diplodocus (Poly by Google, 664 tris) is **CC-BY 3.0**, no rig: I did not download it.
- **Shrew or Mesozoic mammal:** the **Rat** (with Walk and Run) scaled down is the best substitute. The Fox works for a larger mammal.
- **Cycad:** I found none in CC0. The substitutes are the low palm (`PalmTree_A6cK.glb`, thick ringed trunk, which reads as a cycad) and `Fern_1`.

### Import test in Blender 5.2.2 (result)

All 22 assets imported without error with `bpy.ops.import_scene.gltf` or `bpy.ops.import_scene.fbx`. On every rigged model, I put the walk mid-cycle and rendered in Eevee: the mesh deforms with the skeleton, with no loose piece (`build/asset-preview/`).

Gotchas found:

1. **Old Quaternius FBX files (dinosaurs, cars and Ultimate Nature, from 2018) come with the material Alpha at 0.** The model is invisible in Eevee. Fix, after importing:
   ```python
   for m in bpy.data.materials:
       if m.use_nodes:
           for n in m.node_tree.nodes:
               if n.type == "BSDF_PRINCIPLED" and not n.inputs["Alpha"].is_linked:
                   n.inputs["Alpha"].default_value = 1.0
   ```
2. **Arbitrary scales.** The Apatosaurus is 48 m long (the real one is about 22 m: scale 0.45), the Rat 7 m, the Man 4.6 m tall (scale 0.38 for 1.75 m). The UAL/UBC and Kenney ones already come in meters. Always normalize by the height or length you want.
3. **The glTF importer creates an `Icosphere` object** (the bone display shape) and several `*_end` empties. Ignore them in the bounding box calculation and hide them in the render.
4. **glTF animations arrive as NLA tracks** and also as `bpy.data.actions`. To play just one: mute the tracks and assign the action (Blender 5 also has the slot):
   ```python
   ad = arm.animation_data or arm.animation_data_create()
   for tr in ad.nla_tracks:
       tr.mute = True
   act = bpy.data.actions["HumanArmature|Man_Walk"]
   ad.action = act
   if ad.action_slot is None and len(act.slots):
       ad.action_slot = act.slots[0]
   ```
5. **Universal Base Characters + Universal Animation Library:** import both, delete the second's objects and assign `Walk_Loop` to the UBC armature. It works directly, because the 65 bone names match (`build/asset-preview/ubc-male-walk.png`).
6. **In-place walk + moving the object = the foot slides, if the speed does not match.** `plant_speed.py` measures the planted foot's speed.
   - **Man_Walk:** 4.2 units/s with the model 4.6 tall, i.e. about **1.6 m/s** at human scale. The cycle lasts 1.04 s at 24 fps.
   - **Apatosaurus_Walk:** 5.2 s cycle. The hind foot moves 2.7 units/s and the front one only 1.3. **The front and hind feet have different speeds**, so up close some pair will slide. With a distant camera it passes; up close, redo the leg cycle with IK on the same rig.
7. **FBX material:** the importer creates an empty Normal Map node. It is harmless.

### How to use in a set (sketch tested in the parts)

```python
def load_asset(path, scale, location, heading=0.0, action=None, start=1, speed=1.0):
    keep = set(bpy.context.scene.objects)
    if path.endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.context.scene.objects if o not in keep]
    root = next(o for o in new if o.parent is None and o.type in {"EMPTY", "ARMATURE"})
    for o in new:
        if o.name.startswith("Icosphere") or o.name.endswith("_end"):
            o.hide_render = o.hide_viewport = True
    root.scale = (scale,) * 3
    root.location = location
    root.rotation_euler.z = heading
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    if arm and action:
        act = next(a for a in bpy.data.actions if a.name.endswith(action))
        ad = arm.animation_data or arm.animation_data_create()
        for tr in ad.nla_tracks:
            tr.mute = True
        tr = ad.nla_tracks.new()                 # NLA strip: repeat + start frame + speed
        st = tr.strips.new(act.name, start, act)
        st.repeat = 20
        st.scale = 1.0 / speed
    return root, arm
```

To chain actions (walk, stop, die), use one NLA track per action, with `blend_in`/`blend_out` of 6 to 10 frames between the strips. That removes the jerk of switching actions.

---

## Part 1: low-poly modeling and animation guide

### 1.1 What makes low-poly look good (what artists do)

References: Quaternius (CC0 packs, all with the same visual vocabulary), Kenney (Nature Kit, Car Kit), Imphenzia ("low poly in 10 minutes" series: block first, detail only where the camera sees), Polygon Runway (animals and scenes in Blender with a flat palette), the Polycount forum (budgets of under 1,000 tris per character; a good wolf at 420 tris) and J. S. Abbott's low-poly animal tutorial (side view as the main reference).

- **Silhouette comes before everything.** The animal must be recognizable painted black, from the side. In the Quaternius models, what makes it readable is:
  - on the fox, the thin muzzle, the big ears and the thick tail with a white tip;
  - on the rat, the teardrop body, the pink snout, the thin legs and the long pink tail;
  - on the Apatosaurus, the long neck and tail tapering to the tip, and the trunk tall at the hip.

  In our script-made models, the parts were tubes of almost constant radius, and the silhouette became "sausage with toothpicks".
- **Exaggerate the right proportions.** Head and legs slightly bigger than real, waist and ankle thinner. The form tapers to the extremities (tail, neck, muzzle, toes). A blunt, thick tip is what screams "made by code" the most.
- **Budget:** scene animal 800 to 2,000 tris; person 1,200 to 3,000; tree 300 to 4,000. The measured values are in the table above. More polygons do not make the model better; what does is polygons in the right place: joints, silhouette and face.
- **Flat shading with big, intentional facets.** Turn smooth off (`use_smooth_shade = False` on the Skin; `shade_flat()`), but with faces of varied sizes: large on the surfaces, small on the curves. Facets that are all equal (a repeated 8-sided cylinder) look primitive.
- **Short palette:**
  - 3 to 5 colors per model, flat and matte (roughness 0.8 to 1.0);
  - a lighter belly color (countershading), which gives volume without texture;
  - feet, muzzle and ears in a third color.

  Quaternius uses exactly that: Brown / LightBrown / Black on the Apatosaurus.
- **Minimal eyes and details that give life:**
  - dark eye with a highlight dot or a black rectangle, slightly above and in front of the center of the head;
  - nostrils and claws in a dark color;
  - the tail tip in a different color.

  A well-placed eye is worth a thousand polygons. Without eyes, the animal becomes an object.
- **Overlapping parts are acceptable in static shots, but not in animated ones.** In an animated character, the mesh must be **one continuous piece at the joints**. That is exactly where "legs that come loose" come from (see 1.5).

### 1.2 Modeling by script: which tool for what

| Technique | Works well for | Problems |
| --- | --- | --- |
| **Skin modifier** (vertices + edges, radius per vertex) + Subsurf 1 + Decimate | Single-piece animals and people: generates a **continuous** mesh at the junctions and the topology follows the skeleton. It is the recommended method for our animals | Junctions with many branches can twist; needs `use_root` on one vertex; the Skin loses the top of the head (seen in humans-vanished), so reinforce with an extra vertex |
| **Metaballs** (`bpy.data.metaballs`) | Fat organic shapes: clouds, rocks, fat animal body. Convert to mesh and decimate | The conversion generates a lot of triangulated, irregular mesh; hard to control the silhouette |
| **bmesh** (ring-by-ring extrude, "lofts" of elliptical sections) | Trunks and hulls with a controlled profile (what `dinos.py` does). Good for vehicles, buildings and rocks | Joining limbs to the trunk gives no seam: they become separate objects, which come loose when animated |
| **Mirror** | Model half (y ≥ 0) and mirror; guarantees symmetry and halves the code | Apply before the rig; turn on `use_clip` so no hole opens in the middle |
| **Decimate** (Collapse, ratio 0.3 to 0.6) | Give the faceted look from a smoothed mesh (Skin+Subsurf) | A ratio that is too low creates thin triangles and "needles" |

Recipe of the tested demo (`demo_rig.py` in the local research notes; 620 tris, one piece):

```python
me = bpy.data.meshes.new("dog")
me.from_pydata(joint_positions, edges, [])           # the skeleton as vertices and edges
obj = bpy.data.objects.new("dog", me); scene.collection.objects.link(obj)
skin = obj.modifiers.new("Skin", "SKIN"); skin.use_smooth_shade = False
for i, r in enumerate(radii):                         # radius (x, y) per joint: thin out at the tips!
    me.skin_vertices[0].data[i].radius = r
me.skin_vertices[0].data[chest_index].use_root = True
obj.modifiers.new("Sub", "SUBSURF").levels = 1
obj.modifiers.new("Dec", "DECIMATE").ratio = 0.5
bpy.context.view_layer.objects.active = obj
for m in ("Skin", "Sub", "Dec"):
    bpy.ops.object.modifier_apply(modifier=m)          # works in -b
```

Skeleton rule: **each limb needs its own joint on the side of the body** (shoulder and hip at y = ±half width, slightly below the back), and not come out of the center of the trunk. In the first test, the legs came out of the central chest vertex, and the thigh bones rotated around the center of the body: the front legs detached from the trunk, the same defect as in the video. With the lateral joint, the legs stayed attached (`build/asset-preview/rig-demo-skin-ik.png`).

### 1.3 Rig by script

- Create the bones in `EDIT` mode from the same joint positions as the Skin. The `head` of each bone sits **exactly at the joint where the mesh bends**.
- **Automatic Weights in the background works** (tested in `-b`): deselect everything, select the mesh and then the armature, leave the armature active and call `bpy.ops.object.parent_set(type="ARMATURE_AUTO")`. Then check that no vertex group is empty (the demo checks this).
- If "Bone Heat Weighting: failed to find solution for one or more bones" appears:
  - the mesh has loose islands or overlapping faces: do Merge by Distance, or separate the parts and weight each one;
  - the scale was not applied;
  - some bone is outside the mesh;
  - Subsurf is before Armature in the modifier stack.

  The solution is **one continuous mesh**, at scale 1 and bones inside.
- Control bones (`root`, IK targets, poles) get `use_deform = False`.
- **Foot IK:** IK constraint on the shin bone with `chain_count = 2`. Target and pole can be **empties parented to the rig object**, instead of bones: that way the position is in world axes, with no surprise from the bone "roll". In the first test, the targets were bones and the "lift the foot" came out sideways. The pole sits in the leg plane, on the side the knee points to, with `pole_angle = 0`.

### 1.4 Walk cycle

Richard Williams's 4 poses per step (The Animator's Survival Kit), 8 per cycle:

- **contact:** heel touches the ground, legs apart;
- **down:** the body at its lowest point, front knee bent receiving the weight;
- **passing:** the free leg passes beside the support leg, the body rises;
- **up:** the body at its highest point, pushing off on the toe.

The cycle closes on the same contact: render frames 1–24 and repeat without duplicating frame 25. Typical values: 24 to 30 frames per cycle for walking people; the heavy quadruped (sauropod) takes 3 to 5 s per cycle.

What separates a living walk from a "doll":

- the body **bobs up and down** twice per cycle (in the demo, 2.5 cm; on a person, 3 to 5 cm);
- the hip sways to the side of the support foot, and the shoulder rotates opposite to the hip;
- the arms go opposite to the legs, with a delay of 2 to 3 frames (overlap);
- the head and tail come **late** relative to the trunk (follow-through), instead of rigid;
- the planted foot **stays still in the world**. With IK, this comes for free if the root moves at the right speed: `speed = stride / (ground fraction × cycle duration)`. In the demo: 0.50 m / (0.6 × 24 frames) = 1.04 m/s at 30 fps.
- Quadrupeds: diagonal pairs in the trot (front left with hind right). In the slow walk (sauropod), the four legs offset by 1/4 of a cycle, each leg on the ground for about 75% of the time.

**Layers:** the walk sits on an NLA track. The extra pose (raise the neck, look to the side) goes on another track above, with `blend_type = "ADD"` (or as keyframes on the active action, which add on top of the NLA). That way the Apatosaurus neck can rise without redoing the walk.

**Falls and death without stiffness:** use the asset's Death action (Apatosaurus, Rat, Fox and Man have it). If it is a scripted fall, never rotate the whole object like a plank:

- bend the legs first, with 3 to 6 frames of offset between them;
- then the trunk falls with ease-in, gravity accelerating;
- on impact, a small bounce of 2 to 4 frames;
- neck and tail reach the ground last (follow-through).

**Blender 5:** actions are "slotted". `action.fcurves` is no longer the way; the F-Curves live in `action.layers[0].strips[0].channelbag(slot).fcurves`. `keyframe_insert` still works normally. The glTF importer already creates everything correctly.

### 1.5 Mistakes that make the model look "weird" (and what to do)

| Symptom | Cause | Fix |
| --- | --- | --- |
| Legs that come loose from the body | Limbs as separate objects, or the bone pivot at the center of the trunk, not at the joint | One continuous mesh (Skin), pivot at the lateral joint, Automatic Weights |
| Animal looks like a sausage with toothpicks | Constant-radius tubes, blunt tips | Taper to the tips, thin waist and ankle, belly and rump with volume |
| People walk like dolls | Only the legs rotate; trunk, arms and head still; no bob | Use the UAL or Quaternius animations; if by hand, the 6 items of section 1.4 |
| Sliding foot | The root moves at a different speed from the planted foot | IK + `speed = stride / (fraction × cycle)`, or measure the asset with `plant_speed.py` |
| Stiff fall | Rotation of a whole object with linear interpolation | The asset's Death action, or a staged fall with offset and ease |
| Model invisible or black | Old FBX with Alpha 0, or inverted normals | Alpha = 1 (code above); `normals_make_consistent` |
| "Primitive" facets | 6- or 8-sided cylinders all equal | Skin + Subsurf + Decimate, or a ready-made asset |
| Model floating or sunk | Origin off the feet, asset scale | Normalize the scale and put the bounding box base at z = 0 after posing |
| Lifeless | No eyes, no idle | Dark eye with a highlight; when still, play `Idle`, never the frozen pose |

### 1.6 The 5 most important rules

1. **Animated animals and people come from a rigged CC0 asset** (Quaternius or Kenney). By code, only scenery and rigid objects.
2. **An animated character is one continuous mesh**, with bones pivoting exactly at the joints (shoulder and hip on the sides), weighted with Automatic Weights. Never loose parts parented to objects.
3. **Silhouette rules:** forms that taper to the tips, exaggerated proportions in the traits that identify the animal, 3 to 5 flat colors, lighter belly and eyes.
4. **The planted foot does not slide:** IK on the feet and the root moving at the cycle's measured speed. The body bobs up and down, and head and tail come late.
5. **Check on a rendered frame** (preview in `-b`, like `asset_test.py`) and normalize scale and ground of every imported asset before composing the scene.

---

## Sources

- Quaternius: https://quaternius.com/ ; packs https://quaternius.com/packs/animateddinosaurs.html , https://quaternius.com/packs/universalanimationlibrary.html , https://quaternius.com/packs/universalbasecharacters.html , https://quaternius.com/packs/stylizednaturemegakit.html , https://quaternius.com/packs/ultimatenature.html , https://quaternius.com/packs/cars.html ; itch.io https://quaternius.itch.io/animated-lowpoly-dinosaurs (CC0 license in each pack's `License.txt`)
- Poly Pizza (license per model in the page's `Licence` field): https://poly.pizza/m/Bc97C66HKi , https://poly.pizza/m/iltq5bVNaV , https://poly.pizza/m/xMmx6VQP3r , https://poly.pizza/m/HMnuH5geEG , https://poly.pizza/m/jpKRgGDxhk , https://poly.pizza/m/c3Ibh9I3udk , https://poly.pizza/m/jqcanvH7D6 , https://poly.pizza/m/A6cKJYFsIb ; Diplodocus CC-BY (not downloaded) https://poly.pizza/m/12n6ICAVpYB
- Kenney: https://kenney.nl/assets/car-kit , https://kenney.nl/assets/nature-kit , https://kenney.nl/assets/mini-characters
- Blender Manual, Skin Modifier: https://docs.blender.org/manual/en/4.2/modeling/modifiers/generate/skin.html
- Blender 5 API, slotted actions and channelbag: https://docs.blender.org/api/5.2/bpy.types.ActionChannelbag.html ; https://docs.blender.org/manual/en/5.0/animation/actions.html
- Bone Heat Weighting: https://blenderartists.org/t/bone-heat-weighting-failed-to-find-solution-for-one-or-more-bones/423044 ; https://lists.blender.org/pipermail/bf-animsys/2017-April/000255.html
- Walk cycle (Richard Williams's contact method): https://courses.cs.washington.edu/courses/cse464/12wi/assignments/assignment_4/index.html ; https://animation.monmouth.edu/instruct/?p=351 ; https://openlab.bmcc.cuny.edu/mmp260-1301-f2019/week-7/
- Low-poly: https://jsabbott.artstation.com/blog/7olL1/how-do-you-model-a-low-poly-animal-in-blender-3d ; https://polycount.com/discussion/comment/1854025 ; Imphenzia, low poly in 10 minutes: https://www.blendernation.com/2020/07/07/speed-modeling-10-low-poly-cars-in-10-minutes/
