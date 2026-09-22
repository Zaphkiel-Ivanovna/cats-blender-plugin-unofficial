# GPL License
"""Operators that fail cleanly: they cancel and say why instead of raising."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, module
from _models import build_armature, clear

enable()
manual = module("tools.armature_manual")


def run_execute(cls, **props):
    reports = []
    fake = SimpleNamespace(report=lambda level, message: reports.append((sorted(level), message)), **props)
    return cls.execute(fake, bpy.context), reports


def ops_error(call):
    try:
        return call(), None
    except RuntimeError as e:
        return None, str(e).strip()


clear()
build_armature([
    ("Hips", None, (0, 0, 0.9), (0, 0, 1.1)),
    ("Spine", "Hips", (0, 0, 1.1), (0, 0, 1.3)),
    ("Chest", "Spine", (0, 0, 1.3), (0, 0, 1.45)),
    ("Neck", "Chest", (0, 0, 1.45), (0, 0, 1.55)),
    ("Head", "Neck", (0, 0, 1.55), (0, 0, 1.75)),
    ("TailBase", "Hips", (0, 0.1, 0.9), (0, 0.3, 0.8)),
], "Armature")
result, reports = run_execute(manual.ConvertToValveButton, armature_name="")
names = {b.name for b in bpy.data.objects["Armature"].data.bones}
check("convert to valve finishes", result, {'FINISHED'})
check("standard bones are renamed", {"ValveBiped.Bip01_Pelvis", "ValveBiped.Bip01_Head1"} <= names, True)
check("one warning, with the count filled in", reports,
      [(["WARNING"], "Failed to translate 1 bones! Make sure your model has standard bone names!")])

clear()
build_armature([("Hips", None, (0, 0, 0.9), (0, 0, 1.1)), ("Spine", "Hips", (0, 0, 1.1), (0, 0, 1.3))], "Armature")
result, reports = run_execute(manual.ConvertToValveButton, armature_name="")
check("a clean conversion says so, and nothing else", reports, [(["INFO"], "Converted all bones to Valve names!")])

clear()
arm = build_armature([
    ("Thigh_L", None, (0.1, 0, 0.9), (0.1, 0, 0.5)),
    ("Calf_L", "Thigh_L", (0.1, 0, 0.5), (0.1, 0, 0.1)),
    ("Thigh_R", None, (-0.1, 0, 0.9), (-0.1, 0, 0.5)),
    ("Calf_R", "Thigh_R", (-0.1, 0, 0.5), (-0.1, 0, 0.1)),
], "Legs")
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.armature.select_all(action='DESELECT')
for name in ("Thigh_L", "Thigh_R"):
    arm.data.edit_bones[name].select = True
bones_before = sorted(b.name for b in arm.data.edit_bones)
result, error = ops_error(bpy.ops.armature.createdigitigradelegs)
check("digitigrade on a short chain reports an error, not a traceback",
      error, "Error: Bone format incorrect! Please select a chain of 4 continuous bones!")
check("and leaves the armature untouched", sorted(b.name for b in arm.data.edit_bones), bones_before)
bpy.ops.object.mode_set(mode='OBJECT')

clear()
build_armature([("Hips", None, (0, 0, 0.9), (0, 0, 1.1))], "Armature")
result, error = ops_error(lambda: bpy.ops.cats_importer.export_gmod_addon(
    steam_library_path="/nonexistent/", gmod_model_name="Probe"))
check("gmod export without Source Tools returns a valid result", error is None or "NoneType" not in error, True)
check("and cancels", result, {'CANCELLED'})
done()
