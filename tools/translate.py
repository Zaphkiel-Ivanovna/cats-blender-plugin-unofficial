# MIT License

import re
import os
import bpy
import copy
import json
import traceback
import collections
import requests.exceptions
import csv

from datetime import datetime, UTC
from collections import OrderedDict

from . import common as Common
from .register import register_wrap
from .. import globs
from ..extern_tools.google_trans_new.google_trans_new import google_translator
from .translations import t

from mmd_tools_local import translations as mmd_translations

dictionary = {}
dictionary_google = {}

def get_dictionary_file():
    """The downloaded dictionary if there is one, otherwise the bundled copy."""
    downloaded = globs.user_data_path("dictionary.json")
    return downloaded if os.path.isfile(downloaded) else globs.resource_path("dictionary.json")


def get_dictionary_google_file():
    return globs.user_data_path("dictionary_google.json")

def get_cats_dir():
    """Default export directory, used when the scene property is empty."""
    return os.path.join(bpy.utils.user_resource('DATAFILES'), "cats")

@register_wrap
class TranslateShapekeyButton(bpy.types.Operator):
    bl_idname = 'cats_translate.shapekeys'
    bl_label = t('TranslateShapekeyButton.label')
    bl_description = t('TranslateShapekeyButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        saved_data = Common.SavedData()

        cats_dir = context.scene.custom_translate_csv_export_dir
        if not cats_dir:
            cats_dir = get_cats_dir()

        if not os.path.exists(cats_dir):
            try:
                os.makedirs(cats_dir)
            except OSError:
                self.report({'ERROR'}, "Unable to create export folder. Please manually set the export directory")
                return {'CANCELLED'}

        if not os.path.exists(cats_dir) or not os.access(cats_dir, os.W_OK):
            self.report({'ERROR'}, "Unable to write to export folder. Please manually set the export directory")
            return {'CANCELLED'}

        skip_locked_shape_keys = bpy.context.scene.skip_locked_shape_keys
        if context.scene.export_translate_csv:

            blend_path = bpy.context.blend_data.filepath
            if not blend_path:
                self.report({'ERROR'}, "Please save blend first!")
                return {'CANCELLED'}

            to_translate = []
            for mesh in Common.get_meshes_objects(mode=2):
                if Common.has_shapekeys(mesh):
                    for key in mesh.data.shape_keys.key_blocks:
                        if can_translate_shape_key(key, skip_locked_shape_keys):
                            to_translate.append(key.name)

            update_dictionary(to_translate, translating_shapes=True, self=self)
            Common.update_shapekey_orders()

            shapekeys = []
            i = 0
            for mesh in Common.get_meshes_objects(mode=2):
                if Common.has_shapekeys(mesh):
                    for key in mesh.data.shape_keys.key_blocks:
                        if can_translate_shape_key(key, skip_locked_shape_keys):
                            original_name = key.name
                            key.name, translated = translate(key.name, add_space=True, translating_shapes=True)

                            if translated:
                                i += 1
                                shapekeys.append({
                                    'mesh/object': mesh.name,
                                    'original': original_name,
                                    'translated': key.name
                                })

            blend_name = os.path.splitext(os.path.basename(blend_path))[0]
            export_path = os.path.join(str(cats_dir), blend_name + "_shapekeys.csv")

            with open(export_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['mesh/object', 'original', 'translated'])
                for key in shapekeys:
                    writer.writerow([key['mesh/object'], key['original'], key['translated']])

        else:
            to_translate = []
            for mesh in Common.get_meshes_objects(mode=2):
                if Common.has_shapekeys(mesh):
                    for shapekey in mesh.data.shape_keys.key_blocks:
                        if can_translate_shape_key(shapekey, skip_locked_shape_keys) and shapekey.name not in to_translate:
                            to_translate.append(shapekey.name)

            update_dictionary(to_translate, translating_shapes=True, self=self)

            Common.update_shapekey_orders()

            i = 0
            for mesh in Common.get_meshes_objects(mode=2):
                if Common.has_shapekeys(mesh):
                    for shapekey in mesh.data.shape_keys.key_blocks:
                        if can_translate_shape_key(shapekey, skip_locked_shape_keys):
                            shapekey.name, translated = translate(shapekey.name, add_space=True, translating_shapes=True)
                            if translated:
                                i += 1

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateShapekeyButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateBonesButton(bpy.types.Operator):
    bl_idname = 'cats_translate.bones'
    bl_label = t('TranslateBonesButton.label')
    bl_description = t('TranslateBonesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        saved_data = Common.SavedData()

        cats_dir = context.scene.custom_translate_csv_export_dir
        if not cats_dir:
            cats_dir = get_cats_dir()

        if not os.path.exists(cats_dir):
            try:
                os.makedirs(cats_dir)
            except OSError:
                self.report({'ERROR'}, "Unable to create export folder. Please manually set the export directory")
                return {'CANCELLED'}

        if not os.path.exists(cats_dir) or not os.access(cats_dir, os.W_OK):
            self.report({'ERROR'}, "Unable to write to export folder. Please manually set the export directory")
            return {'CANCELLED'}

        if context.scene.export_translate_csv:

            blend_path = bpy.context.blend_data.filepath
            if not blend_path:
                self.report({'ERROR'}, "Please save blend first!")
                return {'CANCELLED'}

            to_translate = []
            for armature in Common.get_armature_objects():
                for bone in armature.data.bones:
                    to_translate.append(bone.name)

            update_dictionary(to_translate, self=self)

            bones = []
            i = 0
            for armature in Common.get_armature_objects():
                for bone in armature.data.bones:
                    original_name = bone.name
                    bone.name, translated = translate(bone.name)
                    if translated:
                        i += 1
                        bones.append({
                            'armature': armature.name,
                            'original': original_name,
                            'translated': bone.name
                        })

            blend_name = os.path.splitext(os.path.basename(blend_path))[0]
            export_path = os.path.join(str(cats_dir), blend_name + "_bones.csv")

            with open(export_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['armature', 'original', 'translated'])
                for bone in bones:
                    writer.writerow([bone['armature'], bone['original'], bone['translated']])

        else:
            to_translate = []
            for armature in Common.get_armature_objects():
                for bone in armature.data.bones:
                    if bone.name not in to_translate:
                        to_translate.append(bone.name)

            update_dictionary(to_translate, self=self)

            i = 0
            for armature in Common.get_armature_objects():
                for bone in armature.data.bones:
                    original_name = bone.name
                    bone.name, translated = translate(bone.name)
                    if translated:
                        i += 1

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateBonesButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateObjectsButton(bpy.types.Operator):
    bl_idname = 'cats_translate.objects'
    bl_label = t('TranslateObjectsButton.label')
    bl_description = t('TranslateObjectsButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        saved_data = Common.SavedData()

        cats_dir = context.scene.custom_translate_csv_export_dir
        if not cats_dir:
            cats_dir = get_cats_dir()

        if not os.path.exists(cats_dir):
            try:
                os.makedirs(cats_dir)
            except OSError:
                self.report({'ERROR'}, "Unable to create export folder. Please manually set the export directory")
                return {'CANCELLED'}

        if not os.path.exists(cats_dir) or not os.access(cats_dir, os.W_OK):
            self.report({'ERROR'}, "Unable to write to export folder. Please manually set the export directory")
            return {'CANCELLED'}

        if context.scene.export_translate_csv:
            blend_path = bpy.context.blend_data.filepath
            if not blend_path:
                self.report({'ERROR'}, "Please save blend first!")
                return {'CANCELLED'}

            to_translate = []
            for obj in Common.get_objects():
                to_translate.append(obj.name)

            update_dictionary(to_translate, self=self)

            objects_translations = []
            i = 0
            for obj in Common.get_objects():
                original_name = obj.name
                obj.name, translated = translate(obj.name)
                if translated:
                    i += 1
                    objects_translations.append({
                        'object': obj.name,
                        'original': original_name,
                        'translated': obj.name
                    })

            blend_name = os.path.splitext(os.path.basename(blend_path))[0]
            export_path = os.path.join(str(cats_dir), blend_name + "_objects.csv")

            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['object', 'original', 'translated'])
                for translation in objects_translations:
                    writer.writerow([translation['object'], translation['original'], translation['translated']])

        else:
            to_translate = []
            for obj in Common.get_objects():
                if obj.name not in to_translate:
                    to_translate.append(obj.name)

            update_dictionary(to_translate, self=self)

            i = 0
            for obj in Common.get_objects():
                original_name = obj.name
                obj.name, translated = translate(obj.name)
                if translated:
                    i += 1

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateObjectsButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateMaterialsButton(bpy.types.Operator):
    bl_idname = 'cats_translate.materials'
    bl_label = t('TranslateMaterialsButton.label')
    bl_description = t('TranslateMaterialsButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        saved_data = Common.SavedData()

        cats_dir = context.scene.custom_translate_csv_export_dir
        if not cats_dir:
            cats_dir = get_cats_dir()

        if not os.path.exists(cats_dir):
            try:
                os.makedirs(cats_dir)
            except OSError:
                self.report({'ERROR'}, "Unable to create export folder. Please manually set the export directory")
                return {'CANCELLED'}

        if not os.path.exists(cats_dir) or not os.access(cats_dir, os.W_OK):
            self.report({'ERROR'}, "Unable to write to export folder. Please manually set the export directory")
            return {'CANCELLED'}

        if context.scene.export_translate_csv:
            blend_path = bpy.context.blend_data.filepath
            if not blend_path:
                self.report({'ERROR'}, "Please save blend first!")
                return {'CANCELLED'}

            to_translate = []
            for mesh in Common.get_meshes_objects(mode=2):
                for matslot in mesh.material_slots:
                    to_translate.append(matslot.name)

            update_dictionary(to_translate, self=self)

            materials_translations = []
            i = 0
            for mesh in Common.get_meshes_objects(mode=2):
                for matslot in mesh.material_slots:
                    original_name = matslot.name
                    matslot.material.name, translated = translate(matslot.material.name)
                    if translated:
                        i += 1
                        materials_translations.append({
                            'mesh': mesh.name,
                            'original': original_name,
                            'translated': matslot.material.name
                        })

            blend_name = os.path.splitext(os.path.basename(blend_path))[0]
            export_path = os.path.join(str(cats_dir), blend_name + "_materials.csv")

            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['mesh', 'original', 'translated'])
                for translation in materials_translations:
                    writer.writerow([translation['mesh'], translation['original'], translation['translated']])

        else:
            to_translate = []
            for mesh in Common.get_meshes_objects(mode=2):
                for matslot in mesh.material_slots:
                    if matslot.name not in to_translate:
                        to_translate.append(matslot.name)

            update_dictionary(to_translate, self=self)

            i = 0
            for mesh in Common.get_meshes_objects(mode=2):
                for matslot in mesh.material_slots:
                    original_name = matslot.name
                    matslot.material.name, translated = translate(matslot.material.name)
                    if translated:
                        i += 1

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateMaterialsButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateAllButton(bpy.types.Operator):
    bl_idname = 'cats_translate.all'
    bl_label = t('TranslateAllButton.label')
    bl_description = t('TranslateAllButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):

        if context.scene.export_translate_csv:
            if not bpy.data.filepath:
                self.report({'ERROR'}, "Please save the blend file before exporting translations.")
                return {'CANCELLED'}

        error_shown = False

        try:
            if Common.get_armature():
                bpy.ops.cats_translate.bones('INVOKE_DEFAULT')
        except RuntimeError as e:
            self.report({'ERROR'}, str(e).replace('Error: ', ''))
            error_shown = True

        try:
            bpy.ops.cats_translate.shapekeys('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        try:
            bpy.ops.cats_translate.objects('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        try:
            bpy.ops.cats_translate.materials('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        if error_shown:
            return {'CANCELLED'}
        self.report({'INFO'}, t('TranslateAllButton.success'))
        return {'FINISHED'}


def load_translations():
    global dictionary
    dictionary = OrderedDict()
    temp_dict = OrderedDict()
    dict_found = False

    try:
        with open(get_dictionary_file(), encoding="utf8") as file:
            temp_dict = json.load(file, object_pairs_hook=collections.OrderedDict)
            dict_found = True
    except FileNotFoundError:
        print('DICTIONARY NOT FOUND!')
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN DICTIONARY")

    try:
        with open(get_dictionary_google_file(), encoding="utf8") as file:
            global dictionary_google
            dictionary_google = json.load(file, object_pairs_hook=collections.OrderedDict)

            if 'created' not in dictionary_google \
                    or 'translations' not in dictionary_google \
                    or 'translations_full' not in dictionary_google:
                reset_google_dict()
            else:
                for name, trans in dictionary_google.get('translations').items():
                    if not name:
                        continue

                    if name in temp_dict:
                        print(name, 'ALREADY IN INTERNAL DICT!')
                        continue

                    temp_dict[name] = trans

    except FileNotFoundError:
        print('GOOGLE DICTIONARY NOT FOUND!')
        reset_google_dict()
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN GOOOGLE DICTIONARY")
        reset_google_dict()

    for key in sorted(temp_dict, key=len, reverse=True):
        dictionary[key] = temp_dict[key]


    return dict_found


def update_dictionary(to_translate_list, translating_shapes=False, self=None):
    global dictionary
    regex = '[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+'

    use_google_only = False
    if translating_shapes and bpy.context.scene.use_google_only:
        use_google_only = True

    if type(to_translate_list) is str:
        to_translate_list = [to_translate_list]

    google_input = []

    for to_translate in to_translate_list:
        length = len(to_translate)
        translated_count = 0

        to_translate = fix_jp_chars(to_translate)

        if use_google_only:
            if not re.findall(regex, to_translate):
                continue

            translated = False
            for key, value in dictionary_google.get('translations_full').items():
                if to_translate == key and value:
                    translated = True

            if not translated:
                google_input.append(to_translate)

        else:
            for key, value in dictionary.items():
                if key in to_translate:
                    if value:
                        to_translate = to_translate.replace(key, value)
                    else:
                        continue

                    translated_count += len(key)
                    if translated_count >= length:
                        break

            if translated_count < length:
                match = re.findall(regex, to_translate)
                if match:
                    for name in match:
                        if name not in google_input and name not in dictionary:
                            google_input.append(name)

    if not google_input:
        return

    print('GOOGLE DICT UPDATE!')
    translator = google_translator(url_suffix='com')
    token_tries = 0
    while True:
        try:
            translations = [translator.translate(text, lang_src='ja', lang_tgt='en').strip() for text in google_input]
            break
        except (requests.exceptions.ConnectionError, ConnectionRefusedError):
            print('CONNECTION TO GOOGLE FAILED!')
            if self:
                self.report({'ERROR'}, t('update_dictionary.error.cantConnect'))
            return
        except (json.JSONDecodeError, TypeError) as e:
            if self:
                print(traceback.format_exc())
                self.report({'ERROR'}, 'Google Translate API has changed or returned an invalid response or you'
                                    '\ncould have been banned. Cats translated what it could with the local dictionary,'
                                    '\nbut you will need to update the translation module or try again later.')
            print('GOOGLE TRANSLATE API ERROR:', str(e))
            return
        except RuntimeError as e:
            error = Common.html_to_text(str(e))
            if self:
                if 'Please try your request again later' in error:
                    self.report({'ERROR'}, t('update_dictionary.error.temporaryBan') + t('update_dictionary.error.catsTranslated'))
                    print('YOU GOT BANNED BY GOOGLE!')
                    return

                if 'Error 403' in error:
                    self.report({'ERROR'}, t('update_dictionary.error.cantAccess') + t('update_dictionary.error.catsTranslated'))
                    print('NO PERMISSION TO USE GOOGLE TRANSLATE!')
                    return

                self.report({'ERROR'}, t('update_dictionary.error.errorMsg') + t('update_dictionary.error.catsTranslated') + '\n' + '\nGoogle: ' + error)
            print('', 'You got an error message from Google:', error, '')
            return
        except AttributeError:
            token_tries += 1
            if token_tries < 3:
                print('RETRY', token_tries)
                translator = google_translator(url_suffix='com')
                continue

            if self:
                self.report({'ERROR'}, t('update_dictionary.error.apiChanged'))
            print('ERROR: GOOGLE API CHANGED!')
            print(traceback.format_exc())
            return

    for i, translation in enumerate(translations):
        name = google_input[i]

        if use_google_only:
            dictionary_google['translations_full'][name] = translation
        else:
            translation_words = translation.split(' ')
            translation_words = [word.capitalize() for word in translation_words]
            translation = ' '.join(translation_words)

            dictionary[name] = translation
            dictionary_google['translations'][name] = translation

        print(google_input[i], '->', translation)

    temp_dict = copy.deepcopy(dictionary)
    dictionary = OrderedDict()
    for key in sorted(temp_dict, key=len, reverse=True):
        dictionary[key] = temp_dict[key]

    save_google_dict()

    print('DICTIONARY UPDATE SUCCEEDED!')
    return


def translate(to_translate, add_space=False, translating_shapes=False):

    pre_translation = to_translate
    length = len(to_translate)
    translated_count = 0

    use_google_only = False
    if translating_shapes and bpy.context.scene.use_google_only:
        use_google_only = True

    addition = ''
    if add_space:
        addition = ' '

    to_translate = fix_jp_chars(to_translate)

    if use_google_only:
        for key, value in dictionary_google.get('translations_full').items():
            if to_translate == key and value:
                to_translate = value

    else:
        for key, value in dictionary.items():
            if key in to_translate:
                if not value:
                    continue

                to_translate = to_translate.replace(key, addition + value)

                translated_count += len(key)
                if translated_count >= length:
                    break

    to_translate = to_translate.replace('.L', '_L').replace('.R', '_R').replace('  ', ' ').replace('し', '').replace('っ', '').strip()


    return to_translate, pre_translation != to_translate


def fix_jp_chars(name):
    for values in mmd_translations.jp_half_to_full_tuples:
        if values[0] in name:
            name = name.replace(values[0], values[1])
    return name


def reset_google_dict():
    global dictionary_google
    dictionary_google = OrderedDict()

    now_utc = datetime.now(UTC).strftime(globs.time_format)

    dictionary_google['created'] = now_utc
    dictionary_google['translations'] = {}
    dictionary_google['translations_full'] = {}

    save_google_dict()
    print('GOOGLE DICT RESET')


def save_google_dict():
    with open(get_dictionary_google_file(), 'w', encoding="utf8") as outfile:
        json.dump(dictionary_google, outfile, ensure_ascii=False, indent=4)


def can_translate_shape_key(shapekey, skip_locked_shape_keys):
    if skip_locked_shape_keys:
        if not shapekey.lock_shape and 'vrc.' not in shapekey.name:
            return True
    else:
        if 'vrc.' not in shapekey.name:
            return True
    return False
