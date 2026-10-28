"""Presets: named sets of the printer- and material-dependent values (the
tolerance and fit tiers), one JSON file each in the user's FreeCAD data
directory (spec: docs/superpowers/specs/2026-10-12-presets-design.md).

    {"format": 1, "note": "...", "values": {"hinge_clearance": 0.15, ...},
     "calibration": ...}

A preset's name is its file name without .json. The built-in preset
"default" is the defaults in params.py and has no file. Shipped presets
(SHIPPED_DIR, in the addon) are read-only and found after the user's: a
user preset of the same name wins. Wherever a name is accepted, a path
works too (see is_path).
"""
import json
import math
import os
import sys
from dataclasses import dataclass

import FreeCAD as App

from hwkan_gfbox.params import DEFAULT_PRESET, PARAMS, PRESET_TIERS
from hwkan_gfbox.sheet import ParamError

DEFAULT = DEFAULT_PRESET
FORMAT = 1
NAMES = [name for name, _, tier, _ in PARAMS if tier in PRESET_TIERS]
_KEYS = ("format", "note", "values", "calibration")
SHIPPED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "presets")


class PresetNotFound(ParamError):
    """No preset by that name, or no file at that path."""


@dataclass
class Preset:
    name: str           # the file name without .json, or "default"
    ref: str            # what the Params sheet's preset cell holds: the name, or an absolute path
    values: dict        # every name in NAMES -> mm
    note: str = ""
    calibration: object = None  # kept as read; the calibration suite defines it


def defaults():
    """{name: mm} for every preset value, from params.py."""
    return {name: float(val.lstrip("=").split()[0]) for name, val, tier, _ in PARAMS if tier in PRESET_TIERS}


def preset_dir(base=None):
    """The preset directory; base is the user data dir (default: FreeCAD's)."""
    return os.path.join(App.getUserAppDataDir() if base is None else base, "hwkan_gfbox", "presets")


def is_path(ref):
    """True if ref names a file rather than a preset in the preset directory."""
    return "/" in ref or os.sep in ref or ref.endswith(".json")


def preset_path(name, base=None):
    """Where the user's preset NAME's file is (whether or not it exists)."""
    if name == DEFAULT:
        raise ParamError("'default' is the built-in preset (the values in params.py); it has no file")
    if is_path(name):
        return os.path.abspath(os.path.expanduser(name))
    return os.path.join(preset_dir(base), name + ".json")


def _check_dir(directory):
    shadow = os.path.join(directory, DEFAULT + ".json")
    if os.path.isfile(shadow):
        raise ParamError(f"{shadow}: 'default' is the built-in preset; rename this file")


def resolve(ref, base=None):
    """The file of a preset name or path, or None for the built-in default.
    Raises PresetNotFound if there is no such preset."""
    if is_path(ref):
        path = os.path.abspath(os.path.expanduser(ref))
        if not os.path.isfile(path):
            raise PresetNotFound(f"preset file not found: {path}")
        return path
    directory = preset_dir(base)
    _check_dir(directory)
    if ref == DEFAULT:
        return None
    for path in (os.path.join(directory, ref + ".json"), os.path.join(SHIPPED_DIR, ref + ".json")):
        if os.path.isfile(path):
            return path
    known = ", ".join(name for name, _ in list_presets(base))
    raise PresetNotFound(f"no preset '{ref}' in {directory} (presets: {known})")


def is_shipped(path):
    """True if path is a shipped preset's file."""
    return path is not None and os.path.dirname(os.path.abspath(path)) == os.path.abspath(SHIPPED_DIR)


def read_only(ref, base=None):
    """True for the built-in default and a shipped preset (not shadowed by a
    user preset); False for a user preset or a missing one."""
    try:
        path = resolve(ref, base)
    except PresetNotFound:
        return False
    return path is None or is_shipped(path)


def _number(path, key, val):
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ParamError(f"{path}: '{key}' must be a number in mm (got {val!r})")
    return float(val)


def load(ref, base=None):
    """The preset named (or at the path) ref, every value filled in: a value
    the file lacks is today's default. Raises ParamError (PresetNotFound if
    it doesn't exist)."""
    path = resolve(ref, base)
    if path is None:
        return Preset(DEFAULT, DEFAULT, defaults())
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ParamError(f"cannot read preset {path}: {e}")
    if not isinstance(data, dict):
        raise ParamError(f"{path}: a preset must be a JSON object")
    unknown = sorted(set(data) - set(_KEYS))
    if unknown:
        raise ParamError(f"{path}: unknown key(s) {', '.join(unknown)}; a preset has {', '.join(_KEYS)}")
    fmt = data.get("format")
    if isinstance(fmt, int) and not isinstance(fmt, bool) and fmt > FORMAT:
        raise ParamError(f"{path}: format {fmt} was made by a newer version of hwkan_gfbox (this one reads {FORMAT})")
    if fmt != FORMAT or isinstance(fmt, bool):
        raise ParamError(f"{path}: 'format' must be {FORMAT} (got {fmt!r})")
    note = data.get("note", "")
    if not isinstance(note, str):
        raise ParamError(f"{path}: 'note' must be text")
    given = data.get("values", {})
    if not isinstance(given, dict):
        raise ParamError(f"{path}: 'values' must be an object of name: mm")
    values = defaults()
    for key, val in given.items():
        if key not in values:
            raise ParamError(f"{path}: '{key}' is not a preset value; a preset holds {', '.join(NAMES)}")
        values[key] = _number(path, key, val)
    name = os.path.splitext(os.path.basename(path))[0]
    return Preset(name, path if is_path(ref) else ref, values, note, data.get("calibration"))


def save(preset, path):
    """Write preset to path with all its values (so it doesn't follow later
    changes of the defaults) and its calibration state."""
    data = {"format": FORMAT, "note": preset.note,
            "values": {name: preset.values[name] for name in NAMES},
            "calibration": {} if preset.calibration is None else preset.calibration}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"  # write beside it, then replace: a kill can't leave half a preset
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def overrides(preset):
    """The preset's values as (name, "value mm") pairs, what build() takes."""
    return [(name, f"{preset.values[name]!r} mm") for name in NAMES]


def list_presets(base=None):
    """(name, note) for "default" and every preset in the preset directory
    and the shipped ones (a user preset hides a shipped one of its name)."""
    directory = preset_dir(base)
    _check_dir(directory)
    files = {}
    for folder in (SHIPPED_DIR, directory):  # the user's last: theirs win
        if os.path.isdir(folder):
            for fname in os.listdir(folder):
                if fname.endswith(".json") and fname != DEFAULT + ".json":
                    files[fname[:-len(".json")]] = os.path.join(folder, fname)
    found = [(DEFAULT, "built-in: the defaults in hwkan_gfbox/params.py")]
    for name in sorted(files):
        try:
            note = load(files[name]).note
        except ParamError as e:
            note = f"(unreadable: {e})"
        found.append((name, note))
    return found


def new(name, source=DEFAULT, base=None):
    """Write a full preset NAME in the preset directory (every value, empty
    calibration state) copied from source (a name or path). Returns its path."""
    if not name or name == DEFAULT or is_path(name):
        raise ParamError(f"a preset name can't be empty, 'default', contain '/' or end in .json (got {name!r})")
    path = preset_path(name, base)
    if os.path.exists(path):
        raise ParamError(f"{path} exists already")
    src = load(source, base)
    save(Preset(name, name, dict(src.values), src.note), path)
    return path


USAGE = """usage: scripts/fc.sh scripts/presets.py list
       scripts/fc.sh scripts/presets.py new NAME [--from NAME|PATH]
       scripts/fc.sh scripts/presets.py path NAME"""


def main(args, base=None):
    """Entry point of scripts/presets.py."""
    try:
        if args == ["list"]:
            for name, note in list_presets(base):
                print(f"{name:20} {note}".rstrip())
        elif len(args) in (2, 4) and args[0] == "new" and (len(args) == 2 or args[2] == "--from"):
            print(f"wrote {new(args[1], args[3] if len(args) == 4 else DEFAULT, base)}")
        elif len(args) == 2 and args[0] == "path":
            print(preset_path(args[1], base))
        else:
            print(USAGE, file=sys.stderr)
            return 2
    except ParamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
