"""Two sheets: Params (what users change) and Internal (the rest).
Spec: docs/superpowers/specs/2026-10-04-parameter-tidy-up-design.md."""
import glob
import os
import re

import FreeCAD as App

import hwkan_gfbox
from hwkan_gfbox.params import INPUT, INTERNAL_SHEET, PARAMS, PRESET_SHEET, PRESET_TIERS, USER_SHEET, sheet_of
from hwkan_gfbox.sheet import create_params_sheet, set_param, value

TIERS = {name: tier for name, _, tier, _ in PARAMS}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(hwkan_gfbox.__file__)))


def _aliases(sheet):
    """The sheet's aliases in row order (column B, the value column)."""
    names = []
    for row in range(1, 400):
        alias = sheet.getAlias(f"B{row}")
        if alias:
            names.append(alias)
    return names


def test_each_sheet_holds_its_rows():
    """Params: the inputs and the preset's name; Preset: the preset's values;
    Internal: the rest."""
    doc = App.newDocument("split_test")
    try:
        create_params_sheet(doc)
        inputs = [n for n, _, t, _ in PARAMS if t == INPUT]
        preset = [n for n, _, t, _ in PARAMS if t in PRESET_TIERS]
        assert _aliases(doc.getObject(USER_SHEET)) == inputs + ["preset"]
        assert _aliases(doc.getObject(PRESET_SHEET)) == preset + ["preset_source"]
        assert set(_aliases(doc.getObject(INTERNAL_SHEET))) == set(TIERS) - set(inputs) - set(preset)
    finally:
        App.closeDocument(doc.Name)


def test_values_and_overrides_route_to_their_sheet():
    doc = App.newDocument("split_test")
    try:
        params = create_params_sheet(doc)
        assert set_param(params, "latch_preload", "0.3") == []           # FIT: no warning
        assert set_param(params, "wall_t", "4") != []                    # internal: warning
        set_param(params, "gf_x", "4")
        doc.recompute()
        internal = doc.getObject(INTERNAL_SHEET)
        assert internal.getContents(internal.getCellFromAlias("wall_t")) == "=4 mm"
        assert value(params, "wall_t") == 4 and value(params, "latch_preload") == 0.3
        assert value(params, "grid_w") == 4 * 42 + 2  # a derived formula on Internal follows Params.gf_x
        assert value(internal, "gf_x") == 4        # routing works from any sheet
        preset = doc.getObject(PRESET_SHEET)
        assert preset.getContents(preset.getCellFromAlias("latch_preload")) == "=0.3 mm"
        set_param(params, "latch_dovetail_fit", "0.15")
        doc.recompute()
        # a derived formula on Internal follows Preset.latch_dovetail_fit
        assert abs(value(params, "lock_nub_h") - (0.15 + value(params, "latch_detent_height"))) < 1e-9
    finally:
        App.closeDocument(doc.Name)


def test_expressions_name_the_right_sheet():
    bad = []
    files = glob.glob(os.path.join(ROOT, "hwkan_gfbox", "**", "*.py"), recursive=True)
    for path in files:
        with open(path) as f:
            text = f.read()
        for m in re.finditer(r"\b(Params|Internal)\.([a-z_][a-z0-9_]*)", text):
            sheet, name = m.groups()
            if name in TIERS and sheet != sheet_of(TIERS[name]):
                bad.append(f"{os.path.relpath(path, ROOT)}: {sheet}.{name}")
    assert not bad, bad


def test_design_gaps_are_internal_and_presets_hold_tolerances_and_fits():
    from hwkan_gfbox.params import DESIGN, DESIGN_GAPS, FIT, PRESET_TIERS, TOLERANCE
    assert all(TIERS[n] == DESIGN for n in DESIGN_GAPS) and "bin_clearance" in DESIGN_GAPS
    assert PRESET_TIERS == (TOLERANCE, FIT)
    assert sorted(n for n, t in TIERS.items() if t in PRESET_TIERS) == sorted([
        "hinge_clearance", "hinge_dovetail_fit", "latch_clearance", "latch_dovetail_fit",
        "latch_preload", "latch_detent_height", "hinge_detent_height"])
