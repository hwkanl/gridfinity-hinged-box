import math

import FreeCAD as App
import Part

from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import ParamError, create_params_sheet, set_param, value
from hwkan_gfbox.tests.helpers import built, inside, is_sound, near, v


def _sheet(*overrides):
    s = create_params_sheet(App.newDocument("hinge_sheet_test"))
    for name, text in overrides:
        set_param(s, name, text)
    s.Document.recompute()
    return s


def test_hinge_derived_defaults():
    s = _sheet()
    assert value(s, "hinge_count") == 2
    assert near(value(s, "knuckle_r"), 3.875) and near(value(s, "hinge_axis_z"), 3.875)
    assert near(value(s, "pin_len"), 2.424, 1e-3), value(s, "pin_len")
    assert near(value(s, "pin_apex"), 2.979, 1e-3) and near(value(s, "pin_tip_c"), 1.424, 1e-3)
    assert near(value(s, "pin_tan_z"), 2.067, 1e-3) and near(value(s, "pin_tan_r"), 0.766, 1e-3)
    assert near(value(s, "hinge_len"), 16)
    assert near(value(s, "pin_angle"), 50), value(s, "pin_angle")
    assert near(value(s, "knuckle_back"), 8.375), value(s, "knuckle_back")
    assert near(value(s, "knuckle_flare_ext"), 4.835, 1e-3), value(s, "knuckle_flare_ext")
    assert near(value(s, "hinge_root_len"), 25.67, 1e-2), value(s, "hinge_root_len")


def test_hinge_count_is_an_input():
    assert value(_sheet(), "hinge_count") == 2
    s = _sheet(("hinge_count", "3"))
    assert value(s, "hinge_count") == 3 and near(value(s, "hinge_pitch"), 42), value(s, "hinge_pitch")
    assert value(_sheet(("gf_x", "8")), "hinge_count") == 2  # no longer follows the grid width


def test_three_hinges_build():
    doc = built(("hinge_count", "3"))
    assert [round(c, 6) for c in hinge_centers(doc)] == [-42.0, 0.0, 42.0]
    assert len(get(doc, "LidKnuckles").Shape.Solids) == 6
    assert is_sound(get(doc, "Lid").Shape) and len(get(doc, "Lid").Shape.Solids) == 1


def test_pin_angle_override():
    s = _sheet(("pin_angle", "45"))
    assert near(value(s, "pin_angle"), 45), value(s, "pin_angle")
    assert near(value(s, "pin_apex"), 2.5, 1e-9), value(s, "pin_apex")
    set_param(s, "pin_angle", "60 deg")
    s.Document.recompute()
    assert near(value(s, "pin_angle"), 60)
    for text in ("45 mm", "steep"):
        try:
            set_param(s, "pin_angle", text)
        except ParamError as e:
            assert "expected a number (deg)" in str(e), str(e)
        else:
            raise AssertionError(f"pin_angle={text} accepted")


def hinge_centers(doc):
    n, gw = int(v(doc, "hinge_count")), v(doc, "grid_w")
    return [-gw / 2 + gw / (2 * n) + k * gw / n for k in range(n)]


def test_default_hinge_centers():
    assert [round(c, 6) for c in hinge_centers(built())] == [-31.5, 31.5]


def test_lid_knuckles_object():
    doc = built()
    shape = get(doc, "LidKnuckles").Shape
    assert is_sound(shape)
    assert len(shape.Solids) == 2 * int(v(doc, "hinge_count")), len(shape.Solids)
    bb = shape.BoundBox
    gap, ln = v(doc, "knuckle_gap"), v(doc, "knuckle_len")
    c = hinge_centers(doc)
    ext = v(doc, "knuckle_flare_ext")
    # the flare reaches knuckle_flare_ext beyond the nominal end at the lid face
    # (and slightly further inside the overlap into the lid)
    ov, tn = v(doc, "overlap"), math.tan(math.radians(v(doc, "knuckle_flare")))
    assert near(bb.XMin, c[0] - gap / 2 - ln - ext - ov * tn, 1e-3), bb
    assert near(bb.XMax, c[-1] + gap / 2 + ln + ext + ov * tn, 1e-3), bb
    assert near(bb.ZMin, v(doc, "split_z")) and near(bb.ZMax, v(doc, "box_h")), bb


def test_lid_is_still_one_sound_solid_with_knuckles():
    shape = get(built(), "Lid").Shape
    assert is_sound(shape) and len(shape.Solids) == 1


def probe_geometry(doc):
    return dict(ya=v(doc, "rim_d") / 2 + v(doc, "hinge_axis_out"),
                za=v(doc, "split_z") + v(doc, "hinge_axis_z"))


def _check_knuckle_probes(doc):
    g = probe_geometry(doc)
    ya, za, sz, rd = g["ya"], g["za"], v(doc, "split_z"), v(doc, "rim_d")
    gap, ln, r = v(doc, "knuckle_gap"), v(doc, "knuckle_len"), v(doc, "knuckle_r")
    out_axis = v(doc, "hinge_axis_out")
    # the arc's lower back quarter, at -60 deg (where revision 1 had its 45 deg underside)
    ca, sa = math.cos(math.radians(60)), math.sin(math.radians(60))
    for c in hinge_centers(doc):
        for xk in (c - gap / 2 - ln / 2, c + gap / 2 + ln / 2):
            assert inside(doc, "Lid", xk, rd / 2 + out_axis / 2, v(doc, "box_h") - 0.1)
            assert inside(doc, "Lid", xk, ya, za)
            assert not inside(doc, "Lid", xk, ya + r + 0.1, za)
            assert not inside(doc, "Lid", xk, ya + (r + 0.1) * ca, za - (r + 0.1) * sa)
            assert inside(doc, "Lid", xk, ya + (r - 0.1) * ca, za - (r - 0.1) * sa)
            # the knuckle stands on the bed up to below the axis, and not behind it
            assert inside(doc, "Lid", xk, ya - 0.1, sz + 0.01)
            assert not inside(doc, "Lid", xk, ya + 0.5, sz + 0.01)
            assert inside(doc, "Lid", xk, rd / 2 + out_axis / 2, sz + 0.01)
            # outside the knuckle's length
            assert not inside(doc, "Lid", c, rd / 2 + out_axis / 2, sz + 1)


def test_knuckle_profile_probes():
    _check_knuckle_probes(built())


def test_knuckle_rebuilds_for_tuned_axis():
    # The old hinge_axis_out=2 case was dropped: the leaf can't fit (its front would not clear the
    # lid face as it swings, and leaf_r <= hinge_axis_out - hinge_clearance). 4.4 is near the minimum.
    for overrides in ([("hinge_axis_out", "4.4")], [("hinge_axis_out", "6")], [("top_t", "4"), ("hinge_axis_out", "6")]):
        doc = built(*overrides)
        shape = get(doc, "Lid").Shape
        assert is_sound(shape) and len(shape.Solids) == 1, overrides
        _check_knuckle_probes(doc)


def _check_flare_probes(doc, flare=None):
    flare = v(doc, "knuckle_flare") if flare is None else flare
    tn = math.tan(math.radians(flare))
    rd, sz, bh = v(doc, "rim_d"), v(doc, "split_z"), v(doc, "box_h")
    gap, ln, back = v(doc, "knuckle_gap"), v(doc, "knuckle_len"), v(doc, "knuckle_back")
    zm = (sz + bh) / 2
    cos = math.cos(math.radians(flare))
    d = 0.1 / cos  # 0.1 mm measured across the tilted face
    for c in hinge_centers(doc):
        for side in (-1, 1):
            out = 0.1
            end = gap / 2 + ln + (back - out) * tn  # |x - c| of the flared end
            assert inside(doc, "Lid", c + side * (end - d), rd / 2 + out, zm)
            assert not inside(doc, "Lid", c + side * (end + d), rd / 2 + out, zm)
            # near the knuckle's back the end is at the nominal position
            out = back - 0.2
            end = gap / 2 + ln + (back - out) * tn
            assert inside(doc, "Lid", c + side * (end - d), rd / 2 + out, zm)
            assert not inside(doc, "Lid", c + side * (end + d), rd / 2 + out, zm)


def test_flare_probes():
    _check_flare_probes(built())


def test_zero_flare_gives_perpendicular_ends():
    doc = built(("knuckle_flare", "0"))
    assert near(v(doc, "knuckle_flare_ext"), 0) and near(v(doc, "hinge_root_len"), 16)
    _check_flare_probes(doc, 0)
    _check_knuckle_probes(doc)
    assert is_sound(get(doc, "Lid").Shape) and len(get(doc, "Lid").Shape.Solids) == 1
    bb = get(doc, "LidKnuckles").Shape.BoundBox
    c = hinge_centers(doc)
    assert near(bb.XMin, c[0] - 8, 1e-6) and near(bb.XMax, c[-1] + 8, 1e-6), bb


def test_pin_probes():
    doc = built()
    g = probe_geometry(doc)
    gap, pl = v(doc, "knuckle_gap"), v(doc, "pin_len")
    for c in hinge_centers(doc):
        for face, sign in ((c - gap / 2, 1), (c + gap / 2, -1)):
            assert inside(doc, "Lid", face + sign * (pl - 0.1), g["ya"], g["za"])
            assert not inside(doc, "Lid", face + sign * (pl + 0.1), g["ya"], g["za"])
        assert not inside(doc, "Lid", c, g["ya"], g["za"])


def test_lid_opens_without_touching_the_bottom():
    # The lid's edge behind the channel swings forward and up as the lid
    # opens; it must lift off the round bead instead of running into it.
    doc = built()
    rd, sz = v(doc, "rim_d"), v(doc, "split_z")
    ay, az = rd / 2 + v(doc, "hinge_axis_out"), sz + v(doc, "hinge_axis_z")
    crop = Part.makeBox(2 * v(doc, "rim_w"), 30, 40, App.Vector(-v(doc, "rim_w"), rd / 2 - 20, sz - 15))
    lid, bottom = get(doc, "Lid").Shape.common(crop), get(doc, "Bottom").Shape.common(crop)
    # Contact, if any, comes in the first few degrees: sample those finely.
    for angle in [a / 2 for a in range(0, 20)] + list(range(10, 91, 5)):
        opened = lid.copy()
        opened.rotate(App.Vector(0, ay, az), App.Vector(1, 0, 0), -angle)  # -angle: the front lifts
        assert opened.common(bottom).Volume < 1e-6, angle


def test_detent_nub_holds_the_leaf_down():
    """A nub above each slot, hinge_detent out of the slot's wide face, sits in
    the leaf's notch: seated nothing touches; lifted past nub_clearance,
    the notch's lower edge runs into the nub's flat underside."""
    doc = built()
    c, sy = v(doc, "hinge_c0"), v(doc, "rim_d") / 2 + v(doc, "leaf_face_gap")
    bot, top, d = v(doc, "hinge_nub_bot"), v(doc, "hinge_nub_top"), v(doc, "hinge_detent")
    mid = (bot + top) / 2
    assert inside(doc, "Bottom", c, sy + d - 0.05, mid) and not inside(doc, "Bottom", c, sy + d + 0.05, mid)
    assert not inside(doc, "Bottom", c, sy + 0.05, bot - 0.05)  # flat underside
    assert inside(doc, "Bottom", c, sy - 0.05, bot - 0.5)  # the shelf behind the leaf
    nb, nd = v(doc, "leaf_notch_bot"), v(doc, "leaf_notch_d")
    assert not inside(doc, "Leaves", c, sy + nd - 0.05, nb + 0.05)
    assert inside(doc, "Leaves", c, sy + 0.05, nb - 0.05)
    leaves, bottom = get(doc, "Leaves").Shape, get(doc, "Bottom").Shape

    def lifted(dz):
        moved = leaves.copy()
        moved.translate(App.Vector(0, 0, dz))
        return moved.common(bottom).Volume
    nc = v(doc, "nub_clearance")
    assert lifted(0) <= 1e-9 and lifted(nc - 0.01) <= 1e-9
    assert lifted(nc + 0.05) > 1e-3
