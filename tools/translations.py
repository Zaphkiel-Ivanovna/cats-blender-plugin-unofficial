# GPL License


import os
import bpy
import json
import time
import requests

from .. import globs
from .register import register_wrap

bundled_translations_dir = globs.resource_path("translations")

dictionary: dict[str, str] = {}
languages = []
verbose = True
last_loaded_language = None
dictionary_download_link = "https://raw.githubusercontent.com/teamneoneko/Cats-Blender-Plugin-Unofficial-translations/5x-translations/dictionary.json"
_addon_startup_time = None

REQUEST_TIMEOUT = 15


def get_user_translations_dir():
    return globs.user_data_dir("translations")


def list_language_codes():
    """Language codes from the downloaded translations and from the bundled ones."""
    codes = set()
    for directory in (bundled_translations_dir, get_user_translations_dir()):
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".json"):
                codes.add(name[:-len(".json")])
    return sorted(codes)


def find_translation_file(language_code):
    """The downloaded translation for this language if there is one, else the bundled one."""
    name = language_code + ".json"
    downloaded = os.path.join(get_user_translations_dir(), name)
    if os.path.isfile(downloaded):
        return downloaded
    bundled = os.path.join(bundled_translations_dir, name)
    return bundled if os.path.isfile(bundled) else None


def load_translations(override_language=None):
    global dictionary, languages, last_loaded_language, _addon_startup_time

    if _addon_startup_time is None:
        _addon_startup_time = time.time()

    dictionary = {}

    print("Loading translations")

    if override_language:
        language = override_language
        print(f"Using override language: {language}")
    else:
        language = get_language_from_settings()
        print(f"Selected language: {language}")

    languages = ["auto", *list_language_codes()]
    print(f"Available languages: {languages}")

    language_to_load = language if language and language in languages else None
    if language_to_load is None:
        print(f"Language '{language}' not available, defaulting to en_US")
        language_to_load = "en_US"

    translation_file = find_translation_file(language_to_load)
    if translation_file is None and language_to_load != "en_US":
        print(f"Translation file not found for language: {language_to_load}")
        language_to_load = "en_US"
        translation_file = find_translation_file(language_to_load)

    if translation_file is None:
        print("DEFAULT TRANSLATION FILE 'en_US.json' NOT FOUND.")
    else:
        print(f"Loading translation file: {translation_file}")
        with open(translation_file, encoding="utf8") as file:
            dictionary = json.load(fp=file)["messages"]
        last_loaded_language = language_to_load
        print(f"Loaded {len(dictionary)} translations from {language_to_load}")

    check_missing_translations()


def t(phrase: str, *args, **kwargs):
    output = dictionary.get(phrase)
    if output is None:
        if verbose:
            print('Warning: Unknown phrase: ' + phrase)
        return phrase

    return output.format(*args, **kwargs)


def check_missing_translations():
    for key, value in dictionary.items():
        if not value and verbose:
            print('Translations en_US: Value missing for key: ' + key)


def get_languages_list(self, context):
    choices = []

    for language in languages:
        choices.append((language, language, language))

    return choices


def update_ui(self, context):

    print("update_ui function called")

    if _addon_startup_time and (time.time() - _addon_startup_time) < 2.0:
        print("Skipping reload during initialization period")
        return

    current_language = context.scene.ui_lang if context and hasattr(context, 'scene') else None

    if current_language and "auto" in current_language.lower():
        current_language = convert_locale_to_language_code(bpy.app.translations.locale)
        if not current_language:
            current_language = "en_US"

    print(f"Current language from scene: {current_language}, Last loaded: {last_loaded_language}")

    if current_language != last_loaded_language:
        print(f"Language changed from {last_loaded_language} to {current_language}, reloading translations")

        from . import settings
        settings.update_settings_core(None, None)

        load_translations()

        def delayed_reload():
            try:
                print("Auto-reloading scripts to apply new language...")
                bpy.ops.script.reload()
                print("Language changed successfully!")
            except Exception as e:
                print(f"Script reload failed: {e}")
            return

        bpy.app.timers.register(delayed_reload, first_interval=2.0)
    else:
        print("Language unchanged, no reload needed")


def get_language_from_settings():
    try:
        with open(globs.get_settings_file(), encoding="utf8") as file:
            settings_data = json.load(file)
    except FileNotFoundError:
        print("SETTINGS FILE NOT FOUND!")
        return None
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN SETTINGS FILE")
        return None

    if not settings_data:
        print("NO DATA IN SETTINGS FILE")
        return None

    lang = settings_data.get("ui_lang")
    if not lang or "auto" in lang.lower():
        current_locale = bpy.app.translations.locale
        detected_lang = convert_locale_to_language_code(current_locale)
        print(f"Auto-detecting language from Blender locale: {current_locale} -> {detected_lang}")
        return detected_lang

    return lang


def convert_locale_to_language_code(blender_locale):
    """
    Convert Blender's locale format to supported language code format.
    Blender uses formats like 'en_US', 'ja_JP', 'ko_KR', etc.
    """
    if not blender_locale:
        return None

    locale_str = str(blender_locale)

    available = list_language_codes()
    for lang_code in available:
        if locale_str == lang_code:
            print(f"Found exact locale match: {lang_code}")
            return lang_code

    language_only = locale_str.split("_", maxsplit=1)[0].lower() if "_" in locale_str else locale_str.lower()
    for lang_code in available:
        if lang_code.lower().startswith(language_only):
            print(f"Found language match: {lang_code}")
            return lang_code

    print(f"No language match found for locale: {locale_str}, defaulting to en_US")
    return None

def reload_scripts():
    bpy.ops.script.reload()
    return


@register_wrap
class DownloadTranslations(bpy.types.Operator):
    bl_idname = 'cats_translations.download_latest'
    bl_label = 'Download Latest Translations'
    bl_description = 'Download the latest translations for cats UI and internal dictionary'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        repo_owner = "teamneoneko"
        repo_name = "Cats-Blender-Plugin-Unofficial-translations"
        branch = "5x-translations"
        folder_path = "UI%20Tanslations"

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{folder_path}?ref={branch}"

        target_dir = get_user_translations_dir()

        try:
            response = requests.get(api_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            entries = response.json()

            for entry in entries:
                if entry["type"] != "file" or not entry["name"].endswith(".json"):
                    continue

                file_name = entry["name"]
                if file_name != os.path.basename(file_name) or file_name.startswith("."):
                    print(f"Skipped translation with an unexpected name: {file_name!r}")
                    continue

                file_response = requests.get(entry["download_url"], timeout=REQUEST_TIMEOUT)
                file_response.raise_for_status()

                with open(os.path.join(target_dir, file_name), 'wb') as out_file:
                    out_file.write(file_response.content)

                print(f"Downloaded: {file_name}")

        except requests.exceptions.RequestException as e:
            print("TRANSLATIONS FILES COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "TRANSLATIONS FILES COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}

        print('TRANSLATIONS DOWNLOAD FINISHED')

        print('DOWNLOAD DICTIONARY FILE')
        try:
            response = requests.get(dictionary_download_link, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            with open(globs.user_data_path("dictionary.json"), 'wb') as out_file:
                out_file.write(response.content)
        except requests.exceptions.RequestException as e:
            print("DICTIONARY FILE COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "DICTIONARY FILE COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}
        print('DICTIONARY DOWNLOAD FINISHED')

        bpy.app.timers.register(reload_scripts, first_interval=0.1)

        self.report({'INFO'}, "Successfully downloaded the translations and dictionary")
        return {'FINISHED'}


load_translations()
