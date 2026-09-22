# GPL License

import unittest
import sys
import bpy


class TestAddon(unittest.TestCase):
    def test_viseme_button(self):
        bpy.ops.cats_armature.fix()

        bpy.ops.cats_translate.shapekeys()

        result = bpy.ops.cats_viseme.create()
        self.assertTrue(result == {'FINISHED'})


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
