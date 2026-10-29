"""The calibration suite's logic (spec:
docs/superpowers/specs/2026-10-12-calibration-suite-design.md)."""
import copy
import json
import os
import shutil
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO

from hwkan_gfbox import calibration as cal
from hwkan_gfbox import presets
from hwkan_gfbox.sheet import ParamError

ALL = lambda *args: True  # noqa: E731  every value valid: valid(value) for the windows, valid(test, value) for start/answer


def _preset(**values):
    return presets.Preset("t", "t", dict(presets.defaults(), **values))


def _error(fn, *args):
    try:
        fn(*args)
    except ParamError as e:
        return str(e)
    raise AssertionError(f"accepted: {args}")


def test_the_table():
    assert list(cal.TESTS) == list("ABCDEFG") and cal.DEFAULT_TESTS == "ABCDEF"
    want = {"A": ("hinge_clearance", 0.025, "hinge_lid", None, "stuck", "sloppy", True),
            "B": ("hinge_dovetail_fit", 0.025, "leaf", "hinge_rib", "tight", "loose", True),
            "C": ("hinge_detent_height", 0.05, "hinge_rib", "leaf", "hard", "weak", False),
            "D": ("latch_clearance", 0.025, "latch", None, "stuck", "sloppy", True),
            "E": ("latch_dovetail_fit", 0.025, "latch_base", "lock_pad", "tight", "loose", True),
            "F": ("latch_detent_height", 0.05, "lock_pad", "latch_base", "hard", "weak", False),
            "G": ("latch_preload", 0.05, "latch_keyless", None, "hard", "weak", False)}
    for letter, row in want.items():
        t = cal.TESTS[letter]
        assert (t.param, t.step, t.piece, t.partner, t.tight, t.loose, t.tight_up) == row, letter
        assert t.check, letter
    assert cal.TESTS["B"].settings == (("hinge_detent_height", "0"),)
    assert cal.TESTS["E"].settings == (("latch_detent_height", "0"),)


def test_numbers_and_values():
    assert cal.value_of(1, 0.025) == 0 and cal.value_of(9, 0.025) == 0.2
    assert cal.number_of(0.2, 0.025) == 9 and cal.number_of(0.09, 0.025) == 5  # nearest
    assert cal.number_of(0.35, 0.05) == 8 and cal.value_of(8, 0.05) == 0.35


def test_first_window():
    a = cal.TESTS["A"]
    assert cal.first_window(a, 0.2, ALL) == [7, 8, 9, 10, 11]
    assert cal.first_window(a, 0.025, ALL) == [1, 2, 3, 4, 5]  # never below 1
    # a limit above: the window moves down, keeping five numbers
    assert cal.first_window(a, 0.2, lambda v: v <= 0.21) == [5, 6, 7, 8, 9]
    # value 0 rejected (hinge_clearance must be > 0): the window starts at 2
    assert cal.first_window(a, 0.025, lambda v: v > 0) == [2, 3, 4, 5, 6]


def test_shifted_window():
    a, c = cal.TESTS["A"], cal.TESTS["C"]
    assert cal.shifted_window(a, [7, 8, 9, 10, 11], True, ALL) == [11, 12, 13, 14, 15]
    assert cal.shifted_window(a, [7, 8, 9, 10, 11], False, ALL) == [3, 4, 5, 6, 7]
    assert cal.shifted_window(c, [3, 4, 5, 6, 7], False, ALL) == [1, 2, 3]  # stops at 1
    assert cal.shifted_window(a, [7, 8, 9, 10, 11], True, lambda v: v <= 0.3) == [11, 12, 13]
    assert "smallest" in _error(cal.shifted_window, c, [1, 2, 3, 4, 5], False, ALL)
    assert "no value" in _error(cal.shifted_window, a, [7, 8, 9, 10, 11], True, lambda v: v <= 0.25)


def test_parse_tests():
    assert cal.parse_tests("def") == "DEF" and cal.parse_tests("G") == "G"
    for bad in ("", "AA", "AH", "A B"):
        _error(cal.parse_tests, bad)


def test_start_sets_up_the_run():
    p = _preset()
    s = cal.start(p, "ABCDEF", ALL)
    assert s == {"tests": "ABCDEF", "current": "A", "sweep": [7, 8, 9, 10, 11], "written": False, "chosen": {}}
    assert p.calibration == s and cal.state(p) == s


def test_state_of_no_run():
    assert cal.state(_preset()) is None
    p = _preset()
    p.calibration = {"tests": "A", "current": None, "sweep": [], "written": True, "chosen": {"A": 9}}
    assert cal.state(p) is None  # finished


def test_pick_records_and_moves_on():
    p = _preset()
    cal.start(p, "ABCDEF", ALL)
    p.calibration["written"] = True
    assert cal.answer(p, "a8", ALL) == "pick"
    assert p.values["hinge_clearance"] == 0.175
    s = p.calibration
    assert s["chosen"] == {"A": 8} and s["current"] == "B" and s["written"] is False
    assert s["sweep"] == [3, 4, 5, 6, 7]  # hinge_dovetail_fit 0.09 -> 5


def test_the_last_pick_ends_the_run():
    p = _preset()
    cal.start(p, "F", ALL)
    p.calibration["written"] = True
    cal.answer(p, "F8", ALL)
    assert p.calibration["current"] is None and p.calibration["sweep"] == [] and cal.state(p) is None
    assert p.values["latch_detent_height"] == 0.35


def test_words_shift_the_right_way():
    for letter, tight_up in (("A", True), ("B", True), ("C", False), ("D", True), ("E", True), ("F", False),
                             ("G", False)):
        t = cal.TESTS[letter]
        for word, up in ((t.tight, tight_up), (t.loose, not tight_up)):
            p = _preset()
            cal.start(p, letter, ALL)
            before = list(p.calibration["sweep"])
            p.calibration["written"] = True
            assert cal.answer(p, word.upper(), ALL) == "shift"
            after = p.calibration["sweep"]
            assert (after[0] > before[0]) == up, (letter, word, before, after)
            assert p.calibration["written"] is False and p.calibration["current"] == letter


def test_bad_answers_change_nothing():
    p = _preset()
    cal.start(p, "ABCDEF", ALL)
    p.calibration["written"] = True
    snapshot = (dict(p.values), dict(p.calibration))
    for text, fragment in (("B4", "test A"), ("A3", "7 to 11"), ("tight", "stuck or sloppy"),
                           ("hello", "stuck or sloppy"), ("A\u00b2", "A7"), ("A", "A7")):
        assert fragment in _error(cal.answer, p, text, ALL), text
        assert (dict(p.values), dict(p.calibration)) == snapshot, text
    p.calibration["written"] = False
    assert "not written" in _error(cal.answer, p, "A8", ALL)


def test_answer_without_a_run():
    assert "no calibration run" in _error(cal.answer, _preset(), "A8", ALL)


def test_status_text():
    p = _preset()
    cal.start(p, "ABCDEF", ALL)
    text = cal.status_text(p, "/out")
    for fragment in ("test A", "hinge_clearance", "A7 = 0.15 mm", "A11 = 0.25 mm", "/out/A_07-11.stl",
                     "stuck", "sloppy", cal.TESTS["A"].check):
        assert fragment in text, (fragment, text)
    assert "no calibration run" in cal.status_text(_preset(), "/out")


def test_status_text_lists_the_choices_plainly():
    p = _preset()
    cal.start(p, "ABC", ALL)
    assert "done so far: none" in cal.status_text(p, "/out")
    p.calibration["written"] = True
    cal.answer(p, "A8", ALL)
    p.calibration["written"] = True
    cal.answer(p, "B4", ALL)
    text = cal.status_text(p, "/out")
    assert "done so far: A8, B4" in text and "{" not in text, text



def test_dialog_texts_have_no_command_line_hints():
    p = _preset()
    texts = [cal.status_text(p, "/out", gui=True)]
    cal.start(p, "F", ALL)
    texts.append(cal.status_text(p, "/out", gui=True))
    p.calibration["written"] = True
    texts.append(cal.status_text(p, "/out", gui=True))
    cal.answer(p, "F8", ALL)
    texts += [cal.status_text(p, "/out", gui=True), cal.finished_text(p, gui=True)]
    for text in texts:
        assert "--" not in text and "scripts/" not in text, text
    assert "Start run with tests G" in texts[-2] and "Calibrate preset" in texts[-1]
    assert "--tests G" in cal.finished_text(p)

def test_test_g_says_what_box_it_is_for():
    assert "printed with this preset" in cal.TESTS["G"].check


def test_sweep_files():
    assert cal.sweep_files(cal.TESTS["C"], [9, 10, 11, 12, 13]) == ("C_09-13.stl", "C_09-13_leaf.stl", "C_09-13.txt")
    assert cal.sweep_files(cal.TESTS["B"], [3, 4, 5, 6, 7])[1] == "B_03-07_hinge_rib.stl"
    assert cal.sweep_files(cal.TESTS["A"], [1, 2, 3]) == ("A_01-03.stl", None, "A_01-03.txt")


def test_a_failing_pick_changes_nothing():
    p = _preset()
    cal.start(p, "AB", ALL)
    p.calibration["written"] = True
    snapshot = copy.deepcopy((p.values, p.calibration))
    _error(cal.answer, p, "A8", lambda test, v: test.letter != "B")
    assert (p.values, p.calibration) == snapshot


def test_status_mentions_test_g_after_a_finished_run():
    p = _preset()
    cal.start(p, "F", ALL)
    p.calibration["written"] = True
    cal.answer(p, "F8", ALL)
    assert "--tests G" in cal.status_text(p, "/out")
    p.calibration["tests"] = "FG"
    assert "--tests G" not in cal.status_text(p, "/out")
    assert "--tests G" not in cal.status_text(_preset(), "/out")




@contextmanager
def _dirs():
    base, out = tempfile.mkdtemp(prefix="cal_base"), tempfile.mkdtemp(prefix="cal_out")
    try:
        yield base, out
    finally:
        shutil.rmtree(base)
        shutil.rmtree(out)


class FakeBuilder:
    """Records sweeps instead of building; fails on demand."""
    def __init__(self):
        self.calls, self.fail = [], False

    def __call__(self, preset, test, sweep, out_dir):
        if self.fail:
            from hwkan_gfbox.build import BuildError
            raise BuildError("simulated")
        self.calls.append((test.letter, list(sweep), dict(preset.values)))
        return []


def _main(args, base, out, builder):
    o, e = StringIO(), StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        code = cal.main(args, base=base, out_root=out, builder=builder)
    return code, o.getvalue(), e.getvalue()


def _saved(base, name):
    with open(presets.preset_path(name, base)) as f:
        return json.load(f)


def test_a_new_preset_starts_at_a():
    with _dirs() as (base, out):
        b = FakeBuilder()
        code, text, _ = _main(["petg"], base, out, b)
        assert code == 0 and b.calls[0][:2] == ("A", [7, 8, 9, 10, 11])
        s = _saved(base, "petg")["calibration"]
        assert s["current"] == "A" and s["written"] is True and "A7 = 0.15 mm" in text


def test_from_copies_values_and_only_for_a_new_preset():
    with _dirs() as (base, out):
        b = FakeBuilder()
        presets.save(presets.Preset("pla", "pla", dict(presets.defaults(), hinge_clearance=0.2)),
                     presets.preset_path("pla", base))
        assert _main(["pla2", "--from", "pla"], base, out, b)[0] == 0
        assert b.calls[0][1] == [7, 8, 9, 10, 11]  # centered on 0.2 -> 9
        code, _, err = _main(["pla2", "--from", "pla"], base, out, b)
        assert code == 2 and "exists" in err


def test_pick_shift_and_end():
    with _dirs() as (base, out):
        b = FakeBuilder()
        _main(["petg", "--tests", "AB"], base, out, b)
        assert _main(["petg", "stuck"], base, out, b)[0] == 0
        assert b.calls[-1][:2] == ("A", [11, 12, 13, 14, 15])
        assert _main(["petg", "A12"], base, out, b)[0] == 0
        assert b.calls[-1][0] == "B" and b.calls[-1][2]["hinge_clearance"] == 0.275
        code, text, _ = _main(["petg", "B5"], base, out, b)
        assert code == 0 and "done" in text and "make_stls.py --preset petg" in text and "--tests G" in text
        saved = _saved(base, "petg")
        assert saved["values"]["hinge_dovetail_fit"] == 0.1 and saved["calibration"]["current"] is None


def test_a_failed_build_keeps_the_answer_and_retries():
    with _dirs() as (base, out):
        b = FakeBuilder()
        _main(["petg"], base, out, b)
        b.fail = True
        code, _, err = _main(["petg", "A9"], base, out, b)
        assert code == 1 and "simulated" in err
        s = _saved(base, "petg")
        assert s["values"]["hinge_clearance"] == 0.2 and s["calibration"]["current"] == "B"
        assert s["calibration"]["written"] is False
        b.fail = False
        assert _main(["petg"], base, out, b)[0] == 0  # writes the pending sweep
        assert b.calls[-1][0] == "B" and _saved(base, "petg")["calibration"]["written"] is True
        n = len(b.calls)
        code, text, _ = _main(["petg"], base, out, b)  # now only the status
        assert code == 0 and len(b.calls) == n and "test B" in text


def test_replacing_a_run_needs_yes():
    with _dirs() as (base, out):
        b = FakeBuilder()
        _main(["petg"], base, out, b)
        _main(["petg", "A9"], base, out, b)
        n = len(b.calls)
        code, _, err = _main(["petg", "--tests", "DEF"], base, out, b)
        assert code == 2 and "--yes" in err and "A" in err and len(b.calls) == n
        assert _main(["petg", "--tests", "DEF", "--yes"], base, out, b)[0] == 0
        assert b.calls[-1][0] == "D" and _saved(base, "petg")["calibration"]["tests"] == "DEF"
        assert _main(["petg", "--restart", "--yes"], base, out, b)[0] == 0
        assert b.calls[-1][0] == "D"  # same tests over


def test_status_only_and_no_run():
    with _dirs() as (base, out):
        b = FakeBuilder()
        presets.save(presets.Preset("pla", "pla", presets.defaults()), presets.preset_path("pla", base))
        code, text, _ = _main(["pla"], base, out, b)
        assert code == 0 and "no calibration run" in text and not b.calls
        assert _main(["pla", "--tests", "G"], base, out, b)[0] == 0  # no run in progress: no --yes needed
        assert b.calls[-1][0] == "G"


def test_bad_arguments():
    with _dirs() as (base, out):
        b = FakeBuilder()
        for args, fragment in ((["petg", "A8"], "no such preset"), ([], "usage"),
                               (["petg", "--tests", "AH"], "tests: expected letters"), (["petg", "A8", "--tests", "B"], "usage"),
                               (["petg", "--bogus"], "usage")):
            code, _, err = _main(args, base, out, b)
            assert code == 2 and fragment in err, (args, err)


def test_a_path_preset():
    with _dirs() as (base, out):
        b = FakeBuilder()
        path = os.path.join(base, "mine.json")
        assert _main([path], base, out, b)[0] == 0
        assert json.load(open(path))["calibration"]["current"] == "A"
        code, text, _ = _main([path], base, out, b)
        assert os.path.join(out, "mine") in text


def test_end_to_end_with_real_builds():
    """Start (A's sweep) and a pick (B's sweep), really built: the files, the
    labels' text file and the preset after each step."""
    with _dirs() as (base, out):
        assert _main(["e2e"], base, out, None)[0] == 0
        d = os.path.join(out, "e2e")
        assert sorted(os.listdir(d)) == ["A_07-11.stl", "A_07-11.txt"]
        assert "A9 = 0.2 mm" in open(os.path.join(d, "A_07-11.txt")).read()
        assert _main(["e2e", "A9"], base, out, None)[0] == 0
        assert {"B_03-07.stl", "B_03-07_hinge_rib.stl", "B_03-07.txt"} <= set(os.listdir(d))
        txt = open(os.path.join(d, "B_03-07.txt")).read()
        assert "hinge_detent_height = 0" in txt and "hinge_clearance = 0.2" in txt
        assert _saved(base, "e2e")["calibration"]["chosen"] == {"A": 9}


def test_default_has_no_file_for_a_run_but_has_a_status():
    with _dirs() as (base, out):
        b = FakeBuilder()
        for extra in (["--tests", "A"], ["--restart"]):
            code, _, err = _main(["default"] + extra, base, out, b)
            assert code == 2 and "built-in" in err and not b.calls, (extra, err)
        code, text, _ = _main(["default"], base, out, b)
        assert code == 0 and "no calibration run" in text


def test_a_shipped_preset_is_not_calibrated_in_place():
    with _dirs() as (base, out):
        b = FakeBuilder()
        code, _, err = _main(["Tight", "--tests", "A"], base, out, b)
        assert code == 2 and "ships with the addon" in err and "--from Tight" in err and not b.calls, err
        assert _main(["tight2", "--from", "Tight"], base, out, b)[0] == 0 and b.calls


def test_from_needs_a_name():
    with _dirs() as (base, out):
        code, _, err = _main(["petg", "--from"], base, out, FakeBuilder())
        assert code == 2 and "usage" in err and not os.path.exists(presets.preset_path("petg", base))


def test_an_answer_for_a_missing_preset():
    with _dirs() as (base, out):
        code, _, err = _main(["petgg", "A8"], base, out, FakeBuilder())
        assert code == 2 and "no such preset 'petgg'" in err
        assert not os.path.exists(presets.preset_path("petgg", base))


def test_restart_needs_yes_only_while_running():
    with _dirs() as (base, out):
        b = FakeBuilder()
        _main(["petg", "--tests", "A"], base, out, b)
        n = len(b.calls)
        code, _, err = _main(["petg", "--restart"], base, out, b)
        assert code == 2 and "--yes" in err and len(b.calls) == n
        _main(["petg", "A9"], base, out, b)  # the run ends
        assert _main(["petg", "--restart"], base, out, b)[0] == 0 and b.calls[-1][0] == "A"


def test_save_leaves_no_temp_file():
    with _dirs() as (base, out):
        _main(["petg"], base, out, FakeBuilder())
        assert os.listdir(os.path.dirname(presets.preset_path("petg", base))) == ["petg.json"]


MALFORMED = {
    "current not a test": {"tests": "AB", "current": "Z", "sweep": [7], "written": True, "chosen": {}},
    "current not in tests": {"tests": "AB", "current": "C", "sweep": [7], "written": True, "chosen": {}},
    "no sweep": {"tests": "AB", "current": "A", "written": True, "chosen": {}},
    "empty sweep": {"tests": "AB", "current": "A", "sweep": [], "written": True, "chosen": {}},
    "no written": {"tests": "AB", "current": "A", "sweep": [7], "chosen": {}},
    "no chosen": {"tests": "AB", "current": "A", "sweep": [7], "written": True},
    "bad tests": {"tests": "AXB", "current": "A", "sweep": [7], "written": True, "chosen": {}},
    "no tests": {"current": "A", "sweep": [7], "written": True, "chosen": {}},
}


def _malformed_preset(base, section):
    path = presets.preset_path("bad", base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"format": presets.FORMAT, "values": {}, "calibration": section}, f)


def test_malformed_section_is_a_param_error():
    for what, section in MALFORMED.items():
        p = _preset()
        p.calibration = section
        msg = _error(cal.state, p)
        assert "preset" in msg and "malformed" in msg and "--tests LETTERS --yes" in msg, (what, msg)


def test_malformed_section_exits_2_and_can_be_replaced():
    for what, section in MALFORMED.items():
        with _dirs() as (base, out):
            _main(["bad", "--tests", "A"], base, out, FakeBuilder())  # makes the file
            _malformed_preset(base, section)
            b = FakeBuilder()
            for args in (["bad"], ["bad", "A8"], ["bad", "--restart"], ["bad", "--tests", "DE"]):
                code, _, err = _main(args, base, out, b)
                assert code == 2 and "malformed" in err and not b.calls, (what, args, err)
            assert _main(["bad", "--tests", "DE", "--yes"], base, out, b)[0] == 0, what
            assert b.calls[-1][0] == "D" and _saved(base, "bad")["calibration"]["tests"] == "DE"
            _malformed_preset(base, section)
            assert _main(["bad", "--restart", "--yes"], base, out, b)[0] == 0, what
            same = "AB" if section.get("tests") == "AB" else "ABCDEF"  # restart keeps valid tests
            assert b.calls[-1][0] == "A" and _saved(base, "bad")["calibration"]["tests"] == same, what


def test_write_pending_saves_before_and_after_the_build():
    base = tempfile.mkdtemp()
    try:
        path = presets.new("petg", base=base)
        p = presets.load("petg", base)
        cal.start(p, "AB", lambda test, value: True)
        seen = []

        def builder(preset, test, sweep, out_dir):
            seen.append(presets.load(path).calibration["current"])  # saved before the build
            return [os.path.join(out_dir, "x.stl")]

        assert cal.write_pending(p, path, "/out", builder) == ["/out/x.stl"]
        assert seen == ["A"] and presets.load(path).calibration["written"] is True
    finally:
        shutil.rmtree(base)


def test_write_pending_keeps_the_run_when_the_build_fails():
    base = tempfile.mkdtemp()
    try:
        path = presets.new("petg", base=base)
        p = presets.load("petg", base)
        cal.start(p, "AB", lambda test, value: True)

        def builder(*_):
            raise RuntimeError("boom")

        try:
            cal.write_pending(p, path, "/out", builder)
        except RuntimeError:
            pass
        saved = presets.load(path).calibration
        assert saved["current"] == "A" and saved["written"] is False
    finally:
        shutil.rmtree(base)
