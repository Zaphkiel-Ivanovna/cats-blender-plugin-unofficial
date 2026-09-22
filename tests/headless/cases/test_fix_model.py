# GPL License
"""Fix Model over a set of armature shapes that drive different branches."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
import _models
from _harness import check, done, enable

enable()

FULL_SPINE = {"Hips", "Spine", "Neck", "Head"}

EXPECTED_BONES = {
    "mmd_raw": FULL_SPINE,
    "with_twist_bones": FULL_SPINE,
    "twist_bones_kept": FULL_SPINE,
    "two_spines": FULL_SPINE | {"Chest"},
    "three_spines": FULL_SPINE | {"Chest", "Upper Chest"},
    "no_spine": {"Hips"},
    "already_clean": FULL_SPINE,
}


def geometry(mesh):
    uvs = []
    for layer in mesh.data.uv_layers:
        flat = np.empty(len(layer.data) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", flat)
        uvs.append(flat)
    return {
        "vertices": len(mesh.data.vertices),
        "polygons": len(mesh.data.polygons),
        "nan_uvs": int(np.isnan(np.concatenate(uvs)).sum()) if uvs else 0,
        "slots": [s.material.name if s.material else "" for s in mesh.material_slots],
    }


for name, build in _models.ALL.items():
    armature = build()
    meshes_before = [o for o in bpy.data.objects if o.type == "MESH"]
    vertices_before = sum(len(o.data.vertices) for o in meshes_before)
    bpy.context.view_layer.objects.active = armature

    try:
        result = bpy.ops.cats_armature.fix()
    except RuntimeError as e:
        result = f"RuntimeError: {e}"

    if not meshes_before:
        check(f"{name}: refused without a mesh", str(result).startswith("RuntimeError"), True)
        continue

    check(f"{name}: finished", result, {"FINISHED"})

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    check(f"{name}: one mesh after the join", len(meshes), 1)
    mesh = meshes[0]
    state = geometry(mesh)

    check(f"{name}: no vertex lost", state["vertices"], vertices_before)
    check(f"{name}: no NaN uv left", state["nan_uvs"], 0)
    check(f"{name}: material slots sorted", state["slots"], sorted(state["slots"]))

    bones = {b.name for b in armature.data.bones}
    check(f"{name}: core bones renamed", sorted(EXPECTED_BONES[name] - bones), [])

    if mesh.data.shape_keys:
        blocks = [k.name for k in mesh.data.shape_keys.key_blocks]
        check(f"{name}: shape keys have unique names", len(set(blocks)), len(blocks))
        vrc = [b for b in blocks if b.startswith("vrc.")]
        if vrc:
            first = blocks.index(vrc[0])
            check(f"{name}: vrc keys grouped at the front", blocks[first:first + len(vrc)], vrc)

done()
