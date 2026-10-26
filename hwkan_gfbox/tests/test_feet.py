from hwkan_gfbox.shapes import get
from hwkan_gfbox.tests.helpers import built, cell_centers, first_cell, inside, is_sound, near, v


def test_lid_with_feet_is_one_sound_solid():
    shape = get(built(), "Lid").Shape
    assert is_sound(shape) and len(shape.Solids) == 1


def test_every_foot_stands_on_the_rim_plane():
    doc = built()
    sz = v(doc, "split_z")
    for cx, cy in cell_centers(doc):
        assert inside(doc, "Lid", cx, cy, sz + 0.01), (cx, cy)
        assert inside(doc, "Lid", cx, cy, sz + 2), (cx, cy)
        assert not inside(doc, "Lid", cx, cy, sz - 0.01), (cx, cy)


def test_foot_bottom_size_follows_xy_clearance():
    # bottom half-width = 41.5 / 2 - clearance - (2.15 + 0.8)
    doc = built()  # clearance 0.25 -> 17.55
    cx, cy = first_cell(doc)
    z = v(doc, "split_z") + 0.01
    assert inside(doc, "Lid", cx + 17.4, cy, z)
    assert not inside(doc, "Lid", cx + 17.7, cy, z)
    doc0 = built(("feet_xy_clearance", "0"))  # -> 17.8
    cx, cy = first_cell(doc0)
    assert inside(doc0, "Lid", cx + 17.7, cy, v(doc0, "split_z") + 0.01)


def test_gaps_around_feet_are_open():
    doc = built()
    cx, cy = first_cell(doc)
    z = v(doc, "ceiling_z") - 0.2
    assert not inside(doc, "Lid", cx + v(doc, "gf_pitch") / 2, cy, z)   # between feet
    assert not inside(doc, "Lid", -v(doc, "grid_w") / 2 + 0.1, cy, z)   # foot to wall
    assert inside(doc, "Lid", cx, cy, v(doc, "ceiling_z") + 0.1)         # ceiling


def test_feet_z_clearance_moves_the_rim_with_the_feet():
    doc = built(("feet_z_clearance", "1"))
    sz = v(doc, "split_z")
    assert near(sz, 45.65)
    assert near(get(doc, "Lid").Shape.optimalBoundingBox().ZMin, sz)
    cx, cy = first_cell(doc)
    assert inside(doc, "Lid", cx, cy, sz + 0.01)
