# Developing and the command line

The workbench (see the [README](README.md)) is the normal way to use the
box. This file is for running the generator without the GUI, as FreeCAD
macros, and for working on it.

The package `hwkan_gfbox` builds the whole FreeCAD document from scratch,
driven by its parameter sheets, and exports print-ready STLs. `scripts/`
holds thin entry points; `scripts/fc.sh` runs them with FreeCAD headless.

## Setup

The scripts run FreeCAD headless through `scripts/fc.sh`, which uses
`$FREECAD` (path to `freecadcmd` or to a FreeCAD AppImage) or else
`freecadcmd` on your PATH:

    export FREECAD=~/app/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage

## Export STLs from the command line

    scripts/fc.sh scripts/make_stls.py                              # default 3x2x6 box -> build/stl/
    scripts/fc.sh scripts/make_stls.py --set gf_x=4 --set gf_y=3    # another size
    scripts/fc.sh scripts/make_stls.py --part lid --fine            # one part, finer mesh
    scripts/fc.sh scripts/make_stls.py --preset prusa-petg          # your printer's tolerances

Files are named after the grid size (`lid_4x3x6.stl`) and are already
oriented for printing: put them on the bed as they are. Both print without
supports; the lid prints open side down, standing on its rim and feet.

The lid STL also holds one free hinge leaf per hinge, printed in place next
to the lid's back. After printing, swing each leaf down past the lid's
rim (toward the side that lay on the bed) until it hangs with its flat
side toward the box; lowering the lid onto the bottom slides the leaves'
dovetails into the slots in the hinge ribs, until a notch in each leaf
snaps over the nub above its slot (`hinge_detent_height` sets how hard). The leaf ends sit
only `hinge_clearance` from the lid's knuckles all the way down to the bed, so
a strong first-layer squish (elephant's foot) can weld them together:
reduce the first-layer squish, or break them free after printing.

`latch.stl` is one latch; see Lock below. Its name does not depend on the
grid size.

`build_info.json` next to them records every parameter value, the FreeCAD
version and the git commit. It describes the most recent export run, so after
exporting single parts with different parameters it only matches the files
from that run.

## Lock

One latch per lock on the front wall (`lock_count`, centered in equal wall
segments, at most one per grid unit). The lid carries a lock lip (a block on
its front face, with a round channel in its top) and the bottom a pad on
its rim band; the pad's top is flush with the parting line, so the lid's
lip rests on the pad. Both are part of the lid and bottom STLs.

`latch.stl` is one latch (base, lever and hook, printed in place with
D-shaped through-axles); print it once per lock. To fit it: slide the base
up into the pad's dovetail slot from below until it snaps over the nub at
the slot's foot (no glue; `latch_detent_height` sets how hard it snaps), then swing the
hook over the lip's channel and press the lever shut. The latch is over
center and draws the hook bar into the channel: its pull (`latch_preload`)
presses the lid onto the bottom, so it works the same for every box
height. The minimum height is 3 units (`gf_z_units` >= 3): a lower box has
no room for the lever.

## Parameters

All parameters are defined in `hwkan_gfbox/params.py`, in tiers: the inputs
and the preset values (listed in the README's Reference section), and
design constants, Gridfinity constants and derived values. The inputs say
what box you get; the preset values depend on your printer and material and
come from a **preset**. Lengths are in mm. Everything else is on the
`Internal` sheet: design constants can be set with `--set`, with a warning,
but the model is not guaranteed to rebuild correctly when they change.

## Presets from the command line

A preset is a JSON file holding the tolerance and fit values above, e.g. one
per printer and material:

    {"format": 1, "note": "Prusa MK4, PETG", "values": {"hinge_clearance": 0.15, "latch_clearance": 0.2}}

Values it leaves out are the defaults. Presets live in FreeCAD's user data
directory (`hwkan_gfbox/presets/NAME.json` under it); `default` is built in.
The addon also ships `Tight` (tighter hinge, dovetail and latch fits, for a
well-tuned printer) and `Loose` (looser ones, for a printer that runs
tight), in `hwkan_gfbox/resources/presets/`. Shipped presets are
read-only and update with the addon; a preset of yours with the same name
is used instead.

    scripts/fc.sh scripts/presets.py list                    # the presets you have
    scripts/fc.sh scripts/presets.py new prusa-petg          # a copy of default to edit
    scripts/fc.sh scripts/presets.py path prusa-petg         # where its file is

Choose one with `--preset NAME` (or `--preset path/to/file.json`) on
`build_box.py`, `make_stls.py` and `make_test_prints.py` (which takes no `--set`). `--set` can't
change a preset's values: edit the preset instead. In the FreeCAD document
the `Params` sheet holds the inputs and the preset's name (the `preset`
cell); the `Preset` sheet shows the values the box was built with. Every
build writes them from the preset file, so edit the file, not those cells.
If the file is gone (a document from another computer), the rebuild keeps
the values on the `Preset` sheet; an empty `preset` cell (no preset) keeps
them too. A name typed into the `preset` cell that doesn't exist is an error
(the `Preset` sheet records which preset its values came from, so a typo is
not mistaken for a moved document).

## In the FreeCAD GUI (macros, for development)

The addon's workbench is the normal way to work in the GUI; from a checkout the
scripts also run as macros:

1. File > Open `scripts/edit_params.py` (opens it in the macro editor),
   then Macro > Execute macro. A `hwkan_gfbox` document holding only the
   `Params` spreadsheet opens: edit the values there (the inputs, and the
   `preset` cell to choose a preset; nothing is built
   yet, so editing is instant). If a generated box is open, it is
   replaced, keeping its inputs and preset.
2. Open and execute `scripts/build_box.py` the same way: it builds the
   box from the open document's inputs and preset (or from the defaults if
   none is open) and shows it. To change the box, run `edit_params.py`
   again rather than editing the sheet of the built box: every edit
   there recomputes the whole box, and a recompute does not give the
   right box anyway (the fillets and chamfers pick their edges when the
   model is built); `build_box.py` must rebuild it.
3. File > Open `scripts/make_stls.py`, then Macro > Execute macro:
   exports all parts of the generated document to `build/stl/`.

The document is always generated: changes made by hand in the GUI are lost
on the next build. To save the model file headless:

    scripts/fc.sh scripts/build_box.py [--set NAME=VALUE ...] [--out build/box.FCStd]

## Test prints from the command line

Four small parts that test a preset (your printer and material's gaps)
without printing a box: the hinge and the lock, cut from a small box built
with the default inputs and that preset:

    scripts/fc.sh scripts/make_test_prints.py [--preset NAME|PATH] [--out build/test_prints] [--fine]

writes `hinge_lid` (a lid strip with the leaf printed in place), `hinge_rib`
(the leaf's dovetail slot), `latch` (base, lever and hook printed in place)
and `lock_front` (the lock pad with the latch base's dovetail slot and, on
it, the lid's lip, as one part), plus `build_info.json`. Slide the leaf into
the rib and the latch base into the pad, then close the latch over the lip.
In the GUI, the *Test prints* command asks for the preset (the open box's
first) and the folder. To find a preset's values, use *Calibrate*.

## Calibration from the command line

A guided sequence of test prints that fills a preset for your printer and
material. Each run writes one sweep (five copies of a piece, engraved on
their underside with a label such as `B4`) and exits; print it, then tell
the script which piece was best:

    scripts/fc.sh scripts/calibrate.py prusa-petg          # new preset: writes test A's sweep
    scripts/fc.sh scripts/calibrate.py prusa-petg A8       # A8 was best: records it, writes test B
    scripts/fc.sh scripts/calibrate.py prusa-petg stuck    # all too tight: test A again, shifted
    scripts/fc.sh scripts/calibrate.py prusa-petg          # where you are, what to print, how to answer

| Test | Value | Print | Too tight / too loose |
|---|---|---|---|
| A | `hinge_clearance` | lid strip with its leaf printed in place | `stuck` / `sloppy` |
| B | `hinge_dovetail_fit` | leaves, and one rib with its slot | `tight` / `loose` |
| C | `hinge_detent_height` | ribs with their nub, and one leaf | `hard` / `weak` |
| D | `latch_clearance` | latches printed in place | `stuck` / `sloppy` |
| E | `latch_dovetail_fit` | latch bases, and one pad | `tight` / `loose` |
| F | `latch_detent_height` | pads with their nub, and one base | `hard` / `weak` |
| G | `latch_preload` | complete latches without the base's key, to try on a printed box or `lock_front` | `hard` / `weak` |

Each test uses the values chosen before it. A label's number is a fixed
value: number 1 is 0 mm, each number one step more (0.025 mm for the
clearances, 0.05 mm for the detents and the preload). The files go to
`build/calibration/NAME/`, with a text file per sweep listing what each
label means. A number whose value the generator rejects is left out of a
sweep, so its labels can have gaps. `--from OTHER` starts a new preset from another one's values,
`--tests DEF` runs only some tests, `--restart` the same tests over (`--yes`
replaces a run in progress). An existing preset with no run in progress
needs `--tests` or `--restart` to start one; without them the script only
prints its status. G is not part of the default run: print a box, or just
`lock_front.stl` from `make_test_prints.py`, with the preset first, then
`--tests G`; the test latches slide in and out of its pads past the
detent, so you can try them all. The wall strips (lid strip,
rib, pad) carry a thin tab on their inner side for the label.

## Platforms

Tested on Linux. Windows: tested by hand. macOS: untested. The addon needs no
shell; the headless `scripts/fc.sh` needs bash (macOS has it; on Windows use
the addon or the GUI macros).

## Checks

    scripts/fc.sh scripts/run_tests.py   # unit and geometry tests
    scripts/fc.sh scripts/verify.py      # geometry checks over a sweep of sizes and tolerances
