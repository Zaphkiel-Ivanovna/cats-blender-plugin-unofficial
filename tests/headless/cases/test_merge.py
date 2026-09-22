# GPL License
"""Merge Armatures cleans up the merged meshes only, and keeps main-bone groups."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, module
from _models import SPINE_CHAIN, _limbs, add_mesh, build_armature, clear

enable()
bones = module("tools.armature_bones")
clear()

base = build_armature(SPINE_CHAIN + _limbs(), "Base")
body = add_mesh(base, "Body", seed=1)

outfit = build_armature(SPINE_CHAIN, "Outfit")
add_mesh(outfit, "Jacket", subdivisions=2, seed=2)

other = build_armature(SPINE_CHAIN, "Other")
bystander = add_mesh(other, "Bystander", subdivisions=2, seed=3)
bystander.vertex_groups.new(name="KeptForLater")

main_bone = next(n for n in bones.dont_delete_these_main_bones if n not in body.vertex_groups)
body.vertex_groups.new(name=main_bone)
body.vertex_groups.new(name="TrulyUnused")

scene = bpy.context.scene
scene.merge_armature_into = "Base"
scene.merge_armature = "Outfit"
scene.merge_armatures_remove_zero_weight_bones = True
scene.merge_armatures_join_meshes = True

bpy.ops.object.select_all(action='DESELECT')
result = bpy.ops.cats_custom.merge_armatures()

merged = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == base]
groups = {g.name for m in merged for g in m.vertex_groups}

check("merge finished", result, {'FINISHED'})
check("the outfit armature is gone", "Outfit" in bpy.data.objects, False)
check("one merged mesh", len(merged), 1)
check("an empty main-bone group survives", main_bone in groups, True)
check("an empty ordinary group is removed", "TrulyUnused" in groups, False)
check("a mesh of an unrelated armature is left alone",
      "KeptForLater" in bpy.data.objects["Bystander"].vertex_groups, True)
done()
