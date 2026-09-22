# MIT License

import bpy
import numpy as np
import copy
import math
import platform
from mathutils import Matrix
from collections import defaultdict

from . import common as Common
from . import material as Material
from . import translate as Translate
from . import armature_bones as Bones
from .register import register_wrap
from .translations import t

mmd_tools_local_installed = False
if platform.system() != "Linux":
    try:
        from mmd_tools_local.operators import morph as Morph
        mmd_tools_local_installed = True
    except ImportError:
        pass


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message, error_code=None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ArmatureValidator:
    """Comprehensive input validation for armature fixing"""
    
    @staticmethod
    def validate_armature_requirements(context, armature):
        """Validate all requirements before processing begins"""
        errors = []
        warnings = []
        
        if not armature:
            errors.append("No armature found in the scene")
            return errors, warnings
            
        if not armature.data:
            errors.append("Armature has no data")
            return errors, warnings
        
        if any(armature.lock_location) or any(armature.lock_rotation) or any(armature.lock_scale):
            warnings.append("Armature has locked transforms - these will be unlocked")
        
        bone_count = len(armature.data.bones)
        if bone_count == 0:
            errors.append("Armature has no bones")
        elif bone_count > 1000:
            warnings.append(f"Armature has {bone_count} bones - processing may be slow")
        
        if ArmatureValidator._is_rigify_armature(armature):
            errors.append("Rigify and Metarig armatures are not supported. Please use Rigify to Unity plugin instead.")
        
        mesh_errors, mesh_warnings = ArmatureValidator._validate_meshes(context, armature)
        errors.extend(mesh_errors)
        warnings.extend(mesh_warnings)
        
        required_bone_groups = [
            ['Hips', 'Spine'],
            ['Head', 'Neck'],
        ]
        
        for bone_group in required_bone_groups:
            if not any(bone.name in bone_group for bone in armature.data.bones):
                warnings.append(f"No bones found from group: {', '.join(bone_group)}")
        
        return errors, warnings
    
    @staticmethod
    def _is_rigify_armature(armature):
        """Check if armature is Rigify/Metarig"""
        if armature.name.lower() == 'metarig':
            return True
            
        rigify_bones = {'brow.B.L', 'lip.B.R', 'lip.T.R', 'lip.B.L', 'lip.T.L'}
        
        for bone in armature.data.bones:
            if bone.name.startswith(('DEF-', 'MCH-', 'ORG-')) or bone.name in rigify_bones:
                return True
                
        return False
    
    @staticmethod
    def _validate_meshes(context, armature):
        """Validate mesh requirements"""
        errors = []
        warnings = []
        
        meshes = Common.get_meshes_objects()
        
        if not meshes:
            is_vrm = False
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    is_vrm = True
                    break
            
            if not is_vrm:
                errors.append("No meshes found in the scene")
        
        
        for mesh in meshes:
            if not mesh.vertex_groups:
                warnings.append(f"Mesh '{mesh.name}' has no vertex groups")
            
            uv_issues = 0
            for uv_layer in mesh.data.uv_layers:
                uvs = np.empty(len(uv_layer.data) * 2, dtype=np.float32)
                uv_layer.data.foreach_get('uv', uvs)
                uv_issues += int(np.isnan(uvs.reshape(-1, 2)).any(axis=1).sum())
            
            if uv_issues > 0:
                warnings.append(f"Mesh '{mesh.name}' has {uv_issues} faulty UV coordinates that will be fixed")
        
        return errors, warnings


class BoneCache:
    """Lightweight cache system for bone lookups"""
    
    def __init__(self, armature):
        self.armature = armature
        self.bone_name_map = {}
        self._build_name_cache()
    
    def _build_name_cache(self):
        """Build lightweight name mapping cache only"""
        for bone in self.armature.data.bones:
            self.bone_name_map[bone.name.lower()] = bone.name
    
    def find_bone_by_name(self, name):
        """Find bone by name with caching"""
        return self.bone_name_map.get(name.lower())
    
    def clear_cache(self):
        """Clear all cached data to prevent memory leaks"""
        self.bone_name_map.clear()
        self.armature = None


def convert_bone_morphs_native(context, armature, mmd_root):
    """Native bone morph to shape key conversion for Linux compatibility"""
    if not hasattr(mmd_root, 'bone_morphs') or len(mmd_root.bone_morphs) == 0:
        return
    
    from mathutils import Vector, Quaternion
    
    mesh_objects = Common.get_meshes_objects()
    if not mesh_objects:
        return
    
    mesh = mesh_objects[0]
    Common.set_active(mesh)
    
    if not mesh.data.shape_keys:
        mesh.shape_key_add(name="Basis")
    
    to_translate = []
    for morph in mmd_root.bone_morphs:
        to_translate.append(morph.name)
    
    Translate.update_dictionary(to_translate, translating_shapes=True)
    
    wm = context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(mmd_root.bone_morphs))
    
    original_transforms = {}
    for bone in armature.pose.bones:
        original_transforms[bone.name] = {
            'location': bone.location.copy(),
            'rotation_quaternion': bone.rotation_quaternion.copy(),
            'rotation_euler': bone.rotation_euler.copy(),
        }
    
    for morph in mmd_root.bone_morphs:
        current_step += 1
        wm.progress_update(current_step)
        
        if not morph.data:
            continue
            
        for morph_data in morph.data:
            if morph_data.bone in armature.pose.bones:
                bone = armature.pose.bones[morph_data.bone]
                
                bone.location = original_transforms[bone.name]['location'] + Vector(morph_data.location)
                offset_quat = Quaternion(morph_data.rotation)
                bone.rotation_quaternion = original_transforms[bone.name]['rotation_quaternion'] @ offset_quat
        
        context.view_layer.update()
        
        original_name = morph.name
        shape_key_name, translated = Translate.translate(original_name, add_space=True, translating_shapes=True)
        shape_key = mesh.shape_key_add(name=shape_key_name)
        
        for bone_name, transforms in original_transforms.items():
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                bone.location = transforms['location']
                bone.rotation_quaternion = transforms['rotation_quaternion']
                bone.rotation_euler = transforms['rotation_euler']
    
    wm.progress_end()
    context.view_layer.update()


@register_wrap
class FixArmature(bpy.types.Operator):
    bl_idname = 'cats_armature.fix'
    bl_label = t('FixArmature.label')
    bl_description = t('FixArmature.desc')

    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if not Common.get_armature():
            return False

        if len(Common.get_armature_objects()) == 0:
            return False

        return True

    def execute(self, context):
        saved_data = Common.SavedData()
        armature = Common.get_armature()
        
        try:
            errors, warnings = ArmatureValidator.validate_armature_requirements(context, armature)
            
            for warning in warnings:
                self.report({'WARNING'}, warning)
            
            if errors:
                for error in errors:
                    self.report({'ERROR'}, error)
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Validation failed: {str(e)}")
            return {'CANCELLED'}
        
        bone_cache = BoneCache(armature)
        
        bone_collections_backup = []
        mmd_root = None
        try:
            mmd_root = armature.parent.mmd_root
        except AttributeError:
            pass
                
        if mmd_root:
            Common.set_active(armature)
            Common.switch('EDIT')
            
            for collection in armature.data.collections:
                collection_data = {
                    'name': collection.name,
                    'is_visible': collection.is_visible,
                    'bones': []
                }
                
                for bone in collection.bones:
                    collection_data['bones'].append(bone.name)
                
                bone_collections_backup.append(collection_data)
            
            Common.switch('OBJECT')
            
            for collection in list(armature.data.collections):
                armature.data.collections.remove(collection)
        
        is_rigify = False
        rigify_bones = {'brow.B.L', 'lip.B.R', 'lip.T.R', 'lip.B.L', 'lip.T.L'}
        
        if armature.name.lower() == 'metarig':
            is_rigify = True
        
        if not is_rigify:
            for bone in armature.data.bones:
                if bone.name.startswith(('DEF-', 'MCH-', 'ORG-')) or bone.name in rigify_bones:
                    is_rigify = True
                    break
                
        if is_rigify:
            Common.show_error(3, ["Rigify and Metarig armatures are not", 
                                "supported. Please use Rigify to Unity", 
                                "plugin instead.",
                                "If you think this is a error, then make sure your",
                                "bones and amrature do not have metarig", 
                                "names or Rigify names."])
            return {'CANCELLED'}

        meshes_to_check = Common.get_meshes_objects()
        for mesh in meshes_to_check:
            if mesh.data.users > 1:
                Common.show_error(4, [t('JoinMeshes.error.not_single_user'),
                                    t('JoinMeshes.error.make_single_user'),
                                    t('JoinMeshes.error.make_single_user1'),
                                    t('JoinMeshes.error.make_single_user2')])
                return {'CANCELLED'}

        is_vrm = False
        if len(Common.get_meshes_objects()) == 0:
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    is_vrm = True
            if not is_vrm:
                Common.show_error(3.8, t('FixArmature.error.noMesh'))
                return {'CANCELLED'}

        print('\nFixing Model:\n')

        wm = bpy.context.window_manager
        armature = Common.set_default_stage()

        temp_rename_bones = copy.deepcopy(Bones.bone_rename)
        temp_reweight_bones = copy.deepcopy(Bones.bone_reweight)
        temp_list_reweight_bones = copy.deepcopy(Bones.bone_list_weight)
        temp_list_reparent_bones = copy.deepcopy(Bones.bone_list_parenting)

        for key, value in Bones.bone_rename_fingers.items():
            temp_rename_bones[key] = value

        for key, value in temp_rename_bones.items():
            if key == 'Spine':
                continue
            bone_list = temp_reweight_bones.get(key) 
            if not bone_list:
                temp_reweight_bones[key] = value
            else:
                for name in value:
                    if name not in bone_list:
                        temp_reweight_bones.get(key).append(name)

        steps = 0
        for key, value in temp_rename_bones.items():
            if "\\L" in key:
                steps += 2 * len(value)
            else:
                steps += len(value)
        for key, value in temp_reweight_bones.items():
            if "\\L" in key:
                steps += 2 * len(value)
            else:
                steps += len(value)
        steps += len(temp_list_reweight_bones)

        print('DOUBLE ENTRIES:')
        print('RENAME:')
        name_list = []  
        for key, value in temp_rename_bones.items():
            for name in value:
                if name.lower() not in name_list:
                    name_list.append(name.lower())
                else:
                    print(key + " | " + name)
        print('REWEIGHT:')
        name_list = [] 
        for key, value in temp_reweight_bones.items():
            for name in value:
                if name.lower() not in name_list:
                    name_list.append(name.lower())
                else:
                    print(key + " | " + name)
        print('DOUBLES END')

        mmd_root = None
        try:
            mmd_root = armature.parent.mmd_root
        except AttributeError:
            pass

        if mmd_root:
            if mmd_tools_local_installed:
                mmd_root.use_toon_texture = False
                mmd_root.use_sphere_texture = False

            if hasattr(mmd_root, 'bone_morphs') and len(mmd_root.bone_morphs) > 0:
                
                if mmd_tools_local_installed:
                    to_translate = []
                    for morph in mmd_root.bone_morphs:
                        to_translate.append(morph.name)
                    
                    Translate.update_dictionary(to_translate, translating_shapes=True)
                    
                    current_step = 0
                    wm.progress_begin(current_step, len(mmd_root.bone_morphs))

                    armature.data.pose_position = 'POSE'
                    for index, morph in enumerate(mmd_root.bone_morphs):
                        current_step += 1
                        wm.progress_update(current_step)

                        armature.parent.mmd_root.active_morph = index
                        Morph.ViewBoneMorph.execute(None, context)

                        mesh = Common.get_meshes_objects()[0]
                        Common.set_active(mesh)

                        original_name = morph.name
                        modifier_name, _ = Translate.translate(original_name, add_space=True, translating_shapes=True)
                        mod = mesh.modifiers.new(modifier_name, 'ARMATURE')
                        mod.object = armature
                        Common.apply_modifier(mod, as_shapekey=True)
                    wm.progress_end()
                else:
                    armature.data.pose_position = 'POSE'
                    convert_bone_morphs_native(context, armature, mmd_root)

        source_engine = False
        for bone in armature.pose.bones:
            if bone.name.startswith('ValveBiped'):
                source_engine = True
                break

        for bone in armature.pose.bones:
            if bone.name.startswith("cShrugger"):
                for bone in armature.pose.bones:
                    if bone.name == "Spine1":
                        bone.name = "Hips"
                        break
                break

        if armature.animation_data and armature.animation_data.action and armature.animation_data.action.name == 'ragdoll':
            armature.animation_data_clear()
            source_engine = True

        for mesh in Common.get_meshes_objects(mode=1):
            if mesh.name == 'VTA vertices':
                Common.delete_hierarchy(mesh)
                source_engine = True
                break

        if source_engine:
            for mesh in Common.get_meshes_objects():
                if len(Common.get_meshes_objects()) == 1:
                    break
                if mesh.name.endswith(('_physics', '_lod1', '_lod2', '_lod3', '_lod4', '_lod5', '_lod6')):
                    Common.delete_hierarchy(mesh)

        armature = Common.set_default_stage()

        view_area = None
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                view_area = area.spaces[0]
                break

        if view_area:
            view_area.clip_start = 0.01
            view_area.clip_end = 300
            armature.data.display_type = 'OCTAHEDRAL'
            if hasattr(armature, 'draw_type'):
                armature.draw_type = 'WIRE'
            armature.show_in_front = True
            armature.data.show_bone_custom_shapes = False
            if view_area:
                view_area.shading.show_backface_culling = True

            try:
                context.scene.view_settings.view_transform = 'Standard'
            except TypeError:
                print('Color Management View Transform "Standard" not found!')

        if context.scene.remove_rigidbodies_joints:
            to_delete = []
            for child in Common.get_top_parent(armature).children:
                if 'rigidbodies' in child.name or 'joints' in child.name and child.name not in to_delete:
                    to_delete.append(child.name)
                    continue
                for child2 in child.children:
                    if 'rigidbodies' in child2.name or 'joints' in child2.name and child2.name not in to_delete:
                        to_delete.append(child2.name)
                        continue
            for obj_name in to_delete:
                Common.set_active(armature)
                Common.switch('EDIT')
                Common.switch('OBJECT')
                Common.delete_hierarchy(bpy.data.objects[obj_name])

        if len(armature.children) > 1:
            for child in armature.children:
                for child2 in child.children:
                    if child2.type != 'MESH':
                        Common.delete(child2)

                if child.type != 'MESH':
                    Common.delete(child)

        for i in range(0, 3):
            armature.lock_location[i] = False
            armature.lock_rotation[i] = False
            armature.lock_scale[i] = False

        for bone in armature.pose.bones:
            bone.lock_location[0] = False
            bone.lock_location[1] = False
            bone.lock_location[2] = False
            bone.lock_rotation[0] = False
            bone.lock_rotation[1] = False
            bone.lock_rotation[2] = False
            bone.lock_scale[0] = False
            bone.lock_scale[1] = False
            bone.lock_scale[2] = False

        Common.set_active(armature)
        Common.switch('EDIT')
        Common.switch('OBJECT')
        Common.remove_empty()
        Common.remove_unused_objects()

        if is_vrm:
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    mesh.parent = armature
        collections_armature_is_in = armature.users_collection
        if collections_armature_is_in:
            armature_collection = collections_armature_is_in[0]
            for col in collections_armature_is_in[1:]:
                col.objects.unlink(armature)
        else:
            armature_collection = context.scene.collection
            armature_collection.objects.link(armature)

        for mesh in Common.get_meshes_objects():
            mesh_already_in_armature_collection = False
            for col in mesh.users_collection:
                if col == armature_collection:
                    mesh_already_in_armature_collection = True
                else:
                    col.objects.unlink(mesh)
            if not mesh_already_in_armature_collection:
                armature_collection.objects.link(mesh)

        print('CHECK TRANSFORMS:', armature.scale[0], armature.scale[1], armature.scale[2])
        if round(armature.scale[0], 2) == 0.01 \
                and round(armature.scale[1], 2) == 0.01 \
                and round(armature.scale[2], 2) == 0.01:

            Common.set_active(armature)
            armature.animation_data_clear()
            for mesh in Common.get_meshes_objects():
                mesh.animation_data_clear()

        Common.fix_zero_length_bones(armature)

        Common.apply_transforms()

        if context.scene.join_meshes:
            meshes = [Common.join_meshes()]
        else:
            meshes = Common.get_meshes_objects()

        for mesh in meshes:
            Common.unselect_all()
            Common.set_active(mesh)

            for i in range(0, 3):
                mesh.lock_location[i] = False
                mesh.lock_rotation[i] = False
                mesh.lock_scale[i] = False

            if hasattr(mesh, 'layers'):
                mesh.layers[0] = True

            if source_engine and Common.has_shapekeys(mesh):
                mesh.data.shape_keys.key_blocks[0].name = "Basis"

            if is_vrm and Common.has_shapekeys(mesh):
                shapekeys = mesh.data.shape_keys.key_blocks
                for shapekey in shapekeys:
                    shapekey.name = shapekey.name.replace('_', ' ').replace('Face.M F00 000 Fcl ', '').replace('Face.M F00 000 00 Fcl ', '')

                shapekey_order = []
                for categorie in ['MTH', 'EYE', 'BRW', 'ALL', 'HA']:
                    for shapekey in shapekeys:
                        if shapekey.name.startswith(categorie):
                            shapekey_order.append(shapekey.name)

                Common.sort_shape_keys(mesh.name, shapekey_order)        

            Common.clean_shapekeys(mesh)
            Common.save_shapekey_order(mesh.name)

            Common.sort_shape_keys(mesh.name)

            if Common.has_shapekeys(mesh):
                for shapekey in mesh.data.shape_keys.key_blocks:
                    shapekey.name = Translate.fix_jp_chars(shapekey.name)

            fixed_uv_coords = 0
            for uv in mesh.data.uv_layers:
                uvs = np.empty(len(uv.data) * 2, dtype=np.float32)
                uv.data.foreach_get('uv', uvs)
                nan_mask = np.isnan(uvs)
                n_nan = int(nan_mask.sum())
                if n_nan:
                    uvs[nan_mask] = 0.0
                    uv.data.foreach_set('uv', uvs)
                    fixed_uv_coords += n_nan

        to_translate = []
        for bone in armature.data.bones:
            to_translate.append(bone.name)
        for pb in armature.pose.bones:
            pb.hide = False
        Translate.update_dictionary(to_translate)
        for bone in armature.data.bones:
            bone.name, translated = Translate.translate(bone.name)

        Common.set_default_stage()
        Common.unselect_all()
        Common.set_active(armature)

        Common.switch('POSE')
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()

        Common.switch('EDIT')

        for bone in armature.data.edit_bones:
            bone.hide = False

        Common.switch('OBJECT')

        for collection in list(armature.data.collections):
            armature.data.collections.remove(collection)

        Common.switch('EDIT')

        Common.delete_bone_constraints()


        steps += len(armature.data.edit_bones)
        
        bone_collections = armature.data.collections
        default_collection_name = "Bones"
        bone_collection = bone_collections.get(default_collection_name)
        if bone_collection is None:
            bone_collection = bone_collections.new(default_collection_name)
        bone_collection.is_visible = True

        for bone in armature.data.edit_bones:
            bone_collection.assign(bone)
        
        for bone in armature.data.edit_bones:
            if bone.name in Bones.bone_list or bone.name.startswith(tuple(Bones.bone_list_with)):
                if bone.parent is not None:
                    steps += 1
                else:
                    steps -= 1

        current_step = 0
        wm.progress_begin(current_step, steps)

        starts_with = [
            ('_', ''),
            ('ValveBiped_', ''),
            ('Valvebiped_', ''),
            ('Bip1_', 'Bip_'),
            ('Bip01_', 'Bip_'),
            ('Bip001_', 'Bip_'),
            ('Bip01', ''),
            ('Bip02_', 'Bip_'),
            ('Character1_', ''),
            ('HLP_', ''),
            ('JD_', ''),
            ('JU_', ''),
            ('Armature|', ''),
            ('Bone_', ''),
            ('C_', ''),
            ('Cf_S_', ''),
            ('Cf_J_', ''),
            ('G_', ''),
            ('Joint_', ''),
            ('Def_C_', ''),
            ('Def_', ''),
            ('DEF_', ''),
            ('Chr_', ''),
            ('Chr_', ''),
            ('B_', ''),
        ]
        ends_with = [
            ('_Bone', ''),
            ('_Bn', ''),
            ('_Le', '_L'),
            ('_Ri', '_R'),
            ('_', ''),
        ]
        replaces = [
            (' ', '_'),
            ('-', '_'),
            ('.', '_'),
            (':', '_'),
            ('____', '_'),
            ('___', '_'),
            ('__', '_'),
            ('_Le_', '_L_'),
            ('_Ri_', '_R_'),
            ('LEFT', 'Left'),
            ('RIGHT', 'Right'),
        ]

        for bone in armature.data.edit_bones:
            current_step += 1
            wm.progress_update(current_step)

            name = bone.name

            upper_name = ''
            for i, s in enumerate(name.split('_')):
                if i != 0:
                    upper_name += '_'
                upper_name += s[:1].upper() + s[1:]
            name = upper_name

            for replacement in replaces:
                name = name.replace(replacement[0], replacement[1])

            for replacement in starts_with:
                if name.startswith(replacement[0]):
                    name = replacement[1] + name[len(replacement[0]):]

            for replacement in ends_with:
                if name.endswith(replacement[0]):
                    name = name[:-len(replacement[0])] + replacement[1]

            name_split = name.split('_')
            if len(name_split) > 1 and name_split[0].isdigit():
                name = name_split[1]

            name_split = name.split('"')
            if len(name_split) > 3:
                name = name_split[1]

            if ':' in name:
                for i, split in enumerate(name.split(':')):
                    if i == 0:
                        name = ''
                    else:
                        name += split

            if name[-2:] == 'S0':
                name = name[:-2]

            if name[-4:] == '_Jnt':
                name = name[:-4]

            bone.name = name

        conflicting_bones = []
        for names in Bones.bone_list_conflicting_names:
            if '\\Left' not in names[1] and '\\L' not in names[1]:
                conflicting_bones.append(names)
                continue

            names0 = []
            name1 = ''
            name2 = ''
            for name0 in names[0]:
                names0.append(name0.replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l'))
            if '\\Left' in names[1] or '\\L' in names[1]:
                name1 = names[1].replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l')
            if '\\Left' in names[2] or '\\L' in names[2]:
                name2 = names[2].replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l')
            conflicting_bones.append((names0, name1, name2))

            for name0 in names[0]:
                names0.append(name0.replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r'))
            if '\\Left' in names[1] or '\\L' in names[1]:
                name1 = names[1].replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r')
            if '\\Left' in names[2] or '\\L' in names[2]:
                name2 = names[2].replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r')
            conflicting_bones.append((names0, name1, name2))

        for names in conflicting_bones:

            bone = None
            for bone_tmp in armature.data.edit_bones:
                if bone_tmp.name.lower() == names[1].lower():
                    bone = bone_tmp
                    break

            if not bone:
                continue

            found_all = True
            for name in names[0]:
                found = False
                for bone_tmp in armature.data.edit_bones:
                    if bone_tmp.name.lower() == name.lower():
                        found = True
                        break
                if not found:
                    found_all = False
                    break

            if found_all:
                bone.name = names[2]

        for bone in armature.data.edit_bones:
            bone.name = bone.name.replace('.', '_')

        spines = []
        spine_parts = []
        for bone_new, bones_old in temp_rename_bones.items():
            if "\\L" in bone_new:
                bones = [[bone_new.replace("\\Left", "Left").replace("\\L", "L"), ""],
                        [bone_new.replace("\\Left", "Right").replace("\\L", "R"), ""]]
            else:
                bones = [[bone_new, ""]]
            for bone_old in bones_old:
                if "\\L" in bone_new:
                    bones[0][1] = bone_old.replace("\\Left", "Left").replace("\\L", "L")
                    bones[1][1] = bone_old.replace("\\Left", "Right").replace("\\L", "R")
                else:
                    bones[0][1] = bone_old

                for bone in bones:
                    current_step += 1
                    wm.progress_update(current_step)

                    bone_final = None
                    for bone_tmp in armature.data.edit_bones:
                        if bone_tmp.name.lower() == bone[1].lower():
                            bone_final = bone_tmp
                            break

                    if not bone_final:
                        continue

                    if bone_new == 'Spine':
                        if len(bone_final.children) > 0:
                            spines.append(bone_final.name)
                        else:
                            spine_parts.append(bone_final.name)
                        continue

                    if bone[0] not in armature.data.edit_bones:
                        bone_final.name = bone[0]

        mixamo = False
        for bone in armature.data.edit_bones:
            if not mixamo and 'Mixamo' in bone.name:
                mixamo = True
                break

        for key, value in Bones.bone_list_rename_unknown_side.items():
            for bone in armature.data.edit_bones:
                parent = bone.parent
                if parent is None:
                    continue
                if parent.name == key or parent.name == key.lower():
                    if 'right' in bone.name.lower():
                        parent.name = 'Right ' + value
                        break
                    elif 'left' in bone.name.lower():
                        parent.name = 'Left ' + value
                        break

                parent = parent.parent
                if parent is None:
                    continue
                if parent.name == key or parent.name == key.lower():
                    if 'right' in bone.name.lower():
                        parent.name = 'Right ' + value
                        break
                    elif 'left' in bone.name.lower():
                        parent.name = 'Left ' + value
                        break

        for bone in armature.data.edit_bones:
            if bone.name in Bones.bone_list or bone.name.startswith(tuple(Bones.bone_list_with)):
                if bone.parent:
                    temp_list_reweight_bones[bone.name] = bone.parent.name
                else:
                    armature.data.edit_bones.remove(bone)
            else:
                bone.use_connect = False
                bone.roll = 0

        if 'Hips' in armature.data.edit_bones:
            hips = armature.data.edit_bones.get('Hips')
            hips.parent = None
            for bone in armature.data.edit_bones:
                if bone.parent is None:
                    bone.parent = hips


        spine_count = len(spines)

        if len(spine_parts) == 1 and not armature.data.edit_bones.get('Neck'):
            if spine_count == 0:
                armature.data.edit_bones.get(spine_parts[0]).name = 'Spine'
            else:
                spines.append(spine_parts[0])

        if spine_count == 0:
            pass

        elif spine_count == 1:
            print('BONE CREATION')
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.new('Chest')
            neck = armature.data.edit_bones.get('Neck')

            if neck:
                chest_top = neck.head
            else:
                chest_top = spine.tail

            spine.name = 'Spine'
            chest.name = 'Chest'

            chest.tail = chest_top
            chest.head = spine.head
            chest.head.z = spine.head.z + (chest_top.z - spine.head.z) / 2
            chest.head.y = spine.head.y + (chest_top.y - spine.head.y) / 2

            spine.tail = chest.head

            chest.parent = spine

            for bone in armature.data.edit_bones:
                if bone.parent == spine:
                    bone.parent = chest

        elif spine_count == 2:
            print('NORMAL')
            armature.data.edit_bones.get(spines[0]).name = 'Spine'
            armature.data.edit_bones.get(spines[1]).name = 'Chest'

        elif spine_count == 3:
            print('NORMAL')
            armature.data.edit_bones.get(spines[0]).name = 'Spine'
            armature.data.edit_bones.get(spines[1]).name = 'Chest'
            armature.data.edit_bones.get(spines[2]).name = 'Upper Chest'

        elif spine_count == 4 and source_engine:
            print('SOURCE ENGINE')
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.get(spines[2])

            chest.name = 'Chest'
            spine.name = 'Spine'

            spine.tail = chest.head

            temp_list_reweight_bones[spines[1]] = 'Spine'
            temp_list_reweight_bones[spines[3]] = 'Chest'

        elif spine_count > 2:
            print('MASS MERGING')
            print(spines)
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.get(spines[spine_count - 1])

            spine.name = 'Spine'
            chest.name = 'Chest'

            spine.tail = chest.head

            for spine in spines[1:spine_count-1]:
                print(spine)
                temp_list_reweight_bones[spine] = 'Spine'

        if 'Neck' not in armature.data.edit_bones:
            if 'Chest' in armature.data.edit_bones:
                if 'Head' in armature.data.edit_bones:
                    neck = armature.data.edit_bones.new('Neck')
                    chest = armature.data.edit_bones.get('Chest')
                    head = armature.data.edit_bones.get('Head')
                    neck.head = chest.tail
                    neck.tail = head.head

                    if neck.head.z == neck.tail.z:
                        neck.tail.z += 0.1

        if 'Head' in armature.data.edit_bones:
            head = armature.data.edit_bones.get('Head')
            head.tail.xy = head.head.xy
            if head.tail.z < head.head.z:
                head.tail.z = head.head.z + 0.1

        Common.correct_bone_positions()

        if not mixamo:
            if 'Hips' in armature.data.edit_bones:
                if 'Spine' in armature.data.edit_bones:
                    if 'Left leg' in armature.data.edit_bones:
                        if 'Right leg' in armature.data.edit_bones:
                            hips = armature.data.edit_bones.get('Hips')
                            spine = armature.data.edit_bones.get('Spine')
                            left_leg = armature.data.edit_bones.get('Left leg')
                            right_leg = armature.data.edit_bones.get('Right leg')


                            hips.head.x = (right_leg.head.x + left_leg.head.x) / 2

                            hips.head.z = left_leg.head.z + (spine.head.z - left_leg.head.z) * 0.33

                            if hips.head.z <= right_leg.head.z:
                                hips.head.z = right_leg.head.z + 0.1

                            hips.tail.xy = hips.head.xy
                            hips.tail.z = spine.head.z

                            if hips.tail.z < hips.head.z:
                                hips.tail.z += 0.1

                            right_knee = armature.data.edit_bones.get('Right knee')
                            left_knee = armature.data.edit_bones.get('Left knee')
                            leg_vectors = []
                            if left_knee:
                                leg_vectors.append((left_leg.head, left_knee.head))
                            if right_knee:
                                leg_vectors.append((right_leg.head, right_knee.head))
                            for leg_head, knee_head in leg_vectors:
                                if all(round(leg, 4) == round(knee, 4) for leg, knee in zip(leg_head.xy, knee_head.xy)):
                                    print('FIXING LEG')
                                    knee_head.y -= 0.001

        def add_eye_children(eye_bone, parent_name):
            for eye in eye_bone.children:
                temp_list_reweight_bones[eye.name] = parent_name
                add_eye_children(eye, parent_name)

        for eye_name in ['Eye_L', 'Eye_R']:
            if eye_name in armature.data.edit_bones:
                eye = armature.data.edit_bones.get(eye_name)
                add_eye_children(eye, eye.name)

        if 'Hips' in armature.data.edit_bones:

            hips = armature.pose.bones.get('Hips')

            obj = hips.id_data
            matrix_final = obj.matrix_world @ hips.matrix

            if matrix_final[2][3] < 0:
                rot_x_neg180 = Matrix.Rotation(-math.pi, 4, 'X')
                armature.matrix_world = rot_x_neg180 @ armature.matrix_world

                for mesh in meshes:
                    mesh.rotation_euler = (math.radians(180), 0, 0)

        Common.fix_zero_length_bones(armature)

        bones_to_delete = []
        
        meshes = Common.get_meshes_objects()

        for mesh in meshes:
            Common.unselect_all()
            Common.switch('OBJECT')
            Common.set_active(mesh)


            for mod in mesh.modifiers:
                if mod.type == 'ARMATURE':
                    bpy.ops.object.modifier_remove(modifier=mod.name)

            print('FIX TWIST BONES')
            print(bones_to_delete)
            Common.fix_twist_bones(mesh, bones_to_delete)
            print(bones_to_delete)

            for name in Bones.bone_reweigth_to_parent:
                if "\\L" in name:
                    bones = [name.replace("\\Left", "Left").replace("\\L", "L"),
                             name.replace("\\Left", "Right").replace("\\L", "R")]
                else:
                    bones = [name]

                for bone_name in bones:
                    bone_child = None
                    bone_parent = None
                    for bone in armature.data.bones:
                        if bone_name.lower() == bone.name.lower():
                            bone_child = bone
                            bone_parent = bone.parent

                    if not bone_child or not bone_parent:
                        continue

                    if context.scene.keep_twist_bones and 'twist' in bone_child.name.lower():
                        continue
                    if context.scene.fix_twist_bones and bone_child.name.lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                        print('TWIST FOUND!')
                        continue

                    parent_in_list = True
                    while parent_in_list:
                        parent_in_list = False
                        for name_tmp in Bones.bone_reweigth_to_parent:
                            if bone_parent.name == name_tmp.replace("\\Left", "Left").replace("\\L", "L") \
                                    or bone_parent.name == name_tmp.replace("\\Left", "Right").replace("\\L", "R"):
                                bone_parent = bone_parent.parent
                                parent_in_list = True
                                break

                    if not bone_parent:
                        continue

                    if bone_child.name not in mesh.vertex_groups:
                        if bone_child.name not in bones_to_delete:
                            bones_to_delete.append(bone_child.name)
                        continue

                    if bone_parent.name not in mesh.vertex_groups:
                        mesh.vertex_groups.new(name=bone_parent.name)

                    bone_tmp = armature.data.bones.get(bone_child.name)
                    if bone_tmp:
                        for child in bone_tmp.children:
                            if not temp_list_reparent_bones.get(child.name):
                                temp_list_reparent_bones[child.name] = bone_parent.name

                    if bone_child.name not in bones_to_delete:
                        bones_to_delete.append(bone_child.name)

                    Common.mix_weights(mesh, bone_child.name, bone_parent.name)

            for bone_new, bones_old in temp_reweight_bones.items():
                if "\\L" in bone_new:
                    bones = [[bone_new.replace("\\Left", "Left").replace("\\L", "L"), ""],
                             [bone_new.replace("\\Left", "Right").replace("\\L", "R"), ""]]
                else:
                    bones = [[bone_new, ""]]
                for bone_old in bones_old:
                    if "\\L" in bone_new:
                        bones[0][1] = bone_old.replace("\\Left", "Left").replace("\\L", "L")
                        bones[1][1] = bone_old.replace("\\Left", "Right").replace("\\L", "R")
                    else:
                        bones[0][1] = bone_old

                    for bone in bones:
                        current_step += 1
                        wm.progress_update(current_step)

                        vg = None
                        for vg_tmp in mesh.vertex_groups:
                            if vg_tmp.name.lower() == bone[1].lower():
                                vg = vg_tmp
                                break

                        if not vg:
                            if bone[1] not in bones_to_delete:
                                bones_to_delete.append(bone[1])
                            continue

                        if bone[0] == vg.name:
                            print('BUG: ' + bone[0] + ' tried to mix weights with itself!')
                            continue

                        if context.scene.keep_twist_bones and 'twist' in bone[1].lower():
                            continue
                        if context.scene.fix_twist_bones and bone[1].lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                            print('TWIST FOUND!')
                            continue


                        if mesh.vertex_groups.get(bone[0]) is None:
                            if bone[0] in Bones.dont_delete_these_bones and bone[0] in armature.data.bones:
                                bpy.ops.object.vertex_group_add()
                                mesh.vertex_groups.active.name = bone[0]
                                if mesh.vertex_groups.get(bone[0]) is None:
                                    continue
                            else:
                                continue

                        bone_tmp = armature.data.bones.get(vg.name)
                        if bone_tmp:
                            for child in bone_tmp.children:
                                if not temp_list_reparent_bones.get(child.name):
                                    temp_list_reparent_bones[child.name] = bone[0]

                        if vg.name not in bones_to_delete:
                            bones_to_delete.append(vg.name)

                        Common.mix_weights(mesh, vg.name, bone[0])

            for key, value in temp_list_reweight_bones.items():
                current_step += 1
                wm.progress_update(current_step)

                vg_from = None
                vg_to = None
                for vg_tmp in mesh.vertex_groups:
                    if vg_tmp.name.lower() == key.lower():
                        vg_from = vg_tmp
                        if vg_to:
                            break
                    elif vg_tmp.name.lower() == value.lower():
                        vg_to = vg_tmp
                        if vg_from:
                            break

                if not vg_from:
                    if key not in bones_to_delete:
                        bones_to_delete.append(key)
                    continue

                if not vg_to:
                    continue

                if context.scene.keep_twist_bones and 'twist' in vg_from.name.lower():
                    continue
                if context.scene.fix_twist_bones and vg_from.name.lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                    print('TWIST FOUND!')
                    continue

                bone_tmp = armature.data.bones.get(vg_from.name)
                if bone_tmp:
                    for child in bone_tmp.children:
                        if not temp_list_reparent_bones.get(child.name):
                            temp_list_reparent_bones[child.name] = vg_to.name

                if vg_from.name == vg_to.name:
                    print('BUG: ' + vg_to.name + ' tried to mix weights with itself!')
                    continue

                if vg_from.name not in bones_to_delete:
                    bones_to_delete.append(vg_from.name)

                Common.mix_weights(mesh, vg_from.name, vg_to.name)

            mod = mesh.modifiers.new("Armature", 'ARMATURE')
            mod.object = armature

            if not context.scene.keep_upper_chest:
                if 'Upper Chest' in mesh.vertex_groups and 'Chest' in mesh.vertex_groups:
                    Common.mix_weights(mesh, 'Upper Chest', 'Chest')

                    if 'Upper Chest' not in bones_to_delete:
                        bones_to_delete.append('Upper Chest')

        Common.unselect_all()
        Common.set_active(armature)
        Common.switch('EDIT')

        for bone_name in bones_to_delete:
            if bone_name in armature.data.edit_bones:
                armature.data.edit_bones.remove(armature.data.edit_bones.get(bone_name))

        for key, value in temp_list_reparent_bones.items():
            if value == 'Upper Chest' and 'Upper Chest' not in armature.data.edit_bones:
                value = 'Chest'

            if key in armature.data.edit_bones and value in armature.data.edit_bones:
                armature.data.edit_bones.get(key).parent = armature.data.edit_bones.get(value)

        Common.fix_twist_bone_names(armature)

        if context.scene.remove_zero_weight:
            Common.remove_unused_vertex_groups()

            Common.delete_zero_weight()

        if context.scene.connect_bones:
            Common.fix_bone_orientations(armature)


        hierarchy_check_hips = check_hierarchy(False, [
            ['Hips', 'Spine', 'Chest', 'Neck', 'Head'],
            ['Hips', 'Left leg', 'Left knee', 'Left ankle'],
            ['Hips', 'Right leg', 'Right knee', 'Right ankle'],
            ['Chest', 'Left shoulder', 'Left arm', 'Left elbow', 'Left wrist'],
            ['Chest', 'Right shoulder', 'Right arm', 'Right elbow', 'Right wrist']
        ])

        Common.fix_armature_names()
        
        fixed_uv_coords = False
        armature.show_in_front = False
        wm.progress_end()

        if not hierarchy_check_hips['result']:
            self.report({'ERROR'}, hierarchy_check_hips['message'])
            saved_data.load()
            return {'FINISHED'}

        if fixed_uv_coords:
            saved_data.load()
            Common.show_error(6.2, [t('FixArmature.error.faultyUV1', uvcoord=str(fixed_uv_coords)),
                                          t('FixArmature.error.faultyUV2'),
                                          t('FixArmature.error.faultyUV3')])
            return {'FINISHED'}

        if bone_cache:
            bone_cache.clear_cache()
            del bone_cache

        saved_data.load()

        self.report({'INFO'}, t('FixArmature.fixedSuccess'))
        return {'FINISHED'}


def check_hierarchy(check_parenting, correct_hierarchy_array):
    armature = Common.set_default_stage()

    missing_bones = []
    missing2 = [t('FixArmature.bonesNotFound'), '']

    for correct_hierarchy in correct_hierarchy_array:
        line = ' - '

        for index, bone in enumerate(correct_hierarchy):
            if bone not in missing_bones and bone not in armature.data.bones:
                missing_bones.append(bone)
                if len(line) > 3:
                    line += ', '
                line += bone

        if len(line) > 3:
            missing2.append(line)

    if len(missing2) > 2 and not check_parenting:
        missing2.append('')
        missing2.append(t('FixArmature.cantFix1'))
        missing2.append(t('FixArmature.cantFix2'))
        missing2.append(t('FixArmature.cantFix3'))

        Common.show_error(6.4, missing2)
        return {'result': True, 'message': ''}

    if check_parenting:
        for correct_hierarchy in correct_hierarchy_array:
            previous = None
            for index, bone in enumerate(correct_hierarchy):
                if index > 0:
                    previous = correct_hierarchy[index - 1]

                if bone in armature.data.bones:
                    bone = armature.data.bones[bone]

                    if previous is not None:
                        if bone.parent is None:
                            return {'result': False, 'message': bone.name + t('FixArmature.notParent')}
                        if previous != bone.parent.name:
                            return {'result': False, 'message': bone.name + t('FixArmature.notParentTo1') + previous + t('FixArmature.notParentTo2')}

    return {'result': True}
