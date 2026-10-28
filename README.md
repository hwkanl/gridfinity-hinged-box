# Gridfinity hinged box (FreeCAD)

A parametric, Gridfinity-compatible storage box generated in FreeCAD.
The only requirement is FreeCAD 1.1 or newer.

Current parts: `bottom` (holds standard Gridfinity bins on built-in
baseplate pockets) and `lid` (Gridfinity feet on its underside drop into
the bins' stacking lips and keep them in place). The two are joined by
hinges: knuckles with cone pins on the lid, a free leaf per hinge whose
dovetail slides into a slot in a rib on the bottom's back wall. Over-center
draw latches on the front wall lock it (see Lock below).

## Install (FreeCAD addon)

Needs FreeCAD 1.1 or newer.

1. In FreeCAD: Tools > Addon Manager > Preferences (the gear) > Custom
   repositories > add `https://github.com/hwkanl/gridfinity-hinged-box`,
   branch `main`.
2. Install "Gridfinity Hinged Box" from the Addon Manager and restart FreeCAD.
3. Pick the "Gridfinity Hinged Box" workbench.

| Command | What it does |
|---|---|
| New box | Build a new box from its size and a preset |
| Edit box | Copy the open box's printable parts into PartDesign bodies to add your own features, then Export STLs |
| Export STLs | Write the STLs of the edited box (if it is the active document) or of the generated box |
| Presets | Make, edit and delete presets (printer/material tolerances) |
| Calibrate | Guided test-print sweeps that fill a preset with your printer's tolerances |
| Test prints | Hinge and lock test pieces, one set or a sweep of one tolerance |

Presets are kept in FreeCAD's user data directory, under
`hwkan_gfbox/presets/` (`~/.local/share/FreeCAD/v1-1/` on Linux,
`%APPDATA%\FreeCAD\v1-1\` on Windows). Each command that writes files asks
for an output folder and remembers the last one.

The rest of this README describes the box and the command line scripts, which
work from a checkout of the repository.

## Setup

The scripts run FreeCAD headless through `scripts/fc.sh`, which uses
`$FREECAD` (path to `freecadcmd` or to a FreeCAD AppImage) or else
`freecadcmd` on your PATH:

    export FREECAD=~/app/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage

## Export STLs

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
snaps over the nub above its slot (`hinge_detent` sets how hard). The leaf ends sit
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
the slot's foot (no glue; `lock_detent` sets how hard it snaps), then swing the
hook over the lip's channel and press the lever shut. The latch is over
center and draws the hook bar into the channel: its pull (`hook_preload`)
presses the lid onto the bottom, so it works the same for every box
height. The minimum height is 3 units (`gf_z_units` >= 3): a lower box has
no room for the lever.

## Parameters

These are the inputs (on the `Params` sheet) and the tolerances and fits a
preset sets (generated from `hwkan_gfbox/params.py`; regenerate with the
command in `hwkan_gfbox/tests/test_readme.py`).

| Name | Default | Meaning |
|---|---|---|
| `gf_x` | 3 | grid cells along X |
| `gf_y` | 2 | grid cells along Y |
| `gf_z_units` | 6 | bin height in 7 mm units (stacking lip not included) |
| `hinge_count` | 2 | number of hinges along the back wall (2 to gf_x, as many as fit) |
| `lock_count` | 2 | number of locks along the front wall (1 to gf_x, as many as fit) |
| `feet_xy_clearance` | 0.25 mm | lid feet shrunk by this per side vs a standard bin base |
| `feet_z_clearance` | 0.5 mm | lid feet raised by this above a seated bin base; the lid never presses on the bins |
| `lip_clearance` | 0.2 mm | gap between the rim's round bead (bottom) and its channel (lid), normal to the arc |
| `hinge_clearance` | 0.2 mm | print-in-place gap between the free leaf and the lid knuckles, pins and lid face |
| `dovetail_clearance` | 0.1 mm | gap between the leaf's dovetail sides and its slot's, normal to the sides (the slot's floor stays nominal) |
| `nub_clearance` | 0.15 mm | gap between the seated leaf's notch edge and the hinge nub's flat underside: how far the snapped leaf can lift |
| `latch_clearance` | 0.25 mm | print-in-place gap between the latch's base, lever and hook, and around their axles |
| `lock_dovetail_clearance` | 0.1 mm | gap between the latch base's dovetail and the pad's slot (sides, normal to the face, and the slot's roof) |
| `lock_seat_clearance` | 0.25 mm | gap around the hook bar in the lip's seat: the seat's curve is this much wider than the bar's round underside |
| `stack_clearance` | 0.2 mm | gap between a lid's stacking notches and the grooves under the box stacked on it, normal to their faces (and at their ends); at most about 0.28 at default sizes (the grooves stay in the wall) |
| `hook_preload` | 0.2 mm | the hook is this much shorter than at zero pressure: the latch's pull on the lid |
| `lock_detent` | 0.4 mm | the nub below the seated latch base stands this far into its dovetail's full-depth part: the snap the base clicks over (0 = no snap, the nub just touches) |
| `hinge_detent` | 0.6 mm | the nub above each hinge slot stands this far out of the slot's wide face into the leaf's notch: the snap the leaf's dovetail flexes over on the way in (0 = no snap) |

The inputs say what box you get; the tolerances and fits depend on your
printer and material and come from a **preset**. Lengths are in mm.
Everything else (design and Gridfinity constants, derived values) is on the
`Internal` sheet: design constants can be set with `--set`, with a warning,
but the model is not guaranteed to rebuild correctly when they change.

## Presets

A preset is a JSON file holding the tolerance and fit values above, e.g. one
per printer and material:

    {"format": 1, "note": "Prusa MK4, PETG", "values": {"hinge_clearance": 0.15, "lip_clearance": 0.25}}

Values it leaves out are the defaults. Presets live in FreeCAD's user data
directory (`hwkan_gfbox/presets/NAME.json` under it); `default` is built in.
The addon also ships `Tight` (tighter hinge, dovetail and latch fits, for a
well-tuned printer; `hwkan_gfbox/resources/presets/`). Shipped presets are
read-only and update with the addon; a preset of yours with the same name
is used instead.

    scripts/fc.sh scripts/presets.py list                    # the presets you have
    scripts/fc.sh scripts/presets.py new prusa-petg          # a copy of default to edit
    scripts/fc.sh scripts/presets.py path prusa-petg         # where its file is

Choose one with `--preset NAME` (or `--preset path/to/file.json`) on
`build_box.py`, `make_stls.py` and `make_test_prints.py`. `--set` can't
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

## Test prints

Small prints of only the hinge and only the lock, cut from a box built with
your values, to tune the printer-dependent gaps before printing a box:

    scripts/fc.sh scripts/make_test_prints.py [--preset NAME] [--set NAME=VALUE ...] [--out build/test_prints]

writes one set: `hinge_lid` (lid strip with the leaf printed in place),
`hinge_rib` (the leaf's slot), `leaf`, `latch` (printed in place),
`lock_pad` (the latch base's slot) and `latch_base`. To compare values of
one tolerance on one plate:

    scripts/fc.sh scripts/make_test_prints.py --sweep latch_clearance=0.15,0.2,0.25

repeats only the piece that tolerance affects, each copy engraved with its
value on its underside (the bed face, mirrored so it reads from below). The
pieces are `hinge_clearance`: `hinge_lid`; `latch_clearance`: `latch`;
`dovetail_clearance`: `leaf`, plus one `hinge_rib`; `lock_dovetail_clearance`:
`latch_base`, plus one `lock_pad`. In the GUI, execute
`scripts/make_test_prints.py` as a macro: it uses the open document's inputs and preset values and asks for the sweep and the output folder in a dialog. Every value is checked
before anything is built; one the generator rejects stops the run with the
reason (`dovetail_clearance` must stay below about 0.35 mm at the default
`hinge_clearance`; the dialog only suggests values the generator accepts).

## Calibration

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
| B | `dovetail_clearance` | leaves, and one rib with its slot | `tight` / `loose` |
| C | `hinge_detent` | ribs with their nub, and one leaf | `hard` / `weak` |
| D | `latch_clearance` | latches printed in place | `stuck` / `sloppy` |
| E | `lock_dovetail_clearance` | latch bases, and one pad | `tight` / `loose` |
| F | `lock_detent` | pads with their nub, and one base | `hard` / `weak` |
| G | `hook_preload` | complete latches without the base's key, to try on a printed box | `hard` / `weak` |

Each test uses the values chosen before it. A label's number is a fixed
value: number 1 is 0 mm, each number one step more (0.025 mm for the
clearances, 0.05 mm for the detents and the preload). The files go to
`build/calibration/NAME/`, with a text file per sweep listing what each
label means. A number whose value the generator rejects is left out of a
sweep, so its labels can have gaps. `--from OTHER` starts a new preset from another one's values,
`--tests DEF` runs only some tests, `--restart` the same tests over (`--yes`
replaces a run in progress). An existing preset with no run in progress
needs `--tests` or `--restart` to start one; without them the script only
prints its status. G is not part of the default run: print a box with the
preset first, then `--tests G`; the test latches slide in and out of its
pads past the detent, so you can try them all. The wall strips (lid strip,
rib, pad) carry a thin tab on their inner side for the label.

## Platforms

Tested on Linux. Windows: tested by hand. macOS: untested. The addon needs no
shell; the headless `scripts/fc.sh` needs bash (macOS has it; on Windows use
the addon or the GUI macros).

## Checks

    scripts/fc.sh scripts/run_tests.py   # unit and geometry tests
    scripts/fc.sh scripts/verify.py      # geometry checks over a sweep of sizes and tolerances

## Licence

Copyright (C) 2026 hwkan. Licensed under the GNU LGPL v2.1 or later; see LICENSE.
