"""Hinge: the lid knuckles with their cone pins (step 1), the free leaf, and
the hinge rib with its dovetail slot (step 2).

Each hinge sits on the lid's back (+Y) face with its axis along X: two
knuckles `knuckle_gap` apart, each with a cone pin on its inner face
pointing at the hinge center. All positions are expressions; the hinge
centers are `hinge_c0 + k * hinge_pitch`.

The free leaf is built in its print position (lying on the bed, pointing
away from the lid; profile frame: `out` from the lid's back face, `z` up
from the bed) and then swung down -90 deg about the hinge axis by its own
Placement: the model is built closed. export.py swings it back up.
"""
import FreeCAD as App

from hwkan_gfbox.sheet import SHEET_NAME, value
from hwkan_gfbox.shapes import common, cut, fuse, half_space, hide, per_count, place, primitive

BACK_Y = "Internal.rim_d / 2"  # the lid's back face (the straight part of the rim outline)
AXIS_Y = f"{BACK_Y} + Internal.hinge_axis_out"
AXIS_Z = "Internal.split_z + Internal.hinge_axis_z"
# The first hinge's left knuckle: its nominal outer end (at the knuckle's back),
# and inner face (where its pin starts).
END_X = "Internal.hinge_c0 - Internal.knuckle_gap / 2 - Internal.knuckle_len"
# The knuckle is built this much longer outward, then cut back to the flared end
# face: the flare's reach into the lid overlap, plus `overlap`.
EXTRA = "((Internal.knuckle_back + Internal.overlap) * tan(Internal.knuckle_flare) + Internal.overlap)"
KNUCKLE_X = f"{END_X} - {EXTRA}"
KNUCKLE_LEN = f"Internal.knuckle_len + {EXTRA}"
FACE_X = "Internal.hinge_c0 - Internal.knuckle_gap / 2"

ALONG_X = App.Rotation(App.Vector(0, 1, 0), 90)  # Part primitive axis Z -> X


_primitive = primitive


def _per_hinge(doc, unit, label):
    """unit (built at the first hinge) repeated along X, one per hinge."""
    return per_count(doc, unit, label, "Params.hinge_count", "Internal.hinge_pitch")


def _knuckle_profile(doc):
    """The knuckle body: a block from the lid face out to the axis, full lid
    height, plus a cylinder on the axis tangent to the lid top and the bed,
    together giving the spec's profile. Both are extended outward past the
    flared end (see _flare_cutter)."""
    block = _primitive(doc, "Part::Box", "KnuckleBlock", {
        "Length": KNUCKLE_LEN,
        "Width": "Internal.hinge_axis_out + Internal.overlap",
        "Height": "Internal.lid_h",
    })
    place(block, KNUCKLE_X, f"{BACK_Y} - Internal.overlap", "Internal.split_z")
    cylinder = _primitive(doc, "Part::Cylinder", "KnuckleCylinder", {
        "Radius": "Internal.knuckle_r",
        "Height": KNUCKLE_LEN,
    }, ALONG_X)
    place(cylinder, KNUCKLE_X, AXIS_Y, AXIS_Z)
    return [block, cylinder]


def _flare_cutter(doc):
    """Half-space (a big box) removing everything outward of the flared end
    face. The face is a vertical plane through the nominal end at the
    knuckle's back (out = knuckle_back), tilted by `knuckle_flare` about Z so
    that it moves outward (-X) toward the lid. The box's local +X normal
    points into the kept side; local +Y runs along the face, outward from the
    lid. Placement.Rotation is Z by `knuckle_flare` about the axis (0, 0, -1),
    and the base is the face point (END_X, BACK_Y + knuckle_back) plus the
    rotated corner offset (-s, -s), written out with sin/cos of the flare."""
    s = (f"({EXTRA} + Internal.knuckle_len + Internal.knuckle_back + Internal.overlap"
         " + Internal.lid_h)")
    cutter = _primitive(doc, "Part::Box", "KnuckleFlareCutter", {
        "Length": s,
        "Width": f"2 * {s}",
        "Height": "Internal.lid_h + 2 * Internal.overlap",
    })
    cutter.Placement.Rotation = App.Rotation(App.Vector(0, 0, -1), 0)
    cutter.setExpression(".Placement.Rotation.Angle", "Internal.knuckle_flare")
    # R * (-s, -s) for a rotation by -flare about Z: (-s cos - s sin, s sin - s cos)
    f = "Internal.knuckle_flare"
    place(cutter,
          f"{END_X} - {s} * (cos({f}) + sin({f}))",
          f"{BACK_Y} + Internal.knuckle_back + {s} * (sin({f}) - cos({f}))",
          "Internal.split_z - Internal.overlap")
    return cutter


def _cone_pin(doc):
    """Cone truncated where the tip sphere meets the flank, plus the sphere,
    pointing +X from the knuckle's inner face. The cone starts `overlap`
    inside the knuckle, widened to continue the flank."""
    cone = _primitive(doc, "Part::Cone", "PinCone", {
        "Radius1": "Internal.pin_dia / 2 + Internal.overlap / tan(Internal.pin_angle)",
        "Radius2": "Internal.pin_tan_r",
        "Height": "Internal.pin_tan_z + Internal.overlap",
    }, ALONG_X)
    place(cone, f"{FACE_X} - Internal.overlap", AXIS_Y, AXIS_Z)
    tip = _primitive(doc, "Part::Sphere", "PinTip", {"Radius": "Internal.pin_tip_r"})
    place(tip, f"{FACE_X} + Internal.pin_tip_c", AXIS_Y, AXIS_Z)
    return [cone, tip]


def build_lid_knuckles(doc):
    """LidKnuckles: one hinge unit (left knuckle with pin, and its mirror
    image about the hinge center) repeated along X, one per hinge."""
    body = fuse(doc, "KnuckleBody", _knuckle_profile(doc))
    flared = cut(doc, "KnuckleFlared", body, _flare_cutter(doc))
    left = fuse(doc, "LidKnuckleL", [flared] + _cone_pin(doc))
    right = doc.addObject("Part::Mirroring", "LidKnuckleR")
    right.Label = "LidKnuckleR"
    right.Source = left
    right.Normal = App.Vector(1, 0, 0)
    right.setExpression(".Base.x", "Internal.hinge_c0")
    hide(left)
    unit = fuse(doc, "HingeUnit", [left, right])
    return _per_hinge(doc, unit, "LidKnuckles")


# The first hinge's leaf: its -X side, and its end (outward from the lid).
LEAF_X = "Internal.hinge_c0 - Internal.leaf_w / 2"
LEAF_END_Y = f"{AXIS_Y} + Internal.leaf_len"
# Half-space boxes for the leaf profile: larger than the leaf in every direction.
LEAF_HALF = "4 * (Internal.lid_h + Internal.hinge_axis_out + Internal.leaf_len)"


def _half_space(doc, label, py, pz, direction):
    """Half-space for the leaf profile over the leaf's width (plus `overlap`
    each side); see shapes.half_space."""
    return half_space(doc, label, f"{LEAF_X} - Internal.overlap", "Internal.leaf_w + 2 * Internal.overlap",
                      py, pz, direction, LEAF_HALF)


def _leaf_profile(doc):
    """The leaf without sockets, in print position, at the first hinge
    (spec, "Leaf geometry"): knuckle cylinder; the 45 deg underside below the
    arc's 225 deg tangent point; the body under the top line (tangent to the
    arc at leaf_top_angle) and beyond the radius to that tangent point (so the
    arc, not the line, bounds the knuckle there) and up and outward of the
    45 deg underside line (for some valid inputs the radius alone would let
    the body reach in front of the foot); the dovetail."""
    knuckle = _primitive(doc, "Part::Cylinder", "LeafKnuckle", {
        "Radius": "Internal.leaf_r",
        "Height": "Internal.leaf_w",
    }, ALONG_X)
    place(knuckle, LEAF_X, AXIS_Y, AXIS_Z)

    cap = _primitive(doc, "Part::Box", "LeafUndersideCap", {
        "Length": "Internal.leaf_w",
        # Reaches the foot even when the foot lies outward of the axis.
        "Width": "Internal.leaf_tan + max(Internal.leaf_foot - Internal.hinge_axis_out; 0 mm) + Internal.overlap",
        "Height": "Internal.hinge_axis_z - Internal.leaf_tan",
    })
    place(cap, LEAF_X, f"{AXIS_Y} - Internal.leaf_tan", "Internal.split_z")
    # The 45 deg line through the foot, pointing down and outward (315 deg):
    # keeps the side up and outward of it.
    foot = (f"{BACK_Y} + Internal.leaf_foot", "Internal.split_z", "315 deg")
    underside = common(doc, "LeafUnderside", cap, _half_space(doc, "LeafUndersideSide", *foot))

    block = _primitive(doc, "Part::Box", "LeafBodyBlock", {
        "Length": "Internal.leaf_w",
        "Width": "Internal.leaf_r + Internal.leaf_len",
        "Height": "Internal.hinge_axis_z + Internal.leaf_r + Internal.overlap",
    })
    place(block, LEAF_X, f"{AXIS_Y} - Internal.leaf_r", "Internal.split_z")
    # The top line, from the end's top edge toward the lid (leaf_top_angle + 90 deg):
    # keeps the side below it.
    top = _half_space(doc, "LeafTopSide", LEAF_END_Y, "Internal.split_z + Internal.dovetail_t",
                      "Internal.leaf_top_angle + 90 deg")
    # The radius through the tangent point, pointing back through the axis
    # (leaf_top_angle + 180 deg): keeps the side toward the leaf's end.
    radial = _half_space(doc, "LeafRadialSide", AXIS_Y, AXIS_Z, "Internal.leaf_top_angle + 180 deg")
    body = common(doc, "LeafBodyRadial", common(doc, "LeafBodyTop", block, top), radial)
    # The same 45 deg line again (common() consumes its inputs): keeps the
    # body up and outward of the underside line.
    body = common(doc, "LeafBody", body, _half_space(doc, "LeafBodySide", *foot))

    # The dovetail's top face (z = dovetail_t) meets the body's top line along
    # the end's top edge by design: the top line runs through that edge.
    # Trapezoid prism: local Y up (wide face on the bed, narrow face at
    # dovetail_t), local Z along the leaf; rotated +90 deg about X, local Z
    # runs toward the lid from the leaf's end.
    dovetail = _primitive(doc, "Part::Wedge", "LeafDovetail", {
        "Xmin": "-(Internal.dovetail_base_w / 2 - Internal.dovetail_side_in)",
        "Xmax": "Internal.dovetail_base_w / 2 - Internal.dovetail_side_in",
        "X2min": "-(Internal.dovetail_w / 2 - Internal.dovetail_side_in)",
        "X2max": "Internal.dovetail_w / 2 - Internal.dovetail_side_in",
        "Ymin": "0 mm",
        "Ymax": "Internal.dovetail_t",
        "Zmin": "0 mm",
        "Zmax": "Internal.dovetail_len",
        "Z2min": "0 mm",
        "Z2max": "Internal.dovetail_len",
    }, App.Rotation(App.Vector(1, 0, 0), 90))
    place(dovetail, "Internal.hinge_c0", LEAF_END_Y, "Internal.split_z")
    return fuse(doc, "LeafSolid", [knuckle, underside, body, dovetail])


def _leaf_sockets(doc):
    """Sharp cones at both end faces, coaxial with the axis, pointing inward:
    apex socket_depth from the end face, flank at pin_angle to the face (so
    hinge_clearance from the pin's flank). Each starts `overlap` outside its
    face, widened to continue the flank."""
    left = _primitive(doc, "Part::Cone", "LeafSocketL", {
        "Radius1": "(Internal.socket_depth + Internal.overlap) / tan(Internal.pin_angle)",
        "Radius2": "0 mm",
        "Height": "Internal.socket_depth + Internal.overlap",
    }, ALONG_X)
    place(left, f"{LEAF_X} - Internal.overlap", AXIS_Y, AXIS_Z)
    right = doc.addObject("Part::Mirroring", "LeafSocketR")
    right.Label = "LeafSocketR"
    right.Source = left
    right.Normal = App.Vector(1, 0, 0)
    right.setExpression(".Base.x", "Internal.hinge_c0")
    return fuse(doc, "LeafSockets", [left, right])


def _leaf_notch(doc):
    """The notch across the leaf's bed face that takes the hinge nub, in
    print position: leaf_notch_d deep, leaf_notch_h long; swung down, its
    lower edge lies at leaf_notch_bot (a model z maps to the print frame's
    out = AXIS_Y + AXIS_Z - z)."""
    notch = _primitive(doc, "Part::Box", "LeafNotch", {
        "Length": "Internal.leaf_w + 2 * Internal.overlap",
        "Width": "Internal.leaf_notch_h",
        "Height": "Internal.leaf_notch_d + Internal.overlap",
    })
    place(notch, f"{LEAF_X} - Internal.overlap",
          f"({AXIS_Y}) + ({AXIS_Z}) - Internal.leaf_notch_bot - Internal.leaf_notch_h",
          "Internal.split_z - Internal.overlap")
    return notch


def build_leaves(doc):
    """Leaves: one free leaf per hinge, modelled swung down (the box is built
    closed). The unit is built in print position, then rotated -90 deg about
    the hinge axis by its Placement: p -> R p + (A - R A), and
    R (0, y, z) = (0, z, -y) for A = (0, AXIS_Y, AXIS_Z)."""
    unit = cut(doc, "LeafUnit", cut(doc, "LeafNotched", _leaf_profile(doc), _leaf_notch(doc)), _leaf_sockets(doc))
    unit.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), -90)
    place(unit, "0 mm", f"({AXIS_Y}) - ({AXIS_Z})", f"({AXIS_Z}) + ({AXIS_Y})")
    return _per_hinge(doc, unit, "Leaves")


# The slot's wide face is the swung-down leaf's underside; the rib's outer face
# is dovetail_t beyond it.
SLOT_Y = f"{BACK_Y} + Internal.leaf_face_gap"
RIB_OUT_Y = f"{SLOT_Y} + Internal.dovetail_t"


def rib_out_y(doc):
    """Numeric RIB_OUT_Y: the hinge ribs' back face, Y."""
    sheet = doc.getObject(SHEET_NAME)
    return value(sheet, "rim_d") / 2 + value(sheet, "leaf_face_gap") + value(sheet, "dovetail_t")


def build_hinge_ribs(doc):
    """HingeRibs: one rib per hinge on the back wall, hinge_rib_w wide, from
    `overlap` inside the wall's outer face to RIB_OUT_Y (it fills the rim
    band's chamfer locally), at full depth from rib_full up to rib_top;
    below rib_full its underside runs in at 45 deg to the wall, so the rib
    doesn't reach the bed."""
    low = "Internal.rib_full - Internal.rib_depth - 2 * Internal.overlap"  # below the 45 deg line at the wall
    block = _primitive(doc, "Part::Box", "HingeRibBlock", {
        "Length": "Internal.hinge_rib_w",
        "Width": f"{RIB_OUT_Y} - (Internal.outer_d / 2 - Internal.overlap)",
        "Height": f"Internal.rib_top - ({low})",
    })
    x0 = "Internal.hinge_c0 - Internal.hinge_rib_w / 2"
    place(block, x0, "Internal.outer_d / 2 - Internal.overlap", low)
    # The 45 deg line through the rib's outer face at rib_full, pointing up and
    # outward: keeps the side above and toward the wall.
    under = half_space(doc, "HingeRibUnderside", f"{x0} - Internal.overlap", "Internal.hinge_rib_w + 2 * Internal.overlap",
                       RIB_OUT_Y, "Internal.rib_full", "45 deg", LEAF_HALF)
    return _per_hinge(doc, common(doc, "HingeRib", block, under), "HingeRibs")


def build_slots(doc):
    """HingeSlots: the nominal dovetail trapezoid per hinge (wide face
    dovetail_base_w at SLOT_Y, narrowing outward at dovetail_angle), from
    slot_floor up to `overlap` above rib_top, and continued `overlap` past the
    rib's outer face so no cut face coincides with it."""
    slot = _primitive(doc, "Part::Wedge", "HingeSlot", {
        "Xmin": "-Internal.dovetail_base_w / 2",
        "Xmax": "Internal.dovetail_base_w / 2",
        "X2min": "-(Internal.dovetail_w / 2 - Internal.overlap / tan(Internal.dovetail_angle))",
        "X2max": "Internal.dovetail_w / 2 - Internal.overlap / tan(Internal.dovetail_angle)",
        "Ymin": "0 mm",
        "Ymax": "Internal.dovetail_t + Internal.overlap",
        "Zmin": "0 mm",
        "Zmax": "Internal.rib_top - Internal.slot_floor + Internal.overlap",
        "Z2min": "0 mm",
        "Z2max": "Internal.rib_top - Internal.slot_floor + Internal.overlap",
    })
    place(slot, "Internal.hinge_c0", SLOT_Y, "Internal.slot_floor")
    return _per_hinge(doc, slot, "HingeSlots")


def build_hinge_nubs(doc):
    """HingeNubs: per hinge, the detent nub above the slot, leaf_w wide: a
    shelf on the rib's top behind the leaf (from the rim band out to the
    slot's wide face, which the leaf's bed face lies in) up to hinge_nub_top,
    and on it the nub, hinge_detent out of that face from hinge_nub_bot (the
    flat ledge the leaf's notch catches on) to hinge_nub_top."""
    shelf = _primitive(doc, "Part::Box", "HingeNubShelf", {
        "Length": "Internal.leaf_w",
        "Width": f"{SLOT_Y} - (Internal.outer_d / 2 - Internal.overlap)",
        "Height": "Internal.hinge_nub_top - Internal.rib_top + Internal.overlap",
    })
    place(shelf, LEAF_X, "Internal.outer_d / 2 - Internal.overlap", "Internal.rib_top - Internal.overlap")
    nub = _primitive(doc, "Part::Box", "HingeNubBlock", {
        "Length": "Internal.leaf_w",
        "Width": "Preset.hinge_detent + Internal.overlap",
        "Height": "Internal.hinge_nub_h",
    })
    place(nub, LEAF_X, f"{SLOT_Y} - Internal.overlap", "Internal.hinge_nub_bot")
    return _per_hinge(doc, fuse(doc, "HingeNub", [shelf, nub]), "HingeNubs")
