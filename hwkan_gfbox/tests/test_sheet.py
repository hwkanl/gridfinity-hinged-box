import FreeCAD as App

from hwkan_gfbox.params import DERIVED, PARAMS, sheet_of
from hwkan_gfbox.sheet import ParamError, _cell_text, create_params_sheet, set_param, value


def _sheet():
    return create_params_sheet(App.newDocument("sheet_test"))


def _near(a, b):
    return abs(a - b) < 1e-9


def test_derived_defaults():
    s = _sheet()
    expected = {
        "grid_w": 128, "grid_d": 86, "outer_w": 134, "outer_d": 92,
        "rim_w": 138, "rim_d": 96,
        "bp_h": 4.65, "base_h": 4.75, "stack_lip_h": 4.4,
        "bin_top_z": 49.4, "ceiling_z": 49.9, "box_h": 52.9,
        "split_z": 45.15, "lid_h": 7.75,
    }
    for name, want in expected.items():
        assert _near(value(s, name), want), (name, value(s, name), want)


def test_every_parameter_is_aliased_and_derived_are_formulas():
    s = _sheet()
    for name, val, tier, _ in PARAMS:
        sheet = s.Document.getObject(sheet_of(tier))
        cell = sheet.getCellFromAlias(name)
        assert cell, name
        if tier == DERIVED:
            assert sheet.getContents(cell) == _cell_text(val, tier), (name, sheet.getContents(cell))


def test_setting_an_input_updates_derived():
    s = _sheet()
    assert set_param(s, "gf_x", "4") == []
    s.Document.recompute()
    assert _near(value(s, "grid_w"), 170)


def test_bare_number_for_a_length_keeps_mm():
    s = _sheet()
    warnings = set_param(s, "wall_t", "4")
    s.Document.recompute()
    assert _near(value(s, "outer_w"), 136), value(s, "outer_w")
    assert warnings and "design constant" in warnings[0]


def test_length_with_explicit_mm_is_accepted():
    s = _sheet()
    set_param(s, "lip_clearance", "0.3 mm")
    s.Document.recompute()
    assert _near(value(s, "lip_clearance"), 0.3)


def test_refused_overrides():
    s = _sheet()
    for name, text, fragment in [
        ("gf_pitch", "40", "gridfinity"),
        ("grid_w", "100", "derived"),
        ("nope", "1", "unknown"),
        ("gf_x", "three", "expected a number"),
        ("gf_x", "3 mm", "expected a number"),
    ]:
        try:
            set_param(s, name, text)
        except ParamError as e:
            assert fragment in str(e), (name, str(e))
        else:
            raise AssertionError(f"{name}={text} was accepted")
