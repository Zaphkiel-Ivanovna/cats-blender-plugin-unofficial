# MIT License

import bpy
import operator
import math
import webbrowser
import numpy as np
import bmesh
from mathutils.geometry import intersect_point_line

from . import common as Common
from . import eyetracking as Eyetracking
from .register import register_wrap
from .translations import t

bone_names = {
    "right_shoulder": ["rightshoulder", "shoulderr", "rshoulder"],
    "right_arm": ["rightarm", "armr", "rarm", "upperarmr", "rightupperarm", "uparmr", "ruparm"],
    "right_elbow": ["rightelbow", "elbowr", "relbow", "lowerarmr", "rightlowerarm", "lowerarmr", "lowarmr", "rlowarm"],
    "right_wrist": ["rightwrist", "wristr", "rwrist", "handr", "righthand", "rhand"],

    "pinkie_1_r": ["littlefinger1r"],
    "pinkie_2_r": ["littlefinger2r"],
    "pinkie_3_r": ["littlefinger3r"],

    "ring_1_r": ["ringfinger1r"],
    "ring_2_r": ["ringfinger2r"],
    "ring_3_r": ["ringfinger3r"],

    "middle_1_r": ["middlefinger1r"],
    "middle_2_r": ["middlefinger2r"],
    "middle_3_r": ["middlefinger3r"],

    "index_1_r": ["indexfinger1r"],
    "index_2_r": ["indexfinger2r"],
    "index_3_r": ["indexfinger3r"],

    "thumb_1_r": ['thumb0r'],
    "thumb_2_r": ['thumb1r'],
    "thumb_3_r": ['thumb2r'],

    "right_leg": ["rightleg", "legr", "rleg", "upperlegr", "thighr", "rightupperleg", "uplegr", "rupleg"],
    "right_knee": ["rightknee", "kneer", "rknee", "lowerlegr", "calfr", "rightlowerleg", "lowlegr", "rlowleg"],
    "right_ankle": ["rightankle", "ankler", "rankle", "rightfoot", "footr", "rightfoot", "rightfeet", "feetright", "rfeet", "feetr"],
    "right_toe": ["righttoe", "toeright", "toer", "rtoe", "toesr", "rtoes"],

    "left_shoulder": ["leftshoulder", "shoulderl", "rshoulder"],
    "left_arm": ["leftarm", "arml", "rarm", "upperarml", "leftupperarm", "uparml", "luparm"],
    "left_elbow": ["leftelbow", "elbowl", "relbow", "lowerarml", "leftlowerarm", "lowerarml", "lowarml", "llowarm"],
    "left_wrist": ["leftwrist", "wristl", "rwrist", "handl", "lefthand", "lhand"],

    "pinkie_1_l": ["littlefinger1l"],
    "pinkie_2_l": ["littlefinger2l"],
    "pinkie_3_l": ["littlefinger3l"],

    "ring_1_l": ["ringfinger1l"],
    "ring_2_l": ["ringfinger2l"],
    "ring_3_l": ["ringfinger3l"],

    "middle_1_l": ["middlefinger1l"],
    "middle_2_l": ["middlefinger2l"],
    "middle_3_l": ["middlefinger3l"],

    "index_1_l": ["indexfinger1l"],
    "index_2_l": ["indexfinger2l"],
    "index_3_l": ["indexfinger3l"],

    "thumb_1_l": ['thumb0l'],
    "thumb_2_l": ['thumb1l'],
    "thumb_3_l": ['thumb2l'],

    "left_leg": ["leftleg", "legl", "rleg", "upperlegl", "thighl","leftupperleg", "uplegl", "lupleg"],
    "left_knee": ["leftknee", "kneel", "rknee", "lowerlegl", "calfl", "leftlowerleg", 'lowlegl', 'llowleg'],
    "left_ankle": ["leftankle", "anklel", "rankle", "leftfoot", "footl", "leftfoot", "leftfeet", "feetleft", "lfeet", "feetl"],
    "left_toe": ["lefttoe", "toeleft", "toel", "ltoe", "toesl", "ltoes"],

    'hips': ["pelvis", "hips"],
    'spine': ["torso", "spine"],
    'chest': ["chest"],
    'upper_chest': ["upperchest"],
    'neck': ["neck"],
    'head': ["head"],
    'left_eye': ["eyeleft", "lefteye", "eyel", "leye"],
    'right_eye': ["eyeright", "righteye", "eyer", "reye"],
}

def simplify_bonename(n):
    return n.lower().translate(dict.fromkeys(map(ord, " _.")))

@register_wrap
class DigitigradeTutorialButton(bpy.types.Operator):
    bl_idname = 'cats_manual.digitigrade_tutorial'
    bl_label = "How to use"
    bl_description = "This will open a basic tutorial on how to setup and use aim constraints for Digitigrade avatars. Desktop-only!"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open("https://www.furaffinity.net/view/44035707/")
        return {'FINISHED'}

@register_wrap
class TwistTutorialButton(bpy.types.Operator):
    bl_idname = 'cats_manual.twist_tutorial'
    bl_label = t('cats_twist.tutorial_button.label')
    bl_description = "This will open a basic tutorial on how to setup and use these constraints. You can skip to the Unity section."
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open("https://www.youtube.com/watch?v=eOwd5KNypfA")
        return {'FINISHED'}

@register_wrap
class StartPoseMode(bpy.types.Operator):
    bl_idname = 'cats_manual.start_pose_mode'
    bl_label = t('StartPoseMode.label')
    bl_description = t('StartPoseMode.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return Common.get_armature() is not None

    def execute(self, context):
        start_pose_mode(reset_pose=True)
        return {'FINISHED'}


@register_wrap
class StartPoseModeNoReset(bpy.types.Operator):
    bl_idname = 'cats_manual.start_pose_mode_no_reset'
    bl_label = t('StartPoseMode.label')
    bl_description = t('StartPoseModeNoReset.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return Common.get_armature() is not None

    def execute(self, context):
        start_pose_mode(reset_pose=False)
        return {'FINISHED'}


def start_pose_mode(reset_pose=True):
    saved_data = Common.SavedData()

    current = ""
    if bpy.context.active_object and bpy.context.active_object.mode == 'EDIT' and bpy.context.active_object.type == 'ARMATURE' and len(
            bpy.context.selected_editable_bones) > 0:
        current = bpy.context.selected_editable_bones[0].name

    armature = Common.set_default_stage()
    Common.remove_rigidbodies_global()
    Common.switch('POSE')
    armature.data.pose_position = 'POSE'

    if reset_pose:
        for mesh in Common.get_meshes_objects():
            if Common.has_shapekeys(mesh):
                for shape_key in mesh.data.shape_keys.key_blocks:
                    shape_key.value = 0

    for pb in armature.pose.bones:
        pb.select = True

    if reset_pose:
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()

    bone = armature.data.bones.get(current)
    if bone is not None:
        for pb in armature.pose.bones:
            if bone.name != pb.name:
                pb.select = False
    else:
        for index, pb in enumerate(armature.pose.bones):
            if index != 0:
                pb.select = False
        bpy.ops.wm.tool_set_by_id(name="builtin.rotate")

    saved_data.load(hide_only=True)
    Common.hide(armature, False)


@register_wrap
class StopPoseMode(bpy.types.Operator):
    bl_idname = 'cats_manual.stop_pose_mode'
    bl_label = t('StopPoseMode.label')
    bl_description = t('StopPoseMode.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return Common.get_armature() is not None

    def execute(self, context):
        stop_pose_mode(reset_pose=True)
        return {'FINISHED'}


@register_wrap
class StopPoseModeNoReset(bpy.types.Operator):
    bl_idname = 'cats_manual.stop_pose_mode_no_reset'
    bl_label = t('StopPoseMode.label')
    bl_description = t('StopPoseModeNoReset.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return Common.get_armature() is not None

    def execute(self, context):
        stop_pose_mode(reset_pose=False)
        return {'FINISHED'}


def stop_pose_mode(reset_pose=True):
    saved_data = Common.SavedData()
    armature = Common.get_armature()
    Common.set_active(armature)

    bpy.ops.object.hide_view_clear()

    for pb in armature.pose.bones:
        pb.hide = False
        pb.select = True

    if reset_pose:
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()

    for pb in armature.pose.bones:
        pb.select = False

    armature = Common.set_default_stage()
    Common.remove_rigidbodies_global()

    if reset_pose:
        for mesh in Common.get_meshes_objects():
            if Common.has_shapekeys(mesh):
                for shape_key in mesh.data.shape_keys.key_blocks:
                    shape_key.value = 0

    bpy.ops.wm.tool_set_by_id(name="builtin.select_box")

    Eyetracking.eye_left = None

    saved_data.load(hide_only=True)


@register_wrap
class PoseToShape(bpy.types.Operator):
    bl_idname = 'cats_manual.pose_to_shape'
    bl_label = t('PoseToShape.label')
    bl_description = t('PoseToShape.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        return armature and armature.mode == 'POSE'

    def execute(self, context):
        bpy.ops.cats_manual.pose_name_popup('INVOKE_DEFAULT')

        return {'FINISHED'}


def pose_to_shapekey(name):
    saved_data = Common.SavedData()

    for mesh in Common.get_meshes_objects():
        Common.unselect_all()
        Common.set_active(mesh)

        Common.switch('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.remove_doubles(threshold=0)
        Common.switch('OBJECT')

        mod = mesh.modifiers.new(name, 'ARMATURE')
        mod.object = Common.get_armature()
        Common.apply_modifier(mod, as_shapekey=True)

    armature = Common.set_default_stage()
    Common.remove_rigidbodies_global()
    Common.switch('POSE')
    armature.data.pose_position = 'POSE'

    saved_data.load(ignore=armature.name)
    return armature


@register_wrap
class PoseNamePopup(bpy.types.Operator):
    bl_idname = "cats_manual.pose_name_popup"
    bl_label = t('PoseNamePopup.label')
    bl_description = t('PoseNamePopup.desc')
    bl_options = {'INTERNAL'}

    bpy.types.Scene.pose_to_shapekey_name = bpy.props.StringProperty(name="Pose Name")

    def execute(self, context):
        name = context.scene.pose_to_shapekey_name
        if not name:
            name = 'Pose'
        pose_to_shapekey(name)
        self.report({'INFO'}, t('PoseNamePopup.success'))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.scene.pose_to_shapekey_name = 'Pose'
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4))

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.3
        row.prop(context.scene, 'pose_to_shapekey_name')


@register_wrap
class PoseToRest(bpy.types.Operator):
    bl_idname = 'cats_manual.pose_to_rest'
    bl_label = t('PoseToRest.label')
    bl_description = t('PoseToRest.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        return armature and armature.mode == 'POSE'

    def execute(self, context):
        saved_data = Common.SavedData()

        armature_obj = Common.get_armature()
        mesh_objs = Common.get_meshes_objects(armature_name=armature_obj.name)
        for mesh_obj in mesh_objs:
            me = mesh_obj.data
            if me:
                if me.shape_keys and me.shape_keys.key_blocks:
                    shape_keys = me.shape_keys
                    key_blocks = shape_keys.key_blocks
                    if len(key_blocks) == 1:
                        basis_shape_key = key_blocks[0]
                        original_basis_name = basis_shape_key.name
                        mesh_obj.shape_key_remove(basis_shape_key)
                        PoseToRest.apply_armature_to_mesh_with_no_shape_keys(armature_obj, mesh_obj)
                        mesh_obj.shape_key_add(name=original_basis_name)
                    else:
                        PoseToRest.apply_armature_to_mesh_with_shape_keys(armature_obj, mesh_obj, context.scene)
                else:
                    PoseToRest.apply_armature_to_mesh_with_no_shape_keys(armature_obj, mesh_obj)
        Common.op_override(bpy.ops.pose.armature_apply, {'active_object': armature_obj})

        bpy.ops.cats_manual.stop_pose_mode()

        saved_data.load(hide_only=True)

        self.report({'INFO'}, t('PoseToRest.success'))
        return {'FINISHED'}

    @staticmethod
    def apply_armature_to_mesh_with_no_shape_keys(armature_obj, mesh_obj):
        armature_mod = mesh_obj.modifiers.new('PoseToRest', 'ARMATURE')
        armature_mod.object = armature_obj
        mod_name = armature_mod.name
        context_override = {'object': mesh_obj}
        Common.op_override(bpy.ops.object.modifier_move_to_index, context_override, modifier=mod_name, index=0)
        Common.op_override(bpy.ops.object.modifier_apply, context_override, modifier=mod_name)

    @staticmethod
    def apply_armature_to_mesh_with_shape_keys(armature_obj, mesh_obj, scene):
        old_active_shape_key_index = mesh_obj.active_shape_key_index

        old_show_only_shape_key = mesh_obj.show_only_shape_key
        mesh_obj.show_only_shape_key = True

        me = mesh_obj.data
        shape_key_vertex_groups = []
        shape_key_mutes = []
        key_blocks = me.shape_keys.key_blocks
        for shape_key in key_blocks:
            shape_key_vertex_groups.append(shape_key.vertex_group)
            shape_key.vertex_group = ''
            shape_key_mutes.append(shape_key.mute)
            shape_key.mute = False

        mods_to_reenable_viewport = []
        for mod in mesh_obj.modifiers:
            if mod.show_viewport:
                mod.show_viewport = False
                mods_to_reenable_viewport.append(mod)

        armature_mod = mesh_obj.modifiers.new('PoseToRest', 'ARMATURE')
        armature_mod.object = armature_obj

        co_length = len(me.vertices) * 3
        eval_verts_cos_array = np.empty(co_length, dtype=np.single)
        depsgraph = None
        evaluated_mesh_obj = None

        def get_eval_cos_array():
            nonlocal depsgraph
            nonlocal evaluated_mesh_obj
            if depsgraph is None or evaluated_mesh_obj is None:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                evaluated_mesh_obj = mesh_obj.evaluated_get(depsgraph)
            else:
                depsgraph.update()
            evaluated_mesh_obj.data.vertices.foreach_get('co', eval_verts_cos_array)
            return eval_verts_cos_array

        for i, shape_key in enumerate(key_blocks):
            mesh_obj.active_shape_key_index = i
            evaluated_cos = get_eval_cos_array()
            shape_key.data.foreach_set('co', evaluated_cos)
            if i == 0:
                mesh_obj.data.vertices.foreach_set('co', evaluated_cos)

        for mod in mods_to_reenable_viewport:
            mod.show_viewport = True
        mesh_obj.modifiers.remove(armature_mod)
        for shape_key, vertex_group, mute in zip(me.shape_keys.key_blocks, shape_key_vertex_groups, shape_key_mutes, strict=True):
            shape_key.vertex_group = vertex_group
            shape_key.mute = mute
        mesh_obj.active_shape_key_index = old_active_shape_key_index
        mesh_obj.show_only_shape_key = old_show_only_shape_key

@register_wrap
class JoinMeshes(bpy.types.Operator):
    bl_idname = 'cats_manual.join_meshes'
    bl_label = t('JoinMeshes.label')
    bl_description = t('JoinMeshes.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        meshes = Common.get_meshes_objects(check=False)
        return meshes and len(meshes) > 0

    def execute(self, context):
        Common.apply_transforms()

        saved_data = Common.SavedData()
        mesh = Common.join_meshes()
        if not mesh:
            saved_data.load()
            self.report({'ERROR'}, t('JoinMeshes.failure'))
            return {'CANCELLED'}

        saved_data.load()
        Common.unselect_all()
        Common.set_active(mesh)

        for i in range(3):
            mesh.lock_location[i] = False
            mesh.lock_rotation[i] = False
            mesh.lock_scale[i] = False

        if hasattr(mesh, 'layers'):
            mesh.layers[0] = True

        self.report({'INFO'}, t('JoinMeshes.success'))
        return {'FINISHED'}


@register_wrap
class JoinMeshesSelected(bpy.types.Operator):
    bl_idname = 'cats_manual.join_meshes_selected'
    bl_label = t('JoinMeshesSelected.label')
    bl_description = t('JoinMeshesSelected.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        meshes = Common.get_meshes_objects(check=False)
        return meshes and len(meshes) > 0

    def execute(self, context):
        saved_data = Common.SavedData()

        if not Common.get_meshes_objects(mode=3):
            saved_data.load()
            self.report({'ERROR'}, t('JoinMeshesSelected.error.noSelect'))
            return {'FINISHED'}

        mesh = Common.join_meshes(mode=1)
        if not mesh:
            saved_data.load()
            self.report({'ERROR'}, t('JoinMeshesSelected.error.cantJoin'))
            return {'CANCELLED'}

        saved_data.load()
        Common.unselect_all()
        Common.set_active(mesh)
        self.report({'INFO'}, t('JoinMeshesSelected.success'))

        for i in range(3):
            mesh.lock_location[i] = False
            mesh.lock_rotation[i] = False
            mesh.lock_scale[i] = False

        if hasattr(mesh, 'layers'):
            mesh.layers[0] = True
        return {'FINISHED'}


@register_wrap
class SeparateByMaterials(bpy.types.Operator):
    bl_idname = 'cats_manual.separate_by_materials'
    bl_label = t('SeparateByMaterials.label')
    bl_description = t('SeparateByMaterials.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object

        if obj and obj.type == 'MESH':
            return True

        meshes = Common.get_meshes_objects(check=False)
        return meshes and len(meshes) >= 1

    def execute(self, context):
        saved_data = Common.SavedData()
        obj = context.active_object

        if not obj or (obj and obj.type != 'MESH'):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.noMesh'))
                return {'FINISHED'}
            if len(meshes) > 1:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.multipleMesh'))
                return {'FINISHED'}
            obj = meshes[0]

        obj_name = obj.name

        Common.separate_by_materials(context, obj)

        saved_data.load(ignore=[obj_name])
        self.report({'INFO'}, t('SeparateByMaterials.success'))
        return {'FINISHED'}


@register_wrap
class SeparateByLooseParts(bpy.types.Operator):
    bl_idname = 'cats_manual.separate_by_loose_parts'
    bl_label = t('SeparateByLooseParts.label')
    bl_description = t('SeparateByLooseParts.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object

        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()
        obj = context.active_object

        if not obj or (obj and obj.type != 'MESH'):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.noMesh'))
                return {'FINISHED'}
            if len(meshes) > 1:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.multipleMesh'))
                return {'FINISHED'}
            obj = meshes[0]
        obj_name = obj.name

        Common.separate_by_loose_parts(context, obj)

        saved_data.load(ignore=[obj_name])
        self.report({'INFO'}, t('SeparateByLooseParts.success'))
        return {'FINISHED'}


@register_wrap
class SeparateByShapekeys(bpy.types.Operator):
    bl_idname = 'cats_manual.separate_by_shape_keys'
    bl_label = t('SeparateByShapekeys.label')
    bl_description = t('SeparateByShapekeys.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object

        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()
        obj = context.active_object

        if not obj or (obj and obj.type != 'MESH'):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.noMesh'))
                return {'FINISHED'}
            if len(meshes) > 1:
                saved_data.load()
                self.report({'ERROR'}, t('SeparateByX.error.multipleMesh'))
                return {'FINISHED'}
            obj = meshes[0]
        obj_name = obj.name

        done_message = t('SeparateByShapekeys.success')
        if not Common.separate_by_shape_keys(context, obj):
            done_message = t('SeparateByX.warn.noSeparation')

        saved_data.load(ignore=[obj_name])
        self.report({'INFO'}, done_message)
        return {'FINISHED'}

@register_wrap
class MergeWeights(bpy.types.Operator):
    bl_idname = 'cats_manual.merge_weights'
    bl_label = t('MergeWeights.label')
    bl_description = t('MergeWeights.desc')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_obj = context.active_object
        if not active_obj or context.active_object.type != 'ARMATURE':
            return False
        if active_obj.mode == 'EDIT' and context.selected_editable_bones:
            return True
        return bool(active_obj.mode == 'POSE' and context.selected_pose_bones)

    def execute(self, context):
        saved_data = Common.SavedData()

        armature = context.object

        Common.switch('EDIT')

        parenting_list = {}
        for bone in context.selected_editable_bones:
            parent = bone.parent
            while parent and parent.parent and parent in context.selected_editable_bones:
                parent = parent.parent
            if not parent:
                continue
            parenting_list[bone.name] = parent.name

        merge_weights(armature, parenting_list)

        saved_data.load()

        self.report({'INFO'}, t('MergeWeights.success', number=str(len(parenting_list))))
        return {'FINISHED'}


@register_wrap
class MergeWeightsToActive(bpy.types.Operator):
    bl_idname = 'cats_manual.merge_weights_to_active'
    bl_label = t('MergeWeightsToActive.label')
    bl_description = t('MergeWeightsToActive.desc')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_obj = bpy.context.active_object
        if not active_obj or bpy.context.active_object.type != 'ARMATURE':
            return False
        if active_obj.mode == 'EDIT' and bpy.context.selected_editable_bones and len(bpy.context.selected_editable_bones) > 1:
            if bpy.context.active_bone in bpy.context.selected_editable_bones:
                return True
        elif active_obj.mode == 'POSE' and bpy.context.selected_pose_bones and len(bpy.context.selected_pose_bones) > 1:
            if bpy.context.active_pose_bone in bpy.context.selected_pose_bones:
                return True

        return False

    def execute(self, context):
        saved_data = Common.SavedData()

        armature = bpy.context.object

        Common.switch('EDIT')

        parenting_list = {}
        for bone in bpy.context.selected_editable_bones:
            if bone.name == bpy.context.active_bone.name:
                continue
            parenting_list[bone.name] = bpy.context.active_bone.name
            bone.parent = bpy.context.active_bone

        merge_weights(armature, parenting_list)

        saved_data.load()

        self.report({'INFO'}, t('MergeWeightsToActive.success', number=str(len(parenting_list))))
        return {'FINISHED'}


def merge_weights(armature, parenting_list):
    Common.switch('OBJECT')
    for mesh in Common.get_meshes_objects(armature_name=armature.name, visible_only=bpy.context.scene.merge_visible_meshes_only):
        Common.set_active(mesh)

        for bone, parent in parenting_list.items():
            if not mesh.vertex_groups.get(bone):
                continue
            if not mesh.vertex_groups.get(parent):
                mesh.vertex_groups.new(name=parent)
            Common.mix_weights(mesh, bone, parent)

    Common.unselect_all()
    Common.set_active(armature)
    Common.switch('EDIT')

    if not bpy.context.scene.keep_merged_bones:
        for bone in parenting_list:
            edited_bone = armature.data.edit_bones.get(bone)
            if edited_bone is not None:
                armature.data.edit_bones.remove(edited_bone)


@register_wrap
class ApplyTransformations(bpy.types.Operator):
    bl_idname = 'cats_manual.apply_transformations'
    bl_label = t('ApplyTransformations.label')
    bl_description = t('ApplyTransformations.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(Common.get_armature())

    def execute(self, context):
        saved_data = Common.SavedData()

        Common.apply_transforms()

        saved_data.load()
        self.report({'INFO'}, t('ApplyTransformations.success'))
        return {'FINISHED'}


@register_wrap
class ApplyAllTransformations(bpy.types.Operator):
    bl_idname = 'cats_manual.apply_all_transformations'
    bl_label = t('ApplyAllTransformations.label')
    bl_description = t('ApplyAllTransformations.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        saved_data = Common.SavedData()

        Common.apply_all_transforms()

        saved_data.load()
        self.report({'INFO'}, t('ApplyAllTransformations.success'))
        return {'FINISHED'}


@register_wrap
class RemoveZeroWeightBones(bpy.types.Operator):
    bl_idname = 'cats_manual.remove_zero_weight_bones'
    bl_label = t('RemoveZeroWeightBones.label')
    bl_description = t('RemoveZeroWeightBones.desc')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(Common.get_armature())

    def execute(self, context):
        saved_data = Common.SavedData()

        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        count = Common.delete_zero_weight()
        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, t('RemoveZeroWeightBones.success', number=str(count)))
        return {'FINISHED'}


@register_wrap
class RemoveZeroWeightGroups(bpy.types.Operator):
    bl_idname = 'cats_manual.remove_zero_weight_groups'
    bl_label = t('RemoveZeroWeightGroups.label')
    bl_description = t('RemoveZeroWeightGroups.desc')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return Common.get_meshes_objects(mode=2, check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        count = Common.remove_unused_vertex_groups()

        saved_data.load()
        self.report({'INFO'}, t('RemoveZeroWeightGroups.success', number=str(count)))
        return {'FINISHED'}


@register_wrap
class RemoveConstraints(bpy.types.Operator):
    bl_idname = 'cats_manual.remove_constraints'
    bl_label = t('RemoveConstraints.label')
    bl_description = t('RemoveConstraints.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(Common.get_armature())

    def execute(self, context):
        saved_data = Common.SavedData()

        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        Common.delete_bone_constraints()
        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, t('RemoveConstraints.success'))
        return {'FINISHED'}

@register_wrap
class GenerateTwistBones(bpy.types.Operator):
    bl_idname = 'cats_manual.generate_twist_bones'
    bl_label = "Generate Twist Bones"
    bl_description = "Attempt to generate twistbones for the selected bones"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if not Common.get_armature():
            return False
        return context.selected_editable_bones

    def execute(self, context):
        saved_data = Common.SavedData()

        if not hasattr(context.scene, 'generate_twistbones_upper'):
            bpy.types.Scene.generate_twistbones_upper = bpy.props.BoolProperty(
                name="Generate Twist Bones Upper",
                description="Generate Twist Bones Upper",
                default=True
            )

        context.object.data.use_mirror_x = False
        context.object.use_mesh_mirror_x = False
        context.object.pose.use_mirror_x = False
        generate_upper = context.scene.generate_twistbones_upper
        armature = context.object
        bone_pairs = []
        twist_locations = {}
        editable_bone_names = [bone.name for bone in context.selected_editable_bones]
        for bone_name in editable_bone_names:
            bone = armature.data.edit_bones[bone_name]
            if not generate_upper:
                twist_bone = armature.data.edit_bones.new('~' + bone.name + "_Twist")
                twist_bone.tail = bone.tail
                twist_bone.head[:] = [(bone.head[i] + bone.tail[i]) / 2 for i in range(3)]
                twist_locations[twist_bone.name] = (twist_bone.head[:], twist_bone.tail[:])
            else:
                twist_bone = armature.data.edit_bones.new('~' + bone.name + "_UpperTwist")
                twist_bone.tail[:] = [(bone.head[i] + bone.tail[i]) / 2 for i in range(3)]
                twist_bone.head = bone.head
                twist_locations[twist_bone.name] = (twist_bone.tail[:], twist_bone.head[:])
            twist_bone.parent = bone

            bone_pairs.append((bone.name, twist_bone.name))

        Common.switch('OBJECT')
        for bone_name, twist_bone_name in bone_pairs:
            twist_bone_head_tail = twist_locations[twist_bone_name]
            print(twist_bone_head_tail[0])
            print(twist_bone_head_tail[1])
            for mesh in Common.get_meshes_objects(armature_name=armature.name):
                if bone_name not in mesh.vertex_groups:
                    continue

                Common.set_active(mesh)
                context.object.data.use_mirror_vertex_groups = False
                context.object.data.use_mirror_x = False
                context.object.use_mesh_mirror_x = False

                mesh.vertex_groups.new(name=twist_bone_name)

                group_idx = mesh.vertex_groups[bone_name].index
                for vertex in mesh.data.vertices:
                    if any(group.group == group_idx for group in vertex.groups):

                        _, dist = intersect_point_line(vertex.co, twist_bone_head_tail[0], twist_bone_head_tail[1])
                        clamped_dist = max(0.0, min(1.0, dist))
                        twist_weight = mesh.vertex_groups[bone_name].weight(vertex.index) * clamped_dist
                        untwist_weight = mesh.vertex_groups[bone_name].weight(vertex.index) * (1.0 - clamped_dist)
                        mesh.vertex_groups[twist_bone_name].add([vertex.index], twist_weight, "REPLACE")
                        mesh.vertex_groups[bone_name].add([vertex.index], untwist_weight, "REPLACE")

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, t('RemoveConstraints.success'))
        return {'FINISHED'}


@register_wrap
class RecalculateNormals(bpy.types.Operator):
    bl_idname = 'cats_manual.recalculate_normals'
    bl_label = t('RecalculateNormals.label')
    bl_description = t('RecalculateNormals.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        obj = context.active_object
        if not obj or (obj and obj.type != 'MESH'):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                return {'FINISHED'}
            obj = meshes[0]
        mesh = obj

        Common.unselect_all()
        Common.set_active(mesh)
        Common.switch('EDIT')
        Common.switch('EDIT')

        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, t('RecalculateNormals.success'))
        return {'FINISHED'}


@register_wrap
class FlipNormals(bpy.types.Operator):
    bl_idname = 'cats_manual.flip_normals'
    bl_label = t('FlipNormals.label')
    bl_description = t('FlipNormals.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        obj = context.active_object
        if not obj or (obj and obj.type != 'MESH'):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                return {'FINISHED'}
            obj = meshes[0]
        mesh = obj

        Common.unselect_all()
        Common.set_active(mesh)
        Common.switch('EDIT')
        Common.switch('EDIT')

        bpy.ops.mesh.select_all(action='SELECT')

        bpy.ops.mesh.flip_normals()

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, t('FlipNormals.success'))
        return {'FINISHED'}

@register_wrap
class RemoveDoubles(bpy.types.Operator):
    bl_idname = 'cats_manual.remove_doubles'
    bl_label = t('RemoveDoubles.label')
    bl_description = t('RemoveDoubles.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True
        return Common.get_meshes_objects(check=False)

    def check_shapekeys_impact(self, mesh, context):
        if not Common.has_shapekeys(mesh):
            return False

        basis = np.array([v.co for v in mesh.data.shape_keys.key_blocks[0].data])
        threshold = context.scene.remove_doubles_threshold

        for shape in mesh.data.shape_keys.key_blocks[1:]:
            shape_verts = np.array([v.co for v in shape.data])
            distances = np.linalg.norm(basis - shape_verts, axis=1)
            if np.any(distances > threshold):
                return True
        return False

    def process_mesh(self, mesh, context):
        threshold = context.scene.remove_doubles_threshold
        try:
            bm = bmesh.new()
            bm.from_mesh(mesh.data)

            initial_tris = len(bm.faces)

            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=threshold)

            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')

            bm.to_mesh(mesh.data)
            mesh.data.update()
            bm.free()

            return initial_tris - len(mesh.data.polygons)

        except Exception as e:
            raise ValueError(f"Failed to process mesh {mesh.name}: {e!s}") from e

    def invoke(self, context, event):
        meshes = Common.get_meshes_objects(mode=3)
        if not meshes:
            meshes = [Common.get_meshes_objects()[0]]

        for mesh in meshes:
            if self.check_shapekeys_impact(mesh, context):
                return context.window_manager.invoke_props_dialog(self)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=t('RemoveDoubles.warning.shapekeys'))
        col.label(text=t('RemoveDoubles.warning.shapekeys.impact'))
        col.label(text=t('RemoveDoubles.warning.shapekeys.continue'))

    def execute(self, context):
        try:
            saved_data = Common.SavedData()
            removed_tris = 0

            meshes = Common.get_meshes_objects(mode=3)
            if not meshes:
                meshes = [Common.get_meshes_objects()[0]]

            Common.set_default_stage()
            Common.remove_rigidbodies_global()

            wm = context.window_manager
            wm.progress_begin(0, len(meshes))

            for i, mesh in enumerate(meshes):
                try:
                    if Common.has_shapekeys(mesh):
                        Common.save_shapekey_order(mesh.name)

                    removed = self.process_mesh(mesh, context)
                    removed_tris += removed

                    if not mesh.data.vertices or not mesh.data.polygons:
                        raise ValueError("Mesh data became invalid")

                    if Common.has_shapekeys(mesh):
                        Common.repair_shapekey_order(mesh.name)

                except Exception as e:
                    Common.show_error(4, [
                        t('RemoveDoubles.error.failed'),
                        str(e),
                        t('RemoveDoubles.error.mesh', mesh=mesh.name)
                    ])
                    continue
                finally:
                    wm.progress_update(i)

            wm.progress_end()
            Common.set_default_stage()
            Common.remove_rigidbodies_global()
            saved_data.load()

            self.report({'INFO'}, t('RemoveDoubles.success', number=str(removed_tris)))
            return {'FINISHED'}

        except Exception as e:
            if 'wm' in locals():
                wm.progress_end()
            Common.show_error(4, [
                t('RemoveDoubles.error.unexpected'),
                str(e)
            ])
            return {'CANCELLED'}

@register_wrap
class OptimizeStaticShapekeys(bpy.types.Operator):
    bl_idname = 'cats_manual.optimize_static_shapekeys'
    bl_label = 'Optimize Static Shapekeys'
    bl_description = "Move all shapekey-affected geometry into its own mesh, significantly decreasing GPU cost"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        objs = [context.active_object]
        if not objs[0] or (objs[0] and (objs[0].type != 'MESH' or objs[0].data.shape_keys is None)):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                return {'FINISHED'}
            objs = meshes

        if len([obj for obj in objs if obj.type == 'MESH']) > 1:
            self.report({'ERROR'}, "Meshes must first be combined for this to be beneficial.")

        for mesh in objs:
            if mesh.type == 'MESH' and mesh.data.shape_keys is not None:
                context.view_layer.objects.active = mesh

                if not mesh.data.corner_normals:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_mode(type="VERT")
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.set_normals_from_faces(keep_sharp=True)

                    normal_list = []
                    for corner_normal in mesh.data.corner_normals:
                        normal_list.append(corner_normal.normal)

                        mesh.data.normals_split_custom_set(normal_list)
                        mesh.data.update()

                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.select_mode(type="VERT")
                bpy.ops.mesh.select_all(action = 'DESELECT')
                bpy.ops.object.mode_set(mode = 'OBJECT')
                for key_block in mesh.data.shape_keys.key_blocks[1:]:
                    basis = mesh.data.shape_keys.key_blocks[0]

                    for idx, vert in enumerate(key_block.data):
                        if (math.sqrt(math.pow(basis.data[idx].co[0] - vert.co[0], 2.0) +
                        math.pow(basis.data[idx].co[1] - vert.co[1], 2.0) +
                        math.pow(basis.data[idx].co[2] - vert.co[2], 2.0)) > 0.0001):
                            mesh.data.vertices[idx].select = True

                if not all(v.select for v in mesh.data.vertices):
                    if any(v.select for v in mesh.data.vertices):
                        bpy.ops.object.mode_set(mode = 'EDIT')
                        bpy.ops.mesh.select_more()
                        bpy.ops.mesh.split()
                        bpy.ops.mesh.separate(type='SELECTED')
                        bpy.ops.object.mode_set(mode = 'OBJECT')
                    bpy.context.object.active_shape_key_index = 0
                    mesh.name = "Static"
                    mesh['catsForcedExportName'] = "Static"
                    bpy.ops.object.shape_key_remove(all=True)

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, "Separation complete.")
        return {'FINISHED'}


@register_wrap
class RepairShapekeys(bpy.types.Operator):
    bl_idname = 'cats_manual.repair_shapekeys'
    bl_label = 'Repair Broken Shapekeys'
    bl_description = "Attempt to repair messed up shapekeys caused by some Blender operations"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        objs = [context.active_object]
        if not objs[0] or (objs[0] and (objs[0].type != 'MESH' or objs[0].data.shape_keys is None)):
            Common.unselect_all()
            meshes = Common.get_meshes_objects()
            if len(meshes) == 0:
                saved_data.load()
                return {'FINISHED'}
            objs = meshes

        for obj in objs:
            if obj.data.shape_keys is None:
                continue
            Common.unselect_all()
            Common.set_active(obj)
            Common.switch('EDIT')
            Common.switch('EDIT')
            points = []
            for vert_idx in range(len(obj.data.shape_keys.key_blocks[0].data)):
                verts = {}
                for shape_idx in range(1, len(obj.data.shape_keys.key_blocks)):
                    vert_coord = obj.data.shape_keys.key_blocks[shape_idx].data[vert_idx]
                    if vert_coord not in verts:
                        verts[vert_coord] = 0
                    verts[vert_coord] += 1
                found_coord = max(verts.items(), key=operator.itemgetter(1))[0]
                print(found_coord)
                points.append(found_coord)
            Common.switch('OBJECT')
            bpy.ops.object.shape_key_add(from_mix=False)
            obj.active_shape_key.name = "CATS Antibasis"

            for vert_idx in range(len(obj.data.shape_keys.key_blocks[0].data)):
                obj.active_shape_key.data[vert_idx].co[0] = points[vert_idx].co[0]
                obj.active_shape_key.data[vert_idx].co[1] = points[vert_idx].co[1]
                obj.active_shape_key.data[vert_idx].co[2] = points[vert_idx].co[2]
            for idx in range(1, len(obj.data.shape_keys.key_blocks) - 1):
                obj.active_shape_key_index = idx
                Common.switch('EDIT')
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.blend_from_shape(shape="CATS Antibasis", blend=-1.0, add=True)
                Common.switch('OBJECT')
            obj.shape_key_remove(key=obj.data.shape_keys.key_blocks["CATS Antibasis"])
            obj.active_shape_key_index = 0


        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()
        self.report({'INFO'}, "Repair complete.")
        return {'FINISHED'}


@register_wrap
class RemoveDoublesNormal(bpy.types.Operator):
    bl_idname = 'cats_manual.remove_doubles_normal'
    bl_label = t('RemoveDoublesNormal.label')
    bl_description = t('RemoveDoublesNormal.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True

        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        removed_tris = 0
        meshes = Common.get_meshes_objects(mode=3)
        if not meshes:
            meshes = [Common.get_meshes_objects()[0]]

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        for mesh in meshes:
            removed_tris += Common.remove_doubles(mesh, 0.00002, save_shapes=True)

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        saved_data.load()

        self.report({'INFO'}, t('RemoveDoublesNormal.success', number=str(removed_tris)))
        return {'FINISHED'}


@register_wrap
class FixVRMShapesButton(bpy.types.Operator):
    bl_idname = 'cats_manual.fix_vrm_shapes'
    bl_label = t('FixVRMShapesButton.label')
    bl_description = t('FixVRMShapesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return Common.get_meshes_objects(check=False)

    def execute(self, context):
        saved_data = Common.SavedData()

        mesh = Common.get_meshes_objects()[0]
        slider_max_eyes = 0.33333
        slider_max_mouth = 0.94

        if not Common.has_shapekeys(mesh):
            self.report({'INFO'}, t('FixVRMShapesButton.warn.notDetected'))
            saved_data.load()
            return {'CANCELLED'}

        Common.set_active(mesh)
        bpy.ops.object.shape_key_clear()

        shapekeys_to_merge_eyes = {}
        shapekeys_to_merge_mouth = {}
        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if index == 0:
                continue

            if shapekey.name.startswith('eye_'):
                shapekey.slider_max = slider_max_eyes
            else:
                shapekey.slider_max = slider_max_mouth

            name_split = shapekey.name.split('00')
            if len(name_split) < 2:
                continue
            pre_name = name_split[0]
            post_name = name_split[1]

            if pre_name == "eye_face.f":
                shapekeys_to_merge_eyes[post_name] = []
            elif pre_name == "kuti_face.f":
                shapekeys_to_merge_mouth[post_name] = []

        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if index == 0:
                continue

            name_split = shapekey.name.split('00')
            if len(name_split) < 2:
                continue
            pre_name = name_split[0]
            post_name = name_split[1]

            if post_name in shapekeys_to_merge_eyes:
                if pre_name == 'eye_face.f' or pre_name == 'eye_siroL.sL' or pre_name == 'eye_line_u.elu':
                    shapekeys_to_merge_eyes[post_name].append(shapekey.name)

            elif post_name in shapekeys_to_merge_mouth:
                if pre_name == 'kuti_face.f' or pre_name == 'kuti_ha.ha' or pre_name == 'kuti_sita.t':
                    shapekeys_to_merge_mouth[post_name].append(shapekey.name)

        shapekeys_used = []
        for name, shapekeys_merge in shapekeys_to_merge_eyes.items():
            if len(shapekeys_merge) <= 1:
                continue

            for shapekey_name in shapekeys_merge:
                mesh.data.shape_keys.key_blocks[shapekey_name].value = slider_max_eyes
                shapekeys_used.append(shapekey_name)

            mesh.shape_key_add(name='eyes_' + name[1:], from_mix=True)
            mesh.active_shape_key_index = len(mesh.data.shape_keys.key_blocks) - 1
            bpy.ops.object.shape_key_move(type='TOP')
            bpy.ops.object.shape_key_clear()

        for name, shapekeys_merge in shapekeys_to_merge_mouth.items():
            if len(shapekeys_merge) <= 1:
                continue

            for shapekey_name in shapekeys_merge:
                mesh.data.shape_keys.key_blocks[shapekey_name].value = slider_max_mouth
                shapekeys_used.append(shapekey_name)

            mesh.shape_key_add(name='mouth_' + name[1:], from_mix=True)
            mesh.active_shape_key_index = len(mesh.data.shape_keys.key_blocks) - 1
            bpy.ops.object.shape_key_move(type='TOP')
            bpy.ops.object.shape_key_clear()

        for index in reversed(range(len(mesh.data.shape_keys.key_blocks))):
            mesh.active_shape_key_index = index
            shapekey = mesh.active_shape_key
            if shapekey.name in shapekeys_used:
                bpy.ops.object.shape_key_remove(all=False)

        saved_data.load()

        self.report({'INFO'}, t('FixVRMShapesButton.success'))
        return {'FINISHED'}

def duplicatebone(b):
    arm = bpy.context.object.data
    cb = arm.edit_bones.new(b.name)

    cb.head = b.head
    cb.tail = b.tail
    cb.matrix = b.matrix
    cb.parent = b.parent
    return cb

@register_wrap
class CreateDigitigradeLegs(bpy.types.Operator):
    """Create digitigrade legs while in edit mode with digitigrade thighs selected."""
    bl_idname = "armature.createdigitigradelegs"
    bl_label = "Create Digitigrade Legs"

    @classmethod
    def poll(cls, context):
        if(context.active_object is None):
            return False
        if(context.selected_editable_bones is not None):
            if(len(context.selected_editable_bones) == 2):
                return True
        return False

    def execute(self, context):
        for digi0 in context.selected_editable_bones:
            bone = digi0
            for _ in range(3):
                if not bone.children:
                    self.report({'ERROR'}, "Bone format incorrect! Please select a chain of 4 continuous bones!")
                    return {'CANCELLED'}
                bone = bone.children[0]

        for digi0 in context.selected_editable_bones:
            digi1 = digi0.children[0]
            digi2 = digi1.children[0]
            digi3 = digi2.children[0]
            digi4 = digi3.children[0] if digi3.children else None
            digi0.select = True
            digi1.select = True
            digi2.select = True
            digi3.select = True
            if(digi4):
                digi4.select = True
            bpy.ops.armature.roll_clear()
            bpy.ops.armature.select_all(action='DESELECT')

            digi0.select = True
            bpy.ops.transform.create_orientation(name="CATS_digi0", overwrite=True)
            bpy.ops.armature.select_all(action='DESELECT')


            thigh = duplicatebone(digi0)
            bpy.ops.armature.select_all(action='DESELECT')

            digi2.align_orientation(digi0)

            thigh.select_tail = True
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False},TRANSFORM_OT_translate=None)
            bpy.ops.armature.select_more()
            calf = context.selected_bones[0]
            bpy.ops.armature.select_all(action='DESELECT')

            calf.tail = digi2.tail

            flipedcalf = duplicatebone(calf)
            bpy.ops.armature.select_all(action='DESELECT')
            flipedcalf.select = True
            bpy.ops.armature.switch_direction()
            bpy.ops.armature.select_all(action='DESELECT')
            flippeddigi1 = duplicatebone(digi1)
            bpy.ops.armature.select_all(action='DESELECT')
            flippeddigi1.select = True
            bpy.ops.armature.switch_direction()
            bpy.ops.armature.select_all(action='DESELECT')


            flipedcalf.align_orientation(flippeddigi1)

            flipedcalf.length = flippeddigi1.length

            calf.head = flipedcalf.tail

            bpy.ops.armature.select_all(action='DESELECT')
            flippeddigi1.select = True
            bpy.ops.armature.delete()
            bpy.ops.armature.select_all(action='DESELECT')
            flipedcalf.select = True
            bpy.ops.armature.delete()
            bpy.ops.armature.select_all(action='DESELECT')


            newfoot = duplicatebone(digi3)
            newfoot.parent = calf
            if(digi4):
                newtoe = duplicatebone(digi4)
                newtoe.parent = newfoot
        return {'FINISHED'}

@register_wrap
class DuplicateBonesButton(bpy.types.Operator):
    bl_idname = 'cats_manual.duplicate_bones'
    bl_label = t('DuplicateBonesButton.label')
    bl_description = t('DuplicateBonesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        active_obj = bpy.context.active_object
        if not active_obj or bpy.context.active_object.type != 'ARMATURE':
            return False
        return bool((active_obj.mode == 'EDIT' and bpy.context.selected_editable_bones) or (active_obj.mode == 'POSE' and bpy.context.selected_pose_bones))

    def execute(self, context):
        saved_data = Common.SavedData()
        armature = bpy.context.object

        if armature.mode == 'POSE':
            selected_bone_names = [bone.name for bone in bpy.context.selected_pose_bones]
        else:
            selected_bone_names = [bone.name for bone in bpy.context.selected_editable_bones]

        Common.switch('EDIT')

        edit_bones = armature.data.edit_bones
        selected_bones = [edit_bones[name] for name in selected_bone_names if name in edit_bones]
        bone_count = len(selected_bones)

        duplicate_vertex_groups = {
            bone.name: f"{bone.name}{'_' if not bone.name.endswith('_') else ''}copy"
            for bone in selected_bones
        }

        new_bones = {}
        for orig_name, new_name in duplicate_vertex_groups.items():
            orig_bone = edit_bones.get(orig_name)
            new_bone = edit_bones.new(new_name)
            new_bones[new_name] = new_bone

            new_bone.head = orig_bone.head
            new_bone.tail = orig_bone.tail
            new_bone.parent = orig_bone.parent

        for new_bone in new_bones.values():
            if new_bone.parent and new_bone.parent.name in duplicate_vertex_groups:
                new_bone.parent = edit_bones.get(duplicate_vertex_groups[new_bone.parent.name])

        wm = context.window_manager
        meshes = Common.get_meshes_objects(armature_name=armature.name)
        wm.progress_begin(0, len(meshes))

        for idx, mesh in enumerate(meshes):
            self._process_mesh_weights(mesh, duplicate_vertex_groups)
            wm.progress_update(idx)

        wm.progress_end()
        saved_data.load()

        self.report({'INFO'}, t('DuplicateBonesButton.success', number=str(bone_count)))
        return {'FINISHED'}

    def _process_mesh_weights(self, mesh, duplicate_groups):
        Common.set_active(mesh)

        for new_name in duplicate_groups.values():
            mesh.vertex_groups.new(name=new_name)

        for orig_name, new_name in duplicate_groups.items():
            Common.mix_weights(mesh, orig_name, new_name, delete_old_vg=False)


@register_wrap
class ConnectBonesButton(bpy.types.Operator):
    bl_idname = 'cats_manual.connect_bones'
    bl_label = 'Connect Bones'
    bl_description = 'Connects all bones with their respective children'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        active_obj = bpy.context.active_object
        return active_obj and active_obj.type == 'ARMATURE'

    def execute(self, context):
        saved_data = Common.SavedData()
        armature = bpy.context.object

        try:
            Common.switch('EDIT')

            edit_bones = armature.data.edit_bones
            bones_processed = 0

            for bone in edit_bones:
                if bone.parent:
                    bone.use_connect = True
                    bones_processed += 1

            Common.fix_bone_orientations(armature)

            self.report({'INFO'}, f'Connected {bones_processed} bones successfully!')
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f'Failed to connect bones: {e!s}')
            return {'CANCELLED'}

        finally:
            saved_data.load()


@register_wrap
class ConvertToValveButton(bpy.types.Operator):
    bl_idname = 'cats_manual.convert_to_valve'
    bl_label = 'Convert Bones To Valve'
    bl_description = ('Converts all main bone names to default valve bone names.'
                      '\nMake sure your model has the CATS standard bone names from after using Fix Model')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    armature_name = bpy.props.StringProperty(default = "")

    @classmethod
    def poll(cls, context):
        return Common.get_armature()

    def execute(self, context):
        translate_bone_fails = 0
        armature = Common.get_armature() if self.armature_name == "" else bpy.data.objects[self.armature_name]

        reverse_bone_lookup = {}
        for (preferred_name, name_list) in bone_names.items():
            for name in name_list:
                reverse_bone_lookup[name] = preferred_name

        valve_translations = {
            'hips': "ValveBiped.Bip01_Pelvis",
            'spine': "ValveBiped.Bip01_Spine",
            'chest': "ValveBiped.Bip01_Spine1",
            'upper_chest': "ValveBiped.Bip01_Spine2",
            'neck': "ValveBiped.Bip01_Neck1",
            'head': "ValveBiped.Bip01_Head1",
            'left_leg': "ValveBiped.Bip01_L_Thigh",
            'left_knee': "ValveBiped.Bip01_L_Calf",
            'left_ankle': "ValveBiped.Bip01_L_Foot",
            'left_toe': "ValveBiped.Bip01_L_Toe0",
            'right_leg': "ValveBiped.Bip01_R_Thigh",
            'right_knee': "ValveBiped.Bip01_R_Calf",
            'right_ankle': "ValveBiped.Bip01_R_Foot",
            'right_toe': "ValveBiped.Bip01_R_Toe0",
            'left_shoulder': "ValveBiped.Bip01_L_Clavicle",
            'left_arm': "ValveBiped.Bip01_L_UpperArm",
            'left_elbow': "ValveBiped.Bip01_L_Forearm",
            'left_wrist': "ValveBiped.Bip01_L_Hand",
            'right_shoulder': "ValveBiped.Bip01_R_Clavicle",
            'right_arm': "ValveBiped.Bip01_R_UpperArm",
            'right_elbow': "ValveBiped.Bip01_R_Forearm",
            'right_wrist': "ValveBiped.Bip01_R_Hand",
            'pinkie_1_l': "ValveBiped.Bip01_L_Finger4",
            'pinkie_2_l': "ValveBiped.Bip01_L_Finger41",
            'pinkie_3_l': "ValveBiped.Bip01_L_Finger42",
            'ring_1_l': "ValveBiped.Bip01_L_Finger3",
            'ring_2_l': "ValveBiped.Bip01_L_Finger31",
            'ring_3_l': "ValveBiped.Bip01_L_Finger32",
            'middle_1_l': "ValveBiped.Bip01_L_Finger2",
            'middle_2_l': "ValveBiped.Bip01_L_Finger21",
            'middle_3_l': "ValveBiped.Bip01_L_Finger22",
            'index_1_l': "ValveBiped.Bip01_L_Finger1",
            'index_2_l': "ValveBiped.Bip01_L_Finger11",
            'index_3_l': "ValveBiped.Bip01_L_Finger12",
            'thumb_1_l': "ValveBiped.Bip01_L_Finger0",
            'thumb_2_l': "ValveBiped.Bip01_L_Finger01",
            'thumb_3_l': "ValveBiped.Bip01_L_Finger02",

            'pinkie_1_r': "ValveBiped.Bip01_R_Finger4",
            'pinkie_2_r': "ValveBiped.Bip01_R_Finger41",
            'pinkie_3_r': "ValveBiped.Bip01_R_Finger42",
            'ring_1_r': "ValveBiped.Bip01_R_Finger3",
            'ring_2_r': "ValveBiped.Bip01_R_Finger31",
            'ring_3_r': "ValveBiped.Bip01_R_Finger32",
            'middle_1_r': "ValveBiped.Bip01_R_Finger2",
            'middle_2_r': "ValveBiped.Bip01_R_Finger21",
            'middle_3_r': "ValveBiped.Bip01_R_Finger22",
            'index_1_r': "ValveBiped.Bip01_R_Finger1",
            'index_2_r': "ValveBiped.Bip01_R_Finger11",
            'index_3_r': "ValveBiped.Bip01_R_Finger12",
            'thumb_1_r': "ValveBiped.Bip01_R_Finger0",
            'thumb_2_r': "ValveBiped.Bip01_R_Finger01",
            'thumb_3_r': "ValveBiped.Bip01_R_Finger02"
        }

        for bone in armature.data.bones:
            if simplify_bonename(bone.name) in reverse_bone_lookup and reverse_bone_lookup[simplify_bonename(bone.name)] in valve_translations:
                bone.name = valve_translations[reverse_bone_lookup[simplify_bonename(bone.name)]]
            else:
                translate_bone_fails += 1

        if translate_bone_fails > 0:
            self.report({'WARNING'}, f"Failed to translate {translate_bone_fails} bones! Make sure your model has standard bone names!")
        else:
            self.report({'INFO'}, 'Converted all bones to Valve names!')
        return {'FINISHED'}

@register_wrap
class RemoveRigidbodiesJointsOperator(bpy.types.Operator):
    bl_idname = 'my_plugin.remove_rigidbodies_joints'
    bl_label = t('RemoveRigidbodiesJointsOperator.label')
    bl_description = t('RemoveRigidbodiesJointsOperator.description')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not Common.get_armature():
            return False

        return len(Common.get_armature_objects()) != 0

    def execute(self, context):
        Common.set_default_stage()
        armature = context.active_object
        to_delete = []
        for child in Common.get_top_parent(armature).children:
            if 'rigidbodies' in child.name or ('joints' in child.name and child.name not in to_delete):
                to_delete.append(child.name)
                continue
            for child2 in child.children:
                if 'rigidbodies' in child2.name or ('joints' in child2.name and child2.name not in to_delete):
                    to_delete.append(child2.name)
                    continue
        for obj_name in to_delete:
            Common.switch('EDIT')
            Common.switch('OBJECT')
            Common.delete_hierarchy(bpy.data.objects[obj_name])

        self.report({'INFO'}, 'Removed rigidbodies and joints.')
        return {'FINISHED'}
