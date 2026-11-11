"""Set for the viruses-disappeared script ("What if all viruses disappeared?").

Run by 'py -m ifscape blender scripts/viruses-disappeared.json [--stills ...]'.
CURRENT STAGE (2026-10-24): 6, camera and keyframes over the hero set. Camera of the 11 scenes tied to the
words (kit.W), cuts from direction.md section 6 (fade through dark of ~7 frames in 04->05, 09->11 and 11->12; darkens
1.5 s until the question at the end), animated lenses in scenes 02, 04, 05 and 07 (viruses_lenses.py), gust in the grass
(11), wildebeest that raises its head (11), herd that walks in (12) and snort in the final pause (12). The oak of
08-09, the child, the dog and the caterpillars are still MARKERS (final model in stage 8).
When building, writes blender/keyframes.json (one frame per voice trigger and per cut) for the contact sheet.

Files: viruses_set.py (waterfront, sky, sun, oak marker), viruses_savanna.py (savanna 11/12),
viruses_cast.py (people, sneeze, wildebeest, herd), viruses_lenses.py (lenses), lib/fx_lens.py, lib/wildebeest.py,
lib/acacia.py.
Light phases (switch only on the cut, CONSTANT key): NOW 01-04 (Sun 120 deg/55 deg), 1 DAY 05-09 (145 deg/62 deg), savanna 11-12
(Sun to the north, behind-right, 55 deg, energy 3.6; sky horizon #CFD3CC).
POV camera at 1.65 m, 24 mm lens (36 mm sensor at the height: 1280 px per radian, ~22.3 px per degree).
"""

import json
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import kit  # noqa: E402
import anim_curves as ac  # noqa: E402
import kid  # noqa: E402
import rigs  # noqa: E402
import viruses_cast as vc  # noqa: E402
import viruses_lenses as vl  # noqa: E402
import viruses_oak as vo  # noqa: E402
import viruses_savanna as sv  # noqa: E402
import viruses_set as vs  # noqa: E402

EYE = 1.65
LENS = 24.0


def objs_of(root):
    return [root, *root.children_recursive]


def show_frames(roots, ranges, total):
    """Turns the object (and children) on only within the intervals [(a, b)] (inclusive); CONSTANT key on the on/off."""
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for root in roots:
        for o in objs_of(root):
            for f in marks:
                o.hide_render = not any(a <= f <= b for a, b in ranges)
                o.keyframe_insert("hide_render", frame=f)


def look_post(scene, enabled=True):
    """Daytime recipe from art.md section 1: bloom threshold 1.0 strength 0.15; vignette 14%."""
    ng = scene.compositing_node_group
    for nd in ng.nodes:
        if nd.bl_idname == "CompositorNodeGlare":
            nd.inputs["Strength"].default_value = 0.15
        if nd.bl_idname == "ShaderNodeMix" and nd.blend_type == "MULTIPLY":
            nd.inputs[0].default_value = 0.14
    scene.render.use_compositing = enabled


# ---------- frames (text format: seconds within the scene, no voice; 2026-10-25) ----------

class Frames:
    """Triggers per second within the scene (the script became text: no voice.json). Sentence timings in
    ifscape/timing.py (1 s + 0.3 s per word); scene 02 is the EVENT (viruses vanish) and matches the script's counter."""

    def __init__(self, tl):
        self.tl = tl
        self.total = tl.frames
        self.first = {sid: tl.at(sid) for sid in tl.scenes}
        self.last = {sid: tl.at(sid, 1.0) - 1 for sid in tl.scenes}
        T = lambda sid, sec: self.first[sid] + int(round(sec * tl.fps))  # noqa: E731
        self.T = T
        self.H1 = self.first["01"]
        self.F11 = self.first["11"]
        self.F12 = self.first["12"]
        self.ORLA = (1, self.last["09"])
        self.NOW = (1, self.last["04"])
        self.DAY = (self.first["05"], self.last["09"])
        self.S11 = (self.first["11"], self.last["11"])
        self.S12 = (self.first["12"], self.total)
        # 02: event. The lens opens at +0.4 s, the viruses vanish at +1.6 s (counter COLDS 3 -> 0 at the same instant), closes at +4.2 s
        self.every, self.vanish, self.stay = T("02", 0.4), T("02", 1.6), T("02", 4.2)
        # 03: handkerchief in the pocket at +0.3 s; the 2nd passerby holds back the sneeze at +1.4 s
        self.so = T("03", 0.0)
        self.nobody, self.colds = self.so + 10, self.so + 43
        # 04: lens opens at +0.2 s; the 3 burst at +3.7 s (line 2); amber spreads at +4.8 s
        self.viruses4, self.third, self.spilled = T("04", 0.2), T("04", 3.7), T("04", 4.8)
        # 05: the lens closes at +2.0 s and the cove appears the same
        self.cove = T("05", 2.0)
        # 06: pan to the right at +0.1 s, stops on the family at +2.3 s
        self.but, self.collapse = T("06", 0.1), T("06", 2.3)
        # 07: lens A (today) opens on the cut; B (model without viruses) opens at +0.5 s and falls at +2.0 s; A never stops
        self.one_says, self.sea7 = T("07", 0.0), T("07", 0.0)
        self.stops = self.total + 200           # no lens A "stopping": 'photosynthesis stops' has no source (2026-10-25)
        self.one_model, self.drops = T("07", 0.5), T("07", 2.0)
        self.H2 = self.drops + 12
        self.hill = T("08", 0.0)
        self.without, self.boom = T("09", 0.0), T("09", 2.6)
        # 11: gust at +1.5 s; the nearest wildebeest raises its head at +3.6 s
        self.cleared, self.wildebeest = T("11", 1.5), T("11", 3.6)
        # 12: herd walks in at +0.9 s; camera tilts to the ground at +2.2 s; young acacias at +3.5 s (H3 +4.6 s);
        # darkens 1.5 s until the end card (the question opens at +6.5 s)
        self.herds, self.fires, self.young = T("12", 0.9), T("12", 2.2), T("12", 3.5)
        self.H3 = T("12", 4.6)
        self.snort = T("12", 5.3)
        self.question = T("12", 6.5)
        self.dark0 = self.question - 33        # darkens in 1.1 s until the end card


# ---------- light per phase ----------

def build_light(fr, world, sun):
    """Sun and sky per phase, switching only on the cut frame (CONSTANT)."""
    sav_q = sv.SUN_DIR.to_track_quat("Z", "Y")
    keys = [(1, vs.sun_vector(*vs.SUN_NOW).to_track_quat("Z", "Y"), 3.4, 0.0),
            (fr.DAY[0], vs.sun_vector(*vs.SUN_DAY).to_track_quat("Z", "Y"), 3.4, 0.0),
            (fr.S11[0], sav_q, 3.6, 1.0)]
    for f, q, e, place in keys:
        sun.rotation_quaternion = q
        sun.keyframe_insert("rotation_quaternion", frame=f)
        sun.data.energy = e
        sun.data.keyframe_insert("energy", frame=f)
        world.place.default_value = place
        world.place.keyframe_insert("default_value", frame=f)
    for idb in (sun, sun.data, world.world.node_tree):
        for fc in ac.bag(idb).fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


# ---------- camera ----------

C0 = (0.0, 0.0, EYE)               # 01-03: on the low wall, in front of the shop
C3 = (1.2, 0.3, EYE)               # 03: after sliding to the right
C4 = (-0.3, 6.6, EYE)              # 04-07: on the pier step (H2)
C7 = (-0.3, 4.6, EYE)              # 07: on the low wall, 2 m before the step, looking at the water
C8 = (2.6, 19.25, EYE)             # 08: south corner of the pier, behind the shop (oak at ~3.2 m, hill behind)
C9 = (1.85, 20.66, 2.0)            # 09: 0.8 m from the branch tip, from the side (background: sea and the other bank)
CS = (sv.ORIGIN.x, sv.ORIGIN.y, EYE)


def shots(fr):
    """Shots: (first frame, last, keys). Key = (frame, position, heading deg, tilt deg, curve into it).
    Heading + = right (toward +x); tilt + = up. Between shots, a cut (key jump)."""
    f = fr.first
    l = fr.last
    return [
        # 01-03: continuous shot. 01-02 stopped (cover and lens); 03 slides to the right on *So*
        (1, l["03"], [(1, C0, -8.0, -11.0, "io"), (fr.so, C0, -8.0, -11.0, "io"),
                      (fr.so + 66, C3, 2.0, -10.0, "io")]),
        # 04: matched cut (left pan finishing, ease-out) to the step; buoy at ~8.7 m (below the
        # lens, to the right of the panel); at -36 the frame looked at the deck axis
        (f["04"], l["04"], [(f["04"], C4, -48.0, -10.0, "io"), (f["04"] + 26, C4, -62.0, -12.0, "out")]),
        # 05: same framing (time jump through the dark)
        (f["05"], l["05"], [(f["05"], C4, -62.0, -12.0, "io")]),
        # 06: on *But* pans to the right to the sidewalk (child, dog) and stops on the family at *collapse*
        (f["06"], l["06"], [(f["06"], C4, -62.0, -12.0, "io"), (fr.but, C4, -62.0, -12.0, "io"),
                            (fr.collapse + 4, C4, 67.0, -6.0, "io")]),
        # 07: matched cut tilting to the water (already moving), stops at H2; 2 m before the step, heading -70
        # (from the step the deck filled the frame: the shot asks for the water)
        (f["07"], l["07"], [(f["07"], C7, -70.0, -14.0, "io"), (f["07"] + 28, C7, -70.0, -26.0, "out")]),
        # 08: rises and pans to the right to the oak (trunk ~3.2 m, right of the panel), hill behind
        (f["08"], l["08"], [(f["08"], C8, -48.0, -20.0, "io"), (fr.hill + 52, C8, -23.0, -6.0, "out")]),
        # 09: branch detail (one step closer), almost still: pushes in 6 cm
        (f["09"], l["09"], [(f["09"], C9, 61.0, 4.0, "io"),
                            (l["09"], (C9[0] + 0.05, C9[1] + 0.03, C9[2]), 61.0, 4.0, "lin")]),
        # 11: savanna, almost still (drifts 2.5 deg to the right)
        (f["11"], l["11"], [(f["11"], CS, 0.0, -10.6, "io"), (l["11"], CS, 2.5, -10.6, "lin")]),
        # 12: opens on the SAME framing as the 1st frame of 11; tilts -8 deg on *fires*; drifts right to the
        # young acacias on *young trees* and stops (H3)
        (f["12"], fr.total, [(f["12"], CS, 0.0, -10.6, "io"), (fr.fires, CS, 0.0, -10.6, "io"),
                             (fr.fires + 27, CS, 0.0, -18.6, "io"), (fr.young, CS, 0.0, -18.6, "io"),
                             (fr.H3 - 6, CS, 15.0, -9.5, "io")]),
    ]


def sample_camera(fr):
    out = {}
    for a, b, keys in shots(fr):
        for f in range(a, b + 1):
            if f <= keys[0][0]:
                k = keys[0]
                out[f] = (k[1], k[2], k[3])
                continue
            if f >= keys[-1][0]:
                k = keys[-1]
                out[f] = (k[1], k[2], k[3])
                continue
            i = max(j for j in range(len(keys)) if keys[j][0] <= f)
            k0, k1 = keys[i], keys[i + 1]
            u = (f - k0[0]) / (k1[0] - k0[0])
            kind = k1[4]
            e = u if kind == "lin" else ac.ease(u, kind)
            pos = tuple(k0[1][c] + (k1[1][c] - k0[1][c]) * e for c in range(3))
            out[f] = (pos, k0[2] + (k1[2] - k0[2]) * e, k0[3] + (k1[3] - k0[3]) * e)
    return out


def build_camera(fr):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.lens = LENS
    cam.data.sensor_fit = "AUTO"
    cam.data.sensor_width = 36.0
    cam.data.clip_start, cam.data.clip_end = 0.05, 12000.0
    cam.rotation_mode = "XYZ"
    table = sample_camera(fr)
    frames = sorted(table)
    for i in range(3):
        ac.write(cam, "location", i, frames, [table[f][0][i] for f in frames])
    ac.write(cam, "rotation_euler", 0, frames, [math.radians(90 + table[f][2]) for f in frames])
    ac.write(cam, "rotation_euler", 1, frames, [0.0] * len(frames))
    ac.write(cam, "rotation_euler", 2, frames, [math.radians(-table[f][1]) for f in frames])
    return cam


def build_fade(fr, cam):
    """Pass through the dark: black plane in front of the camera (0.1 m, in front of the lenses), opacity by key.
    Cuts 04->05, 09->11, 11->12: rises in 3 frames, 2 black frames (the cut one is the 1st of the new scene), falls in
    3 (~7 frames in the dark). End: darkens in 1.5 s until the question and stays black."""
    mat = bpy.data.materials.new("FadeBlack")
    if not mat.node_tree:
        mat.use_nodes = True
    n, L = mat.node_tree.nodes, mat.node_tree.links
    for nd in list(n):
        if nd.type != "OUTPUT_MATERIAL":
            n.remove(nd)
    out = next(nd for nd in n if nd.type == "OUTPUT_MATERIAL")
    tr, em = n.new("ShaderNodeBsdfTransparent"), n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = n.new("ShaderNodeMixShader")
    mix.name = "Fade"
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    o = kit.mesh_object("FadePlane", [(-0.1, -0.15, 0), (0.1, -0.15, 0), (0.1, 0.15, 0), (-0.1, 0.15, 0)],
                        [(0, 1, 2, 3)], [mat], (0, 0, -0.1))
    o.parent = cam
    o.visible_shadow = False
    keys = {1: 0.0}
    for c in (fr.first["05"], fr.first["11"], fr.first["12"]):
        keys.update({c - 4: 0.0, c - 1: 1.0, c: 1.0, c + 3: 0.0})
    n_dark = fr.question - fr.dark0
    for k in range(n_dark + 1):
        keys[fr.dark0 + k] = ac.ease(k / n_dark)
    keys[fr.total] = 1.0
    frames = sorted(keys)
    ac.write(mat.node_tree, 'nodes["Fade"].inputs[0].default_value', 0, frames, [keys[f] for f in frames])
    ranges = [(c - 4, c + 3) for c in (fr.first["05"], fr.first["11"], fr.first["12"])] + [(fr.dark0, fr.total)]
    ac.visible_ranges([o], ranges, fr.total)
    return o


# ---------- orla ----------

PEOPLE = [  # (key, clothes, height, x, y, z, heading degrees (0 = +x/west), action); in front of the shop and on the pier
    ("woman", 1, 1.66, 1.75, 7.0, 0.0, 95, "idle"),                # on the right edge, looking at the shop window
    ("man", 2, 1.80, 5.6, 6.4, 0.0, 12, "walk"),
    ("woman", 5, 1.62, 6.6, 9.7, 0.0, -100, "idle"),               # family (06): mother
    ("man", 3, 1.74, 7.3, 9.5, 0.0, 165, "idle"),                  # family (06): father
    ("man", 4, 1.76, 11.0, 7.8, 0.0, 190, "walk"),
    ("man", 6, 1.76, -15.5, 32.6, -1.0, 250, "idle"),             # on the deck of the red boat (leaves on 1 DAY)
    ("man", 0, 1.74, -34.6, 61.0, -1.0, 95, "idle"),               # no barco branco
]


WALK_LOOPS = {1: (2.6, 0.6, 1.8), 4: (2.0, 0.45, 3.6)}      # index in PEOPLE: (half line, radius, start)
LOOP_SHIFT = {4: (0.0, -0.3, 0.0)}                            # far from the pole (14; 8.6)
DOCK_WALK = {3: 2.4, 4: 4.4}                                  # deck: meters until stopping (before the next one standing)


def dock_people(dock):
    """People on the deck only on the outer half (u >= 13 m): the inner half falls in the panel strip in H1
    (review of the heroes, 2026-10-24)."""
    out = []
    for k, (u, s, key, cl, h, hd_off, act) in enumerate(((13.0, 0.4, "man", 4, 1.78, 90, "idle"),
                                                          (13.7, -0.3, "woman", 0, 1.64, 70, "idle"),
                                                          (15.4, -0.6, "woman", 3, 1.6, -80, "idle"),
                                                          (17.0, -0.2, "woman", 2, 1.62, 180, "walk"),
                                                          (18.4, 0.5, "man", 5, 1.8, 180, "walk"),
                                                          (19.6, 0.6, "man", 1, 1.76, 0, "idle"),
                                                          (21.0, -0.5, "woman", 6, 1.58, -90, "idle"))):
        p = dock.origin + dock.d * u + dock.side * s
        hd = math.atan2(dock.d.y, dock.d.x) + math.radians(hd_off)
        out.append((key, cl, h, p.x, p.y, dock.z, math.degrees(hd), act))
    return out


def marker(name, size, loc, color, rot=0.0):
    """Marker for stage 6 (box at the right size and place; the final model is for stage 8)."""
    o = kit.mesh_object(name, *kit._box_geo(size[0], size[1], size[2], -size[0] / 2, -size[1] / 2, 0.0),
                        [rigs.flat_mat(color)], loc)
    o.rotation_euler = (0, 0, rot)
    return o


def ice_cream(r):
    """Cone (#C89A5A) with scoop (#F0C8C8), attached to the child's right hand bone."""
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    palm = r.arm.pose.bones["Palm.R"]
    hand = r.arm.matrix_world @ palm.tail
    v1, f1 = kit._prism_geo(8, 0.004, 0.028, 0.09)
    v2, f2 = kit._ico_geo(0.033, (0, 0, 0.11))
    v, f, own = kit.merge((v1, f1), (v2, f2))
    o = kit.mesh_object("IceCream", v, f, [rigs.flat_mat("#C89A5A"), rigs.flat_mat("#F0C8C8")], face_mats=own)
    for p in o.data.polygons:
        p.use_smooth = False
    o.parent, o.parent_type, o.parent_bone = r.arm, "BONE", "Palm.R"
    bpy.context.view_layer.update()
    o.matrix_world = Matrix.Translation(hand + Vector((0, 0, 0.02)))
    return o


def build_people(fr, orla):
    rnd = random.Random(11)
    rigs_out = []
    total = fr.total
    dock_n = len(PEOPLE)
    for k, (key, cl, h, x, y, z, hd, act) in enumerate(PEOPLE + dock_people(orla.dock)):
        r = vc.person(key, f"P{k}", cl, h, (x, y, z), math.radians(hd))
        if act == "walk" and k < dock_n:
            # sidewalk: loops along a track (2 straights + half-turns) at 1.25 m/s, without crossing anyone
            a = math.radians(hd)
            ax, bx = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
            half, rad, d0 = WALK_LOOPS[k]
            c = Vector((x, y, 0)) + bx * rad + ax * (half - d0) + Vector(LOOP_SHIFT.get(k, (0, 0, 0)))
            vc.walk_loop(r, list(range(1, fr.ORLA[1] + 2)), c, ax, half, rad, 1.25, z=z, d0=d0, phase=rnd.random())
        elif act == "walk":
            # deck: walks until near the next standing one and stays (Idle)
            vc.walk_then_idle(r, (x, y), math.radians(hd), 1.25, DOCK_WALK.get(k - dock_n, 2.0), fr.ORLA[1], z=z,
                              phase=rnd.random())
        else:
            rigs.loop(r, "Idle", 1, fr.ORLA[1], rate=0.7, phase=rnd.random())
        rigs_out.append(r)
    # the sneeze: in right profile (x 600-900 in H1), in front of the shop's shaded door (NOW only); after the
    # peak the body returns, the hand lowers with the handkerchief and on *nobody* the handkerchief goes to the pocket
    sn = vc.sneezer("Sneezer", (-0.19, 4.2, 0.0), math.radians(3.0), fr.H1, fr.ORLA[1], k=0, side="R",
                    f_nobody=fr.nobody)
    drops = vc.droplet_cone("Droplets", sn.nose, sn.fwd, random.Random(7), f0=fr.H1)
    show_frames([drops], [(1, fr.last["01"])], total)
    # 2nd passerby of 03: rubs the nose since *So* and, on *colds*, holds back the sneeze (head back) and relaxes
    p2 = vc.person("man", "Passerby", 3, 1.74, (1.9, 4.9, 0.0), math.radians(-115))
    rigs.loop(p2, "Idle", 1, fr.NOW[1], rate=0.8)
    vc.rub_and_hold(p2, "Passerby", "L", fr.so - 4, fr.colds, fr.NOW[1])
    # the family of 06 gets the child; child with ice cream and dog pass on the sidewalk on 1 DAY (markers)
    fam_kid = kid.childlike(vc.person("man", "FamilyKid", 5, 1.15, (6.95, 9.05, 0.0), math.radians(-60)))
    rigs.loop(fam_kid, "Idle", 1, fr.ORLA[1], rate=0.9)
    ice_kid = kid.childlike(vc.person("man", "IceKid", 1, 1.12, (1.5, 9.5, 0.0), math.radians(-150)))
    rigs.loop(ice_kid, "Idle", 1, fr.ORLA[1], rate=0.9)
    cone = ice_cream(ice_kid)
    # dog: Quaternius fox (CC0) repainted as a caramel dog, standing in Idle next to the child
    dog = rigs.spawn("fox", "Dog", length=0.75, location=(2.25, 9.15, 0.0), heading=math.radians(-150))
    rigs.paint(dog, {"Main": "#A87A4A", "Main_Light": "#E8DCC4", "Grey": "#5A4634"})
    rigs.loop(dog, "Idle", 1, fr.ORLA[1], rate=0.8)
    dog = dog.root
    show_frames([r.root for r in rigs_out[1:]] + [fam_kid.root], [fr.ORLA], total)
    # the woman at the shop window (right edge of H1) only on NOW: on 1 DAY she entered huge in front of the 06 family
    show_frames([sn.rig.root, p2.root, rigs_out[0].root], [fr.NOW], total)
    show_frames([ice_kid.root, cone, dog], [fr.DAY], total)
    return SimpleNamespace(people=rigs_out, sneezer=sn, drops=drops, passerby=p2, family=rigs_out[2:4] + [fam_kid],
                           ice_kid=ice_kid, dog=dog)


def build_oak(fr):
    """Final oak (08-09): tree, leaves, walking caterpillars and the leaf eaten in 4 bites starting from *boom*."""
    ns = SimpleNamespace(f08=fr.first["08"], without=fr.without, boom=fr.boom, end09=fr.last["09"])
    return vo.build((C9, 61.0, 4.0), C8[:2], ns, vs.OAK, sun=vs.sun_vector(*vs.SUN_DAY))


# ---------- savana ----------

def build_savanna(fr):
    rnd = random.Random(5)
    S = sv.build(rnd, gust=(fr.cleared - 2, 9.0, 7.0, 0.45, 4.5))
    g11 = vc.rigged_gnus(vc.GNUS_11, "Gnu11_", fr.S11[0], fr.S11[1], random.Random(31),
                         fns={0: (vc.head_up_fn(fr.wildebeest), None)})
    g12 = vc.rigged_gnus(vc.GNUS_12, "Gnu12_", fr.S12[0], fr.S12[1], random.Random(32),
                         fns={1: vc.snort_fns(fr.snort)})
    snaps = vc.snapshots()
    still, walkers, herd = vc.herd_12(random.Random(33), snaps, fr.S12[0], fr.herds, fr.total)
    show_frames([S.t11, *S.grass.tall, *S.burns, *[g.root for g in g11]], [fr.S11], fr.total)
    show_frames([S.t12, *S.grass.short, *[t for t, _ in S.acacias.young], *[g.root for g in g12], *still],
                [fr.S12], fr.total)
    show_frames([*[t for t, _ in S.acacias.old], *S.acacias.far, S.kopje, S.hills, *S.clouds],
                [(fr.S11[0], fr.total)], fr.total)
    return SimpleNamespace(S=S, g11=g11, g12=g12, still=still, walkers=walkers, herd=herd)


def place_collection(name):
    """Collection of one place (waterfront or savanna), active while the place is being built. The two places occupy the SAME space
    near the origin (the savanna at 60 km streaked the sun shadows: float precision in the shadow map, 2026-10-24) and
    only one shows at a time, by the on/off on cut 09->11."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[name]
    return col


def _has_visibility_keys(o):
    ad = o.animation_data
    return bool(ad and ad.action and any(fc.data_path == "hide_render" for fc in ac.bag(o).fcurves))


def key_place(col, rng, total):
    """On/off per place for every object in the collection that does not yet have its own key (the own keys are
    already subsets of the place). Hidden molds (assets, scatter models) are left out."""
    for o in list(col.all_objects):
        if o is None or o.hide_render or _has_visibility_keys(o):
            continue
        show_frames_one(o, [rng], total)


def show_frames_one(o, ranges, total):
    marks = sorted({1, total} | {a for a, _ in ranges} | {b + 1 for _, b in ranges})
    for f in marks:
        o.hide_render = not any(a <= f <= b for a, b in ranges)
        o.keyframe_insert("hide_render", frame=f)


# ---------- checks and contact sheet ----------

def in_view(scene, cam, p, f):
    scene.frame_set(f)
    co = world_to_camera_view(scene, cam, Vector(p))
    return co.z > 0 and -0.02 < co.x < 1.02 and -0.02 < co.y < 1.02


def checks(fr, scene, cam, ppl, orla, sav):
    rf = kit.require_in_frame
    rf("sneeze face (H1)", scene, cam, ppl.sneezer.nose, fr.H1)
    head = lambda r, h=1.6: r.root.matrix_world.translation + Vector((0, 0, h))  # noqa: E731
    rf("2nd passerby on *colds*", scene, cam, head(ppl.passerby), fr.colds)
    for k, r in enumerate(ppl.family):
        rf(f"family {k} on *collapse*", scene, cam, head(r, 1.2), fr.collapse + 6)
    rf("burlap band of the oak (08)", scene, cam, vs.OAK + Vector((0.3, -0.35, 1.35)), fr.hill + 52)
    rf("branch tip (09)", scene, cam, orla.oak.tip, fr.without)
    rf("eaten leaf (09)", scene, cam, orla.oak.hero.matrix_world @ Vector((0.13, 0.0, 0.0)), fr.boom + 24)
    rf("edge caterpillar (09)", scene, cam, orla.oak.eater.matrix_world.translation, fr.boom)
    rf("wildebeest raising its head (11)", scene, cam, head(sav.g11[0], 1.2), fr.wildebeest)
    rf("wildebeest that snorts (12)", scene, cam, head(sav.g12[1], 1.2), fr.snort)
    for k, (t, _) in enumerate(sav.S.acacias.young[:3]):
        rf(f"young acacia {k} (H3)", scene, cam, t.matrix_world.translation + Vector((0, 0, 1.6)), fr.H3)
    # the herd is not born inside the frame: on the 1st frame of 12 no walking line is in view
    scene.frame_set(fr.F12)
    for r in sav.walkers:
        if in_view(scene, cam, r.matrix_world.translation + Vector((0, 0, 0.7)), fr.F12):
            kit.problem(f"walking wildebeest {r.name} is already in frame on the 1st frame of 12")
    # count of wildebeest in view (for NOTES.md)
    counts = {}
    for label, f in (("11", fr.F11 + 30), ("12 start", fr.F12), ("12 fires", fr.fires), ("H3", fr.H3)):
        if label == "11":
            pts = [g.root.matrix_world.translation for g in sav.g11]
        else:
            pts = [g.root.matrix_world.translation for g in sav.g12] + [o.matrix_world.translation for o in sav.still]
            scene.frame_set(f)
            pts += [r.matrix_world.translation.copy() for r in sav.walkers]
        counts[label] = sum(1 for p in pts if in_view(scene, cam, p + Vector((0, 0, 0.7)), f))
    print("WILDEBEEST IN VIEW:", counts)
    lc = bpy.context.view_layer.layer_collection.children["Orla"]
    lc.exclude = True                      # the ground ray of the savanna must not hit the pier (same space)
    for g in sav.g12[:3] + sav.g11[:3]:
        kit.require_grounded(f"gnu {g.name}", g.meshes[0])
    lc.exclude = False


def write_keyframes(fr):
    """One frame per voice trigger and per cut (~0.5 s after the trigger, when the action is already visible)."""
    h = lambda f: f + 15  # noqa: E731
    k = {
        "01": [(fr.H1, "H1 cover"), (fr.T("01", 4.0), "question")],
        "02": [(fr.every + 9, "Every: lens"), (fr.vanish + 10, "vanishes"), (fr.stay + 4, "stay: closes")],
        "03": [(fr.nobody, "nobody"), (fr.colds + 6, "colds")],
        "04": [(fr.first["04"] + 2, "cut"), (fr.viruses4 + 20, "Viruses: phages"), (fr.third + 18, "third"),
               (fr.spilled + 30, "spilled"), (fr.last["04"] - 2, "fade")],
        "05": [(fr.first["05"], "black"), (fr.first["05"] + 4, "1 DAY"), (fr.cove + 4, "cove: closes")],
        "06": [(h(fr.but) + 20, "But: pan"), (fr.but + 40, "turn: child"), (fr.collapse + 8, "collapse")],
        "07": [(fr.first["07"] + 3, "cut"), (fr.sea7 + 12, "A alive"), (fr.stops + 14, "stops"),
               (fr.one_model + 12, "One model"), (fr.H2, "H2 drops")],
        "08": [(fr.first["08"] + 3, "cut"), (fr.hill + 55, "On the hill")],
        "09": [(fr.without + 6, "Without"), (fr.boom + 26, "boom lasts")],
        "11": [(fr.last["09"] - 2, "fade waterfront"), (fr.first["11"] + 3, "In our world"), (fr.cleared + 25, "cleared"),
               (fr.wildebeest + 20, "wildebeest")],
        "12": [(fr.first["12"] - 3, "fade 11"), (fr.first["12"] + 3, "1970s"), (fr.herds + 30, "herds"), (fr.fires + 30, "fires"), (fr.H3, "H3"),
               (fr.snort + 6, "snort"), (fr.dark0 + 25, "darken")],
    }
    path = Path(sys.argv[sys.argv.index("--timeline") + 1]).resolve().parent / "keyframes.json"
    path.write_text(json.dumps({sid: [[int(f), lbl] for f, lbl in rows] for sid, rows in k.items()}, indent=1),
                    encoding="utf-8")


def build(tl):
    fr = Frames(tl)
    scene = bpy.context.scene
    look_post(scene)
    world = vs.build_world()
    sun = vs.build_sun()
    build_light(fr, world, sun)
    cam = build_camera(fr)
    build_fade(fr, cam)
    vl.lens_02(cam, fr.every, fr.vanish, fr.stay, fr.total)
    vl.lens_04(cam, fr.viruses4, fr.third, fr.spilled, fr.total, fr.last["04"])
    vl.lens_05(cam, fr.first["05"], fr.cove, fr.total)
    vl.lenses_07(cam, fr.sea7, fr.stops, fr.one_model, fr.drops, fr.last["07"], fr.total)
    rnd = random.Random(42)
    orla_col = place_collection("Orla")
    M = vs.make_mats()
    orla = vs.build_orla(M, rnd)
    vs.clouds(M["cloud"], random.Random(8))
    show_frames([orla.boats.red], [fr.NOW], fr.total)
    ppl = build_people(fr, orla)
    orla.oak = build_oak(fr)
    sav_col = place_collection("Savana")
    sav = build_savanna(fr)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
    key_place(orla_col, fr.ORLA, fr.total)
    key_place(sav_col, (fr.S11[0], fr.total), fr.total)
    checks(fr, scene, cam, ppl, orla, sav)
    write_keyframes(fr)
    scene.frame_set(1)


kit.run(build)
