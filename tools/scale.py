# GPL License


import bpy
import webbrowser
import addon_utils

from .register import register_wrap
from .translations import t

@register_wrap
class EnableIMScale(bpy.types.Operator):
    bl_idname = 'cats_scale.enable_imscale'
    bl_label = t('EnableIMScale.label')
    bl_description = t('EnableIMScale.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        for mod in addon_utils.modules():
            if mod.bl_info['name'] == "Immersive Scaler":
                if mod.bl_info['version'] < (0, 5, 2) and addon_utils.check(mod.__name__)[0]:
                    try:
                        bpy.ops.preferences.addon_disable(module=mod.__name__)
                    except Exception:
                        pass
                    continue

        for mod in addon_utils.modules():
            if mod.bl_info['name'] == "Immersive Scaler":
                if mod.bl_info['version'] < (0, 5, 2):
                    continue
                if not addon_utils.check(mod.__name__)[0]:
                    bpy.ops.preferences.addon_enable(module=mod.__name__)
                    break
        self.report({'INFO'}, t('EnableIMScale.success'))
        return {'FINISHED'}


@register_wrap
class ImmersiveScalerButton(bpy.types.Operator):
    bl_idname = 'imscale.download_immersive_scaler'
    bl_label = t('ImmersiveScalerButton.label')
    bl_description = t('ImmersiveScalerButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open('https://github.com/teamneoneko/immersive_scaler/releases/latest')

        self.report({'INFO'}, 'ImmersiveScalerButton.success')
        return {'FINISHED'}

@register_wrap
class ImmersiveScalerHelpButton(bpy.types.Operator):
    bl_idname = 'imscale.help'
    bl_label = t('ImmersiveScalerHelpButton.label')
    bl_description = t('ImmersiveScalerHelpButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('ImmersiveScalerHelpButton.URL'))

        self.report({'INFO'}, t('ImmersiveScalerHelpButton.success'))
        return {'FINISHED'}
