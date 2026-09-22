# GPL License
"""Apply Shape Key as Basis, and the states it has to refuse.

Replaces tests/shapekeys/shape_key_to_basis.test.py, which could no longer run:
it imported version_2_79_or_older, gone from the codebase, and needed a .blend
downloaded from Google Drive. Every guard it covered is reachable synthetically.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, clear_scene, done, enable

enable()

APPLY = "cats_shapekey.shape_key_to_basis"


def new_mesh(key_names=()):
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    mesh = bpy.context.object
    for name in key_names:
        mesh.shape_key_add(name=name, from_mix=False)
    bpy.context.view_layer.objects.active = mesh
    return mesh


def apply():
    try:
        return bpy.ops.cats_shapekey.shape_key_to_basis('EXEC_DEFAULT')
    except RuntimeError as e:
        return f"RuntimeError: {str(e)[:60]}"


def refused(result):
    return str(result).startswith("RuntimeError")


mesh = new_mesh()
check("refused with no shape key", refused(apply()), True)

mesh = new_mesh(("Basis", "key1"))
mesh.active_shape_key_index = 0
check("refused when Basis is active", refused(apply()), True)

mesh = new_mesh(("Basis", "key1"))
blocks = mesh.data.shape_keys.key_blocks
blocks["key1"].relative_key = blocks["key1"]
mesh.active_shape_key_index = blocks.find("key1")
check("refused when a key is relative to itself", refused(apply()), True)

mesh = new_mesh(("Basis", "key1", "key2"))
blocks = mesh.data.shape_keys.key_blocks
blocks["key1"].relative_key = blocks["key2"]
blocks["key2"].relative_key = blocks["key1"]
mesh.active_shape_key_index = blocks.find("key1")
check("refused on a relative-key loop", refused(apply()), True)

mesh = new_mesh(("Basis", "key1"))
blocks = mesh.data.shape_keys.key_blocks
blocks["key1"].data[0].co.z += 0.5
mesh.active_shape_key_index = blocks.find("key1")
check("applied when relative to Basis", apply(), {"FINISHED"})
names = [k.name for k in mesh.data.shape_keys.key_blocks]
check("the applied key is marked reverted", [n for n in names if n.endswith(" - Reverted")],
      ["key1 - Reverted"])

mesh.active_shape_key_index = mesh.data.shape_keys.key_blocks.find("key1 - Reverted")
check("applying again succeeds", apply(), {"FINISHED"})
names = [k.name for k in mesh.data.shape_keys.key_blocks]
check("the marker is dropped on the way back", "key1" in names, True)
check("no marker left over", [n for n in names if n.endswith(" - Reverted")], [])

done()
