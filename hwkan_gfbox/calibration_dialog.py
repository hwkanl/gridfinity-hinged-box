"""The Calibrate dialog: the calibration suite (calibration.py) run with
buttons instead of scripts/calibrate.py. Qt and FreeCADGui are imported
inside run_dialog only."""
import os
import sys
import traceback

from hwkan_gfbox import calibration as cal
from hwkan_gfbox import outdirs, presets
from hwkan_gfbox.shapes import BuildError
from hwkan_gfbox.sheet import ParamError


def run_dialog():
    import FreeCADGui
    from PySide import QtCore, QtWidgets

    busy = {"on": False}

    class _Dialog(QtWidgets.QDialog):
        def reject(self):  # Esc, the window's X and Close: not while a sweep is built
            if not busy["on"]:
                super().reject()

    dialog = _Dialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Calibrate")
    dialog.resize(680, 560)
    form = QtWidgets.QFormLayout(dialog)
    all_names = [n for n, _ in presets.list_presets()]
    name = QtWidgets.QComboBox()
    name.setEditable(True)
    name.addItems([n for n in all_names if not presets.read_only(n)])
    source = QtWidgets.QComboBox()
    source.addItems(all_names)
    tests = QtWidgets.QLineEdit(cal.DEFAULT_TESTS)
    folder = QtWidgets.QLineEdit(outdirs.last_dir(outdirs.CALIBRATION))
    browse = QtWidgets.QPushButton("Browse…")
    folder_row = QtWidgets.QHBoxLayout()
    folder_row.addWidget(folder)
    folder_row.addWidget(browse)
    start_b = QtWidgets.QPushButton("Start run")
    write_b = QtWidgets.QPushButton("Write pending sweep")
    run_row = QtWidgets.QHBoxLayout()
    run_row.addWidget(start_b)
    run_row.addWidget(write_b)
    status = QtWidgets.QPlainTextEdit()
    status.setReadOnly(True)
    answers = QtWidgets.QHBoxLayout()
    close_b = QtWidgets.QPushButton("Close")
    for b in (browse, start_b, write_b, close_b):
        b.setAutoDefault(False)
    form.addRow("Preset", name)
    form.addRow("New preset: copy from", source)
    form.addRow("Tests", tests)
    form.addRow("Folder", folder_row)
    form.addRow(run_row)
    form.addRow(status)
    form.addRow("Answer", answers)
    form.addRow(close_b)

    def current():
        """(preset, path, created) for the typed name (a new one is copied
        from source, written on Start)."""
        n = name.currentText().strip()
        if not n:
            raise ParamError("type a preset name")
        try:
            presets.load(n)
            src = None
        except presets.PresetNotFound:
            src = source.currentText()
        preset, path, created = cal.open_preset(n, src, None)
        if path is None:
            raise ParamError("the built-in default can't hold a calibration run: type a new preset name")
        return preset, path, created

    def folder_path():
        f = os.path.expanduser(folder.text().strip())
        if not f:
            raise ParamError("choose a folder for the sweeps")
        return os.path.abspath(f)

    def out_dir(preset):
        return os.path.join(folder_path(), preset.name)

    def clear_answers():
        while answers.count():
            answers.takeAt(0).widget().deleteLater()

    def refresh(preset):
        clear_answers()
        status.setPlainText(cal.status_text(preset, out_dir(preset), gui=True))
        s = cal.state(preset)
        write_b.setEnabled(bool(s) and not s["written"])
        if not s or not s["written"]:
            return
        test = cal.TESTS[s["current"]]
        for text in [f"{test.letter}{n}" for n in s["sweep"]] + [test.tight, test.loose]:
            b = QtWidgets.QPushButton(text)
            b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, t=text: guarded(lambda: on_answer(t)))
            answers.addWidget(b)

    def guarded(work):
        try:
            work()
        except (ParamError, BuildError, OSError) as e:
            status.appendPlainText(f"error: {e}")
            print(f"error: {e}", file=sys.stderr)
        except Exception as e:  # last resort: show it, keep the dialog open
            status.appendPlainText(f"error: {e!r}")
            traceback.print_exc()

    def write(preset, path):
        status.setPlainText("Building the sweep …")
        busy["on"] = True
        dialog.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        status.repaint()  # no event processing: no input is handled mid-build
        try:
            out = out_dir(preset)
            outdirs.remember(outdirs.CALIBRATION, folder_path())
            for p in cal.write_pending(preset, path, out):
                print(f"wrote {p}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            dialog.setEnabled(True)
            busy["on"] = False

    def on_name():
        n = name.currentText().strip()
        source.setEnabled(n not in all_names)
        clear_answers()
        write_b.setEnabled(False)
        if not n:
            return status.setPlainText("")
        preset, _, created = current()
        if created:
            return status.setPlainText(f"new preset '{n}': Start run makes it as a copy of the preset chosen below")
        refresh(preset)

    def on_start():
        preset, path, created = current()
        wanted = cal.parse_tests(tests.text().strip())
        try:
            running = cal.state(preset)
        except ParamError:  # a malformed run: replacing it is the fix
            running = True
        if running and not created and QtWidgets.QMessageBox.question(
                dialog, "Calibrate", f"A run is in progress for '{preset.name}'. Replace it?") != QtWidgets.QMessageBox.Yes:
            return
        cal.start(preset, wanted, cal.validator(preset))
        try:
            write(preset, path)
        finally:
            if created and os.path.exists(path) and preset.name not in all_names:
                all_names.append(preset.name)
                name.blockSignals(True)
                name.addItem(preset.name)
                name.blockSignals(False)
                source.setEnabled(False)
            refresh(preset)

    def on_write():
        preset, path, _ = current()
        try:
            write(preset, path)
        finally:
            refresh(preset)

    def on_answer(text):
        preset, path, _ = current()
        cal.answer(preset, text, cal.validator(preset))
        if cal.state(preset) is None:
            presets.save(preset, path)
            clear_answers()
            return status.setPlainText(cal.finished_text(preset, gui=True))
        try:
            write(preset, path)
        finally:
            refresh(preset)

    def on_browse():
        path = outdirs.ask(outdirs.CALIBRATION, "Write calibration sweeps to", dialog)
        if path:
            folder.setText(path)
            guarded(on_name)

    name.editTextChanged.connect(lambda _: guarded(on_name))
    start_b.clicked.connect(lambda: guarded(on_start))
    write_b.clicked.connect(lambda: guarded(on_write))
    browse.clicked.connect(on_browse)
    close_b.clicked.connect(dialog.reject)
    guarded(on_name)
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()
