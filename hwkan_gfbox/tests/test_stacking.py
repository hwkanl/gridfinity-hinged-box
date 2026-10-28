"""Stacking: notches on the lid top's corners, grooves under the bottom's."""
import FreeCAD as App

from hwkan_gfbox.shapes import get
from hwkan_gfbox.tests.helpers import built, inside, is_sound, near, v


def _wall_x(doc, t):
    """x of the point t outward from the cavity's -X wall."""
    return -v(doc, "grid_w") / 2 - t


def test_notches_and_grooves_derived_defaults():
    doc = built()
    for name, want in (("stack_in", 0.4), ("stack_out", 2.6), ("groove_in", 0.4 - 0.2 * 2 ** 0.5),
                       ("groove_out", 2.6 + 0.2 * 2 ** 0.5), ("groove_d", 0.9)):
        assert near(v(doc, name), want), (name, v(doc, name))


def test_notch_profile_at_each_corner():
    doc = built()
    top, h, mid = v(doc, "box_h"), v(doc, "stack_h"), v(doc, "wall_t") / 2
    od, ow = v(doc, "outer_d"), v(doc, "outer_w")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (v(doc, "grid_w") / 2 + mid), sy * (od / 2 - 4)  # wall middle, 4 mm from the corner (past its rounding)
            assert inside(doc, "Lid", x, y, top + h - 0.05), (sx, sy)            # up to stack_h
            assert not inside(doc, "Lid", x, y, top + h + 0.05), (sx, sy)
            # 45 deg sides: at half height the notch is stack_w - stack_h wide
            half = (v(doc, "stack_w") - h) / 2
            assert inside(doc, "Lid", x - sx * (half - 0.05), y, top + h / 2), (sx, sy)
            assert not inside(doc, "Lid", x - sx * (half + 0.05), y, top + h / 2), (sx, sy)
            # along the other wall too, and only within stack_reach of the corner
            x2, y2 = sx * (ow / 2 - 4), sy * (v(doc, "grid_d") / 2 + mid)
            assert inside(doc, "Lid", x2, y2, top + 0.3), (sx, sy)
            reach = ow / 2 - v(doc, "stack_reach")
            assert inside(doc, "Lid", sx * (reach + 0.1), y2, top + 0.3)
            assert not inside(doc, "Lid", sx * (reach - 0.1), y2, top + 0.3)
    assert not inside(doc, "Lid", 0, 0, top + 0.3)  # nothing in the middle


def test_groove_profile_and_reach():
    doc = built()
    d, od = v(doc, "groove_d"), v(doc, "outer_d")
    y = -od / 2 + 4  # past the corner rounding
    for t in (v(doc, "groove_in") + 0.05, v(doc, "groove_out") - 0.05):   # open at the bed, edge to edge
        assert not inside(doc, "Bottom", _wall_x(doc, t), y, 0.01), t
    assert inside(doc, "Bottom", _wall_x(doc, v(doc, "groove_in") - 0.05), y, 0.01)
    mid = v(doc, "wall_t") / 2
    assert not inside(doc, "Bottom", _wall_x(doc, mid), y, d - 0.05) and inside(doc, "Bottom", _wall_x(doc, mid), y, d + 0.05)
    reach = od / 2 - v(doc, "stack_reach") - v(doc, "stack_clearance")
    t = v(doc, "groove_in") + 0.2  # inside the groove, clear of the wall's bed chamfer
    assert not inside(doc, "Bottom", _wall_x(doc, t), -(reach + 0.1), 0.15)
    assert inside(doc, "Bottom", _wall_x(doc, t), -(reach - 0.1), 0.15)


def test_parts_stay_sound_and_boxes_stack():
    for doc in (built(), built(("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3"))):
        lid, bottom = get(doc, "Lid").Shape, get(doc, "Bottom").Shape
        assert is_sound(lid) and len(lid.Solids) == 1 and is_sound(bottom) and len(bottom.Solids) == 1
        above = bottom.copy()
        above.translate(App.Vector(0, 0, v(doc, "box_h")))
        notches = get(doc, "Notches").Shape
        assert above.common(lid).Volume < 1e-6
        assert abs(above.distToShape(notches)[0] - v(doc, "stack_clearance")) < 1e-4
        # seated: slid stack_clearance * 2 sideways it hits the notches
        above.translate(App.Vector(2 * v(doc, "stack_side") + 0.1, 0, 0))
        assert above.common(notches).Volume > 1e-6
