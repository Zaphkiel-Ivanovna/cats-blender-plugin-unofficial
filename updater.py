# MIT License

import os
import bpy
import shutil
import zipfile
import requests
from threading import Thread
from collections import OrderedDict
from .tools.translations import t
from .tools.common import wrap_dynamic_enum_items
from . import globs
from . import CATS_VERSION, dev_branch

no_ver_check = False
fake_update = False

is_checking_for_update = False
checked_on_startup = False
_check_finished = False
_check_error = ''
version_list = None
current_version = []
current_version_str = ''
update_needed = False
latest_version = None
latest_version_str = ''
used_updater_panel = False
update_finished = False
remind_me_later = False
is_ignored_version = False

confirm_update_to = ''

show_error = ''

main_dir = os.path.dirname(__file__)
downloads_dir = globs.user_data_path("downloads")
ignore_ver_file = globs.user_data_path("ignore_version.txt")
no_auto_ver_check_file = globs.user_data_path("no_auto_ver_check.txt")

package_name = __package__

ICON_URL = 'URL'

RELEASES_API_URL = 'https://git.disroot.org/api/v1/repos/Neoneko/Cats-Blender-Plugin/releases'
REQUEST_TIMEOUT = 15


def get_repo_module():
    """The extension repository this add-on is installed in, e.g. 'user_default'.

    Returns None when it is not running as an extension, in which case Blender's
    installer cannot be used and the update has to go through the Extensions UI.
    """
    parts = (__package__ or '').split('.')
    if len(parts) >= 3 and parts[0] == 'bl_ext':
        return parts[1]
    return None

BLENDER_VERSION = tuple(bpy.app.version)

class CheckForUpdateButton(bpy.types.Operator):
    bl_idname = 'cats_updater.check_for_update'
    bl_label = t('CheckForUpdateButton.label')
    bl_description = t('CheckForUpdateButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return not is_checking_for_update

    def execute(self, context):
        global used_updater_panel
        used_updater_panel = True
        check_for_update_background()
        return {'FINISHED'}


class UpdateToLatestButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_latest'
    bl_label = t('UpdateToLatestButton.label')
    bl_description = t('UpdateToLatestButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return update_needed

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = 'latest'
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class UpdateToSelectedButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_selected'
    bl_label = t('UpdateToSelectedButton.label')
    bl_description = t('UpdateToSelectedButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if is_checking_for_update or not version_list:
            return False
        return True

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = context.scene.cats_updater_version_list
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class UpdateToDevButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_dev'
    bl_label = t('UpdateToDevButton.label')
    bl_description = t('UpdateToDevButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = 'dev'
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class RemindMeLaterButton(bpy.types.Operator):
    bl_idname = 'cats_updater.remind_me_later'
    bl_label = t('RemindMeLaterButton.label')
    bl_description = t('RemindMeLaterButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global remind_me_later
        remind_me_later = True
        self.report({'INFO'}, t('RemindMeLaterButton.success'))
        return {'FINISHED'}


class IgnoreThisVersionButton(bpy.types.Operator):
    bl_idname = 'cats_updater.ignore_this_version'
    bl_label = t('IgnoreThisVersionButton.label')
    bl_description = t('IgnoreThisVersionButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        set_ignored_version()
        self.report({'INFO'}, t('IgnoreThisVersionButton.success', name=latest_version_str))
        return {'FINISHED'}


class ShowPatchnotesPanel(bpy.types.Operator):
    bl_idname = 'cats_updater.show_patchnotes'
    bl_label = t('ShowPatchnotesPanel.label')
    bl_description = t('ShowPatchnotesPanel.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if is_checking_for_update or not version_list:
            return False
        return True

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        global used_updater_panel
        used_updater_panel = True
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 8.2))

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = col.row(align=True)
        row.prop(context.scene, 'cats_updater_version_list')

        if context.scene.cats_updater_version_list:
            version = version_list.get(context.scene.cats_updater_version_list)

            col.separator()
            row = col.row(align=True)
            row.label(text=t('ShowPatchnotesPanel.releaseDate', date=version[2]))

            col.separator()
            for line in version[1].replace('**', '').split('\r\n'):
                row = col.row(align=True)
                row.scale_y = 0.75
                row.label(text=line)

        col.separator()


class ConfirmUpdatePanel(bpy.types.Operator):
    bl_idname = 'cats_updater.confirm_update_panel'
    bl_label = t('ConfirmUpdatePanel.label')
    bl_description = t('ConfirmUpdatePanel.desc')
    bl_options = {'INTERNAL'}

    show_patchnotes = False

    def execute(self, context):
        print('UPDATE TO ' + confirm_update_to)
        if confirm_update_to == 'dev':
            update_now(dev=True)
        elif confirm_update_to == 'latest':
            update_now(latest=True)
        else:
            update_now(version=confirm_update_to)
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.1))

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        version_str = confirm_update_to
        if confirm_update_to == 'latest':
            version_str = latest_version_str
        elif confirm_update_to == 'dev':
            version_str = 'Dev'

        col.separator()
        row = col.row(align=True)
        row.label(text='Version: ' + version_str)

        if confirm_update_to == 'dev':
            col.separator()
            col.separator()
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev1'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev2'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev3'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev4'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev5'))

        else:
            row.operator(ShowPatchnotesPanel.bl_idname, text=t('ConfirmUpdatePanel.ShowPatchnotesPanel.label'))

        col.separator()
        col.separator()
        row = col.row(align=True)
        row.scale_y = 0.65
        row.label(text=t('ConfirmUpdatePanel.updateNow'), icon=ICON_URL)


class UpdateCompletePanel(bpy.types.Operator):
    bl_idname = 'cats_updater.update_complete_panel'
    bl_label = t('UpdateCompletePanel.label')
    bl_description = t('UpdateCompletePanel.desc')
    bl_options = {'INTERNAL'}

    show_patchnotes = False

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.1))

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        if update_finished:
            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.success1'), icon='FILE_TICK')

            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.success2'), icon='BLANK1')
        else:
            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.failure1'), icon='CANCEL')

            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.failure2'), icon='BLANK1')


class UpdateNotificationPopup(bpy.types.Operator):
    bl_idname = 'cats_updater.update_notification_popup'
    bl_label = t('UpdateNotificationPopup.label')
    bl_description = t('UpdateNotificationPopup.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        action = context.scene.cats_update_action
        if action == 'UPDATE':
            update_now(latest=True)
        elif action == 'IGNORE':
            set_ignored_version()
        else:
            global remind_me_later
            remind_me_later = True
        ui_refresh()
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.6))


    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = layout_split(col, factor=0.55, align=True)
        row.scale_y = 1.05
        row.label(text=t('UpdateNotificationPopup.newUpdate', name=latest_version_str), icon='SOLO_ON')
        row.operator(ShowPatchnotesPanel.bl_idname, text=t('UpdateNotificationPopup.ShowPatchnotesPanel.label'))

        col.separator()
        col.separator()
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'cats_update_action', expand=True)


def check_for_update_background(check_on_startup=False):
    global is_checking_for_update, checked_on_startup, _check_finished, _check_error
    if check_on_startup and checked_on_startup:
        return
    if is_checking_for_update:
        return

    checked_on_startup = True

    if check_on_startup and os.path.isfile(no_auto_ver_check_file):
        print('AUTO CHECK DISABLED VIA FILE')
        return

    is_checking_for_update = True
    _check_finished = False
    _check_error = ''

    bpy.app.timers.register(_poll_update_check, first_interval=0.2)

    thread = Thread(target=check_for_update, args=[], daemon=True)
    thread.start()


def check_for_update():
    """Runs on a worker thread, so it must not touch bpy at all.

    None of Blender's Python API is thread safe, and its own docs say Python
    threads are unsupported. This does network I/O and writes plain module
    globals; every bpy call belongs to _poll_update_check on the main thread.
    """
    global update_needed, is_ignored_version, _check_finished, _check_error
    print('Checking for Cats update...')

    try:
        if not get_github_releases('teamneoneko'):
            _check_error = t('check_for_update.cantCheck')
            return

        update_needed = check_for_update_available()
        is_ignored_version = check_ignored_version()
        print('Update found!' if update_needed else 'No update found.')
    finally:
        _check_finished = True


def _poll_update_check():
    """Main-thread timer that picks up the worker's result and does the bpy work."""
    if not _check_finished:
        return 0.2

    finish_update_checking(error=_check_error)

    if update_needed and not used_updater_panel and not is_ignored_version:
        show_update_notification()

    return None


def get_github_releases(repo):
    global version_list
    version_list = OrderedDict()

    if fake_update:
        print('FAKE INSTALL!')

        version = 'v-99-99-99'
        version_tag = version.replace('-', '.')
        if version_tag.startswith('v.'):
            version_tag = version_tag[2:]
        if version_tag.startswith('v'):
            version_tag = version_tag[1:]

        version_list[version_tag] = ['', 'Put exiting new stuff here', 'Today']
        version_list['12.34.56.78'] = ['', 'Nothing new to see', 'A week ago probably']
        return True

    try:
        response = requests.get(RELEASES_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        print('URL ERROR:', e)
        return False
    if not data:
        return False
    
    tag_prefix = f"{BLENDER_VERSION[0]}.{BLENDER_VERSION[1]}."

    for version in data:
        full_tag = version.get('tag_name')
        if not full_tag or not full_tag.startswith(tag_prefix):
            continue

        version_list[full_tag] = [
            version['zipball_url'],
            version['body'],
            version['published_at'].split('T')[0]
        ]

    return True


def parse_version(version_str):
    """Turn a normalized tag such as '5.0.2' into [5, 0, 2], stopping at the first non-numeric part."""
    parts = []
    for part in version_str.split('.'):
        if not part.isdigit():
            break
        parts.append(int(part))
    return parts


def check_for_update_available():
    if not version_list:
        return False

    global latest_version, latest_version_str
    latest_version = []
    for version in version_list.keys():
        parsed = parse_version(version)
        if parsed > latest_version:
            latest_version = parsed
            latest_version_str = version

    return bool(latest_version) and latest_version > current_version


def finish_update_checking(error=''):
    global is_checking_for_update, show_error
    is_checking_for_update = False

    if used_updater_panel:
        show_error = error

    ui_refresh()


def ui_refresh():
    for window_manager in bpy.data.window_managers:
        for window in window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()


def show_update_notification():
    atr = UpdateNotificationPopup.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


def update_now(version=None, latest=False, dev=False):
    if fake_update:
        finish_update()
        return
    if dev:
        print('UPDATE TO DEVELOPMENT')
        major_version = CATS_VERSION.split('.')[0]
        update_link = f'https://git.disroot.org/Neoneko/Cats-Blender-Plugin/archive/blender-{major_version}x-dev.zip'
    elif latest or not version:
        print('UPDATE TO ' + latest_version_str)
        update_link = version_list.get(latest_version_str)[0]
        bpy.context.scene.cats_updater_version_list = latest_version_str
    else:
        print('UPDATE TO ' + version)
        update_link = version_list[version][0]

    download_file(update_link)


def download_file(update_url):
    update_zip_file = os.path.join(downloads_dir, "cats-update.zip")

    if os.path.isdir(downloads_dir):
        print("DOWNLOAD FOLDER EXISTED")
        shutil.rmtree(downloads_dir)

    os.makedirs(downloads_dir, exist_ok=True)

    print('DOWNLOAD FILE')
    try:
        with requests.get(update_url, timeout=REQUEST_TIMEOUT, stream=True) as response:
            response.raise_for_status()
            with open(update_zip_file, 'wb') as zip_out:
                for chunk in response.iter_content(chunk_size=65536):
                    zip_out.write(chunk)
    except requests.RequestException as e:
        print("FILE COULD NOT BE DOWNLOADED:", e)
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.cantConnect'))
        return
    print('DOWNLOAD FINISHED')

    if not os.path.isfile(update_zip_file):
        print("ZIP NOT FOUND!")
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.cantFindZip'))
        return

    print('EXTRACTING ZIP')
    with zipfile.ZipFile(update_zip_file, "r") as zip_ref:
        zip_ref.extractall(downloads_dir)
    print('EXTRACTED')

    print('REMOVING ZIP FILE')
    os.remove(update_zip_file)

    print('SEARCHING FOR INIT 1')

    def searchInit(path):
        print('SEARCHING IN ' + path)
        files = os.listdir(path)
        if "__init__.py" in files:
            print('FOUND')
            return path
        folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
        if len(folders) != 1:
            print(len(folders), 'FOLDERS DETECTED')
            return None
        print('GOING DEEPER')
        return searchInit(os.path.join(path, folders[0]))

    print('SEARCHING FOR INIT 2')
    extracted_zip_dir = searchInit(downloads_dir)
    if not extracted_zip_dir:
        print("INIT NOT FOUND!")
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.cantFindCATS'))
        return

    repo_module = get_repo_module()
    if not repo_module:
        print("NOT INSTALLED AS AN EXTENSION")
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.notAnExtension'))
        return

    package_zip = os.path.join(downloads_dir, "cats-extension")
    shutil.make_archive(package_zip, 'zip', root_dir=extracted_zip_dir)
    package_zip += ".zip"

    try:
        bpy.ops.extensions.package_install_files('EXEC_DEFAULT',
                                                 filepath=package_zip,
                                                 repo=repo_module)
    except RuntimeError as e:
        print("INSTALL FAILED:", e)
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.installFailed'))
        return

    print('DELETE DOWNLOADS DIR')
    shutil.rmtree(downloads_dir)

    finish_update()


def finish_update(error=''):
    global update_finished, show_error
    show_error = error

    if not error:
        update_finished = True

    bpy.ops.cats_updater.update_complete_panel('INVOKE_DEFAULT')
    ui_refresh()
    print("UPDATE DONE!")


def set_ignored_version():
    with open(ignore_ver_file, 'w', encoding="utf8") as outfile:
        outfile.write(latest_version_str)

    global is_ignored_version
    is_ignored_version = True
    print('IGNORE VERSION ' + latest_version_str)


def check_ignored_version():
    if not os.path.isfile(ignore_ver_file):
        return False

    with open(ignore_ver_file, 'r', encoding="utf8") as outfile:
        version = outfile.read()

    if latest_version_str == version:
        print('Update ignored.')
        return True

    try:
        os.remove(ignore_ver_file)
    except OSError:
        print("FAILED TO REMOVE IGNORE VERSION FILE")

    return False


def get_version_list(self, context):
    choices = []
    if version_list:
        for version in version_list.keys():
            choices.append((version, version, version))

    return choices


def get_user_preferences():
    return bpy.context.preferences


def layout_split(layout, factor=0.0, align=False):
    return layout.split(factor=factor, align=align)


def draw_update_notification_panel(layout):
    if not update_needed or remind_me_later or is_ignored_version:
        return

    col = layout.column(align=True)

    if update_finished:
        col.separator()
        row = col.row(align=True)
        row.label(text=t('draw_update_notification_panel.success'), icon='ERROR')
        col.separator()
        return

    row = col.row(align=True)
    row.scale_y = 0.75
    row.label(text=t('draw_update_notification_panel.newUpdate', name=latest_version_str), icon='SOLO_ON')

    col.separator()
    row = col.row(align=True)
    row.scale_y = 1.3
    row.operator(UpdateToLatestButton.bl_idname, text=t('draw_update_notification_panel.UpdateToLatestButton.label'))

    row = col.row(align=True)
    row.scale_y = 1
    row.operator(RemindMeLaterButton.bl_idname, text=t('draw_update_notification_panel.RemindMeLaterButton.label'))
    row.operator(IgnoreThisVersionButton.bl_idname, text=t('draw_update_notification_panel.IgnoreThisVersionButton.label'))


def draw_updater_panel(context, layout, user_preferences=False):
    col = layout.column(align=True)

    scale_big = 2
    scale_small = 1.2

    row = col.row(align=True)
    row.scale_y = 0.8
    row.label(text=t('draw_updater_panel.updateLabel') if not user_preferences else t('draw_updater_panel.updateLabel_alt'), icon=ICON_URL)
    col.separator()

    if update_finished:
        col.separator()
        row = col.row(align=True)
        row.label(text=t('draw_updater_panel.success'), icon='ERROR')
        col.separator()
        return

    if show_error:
        row = col.row(align=True)
        row.label(text=show_error, icon='ERROR')
        col.separator()

    if is_checking_for_update:
        if not used_updater_panel:
            row = col.row(align=True)
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label'))
        else:
            split = col.row(align=True)
            row = split.row(align=True)
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label'))
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')

    elif update_needed:
        split = col.row(align=True)
        row = split.row(align=True)
        row.scale_y = scale_big
        row.operator(UpdateToLatestButton.bl_idname, text=t('draw_updater_panel.UpdateToLatestButton.label', name=latest_version_str))
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')

    elif not used_updater_panel or not version_list:
        row = col.row(align=True)
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label_alt'))

    else:
        split = col.row(align=True)
        row = split.row(align=True)
        row.scale_y = scale_big
        row.operator(UpdateToLatestButton.bl_idname, text=t('draw_updater_panel.UpdateToLatestButton.label_alt'))
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')


    col.separator()
    col.separator()
    split = col.row(align=True)
    row = layout_split(split, factor=0.55, align=True)
    row.scale_y = scale_small
    row.active = True if not is_checking_for_update and version_list else False
    row.operator(UpdateToSelectedButton.bl_idname, text=t('draw_updater_panel.UpdateToSelectedButton.label'))
    row.prop(context.scene, 'cats_updater_version_list', text='')
    row = split.row(align=True)
    row.scale_y = scale_small
    row.operator(ShowPatchnotesPanel.bl_idname, text="", icon='WORDWRAP_ON')


    row = col.row(align=True)
    row.scale_y = scale_small
    row.operator(UpdateToDevButton.bl_idname, text=t('draw_updater_panel.UpdateToDevButton.label'))

    col.separator()
    row = col.row(align=True)
    row.scale_y = 0.65
    row.label(text=t('draw_updater_panel.currentVersion', name=current_version_str))


class DemoPreferences(bpy.types.AddonPreferences):
    bl_idname = package_name

    def draw(self, context):
        layout = self.layout
        draw_updater_panel(context, layout, user_preferences=True)


to_register = [
    CheckForUpdateButton,
    UpdateToLatestButton,
    UpdateToSelectedButton,
    UpdateToDevButton,
    RemindMeLaterButton,
    IgnoreThisVersionButton,
    ShowPatchnotesPanel,
    ConfirmUpdatePanel,
    UpdateCompletePanel,
    UpdateNotificationPopup,
    DemoPreferences,
]


def register(dev_branch, version_str):
    global current_version, fake_update, current_version_str

    if not dev_branch:
        fake_update = False
    current_version_str = version_str

    current_version = []
    version_parts = CATS_VERSION.split(".")

    for part in version_parts:
        current_version.append(int(part))

    bpy.types.Scene.cats_updater_version_list = bpy.props.EnumProperty(
        name=t('bpy.types.Scene.cats_updater_version_list.label'),
        description=t('bpy.types.Scene.cats_updater_version_list.desc'),
        items=wrap_dynamic_enum_items(get_version_list, 'cats_updater_version_list', sort=False)
    )
    bpy.types.Scene.cats_update_action = bpy.props.EnumProperty(
        name=t('bpy.types.Scene.cats_update_action.label'),
        description=t('bpy.types.Scene.cats_update_action.desc'),
        items=[
            ("UPDATE", t('bpy.types.Scene.cats_update_action.update.label'), t('bpy.types.Scene.cats_update_action.update.desc')),
            ("IGNORE", t('bpy.types.Scene.cats_update_action.ignore.label'), t( 'bpy.types.Scene.cats_update_action.ignore.desc')),
            ("DEFER", t('bpy.types.Scene.cats_update_action.defer.label'), t( 'bpy.types.Scene.cats_update_action.defer.desc'))
        ]
    )

    count = 0
    for cls in to_register:
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError:
            pass
    if count < len(to_register):
        print('Skipped', len(to_register) - count, 'CATS updater classes.')


def unregister():
    for cls in reversed(to_register):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    if hasattr(bpy.types.Scene, 'cats_updater_version_list'):
        del bpy.types.Scene.cats_updater_version_list

    if hasattr(bpy.types.Scene, 'cats_update_action'):
        del bpy.types.Scene.cats_update_action
