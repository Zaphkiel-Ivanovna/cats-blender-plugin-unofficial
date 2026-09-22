# MIT License

import os
import bpy
import bpy.utils.previews
from bpy.utils.previews import ImagePreviewCollection

from .. import globs

preview_collections: dict[str, ImagePreviewCollection] = {}

OTHER_ICONS = {
    'heart1': 'heart1.png',
    'discord1': 'discord1.png',
    'help1': 'help1.png',
    'cats1': 'cats1.png',
    'empty': 'empty.png',
    'mesh': 'mesh.png',
    'UP_ARROW': 'blender_up_arrow.png',
    'Resonite': 'rsn_logo128.png',
}


def load_other_icons():
    unload_icons()

    pcoll = bpy.utils.previews.new()

    icons_other_dir = globs.resource_path("icons", "other")
    for name, file_name in OTHER_ICONS.items():
        pcoll.load(name, os.path.join(icons_other_dir, file_name), 'IMAGE')

    preview_collections['custom_icons'] = pcoll


def unload_icons():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
