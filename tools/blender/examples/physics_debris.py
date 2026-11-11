"""Tested example (Blender 5.2.2, background): debris with rigid body + dust with particles.

  blender -b --factory-startup -P tools/blender/examples/physics_debris.py -- <output_folder> [--render]

Measured:
- bpy.ops.ptcache.bake_all(bake=True) works WITHOUT a window and without an override (point_cache.is_baked = True);
- bpy.ops.rigidbody.object_add needs the object in context -> temp_override(object=..., active_object=...);
- bpy.ops.rigidbody.bake_to_keyframes FAILS in background (it calls anim.keyframe_insert_by_name, whose poll
  requires a window) -> convert by hand: read matrix_world frame by frame, remove the world and write keys;
- particles WITHOUT bake give wrong positions when frame_set skips frames (which is what --stills do):
  mean z 0.29 m at frame 28 and 0.02 m at 35. With bake_all, any order gives the same result.
- particles render_type='OBJECT' render in Eevee (80 instances in the depsgraph and in the PNG).
"""
import os
import random
import sys

import bmesh
import bpy


def box_mesh(name, s):
    me = bpy.data.meshes.new(name)
    v = [(x * s, y * s, z * s) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    me.from_pydata(v, [], [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
    return me


def add_body(obj, kind="ACTIVE", shape="BOX", mass=1.0):
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.rigidbody.object_add(type=kind)
    obj.rigid_body.collision_shape = shape            # BOX/SPHERE/CONVEX_HULL: stable; MESH only for passive bodies
    obj.rigid_body.mass = mass
    obj.rigid_body.friction, obj.rigid_body.restitution = 0.8, 0.2


def debris(scene, ground, count=12, f_end=60):
    bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.point_cache.frame_start, world.point_cache.frame_end = 1, f_end
    add_body(ground, "PASSIVE", "MESH")
    rnd = random.Random(3)
    pieces = []
    for i in range(count):
        o = bpy.data.objects.new(f"Debris{i}", box_mesh(f"Debris{i}", rnd.uniform(0.1, 0.25)))
        o.location = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), 2 + i * 0.4)
        o.rotation_euler = [rnd.uniform(0, 3) for _ in range(3)]
        scene.collection.objects.link(o)
        add_body(o, mass=2.0)
        pieces.append(o)
    print("bake_all:", bpy.ops.ptcache.bake_all(bake=True), "| is_baked:", world.point_cache.is_baked)
    return pieces


def physics_to_keys(scene, objects, f0, f1):
    """Replaces the simulation with keys (editable, combinable with other animations, no cache to invalidate)."""
    track = {o.name: [] for o in objects}
    for f in range(f0, f1 + 1):
        scene.frame_set(f)                                   # baked cache: it can skip frames without error
        for o in objects:
            track[o.name].append(o.matrix_world.copy())
    with bpy.context.temp_override(scene=scene):
        bpy.ops.rigidbody.world_remove()
    for o in objects:
        prev = None
        for f, m in enumerate(track[o.name], start=f0):
            loc, rot, _ = m.decompose()
            e = rot.to_euler("XYZ", prev) if prev else rot.to_euler("XYZ")   # compatible euler: no 360° spin
            o.location, o.rotation_euler = loc, e
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
            prev = e


def dust(scene, center, f_start, f_end):
    """Dust cloud: face emitter that releases translucent icospheres (render_type OBJECT)."""
    puff_me = bpy.data.meshes.new("Puff")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.to_mesh(puff_me)
    bm.free()
    mat = bpy.data.materials.new("Dust")
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.6, 0.5, 0.4, 1)
    bsdf.inputs["Alpha"].default_value = 0.5
    mat.surface_render_method = "BLENDED"                    # translucent in Eevee
    puff_me.materials.append(mat)
    puff = bpy.data.objects.new("Puff", puff_me)
    puff.location = (0, 0, -100)                             # the model stays out of frame
    scene.collection.objects.link(puff)

    x, y, z = center
    em_me = bpy.data.meshes.new("DustEmitter")
    em_me.from_pydata([(x - 1, y - 1, z), (x + 1, y - 1, z), (x + 1, y + 1, z), (x - 1, y + 1, z)], [], [(0, 1, 2, 3)])
    em = bpy.data.objects.new("DustEmitter", em_me)
    scene.collection.objects.link(em)
    ps = em.modifiers.new("Dust", "PARTICLE_SYSTEM").particle_system.settings
    ps.count, ps.frame_start, ps.frame_end, ps.lifetime = 80, f_start, f_end, 40
    ps.emit_from, ps.normal_factor, ps.factor_random = "FACE", 1.5, 1.0
    ps.effector_weights.gravity = 0.05                       # dust barely falls
    ps.render_type, ps.instance_object = "OBJECT", puff
    ps.particle_size, ps.size_random = 0.15, 0.6
    em.show_instancer_for_render = False                     # the emitter plane does not show
    bpy.ops.ptcache.bake_all(bake=True)                      # WITHOUT this, out-of-order frame_set gets the dust wrong
    return em


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = args[0]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render_setup
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 60
    render_setup.side_view(sc, center=(0, 0, 1), dist=9)
    pieces = debris(sc, bpy.data.objects["Ground"])
    physics_to_keys(sc, pieces, 1, 60)
    em = dust(sc, (0, 0, 0.02), 20, 26)
    for f in (50, 35, 28, 35):                               # out of order, on purpose
        sc.frame_set(f)
        psys = em.evaluated_get(bpy.context.evaluated_depsgraph_get()).particle_systems[0]
        alive = [p for p in psys.particles if p.alive_state == "ALIVE"]
        print(f"frame {f}: {len(alive)} alive, mean z {sum(p.location.z for p in alive) / max(1, len(alive)):.3f}")
    if "--render" in args:
        sc.frame_set(35)
        sc.render.filepath = os.path.join(out, "debris_035.png")
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "debris.blend"))


if __name__ == "__main__":
    main()
