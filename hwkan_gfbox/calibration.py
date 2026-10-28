"""The calibration suite: guided test-print sweeps that fill a preset (spec:
docs/superpowers/specs/2026-10-12-calibration-suite-design.md).

Each test (A-G) sweeps one value; a piece is engraved with its label, the
test's letter and a number: value = (number - 1) * step. The run's state is
the preset's "calibration" section:
    {"tests": "ABCDEF", "current": "C", "sweep": [9, ..., 13],
     "written": true, "chosen": {"A": 8, "B": 4}}
"""
import os
import sys
from dataclasses import dataclass

from hwkan_gfbox import presets
from hwkan_gfbox.sheet import ParamError

WINDOW = 5  # numbers per sweep
SHIFT = 4   # a too-tight / too-loose answer moves the window this far (its edge is printed again)
DEFAULT_TESTS = "ABCDEF"


@dataclass(frozen=True)
class Test:
    letter: str
    param: str
    step: float       # mm per number
    piece: str        # the swept piece (testprints.PIECES), engraved
    partner: object   # the fixed piece printed once (None: none)
    settings: tuple   # (name, value) overrides for this test's builds
    tight: str        # the answer for "every piece too tight"
    loose: str        # ... "every piece too loose"
    tight_up: bool    # True: too tight means a bigger value
    check: str        # what to look for on the print


TESTS = {t.letter: t for t in (
    Test("A", "hinge_clearance", 0.025, "hinge_lid", None, (), "stuck", "sloppy", True,
         "Break each leaf free and swing it: pick the smallest number that swings freely."),
    Test("B", "dovetail_clearance", 0.025, "leaf", "hinge_rib", (("hinge_detent", "0"),), "tight", "loose", True,
         "Slide each leaf into the rib's slot: pick the one that slides in without force and without play."),
    Test("C", "hinge_detent", 0.05, "hinge_rib", "leaf", (), "hard", "weak", False,
         "Push the leaf into each rib: pick the one that snaps in firmly and still goes in by hand."),
    Test("D", "latch_clearance", 0.025, "latch", None, (), "stuck", "sloppy", True,
         "Work each latch: pick the smallest number whose lever and hook move freely."),
    Test("E", "lock_dovetail_clearance", 0.025, "latch_base", "lock_pad", (("lock_detent", "0"),), "tight",
         "loose", True,
         "Slide each base up into the pad's slot: pick the one that slides without force and without play."),
    Test("F", "lock_detent", 0.05, "lock_pad", "latch_base", (), "hard", "weak", False,
         "Push the base into each pad: pick the one that clicks in firmly and still goes in by hand."),
    Test("G", "hook_preload", 0.05, "latch_keyless", None, (), "hard", "weak", False,
         "These latches are fitted to a box printed with this preset: fit each to it and close it, "
         "and pick the one that holds the lid tight and still closes by hand."),
)}


def value_of(number, step):
    """The value of a number: (number - 1) * step, in mm."""
    return round((number - 1) * step, 6)


def number_of(value, step):
    """The number nearest to value."""
    return int(round(value / step)) + 1


def _valid_numbers(test, numbers, valid):
    return [n for n in numbers if n >= 1 and valid(value_of(n, test.step))]


def first_window(test, current_value, valid):
    """WINDOW numbers centered on current_value's number; if some are below
    1 or rejected, the window moves away from that limit (as little as
    possible); failing that, the centered window's valid numbers."""
    center = number_of(current_value, test.step)
    for offset in sorted(range(-WINDOW, WINDOW + 1), key=lambda k: (abs(k), -k)):
        numbers = list(range(center - WINDOW // 2 + offset, center + WINDOW // 2 + 1 + offset))
        if _valid_numbers(test, numbers, valid) == numbers:
            return numbers
    numbers = _valid_numbers(test, range(center - WINDOW // 2, center + WINDOW // 2 + 1), valid)
    if not numbers:
        raise ParamError(f"test {test.letter}: no value near {current_value:g} mm is accepted")
    return numbers


def shifted_window(test, sweep, up, valid):
    """The window SHIFT numbers up (or down) from sweep, its edge number
    included again; never below 1; rejected values dropped."""
    if up:
        numbers = range(sweep[-1], sweep[-1] + WINDOW)
    else:
        if sweep[0] <= 1:
            raise ParamError(f"test {test.letter}: the sweep already starts at the smallest value (number 1 = 0 mm)")
        numbers = range(max(1, sweep[0] - SHIFT), sweep[0] + 1)
    numbers = _valid_numbers(test, numbers, valid)
    if not set(numbers) - set(sweep):  # nothing beyond the edge
        raise ParamError(f"test {test.letter}: no value {'above' if up else 'below'} "
                         f"{value_of(sweep[-1] if up else sweep[0], test.step):g} mm is accepted")
    return numbers


def parse_tests(text):
    """--tests: letters from TESTS, each at most once, in the given order."""
    letters = text.strip().upper()
    if not letters or any(c not in TESTS for c in letters) or len(set(letters)) != len(letters):
        raise ParamError(f"tests: expected letters from {''.join(TESTS)}, each at most once (got {text!r})")
    return letters


def _malformed(preset, what):
    return ParamError(f"preset '{preset.name}': its calibration section is malformed ({what}); "
                      f"start a new run over it (command line: --tests LETTERS --yes)")


def state(preset):
    """The run in progress (the preset's calibration section), or None.
    Raises ParamError if the section (hand-edited?) is malformed."""
    s = preset.calibration
    if not isinstance(s, dict) or not s.get("current"):
        return None
    tests = s.get("tests")
    if not isinstance(tests, str) or not tests or any(c not in TESTS for c in tests) or len(set(tests)) != len(tests):
        raise _malformed(preset, f"tests {tests!r} is not letters from {''.join(TESTS)}")
    if s["current"] not in tests:
        raise _malformed(preset, f"current test {s['current']!r} is not one of the tests {tests}")
    sweep = s.get("sweep")
    if not isinstance(sweep, list) or not sweep or not all(isinstance(n, int) and not isinstance(n, bool) for n in sweep):
        raise _malformed(preset, "sweep is not a list of numbers")
    if not isinstance(s.get("written"), bool):
        raise _malformed(preset, "written is missing")
    if not isinstance(s.get("chosen"), dict):
        raise _malformed(preset, "chosen is missing")
    return s


def start(preset, tests, valid):
    """A new run of tests (replacing any other) at its first test's first
    window. valid(test, value) -> bool. Returns the state."""
    first = TESTS[tests[0]]
    preset.calibration = {"tests": tests, "current": first.letter,
                          "sweep": first_window(first, preset.values[first.param], lambda v: valid(first, v)),
                          "written": False, "chosen": {}}
    return preset.calibration


def _expected(test, sweep):
    return (f"a label {test.letter}{sweep[0]} to {test.letter}{sweep[-1]} "
            f"(numbers {sweep[0]} to {sweep[-1]}), {test.tight} or {test.loose}")


def answer(preset, text, valid):
    """Apply an answer about the current sweep: a label (pick) or the test's
    tight / loose word (shift). Returns "pick" or "shift". Raises ParamError
    (nothing changed) for an answer that doesn't fit the run."""
    s = state(preset)
    if s is None:
        raise ParamError("no calibration run in progress: start one with --tests or --restart")
    test, sweep = TESTS[s["current"]], s["sweep"]
    if not s["written"]:
        raise ParamError(f"test {test.letter}'s sweep was not written yet: run without an answer to write it")
    word = text.strip().lower()
    if word in (test.tight, test.loose):
        up = (word == test.tight) == test.tight_up
        s["sweep"] = shifted_window(test, sweep, up, lambda v: valid(test, v))
        s["written"] = False
        return "shift"
    label = text.strip().upper()
    letter, digits = label[:1], label[1:]
    if letter != test.letter and letter in TESTS and digits.isascii() and digits.isdigit():
        raise ParamError(f"the current test is test {test.letter}, not {letter}: answer with {_expected(test, sweep)}")
    if letter != test.letter or not (digits.isascii() and digits.isdigit()) or int(digits) not in sweep:
        raise ParamError(f"expected {_expected(test, sweep)} (got {text!r})")
    number = int(digits)
    value = value_of(number, test.step)
    rest = s["tests"][s["tests"].index(test.letter) + 1:]
    if rest:
        nxt = TESTS[rest[0]]
        nxt_sweep = first_window(nxt, dict(preset.values, **{test.param: value})[nxt.param],
                                 lambda v: valid(nxt, v))  # may raise: nothing is assigned before it
        current, sweep_after, written = nxt.letter, nxt_sweep, False
    else:
        current, sweep_after, written = None, [], True
    preset.values[test.param] = value
    s["chosen"][test.letter] = number
    s["current"], s["sweep"], s["written"] = current, sweep_after, written
    return "pick"


def sweep_files(test, sweep):
    """(plate STL, partner STL or None, value-list .txt) file names of a sweep."""
    stem = f"{test.letter}_{sweep[0]:02d}-{sweep[-1]:02d}"  # the partner is per sweep too: it follows the largest value
    return f"{stem}.stl", (f"{stem}_{test.partner}.stl" if test.partner else None), f"{stem}.txt"


# How to do things, for the command line (False) and the Calibrate dialog (True).
HINTS = {
    False: {"start": f"start one with --tests {DEFAULT_TESTS} (or --restart)", "run_g": "--tests G",
            "unwritten": "run again without an answer to write it", "answer": "answer",
            "box": "scripts/fc.sh scripts/make_stls.py --preset {ref}",
            "g": "scripts/fc.sh scripts/calibrate.py {ref} --tests G"},
    True: {"start": f"start one with Start run (tests {DEFAULT_TESTS})", "run_g": "Start run with tests G",
           "unwritten": "press Write pending sweep", "answer": "answer with a button below",
           "box": "New box with preset '{ref}', then Export STLs",
           "g": "Calibrate preset '{ref}' with tests G"},
}


def status_text(preset, out_dir, gui=False):
    """What the run is waiting for: the test, its labels in mm, the files,
    what to check and the answers; or that no run is in progress. gui: say
    how to do it in the Calibrate dialog, not on the command line."""
    hint = HINTS[gui]
    s = state(preset)
    if s is None:
        values = "\n".join(f"  {t.param} = {preset.values[t.param]:g} mm" for t in TESTS.values())
        extra = ""
        done = preset.calibration
        if (isinstance(done, dict) and done.get("current") is None and isinstance(done.get("tests"), str)
                and "G" not in done["tests"]):
            extra = (f"\ntest G ({TESTS['G'].param}) can be run on a box printed with this preset: {hint['run_g']}")
        return (f"no calibration run in progress for preset '{preset.name}'. Its values:\n{values}\n"
                f"{hint['start']}{extra}")
    test = TESTS[s["current"]]
    plate, partner, _ = sweep_files(test, s["sweep"])
    labels = "\n".join(f"  {test.letter}{n} = {value_of(n, test.step):g} mm" for n in s["sweep"])
    files = "\n".join(f"  {out_dir}/{f}" for f in (plate, partner) if f)
    chosen = ", ".join(f"{t}{n}" for t, n in s["chosen"].items()) or "none"
    written = "" if s["written"] else f"\n(not written yet: {hint['unwritten']})"
    return (f"preset '{preset.name}': test {test.letter} ({test.param}), "
            f"tests {s['tests']}, done so far: {chosen}\n"
            f"labels:\n{labels}\nfiles:\n{files}{written}\n{test.check}\n"
            f"{hint['answer']}: the best label, or '{test.tight}' (all too tight) / '{test.loose}' (all too loose)")


USAGE = """usage: scripts/fc.sh scripts/calibrate.py NAME [ANSWER] [--from OTHER] [--tests LETTERS] [--restart] [--yes]
  NAME                 status (or write a sweep that is still pending); a new preset starts at test A
  NAME B4              B4 was the best piece
  NAME stuck           every piece too tight (or the current test's other word)
  NAME --from OTHER    a new preset copied from OTHER
  NAME --tests DEF     a run of only these tests (--yes replaces a run in progress)
  NAME --restart       the same tests over (--yes replaces a run in progress)"""
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "build", "calibration")


def validator(preset):
    """valid(test, value): the generator accepts value for test's parameter
    with the test's settings (the sheets alone; no box is built)."""
    from hwkan_gfbox import testprints
    return lambda test, value: testprints.valid_value(list(test.settings), test.param, value, preset)


def build_sweep(preset, test, sweep, out_dir):
    """Write the sweep's plate, partner and text file into out_dir."""
    from hwkan_gfbox import testprints
    if not os.path.isfile(testprints.FONT):
        from hwkan_gfbox.build import BuildError
        raise BuildError(f"font not found ({testprints.FONT}): calibration pieces need their labels")
    plate, partner, txt = sweep_files(test, sweep)
    values = [value_of(n, test.step) for n in sweep]
    paths, _, info, warnings = testprints.write_sweep(
        test.param, values, [f"{test.letter}{n}" for n in sweep], test.piece, out_dir, plate,
        test.partner, partner, list(test.settings), preset)
    for warning in warnings:
        print(warning, file=sys.stderr)
    lines = [f"test {test.letter}: {test.param} (step {test.step:g} mm)", ""]
    lines += [f"{test.letter}{n} = {value_of(n, test.step):g} mm" for n in sweep]
    lines += ["", "values used (the largest swept value's build):"]
    lines += [f"{name} = {val:g}" for name, val in sorted(info["parameters"].items())]
    with open(os.path.join(out_dir, txt), "w") as f:
        f.write("\n".join(lines) + "\n")
    return paths + [os.path.join(out_dir, txt)]


def _parse(args):
    """(name, answer, from, tests, restart, yes). Raises ParamError with USAGE."""
    name = answer = source = tests = None
    restart = yes = False
    it = iter(args)
    for arg in it:
        if arg == "--from":
            source = next(it, "")
        elif arg == "--tests":
            tests = parse_tests(next(it, "") or "")
        elif arg == "--restart":
            restart = True
        elif arg == "--yes":
            yes = True
        elif arg.startswith("--") or (name is not None and answer is not None):
            raise ParamError(USAGE)
        elif name is None:
            name = arg
        else:
            answer = arg
    if name is None or (answer and (tests or restart or source)) or (tests and restart) or source == "":
        raise ParamError(USAGE)
    return name, answer, source, tests, restart, yes


def open_preset(name, source, base):
    """(preset, its file, created?) for NAME: loaded, or created from
    default / source if it doesn't exist."""
    try:
        preset = presets.load(name, base)
    except presets.PresetNotFound:
        src = presets.load(source or presets.DEFAULT, base)
        path = presets.preset_path(name, base)
        ref = path if presets.is_path(name) else name
        preset = presets.Preset(os.path.splitext(os.path.basename(path))[0], ref, dict(src.values), src.note)
        return preset, path, True
    if source:
        raise ParamError(f"preset '{name}' exists already: --from only makes a new one")
    path = presets.resolve(name, base)
    if presets.is_shipped(path):
        raise ParamError(f"'{name}' ships with the addon and is read-only: calibrate a new preset made from it "
                         f"(--from {name})")
    return preset, path, False


def write_pending(preset, path, out_dir, builder=None):
    """Write the run's current sweep: save the preset first (the answer or
    new run: a failed build keeps it), build the sweep into out_dir, mark
    it written and save again. Returns the paths written."""
    builder = builder or build_sweep
    presets.save(preset, path)
    s = state(preset)
    paths = builder(preset, TESTS[s["current"]], s["sweep"], out_dir)
    s["written"] = True
    presets.save(preset, path)
    return paths


def main(args, base=None, out_root=None, builder=None):
    """Entry point of scripts/calibrate.py (see USAGE). builder(preset, test,
    sweep, out_dir) writes a sweep (default build_sweep; tests pass a fake)."""
    from hwkan_gfbox.build import BuildError
    builder = builder or build_sweep
    try:
        name, ans, source, tests, restart, yes = _parse(args)
        preset, path, created = open_preset(name, source, base)
        out_dir = os.path.join(out_root or DEFAULT_OUT, preset.name)
        valid = validator(preset)
        try:
            running, malformed = state(preset), None
        except ParamError as e:  # --tests / --restart with --yes replace it
            running, malformed = None, e
        if malformed and not ((tests or restart) and yes):
            raise malformed
        if ans and created:
            raise ParamError(f"no such preset '{name}'; start a run with: calibrate.py {name}")
        if ans and running is None:
            raise ParamError(f"no calibration run in progress for '{name}': start one with --tests or --restart")
        if created or tests or restart:
            path = path or presets.preset_path(name, base)  # the built-in default has no file: error
            if running and not created and not yes:
                raise ParamError(f"a run of tests {running['tests']} is in progress (at test {running['current']}, "
                                 f"chosen so far: {running['chosen'] or 'none'}); add --yes to replace it")
            if restart:  # the same tests over (a malformed old section: the default ones)
                old = preset.calibration.get("tests") if isinstance(preset.calibration, dict) else None
                try:
                    tests = parse_tests(old)
                except (ParamError, AttributeError):
                    tests = None
            start(preset, tests or DEFAULT_TESTS, valid)
        elif ans:
            done = answer(preset, ans, valid)
            if state(preset) is None:
                presets.save(preset, path)
                print(finished_text(preset))
                return 0
            print(f"recorded: {ans}" if done == "pick" else f"{ans}: test {state(preset)['current']} again, shifted")
        elif running is None or running["written"]:
            print(status_text(preset, out_dir))
            return 0
        for p in write_pending(preset, path, out_dir, builder):
            print(f"wrote {p}")
        print(status_text(preset, out_dir))
    except ParamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def finished_text(preset, gui=False):
    hint, s = HINTS[gui], preset.calibration
    lines = [f"calibration of preset '{preset.name}' done (tests {s['tests']}):"]
    lines += [f"  {TESTS[t].param} = {preset.values[TESTS[t].param]:g} mm ({t}{n})" for t, n in s["chosen"].items()]
    lines.append("print a box with it: " + hint["box"].format(ref=preset.ref))
    if "G" not in s["tests"]:
        lines.append("then, to tune hook_preload on that box: " + hint["g"].format(ref=preset.ref))
    return "\n".join(lines)
