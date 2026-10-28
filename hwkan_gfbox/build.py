"""Build the Gridfinity box document from scratch.

Entry point: scripts/build_box.py
    headless: scripts/fc.sh scripts/build_box.py [--preset NAME|PATH]
              [--set NAME=VALUE ...] [--out PATH]   (default: build/box.FCStd)
    GUI:      execute scripts/build_box.py as a macro: builds the document and
              shows it; if a generated one is open, it is rebuilt with that
              document's inputs and the preset named in its Params sheet.

Entry point: scripts/edit_params.py (GUI only)
    execute it as a macro first: opens a document holding only the Params
    sheet (with the open generated document's values, if any) to edit at
    no recompute cost; then build_box.py builds the box from it.
"""
import os
import sys

import FreeCAD as App

from hwkan_gfbox import presets
from hwkan_gfbox.cli import parse_overrides
from hwkan_gfbox.parts import body, cosmetics, feet, halves, hinge, lock, stacking
from hwkan_gfbox.shapes import BuildError, cut, fuse
from hwkan_gfbox.sheet import (SHEET_NAME, ParamError, apply_overrides, create_params_sheet, preset_values,
                               set_preset, sheet_overrides, sheet_preset, sheet_source)
from hwkan_gfbox.validate import validate

# The project directory (parent of this package); default outputs go under build/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOC_NAME = "hwkan_gfbox"  # unique: a GUI rebuild closes the document with this name
DEFAULT_OUT = os.path.join(ROOT, "build", "box.FCStd")


def _build_geometry(doc):
    bottom_raw, lid_raw = halves.split(doc, body.build_box(doc))
    bottom_base = fuse(doc, "BottomBase", [bottom_raw, halves.build_rim_band(doc),
                                           halves.build_corner_pads(doc), halves.build_tongue(doc)])
    bottom_body = fuse(doc, "BottomBody", [bottom_base, hinge.build_hinge_ribs(doc), hinge.build_hinge_nubs(doc),
                                           lock.build_lock_pads(doc)])
    slots = fuse(doc, "Slots", [hinge.build_slots(doc), lock.build_lock_slots(doc)])
    finished = cosmetics.finish_bottom(doc, cut(doc, "BottomBare", bottom_body, slots))
    cut(doc, "Bottom", finished, stacking.build_grooves(doc))
    lid_body = fuse(doc, "LidBody", [lid_raw, halves.build_lid_rim(doc), feet.build_feet(doc),
                                     hinge.build_lid_knuckles(doc), lock.build_lock_lips(doc)])
    finished = cosmetics.finish_lid(doc, cut(doc, "LidBare", lid_body, halves.build_groove(doc)))
    fuse(doc, "Lid", [finished, stacking.build_notches(doc)])
    hinge.build_leaves(doc)
    lock.build_latch_bases(doc)
    lock.build_latch_levers(doc)
    lock.build_latch_hooks(doc)


def check_recompute(doc):
    """Raise BuildError naming every object that failed to recompute."""
    broken = [obj.Label for obj in doc.Objects if not obj.isValid()]
    if broken:
        raise BuildError("recompute failed for: " + ", ".join(broken))


def _apply(sheet, overrides, preset):
    """Apply the preset's values (if any), then overrides; name the preset in
    its cell. Returns the warnings."""
    warnings = apply_overrides(sheet, (presets.overrides(preset) if preset else []) + list(overrides))
    if preset:
        set_preset(sheet, preset.ref)
    return warnings


def build(overrides=(), doc_name=DOC_NAME, preset=None):
    """Build a fresh document.

    preset: a presets.Preset (its values first; None: the defaults, and the
    preset cell says "default"); overrides: (name, value) string pairs,
    applied after it, in order.
    Returns (doc, warnings). Raises ParamError for bad parameters and
    BuildError for recompute failures; a half-built document is closed.
    """
    doc = App.newDocument(doc_name)
    try:
        sheet = create_params_sheet(doc)
        warnings = _apply(sheet, overrides, preset)
        doc.recompute()
        validate(sheet)
        _build_geometry(doc)
        doc.recompute()
        check_recompute(doc)
    except Exception:
        App.closeDocument(doc.Name)
        raise
    return doc, warnings


def params_document(overrides=(), doc_name=DOC_NAME, preset=None, hidden=False):
    """A document holding only the parameter sheets, preset and overrides
    applied (as in build): edited without recomputing a box, then built by
    build_box.py; hidden: no 3D view in the GUI (for checks). Returns (doc,
    warnings). Raises ParamError for bad parameters."""
    doc = App.newDocument(doc_name, hidden=hidden)
    try:
        warnings = _apply(create_params_sheet(doc), overrides, preset)
        doc.recompute()
    except Exception:
        App.closeDocument(doc.Name)
        raise
    return doc, warnings


def sheet_settings(sheet, base=None):
    """What a rebuild of this document needs: (overrides, preset, warnings).
    overrides: its inputs (sheet_overrides). preset: the one its preset cell
    names, loaded from its file; if that file is gone (a document from
    another machine) or the cell is empty or missing (an older generator's
    document), the values stored in the document, under the same name.
    A preset that exists but is invalid raises ParamError; so does a missing
    one the cell was changed to (a mistyped name: not the preset the stored
    values came from)."""
    overrides, ref, source = sheet_overrides(sheet), sheet_preset(sheet), sheet_source(sheet)
    if ref:
        try:
            return overrides, presets.load(ref, base), []
        except presets.PresetNotFound as e:
            if source is not None and source != ref:
                raise presets.PresetNotFound(f"{e}; the box was built with preset '{source}': "
                                             "correct the preset cell")
            warning = f"warning: {e}; using the values stored in the document"
    else:
        warning = ("warning: the document names no preset; using the values stored in it "
                   "(set the preset cell to choose one)")
    stored = presets.Preset(ref or "", ref or "", {**presets.defaults(), **preset_values(sheet)})
    return overrides, stored, [warning]


BOX_LABELS = ("Bottom", "Lid", "Leaves", "LatchBase", "LatchLever", "LatchHook")


def box_document():
    """GUI: the generated box the commands work on: the active document if
    it is one (a Params sheet and every part; e.g. saved and reopened under
    another name), else the one named DOC_NAME; None if neither is open."""
    doc = App.ActiveDocument
    if (doc is not None and doc.getObject(SHEET_NAME) is not None
            and all(doc.getObjectsByLabel(label) for label in BOX_LABELS)):
        return doc
    return App.getDocument(DOC_NAME) if DOC_NAME in App.listDocuments() else None


def _open_settings(base=None):
    """GUI: sheet_settings of the open generated document, checked as
    build would (validate), and only then the document is closed; ([], the
    default preset, []) if none is open. A broken or rejected preset raises
    ParamError and leaves the open document alone."""
    box = box_document()
    if box is None:
        return [], presets.load(presets.DEFAULT), []
    overrides, preset, warnings = sheet_settings(box.getObject(SHEET_NAME), base)
    check = params_document(overrides, doc_name=DOC_NAME + "_check", preset=preset)[0]
    try:
        validate(check.getObject(SHEET_NAME))
    finally:
        App.closeDocument(check.Name)
    App.closeDocument(box.Name)
    return overrides, preset, warnings


def show(doc):
    """GUI only: isometric, zoom-to-fit view of doc. (A document created
    from a script does not become the GUI's active document, so its own
    3D view is looked up instead of using the active view.)"""
    import FreeCADGui
    for view in FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor"):
        view.viewIsometric()
        view.fitAll()


def main(args):
    if App.GuiUp:
        # Rebuild with the open document's inputs and preset (the cosmetics'
        # edges are chosen at build time, so a recompute can't follow a change).
        try:
            overrides, preset, warnings = _open_settings()
            doc, more = build(overrides, preset=preset)
        except (ParamError, BuildError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        for warning in warnings + more:
            print(warning, file=sys.stderr)
        show(doc)
        return 0
    try:
        overrides, preset, rest = parse_overrides(args)
        out = DEFAULT_OUT
        if len(rest) == 2 and rest[0] == "--out":
            out = rest[1]
        elif rest:
            raise ParamError(f"unexpected arguments: {' '.join(rest)}")
        doc, warnings = build(overrides, preset=preset)
    except (ParamError, BuildError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(warning, file=sys.stderr)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc.saveAs(out)
    print(f"wrote {out}")
    return 0


def edit_params_main(args):
    """GUI: replace the open generated document (if any) by one holding only
    the sheets, with its inputs and preset, and open the Params sheet for editing."""
    if not App.GuiUp:
        print("error: edit_params.py is for the FreeCAD GUI; headless, pass "
              "--preset NAME and --set NAME=VALUE to build_box.py or make_stls.py", file=sys.stderr)
        return 2
    import FreeCADGui
    try:
        overrides, preset, warnings = _open_settings()
        doc, more = params_document(overrides, preset=preset)
    except ParamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for warning in warnings + more:
        print(warning, file=sys.stderr)
    FreeCADGui.getDocument(doc.Name).setEdit(doc.getObject(SHEET_NAME))
    return 0
