"""Hinge step 2: the free leaf (printed in place with the lid, modelled
swung down) and the hinge rib with its dovetail slot on the bottom part."""
import math

import FreeCAD as App
import Part

from hwkan_gfbox.export import leaves_print_shapes
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import value
from hwkan_gfbox.tests.helpers import built, inside, is_sound, near, v
from hwkan_gfbox.tests.test_hinge import _sheet, hinge_centers


def test_leaf_derived_defaults():
    s = _sheet(("hinge_clearance", "0.15"), ("hinge_dovetail_fit", "0.09"))  # the values these were worked out for
    for name, want, tol in (("leaf_w", 9.7, 1e-9), ("leaf_tan", 2.474874, 1e-6),
                            ("leaf_foot", 3.425252, 1e-6), ("dovetail_start", 6.875, 1e-9),
                            ("leaf_len", 16.875, 1e-9), ("leaf_top_angle", 75.077600, 1e-5),
                            ("socket_depth", 3.062743, 1e-6), ("dovetail_base_w", 13.864102, 1e-6),
                            ("dovetail_side_in", 0.103923, 1e-5), ("leaf_face_gap", 0.625, 1e-9),
                            ("rib_top", 42.15, 1e-9), ("slot_floor", 32.15, 1e-9)):
        assert near(value(s, name), want, tol), (name, value(s, name))


def _axis(doc):
    rd, sz = v(doc, "rim_d"), v(doc, "split_z")
    return rd / 2 + v(doc, "hinge_axis_out"), sz + v(doc, "hinge_axis_z")


def leaf_xyz(doc, x, out, z):
    """Model-frame point of the leaf point (x, out, z) given in its print frame
    (out from the lid's back face, z up from the bed). The leaves are modelled
    swung down, -90 deg about the hinge axis: offsets (dy, dz) -> (dz, -dy)."""
    ay, az = _axis(doc)
    dy, dz = v(doc, "rim_d") / 2 + out - ay, v(doc, "split_z") + z - az
    return App.Vector(x, ay + dz, az - dy)


def in_leaf(doc, x, out, z):
    p = leaf_xyz(doc, x, out, z)
    return any(s.isInside(p, 1e-6, True) for s in get(doc, "Leaves").Shape.Solids)


def lid_near_first_hinge(doc):
    """The lid cropped to the first hinge's neighbourhood (fast distance checks)."""
    c, half = v(doc, "hinge_c0"), v(doc, "hinge_root_len") / 2 + 1
    rd, sz = v(doc, "rim_d"), v(doc, "split_z")
    crop = Part.makeBox(2 * half, 40, 60, App.Vector(c - half, rd / 2 - 3, sz - 30))
    return get(doc, "Lid").Shape.common(crop)


def test_leaves_object():
    doc = built()
    shape = get(doc, "Leaves").Shape
    assert len(shape.Solids) == int(v(doc, "hinge_count")), len(shape.Solids)
    assert all(is_sound(s) for s in shape.Solids)


def test_leaf_profile_probes():
    doc = built()
    ao, az, r = v(doc, "hinge_axis_out"), v(doc, "hinge_axis_z"), v(doc, "leaf_r")
    lt, foot, ll, t = v(doc, "leaf_tan"), v(doc, "leaf_foot"), v(doc, "leaf_len"), v(doc, "dovetail_t")
    phi = math.radians(v(doc, "leaf_top_angle"))
    n = 0.1 / math.sqrt(2)
    mid_out, mid_z = (ao - lt + foot) / 2, (az - lt) / 2           # middle of the 45 deg underside
    u_out, u_z = ao + r * math.cos(phi), az + r * math.sin(phi)    # where the top line touches the arc
    top_out, top_z = (u_out + ao + ll) / 2, (u_z + t) / 2          # middle of the top line
    nx, nz = 0.1 * math.cos(phi), 0.1 * math.sin(phi)              # the top line's outward normal
    for c in hinge_centers(doc):
        assert in_leaf(doc, c, ao, az), c                                                  # knuckle at the axis
        assert in_leaf(doc, c, ao, az + r - 0.1) and not in_leaf(doc, c, ao, az + r + 0.1), c   # arc top
        assert in_leaf(doc, c, ao - r + 0.1, az) and not in_leaf(doc, c, ao - r - 0.1, az), c   # arc front
        assert in_leaf(doc, c, mid_out + n, mid_z + n) and not in_leaf(doc, c, mid_out - n, mid_z - n), c
        assert in_leaf(doc, c, top_out - nx, top_z - nz) and not in_leaf(doc, c, top_out + nx, top_z + nz), c
        assert in_leaf(doc, c, ao + 3, 0.05), c                                            # flat on the bed (short of the notch)
        assert not in_leaf(doc, c, foot - 0.1, 0.05) and in_leaf(doc, c, foot + 0.1, 0.05), c  # the foot
        assert in_leaf(doc, c, ao + ll - 0.1, 0.1) and not in_leaf(doc, c, ao + ll + 0.1, 0.1), c  # end face
        assert in_leaf(doc, c, ao + ll - 0.1, t - 0.1) and not in_leaf(doc, c, ao + ll - 0.1, t + 0.1), c


def test_leaf_width_dovetail_and_sockets():
    doc = built()
    ao, az = v(doc, "hinge_axis_out"), v(doc, "hinge_axis_z")
    lw, ds, dl, t = v(doc, "leaf_w"), v(doc, "dovetail_start"), v(doc, "dovetail_len"), v(doc, "dovetail_t")
    bw, w, side_in = v(doc, "dovetail_base_w"), v(doc, "dovetail_w"), v(doc, "dovetail_side_in")
    tan_a = math.tan(math.radians(v(doc, "dovetail_angle")))
    sd = v(doc, "socket_depth")
    body_out, dove_out = ao + 5, ao + ds + dl / 2
    assert near(lw, v(doc, "knuckle_gap") - 2 * v(doc, "hinge_clearance"))
    for c in hinge_centers(doc):
        for side in (-1, 1):
            # leaf sides
            assert in_leaf(doc, c + side * (lw / 2 - 0.05), body_out, 1), (c, side)
            assert not in_leaf(doc, c + side * (lw / 2 + 0.05), body_out, 1), (c, side)
            # dovetail flanks (sides moved in by dovetail_side_in), near the bed and the narrow face
            for z, half in ((0.1, bw / 2 - side_in - 0.1 / tan_a), (t - 0.1, w / 2 - side_in + 0.1 / tan_a)):
                assert in_leaf(doc, c + side * (half - 0.05), dove_out, z), (c, side, z)
                assert not in_leaf(doc, c + side * (half + 0.05), dove_out, z), (c, side, z)
            # the dovetail starts dovetail_start from the axis; its wings are dovetail_t high
            wing = c + side * (lw / 2 + 0.5)
            assert in_leaf(doc, wing, ao + ds + 0.1, 0.1) and not in_leaf(doc, wing, ao + ds - 0.1, 0.1), (c, side)
            assert not in_leaf(doc, wing, dove_out, t + 0.1), (c, side)
            # socket: open on the axis from the end face to socket_depth
            face = c + side * lw / 2
            assert not in_leaf(doc, face - side * 0.1, ao, az), (c, side)
            assert not in_leaf(doc, face - side * (sd - 0.1), ao, az), (c, side)
            assert in_leaf(doc, face - side * (sd + 0.1), ao, az), (c, side)


def test_leaves_clear_the_lid_closed_and_in_print_position():
    doc = built()
    leaves = get(doc, "Leaves").Shape
    assert leaves.common(get(doc, "Lid").Shape).Volume < 1e-6
    printed = Part.makeCompound(leaves_print_shapes(doc))  # export's own rotation
    assert printed.common(get(doc, "Lid").Shape).Volume < 1e-6
    gap = leaves.Solids[0].distToShape(lid_near_first_hinge(doc))[0]
    assert gap >= v(doc, "hinge_clearance") - 1e-4, gap
    assert near(printed.optimalBoundingBox().ZMin, v(doc, "split_z"), 1e-6)  # on the bed with the lid
    gap = printed.Solids[0].distToShape(lid_near_first_hinge(doc))[0]
    assert gap >= v(doc, "hinge_clearance") - 1e-4, gap


def test_leaf_body_stays_behind_the_underside():
    """Valid overrides that move the body's radial boundary in front of the
    45 deg foot: the body must still be bounded by the underside line."""
    for override in (("dovetail_len", "5"), ("leaf_r", "3.2")):
        doc = built(override)
        assert all(is_sound(s) for s in get(doc, "Leaves").Shape.Solids), override
        c, foot = v(doc, "hinge_c0"), v(doc, "leaf_foot")
        assert not in_leaf(doc, c, foot - 0.1, 0.05), override
        assert in_leaf(doc, c, foot + 0.1, 0.05), override


def test_hinge_ribs_and_slots():
    doc = built()
    rd = v(doc, "rim_d")
    rib_w, rib_top, floor = v(doc, "hinge_rib_w"), v(doc, "rib_top"), v(doc, "slot_floor")
    bw, w, t = v(doc, "dovetail_base_w"), v(doc, "dovetail_w"), v(doc, "dovetail_t")
    slot_y = rd / 2 + v(doc, "leaf_face_gap")  # the slot's wide face = the leaf's swung-down underside
    rib_out, ymid = slot_y + t, slot_y + t / 2
    for c in hinge_centers(doc):
        x_rib = c + (bw / 2 + rib_w / 2) / 2  # in the rib, beside the slot
        assert inside(doc, "Bottom", x_rib, ymid, rib_top - 1), c
        assert not inside(doc, "Bottom", x_rib, ymid, rib_top + 0.1), c        # dovetail_drop below the split
        # full depth from rib_full up
        full, depth, wall = v(doc, "rib_full"), v(doc, "rib_depth"), v(doc, "outer_d") / 2
        assert inside(doc, "Bottom", x_rib, rib_out - 0.1, full + 0.5), c
        assert not inside(doc, "Bottom", x_rib, rib_out + 0.1, full + 0.5), c           # outer face
        assert inside(doc, "Bottom", c + rib_w / 2 - 0.1, rd / 2 + 1, full + 0.5), c
        assert not inside(doc, "Bottom", c + rib_w / 2 + 0.1, rd / 2 + 1, full + 0.5), c  # rib width
        # below rib_full the underside runs in at 45 deg; nothing below its foot
        assert inside(doc, "Bottom", x_rib, wall + depth - 1 - 0.1, full - 1), c
        assert not inside(doc, "Bottom", x_rib, wall + depth - 1 + 0.1, full - 1), c
        assert not inside(doc, "Bottom", x_rib, wall + 0.1, full - depth - 0.1), c
        assert not inside(doc, "Bottom", x_rib, wall + 0.1, 1), c
        assert not inside(doc, "Bottom", c, ymid, floor + 0.1), c
        assert inside(doc, "Bottom", c, ymid, floor - 0.1), c                  # slot floor
        half = (bw + w) / 4  # slot half-width at mid-thickness
        for side in (-1, 1):
            assert not inside(doc, "Bottom", c + side * (half - 0.05), ymid, rib_top - 2), (c, side)
            assert inside(doc, "Bottom", c + side * (half + 0.05), ymid, rib_top - 2), (c, side)
        assert inside(doc, "Bottom", c, slot_y - 0.1, rib_top - 2), c
        assert not inside(doc, "Bottom", c, slot_y + 0.1, rib_top - 2), c      # slot wide face
        assert not inside(doc, "Bottom", c, rib_out - 0.1, rib_top - 2), c     # open at the outer face
        assert not inside(doc, "Bottom", c, ymid, rib_top - 0.1), c            # open at the top


def test_leaves_sit_in_the_slots_without_overlap():
    # The dovetail's bed face and the leaf's underside lie in the slot's
    # wide-face plane by design (zero gap there, nominally); the flanks and
    # floor carry hinge_dovetail_fit.
    doc = built()
    assert get(doc, "Leaves").Shape.common(get(doc, "Bottom").Shape).Volume < 1e-6
