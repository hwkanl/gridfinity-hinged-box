import json
import os
import shutil
import tempfile

import FreeCAD as App
import Mesh
import Part

from hwkan_gfbox.tests.helpers import built, cell_centers, near, v
from hwkan_gfbox.export import ExportError, check_leaves, check_part, export, latch_print_shapes, print_shape, stl_name
from hwkan_gfbox.shapes import get


def test_stl_names_carry_the_grid_size():
    doc = built()
    assert stl_name(doc, "lid") == "lid_3x2x6.stl"
    assert stl_name(doc, "bottom") == "bottom_3x2x6.stl"


def test_print_shapes_sit_on_the_bed_centered():
    doc = built()
    for part in ("bottom", "lid"):
        bb = print_shape(doc, part).optimalBoundingBox()
        assert near(bb.ZMin, 0) and near(bb.XMin + bb.XMax, 0) and near(bb.YMin + bb.YMax, 0), (part, bb)
    assert near(print_shape(doc, "lid").optimalBoundingBox().ZMax, v(doc, "lid_h"))


def test_lid_prints_with_rim_and_every_foot_on_the_bed():
    doc = built()
    lid = print_shape(doc, "lid").Solids[0]  # the lid; the leaves follow
    on_bed = [(-v(doc, "rim_w") / 2 + 0.3, 0)] + cell_centers(doc)
    for x, y in on_bed:
        assert lid.isInside(App.Vector(x, y, 0.01), 1e-6, True), (x, y)


def test_lid_print_holds_the_leaves_on_the_bed():
    doc = built()
    printed = print_shape(doc, "lid")
    n = int(v(doc, "hinge_count"))
    assert len(printed.Solids) == 1 + n, len(printed.Solids)
    lid, leaves = printed.Solids[0], printed.Solids[1:]
    assert near(lid.Volume, get(doc, "Lid").Shape.Volume, 1e-6 * lid.Volume)
    for leaf in leaves:
        assert near(leaf.optimalBoundingBox().ZMin, 0, 1e-6), leaf.optimalBoundingBox()
        assert leaf.common(lid).Volume < 1e-6


def test_export_rejects_a_missing_leaf():
    doc = built()
    try:
        check_leaves(Part.makeCompound(get(doc, "Leaves").Shape.Solids[:-1]), int(v(doc, "hinge_count")))
    except ExportError as e:
        assert "leaves" in str(e), str(e)
    else:
        raise AssertionError("wrong leaf count accepted")


def test_latch_prints_three_parts_on_the_bed():
    doc = built()
    printed = print_shape(doc, "latch")
    assert len(printed.Solids) == 3
    lc = v(doc, "latch_clearance")
    for s in printed.Solids:
        check_part("latch", s)
        assert near(s.optimalBoundingBox().ZMin, 0, 1e-6), s.optimalBoundingBox()
    a, b, c = printed.Solids
    for p, q in ((a, b), (b, c), (a, c)):
        assert p.distToShape(q)[0] >= lc - 1e-3, p.distToShape(q)[0]
    bb = printed.optimalBoundingBox()
    assert near(bb.XMin + bb.XMax, 0) and near(bb.YMin + bb.YMax, 0)
    assert near(bb.XLength, v(doc, "latch_w"), 1e-6) and near(bb.ZLength, 10, 0.05), bb
    assert stl_name(doc, "latch") == "latch.stl"


def test_check_part_rejects_two_solids():
    two = Part.makeCompound([Part.makeBox(1, 1, 1), Part.makeBox(1, 1, 1, App.Vector(5, 0, 0))])
    try:
        check_part("lid", two)
    except ExportError as e:
        assert "2 solids" in str(e), str(e)
    else:
        raise AssertionError("two solids accepted")


def test_export_writes_solid_stls_and_build_info():
    doc = built()
    out = tempfile.mkdtemp()
    try:
        paths = export(doc, ["bottom", "lid", "latch"], out)
        assert [os.path.basename(p) for p in paths] == ["bottom_3x2x6.stl", "lid_3x2x6.stl", "latch.stl"]
        for path in paths:
            mesh = Mesh.Mesh(path)
            assert mesh.CountFacets > 0 and mesh.isSolid(), path
            assert near(mesh.BoundBox.ZMin, 0, 1e-4), (path, mesh.BoundBox)
        lid_mesh = Mesh.Mesh(paths[1])
        assert lid_mesh.countComponents() == 1 + int(v(doc, "hinge_count")), lid_mesh.countComponents()
        assert Mesh.Mesh(paths[2]).countComponents() == 3
        with open(os.path.join(out, "build_info.json")) as f:
            info = json.load(f)
        assert info["parameters"]["gf_x"] == 3 and info["freecad"].startswith("1.")
        assert info["preset"] == "default", info["preset"]
    finally:
        shutil.rmtree(out)
