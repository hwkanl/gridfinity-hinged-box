import os
import shutil
import tempfile

import FreeCAD as App

from hwkan_gfbox import box_panel, presets
from hwkan_gfbox import testprints
from hwkan_gfbox.build import DOC_NAME, box_document, params_document
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import ParamError
from hwkan_gfbox.tests.helpers import built, v


def _close_box():
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)


def test_defaults_are_the_input_defaults():
    assert box_panel.defaults() == {"gf_x": 3, "gf_y": 2, "gf_z_units": 6, "hinge_count": 2, "lock_count": 2}


def test_rebuild_replaces_the_open_box():
    _close_box()
    try:
        params_document(doc_name=DOC_NAME)[0]  # stands in for an open box
        doc, _ = box_panel.rebuild({**box_panel.defaults(), "gf_x": 4}, presets.load(presets.DEFAULT))
        assert doc.Name == DOC_NAME
        assert v(doc, "gf_x") == 4 and get(doc, "Bottom").Shape.Volume > 0
        assert DOC_NAME + "001" not in App.listDocuments()
    finally:
        _close_box()


def test_check_accepts_the_defaults():
    assert box_panel.check(box_panel.defaults(), presets.load(presets.DEFAULT)) == ""


def test_check_reports_what_validate_rejects():
    problem = box_panel.check({**box_panel.defaults(), "lock_count": 5}, presets.load(presets.DEFAULT))
    assert "lock_count must be at most gf_x" in problem, problem


def test_check_leaves_no_document_open():
    before = set(App.listDocuments())
    box_panel.check({**box_panel.defaults(), "gf_y": 1}, presets.load(presets.DEFAULT))
    assert set(App.listDocuments()) == before


def test_initial_rebuild_reads_the_open_box():
    _close_box()
    base = tempfile.mkdtemp()
    try:
        presets.new("pla", base=base)
        params_document([("gf_x", "4"), ("lock_count", "3")], doc_name=DOC_NAME,
                        preset=presets.load("pla", base))
        inputs, preset, warnings = box_panel.initial(rebuild=True, base=base)
        assert inputs == {**box_panel.defaults(), "gf_x": 4, "lock_count": 3}
        assert preset.name == "pla" and warnings == []
    finally:
        _close_box()
        shutil.rmtree(base)


def test_initial_rebuild_without_a_box_raises():
    _close_box()
    try:
        box_panel.initial(rebuild=True)
    except ParamError as e:
        assert "no generated box is open" in str(e)
    else:
        raise AssertionError("expected ParamError")


def test_initial_new_is_the_defaults():
    inputs, preset, warnings = box_panel.initial(rebuild=False)
    assert inputs == box_panel.defaults() and preset.name == presets.DEFAULT and warnings == []


def test_check_keeps_the_active_document():
    doc = App.newDocument("check_active")
    try:
        App.setActiveDocument(doc.Name)
        preset = presets.load(presets.DEFAULT)
        box_panel.check(box_panel.defaults(), preset)
        assert App.ActiveDocument.Name == "check_active"
        box_panel.check({**box_panel.defaults(), "lock_count": 5}, preset)
        assert App.ActiveDocument.Name == "check_active"
    finally:
        App.closeDocument("check_active")


def test_initial_rebuild_with_the_preset_file_gone():
    _close_box()
    base = tempfile.mkdtemp()
    try:
        path = presets.new("pla", base=base)
        params_document([("gf_x", "4"), ("lock_count", "3")], doc_name=DOC_NAME,
                        preset=presets.load("pla", base))
        os.remove(path)
        inputs, preset, warnings = box_panel.initial(rebuild=True, base=base)
        assert inputs == {**box_panel.defaults(), "gf_x": 4, "lock_count": 3}
        assert preset.name == "pla" and len(warnings) == 1, warnings
    finally:
        _close_box()
        shutil.rmtree(base)


def test_a_box_saved_under_another_name_is_the_open_box_when_active():
    _close_box()
    # named "test", like a box saved and reopened as test.FCStd
    box = built(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"))
    App.setActiveDocument(box.Name)
    assert box_document() is box
    assert box_panel.initial(True)[0]["gf_x"] == 2
    assert any(n == "gf_x" for n, _ in testprints.gui_inputs()[0])
    params_document(doc_name="not_a_box")  # active, but no parts: not a box
    try:
        assert box_document() is None
    finally:
        App.closeDocument("not_a_box")
