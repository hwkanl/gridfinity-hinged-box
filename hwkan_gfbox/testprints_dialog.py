"""The GUI dialog of the Test prints command: which preset to test, and the
folder. Qt and FreeCADGui are imported inside the function only (the
package must import without the GUI)."""
import os
import sys

from hwkan_gfbox import outdirs, presets, testprints
from hwkan_gfbox.build import BuildError
from hwkan_gfbox.export import ExportError
from hwkan_gfbox.sheet import ParamError


def ask_and_run():
    """Ask for the preset and the folder, then build and write the preset's
    test prints and show them. Errors go to the Report view and into the
    dialog, which stays open. Returns 0 when written, 1 when cancelled."""
    import FreeCADGui
    from PySide import QtCore, QtWidgets

    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Test prints")
    form = QtWidgets.QFormLayout(dialog)
    choice = QtWidgets.QComboBox()
    for name, note in presets.list_presets():
        choice.addItem(name)
        choice.setItemData(choice.count() - 1, note, QtCore.Qt.ToolTipRole)
    choice.setCurrentIndex(max(0, choice.findText(testprints.gui_preset())))
    folder = QtWidgets.QLineEdit(outdirs.last_dir(outdirs.TEST_PRINTS))
    browse = QtWidgets.QPushButton("Browse…")
    browse.setAutoDefault(False)
    folder_row = QtWidgets.QHBoxLayout()
    folder_row.addWidget(folder)
    folder_row.addWidget(browse)
    status = QtWidgets.QLabel(", ".join(f"{name}.stl" for name in testprints.TEST_SET))
    status.setWordWrap(True)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    form.addRow("Preset", choice)
    form.addRow("Folder", folder_row)
    form.addRow(status)
    form.addRow(buttons)

    def pick_folder():
        path = outdirs.ask(outdirs.TEST_PRINTS, "Write test prints to", dialog)
        if path:
            folder.setText(path)

    written = []

    def accept():
        try:
            preset = presets.load(choice.currentText())
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
                paths, files, warnings = testprints.run(preset, out)
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

    browse.clicked.connect(pick_folder)
    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)
    dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()
    return 0 if written else 1
