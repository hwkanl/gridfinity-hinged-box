"""The workbench's commands, registered by InitGui.py. FreeCADGui and Qt
are imported inside functions: the package must import without the GUI."""
import os
import sys

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons")


def icon(name):
    return os.path.join(ICONS, f"{name}.svg")


def _no_dialog():
    import FreeCADGui
    return not FreeCADGui.Control.activeDialog()


def guarded(work):
    """Run work(); a ParamError, BuildError or ExportError goes to the
    Report view and a message box."""
    from hwkan_gfbox.export import ExportError
    from hwkan_gfbox.shapes import BuildError
    from hwkan_gfbox.sheet import ParamError
    try:
        work()
    except (ParamError, BuildError, ExportError) as e:
        print(f"error: {e}", file=sys.stderr)
        import FreeCADGui
        from PySide import QtWidgets
        QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Gridfinity Hinged Box", str(e))


def _new_box():
    from hwkan_gfbox import box_panel
    guarded(lambda: box_panel.show_panel())


def _generated_box():
    """True if export.gui_document finds a generated box (open under any name)."""
    from hwkan_gfbox import export
    from hwkan_gfbox.sheet import ParamError
    try:
        export.gui_document()
    except ParamError:
        return False
    return True


def _export_active():  # also an active edited box
    import FreeCAD as App
    from hwkan_gfbox import editable
    doc = App.ActiveDocument
    return _no_dialog() and ((doc is not None and editable.is_edited(doc)) or _generated_box())


def _edit_box():
    def work():
        import FreeCADGui
        from PySide import QtWidgets
        from hwkan_gfbox import editable, export
        from hwkan_gfbox.build import show
        doc = export.open_box()
        old = editable.unsaved_edit_document()
        if old is not None and QtWidgets.QMessageBox.question(
                FreeCADGui.getMainWindow(), "Edit box",
                f"Replace the open '{old.Label}' document (it is not saved; its edits are lost)?"
        ) != QtWidgets.QMessageBox.Yes:
            return
        out = editable.make_editable(doc)
        show(out)
        FreeCADGui.setActiveDocument(out.Name)
        print(f"made {out.Name}: one PartDesign body per STL, in print pose; add your features, "
              "save it under a name of your own, then Export STLs with it active")
    guarded(work)


def _export_stls():
    def work():
        import FreeCAD as App
        from hwkan_gfbox import editable, export, outdirs
        from hwkan_gfbox.sheet import SHEET_NAME, value
        active = App.ActiveDocument
        if active is not None and editable.is_edited(active):
            locks = int(editable.build_info(active)["parameters"]["lock_count"])  # ExportError if damaged
            write = lambda out: editable.export_edited(active, out)
        else:
            doc = export.open_box()  # check before asking for a folder
            locks = int(value(doc.getObject(SHEET_NAME), "lock_count"))
            write = lambda out: export.export(doc, list(export.PARTS), out)
        out = outdirs.ask(outdirs.EXPORT, "Export STLs to")
        if out is None:
            return
        try:
            paths = write(out)
        except OSError as e:
            raise export.ExportError(f"cannot write to {out}: {e}")
        for path in paths:
            print(f"wrote {path}")
        print(f"print latch.stl {locks} time{'s' if locks != 1 else ''} (one latch per lock)")
    guarded(work)


def _presets():
    from hwkan_gfbox import presets_dialog
    guarded(presets_dialog.run_dialog)


def _calibrate():
    from hwkan_gfbox import calibration_dialog
    guarded(calibration_dialog.run_dialog)


def _test_prints():
    from hwkan_gfbox import testprints_dialog
    guarded(testprints_dialog.ask_and_run)


# (command id, icon, menu text, tool tip, run, is active)
COMMAND_TABLE = [
    ("HwkanGfbox_NewBox", "new_box", "New box", "Build a new box from its size and a preset", _new_box, _no_dialog),
    ("HwkanGfbox_EditBox", "edit_box", "Edit box",
     "Copy the open box's printable parts into PartDesign bodies to add your own features, then Export STLs",
     _edit_box, lambda: _no_dialog() and _generated_box()),
    ("HwkanGfbox_ExportStls", "export_stls", "Export STLs",
     "Write the STLs of the edited box (if it is the active document) or of the generated box", _export_stls, _export_active),
    ("HwkanGfbox_Presets", "presets", "Presets", "Make, edit and delete presets (printer/material tolerances)",
     _presets, _no_dialog),
    ("HwkanGfbox_Calibrate", "calibrate", "Calibrate",
     "Guided test-print sweeps that fill a preset with your printer's tolerances", _calibrate, _no_dialog),
    ("HwkanGfbox_TestPrints", "test_prints", "Test prints",
     "Four small parts that test a preset: the hinge, its dovetail slot, the latch and its pad with the lid's lip",
     _test_prints, _no_dialog),
]
COMMANDS = [c[0] for c in COMMAND_TABLE]


class _Command:
    def __init__(self, icon_name, menu, tip, run, active):
        self.icon_name, self.menu, self.tip, self.run, self.active = icon_name, menu, tip, run, active

    def GetResources(self):
        return {"Pixmap": icon(self.icon_name), "MenuText": self.menu, "ToolTip": self.tip}

    def Activated(self):
        self.run()

    def IsActive(self):
        return self.active()


def register():
    import FreeCADGui
    for cmd_id, icon_name, menu, tip, run, active in COMMAND_TABLE:
        FreeCADGui.addCommand(cmd_id, _Command(icon_name, menu, tip, run, active))
