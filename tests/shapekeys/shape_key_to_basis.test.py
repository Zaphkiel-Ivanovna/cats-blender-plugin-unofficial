# GPL License

import unittest
import sys
import bpy

from cats.tools.common import version_2_79_or_older


class TestAddon(unittest.TestCase):
    def set_active_by_name(self, object_name):
        if version_2_79_or_older():
            objects = bpy.context.scene.objects
        else:
            objects = bpy.context.view_layer.objects

        object_index = objects.find(object_name)
        self.assertGreaterEqual(object_index, 0, msg="Could not find object with name {name}".format(name=object_name))
        found_object = objects[object_index]
        objects.active = found_object
        return found_object

    def assertShapeKeysEqual(self, obj, expected_flattened_co_array, *shape_key_names):
        for shape_key_name in shape_key_names:
            shape_key = obj.data.shape_keys.key_blocks[shape_key_name]
            flattened_co_array = [None, ] * (len(shape_key.data) * 3)
            shape_key.data.foreach_get('co', flattened_co_array)
            self.assertEqual(expected_flattened_co_array, flattened_co_array,
                             msg="Expected {name} to be {expected}, but it was {actual}"
                             .format(name=shape_key_name, expected=expected_flattened_co_array, actual=flattened_co_array))

    def assertShapeKeysRelativeTo(self, obj, expected_relative_key_name, *shape_key_names):
        for shape_key_name in shape_key_names:
            shape_key = obj.data.shape_keys.key_blocks[shape_key_name]
            self.assertEqual(expected_relative_key_name, shape_key.relative_key.name)

    def assertShapeKeyValueEquals(self, obj, expected_value, shape_key_name):
        shape_key = obj.data.shape_keys.key_blocks[shape_key_name]
        self.assertEqual(expected_value, shape_key.value)

    def assertShapeKeyVertexGroupNameEquals(self, obj, expected_name, shape_key_name):
        shape_key = obj.data.shape_keys.key_blocks[shape_key_name]
        self.assertEqual(expected_name, shape_key.vertex_group)

    def test_no_shape_keys(self):
        self.set_active_by_name('01_NoShapes')
        self.assertRaises(RuntimeError, bpy.ops.cats_shapekey.shape_key_to_basis)

    def test_active_is_basis(self):
        self.set_active_by_name('02_BasisActive')
        self.assertRaises(RuntimeError, bpy.ops.cats_shapekey.shape_key_to_basis)

    def test_active_is_basis_relative_to_key1(self):
        self.set_active_by_name('03_BasisActiveRelativeToKey1')
        self.assertRaises(RuntimeError, bpy.ops.cats_shapekey.shape_key_to_basis)

    def test_active_relative_to_self(self):
        self.set_active_by_name('04_ActiveRelativeToSelf')
        self.assertRaises(RuntimeError, bpy.ops.cats_shapekey.shape_key_to_basis)

    def test_active_recursively_relative_to_self(self):
        self.set_active_by_name('05_ActiveRecursivelyRelativeToSelf')
        self.assertRaises(RuntimeError, bpy.ops.cats_shapekey.shape_key_to_basis)

    def test_immediately_relative_to_basis(self):
        obj = self.set_active_by_name('06_ImmediatelyRelative')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis', 'Key 2', 'Key 3', 'Key 4', 'Key 5', 'Key 6')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Basis', 'Key 2', 'Key 4')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Key 1 - Reverted', 'Key 5', 'Key 6')
        self.assertShapeKeysEqual(obj, [-1, -1, -1], 'Key 3')

    def test_recursively_relative_to_basis(self):
        obj = self.set_active_by_name('07_RecursivelyRelative')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis', 'Key 2', 'Key 3', 'Key 4', 'Key 5', 'Key 6', 'Key 7')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Basis', 'Key 2', 'Key 3', 'Key 5')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Key 1 - Reverted', 'Key 6', 'Key 7')
        self.assertShapeKeysEqual(obj, [-1, -1, -1], 'Key 4')

    def test_separate_from_basis(self):
        obj = self.set_active_by_name('08_Separate')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 2')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis', 'Key 1', 'Key 3', 'Key 4', 'Key 5', 'Key 6', 'Key 7', 'Key 8')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Basis', 'Key 3', 'Key 4')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Key 1', 'Key 5', 'Key 7', 'Key 8')
        self.assertShapeKeysEqual(obj, [-1, -1, -1], 'Key 2 - Reverted')
        self.assertShapeKeysEqual(obj, [-2, -2, -2], 'Key 6')

    def test_basis_relative_loop_special_case_(self):
        obj = self.set_active_by_name('09_BasisLoopSpecial')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeysRelativeTo(obj, 'Basis', 'Key 1')
        self.assertShapeKeysRelativeTo(obj, 'Key 1', 'Basis')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Basis')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Key 1 - Reverted')
        self.assertShapeKeysRelativeTo(obj, 'Basis', 'Key 1 - Reverted')
        self.assertShapeKeysRelativeTo(obj, 'Key 1 - Reverted', 'Basis')

    def test_non_zero_value(self):
        obj = self.set_active_by_name('10_Value')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeyValueEquals(obj, 0.25, 'Key 1')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [0.25, 0.25, 0.25], 'Basis')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Key 1 - Reverted')

    def test_vertex_group(self):
        obj = self.set_active_by_name('11_VertexGroup')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeyVertexGroupNameEquals(obj, 'Group', 'Key 1')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [0.25, 0.25, 0.25], 'Basis')
        self.assertShapeKeysEqual(obj, [-0.75, -0.75, -0.75], 'Key 1 - Reverted')
        self.assertShapeKeyVertexGroupNameEquals(obj, 'Group', 'Key 1 - Reverted')

    def test_non_zero_value_and_vertex_group(self):
        obj = self.set_active_by_name('12_ValueAndVertexGroup')
        self.assertShapeKeysEqual(obj, [0, 0, 0], 'Basis')
        self.assertShapeKeysEqual(obj, [1, 1, 1], 'Key 1')
        self.assertShapeKeyValueEquals(obj, 0.25, 'Key 1')
        self.assertShapeKeyVertexGroupNameEquals(obj, 'Group', 'Key 1')

        self.assertEqual(bpy.ops.cats_shapekey.shape_key_to_basis(), {'FINISHED'})

        self.assertShapeKeysEqual(obj, [0.0625, 0.0625, 0.0625], 'Basis')
        self.assertShapeKeysEqual(obj, [-0.1875, -0.1875, -0.1875], 'Key 1 - Reverted')
        self.assertShapeKeyVertexGroupNameEquals(obj, 'Group', 'Key 1 - Reverted')


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
