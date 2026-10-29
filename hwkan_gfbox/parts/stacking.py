"""Stacking: a raised notch at each corner of the lid top, centered over the
wall, and a matching groove under each corner of the bottom part, so a box
stacks on another of the same footprint. Both have 45 deg sides: the notches
center the box above, and the grooves (recesses in the bottom's bed face)
print without supports.

Both are added after the cosmetics: the lid's top chamfer and the bottom's
bed chamfer select every edge in their plane, which would include the
notches' and grooves' own edges there.
"""
from hwkan_gfbox.shapes import box, cut, fuse, offset_loft
from hwkan_gfbox.parts.halves import HALF_XY


def _keep_corners(doc, label, ring, reach, z0, height):
    """ring kept only within `reach` of each corner, measured along each wall
    from the outer corner point of the wall_t walls (as the corner pads)."""
    across_x = box(doc, f"{label}CrossX", f"Internal.outer_w - 2 * ({reach})", HALF_XY, z0, height)
    across_y = box(doc, f"{label}CrossY", HALF_XY, f"Internal.outer_d - 2 * ({reach})", z0, height)
    return cut(doc, label, ring, fuse(doc, f"{label}Cross", [across_x, across_y]))


def build_notches(doc):
    """The lid's notches: stack_h tall on the lid top, stack_w wide at the
    foot, 45 deg sides; sunk `overlap` into the lid. The inner loft starts
    below the lid top at a smaller offset (a ruled loft keeps the corner
    radii positive) and overshoots the notch top."""
    top, ov = "Internal.box_h", "Internal.overlap"
    outer = offset_loft(doc, "NotchOuter", [
        (f"{top} - {ov}", "Internal.stack_out"),
        (top, "Internal.stack_out"),
        (f"{top} + Internal.stack_h", "Internal.stack_out - Internal.stack_h"),
    ])
    inner = offset_loft(doc, "NotchInner", [
        (f"{top} - 2 * {ov}", "Internal.stack_in / 2"),
        (top, "Internal.stack_in"),
        (f"{top} + Internal.stack_h + {ov}", f"Internal.stack_in + Internal.stack_h + {ov}"),
    ])
    ring = cut(doc, "NotchRing", outer, inner)
    return _keep_corners(doc, "Notches", ring, "Internal.stack_reach",
                         f"{top} - 3 * {ov}", f"Internal.stack_h + 6 * {ov}")


def build_grooves(doc):
    """The bottom's grooves (a cutting tool): the notches grown by
    stack_clearance normal to every face (sides stack_side further out
    horizontally, groove_d deep, stack_clearance longer at each end), from
    `overlap` below the bed face up."""
    ov = "Internal.overlap"
    outer = offset_loft(doc, "GrooveOuter", [
        (f"-{ov}", f"Internal.groove_out + {ov}"),
        ("Internal.groove_d", "Internal.groove_out - Internal.groove_d"),
    ])
    inner = offset_loft(doc, "GrooveInner", [
        (f"-2 * {ov}", "Internal.groove_in / 2"),
        ("0 mm", "Internal.groove_in"),
        (f"Internal.groove_d + {ov}", f"Internal.groove_in + Internal.groove_d + {ov}"),
    ])
    ring = cut(doc, "GrooveRing", outer, inner)
    return _keep_corners(doc, "Grooves", ring, "Internal.stack_reach + Internal.stack_clearance",
                         f"-3 * {ov}", f"Internal.groove_d + 6 * {ov}")
