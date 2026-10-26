import os
import shutil
import tempfile

from hwkan_gfbox import presets
from hwkan_gfbox import presets_dialog as pd
from hwkan_gfbox.sheet import ParamError


def _raises(fn, text):
    try:
        fn()
    except ParamError as e:
        assert text in str(e), str(e)
    else:
        raise AssertionError("expected ParamError")


def test_edited_parses_the_values_and_keeps_the_rest():
    p = presets.Preset("pla", "pla", presets.defaults(), "note", {"tests": "A"})
    q = pd.edited(p, {"hinge_clearance": "0.12"}, "new note")
    assert q.values["hinge_clearance"] == 0.12 and q.note == "new note" and q.calibration == {"tests": "A"}
    assert p.values["hinge_clearance"] != 0.12  # a copy
    for bad in ("abc", "nan", "inf", "1_0"):
        _raises(lambda: pd.edited(p, {"hinge_clearance": bad}), f"hinge_clearance: '{bad}' is not a number")


def test_save_checked_refuses_the_default():
    base = tempfile.mkdtemp()
    try:
        _raises(lambda: pd.save_checked(presets.load(presets.DEFAULT, base), base), "built-in default can't be changed")
    finally:
        shutil.rmtree(base)


def test_save_checked_keeps_the_calibration():
    base = tempfile.mkdtemp()
    try:
        path = presets.new("pla", base=base)
        p = presets.load("pla", base)
        p.calibration = {"tests": "A"}
        presets.save(p, path)
        pd.save_checked(pd.edited(presets.load("pla", base), {"hinge_clearance": "0.12"}), base)
        assert presets.load("pla", base).calibration == {"tests": "A"}
    finally:
        shutil.rmtree(base)


def test_save_checked_validates_then_saves():
    base = tempfile.mkdtemp()
    try:
        presets.new("pla", base=base)
        p = presets.load("pla", base)
        _raises(lambda: pd.save_checked(pd.edited(p, {"feet_xy_clearance": "0.9"}), base), "feet_xy_clearance")
        assert presets.load("pla", base).values["feet_xy_clearance"] != 0.9  # not saved
        pd.save_checked(pd.edited(p, {"hinge_clearance": "0.12"}), base)
        assert presets.load("pla", base).values["hinge_clearance"] == 0.12
    finally:
        shutil.rmtree(base)


def test_delete_removes_the_file_but_not_the_default():
    base = tempfile.mkdtemp()
    try:
        path = presets.new("pla", base=base)
        pd.delete("pla", base)
        assert not os.path.exists(path)
        _raises(lambda: pd.delete(presets.DEFAULT, base), "built-in default can't be deleted")
    finally:
        shutil.rmtree(base)
