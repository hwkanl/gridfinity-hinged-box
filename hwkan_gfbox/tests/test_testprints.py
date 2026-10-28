"""Test prints of the hinge and the lock (spec:
docs/superpowers/specs/2026-10-05-test-prints-design.md)."""
import json
import os
import tempfile

import FreeCAD as App
import Mesh
import Part

from hwkan_gfbox import testprints
from hwkan_gfbox.build import DOC_NAME, build, params_document
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import ParamError
from hwkan_gfbox.tests.helpers import built, is_sound, near, v

_docs = {}


def _small(*extra):
    """The small test-print box with these extra overrides, cached."""
    if extra not in _docs:
        _docs[extra] = build(testprints.SMALL_BOX + list(extra), doc_name="tp_test")[0]
    return _docs[extra]


EXPECTED_SOLIDS = {"hinge_lid": 2, "hinge_rib": 1, "leaf": 1, "latch": 3, "lock_pad": 1, "latch_base": 1, "latch_keyless": 3}


def test_pieces_are_sound_and_on_the_bed():
    doc = _small()
    assert list(testprints.PIECES) == list(EXPECTED_SOLIDS)
    for name, n in EXPECTED_SOLIDS.items():
        solids = testprints.piece(doc, name)
        assert len(solids) == n, (name, len(solids))
        assert all(is_sound(s) for s in solids), name
        assert near(Part.makeCompound(solids).optimalBoundingBox().ZMin, 0, 1e-6), name


def _covers(part, strip, features):
    """strip holds all of part's material in the features' bounding box
    (grown 0.5 mm): the cut did not clip the hinge or the pad."""
    bb = App.BoundBox()
    for f in features:
        bb.add(f.BoundBox)
    region = Part.makeBox(bb.XLength + 1, bb.YLength + 1, bb.ZLength + 1,
                          App.Vector(bb.XMin - 0.5, bb.YMin - 0.5, bb.ZMin - 0.5))
    want = part.common(region).Volume
    return want > 0 and abs(strip.common(region).Volume - want) <= 1e-3


def test_strips_hold_the_whole_hinge_and_pad():
    doc = _small()

    def near_x(label, c):
        return [s for s in get(doc, label).Shape.Solids if abs(s.BoundBox.Center.x - c) < 15]

    hc, lc = v(doc, "hinge_c0"), v(doc, "lock_c0")
    lid_strip = testprints.PIECES["hinge_lid"][0](doc)[0]
    assert _covers(get(doc, "Lid").Shape, lid_strip, near_x("LidKnuckles", hc))
    rib_strip = testprints.PIECES["hinge_rib"][0](doc)[0]
    assert _covers(get(doc, "Bottom").Shape, rib_strip, near_x("HingeRibs", hc))
    pad_strip = testprints.PIECES["lock_pad"][0](doc)[0]
    assert _covers(get(doc, "Bottom").Shape, pad_strip, near_x("LockPads", lc))


def test_print_in_place_pieces_are_free():
    doc = _small()
    lid, leaf = testprints.piece(doc, "hinge_lid")
    assert lid.common(leaf).Volume <= 1e-6
    assert lid.distToShape(leaf)[0] >= v(doc, "hinge_clearance") - 1e-4
    latch = testprints.piece(doc, "latch")
    lc = v(doc, "latch_clearance")
    for i, j in ((0, 1), (1, 2), (0, 2)):
        assert latch[i].common(latch[j]).Volume <= 1e-6, (i, j)
        assert latch[i].distToShape(latch[j])[0] >= lc - 1e-3, (i, j)


def _same(a, b):
    """Equal up to a translation: exact bounding-box minima moved onto each
    other (not from a cached triangulation), then an empty difference both
    ways."""
    a, b = Part.makeCompound(a), Part.makeCompound(b)
    ba, bb = a.optimalBoundingBox(False), b.optimalBoundingBox(False)
    b = b.copy()
    b.translate(App.Vector(ba.XMin - bb.XMin, ba.YMin - bb.YMin, ba.ZMin - bb.ZMin))
    return abs(a.Volume - b.Volume) <= 1e-3 and a.cut(b).Volume <= 1e-3 and b.cut(a).Volume <= 1e-3


def test_pieces_do_not_depend_on_the_box_size():
    small, default = _small(), built()  # built() is the default 3x2x6 box
    for name in ("hinge_lid", "latch", "lock_pad"):
        assert _same(testprints.piece(small, name), testprints.piece(default, name)), name


def test_label_text():
    assert testprints.label_text(0.2) == "0.20"
    assert testprints.label_text(0.15) == "0.15"


def test_label_goes_into_the_bed_face():
    box = Part.makeBox(30, 20, 5)
    labelled, ok = testprints.engrave(box, "0.20")
    assert ok and is_sound(labelled) and len(labelled.Solids) == 1
    removed = box.cut(labelled)
    assert removed.Volume > 0.3
    assert removed.BoundBox.ZMax <= testprints.LABEL_DEPTH + 1e-6  # only the bed face


def test_no_room_on_the_bed_face_is_reported():
    cone = Part.makeCone(0.5, 10, 5)  # a large top face, a tiny bed face
    labelled, ok = testprints.engrave(cone, "0.20")
    assert not ok and near(labelled.Volume, cone.Volume)


def test_label_skipped_without_the_font():
    old = testprints.FONT
    testprints.FONT = "/nonexistent/font.ttf"
    try:
        box = Part.makeBox(30, 20, 5)
        labelled, ok = testprints.engrave(box, "0.20")
        assert not ok and near(labelled.Volume, box.Volume)
    finally:
        testprints.FONT = old


def test_every_swept_piece_takes_a_label():
    doc = _small()
    for name in testprints.SWEEPABLE.values():
        solids = testprints.piece(doc, name)
        k = testprints.PIECES[name][2]
        labelled, ok = testprints.engrave(solids[k], "0.20")
        assert ok, name
        assert is_sound(labelled) and len(labelled.Solids) == 1, name
        lost = solids[k].Volume - labelled.Volume
        assert 0.3 < lost < 40, (name, lost)
        b0, b1 = solids[k].optimalBoundingBox(), labelled.optimalBoundingBox()
        assert near(b0.ZMin, b1.ZMin, 1e-6) and near(b0.ZMax, b1.ZMax, 1e-6), name



def test_parse_sweep():
    assert testprints.parse_sweep("latch_clearance=0.15,0.2, 0.25") == ("latch_clearance", [0.15, 0.2, 0.25])
    assert testprints.parse_sweep("hinge_clearance=0.2 mm; 0.3mm 0.25") == ("hinge_clearance", [0.2, 0.3, 0.25])
    for bad in ("wall_t=1,2", "hook_preload=0.1", "latch_clearance=", "latch_clearance",
                "latch_clearance=0.1,-0.1", "latch_clearance=0.1,0", "latch_clearance=0.1,abc"):
        try:
            testprints.parse_sweep(bad)
        except ParamError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_default_sweep_values():
    assert testprints.default_sweep_values(0.2) == "0.15, 0.2, 0.25"
    assert testprints.default_sweep_values(0.04) == "0.02, 0.04, 0.09"


# Two valid values per tolerance, small first: hinge_clearance must stay > 0
# and dovetail_clearance below ~0.35
SWEEP_VALUES = {"hinge_clearance": (0.2, 0.3), "latch_clearance": (0.15, 0.25),
                "dovetail_clearance": (0.1, 0.15), "lock_dovetail_clearance": (0.1, 0.2)}


def _run(**kw):
    out = tempfile.mkdtemp(prefix="tp_")
    paths, files, warnings = testprints.run(out_dir=out, **kw)
    return out, paths, files, warnings


def _copies(plate):
    return plate.SubShapes  # one sub-compound per copy


def test_one_set_writes_every_piece():
    out, paths, files, _ = _run()
    six = ["hinge_lid", "hinge_rib", "latch", "latch_base", "leaf", "lock_pad"]
    assert sorted(os.path.basename(p) for p in paths) == sorted(f"{n}.stl" for n in six)
    assert "latch_keyless" in testprints.PIECES and "latch_keyless" not in testprints.BASIC_SET
    assert all(os.path.getsize(p) > 1000 for p in paths)
    info = json.load(open(os.path.join(out, "build_info.json")))
    assert info["parameters"]["gf_x"] == 2 and "sweep" not in info
    assert not any(d.startswith(testprints.DOC_PREFIX) for d in App.listDocuments())


def test_sweeps_repeat_the_right_piece():
    for tol, name in testprints.SWEEPABLE.items():
        lo, hi = SWEEP_VALUES[tol]
        values = [hi, lo]  # unsorted on purpose
        out, paths, files, warnings = _run(sweep=(tol, values))
        main = files[f"{name}_{tol}_sweep.stl"]
        copies = _copies(main)
        assert len(copies) == 2, tol
        n = len(testprints.piece(_small(), name))
        assert all(len(c.Solids) == n for c in copies), tol
        assert not [w for w in warnings if "no label" in w], warnings
        boxes = [c.optimalBoundingBox(False) for c in copies]  # run() meshed them: not the mesh's box
        assert boxes[0].XMax + testprints.ROW_GAP - 1e-6 <= boxes[1].XMin, tol  # in a row, apart
        stl = Mesh.Mesh(os.path.join(out, f"{name}_{tol}_sweep.stl"))  # on the bed as the slicer sees it
        assert near(stl.BoundBox.ZMin, 0, 1e-6), (tol, stl.BoundBox.ZMin)
        slot = testprints.SLOT_PIECE.get(tol)
        if slot:
            plate = files[f"{slot}_{tol}_sweep.stl"]
            assert _same(plate.Solids, testprints.piece(_small((tol, f"{hi:g}")), slot)), tol
        else:
            assert len(files) == 1, tol
        info = json.load(open(os.path.join(out, f"build_info_{tol}_sweep.json")))
        assert info["sweep"] == {"name": tol, "values": values}, tol


def test_swept_value_reaches_the_piece():
    """More clearance, less material (unlabelled pieces)."""
    for tol, name in testprints.SWEEPABLE.items():
        a, b = SWEEP_VALUES[tol]
        lo = sum(s.Volume for s in testprints.piece(_small((tol, f"{a:g}")), name))
        hi = sum(s.Volume for s in testprints.piece(_small((tol, f"{b:g}")), name))
        assert hi < lo - 1e-3, (tol, lo, hi)


def test_another_box_size_still_gives_the_test_prints():
    _, paths, _, _ = _run(overrides=[("gf_x", "5"), ("gf_y", "3"), ("hinge_count", "3"), ("lock_count", "3")],
                          sweep=("latch_clearance", [0.2]))
    assert len(paths) == 1


def test_a_bad_sweep_value_is_named_before_building():
    import time
    t = time.time()
    try:
        _run(sweep=("hinge_clearance", [0.2, 1.5]))
    except ParamError as e:
        assert "hinge_clearance = 1.5" in str(e), str(e)
    else:
        raise AssertionError("hinge_clearance 1.5 was accepted")
    assert time.time() - t < 3, "validated only after building"
    assert not any(d.startswith(testprints.DOC_PREFIX) for d in App.listDocuments())


def test_gui_inputs_leave_the_document_open():
    doc = params_document([("gf_x", "4"), ("latch_clearance", "0.3")])[0]
    try:
        overrides, current = testprints.gui_inputs()
        assert ("gf_x", "4") in overrides and near(current["latch_clearance"], 0.3)
        assert DOC_NAME in App.listDocuments()
    finally:
        App.closeDocument(doc.Name)
    overrides, current = testprints.gui_inputs()
    assert overrides == [] and near(current["hinge_clearance"], 0.2)


def test_every_digit_can_be_labelled():
    box = Part.makeBox(60, 20, 5)
    for text in ("0.123", "0.456", "0.789", "1.00"):
        labelled, ok = testprints.engrave(box, text)
        assert ok and is_sound(labelled), text


def test_bed_labels_are_mirrored():
    """Read from below, a bed-face label reads the right way round: "1." has
    its 1 (most of the material) on the right seen from above."""
    def mass_x(shape):  # x of the center of mass, relative to the bounding box's center
        return sum(s.CenterOfMass.x * s.Volume for s in shape.Solids) / shape.Volume - shape.BoundBox.Center.x

    box = Part.makeBox(30, 20, 5)
    assert mass_x(box.cut(testprints.engrave(box, "1.")[0])) > 0


WALL_STRIPS = ("hinge_lid", "hinge_rib", "lock_pad")
CALIBRATION_PIECES = ("hinge_lid", "leaf", "hinge_rib", "latch", "latch_base", "lock_pad", "latch_keyless")


def test_wall_strips_have_a_label_tab():
    """Each wall strip has a flat tab on its bed, on the box's inner side,
    LABEL_TAB deep: the largest bed face, larger than the strip's own."""
    doc = _small()
    depth, _ = testprints.LABEL_TAB
    for name in WALL_STRIPS:
        strip = testprints.piece(doc, name)[0]
        faces = testprints._flat_faces(strip, -1)
        assert faces and near(faces[0].BoundBox.ZMin, 0, 1e-6), name
        assert min(faces[0].BoundBox.XLength, faces[0].BoundBox.YLength) >= depth - 1e-6, name


def test_every_labelled_piece_has_room_on_its_bed():
    """Calibration labels (three characters) on every piece a calibration
    test sweeps, --sweep's value labels on every --sweep piece."""
    doc = _small()
    cases = [(n, "C13") for n in CALIBRATION_PIECES] + [(n, "0.125") for n in testprints.SWEEPABLE.values()]
    for name, text in cases:
        solids = testprints.piece(doc, name)
        k = testprints.PIECES[name][2]
        labelled, ok = testprints.engrave(solids[k], text)
        assert ok, (name, text)
        assert is_sound(labelled) and len(labelled.Solids) == 1, (name, text)
        assert solids[k].cut(labelled).BoundBox.ZMax <= testprints.LABEL_DEPTH + 1e-6, (name, text)


def test_pieces_lie_on_the_bed_after_the_box_was_meshed():
    """Meshing a shape (an STL export, a GUI view) caches a triangulation
    that optimalBoundingBox() measures by default: placement must not use
    it."""
    import MeshPart
    doc = _small()
    for label in ("Lid", "Bottom"):
        MeshPart.meshFromShape(Shape=get(doc, label).Shape, LinearDeflection=0.3, AngularDeflection=0.5)
    for name in ("hinge_lid", "hinge_rib", "lock_pad"):
        zmin = Part.makeCompound(testprints.piece(doc, name)).optimalBoundingBox(False).ZMin
        assert near(zmin, 0, 1e-6), (name, zmin)


def test_labels_keep_every_decimal():
    assert [testprints.label_text(x) for x in (0.1, 0.2, 0.15, 0.125, 0.075)] == \
        ["0.10", "0.20", "0.15", "0.125", "0.075"]


def test_dialog_suggests_only_valid_values():
    """At default values a centered window would start below hinge_clearance's
    and end above dovetail_clearance's limit: the suggestion moves away."""
    overrides, current = testprints.gui_inputs()
    for tol in testprints.SWEEPABLE:
        text = testprints.default_sweep_values(current[tol], lambda x: testprints.valid_value(overrides, tol, x))
        _, values = testprints.parse_sweep(f"{tol}={text}")
        assert len(values) == 3 and current[tol] in values, (tol, text)
        assert all(testprints.valid_value(overrides, tol, x) for x in values), (tol, text)


def test_keyless_latch_slides_past_the_nub():
    """G's test latch: its base moved down along the slot (as it goes in from
    below) never touches the bottom, where the real base runs into the nub."""
    doc = _small()
    bottom = get(doc, "Bottom").Shape
    real = get(doc, "LatchBase").Shape
    keyless = testprints._keyless_base(doc)
    assert 15 < real.Volume - keyless.Volume < 25  # the key only

    def worst(base):
        overlaps = []
        for i in range(31):
            moved = base.copy()
            moved.translate(App.Vector(0, 0, -0.5 * i))
            overlaps.append(moved.common(bottom).Volume)
        return max(overlaps)

    assert worst(real) > 0.1
    assert worst(keyless) <= 1e-6
    solids = testprints.piece(doc, "latch_keyless")
    assert len(solids) == 3 and all(is_sound(s) for s in solids)


def test_detents_reach_their_slot_strips():
    """A bigger detent, a bigger nub: more material in the slot strip."""
    for name, param in (("hinge_rib", "hinge_detent"), ("lock_pad", "lock_detent")):
        lo = testprints.piece(_small((param, "0.1")), name)[0].Volume
        hi = testprints.piece(_small((param, "0.4")), name)[0].Volume
        assert hi > lo + 1e-3, (name, lo, hi)


def test_write_sweep_labels_and_partner():
    out = tempfile.mkdtemp(prefix="tp_ws_")
    paths, files, info, warnings = testprints.write_sweep(
        "hinge_detent", [0.4, 0.5], ["C9", "C11"], "hinge_rib", out, "C_09-11.stl",
        partner="leaf", partner_file="C_leaf.stl")
    assert sorted(os.path.basename(p) for p in paths) == ["C_09-11.stl", "C_leaf.stl"]
    assert len(_copies(files["C_09-11.stl"])) == 2 and not warnings
    assert near(info["parameters"]["hinge_detent"], 0.5)
    assert _same(files["C_leaf.stl"].Solids, testprints.piece(_small(("hinge_detent", "0.5")), "leaf"))
    unlabelled = testprints.piece(_small(("hinge_detent", "0.4")), "hinge_rib")[0]
    assert _copies(files["C_09-11.stl"])[0].Volume < unlabelled.Volume - 0.3  # engraved


def test_write_sweep_needs_a_label_per_value():
    try:
        testprints.write_sweep("latch_clearance", [0.2, 0.25], ["A1"], "latch", tempfile.mkdtemp(), "x.stl")
    except ValueError as e:
        assert "labels" in str(e)
    else:
        raise AssertionError("accepted")


def test_write_sweep_refuses_a_label_that_does_not_fit():
    from hwkan_gfbox.build import BuildError
    try:
        testprints.write_sweep("latch_clearance", [0.2], ["X" * 40], "latch", tempfile.mkdtemp(), "x.stl")
    except BuildError as e:
        assert "latch" in str(e) and "no bed face" in str(e), e
    else:
        raise AssertionError("an unlabelled plate was written")
