# GPL License
"""Assumptions this add-on makes about the Blender API."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done

check("MESH_MT_shape_key_context_menu exists",
      hasattr(bpy.types, "MESH_MT_shape_key_context_menu"), True)
check("extension_path_user exists", hasattr(bpy.utils, "extension_path_user"), True)

prop = bpy.props.PointerProperty(type=bpy.types.Object)
check("bpy.props returns _PropertyDeferred", type(prop).__name__, "_PropertyDeferred")
check("_PropertyDeferred exposes .function", prop.function is bpy.props.PointerProperty, True)
check("_PropertyDeferred exposes .keywords", prop.keywords.get("type") is bpy.types.Object, True)

# shape_key_move('TOP') targets index 1 and never displaces the reference key.
# tools.common.sort_shape_keys depends on exactly this.
bpy.ops.mesh.primitive_cube_add()
ob = bpy.context.object
for name in ("Basis", "A", "B", "C"):
    ob.shape_key_add(name=name, from_mix=False)
blocks = ob.data.shape_keys.key_blocks
ob.active_shape_key_index = blocks.find("C")
bpy.ops.object.shape_key_move(type="TOP")
check("TOP moves to index 1", [k.name for k in blocks].index("C"), 1)
check("the reference key stays at index 0", blocks[0].name, "Basis")
ob.active_shape_key_index = 0
check("TOP on the reference key is refused",
      "CANCELLED" in bpy.ops.object.shape_key_move(type="TOP"), True)

done()
