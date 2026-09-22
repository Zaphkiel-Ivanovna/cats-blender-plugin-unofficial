# GPL License
"""register() / unregister() must be symmetrical and survive a reload cycle."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from _harness import check, done, enable, PACKAGE

cats = enable()
check("register succeeded", PACKAGE in bpy.context.preferences.addons, True)

props = list(getattr(cats.extentions, "_registered_properties", []))
classes = list(cats.tools.register.get_ordered_classes())
check("Scene properties were recorded", len(props) > 50, True)
check("classes were ordered", len(classes) > 50, True)
check("icons loaded", "custom_icons" in cats.tools.iconloader.preview_collections, True)
check("settings timer runs on the main thread",
      bpy.app.timers.is_registered(cats.tools.settings.apply_settings), True)

menu = bpy.types.MESH_MT_shape_key_context_menu._dyn_ui_initialize()
check("one shape key menu entry",
      sum(1 for f in menu if getattr(f, "__name__", "") == "addToShapekeyMenu"), 1)

bpy.ops.preferences.addon_disable(module=PACKAGE)
check("no Scene property left behind",
      [p for p in props if hasattr(bpy.types.Scene, p)], [])
check("settings timer stopped",
      bpy.app.timers.is_registered(cats.tools.settings.apply_settings), False)
check("preview collections released", list(cats.tools.iconloader.preview_collections), [])

bpy.ops.preferences.addon_enable(module=PACKAGE)
check("re-enable works", PACKAGE in bpy.context.preferences.addons, True)
menu = bpy.types.MESH_MT_shape_key_context_menu._dyn_ui_initialize()
check("still one menu entry after a full cycle",
      sum(1 for f in menu if getattr(f, "__name__", "") == "addToShapekeyMenu"), 1)

done()
