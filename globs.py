# MIT License

import os

import bpy

_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), 'resources')


def resource_path(*subpaths):
    """Path to a read-only file shipped inside the add-on."""
    return os.path.join(_RESOURCES_DIR, *subpaths)


def user_data_path(*subpaths, create=True):
    """Path under the per-user data directory.

    Blender replaces the extension directory wholesale on every update and mounts
    it read-only for system repositories, so writable state cannot live in there.
    extension_path_user is the API added in 4.2 for exactly this.
    """
    try:
        base = bpy.utils.extension_path_user(__package__, create=create)
    except (AttributeError, ValueError):
        base = bpy.utils.user_resource('CONFIG', path='cats_blender_plugin', create=create)

    path = os.path.join(base, *subpaths)
    if create and subpaths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def user_data_dir(*subpaths):
    """Directory under the per-user data directory, created if it is missing."""
    path = user_data_path(*subpaths)
    os.makedirs(path, exist_ok=True)
    return path


def get_settings_file():
    return user_data_path("settings.json")

root_bones = {}
root_bones_choices = {}

testing = []

dev_branch = False
dict_found = False
version = None
version_str = ''

time_format = "%Y-%m-%d %H:%M:%S"
time_format_github = "%Y-%m-%dT%H:%M:%SZ"

ICON_ADD, ICON_REMOVE = 'ADD', 'REMOVE'
ICON_URL = 'URL'
ICON_SETTINGS = 'SETTINGS'
ICON_ALL = 'PROP_ON'
ICON_MOD_ARMATURE = 'MOD_ARMATURE'
ICON_FIX_MODEL = 'SHADERFX'
ICON_EYE_ROTATION = 'DRIVER_ROTATIONAL_DIFFERENCE'
ICON_POSE_MODE = 'POSE_HLT'
ICON_SHADING_TEXTURE = 'SHADING_TEXTURE'
ICON_PROTECT = 'LOCKED'
ICON_UNPROTECT = 'UNLOCKED'
ICON_EXPORT = 'EXPORT'

ICON_ERROR = 'ERROR'
ICON_WARNING = 'ERROR'
ICON_INFO = 'INFO'
ICON_QUESTION = 'QUESTION'
ICON_REFRESH = 'FILE_REFRESH'
ICON_PLAY = 'PLAY'
ICON_PAUSE = 'PAUSE'
ICON_EXECUTE = 'TRIA_RIGHT'
ICON_ARMATURE = 'ARMATURE_DATA'
ICON_MESH = 'MESH_DATA'
ICON_BONE = 'BONE_DATA'
ICON_MATERIAL = 'MATERIAL'
ICON_SHAPEKEY = 'SHAPEKEY_DATA'
ICON_HEART = 'HEART'

