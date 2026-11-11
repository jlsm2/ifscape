"""Motion audit in a Blender scene: finds "lifeless" animation that flicker.py does not catch.

Usage (runs inside Blender, on the scene saved by the render):
  blender -b build/<slug>/blender/scene.blend -P tools/qa/anim_audit.py -- build/<slug>/blender/timeline.json [output.md]

For each scene in the timeline, samples every 2 frames the visible objects that move and flags:
- SLIDES: a character (object with child parts, or a mesh that walks) that moves without moving legs/arms/body
  (a skating statue, the error of the people in scene 08 before it was fixed);
- RIGID SPIN: an object that rotates more than 45° in a scene without any part of it moving during the spin, or with
  almost constant speed (a fall without acceleration or impact; the error of the dinosaur fall);
- POP: hide_render toggling outside the scene cut, or scale going to ~0 / coming back from ~0 within 2 frames;
- ORPHAN: a visible part with a hidden parent (the mammal's legs were left loose around the set);
- LOOSE PART: a part (mesh child of a mesh) that moves away from its parent's body during the animation;
- TOO STILL: a big event (object whose name has Impact/Flash/Explosion/Asteroid) with a single layer, without
  light or smoke/dust in the same scene (weak effect);
- CLIPS THROUGH: a character mesh (with an Armature modifier), in the DEFORMED pose of the frame, crossing the faces of
  another visible object: head through the ceiling, legs through the car floor (technology-disappeared:
  it went through two reviews and only showed up when watching). Flat ground and the character's own parts do not count.
It is a filter, not a verdict: check each item in the video frames.
"""

import json
import math
import sys
from pathlib import Path

import bpy

IGNORE = ("Eye", "Sun", "Moon", "Sky", "Space", "Star", "Shell")
# Effects that walk and spin whole by nature (leaf in the wind, dust, windmill blade, distant bird): SLIDES and
# RIGID SPIN on them are noise (they were ~260 of the ~270 "HIGH" on plants-extinct). POP still applies.
DRIFT = ("Leaf", "Dust", "Gull", "Bird", "Cloud", "WindmillSails", "Sails", "Ember", "Spark", "Debris", "Grain")
MOTION_KINDS = ("SLIDES", "RIGID SPIN")
EVENT = ("Impact", "Flash", "Explosion", "Asteroid")
LAYER = ("Light", "Smoke", "Cap", "Dust", "Wall", "Core", "Head", "Trail")
STEP = 2


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return Path(a[0]), (Path(a[1]) if len(a) > 1 else None)


def drift_prefixes(tl_path):
    """DRIFT + video prefixes in build/<slug>/qa/anim_ignore.txt (one per line; # comments)."""
    extra = tl_path.parent.parent / "qa" / "anim_ignore.txt"
    names = [ln.split("#")[0].strip() for ln in extra.read_text(encoding="utf-8").splitlines()] if extra.exists() else []
    return DRIFT + tuple(n for n in names if n)


def has_anim(o):
    return o.animation_data is not None and o.animation_data.action is not None


def visible_at(o, f):
    scene = bpy.context.scene
    scene.frame_set(f)
    return not o.hide_render


def descendants(o):
    return list(o.children_recursive)


def world_box(o):
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def detached(child, parent, slack=0.3):
    """The part's box does not touch the parent's box (with 30% of the parent's size as slack)."""
    clo, chi = world_box(child)
    plo, phi = world_box(parent)
    pad = (phi - plo) * slack
    return any(chi[i] < plo[i] - pad[i] or clo[i] > phi[i] + pad[i] for i in range(3))


def white_covered():
    """The white screen (object/material 'Whiteout') covers the current frame."""
    mat = bpy.data.materials.get("Whiteout")
    if mat is None or not mat.node_tree:
        return False
    node = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return node is not None and node.inputs["Alpha"].default_value > 0.9


def bone_parts(parts):
    """Armature bones between the parts: in a rigged character (asset with a deformed mesh), the legs
    move through the bones and the mesh matrix_local stays still; without this, every rigged creature would come out SLIDES."""
    out = []
    for p in parts:
        if p.type == "ARMATURE":
            for pb in p.pose.bones:
                m = pb.matrix_channel
                out.append((m.to_quaternion().copy(), m.to_scale().copy()))
    return out


def rot_deg(q0, q1):
    return math.degrees(q0.rotation_difference(q1).angle)


FLAT = 0.08            # object lower than this (m) is ground: a foot and hip touching it do not count
PEN_STEP = 6           # CLIPS THROUGH samples every 6 frames (the BVH of the deformed pose is expensive)
PEN_MIN_PAIRS = 3
FOOT = 0.15            # m: foot band, where touching the ground is normal
LOW = 0.6              # m: an object that does not rise above this over the character's foot is "ground"
ROPE = 0.04            # m: object thin in two dimensions (rein, rope, cable) only touches, does not count      # less than this is touching (hand on the handlebar), not clipping through


FX = ("Rope", "Rein", "Leash", "Cable", "TechBits", "Spark", "Flame", "Fire", "Smoke", "Dust", "Drop", "Bits", "Glow", "Flash")


def owner_of(char):
    """The "owner" of the character mesh: the parent of the armature that deforms it (the character Empty). Parts inside it
    (clothes, bag, tool) belong to the character itself; the car it is sitting in does not."""
    arm = next((m.object for m in char.modifiers if m.type == "ARMATURE" and m.object), None)
    base = arm or char
    return base.parent or base


def gone(o):
    """Invisible in the frame: hide_render, or undone by the vanishing effect ("vanish" property of town_fx, which
    disappears through the material and leaves the mesh in place). The owner counts too: a part of a vanished car vanished with it."""
    while o is not None:
        if o.hide_render or float(o.get("vanish", 0.0)) >= 0.95:
            return True
        o = o.parent
    return False


def inside(o, group):
    while o is not None:
        if o is group:
            return True
        o = o.parent
    return False


def bvh_world(o, depsgraph):
    """BVH of the evaluated mesh (deformed pose, modifiers applied) in world coordinates."""
    from mathutils.bvhtree import BVHTree
    ev = o.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    try:
        verts = [ev.matrix_world @ v.co for v in mesh.vertices]
        polys = [tuple(p.vertices) for p in mesh.polygons]
        return BVHTree.FromPolygons(verts, polys), verts, polys
    finally:
        ev.to_mesh_clear()


def boxes_touch(a, b):
    (alo, ahi), (blo, bhi) = a, b
    return all(ahi[i] >= blo[i] and bhi[i] >= alo[i] for i in range(3))


OUT_MARGIN = 0.03      # 3 cm of slack for the vehicle box
OUT_MIN = 20           # vertices outside to count (fewer than that is edge noise)


def sticking_out(c, depsgraph, cache):
    """Character whose owner is a child of a vehicle (driver: Driver0 inside Car0): parts of the pose that leave the
    box of the vehicle meshes. Catches a leg showing underneath even if the car has no modeled floor."""
    owner = owner_of(c)
    vehicle = owner.parent
    if vehicle is None or gone(vehicle) or float(vehicle.get("vanish", 0.0)) > 0.0:
        return None
    body = [m for m in vehicle.children_recursive if m.type == "MESH" and not inside(m, owner) and not gone(m)
            and float(m.get("vanish", 0.0)) == 0.0]
    shell = [m for m in body if "Body" in m.name]   # bodywork: the wheels go down to the ground and would hide the leg
    body = shell or body
    if not body:
        return None
    boxes = [world_box(m) for m in body]
    lo = [min(b[0][i] for b in boxes) - OUT_MARGIN for i in range(3)]
    hi = [max(b[1][i] for b in boxes) + OUT_MARGIN for i in range(3)]
    if c.name not in cache:
        cache[c.name] = bvh_world(c, depsgraph)
    verts = cache[c.name][1]
    out = [v for v in verts if any(v[i] < lo[i] or v[i] > hi[i] for i in range(3))]
    if len(out) < OUT_MIN:
        return None
    from mathutils import Vector
    return len(out), vehicle.name, (Vector(lo), Vector(hi))


def penetrations(windows):
    """CLIPS THROUGH: faces of the character's real pose crossing faces of another visible object."""
    scene = bpy.context.scene
    chars = [o for o in scene.objects if o.type == "MESH"
             and any(m.type == "ARMATURE" for m in o.modifiers)]
    others = [o for o in scene.objects if o.type == "MESH" and o not in chars and not any(t in o.name for t in FX)]
    found = {}
    for sid, a, b in windows:
        for f in range(a, b, PEN_STEP):
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            live = [c for c in chars if not gone(c)]
            if not live:
                continue
            cache = {}
            # Boxes once per frame, and only of the objects that touch some character's box: on the park stage
            # (thousands of parts and ~50 characters) recomputing the box inside the pair took hours.
            cboxes = {c.name: world_box(c) for c in live}
            u_lo = [min(b[0][i] for b in cboxes.values()) for i in range(3)]
            u_hi = [max(b[1][i] for b in cboxes.values()) for i in range(3)]
            near = []
            for o in others:
                if gone(o):
                    continue
                obox = world_box(o)
                if any(obox[1][i] < u_lo[i] or obox[0][i] > u_hi[i] for i in range(3)):
                    continue
                dims = sorted(obox[1][i] - obox[0][i] for i in range(3))
                if obox[1].z - obox[0].z < FLAT or dims[1] < ROPE:
                    continue
                near.append((o, obox))
            for c in live:
                cbox = cboxes[c.name]
                for o, obox in near:
                    if inside(o, owner_of(c)) or not boxes_touch(cbox, obox):
                        continue
                    if c.name not in cache:
                        cache[c.name] = bvh_world(c, depsgraph)
                    if o.name not in cache:
                        cache[o.name] = bvh_world(o, depsgraph)
                    (cb, cverts, cpolys), (ob, _, _) = cache[c.name], cache[o.name]
                    # Soles and feet touching the ground or the flower bed are contact, not clipping through: ignores the faces of the
                    # character in the last FOOT m of its height.
                    floor = min(v.z for v in cverts) + FOOT
                    pairs = [(i, j) for i, j in cb.overlap(ob) if any(cverts[k].z > floor for k in cpolys[i])]
                    if len(pairs) < PEN_MIN_PAIRS:
                        continue
                    low = obox[1].z < floor - FOOT + LOW   # canteiro, planta, rua: sentar/ajoelhar encosta
                    fading = low or any(float(x.get("vanish", 0.0)) > 0.0 for x in (o, o.parent) if x is not None)
                    key = (sid, owner_of(c).name, o.name.split(".")[0])
                    if key not in found or len(pairs) > found[key][1]:
                        found[key] = (f, len(pairs), o.name, obox, fading)
                outside = sticking_out(c, depsgraph, cache)
                if outside:
                    key = (sid, owner_of(c).name, "outside the vehicle")
                    found.setdefault(key, (f, outside[0], outside[1], outside[2], False))
    rows = []
    for (sid, cname, oname), (f, n, part, (lo, hi), fading) in found.items():
        if oname == "outside the vehicle":
            rows.append((3, sid, f, f"{cname} in {part}", "CLIPS THROUGH",
                         f"{n} pose vertices outside the vehicle box (z {lo.z:.2f} to {hi.z:.2f} m): leg underneath, "
                         "head through the roof or arm through the body panel"))
        else:
            rows.append((2 if fading else 3, sid, f, f"{cname} × {part}", "CLIPS THROUGH",
                         f"{n} face pairs crossing in the frame pose (object spans z {lo.z:.2f} to {hi.z:.2f} m)"
                         + ("; low object dissolving or ground-level (sitting, kneeling, weeding): check whether it shows clipping through"
                            if fading else "")))
    return rows


def audit(tl_path):
    tl = json.loads(tl_path.read_text(encoding="utf-8"))
    scene = bpy.context.scene
    windows = [(s["id"], s["start"] + 1, s["end"]) for s in tl["scenes"]]
    cuts = {a for _, a, _ in windows}
    # the camera is not a character: its spin is the framing, not lifeless animation
    movers = [o for o in scene.objects if has_anim(o) and o.type != "CAMERA" and not o.name.startswith(IGNORE)]
    roots = [o for o in movers if not (o.parent and has_anim(o.parent))]
    findings = []
    for sid, a, b in windows:
        frames = list(range(a, b, STEP))
        if len(frames) < 3:
            continue
        mid = frames[len(frames) // 2]
        scene.frame_set(mid)
        live = [o for o in roots if not o.hide_render]
        track = {}
        covered = set()
        for o in scene.objects:                                  # ORPHAN: visible part, hidden parent
            if o.type == "MESH" and not o.hide_render and o.parent is not None:
                anc = o.parent
                while anc is not None and not anc.hide_render:
                    anc = anc.parent
                if anc is not None:
                    findings.append((3, sid, mid, o.name, "ORPHAN",
                                     f"visible with its parent '{anc.name}' hidden (it is left loose in the set)"))
        loose = {}
        for f in frames:
            scene.frame_set(f)
            if white_covered():
                covered.add(f)
            for o in live:
                for c in descendants(o):
                    if c.type == "MESH" and c.parent is not None and c.parent.type == "MESH" and not c.hide_render                             and detached(c, c.parent):
                        loose.setdefault(c.name, f)
            for o in live:
                m = o.matrix_world
                parts = descendants(o)
                track.setdefault(o.name, []).append((
                    f, m.to_translation().copy(), m.to_quaternion().copy(), m.to_scale().copy(),
                    [(p.matrix_local.to_quaternion().copy(), p.matrix_local.to_scale().copy()) for p in parts]
                    + bone_parts(parts),
                    o.hide_render))
        for name, rows in track.items():
            o = scene.objects[name]
            pos = [r[1] for r in rows]
            dist = max((p - pos[0]).length for p in pos)
            span = (rows[-1][0] - rows[0][0]) / scene.render.fps
            limb = 0.0
            for k in range(1, len(rows)):
                for (q0, s0), (q1, s1) in zip(rows[k - 1][4], rows[k][4]):
                    limb = max(limb, rot_deg(q0, q1), abs(s1.z - s0.z) * 100)
            # SLIDES: walks more than 1 m without the parts moving more than 1° between samples
            is_char = bool(rows[0][4]) or o.type == "MESH"
            if is_char and dist > 1.0 and span > 0 and dist / span > 0.2 and limb < 1.0 \
                    and not name.startswith(("Car", "Asteroid", "Impact", "Trail", "Cloud", "Monsoon")):
                kind = "still parts" if rows[0][4] else "single body without limbs"
                findings.append((3, sid, rows[0][0], name, "DESLIZA",
                                 f"walks {dist:.1f} m in {span:.1f} s with {kind} (max swing {limb:.1f}°)"))
            # RIGID SPIN: rotates > 45° and the parts do not move / almost constant speed
            total = rot_deg(rows[0][2], rows[-1][2])
            # Effect debris (Impact*/Asteroid*) spins whole on purpose: a rolling rock has no parts.
            if total > 45 and not name.startswith(EVENT):
                rates = [rot_deg(rows[k - 1][2], rows[k][2]) for k in range(1, len(rows))]
                moving = [r for r in rates if r > 0.2]
                peak = max(moving) if moving else 0
                mean = sum(moving) / len(moving) if moving else 0
                if limb < 1.0:
                    findings.append((3, sid, rows[0][0], name, "RIGID SPIN",
                                     f"rotates {total:.0f}° without any part moving"))
                elif mean and peak / mean < 1.3 and len(moving) > 4:
                    findings.append((2, sid, rows[0][0], name, "RIGID SPIN",
                                     f"rotates {total:.0f}° at almost constant speed (peak/mean {peak / mean:.2f}): "
                                     "no acceleration or impact"))
            # POP: scale collapsing or appearing from one sample to the next; hide_render outside the cut
            peak = max(r[3].length for r in rows)
            for k in range(1, len(rows)):
                s0, s1 = rows[k - 1][3].length, rows[k][3].length
                # Pop = reaches more than half the maximum size (or vanishes from it) in one sample. An effect that starts
                # small and grows (dust, smoke) does not count.
                if (s0 > 0.5 * peak and s1 < 0.02) or (s0 < 0.02 and s1 > 0.5 * peak):
                    findings.append((2, sid, rows[k][0], name, "POP",
                                     f"scale {s0:.2f} → {s1:.2f} in {STEP} frames"))
                if rows[k][5] != rows[k - 1][5] and not any(abs(rows[k][0] - c) <= STEP for c in cuts)                         and rows[k][0] not in covered and rows[k - 1][0] not in covered:
                    findings.append((3, sid, rows[k][0], name, "POP", "appears/disappears in the middle of the scene (hide_render)"))
        for name, f in loose.items():
            findings.append((3, sid, f, name, "LOOSE PART", "the part moves away from its parent's body"))
        # TOO STILL: big event with a single layer
        events = [n for n in track if n.startswith(EVENT)]
        layers = [n for n in track if any(t in n for t in LAYER)]
        if events and len(set(layers)) < 2:
            findings.append((2, sid, a, ", ".join(events[:3]), "WEAK EFFECT",
                             "big event without layers (light, smoke, dust, core)"))
    findings.extend(penetrations(windows))
    drift = drift_prefixes(tl_path)
    skipped = {}
    for r in findings:
        if r[4] in MOTION_KINDS and r[3].startswith(drift):
            pre = next(d for d in drift if r[3].startswith(d))
            skipped.setdefault(pre, set()).add(r[3].split(".")[0])
    findings = [r for r in findings if not (r[4] in MOTION_KINDS and r[3].startswith(drift))]
    findings.sort(key=lambda r: (-r[0], r[1], r[2]))
    sev = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}
    note = ("Ignored (SLIDES and SPIN of effects that walk by nature): "
            + ", ".join(f"{k} ({len(v)})" for k, v in sorted(skipped.items())) + "." if skipped else "")
    lines = ["# Motion audit", "", f"{len(findings)} findings.", note, "",
             "| Severity | Scene | Frame | Object | Type | Measure |", "| --- | --- | --- | --- | --- | --- |"]
    seen = set()
    for s, sid, f, name, kind, msg in findings:
        k = (sid, name.split(".")[0], kind)
        if k in seen:
            continue
        seen.add(k)
        lines.append(f"| {sev[s]} | {sid} | {f} | {name} | {kind} | {msg} |")
    return "\n".join(lines)


def main():
    tl, out = args()
    report = audit(tl)
    print(report)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")


main()
