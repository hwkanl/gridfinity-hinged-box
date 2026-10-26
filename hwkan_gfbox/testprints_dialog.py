"""The GUI dialog of scripts/make_test_prints.py: which tolerance to sweep,
and its values. Qt and FreeCADGui are imported inside the function only
(the package must import without the GUI)."""
import os
import sys

from hwkan_gfbox import outdirs, testprints
from hwkan_gfbox.build import BuildError
from hwkan_gfbox.export import ExportError
from hwkan_gfbox.sheet import ParamError

NO_SWEEP = "none: one set at the current values"


def ask_and_run():
    """Ask for the sweep, then build and write the test prints with the open
    document's Params values and show them. Errors go to the Report view
    and into the dialog, which stays open. Returns 0 when written, 1 when
    cancelled."""
    import FreeCADGui
    from PySide import QtWidgets

    overrides, current = testprints.gui_inputs()
    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Test prints")
    form = QtWidgets.QFormLayout(dialog)
    choice = QtWidgets.QComboBox()
    choice.addItem(NO_SWEEP, None)
    for tol in testprints.SWEEPABLE:
        choice.addItem(tol, tol)
    values = QtWidgets.QLineEdit()
    folder = QtWidgets.QLineEdit(outdirs.last_dir(outdirs.TEST_PRINTS))
    browse = QtWidgets.QPushButton("Browse…")
    browse.setAutoDefault(False)
    folder_row = QtWidgets.QHBoxLayout()
    folder_row.addWidget(folder)
    folder_row.addWidget(browse)
    status = QtWidgets.QLabel("")
    status.setWordWrap(True)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    form.addRow("Sweep", choice)
    form.addRow("Values (mm)", values)
    form.addRow("Folder", folder_row)
    form.addRow(status)
    form.addRow(buttons)

    def picked():
        tol = choice.currentData()
        values.setEnabled(tol is not None)
        values.setText(testprints.default_sweep_values(
            current[tol], lambda val: testprints.valid_value(overrides, tol, val)) if tol else "")

    def pick_folder():
        path = outdirs.ask(outdirs.TEST_PRINTS, "Write test prints to", dialog)
        if path:
            folder.setText(path)

    written = []

    def accept():
        tol = choice.currentData()
        try:
            sweep = testprints.parse_sweep(f"{tol}={values.text()}") if tol else None
            out = os.path.expanduser(folder.text().strip())
            if not out:
                raise ParamError("choose a folder for the test prints")
            out = os.path.abspath(out)
            status.setText("Building ...")
            dialog.setEnabled(False)  # no input is handled mid-build
            status.repaint()
            try:
                os.makedirs(out, exist_ok=True)
                outdirs.remember(outdirs.TEST_PRINTS, out)
                paths, files, warnings = testprints.run(overrides, sweep, out)
            finally:
                dialog.setEnabled(True)
        except (ParamError, BuildError, ExportError, OSError) as e:
            status.setText(f"error: {e}")
            print(f"error: {e}", file=sys.stderr)
            return
        for warning in warnings:
            print(warning, file=sys.stderr)
        for path in paths:
            print(f"wrote {path}")
        testprints.show(files)
        written.extend(paths)
        dialog.accept()

    choice.currentIndexChanged.connect(lambda _: picked())
    browse.clicked.connect(pick_folder)
    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)
    picked()
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()
    return 0 if written else 1
