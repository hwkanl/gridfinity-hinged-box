import FreeCAD as App

from hwkan_gfbox.build import build
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import ParamError
from hwkan_gfbox.tests.helpers import built, first_cell, inside, is_sound, near, v


def test_cavity_is_one_sound_solid():
    shape = get(built(), "Cavity").Shape
    assert is_sound(shape) and len(shape.Solids) == 1, (is_sound(shape), len(shape.Solids))


def test_cavity_bounding_box():
    doc = built()
    bb = get(doc, "Cavity").Shape.BoundBox
    gw, gd = v(doc, "grid_w"), v(doc, "grid_d")
    assert near(bb.XMin, -gw / 2) and near(bb.XMax, gw / 2), bb
    assert near(bb.YMin, -gd / 2) and near(bb.YMax, gd / 2), bb
    assert near(bb.ZMin, v(doc, "floor_t")) and near(bb.ZMax, v(doc, "ceiling_z")), bb


def test_pocket_profile():
    doc = built()
    cx, cy = first_cell(doc)
    floor = v(doc, "floor_t")
    # pocket bottom: half-width 42/2 - 2.15 - 0.7 = 18.15 at the floor
    assert inside(doc, "Cavity", cx, cy, floor + 0.1)
    assert inside(doc, "Cavity", cx + 18.1, cy, floor + 0.05)
    assert not inside(doc, "Cavity", cx + 18.3, cy, floor + 0.05)
    # vertical section: half-width 18.85
    assert inside(doc, "Cavity", cx + 18.8, cy, floor + 1.5)
    assert not inside(doc, "Cavity", cx + 18.9, cy, floor + 1.5)


def test_ridges_are_clipped_and_corner_posts_kept():
    doc = built()
    cx, cy = first_cell(doc)
    clip_z = v(doc, "floor_t") + v(doc, "bp_h") - v(doc, "ridge_clip")
    gw, gd, p = v(doc, "grid_w"), v(doc, "grid_d"), v(doc, "gf_pitch")
    # the ridge between cell 0 and cell 1 is material up to clip_z ...
    assert not inside(doc, "Cavity", cx + p / 2, cy, clip_z - 0.1)
    # ... and open bin space above it
    assert inside(doc, "Cavity", cx + p / 2, cy, clip_z + 0.1)
    # corner post at the cavity corner
    assert not inside(doc, "Cavity", -gw / 2 + 0.3, -gd / 2 + 0.3, clip_z - 0.1)
    # the smallest box still gives one sound cavity solid
    smallest = get(built(("gf_x", "2"), ("gf_y", "2")), "Cavity").Shape
    assert is_sound(smallest) and len(smallest.Solids) == 1


def test_cavity_follows_grid_size():
    doc = built(("gf_x", "4"), ("gf_y", "2"))
    shape = get(doc, "Cavity").Shape
    assert is_sound(shape) and len(shape.Solids) == 1
    bb = shape.BoundBox
    c = v(doc, "bin_clearance")
    assert near(bb.XMax, 84 + c) and near(bb.YMax, 42 + c), bb  # bin_clearance all around
    # the grid is centered, so the extra size is a strip along every wall:
    # no pocket there (floor), open above the pockets
    pocket_top = v(doc, "floor_t") + v(doc, "bp_h")
    x, y = 21, 21  # a cell center (gf_x 4, gf_y 2)
    for px, py, ix, iy in ((x, 42 + c / 2, x, 40), (x, -42 - c / 2, x, -40),
                           (84 + c / 2, y, 82, y), (-84 - c / 2, y, -82, y)):
        assert not inside(doc, "Cavity", px, py, pocket_top - 1) and inside(doc, "Cavity", px, py, pocket_top + 1)
        # the outer pocket, 2 mm in from its cell's edge (its wall slopes 45 deg)
        assert inside(doc, "Cavity", ix, iy, pocket_top - 1), (ix, iy)


def test_rejected_parameters_leave_no_document_open():
    before = set(App.listDocuments())
    try:
        build([("gf_x", "0")], doc_name="rejected")
    except ParamError:
        pass
    else:
        raise AssertionError("gf_x=0 was accepted")
    assert set(App.listDocuments()) == before
