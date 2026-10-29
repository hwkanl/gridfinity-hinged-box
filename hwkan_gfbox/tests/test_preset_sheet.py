"""The preset in the document: the preset cell, its values on Params, and
build() / params_document() taking a preset."""
import FreeCAD as App

from hwkan_gfbox import presets
from hwkan_gfbox.build import build, params_document
from hwkan_gfbox.presets import Preset
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import ParamError, preset_values, sheet_preset, value

PETG = Preset("petg", "petg", dict(presets.defaults(), hinge_clearance=0.15, latch_clearance=0.3, latch_detent_height=0.0))


def test_the_preset_cell_and_values():
    doc = params_document(doc_name="preset_cell")[0]
    try:
        sheet = doc.getObject("Params")
        assert sheet_preset(sheet) == "default"
        assert preset_values(sheet) == presets.defaults()
    finally:
        App.closeDocument(doc.Name)
    doc = params_document([("gf_x", "4")], doc_name="preset_cell", preset=PETG)[0]
    try:
        sheet = doc.getObject("Params")
        assert sheet_preset(sheet) == "petg"
        assert value(sheet, "hinge_clearance") == 0.15 and value(sheet, "latch_detent_height") == 0
        assert value(sheet, "gf_x") == 4 and preset_values(sheet) == PETG.values
    finally:
        App.closeDocument(doc.Name)


def test_overrides_come_after_the_preset():
    doc = params_document([("hinge_clearance", "0.25")], doc_name="preset_order", preset=PETG)[0]
    try:
        assert value(doc.getObject("Params"), "hinge_clearance") == 0.25
    finally:
        App.closeDocument(doc.Name)


def test_a_preset_value_the_model_rejects_is_named():
    bad = Preset("bad", "bad", dict(presets.defaults(), hinge_clearance=0.0))
    try:
        build(preset=bad, doc_name="preset_bad")
    except ParamError as e:
        assert "hinge_clearance must be > 0" in str(e), e
    else:
        raise AssertionError("a preset with hinge_clearance 0 was built")
    assert "preset_bad" not in App.listDocuments()


def test_a_build_with_a_preset_equals_one_with_the_same_overrides():
    names = ("preset_a", "preset_b", "preset_c")
    try:
        a = build(preset=PETG, doc_name=names[0])[0]
        b = build(presets.overrides(PETG), doc_name=names[1])[0]
        c = build(doc_name=names[2])[0]  # defaults: the preset must make a difference
        for label in ("Bottom", "Lid", "Leaves", "LatchBase", "LatchLever", "LatchHook"):
            va, vb = get(a, label).Shape.Volume, get(b, label).Shape.Volume
            assert abs(va - vb) < 1e-6, (label, va, vb)
        assert abs(get(a, "Bottom").Shape.Volume - get(c, "Bottom").Shape.Volume) > 1e-3  # lip_clearance 0.3 (the bead)
    finally:
        for name in names:
            if name in App.listDocuments():
                App.closeDocument(name)
