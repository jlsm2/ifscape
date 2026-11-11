# Library of approved models (tools/blender/lib/)

Every model approved in a video goes in here so later videos can reuse it (parts and models; the assembled set stays new for each video, **unless reuse is necessary**).

Rules:
- One file per model (or family): `<name>.py` with a `build(...)` that returns the root, scale and color parameters, and the `SOURCE`/license at the top (CC0 from the source pack, or "procedural").
- Prefer the ready-made model (CC0) and only adjust color and scale to the style (flat low-poly). Ceiling of ~300 triangles and ~15 min per hand-made model.
- Before using, check the model in a small showcase (540x960 or a contact sheet), not at full resolution.
- Downloaded assets live in `assets/<source>/<pack>/` with a `SOURCE.txt` (URL, license, date). A new Quaternius pack may be under QAL v1.0: check the page.

Index (update when adding): see the list below.

| Model | File | Source / license | Video | Notes |
| --- | --- | --- | --- | --- |
| Dairy cow (rig, grazing) | `cow_quaternius.py` | Quaternius Farm Animals (Cow.fbx), CC0 | plants-extinct (06) | `build(name, loc, heading, length=2.3)`; `graze(rig, f0, f1)` = Idle + chewing low-neck layer; 796 tri (asset) |
| Child (6-8 years old) | `kid.py` | Quaternius Man (rigs.py), CC0 | plants-extinct (square) | `childlike(rig)`: bone scale (head 1.38, torso 0.9) on the copy; use with `rigs.spawn("man", height=1.2)` |
| First-person hands in the world | `fp_hands.py` | procedural (geometry from `cell_models.py`) | plants-extinct (04, 07) | `hand(name, side, sleeve=...)`, `place(obj, wrist, fingers, palm)`; the sleeve up to the shoulder (Stretch To) is in `plants_build_a._arm_sleeve` |
| (part A showcase) | `preview_a.py` | — | plants-extinct | `blender -b -P tools/blender/lib/preview_a.py -- cow|kid|hands <abs folder>` |
| Stone shed (open door, channel tile roof) | `stone_shed.py` | procedural | plants-extinct (07) | `build(name, x0, x1, y0, y1, mats, door=(ya, yb))`; mats stone/wood/roof/dark; ~300 tri |
| Burlap sack open/closed | `grain_sack.py` | procedural | plants-extinct (07) | `open_sack(...)` (mats sack, grain), `closed_sack(..., lying=)`; ~120 tri |
| Garden bed (damp soil with furrow, cracked soil, border, stake, seeds) | `garden_bed.py` | procedural | plants-extinct (07, 08) | `soil(...)`, `cracked_mat()` (distorted Voronoi), `border`, `stake`, `seeds`, `surface_z` |
| Mediterranean tower windmill with sails | `windmill_tower.py` | procedural | plants-extinct (05) | `build(name, base, mats, facing)`; `.sails` rotates on x; ~320 tri; readable at 250 m |
| Switchback trail on a hillside | `hill_trail.py` | procedural | plants-extinct (05) | `switchbacks(a, b)`, `build(name, curve, zf, ...)` (ribbon + dark border) |
| Dry plane-tree leaf + flight | `fx_leaves.py` | procedural | plants-extinct (05) | `leaf_geo(size)` 14 tri, `fly(obj, frames, path_fn, rnd)` |
| Gliding seagull | `gull.py` | procedural | plants-extinct (05) | `build(name, mats)`, `animate(g, frames, path_fn, flaps)`; M-shaped wing with wrist |
| Amber ruler band + outline (inverted hull) | `fx_highlight.py` | procedural | plants-extinct (06) | `band_mat/band/grow_band`, `outline_mat/outline(obj, mat, keys)` |
| Drifting dust, blob smoke and smoke wisp | `fx_drift.py` | procedural | plants-extinct (08, 09) | `dust(...)` with wrap; `smoke_loop` and `smoke_wisp` (NOT approved: the blob looks like a rock close to the camera) |
| Dense keys via the channelbag | `anim_curves.py` | procedural | — | `write`, `write_vec`, `visible_ranges`, `ease` |
| Magnifying lens attached to the camera (amber ring, seabed, diatoms, bubbles) | `fx_lens.py` | procedural | viruses-disappeared (02, 04, 05, 07) | `build(name, cam, center_px, diameter_px)`, `diatoms`, `bubbles`, `set_brightness`; pure emission (no scene light) |
| Blue wildebeest (rig, grazing/walking) | `wildebeest.py` | edited Quaternius cow, CC0 | viruses-disappeared (11, 12) | `build(name, loc, heading, length=2.5)`, `graze`, `head_up`; showcase `preview_models.py -- gnu` |
| Umbrella thorn acacia, old and young | `acacia.py` | procedural | viruses-disappeared (11, 12) | `old(...)`, `young(...)`; child crown (`<name>Crown`) for the wind |
| Spongy moth caterpillar (wave crawl, 8 shape keys) | `caterpillar.py` | procedural | viruses-disappeared (08, 09) | `phase_meshes`, `crawl_keys(meshes, f0, f1)`, `instance`, `frame_matrix`, `key_path`; 52 mm, ~600 tri; showcase `preview_models.py -- caterpillar` |
| Red oak: lobed leaf in a grid, furrowed bark, trunk with roots, gnarled limb | `oak.py` | procedural | viruses-disappeared (08, 09) | `leaf_geo`, `leaf_matrix`, `leaf_mat` (translucent), `bark_mat`, `trunk_geo`, `limb_geo`; chewed leaf = Weld + Solidify + Boolean EXACT (without Weld the leaf vanishes) |
