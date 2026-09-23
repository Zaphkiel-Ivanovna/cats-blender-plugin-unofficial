# GPL License
"""A PMX written by the bundled mmd_tools imports through CATS and survives Fix Model."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable
from _models import SPINE_CHAIN, _limbs, add_mesh, build_armature, clear

enable()
clear()
armature = build_armature(SPINE_CHAIN + _limbs(), "Armature")
mesh = add_mesh(armature, "Body", subdivisions=2, shape_keys=3)
face_count = len(mesh.data.polygons)
bone_count = len(armature.data.bones)

bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
mesh.select_set(True)
bpy.context.view_layer.objects.active = armature
check("converts to an MMD model", bpy.ops.mmd_tools_local.convert_to_mmd_model(), {'FINISHED'})
root = next(o for o in bpy.data.objects if getattr(o, "mmd_type", "") == 'ROOT')

folder = tempfile.mkdtemp()
path = os.path.join(folder, "model.pmx")
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = root
root.select_set(True)
check("exports a PMX", bpy.ops.mmd_tools_local.export_pmx(filepath=path), {'FINISHED'})
check("the PMX is on disk", os.path.getsize(path) > 0, True)

clear()
result = bpy.ops.cats_importer.import_any_model(directory=folder, files=[{"name": "model.pmx"}])
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
check("CATS imports it", result, {'FINISHED'})
check("with one armature", len(arms), 1)
check("with every bone", len(arms[0].data.bones) if arms else 0, bone_count)
check("and every face", sum(len(m.data.polygons) for m in meshes), face_count)

check("Fix Model runs on it", bpy.ops.cats_armature.fix(), {'FINISHED'})
check("and leaves one mesh", len([o for o in bpy.data.objects if o.type == 'MESH']), 1)
done()
