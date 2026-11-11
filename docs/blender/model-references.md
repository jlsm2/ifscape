# Low-poly model references (2026-10-21, bacteria-disappeared script)

Research done on the owner's request ("put more effort into Blender, models that make more sense"). Meters, Z up, object facing +X, origin on the ground.

## Cow (Holstein, ~700-900 tris; density reference: https://sketchfab.com/3d-models/cow-430ba6ec463649bd903f3aced3f0ad09, 823 tris)

- Withers 1.40-1.46 m; body (shoulder to pin bone) 1.6-1.7 m; muzzle to tail base ~2.4 m.
- Barrel at ~55% of the height (0.80 m): legs only ~45%; belly at ~0.62 m from the ground; width ~0.6 m.
- Head ~0.5 m, hanging forward and down (face at 45-60 degrees); poll at withers height or below.
- What makes it read as a cow: long, straight back with a high, square rump (hip bones form a "coat hanger"); low wedge-shaped head with a wide, light muzzle and ears out to the sides; zigzag hock on the hind legs, udder, big black patches (3-4 blocks, never little dots).
- Barrel in 6 hexagonal sections along X:

  | x | half-width | top z | bottom z |
  |---|---|---|---|
  | +0.80 | 0.24 | 1.40 | 0.85 |
  | +0.45 | 0.30 | 1.42 | 0.66 |
  | 0.00 | 0.33 | 1.42 | 0.62 |
  | −0.45 | 0.30 | 1.43 | 0.72 |
  | −0.80 | 0.25 | 1.46 | 0.98 |
  | −0.90 | 0.17 | 1.42 | 1.08 |

- Neck (0.80; 0; 1.22) → (1.10; 0; 1.08), r 0.22→0.15, with dewlap. Head from the poll (1.12; 0; 1.18) to the muzzle (1.50; 0; 0.82), 0.26→0.20 wide. Muzzle `#B98C88`. Ears 0.22×0.10×0.03 out to the sides. Short horns optional.
- Front legs straight at x +0.60; hind legs at x −0.62 with knee (−0.52; 0.85), hock (−0.74; 0.48), fetlock (−0.68; 0.10). Hooves `#2A2622`. Tail down to the hock with a tuft.
- Colors: white `#E9E4DA`, patches `#1E1F24`.
- Thin cow (shape key of the same section generator): half-width ×0.8, belly rises 0.10, deep flank; hip bones jutting 0.06-0.08 above the back; tail base sinks (hip-pin line from U to V, body score ≤3); spine ridge; 5 ribs per side in `#BDB5A8`.
- Sources: https://www.holsteinusa.com/pdf/print_material/linear_traits.pdf ; https://www.ontario.ca/page/body-condition-scoring-dairy-cattle ; https://extension.psu.edu/learn-to-score-body-condition

## Farm

- Gambrel barn 11 × 14.6 m: wall up to 3.4 m; lower slope ~60 degrees, break at z 5.8; upper slope ~27 degrees, ridge ~7.9 m; roof `#2A2F3A` with 0.3 m eaves. Walls `#A3352B`, trim `#EDE6D6`. Door 3.6×4.2 m with white frame and X; hayloft door 1.8×2.1 m at z 5.0 with X; ridge hood 1 m out with beam and pulley (strong cue); cupola.
- House 8×10 m, two stories (eaves 6 m), 40 degree roof `#3A3F4A`, boards `#D9D2C3`; full front porch, 2.4 m deep, floor at 0.5 m, posts every 2.4 m, 2.7 m high; windows 0.9×1.5 lit in amber; chimney `#6E3B2E`.
- Fence: posts 0.12 m, 1.2 m high, every 2.4-3 m; 3 rails at z 1.05 / 0.65 / 0.25; `#8C7A64`.
- Square bale 0.36×0.46×0.91; round bale 1.5 × 1.5 m lying down, `#D8B25A` with ring `#B48A3A`. Trough 3×0.6×0.5 `#7E8A99`. Corn in rows 0.76 m apart, plants 2.2 m tall, `#4E7A3A` → `#B89A5A`. Manure pit: 3 concrete walls 4×4×1.5 `#8D8A82`, pile `#4A3326`.
- Silo 6 × 18 m, 16 sides, dome; concrete `#BFB6A6` or blue `#2F4B7C`. Windmill: 10 m lattice tower, 2.4 m wheel with 18 blades and a tail vane.

## Landscape

- Hills: ~40×40 plane displaced by noise (3-8 m), decimated, flat-shaded; `#5E7F45` by day.
- Tree: trunk r 0.18→0.11, 2.5 m; canopy with 2-3 icospheres (r 1.3-2.0) with vertices jittered ±12%. Autumn: `#4F7D3B` → `#D9A93A` → `#C7652B`, then the canopy shrinks and reveals Y-shaped branches hidden inside; falling leaves; timings offset per tree. Conifers `#24453A` in the middle make the bare ones look bare.
- Distant ocean low `water_grid` `#1C3557`, amber strip under the sun, sharp horizon.

## Fertilizer plant (distant silhouette)

Ammonia spheres 17-18 m on legs; prilling tower ~61 m; stack ~50 m; flare ~70 m with amber flame; pipe racks 6×8 m; everything `#1A2335`, occasional amber lights, steam plumes `#6F7F99`.

## Cell and mitochondrion (Kurzgesagt style: round shapes, saturated color, no outline, depth of field)

Bean 3.0 × 1.2 m curved 15-20 degrees; outer membrane with thickness; inner one 0.1 smaller; 7-9 alternating cristae covering ~70% of the width; cutaway at the top (40%) with the cut face in its own color. Colors: membrane `#E0703A`, cristae `#F7C46A`, matrix `#7A2E2A`, cytoplasm `#13284A`, ribosomes `#2F5E8C`, nucleus `#2B3F7A`, ATP as little amber dots `#F5A524`.

Colors, cow head height, corn spacing and plant heights have no source: they come from the agent and the palette.
