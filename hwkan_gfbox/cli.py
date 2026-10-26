"""Command-line options shared by the scripts: --preset and --set."""
from hwkan_gfbox import presets
from hwkan_gfbox.params import DEFAULT_PRESET
from hwkan_gfbox.sheet import ParamError


def parse_overrides(args, base=None):
    """Take --preset NAME|PATH and --set NAME=VALUE out of args.

    Returns (overrides, preset, remaining_args): overrides are the --set
    (name, value) pairs in command-line order; preset is the loaded
    presets.Preset (the built-in default without --preset). The preset's
    values can't be --set: a rebuild reloads them from the preset.
    """
    sets, rest, ref = [], [], DEFAULT_PRESET
    it = iter(args)
    for arg in it:
        if arg == "--params":
            raise ParamError('--params is gone: use --preset NAME|PATH (a preset file is '
                             '{"format": 1, "values": {...}}; see README, Presets)')
        if arg == "--preset":
            ref = next(it, None)
            if not ref:
                raise ParamError("--preset expects a preset name or a JSON file")
        elif arg == "--set":
            item = next(it, None)
            if item is None or "=" not in item:
                raise ParamError(f"--set expects NAME=VALUE, got {item!r}")
            name, val = item.split("=", 1)
            name = name.strip()
            if name in presets.NAMES:
                raise ParamError(f"{name} comes from the preset; edit the preset "
                                 "(scripts/presets.py path NAME) or use another")
            sets.append((name, val.strip()))
        else:
            rest.append(arg)
    return sets, presets.load(ref, base), rest
