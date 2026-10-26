"""The Presets dialog, and the logic behind it (plain functions). Qt and
FreeCADGui are imported inside run_dialog only."""
import math
import os
import sys

from hwkan_gfbox import box_panel, presets
from hwkan_gfbox.params import PARAMS
from hwkan_gfbox.sheet import ParamError

DESCRIPTIONS = {name: doc for name, _, _, doc in PARAMS}


def edited(preset, texts, note=None):
    """A copy of preset with the values in texts ({name: "0.15"}, mm) and
    note (None: unchanged). Raises ParamError for a non-number."""
    values = dict(preset.values)
    for name, text in texts.items():
        text = text.strip()
        try:
            if "_" in text:
                raise ValueError(text)
            values[name] = float(text)
            if not math.isfinite(values[name]):
                raise ValueError(text)
        except ValueError:
            raise ParamError(f"{name}: '{text}' is not a number (mm)")
    return presets.Preset(preset.name, preset.ref, values, preset.note if note is None else note,
                          preset.calibration)


def save_checked(preset, base=None):
    """Check preset with the default inputs (as a build would), then write
    it to its file. Returns the path. Raises ParamError."""
    path = presets.resolve(preset.ref, base)
    if path is None:
        raise ParamError("the built-in default can't be changed: make a new preset from it")
    problem = box_panel.check(box_panel.defaults(), preset)
    if problem:
        raise ParamError(problem)
    presets.save(preset, path)
    return path


def delete(name, base=None):
    if name == presets.DEFAULT:
        raise ParamError("the built-in default can't be deleted")
    os.remove(presets.preset_path(name, base))


def run_dialog():
    import FreeCADGui
    from PySide import QtCore, QtGui, QtWidgets

    class _Dialog(QtWidgets.QDialog):
        def reject(self):  # Esc, the window's X and Close
            if discard_ok():
                super().reject()

    dialog = _Dialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Presets")
    dialog.resize(900, 480)
    outer = QtWidgets.QHBoxLayout(dialog)
    names = QtWidgets.QListWidget()
    outer.addWidget(names, 1)
    right = QtWidgets.QVBoxLayout()
    outer.addLayout(right, 3)
    note = QtWidgets.QLineEdit()
    table = QtWidgets.QTableWidget(len(presets.NAMES), 2)
    table.setHorizontalHeaderLabels(["value (mm)", "what it is"])
    table.setVerticalHeaderLabels(presets.NAMES)
    table.horizontalHeader().setStretchLastSection(True)
    status = QtWidgets.QLabel()
    status.setWordWrap(True)
    row = QtWidgets.QHBoxLayout()
    new_b, delete_b, folder_b, save_b, close_b = (
        QtWidgets.QPushButton(t) for t in ("New…", "Delete", "Open folder", "Save", "Close"))
    for b in (new_b, delete_b, folder_b, save_b, close_b):
        b.setAutoDefault(False)
        row.addWidget(b)
    right.addWidget(QtWidgets.QLabel("Note"))
    right.addWidget(note)
    right.addWidget(table)
    right.addWidget(status)
    right.addLayout(row)
    current = {}
    shown = {"name": None}

    def error(e):
        status.setText(f"error: {e}")
        print(f"error: {e}", file=sys.stderr)

    def selected():
        return names.currentItem().text() if names.currentItem() else presets.DEFAULT

    def texts():
        return {key: table.item(i, 0).text() for i, key in enumerate(presets.NAMES)}

    def changed():
        p = current.get("preset")
        if p is None or p.name == presets.DEFAULT:
            return False
        try:
            q = edited(p, texts(), note.text())
        except ParamError:
            return True
        return q.values != p.values or q.note != p.note

    def forget():
        current.pop("preset", None)
        shown["name"] = None

    def discard_ok():
        table.setCurrentCell(-1, -1)  # commit an open cell editor
        if not changed():
            return True
        name = current["preset"].name
        return QtWidgets.QMessageBox.question(
            dialog, "Presets", f"Discard unsaved changes to '{name}'?") == QtWidgets.QMessageBox.Yes

    def fill_names(select=presets.DEFAULT):
        names.blockSignals(True)
        try:
            names.clear()
            for n, _ in presets.list_presets():
                names.addItem(n)
        finally:
            names.blockSignals(False)
        found = names.findItems(select, QtCore.Qt.MatchExactly)
        names.setCurrentItem(found[0] if found else names.item(0))

    def show_selected():
        shown["name"] = selected()
        try:
            p = presets.load(shown["name"])
        except ParamError as e:
            current.pop("preset", None)
            note.setText("")
            note.setReadOnly(True)
            for i in range(len(presets.NAMES)):
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(""))
            save_b.setEnabled(False)
            delete_b.setEnabled(True)
            return error(e)
        current["preset"] = p
        read_only = p.name == presets.DEFAULT
        note.setText(p.note)
        note.setReadOnly(read_only)
        for i, key in enumerate(presets.NAMES):
            val = QtWidgets.QTableWidgetItem(repr(p.values[key]))
            desc = QtWidgets.QTableWidgetItem(DESCRIPTIONS[key])
            desc.setFlags(desc.flags() & ~QtCore.Qt.ItemIsEditable)
            if read_only:
                val.setFlags(val.flags() & ~QtCore.Qt.ItemIsEditable)
            table.setItem(i, 0, val)
            table.setItem(i, 1, desc)
        save_b.setEnabled(not read_only)
        delete_b.setEnabled(not read_only)
        status.setText("built-in, read-only: New… makes an editable copy" if read_only else "")

    def save():
        if "preset" not in current:
            return
        try:
            p = edited(current["preset"], texts(), note.text())
            path = save_checked(p)
        except ParamError as e:
            return error(e)
        current["preset"] = p  # what's on screen is saved now: no discard prompt
        status.setText(f"saved {path}")

    def switch(item, previous):
        if item is None or item.text() == shown["name"]:
            return
        if not discard_ok():
            # after the click is done: Qt selects the clicked item after this signal
            QtCore.QTimer.singleShot(0, select_shown)
            return
        show_selected()

    def select_shown():
        names.blockSignals(True)
        try:
            found = names.findItems(shown["name"], QtCore.Qt.MatchExactly)
            if found:
                names.setCurrentItem(found[0])
        finally:
            names.blockSignals(False)

    def new():
        if not discard_ok():
            return
        forget()
        source = selected()
        name, ok = QtWidgets.QInputDialog.getText(dialog, "New preset", f"Name (a copy of '{source}'):")
        if not ok:
            return show_selected()
        try:
            presets.new(name.strip(), source)
        except ParamError as e:
            show_selected()
            return error(e)
        fill_names(name.strip())

    def remove():
        name = selected()
        if QtWidgets.QMessageBox.question(dialog, "Presets", f"Delete preset '{name}'?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            delete(name)
        except (ParamError, OSError) as e:
            return error(e)
        forget()
        fill_names()

    def open_folder():
        folder = presets.preset_dir()
        os.makedirs(folder, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    names.currentItemChanged.connect(switch)
    save_b.clicked.connect(save)
    new_b.clicked.connect(new)
    delete_b.clicked.connect(remove)
    folder_b.clicked.connect(open_folder)
    close_b.clicked.connect(dialog.reject)
    try:
        fill_names()
    except ParamError as e:
        error(e)
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()
