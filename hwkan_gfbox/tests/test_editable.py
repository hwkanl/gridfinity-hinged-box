import json
import os
import shutil
import tempfile

import FreeCAD as App
import Mesh
import Part

from hwkan_gfbox import editable
from hwkan_gfbox.build import BuildError
from hwkan_gfbox.export import PARTS, ExportError, print_shape, stl_name
from hwkan_gfbox.tests.helpers import built, is_sound, near


def _bodies(out):
    return [o for o in out.Objects if o.TypeId == "PartDesign::Body"]


def test_edit_box_gives_one_body_per_stl_like_the_print_shapes():
    doc = built()
    out = editable.make_editable(doc)
    try:
        bodies = _bodies(out)
        assert [b.Label for b in bodies] == [os.path.splitext(stl_name(doc, p))[0] for p in PARTS]
        prev_xmax = None
        for body, part in zip(bodies, PARTS):
            want, got = print_shape(doc, part), body.Shape
            assert len(got.Solids) == len(want.Solids), part
            assert near(got.Volume, want.Volume, 1e-6 * want.Volume), part
            a, b = got.copy().optimalBoundingBox(False), want.copy().optimalBoundingBox(False)
            for attr in ("XLength", "YLength", "ZLength", "YMin", "ZMin"):
                assert near(getattr(a, attr), getattr(b, attr), 1e-5), (part, attr)
            if prev_xmax is not None:
                assert near(a.XMin, prev_xmax + editable.GAP, 1e-5), part
            prev_xmax = a.XMax
            assert is_sound(got), part
            assert body.BaseFeature.Placement.isIdentity(), part
        for obj in out.Objects:
            assert all(dep.Document is out for dep in obj.OutList), obj.Label
    finally:
        App.closeDocument(out.Name)


def test_an_edited_box_is_recognised_after_save_and_reopen():
    out = editable.make_editable(built())
    tmp = tempfile.mkdtemp()
    try:
        assert editable.is_edited(out) and not editable.is_edited(built())
        assert editable.build_info(out)["parameters"]["gf_x"] == 3
        path = os.path.join(tmp, "my_box.FCStd")
        out.saveAs(path)
        App.closeDocument(out.Name)
        out = App.openDocument(path)
        assert out.Name == "my_box" and editable.is_edited(out)
    finally:
        App.closeDocument(out.Name)
        shutil.rmtree(tmp)


def test_export_edited_writes_each_body_with_its_features():
    doc = built()
    out = editable.make_editable(doc)
    tmp = tempfile.mkdtemp()
    try:
        lid = _bodies(out)[1]
        bb = lid.Shape.optimalBoundingBox(False)
        knob = out.addObject("PartDesign::AdditiveBox", "Knob")  # stands in for the user's feature
        knob.Length = knob.Width = knob.Height = 5
        knob.Placement.Base = App.Vector((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, bb.ZMax - 0.5)
        lid.addObject(knob)
        out.recompute()
        paths = editable.export_edited(out, tmp)
        assert [os.path.basename(p) for p in paths] == [f"{b.Label}.stl" for b in _bodies(out)]
        for path in paths:
            mesh = Mesh.Mesh(path)
            assert mesh.isSolid() and near(mesh.BoundBox.ZMin, 0, 1e-4), path
        lid_height = Mesh.Mesh(paths[1]).BoundBox.ZLength
        assert near(lid_height, bb.ZLength + 4.5, 1e-3), lid_height  # the knob is in the STL
        with open(os.path.join(tmp, "build_info.json")) as f:
            info = json.load(f)
        assert info["edited"] is True and info["parameters"]["gf_x"] == 3
    finally:
        App.closeDocument(out.Name)
        shutil.rmtree(tmp)


def _raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


def test_export_edited_refuses_a_failed_feature_and_writes_nothing():
    out = editable.make_editable(built())
    tmp = tempfile.mkdtemp()
    try:
        lid = _bodies(out)[1]
        pocket = out.addObject("PartDesign::Pocket", "NoProfile")
        lid.addObject(pocket)
        out.recompute()
        assert _raises(BuildError, lambda: editable.export_edited(out, tmp))
        assert os.listdir(tmp) == []
    finally:
        App.closeDocument(out.Name)
        shutil.rmtree(tmp)


def test_export_edited_refuses_bad_body_labels_and_writes_nothing():
    out = editable.make_editable(built())
    tmp = tempfile.mkdtemp()
    try:
        bodies = _bodies(out)
        old = bodies[0].Label
        bodies[0].Label = "a/b"
        assert _raises(ExportError, lambda: editable.export_edited(out, tmp))
        bodies[0].Label = bodies[1].Label.upper()
        assert _raises(ExportError, lambda: editable.export_edited(out, tmp))
        assert os.listdir(tmp) == []
        bodies[0].Label = old
    finally:
        App.closeDocument(out.Name)
        shutil.rmtree(tmp)


def test_edit_box_keeps_a_saved_document_and_replaces_an_unsaved_one():
    doc = built()
    first = editable.make_editable(doc)
    tmp = tempfile.mkdtemp()
    third = None
    second = None
    try:
        assert editable.unsaved_edit_document() is first
        first.saveAs(os.path.join(tmp, "mine.FCStd"))
        assert editable.unsaved_edit_document() is None
        second = editable.make_editable(doc)
        assert second is not first and App.listDocuments().get(first.Name) is first
        assert editable.is_edited(second)
        assert editable.unsaved_edit_document() is second
        third = editable.make_editable(doc)
        assert editable.unsaved_edit_document() is third
        assert App.listDocuments().get(first.Name) is first
    finally:
        for d in (first, third):
            if d is not None and d.Name in App.listDocuments():
                App.closeDocument(d.Name)
        shutil.rmtree(tmp)


def test_a_damaged_meta_value_is_an_export_error():
    out = editable.make_editable(built())
    try:
        for bad in ("{not json", "{}", json.dumps({"parameters": {}})):
            meta = out.Meta
            meta[editable.META_KEY] = bad
            out.Meta = meta
            assert _raises(ExportError, lambda: editable.build_info(out)), bad
    finally:
        App.closeDocument(out.Name)
