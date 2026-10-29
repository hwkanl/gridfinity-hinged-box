"""Preset files: lookup, checks, save and load
(spec: docs/superpowers/specs/2026-10-12-presets-design.md)."""
import json
import os
import shutil
import tempfile
from contextlib import contextmanager

from hwkan_gfbox import presets
from hwkan_gfbox.presets import Preset, PresetNotFound
from hwkan_gfbox.sheet import ParamError


@contextmanager
def _base():
    """A fresh user data dir whose preset directory exists."""
    base = tempfile.mkdtemp(prefix="presets_test")
    os.makedirs(presets.preset_dir(base))
    try:
        yield base
    finally:
        shutil.rmtree(base)


def _write(path, data):
    with open(path, "w") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return path


def _in_dir(base, name, data):
    return _write(os.path.join(presets.preset_dir(base), name + ".json"), data)


def _error(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ParamError as e:
        return e
    raise AssertionError(f"accepted: {args} {kw}")


def test_names_are_the_seven_preset_values():
    """What the test prints check, hinge then latch; the other gaps are design values."""
    assert presets.NAMES == ["hinge_clearance", "hinge_dovetail_fit", "hinge_detent_height", "latch_clearance",
                             "latch_dovetail_fit", "latch_detent_height", "latch_preload"]
    assert presets.defaults()["hinge_dovetail_fit"] == 0.1 and presets.defaults()["hinge_detent_height"] == 0.6


def test_default_needs_no_file():
    with _base() as b:
        p = presets.load("default", b)
        assert (p.name, p.ref, p.note, p.calibration) == ("default", "default", "", None)
        assert p.values == presets.defaults()
        assert presets.resolve("default", b) is None


def test_partial_file_takes_defaults():
    with _base() as b:
        _in_dir(b, "mine", {"format": 1, "values": {"hinge_clearance": 0.15, "latch_detent_height": 0}})
        p = presets.load("mine", b)
        assert (p.name, p.ref, p.note, p.calibration) == ("mine", "mine", "", None)
        assert p.values["hinge_clearance"] == 0.15 and p.values["latch_detent_height"] == 0.0
        assert isinstance(p.values["latch_detent_height"], float)
        assert p.values["latch_clearance"] == presets.defaults()["latch_clearance"]
        _in_dir(b, "empty", {"format": 1, "values": {}})
        assert presets.load("empty", b).values == presets.defaults()


def test_round_trip_keeps_note_and_calibration():
    with _base() as b:
        values = dict(presets.defaults(), hinge_clearance=0.15)
        cal = {"test": "B", "sweep": [3, 4, 5, 6, 7], "chosen": {"A": 4}}
        path = presets.preset_path("petg", b)
        presets.save(Preset("petg", "petg", values, "Prusa MK4, PETG", cal), path)
        with open(path) as f:
            data = json.load(f)
        assert data["format"] == 1 and list(data["values"]) == presets.NAMES
        p = presets.load("petg", b)
        assert p.values == values and p.note == "Prusa MK4, PETG" and p.calibration == cal


def test_file_errors_name_the_file_and_key():
    with _base() as b:
        cases = [
            ({"format": 1, "values": {"gf_x": 4}}, "'gf_x' is not a preset value"),
            ({"format": 1, "values": {"bin_clearance": 1}}, "'bin_clearance' is not a preset value"),
            ({"format": 1, "value": {}}, "unknown key"),
            ({"format": 1, "values": {"hinge_clearance": "0.2 mm"}}, "'hinge_clearance' must be a number"),
            ({"format": 1, "values": {"hinge_clearance": True}}, "'hinge_clearance' must be a number"),
            ({"format": 1, "values": []}, "'values' must be an object"),
            ({"format": 1, "note": 3}, "'note' must be text"),
            ({"format": 2}, "newer version"),
            ({"values": {}}, "'format' must be 1"),
            ([1, 2], "must be a JSON object"),
            ("{not json", "cannot read preset"),
        ]
        for data, fragment in cases:
            path = _in_dir(b, "bad", data)
            msg = str(_error(presets.load, "bad", b))
            assert fragment in msg and path in msg, (data, msg)
        path = _in_dir(b, "nan", '{"format": 1, "values": {"hinge_clearance": NaN}}')
        assert "'hinge_clearance' must be a number" in str(_error(presets.load, "nan", b))


def test_missing_preset_lists_the_existing_ones():
    with _base() as b:
        _in_dir(b, "petg", {"format": 1})
        e = _error(presets.load, "pla", b)
        assert isinstance(e, PresetNotFound) and "'pla'" in str(e) and "petg" in str(e) and "default" in str(e), e
        assert isinstance(_error(presets.load, "/nowhere/x.json", b), PresetNotFound)


def test_default_json_is_refused():
    with _base() as b:
        _in_dir(b, "default", {"format": 1})
        assert "built-in" in str(_error(presets.load, "default", b))
        assert "built-in" in str(_error(presets.list_presets, b))


def test_paths_are_read_as_files_and_kept_absolute():
    with _base() as b:
        d = tempfile.mkdtemp(prefix="presets_path")
        try:
            path = _write(os.path.join(d, "shared.json"), {"format": 1, "values": {"latch_clearance": 0.3}})
            p = presets.load(path, b)
            assert (p.name, p.ref, p.values["latch_clearance"]) == ("shared", path, 0.3)
            here = os.getcwd()
            os.chdir(d)
            try:
                ref = presets.load("shared.json", b).ref   # relative -> absolute
                assert os.path.isabs(ref) and os.path.samefile(ref, path), ref
            finally:
                os.chdir(here)
            assert presets.is_path("a/b") and presets.is_path("x.json") and not presets.is_path("petg")
        finally:
            shutil.rmtree(d)


def test_overrides_are_mm_pairs_in_params_order():
    pairs = presets.overrides(presets.load("default"))
    assert [n for n, _ in pairs] == presets.NAMES
    assert dict(pairs)["hinge_dovetail_fit"] == "0.1 mm" and dict(pairs)["latch_detent_height"] == "0.4 mm"


def test_new_list_and_path():
    with _base() as b:
        path = presets.new("petg", base=b)
        assert path == presets.preset_path("petg", b) and path.endswith(os.path.join("presets", "petg.json"))
        with open(path) as f:
            data = json.load(f)
        assert list(data["values"]) == presets.NAMES and data["calibration"] == {}
        _in_dir(b, "pla", {"format": 1, "note": "PLA", "values": {"hinge_clearance": 0.15}})
        presets.new("pla2", "pla", b)
        assert presets.load("pla2", b).values["hinge_clearance"] == 0.15
        assert presets.list_presets(b)[0][0] == "default"
        assert ("pla", "PLA") in presets.list_presets(b) and ("petg", "") in presets.list_presets(b)
        assert "exists" in str(_error(presets.new, "petg", base=b))
        before = sorted(os.listdir(presets.preset_dir(b)))
        for bad in ("default", "a/b", "x.json", ""):
            _error(presets.new, bad, base=b)
        assert isinstance(_error(presets.new, "y", "nope", b), PresetNotFound)
        assert sorted(os.listdir(presets.preset_dir(b))) == before   # nothing written
        assert "built-in" in str(_error(presets.preset_path, "default", b))


def test_list_tolerates_an_unreadable_file():
    with _base() as b:
        _in_dir(b, "broken", "{")
        note = dict(presets.list_presets(b))["broken"]
        assert note.startswith("(unreadable")


def test_shipped_tight_is_found_after_the_users_and_read_only():
    with _base() as b:
        t = presets.load("Tight", b)
        assert presets.is_shipped(presets.resolve("Tight", b)) and presets.read_only("Tight", b)
        assert t.values["hinge_clearance"] == 0.15 and t.values["hinge_dovetail_fit"] == 0.075
        assert dict(presets.list_presets(b))["Tight"] == t.note and t.note.startswith("shipped")
        assert presets.read_only("default", b) and not presets.read_only("nope", b)
        # a user preset of the same name wins, and is the user's to change
        _in_dir(b, "Tight", {"format": 1, "values": {"hinge_clearance": 0.12}})
        assert presets.load("Tight", b).values["hinge_clearance"] == 0.12 and not presets.read_only("Tight", b)
        assert [n for n, _ in presets.list_presets(b)].count("Tight") == 1


def test_shipped_presets_are_valid_and_differ_from_default():
    for fname in os.listdir(presets.SHIPPED_DIR):
        p = presets.load(os.path.join(presets.SHIPPED_DIR, fname))
        assert fname.endswith(".json") and fname != "default.json" and p.values != presets.defaults(), fname


def test_main():
    import io
    from contextlib import redirect_stderr, redirect_stdout
    with _base() as b:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            assert presets.main(["new", "petg"], b) == 0
            assert presets.main(["new", "petg2", "--from", "petg"], b) == 0
            assert presets.main(["list"], b) == 0
            assert presets.main(["path", "pla"], b) == 0
            assert presets.main(["new", "petg"], b) == 2       # exists
            assert presets.main(["bogus"], b) == 2
            assert presets.main([], b) == 2
        text = out.getvalue()
        assert "wrote " + presets.preset_path("petg", b) in text and "petg2" in text, text
        assert presets.preset_path("pla", b) in text and "default" in text
        assert "exists" in err.getvalue() and "usage" in err.getvalue()
