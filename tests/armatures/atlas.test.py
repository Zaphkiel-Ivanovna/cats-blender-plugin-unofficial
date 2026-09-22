# GPL License

import unittest
import sys
import bpy


class TestAddon(unittest.TestCase):
    def test_atlas_button(self):


        self.assertTrue(True)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddon)
runner = unittest.TextTestRunner()
ret = not runner.run(suite).wasSuccessful()
sys.exit(ret)
