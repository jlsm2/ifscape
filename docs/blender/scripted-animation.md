# Scripted rig and animation in Blender 5.x (bpy, background)

Research from 2026-10-21 for the `blender-specialist` agent. Everything marked **[tested]** ran in the local Blender **5.2.2 LTS** (`blender -b --factory-startup -P …`). The examples that worked live in `tools/blender/examples/`, short and commented:

| File | What it shows | Measured result |
| --- | --- | --- |
| `rig_three_bones.py` | 3-bone armature, automatic weights, 30-frame action, render | `ARMATURE_AUTO` FINISHED with no window; 0 of 104 vertices without weight; 30 PNGs |
| `layered_action.py` | layered action written and read by hand, 2 slots, NLA, glTF reapplied on another rig | the other rig moves (quaternion 0.983/0.183 at frame 8) |
| `walk_biped_ik.py` | biped, 2-bone IK with pole, planted foot, hip, arms | foot slide during stance: **0.01 mm**; knee always forward |
| `gait.py` | phases of walk, sauropod, trot, pace, gallop, run; stride from speed | Pure Python (`py gait.py`); foot still during stance, mid-stance under the hip |
| `physics_debris.py` | rigid body with bake, physics converted to keys, particle dust | `bake_all` works with no window; dust correct in any frame order |
| `scatter_gn.py` | forest with Geometry Nodes built by script, mask by vertex group | 409 instances in 0.04 s; empty path (0 trees with \|x\| < 2.5) |
| `render_setup.py` | camera, sun, ground and background of the examples | — |

Today the project does not use an armature: parts are child objects with the pivot at the joint, and the rotation keys are computed by hand (`dinos.walk`, `people.walk`). That works, but has limits: the foot only stays planted through hand-done trigonometry, no mesh bends and no rigged asset (glTF or FBX) fits in. This guide shows the armature path, tested.

---

## 1. Layered actions (slotted actions)

### What changed

- **4.4:** every action now has slots. The f-curves live in an infinite keyframe strip, inside a layer. For now there is only 1 layer with 1 strip per action.
- **4.4:** `action.fcurves`, `action.groups` and `action.id_root` became legacy API, which reads only the first slot.
- **5.0:** that legacy API was **removed**. **[tested]** In 5.2.2, `bpy.types.Action` has no `fcurves`. In place of `id_root`, use `slot.target_id_type`.
- **5.1:** the `ANIM_OT_convert_legacy_action` operator was dropped.
- Hierarchy: `Action → slots` (for WHOM the action animates) and `Action → layers → strips (KEYFRAME) → channelbags (one per slot) → fcurves and groups`.

### Write without `keyframe_insert` **[tested]**

```python
import bpy, bpy_extras.anim_utils as au
LINEAR = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value

act = bpy.data.actions.new("Wave")
slot = act.slots.new(id_type="OBJECT", name="Rig")         # identifier = "OBRig"
bag = au.action_ensure_channelbag_for_slot(act, slot)      # creates layer + strip + channelbag (5.0+)
# by-hand equivalent: act.layers.new("Base").strips.new(type="KEYFRAME").channelbag(slot, ensure=True)
fc = bag.fcurves.new('pose.bones["Mid"].rotation_euler', index=1, group_name="Mid")  # .ensure() if it already exists
fc.keyframe_points.add(len(frames))
fc.keyframe_points.foreach_set("co", [c for fv in zip(frames, values) for c in fv])  # [f0, v0, f1, v1, ...]
fc.keyframe_points.foreach_set("interpolation", [LINEAR] * len(frames))
fc.update()
```

- `foreach_set` writes hundreds of keys at once, with no operator and without touching the scene. It is much faster than `keyframe_insert` in a loop.
- The `data_path` has to match the bone's `rotation_mode`. `rotation_euler` only has an effect if `pose_bone.rotation_mode == "XYZ"`, which is **not** the default: the pose bone default is `QUATERNION`.
- `Action.fcurve_ensure_for_datablock(obj, data_path, index=, group_name=)` creates layer, strip, slot and f-curve and already assigns the slot. The action has to be already assigned to the object.

### Read

```python
def fcurves_of(action, slot=None):           # replaces action.fcurves; same as globe._fcurves_of
    return [fc for L in action.layers for s in L.strips for cb in s.channelbags
            if slot is None or cb.slot == slot for fc in cb.fcurves]

bag = au.animdata_get_channelbag_for_assigned_slot(obj.animation_data)   # the channelbag the object is using
fc = bag.fcurves.find('pose.bones["Mid"].rotation_euler', index=1)
fc.evaluate(8)                                                          # value at frame 8
```

**[tested]** `keyframe_insert` on an object with no animation creates by itself the action (`RigAction`), the slot (`OBRig`), the layer, the strip and the channelbag. The groups get the bones' names.

### Assign an action and choose the slot

- `obj.animation_data.action = act` tries to choose the slot by itself, in this order:
  1. the slot with the `last_slot_identifier`;
  2. the slot with the object's name;
  3. the only never-used slot.

  **It may find none, and then the object stays still with no error.** Always set the slot explicitly: `ad.action_slot = slot`, or `au.action_get_first_suitable_slot(act, "OBJECT")`.
- One action can animate several objects, each in its own slot. **[tested]** An action with `OBRig` and `OBMarker` worked, each object with its own motion.

### Imported action (glTF) on another armature **[tested]**

```python
before = set(bpy.data.actions)
bpy.ops.import_scene.gltf(filepath=path)
act = next(a for a in bpy.data.actions if a not in before)
# bones with the same name on the target (otherwise: rename the f-curves' data_path or the bones)
for pb in target.pose.bones:
    pb.rotation_mode = "QUATERNION"         # glTF animates rotation_quaternion
target.animation_data_create()
target.animation_data.action = act
target.animation_data.action_slot = target.animation_data.action_slot or au.action_get_first_suitable_slot(act, "OBJECT")
```

Measured pitfalls:

- With the bone in `XYZ`, the glTF action **moves nothing**. The value goes to `rotation_quaternion`, which the bone ignores.
- The glTF exporter takes **all** the file's actions that fit the object. In the test, `Wave` and `RigAction` came out together.
- The importer creates one action per animation, each with its own slot (`OBRig.001`).
- For rigs with different names (Quaternius × ours), rename the target's bones or rewrite the `data_path`. To do that, create the new f-curve with `bag.fcurves.new_from_fcurve(src, data_path=new)`.

### NLA by script **[tested]**

```python
ad.action = None                              # the active action stays ON TOP of the NLA
tr = ad.nla_tracks.new(); tr.name = "Walk"
st = tr.strips.new("Walk", 1, act)           # (name, start frame, action)
st.action_slot = act.slots["OBRig"]          # the strip also has a slot
st.repeat = 3.0                              # repeated cycle: frame_end adjusts by itself (1 -> 82)
st.blend_in = st.blend_out = 4
st2 = ad.nla_tracks.new().strips.new("Breath", 1, breath)
st2.blend_type, st2.influence = "ADD", 0.5   # added layer (breathing on top of the walk)
```

Assigning `strip.action` picks the first compatible-type slot by itself. For a simple cycle, the **CYCLES** modifier on the f-curve is shorter **[tested]**: `fc.modifiers.new("CYCLES")` repeats the frame 9 key at frames 41 and 105.

---

## 2. Armature by script in the background

### Create **[tested]**

```python
arm = bpy.data.armatures.new("Rig"); rig = bpy.data.objects.new("Rig", arm)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")              # works with -b: only needs an active object
eb = arm.edit_bones.new("Thigh.L")
eb.head, eb.tail, eb.roll = (0.1, 0, 0.98), (0.1, 0.02, 0.52), 0.0
eb.parent, eb.use_connect = arm.edit_bones["Pelvis"], False
bpy.ops.object.mode_set(mode="OBJECT")            # writes the edit bones into arm.bones
```

- **The pose bone's local axes = the bone's rest axes:** Y along the bone, roll rotates X and Z. With roll 0:
  - bone toward +Y: axes equal to the world's;
  - bone toward +Z: local Y = world Z;
  - bone toward -Z: rotation on local X swings forward and back.

  The biped example uses this. Prefer building leg and arm bones standing, with roll 0, and checking with a frame.
- **Bone length is leg length.** In the first test, the shin ended up 0.38 m instead of 0.44 m because the joint height came from another constant. Result: IK stretched the leg to the maximum and the foot slid 35 to 55 mm. Build the rig with a straight leg (hip = ankle + thigh + shin) and lower the hip in the animation.
- Blender 5.0: `Bone.select` and `Bone.hide` (for pose) moved to `pose.bones[i].select` and `pose.bones[i].hide`.

### Weights

| Path | When | Status |
| --- | --- | --- |
| `parent_set(type="ARMATURE_AUTO")` | whole organic mesh (bone heat) | **[tested]** FINISHED with no window and no override: mesh and armature selected, armature active; 0 vertices without weight |
| `parent_set(type="ARMATURE_ENVELOPE")` | when heat fails; control by `envelope_distance`, `head_radius` and `tail_radius` | **[tested]** with `temp_override(active_object=rig, selected_editable_objects=[mesh, rig])` |
| hand-made vertex groups + Armature modifier | **low-poly in parts** (our case), rigid 100% weights per part; never fails | **[tested]** in `walk_biped_ik.build_body` |

The parent operator requires an active object and walks `selected_editable_objects`. It depends on neither area nor region, so it runs in `-b`.

The warning "Bone Heat Weighting: failed to find solution for one or more bones" comes out as a WARNING: the operator finishes, but leaves empty groups. Reported causes:

- loose parts in the same object;
- inverted normals;
- scale not applied;
- bone outside the mesh;
- duplicate vertices.

Always check `sum(1 for v in me.vertices if not v.groups) == 0`.

Rigid weights by hand (4 lines):

```python
g = body.vertex_groups.new(name="Shin.L")             # name = bone name
g.add(part_indices, 1.0, "REPLACE")
body.parent = rig
body.modifiers.new("Armature", "ARMATURE").object = rig
```

To read the deformed mesh (measure the foot, collision, stills), use `mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).data`. `mesh.data` stays in the rest pose.

---

## 3. Procedural locomotion

### Walk cycle (Richard Williams)

It is 4 poses per step and 8 per cycle: **contact** (feet apart, heel touches), **down** (front leg bends, body at its **lowest** point), **passing** (free leg passes the support leg) and **up** (push-off, body at its **highest** point). The example puts the height minimum right after each contact (`u = 0.1` and `0.6` of the cycle). The hip rotates about 5° and the chest about 9° in the opposite direction. The arms go opposite to the leg on the same side.

### Planted foot with IK **[tested]**

```python
c = rig.pose.bones["Shin.L"].constraints.new("IK")
c.target, c.chain_count = ik_empty, 2              # shin + thigh
c.pole_target, c.pole_angle = pole_empty, math.radians(90)
```

- **Measured pole angle** (vertical bones, roll 0, pole in front of the knee):

  | Angle | Result |
  | --- | --- |
  | +90° | knee forward (4 to 27 cm) |
  | -90° | bends backward |
  | 0° and 180° | knee 27 cm to the side |

  For another rig, sweep the 4 values and measure (`walk_biped_ik.measure_slide`).
- Target and pole as **empties animated in world space**: the foot math stays in world meters, with no conversion to bone space. The pole moves along with the body.
- The foot stays still in stance because the IK target does not move in that stretch:

  ```text
  stride   = v · T                                   (same foot, contact to contact)
  stance   : y_foot = stride · (cycle + phase + duty/2)  -> constant
  swing    : y_foot advances one stride with smoothstep; height = lift · sin(π·v)
  reach    = v · T · duty / 2   (how far the foot stays in front of or behind the hip)
  ```

- **Mandatory check:** `hypot(hip_height - ankle, reach) < thigh + shin`. If it does not pass, IK stretches the leg and the foot detaches (slides). Fixes: lower the speed, shorten the cycle or lower the hip.
- Key on **every frame** (or every 2, with LINEAR) on the target, the Root and the hip. With Bezier, the curve between keys reintroduces the slide.

### Stride, duty and gait from speed

| Quantity | Formula or value | Source |
| --- | --- | --- |
| Froude | Fr = v² / (g·h), with h = hip height | Alexander & Jayes 1983 |
| Walk → run | switch near Fr ≈ 0.5 (0.4 to 0.6) | Kram et al. 1997; Donelan & Kram 1997 |
| Relative stride | λ/h ≈ 2.3·Fr^0.3 (λ = stride) | Alexander 1976 (secondary source) |
| Duty factor | walk > 0.5 (classic lateral 0.75); trot ≈ 0.5; gallop and run < 0.5 (aerial phase) | Hildebrand; Cartmill et al. 2002 |

Phases (fraction of the cycle in which each leg touches the ground), in `gait.GAITS` **[tested: legs on the ground per gait]**:

| Gait | LH | LF | RH | RF | Duty | Legs on the ground |
| --- | --- | --- | --- | --- | --- | --- |
| walk (lateral sequence) | 0 | 0.25 | 0.5 | 0.75 | 0.75 | 3 to 4 |
| **sauropod** (lateral, diagonal couplet) | 0 | 0.35 | 0.5 | 0.85 | 0.70 | 2 to 4, always with diagonal support |
| trot | 0 | 0.5 | 0.5 | 0 | 0.50 | 2 |
| pace (camel, giraffe) | 0 | 0 | 0.5 | 0.5 | 0.55 | 2 to 4 |
| transverse gallop | 0 | 0.5 | 0.1 | 0.6 | 0.35 | 0 to 2 |
| biped walking / running | L 0 | | R 0.5 | | 0.60 / 0.35 | 1 to 2 / 0 to 1 |

- **Sauropods** (Lallensack & Falkingham 2022, from trackways): they walked in a lateral sequence with a "diagonal couplet". The front foot touches shortly after the hind foot on the same side, and diagonal support is never missing. It was more hippo than elephant.
- The current `dinos.walk` uses diagonal pairs in exact phase (0 and 0.5), which is a slow trot. Swapping to the `sauropod` phases is the cheapest change to make the brachiosaur look right.
- **Quadruped:** each leg is an IK chain (or the current `asin`) with its own hip or shoulder. The body bobs 2 times per cycle in the walk and 1 time in the gallop. The head and neck compensate with a delay of 2 to 4 frames.
- **Idle and breathing:** an `ADD` NLA strip with the chest scaling 1 to 2% (or a 1 to 2° rotation on the chest bone), with a period of 3 to 4 s for a human and 6 to 10 s for a large animal. It fades with the walk's weight; never leave a character 100% still.

---

## 4. Falls and impacts

### Rigid body **[tested]**

```python
bpy.ops.rigidbody.world_add()
sc.rigidbody_world.point_cache.frame_start, sc.rigidbody_world.point_cache.frame_end = 1, 60
with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o]):
    bpy.ops.rigidbody.object_add(type="ACTIVE")       # PASSIVE for the ground
o.rigid_body.collision_shape = "BOX"                   # BOX/SPHERE/CONVEX_HULL; MESH only on passives
bpy.ops.ptcache.bake_all(bake=True)                    # works with -b, no override
```

- `ptcache.bake_all` only requires a scene in the poll and bakes synchronously when called from Python. For a single cache: `with temp_override(point_cache=pc): bpy.ops.ptcache.bake(bake=True)`. That case was not tested; it comes from the source code.
- **`bpy.ops.rigidbody.bake_to_keyframes` FAILS in the background**, because it calls `anim.keyframe_insert_by_name`, whose poll requires a window. Convert by hand (`physics_debris.physics_to_keys`): read `matrix_world` frame by frame with the baked cache, run `rigidbody.world_remove()` and write `location` and `rotation_euler`. Use `rot.to_euler("XYZ", previous)` so the euler does not jump 360°.
- Physics converted to keys does not depend on a cache, survives the pipeline's partial `--frames` and passes the audit.

### Ragdoll (not tested)

The known path:

- one rigid body per bone (capsule);
- `RigidBodyConstraint` of type `GENERIC_SPRING` or `POINT` between them;
- on the bone, `Copy Transforms` pointing to the body, switched on by a key at the moment of impact.

It is costly to set up and unstable with thin limbs. For our style, the keyframed fall below gives more control.

### Keyframed fall with easing **[tested]**

Evaluated values of a fall from z = 5 to z = 0 in 20 frames:

| Key | Evaluation | Use |
| --- | --- | --- |
| `LINEAR` | 5 → 3.75 → 2.5 → 0 | constant speed ("plank" look) |
| `QUAD` + `EASE_IN` | 4.95 → 3.75 → 0.95 → 0 | **gravity**: starts slow, accelerates to the impact |
| `BACK` + `EASE_IN`, `back = 2` | rises to 5.62 before falling | **anticipation** (crouches or lifts before tipping) |
| `BOUNCE` + `EASE_OUT` | 2.64 → 1.17 → 0.14 → 0 | bounce on the ground after the impact |
| `ELASTIC` + `EASE_OUT` | overshoots the target and oscillates | impact tremor on a light part |

The interpolation and the easing live on the **outgoing key** (the one at the start of the stretch): `kp.interpolation`, `kp.easing`, `kp.back`, `kp.amplitude`, `kp.period`. Recipe for a tumble with life:

1. **Anticipation:** BACK for 4 to 8 frames.
2. **Fall:** QUAD or CUBIC with EASE_IN; the rotation accelerates.
3. **Impact:** exact frame, with dust and a short camera jolt.
4. **Settling:** small BOUNCE, or 2 bounce keys.
5. **Delay of the soft parts:** neck and tail hit 3 to 6 frames after the body.

---

## 5. Instances and scattering with Geometry Nodes **[tested]**

```python
ng = bpy.data.node_groups.new("Forest", "GeometryNodeTree")
ng.is_modifier = True
ng.interface.new_socket("Geometry", in_out="INPUT",  socket_type="NodeSocketGeometry")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket("Density Mask", in_out="INPUT", socket_type="NodeSocketFloat")
# nodes: GeometryNodeDistributePointsOnFaces (POISSON, Distance Min, Density Max, Seed)
#   -> GeometryNodeInstanceOnPoints (Pick Instance = True) <- GeometryNodeCollectionInfo (Separate/Reset Children)
#   + FunctionNodeRandomValue (Z rotation, scale) -> Join Geometry with the terrain -> output
mod = obj.modifiers.new("Forest", "NODES"); mod.node_group = ng
```

**A 5.2 change that breaks old code:** the modifier inputs are no longer IDProperties.

```python
mod["Socket_2"] = 0.5                       # 5.2: TypeError "id properties not supported"
mod["Socket_2_use_attribute"] = True        # same
entry = getattr(mod.properties.inputs, "Socket_2")    # identifier of the interface socket
entry.type, entry.attribute_name = "ATTRIBUTE", "forest"   # or entry.type = "VALUE"; entry.value = 0.5
```

`scatter_gn.set_input(mod, "Density Mask", attribute="forest")` finds the identifier by name.

Measured with **15,893 trees** (3 models, 270x480 render in Eevee):

| | Build | 1-frame render | .blend |
| --- | --- | --- | --- |
| GN (one object) | 0.03 s | 1.02 s | 0.4 MB |
| loose objects (shared mesh) | 0.93 s | 2.25 s | 1.6 MB |

- With up to a few thousand objects, creating is not the bottleneck (5000 in 0.11 s). The gain is in the render, the file size and changing density, seed or mask in one place.
- The vertex group as a density mask keeps the path clear: 0 of 409 trees on the path.
- The models sit in a collection with `layer_collection.exclude = True`: they serve as a mold and do not show.
- The origin of each model at the tree's foot makes the instance spawn on the ground.
- In 5.2, Empty objects can also have a node modifier.
- GN instances do **not** appear in `obj.children`. For the audit and `visible()`, hiding the terrain hides the trees.

---

## 6. Particles and dust and debris simulation **[tested]**

- A face emitter with `render_type = "OBJECT"` (or `COLLECTION`) renders in Eevee: 80 instances in the depsgraph and visible in the PNG. Halo, Line and Path do not work for Eevee. There is only an old report, unconfirmed on 4.2+; do not use.
- **Bake is mandatory.** A particle without a baked cache errs when `frame_set` skips frames, which is what `--stills` and `--frames` do. Measured without bake: mean z of 0.29 m at frame 28 and 0.02 m at 35, with the dust "respawning". With `bpy.ops.ptcache.bake_all(bake=True)`, the order does not matter (0.673 m at 35, in both readings).
- Translucent dust: `mat.surface_render_method = "BLENDED"`, alpha 0.4 to 0.6, `effector_weights.gravity` near 0, and `em.show_instancer_for_render = False` to hide the emitter plane.
- Cache-free alternative (the one in `dinos.collapse`): icospheres with scale and position keys. Deterministic, easier to sync with the sound (`sound-designer`) and passes the partial `--frames`. For up to 20 to 30 clouds, prefer keys; for hundreds of grains, use baked particles.
- Debris: rigid body baked and **converted to keys** (section 4) is the most stable for the pipeline.
- Hair in Eevee 5.0 respects `resolution` and generates about 15 times more geometry by default. For grass, use GN with instances, not hair.

---

## 7. bpy background pitfalls (5.x)

| Pitfall | What to do | Status |
| --- | --- | --- |
| `action.fcurves` does not exist (removed in 5.0) | `fcurves_of()`, channelbag or `au.animdata_get_channelbag_for_assigned_slot` | tested |
| Action assigned without a slot: object still with no error | always `ad.action_slot = slot` | tested and in the 4.4 notes |
| Bone `rotation_mode` different from the curve's `data_path` | pose bone starts as QUATERNION; set XYZ before using `rotation_euler`, or QUATERNION for glTF | tested |
| Operators that require an active or selected object | `with bpy.context.temp_override(object=o, active_object=o, selected_objects=[...], selected_editable_objects=[...])` | tested (`rigidbody.object_add`, `parent_set`, `modifier_apply`) |
| Operator that calls another window operator inside | `rigidbody.bake_to_keyframes` fails; do it by hand | tested |
| Applying a modifier | `temp_override(object=o, active_object=o)` + `bpy.ops.object.modifier_apply(modifier=...)`, or without an operator: `bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph))` (`kit.skin_mesh` already does it this way) | tested |
| Reading the deformed mesh or the GN result | `obj.evaluated_get(bpy.context.evaluated_depsgraph_get())`; after changing data, `view_layer.update()` or `frame_set` | tested |
| GN modifier inputs | `mod.properties.inputs.<Socket_N>.value / .type / .attribute_name` (5.2) | tested |
| `Material.use_nodes` and `World.use_nodes` | deprecated, "expected to be removed in Blender 6.0"; always True. Reading or writing raises a DeprecationWarning (`kit.flat` reads it; it can be removed). `scene.node_tree` became `scene.compositing_node_group` | tested |
| `world.color` does not paint the render background | the world is born with nodes: change `world.node_tree.nodes["Background"].inputs["Color"]` | tested |
| Engine id | `"BLENDER_EEVEE"` in 5.x (the enum has only that); 4.2 to 4.5 used `"BLENDER_EEVEE_NEXT"` | tested |
| Particles and physics cache with out-of-order `frame_set` | `bpy.ops.ptcache.bake_all(bake=True)` before any still | tested |
| Edit bones | only exist between `mode_set("EDIT")` and `mode_set("OBJECT")`; keep names, not references | tested |
| Bone selection (5.0) | `pose.bones[i].select` and `edit_bones[i].select`; `Bone.select` is gone | 5.0 notes |
| Windowless render on Windows | `-b` works (all tests); the manual warns that headless Windows (no graphical session) is not supported | tested with an open session |

---

## Sources

**Blender: release notes and API**

- 4.4, Python API (slotted actions, legacy API): https://developer.blender.org/docs/release_notes/4.4/python_api/
- 4.4, Animation & Rigging: https://developer.blender.org/docs/release_notes/4.4/animation_rigging/
- 5.0, Python API (removal of `action.fcurves`, `action_ensure_channelbag_for_slot`, `use_nodes`, `compositing_node_group`, engine id): https://developer.blender.org/docs/release_notes/5.0/python_api/
- 5.0, Eevee (hair with `resolution`): https://developer.blender.org/docs/release_notes/5.0/eevee/
- 5.2, Python API (node modifier inputs in `properties.inputs`): https://developer.blender.org/docs/release_notes/5.2/python_api/
- 4.2, Python API (`BLENDER_EEVEE_NEXT`, motion blur in `scene.render`): https://developer.blender.org/docs/release_notes/4.2/python_api/
- 4.0, Python API (`interface.new_socket`): https://developer.blender.org/docs/release_notes/4.0/python_api/
- `bpy.types.Action`: https://docs.blender.org/api/current/bpy.types.Action.html
- `ActionSlots`: https://docs.blender.org/api/current/bpy.types.ActionSlots.html
- `ActionLayers`: https://docs.blender.org/api/current/bpy.types.ActionLayers.html
- `ActionStrips`: https://docs.blender.org/api/current/bpy.types.ActionStrips.html
- `ActionKeyframeStrip`: https://docs.blender.org/api/current/bpy.types.ActionKeyframeStrip.html
- `ActionChannelbagFCurves`: https://docs.blender.org/api/current/bpy.types.ActionChannelbagFCurves.html
- `bpy_extras.anim_utils`: https://docs.blender.org/api/current/bpy_extras.anim_utils.html
- `AnimData`: https://docs.blender.org/api/current/bpy.types.AnimData.html
- `NlaStrips`: https://docs.blender.org/api/current/bpy.types.NlaStrips.html
- `NlaStrip`: https://docs.blender.org/api/current/bpy.types.NlaStrip.html
- `Keyframe` (easing, back, amplitude, period): https://docs.blender.org/api/current/bpy.types.Keyframe.html
- Interpolations: https://docs.blender.org/api/current/bpy_types_enum_items/beztriple_interpolation_mode_items.html
- Easing: https://docs.blender.org/api/current/bpy_types_enum_items/beztriple_interpolation_easing_items.html
- `bpy.ops.object` (`parent_set`): https://docs.blender.org/api/current/bpy.ops.object.html
- `bpy.ops.ptcache`: https://docs.blender.org/api/current/bpy.ops.ptcache.html
- `bpy.ops.rigidbody`: https://docs.blender.org/api/current/bpy.ops.rigidbody.html
- `RigidBodyWorld`: https://docs.blender.org/api/current/bpy.types.RigidBodyWorld.html
- `PointCache`: https://docs.blender.org/api/current/bpy.types.PointCache.html
- `RigidBodyObject`: https://docs.blender.org/api/current/bpy.types.RigidBodyObject.html
- `NodeTreeInterface`: https://docs.blender.org/api/current/bpy.types.NodeTreeInterface.html
- `GeometryNodeTree` (`is_modifier`): https://docs.blender.org/api/current/bpy.types.GeometryNodeTree.html
- `ParticleSettings`: https://docs.blender.org/api/current/bpy.types.ParticleSettings.html

**Manual**

- Parenting and skinning (automatic and envelope): https://docs.blender.org/manual/en/latest/animation/armatures/skinning/parenting.html
- Rigid Body World: https://docs.blender.org/manual/en/latest/physics/rigid_body/world.html
- Baking: https://docs.blender.org/manual/en/latest/physics/baking.html
- Rigid body collisions: https://docs.blender.org/manual/en/latest/physics/rigid_body/properties/collisions.html
- Particle render: https://docs.blender.org/manual/en/latest/physics/particles/emitter/render.html
- Eevee limitations: https://docs.blender.org/manual/en/latest/render/eevee/limitations/limitations.html

**Source code and reports**

- `parent_set` (poll and exec): https://projects.blender.org/blender/blender/src/branch/main/source/blender/editors/object/object_relations.cc
- Bone heat: https://projects.blender.org/blender/blender/src/branch/main/source/blender/editors/armature/meshlaplacian.cc
- Point cache bake: https://projects.blender.org/blender/blender/src/branch/main/source/blender/editors/physics/physics_pointcache.cc
- GN by Blender itself (`is_modifier`): https://projects.blender.org/blender/blender/src/branch/main/scripts/startup/bl_operators/geometry_nodes.py
- Causes of "failed to find solution":
  - https://archive.blender.org/lists/bf-animsys/2017-April/000260.html
  - https://projects.blender.org/blender/blender/issues/37685
  - https://blenderartists.org/t/bone-heat-weighting-failed-to-find-solution-for-one-or-more-bones/701412
- Particles in Eevee (old report): https://projects.blender.org/blender/blender/issues/80197

**Locomotion**

- Alexander, R. McN. (1976). Estimates of speeds of dinosaurs. *Nature* 261:129–130. https://doi.org/10.1038/261129a0 (formula seen in a secondary source: https://www.eps.sci.kyoto-u.ac.jp/ieshub/kagi21/jp/workshop/2005/20050824-0000_a.html)
- Alexander & Jayes (1983). A dynamic similarity hypothesis for the gaits of quadrupedal mammals. *J. Zool.* 201:135–152. https://doi.org/10.1111/j.1469-7998.1983.tb04266.x
- Kram, Domingo & Ferris (1997). *J. Exp. Biol.* 200:821. https://journals.biologists.com/jeb/article/200/4/821/
- Donelan & Kram (1997). *J. Exp. Biol.* 200:3193. https://doi.org/10.1242/jeb.200.24.3193
- Cartmill et al. (2002). Support polygons and symmetrical gaits in mammals: https://www.originalwisdom.com/wp-content/uploads/bsk-pdf-manager/2019/10/Cartmill-et-al_2002_Support-polygons-and-symmetrical-gaits-in-mammals.pdf
- Lallensack & Falkingham (2022). Limb phase from trackways, sauropod gaits. *Current Biology* 32:1635–1640. https://doi.org/10.1016/j.cub.2022.02.012 (https://researchonline.ljmu.ac.uk/id/eprint/16310/; summary: https://theconversation.com/we-discovered-how-the-largest-dinosaurs-walked-and-it-was-more-like-hippos-than-elephants-178194)
- Williams's poses (secondary source, the book is not online): https://courses.cs.washington.edu/courses/cse459/19au/assignments/assignment_5/index.html

**Not confirmed in a primary source:** the original text of Alexander 1976 and Hildebrand 1965 (the formulas come from a secondary source); Halo, Line and Path particles in Eevee 4.2+; `ptcache.bake` with a single-cache override (inferred from the code, not tested); ragdoll (not tested).
