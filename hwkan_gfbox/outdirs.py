"""The output folders the GUI commands ask for: each starts at the last
one used for that command, kept in FreeCAD's parameter store. (The
scripts keep their build/ defaults.)"""
import os

import FreeCAD as App

GROUP = "User parameter:BaseApp/Preferences/Mod/hwkan_gfbox"
EXPORT, TEST_PRINTS, CALIBRATION = "LastExportDir", "LastTestPrintDir", "LastCalibrationDir"


def default_dir():
    """~/hwkan_gfbox; on Windows Documents/hwkan_gfbox."""
    home = os.path.expanduser("~")
    if os.name == "nt":
        home = os.path.join(home, "Documents")
    return os.path.join(home, "hwkan_gfbox")


def last_dir(key, group=GROUP):
    return App.ParamGet(group).GetString(key, "") or default_dir()


def remember(key, path, group=GROUP):
    App.ParamGet(group).SetString(key, os.path.abspath(path))


def ask(key, title, parent=None):
    """GUI: a folder picker starting at last_dir(key) (its parent folders
    while it doesn't exist). Returns the chosen folder, remembered, or None
    if cancelled."""
    from PySide import QtWidgets
    import FreeCADGui
    if not App.ParamGet(GROUP).GetString(key, ""):
        os.makedirs(default_dir(), exist_ok=True)
    start = last_dir(key)
    while not os.path.isdir(start) and os.path.dirname(start) != start:
        start = os.path.dirname(start)
    path = QtWidgets.QFileDialog.getExistingDirectory(parent or FreeCADGui.getMainWindow(), title, start)
    if not path:
        return None
    remember(key, path)
    return os.path.abspath(path)
