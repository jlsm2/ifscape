"""Tested example (Blender 5.2.2, background): scatter trees and grass with Geometry Nodes, built by script.

  blender -b --factory-startup -P tools/blender/examples/scatter_gn.py -- <output_folder> [--render]

A single object (the terrain) carries thousands of instances. Compared with thousands of objects (kit.instance), the
scene builds in a fraction of the time, the .blend stays small and Eevee draws the instances in batches.
Trees live in a collection excluded from the render; Collection Info with "Separate Children" + "Pick Instance"
picks a model per point. The density can come from a vertex group (here, "forest": zero on the path).
"""
import math
import os
import sys
import time

import bpy


def tree_variants(col):
    """Three low-poly trees (trunk + conical crown) in a collection that does NOT render (it only serves as a model)."""
    import bmesh
    for k, (h, r) in enumerate(((3.0, 1.1), (4.2, 1.3), (2.4, 0.9))):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.15, radius2=0.12, depth=h * 0.4)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h * 0.2))
        top = bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=r, radius2=0.0, depth=h * 0.75)
        bmesh.ops.translate(bm, verts=top["verts"], vec=(0, 0, h * 0.4 + h * 0.375))
        me = bpy.data.meshes.new(f"Tree{k}")
        bm.to_mesh(me)
        bm.free()
        mat = bpy.data.materials.new(f"Leaf{k}")
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.25 + 0.05 * k, 0.1, 1)
        me.materials.append(mat)
        o = bpy.data.objects.new(f"Tree{k}", me)
        col.objects.link(o)                       # origin at the tree's base: the instance is born on the ground


def terrain(size=60, n=60):
    """Grid with gentle relief and a "forest" vertex group (weight 0 on the middle path)."""
    verts = []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = size * (i / n - 0.5), size * (j / n - 0.5)
            verts.append((x, y, 0.6 * math.sin(x * 0.15) * math.cos(y * 0.12)))
    faces = [(j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i)
             for j in range(n) for i in range(n)]
    me = bpy.data.meshes.new("Terrain")
    me.from_pydata(verts, [], faces)
    mat = bpy.data.materials.new("Grass")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.2, 0.08, 1)
    me.materials.append(mat)
    obj = bpy.data.objects.new("Terrain", me)
    bpy.context.scene.collection.objects.link(obj)
    g = obj.vertex_groups.new(name="forest")
    for v in me.vertices:
        g.add([v.index], min(1.0, max(0.0, (abs(v.co.x) - 3) / 4)), "REPLACE")   # path at x ~ 0
    return obj


def scatter_group(name, collection, density, seed, scale=(0.7, 1.3)):
    """Node group: Distribute Points on Faces -> Instance on Points (collection) -> Join with the terrain."""
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.is_modifier = True                                         # shows up as a modifier
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    dens = ng.interface.new_socket("Density Mask", in_out="INPUT", socket_type="NodeSocketFloat")
    dens.default_value = 1.0
    N, L = ng.nodes, ng.links
    gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")

    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"                            # no trees stuck together
    dist.inputs["Distance Min"].default_value = 1.6
    dist.inputs["Density Max"].default_value = density
    dist.inputs["Seed"].default_value = seed
    L.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    L.new(gin.outputs["Density Mask"], dist.inputs["Density Factor"])

    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = collection
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True

    rnd_rot = N.new("FunctionNodeRandomValue"); rnd_rot.data_type = "FLOAT_VECTOR"
    rnd_rot.inputs["Max"].default_value = (0, 0, 2 * math.pi)     # rotates only on Z (tree stays upright)
    rnd_rot.inputs["Seed"].default_value = seed + 1
    rnd_sc = N.new("FunctionNodeRandomValue"); rnd_sc.data_type = "FLOAT"
    rnd_sc.inputs["Min"].default_value, rnd_sc.inputs["Max"].default_value = scale
    rnd_sc.inputs["Seed"].default_value = seed + 2

    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True              # one child of the collection per point
    L.new(dist.outputs["Points"], inst.inputs["Points"])
    L.new(info.outputs["Instances"], inst.inputs["Instance"])
    L.new(rnd_rot.outputs["Value"], inst.inputs["Rotation"])
    L.new(rnd_sc.outputs["Value"], inst.inputs["Scale"])

    join = N.new("GeometryNodeJoinGeometry")
    L.new(gin.outputs["Geometry"], join.inputs["Geometry"])        # the terrain keeps showing
    L.new(inst.outputs["Instances"], join.inputs["Geometry"])
    L.new(join.outputs["Geometry"], gout.inputs["Geometry"])
    return ng


def add_scatter(obj, ng, vertex_group=None):
    mod = obj.modifiers.new(ng.name, "NODES")
    mod.node_group = ng
    if vertex_group:                                                # connects the vertex group to the "Density Mask" input
        set_input(mod, "Density Mask", attribute=vertex_group)
    return mod


def set_input(mod, socket_name, value=None, attribute=None):
    """Node modifier input in Blender 5.x: mod.properties.inputs.<Socket_N> with .value, .type
    ('VALUE' or 'ATTRIBUTE') and .attribute_name. The old way (mod["Socket_1"], mod["Socket_1_use_attribute"])
    gives 'TypeError: id properties not supported' in 5.2."""
    ident = next(i.identifier for i in mod.node_group.interface.items_tree
                 if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == socket_name)
    entry = getattr(mod.properties.inputs, ident)
    if attribute is not None:
        entry.type, entry.attribute_name = "ATTRIBUTE", attribute
    else:
        entry.type, entry.value = "VALUE", value


def count_instances(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    return sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == obj)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = args[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    t0 = time.time()
    trees = bpy.data.collections.new("TreeModels")
    sc.collection.children.link(trees)
    bpy.context.view_layer.layer_collection.children["TreeModels"].exclude = True   # models out of the render
    tree_variants(trees)
    ground = terrain()
    add_scatter(ground, scatter_group("Forest", trees, density=0.25, seed=7), vertex_group="forest")
    n = count_instances(ground)
    print(f"instances: {n} in {time.time() - t0:.2f}s (a single object)")
    if "--render" in args:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import render_setup
        cam = render_setup.side_view(sc, center=(0, 0, 1.5), dist=26)
        bpy.data.objects.remove(bpy.data.objects["Ground"])
        cam.location.z = 7
        sc.render.filepath = os.path.join(out, "scatter.png")
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "scatter.blend"))


if __name__ == "__main__":
    main()
