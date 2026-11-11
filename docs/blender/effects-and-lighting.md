# Visual effects, light and color in Eevee for low-poly (Blender 5.2)

Research from 2026-10-21 for the `blender-specialist` agent. Everything marked **[tested]** was rendered in this PC's Blender 5.2.2 LTS (RX 7600, Eevee, in the background), with pixel measurement. What is marked **[source]** comes from the manual or the release notes, without a test here.

Scripts that worked: `tools/blender/examples/`.

| File | What it does |
| --- | --- |
| `fx_common.py` | Night test scene, faceted icosphere, `view()` (color management), dense LINEAR keys |
| `fx_color.py` | Test (a): the same fireball in AgX, AgX Punchy, Standard and Khronos |
| `fx_agx_grid.py` | Emission map: which input gives which screen color in AgX |
| `fx_explosion.py` | Test (b): layered explosion, no volume |
| `fx_dust.py` | Test (c): "glass" dust against matte dust and erosion dust |
| `fx_volume_cost.py` | Faceted mesh against Principled Volume: time and look |
| `fx_sheet.py` | Side-by-side sheet and color measurement (Pillow, outside Blender) |

Images: `build/fx-tests/`.

---

## 1. Color management: AgX, Filmic, Standard

### What Blender 5.2 offers

Checked in Blender 5.2's own `config.ocio` **[tested]**.

- **Views for sRGB:** Standard, ACES 1.3, ACES 2.0, Khronos PBR Neutral, AgX, Filmic, Filmic Log, False Color and Raw.
- **AgX looks:** `AgX - Punchy`, `AgX - Greyscale`, `AgX - Very High Contrast`, `High Contrast`, `Medium High Contrast`, `Base Contrast`, `Medium Low Contrast`, `Low Contrast` and `Very Low Contrast`.
- **What each look does:** Punchy is a *GradingTone* that darkens the shadows plus a power curve of 1.09. The contrast ones change the contrast around 18% gray and reduce saturation to 0.9 to 0.95 on the strongest.
- **Pipeline default:** `reset_scene` uses `read_factory_settings`, so today every video comes out in **AgX, look None, exposure 0**.

What the sources say:

- **AgX** [source, manual 5.2]: "desaturates highly exposed colors to mimic film's natural response to light". The 4.0 notes say: "bright colors go towards white, similar to real cameras".
- **Standard** [source]: "Does no extra conversion besides the conversion for the display. Often used for non-photorealistic results".
- **Filmic** [source]: "deprecated and is superseded by AgX". Do not use.
- **Khronos PBR Neutral** [source]: made for product photography, with base colors faithful under gray light.

### Why emission turns pink or cream [tested]

AgX works in log (from -12.5 to +12.5 stops). The farther from middle gray, the more it pulls the color toward white. Orange has little green and little blue, which are exactly the channels that "rise" first on that path. That is why orange passes through salmon and cream before reaching white.

Test `fx_color.py`: emission color #FF6A00, black base, same geometry. Sheet in `build/fx-tests/a_color_side_by_side.png`.

| Strength | AgX | AgX Punchy | Standard | Khronos |
| --- | --- | --- | --- | --- |
| 0.8 | #CB6215 (sat 0.90) | #AB4900 (sat 1.00, dark) | #E75F00 | #E45E09 |
| 2 | **#EB9266 (sat 0.57, salmon)** | #DC7539 | #FF9200 (orange-yellow) | #FA8865 (salmon) |
| 5 | #FCBB9F (pinkish cream) | #F5A47F | #FFDC00 (yellow) | #FDB4A4 (pink) |
| 15 | #FEDCCB (almost white) | #FECEB8 | #FFFF00 (pure yellow) | #FEDCD6 |
| Brand amber #F5A524, strength 1 | **#CA954A (sat 0.63, dull)** | #B37A18 | **#F5A524 (exact)** | #EC9E17 |
| Sky #0E1626 (background) | #07121F (darker) | **#010309 (black)** | #0F1727 (exact) | #010D22 |

What the table shows:

1. **In AgX, strength 2 is already salmon.** That is exactly the "pink dome" of the Pangaea video. Orange only stays saturated with strength below ~1 and with the largest channel up to ~1.
2. **AgX does not reach the brand palette.** `fx_agx_grid.py` tested 256 input combinations (green/red from 0.10 to 0.70, strength from 0.35 to 4.8). The closest to amber #F5A524 comes out #CD9240 (input `(1, 0.38, 0) x 0.95`). The one for orange #FF6A00 comes out #CB6115 (`(1, 0.14, 0) x 0.8`). Both end up ~20% darker and less saturated, with an RGB error of ~50. No input solves it. Ember (#E0611C → #D45F24) and red (#C0300A → #B04000) can get close.
3. **AgX - Punchy crushes the navy night to black** (sky #0E1626 → #010309). It saturates the fire, but kills the identity's background. **Do not use.**
4. **Standard is faithful to the palette** (#F5A524 → #F5A524; sky exact). When emission goes above 1, it clips channel by channel: orange goes to **yellow** (#FF9200 → #FFDC00 → #FFFF00), not to pink. For fire, that is the "classic" color path (yellow core, orange edge) and it matches the brand amber.
5. **Khronos behaves like AgX on fire** (salmon at strength 2). It does not work either.

### Recommendation for the flat low-poly style

**Option A: stay on AgX** (changes nothing in videos already made).

- **Colored emission:** strength ≤ 1, i.e. the largest channel of (linear color x strength) up to ~1.
- **Fire glow:** comes from color (yellow in the center, orange at the edge), not from strength.
- **High strength (≥ 3):** only on small parts that should turn white (flash core, sparks).
- **Look:** None. Never Punchy.
- **Price:** the brand color in 3D comes out ~20% duller (#CA954A). The amber windows of `window_material` (strength 2.2) already come out cream because of that.

**Option B: Standard** (recommended for the next videos, **if the owner approves after seeing a still**).

- **Gain:** the palette comes out exact, fire goes to yellow and the night stays in the chosen navy.
- **Price:** there is no "shoulder" in the highlights. A surface lit above 1.0 clips hard. So:
  - sun and ambient need to be readjusted (direct light + albedo ≤ ~0.9);
  - specular highlight off (`Specular IOR Level = 0` on the flat materials, which is already right for low-poly).
- **How to test:** render a still of an existing set in both modes before switching:

  ```python
  scene.view_settings.view_transform = "Standard"   # or "AgX"
  scene.view_settings.look = "None"
  scene.view_settings.exposure = 0.0                 # Standard: compensate with exposure -0.3 to -0.6 if the scene blows out
  ```

  It is a change to the look of the whole video. Do not apply without the owner seeing it.

**Compositor only for effects?** It would be possible to render in Raw and convert in the compositor (new *Convert to Display* node, 5.0 [source]). Not worth it: the color transform is global, and mixing two in the same frame requires a mask (cryptomatte) per frame and doubles the chance of a jagged edge. The "strength ≤ 1" rule in AgX, or Standard, solve it without a compositor.

---

## 2. Stylized low-poly explosions

### How artists do it [source]

- **"Cartoon Explosions" (Blender Artists):**
  - icosphere;
  - Subdivision 2 → Displace with a hard-blotch texture (shape) → Displace with no texture, strength 0.05 (inflates) → Subdivision → Displace with clouds (size 0.25, strength 0.15). With the coordinates on an Empty, the Displace "boils" when the Empty moves;
  - a single material with three animated controls: fire→smoke, smoke alpha and brightness;
  - debris = copies of the same stack in a cone;
  - "The key to creating a good explosion is in the timing".
- **Shockwave (Bad Normals / 3dart.it):** disc or slice of a sphere, no volume or simulation.
- **Volumetric** ("Stylized Explosions" packs and similar): volume pyro. Pretty, but it is another style (blurry, see below).

### Volume in Eevee: cost and limits

- **Cost** [tested, `fx_volume_cost.py`, 1080x1920, 32 samples]: a Principled Volume cloud cost **0.40 s per frame, against 0.39 s** for the same cloud as a mesh. For a small volume, the cost is the same.
- **The problem is the style:** the volume comes out **blurry and with no facets** (`build/fx-tests/d_volume_vs_mesh.png`). It does not match low-poly.
- **Limits [source, manual]:**
  - only one scattering;
  - volume "does not cast shadows on solid objects";
  - does not appear in reflections or probes;
  - uses heavy 3D textures in memory;
  - volume in the World blocks sun and sky since 4.2.
- **Conclusion:** always faceted mesh. Volume only for background fog, and carefully (section 7).

### Tested recipe: `fx_explosion.py` [tested]

Images:
- `build/fx-tests/b_explosion_AgX.png`
- `build/fx-tests/b_explosion_Standard.png`
- `b_explosion_*.mp4` (3 s, half resolution)
- 1st attempt with defects: `b_explosion_AgX_v1.png` and `_v2.png`

Timing at 30 fps, with F = the flash frame:

| Phase | Frames | What happens |
| --- | --- | --- |
| Anticipation | 1 to F-1 (~0.25 s) | Hot seed that swells and contracts, with weak light on the ground |
| Flash | F to F+4 | White core (strength 8, on purpose) grows in 3 frames. Point light rises with `ease_in_out` in 5 frames and decays exponentially (~7 frames) |
| Expansion | F to F+16 | 9 bubbles grow with `ease_out(u)**3` (fast and then slow), shock ring on the ground, dust running with the ring, ballistic debris with real gravity and sparks stretched in the direction of flight |
| Residue | F+16 onward | Color cools (white → orange → ember → gray), the upper bubbles rise more (mushroom), embers on the debris fade, scorched ground |

Mean brightness measured frame by frame: 15 → 20 → 33 → 41 → 45, with no step. `tools/qa/flicker.py` flagged nothing in AgX. In Standard it flagged only the frame of the flash peak (intentional).

The points that make the difference:

1. **One material for the whole fire, with one "temperature".** A Value node `Heat` (0..1, animated) goes through a color ramp: #2A0C04 → #B8300A → #FF5A00 → #FFA830 → #FFF2CC.
   - Strength is `3 x heat²`: hot turns white, warm turns orange with strength ~1 (in AgX, more than that turns salmon).
   - Base Color gray #77727E: with `heat = 0` the smoke is left, without swapping objects.
   - `Object Info > Random` varies ±15% per bubble.
2. **Facets that read as volume, not a flat disc.**
   - *Layer Weight > Facing* (with flat shading it applies per face) cools the edge of each facet: `temperature = heat - 0.35 x facing`. Without it, pure emission becomes a cut-out disc (see `a_color_side_by_side.png`).
   - Shape: icosphere subdiv 2 + `lumpy()` (continuous per-vertex noise, flattened at the bottom) + Displace CLOUDS with coordinates on an Empty that rises 0.05 per frame, which is the "boiling".
3. **Dense LINEAR keys**, one per frame, computed in Python (`fx.curve_keys` + `fx.set_interp`). No Bezier overshooting and no CONSTANT.
4. **`visible_shadow = False` on every part of the effect.** Only the flash point light casts shadow. That solves the "dome that wipes out the scene".
5. **Smoke lighter than the sky.** With #3A3840 it vanished against the night (v1); with #77727E it reads. The dust gets warm emission `0.08 + 0.5 x heat`: it is lit by the fire and fades with it.
6. **Scale against the camera.** Nothing of the effect may reach the camera.
   - In v2 the dust ran 11 m and became boulders in front of the lens.
   - In v3 the ring went up to 16 m (the exact distance to the camera) and became a brown band at the base of the screen. `flicker.py` flagged a "pop" at frame 18.
   - **Limit the reach to ~60% of the distance to the camera.**

What still did not come out good, honestly:

- The ring's dust bubbles still look like stones when still; in motion they read better.
- The white flash hides everything for ~6 frames.

### Reference timing (30 fps)

| Phase | Duration |
| --- | --- |
| Anticipation | 4 to 8 frames |
| Flash rise | 3 to 5 frames (never 1: it is the step the owner calls flicker) |
| Fireball | Reaches ~85% of the size in 16 frames and keeps growing ~0.4% per frame |
| Cooling | Constant of ~26 frames (too fast becomes ember already mid-expansion; v1) |
| Residue | 2 s or more |
| Flash light | Falls to ~12% in ~1 s and follows the temperature down to zero |

---

## 3. Low-poly dust and smoke

### Test `fx_dust.py` [tested]

`build/fx-tests/c_dust.png`: the same cloud of 9 icospheres, at frames 8, 30 and 50.

| Version | What it is | Result |
| --- | --- | --- |
| A "glass" | Blended, alpha 0.45 → 0, roughness 0.3, smooth | **Looks like a glass bubble** (specular reflection + see-through). And it **does not fade**: 9 overlapping bubbles = ~18 Blended layers. At 0.075 per layer it still covers ~75% (1 - 0.925^18). At frame 50 it is still there |
| B matte opaque | Roughness 1, `Specular IOR Level` 0, no transparency. It vanishes by **shrinking**, from the outside in, rising and fading to the sky color (#3A4660) | **Reads as dust and vanishes cleanly.** It is the recommended one |
| C matte by erosion | Dithered + **binary** alpha (`Noise > threshold`, with the threshold animated) + `use_backface_culling` | Breaks up in pieces, no grain. Works to dissipate quickly, but looks like "Swiss cheese" if it takes long. Without backface culling, the dark inside shows through the holes |

### Rules

- **Not translucent, shrinking yes.** In low-poly, dissipate = scale to 0 + color going to the ambient color.
- **If you need alpha:**
  - **Dithered** with alpha 0/1 (the manual recommends the *Alpha Clip Setup* with `Greater Than` to avoid noise);
  - or **Blended** with `use_transparency_overlap = False` (front face only) and **one object per cloud**.
- **Blended limits** [source]:
  - sorts only by object, by origin, never by face;
  - stays out of raytracing and passes;
  - thousands of Blended objects degrade performance.
- **What makes it look like glass:** reflection (specular > 0, roughness < 0.8), smooth surface (smooth shading/subdiv), edge lighter than the center and uniform transparency. The remedy is the opposite: matte, flat and opaque.
- **Shadows:** dust and smoke with `visible_shadow = False`. In 4.2+ the old material "Shadow Mode" became `Object > Visibility > Ray Visibility > Shadow` [source, 4.2 migration]. Dust with shadow leaves hard stains on the ground.
- **Smoke at night:** **lighter** color than the sky, or lit from below by the fire. Dark smoke vanishes.

---

## 4. Low-poly scene lighting

- **Base:** a sun (direction and color) + the world as ambient. `humans_set.build_world` already separates the seen sky (camera ray) from the ambient light (`Light Path > Is Camera Ray`). That is right: you can brighten the scene without brightening the sky.
- **World = indirect light** [source, manual]: Eevee stores the world light in an internal probe, "less precise than Cycles". The world casts no direct shadow.
- **World Sun Threshold** (`world.sun_threshold`): whatever exceeds it becomes an extracted sun. In a dark procedural sky this does not matter.
- **Shadows (Virtual Shadow Maps)** [source]:
  - `light.shadow_maximum_resolution`: the sun's default is 0.001 m per texel; larger = lighter and more leaking;
  - `shadow_filter_radius`: default 1; more than 1 px increases leaking;
  - `use_shadow_jitter`: real softness, but "high performance impact", because it redoes the map every sample;
  - `scene.eevee.shadow_resolution_scale`: 1.0;
  - `shadow_ray_count` / `shadow_step_count`: 1 / 6.
  - For low-poly, nearly hard shadow, with `light.angle` of 1 to 3 degrees on the sun, no jitter. Cheap and stable.
- **Low-poly with "jagged" shadow at the terminator** (faces toward the light with a shadow step): use the 4.5+ *Shadow Terminator* (`obj.shadow_terminator_normal_offset`, `..._geometry_offset`) [source, 4.5 notes: "remove the self shadowing artifacts on low-polygon geometry"].
- **Raytracing** (`scene.eevee.use_raytracing`, default False):
  - leave it **off**: without reflections, matte low-poly gains nothing, and the alternative mode is "more visually stable" [source];
  - *Fast GI* (`use_fast_gi`, default True, AO method) is the cheap AO; keep it;
  - 5.2 redid the screen-trace and the AO ("some scenes might render darker") [source, 5.2 notes].
- **Light Probes Volume:** only for interiors (light bounced inside a house). Exterior at night does not need it.
- **Night with amber light:**
  - blue ambient (#3A5285, strength 0.6 to 1.6) + cold moon sun (0.65, 0.75, 1.0), energy ~0.8 to 1.2;
  - amber point lights (1.0, 0.72, 0.42) for lampposts and windows;
  - windows lit by emission ≤ 1 in AgX, otherwise cream.
- **Event light (flash) without flicker:**
  - per-frame key with a smooth rise (3 to 5 frames) and exponential decay, always LINEAR (see `seed_and_flash`);
  - a change of light state only at the cut (`lights()` of Pangaea, with CONSTANT keys at the start of each scene);
  - **never** random per frame.
- **Light Threshold** (`scene.eevee.light_threshold`, default 0.01): defines where each light stops reaching. Lower value = more cost [source]. 5.2 fixed shadow artifacts with threshold 0 [source]. Leave 0.01. For the flash to reach far, use `light.use_custom_distance` instead of zeroing the threshold.

---

## 5. Flicker and aliasing

| Cause | Remedy |
| --- | --- |
| Flashing sky | Sky and light states only change at the cut (CONSTANT key on the scene's 1st frame) or with a slow ramp. No day/night time-lapse (owner's rule) |
| Light step | Rise over 3 to 5 frames (`ease_in_out`). See the explosion measurement |
| Thin faces shimmering (grass, wires, lines, stars) | Nothing thinner than ~2 px on the final screen (1080 wide): at 10 m with a 24 mm lens, 1 px ≈ 1.4 cm, so the grass needs ≥ 3 cm of face width. TAA (`taa_render_samples`, 32 in the pipeline) smooths, but does not create what is missing between samples. A larger `render.filter_size` (default 1.5 px) softens, at the cost of sharpness [source] |
| Voronoi stars in the world (`humans_set`) | With the camera rotating, subpixel points shimmer. Point ≥ 2 px or stars as small emissive meshes |
| Overlapping faces fighting (z-fighting) | Never two coplanar faces: move apart ≥ 1 cm or delete one. 4.5 brought Reverse-Z (less fighting at long distance) [source]. Even so, `clip_start` 0.05 with `clip_end` 4000 is a high ratio; raise `clip_start` when the camera does not get close to anything |
| Shadow leaking or trembling on a thin wall | The manual: "Thin objects (e.g. walls without thickness) might have light leaking" [source]. Give the walls thickness (Solidify) |
| Shadow that changes frame to frame with the camera moving | Reported in the EEVEE Next feedback [source, devtalk]. Jitter helps little. Prefer nearly hard shadow, fixed `shadow_maximum_resolution` and still lights |

To audit, use the half-resolution preview (`IFSCAPE_PREVIEW=1`) and then `py tools/qa/flicker.py <video>`. It correctly flagged the ring that passed under the camera.

### Motion blur at 30 fps [source; not tested here]

- `scene.render.use_motion_blur`, `motion_blur_shutter` (in frames) and `scene.eevee.motion_blur_steps`.
- Each step "corresponds to a full scene re-evaluation", so 4 steps ≈ 4x the time.
- 5.2 fixed the over-blurred background.
- Recommendation: **off by default**. Low-poly is sharp, and blur on the facets takes away the style. If a scene has debris or a fast shaking camera, use `shutter 0.5` and `steps 1` (post-process only, almost free) and check on an 8-frame excerpt.

---

## 6. Outline and style [source; not tested here]

| Technique | How | Cost and risk |
| --- | --- | --- |
| Inverted hull | Solidify with `use_flip_normals`, small negative thickness, `material_offset` = 1 for a 2nd black emissive material with `use_backface_culling` | Cheap. Doubles the geometry, the thickness has to change with distance and it shimmers on far objects |
| Freestyle | `scene.render.use_freestyle` | Works in Eevee, but runs on the CPU after the render (slow) and can jitter frame to frame |
| Line Art (Grease Pencil) | Line Art modifier | Stable, configurable line, but GP changed a lot from 4.3 to 5.0 (GP v3) and it is one more system to maintain |
| Raycast node (5.1+) | Lines in the shader itself [source, 5.1 notes: "Line Rendering"] | Screen-space only |

**Recommendation:** **no outline.** The "Instrument" identity and the niche's viral videos are flat low-poly with no line. The facets and the light (sun + ambient) already separate the shapes. Outline only if the owner asks, and then with an inverted hull on the main characters only.

---

## 7. Sky, atmosphere and stylized fog

- **Sky:** procedural gradient from the horizon to the zenith (`sky_ramp` in `humans_set`) + camera seeing the sky and the scene lit by another ambient. Good, and already tested in the videos.
- **Distance fog without volume** (cheap and stable), pick one:
  1. **Mist pass + compositor** [source]: `view_layer.use_pass_mist = True`; `world.mist_settings.start`, `.depth` and `.falloff` ('QUADRATIC', 'LINEAR', 'INVERSE_QUADRATIC'). In the compositor, mix the image with the sky color by the mist. In 5.x the compositor is a node group in `scene.compositing_node_group` (no longer `scene.node_tree`).
  2. **In the material:** camera distance (`Camera Data > View Distance`) → Map Range → Mix from the object's color to the horizon color. It all stays in one pass and works in any view transform.
- **Volume in the World** (`Volume Scatter`):
  - costs the 3D textures;
  - since 4.2 "completely blocks distant light (world and sun lights)" [source];
  - makes everything milky.
  - Avoid. If used, very low density and `use_volume_custom_range` with a short `volumetric_end`.
- **Owner's rule (quality report of 10/20):** fog is for depth, **never to hide a defect**. Start soft: mist at ~40% of reach. Near planes stay 100% sharp.

---

## 8. Recommended configuration (`kit.reset_scene` or the set's `build`)

```python
scene.eevee.taa_render_samples = 32          # already the pipeline's
scene.render.filter_size = 1.5               # default; 2.0 if there is fine shimmering
scene.eevee.use_raytracing = False           # matte low-poly: stable and cheap
scene.eevee.use_fast_gi = True               # cheap AO
scene.eevee.light_threshold = 0.01           # default; use light.use_custom_distance for event light
scene.render.use_motion_blur = False
scene.view_settings.view_transform = "AgX"   # or "Standard" if the owner approves (section 1)
scene.view_settings.look = "None"            # never "AgX - Punchy" (crushes the blue night)
sun.angle = math.radians(2)                  # nearly hard, stable shadow; no use_shadow_jitter
# effects: obj.visible_shadow = False; flat materials: "Specular IOR Level" = 0, Roughness = 1
```

---

## The 8 rules for the specialist

1. **Colored emission in AgX: strength ≤ 1** (largest channel of color x strength up to ~1). Strength 2 is already salmon (measured: #FF6A00 x2 → #EB9266). Glow comes from color; high strength only on what should turn white (core, sparks). Never the Punchy look.
2. **An effect part casts no shadow** (`visible_shadow = False`). Only the flash light does.
3. **An explosion is layered faceted mesh, not volume:** anticipation → flash (rise of 3 to 5 frames) → fireball with `ease_out` and a "temperature" material that cools until it becomes smoke → ring + debris + sparks → residue. Facet edges cooler (*Layer Weight Facing*) so it does not become a flat disc.
4. **Dust and smoke: matte and opaque; vanishes by shrinking and fading to the sky color.** No overlapping translucent Blended: the layers stack (18 layers at 0.075 still cover 75%) and it looks like glass. If you need alpha: Dithered with binary alpha + backface culling.
5. **Smoke at night lighter than the sky** (or lit by the fire), otherwise it vanishes.
6. **Effect animation in dense LINEAR keys** computed in Python. Light changes only at the cut or in a ramp; nothing random per frame.
7. **Nothing too thin and nothing coplanar:** ≥ 2 px on the final screen, faces apart ≥ 1 cm, walls with thickness. No effect may reach the camera (reach ≤ ~60% of the distance).
8. **Prove it on a rendered frame and with `flicker.py`.** A sheet of 4 frames (anticipation, peak, expansion, residue) + an audited half-resolution preview. The tests in this research only came out good on the 3rd round, always because of defects seen in the render.

---

## Sources

Blender 5.2 manual (.rst source at projects.blender.org/blender/blender-manual, main branch):

- Sampling and Shadows: https://docs.blender.org/manual/en/latest/render/eevee/render_settings/sampling.html
- Raytracing: https://docs.blender.org/manual/en/latest/render/eevee/render_settings/raytracing.html
- Volumes: https://docs.blender.org/manual/en/latest/render/eevee/render_settings/volumes.html
- Motion Blur: https://docs.blender.org/manual/en/latest/render/eevee/render_settings/motion_blur.html
- Film: https://docs.blender.org/manual/en/latest/render/eevee/render_settings/film.html
- Material Settings (Dithered x Blended, Transparency Overlap, Alpha Clip Setup): https://docs.blender.org/manual/en/latest/render/eevee/material_settings.html
- Light Settings (Virtual Shadow Maps, jitter, filter, resolution limit): https://docs.blender.org/manual/en/latest/render/eevee/light_settings.html
- World Settings (mist, sun threshold): https://docs.blender.org/manual/en/latest/render/eevee/world_settings.html
- Light Probe Volume: https://docs.blender.org/manual/en/latest/render/eevee/light_probes/volume.html
- Limitations: https://docs.blender.org/manual/en/latest/render/eevee/limitations/limitations.html
- Object Data (ray visibility, shadow terminator): https://docs.blender.org/manual/en/latest/render/eevee/object_settings/object_data.html
- Displays and Views (AgX, Standard, Khronos, looks, exposure): https://docs.blender.org/manual/en/latest/render/color_management/displays_views.html

Release notes:

- 4.0 Color Management (AgX): https://developer.blender.org/docs/release_notes/4.0/color_management/
- 4.2 EEVEE Next: https://developer.blender.org/docs/release_notes/4.2/eevee/
- 4.2 migration (bloom, shadow mode, world volume): https://developer.blender.org/docs/release_notes/4.2/eevee_migration/
- 4.4 Compositor (revised Glare): https://developer.blender.org/docs/release_notes/4.4/compositor/
- 4.5 EEVEE (shadow terminator, Reverse-Z): https://developer.blender.org/docs/release_notes/4.5/eevee/
- 5.0 EEVEE: https://developer.blender.org/docs/release_notes/5.0/eevee/
- 5.0 Color Management (ACES 2.0, Convert to Display): https://developer.blender.org/docs/release_notes/5.0/color_management/
- 5.1 EEVEE (Raycast node, light path intensity): https://developer.blender.org/docs/release_notes/5.1/eevee/
- 5.2 EEVEE (screen-space raytracing, Fast GI, light threshold 0): https://developer.blender.org/docs/release_notes/5.2/eevee/
- Blender 5.2 OCIO config (AgX looks): `C:/Program Files/Blender Foundation/Blender 5.2/5.2/datafiles/colormanagement/config.ocio`

Community:

- AgX (Eary Chow): https://github.com/EaryChow/AgX
- Cartoon Explosions tutorial: https://blenderartists.org/t/cartoon-explosions-tutorial/1175640
- Strange coloring of blackbodies with AgX: https://blenderartists.org/t/strange-coloring-of-blackbodies-with-new-agx-color-management/1487373
- Why does only Filmic handle intense emissive colors well?: https://blenderartists.org/t/why-does-only-filmic-color-management-seem-to-handle-intense-emissive-colors-well/1573545
- Shockwave without volume (Bad Normals): https://3dart.it/shockwave-simulation-in-blender-tutorial
- Inverse hull (BNPR): https://bnpr.gitbook.io/bnpr/outline/inverse-hull-method
- EEVEE Next feedback (shadows in animation): https://devtalk.blender.org/t/blender-4-2-eevee-next-feedback/31813?page=52
- Soft shadows in Next (#116335): https://projects.blender.org/blender/blender/issues/116335

I found no specific material from Imphenzia, Polygon Runway, Grant Abbitt or Ryan King Art on explosion or color in Eevee. The searches only brought up course pages. The recommendations above come from the tests and the manual, not from them.
