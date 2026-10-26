"""Export print-ready STL files.

Entry point: scripts/make_stls.py
    headless: scripts/fc.sh scripts/make_stls.py [--preset NAME|PATH]
              [--set NAME=VALUE ...] [--part all|bottom|lid|latch] [--out DIR] [--fine]
              Builds a fresh model with the given parameters
              (default output: build/stl/).
    GUI:      execute scripts/make_stls.py as a macro with the generated
              document active: exports every part using its Params sheet.
"""
import json
import os
import subprocess
import sys

import FreeCAD as App
import MeshPart
import Part

import hwkan_gfbox

from hwkan_gfbox.build import BuildError, box_document, build, check_recompute
from hwkan_gfbox.cli import parse_overrides
from hwkan_gfbox.params import PARAMS
from hwkan_gfbox.parts import lock
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import SHEET_NAME, ParamError, sheet_preset, value
from hwkan_gfbox.validate import validate

# The project directory (parent of this package); default outputs go under build/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_OUT = os.path.join(ROOT, "build", "stl")

MESH_SETTINGS = {
    False: {"LinearDeflection": 0.05, "AngularDeflection": 0.5236},  # 30 deg
    True: {"LinearDeflection": 0.01, "AngularDeflection": 0.1745},   # 10 deg (--fine)
}


class ExportError(RuntimeError):
    """A part is not fit to be exported."""


def check_part(part, shape):
    """Raise ExportError unless shape is exactly one sound, closed solid."""
    if shape.isNull():
        raise ExportError(f"{part}: empty shape")
    problems = []
    if not shape.isValid():
        problems.append("invalid shape")
    else:
        try:
            shape.check(True)
        except Exception as e:
            problems.append(f"failed geometry check ({str(e).splitlines()[-1]})")
    if len(shape.Solids) != 1:
        problems.append(f"{len(shape.Solids)} solids (expected 1)")
    if not all(shell.isClosed() for shell in shape.Shells):
        problems.append("open shell")
    if problems:
        raise ExportError(f"{part}: " + ", ".join(problems))


def leaves_print_shapes(doc):
    """The free leaves swung up into print position (+90 deg about the hinge
    axis; the model has them swung down), one solid per hinge."""
    sheet = doc.getObject(SHEET_NAME)
    ay = value(sheet, "rim_d") / 2 + value(sheet, "hinge_axis_out")
    az = value(sheet, "split_z") + value(sheet, "hinge_axis_z")
    leaves = get(doc, "Leaves").Shape.copy()
    leaves.rotate(App.Vector(0, ay, az), App.Vector(1, 0, 0), 90)
    return leaves.Solids


def latch_print_shapes(doc):
    """The first lock's latch in print pose (spec, "Print pose"), still in
    the model frame with its bed plane z = latch_top above the parts: the
    base as modelled; the lever turned lever_print_angle about P0, the hook
    hook_print_angle about P1 and moved with P1 to the lever's P1."""
    sheet = doc.getObject(SHEET_NAME)

    def val(name):
        return value(sheet, name)

    p0 = lock.point(doc, val("lock_p0_u"), val("lock_p0_z"))
    p1 = lock.point(doc, val("lock_p1_u"), val("lock_p1_z"))
    base = get(doc, "LatchBase").Shape.copy()
    lever = get(doc, "LatchLever").Shape.copy()
    lever.rotate(p0, lock.MINUS_X, val("lever_print_angle"))
    hook = get(doc, "LatchHook").Shape.copy()
    hook.rotate(p1, lock.MINUS_X, val("hook_print_angle"))
    hook.translate(lock.point(doc, val("lock_p0_u") + val("pivot_dist"), val("lock_p0_z")) - p1)
    return [base, lever, hook]


def check_leaves(shape, expected):
    """Raise ExportError unless shape (the Leaves shape) holds `expected`
    sound solids, one per hinge."""
    solids = shape.Solids
    if len(solids) != expected:
        raise ExportError(f"leaves: {len(solids)} solids (expected {expected})")
    for k, solid in enumerate(solids):
        check_part(f"leaf {k + 1}", solid)


def lid_print_shapes(doc):
    """The lid, then one leaf per hinge: the leaves print in place with it."""
    if not doc.getObjectsByLabel("Leaves"):
        raise ExportError("leaves: no 'Leaves' object in the document; regenerate the box")
    check_leaves(get(doc, "Leaves").Shape, int(value(doc.getObject(SHEET_NAME), "hinge_count")))
    return [get(doc, "Lid").Shape.copy()] + leaves_print_shapes(doc)


# The latch is built with its bed (z = latch_top) on top: it is turned over.
LATCH_ROTATION = (App.Vector(1, 0, 0), 180)

# Printable parts: name -> (the part's solids, still in the model frame;
# rotation about the origin before it goes on the bed, None = as modelled,
# else (axis, degrees); STL name carries the box size).
PARTS = {
    "bottom": (lambda doc: [get(doc, "Bottom").Shape.copy()], None, True),  # floor down
    "lid": (lid_print_shapes, None, True),  # modelled closed = already open side down
    # built with its bed (z = latch_top) on top: turn it over
    "latch": (latch_print_shapes, LATCH_ROTATION, False),
}


def place_on_bed(solids, rotation=None):
    """The solids as one compound in print position: rotated about the
    origin by rotation ((axis, degrees), None = as given), lowest point on
    Z = 0, centered in XY."""
    shape = Part.makeCompound(solids)
    if rotation:
        shape.rotate(App.Vector(0, 0, 0), *rotation)
    # exact (BoundBox is loose around the rim's curved faces), and not from a
    # triangulation a mesh export or GUI view may have cached on the shapes
    bb = shape.optimalBoundingBox(False)
    shape.translate(App.Vector(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
    return shape


def print_shape(doc, part):
    """The part's solids (copies) as one compound in print position (see
    place_on_bed). For the lid: the lid's solid first, then one solid per
    leaf."""
    solids, rotation, _ = PARTS[part]
    return place_on_bed(solids(doc), rotation)


def stl_name(doc, part):
    if not PARTS[part][2]:
        return f"{part}.stl"
    sheet = doc.getObject(SHEET_NAME)
    x, y, z = (int(value(sheet, n)) for n in ("gf_x", "gf_y", "gf_z_units"))
    return f"{part}_{x}x{y}x{z}.stl"


def _git_commit():
    try:
        rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return rev + ("-dirty" if dirty else "")


def build_info(doc):
    sheet = doc.getObject(SHEET_NAME)
    return {
        "preset": sheet_preset(sheet),
        "parameters": {name: value(sheet, name) for name, _, _, _ in PARAMS},
        "hwkan_gfbox": hwkan_gfbox.__version__,
        "freecad": ".".join(App.Version()[:3]),
        "commit": _git_commit(),
    }


def export(doc, parts, out_dir, fine=False):
    """Check every part, then write one binary STL per part plus
    build_info.json. Nothing is written if any part fails its check.
    Returns the STL paths."""
    for part in parts:
        solids = PARTS[part][0](doc)
        for k, solid in enumerate(solids):
            check_part(part if len(solids) == 1 else f"{part} solid {k + 1}", solid)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for part in parts:
        mesh = MeshPart.meshFromShape(Shape=print_shape(doc, part), Relative=False,
                                      **MESH_SETTINGS[fine])
        path = os.path.join(out_dir, stl_name(doc, part))
        mesh.write(path)
        written.append(path)
    with open(os.path.join(out_dir, "build_info.json"), "w") as f:
        json.dump(build_info(doc), f, indent=2)
    return written


def gui_document():
    """The document to export in the GUI (build.box_document). Raises
    ParamError if no generated box is open."""
    doc = box_document()
    if doc is None:
        raise ParamError("no generated box is open: build one first (New box)")
    return doc


def open_box():
    """GUI: the open generated box (gui_document), recomputed and checked
    as build would (validate, check_recompute)."""
    doc = gui_document()
    doc.recompute()
    validate(doc.getObject(SHEET_NAME))
    check_recompute(doc)
    return doc


def main(args):
    try:
        overrides, preset, rest = parse_overrides(args)
        part, out_dir, fine = "all", DEFAULT_OUT, False
        it = iter(rest)
        for arg in it:
            if arg == "--part":
                part = next(it, "")
            elif arg == "--out":
                out_dir = next(it, "")
            elif arg == "--fine":
                fine = True
            else:
                raise ParamError(f"unexpected argument: {arg}")
        if part != "all" and part not in PARTS:
            raise ParamError(f"--part must be one of: all, {', '.join(PARTS)}")
        parts = list(PARTS) if part == "all" else [part]
        if App.GuiUp:
            doc = open_box()
        else:
            doc, warnings = build(overrides, preset=preset)
            for warning in warnings:
                print(warning, file=sys.stderr)
        for path in export(doc, parts, os.path.abspath(out_dir), fine):
            print(f"wrote {path}")
    except ParamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (BuildError, ExportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
