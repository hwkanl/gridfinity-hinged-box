import json
import os
import shutil
import tempfile

import FreeCAD as App

from hwkan_gfbox.cli import parse_overrides
from hwkan_gfbox.sheet import ParamError, apply_overrides, create_params_sheet
from hwkan_gfbox.validate import validate


def _validate_with(*overrides):
    sheet = create_params_sheet(App.newDocument("validate_test"))
    apply_overrides(sheet, overrides)
    sheet.Document.recompute()
    validate(sheet)


def _error_of(*overrides):
    try:
        _validate_with(*overrides)
    except ParamError as e:
        return str(e)
    raise AssertionError(f"accepted: {overrides}")


def test_defaults_are_valid():
    _validate_with()


def test_grid_counts_must_be_whole_and_positive():
    assert "gf_x must be a whole number" in _error_of(("gf_x", "0"))
    assert "gf_y must be a whole number" in _error_of(("gf_y", "2.5"))


def test_all_errors_are_reported_together():
    msg = _error_of(("gf_x", "0"), ("gf_z_units", "0"))
    assert "gf_x" in msg and "gf_z_units" in msg, msg


def test_tolerances_must_not_be_negative():
    assert "lip_clearance must be >= 0" in _error_of(("lip_clearance", "-0.1"))


def test_feet_xy_clearance_limit():
    _validate_with(("feet_xy_clearance", "0.5"))
    assert "feet_xy_clearance must be <=" in _error_of(("feet_xy_clearance", "0.6"))


def test_lip_must_fit_in_wall():
    assert "lid wall beside the channel" in _error_of(("lip_thickness", "3.5"))
    _validate_with(("lip_thickness", "3.4"))  # exactly min_wall (0.8 mm) walls


def test_lip_arc_rules():
    assert "between 0 and lip_thickness / 2" in _error_of(("lip_height", "1.5"))
    assert "between 0 and lip_thickness / 2" in _error_of(("lip_height", "0"))
    assert "no bead" in _error_of(("lip_clearance", "0.7"))
    # The hinge allows an arc edge up to atan2(4.5 + 1, 3.875) = 54.8 deg from vertical:
    _validate_with(("lip_height", "0.75"))  # r = 1.875, edge 53.1 deg
    assert "too steep" in _error_of(("lip_height", "0.8"))  # r = 1.806, edge 56.2 deg
    # a flat arc has a radius larger than the rim's corner radius (2.5 mm)
    assert "folds over itself" in _error_of(("lip_height", "0.4"))  # r = 3.01
    _validate_with(("lip_height", "0.55"))  # r = 2.32


def test_rim_band_must_hold_its_chamfer():
    assert "rim_band_h must be greater than rim_extra" in _error_of(("rim_band_h", "2"))


def test_channel_depth_limit():
    # a wide rim, so a channel as deep as base_h is still a shallow arc
    assert "channel depth" in _error_of(("wall_t", "10"), ("lip_thickness", "9.6"), ("lip_height", "4.75"))


def test_parse_overrides_order_and_rest():
    d = tempfile.mkdtemp(prefix="cli_test")
    try:
        path = os.path.join(d, "mine.json")
        with open(path, "w") as f:
            json.dump({"format": 1, "values": {"lip_clearance": 0.3}}, f)
        overrides, preset, rest = parse_overrides(
            ["--set", "gf_x=5", "--part", "lid", "--preset", path, "--set", "lid_chamfer=1.5", "--fine"])
    finally:
        shutil.rmtree(d)
    assert overrides == [("gf_x", "5"), ("lid_chamfer", "1.5")], overrides
    assert (preset.name, preset.ref, preset.values["lip_clearance"]) == ("mine", path, 0.3)
    assert rest == ["--part", "lid", "--fine"], rest


def test_parse_overrides_defaults_to_the_default_preset():
    overrides, preset, rest = parse_overrides(["--out", "x"])
    assert overrides == [] and preset.name == "default" and rest == ["--out", "x"]


def test_preset_values_cannot_be_set_on_the_command_line():
    for args, fragment in [
        (["--set", "hinge_clearance=0.15"], "hinge_clearance comes from the preset"),
        (["--set", "hook_preload=0.3"], "hook_preload comes from the preset"),
        (["--params", "x.json"], "--preset"),
        (["--preset"], "--preset expects"),
        (["--preset", "/nowhere/x.json"], "not found"),
    ]:
        try:
            parse_overrides(args)
        except ParamError as e:
            assert fragment in str(e), (args, str(e))
        else:
            raise AssertionError(f"accepted: {args}")


def test_parse_overrides_rejects_malformed_set():
    for args in (["--set"], ["--set", "gf_x"]):
        try:
            parse_overrides(args)
        except ParamError as e:
            assert "--set expects NAME=VALUE" in str(e)
        else:
            raise AssertionError(f"accepted: {args}")


def test_negative_input_is_reported_not_crashing():
    assert "gf_x must be a whole number" in _error_of(("gf_x", "-1"))


def test_non_finite_values_are_refused():
    sheet = create_params_sheet(App.newDocument("finite_test"))
    for text in ("nan", "inf", "-inf", "nan mm"):
        try:
            apply_overrides(sheet, [("gf_x" if "mm" not in text else "wall_t", text)])
        except ParamError as e:
            assert "expected a number" in str(e), str(e)
        else:
            raise AssertionError(f"accepted: {text}")


def test_hinged_box_size_rules():
    assert "at least 2 for a hinged box" in _error_of(("gf_x", "1"))
    assert "at least 2 for a hinged box" in _error_of(("gf_y", "1"))
    msg = _error_of(("gf_x", "2"), ("gf_y", "3"))
    assert "gf_x must be >= gf_y" in msg and "swap" in msg, msg
    _validate_with(("gf_x", "2"), ("gf_y", "2"))
    _validate_with(("gf_x", "5"), ("gf_y", "3"))


def test_hinge_rules():
    assert "pins" in _error_of(("knuckle_gap", "4"))
    assert "knuckle_r must be greater than pin_dia / 2" in _error_of(("pin_dia", "8"))
    assert "pin_tip_c must be > 0" in _error_of(("pin_tip_r", "2"))
    assert "widened base must fit" in _error_of(("pin_dia", "7"))  # 3.5 + 0.42 > r = 3.875
    _validate_with(("pin_dia", "6.8"), ("leaf_r", "3.7"))  # 3.4 + 0.42 < 3.875; leaf_r > 3.4 + hinge_clearance
    assert "pin_angle must be between" in _error_of(("pin_angle", "95"))
    assert "corner pads" in _error_of(("gf_x", "2"), ("gf_y", "2"), ("knuckle_len", "12"))


def test_knuckle_flare_rules():
    two = (("gf_x", "2"), ("gf_y", "2"))
    # 2x2: the pad rule is tight: 21 + hinge_root_len / 2 <= 45 - 8 = 37 mm
    _validate_with(*two, ("knuckle_flare", "43"))  # root 31.62 -> 36.81 mm
    msg = _error_of(*two, ("knuckle_flare", "44"))  # root 32.18 -> 37.09 mm
    assert "corner pads" in msg and "flared root" in msg, msg
    assert "corner pads" in _error_of(*two, ("knuckle_flare", "45"))
    _validate_with(("gf_x", "3"), ("gf_y", "2"), ("knuckle_flare", "45"))
    _validate_with(("knuckle_flare", "0"))
    # neighbouring roots: hinge_root_len < hinge_pitch (42 mm on 2x2; 60 deg gives 45.01)
    msg = _error_of(*two, ("knuckle_flare", "60"), ("pad_reach", "3"))
    assert "neighbouring hinges" in msg, msg
    # hinge_pitch 63: flare 68 gives root 16 + 41.46 = 57.46 < 63, no such error
    assert "neighbouring" not in _error_of(("gf_x", "3"), ("knuckle_flare", "68"))
    for text in ("90", "95", "-5"):
        assert "knuckle_flare must be between" in _error_of(("knuckle_flare", text)), text


def test_pad_reach_limits():
    assert "pad_reach must be at least wall_t" in _error_of(("pad_reach", "2"))
    assert "2 * pad_reach must be less than" in _error_of(("pad_reach", "45.5"))  # outer_d 91
    _validate_with(("pad_reach", "8"))


def test_leaf_rules():
    assert "hinge_clearance must be > 0" in _error_of(("hinge_clearance", "0"))
    assert "socket must fit in the leaf knuckle" in _error_of(("leaf_r", "2.6"))  # 2.6 <= 2.5 + 0.2
    assert "sockets meet" in _error_of(("knuckle_gap", "6.4"))  # leaf_w 6.1 <= 2 * 3.063
    assert "dovetail_angle must be between" in _error_of(("dovetail_angle", "90"))
    assert "leaf body must clear the slot" in _error_of(("dovetail_clearance", "0.4"))  # 0.346 < 0.4
    assert "rib must hold the slot" in _error_of(("hinge_rib_w", "14"))  # < 13.86 + 1.6
    two = (("gf_x", "2"), ("gf_y", "2"))
    assert "hinge ribs must clear the corner pads" in _error_of(*two, ("hinge_rib_w", "34"))  # 21 + 17 > 37
    assert "neighbouring hinge ribs" in _error_of(*two, ("hinge_rib_w", "42"))
    assert "slot floor" in _error_of(*two, ("gf_z_units", "1"))  # 10.15 - 3 - 10 - 0.15 < 0
    msg = _error_of(("leaf_r", "4.4"))
    assert "clear the lid face" in msg and "leaf_r must be <=" in msg and "leaf top" in msg, msg
    _validate_with(("leaf_r", "3.7"))  # foot 4.108 from the axis <= 4.3
    assert "45 deg underside reaches the bed" in _error_of(("leaf_r", "5.6"))  # 3.96 > 3.875
    assert "dovetail must clear the lid knuckles" in _error_of(("dovetail_drop", "0"))  # 3.875 < 4.075
    assert "dovetail_len must be > 0" in _error_of(("dovetail_len", "0"))
    assert "dovetail_t must be > 0" in _error_of(("dovetail_t", "0"))
    assert "dovetail_t must be > 0" in _error_of(("dovetail_t", "7.5"))  # > 3.875 + 3.5


def test_hinge_and_lock_count_rules():
    assert "hinge_count must be at least 2" in _error_of(("hinge_count", "1"))
    assert "lock_count must be a whole number >= 1" in _error_of(("lock_count", "0"))
    _validate_with(("lock_count", "3"))  # more locks than hinges is fine
    assert "lock_count must be at most gf_x" in _error_of(("lock_count", "4"))
    assert "hinge_count must be at most gf_x" in _error_of(("hinge_count", "4"))
    _validate_with(("hinge_count", "3"), ("lock_count", "3"))
    _validate_with(("hinge_count", "3"), ("lock_count", "1"))
    msg = _error_of(("hinge_count", "4"))  # 3x2: pitch 31.5, 63 - 15.75 + 12.84 > 58
    assert "corner pads" in msg and "lower hinge_count" in msg, msg
    msg = _error_of(("gf_x", "2"), ("gf_y", "2"), ("hinge_count", "3"))
    assert "lower hinge_count" in msg, msg
    _validate_with(("gf_x", "5"), ("gf_y", "3"), ("hinge_count", "4"), ("lock_count", "2"))


def test_lock_rules():
    assert "latch_clearance must be > 0" in _error_of(("latch_clearance", "0"))
    assert "pad_top must be <= 0" in _error_of(("pad_top", "0.5"))
    assert "slot's roof must be at least min_wall" in _error_of(("pad_top", "-1.5"))  # 0.4 < 0.8
    msg = _error_of(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "2"))
    assert "below the box bottom" in msg and "gf_z_units" in msg, msg
    _validate_with(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"))  # 24.15 - 23.24 >= 0
    _validate_with(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"), ("feet_z_clearance", "0"))  # 23.65
    msg = _error_of(("hinge_count", "3"), ("lock_count", "3"), ("latch_base_hw", "16"))  # latch_w 43.5 >= 42
    assert "neighbouring locks" in msg and "lower lock_count" in msg, msg
    msg = _error_of(("gf_x", "2"), ("gf_y", "2"), ("latch_base_hw", "12"))  # latch_w 35.5: 42 - 21 + 17.75 > 37
    assert "locks must clear the corner pads" in msg, msg
    assert "latch_base_hw must be > 0" in _error_of(("latch_base_hw", "0"))
    assert "pivot_dist must be > 0" in _error_of(("pivot_dist", "0"))
    assert "over_center must be between" in _error_of(("over_center", "90"))
    assert "bar_r must be > 0 and less than lobe_r" in _error_of(("bar_r", "3"))
    assert "lock_lip_e must be > 0" in _error_of(("lock_lip_e", "0"))
    # a derived cell forced to NaN (no input combination is known to give one)
    sheet = create_params_sheet(App.newDocument("validate_nan_test"))
    sheet.Document.getObject("Internal").set("hook_nl", "=acos(2)")
    sheet.Document.recompute()
    try:
        validate(sheet)
    except ParamError as e:
        assert "hook_nl is not a finite number" in str(e), e
    else:
        raise AssertionError("NaN accepted")


def test_lock_seat_rules():
    assert "the lip's seat must lie in front of the lid face" in _error_of(("lock_k_u", "0.05"))  # seat center 0.07 nearer the lid
    assert "the lip under the seat must be at least min_wall" in _error_of(("lock_bar_drop", "3.5"))  # floor 0.37 up
    assert "the stop along the lip's front edge must be at least min_wall wide" in _error_of(("lock_lip_e", "3.5"))  # stop 3.5 - 2.93 = 0.57
    _validate_with(("lock_lip_e", "3.8"))  # stop 0.87 >= min_wall 0.8
    assert "the stop's top" in _error_of(("lock_stop_rise", "0"))  # below the seat's center (0.24 above the bar's)
    assert "the stop's top" in _error_of(("lock_stop_rise", "3.5"))  # 8.125 > lid_h 7.75


def test_hinge_clearance_can_go_below_the_old_limit():
    # dovetail_w 10.4: the leaf body clears the slot's opening by
    # (10.4 - (10 - 2 * hc)) / 2 * sin(60) >= dovetail_clearance for any hc > 0
    _validate_with(("hinge_clearance", "0.05"))
    _validate_with(("hinge_clearance", "0.12"))
