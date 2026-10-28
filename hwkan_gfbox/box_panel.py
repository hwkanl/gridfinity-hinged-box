"""The New box task panel. Its logic (defaults, check, replace_box) is
plain functions; Qt and FreeCADGui are imported inside the panel only."""
import sys

import FreeCAD as App

from hwkan_gfbox import presets
from hwkan_gfbox.build import DOC_NAME, box_document, build, params_document, show
from hwkan_gfbox.params import INPUT, PARAMS
from hwkan_gfbox.shapes import BuildError
from hwkan_gfbox.sheet import SHEET_NAME, ParamError
from hwkan_gfbox.validate import validate

# (name, default, description) of each input, in PARAMS order
INPUTS = [(name, int(default), doc) for name, default, tier, doc in PARAMS if tier == INPUT]
LABELS = {"gf_x": "Width (cells)", "gf_y": "Depth (cells)", "gf_z_units": "Height (7 mm units)",
          "hinge_count": "Hinges", "lock_count": "Locks"}


def defaults():
    return {name: default for name, default, _ in INPUTS}


def overrides(inputs):
    """inputs {name: int} as the (name, value) pairs build() takes."""
    return [(name, str(inputs[name])) for name, _, _ in INPUTS]

CHECK_DOC = DOC_NAME + "_check"


def initial(base=None):
    """(inputs {name: int}, preset) the panel starts with: the defaults and
    the default preset."""
    return defaults(), presets.load(presets.DEFAULT, base)


def check(inputs, preset):
    """'' if the generator accepts inputs with preset, else the problems
    (validate's message). Builds only the sheets, in a hidden document
    that is closed again."""
    active = App.ActiveDocument
    doc = None
    try:
        doc = params_document(overrides(inputs), doc_name=CHECK_DOC, preset=preset, hidden=True)[0]
        validate(doc.getObject(SHEET_NAME))
        return ""
    except ParamError as e:
        return str(e)
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)
        if active is not None and active.Name in App.listDocuments():
            App.setActiveDocument(active.Name)


def replace_box(inputs, preset):
    """Replace the open box (if any) by one built from inputs and preset,
    as build_box.py does in the GUI. Returns (doc, warnings). Raises
    ParamError / BuildError; the open box is gone then too."""
    box = box_document()
    if box is not None:
        App.closeDocument(box.Name)
    return build(overrides(inputs), preset=preset)


class _Panel:
    """A FreeCAD task panel: FreeCADGui.Control shows self.form and calls
    accept / reject."""

    def __init__(self):
        from PySide import QtCore, QtWidgets
        inputs, self.preset = initial()
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("New box")
        layout = QtWidgets.QFormLayout(self.form)
        self.spins = {}
        for name, _, doc in INPUTS:
            spin = QtWidgets.QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(inputs[name])
            spin.setToolTip(doc)
            layout.addRow(LABELS[name], spin)
            self.spins[name] = spin
        self.presets = QtWidgets.QComboBox()
        names = [n for n, _ in presets.list_presets()]
        for n in names:
            self.presets.addItem(n, None if n == self.preset.name else n)
        self.presets.setCurrentIndex(max(0, self.presets.findData(None)))
        layout.addRow("Preset", self.presets)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        layout.addRow(self.message)
        self.note = "A box is open: OK replaces it." if box_document() is not None else ""
        self.timer = QtCore.QTimer(self.form)  # check 0.3 s after the last change, not on every click
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.recheck)
        for spin in self.spins.values():
            spin.valueChanged.connect(lambda _: self.timer.start())
        self.presets.currentIndexChanged.connect(lambda _: self.timer.start())
        self.recheck()

    def inputs(self):
        return {name: spin.value() for name, spin in self.spins.items()}

    def chosen(self):
        """The preset picked: the one loaded at start (data None), else by name."""
        name = self.presets.currentData()
        return self.preset if name is None else presets.load(name)

    def recheck(self):
        """Show the problems with the current values (none: the note, if any)."""
        try:
            problem = check(self.inputs(), self.chosen())
        except ParamError as e:  # the picked preset's file is broken
            problem = str(e)
        self.message.setText(problem or self.note)
        return problem

    def accept(self):
        import FreeCADGui
        self.timer.stop()
        if self.recheck():
            return False  # the panel stays open with the problem shown
        try:
            doc, warnings = replace_box(self.inputs(), self.chosen())
        except (ParamError, BuildError) as e:
            self.message.setText(f"error: {e}")
            print(f"error: {e}", file=sys.stderr)
            return False
        for warning in warnings:
            print(warning, file=sys.stderr)
        FreeCADGui.Control.closeDialog()
        show(doc)
        return True

    def reject(self):
        import FreeCADGui
        self.timer.stop()
        FreeCADGui.Control.closeDialog()
        return True


def show_panel():
    import FreeCADGui
    FreeCADGui.Control.showDialog(_Panel())
