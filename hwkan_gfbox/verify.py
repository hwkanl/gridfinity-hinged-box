"""Geometry verification over a sweep of inputs and tolerances.

Entry point: scripts/verify.py
    scripts/fc.sh scripts/verify.py            # full sweep (4 sizes x 3 tolerance sets)
    scripts/fc.sh scripts/verify.py --quick    # defaults only

Prints one line per check; exit status 1 if any check fails.
"""
import itertools
import math

import FreeCAD as App
import Part

from hwkan_gfbox.build import build
from hwkan_gfbox.params import PARAMS, PRESET_TIERS
from hwkan_gfbox.parts import lock
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import SHEET_NAME, value
from hwkan_gfbox.export import ExportError, check_part, latch_print_shapes, leaves_print_shapes, print_shape

# The preset's values, plus bin_clearance (a design value now, but still a gap
# whose extremes matter: the closing lid against the bins).
TOLERANCE_NAMES = [name for name, _, tier, _ in PARAMS if tier in PRESET_TIERS] + ["bin_clearance"]
SIZES = [
    ("2x2x3", [("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3")]),
    ("3x2x6", []),
    ("3x2x6 1 lock", [("lock_count", "1")]),
    ("3x2x6 3 hinges 3 locks", [("hinge_count", "3"), ("lock_count", "3")]),
    ("5x3x10 3 hinges 2 locks", [("gf_x", "5"), ("gf_y", "3"), ("gf_z_units", "10"),
                                 ("hinge_count", "3"), ("lock_count", "2")]),
]
# Low and high tolerance sets. The hinge needs hinge_clearance > 0, and at most
# about 0.48 at default dimensions (the leaf's front must clear the lid face
# while it swings); dovetail_clearance at most about 0.35 (the leaf body in its
# slot). Those two get their own extremes.
# The latch needs latch_clearance > 0 (printed in place). bin_clearance must
# exceed about 0.51 at default dimensions (the closing lid's inner back edge
# reaches 0.76 in from the back wall below the bin tops; the bins stand 0.25
# inside their cells).
# nub_clearance must stay below leaf_notch_h - hinge_nub_h (0.5).
# hook_preload and lock_detent are interferences, not gaps: low 0, high 0.5
# (lock_detent's limit, lock_key_d).
_LOW = {"hinge_clearance": "0.1", "latch_clearance": "0.1", "hook_preload": "0", "bin_clearance": "0.6"}
_HIGH = {"hinge_clearance": "0.4", "dovetail_clearance": "0.25", "latch_clearance": "0.4", "hook_preload": "0.5",
         "bin_clearance": "1.5", "nub_clearance": "0.4"}
TOLERANCE_SETS = [
    ("tol=default", []),
    ("tol=low", [(n, _LOW.get(n, "0")) for n in TOLERANCE_NAMES]),
    ("tol=high", [(n, _HIGH.get(n, "0.5")) for n in TOLERANCE_NAMES]),
]
EPS = 1e-6


def _sound(part, shape):
    try:
        check_part(part, shape)
    except ExportError:
        return False
    return True


def checks(doc):
    """Yield (description, passed) for one built document."""
    sheet = doc.getObject(SHEET_NAME)

    def v(name):
        return value(sheet, name)

    def inside(shape, x, y, z):
        return shape.isInside(App.Vector(x, y, z), EPS, True)

    def near(a, b, tol=EPS):
        return abs(a - b) <= tol

    bottom, lid = get(doc, "Bottom").Shape, get(doc, "Lid").Shape
    gw, gd, pitch = v("grid_w"), v("grid_d"), v("gf_pitch")
    ow, od = v("outer_w"), v("outer_d")
    rw, rd, e, hb = v("rim_w"), v("rim_d"), v("rim_extra"), v("rim_band_h")
    sz, ceil, bh = v("split_z"), v("ceiling_z"), v("box_h")
    lt, lc, lh, wt = v("lip_thickness"), v("lip_clearance"), v("lip_height"), v("wall_t")
    fxy = v("feet_xy_clearance")
    m = (wt + e) / 2  # middle of the rim, outward from the cavity wall
    cx0, cy0 = (-g / 2 + v("bin_clearance") + pitch / 2 for g in (gw, gd))
    n_hinges = int(v("hinge_count"))
    centers = [(cx0 + i * pitch, cy0 + j * pitch)
               for i in range(int(v("gf_x"))) for j in range(int(v("gf_y")))]

    # 1. Rebuild
    yield "Bottom is one sound closed solid", _sound("bottom", bottom)
    yield "Lid is one sound closed solid", _sound("lid", lid)

    # 2. Dimensions
    for label, shape, z0, z1 in (("Bottom", bottom, 0, sz + lh - lc), ("Lid", lid, sz, bh)):
        bb = shape.optimalBoundingBox()  # BoundBox is loose around the rim's curved faces
        # The lid's knuckles stand out of its back by hinge_axis_out + knuckle_r,
        # the bottom's hinge ribs by leaf_face_gap + dovetail_t.
        back = (v("hinge_axis_out") + v("knuckle_r") if label == "Lid"
                else v("leaf_face_gap") + v("dovetail_t"))
        # The lid's lock lips stand out of its front by lock_lip_e, the bottom's pads by pad_front.
        front = v("lock_lip_e") if label == "Lid" else v("pad_front")
        yield (f"{label} footprint is rim_w x rim_d plus the hinge parts at the back and the lock at the front",
               near(bb.XLength, rw) and near(bb.YLength, rd + back + front))
        yield f"{label} spans Z {z0:g} -> {z1:g}", near(bb.ZMin, z0) and near(bb.ZMax, z1)

    # 3. Invariants
    yield "every foot bottom lies in the rim plane", all(
        inside(lid, x, y, sz + 0.01) and not inside(lid, x, y, sz - 0.01) for x, y in centers)
    yield "lid rim lies in the rim plane", inside(lid, -rw / 2 + 0.3, 0, sz + 0.01)

    reach = v("pad_reach")

    def ring_area(a, b):
        """Area of the ring between the cavity rectangle offset by a and by b
        (concentric rounded corners)."""
        def area(t):
            return gw * gd + 2 * t * (gw + gd) + math.pi * t ** 2
        return area(b) - area(a)

    def corner_area(a, b):
        """Part of ring_area(a, b) (wt <= a) inside the corner zones: four
        quarter-annuli plus two straight strips of length reach - wt per corner."""
        return math.pi * (b ** 2 - a ** 2) + 8 * (reach - wt) * (b - a)

    # Rim band outside the wall: straight part plus the 45 deg chamfer, whose
    # cross-section at height t above its bottom edge is ring_area(wt, wt + t).
    band_vol = ring_area(wt, wt + e) * (hb - e) + (gw + gd) * e ** 2 + math.pi * (wt * e ** 2 + e ** 3 / 3)
    # The part of the band inside the corner zones lies inside the pads.
    band_in_corners = (corner_area(wt, wt + e) * (hb - e) + math.pi * (wt * e ** 2 + e ** 3 / 3)
                       + 4 * (reach - wt) * e ** 2)
    pads_vol = corner_area(wt, wt + e) * sz
    lid_rim_vol = ring_area(wt, wt + e) * (bh - sz)
    # Bead and channel: circle segments above the split, swept along the rim's
    # middle line (Pappus: the segments are symmetric about that line). Below
    # the split the bead lies in the rim.
    lip_c = v("lip_c")

    def segment(r):
        """Area of a circle of radius r, centered lip_c below the split, above the split."""
        return r * r * math.acos(lip_c / r) - lip_c * math.sqrt(r * r - lip_c * lip_c)

    rim_path = 2 * (gw + gd) + 2 * math.pi * m
    tongue_vol = segment(v("lip_r") - lc) * rim_path
    groove_vol = segment(v("lip_r")) * rim_path
    s, r = v("base_top") - 2 * fxy, v("base_top_r") - fxy
    feet_vol = get(doc, "Feet").Shape.Volume - len(centers) * v("overlap") * (s * s - (4 - math.pi) * r * r)
    box_vol = get(doc, "Box").Shape.Volume
    # The knuckles' overlap into the lid lies in solid lid wall, outside the groove.
    # Per knuckle the overlap slab (overlap deep, lid_h high) is knuckle_len long
    # plus the flare's extra length at its middle, out = -overlap / 2.
    tan_flare = math.tan(math.radians(v("knuckle_flare")))
    slab_len = v("knuckle_len") + (v("knuckle_back") + v("overlap") / 2) * tan_flare
    knuckles_vol = (get(doc, "LidKnuckles").Shape.Volume
                    - 2 * n_hinges * v("overlap") * v("lid_h") * slab_len)
    # Hinge ribs minus slots. A rib overlaps the wall by `overlap` and the rim
    # band where they meet: the band is 45 deg chamfered from sz - hb up to
    # sz - hb + e, then e thick; the rib reaches h into that height range.
    h = max(0.0, v("rib_top") - (sz - hb))
    band_in_rib = h * h / 2 if h <= e else e * e / 2 + e * (h - e)
    rib_depth = rd / 2 + v("leaf_face_gap") + v("dovetail_t") - od / 2  # outward from the wall face
    slot_area = (v("dovetail_base_w") + v("dovetail_w")) / 2 * v("dovetail_t")
    # Full depth from rib_full up, a 45 deg underside below it.
    rib_area = rib_depth * (v("rib_top") - v("rib_full")) + rib_depth * rib_depth / 2
    ribs_vol = n_hinges * (v("hinge_rib_w") * (rib_area - band_in_rib)
                           - slot_area * (v("rib_top") - v("slot_floor")))
    # Lock lips: lock_lip_e x lock_stop_top in front of the lid face, less the
    # seat: back to the lid face from its floor (seat center - radius), a
    # quarter circle below its center on the outer side, straight up above it;
    # their overlap lies in solid lid wall.
    n_locks = int(v("lock_count"))
    su, sc, sr, top = v("lock_seat_u"), v("lock_seat_z"), v("lock_seat_r"), v("lock_stop_top")
    seat = su * (top - (sc - sr)) + math.pi * sr * sr / 4 + sr * (top - sc)
    lips_vol = n_locks * v("lock_lip_w") * (v("lock_lip_e") * top - seat)
    # Lock pads add what lies outside the bottom's base (their overlap with the
    # band and its chamfer is awkward analytically); the lock slots remove
    # what they cut from base and pads. These two terms are shape-based: they
    # check the booleans, not the sizes (the point probes in test_lock and
    # the mockup comparison check those).
    base_shape, lock_pads = get(doc, "BottomBase").Shape, get(doc, "LockPads").Shape
    lock_pads_vol = lock_pads.Volume - lock_pads.common(base_shape).Volume
    lock_slots_vol = get(doc, "LockSlots").Shape.common(base_shape.fuse(lock_pads)).Volume
    # The hinge nubs (shelf and nub) add what lies outside the base and ribs (shape-based too).
    nubs = get(doc, "HingeNubs").Shape
    nubs_vol = nubs.Volume - nubs.common(base_shape.fuse(get(doc, "HingeRibs").Shape)).Volume
    expected = (box_vol + band_vol - band_in_corners + pads_vol + lid_rim_vol
                + tongue_vol - groove_vol + feet_vol + knuckles_vol + ribs_vol
                + lips_vol + lock_pads_vol - lock_slots_vol + nubs_vol)
    yield ("volumes: bottom + lid = box + band + corner pads + lid rim + tongue - groove + feet + knuckles "
           "+ ribs - slots + lock lips + lock pads - lock slots + hinge nubs "
           "(band and pads overlap in the corner zones)"), near(
        before_cosmetics(doc, "Bottom").Shape.Volume + before_cosmetics(doc, "Lid").Shape.Volume,
        expected, 1e-6 * box_vol)

    # 4. Point probes
    floor, clip_z = v("floor_t"), v("floor_t") + v("bp_h") - v("ridge_clip")
    yield "pocket centers are open", not any(inside(bottom, x, y, floor + 0.1) for x, y in centers)
    yield "floor is solid", inside(bottom, cx0, cy0, floor / 2)
    yield "wall is solid", inside(bottom, -ow / 2 + wt / 2, 0, sz / 2)
    yield "corner post is solid", inside(bottom, -gw / 2 + 0.3, -gd / 2 + 0.3, clip_z - 0.1)
    yield "ridge between pockets is solid", inside(bottom, cx0 + pitch / 2, cy0, clip_z - 0.1)
    yield "gap between feet is open", not inside(lid, cx0 + pitch / 2, cy0, ceil - 0.2)
    yield "feet are solid", all(inside(lid, x, y, sz + 2) for x, y in centers)
    yield "gap between outer foot and wall is open", not inside(lid, -gw / 2 + 0.1, cy0, ceil - 0.2)

    def d(t):
        """x of the point at distance t outward from the cavity wall (-X side)."""
        return -gw / 2 - t

    a, b = m - lt / 2, m + lt / 2  # channel edges at the split
    yield "bead is solid", inside(bottom, d(m), 0, sz + (lh - lc) / 2)
    yield "channel is open", not inside(lid, d(m), 0, sz + lh - 0.05)
    yield "lid wall is solid on both sides of the channel", (
        inside(lid, d(a / 2), 0, sz + 0.1) and inside(lid, d((b + wt + e) / 2), 0, sz + 0.1))
    yield "rim band is solid", inside(bottom, d(wt + e / 2), 0, sz - hb / 2)
    yield "rim band underside is chamfered", (
        not inside(bottom, d(wt + e - 0.3), 0, sz - hb + 0.2)
        and inside(bottom, d(wt + 0.1), 0, sz - hb + 0.2))

    # Corner pads and concentric outer corners, on the -X/-Y corner diagonal.
    px = -gw / 2 - (wt + e / 2)  # in the pad, outside the -X wall
    # (the bare bottom: the bed chamfer rounds the floor-level edge)
    yield "corner pads are solid at floor level", inside(before_cosmetics(doc, "Bottom").Shape, px, -(od / 2 - reach + 1), 0.5)
    yield "corner pads end at pad_reach", not inside(bottom, px, -(od / 2 - reach - 1), 0.5)

    def diag(t, z):
        k = t / math.sqrt(2)
        return -gw / 2 - k, -gd / 2 - k, z

    rr = wt + e
    yield "outer corners follow the concentric radius", (
        inside(bottom, *diag(rr - 0.1, sz / 2)) and not inside(bottom, *diag(rr + 0.1, sz / 2))
        and inside(lid, *diag(rr - 0.1, sz + 3)) and not inside(lid, *diag(rr + 0.1, sz + 3)))

    # Hinge knuckles and pins, for every hinge, on both sides of its center.
    out0, r, ln, gap = v("hinge_axis_out"), v("knuckle_r"), v("knuckle_len"), v("knuckle_gap")
    ya, za, pl = rd / 2 + out0, sz + v("hinge_axis_z"), v("pin_len")
    ca, sa = math.cos(math.radians(60)), math.sin(math.radians(60))  # the arc's lower back quarter, at -60 deg
    hinge_xs = [v("hinge_c0") + k * v("hinge_pitch") for k in range(n_hinges)]
    knuckle_xs = [c + side * (gap / 2 + ln / 2) for c in hinge_xs for side in (-1, 1)]
    yield "hinge centers are one per equal back wall segment", near(
        sum(hinge_xs), 0, 1e-6) and near(hinge_xs[0], -gw / 2 + gw / (2 * n_hinges))
    yield "every knuckle is solid below its top", all(
        inside(lid, x, rd / 2 + out0 / 2, bh - 0.1) for x in knuckle_xs)
    yield "every knuckle is solid at the hinge axis", all(inside(lid, x, ya, za) for x in knuckle_xs)
    yield "every knuckle is open just outside its arc", not any(
        inside(lid, x, ya + r + 0.1, za) for x in knuckle_xs)
    yield "every knuckle's arc runs down to the bed: solid / open 0.1 mm inside / outside it at -60 deg", all(
        inside(lid, x, ya + (r - 0.1) * ca, za - (r - 0.1) * sa)
        and not inside(lid, x, ya + (r + 0.1) * ca, za - (r + 0.1) * sa) for x in knuckle_xs)
    flare_ok = True
    cosf = math.cos(math.radians(v("knuckle_flare")))
    for c in hinge_xs:
        for side in (-1, 1):
            for out in (0.1, v("knuckle_back") - 0.2):
                end = gap / 2 + ln + (v("knuckle_back") - out) * tan_flare  # |x - c| of the flared end
                flare_ok &= (inside(lid, c + side * (end - 0.1 / cosf), rd / 2 + out, sz + v("lid_h") / 2)
                             and not inside(lid, c + side * (end + 0.1 / cosf), rd / 2 + out, sz + v("lid_h") / 2))
    yield "every knuckle's outer end is flared: solid / open 0.1 mm inside / outside it", flare_ok
    yield "every pin is solid up to pin_len and open beyond, and the hinge center is open", all(
        inside(lid, c + side * (gap / 2 - pl + 0.1), ya, za)
        and not inside(lid, c + side * (gap / 2 - pl - 0.1), ya, za)
        and not inside(lid, c, ya, za) for c in hinge_xs for side in (-1, 1))

    # Opening: the lid, rotated about the hinge axis (its front lifting), never
    # enters the bottom part. Both are cropped to the back wall for speed.
    crop = Part.makeBox(2 * rw, 30, 40, App.Vector(-rw, rd / 2 - 20, sz - 15))
    lid_back, bottom_back = lid.common(crop), bottom.common(crop)
    leaves = get(doc, "Leaves").Shape
    hits = []
    # Contact, if any, comes in the first few degrees: sample those finely.
    for angle in [a / 2 for a in range(0, 20)] + list(range(10, 91, 5)):
        opened = lid_back.copy()
        opened.rotate(App.Vector(0, ya, za), App.Vector(1, 0, 0), -angle)
        if opened.common(bottom_back).Volume > EPS or opened.common(leaves).Volume > EPS:
            hits.append(angle)
    yield ("the lid opens 0-90 deg without entering the bottom part or the leaves "
           f"(contact at: {hits or 'none'} deg)"), not hits
    # ... nor the outer bins: their walls above the parting line, all around,
    # a 0.2 mm skin with the stacking lip's top chamfer (stack_ch_high, 45 deg
    # in and down from the top edge) inside it, where the lid's feet nest.
    top, ch = v("bin_top_z"), v("stack_ch_high")
    inset = (pitch - v("base_top")) / 2  # bins stand this far inside their cells
    bx, by = v("gf_x") * pitch / 2 - inset, v("gf_y") * pitch / 2 - inset  # the grid is centered

    def skin(side, half_len):
        """The bins' skin along their +Y side, at y = side, x from -half_len to half_len."""
        section = Part.Face(Part.makePolygon([App.Vector(-half_len, y, z) for y, z in (
            (side, sz), (side, top), (side - ch, top - ch), (side - 0.2, top - ch), (side - 0.2, sz), (side, sz))]))
        return section.extrude(App.Vector(2 * half_len, 0, 0))

    origin = App.Vector(0, 0, 0)
    back_skin, side_skin = skin(by, bx), skin(bx, by)
    side_skin.rotate(origin, App.Vector(0, 0, 1), -90)  # its +Y side to +X
    skins = {"back": back_skin, "front": back_skin.mirror(origin, App.Vector(0, 1, 0)),
             "+X": side_skin, "-X": side_skin.mirror(origin, App.Vector(1, 0, 0))}
    # The lid without its middle (well inside the bins, lifting away): its walls,
    # the outer feet, knuckles and lips.
    k = 5
    lid_ring = lid.cut(Part.makeBox(2 * (bx - k), 2 * (by - k), bh, App.Vector(k - bx, k - by, sz - 1)))
    bin_hits = []
    for angle in range(0, 91, 2):
        opened = lid_ring.copy()
        opened.rotate(App.Vector(0, ya, za), App.Vector(1, 0, 0), -angle)
        bin_hits += [f"{name} {angle}" for name, s in skins.items() if opened.common(s).Volume > EPS]
    yield f"the lid opens 0-90 deg clear of the outer bins (contact at: {bin_hits or 'none'} deg)", not bin_hits

    yield from _leaf_checks(doc, v, near, bottom, lid, ya, za)
    yield from _lock_checks(doc, v, near, bottom, lid)

    # 5. Print orientation
    for part in ("bottom", "lid", "latch"):
        bb = print_shape(doc, part).optimalBoundingBox()
        yield f"{part} print placement: on Z=0, centered", (
            near(bb.ZMin, 0) and near(bb.XMin + bb.XMax, 0) and near(bb.YMin + bb.YMax, 0))
    printed_lid = print_shape(doc, "lid")
    # The lid solid (first) is the lid as modelled, shifted as part of the
    # compound with its leaves; the shift is the difference of the lid's own
    # bounding boxes, so it does not depend on where the leaves lie.
    pbb, lbb = printed_lid.Solids[0].optimalBoundingBox(), lid.optimalBoundingBox()
    dx, dy = pbb.XMin - lbb.XMin, pbb.YMin - lbb.YMin
    yield "lid prints with rim, every foot and every knuckle on the bed", all(
        inside(printed_lid.Solids[0], x + dx, y + dy, 0.01)
        for x, y in [(-rw / 2 + 0.3, 0)] + centers + [(x, rd / 2 + out0 / 2) for x in knuckle_xs])
    n_leaves = len(printed_lid.Solids) - 1
    yield "lid print holds one leaf per hinge, each on the bed", n_leaves == n_hinges and all(
        near(s.optimalBoundingBox().ZMin, 0, 1e-6) for s in printed_lid.Solids[1:])


def _first_hinge(solids, c0):
    """The solid of the first hinge (centered nearest x = c0), whatever the
    array's order."""
    return min(solids, key=lambda s: abs(s.BoundBox.Center.x - c0))


def _leaf_checks(doc, v, near, bottom, lid, ya, za):
    """Hinge step 2: the leaves (closed, probes, print position, swing).
    (ya, za): the hinge axis."""
    rd, sz, bh, rw = v("rim_d"), v("split_z"), v("box_h"), v("rim_w")
    axis = (App.Vector(0, ya, za), App.Vector(1, 0, 0))
    hc, n = v("hinge_clearance"), int(v("hinge_count"))
    ao, az, ll, lw = v("hinge_axis_out"), v("hinge_axis_z"), v("leaf_len"), v("leaf_w")
    c0, sd = v("hinge_c0"), v("socket_depth")
    leaves = get(doc, "Leaves").Shape
    yield "Leaves: one sound solid per hinge", len(leaves.Solids) == n and all(
        _sound("leaf", s) for s in leaves.Solids)
    first = _first_hinge(leaves.Solids, c0)
    yield "closed: the leaves don't enter the lid", leaves.common(lid).Volume <= EPS
    yield "closed: the leaves don't enter the bottom part", leaves.common(bottom).Volume <= EPS

    def in_leaf(x, out, z):
        """Probe the first leaf at print-frame (x, out, z) (it is modelled swung down)."""
        dy, dz = rd / 2 + out - ya, sz + z - za
        return first.isInside(App.Vector(x, ya + dz, za - dy), EPS, True)

    yield "leaf: solid at the axis, along the bed and to its end", (
        in_leaf(c0, ao, az) and in_leaf(c0, ao + 3, 0.05)
        and in_leaf(c0, ao + ll - 0.1, 0.1) and not in_leaf(c0, ao + ll + 0.1, 0.1))
    yield "leaf: sockets open on the axis to socket_depth", all(
        not in_leaf(c0 + s * (lw / 2 - 0.1), ao, az) and not in_leaf(c0 + s * (lw / 2 - sd + 0.1), ao, az)
        and in_leaf(c0 + s * (lw / 2 - sd - 0.1), ao, az) for s in (-1, 1))

    # Print position: every leaf swung up beside the lid (cropped to the back
    # for speed) shares no volume with it; the first hinge's leaf gap is
    # measured (all leaves are copies).
    printed = leaves_print_shapes(doc)
    lid_back = lid.common(Part.makeBox(2 * rw, 40, bh - sz + 31, App.Vector(-rw, rd / 2 - 3, sz - 30)))
    yield "print position: no leaf enters the lid", len(printed) == n and all(
        p.common(lid_back).Volume <= EPS for p in printed)
    half = v("hinge_root_len") / 2 + 1
    lid_near = lid.common(Part.makeBox(2 * half, 40, bh - sz + 31, App.Vector(c0 - half, rd / 2 - 3, sz - 30)))
    leaf = _first_hinge(printed, c0)
    gap = leaf.distToShape(lid_near)[0]
    yield (f"print position: leaf clear of the lid by {gap:.3f} mm (>= hinge_clearance)",
           gap >= hc - 1e-4 and leaf.common(lid_near).Volume <= EPS)
    yield "print position: leaf flat on the bed with the lid", near(leaf.optimalBoundingBox().ZMin, sz, 1e-6)

    # Swing from print position (0) to hanging (90): never into the lid; the
    # gap to the lid's back face (between the pins) is measured.
    room = v("knuckle_gap") / 2 - v("pin_len") - 0.1
    face = lid.common(Part.makeBox(2 * room, 40, bh - sz + 31, App.Vector(c0 - room, rd / 2 - 5, sz - 30)))
    hits, best = [], (float("inf"), None)
    for angle in range(0, 91, 5):
        swung = leaf.copy()
        swung.rotate(*axis, -angle)
        if swung.common(lid_near).Volume > EPS:
            hits.append(angle)
        best = min(best, (swung.distToShape(face)[0], angle))
    yield (f"swing 0-90 deg: leaf never enters the lid (contact at: {hits or 'none'} deg); "
           f"closest to the lid's back face {best[0]:.3f} mm at {best[1]} deg"), not hits and best[0] >= hc - 1e-4


def gap(a, b):
    return a.distToShape(b)[0]


def before_cosmetics(doc, part):
    """The part before its fillets and chamfers (the part itself if it has none)."""
    found = doc.getObjectsByLabel(part + "Bare")
    return found[0] if found else get(doc, part)


def latch_fit_checks(doc):
    """The latches as modelled (closed): (name, ok) pairs. Shared with
    tests/test_lock.py."""
    sheet = doc.getObject(SHEET_NAME)
    n, lc, dc = (value(sheet, k) for k in ("lock_count", "latch_clearance", "lock_dovetail_clearance"))
    arrays = {label: get(doc, label).Shape for label in ("LatchBases", "LatchLevers", "LatchHooks")}
    bottom, lid = get(doc, "Bottom").Shape, get(doc, "Lid").Shape
    yield "latches: one sound base, lever and hook per lock", all(
        len(s.Solids) == int(n) and all(_sound("latch", x) for x in s.Solids) for s in arrays.values())
    bases, levers, hooks = arrays["LatchBases"], arrays["LatchLevers"], arrays["LatchHooks"]

    g = gap(bases, bottom)
    yield f"closed: bases in their slots, {g:.3f} mm (= lock_dovetail_clearance)", (
        bases.common(bottom).Volume <= EPS and abs(g - dc) <= 1e-3)
    g = gap(levers, bases)
    yield f"closed: levers clear the bases by {g:.3f} mm (= latch_clearance)", (
        levers.common(bases).Volume <= EPS and abs(g - lc) <= 1e-3)
    pairs = {"hook-lever": (hooks, levers), "hook-base": (hooks, bases),
             "lever-bottom": (levers, bottom), "hook-bottom": (hooks, bottom), "lever-lid": (levers, lid),
             "base-lid": (bases, lid)}
    gaps = {k: gap(a, b) for k, (a, b) in pairs.items()}
    yield ("closed: latch gaps >= latch_clearance (" + ", ".join(f"{k} {g:.3f}" for k, g in gaps.items()) + ")",
           all(g >= lc - 1e-3 for g in gaps.values()))
    # Side play along the axles (gap() alone finds the axle-in-hole gap):
    # slid latch_clearance either way the hooks still clear the levers, a
    # little further they hit them.
    def slid(dx):
        moved = hooks.copy()
        moved.translate(App.Vector(dx, 0, 0))
        return moved.common(levers).Volume
    yield "closed: the hooks have latch_clearance side play on the levers, no more", all(
        slid(s * (lc - 0.01)) <= EPS and slid(s * (lc + 0.05)) > EPS for s in (1, -1))
    pressed = hooks.common(lid)
    yield "closed: the hook bars press into the lips only (the preload)", (
        pressed.Volume > 1e-3 and pressed.common(get(doc, "LockLips").Shape).Volume >= pressed.Volume - 1e-6)
    low = min(s.optimalBoundingBox().ZMin for s in arrays.values())
    yield f"closed: the latches stay above the box bottom (lowest {low:.3f} mm)", low >= -1e-6


def _lock_checks(doc, v, near, bottom, lid):
    """The latches: closed fit, open lever, print pose."""
    yield from latch_fit_checks(doc)
    lc = v("latch_clearance")
    base, lever = (get(doc, label).Shape for label in ("LatchBase", "LatchLever"))
    # Opening: the lever turns counterclockwise in (u, z) about P0.
    p0 = lock.point(doc, v("lock_p0_u"), v("lock_p0_z"))
    worst = float("inf")
    for angle in range(0, 111, 10):
        opened = lever.copy()
        opened.rotate(p0, lock.MINUS_X, angle)
        worst = min(worst, gap(opened, lid), gap(opened, bottom), gap(opened, base))
    yield (f"open: the lever swung 0-110 deg clears the lid, bottom and base (closest {worst:.3f} mm)",
           worst >= lc - 1e-3)
    # With the lever open, P1 has moved 110 deg about P0; the bar can be lifted
    # out of its seat and over the stop if the hook (P1 to bar) is longer than
    # P1 to the seat by more than the stop stands above the bar's underside.
    p1 = lock.point(doc, v("lock_p1_u"), v("lock_p1_z"))
    bar_c = lock.point(doc, v("lock_k_u"), v("lock_bar_c_z"))
    p1_open = Part.Vertex(p1)
    p1_open.rotate(p0, lock.MINUS_X, 110)
    slack = v("hook_l") - p1_open.Point.sub(bar_c).Length
    lift = v("lock_stop_top") - (v("lock_bar_c_z") - v("bar_r"))
    yield (f"open: the hook bar lifts out of its seat over the stop (slack {slack:.3f} mm > {lift:.3f} mm)",
           slack > lift)
    printed = latch_print_shapes(doc)
    pg = [printed[i].distToShape(printed[j])[0] for i, j in ((0, 1), (1, 2), (0, 2))]
    tops = [s.optimalBoundingBox().ZMax for s in printed]
    yield (f"print pose: base, lever and hook {', '.join(f'{g:.3f}' for g in pg)} mm apart, all on the bed",
           all(g >= lc - 1e-3 for g in pg) and all(near(t, max(tops), 1e-6) for t in tops))


def main(args):
    if "--quick" in args:
        cases = [("3x2x6 tol=default", [])]
    else:
        cases = [(f"{size} {tol}", size_ov + tol_ov)
                 for (size, size_ov), (tol, tol_ov) in itertools.product(SIZES, TOLERANCE_SETS)]
    failures = 0
    for name, overrides in cases:
        try:
            doc, _ = build(overrides, doc_name="verify")
        except Exception as e:
            print(f"FAIL {name}: build failed: {e}")
            failures += 1
            continue
        try:
            for description, passed in checks(doc):
                print(f"{'ok  ' if passed else 'FAIL'} {name}: {description}")
                failures += not passed
        except Exception as e:
            print(f"FAIL {name}: check crashed: {e!r}")
            failures += 1
        finally:
            App.closeDocument(doc.Name)
    print(f"{len(cases)} case(s), {failures} failure(s)")
    return 1 if failures else 0

