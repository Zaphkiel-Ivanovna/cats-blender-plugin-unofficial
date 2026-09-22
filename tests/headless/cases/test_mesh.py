# GPL License
"""Regressions in the mesh helpers, each one a bug that shipped."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from _harness import check, clear_scene, done, enable, module

enable()
Common = module("tools.common")

# get_meshes_objects(visible_only=True) used to filter a list while walking it,
# so it let every second hidden mesh through.
clear_scene()
armature_data = bpy.data.armatures.new("A")
armature = bpy.data.objects.new("A", armature_data)
bpy.context.collection.objects.link(armature)
for i in range(6):
    bpy.ops.mesh.primitive_cube_add()
    mesh = bpy.context.object
    mesh.name = f"m{i}"
    mesh.parent = armature
    if i < 4:
        mesh.hide_set(True)
visible = Common.get_meshes_objects(armature_name=armature.name, mode=0,
                                    check=False, visible_only=True)
check("visible_only returns no hidden mesh", [o.name for o in visible if Common.is_hidden(o)], [])
check("visible_only returns every visible mesh", len(visible), 2)

# sort_material_slots must be stable, keep each face on its own material,
# and be a no-op the second time.
clear_scene()
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4)
ob = bpy.context.object
for name in ("zeta", "alpha", "mu", "beta"):
    ob.data.materials.append(bpy.data.materials.new(name))
indices = np.array([i % 4 for i in range(len(ob.data.polygons))], dtype=np.int32)
ob.data.polygons.foreach_set("material_index", indices)


def face_materials(obj):
    idx = np.empty(len(obj.data.polygons), dtype=np.int32)
    obj.data.polygons.foreach_get("material_index", idx)
    names = [s.material.name if s.material else None for s in obj.material_slots]
    return [names[i] for i in idx]


before = face_materials(ob)
Common.sort_material_slots(ob)
check("every face keeps its material", face_materials(ob), before)
check("slots come out name-sorted",
      [s.material.name for s in ob.material_slots], sorted(m.name for m in ob.data.materials))
once = [s.material.name for s in ob.material_slots]
Common.sort_material_slots(ob)
check("sorting twice changes nothing", [s.material.name for s in ob.material_slots], once)

# can_remove_shapekey: a key identical to its relative can go, a moved one cannot.
clear_scene()
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3)
ob = bpy.context.object
ob.shape_key_add(name="Basis", from_mix=False)
same = ob.shape_key_add(name="same", from_mix=False)
moved = ob.shape_key_add(name="moved", from_mix=False)
moved.data[3].co.z += 0.01
check("an identical shape key is removable", Common.can_remove_shapekey(same), True)
check("a moved shape key is kept", Common.can_remove_shapekey(moved), False)

# NaN UVs are repaired across the whole layer, final loop included.
uv = ob.data.uv_layers.new(name="UVTest")
count = len(uv.data)
for i in (0, count // 2, count - 1):
    uv.data[i].uv = (float("nan"), float("nan"))
flat = np.empty(count * 2, dtype=np.float32)
uv.data.foreach_get("uv", flat)
check("NaNs are seeded, last loop included", int(np.isnan(flat).sum()), 6)
mask = np.isnan(flat)
flat[mask] = 0.0
uv.data.foreach_set("uv", flat)
uv.data.foreach_get("uv", flat)
check("no NaN survives the repair", int(np.isnan(flat).sum()), 0)

done()
