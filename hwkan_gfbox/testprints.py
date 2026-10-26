"""Test prints of the hinge and the lock, cut from a really built box, to
tune the printer-dependent gaps without printing a box (spec:
docs/superpowers/specs/2026-10-05-test-prints-design.md).

Entry point: scripts/make_test_prints.py
    headless: scripts/fc.sh scripts/make_test_prints.py [--preset NAME|PATH]
              [--set NAME=VALUE ...] [--sweep NAME=V1,V2,...] [--out DIR] [--fine]
              (default output: build/test_prints/)
    GUI:      execute scripts/make_test_prints.py as a macro: a dialog asks
              for the sweep and the folder; the open hwkan_gfbox document's Params values
              are used (it is left as it is).
"""
import json
import os
import re
import sys

import FreeCAD as App
import MeshPart
import Part

from hwkan_gfbox import presets
from hwkan_gfbox.build import BuildError, box_document, build, params_document
from hwkan_gfbox.cli import parse_overrides
from hwkan_gfbox.export import (LATCH_ROTATION, MESH_SETTINGS, ExportError, build_info, check_part,
                                latch_print_shapes, leaves_print_shapes, place_on_bed)
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import SHEET_NAME, ParamError, preset_values, sheet_overrides, value
from hwkan_gfbox.validate import validate

# Every test-print build is this small box (after the user's values): the
# pieces are local to one hinge and one lock, which don't depend on the size.
SMALL_BOX = [("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"), ("hinge_count", "2"), ("lock_count", "1")]
MARGIN = 3.0   # each strip reaches this far beyond the hinge or pad on either side (mm)
ROW_GAP = 5.0  # gap between the copies of a sweep (mm)
LABEL_TAB = (7.0, 1.2)  # a wall strip's label tab: depth in from the wall's inner face, thickness (mm)


def _strip(shape, x0, x1, y0, y1, z0, z1):
    """shape's material inside the box [x0, x1] x [y0, y1] x [z0, z1]."""
    return shape.common(Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0)))


def _with_tab(strip, x0, x1, y_wall, inward, z_bed):
    """strip fused with a LABEL_TAB plate on its bed (z_bed up), across
    x0..x1, from the wall's inner face y_wall LABEL_TAB deep toward the box's
    inside (inward = +1 or -1), 0.1 into the wall so the two fuse: room for a
    bed-face label away from the slot."""
    depth, thick = LABEL_TAB
    y0, y1 = sorted((y_wall - inward * 0.1, y_wall + inward * depth))
    tab = Part.makeBox(x1 - x0, y1 - y0, thick, App.Vector(x0, y0, z_bed))
    return strip.fuse(tab).Solids


def _nearest(solids, x):
    """The solid whose bounding-box center is nearest to X = x."""
    return min(solids, key=lambda s: abs(s.BoundBox.Center.x - x))


def _val(doc, name):
    return value(doc.getObject(SHEET_NAME), name)


def _inner(doc):
    """Y of the back wall's inner face (the front wall's is at -this)."""
    return _val(doc, "outer_d") / 2 - _val(doc, "wall_t")


def _hinge_lid(doc):
    """The lid from the back wall's inner face out, around the first hinge's
    knuckles, with a label tab on its bed inside the wall, and that hinge's
    leaf swung up to print in place with it."""
    c = _val(doc, "hinge_c0")
    hw = _val(doc, "hinge_root_len") / 2 + MARGIN
    lid = get(doc, "Lid").Shape.copy()  # copies: no triangulation cached on the original
    bb = lid.optimalBoundingBox(False)
    strip = _strip(lid, c - hw, c + hw, _inner(doc), bb.YMax + 1, bb.ZMin - 1, bb.ZMax + 1)
    return _with_tab(strip, c - hw, c + hw, _inner(doc), -1, bb.ZMin) + [_nearest(leaves_print_shapes(doc), c)]


def _hinge_rib(doc):
    """The bottom from the back wall's inner face out, around the first
    hinge rib and its slot, cut flat 1 mm below the rib (it prints as the
    bottom does, on that cut), with a label tab on its bed inside the wall."""
    c = _val(doc, "hinge_c0")
    hw = _val(doc, "hinge_rib_w") / 2 + MARGIN
    rib = _nearest(get(doc, "HingeRibs").Shape.Solids, c)
    bottom = get(doc, "Bottom").Shape.copy()
    bb = bottom.optimalBoundingBox(False)
    z0 = rib.BoundBox.ZMin - 1
    strip = _strip(bottom, c - hw, c + hw, _inner(doc), bb.YMax + 1, z0, bb.ZMax + 1)
    return _with_tab(strip, c - hw, c + hw, _inner(doc), -1, z0)


def _lock_pad(doc):
    """The bottom from the front wall's inner face out, around the first
    lock pad and its slot, cut flat 1 mm below the pad, with a label tab on
    its bed inside the wall."""
    c = _val(doc, "lock_c0")
    hw = _val(doc, "pad_hw") + MARGIN
    pad = _nearest(get(doc, "LockPads").Shape.Solids, c)
    bottom = get(doc, "Bottom").Shape.copy()
    bb = bottom.optimalBoundingBox(False)
    z0 = pad.BoundBox.ZMin - 1
    strip = _strip(bottom, c - hw, c + hw, bb.YMin - 1, -_inner(doc), z0, bb.ZMax + 1)
    return _with_tab(strip, c - hw, c + hw, -_inner(doc), 1, z0)


def _leaf(doc):
    """The first hinge's leaf alone, swung up as it prints with the lid."""
    return [_nearest(leaves_print_shapes(doc), _val(doc, "hinge_c0"))]


def _latch_base(doc):
    """The first latch's base alone."""
    return latch_print_shapes(doc)[:1]


def _keyless_base(doc):
    """The first latch's base without its key (test G): the generator's key
    region (LatchBaseKeyRegion: everything within lock_key_d of the tongue's
    wide face) cut out over the whole height, so it slides past a printed
    pad's nub."""
    return get(doc, "LatchBase").Shape.cut(get(doc, "LatchBaseKeyRegion").Shape)


def _latch_keyless(doc):
    """The first latch in print pose with a keyless base (test G)."""
    base, *rest = latch_print_shapes(doc)
    return [_keyless_base(doc)] + rest


# Test-print pieces: name -> (its solids in the model frame; rotation before
# it goes on the bed, as in export.PARTS; index of the solid that takes a
# sweep's label, None = never labelled; the tolerance whose sweep repeats it).
PIECES = {
    "hinge_lid": (_hinge_lid, None, 0, "hinge_clearance"),
    "hinge_rib": (_hinge_rib, None, 0, None),
    "leaf": (_leaf, None, 0, "dovetail_clearance"),
    "latch": (latch_print_shapes, LATCH_ROTATION, 0, "latch_clearance"),  # label on the base (the lever and hook are too narrow)
    "lock_pad": (_lock_pad, None, 0, None),
    "latch_base": (_latch_base, LATCH_ROTATION, 0, "lock_dovetail_clearance"),
    "latch_keyless": (_latch_keyless, LATCH_ROTATION, 0, None),
}
# The basic set (no sweep): every piece but the calibration-only ones.
BASIC_SET = ("hinge_lid", "hinge_rib", "leaf", "latch", "lock_pad", "latch_base")
SWEEPABLE = {tol: name for name, (_, _, _, tol) in PIECES.items() if tol}
# A dovetail sweep adds one slot strip, cut from the build with the largest value.
SLOT_PIECE = {"dovetail_clearance": "hinge_rib", "lock_dovetail_clearance": "lock_pad"}


def piece(doc, name):
    """The piece's solids, checked, in print position (on Z = 0, centered in
    XY), in PIECES order (for hinge_lid: strip, leaf; for latch: base,
    lever, hook)."""
    solids_of, rotation, _, _ = PIECES[name]
    solids = solids_of(doc)
    for k, solid in enumerate(solids):
        check_part(name if len(solids) == 1 else f"{name} solid {k + 1}", solid)
    return place_on_bed(solids, rotation).Solids


# Labels: FreeCAD's own font (TechDraw ships it with every install).
FONT = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "Resources", "fonts", "osifont-lgpl3fe.ttf")
LABEL_SIZES = tuple(k / 4 for k in range(48, 11, -1))  # font sizes tried, 12 down to 3 by 0.25; digits come out about 2/3 as high
LABEL_DEPTH = 0.6   # engraving depth (mm): at least three 0.2 layers
LABEL_STROKE = 0.15  # osifont is thin: each stroke is thickened by this on both sides (mm)
LABEL_MARGIN = 0.8  # the text keeps this far inside its face (mm)


def label_text(val):
    """Two decimals ("0.20"), or as many as the value has ("0.125")."""
    return f"{val:.2f}" if abs(round(val, 2) - val) < 1e-9 else f"{val:g}"


def _polygon_face(face):
    """face rebuilt from fine polygons in Z = 0: makeOffset2D gives offset
    curves (slightly out of plane) whose extrusions fail check(True)."""
    polys = []
    for wire in face.Wires:
        # evenly spaced (a deflection-based discretization left edges too
        # short for the BOP check), near-duplicates dropped, closed
        pts = []
        for p in wire.discretize(Distance=0.05):
            p = App.Vector(p.x, p.y, 0)
            if not pts or (p - pts[-1]).Length > 0.01:
                pts.append(p)
        if (pts[0] - pts[-1]).Length <= 0.01:
            pts.pop()
        polys.append(Part.makePolygon(pts + [pts[0]]))
    return Part.makeFace(polys, "Part::FaceMakerBullseye")


def _thickened(glyph):
    """glyph grown by LABEL_STROKE; as it is if the offset fails (it does
    for some glyphs)."""
    try:
        return glyph.makeOffset2D(LABEL_STROKE)
    except (ValueError, Part.OCCError):
        return glyph


def _text_face(text, size):
    """The text as a compound of one face per glyph in the XY plane,
    centered on the origin, strokes thickened by LABEL_STROKE."""
    shape = Part.makeCompound([_polygon_face(_thickened(Part.makeFace(wires, "Part::FaceMakerBullseye")))
                               for wires in Part.makeWireString(text, FONT, size, 0) if wires])
    bb = shape.BoundBox
    shape.translate(App.Vector(-bb.Center.x, -bb.Center.y, 0))
    return shape


def _flat_faces(solid, sign):
    """solid's planar faces facing +Z (sign 1) or -Z (sign -1), largest first."""
    faces = [f for f in solid.Faces
             if f.Surface.TypeId == "Part::GeomPlane" and abs(f.normalAt(0, 0).z - sign) < 1e-6]
    return sorted(faces, key=lambda f: -f.Area)


def _centers(face, n=9):
    """Candidate text centers on face: its centroid, then an n x n grid over
    its bounding box (points on the face only), nearest to the centroid
    first."""
    c, bb = face.CenterOfMass, face.BoundBox
    grid = [App.Vector(bb.XMin + (i + 0.5) * bb.XLength / n, bb.YMin + (j + 0.5) * bb.YLength / n, c.z)
            for i in range(n) for j in range(n)]
    grid = [p for p in grid if face.isInside(p, 1e-6, True)]
    return [c] + sorted(grid, key=lambda p: (p - c).Length)


def engrave(solid, text):
    """Engrave text LABEL_DEPTH deep into solid's bed face (in print
    position), mirrored so it reads from below: the largest size that fits,
    along X, then along Y, centered as near the face's centroid as it fits.
    Returns (solid, True), or (the solid unchanged, False) when the font is
    missing or no bed face is large enough."""
    if not os.path.isfile(FONT):
        return solid, False
    sign = -1
    for face in _flat_faces(solid, sign)[:3]:
        z = face.BoundBox.ZMin
        centers = _centers(face)
        fb = face.BoundBox
        for size in LABEL_SIZES:
            mirrored = _text_face(text, size).mirror(App.Vector(0, 0, 0), App.Vector(1, 0, 0))  # returns a copy
            for turn in (0, 90):
                text_face = mirrored.copy()
                text_face.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), turn)
                tb = text_face.BoundBox
                if tb.XLength + 2 * LABEL_MARGIN > fb.XLength or tb.YLength + 2 * LABEL_MARGIN > fb.YLength:
                    continue  # can't fit anywhere on the face
                for c in centers:
                    placed = text_face.copy()
                    placed.translate(App.Vector(c.x, c.y, z))
                    bb, m = placed.BoundBox, LABEL_MARGIN
                    room = Part.makePlane(bb.XLength + 2 * m, bb.YLength + 2 * m,
                                          App.Vector(bb.XMin - m, bb.YMin - m, z))
                    if room.cut(face).Area > 1e-6:
                        continue  # the text (with its margin) leaves the face
                    # the cutter starts 0.1 outside the face: coplanar with it, the
                    # cut came out unorientable
                    cutter = placed.extrude(App.Vector(0, 0, -sign * (LABEL_DEPTH + 0.1)))
                    cutter.translate(App.Vector(0, 0, sign * 0.1))
                    return solid.cut(cutter).Solids[0], True
    return solid, False


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "build", "test_prints")
DOC_PREFIX = "hwkan_gfbox_tp"        # the builds' documents (closed after cutting)
SHOW_DOC = "hwkan_gfbox_testprints"  # GUI: the pieces are shown here


def parse_sweep(text):
    """'NAME=V1,V2,...' -> (NAME, [V1, V2, ...]). Values are mm, separated by
    commas, semicolons or spaces, each optionally followed by 'mm'. Raises
    ParamError unless NAME is sweepable and every value is a number > 0."""
    name, sep, rest = text.partition("=")
    name = name.strip()
    if name not in SWEEPABLE:
        raise ParamError(f"--sweep: '{name}' can't be swept; choose one of {', '.join(SWEEPABLE)}")
    items = [t for t in re.split(r"[,;\s]+", re.sub(r"\s*mm\b", "", rest)) if t]
    if not sep or not items:
        raise ParamError(f"--sweep expects {name}=V1,V2,... (mm)")
    values = []
    for item in items:
        try:
            val = float(item)
        except ValueError:
            raise ParamError(f"--sweep {name}: '{item}' is not a number")
        if val <= 0:
            raise ParamError(f"--sweep {name}: values must be > 0 (got {item})")
        values.append(val)
    return name, values


def default_sweep_values(current, ok=lambda val: True):
    """The dialog's starting values: current - 0.05, current, current + 0.05
    (half of current instead of current - 0.05 if that would not be > 0);
    if ok rejects one, the window moves away from that limit (up to two
    steps) while keeping current; failing that, current alone."""
    step = 0.05
    low = current - step if current > step + 1e-9 else current / 2
    windows = [(low, current, current + step), (current, current + step, current + 2 * step),
               (current - 2 * step, current - step, current)]
    for window in windows:
        if all(x > 0 and ok(x) for x in window):
            return ", ".join(f"{round(x, 3):g}" for x in window)
    return f"{round(current, 3):g}"


def valid_value(overrides, tol, val, preset=None):
    """True if the generator accepts tol = val with this preset and these
    overrides (the sheets alone; no box is built)."""
    try:
        _check_values(overrides, tol, [val], preset)
    except ParamError:
        return False
    return True


def _check_values(overrides, tol, values, preset=None):
    """Raise ParamError naming the first sweep value the generator rejects,
    from the parameter sheets alone (seconds, before any box is built)."""
    for val in values:
        doc = params_document(list(overrides) + SMALL_BOX + [(tol, f"{val:g}")], doc_name=f"{DOC_PREFIX}_check",
                              preset=preset)[0]
        try:
            validate(doc.getObject(SHEET_NAME))
        except ParamError as e:
            raise ParamError(f"{tol} = {val:g}: {e}")
        finally:
            App.closeDocument(doc.Name)


def _build(overrides, k, tol=None, val=None, preset=None):
    """A small box with the preset, overrides (and tol = val), in its own document."""
    extra = [(tol, f"{val:g}")] if tol else []
    try:
        return build(list(overrides) + SMALL_BOX + extra, doc_name=f"{DOC_PREFIX}{k}", preset=preset)
    except ParamError as e:
        raise ParamError(f"{tol} = {val:g}: {e}" if tol else str(e))


def _plate(copies):
    """Copies (each a list of solids in print position) in a row along X,
    ROW_GAP apart, as one compound of one compound per copy, on Z = 0 and
    centered in XY."""
    placed, x = [], 0.0
    for solids in copies:
        copy = Part.makeCompound(solids)
        bb = copy.optimalBoundingBox(False)  # not a cached triangulation's (see place_on_bed)
        copy.translate(App.Vector(x - bb.XMin, 0, 0))
        placed.append(copy)
        x += bb.XLength + ROW_GAP
    return place_on_bed(placed)


def write_sweep(param, values, labels, name, out_dir, plate_file, partner=None, partner_file=None,
                overrides=(), preset=None, fine=False):
    """One copy of the piece `name` per value of param (each from its own
    small box: the preset, then overrides, then param = value), engraved
    with labels[k] on its bed face, in a row on one plate; and partner (if
    any) from the build with the largest value. Every value is checked
    before anything is built. Writes plate_file (and partner_file) into
    out_dir. Returns (paths, {file: plate}, build_info of the largest
    value's build, warnings). Raises BuildError if a label doesn't fit."""
    if len(values) != len(labels):
        raise ValueError(f"{len(values)} values but {len(labels)} labels")
    _check_values(overrides, param, values, preset)
    warnings = []
    font = os.path.isfile(FONT)
    if not font:
        warnings.append(f"warning: font not found ({FONT}): the copies are not labelled")
    copies, info, partner_solids = [], None, None
    for k, (val, label) in enumerate(zip(values, labels)):
        doc, w = _build(overrides, k, param, val, preset)
        warnings += w
        try:
            solids = piece(doc, name)
            i = PIECES[name][2]
            solids[i], ok = engrave(solids[i], label)
            if font and not ok:
                raise BuildError(f"{name}: no bed face with room for the label '{label}'")
            copies.append(solids)
            if val == max(values):
                info = build_info(doc)
                if partner:
                    partner_solids = piece(doc, partner)
        finally:
            App.closeDocument(doc.Name)
    files = {plate_file: _plate(copies)}
    if partner:
        files[partner_file] = _plate([partner_solids])
    return _write_plates(files, out_dir, fine), files, info, warnings


def _write_plates(files, out_dir, fine):
    """Mesh each plate into out_dir; returns the paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for fname, plate in files.items():
        path = os.path.join(out_dir, fname)
        MeshPart.meshFromShape(Shape=plate, Relative=False, **MESH_SETTINGS[fine]).write(path)
        paths.append(path)
    return paths


def run(overrides=(), sweep=None, out_dir=DEFAULT_OUT, fine=False, preset=None):
    """Build, cut, label and write the test prints. preset: a presets.Preset
    applied before the overrides (None: the defaults). sweep: None (one set of
    every piece at the overrides' values) or (tolerance, values) from
    parse_sweep. Returns (written paths, {STL name: plate}, warnings)."""
    if sweep is None:
        doc, warnings = _build(overrides, 0, preset=preset)
        try:
            files = {f"{name}.stl": _plate([piece(doc, name)]) for name in BASIC_SET}
            info = build_info(doc)
        finally:
            App.closeDocument(doc.Name)
        paths = _write_plates(files, out_dir, fine)
        info_name = "build_info.json"
    else:
        tol, values = sweep
        name, slot = SWEEPABLE[tol], SLOT_PIECE.get(tol)
        paths, files, info, warnings = write_sweep(
            tol, values, [label_text(v) for v in values], name, out_dir, f"{name}_{tol}_sweep.stl",
            slot, slot and f"{slot}_{tol}_sweep.stl", overrides, preset, fine)
        info["sweep"] = {"name": tol, "values": values}
        info_name = f"build_info_{tol}_sweep.json"
    with open(os.path.join(out_dir, info_name), "w") as f:
        json.dump(info, f, indent=2)
    return paths, files, warnings


def gui_inputs():
    """GUI: (overrides, {tolerance: current value}) from the open generated
    document's Params sheet (left open, unchanged): its inputs and the
    preset values it was built with; or ([], defaults)."""
    box = box_document()
    if box is not None:
        sheet = box.getObject(SHEET_NAME)
        stored = [(name, f"{val!r} mm") for name, val in preset_values(sheet).items()]
        return sheet_overrides(sheet) + stored, {tol: value(sheet, tol) for tol in SWEEPABLE}
    defaults = presets.defaults()
    return [], {tol: defaults[tol] for tol in SWEEPABLE}


def show(files):
    """GUI: the plates side by side along Y in the document SHOW_DOC
    (replaced if open), one Part::Feature per STL."""
    import FreeCADGui
    if SHOW_DOC in App.listDocuments():
        App.closeDocument(SHOW_DOC)
    doc = App.newDocument(SHOW_DOC)
    y = 0.0
    for fname, plate in files.items():
        shape = plate.copy()
        bb = shape.optimalBoundingBox(False)
        shape.translate(App.Vector(0, y - bb.YMin, 0))
        y += bb.YLength + 10
        doc.addObject("Part::Feature", os.path.splitext(fname)[0]).Shape = shape
    doc.recompute()
    for view in FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor"):
        view.viewIsometric()
        view.fitAll()
    return doc


def main(args):
    if App.GuiUp:
        from hwkan_gfbox import testprints_dialog
        return testprints_dialog.ask_and_run()
    try:
        overrides, preset, rest = parse_overrides(args)
        sweep, out_dir, fine = None, DEFAULT_OUT, False
        it = iter(rest)
        for arg in it:
            if arg == "--sweep":
                sweep = parse_sweep(next(it, ""))
            elif arg == "--out":
                out_dir = next(it, "")
            elif arg == "--fine":
                fine = True
            else:
                raise ParamError(f"unexpected argument: {arg}")
        paths, _, warnings = run(overrides, sweep, os.path.abspath(out_dir), fine, preset)
    except ParamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (BuildError, ExportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(warning, file=sys.stderr)
    for path in paths:
        print(f"wrote {path}")
    return 0
