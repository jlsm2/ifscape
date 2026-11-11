"""Set for the bacteria-disappeared script: the farm, the landscape and the cell. Builds everything and returns the pieces to animate.

Axes: house at the origin with the porch facing +y; barn from y 16 to 28 (doors at front and back);
manure pen behind the barn; pasture fence at y 40; cornfield to the east; hillock to the northwest;
the terrain slopes down to the north until the sea. The cell sits far away, underground (z -500).
"""

import math
import random
from types import SimpleNamespace

import bpy
from mathutils import Vector

import cell_models as cm
import farm_animals as fa
import farm_buildings as fb
import kit
import land
from kit import flat

BARN_Y0, BARN_LEN = 16.0, 12.0
COWS_Y = (18.0, 20.5, 23.0)
COW_X = -3.2
BAY = (5.0, 32.0)
CELL = Vector((0.0, 0.0, -500.0))
HERO_MITO = Vector((-14.0, -6.0, -2.0))    # mitochondrion in cross-section, relative to the cell (away from the nucleus and the reticulum)


def rumen(cow):
    """Rumen (the big stomach) inside the cow: pinkish sac with still chewed grass on top.
    Everything is a child of an Empty at the center of the belly (it is what grows in scene 05, without leaving its place).
    Only shows when the cow's body becomes transparent."""
    root = bpy.data.objects.new("RumenRoot", None)
    bpy.context.collection.objects.link(root)
    root.parent, root.location = cow.root, (-0.05, 0.0, 1.0)
    sac = kit.mesh_object("Rumen", *kit._ico_geo(1.0, (0, 0, 0), (0.42, 0.24, 0.27))[:2], [flat("Rumen", "#C98A7A")])
    sac.parent = root
    rnd = random.Random(11)
    grass = flat("ChewedGrass", "#6E7F3A")
    for _ in range(14):
        a = rnd.uniform(0, math.tau)
        p = (math.cos(a) * 0.3, math.sin(a) * 0.14, rnd.uniform(0.12, 0.24))
        kit.mesh_object("Chewed", *kit._ico_geo(1.0, p, (0.07, 0.05, 0.035))[:2], [grass]).parent = root
    return root


def xray_materials(cow):
    """Copies the materials of the front cow's body (the others do not change) and leaves the alpha animatable."""
    sockets = []
    for i, mat in enumerate(cow.body.data.materials):
        m = mat.copy()
        m.surface_render_method = "BLENDED"
        cow.body.data.materials[i] = m
        sockets.append(kit.principled(m).inputs["Alpha"])
    return sockets


def build_farm(rnd):
    win = flat("HouseWin", "#2A2410", emission=kit.LUZ, strength=3.0)
    house = fb.house(0, -2, win)
    barn = fb.barn(0, BARN_Y0, length=BARN_LEN, rnd=rnd)
    trough = fb.trough("Trough", -4.6, 17.0, 25.0)
    cows = [fa.cow(f"Cow{i}", (COW_X, y, 0), heading=math.pi) for i, y in enumerate(COWS_Y)]
    fb.fence("FenceNorth", [(-8, 40), (40, 40)])
    fb.fence("FenceEast", [(14, 4), (14, 39.5)])
    fb.round_bale("Bale", (8, 10, 0), 0.4)
    fb.round_bale("Bale2", (9.6, 11.4, 0), 1.2)
    bay = fb.manure_bay(*BAY, rnd)
    fb.silo(-9.5, 21)
    mill = fb.windmill(-16, 6)
    return SimpleNamespace(house=house, barn=barn, trough=trough, cows=cows, bay=bay, mill=mill,
                           rumen=rumen(cows[0]), xray=xray_materials(cows[0]))


def build_land(rnd):
    grass = flat("Grass", land.GRASS)
    ground = land.terrain(grass)
    land.ocean()
    leaves = land.autumn_materials(6, rnd)
    trunk = flat("Trunk", land.TRUNK)
    kx, ky, _, kr = land.KNOLL
    keep = [(30, 420, 0, 260), (kx - kr, kx + kr, ky - kr, ky + kr)]
    land.far_forest(rnd, leaves, trunk, keep_out=keep)
    near = []
    while len(near) < 16:
        x, y = rnd.uniform(-2, 44), rnd.uniform(70, 98)
        if math.hypot(x - kx, y - ky) > kr + 2:
            near.append(land.near_tree(f"Tree{len(near)}", (x, y), rnd, leaves, trunk))
    knoll_cover(rnd, leaves, grass)
    corn = land.cornfield(rnd)
    plant = land.fertilizer_plant(230, 95, rnd)
    return SimpleNamespace(grass=kit.principled(grass).inputs["Base Color"], ground=ground, leaves=leaves,
                           near=near, corn=corn, plant=plant)


def knoll_cover(rnd, leaves, grass):
    """Bushes and grass tufts on top of the hillock, in front of the camera (scenes 09 to 11): the ground stops being
    a smooth slab. They use the animated canopy and grass materials, so they yellow and dry together."""
    kx, ky, _, _ = land.KNOLL
    tufts = []
    for _ in range(140):
        a, r = rnd.uniform(-1.2, 1.2) + math.pi / 2, rnd.uniform(4.0, 18.0)       # fan toward the north
        x, y = kx + math.cos(a) * r, ky + 6 + math.sin(a) * r
        z = land.ground_z(x, y)
        if rnd.random() < 0.3:
            v, f = kit._ico_geo(1.0, (x, y, z + 0.12), (rnd.uniform(0.25, 0.45), rnd.uniform(0.25, 0.45), 0.25))
            kit.mesh_object("Bush", v, f, [rnd.choice(leaves).mat])
        else:
            for k in range(4):
                b = rnd.uniform(0, math.tau)
                tip = (x + math.cos(b) * 0.18, y + math.sin(b) * 0.18, z + rnd.uniform(0.35, 0.6))
                tufts.append(([(x - 0.04, y, z), (x + 0.04, y, z), tip], [(0, 1, 2)]))
    v, f, _ = kit.merge(*tufts)
    kit.mesh_object("Tufts", v, f, [grass])


def build_cell(rnd):
    hero_world = CELL + HERO_MITO
    path = (HERO_MITO + Vector((0, -14, 2.5)), HERO_MITO, HERO_MITO + Vector((-1, -5, 2.4)))   # camera path
    cell = cm.cell_interior(tuple(CELL), rnd=rnd, keep_clear=path)
    hero = cm.mitochondrion("HeroMito", tuple(hero_world), rotation=(0, 0, math.radians(20)), rnd=rnd)
    return SimpleNamespace(cell=cell, hero=hero)


def build(rnd):
    return SimpleNamespace(farm=build_farm(rnd), land=build_land(rnd), cell=build_cell(rnd))
