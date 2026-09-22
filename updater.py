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
# These survive add-on updates, so they live outside the extension directory
downloads_dir = globs.user_data_path("downloads")
ignore_ver_file = globs.user_data_path("ignore_version.txt")
no_auto_ver_check_file = globs.user_data_path("no_auto_ver_check.txt")

# Package name of this add-on, used as the AddonPreferences bl_idname
package_name = __package__

# Icons for UI
ICON_URL = 'URL'

RELEASES_API_URL = 'https://git.disroot.org/api/v1/repos/Neoneko/Cats-Blender-Plugin/releases'
REQUEST_TIMEOUT = 15

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
        # Important for changing options
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
        # Important for changing options
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
        # col.separator()
        row = col.row(align=True)
        row.scale_y = 0.65
        # row.label(text='Update now to ' + version_str + ':', icon=ICON_URL)
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
        # Important for changing options
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
            # Remind later aka defer
            global remind_me_later
            remind_me_later = True
        ui_refresh()
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.6))

    # def invoke(self, context, event):
    #     return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        # Important for changing options
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
    global is_checking_for_update, checked_on_startup
    if check_on_startup and checked_on_startup:
        # print('ALREADY CHECKED ON STARTUP')
        return
    if is_checking_for_update:
        # print('ALREADY CHECKING')
        return

    checked_on_startup = True

    if check_on_startup and os.path.isfile(no_auto_ver_check_file):
        print('AUTO CHECK DISABLED VIA FILE')
        return

    is_checking_for_update = True

    thread = Thread(target=check_for_update, args=[])
    thread.start()


def check_for_update():
    print('Checking for Cats update...')

    # Get all releases from Github
    if not get_github_releases('teamneoneko'):
        finish_update_checking(error=t('check_for_update.cantCheck'))
        return

    # Check if an update is needed
    global update_needed, is_ignored_version
    update_needed = check_for_update_available()
    is_ignored_version = check_ignored_version()

    # Update needed, show the notification popup if it wasn't checked through the UI
    if update_needed:
        print('Update found!')
        if not used_updater_panel and not is_ignored_version:
            prepare_to_show_update_notification()
    else:
        print('No update found.')

    # Finish update checking, update the UI
    finish_update_checking()


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
    
    # Determine tag prefix based on Blender version
    tag_prefix = ""
    if bpy.app.version >= (5, 0) and bpy.app.version < (5, 1):
        tag_prefix = "5.0."

    for version in data:
        full_tag = version.get('tag_name')
        
        # If we have a tag prefix, skip versions that don't match
        if tag_prefix and not full_tag.startswith(tag_prefix):
            continue   
            
        version_tag = full_tag
        
        # Remove prefix if present
        if tag_prefix and version_tag.startswith(tag_prefix):
            version_tag = version_tag[len(tag_prefix):]
        
        # Normalize version_tag 
        version_tag = version_tag.replace('-', '.')
        if version_tag.startswith('v.'):
            version_tag = version_tag[2:]
        if version_tag.startswith('v'):
            version_tag = version_tag[1:]
        
        # Key on the normalized tag: check_for_update_available parses it as numbers
        version_list[version_tag] = [
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

    # Only show error if the update panel was used before
    if used_updater_panel:
        show_error = error

    ui_refresh()


def _tag_areas_for_redraw():
    for window_manager in bpy.data.window_managers:
        for window in window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    return None


def ui_refresh():
    # tag_redraw touches window data, so it has to run on the main thread.
    # bpy.app.timers.register is the one bpy call that is safe from a worker thread.
    bpy.app.timers.register(_tag_areas_for_redraw)


def prepare_to_show_update_notification():
    # Called from the update-check thread. bpy.app.timers.register is safe to call
    # from any thread and runs the callback on the main thread, which is the only
    # place a popup operator can be invoked from.
    bpy.app.timers.register(show_update_notification, first_interval=0.1)


def show_update_notification():
    atr = UpdateNotificationPopup.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
    return None


def update_now(version=None, latest=False, dev=False):
    if fake_update:
        finish_update()
        return
    if dev:
        print('UPDATE TO DEVELOPMENT')
        # Dynamically construct dev branch URL based on major version
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
    # Load all the directories and files
    update_zip_file = os.path.join(downloads_dir, "cats-update.zip")

    # Remove existing download folder
    if os.path.isdir(downloads_dir):
        print("DOWNLOAD FOLDER EXISTED")
        shutil.rmtree(downloads_dir)

    # Create download folder
    os.makedirs(downloads_dir, exist_ok=True)

    # Download zip
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

    # If zip is not downloaded, abort
    if not os.path.isfile(update_zip_file):
        print("ZIP NOT FOUND!")
        shutil.rmtree(downloads_dir)
        finish_update(error=t('download_file.cantFindZip'))
        return

    # Extract the downloaded zip
    print('EXTRACTING ZIP')
    with zipfile.ZipFile(update_zip_file, "r") as zip_ref:
        zip_ref.extractall(downloads_dir)
    print('EXTRACTED')

    # Delete the extracted zip file
    print('REMOVING ZIP FILE')
    os.remove(update_zip_file)

    # Detect the extracted folders and files
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
        # finish_reloading()
        finish_update(error=t('download_file.cantFindCATS'))
        return

    # Remove old addon files
    clean_addon_dir()

    # Move the extracted files to their correct places
    def move_files(from_dir, to_dir):
        print('MOVE FILES TO DIR:', to_dir)
        files = os.listdir(from_dir)
        for file in files:
            file_dir = os.path.join(from_dir, file)
            target_dir = os.path.join(to_dir, file)
            print('MOVE', file_dir)

            # If file exists
            if os.path.isfile(file_dir) and os.path.isfile(target_dir):
                os.remove(target_dir)
                shutil.move(file_dir, to_dir)
                print('REMOVED AND MOVED', file)

            elif os.path.isdir(file_dir) and os.path.isdir(target_dir):
                move_files(file_dir, target_dir)

            else:
                shutil.move(file_dir, to_dir)
                print('MOVED', file)

    move_files(extracted_zip_dir, main_dir)

    # Delete download folder
    print('DELETE DOWNLOADS DIR')
    shutil.rmtree(downloads_dir)

    # Finish the update
    finish_update()


def finish_update(error=''):
    global update_finished, show_error
    show_error = error

    if not error:
        update_finished = True

    bpy.ops.cats_updater.update_complete_panel('INVOKE_DEFAULT')
    ui_refresh()
    print("UPDATE DONE!")


def clean_addon_dir():
    print("CLEAN ADDON FOLDER")

    # first remove root files and folders (except update folder, important folders and resource folder)
    files = [f for f in os.listdir(main_dir) if os.path.isfile(os.path.join(main_dir, f))]
    folders = [f for f in os.listdir(main_dir) if os.path.isdir(os.path.join(main_dir, f))]

    for f in files:
        file = os.path.join(main_dir, f)
        try:
            os.remove(file)
            print("Clean removing file {}".format(file))
        except OSError:
            print("Failed to pre-remove file " + file)

    for f in folders:
        folder = os.path.join(main_dir, f)
        if f.startswith('.') or f == 'resources' or f == 'downloads':
            continue

        try:
            shutil.rmtree(folder)
            print("Clean removing folder and contents {}".format(folder))
        except OSError:
            print("Failed to pre-remove folder " + folder)

    # then remove the bundled resource files and folders. Settings and the google
    # dictionary are no longer in here, they live under the user data directory.
    resources_folder = os.path.join(main_dir, 'resources')
    files = [f for f in os.listdir(resources_folder) if os.path.isfile(os.path.join(resources_folder, f))]
    folders = [f for f in os.listdir(resources_folder) if os.path.isdir(os.path.join(resources_folder, f))]

    for f in files:
        file = os.path.join(resources_folder, f)
        try:
            os.remove(file)
            print("Clean removing file {}".format(file))
        except OSError:
            print("Failed to pre-remove " + file)

    for f in folders:
        folder = os.path.join(resources_folder, f)
        try:
            shutil.rmtree(folder)
            print("Clean removing folder and contents {}".format(folder))
        except OSError:
            print("Failed to pre-remove folder " + folder)


def set_ignored_version():
    # Create ignore file, user_data_path() already made the folder
    with open(ignore_ver_file, 'w', encoding="utf8") as outfile:
        outfile.write(latest_version_str)

    # Set ignored status
    global is_ignored_version
    is_ignored_version = True
    print('IGNORE VERSION ' + latest_version_str)


def check_ignored_version():
    if not os.path.isfile(ignore_ver_file):
        # print('IGNORE FILE NOT FOUND')
        return False

    # Read ignore file
    with open(ignore_ver_file, 'r', encoding="utf8") as outfile:
        version = outfile.read()

    # Check if the latest version matches the one in the ignore file
    if latest_version_str == version:
        print('Update ignored.')
        return True

    # Delete ignore version file if the latest version is not the version in the file
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
        # pass
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

    # col.separator()
    # col.separator()
    # col.separator()
    # row = layout_split(col, factor=0.6, align=True)
    # row.scale_y = 0.9
    # row.active = True if not is_checking_for_update and version_list else False
    # row.label(text="Select Version:")
    # row.prop(context.scene, 'cats_updater_version_list', text='')
    #
    # row = layout_split(col, factor=0.6, align=True)
    # row.scale_y = scale_small
    # row.operator(UpdateToSelectedButton.bl_idname, text='Install Selected Version')
    # row.operator(ShowPatchnotesPanel.bl_idname, text='Show Patchnotes')

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

    # topsplit = layout_split(col, factor=0.55, align=True)
    #
    # split = topsplit.row(align=True)
    # row = split.row(align=True)
    # row.scale_y = scale_small
    # row.active = True if not is_checking_for_update and version_list else False
    # row.operator(UpdateToSelectedButton.bl_idname, text='Install Version:')
    #
    # row = split.row(align=True)
    # row.alignment = 'RIGHT'
    # row.scale_y = scale_small
    # row.operator(ShowPatchnotesPanel.bl_idname, text="", icon='WORDWRAP_ON')
    #
    # row = topsplit.row(align=True)
    # row.scale_y = scale_small
    # row.prop(context.scene, 'cats_updater_version_list', text='')

    row = col.row(align=True)
    row.scale_y = scale_small
    row.operator(UpdateToDevButton.bl_idname, text=t('draw_updater_panel.UpdateToDevButton.label'))

    col.separator()
    row = col.row(align=True)
    row.scale_y = 0.65
    row.label(text=t('draw_updater_panel.currentVersion', name=current_version_str))


# demo bare-bones preferences
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
    # print('REGISTER CATS UPDATER')
    global current_version, fake_update, current_version_str

    # If not dev branch, always disable fake update!
    if not dev_branch:
        fake_update = False
    current_version_str = version_str

    # Get current version
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

    # Register all Updater classes
    count = 0
    for cls in to_register:
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError:
            pass
    # print('Registered', count, 'CATS updater classes.')
    if count < len(to_register):
        print('Skipped', len(to_register) - count, 'CATS updater classes.')


def unregister():
    # Unregister all Updater classes
    for cls in reversed(to_register):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    if hasattr(bpy.types.Scene, 'cats_updater_version_list'):
        del bpy.types.Scene.cats_updater_version_list

    if hasattr(bpy.types.Scene, 'cats_update_action'):
        del bpy.types.Scene.cats_update_action
