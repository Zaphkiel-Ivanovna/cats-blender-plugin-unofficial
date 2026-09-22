# MIT License

import re
import bpy
import time
import bmesh
import numpy as np

from bpy.types import (
    ShapeKey,
    Object,
)

from mathutils import Vector
from html.parser import HTMLParser
from functools import lru_cache
from html.entities import name2codepoint
from typing import Any

from . import iconloader as Iconloader
from . import translate as Translate
from . import armature_bones as Bones
from .register import register_wrap
from .translations import t
from sys import intern

from mmd_tools_local import utils
import contextlib

def get_objects():
    return bpy.context.view_layer.objects


def get_enum_property_value(property_holder, property_name, items_func=None):
    """Safely get an enum property value, handling integer indices from Blender 5.0.

    Args:
        property_holder: The object holding the property (e.g., context.scene)
        property_name: Name of the enum property
        items_func: Optional function to get valid items. If provided, integer indices
                   will be converted to their corresponding identifier strings.

    Returns:
        The string identifier value of the enum, or empty string if invalid.
    """
    try:
        value = getattr(property_holder, property_name, None)
        if value is None:
            return ''

        if isinstance(value, str):
            return value

        if isinstance(value, int) and items_func is not None:
            try:
                items = items_func(property_holder, bpy.context)
                if items and 0 <= value < len(items):
                    return items[value][0]
            except Exception:
                pass

        return str(value) if value is not None else ''
    except Exception:
        return ''


class SavedData:
    __object_properties = {}
    __active_object = None

    def __init__(self):
        context = bpy.context
        self.__object_properties = {}
        self.__active_object = None

        for obj in get_objects():
            mode = obj.mode
            selected = obj.select_get()
            hidden = is_hidden(obj)
            pose = None
            if obj.type == 'ARMATURE':
                pose = obj.data.pose_position
            self.__object_properties[obj.name] = [mode, selected, hidden, pose]

            active = context.view_layer.objects.active
            if active:
                self.__active_object = active.name

    def load(self, ignore=None, load_mode=True, load_select=True, load_hide=True, load_active=True, hide_only=False):
        if not ignore:
            ignore = []
        if hide_only:
            load_mode = False
            load_select = False
            load_active = False

        for obj_name, values in self.__object_properties.items():
            if obj_name in ignore:
                continue

            obj = get_objects().get(obj_name)
            if not obj:
                continue

            mode, selected, hidden, pose = values
            print(obj_name, pose)

            if load_mode and obj.mode != mode:
                set_active(obj, skip_sel=True)
                switch(mode, check_mode=False)
                if pose:
                    obj.data.pose_position = pose

            if load_select:
                select(obj, selected)
            if load_hide:
                hide(obj, hidden)

        if load_active and self.__active_object and get_objects().get(self.__active_object):
            context = bpy.context
            if self.__active_object not in ignore and self.__active_object != context.view_layer.objects.active:
                set_active(get_objects().get(self.__active_object), skip_sel=True)

def get_armature(armature_name=None):
    if not armature_name:
        armature_name = get_enum_property_value(bpy.context.scene, 'armature', get_armature_list)

    if isinstance(armature_name, int):
        armatures = get_armature_objects()
        if 0 <= armature_name < len(armatures):
            return armatures[armature_name]
        if armatures:
            return armatures[0]
        return None

    objects = get_objects()
    if not objects:
        return None

    for obj in objects:
        if obj and obj.type == 'ARMATURE' and obj.name == armature_name:
            return obj

    if is_enum_empty(armature_name):
        for obj in objects:
            if obj and obj.type == 'ARMATURE':
                return obj

    for obj in objects:
        if obj and obj.type == 'ARMATURE':
            return obj

    return None

def get_armature_objects():
    armatures = []
    for obj in get_objects():
        if obj.type == 'ARMATURE':
            armatures.append(obj)
    return armatures


def get_top_parent(child):
    if child.parent:
        return get_top_parent(child.parent)
    return child


def unhide_all_unnecessary():
    try:
        switch('OBJECT')
        bpy.ops.object.hide_view_clear()
    except RuntimeError:
        pass

    for collection in bpy.data.collections:
        collection.hide_select = False
        collection.hide_viewport = False


def unhide_all():
    for obj in get_objects():
        hide(obj, False)
        set_unselectable(obj, False)

        unhide_all_unnecessary()


def unhide_children(parent):
    for child in parent.children:
        hide(child, False)
        set_unselectable(child, False)
        unhide_children(child)


def unhide_all_of(obj_to_unhide=None):
    if not obj_to_unhide:
        return

    top_parent = get_top_parent(obj_to_unhide)
    hide(top_parent, False)
    set_unselectable(top_parent, False)
    unhide_children(top_parent)


def unselect_all():
    for obj in get_objects():
        select(obj, False)


def set_active(obj, skip_sel=False):
    if not skip_sel:
        select(obj)
        bpy.context.view_layer.objects.active = obj


def select(obj, sel=True):
    if obj is not None:
        hide(obj, False)
        obj.select_set(sel)


def hide(obj, val=True):
    if hasattr(obj, 'hide_set'):
        obj.hide_set(val)
    elif hasattr(obj, 'hide'):
        obj.hide = val


def is_hidden(obj):
    if hasattr(obj, 'hide_get'):
        return obj.hide_get()
    if hasattr(obj, 'hide'):
        return obj.hide
    return False


def set_unselectable(obj, val=True):
    obj.hide_select = val


def switch(new_mode, check_mode=True):
    context = bpy.context
    active = context.view_layer.objects.active
    if check_mode and active and active.mode == new_mode:
        return

    if active is None:
        print(f"Warning: No active object when trying to switch to {new_mode} mode")
        return

    supported_modes = []
    if active.type == 'MESH':
        supported_modes = ['OBJECT', 'EDIT', 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT']
    elif active.type == 'ARMATURE':
        supported_modes = ['OBJECT', 'EDIT', 'POSE']
    elif active.type in ['CURVE', 'SURFACE', 'META', 'FONT'] or active.type == 'LATTICE':
        supported_modes = ['OBJECT', 'EDIT']
    else:
        supported_modes = ['OBJECT']

    if new_mode not in supported_modes:
        print(f"Warning: {active.type} object '{active.name}' does not support {new_mode} mode. Supported modes: {supported_modes}")
        return

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=new_mode, toggle=False)


def remove_rigidbodies_global():

    if bpy.context.scene.remove_rigidbodies_joints_global:
        print('Collections:')
        for collection in list(bpy.data.collections):
            print(' ' + collection.name, collection.name.lower())
            if 'rigidbody' in collection.name.lower():
                print('DELETE')
                for obj in list(collection.objects):
                    delete(obj)
                bpy.data.collections.remove(collection)

    armature = get_armature()
    if armature:
        set_active(armature)

    return armature

def set_default_stage():
    """
    Selects the armature, unhides everything and sets the modes of every object to object mode
    :return: the armature
    """

    unhide_all()
    unselect_all()

    for obj in get_objects():
        set_active(obj)
        switch('OBJECT')
        if obj.type == 'ARMATURE':
            pass

        select(obj, False)

    armature = get_armature()
    if armature:
        set_active(armature)

    return armature


def apply_modifier(mod, as_shapekey=False):
    if as_shapekey:
        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=False, modifier=mod.name)
    else:
        bpy.ops.object.modifier_apply(modifier=mod.name)


def remove_bone(find_bone):
    armature = get_armature()
    switch('EDIT')
    edit_bones = armature.data.edit_bones
    bone = edit_bones.get(find_bone)
    if bone:
        edit_bones.remove(bone)


def remove_empty():
    armature = set_default_stage()
    if armature and armature.parent and armature.parent.type == 'EMPTY':
        unselect_all()
        set_active(armature.parent)
        bpy.ops.object.delete(use_global=False)
        unselect_all()


def remove_unused_vertex_groups(ignore_main_bones=False, meshes=None):
    remove_count = 0
    unselect_all()
    for mesh in get_meshes_objects(mode=2) if meshes is None else meshes:
        mesh.update_from_editmode()

        vgroup_used = {i: False for i, k in enumerate(mesh.vertex_groups)}

        for v in mesh.data.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    vgroup_used[g.group] = True

        for i, used in sorted(vgroup_used.items(), reverse=True):
            if not used:
                if ignore_main_bones and mesh.vertex_groups[i].name in Bones.dont_delete_these_main_bones:
                    continue
                mesh.vertex_groups.remove(mesh.vertex_groups[i])
                remove_count += 1
    return remove_count


def find_center_vector_of_vertex_group(mesh, vertex_group):
    data = mesh.data
    verts = data.vertices
    verts_in_group = []

    vg = mesh.vertex_groups.get(vertex_group)
    if vg is None:
        return None
    for vert in verts:
        i = vert.index
        try:
            if vg.weight(i) > 0:
                verts_in_group.append(vert)
        except RuntimeError:
            pass

    if not verts_in_group:
        return None
    total = Vector()
    for vert in verts_in_group:
        total += vert.co

    return total / len(verts_in_group)


def vertex_group_exists(mesh_name, bone_name):
    mesh = get_objects()[mesh_name]
    data = mesh.data
    verts = data.vertices

    for vert in verts:
        i = vert.index
        try:
            mesh.vertex_groups[bone_name].weight(i)
            return True
        except Exception:
            pass

    return False


def get_meshes(self, context):

    choices = []

    for mesh in get_meshes_objects(mode=0, check=False):
        choices.append((mesh.name, mesh.name, mesh.name))

    return _sort_enum_choices_by_identifier_lower(choices)


def get_top_meshes(self, context):
    choices = []

    for mesh in get_meshes_objects(mode=1, check=False):
        choices.append((mesh.name, mesh.name, mesh.name))

    return choices


def get_armature_list(self, context):
    choices = []

    for armature in get_armature_objects():
        name = armature.data.name
        if name.startswith('Armature ('):
            name = armature.name + ' (' + name.replace('Armature (', '')[:-1] + ')'

        choices.append((armature.name, name, armature.name))

    return choices


def validate_armature_selection():
    """Validate and fix the scene's armature selection if it's invalid. Safe to call from UI draw or operators."""
    try:
        context = bpy.context
        if not context or not context.scene:
            return

        current_armature = context.scene.armature
        available_armatures = [obj.name for obj in get_armature_objects()]

        if not available_armatures:
            return

        new_armature = None

        if isinstance(current_armature, int):
            if current_armature < 0 or current_armature >= len(available_armatures):
                new_armature = available_armatures[0]
        elif isinstance(current_armature, str):
            if current_armature not in available_armatures:
                new_armature = available_armatures[0]

        if new_armature:
            try:
                context.scene.armature = new_armature
            except (AttributeError, TypeError):
                def fix_armature_selection():
                    with contextlib.suppress(Exception):
                        bpy.context.scene.armature = new_armature
                    return
                bpy.app.timers.register(fix_armature_selection)
    except Exception:
        pass


def update_armature_selection(self, context):
    """Update callback for armature selection. Validates and updates material list."""
    try:
        validate_armature_selection()
        update_material_list(self, context)
    except Exception:
        pass


def get_armature_merge_list(self, context):
    choices = []
    current_armature = get_enum_property_value(context.scene, 'merge_armature_into', get_armature_list)

    for armature in get_armature_objects():
        if armature.name != current_armature:
            name = armature.data.name
            if name.startswith('Armature ('):
                name = armature.name + ' (' + name.replace('Armature (', '')[:-1] + ')'

            choices.append((armature.name, name, armature.name))

    return choices


def get_bone_orientations(armature):
    x_cord = 0
    y_cord = 1
    z_cord = 2
    fbx = False
    return x_cord, y_cord, z_cord, fbx


def get_bones_head(self, context):
    return get_bones(names=['Head'])


def get_bones_eye_l(self, context):
    return get_bones(names=['Eye_L', 'EyeReturn_L'])


def get_bones_eye_r(self, context):
    return get_bones(names=['Eye_R', 'EyeReturn_R'])


def get_bones_merge(self, context):
    armature_name = get_enum_property_value(bpy.context.scene, 'merge_armature_into', get_armature_list)
    return get_bones(armature_name=armature_name)


def get_bones(names=None, armature_name=None, check_list=False):
    if not names:
        names = []
    if not armature_name:
        armature_name = get_enum_property_value(bpy.context.scene, 'armature', get_armature_list)

    choices = []
    armature = get_armature(armature_name=armature_name)

    if not armature:
        return choices

    for bone in armature.data.bones:
        try:
            choices.append((bone.name, bone.name, bone.name))
        except UnicodeDecodeError:
            print("ERROR", bone.name)

    _sort_enum_choices_by_identifier_lower(choices)

    choices2 = []
    for name in names:
        if name in armature.data.bones and choices[0][0] != name:
            choices2.append((name, name, name))

    if not check_list:
        choices2.extend(choices)

    return choices2


def get_shapekeys_mouth_ah(self, context):
    return get_shapekeys(context, ['MTH A', 'Ah', 'A'], True, False, False)


def get_shapekeys_mouth_oh(self, context):
    return get_shapekeys(context, ['MTH U', 'Oh', 'O', 'Your'], True, False, False)


def get_shapekeys_mouth_ch(self, context):
    return get_shapekeys(context, ['MTH I', 'Glue', 'Ch', 'I', 'There'], True, False, False)


def get_shapekeys_eye_blink_l(self, context):
    return get_shapekeys(context, ['EYE Close L', 'Wink 2', 'Wink', 'Wink left', 'Wink Left', 'Blink (Left)', 'Blink', 'Basis'], False, False, False)


def get_shapekeys_eye_blink_r(self, context):
    return get_shapekeys(context, ['EYE Close R', 'Wink 2 right', 'Wink 2 Right', 'Wink right 2', 'Wink Right 2', 'Wink right', 'Wink Right', 'Blink (Right)', 'Basis'], False, False, False)


def get_shapekeys_eye_low_l(self, context):
    return get_shapekeys(context, ['Basis'], False, False, False)


def get_shapekeys_eye_low_r(self, context):
    return get_shapekeys(context, ['Basis'], False, False, False)


def get_shapekeys(context, names, is_mouth, no_basis, return_list):
    choices = []
    choices_simple = []
    meshes_list = get_meshes_objects(check=False)

    if meshes_list:
        if is_mouth:
            meshes = [get_objects().get(context.scene.mesh_name_viseme)]
        else:
            meshes = [get_objects().get(context.scene.mesh_name_eye)]
    else:
        return choices

    for mesh in meshes:
        if not mesh or not has_shapekeys(mesh):
            return choices

        for shapekey in mesh.data.shape_keys.key_blocks:
            name = shapekey.name
            if name in choices_simple:
                continue
            if no_basis and name == 'Basis':
                continue
            choices.append((name, name, name))
            choices_simple.append(name)

    _sort_enum_choices_by_identifier_lower(choices)

    choices2 = []
    for name in names:
        if name in choices_simple and len(choices) > 1 and choices[0][0] != name:
            continue
        choices2.append((name, name, name))

    choices2.extend(choices)

    if return_list:
        shape_list = []
        for choice in choices2:
            shape_list.append(choice[0])
        return shape_list

    return choices2


def fix_armature_names(armature_name=None):
    if not armature_name:
        armature_name = get_enum_property_value(bpy.context.scene, 'armature', get_armature_list)
    base_armature = get_armature(armature_name=get_enum_property_value(bpy.context.scene, 'merge_armature_into', get_armature_list))
    merge_armature = get_armature(armature_name=get_enum_property_value(bpy.context.scene, 'merge_armature', get_armature_merge_list))

    armature = get_armature(armature_name=armature_name)
    armature.name = 'Armature'
    if not armature.data.name.startswith('Armature'):
        Translate.update_dictionary(armature.data.name)
        armature.data.name = 'Armature (' + Translate.translate(armature.data.name, add_space=True)[0] + ')'

    with contextlib.suppress(TypeError):
        bpy.context.scene.armature = armature.name

    try:
        if base_armature:
            bpy.context.scene.merge_armature_into = base_armature.name
    except TypeError:
        pass

    try:
        if merge_armature:
            bpy.context.scene.merge_armature = merge_armature.name
    except TypeError:
        pass


def get_meshes_objects(armature_name=None, mode=0, check=True, visible_only=False):
    context = bpy.context

    if not armature_name:
        armature = get_armature()
        if armature:
            armature_name = armature.name

    meshes = []

    for ob in get_objects():
            if ob is None:
                continue
            if ob.type != 'MESH':
                continue

            if mode == 0 or mode == 5:
                if ob.parent:
                    if (ob.parent.type == 'ARMATURE' and ob.parent.name == armature_name) or (ob.parent.parent and ob.parent.parent.type == 'ARMATURE' and ob.parent.parent.name == armature_name):
                        meshes.append(ob)

            elif mode == 1:
                if not ob.parent:
                    meshes.append(ob)

            elif mode == 2 or (mode == 3 and ob.select_get()):
                meshes.append(ob)

    if visible_only:
        meshes = [mesh for mesh in meshes if not is_hidden(mesh)]

    if check:
        current_active = context.view_layer.objects.active
        to_remove = []
        for mesh in meshes:
            selected = mesh.select_get()
            set_active(mesh)

            if not context.view_layer.objects.active:
                to_remove.append(mesh)

            if not selected:
                select(mesh, False)

        for mesh in to_remove:
            print('DELETED CORRUPTED MESH:', mesh.name, mesh.users)
            meshes.remove(mesh)
            delete(mesh)

        if current_active:
            set_active(current_active)

    return meshes

def get_meshes_objects_for_export(armature_name=None, mode=0, check=True):
    if not armature_name:
        armature = get_armature()
        if armature:
            armature_name = armature.name

    meshes = []

    for ob in get_objects():
        if ob is None or ob.type != 'MESH':
            continue

        if is_hidden(ob):
            continue

        if mode == 0 or mode == 5:
            if ob.parent:
                if (ob.parent.type == 'ARMATURE' and ob.parent.name == armature_name) or (ob.parent.parent and ob.parent.parent.type == 'ARMATURE' and ob.parent.parent.name == armature_name):
                    meshes.append(ob)
        elif mode == 1:
            if not ob.parent:
                meshes.append(ob)
        elif mode == 2 or (mode == 3 and ob.select_get()):
            meshes.append(ob)

    return meshes

def join_meshes(armature_name=None, mode=0, apply_transformations=True, repair_shape_keys=True):
    context = bpy.context

    if not armature_name:
        armature_name = bpy.context.scene.armature

    meshes_to_join = get_meshes_objects(armature_name=armature_name, mode=3 if mode == 1 else 0)
    if not meshes_to_join:
        return None

    for mesh in meshes_to_join:
        if mesh.data.users > 1:
            show_error(4, [t('JoinMeshes.error.not_single_user'),
                           t('JoinMeshes.error.make_single_user'),
                           t('JoinMeshes.error.make_single_user1'),
                           t('JoinMeshes.error.make_single_user2')])
            return None

    set_default_stage()
    unselect_all()

    if apply_transformations:
        apply_transforms(armature_name=armature_name)

    unselect_all()

    for mesh in meshes_to_join:
        set_active(mesh)

        for mod in list(mesh.modifiers):
            if mod.type == 'SUBSURF':
                mesh.modifiers.remove(mod)

        if mesh.data.uv_layers:
            mesh.data.uv_layers[0].name = 'UVMap'


    active_mesh_name = context.view_layer.objects.active.name

    if bpy.ops.object.join.poll():
        bpy.ops.object.join()
    else:
        print('NO MESH COMBINED!')

    context = bpy.context


    for mesh in get_meshes_objects(armature_name=armature_name):
        if mesh.name == active_mesh_name:
            set_active(mesh)

    mesh = context.view_layer.objects.active
    if mesh:
        if len(get_meshes_objects(armature_name=armature_name)) == 1:
            mesh.name = 'Body'
        mesh.parent_type = 'OBJECT'

        repair_mesh(mesh, armature_name)

        if repair_shape_keys:
            repair_shapekey_order(mesh.name, armature_name)

        sort_material_slots(mesh)

    update_material_list()

    return mesh


def repair_mesh(mesh, armature_name):
    mesh.parent_type = 'OBJECT'

    mod_count = 0
    for mod in list(mesh.modifiers):
        mod.show_expanded = False
        if mod.type == 'ARMATURE':
            mod_count += 1
            if mod_count > 1:
                mesh.modifiers.remove(mod)
                continue
            mod.object = get_armature(armature_name=armature_name)
            mod.show_viewport = True

    if mod_count == 0:
        mod = mesh.modifiers.new("Armature", 'ARMATURE')
        mod.object = get_armature(armature_name=armature_name)


def apply_transforms(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
    armature = get_armature(armature_name=armature_name)

    unselect_all()
    set_active(armature)
    switch('OBJECT')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for mesh in get_meshes_objects(armature_name=armature_name):
        unselect_all()
        set_active(mesh)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_transforms_to_mesh(mesh):
    """Apply transforms to a single mesh object."""
    unselect_all()
    set_active(mesh)
    switch('OBJECT')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_all_transforms():

    def apply_transforms_with_children(parent):
        unselect_all()
        set_active(parent)
        switch('OBJECT')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for child in parent.children:
            apply_transforms_with_children(child)

    for obj in get_objects():
        if not obj.parent:
            apply_transforms_with_children(obj)


def separate_by_materials(context, mesh):
    prepare_separation(mesh)

    utils.separateByMaterials(mesh)

    for ob in context.selected_objects:
        if ob.type == 'MESH':
            hide(ob, False)
            clean_shapekeys(ob)

    utils.clearUnusedMeshes()

    update_material_list()


def separate_by_loose_parts(context, mesh):
    prepare_separation(mesh)

    remove_doubles(mesh, 0, save_shapes=True)

    set_active(mesh)
    switch('EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    bpy.ops.mesh.separate(type='LOOSE')

    meshes = []
    for obj in context.selected_objects:
        if obj.type == 'MESH':
            hide(obj, False)
            meshes.append(obj)

    wm = bpy.context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(meshes))

    for mesh in meshes:
        clean_shapekeys(mesh)

        current_step += 1
        wm.progress_update(current_step)

    wm.progress_end()

    switch('OBJECT')

    utils.clearUnusedMeshes()

    update_material_list()


def separate_by_shape_keys(context, mesh):
    prepare_separation(mesh)

    switch('EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')

    switch('OBJECT')
    vertex_count = len(mesh.data.vertices)
    moved_by_shape_key = np.zeros(vertex_count, dtype=bool)
    if has_shapekeys(mesh):
        for kb in mesh.data.shape_keys.key_blocks:
            relative_key = kb.relative_key
            if relative_key is None or relative_key == kb:
                continue
            same = _get_shape_key_co(kb) == _get_shape_key_co(relative_key)
            moved_by_shape_key |= ~np.all(same.reshape(-1, 3), axis=1)

    selected_count = int(moved_by_shape_key.sum())
    if not selected_count or selected_count == vertex_count:
        return False

    mesh.data.vertices.foreach_set('select', moved_by_shape_key)

    switch('EDIT')
    bpy.ops.mesh.select_all(action='INVERT')

    bpy.ops.mesh.separate(type='SELECTED')

    for ob in context.selected_objects:
        if ob.type == 'MESH':
            active_tmp = context.view_layer.objects.active
            if ob != active_tmp:
                print('not active', ob.name)
                ob.name = ob.name.replace('.001', '') + '.no_shapes'
                set_active(ob)
                bpy.ops.object.shape_key_remove(all=True)
                set_active(active_tmp)
                select(ob, False)
            else:
                print('active', ob.name)
                clean_shapekeys(ob)
                switch('OBJECT')

    utils.clearUnusedMeshes()

    update_material_list()
    return True


def prepare_separation(mesh):
    set_default_stage()
    unselect_all()

    if bpy.context.scene.remove_rigidbodies_joints:
        for obj in get_objects():
            if 'rigidbodies' in obj.name or 'joints' in obj.name:
                delete_hierarchy(obj)

    save_shapekey_order(mesh.name)
    set_active(mesh)

    for mod in mesh.modifiers:
        mod.show_expanded = False

    clean_material_names(mesh)


def clean_shapekeys(mesh):
    if has_shapekeys(mesh):
        co_getter = lru_cache(maxsize=None)(_get_shape_key_co)
        for kb in list(mesh.data.shape_keys.key_blocks):
            if can_remove_shapekey(kb, co_getter):
                mesh.shape_key_remove(kb)
        del co_getter
        if len(mesh.data.shape_keys.key_blocks) == 1:
            mesh.shape_key_remove(mesh.data.shape_keys.key_blocks[0])


def can_remove_shapekey(key_block, co_getter=None):
    if 'mmd_' in key_block.name:
        return True
    relative_key = key_block.relative_key
    if relative_key is None or relative_key == key_block:
        return False
    if co_getter is None:
        co_getter = _get_shape_key_co
    return np.array_equal(co_getter(key_block), co_getter(relative_key))


def save_shapekey_order(mesh_name):
    mesh = get_objects()[mesh_name]
    armature = get_armature()

    if not armature:
        return

    sys_props = armature.bl_system_properties_get()
    if not sys_props:
        return

    custom_data = sys_props.get('CUSTOM')

    if not custom_data:
        custom_data = {}

    shape_key_order = []
    if has_shapekeys(mesh):
        for _index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            shape_key_order.append(shapekey.name)

    if custom_data.get('shape_key_order'):
        old_len = len(custom_data.get('shape_key_order'))

        if type(shape_key_order) is str:
            old_len = len(shape_key_order.split(',,,'))

        if len(shape_key_order) <= old_len:
            return

    custom_data['shape_key_order'] = shape_key_order

    sys_props = armature.bl_system_properties_get()
    if sys_props:
        sys_props['CUSTOM'] = custom_data


def repair_shapekey_order(mesh_name, armature_name=None):
    armature = bpy.data.objects.get(armature_name) if armature_name else get_armature()
    if not armature:
        return

    sys_props = armature.bl_system_properties_get()
    if not sys_props:
        return

    if 'CUSTOM' not in sys_props:
        return

    custom_data = sys_props.get('CUSTOM', {})

    if not isinstance(custom_data, dict):
        return

    shape_key_order = custom_data.get('shape_key_order', [])

    if not shape_key_order:
        custom_data['shape_key_order'] = []
        if sys_props:
            sys_props['CUSTOM'] = custom_data
    elif isinstance(shape_key_order, str):
        shape_key_order_temp = shape_key_order.split(',,,')
        custom_data['shape_key_order'] = shape_key_order_temp
        if sys_props:
            sys_props['CUSTOM'] = custom_data

    if custom_data.get('shape_key_order'):
        sort_shape_keys(mesh_name, custom_data['shape_key_order'])


def update_shapekey_orders():
    for armature in get_armature_objects():
        shape_key_order_translated = []

        custom_data = armature.get('CUSTOM')
        if not custom_data:
            continue
        order = custom_data.get('shape_key_order')
        if not order:
            continue

        if type(order) is str:
            shape_key_order_temp = order.split(',,,')
            order = []
            for shape_name in shape_key_order_temp:
                order.append(shape_name)

        for shape_name in order:
            shape_key_order_translated.append(Translate.translate(shape_name, add_space=True, translating_shapes=True)[0])

        custom_data['shape_key_order'] = shape_key_order_translated
        armature['CUSTOM'] = custom_data


def sort_shape_keys(mesh_name, shape_key_order=None):
    mesh = get_objects().get(mesh_name)
    if not mesh or not has_shapekeys(mesh):
        return
    set_active(mesh)

    shape_key_order = shape_key_order or []

    order = [
        'Basis',
        'vrc.blink_left',
        'vrc.blink_right',
        'vrc.lowerlid_left',
        'vrc.lowerlid_right',
        'vrc.v_aa',
        'vrc.v_ch',
        'vrc.v_dd',
        'vrc.v_e',
        'vrc.v_ff',
        'vrc.v_ih',
        'vrc.v_kk',
        'vrc.v_nn',
        'vrc.v_oh',
        'vrc.v_ou',
        'vrc.v_pp',
        'vrc.v_rr',
        'vrc.v_sil',
        'vrc.v_ss',
        'vrc.v_th',
        'Basis Original'
    ]

    for shape in shape_key_order:
        if shape not in order:
            order.append(shape)

    key_blocks = mesh.data.shape_keys.key_blocks
    wanted = [name for name in order if name in key_blocks and key_blocks.find(name) > 0]
    if not wanted:
        mesh.active_shape_key_index = 0
        return

    wm = bpy.context.window_manager
    wm.progress_begin(0, len(wanted))

    for step, name in enumerate(reversed(wanted), start=1):
        mesh.active_shape_key_index = key_blocks.find(name)
        bpy.ops.object.shape_key_move(type='TOP')
        wm.progress_update(step)

    mesh.active_shape_key_index = 0

    wm.progress_end()


def delete_hierarchy(parent):
    unselect_all()
    to_delete = []

    def get_child_names(obj):
        for child in obj.children:
            to_delete.append(child)
            if child.children:
                get_child_names(child)

    get_child_names(parent)
    to_delete.append(parent)

    objs = bpy.data.objects
    for obj in to_delete:
        objs.remove(objs[obj.name], do_unlink=True)


def delete(obj):
    if obj.parent:
        for child in obj.children:
            child.parent = obj.parent

    objs = bpy.data.objects
    objs.remove(objs[obj.name], do_unlink=True)


def delete_bone_constraints(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature

    armature = get_armature(armature_name=armature_name)
    switch('POSE')

    for bone in armature.pose.bones:
        for constraint in list(bone.constraints):
            bone.constraints.remove(constraint)

    switch('EDIT')


def delete_zero_weight(armature_name=None, ignore=''):
    if not armature_name:
        armature_name = bpy.context.scene.armature

    armature = get_armature(armature_name=armature_name)
    switch('EDIT')

    bone_names_to_work_on = {bone.name for bone in armature.data.edit_bones}

    bone_name_to_edit_bone = {}
    for edit_bone in armature.data.edit_bones:
        bone_name_to_edit_bone[edit_bone.name] = edit_bone

    vertex_group_names_used = set()
    vertex_group_name_to_objects_having_same_named_vertex_group = {}
    for objects in get_meshes_objects(armature_name=armature_name):
        vertex_group_id_to_vertex_group_name = {}
        for vertex_group in objects.vertex_groups:
            vertex_group_id_to_vertex_group_name[vertex_group.index] = vertex_group.name
            if vertex_group.name not in vertex_group_name_to_objects_having_same_named_vertex_group:
                vertex_group_name_to_objects_having_same_named_vertex_group[vertex_group.name] = set()
            vertex_group_name_to_objects_having_same_named_vertex_group[vertex_group.name].add(objects)
        for vertex in objects.data.vertices:
            for group in vertex.groups:
                if group.weight > 0:
                    vertex_group_names_used.add(vertex_group_id_to_vertex_group_name.get(group.group))

    not_used_bone_names = bone_names_to_work_on - vertex_group_names_used

    count = 0
    keep_twists = bpy.context.scene.delete_zero_weight_keep_twists
    keep_empty_parents = bpy.context.scene.delete_zero_weight_keep_empty_parents
    skip_hidden_bones = bpy.context.scene.delete_zero_weight_skip_hidden_bones

    for bone_name in not_used_bone_names:
        bone = bone_name_to_edit_bone[bone_name]

        if skip_hidden_bones and bone.hide:
            continue

        if keep_twists and ("_twist" in bone_name.lower() or "Twist" in bone_name):
            continue

        if keep_empty_parents:
            found_non_empty_child = False
            if bone:
                for child in bone.children_recursive:
                    if child.name in vertex_group_names_used:
                        found_non_empty_child = True
                        break
            if found_non_empty_child:
                continue

        if not bpy.context.scene.keep_end_bones or not is_end_bone(bone_name, armature_name):
            if bone_name not in Bones.dont_delete_these_bones and 'Root_' not in bone_name and bone_name != ignore:
                armature.data.edit_bones.remove(bone)
                count += 1
                if bone_name in vertex_group_name_to_objects_having_same_named_vertex_group:
                    for objects in vertex_group_name_to_objects_having_same_named_vertex_group[bone_name]:
                        vertex_group = objects.vertex_groups.get(bone_name)
                        if vertex_group is not None:
                            objects.vertex_groups.remove(vertex_group)

    return count


def remove_unused_objects():
    default_scene_objects = []

    for obj in get_objects():
        if obj.type in {'CAMERA', 'LAMP', 'LIGHT', 'MESH'} and is_default_object(obj):
            default_scene_objects.append(obj)

    if len(default_scene_objects) == 3:
        for obj in default_scene_objects:
            delete_hierarchy(obj)

def is_default_object(obj):
    return bool((obj.type == 'CAMERA' and obj.data.name == 'Camera') or (obj.type == 'LAMP' and obj.data.name == 'Lamp') or (obj.type == 'LIGHT' and obj.data.name == 'Light') or (obj.type == 'MESH' and obj.data.name == 'Cube'))


def is_end_bone(name, armature_name):
    armature = get_armature(armature_name=armature_name)
    end_bone = armature.data.edit_bones.get(name)
    return bool(end_bone and end_bone.parent and len(end_bone.parent.children) == 1)


def correct_bone_positions(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
    armature = get_armature(armature_name=armature_name)

    upper_chest = armature.data.edit_bones.get('Upper Chest')
    chest = armature.data.edit_bones.get('Chest')
    neck = armature.data.edit_bones.get('Neck')
    head = armature.data.edit_bones.get('Head')
    if chest and neck:
        if upper_chest and bpy.context.scene.keep_upper_chest:
            chest.tail = upper_chest.head
            upper_chest.tail = neck.head
        else:
            chest.tail = neck.head
    if neck and head:
        neck.tail = head.head

    if 'Left shoulder' in armature.data.edit_bones:
        if 'Left arm' in armature.data.edit_bones:
            if 'Left elbow' in armature.data.edit_bones:
                if 'Left wrist' in armature.data.edit_bones:
                    shoulder = armature.data.edit_bones.get('Left shoulder')
                    arm = armature.data.edit_bones.get('Left arm')
                    elbow = armature.data.edit_bones.get('Left elbow')
                    wrist = armature.data.edit_bones.get('Left wrist')
                    shoulder.tail = arm.head
                    arm.tail = elbow.head
                    elbow.tail = wrist.head

    if 'Right shoulder' in armature.data.edit_bones:
        if 'Right arm' in armature.data.edit_bones:
            if 'Right elbow' in armature.data.edit_bones:
                if 'Right wrist' in armature.data.edit_bones:
                    shoulder = armature.data.edit_bones.get('Right shoulder')
                    arm = armature.data.edit_bones.get('Right arm')
                    elbow = armature.data.edit_bones.get('Right elbow')
                    wrist = armature.data.edit_bones.get('Right wrist')
                    shoulder.tail = arm.head
                    arm.tail = elbow.head
                    elbow.tail = wrist.head

    if 'Left leg' in armature.data.edit_bones:
        if 'Left knee' in armature.data.edit_bones:
            if 'Left ankle' in armature.data.edit_bones:
                leg = armature.data.edit_bones.get('Left leg')
                knee = armature.data.edit_bones.get('Left knee')
                ankle = armature.data.edit_bones.get('Left ankle')

                if 'Left leg 2' in armature.data.edit_bones:
                    leg = armature.data.edit_bones.get('Left leg 2')

                leg.tail = knee.head
                knee.tail = ankle.head

    if 'Right leg' in armature.data.edit_bones:
        if 'Right knee' in armature.data.edit_bones:
            if 'Right ankle' in armature.data.edit_bones:
                leg = armature.data.edit_bones.get('Right leg')
                knee = armature.data.edit_bones.get('Right knee')
                ankle = armature.data.edit_bones.get('Right ankle')

                if 'Right leg 2' in armature.data.edit_bones:
                    leg = armature.data.edit_bones.get('Right leg 2')

                leg.tail = knee.head
                knee.tail = ankle.head


dpi_scale = 3
error = []
override = False


def show_error(scale, error_list, override_header=False):
    global override, dpi_scale, error
    override = override_header
    dpi_scale = scale

    if type(error_list) is str:
        error_list = error_list.split('\n')

    error = error_list

    header = t('ShowError.label')
    if override:
        header = error_list[0]

    ShowError.bl_label = header
    try:
        bpy.utils.register_class(ShowError)
    except ValueError:
        bpy.utils.unregister_class(ShowError)
        bpy.utils.register_class(ShowError)

    bpy.ops.cats_common.show_error('INVOKE_DEFAULT')

    print()
    print('Report: Error')
    for line in error:
        print('    ' + line)


@register_wrap
class ShowError(bpy.types.Operator):
    bl_idname = 'cats_common.show_error'
    bl_label = t('ShowError.label')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * dpi_scale))

    def draw(self, context):
        if not error or len(error) == 0:
            return

        if override and len(error) == 1:
            return

        layout = self.layout
        col = layout.column(align=True)

        first_line = False
        for i, line in enumerate(error):
            if i == 0 and override:
                continue
            if line == '':
                col.separator()
            else:
                row = col.row(align=True)
                row.scale_y = 0.85
                if not first_line:
                    row.label(text=line, icon='ERROR')
                    first_line = True
                else:
                    row.label(text=line, icon_value=Iconloader.preview_collections["custom_icons"]["empty"].icon_id)


def _get_shape_key_co(shape_key: ShapeKey) -> np.ndarray:
    co = np.empty(len(shape_key.data) * 3, dtype=np.float32)
    shape_key.data.foreach_get('co', co)
    return co


def remove_doubles(mesh_obj: Object, threshold: float, save_shapes: bool = True) -> int:
    if not isinstance(mesh_obj, Object):
        raise TypeError("mesh_obj must be an instance of Object")

    mesh = mesh_obj.data

    if not has_shapekeys(mesh_obj) or len(mesh.shape_keys.key_blocks) == 1:
        return 0

    pre_polygons = len(mesh.polygons)
    vertex_selection = None

    if save_shapes:
        vertex_selection = np.full(len(mesh.vertices), True, dtype=bool)
        cached_co_getter = lru_cache(maxsize=None)(_get_shape_key_co)
        for kb in mesh.shape_keys.key_blocks[1:]:
            relative_key = kb.relative_key
            if relative_key is None or kb == relative_key:
                continue
            same = cached_co_getter(kb) == cached_co_getter(relative_key)
            vertex_not_moved_by_shape_key = np.all(same.reshape(-1, 3), axis=1)
            vertex_selection &= vertex_not_moved_by_shape_key
        del cached_co_getter

        if not vertex_selection.any():
            return 0

        if vertex_selection.all():
            save_shapes = False

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        verts = [v for i, v in enumerate(bm.verts) if vertex_selection[i]] if save_shapes else bm.verts

        bmesh.ops.remove_doubles(bm, verts=verts, dist=threshold)
        bm.to_mesh(mesh)
    finally:
        bm.free()

    mesh.update()

    return pre_polygons - len(mesh.polygons)


def get_tricount(obj):
    bmesh_mesh = bmesh.new()
    bmesh_mesh.from_mesh(obj.data)

    bmesh.ops.triangulate(bmesh_mesh, faces=bmesh_mesh.faces[:])
    return len(bmesh_mesh.faces)


def sort_material_slots(mesh):
    """Put the material slots in a stable, name-sorted order.

    After a join the slot order follows the view layer, and Blender's FBX importer
    does not produce a stable object order, so joining the same model twice gives a
    different slot order each time. That order is visible downstream, most obviously
    when the model is taken into Unity. Face material indices are remapped so the
    result looks identical.
    """
    materials = [slot.material for slot in mesh.material_slots]
    if len(materials) < 2:
        return

    order = sorted(range(len(materials)),
                   key=lambda i: (materials[i] is None, materials[i].name if materials[i] else ''))
    if order == list(range(len(materials))):
        return

    remap = np.empty(len(order), dtype=np.int32)
    for new_index, old_index in enumerate(order):
        remap[old_index] = new_index

    polygons = mesh.data.polygons
    indices = np.empty(len(polygons), dtype=np.int32)
    polygons.foreach_get('material_index', indices)
    polygons.foreach_set('material_index', remap[indices])

    for new_index, old_index in enumerate(order):
        mesh.material_slots[new_index].material = materials[old_index]


def clean_material_names(mesh):
    for j, mat in enumerate(mesh.material_slots):
        if mat.name.endswith(('.0+', ' 0+')):
            mesh.active_material_index = j
            mesh.active_material.name = mat.name[:-len(mat.name.rstrip('0')) - 1]


def mix_weights(mesh, vg_from, vg_to, mix_strength=1.0, mix_mode='ADD', mix_set='ALL', delete_old_vg=True):
    """Mix the weights of two vertex groups on the mesh, optionally removing the vertex group named vg_from.
    This function uses the Vertex Weight Mix modifier to efficiently mix vertex group weights.
    """
    mesh.active_shape_key_index = 0
    mod = mesh.modifiers.new(name="VertexWeightMix_" + vg_from + "_into_" + vg_to, type='VERTEX_WEIGHT_MIX')
    mod.vertex_group_a = vg_to
    mod.vertex_group_b = vg_from
    mod.mix_mode = mix_mode
    mod.mix_set = mix_set
    mod.mask_constant = mix_strength
    if bpy.ops.object.modifier_apply.poll():
        mesh.modifiers.active = mod
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if delete_old_vg:
        vg_from_group = mesh.vertex_groups.get(vg_from)
        if vg_from_group:
            mesh.vertex_groups.remove(vg_from_group)

    mesh.active_shape_key_index = 0


def get_user_preferences():
    return bpy.context.user_preferences if hasattr(bpy.context, 'user_preferences') else bpy.context.preferences


def has_shapekeys(mesh):
    if not hasattr(mesh.data, 'shape_keys'):
        return False
    return hasattr(mesh.data.shape_keys, 'key_blocks')


def ui_refresh():
    refreshed = False
    while not refreshed:
        if hasattr(bpy.data, 'window_managers'):
            for windowManager in bpy.data.window_managers:
                for window in windowManager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()
            refreshed = True
        else:
            time.sleep(0.5)


def fix_zero_length_bones(armature: bpy.types.Object):
    if armature.mode != 'EDIT':
        return

    edit_bones = armature.data.edit_bones[:]

    for bone in edit_bones:
        length = (bone.head - bone.tail).length
        if length > 0.0001:
            continue

        head_rounded = [round(x, 4) for x in bone.head]
        tail_rounded = [round(x, 4) for x in bone.tail]

        if head_rounded == tail_rounded:
            bone.tail += Vector((0, 0, 0.1))

def fix_bone_orientations(armature):
    for bone in armature.data.edit_bones:
        if len(bone.children) == 1 and bone.name not in ['LeftEye', 'RightEye', 'Head', 'Hips']:
            p1 = bone.head
            p2 = bone.children[0].head
            dist = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2) ** (1/2)

            if dist > 0.005:
                bone.tail = bone.children[0].head
                if bone.parent and len(bone.parent.children) == 1:
                    bone.use_connect = True


def update_material_list(self=None, context=None):
    try:
        if hasattr(bpy.context.scene, 'smc_ob_data') and bpy.context.scene.smc_ob_data:
            bpy.ops.smc.refresh_ob_data()
    except AttributeError:
        print('Material Combiner not found')


def fix_twist_bones(mesh, bones_to_delete):

    for bone_type in ['Hand', 'Arm']:
        for suffix in ['L', 'R']:
            prefix = 'Left' if suffix == 'L' else 'Right'
            bone_parent_name = prefix + ' ' + ('elbow' if bone_type == 'Hand' else 'arm')

            vg_twist = mesh.vertex_groups.get(bone_type + 'Twist_' + suffix)
            vg_parent = mesh.vertex_groups.get(bone_parent_name)

            if not vg_twist:
                print('1. no ' + bone_type + 'Twist_' + suffix)
                continue
            if not vg_parent:
                print('2. no ' + bone_parent_name)
                vg_parent = mesh.vertex_groups.new(name=bone_parent_name)

            vg_twist1_name = bone_type + 'Twist1_' + suffix
            vg_twist2_name = bone_type + 'Twist2_' + suffix
            vg_twist3_name = bone_type + 'Twist3_' + suffix
            vg_twist1 = bool(mesh.vertex_groups.get(vg_twist1_name))
            vg_twist2 = bool(mesh.vertex_groups.get(vg_twist2_name))
            vg_twist3 = bool(mesh.vertex_groups.get(vg_twist3_name))

            vg_twist_name = vg_twist.name
            vg_parent_name = vg_parent.name

            mix_weights(mesh, vg_twist_name, vg_parent_name, mix_strength=0.2, delete_old_vg=False)
            mix_weights(mesh, vg_twist_name, vg_twist_name, mix_strength=0.2, mix_mode='SUB', delete_old_vg=False)

            if vg_twist1:
                bones_to_delete.append(vg_twist1_name)
                mix_weights(mesh, vg_twist1_name, vg_twist_name, mix_strength=0.25, delete_old_vg=False)
                mix_weights(mesh, vg_twist1_name, vg_parent_name, mix_strength=0.75)

            if vg_twist2:
                bones_to_delete.append(vg_twist2_name)
                mix_weights(mesh, vg_twist2_name, vg_twist_name, mix_strength=0.5, delete_old_vg=False)
                mix_weights(mesh, vg_twist2_name, vg_parent_name, mix_strength=0.5)

            if vg_twist3:
                bones_to_delete.append(vg_twist3_name)
                mix_weights(mesh, vg_twist3_name, vg_twist_name, mix_strength=0.75, delete_old_vg=False)
                mix_weights(mesh, vg_twist3_name, vg_parent_name, mix_strength=0.25)


def fix_twist_bone_names(armature):
    for bone_type in ['Hand', 'Arm']:
        for suffix in ['L', 'R']:
            bone_twist = armature.data.edit_bones.get(bone_type + 'Twist_' + suffix)
            if bone_twist:
                bone_twist.name = 'z' + bone_twist.name


"""
HTML <-> text conversions.
http://stackoverflow.com/questions/328356/extracting-text-from-html-file-using-python
"""


class _HTMLToText(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._buf = []
        self.hide_output = False

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'br') and not self.hide_output:
            self._buf.append('\n')
        elif tag in ('script', 'style'):
            self.hide_output = True

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self._buf.append('\n')

    def handle_endtag(self, tag):
        if tag == 'p':
            self._buf.append('\n')
        elif tag in ('script', 'style'):
            self.hide_output = False

    def handle_data(self, text):
        if text and not self.hide_output:
            self._buf.append(re.sub(r'\s+', ' ', text))

    def handle_entityref(self, name):
        if name in name2codepoint and not self.hide_output:
            c = chr(name2codepoint[name])
            self._buf.append(c)

    def handle_charref(self, name):
        if not self.hide_output:
            n = int(name[1:], 16) if name.startswith('x') else int(name)
            self._buf.append(chr(n))

    def get_text(self):
        return re.sub(r' +', ' ', ''.join(self._buf))


def html_to_text(html):
    """
    Given a piece of HTML, return the plain text it contains.
    This handles entities and char refs, but not javascript and stylesheets.
    """
    parser = _HTMLToText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    return parser.get_text()


def _sort_enum_choices_by_identifier_lower(choices, in_place=True):
    """Sort a list of enum choices (items) by the lowercase of their identifier.

    Sorting is performed in-place by default, but can be changed by setting in_place=False.

    Returns the sorted list of enum choices."""

    def identifier_lower(choice):
        return choice[0].lower()

    if in_place:
        choices.sort(key=identifier_lower)
    else:
        choices = sorted(choices, key=identifier_lower)
    return choices


_empty_enum_identifier = 'Cats_empty_enum_identifier'


def _ensure_enum_choices_not_empty(choices, in_place=True):
    if not in_place:
        choices = choices.copy()

    num_choices = len(choices)
    if num_choices == 0:
        choices.append((_empty_enum_identifier, 'None', '(auto-generated)'))

    return choices


_enum_string_cache = {}


def _ensure_python_references(choices, property_path, in_place=True):
    new_cache = set()

    def keep_string_reference(element):
        if isinstance(element, str):
            element = intern(element)
            new_cache.add(element)
        return element

    if in_place:
        for i, choice in enumerate(choices):
            choices[i] = tuple(map(keep_string_reference, choice))
    else:
        choices = [tuple(map(keep_string_reference, choice)) for choice in choices]

    object_name_cache = _enum_string_cache.setdefault(property_path, set())
    object_name_cache.update(new_cache)
    object_name_cache.intersection_update(new_cache)
    return choices


_enum_choice_fix_scheduled = {}


_max_enum_padding = 256


def _pad_enum_choices(choices, target_index):
    """Append placeholder choices until target_index is in range, up to the cap."""
    num_choices = len(choices)
    for i in range(min(target_index - num_choices + 1, _max_enum_padding)):
        temp_identifier = f"__temp_choice_{num_choices + i}__"
        choices.append((temp_identifier, choices[0][1], choices[0][2]))
    return choices


def _fix_out_of_bounds_enum_choices(property_holder, scene, choices, property_name, property_path, in_place=True):
    """Check for and fix an EnumProperty if its index is out of bounds.

    If it isn't possible to change the index immediately, because this is being called as part of a UI drawing method,
    a task to change the active choice will be scheduled to run as soon as possible.

    Adds duplicates of the last choice to 'choices' to prevent warnings until the invalid choices are fixed.

    property_holder is the holder of the property, in an EnumProperty's items function, this is the 'self' argument

    scene is the scene that owns the property, either directly or held in a PropertyGroup or PropertyCollection. It must
    be the .id_data of the property.

    choices is the list of choices returned by the EnumProperty's items function.

    property_name is the name of the EnumProperty on the property_holder to be checked against whether the choices are
    valid.

    property_path is the full path from the owner of the EnumProperty (scene) to the EnumProperty itself. This can be
    retrieved with property_holder.path_from_id(property_name).

    By default, the passed in 'choices' argument is modified, this can be disabled by setting in_place=False.

    Returns 'choices' with enough extra elements to avoid warnings of the property's index being out of bounds."""

    if not in_place:
        choices = choices.copy()

    num_choices = len(choices)
    if num_choices == 0:
        return choices

    current_choice_value = property_holder.get(property_name)
    is_initialised = current_choice_value is not None

    if not is_initialised:
        return choices

    valid_identifiers = {choice[0] for choice in choices}

    if isinstance(current_choice_value, str):
        if current_choice_value in valid_identifiers:
            return choices
        try:
            numeric_value = int(current_choice_value)
            if numeric_value >= num_choices:
                _pad_enum_choices(choices, numeric_value)
        except (ValueError, TypeError):
            pass
        replacement_identifier = choices[0][0]
        _schedule_enum_fix(property_holder, scene, property_name, property_path, replacement_identifier)
        return choices

    if isinstance(current_choice_value, int):
        if 0 <= current_choice_value < num_choices:
            return choices
        _pad_enum_choices(choices, current_choice_value)

        replacement_identifier = choices[0][0]
        _schedule_enum_fix(property_holder, scene, property_name, property_path, replacement_identifier)

    return choices


def _schedule_enum_fix(property_holder, scene, property_name, property_path, new_value):
    """Schedule a fix for an enum property to be applied outside of the UI draw context.

    IMPORTANT: This function must NEVER attempt to set the property directly via setattr(),
    as doing so will cause Blender to re-validate the enum value by calling the items callback,
    which leads to infinite recursion when called during object deletion or other state changes.
    All fixes must be scheduled via timer to run outside the callback context.
    """

    scene_name = scene.name
    scheduled_property_set = _enum_choice_fix_scheduled.setdefault(scene_name, set())

    if property_path in scheduled_property_set:
        return

    scheduled_property_set.add(property_path)

    def fix_enum_task():
        scene_by_name = bpy.data.scenes.get(scene_name)
        if scene_by_name:
            try:
                prop = scene_by_name.path_resolve(property_path, False)
                setattr(prop.data, property_name, new_value)
            except Exception:
                with contextlib.suppress(Exception):
                    setattr(scene_by_name, property_name, new_value)
        scheduled_property_set.discard(property_path)
        return

    bpy.app.timers.register(fix_enum_task, first_interval=0.0)


def is_enum_empty(string):
    """Returns True only if the tested string is the string that signifies that an EnumProperty is empty.

    Returns False in all other cases."""
    return _empty_enum_identifier == string

def is_enum_non_empty(string):
    """Returns False only if the tested string is not the string that signifies that an EnumProperty is empty.

    Returns True in all other cases."""
    return _empty_enum_identifier != string


_enum_items_being_processed = {}


def wrap_dynamic_enum_items(items_func, property_name, sort=True, in_place=True, is_holder=True):
    """Wrap an EnumProperty items function to automatically fix the property when it goes out of bounds of the items list.
    Automatically adds at least one choice if the items function returns an empty list.
    By default, sorts the items by the lowercase of the identifiers, this can be disabled by setting sort=False.
    Interns and caches all strings in the items to avoid a known Blender UI bug.
    Only works for properties whose owner is a scene.
    By setting is_holder=false, the fix for out of bounds values will be disabled."""
    def wrapped_items_func(self, context):
        holder_id = self.as_pointer()
        property_set = _enum_items_being_processed.setdefault(holder_id, set())

        if property_name in property_set:
            return [(_empty_enum_identifier, "Loading...", "")]

        try:
            property_set.add(property_name)

            do_in_place = in_place
            items = items_func(self, context)
            if sort:
                items = _sort_enum_choices_by_identifier_lower(items, in_place=do_in_place)
                if not do_in_place:
                    do_in_place = True
            items = _ensure_enum_choices_not_empty(items, in_place=do_in_place)
            property_path = self.path_from_id(property_name) if is_holder else property_name
            items = _ensure_python_references(items, property_path)
            if is_holder:
                return _fix_out_of_bounds_enum_choices(self, context.scene, items, property_name, property_path)
            return items
        finally:
            property_set.discard(property_name)
            if not property_set:
                _enum_items_being_processed.pop(holder_id, None)

    return wrapped_items_func

def op_override(operator, context_override: dict[str, Any], context: bpy.types.Context | None = None,
                execution_context: str | None = None,
                undo: bool | None = None, **operator_args) -> set[str]:
    """Call an operator with a context override"""
    args = []
    if execution_context is not None:
        args.append(execution_context)
    if undo is not None:
        args.append(undo)

    if context is None:
        context = bpy.context
    with context.temp_override(**context_override):
        return operator(*args, **operator_args)


def set_material_shading():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'
                    space.shading.studio_light = 'forest.exr'
                    space.shading.studiolight_rotate_z = 0.0
                    space.shading.studiolight_background_alpha = 0.0
                    space.shading.render_pass = 'COMBINED'

def clear_unused_data():
    """
    Clear unused data blocks to improve memory usage.
    """
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
