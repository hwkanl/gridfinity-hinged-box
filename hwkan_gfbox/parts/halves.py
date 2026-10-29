"""Split the box into bottom and lid at split_z; rim band, lid rim, and the
rim's round alignment bead (bottom) and channel (lid)."""
import FreeCAD as App

from hwkan_gfbox.shapes import (_bind, box, common, cut, fuse, hide, offset_loft, offset_prism, place,
                                rounded_rect)

# Half-space boxes: wider than anything that will ever be added to the box.
HALF_XY = "2 * (Internal.outer_w + Internal.outer_d)"


def split(doc, box_obj):
    """Returns (BottomRaw, LidRaw): box_obj below / above split_z."""
    lower = box(doc, "LowerHalf", HALF_XY, HALF_XY, "-Internal.box_h", "Internal.box_h + Internal.split_z")
    upper = box(doc, "UpperHalf", HALF_XY, HALF_XY, "Internal.split_z", "2 * Internal.box_h")
    return common(doc, "BottomRaw", box_obj, lower), common(doc, "LidRaw", box_obj, upper)


# Middle of the rim (wall plus rim_extra), measured outward from the cavity wall.
RIM_MID = "(Internal.wall_t + Internal.rim_extra) / 2"


def _ring(doc, label, inner, outer, z0, height):
    """Ring between the cavity rectangle offset by `inner` and by `outer`
    (concentric rounded corners), from z0 up by height. The inner prism
    overshoots by `overlap` below and above."""
    outer_prism = offset_prism(doc, f"{label}Outer", outer, z0, height)
    inner_prism = offset_prism(doc, f"{label}Inner", inner,
                               f"({z0}) - Internal.overlap", f"({height}) + 2 * Internal.overlap")
    return cut(doc, label, outer_prism, inner_prism)


def build_rim_band(doc):
    """Bottom part's band, rim_extra proud of the wall below the split,
    with a 45 degree underside chamfer so it prints without overhang."""
    z0 = "Internal.split_z - Internal.rim_band_h"
    outer = offset_loft(doc, "RimBandOuter", [
        (z0, "Internal.wall_t"),
        (f"{z0} + Internal.rim_extra", "Internal.wall_t + Internal.rim_extra"),
        ("Internal.split_z", "Internal.wall_t + Internal.rim_extra"),
    ])
    inner = offset_prism(doc, "RimBandInner", "Internal.wall_t - Internal.overlap",
                         f"{z0} - Internal.overlap", "Internal.rim_band_h + 2 * Internal.overlap")
    return cut(doc, "RimBand", outer, inner)


def build_corner_pads(doc):
    """Corner pads: the rim-width ring over the bottom part's full height,
    kept only within pad_reach of each corner (flush with the band)."""
    ring = _ring(doc, "CornerPadRing", "Internal.wall_t - Internal.overlap",
                 "Internal.wall_t + Internal.rim_extra", "0 mm", "Internal.split_z")
    h = "Internal.split_z + 2 * Internal.overlap"
    across_x = box(doc, "PadCrossX", "Internal.outer_w - 2 * Internal.pad_reach", HALF_XY,
                   "-Internal.overlap", h)
    across_y = box(doc, "PadCrossY", HALF_XY, "Internal.outer_d - 2 * Internal.pad_reach",
                   "-Internal.overlap", h)
    return cut(doc, "CornerPads", ring, fuse(doc, "PadCross", [across_x, across_y]))


def build_lid_rim(doc):
    """Widens the whole lid by rim_extra, flush with the bottom's band."""
    return _ring(doc, "LidRim", "Internal.wall_t - Internal.overlap",
                 "Internal.wall_t + Internal.rim_extra", "Internal.split_z", "Internal.lid_h")


# The rim's alignment bead (bottom) and channel (lid) share one section: a
# circular arc centered on the rim's middle line, lip_c below the split.
LIP_Z = "Internal.split_z - Internal.lip_c"


def _round_ring(doc, label, radius):
    """Solid ring of circular section (`radius`) whose center line is the
    rim's middle line (the cavity outline offset by RIM_MID, corners
    concentric) at height LIP_Z: a circle swept along that line. (Cylinders
    plus quarter tori gave invalid unions for most grid sizes.)"""
    path = rounded_rect(doc, f"{label}Path", f"Internal.grid_w + 2 * {RIM_MID}",
                        f"Internal.grid_d + 2 * {RIM_MID}", RIM_MID, "0 mm", "0 mm", LIP_Z)
    section = doc.addObject("Part::Circle", f"{label}Section")
    section.Label = f"{label}Section"
    section.Placement.Rotation = App.Rotation(App.Vector(0, 1, 0), 90)  # normal along X
    _bind(section, {"Radius": radius})
    place(section, "0 mm", f"-Internal.grid_d / 2 - {RIM_MID}", LIP_Z)  # on the front edge of the path
    sweep = doc.addObject("Part::Sweep", label)
    sweep.Label = label
    sweep.Sections = [section]
    sweep.Spine = path
    sweep.Solid = True
    sweep.Frenet = True
    hide(section)
    return sweep


def build_tongue(doc):
    """The bottom's round alignment bead: the ring of the channel's section
    less lip_clearance, kept from `overlap` below the split up. (Fusing the
    whole ring, deep into the rim, made an invalid Bottom for some sizes.)"""
    ring = _round_ring(doc, "TongueRing", "Internal.lip_r - Internal.lip_clearance")
    above = box(doc, "TongueAbove", HALF_XY, HALF_XY, "Internal.split_z - Internal.overlap", "Internal.lid_h")
    return common(doc, "Tongue", ring, above)


def build_groove(doc):
    """The lid's round alignment channel, cut from the lid: lip_thickness wide
    and lip_height deep at the split. As the lid opens it lifts off the bead
    (see validate: the arc is shallower than the lid's motion at its edge)."""
    return _round_ring(doc, "Groove", "Internal.lip_r")
