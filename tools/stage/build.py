"""Builds the whole scene from the 'stage' field of each script scene (no new code per video).

stage per scene (meters; x right, y depth, z up):
  set      stage (presets.SETS) ........ "meadow" | "savanna" | "forest" | "desert" | "vacuo" | "same"
           ("same" = continues the previous scene's stage, sky and light; the scene's pieces are new)
  light    light (presets.LIGHTS) ...... "noon" | "dawn" | "dusk" | "night" | "overcast" | "dry-noon"
  props    list of pieces:
             id | kind(+pack,tag)   a catalog model (id may be a list; kind draws one)
             name                   name for the camera and cues to look at
             at [x,y] | layout      single (default) | scatter | herd | line | ring | grid
             n, area [cx,cy,r], spread, to [x,y], gap, rows, cols
             h (m) | len (m)        height (people, plant, building) or length (animal)
             face  degrees | "name" direction; default: facing the camera
             action "Idle"|"Walk"|"Run"|...   (animal and person)
             to [x,y] | path [[x,y],...] + speed (m/s)   walks (the camera follows)
             z (m)                  initial height above the ground (bird in the air; the move cue brings it down with [x,y,z])
  camera   {preset, at [x,y], look name|[x,y,z], dist, arc, lens, z, sway}   (cameras.py)
           preset "path": path [{t|frac, at [x,y], z, look, lens} | {t, prev: true}] goes through all the points, smooth;
           'prev' starts where the previous scene's camera ended (continuous shot)
  cues     [{word, nth, off | t | frac, do: pop|vanish|move|action|shake|light|grow|meteor|still|water|dust|react, target, to, dur,
             action, amp, light (name), from, size, stagger, keep, color}]
             still: what floats (boat) stops rocking in 'dur' s; water: the water color ('ocean' stage) goes to 'color'
             in 'dur' s; action drink|cast|bite: synthesized fishing gesture (the piece needs 'rod', m of rod)
             grow on a plated piece (ice): 'keep' m around the pivot already done at the cut, the rest opens from near
             to far in 'stagger' s; what floats in there locks
             meteor: fireball with a tail crosses the sky from 'from' to 'to' ([x,y,z] in m, ~500 m away) in 'dur' s and vanishes at the end
             (end below the horizon, z ~ 12 m, so it disappears behind the hills);
             'size' = head radius (m, default 20)
             light: the light goes slowly to 'light' in 'dur' s; grow: scale from 'from' (0.05) to 'size' (1) in 'dur' s,
             each target starts up to 'stagger' s later (growing forest)
Written for lean mode, phase 2.
"""

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import rigs  # noqa: E402
from lib import anim_curves as ac  # noqa: E402

import cameras  # noqa: E402
import models  # noqa: E402
import presets  # noqa: E402
import procedural  # noqa: E402
import riverside  # noqa: E402

FPS_STRIDE = {"person": 1.5}     # stride (m per walk cycle); animal: 0.9 x length
WALK_SPEED = {"person": 1.4}     # m/s; animal: 0.35 x length per second
STEP = 3


# ---------- positions ----------

def layout_positions(spec: dict, rng: random.Random, keepout: list) -> list[tuple[float, float]]:
    n = int(spec.get("n", 1))
    at = spec.get("at", [0.0, 0.0])
    layout = spec.get("layout", "single" if n == 1 else "scatter")
    if layout == "single":
        return [(at[0], at[1])]
    if layout == "line":
        to = spec["to"] if "to" in spec and spec.get("layout") == "line" else [at[0] + 2 * n, at[1]]
        return [(at[0] + (to[0] - at[0]) * k / max(n - 1, 1), at[1] + (to[1] - at[1]) * k / max(n - 1, 1))
                for k in range(n)]
    if layout == "ring":
        r = spec.get("spread", 4.0)
        return [(at[0] + r * math.cos(math.tau * k / n), at[1] + r * math.sin(math.tau * k / n)) for k in range(n)]
    if layout == "grid":
        cols = int(spec.get("cols", math.ceil(math.sqrt(n)))); gap = spec.get("gap", 3.0)
        return [(at[0] + (k % cols) * gap, at[1] + (k // cols) * gap) for k in range(n)]
    # scatter and herd: dart-throwing attempts with a minimum distance, outside the forbidden zones
    area = spec.get("area", [at[0], at[1], spec.get("spread", 10.0)])
    gap = spec.get("gap", max(0.6, 0.55 * area[2] / math.sqrt(n)) if layout == "scatter" else 1.6)
    pts = []
    for _ in range(n):
        for _try in range(40):
            a, r = rng.uniform(0, math.tau), area[2] * math.sqrt(rng.random())
            p = (area[0] + r * math.cos(a), area[1] + r * math.sin(a))
            if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= gap for q in pts) and \
                    all(math.hypot(p[0] - kx, p[1] - ky) > kr for kx, ky, kr in keepout):
                break
        pts.append(p)
    return pts


# ---------- pieces ----------

class Prop:
    def __init__(self, name, obj, height, positions, rig=None):
        self.name, self.obj, self.height, self.rig = name, obj, height, rig
        self.ident, self.spec, self.parts = None, {}, None
        self.positions = positions                 # [(frame, Vector)] sorted; constant if there is only one

    def pos(self, frame) -> Vector:
        pts = self.positions
        if len(pts) == 1 or frame <= pts[0][0]:
            return pts[0][1].copy()
        if frame >= pts[-1][0]:
            return pts[-1][1].copy()
        for (f0, p0), (f1, p1) in zip(pts, pts[1:]):
            if f0 <= frame <= f1:
                return p0.lerp(p1, (frame - f0) / max(f1 - f0, 1))
        return pts[-1][1].copy()


def _heading(spec, p, cam_at, targets: dict, rng) -> float:
    face = spec.get("face", "camera")
    if face == "random":
        return rng.uniform(0, math.tau)
    if face == "camera":
        return models.facing(p, cam_at)
    if isinstance(face, str) and face in targets:
        q = targets[face].pos(1)
        return models.facing(p, (q.x, q.y))
    return math.radians(float(face))


def place_props(sid, stage, coll, start, end, rng, fps, keepout, ctx=None):
    """Creates the scene's pieces. With 'span' the piece goes to its own collection and lives from one scene to another (ctx brings the
    frames of the group and of the script). Returns (scene pieces, [(name, piece, (start, end), collection)] of the 'span' ones)."""
    cam_at = stage["camera"]["at"]
    props: dict[str, Prop] = {}
    spans = []
    live = (ctx or {}).get("live", {})
    for spec in stage.get("props", []):
        base0 = spec.get("name") or spec.get("id") or spec.get("kind")
        if int(spec.get("n", 1)) == 1 and base0 in live:
            # the piece already lives here (span from a previous scene): in the same place and not walking, it is only a citation; if it changes place,
            # walks or changes action, the old one leaves at the cut and this one enters
            old, rng_ = live[base0]
            if not spec.get("span") and spec.get("id") == old.ident and list(spec.get("at", [])) == list(old.spec.get("at", []))                     and "path" not in spec and "to" not in spec and spec.get("action", old.spec.get("action")) == old.spec.get("action") \
                    and spec.get("rod", old.spec.get("rod")) == old.spec.get("rod"):
                continue
            rng_[1] = start - 1
        pcoll, pstart, pend = coll, start, end
        if spec.get("span"):
            sp = spec["span"]
            if sp == "group":
                pstart, pend = ctx["group"]
            else:
                pstart, pend = ctx["tl"].scenes[sp[0]][0], ctx["tl"].scenes[sp[1]][1] - 1
            pcoll = bpy.data.collections.new(f"P{sid}_{spec.get('name') or spec.get('id') or spec.get('kind')}")
            bpy.context.scene.collection.children.link(pcoll)
        n = int(spec.get("n", 1))
        positions = layout_positions(spec, rng, keepout)
        for k, (x, y) in enumerate(positions):
            ident = models.resolve(spec, rng)
            item = models.CATALOG[ident]
            base = spec.get("name") or ident
            name = base if n == 1 else f"{base}{k}"
            z = presets.ground_height(x, y) + float(spec.get("z", 0.0))     # z: height above the ground (bird in the air)
            heading = _heading(spec, (x, y), cam_at, props, rng)
            rigged = models.is_rigged(ident)
            h = spec.get("h"); h = rng.uniform(*h) if isinstance(h, list) else h
            ln = spec.get("len"); ln = rng.uniform(*ln) if isinstance(ln, list) else ln
            if procedural.has(ident):
                if "face" not in spec and ident in procedural.DEFAULT_FACE:
                    heading = math.radians(procedural.DEFAULT_FACE[ident])
                res = procedural.SPAWN[ident](name, pcoll, spec, x, y, heading, pstart, pend, fps,
                                              random.Random(f"{sid}{name}"))
                prop = Prop(name, res.obj, res.height, getattr(res, "positions", None) or [(pstart, Vector((x, y, z)))])
                prop.parts = getattr(res, "parts", None)
            elif rigged:
                rig = models.rig_spawn(ident, name, pcoll, length=ln, height=h)
                rig.root.location = (x, y, z)
                rig.root.rotation_euler = (0, 0, heading + math.pi / 2)
                size = rig.t.box.size.z * rig.scale
                prop = Prop(name, rig.root, size, [(pstart, Vector((x, y, z)))], rig)
                _animate_rig(prop, rig, ident, spec, (x, y), heading, k, n, pstart, pend, fps, rng)
                if spec.get("rod") in procedural.REST_MODES:     # gave up: rod leaning/lying, no line
                    procedural.rest_kit(prop, spec, pcoll, pstart, pend, fps,
                                        sitting=str(spec.get("action", "")).lower() in HOLD_END, cam_at=cam_at)
                elif spec.get("rod"):
                    procedural.fisher_kit(prop, spec, pcoll, pstart, pend, fps,
                                          sitting=str(spec.get("action", "")).lower() in HOLD_END, cam_at=cam_at)
                if spec.get("carry") == "crumb" and ident == "ant":   # small ant with a crumb in its mouth
                    procedural.ant.carry_crumb(rig, pcoll, random.Random(f"{sid}{name}crumb"),
                                               float(spec.get("crumb", 1.0)))
                elif spec.get("carry"):                       # rod and empty bucket in hand (going home)
                    procedural.carry_kit(prop, pcoll, pstart + 1, bucket=spec["carry"] != "rod")
            else:
                obj = models.static_instance(ident, name, pcoll, height=h or item["height_m"])
                obj.location = (x, y, z - 0.02)
                obj.rotation_euler = (0, 0, heading)
                prop = Prop(name, obj, (h or item["height_m"]), [(pstart, Vector((x, y, z)))])
                holder = props.get(spec.get("carry")) if isinstance(spec.get("carry"), str) else None
                if holder is not None and holder.rig is not None:     # cup in the hand of whoever is seated
                    riverside.carry(prop, holder, pstart + 2)
            prop.ident, prop.spec = ident, spec
            prop.must_see = bool(spec.get("must_see"))
            props[name] = prop
            if pcoll is not coll:
                spans.append((name, prop, [pstart, pend], pcoll))
    return props, spans


def _animate_rig(prop, rig, ident, spec, p0, heading, k, n, start, end, fps, rng):
    kind = models.CATALOG[ident]["kind"]
    idle = models.pick_action(rig, "Idle")
    rigs.loop(rig, idle, start, end, phase=rng.random() if n > 1 else 0.0)
    wanted = spec.get("action")
    path = spec.get("path")
    if "to" in spec and spec.get("layout", "single") in ("single", "herd", "scatter") and not path:
        dx, dy = spec["to"][0] - spec.get("at", [0, 0])[0], spec["to"][1] - spec.get("at", [0, 0])[1]
        path = [[p0[0], p0[1]], [p0[0] + dx, p0[1] + dy]]
    elif path:
        ox, oy = p0[0] - path[0][0], p0[1] - path[0][1]
        path = [[a + ox, b + oy] for a, b in path]
    if path:
        gait = models.pick_action(rig, wanted or "Walk")
        feet = models.feet_of(rig)
        native = rigs.planted_speed(rig, gait, feet) * rig.scale * rigs.ASSET_FPS if feet else 0.0   # m/s of the planted foot
        if native > 1e-3:                      # matched step: the body walks at the planted foot's speed (no skating)
            want = spec.get("speed")
            rate = float(spec.get("rate", 1.0)) if want is None else float(want) / native
            rate = max(0.45, min(1.8, rate))
            speed = native * rate
            print(f"  step: {prop.name} planted foot {native:.2f} m/s, cadence {rate:.2f}x -> {speed:.2f} m/s")
        else:                                   # no leg in the skeleton: old heuristic
            length_m = rig.t.box.size.y * rig.scale
            speed = float(spec.get("speed", WALK_SPEED.get(kind, 0.35 * length_m)))
            stride = FPS_STRIDE.get(kind, 0.9 * length_m)
            act = rig.t.actions[gait]
            natural = (act.frame_range[1] - act.frame_range[0]) / rigs.ASSET_FPS      # seconds of the cycle at rate 1
            rate = natural / (stride / speed)
        if spec.get("loop") and len(path) >= 2:     # goes back and forth along the points until the end of the span (always-living piece)
            need, pts_, i, step = speed * (end - start) / fps, [path[0]], 0, 1
            while sum(math.dist(a, b) for a, b in zip(pts_, pts_[1:])) < need and len(pts_) < 400:
                i += step
                if i < 0 or i >= len(path):
                    step = -step
                    i += 2 * step
                pts_.append(path[i])
            path = pts_
        curve, total = rigs.smooth_path(path) if len(path) > 2 else rigs.smooth_path([path[0], [(path[0][0] + path[1][0]) / 2, (path[0][1] + path[1][1]) / 2], path[1]])
        total = max(total, 1e-3)
        t0 = int(start + float(spec.get("wait", 0)) * fps)
        t1 = min(end, t0 + int(total / speed * fps))
        frames = list(range(t0, t1 + 1, STEP))
        if frames[-1] != t1:
            frames.append(t1)
        pts, heads = [], []
        for f in frames:
            d = min(total, speed * (f - t0) / fps)      # at the planted foot's speed (a path that goes past the end of the scene does not speed up)
            pnt, hd = rigs.along(curve, total, d)
            pts.append((pnt.x, pnt.y, presets.ground_height(pnt.x, pnt.y)))
            heads.append(hd)
        rigs.key_root(rig, frames, pts, heads)
        st = rigs.loop(rig, gait, t0, t1, rate=rate, blend_in=4, blend_out=4, extend="NOTHING")
        a0_, a1_ = rig.t.actions[gait].frame_range
        if not spec.get("loop"):                 # the cycle ends when the body arrives (before, it walked in place for up to 1 extra cycle)
            st.repeat = max(0.05, (t1 + 2 - st.frame_start) / ((a1_ - a0_) * st.scale))
        prop.positions = [(start, Vector(pts[0]))] + [(f, Vector(p)) for f, p in zip(frames, pts)] + [(end, Vector(pts[-1]))]
    elif wanted and wanted.lower() in HOLD_END:
        hold_end(rig, models.pick_action(rig, wanted), start, end)
    elif wanted and wanted.lower() != "idle":
        key = models.pick_action(rig, wanted)
        if key in getattr(rig.t, "once", ()):          # ant: Rise/Tremble/Sag play once and hold the pose
            procedural.ant.play(rig, key, start)
        else:
            rigs.loop(rig, key, start, end, blend_in=4, extend="HOLD")


HOLD_END = ("sitting",)          # actions that end in a pose (sitting): the piece is already in it from the cut


def hold_end(rig, action_key, start, end):
    """Holds the end of the action (seated) for the whole scene: NLA strip that repeats only the last 2 frames."""
    act = rig.t.actions[action_key]
    a1 = act.frame_range[1]
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    st = track.strips.new(action_key, int(start), act)
    st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.action_frame_start, st.action_frame_end = a1 - 2, a1
    st.scale = 1.0
    st.repeat = max(1.0, (end - start) / 2.0 + 1.0)
    st.extrapolation = "HOLD"
    return st


# ---------- gatilhos ----------

def cue_frame(cue, sid, tl, start, end, fps, have_voice) -> int:
    if "word" in cue and have_voice:
        return kit.W(tl, sid, cue["word"], int(cue.get("nth", 0)), float(cue.get("off", 0.0)))
    if "t" in cue:
        return start + int(float(cue["t"]) * fps)
    frac = float(cue.get("frac", 0.5))
    if "word" in cue:
        print(f"  warning: no voice for '{cue['word']}' in scene {sid}; using {frac:.0%} of the scene")
    return start + int((end - start) * frac)


def targets_of(cue, props):
    key = cue.get("target")
    return [p for n, p in props.items() if n == key or (n.startswith(key) and n[len(key):].isdigit())]


def make_meteor(coll, sid, cue, f0, end, fps):
    """Asteroid in the background: incandescent rocky head and gas tail that fades at the tip, from 'from' to 'to'."""
    a, b = Vector(cue["from"]), Vector(cue["to"])
    d = (b - a).normalized()
    size = float(cue.get("size", 20.0))
    f1 = min(end, f0 + max(1, int(float(cue.get("dur", 3.4)) * fps)))
    rng = random.Random(f"{sid}meteor")
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=size)
    head = bpy.context.active_object
    head.name = f"meteor{sid}"
    for v in head.data.vertices:                       # rocha irregular
        v.co *= rng.uniform(0.78, 1.18)
    for p in head.data.polygons:
        p.use_smooth = False
    head.data.materials.append(kit.flat("meteor_head", "#FFB060", rough=1.0, emission="#FF9A40", strength=9.0))
    length = size * 13
    bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=size * 0.95, radius2=0.0, depth=length)
    tail = bpy.context.active_object
    tail.name = f"meteor{sid}_tail"
    tail.parent = head
    tail.rotation_mode = "QUATERNION"
    tail.rotation_quaternion = (-d).to_track_quat("Z", "Y")
    tail.location = -d * (length / 2 + size * 0.2)
    mat = bpy.data.materials.new("meteor_tail")
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rng_map = nt.nodes.new("ShaderNodeMapRange")           # z local: base (-L/2) = 1, ponta (+L/2) = 0
    rng_map.inputs["From Min"].default_value, rng_map.inputs["From Max"].default_value = -length / 2, length / 2
    rng_map.inputs["To Min"].default_value, rng_map.inputs["To Max"].default_value = 0.7, 0.0
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = kit.lin("#FF7A30")
    em.inputs["Strength"].default_value = 2.6
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    L = nt.links
    L.new(coord.outputs["Object"], sep.inputs[0])
    L.new(sep.outputs["Z"], rng_map.inputs["Value"])
    L.new(rng_map.outputs["Result"], mix.inputs["Fac"])
    L.new(clear.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    tail.data.materials.append(mat)
    for o in (head, tail):
        o.visible_shadow = False
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    for i in range(3):
        ac.write(head, "location", i, [f0, f1], [a[i], b[i]])
    head.location = a
    # vanishes at the end of the trajectory (behind the horizon or, if preferred, shrinking): without this the piece sits still in the air
    head.scale = (1, 1, 1)
    kit.key(head, "scale", (1, 1, 1), max(1, f1 - 8))
    kit.key(head, "scale", (0, 0, 0), f1 + 1)
    head.scale = (1, 1, 1)


DUST_COLOR, DUST_FADE = "#CDBB98", "#DDD3C0"     # dry light earth; fades to the afternoon haze tone
_dusts = []                                       # (coll, sid, prop, f, end, cue): made after the animated camera


def _dust_material(name, alpha_key):
    """Dust (round 3): matte, soft edge (alpha falls off at the silhouette: Layer Weight > Facing) and slightly
    translucent in the core; BLENDED, no specular, no shadow. alpha_key: [(frame, core alpha)] (fades out)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = kit.lin(DUST_COLOR)
    pr.inputs["Roughness"].default_value = 1.0
    pr.inputs["Specular IOR Level"].default_value = 0.0
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.55
    ramp = nt.nodes.new("ShaderNodeMapRange")                 # facing 0 (head-on) -> 1, edge (1) -> 0
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.25, 0.95
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 1.0, 0.0
    core = nt.nodes.new("ShaderNodeValue")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    L = nt.links
    L.new(lw.outputs["Facing"], ramp.inputs["Value"])
    L.new(ramp.outputs["Result"], mul.inputs[0])
    L.new(core.outputs[0], mul.inputs[1])
    L.new(mul.outputs[0], mix.inputs["Fac"])
    L.new(clear.outputs[0], mix.inputs[1])
    L.new(pr.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    core.outputs[0].default_value = alpha_key[0][1]
    ac.write(nt, core.outputs[0].path_from_id("default_value"), 0, [f for f, _ in alpha_key], [a for _, a in alpha_key])
    return mat, pr


def make_dust(coll, sid, prop, f0, end, fps, cue, cam):
    """Impact dust (ants-human-size; round 3: reads as dust, not rock): ~40 clouds of faceted
    mesh with a soft edge and a slightly translucent core (BLENDED, no shadow, no particles). They come out small and
    along the ground from the base of the piece, roll toward the camera up to 'reach' of the distance (default 0.55; max 0.6),
    rise and spread while rolling (the back ones rise more), and fade out becoming transparent until ~2.9 s.
    'size' scales the clouds (1 = proportional to the piece), 'n' changes the number."""
    rng = random.Random(f"{sid}{prop.name}dust")
    L = float(prop.spec.get("len") or prop.height or 1.0) * float(cue.get("size", 1.0))
    base = prop.pos(f0)
    bpy.context.scene.frame_set(f0)
    c = cam.matrix_world.translation
    to_cam = Vector((c.x - base.x, c.y - base.y, 0.0))
    D = max(to_cam.length, 0.5)
    fwd = to_cam.normalized()
    side = Vector((-fwd.y, fwd.x, 0.0))
    reach = min(0.6, float(cue.get("reach", 0.55)))
    life = int(2.9 * fps)
    frames = list(range(f0, min(end, f0 + life) + 1))
    akey = [(f, 0.9 * (1 - _smooth01(((f - f0) / fps - 1.0) / 1.8))) for f in frames[::2]]
    mat, pr = _dust_material(f"Dust{sid}{prop.name}", akey)
    a, b = kit.lin(DUST_COLOR), kit.lin(DUST_FADE)
    cols = [tuple(x + (y - x) * _smooth01((f - f0) / life) for x, y in zip(a, b)) for f in frames[::2]]
    for i in range(4):
        ac.write(mat.node_tree, pr.inputs["Base Color"].path_from_id("default_value"), i, frames[::2], [v[i] for v in cols])
    import bmesh
    meshes = []
    for v_ in range(3):                                   # 3 cloud shapes (shared meshes)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in bm.verts:                                   # nuvem irregular, achatada embaixo
            v.co *= rng.uniform(0.85, 1.12)
            if v.co.z < 0:
                v.co.z *= 0.5
        me = bpy.data.meshes.new(f"dust{sid}{prop.name}{v_}")
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
        me.materials.append(mat)
        meshes.append(me)
    n = int(cue.get("n", 40))
    travel = 0.0
    for k in range(n):
        lead = rng.random() ** 0.7                        # 1 = goes farther, in front
        lat = rng.uniform(-1, 1)
        start = base + side * (lat * 0.5 * L) + fwd * (rng.uniform(-0.1, 0.25) * L)
        travel = D * reach * (0.2 + 0.8 * lead)
        drift = side * (lat * rng.uniform(0.3, 0.8) * L)
        r = L * rng.uniform(0.05, 0.13) * (1.15 - 0.35 * lead)    # varied sizes; the front ones, near the lens, smaller
        delay = rng.uniform(0.0, 0.2) + 0.12 * (1 - lead)
        rise = L * rng.uniform(0.15, 0.4) * (1.3 - 0.6 * lead)   # the back ones rise more (a column that opens)
        t_gone0 = 1.0 + 0.6 * lead + rng.uniform(0, 0.25)
        o = bpy.data.objects.new(f"dust{sid}_{prop.name}{k}", meshes[k % 3])
        coll.objects.link(o)
        o.visible_shadow = False
        o.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        spin = rng.uniform(-0.6, 0.6)
        locs, scales, rots = [], [], []
        for f in frames:
            t = (f - f0) / fps - delay
            if t <= 0:
                locs.append(tuple(start)); scales.append((0.0, 0.0, 0.0)); rots.append(o.rotation_euler.z); continue
            go = 1 - (1 - min(1.0, t / 1.6)) ** 3        # rolls fast and brakes (ease-out)
            grow = 1 - (1 - min(1.0, t / 0.4)) ** 2
            gone = _smooth01((t - t_gone0) / 1.0)
            s = r * (0.12 + 0.88 * grow) * (1 + 1.3 * min(1.0, t / 2.2)) * (1 - 0.55 * gone)
            p = start + fwd * (travel * go) + drift * go
            p.z = presets.ground_height(p.x, p.y) + s * 0.45 + rise * (1 - (1 - min(1.0, t / 2.4)) ** 2)
            locs.append(tuple(p)); scales.append((s, s, s * 0.8)); rots.append(o.rotation_euler.z + spin * t)
        locs.append(locs[-1]); scales.append((0.0, 0.0, 0.0)); rots.append(rots[-1])
        fr = frames + [frames[-1] + 1]
        ac.write_vec(o, "location", fr, locs)
        ac.write_vec(o, "scale", fr, scales)
        ac.write(o, "rotation_euler", 2, fr, rots)
        o.scale = (0, 0, 0)
    print(f"  dust: {prop.name} f{f0}, {n} clouds, reach {travel:.1f} m of {D:.1f} m to the camera")


def _smooth01(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ---------- reaction of whoever is seated (react) ----------

_reacts = {}          # piece name -> (piece, [(frame, cue, function of the looked-at point or None)])
REACT_BONES = {        # share of the turn and the lean in each bone (head in front, torso delayed)
    "yaw": (("Head", 0.45, 0), ("Neck", 0.33, 2), ("Torso", 0.22, 5)),
    "pitch": (("Head", 0.6, 0), ("Neck", 0.4, 2)),
    "lean": (("Abdomen", 0.5, 2), ("Torso", 0.5, 0)),
}


def _ease_out_back(u, s=0.9):
    """Fast at the start, overshoots the target a little and settles (scare, quick head turn)."""
    u = max(0.0, min(1.0, u)) - 1.0
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def _react_cue(prop, cue, f, props):
    """Stores the cue; the looked-at point is a piece (with 'look_z' m above the foot; default half the height) or [x, y, z]."""
    look = cue.get("look", "keep")
    if look is None or look == "front":
        fn = None
    elif look == "keep":
        fn = "keep"
    elif isinstance(look, list):
        v = Vector(look) if len(look) == 3 else Vector((look[0], look[1], 1.2))
        fn = lambda fr, v=v: v
    else:
        tg = props.get(look)
        if tg is None:
            kit.problem(f"react on '{prop.name}': 'look' '{look}' does not exist in the scene")
            return
        z = float(cue.get("look_z", tg.height * 0.5))
        fn = lambda fr, tg=tg, z=z: tg.pos(fr) + Vector((0, 0, z))
    _reacts.setdefault(prop.name, (prop, []))[1].append((f, cue, fn))


def write_reacts(fps, last):
    """Additive layer (COMBINE) over the seated pose: head, neck and torso turn toward the looked-at point
    (the head leads, the torso comes 5 frames later), torso lean ('lean' degrees, negative = backward) that
    arrives in 'snap' s (fast, with a slight overshoot) and, with 'hold' s, returns to 0 in 'back' s (slow, smooth).
    While looking, the gaze wanders slowly (±2.5°) and the chest breathes; both vanish at the start and end of the video
    (the loop closing repeats f1)."""
    scene = bpy.context.scene
    for name, (prop, evs) in _reacts.items():
        rig = prop.rig
        if rig is None:
            kit.problem(f"react on '{name}', which has no skeleton")
            continue
        evs.sort(key=lambda e: e[0])
        scene.frame_set(evs[0][0])
        head = rig.arm.matrix_world @ rig.arm.pose.bones["Head"].head
        hd = rig.root.rotation_euler.z - math.pi / 2              # direction of the body (0 = +x)

        def aim(p):
            d = p - head
            yaw = (math.degrees(math.atan2(d.y, d.x) - hd) + 180) % 360 - 180
            pitch = math.degrees(math.atan2(-d.z, max(1e-3, math.hypot(d.x, d.y))))
            return max(-75.0, min(75.0, yaw)), max(-30.0, min(40.0, pitch))

        # segments per channel: (start, end, target(f) -> value, curve)
        look_seg, lean_seg = [], []
        for f, cue, fn in evs:
            if fn != "keep":
                turn = int(float(cue.get("turn", 0.45)) * fps)          # 0 = already looking (1st frame of the loop)
                tgt = (lambda fr: (0.0, 0.0)) if fn is None else (lambda fr, fn=fn: aim(fn(fr)))
                look_seg.append((f, f + turn, tgt, "back" if turn <= 0.6 * fps else "smooth"))
            if "lean" in cue:
                snap = max(1, int(float(cue.get("snap", 0.2)) * fps))
                amp = float(cue["lean"])
                lean_seg.append((f, f + snap, lambda fr, a=amp: a, "back" if snap <= 0.4 * fps else "smooth"))
                if cue.get("hold") is not None:
                    f2 = f + snap + int(float(cue["hold"]) * fps)
                    lean_seg.append((f2, f2 + max(1, int(float(cue.get("back", 1.5)) * fps)), lambda fr: 0.0, "smooth"))
        lo = max(1, evs[0][0] - 8)
        frames = list(range(1, last + 1))

        def run(segs, zero, n):
            vals, cur, seg, frm = {}, zero, None, zero
            pending = sorted(segs, key=lambda s: s[0])
            for fr in frames:
                while pending and pending[0][0] <= fr:
                    seg, frm = pending.pop(0), cur
                if seg is not None:
                    a, b, tgt, kind = seg
                    u = 1.0 if b <= a else (fr - a) / (b - a)
                    e = _ease_out_back(u) if kind == "back" and u < 1 else _smooth01(u)
                    goal = tgt(fr)
                    cur = tuple(x + (y - x) * e for x, y in zip(frm, goal)) if n > 1 else frm + (goal - frm) * e
                vals[fr] = cur
            return vals

        look = run(look_seg, (0.0, 0.0), 2)
        lean = run(lean_seg, 0.0, 1)
        rngp = random.Random(f"react{name}")
        ph = [rngp.uniform(0, math.tau) for _ in range(3)]
        env = {fr: _smooth01((fr - lo) / fps) * _smooth01((last - fr) / (1.5 * fps)) for fr in frames}

        def drift(fr):
            t = fr / fps
            looking = min(1.0, (abs(look[fr][0]) + abs(look[fr][1])) / 6.0)
            return (looking * env[fr] * 2.5 * math.sin(math.tau * t / 5.3 + ph[0]),
                    looking * env[fr] * 1.5 * math.sin(math.tau * t / 3.7 + ph[1]),
                    env[fr] * 0.8 * math.sin(math.tau * t / 4.2 + ph[2]))        # breathing (chest)

        def pose(fr):
            spec = {}
            for bone, share, lag in REACT_BONES["yaw"]:
                y = look[max(1, fr - lag)][0] + drift(max(1, fr - lag))[0]
                spec.setdefault(bone, []).append(((0, 0, 1), share * y))
            for bone, share, lag in REACT_BONES["pitch"]:
                p = look[max(1, fr - lag)][1] + drift(max(1, fr - lag))[1]
                spec.setdefault(bone, []).append(((1, 0, 0), share * p))
            for bone, share, lag in REACT_BONES["lean"]:
                ln = lean[max(1, fr - lag)]
                spec.setdefault(bone, []).append(((1, 0, 0), share * ln + (drift(fr)[2] if bone == "Torso" else 0.0)))
            spec["Head"].append(((1, 0, 0), -0.45 * lean[fr]))      # the gaze stays on the target while the torso leans back
            return procedural._bend(rig, spec)

        rigs.pose_layer(rig, frames, pose)
        print(f"  react: {name}, {len(evs)} cues, max gaze {max(abs(v[0]) for v in look.values()):.0f}°, "
              f"lean {min(lean.values()):.1f}..{max(lean.values()):.1f}°")
    _reacts.clear()


def apply_cues(sid, stage, props, tl, start, end, fps, have_voice, coll=None):
    """Applies the cues. Returns (shakes, light changes [(frame, frames, name)], water color [(frame, frames, hex)])."""
    shakes, lights, waters = [], [], []
    rng = random.Random(f"{sid}cue")
    for cue in stage.get("cues", []):
        f = max(start, min(end, cue_frame(cue, sid, tl, start, end, fps, have_voice)))
        do = cue["do"]
        if do == "shake":
            shakes.append((f, float(cue.get("amp", 0.12))))
            continue
        if do == "meteor":
            make_meteor(coll, sid, cue, f, end, fps)
            continue
        if do == "light":
            lights.append((f, max(1, int(float(cue.get("dur", 10.0)) * fps)), cue["light"]))
            continue
        if do == "water":
            waters.append((f, max(1, int(float(cue.get("dur", 6.0)) * fps)), cue["color"]))
            continue
        if do == "sink":                          # camera drops (doubled weight): cameras.sink_offset
            _SINKS.append((f, max(1, int(float(cue.get("dur", 1.4)) * fps)), float(cue.get("z", 1.45))))
            riverside.EVENTS.append(f)
            continue
        found = targets_of(cue, props)
        if not found:
            kit.problem(f"scene {sid}: cue '{do}' without target '{cue.get('target')}'")
        if do == "grow" and any(p.ident == "ant" for p in found):     # anthill that grows along ('scale_with_ants')
            a, b = float(cue.get("from", 0.05)), float(cue.get("size", 1.0))
            for hill in [p for p in props.values() if p.ident == "anthill" and p.spec.get("scale_with_ants")]:
                k = b / a if hill.spec["scale_with_ants"] is True else float(hill.spec["scale_with_ants"])
                cur = tuple(hill.obj.scale)
                f1 = f + max(1, int((float(cue.get("dur", 8.0)) + float(cue.get("stagger", 0.0)) / 2) * fps))
                kit.key(hill.obj, "scale", cur, start)
                kit.key(hill.obj, "scale", cur, f)
                kit.key(hill.obj, "scale", tuple(c * k for c in cur), f1)
        for prop in found:
            o = prop.obj
            if do in ("pop", "vanish"):
                cur = tuple(o.scale)
                if do == "pop":
                    kit.key(o, "scale", (0, 0, 0), start)
                    kit.key(o, "scale", (0, 0, 0), max(start, f - 1))
                    kit.key(o, "scale", cur, f + 6)
                else:
                    kit.key(o, "scale", cur, start)
                    kit.key(o, "scale", cur, f)
                    kit.key(o, "scale", (0, 0, 0), f + 8)
            elif do in riverside.CUES:
                riverside.cue(do, prop, cue, f, start, end, fps, coll)
            elif do == "action" and str(cue["action"]).lower() in riverside.GESTURES:
                riverside.gesture(prop, str(cue["action"]).lower(), f, fps, cue)
            elif do == "move" and prop.rig is not None and _paired(stage, cue, "action"):
                _walk_move(prop, cue, f, fps, _paired(stage, cue, "action"))
            elif do == "action" and prop.rig is not None and str(cue["action"]).lower() in HOLD_END:
                _sit(prop, cue, f, fps, props)
            elif do == "action" and prop.rig is not None and _paired(stage, cue, "move"):
                continue                               # the walk comes along with the 'move' (_walk_move)
            elif do == "move":
                t = Vector(cue["to"]) if len(cue["to"]) == 3 else Vector((*cue["to"], presets.ground_height(*cue["to"])))
                dur = int(float(cue.get("dur", 1.0)) * fps)
                kit.key(o, "location", tuple(o.location), start)
                kit.key(o, "location", tuple(o.location), f)
                kit.key(o, "location", tuple(t), f + dur)
                prop.positions = [(start, Vector(o.location)), (f, Vector(o.location)), (f + dur, t)]
            elif do == "grow" and procedural.is_fish(o):      # dead fish: floats up to the surface, each at its own instant
                f0 = min(end, f + int(rng.uniform(0, float(cue.get("stagger", 0.0))) * fps))
                procedural.fish_rise(o, f0, float(cue.get("dur", 1.2)))
            elif do == "grow" and prop.parts:
                when = procedural.grow_parts(prop.parts, f, end, fps, float(cue.get("from", 0.05)), float(cue.get("size", 1.0)),
                                             float(cue.get("dur", 2.5)), float(cue.get("stagger", 8.0)),
                                             float(cue.get("keep", 0.0)), o.location)
                procedural.freeze_floaters(o.location, when, start, fps)
            elif do == "still":
                if not procedural.still(o, f, float(cue.get("dur", 2.0)), fps):
                    kit.problem(f"scene {sid}: 'still' on '{prop.name}', which does not float")
            elif do == "grow":
                cur = tuple(o.scale)
                a, b = float(cue.get("from", 0.05)), float(cue.get("size", 1.0))
                f0 = min(end, f + int(rng.uniform(0, float(cue.get("stagger", 0.0))) * fps))
                f1 = f0 + max(1, int(float(cue.get("dur", 8.0)) * fps))
                kit.key(o, "scale", tuple(c * a for c in cur), start)
                kit.key(o, "scale", tuple(c * a for c in cur), f0)
                kit.key(o, "scale", tuple(c * b for c in cur), f1)
            elif do == "action" and str(cue["action"]).lower() in procedural.GESTURES:
                procedural.gesture(prop, str(cue["action"]).lower(), f, fps, cue)
            elif do == "react":
                _react_cue(prop, cue, f, props)
            elif do == "dust":
                _dusts.append((coll, sid, prop, f, end, fps, cue))
            elif do == "dive":
                delay = random.Random(f"{sid}{prop.name}dive").uniform(0, float(cue.get("stagger", 0.0)))
                if not procedural.gull_dive(o, f, delay):
                    kit.problem(f"scene {sid}: 'dive' on '{prop.name}', which is not a gull")
            elif do == "action":
                if prop.rig is None:
                    kit.problem(f"scene {sid}: cue 'action' on '{prop.name}', which has no skeleton")
                else:
                    key = models.pick_action(prop.rig, cue["action"])
                    fa = f
                    if cue.get("stagger"):                   # group: each target at its own instant
                        fa = min(end, f + int(random.Random(f"{sid}{prop.name}act").uniform(0, float(cue["stagger"])) * fps))
                    if key in getattr(prop.rig.t, "once", ()):
                        procedural.ant.play(prop.rig, key, fa)
                        if cue.get("rest") and key == "Sag":       # lying in a loop right after the Sag (no extra cue)
                            procedural.ant.play(prop.rig, "SagIdle", fa + int(3.9 * fps))
                    else:
                        rigs.loop(prop.rig, key, fa, end, blend_in=4, extend="HOLD")
            else:
                kit.problem(f"scene {sid}: cue 'do': '{do}' unknown (pop, vanish, move, action, shake, light, grow, dive, dust, react)")
    return shakes, lights, waters


# ---------- walk to a point and sit (people cues; gravity-doubled) ----------

_SINKS = []                                       # (frame, frames, z) of the camera cue 'sink'
SIT_Z = 0.08                                      # how much the root rises when sitting by cue (thigh over the 0.42 m seat)
WALKS = ("walk", "run")


def _cue_t(c):
    return float(c.get("t", c.get("frac", -1)))


def _paired(stage, cue, other):
    """'move' + 'action' Walk/Run on the same target and at the same instant (±0.15 s) = walk to the point with a matched step."""
    for c in stage.get("cues", []):
        if c is cue or c.get("target") != cue.get("target") or abs(_cue_t(c) - _cue_t(cue)) > 0.15:
            continue
        if other == "action" and c.get("do") == "action" and str(c.get("action", "")).lower() in WALKS:
            return c
        if other == "move" and c.get("do") == "move" and str(cue.get("action", "")).lower() in WALKS:
            return c
    return None


def _root_at(rig, f):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    return rig.root.location.copy(), rig.root.rotation_euler.z


def _key_root(rig, frames, locs, rots):
    root = rig.root
    for fr, p, r in zip(frames, locs, rots):
        root.location = tuple(p)
        root.keyframe_insert("location", frame=fr)
        root.rotation_euler = (0, 0, r)
        root.keyframe_insert("rotation_euler", frame=fr)
    for fc in ac.bag(root).fcurves:
        for kp in fc.keyframe_points:
            if frames[0] - 1 <= kp.co[0] <= frames[-1]:
                kp.interpolation = "LINEAR"


def _walk_move(prop, cue, f, fps, pair):
    """People walk to 'to' in 'dur' s: turn toward the destination in 0.35 s, accelerate, walk and brake; the walk cycle follows the
    distance covered (rigs.timed by the planted foot: it does not skate with the speed varying)."""
    rig = prop.rig
    gait = models.pick_action(rig, pair.get("action", "Walk"))
    p0, r0 = _root_at(rig, f)
    to = cue["to"]
    p1 = Vector((to[0], to[1], presets.ground_height(to[0], to[1]) if len(to) == 2 else to[2]))
    D = max(2, int(float(cue.get("dur", 1.5)) * fps))
    vec = p1 - p0
    total = vec.to_2d().length
    hd = math.atan2(vec.y, vec.x) + math.pi / 2
    hd = r0 + (hd - r0 + math.pi) % math.tau - math.pi
    ta, td = min(0.3 * fps, D / 3), min(0.35 * fps, D / 3)
    frames = list(range(f, f + D + 1))
    dist, s = [], 0.0
    for fr in frames:
        k = fr - f
        v = min(1.0, k / ta, (D - k) / td)
        s += max(v, 0.0)
        dist.append(s)
    dist = [d * total / max(dist[-1], 1e-6) for d in dist]
    vmax = max(b - a for a, b in zip(dist, dist[1:])) * fps
    locs = [p0.lerp(p1, d / max(total, 1e-6)) for d in dist]
    for q in locs:
        q.z = presets.ground_height(q.x, q.y)
    turn = max(1, int(0.35 * fps))
    rots = [r0 + (hd - r0) * _smooth01((fr - f) / turn) for fr in frames]
    _key_root(rig, frames, locs, rots)
    per = riverside.planted_per_frame(rig, gait)
    a0 = rig.t.actions[gait].frame_range[0]
    times = [a0 + d / max(per, 1e-4) for d in dist]
    infl = [max(0.0, min(1.0, (fr - f) / 4.0, (f + D - fr) / 6.0)) for fr in frames]
    rigs.timed(rig, gait, frames, times, infl)
    prop.positions = [pp for pp in prop.positions if pp[0] < f] + [(fr, Vector(q)) for fr, q in zip(frames, locs)]
    print(f"  walk: {prop.name} {total:.2f} m in {D / fps:.1f} s (max {vmax:.2f} m/s; planted foot {per * rigs.ASSET_FPS:.2f} m/s)")


def _sit(prop, cue, f, fps, props):
    """Sit by cue: turns in 0.35 s toward the cue's 'face' or the nearest bench (up to 0.8 m), sits once
    (the 'Sitting' action has the sit-down movement at the start) and holds the pose; rises 6 cm for the seat."""
    rig = prop.rig
    p0, r0 = _root_at(rig, f)
    face = cue.get("face")
    if face is None:
        best = None
        for bx, by in riverside.BENCHES:
            d = math.hypot(p0.x - bx, p0.y - by)
            if d < 0.8 and (best is None or d < best[0]):
                best = (d, 90.0)
        for n, q in props.items():
            if q.ident == "bench":
                b = q.pos(f)
                d = math.hypot(p0.x - b.x, p0.y - b.y)
                if d < 0.8 and (best is None or d < best[0]):
                    best = (d, math.degrees(q.obj.rotation_euler.z - math.pi / 2))
        face = best[1] if best else None
    turn = max(1, int(0.35 * fps))
    frames = list(range(f, f + turn + int(0.5 * fps) + 1))
    hd = r0 if face is None else math.radians(float(face)) + math.pi / 2
    hd = r0 + (hd - r0 + math.pi) % math.tau - math.pi
    rots = [r0 + (hd - r0) * _smooth01((fr - f) / turn) for fr in frames]
    sit0 = f + int(0.25 * fps)
    locs = [p0 + Vector((0, 0, SIT_Z * _smooth01((fr - sit0) / (0.4 * fps)))) for fr in frames]
    _key_root(rig, frames, locs, rots)
    key = models.pick_action(rig, cue["action"])
    act = rig.t.actions[key]
    ad = rig.arm.animation_data or rig.arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = f"Sit{f}"
    st = track.strips.new(key, sit0, act)
    st.action_slot = act.slots[0]
    st.use_auto_blend = False
    st.scale = rigs.strip_scale(1.0)
    st.blend_in = 4
    st.extrapolation = "HOLD_FORWARD"
    prop.positions = [pp for pp in prop.positions if pp[0] < f] + [(frames[-1], locs[-1])]
    print(f"  sits: {prop.name} f{sit0}, facing {math.degrees(hd - math.pi / 2):.0f} degrees")


# ---------- world and scene ----------

def make_world():
    world = bpy.data.worlds.new("Stage")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bpy.context.scene.world = world
    return bg.inputs["Strength"]


def make_camera():
    data = bpy.data.cameras.new("Eye")
    data.lens = 24
    data.clip_start, data.clip_end = 0.05, 4000.0
    cam = bpy.data.objects.new("Eye", data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def _stage_refs(stage) -> set:
    """Piece names that the camera and cues cite in the scene (group 'herd' counts for the members 'herd0'...)."""
    cam = stage["camera"]
    looks = [w.get("look") for w in cam["path"]] if cam.get("preset") == "path" else [cam.get("look")]
    refs = {look.split("^")[0] for look in looks if isinstance(look, str)}
    refs |= {c["target"] for c in stage.get("cues", []) if c.get("target")}
    return refs


def stage_checks(sid, stage, props, cam, start, end):
    """Camera target inside the safe area (start, middle and end) and static pieces resting on the ground."""
    spec = stage["camera"]
    if spec.get("preset") == "path":           # each pass-through point checks its own target in its own frame
        for w in spec["path"]:
            look = w.get("look")
            if isinstance(look, str) and look.split("^")[0] in props:
                p_ = props[look.split("^")[0]]
                f = start + int(float(w["t"]) * bpy.context.scene.render.fps) if "t" in w else                     start + int(float(w.get("frac", 0.5)) * (end - start))
                f = max(start + 2, min(end - 1, f))
                kit.require_in_frame(f"scene {sid} target '{look}'", bpy.context.scene, cam,
                                     p_.pos(f) + Vector((0, 0, p_.height * 0.5)), f)
        return
    looks = {spec["look"]} if isinstance(spec["look"], str) else set()
    looks = {look.split("^")[0] for look in looks}
    for look in sorted(looks & props.keys()):
        if look not in props:
            continue
        for f in (start + 2, (start + end) // 2, end - 1):
            kit.require_in_frame(f"scene {sid} target '{look}'", bpy.context.scene, cam,
                                 props[look].pos(f) + Vector((0, 0, props[look].height * 0.5)), f)


def build(tl):
    args = sys.argv[sys.argv.index("--") + 1:]
    data = json.loads(Path(args[args.index("--timeline") + 1]).read_text(encoding="utf-8"))
    stages = {s["id"]: s["stage"] for s in data["scenes"] if s.get("stage")}
    missing = [s["id"] for s in data["scenes"] if not s.get("stage")]
    if missing:
        raise SystemExit(f"stage: scenes without the 'stage' field: {missing}")
    fps = tl.fps
    have_voice = bool(kit.VOICE)
    scene = bpy.context.scene
    make_world()
    cam = make_camera()
    samples, ends, checks, groups = [], set(), [], []
    # extent of each group of 'same' scenes (pieces with span 'group' live from its start to its end)
    extent, cur = {}, None
    for sc in data["scenes"]:
        a, b = tl.scenes[sc["id"]]
        if stages[sc["id"]].get("set", "meadow") != "same" or cur is None:
            cur = [a, b - 1, []]
        cur[1] = b - 1
        cur[2].append(sc["id"])
        for sid_ in cur[2]:
            extent[sid_] = cur
    # 1) pieces of each scene (the camera and the group's pieces enter the dressing's forbidden zone)
    for sc in data["scenes"]:
        sid = sc["id"]
        stage = stages[sid]
        start, end = tl.scenes[sid]
        end -= 1                                  # exclusive end of the timeline -> last frame of the scene
        rng = random.Random(f"{sid}")
        coll = bpy.data.collections.new(f"S{sid}")
        scene.collection.children.link(coll)
        cam_spec = stage["camera"]
        cam_at = cam_spec["at"] if cam_spec.get("preset") != "path" else next(w["at"] for w in cam_spec["path"] if "at" in w)
        stage = {**stage, "camera": {**cam_spec, "at": cam_at}}
        keepout = [(cam_at[0], cam_at[1], 3.0)]
        if stage.get("set", "meadow") == "same":
            if not groups:
                raise SystemExit(f"stage: scene {sid} uses set 'same' but is the first (there is no previous stage)")
            group = groups[-1]
        else:
            group = dict(set=stage.get("set", "meadow"), light=stage.get("light", "noon"), keepout=[],
                         scenes=[], ranges=[], first=sid, spans=[])
            groups.append(group)
        presets.set_active(group["set"])
        live = {n_: (p_, r_) for n_, p_, r_, _c in group["spans"] if r_[0] <= start and end <= r_[1]}
        props, spans = place_props(sid, stage, coll, start, end, rng, fps, keepout,
                                   {"tl": tl, "group": (extent[sid][0], extent[sid][1]), "live": live})
        keepout += [(p.pos(start).x, p.pos(start).y, 4.0) for p in props.values()]
        for _n, p_, _r, _c in spans:          # walker's corridor: the dressing (bush, tree) does not spawn in the path
            keepout += [(v.x, v.y, 3.0) for _f, v in p_.positions[::6]]
        group["keepout"] += keepout
        group["spans"].extend(spans)
        for n_, p_, (s_, e_), _c in group["spans"]:            # span pieces from previous scenes that cover this one
            if s_ <= start and end <= e_ and n_ not in props:
                props[n_] = p_
        group["scenes"].append((sid, stage, props, coll, start, end))
        group["ranges"].append((start, end))
    # 2) stage (ground, sky, sun, dressing) once per group, visible in all the group's scenes
    for group in groups:
        gcoll = bpy.data.collections.new(f"E{group['first']}")
        scene.collection.children.link(gcoll)
        group["env"] = presets.build(gcoll, group["set"], group["light"], random.Random(f"env{group['first']}"),
                                     group["keepout"], span=(group["ranges"][0][0], group["ranges"][-1][1]))
        ac.visible_ranges(list(gcoll.all_objects), group["ranges"], tl.frames)
    # 3) cues, camera and light, scene by scene
    for group in groups:
        env = group["env"]
        presets.set_active(group["set"])
        env.key(group["ranges"][0][0], env.light)
        for _sc in group["scenes"]:                  # cue targets the stage creates (riverside: footbridge, crane...)
            for n_, t_ in getattr(env, "targets", {}).items():
                if n_ not in _sc[2]:
                    tp = Prop(n_, t_.obj, t_.height, [(_sc[4], Vector(t_.at))])
                    tp.ident, tp.spec = n_, {}
                    _sc[2][n_] = tp
        for n_, p_, (s_, e_), c_ in group.get("spans", []):
            ac.visible_ranges(list(c_.all_objects), [(s_, e_)], tl.frames)
        for idx, (sid, stage, props, coll, start, end) in enumerate(group["scenes"]):
            if idx and stage.get("light"):            # time jump on the same stage: the light state changes AT THE CUT
                env.key(start - 1, env.light)
                env.key(start, presets.LIGHTS[stage["light"]])
            shakes, lights, waters = apply_cues(sid, stage, props, tl, start, end, fps, have_voice, coll)
            for f, dur, hexa in sorted(waters):
                env.key_water(f, f + dur, hexa)
            for f, dur, name in sorted(lights):
                f0 = max(f, env.keys["amb0"][-1][0])
                env.key(f0, env.light)
                env.key(f0 + dur, presets.LIGHTS[name])
            look_map = {n: (p.pos, p.height) for n, p in props.items()}
            for ref in _stage_refs(stage):
                if not any(n == ref or (n.startswith(ref) and n[len(ref):].isdigit()) for n in props):
                    raise SystemExit(f"stage: scene {sid} cites '{ref}', which does not exist in it (pieces with span must cover the scene)")
            samples += cameras.plan(stage["camera"], start, end, look_map, shakes, fps,
                                    sinks=[s for s in _SINKS if start <= s[0] <= end])
            ends.add(end)
            checks.append((sid, stage, props, start, end))
            ac.visible_ranges(list(coll.all_objects), [(start, end)], tl.frames)
        env.key(group["ranges"][-1][1], env.light)       # holds the light until the end of the group (hard cut to the next)
        env.write_keys()
    write_reacts(fps, tl.frames)                  # whoever is seated reacts (layer over the pose)
    riverside.finish(fps, tl.frames)              # riverside stage: footbridge, crane, fall, scale, background people
    procedural.finish(fps)                        # sway of what floats, fishing rods and floats
    cameras.key_camera(cam, samples, ends)
    for d in _dusts:                              # dust that rolls to the camera: needs the camera already animated
        make_dust(*d, cam)
    amb = sorted(f_v for g in groups for f_v in g["env"].keys["amb0"])
    ac.write(scene.world.node_tree, 'nodes["Background"].inputs[1].default_value', 0, [f for f, _ in amb],
             [v for _, v in amb])
    presets.write_world(groups)                   # world color keyed and distance mist
    for check in checks:                          # with the camera already animated
        stage_checks(*check[:3], cam, *check[3:])
