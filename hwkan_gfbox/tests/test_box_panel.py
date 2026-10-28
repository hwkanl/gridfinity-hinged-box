import FreeCAD as App

from hwkan_gfbox import box_panel, presets
from hwkan_gfbox import testprints
from hwkan_gfbox.build import DOC_NAME, box_document, params_document
from hwkan_gfbox.shapes import get
from hwkan_gfbox.tests.helpers import built, v


def _close_box():
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)


def test_defaults_are_the_input_defaults():
    assert box_panel.defaults() == {"gf_x": 3, "gf_y": 2, "gf_z_units": 6, "hinge_count": 2, "lock_count": 2}


def test_replace_box_replaces_the_open_box():
    _close_box()
    try:
        params_document(doc_name=DOC_NAME)[0]  # stands in for an open box
        doc, _ = box_panel.replace_box({**box_panel.defaults(), "gf_x": 4}, presets.load(presets.DEFAULT))
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


def test_initial_new_is_the_defaults():
    inputs, preset = box_panel.initial()
    assert inputs == box_panel.defaults() and preset.name == presets.DEFAULT


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


def test_a_box_saved_under_another_name_is_the_open_box_when_active():
    _close_box()
    # named "test", like a box saved and reopened as test.FCStd
    box = built(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"))
    App.setActiveDocument(box.Name)
    assert box_document() is box
    assert any(n == "gf_x" for n, _ in testprints.gui_inputs()[0])
    params_document(doc_name="not_a_box")  # active, but no parts: not a box
    try:
        assert box_document() is None
    finally:
        App.closeDocument("not_a_box")
