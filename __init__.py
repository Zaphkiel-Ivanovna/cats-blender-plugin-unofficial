# MIT License

CATS_VERSION = "5.0.2.2"
dev_branch = False

import os
import sys

file_dir = os.path.join(os.path.dirname(__file__), 'extern_tools')
if file_dir not in sys.path:
    sys.path.append(file_dir)

import requests

from importlib.util import find_spec

from . import globs

if "bpy" not in locals():
    import bpy
    is_reloading = False
else:
    is_reloading = True

if not is_reloading:
    import mmd_tools_local
    if find_spec("imscale") and find_spec("imscale.immersive_scaler"):
        import imscale.immersive_scaler as imscale
    from . import updater
    from . import tools
    from . import ui
    from . import extentions
else:
    import importlib
    importlib.reload(updater)
    importlib.reload(mmd_tools_local)
    if 'imscale' in vars():
        importlib.reload(imscale)
    importlib.reload(tools)
    importlib.reload(ui)
    importlib.reload(extentions)

from .tools import translations
from .tools.translations import t


def check_unsupported_blender_versions():
    if bpy.app.version < (5, 0):
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.29unsupportedVersion'))

    if bpy.app.version >= (5, 2):
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.40unsupportedVersion'))

def set_cats_version_string():
    version_parts = CATS_VERSION.split(".")

    version_parts = [int(part) for part in version_parts]

    if dev_branch:
        version_parts[-1] += 1

    version_str = ".".join(str(part) for part in version_parts)

    if dev_branch:
        version_str += "-dev"

    return version_str

def register():
    print("\n### Loading CATS...")

    check_unsupported_blender_versions()

    version_str = set_cats_version_string()

    updater.register(dev_branch, version_str)

    globs.dev_branch = dev_branch
    globs.version_str = version_str

    try:
        tools.settings.load_settings()
    except FileNotFoundError:
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.restartAndEnable_alt'))


    try:
        mmd_tools_local.register()
    except NameError:
        print('Could not register local mmd_tools_local')
    except AttributeError:
        print('Could not register local mmd_tools_local')
    except ValueError:
        print('mmd_tools_local is already registered')

    if find_spec("imscale") and find_spec("imscale.immersive_scaler"):
        import imscale.immersive_scaler as imscale
        try:
            imscale.register()
        except ModuleNotFoundError:
            pass

    count = 0
    tools.register.order_classes()
    ordered_classes = tools.register.get_ordered_classes()
    for cls in ordered_classes:
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError:
            pass
    if count < len(ordered_classes):
        print('Skipped', len(ordered_classes) - count, 'CATS classes.')

    extentions.register()
    
    tools.iconloader.load_other_icons()

    globs.dict_found = tools.translate.load_translations()

    tools.common.get_user_preferences().filepaths.use_file_compression = True
    bpy.context.window_manager.addon_support = {'OFFICIAL', 'COMMUNITY'}

    bpy.types.MESH_MT_shape_key_context_menu.append(tools.shapekey.addToShapekeyMenu)

    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

    tools.settings.start_apply_settings_timer()

    print("### Loaded CATS successfully!\n")


def unregister():
    print("### Unloading CATS...")

    updater.unregister()

    try:
        mmd_tools_local.unregister()
    except NameError:
        print('mmd_tools_local was not registered')
        pass
    except AttributeError:
        print('Could not unregister local mmd_tools_local')
        pass
    except ValueError:
        print('mmd_tools_local was not registered')
        pass

    if find_spec("imscale") and find_spec("imscale.immersive_scaler"):
        import imscale.immersive_scaler as imscale
        try:
            imscale.unregister()
        except ModuleNotFoundError:
            pass 

    count = 0
    for cls in reversed(tools.register.get_ordered_classes()):
        try:
            bpy.utils.unregister_class(cls)
            count += 1
        except ValueError:
            pass
        except RuntimeError:
            pass
    print('Unregistered', count, 'CATS classes.')

    extentions.unregister()

    tools.iconloader.unload_icons()

    try:
        bpy.types.MESH_MT_shape_key_context_menu.remove(tools.shapekey.addToShapekeyMenu)
    except (AttributeError, ValueError):
        print('shapekey button was not registered')

    if file_dir in sys.path:
        sys.path.remove(file_dir)

    tools.settings.stop_apply_settings_timer()

    print("### Unloaded CATS successfully!\n")


if __name__ == '__main__':
    register()
