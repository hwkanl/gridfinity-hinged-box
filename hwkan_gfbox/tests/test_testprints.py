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


EXPECTED_SOLIDS = {"hinge_lid": 2, "hinge_rib": 1, "leaf": 1, "latch": 3, "lock_pad": 1, "lock_front": 1,
                   "latch_base": 1, "latch_keyless": 3}


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
    front = testprints.PIECES["lock_front"][0](doc)[0]
    closed = get(doc, "Bottom").Shape.fuse(get(doc, "Lid").Shape)  # lock_front holds both halves
    assert _covers(closed, front, near_x("LockPads", lc) + near_x("LockLips", lc))


def test_lock_front_is_the_pad_strip_and_the_lid_above_it():
    """One solid: the pad strip's material and the lid's at the lock, the
    lid's on top (from the parting line up), nothing else."""
    doc = _small()
    pad = testprints.PIECES["lock_pad"][0](doc)[0]
    front = testprints.PIECES["lock_front"][0](doc)[0]
    lid = get(doc, "Lid").Shape
    split = v(doc, "split_z")
    above = front.cut(pad)
    assert above.Volume > 100 and abs(above.common(lid).Volume - above.Volume) <= 1e-3
    assert above.optimalBoundingBox(False).ZMin >= split - 1e-6
    assert front.common(pad).Volume >= pad.Volume - 1e-3


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
    for name in ("hinge_lid", "latch", "lock_pad", "lock_front"):
        assert _same(testprints.piece(small, name), testprints.piece(default, name)), name


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


def test_every_value_swept_piece_takes_a_label():
    doc = _small()
    for name in ("hinge_lid", "leaf", "latch", "latch_base"):
        solids = testprints.piece(doc, name)
        k = testprints.PIECES[name][2]
        labelled, ok = testprints.engrave(solids[k], "0.20")
        assert ok, name
        assert is_sound(labelled) and len(labelled.Solids) == 1, name
        lost = solids[k].Volume - labelled.Volume
        assert 0.3 < lost < 40, (name, lost)
        b0, b1 = solids[k].optimalBoundingBox(), labelled.optimalBoundingBox()
        assert near(b0.ZMin, b1.ZMin, 1e-6) and near(b0.ZMax, b1.ZMax, 1e-6), name



def _run(preset=None):
    out = tempfile.mkdtemp(prefix="tp_")
    paths, files, warnings = testprints.run(preset, out)
    return out, paths, files, warnings


def test_a_preset_writes_the_four_parts():
    from hwkan_gfbox import presets
    preset = presets.Preset("tp_test", "tp_test", dict(presets.load(presets.DEFAULT).values, hinge_clearance=0.3))
    out, paths, files, _ = _run(preset)
    assert sorted(os.path.basename(p) for p in paths) == sorted(f"{n}.stl" for n in testprints.TEST_SET)
    assert testprints.TEST_SET == ("hinge_lid", "hinge_rib", "latch", "lock_front")
    assert all(os.path.getsize(p) > 1000 for p in paths)
    for p in paths:  # on the bed as the slicer sees it
        assert near(Mesh.Mesh(p).BoundBox.ZMin, 0, 1e-6), p
    info = json.load(open(os.path.join(out, "build_info.json")))
    assert info["parameters"]["gf_x"] == 2 and near(info["parameters"]["hinge_clearance"], 0.3)
    assert info["preset"] == "tp_test", info["preset"]
    default = testprints.piece(_small(), "hinge_lid")
    assert _same(files["hinge_lid.stl"].Solids, testprints.piece(_small(("hinge_clearance", "0.3")), "hinge_lid"))
    assert not _same(files["hinge_lid.stl"].Solids, default)  # the preset's value reached the piece
    assert not any(d.startswith(testprints.DOC_PREFIX) for d in App.listDocuments())


def test_gui_preset_is_the_open_box_s_or_the_default():
    from hwkan_gfbox import presets
    doc = params_document([("gf_x", "4")])[0]
    try:
        assert testprints.gui_preset() == presets.DEFAULT  # the default box's preset
    finally:
        App.closeDocument(doc.Name)
    assert testprints.gui_preset() == presets.DEFAULT


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


WALL_STRIPS = ("hinge_lid", "hinge_rib", "lock_pad", "lock_front")
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
    test sweeps."""
    doc = _small()
    cases = [(n, "C13") for n in CALIBRATION_PIECES]
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
    for name in ("hinge_lid", "hinge_rib", "lock_pad", "lock_front"):
        zmin = Part.makeCompound(testprints.piece(doc, name)).optimalBoundingBox(False).ZMin
        assert near(zmin, 0, 1e-6), (name, zmin)


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
    for name, param in (("hinge_rib", "hinge_detent_height"), ("lock_pad", "latch_detent_height")):
        lo = testprints.piece(_small((param, "0.1")), name)[0].Volume
        hi = testprints.piece(_small((param, "0.4")), name)[0].Volume
        assert hi > lo + 1e-3, (name, lo, hi)


def test_write_sweep_labels_and_partner():
    out = tempfile.mkdtemp(prefix="tp_ws_")
    paths, files, info, warnings = testprints.write_sweep(
        "hinge_detent_height", [0.4, 0.5], ["C9", "C11"], "hinge_rib", out, "C_09-11.stl",
        partner="leaf", partner_file="C_leaf.stl")
    assert sorted(os.path.basename(p) for p in paths) == ["C_09-11.stl", "C_leaf.stl"]
    assert len(_copies(files["C_09-11.stl"])) == 2 and not warnings
    assert near(info["parameters"]["hinge_detent_height"], 0.5)
    assert _same(files["C_leaf.stl"].Solids, testprints.piece(_small(("hinge_detent_height", "0.5")), "leaf"))
    unlabelled = testprints.piece(_small(("hinge_detent_height", "0.4")), "hinge_rib")[0]
    assert _copies(files["C_09-11.stl"])[0].Volume < unlabelled.Volume - 0.3  # engraved


def _copies(plate):
    return plate.SubShapes  # one sub-compound per copy


def test_a_bad_sweep_value_is_named_before_building():
    import time
    t = time.time()
    try:
        testprints.write_sweep("hinge_clearance", [0.2, 1.5], ["A1", "A2"], "hinge_lid", tempfile.mkdtemp(), "x.stl")
    except ParamError as e:
        assert "hinge_clearance = 1.5" in str(e), str(e)
    else:
        raise AssertionError("hinge_clearance 1.5 was accepted")
    assert time.time() - t < 3, "validated only after building"
    assert not any(d.startswith(testprints.DOC_PREFIX) for d in App.listDocuments())


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
