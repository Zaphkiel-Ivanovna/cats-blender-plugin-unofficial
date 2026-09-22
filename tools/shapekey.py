# GPL License

import bpy
import numpy as np
from .register import register_wrap
from .translations import t


@register_wrap
class ShapeKeyApplier(bpy.types.Operator):
    bl_idname = "cats_shapekey.shape_key_to_basis"
    bl_label = t('ShapeKeyApplier.label')
    bl_description = t('ShapeKeyApplier.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and
                context.object and
                context.object.type == 'MESH' and
                context.object.active_shape_key_index > 0 and
                context.object.data.shape_keys.use_relative and
                context.object.active_shape_key.relative_key != context.object.active_shape_key)

    def execute(self, context):
        mesh = context.object

        new_basis_shapekey = mesh.active_shape_key

        reverse_relative_map = ShapeKeyApplier.ReverseRelativeMap(mesh)

        keys_relative_recursive_to_new_basis = reverse_relative_map.get_relative_recursive_keys(new_basis_shapekey)

        if new_basis_shapekey in keys_relative_recursive_to_new_basis:
            self.report({'ERROR_INVALID_INPUT'}, t('ShapeKeyApplier.error.recursiveRelativeToLoop', name=new_basis_shapekey.name))
            return {'CANCELLED'}

        old_basis_shapekey = mesh.data.shape_keys.key_blocks[0]

        keys_relative_recursive_to_old_basis = reverse_relative_map.get_relative_recursive_keys(old_basis_shapekey)

        if new_basis_shapekey.value == 0.0:
            new_basis_shapekey.value = 1.0

        ShapeKeyApplier.apply_key_to_basis(mesh=mesh,
                                           new_basis_shapekey=new_basis_shapekey,
                                           keys_relative_recursive_to_new_basis=keys_relative_recursive_to_new_basis,
                                           keys_relative_recursive_to_basis=keys_relative_recursive_to_old_basis)

        reverted_string = ' - Reverted'
        reverted_string_len = len(reverted_string)
        old_name = new_basis_shapekey.name

        if new_basis_shapekey.name[-reverted_string_len:] == reverted_string:
            new_basis_shapekey.name = new_basis_shapekey.name[:-reverted_string_len]
            reverted = True
        else:
            new_basis_shapekey.name = new_basis_shapekey.name + reverted_string
            reverted = False

        new_basis_shapekey.value = 0.0
        new_basis_shapekey.slider_min = 0.0
        new_basis_shapekey.slider_max = 1.0

        response_message = 'ShapeKeyApplier.successRemoved' if reverted else 'ShapeKeyApplier.successSet'
        self.report({'INFO'}, t(response_message, name=old_name))
        return {'FINISHED'}

    class ReverseRelativeMap:
        def __init__(self, obj):
            reverse_relative_map = {}

            basis_key = obj.data.shape_keys.key_blocks[0]
            for key in obj.data.shape_keys.key_blocks:
                relative_key = basis_key if key == basis_key else key.relative_key
                keys_relative_to_relative_key = reverse_relative_map.get(relative_key)
                if keys_relative_to_relative_key is None:
                    keys_relative_to_relative_key = {key}
                    reverse_relative_map[relative_key] = keys_relative_to_relative_key
                else:
                    keys_relative_to_relative_key.add(key)
            self.reverse_relative_map = reverse_relative_map

        def get_relative_recursive_keys(self, shape_key):
            shape_set = set()

            def inner_recursive_loop(key, checked_set):
                if key not in checked_set:
                    checked_set.add(key)
                    keys_relative_to_shape_key_inner = self.reverse_relative_map.get(key)
                    if keys_relative_to_shape_key_inner:
                        for relative_to_inner in keys_relative_to_shape_key_inner:
                            shape_set.add(relative_to_inner)
                            inner_recursive_loop(relative_to_inner, checked_set)

            inner_recursive_loop(shape_key, set())
            return shape_set

    @staticmethod
    def isolate_active_shape(obj_with_shapes):
        active_shape = obj_with_shapes.active_shape_key
        restore_data = {}

        if active_shape.value == 1.0:
            if obj_with_shapes.show_only_shape_key:
                pass
            else:
                restore_data['show_only_shape_key'] = False
                obj_with_shapes.show_only_shape_key = True
        else:
            shapekey_mutes = []
            for key_block in obj_with_shapes.data.shape_keys.key_blocks:
                shapekey_mutes.append(key_block.mute)
                key_block.mute = True
            active_shape.mute = False

            restore_data['mutes'] = shapekey_mutes

            if obj_with_shapes.show_only_shape_key:
                restore_data['show_only_shape_key'] = True
                obj_with_shapes.show_only_shape_key = False

        def restore_function():
            if restore_data:
                mutes = restore_data.get('mutes')
                if mutes:
                    for mute, shape in zip(mutes, obj_with_shapes.data.shape_keys.key_blocks, strict=False):
                        shape.mute = mute
                show_only_shape_key = restore_data.get('show_only_shape_key')
                if show_only_shape_key is not None:
                    obj_with_shapes.show_only_shape_key = show_only_shape_key

        return restore_function

    @staticmethod
    def apply_key_to_basis(*, mesh, new_basis_shapekey, keys_relative_recursive_to_new_basis, keys_relative_recursive_to_basis):
        data = mesh.data
        num_verts = len(data.vertices)

        new_basis_shapekey_vertex_group_name = new_basis_shapekey.vertex_group
        if new_basis_shapekey_vertex_group_name:
            new_basis_shapekey_vertex_group = mesh.vertex_groups.get(new_basis_shapekey_vertex_group_name)
        else:
            new_basis_shapekey_vertex_group = None

        new_basis_affected_by_own_application = new_basis_shapekey in keys_relative_recursive_to_basis

        flattened_co_length = num_verts * 3

        new_basis_co_flat = np.empty(flattened_co_length, dtype=np.single)
        new_basis_relative_co_flat = np.empty(flattened_co_length, dtype=np.single)

        new_basis_shapekey.data.foreach_get('co', new_basis_co_flat)
        new_basis_shapekey.relative_key.data.foreach_get('co', new_basis_relative_co_flat)

        difference_co_flat = np.subtract(new_basis_co_flat, new_basis_relative_co_flat)

        difference_co_flat_value_scaled = np.multiply(difference_co_flat, new_basis_shapekey.value)

        temp_co_array = np.empty(flattened_co_length, dtype=np.single)
        temp_co_array2 = np.empty(flattened_co_length, dtype=np.single)

        if new_basis_shapekey_vertex_group:
            restore_function = ShapeKeyApplier.isolate_active_shape(mesh)
            new_basis_mixed = mesh.shape_key_add(name="temp shape (you shouldn't see this)", from_mix=True)
            restore_function()

            temp_shape_co_flat = temp_co_array

            new_basis_mixed.data.foreach_get('co', temp_shape_co_flat)

            if new_basis_mixed.relative_key == new_basis_shapekey.relative_key:
                temp_shape_relative_co_flat = new_basis_relative_co_flat
            else:
                new_basis_mixed.relative_key.data.foreach_get('co', temp_co_array2)
                temp_shape_relative_co_flat = temp_co_array2

            difference_co_flat_scaled = np.subtract(temp_shape_co_flat, temp_shape_relative_co_flat)

            active_index = mesh.active_shape_key_index
            mesh.shape_key_remove(new_basis_mixed)
            mesh.active_shape_key_index = active_index
        else:
            difference_co_flat_scaled = difference_co_flat_value_scaled

        if new_basis_affected_by_own_application:
            keys_not_relative_recursive_to_new_basis_and_not_new_basis = (keys_relative_recursive_to_basis - keys_relative_recursive_to_new_basis) - {new_basis_shapekey}

            new_basis_shapekey.relative_key.data.foreach_set('co', np.add(new_basis_relative_co_flat, difference_co_flat_scaled, out=temp_co_array))
            for key_block in keys_not_relative_recursive_to_new_basis_and_not_new_basis - {new_basis_shapekey.relative_key}:
                key_block.data.foreach_get('co', temp_co_array)
                key_block.data.foreach_set('co', np.add(temp_co_array, difference_co_flat_scaled, out=temp_co_array))

            if new_basis_shapekey_vertex_group:
                np.multiply(difference_co_flat, -1 - new_basis_shapekey.value, out=temp_co_array2)
                np.add(temp_co_array2, difference_co_flat_scaled, out=temp_co_array2)

                new_basis_shapekey.data.foreach_set('co', np.add(new_basis_co_flat, temp_co_array2, out=temp_co_array))

                for key_block in keys_relative_recursive_to_new_basis:
                    key_block.data.foreach_get('co', temp_co_array)
                    key_block.data.foreach_set('co', np.add(temp_co_array, temp_co_array2, out=temp_co_array))
            else:
                new_basis_shapekey.data.foreach_set('co', new_basis_relative_co_flat)
                for key_block in keys_relative_recursive_to_new_basis:
                    key_block.data.foreach_get('co', temp_co_array)
                    key_block.data.foreach_set('co', np.subtract(temp_co_array, difference_co_flat, out=temp_co_array))
        else:

            for key_block in keys_relative_recursive_to_basis:
                key_block.data.foreach_get('co', temp_co_array)
                key_block.data.foreach_set('co', np.add(temp_co_array, difference_co_flat_scaled, out=temp_co_array))

            np.multiply(difference_co_flat, -1 - new_basis_shapekey.value, out=temp_co_array2)

            new_basis_shapekey.data.foreach_set('co', np.add(new_basis_co_flat, temp_co_array2, out=temp_co_array))
            for key_block in keys_relative_recursive_to_new_basis:
                key_block.data.foreach_get('co', temp_co_array)
                key_block.data.foreach_set('co', np.add(temp_co_array, temp_co_array2, out=temp_co_array))

        data.shape_keys.reference_key.data.foreach_get('co', temp_co_array)
        data.vertices.foreach_set('co', temp_co_array)

@register_wrap
class ShapeKeyPruner(bpy.types.Operator):

    bl_idname = "cats_shapekey.shape_key_prune"
    bl_label = t('ShapeKeyPruner.label')
    bl_description = t('ShapeKeyPruner.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    TOLERANCE = 0.001

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and
                context.object and
                context.object.type == 'MESH' and
                context.object.data.shape_keys and
                context.object.data.shape_keys.use_relative)

    def execute(self, context):

        mesh = context.object

        report_messages = []

        shape_keys = mesh.data.shape_keys.key_blocks
        num_vertices = len(mesh.data.vertices)
        shape_keys_to_delete = []

        relative_key_cache = {}

        vertex_locations = np.empty(3 * num_vertices, dtype=np.float32)

        for shape_key in shape_keys:
            if shape_key == shape_key.relative_key:
                continue

            shape_key.data.foreach_get("co", vertex_locations)

            if shape_key.relative_key.name not in relative_key_cache:
                relative_locations = np.empty(3 * num_vertices, dtype=np.float32)
                shape_key.relative_key.data.foreach_get("co", relative_locations)
                relative_key_cache[shape_key.relative_key.name] = relative_locations

            relative_locations = relative_key_cache[shape_key.relative_key.name]

            vertex_locations -= relative_locations

            if (np.abs(vertex_locations) < ShapeKeyPruner.TOLERANCE).all():
                if ('vrc.v_sil' not in shape_key.name):
                    shape_keys_to_delete.append(shape_key.name)

        if (len(shape_keys_to_delete) > 0):
            report_messages.append(t('ShapeKeyPruner.removedPrefix'))

            for keyblock_name in shape_keys_to_delete:
                mesh.shape_key_remove(mesh.data.shape_keys.key_blocks[keyblock_name])
                report_messages.append(keyblock_name)

        else:
            report_messages.append(t('ShapeKeyPruner.nothingRemoved'))

        self.report({'INFO'}, " \n".join(report_messages))
        return {'FINISHED'}


def addToShapekeyMenu(self, context):
    self.layout.separator()
    self.layout.operator(ShapeKeyApplier.bl_idname, text=t('addToShapekeyMenu.ShapeKeyApplier.label'), icon="KEY_HLT")
    self.layout.operator(ShapeKeyPruner.bl_idname, text=t('addToShapekeyMenu.ShapeKeyPruner.label'), icon="KEY_DEHLT")
