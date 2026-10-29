"""Screenshots of the workbench for the user guide (README.md), taken in the
FreeCAD GUI: each panel and dialog is opened, saved as a PNG with
QWidget.grab() and closed again. Entry point: scripts/guide_screenshots.py.
Qt and FreeCADGui are imported inside the functions only (the package must
import without the GUI)."""
import os

# (file name, what it shows), in the order they're taken.
SHOTS = [
    ("toolbar.png", "the workbench's toolbar"),
    ("new_box.png", "the New box panel"),
    ("presets.png", "the Presets dialog, the shipped Tight preset selected"),
    ("test_prints.png", "the Test prints dialog"),
    ("calibrate.png", "the Calibrate dialog"),
]
WORKBENCH = "HwkanGfboxWorkbench"
TOOLBAR = "Gridfinity Hinged Box"
SETTLE_MS = 1500  # a dialog is grabbed this long after it opens
FOLDER = "Documents/hwkan_gfbox"  # shown in folder fields instead of this machine's paths
EXAMPLE_PRESET = "my-printer"  # typed into Calibrate's preset field
MIN_WIDTH = 420  # dialogs with a folder field are widened to this (px)


def _save(widget, path):
    if not widget.grab().save(path, "PNG"):
        raise OSError(f"could not write {path}")
    return path


def _grab_modal(path, before=None):
    """Grab the modal dialog that opens next (SETTLE_MS later), then close it.
    before(dialog) runs first (e.g. to select a list item); the grab
    waits another SETTLE_MS after it. Returns a list that gets the path."""
    from PySide import QtCore, QtWidgets
    written = []

    def grab():
        dialog = QtWidgets.QApplication.activeModalWidget()
        if dialog is None:
            return
        written.append(_save(dialog, path))
        dialog.done(0)  # not reject(): the Presets dialog's reject may ask about unsaved edits

    def start():
        dialog = QtWidgets.QApplication.activeModalWidget()
        if before is not None and dialog is not None:
            before(dialog)
            QtCore.QTimer.singleShot(SETTLE_MS, grab)
        else:
            grab()

    QtCore.QTimer.singleShot(SETTLE_MS, start)
    return written


def _select(name):
    """before() for the Presets dialog: select the preset name in its list."""
    def before(dialog):
        from PySide import QtCore, QtWidgets
        for names in dialog.findChildren(QtWidgets.QListWidget):
            found = names.findItems(name, QtCore.Qt.MatchExactly)
            if found:
                names.setCurrentItem(found[0])
    return before


def _neutral(preset=None):
    """before() for dialogs with a folder field: FOLDER in place of this
    machine's path; with preset, that name typed into the editable preset
    field (Calibrate)."""
    def before(dialog):
        from PySide import QtWidgets
        dialog.resize(max(dialog.width(), MIN_WIDTH), dialog.height())  # room for the whole folder
        for edit in dialog.findChildren(QtWidgets.QLineEdit):
            if os.sep in edit.text() or "/" in edit.text():
                edit.setText(FOLDER)
                edit.setCursorPosition(0)  # show the start, not the end
        if preset:
            for box in dialog.findChildren(QtWidgets.QComboBox):
                if box.isEditable():
                    box.setEditText(preset)
                    break
    return before


def _wait(ms):
    from PySide import QtCore
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


def take(out_dir):
    """Take every shot in SHOTS into out_dir; returns the paths written.
    Runs inside the GUI's event loop (call it from a timer), as the modal
    dialogs open their own loops."""
    import FreeCADGui
    from PySide import QtCore, QtWidgets

    from hwkan_gfbox import box_panel, calibration_dialog, presets_dialog, testprints_dialog

    os.makedirs(out_dir, exist_ok=True)
    path = {name: os.path.join(out_dir, name) for name, _ in SHOTS}
    written = []

    FreeCADGui.activateWorkbench(WORKBENCH)
    _wait(SETTLE_MS)
    bars = [b for b in FreeCADGui.getMainWindow().findChildren(QtWidgets.QToolBar) if b.windowTitle() == TOOLBAR]
    if not bars:
        raise RuntimeError(f"toolbar '{TOOLBAR}' not found")
    bar = bars[0]
    buttons = [w for w in bar.findChildren(QtWidgets.QToolButton) if w.isVisible() and w.parent() is bar]
    right = max(w.geometry().right() for w in buttons) + 4  # just past the last button
    bar.grab(QtCore.QRect(0, 0, right, bar.height())).save(path["toolbar.png"], "PNG")
    written.append(path["toolbar.png"])

    box_panel.show_panel()
    _wait(SETTLE_MS)
    panel = _task_form()
    if panel is not None:
        written.append(_save(panel, path["new_box.png"]))
    FreeCADGui.Control.closeDialog()

    for name, run, before in (("presets.png", presets_dialog.run_dialog, _select("Tight")),
                              ("test_prints.png", testprints_dialog.ask_and_run, _neutral()),
                              ("calibrate.png", calibration_dialog.run_dialog, _neutral(EXAMPLE_PRESET))):
        got = _grab_modal(path[name], before)
        run()
        written += got
    return written


def _task_form():
    """The New box panel's form in the task view (found by its title)."""
    import FreeCADGui
    from PySide import QtWidgets
    for widget in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
        if widget.windowTitle() == "New box" and widget.isVisible():
            return widget
    return None
