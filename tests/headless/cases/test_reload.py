# GPL License
"""Reload Scripts re-runs every sub-package, not only the root one."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, module

enable()

common = module("tools.common")
main = module("ui.main")
register = module("tools.register")

before_func = common.get_armature
before_class = main.ToolPanel
before_count = len(register.get_ordered_classes())

bpy.utils.load_scripts(reload_scripts=True)

common = module("tools.common")
main = module("ui.main")
register = module("tools.register")

check("tools modules are re-run", common.get_armature is not before_func, True)
check("ui modules are re-run", main.ToolPanel is not before_class, True)
check("the same number of classes registers again", len(register.get_ordered_classes()), before_count)
check("the add-on is still enabled after the reload",
      any(addon.module == os.environ.get("CATS_TEST_PACKAGE", "bl_ext.user_default.cats_blender_plugin")
          for addon in bpy.context.preferences.addons), True)
done()
