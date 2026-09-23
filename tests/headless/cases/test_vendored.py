# GPL License
"""Bundled mmd_tools stays inside the add-on package and still registers in full."""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, module

enable()
package = os.environ.get("CATS_TEST_PACKAGE", "bl_ext.user_default.cats_blender_plugin")


def walk(cls, seen):
    for sub in cls.__subclasses__():
        if "mmd_tools_local" in sub.__module__:
            seen.add(f"{sub.__name__}|{getattr(sub, 'bl_idname', '')}")
        walk(sub, seen)


classes = set()
walk(bpy.types.bpy_struct, classes)
props = sorted(f"{t}.{k}" for t in ("Object", "Scene", "Material", "Bone", "PoseBone", "Armature", "Mesh")
               for k in dir(getattr(bpy.types, t)) if k.startswith("mmd"))
operators = sorted(dir(bpy.ops.mmd_tools_local))

out = os.environ.get("MMD_FINGERPRINT_OUT")
if out:
    with open(out, "w") as handle:
        json.dump({"classes": sorted(classes), "props": props, "operators": operators}, handle, indent=1)

check("no bundled folder on sys.path", [p for p in sys.path if p.rstrip("/").endswith("extern_tools")], [])
check("mmd_tools_local is not a top-level module", "mmd_tools_local" in sys.modules, False)
check("it is loaded as part of the add-on", f"{package}.extern_tools.mmd_tools_local" in sys.modules, True)
check("mmd classes register", len(classes) > 50, True)
check("mmd operators are available", "import_vmd" in operators, True)
prefs = sys.modules[f"{package}.extern_tools.mmd_tools_local.preferences"].MMDToolsAddonPreferences
check("its preferences class registers under the nested name", prefs.is_registered, True)
check("and its bl_idname agrees with the lookups that use it",
      prefs.bl_idname, sys.modules[f"{package}.extern_tools.mmd_tools_local.operators.fileio"].get_addon_package_name())
check("mmd properties are added to objects", "Object.mmd_type" in props, True)
check("the importer sees mmd_tools as installed", module("tools.importer").mmd_tools_local_installed, True)
check("the importer's dictionary enum resolves", callable(module("tools.importer").DictionaryEnum.get_dictionary_items), True)

class FakeProp(dict):
    bl_rna = SimpleNamespace(identifier="export")


translations = sys.modules[f"{package}.extern_tools.mmd_tools_local.translations"] \
    if f"{package}.extern_tools.mmd_tools_local.translations" in sys.modules else sys.modules.get("mmd_tools_local.translations")
check("the internal dictionary keeps its description",
      any(item[2] == "The dictionary defined in mmd_tools_local.translations"
          for item in translations.DictionaryEnum.get_dictionary_items(
              FakeProp(), bpy.context)), True)
done()
