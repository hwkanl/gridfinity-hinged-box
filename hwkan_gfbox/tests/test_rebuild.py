"""A GUI rebuild keeps the user's inputs and reloads the preset named in the
document (the GUI macro rebuilds instead of recomputing: the cosmetics'
edges are chosen at build time). Spec:
docs/superpowers/specs/2026-10-12-presets-design.md."""
import json
import os
import shutil
import tempfile

import FreeCAD as App

from hwkan_gfbox import presets
from hwkan_gfbox.build import DOC_NAME, _open_settings, params_document, sheet_settings
from hwkan_gfbox.sheet import ParamError, set_preset, sheet_preset, sheet_source, value


def _base_with(name, values):
    base = tempfile.mkdtemp(prefix="rebuild_test")
    os.makedirs(presets.preset_dir(base))
    with open(os.path.join(presets.preset_dir(base), name + ".json"), "w") as f:
        json.dump({"format": 1, "values": values}, f)
    return base


def _type(sheet, name, text):
    """A value typed into a cell in the GUI."""
    cell = sheet.getCellFromAlias(name)
    sheet.set(cell, text)
    sheet.Document.recompute()


def test_rebuild_keeps_inputs_and_reloads_the_preset():
    base = _base_with("petg", {"hinge_clearance": 0.15})
    docs = []
    try:
        doc = params_document([("gf_x", "4")], doc_name="rebuild_src", preset=presets.load("petg", base))[0]
        docs.append(doc)
        sheet = doc.getObject("Params")
        _type(sheet, "gf_y", "3")
        _type(doc.getObject("Preset"), "hinge_clearance", "=0.3 mm")  # edited in the sheet: overwritten by the preset
        overrides, preset, warnings = sheet_settings(sheet, base)
        assert overrides == [("gf_x", "4"), ("gf_y", "3")], overrides
        assert (preset.name, preset.values["hinge_clearance"], warnings) == ("petg", 0.15, [])
        again = params_document(overrides, doc_name="rebuild_dst", preset=preset)[0]
        docs.append(again)
        s = again.getObject("Params")
        assert value(s, "gf_y") == 3 and value(s, "hinge_clearance") == 0.15 and sheet_preset(s) == "petg"
    finally:
        for d in docs:
            App.closeDocument(d.Name)
        shutil.rmtree(base)


def test_a_missing_preset_falls_back_to_the_stored_values():
    gone = presets.Preset("gone", "gone", dict(presets.defaults(), hinge_clearance=0.15))
    doc = params_document(doc_name="rebuild_gone", preset=gone)[0]
    empty = tempfile.mkdtemp(prefix="rebuild_test")
    try:
        overrides, preset, warnings = sheet_settings(doc.getObject("Params"), empty)
        assert preset.ref == "gone" and preset.values == gone.values
        assert len(warnings) == 1 and "gone" in warnings[0] and "stored in the document" in warnings[0], warnings
    finally:
        App.closeDocument(doc.Name)
        shutil.rmtree(empty)


def test_a_mistyped_preset_name_is_an_error():
    """The preset cell changed to a name that doesn't exist (not the preset
    the values came from): an error, not the previous values."""
    base = _base_with("petg", {"hinge_clearance": 0.15})
    doc = params_document(doc_name="rebuild_typo", preset=presets.load("petg", base))[0]
    try:
        params = doc.getObject("Params")
        assert sheet_source(params) == "petg"
        params.set(params.getCellFromAlias("preset"), "'petgg")  # typed into the cell
        doc.recompute()
        try:
            sheet_settings(params, base)
        except presets.PresetNotFound as e:
            assert "'petgg'" in str(e) and "built with preset 'petg'" in str(e), e
        else:
            raise AssertionError("a mistyped preset name fell back to the stored values")
    finally:
        App.closeDocument(doc.Name)
        shutil.rmtree(base)


def test_a_missing_preset_without_a_recorded_source_falls_back():
    """A document from before the source cell: a missing preset can't be told
    from a typo, so its stored values are kept, as before."""
    gone = presets.Preset("gone", "gone", dict(presets.defaults(), hinge_clearance=0.15))
    doc = params_document(doc_name="rebuild_nosource", preset=gone)[0]
    empty = tempfile.mkdtemp(prefix="rebuild_test")
    try:
        sheet = doc.getObject("Preset")
        sheet.setAlias(sheet.getCellFromAlias("preset_source"), "")
        doc.recompute()
        assert sheet_source(sheet) is None
        set_preset(sheet, "other")
        doc.recompute()
        _, preset, warnings = sheet_settings(sheet, empty)
        assert preset.ref == "other" and preset.values == gone.values and len(warnings) == 1
    finally:
        App.closeDocument(doc.Name)
        shutil.rmtree(empty)


def _older_document(doc_name):
    """A document as built before presets: no preset cell and no Preset
    sheet; its tolerances and fits on Params (hinge_clearance edited to 0.3,
    lock_seat_clearance missing)."""
    doc = params_document([("gf_x", "4")], doc_name=doc_name)[0]
    params = doc.getObject("Params")
    params.setAlias(params.getCellFromAlias("preset"), "")
    row = 100
    for name, val in presets.defaults().items():
        if name != "lock_seat_clearance":
            row += 1
            params.set(f"B{row}", f"={0.3 if name == 'hinge_clearance' else val} mm")
            params.setAlias(f"B{row}", name)
    doc.removeObject("Preset")
    doc.recompute()
    return doc


def test_an_older_document_keeps_its_values():
    """Built before presets: no preset cell, the values on Params, one
    edited, one missing. The rebuild keeps the values it has (today's
    default for the missing one) and says why."""
    doc = _older_document("rebuild_old")
    try:
        params = doc.getObject("Params")
        overrides, preset, warnings = sheet_settings(params)
        assert overrides == [("gf_x", "4")], overrides
        assert preset.ref == "" and preset.values["hinge_clearance"] == 0.3
        assert preset.values["lock_seat_clearance"] == presets.defaults()["lock_seat_clearance"]
        assert len(warnings) == 1 and "no preset" in warnings[0], warnings
    finally:
        App.closeDocument(doc.Name)


def test_an_invalid_preset_is_an_error_not_a_fallback():
    base = _base_with("bad", {"gf_x": 4})
    doc = params_document(doc_name="rebuild_bad", preset=presets.Preset("bad", "bad", presets.defaults()))[0]
    try:
        try:
            sheet_settings(doc.getObject("Params"), base)
        except ParamError as e:
            assert "not a preset value" in str(e), e
        else:
            raise AssertionError("an invalid preset was replaced by the stored values")
    finally:
        App.closeDocument(doc.Name)
        shutil.rmtree(base)


def test_params_document_holds_only_the_sheets():
    """edit_params.py's document: the sheets and no geometry, so editing it
    recomputes nothing; build_box.py builds from it."""
    doc = params_document([("gf_x", "4")], doc_name="params_only")[0]
    try:
        assert sorted(o.Name for o in doc.Objects) == ["Internal", "Params", "Preset"]
    finally:
        App.closeDocument(doc.Name)


def _open_box(name):
    """An open generated document whose preset cell names `name` (one left
    open by another test would make FreeCAD rename this one)."""
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    return params_document(doc_name=DOC_NAME, preset=presets.Preset(name, name, presets.defaults()))[0]


def test_a_rejected_preset_leaves_the_open_box_open():
    for values, message in (({"hinge_clearence": 0.1}, "not a preset value"), ({"hinge_clearance": 0}, "")):
        base = _base_with("bad", values)
        _open_box("bad")
        try:
            try:
                _open_settings(base)
            except ParamError as e:
                assert message in str(e), e
            else:
                raise AssertionError(f"{values} was accepted")
            assert DOC_NAME in App.listDocuments(), values
            assert DOC_NAME + "_check" not in App.listDocuments()
        finally:
            App.closeDocument(DOC_NAME)
            shutil.rmtree(base)


def test_a_good_preset_closes_the_open_box():
    base = _base_with("petg", {"hinge_clearance": 0.15})
    _open_box("petg")
    try:
        overrides, preset, warnings = _open_settings(base)
        assert preset.values["hinge_clearance"] == 0.15 and warnings == []
        assert DOC_NAME not in App.listDocuments() and DOC_NAME + "_check" not in App.listDocuments()
    finally:
        if DOC_NAME in App.listDocuments():
            App.closeDocument(DOC_NAME)
        shutil.rmtree(base)


def test_an_older_document_rebuilds_onto_the_preset_sheet():
    """The stored values of a document from before the Preset sheet reach a
    rebuilt document's Preset sheet; its Params holds only inputs and the cell."""
    doc = _older_document("rebuild_old2")
    docs = [doc]
    try:
        overrides, preset, _ = sheet_settings(doc.getObject("Params"))
        again = params_document(overrides, doc_name="rebuild_new", preset=preset)[0]
        docs.append(again)
        assert value(again.getObject("Preset"), "hinge_clearance") == 0.3
        assert again.getObject("Params").getCellFromAlias("hinge_clearance") is None
        assert sheet_preset(again.getObject("Params")) == ""
    finally:
        for d in docs:
            App.closeDocument(d.Name)
