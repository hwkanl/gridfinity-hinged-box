"""Test prints of one preset: the hinge and the lock, cut from a really
built small box (the default inputs and the preset), to check the preset's
gaps without printing a box (spec:
docs/superpowers/specs/2026-10-05-test-prints-design.md). Four parts:
hinge_lid (lid strip, leaf printed in place), hinge_rib (the leaf's
dovetail slot), latch (printed in place) and lock_front (the lock pad with
its slot and the lid's lip above it, one part). The pieces and the labelled
sweeps are also what the calibration (hwkan_gfbox.calibration) prints.

Entry point: scripts/make_test_prints.py
    headless: scripts/fc.sh scripts/make_test_prints.py [--preset NAME|PATH]
              [--out DIR] [--fine]   (default output: build/test_prints/)
    GUI:      the Test prints command: a dialog asks for the preset and the
              folder.
"""
import json
import os
import sys

import FreeCAD as App
import MeshPart
import Part

from hwkan_gfbox import presets
from hwkan_gfbox.build import BuildError, box_document, build, params_document
from hwkan_gfbox.export import (LATCH_ROTATION, MESH_SETTINGS, ExportError, build_info, check_part,
                                latch_print_shapes, leaves_print_shapes, place_on_bed)
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import SHEET_NAME, ParamError, sheet_preset, value
from hwkan_gfbox.validate import validate

# Every test-print build is this small box (after any overrides, e.g. calibration's):
# the pieces are local to one hinge and one lock, which don't depend on the size.
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


def _lock_front(doc):
    """The lock pad's strip (_lock_pad) with the lid's strip above it (the
    lock lip and the lid's wall from its inner face out, over the same X),
    fused as the box stands closed: one part to hook a latch onto."""
    c = _val(doc, "lock_c0")
    hw = _val(doc, "pad_hw") + MARGIN
    lid = get(doc, "Lid").Shape.copy()
    bb = lid.optimalBoundingBox(False)
    lid_strip = _strip(lid, c - hw, c + hw, bb.YMin - 1, -_inner(doc), bb.ZMin - 1, bb.ZMax + 1)
    front = Part.makeCompound(_lock_pad(doc)).fuse(lid_strip).Solids
    if len(front) != 1:
        raise BuildError(f"lock_front: the pad and the lid strip fused into {len(front)} solids, not one")
    return front


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
# sweep's label).
PIECES = {
    "hinge_lid": (_hinge_lid, None, 0),
    "hinge_rib": (_hinge_rib, None, 0),
    "leaf": (_leaf, None, 0),
    "latch": (latch_print_shapes, LATCH_ROTATION, 0),  # label on the base (the lever and hook are too narrow)
    "lock_pad": (_lock_pad, None, 0),
    "lock_front": (_lock_front, None, 0),
    "latch_base": (_latch_base, LATCH_ROTATION, 0),
    "latch_keyless": (_latch_keyless, LATCH_ROTATION, 0),
}
# The test prints of a preset: one STL each.
TEST_SET = ("hinge_lid", "hinge_rib", "latch", "lock_front")


def piece(doc, name):
    """The piece's solids, checked, in print position (on Z = 0, centered in
    XY), in PIECES order (for hinge_lid: strip, leaf; for latch: base,
    lever, hook)."""
    solids_of, rotation, _ = PIECES[name]
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


def run(preset=None, out_dir=DEFAULT_OUT, fine=False):
    """Build, cut and write the test prints of preset (a presets.Preset; None:
    the defaults): one STL per TEST_SET piece, from one small box with the
    default inputs, plus build_info.json. Returns (written paths,
    {STL name: plate}, warnings)."""
    doc, warnings = _build((), 0, preset=preset)
    try:
        files = {f"{name}.stl": _plate([piece(doc, name)]) for name in TEST_SET}
        info = build_info(doc)
    finally:
        App.closeDocument(doc.Name)
    paths = _write_plates(files, out_dir, fine)
    with open(os.path.join(out_dir, "build_info.json"), "w") as f:
        json.dump(info, f, indent=2)
    return paths, files, warnings


def gui_preset():
    """GUI: the name of the open generated box's preset if it still exists,
    else the default: the dialog's first choice."""
    box = box_document()
    name = box is not None and sheet_preset(box.getObject(SHEET_NAME))
    return name if name in [n for n, _ in presets.list_presets()] else presets.DEFAULT


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
        preset, out_dir, fine = presets.load(presets.DEFAULT), DEFAULT_OUT, False
        it = iter(args)
        for arg in it:
            if arg == "--preset":
                ref = next(it, None)
                if not ref:
                    raise ParamError("--preset expects a preset name or a JSON file")
                preset = presets.load(ref)
            elif arg == "--out":
                out_dir = next(it, "")
            elif arg == "--fine":
                fine = True
            else:
                raise ParamError(f"unexpected argument: {arg} (usage: [--preset NAME|PATH] [--out DIR] [--fine])")
        paths, _, warnings = run(preset, os.path.abspath(out_dir), fine)
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
