# GPL License
"""The eye tracking shape repair walks shape layers by name and only nudges vrc.* keys."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, module
from _models import SPINE_CHAIN, add_mesh, build_armature, clear

enable()
eyes = module("tools.eyetracking")


def snapshot(mesh):
    return {k.name: [tuple(p.co) for p in k.data] for k in mesh.data.shape_keys.key_blocks}


def moved(before, after, name):
    return sum(a != b for a, b in zip(before[name], after[name], strict=True))


def fresh():
    clear()
    arm = build_armature(SPINE_CHAIN, "Armature")
    mesh = add_mesh(arm, "Body", subdivisions=1)
    mesh.shape_key_add(name="Basis", from_mix=False)
    mesh.shape_key_add(name="vrc.blink_left", from_mix=False)
    mesh.shape_key_add(name="custom_smile", from_mix=False)
    return mesh


mesh = fresh()
before = snapshot(mesh)
error = None
try:
    eyes.repair_shapekeys_mouth(mesh.name)
except Exception as e:
    error = f"{type(e).__name__}: {e}"
after = snapshot(bpy.data.objects["Body"])
check("repair_shapekeys_mouth runs", error, None)
check("it nudges the vrc key", moved(before, after, "vrc.blink_left") > 0, True)
check("it leaves other keys alone", moved(before, after, "custom_smile"), 0)
check("and the basis", moved(before, after, "Basis"), 0)

mesh = fresh()
group = mesh.vertex_groups.new(name="LeftEye")
group.add([0], 1.0, 'REPLACE')
before = snapshot(mesh)
error = None
try:
    eyes.repair_shapekeys(mesh.name, "LeftEye")
except Exception as e:
    error = f"{type(e).__name__}: {e}"
after = snapshot(bpy.data.objects["Body"])
check("repair_shapekeys runs", error, None)
check("it nudges one vertex of the vrc key", moved(before, after, "vrc.blink_left"), 1)
check("it leaves other keys alone", moved(before, after, "custom_smile"), 0)
done()
