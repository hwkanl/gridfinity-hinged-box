"""Cosmetics: fillets and chamfers on the finished parts.
Spec: docs/superpowers/specs/2026-10-04-cosmetics-design.md."""
import math

import FreeCAD as App

from hwkan_gfbox.build import build
from hwkan_gfbox.parts import lock
from hwkan_gfbox.parts.hinge import rib_out_y
from hwkan_gfbox.shapes import BuildError, get
from hwkan_gfbox.tests.helpers import built, inside, is_sound, v

# Default, a small box, and three hinges / three locks (a lock at x = 0).
SIZES = [(), (("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3")),
         (("hinge_count", "3"), ("lock_count", "3"))]
OFF = tuple((name, "0") for name in ("rib_root_fillet", "bottom_chamfer", "rib_fillet", "lid_chamfer",
                                     "lip_chamfer", "lever_tip_fillet", "lever_heel_fillet"))


def _rib_sides(doc):
    """(x, d) of every hinge rib's side face: d = +1 on its +X side, -1 on its -X side."""
    hw = v(doc, "hinge_rib_w") / 2
    return [(v(doc, "hinge_c0") + k * v(doc, "hinge_pitch") + d * hw, d)
            for k in range(int(v(doc, "hinge_count"))) for d in (-1, 1)]


def _check_bottom(doc):
    assert is_sound(get(doc, "Bottom").Shape)
    wall_y = v(doc, "outer_d") / 2
    rib_y = rib_out_y(doc)
    # in the ribs' full depth, below the rim band
    z = (v(doc, "rib_full") + min(v(doc, "rib_top"), v(doc, "split_z") - v(doc, "rim_band_h"))) / 2
    for x, d in _rib_sides(doc):
        # 1. the inside corner (rib side / back wall) is filled
        assert not inside(doc, "BottomBare", x + d * 0.1, wall_y + 0.1, z), (x, d)
        assert inside(doc, "Bottom", x + d * 0.1, wall_y + 0.1, z), (x, d)
        # 3. the outer corner (rib side / rib back) is rounded
        assert inside(doc, "BottomBare", x - d * 0.1, rib_y - 0.1, z), (x, d)
        assert not inside(doc, "Bottom", x - d * 0.1, rib_y - 0.1, z), (x, d)
    # ... and around each rib's 45 deg underside: the knee (rounded), the line
    # along the wall (filled), the two slanted edges (rounded)
    full, depth = v(doc, "rib_full"), v(doc, "rib_depth")
    foot = full - depth
    s = 0.05 * 2 ** 0.5  # 0.1 mm into the rib, normal to the underside
    for k in range(int(v(doc, "hinge_count"))):
        c = v(doc, "hinge_c0") + k * v(doc, "hinge_pitch")
        assert inside(doc, "BottomBare", c, rib_y - 0.02, full + 0.02) and not inside(doc, "Bottom", c, rib_y - 0.02, full + 0.02), c
        assert not inside(doc, "BottomBare", c, wall_y + 0.05, foot + 0.02) and inside(doc, "Bottom", c, wall_y + 0.05, foot + 0.02), c
        for d in (-1, 1):
            x, y, z = c + d * (v(doc, "hinge_rib_w") / 2 - 0.1), wall_y + depth / 2 - s, foot + depth / 2 + s
            assert inside(doc, "BottomBare", x, y, z) and not inside(doc, "Bottom", x, y, z), (c, d)
    # 2. the bed edge is chamfered: front wall, middle; full wall above the chamfer
    y = -v(doc, "outer_d") / 2 + 0.3
    assert inside(doc, "BottomBare", 0, y, 0.3) and not inside(doc, "Bottom", 0, y, 0.3)
    assert inside(doc, "Bottom", 0, y, v(doc, "bottom_chamfer") + 0.5)
    # ... and on a side wall (middle)
    x = v(doc, "outer_w") / 2 - 0.3
    assert inside(doc, "BottomBare", x, 0, 0.3) and not inside(doc, "Bottom", x, 0, 0.3)


def test_bottom():
    for overrides in SIZES:
        _check_bottom(built(*overrides))


def _check_lid(doc):
    assert is_sound(get(doc, "Lid").Shape)
    rd, bh, sz = v(doc, "rim_d") / 2, v(doc, "box_h"), v(doc, "split_z")
    # 4. the top outline is chamfered (front, middle) ...
    assert inside(doc, "LidBare", 0, -rd + 0.3, bh - 0.3) and not inside(doc, "Lid", 0, -rd + 0.3, bh - 0.3)
    # ... but not a knuckle's top: its inner side edge (x = hinge center + knuckle_gap / 2)
    xk = v(doc, "hinge_c0") + v(doc, "knuckle_gap") / 2
    assert inside(doc, "Lid", xk + 0.3, rd + 2, bh - 0.3)
    # 5. every lock lip's lower front edge is chamfered
    y = -(rd + v(doc, "lock_lip_e")) + 0.3
    for k in range(int(v(doc, "lock_count"))):
        x = v(doc, "lock_c0") + k * v(doc, "lock_pitch")
        assert inside(doc, "LidBare", x, y, sz + 0.3) and not inside(doc, "Lid", x, y, sz + 0.3), x


def test_lid():
    for overrides in SIZES:
        _check_lid(built(*overrides))


def test_zero_turns_the_details_off():
    doc = built(*OFF)
    for part in ("Bottom", "Lid", "LatchLever"):
        assert get(doc, part).TypeId == "Part::Cut" and not doc.getObjectsByLabel(part + "Bare"), part


def test_an_impossible_size_is_a_build_error():
    try:
        doc, _ = build([("rib_fillet", "15")], doc_name="cosmetics_error")
    except BuildError as e:
        assert "rib_fillet" in str(e), str(e)
    else:
        App.closeDocument(doc.Name)
        raise AssertionError("a 15 mm rib fillet was accepted")


def _check_lever(doc):
    bare, lever = get(doc, "LatchLeverBare").Shape, get(doc, "LatchLever").Shape
    assert is_sound(lever)
    c, r = v(doc, "lock_c0"), v(doc, "lobe_r")
    tip = v(doc, "lever_len") + r
    heel = tip - 2 * r * math.tan(math.radians(v(doc, "end_slant")))

    def p(du, dz):
        return lock.lever_point(doc, du, dz, c)

    # in place: inside the bare lever (a misapplied Placement would move it), axle at P0
    assert abs(lever.common(bare).Volume - lever.Volume) < 1e-6
    assert lever.isInside(p(0, 0), 1e-6, True)
    # 6. the outer end corner and 7. the wall-side end corner are rounded
    for du, dz in ((tip - 0.1, r - 0.1), (heel - 0.1, -r + 0.1)):
        assert bare.isInside(p(du, dz), 1e-6, True) and not lever.isInside(p(du, dz), 1e-6, True), (du, dz)
    # every lock's lever has them
    assert all(abs(s.Volume - lever.Volume) < 1e-6 for s in get(doc, "LatchLevers").Shape.Solids)


def test_lever():
    for overrides in SIZES:
        _check_lever(built(*overrides))
