"""Tested example (Blender 5.2.2, background): biped with armature, rigid weights by vertex group,
2-bone IK with pole and planted foot (no sliding), hip that rises and falls, opposing arms.

  blender -b --factory-startup -P tools/blender/examples/walk_biped_ik.py -- <output_folder> [--render]

Prints the maximum foot slide during stance (should stay < 2 mm) and, with --render, writes walk_####.png.
Front along +Y, feet at z = 0. Everything in meters and seconds.

Local axes of a pose bone = axes of the bone at rest (Y along the bone). With roll 0:
  bone pointing +Y  -> local equals world;
  bone pointing +Z  -> local Y = world Z, local Z = world -Y (rotation about local Y = turning about Z);
  bone pointing -Z  -> rotation about local X swings forward/back.
"""
import math
import os
import sys

import bpy

FPS = 30
SPEED = 1.1            # m/s
CYCLE = 1.1            # s per full cycle (two steps)
DUTY = 0.6             # fraction of the cycle with the foot on the ground (walking > 0.5; running < 0.5)
THIGH, SHIN, ANKLE_Z = 0.46, 0.44, 0.08
HIP_REST = ANKLE_Z + THIGH + SHIN   # 0.98: the rig is built with the leg straight (the bones have the right length)
HIP_Z = 0.92           # hip height while walking: below HIP_REST, so the knee always bends a little
BOB = 0.03             # how far the hip drops at the "down"
LIFT = 0.12            # maximum foot height in the swing
POLE_ANGLE = math.radians(90)   # measured: with vertical bones and roll 0, +90° turns the knee toward the pole (-90° inverts)


def build_rig():
    """Armature created in EDIT mode (works in background: an active object in the view_layer is enough)."""
    arm = bpy.data.armatures.new("Walker")
    rig = bpy.data.objects.new("Walker", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones

    def bone(name, head, tail, parent=None, connect=False):
        b = eb.new(name)
        b.head, b.tail, b.roll = head, tail, 0.0
        if parent:
            b.parent, b.use_connect = eb[parent], connect

    bone("Root", (0, 0, 0), (0, 0.3, 0))                         # walks along the ground (points +Y: axes = world)
    bone("Pelvis", (0, 0, HIP_REST), (0, 0, HIP_REST + 0.2), "Root")   # rises/falls, rotates
    bone("Chest", (0, 0, HIP_REST + 0.2), (0, 0, 1.8), "Pelvis", True)
    for s, x in (("L", 0.1), ("R", -0.1)):
        knee = (x, 0.02, HIP_REST - THIGH)                      # knee slightly forward: gives the bend direction
        bone(f"Thigh.{s}", (x, 0, HIP_REST), knee, "Pelvis")
        bone(f"Shin.{s}", knee, (x, 0, ANKLE_Z), f"Thigh.{s}", True)
        bone(f"Arm.{s}", (x * 2.2, 0, 1.48), (x * 2.3, 0, 0.98), "Chest")
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def box(cx, cy, z0, z1, w, d):
    v = [(cx + sx * w / 2, cy + sy * d / 2, z) for z in (z0, z1) for sy in (-1, 1) for sx in (-1, 1)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return v, f


def build_body(rig):
    """Low-poly mesh with RIGID weights: each piece 100% on one bone (vertex group named after the bone).
    It is the fail-proof path when automatic weighting (heat) finds no solution, and it suits low-poly."""
    hz = HIP_REST
    parts = [("Pelvis", box(0, 0, hz - 0.05, hz + 0.2, 0.32, 0.2)),
             ("Chest", box(0, 0, hz + 0.2, 1.56, 0.38, 0.22)),
             ("Chest", box(0, 0.01, 1.59, 1.84, 0.2, 0.22))]          # head
    for s, x in (("L", 0.1), ("R", -0.1)):
        parts += [(f"Thigh.{s}", box(x, 0.01, hz - THIGH, hz - 0.02, 0.13, 0.14)),
                  (f"Shin.{s}", box(x, 0.01, ANKLE_Z, hz - THIGH, 0.1, 0.11)),
                  (f"Shin.{s}", box(x, 0.05, 0.0, ANKLE_Z, 0.11, 0.26)),            # foot
                  (f"Arm.{s}", box(x * 2.25, 0, 0.96, 1.5, 0.09, 0.1))]
    verts, faces, owner = [], [], []
    for name, (v, f) in parts:
        base = len(verts)
        verts += v
        faces += [tuple(i + base for i in p) for p in f]
        owner += [name] * len(v)
    me = bpy.data.meshes.new("Body")
    me.from_pydata(verts, [], faces)
    mat = bpy.data.materials.new("Skin")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.45, 0.25, 1)
    me.materials.append(mat)
    body = bpy.data.objects.new("Body", me)
    bpy.context.scene.collection.objects.link(body)
    for name in set(owner):
        g = body.vertex_groups.new(name=name)
        g.add([i for i, o in enumerate(owner) if o == name], 1.0, "REPLACE")
    body.parent = rig
    body.modifiers.new("Armature", "ARMATURE").object = rig            # = parent_set(type='ARMATURE_NAME')
    return body


def empty(name, loc):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    bpy.context.scene.collection.objects.link(e)
    return e


def add_ik(rig, pole_angle=POLE_ANGLE):
    """IK on the Shin (chain_count=2 takes Shin+Thigh). Target and pole are empties animated in world space:
    the planted-foot math stays in world coordinates, with no conversion to bone space."""
    targets = {}
    for s, x in (("L", 0.1), ("R", -0.1)):
        tgt = empty(f"IK.{s}", (x, 0, ANKLE_Z))
        pole = empty(f"Pole.{s}", (x, 1.0, HIP_Z - THIGH))          # in front of the knee
        c = rig.pose.bones[f"Shin.{s}"].constraints.new("IK")
        c.target, c.pole_target, c.chain_count = tgt, pole, 2
        c.pole_angle = pole_angle
        targets[s] = (tgt, pole)
    return targets


def foot(t, offset):
    """Foot Y (world) and height at time t. Stance: still on the ground. Swing: advances one stride and rises."""
    stride = SPEED * CYCLE                         # stride = distance between two contacts of the SAME foot
    phase = t / CYCLE + offset
    c, u = math.floor(phase), phase % 1.0
    y0 = stride * (DUTY / 2 - offset)              # mid-stance falls under the hip
    if u < DUTY:
        return stride * c + y0, 0.0
    v = (u - DUTY) / (1 - DUTY)
    e = v * v * (3 - 2 * v)                        # smoothstep: the foot leaves and arrives slowly
    return stride * (c + e) + y0, LIFT * math.sin(math.pi * v)


def check_reach():
    """The leg must reach the foot at the extremes of stance; otherwise the IK stretches and the foot detaches (slides)."""
    reach = SPEED * CYCLE * DUTY / 2
    need = math.hypot(HIP_Z - BOB - ANKLE_Z, reach)
    print(f"stride {SPEED * CYCLE:.2f} m, reach {reach:.2f} m, leg needs {need:.3f} of {THIGH + SHIN:.3f} m")
    assert need < THIGH + SHIN, "leg too short for this speed: lower SPEED, raise CYCLE or lower HIP_Z"


def animate(rig, targets, f0, f1):
    pb = rig.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"
    for f in range(f0, f1 + 1):                    # key on every frame: interpolation has nothing to get wrong
        t = (f - f0) / FPS
        hip_y = SPEED * t
        u = (t / CYCLE) % 1.0
        pb["Root"].location = (0, hip_y, 0)
        pb["Root"].keyframe_insert("location", frame=f)
        # lowest ("down") right after each contact (u = 0.1 and 0.6); highest at mid-stance
        drop = (HIP_REST - HIP_Z) + BOB * 0.5 * (1 + math.cos(4 * math.pi * (u - 0.1)))
        pb["Pelvis"].location = (0, -drop, 0)                                             # local Y = world Z
        pb["Pelvis"].rotation_euler = (0, math.radians(5) * math.sin(2 * math.pi * u), 0)     # hip rotation
        pb["Chest"].rotation_euler = (0, -math.radians(9) * math.sin(2 * math.pi * u), 0)     # shoulder against hip
        for name, path in (("Pelvis", "location"), ("Pelvis", "rotation_euler"), ("Chest", "rotation_euler")):
            pb[name].keyframe_insert(path, frame=f)
        for s, off in (("L", 0.0), ("R", 0.5)):
            tgt, pole = targets[s]
            fy, lift = foot(t, off)
            tgt.location = (tgt.location.x, fy, ANKLE_Z + lift)
            tgt.keyframe_insert("location", frame=f)
            pole.location = (pole.location.x, hip_y + 1.0, HIP_Z - THIGH)
            pole.keyframe_insert("location", frame=f)
            swing = (fy - hip_y) / (THIGH + SHIN)                  # arm goes back when the foot goes forward
            pb[f"Arm.{s}"].rotation_euler = (-0.9 * swing, 0, 0)
            pb[f"Arm.{s}"].keyframe_insert("rotation_euler", frame=f)


def measure_slide(rig, f0, f1):
    """Ankle slide (Shin tail, evaluated pose) between consecutive frames with the foot in stance."""
    sc = bpy.context.scene
    worst, prev = 0.0, {}
    knee_ahead = True
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        t = (f - f0) / FPS
        for s, off in (("L", 0.0), ("R", 0.5)):
            pose = rig.pose.bones
            ankle = rig.matrix_world @ pose[f"Shin.{s}"].tail
            hip = rig.matrix_world @ pose[f"Thigh.{s}"].head
            knee = rig.matrix_world @ pose[f"Shin.{s}"].head
            mid = (hip + ankle) / 2
            knee_ahead &= knee.y > mid.y and abs(knee.x - hip.x) < 0.02   # knee forward, never backward or sideways
            stance = foot(t, off)[1] == 0.0
            if stance and prev.get(s, (None, False))[1]:
                worst = max(worst, (ankle.xy - prev[s][0].xy).length)
            prev[s] = (ankle.copy(), stance)
    print(f"max slide in stance: {worst * 1000:.2f} mm | knee always forward: {knee_ahead}")
    return worst


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = args[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.frame_start, sc.frame_end = FPS, 1, 66
    check_reach()
    rig = build_rig()
    build_body(rig)
    targets = add_ik(rig)
    animate(rig, targets, 1, 66)
    measure_slide(rig, 1, 66)
    if "--render" in args:
        import render_setup                       # camera, light and ground (file next to this one)
        render_setup.side_view(sc, center=(0, SPEED * 1.1, 0.9), dist=6)
        sc.render.filepath = os.path.join(out, "walk_")
        bpy.ops.render.render(animation=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "walk.blend"))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
