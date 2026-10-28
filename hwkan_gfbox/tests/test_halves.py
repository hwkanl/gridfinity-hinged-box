import math

from hwkan_gfbox.shapes import get
from hwkan_gfbox.tests.helpers import built, inside, is_sound, near, v


def test_halves_are_single_sound_solids():
    doc = built()
    for label in ("Bottom", "Lid"):
        shape = get(doc, label).Shape
        assert is_sound(shape) and len(shape.Solids) == 1, label


def test_half_heights():
    doc = built()
    bb = get(doc, "Bottom").Shape.optimalBoundingBox()
    assert near(bb.ZMin, 0) and near(bb.ZMax, v(doc, "split_z") + v(doc, "lip_height") - v(doc, "lip_clearance")), bb
    bb = get(doc, "Lid").Shape.optimalBoundingBox()
    assert near(bb.ZMin, v(doc, "split_z")) and near(bb.ZMax, v(doc, "box_h") + v(doc, "stack_h")), bb  # the notches


def test_parting_line_footprint():
    doc = built()
    ribs = v(doc, "leaf_face_gap") + v(doc, "dovetail_t")  # the hinge ribs stand out of the bottom's back
    # The lid's knuckles stand out of its back (+Y); at the front (-Y) the lock's
    # pads stand out of the bottom by pad_front, its lips out of the lid by lock_lip_e.
    for label, back, front in (("Bottom", ribs, v(doc, "pad_front")),
                               ("Lid", v(doc, "hinge_axis_out") + v(doc, "knuckle_r"), v(doc, "lock_lip_e"))):
        bb = get(doc, label).Shape.optimalBoundingBox()
        assert near(bb.XLength, v(doc, "rim_w")) and near(bb.YLength, v(doc, "rim_d") + back + front), (label, bb)
        assert near(bb.XMin, -v(doc, "rim_w") / 2) and near(bb.YMin, -v(doc, "rim_d") / 2 - front), (label, bb)


def test_round_bead_and_channel():
    doc = built()
    gw, gd, sz = v(doc, "grid_w"), v(doc, "grid_d"), v(doc, "split_z")
    lt, lc, lh, wt, e = (v(doc, n) for n in ("lip_thickness", "lip_clearance", "lip_height",
                                             "wall_t", "rim_extra"))
    r, c = v(doc, "lip_r"), v(doc, "lip_c")
    assert near(r, 1.957143, 1e-6) and near(c, 1.257143, 1e-6), (r, c)
    m = (wt + e) / 2
    top = sz + lh - lc  # the bead's top, on the rim's middle line

    def d(t):
        return -gw / 2 - t

    assert inside(doc, "Bottom", d(m), 0, top - 0.05)               # bead is solid to its top
    assert not inside(doc, "Bottom", d(m), 0, top + 0.05)
    assert not inside(doc, "Lid", d(m), 0, sz + lh - 0.05)          # channel open to its depth
    assert inside(doc, "Lid", d(m), 0, sz + lh + 0.05)
    # at the split the channel is lip_thickness wide, the bead narrower by its clearance
    for side in (-1, 1):
        assert inside(doc, "Lid", d(m + side * (lt / 2 + 0.05)), 0, sz + 0.01), side
        assert not inside(doc, "Lid", d(m + side * (lt / 2 - 0.05)), 0, sz + 0.01), side
        half = math.sqrt((r - lc) ** 2 - c ** 2)
        assert inside(doc, "Bottom", d(m + side * (half - 0.05)), 0, sz + 0.01), side
        assert not inside(doc, "Bottom", d(m + side * (half + 0.05)), 0, sz + 0.01), side
    # the same section on the back wall and around a corner (on the diagonal)
    k = m / math.sqrt(2)
    for x, y in ((0, gd / 2 + m), (-gw / 2 - k, -gd / 2 - k)):
        assert inside(doc, "Bottom", x, y, top - 0.05) and not inside(doc, "Bottom", x, y, top + 0.05), (x, y)
        assert not inside(doc, "Lid", x, y, sz + lh - 0.05) and inside(doc, "Lid", x, y, sz + lh + 0.05), (x, y)
    assert inside(doc, "Lid", d(wt + e - 0.3), 0, sz + 0.5)          # lid widened to the rim


def test_rim_band():
    doc = built()
    gw, sz = v(doc, "grid_w"), v(doc, "split_z")
    hb, e, wt = v(doc, "rim_band_h"), v(doc, "rim_extra"), v(doc, "wall_t")

    def d(t):
        return -gw / 2 - t

    assert inside(doc, "Bottom", d(wt + e / 2), 0, sz - hb / 2)          # band is solid
    assert not inside(doc, "Bottom", d(wt + e / 2), 0, sz - hb - 1)      # nothing below it
    assert not inside(doc, "Bottom", d(wt + e - 0.3), 0, sz - hb + 0.2)  # chamfer: outer edge open just above the bottom
    assert inside(doc, "Bottom", d(wt + 0.1), 0, sz - hb + 0.2)          # band next to the wall


def _diagonal(doc, t, z):
    """Point at distance t from the -X/-Y cavity corner, along the outward diagonal."""
    k = t / math.sqrt(2)
    return -v(doc, "grid_w") / 2 - k, -v(doc, "grid_d") / 2 - k, z


def test_corner_pads():
    doc = built()
    gw, od, sz = v(doc, "grid_w"), v(doc, "outer_d"), v(doc, "split_z")
    wt, e, hb, reach = (v(doc, n) for n in ("wall_t", "rim_extra", "rim_band_h", "pad_reach"))
    x = -gw / 2 - (wt + e / 2)  # in the pad, outside the -X wall
    # BottomBare: the bed chamfer rounds the pad's floor-level edge (z < bottom_chamfer)
    assert inside(doc, "BottomBare", x, -(od / 2 - reach + 1), 0.5)              # pad solid at floor level
    assert not inside(doc, "BottomBare", x, -(od / 2 - reach - 1), 0.5)          # open just past pad_reach
    assert inside(doc, "Bottom", x, -(od / 2 - reach + 1), sz - hb - 1)      # pad solid below the band


def test_outer_corners_follow_rim_radius():
    doc = built()
    sz = v(doc, "split_z")
    r = v(doc, "wall_t") + v(doc, "rim_extra")
    for label, z in (("Bottom", sz / 2), ("Lid", sz + 3)):
        assert inside(doc, label, *_diagonal(doc, r - 0.1, z)), label
        assert not inside(doc, label, *_diagonal(doc, r + 0.1, z)), label
