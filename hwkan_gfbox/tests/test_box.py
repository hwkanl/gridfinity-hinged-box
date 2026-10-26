import math

from hwkan_gfbox.shapes import get
from hwkan_gfbox.tests.helpers import built, first_cell, inside, is_sound, near, v


def test_box_is_one_sound_solid():
    shape = get(built(), "Box").Shape
    assert is_sound(shape) and len(shape.Solids) == 1


def test_box_bounding_box():
    doc = built()
    bb = get(doc, "Box").Shape.BoundBox
    assert near(bb.XLength, v(doc, "outer_w")) and near(bb.YLength, v(doc, "outer_d")), bb
    assert near(bb.XMin, -v(doc, "outer_w") / 2) and near(bb.YMin, -v(doc, "outer_d") / 2), bb
    assert near(bb.ZMin, 0) and near(bb.ZMax, v(doc, "box_h")), bb


def test_box_skins_and_interior():
    doc = built()
    cx, cy = first_cell(doc)
    assert inside(doc, "Box", cx, cy, v(doc, "floor_t") / 2)                     # floor
    assert inside(doc, "Box", v(doc, "outer_w") / 2 - v(doc, "wall_t") / 2, 0, 20)  # wall
    assert inside(doc, "Box", 0, 0, v(doc, "box_h") - v(doc, "top_t") / 2)     # ceiling
    assert not inside(doc, "Box", 0, 0, v(doc, "box_h") / 2)                   # bin space
    assert not inside(doc, "Box", cx, cy, v(doc, "floor_t") + 0.1)             # pocket


def test_box_volume_is_solid_minus_cavity():
    doc = built()
    expected = get(doc, "BoxSolid").Shape.Volume - get(doc, "Cavity").Shape.Volume
    assert near(get(doc, "Box").Shape.Volume, expected, 1e-6 * expected)


def test_box_outer_corners_are_concentric():
    doc = built()
    gw, gd, wt = v(doc, "grid_w"), v(doc, "grid_d"), v(doc, "wall_t")
    z = v(doc, "box_h") / 2

    def on_diagonal(t):
        k = t / math.sqrt(2)
        return -gw / 2 - k, -gd / 2 - k, z

    assert inside(doc, "Box", *on_diagonal(wt - 0.1))
    assert not inside(doc, "Box", *on_diagonal(wt + 0.1))
