"""Test (c): low-poly dust cloud that does NOT look like a glass bubble. Three versions side by side, same cloud:

  A "glass" (the mistake): Blended with alpha 0.45, specular shine, smooth surface -> reflection + transparency = glass.
    And the fade fails: 9 overlapping blobs = ~18 Blended layers; at 0.075 per layer it still covers ~75%.
  B "matte opaque": matte faceted icospheres (roughness 1, specular 0, no transparency); it vanishes by SHRINKING,
    blob by blob (the outer ones first), rising and lightening toward the sky color.
  C "matte dissolving": same as B, but it vanishes by erosion: Dithered + BINARY alpha (noise > animated threshold),
    the edge breaks apart into faceted pieces (without the dithering grain, without transparency sorting).
None of them casts a shadow (visible_shadow = False): dust with shadow darkens the ground in hard patches.

    blender -b -P tools/blender/examples/fx_dust.py -- <folder> [AgX|Standard]
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import fx_common as fx  # noqa: E402
import kit  # noqa: E402
from kit import lin  # noqa: E402

LIFE = range(1, 61)                    # 2 s of life
SHOTS = (8, 30, 50)
DUST = "#9C8670"
FADE_TO = "#3A4660"                    # sky/ambient color the dust fades toward (vanishes into the air, does not go black)


def cluster(name, mat, center, rnd, smooth=False):
    """9 icospheres of varied sizes, flattened at the bottom, larger in the middle."""
    out = []
    for k in range(9):
        off = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.6), rnd.uniform(0, 1.2))) * (0 if k == 0 else 1)
        r = (1.0 if k == 0 else rnd.uniform(0.45, 0.8)) * (1.15 - 0.25 * off.length)
        v, f = fx.ico(1 if not smooth else 3, 1.0)
        o = fx.flat_obj(f"{name}{k}", fx.lumpy(v, seed=k * 3 + len(name), amount=0.2, squash=0.6), f, mat,
                        tuple(Vector(center) + off + Vector((0, 0, r * 0.6))))
        if smooth:
            for p in o.data.polygons:
                p.use_smooth = True
        o.scale = (r, r, r)
        o.visible_shadow = False
        out.append((o, off, r))
    return out


def glass(center, rnd):
    mat = kit.flat("DustGlass", DUST, rough=0.3)
    mat.surface_render_method = "BLENDED"
    alpha = kit.principled(mat).inputs["Alpha"]
    fx.curve_keys(alpha, "default_value", LIFE, lambda f: 0.45 * (1 - f / 60))
    fx.set_interp(mat.node_tree)
    cluster("Glass", mat, center, rnd, smooth=True)


def matte_material(name):
    mat = kit.flat(name, DUST, rough=1.0)
    p = kit.principled(mat)
    p.inputs["Specular IOR Level"].default_value = 0.0          # no reflection: the reflection is what makes "glass"
    fade = p.inputs["Base Color"]
    fx.curve_keys(fade, "default_value", LIFE,
                  lambda f: tuple(a + (b - a) * fx.ease_in_out(f / 60) for a, b in zip(lin(DUST), lin(FADE_TO))))
    fx.set_interp(mat.node_tree)
    return mat


def shrink_away(parts, center):
    """Each blob vanishes by shrinking; the outer ones (far from the center) first. All rise and spread out a little."""
    for o, off, r in parts:
        delay = 1 - min(off.length / 1.6, 1)                     # 0 = outer, 1 = from the center

        def scl(f, r=r, delay=delay):
            grow = fx.ease_out(f / 10)
            gone = fx.ease_in_out((f - 12 - 18 * delay) / 22)
            s = r * grow * (1 + 0.4 * f / 60) * (1 - gone)
            return (s, s, s * 0.9)

        def pos(f, off=off, r=r):
            return tuple(Vector(center) + off * (1 + 0.5 * f / 60) + Vector((0, 0, r * 0.6 + 0.9 * f / 60)))

        fx.curve_keys(o, "scale", LIFE, scl)
        fx.curve_keys(o, "location", LIFE, pos)
        fx.set_interp(o)


def matte(center, rnd):
    shrink_away(cluster("Matte", matte_material("DustMatte"), center, rnd), center)


def eroding(center, rnd):
    """Dithered + alpha 0/1: the noise (in object coordinates, so it sticks to the blob) above a rising threshold."""
    mat = matte_material("DustErode")
    mat.surface_render_method = "DITHERED"
    mat.use_backface_culling = True                              # through the holes you see the background, not the dark back face
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 0.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"     # binary alpha: clean edge
    nt.links.new(nz.outputs["Fac"], gt.inputs[0])
    nt.links.new(gt.outputs[0], kit.principled(mat).inputs["Alpha"])
    fx.curve_keys(gt.inputs[1], "default_value", LIFE, lambda f: 0.25 + 0.55 * fx.ease_in_out((f - 12) / 45))
    fx.set_interp(nt)
    parts = cluster("Erode", mat, center, rnd)
    for o, off, r in parts:                                     # grows, rises; what vanishes is the alpha
        fx.curve_keys(o, "scale", LIFE, lambda f, r=r: (r * fx.ease_out(f / 10) * (1 + 0.4 * f / 60),) * 3)
        fx.curve_keys(o, "location", LIFE,
                      lambda f, off=off, r=r: tuple(Vector(center) + off * (1 + 0.5 * f / 60)
                                                    + Vector((0, 0, r * 0.6 + 0.9 * f / 60))))
        fx.set_interp(o)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out, transform = Path(args[0]), (args[1] if len(args) > 1 else "AgX")
    scene = fx.night_scene(res=(1080, 1920), samples=32, cam_loc=(0, -12, 1.65), target=(0, 0, 1.4), lens=22)
    fx.props(scene, random.Random(8), n=10, spread=9, y0=5)
    warm = bpy.data.lights.new("Warm", "POINT")                  # amber light from a lamp post/fire nearby
    warm.energy, warm.color, warm.shadow_soft_size = 1500.0, (1.0, 0.72, 0.42), 0.5
    lamp = bpy.data.objects.new("Warm", warm)
    lamp.location = (-4.0, -2.0, 3.5)
    scene.collection.objects.link(lamp)
    for build, x, seed in ((glass, -3.3, 1), (matte, 0.0, 1), (eroding, 3.3, 1)):
        build((x, 0, 0), random.Random(seed))                  # same seed: the same cloud in all three
    fx.view(scene, transform)
    for f in SHOTS:
        scene.frame_set(f)
        fx.render(scene, out / f"dust_{transform}_f{f:03d}.png")


main()
