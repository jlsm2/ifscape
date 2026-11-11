# Ifscape art bible (v2, 2026-10-23)

Maintained by the `art-director`. Applies to every video on the channel. Only what the owner approved or what is a fixed identity rule goes in here; what is still a proposal stays marked **[proposal]** until the owner approves the hero frame. Basis of this version: Mode 0 of moon-disappeared (`build/moon-disappeared/art.md`), with a measured render test.

## 0. Identity that does not change
Low-poly, simple shapes, flat matte colors, dark blue night with amber `#F5A524`, POV camera at ~1.6 m (only space uses a slow orbit), **Standard** view transform (AgX killed the amber), no sky time-lapse, no fog or darkness to hide defects, panel and caption inside the safe zones (panel x 72-972 y 860-1120; caption y ~1250-1330; @ y 1440-1480; buttons x > 930; question y 470-690). Improve the finish, do not change the style.

## 1. Light
1. **Every light has a source you can see or understand** (Moon, Sun, lamp, boat, window). Light without a source = finding.
2. **The key leads, the fill only supports.** In moon-disappeared the world ambient beat the key (moonlight 0.8 against ambient 2.2) and everything went flat. Night: the Moon (or the lamp, without a Moon) is the key; the world is a weak blue fill. [measured proposal: ambient x0.65, key x1.25]
3. **Sky reflected in water comes from the sky itself**, not from the ambient: the world shows the sky gradient for camera rays **and reflection rays** (`Light Path > Is Camera Ray` MAX `Is Glossy Ray`). That way the water darkens up close and brightens at the horizon (Fresnel) with no new texture.
4. **Glitter on water = broken column** of horizontal pieces with dark gaps, narrower near the source and wide at the horizon, twinkling slowly (4D noise with linear phase). Never a flat smudge, never a straight edge, never a regular staircase of equal bars, never blown-out pure white over a large area (max ~#E8EEFF in the core).
5. **A glowing celestial body has a halo** (Moon, Sun, lamp): disc + additive halo + light compositor bloom. A white ball with no halo = finding.
6. **Light changes only by a smooth curve or in the dark of a cut** (owner's rule: no flashing sky).
7. **A reflection is never brighter than its source:** the core of the moonlight path stays <= #E8EEFF, below the Moon's disc (~#F1F0E9); 255 only on the disc.
8. **Globe in space:** the night side is a fixed floor added to the whole disc (max(diffuse, floor)); the terminator is never darker than the night side (otherwise it becomes a dark band in the middle). Atmosphere masked by the Sun's direction (strong in the day, weak at night); an identical rim on both sides = glass ball.
9. **Glow from a source outside the frame** has to reach a high value at the edge (warm bright core, fast falloff); warm color at 18% over navy turns into a brown smudge.
10. **Same logic across scenes:** the same lamp has the same color (1.0/0.65/0.28) and the same halo in every scene; it only changes strength with a reason (dawn = 0.35).

## 2. Color and value
- The subject is the brightest OR most saturated point of the frame; at night the water is never brighter than the horizon sky (except the glitter).
- Amber `#F5A524` only where it carries meaning: human light (lamp, boat), ruler/diagram (axis, arc, tide mark). Not as a 1 px line on the horizon (reads as interface).
- Night: sky zenith ~#070C1B -> horizon ~#1A2845; sea #0E1830 to #22345C; wood #2C2420 (outside the lamp) to #A06A3A (in the amber pool).
- Pink dawn: horizon #E9A490, middle #9A7896, top #4A4C75; water ~#4A4262 with a pink reflection at the horizon.
- Snow white is never flat #FFFFFF: #E6ECF4 in light, #8FA0BE in shadow, #F5D8A8 under the lamp.

## 3. Materials
| Material | Rule |
| --- | --- |
| Wood | roughness 0.9; grain by stretched noise (already exists) + **per-plank variation** of +-8% in value; edge planks more worn (lighter); never uniform plastic |
| Water | Principled, dark base, roughness 0.15-0.3, reflects the sky (rule 1.3); low-poly facets visible only in the glitter; no regular stripes. Crests: noise STRETCHED horizontally (1:4) and broken by a 2nd mask, troughs darker than the base; never an isotropic noise ridge (turns into marble veins). Object in the water: submerged part darker and irregular foam at the waterline, never a white slab. The same water has the same look across shots of the same instant |
| Snow | matte (roughness 1, specular 0.2), base #E6ECF4, edge with volume (bevelled layer), blue shadow; no plastic shine |
| Sea ice | plates of varied sizes (3 scales), irregular edges with 5 to 9 sides, 2 tones + snow on top; dark water #0E1830 between the plates (pink reflection only near the horizon; wine color in the foreground = finding) |
| Feathers (owl) | 2-3 tones in bands, chest with spots, not a gray rectangle; eyes with a weak emissive amber iris (0.1-0.25) |
| Mouse fur | gray-brown field mouse #8E8073, belly #B9AE9F; white = lab mouse (finding) |
| Hull | dirty white #D9D6CC, blue stripe, no pure white; amber lights |
| Earth (globe) | ocean in 2 tones (#1F4E8C deep, #2E6DB4 shelf), green/ochre continents with a clean edge, white polar ice, atmosphere in a soft gradient (Fresnel), never a hard ring |

## 4. Shapes
- Coherent scale: exaggeration only when marked and equal across characters in the same frame (owl 2x, mouse 2.3x).
- Nothing smaller than ~4 px on the final screen in detail that shows in a full frame (nails, stars, wires); otherwise it flickers.
- Repetition that does not look like a comb: icicles, stakes, plates and waves with variation in size and spacing (+-30%).
- Stars: 3 sizes (3, 4, 6 px) and 3 brightnesses, round point with a soft edge, not an identical little square; Milky Way with a dark dust lane in the middle.

## 5. Render (Eevee 5.2) [adopted in the final render of moon-disappeared, 0.59 s/frame]
- Standard, 32 samples, shadow pool 1024, horizon scan (fast GI) on (already the default).
- World fill x0.65 of what it is today; key x1.25; Sun/Moon light specular 0.45 (no blown shards in the water).
- Sky in the reflections: `Is Camera Ray` MAX `Is Glossy Ray` on the world factor, **always with `world.use_sun_shadow = False`** (without it: 4.2 s/frame and a blown shadow buffer).
- Compositor: Glare **Bloom** (threshold 1.0, smoothness 0.3, strength 0.25, size 0.5) + vignette (ellipse 1.15 x 1.0, 300 px blur, 22% at the corners). Threshold 0.85 / strength 0.35 blows out the water glitter.
- Translucents: Eevee sorts by object ORIGIN; the darkening plane and the instrument layer get their origin behind the camera so they stay on top.
- Do not use: screen-space raytracing (+12%, no gain), shadow jitter (+42%, no gain), motion blur, outline, volume fog.

## 5b. Text over the scene
- Caption (y ~1250-1330) and final call never over the brightest area of the frame (moonlight, blown-out lamp, bright midday sky). If the scene requires it, a soft dark gradient behind the text (the same device as the cover title) and light that does not blow out (#FFFFCC) in that strip.

## 6. Anti-patterns (already caught; do not repeat)
- Lamp light as a flat smudge with a straight edge on the water.
- Sun or Moon as a white ball with no halo.
- Waves as regular stripes (wave distorted into bands).
- Globe with a cyan interface ring.
- A 3 px object that flickers (nails).
- Boat made of boxes; tiny ruler-plank.
- Hard cut between different lights (use dark 4+4).
- **New (10/23):** visible seam between the near sea and the far sea (thin horizontal line in the sea); ambient stronger than the key (everything flat); water brighter than the sky at night; moonlight path blown out to white with triangular shards with straight edges; stars as identical square confetti; identical hexagonal ice plates; icicles like a comb; 1 px amber line on the horizon; white lab mouse.
- **New (10/23, final render):** water as a lilac floor with veins (isotropic noise ridge); ghost wave as a frosted-glass box with a dashed crest; dark band at the globe's terminator; atmosphere rim equal on both sides; Sun glow outside the frame in brown; ice gaps wine-colored; navy-blue snow railing; snow slab with no volume; thin amber line that should say movement (Moon moving away = hair strand); Sun trajectory arcs in an "M" with the V above the horizon; reflection brighter than the source.

## 7. Hero frames
moon-disappeared, final render V2 r2:
- **q1, pier at night (the channel's reference for night with a Moon):** Moon with halo and counter on the same line, sea darker than the sky, broken amber column and silver path as the only two lights on the water, lit railing. Composition grade 5. Pending: #FFF core of the path.
- **q1100, Earth in space (reference for a diagram in space):** background #05070F, round stars, 250 px Earth with legible continents, 8 px amber axis as the most saturated thing, degree label. HIGH pending items: dark band at the terminator, uniform rim, brown Sun glow.
- **q1930, winter with a lamp (reference for snow):** Milky Way with dust, varied plates, random icicles, lamp as the key. Pending: railing blown out in the caption strip, wine gaps, 1 px line on the horizon.

## 8. What the viral videos do better and what we do better
- They: density of life (people, kites, seagulls, cars), generous bloom and halo on the Sun, thin and numerous stars with a textured Milky Way, soft shadow and contact occlusion, aerial perspective (subtle distance gradient, not fog that hides things).
- Us: one clear physical ruler per scene (stake, axis, arc), coherent brand palette, stable POV, subject legibility and an honest diagram.
