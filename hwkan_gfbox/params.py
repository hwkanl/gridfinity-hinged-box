"""The parameter table: the only place defaults and formulas are written down.

Each row is (name, value, tier, comment). value is the spreadsheet cell
content: a number ("3"), a length ("3 mm"), or a formula ("=gf_x * gf_pitch")
that refers to other parameters by name.
"""
INPUT = "input"
TOLERANCE = "tolerance"
DESIGN = "design"
GRIDFINITY = "gridfinity"
DERIVED = "derived"
FIT = "fit"

# Spreadsheet sections, in display order.
SECTIONS = [
    (INPUT, "Inputs"),
    (TOLERANCE, "Tolerances (gaps between printed parts; depend on your printer)"),
    (FIT, "Fit"),
    (DESIGN, "Design constants (internal - not guaranteed robust to changes)"),
    (GRIDFINITY, "Gridfinity constants (standard - do not edit)"),
    (DERIVED, "Derived (formulas)"),
]

# What users set: the inputs (on the Params sheet) and the preset's values.
USER_TIERS = (INPUT, TOLERANCE, FIT)
USER_SHEET = "Params"
PRESET_SHEET = "Preset"  # the preset's values the box was built with; written by every build
INTERNAL_SHEET = "Internal"

# What a preset holds (hwkan_gfbox.presets): the printer- and material-dependent values.
PRESET_TIERS = (TOLERANCE, FIT)
DEFAULT_PRESET = "default"  # the built-in preset: the defaults below


def sheet_of(tier):
    """Name of the sheet that holds parameters of this tier."""
    if tier == INPUT:
        return USER_SHEET
    return PRESET_SHEET if tier in PRESET_TIERS else INTERNAL_SHEET

PARAMS = [
    ("gf_x", "3", INPUT, "grid cells along X"),
    ("gf_y", "2", INPUT, "grid cells along Y"),
    ("gf_z_units", "6", INPUT, "bin height in 7 mm units (stacking lip not included)"),
    ("hinge_count", "2", INPUT, "number of hinges along the back wall (2 to gf_x, as many as fit)"),
    ("lock_count", "2", INPUT, "number of locks along the front wall (1 to gf_x, as many as fit)"),

    ("feet_xy_clearance", "0.25 mm", TOLERANCE, "lid feet shrunk by this per side vs a standard bin base"),
    ("feet_z_clearance", "0.5 mm", TOLERANCE, "lid feet raised by this above a seated bin base; the lid never presses on the bins"),
    ("lip_clearance", "0.2 mm", TOLERANCE, "gap between the rim's round bead (bottom) and its channel (lid), normal to the arc"),
    ("hinge_clearance", "0.15 mm", TOLERANCE, "print-in-place gap between the free leaf and the lid knuckles, pins and lid face"),
    ("dovetail_clearance", "0.09 mm", TOLERANCE, "gap between the leaf's dovetail sides and its slot's, normal to the sides (the slot's floor stays nominal)"),
    ("nub_clearance", "0.15 mm", TOLERANCE, "gap between the seated leaf's notch edge and the hinge nub's flat underside: how far the snapped leaf can lift"),
    ("latch_clearance", "0.2 mm", TOLERANCE, "print-in-place gap between the latch's base, lever and hook, and around their axles"),
    ("lock_dovetail_clearance", "0.1 mm", TOLERANCE, "gap between the latch base's dovetail and the pad's slot (sides, normal to the face, and the slot's roof)"),
    ("back_clearance", "1 mm", DESIGN, "extra gap between the back row of bins and the hinge wall, so the closing lid's back edge clears the bins (more than ~0.51 needed)"),
    ("lock_seat_clearance", "0.25 mm", TOLERANCE, "gap around the hook bar in the lip's seat: the seat's curve is this much wider than the bar's round underside"),
    ("hook_preload", "0.2 mm", FIT, "the hook is this much shorter than at zero pressure: the latch's pull on the lid"),
    ("lock_detent", "0.35 mm", FIT, "the nub below the seated latch base stands this far into its dovetail's full-depth part: the snap the base clicks over (0 = no snap, the nub just touches)"),
    ("hinge_detent", "0.6 mm", FIT, "the nub above each hinge slot stands this far out of the slot's wide face into the leaf's notch: the snap the leaf's dovetail flexes over on the way in (0 = no snap)"),

    ("wall_t", "3 mm", DESIGN, "side wall thickness"),
    ("floor_t", "3 mm", DESIGN, "floor skin under the baseplate pockets"),
    ("top_t", "3 mm", DESIGN, "lid ceiling skin"),
    ("lip_height", "0.7 mm", DESIGN, "depth of the lid's round channel above the split (the bead on the bottom is lip_clearance lower)"),
    ("lip_thickness", "3 mm", DESIGN, "width of the lid's round channel at the split, centered in the rim (wall_t + rim_extra)"),
    ("rim_extra", "2 mm", DESIGN, "extra outward wall thickness at the parting line: the whole lid and a band on the bottom"),
    ("rim_band_h", "8 mm", DESIGN, "height of the bottom part's rim band below the split, including its 45 deg underside chamfer"),
    ("min_wall", "0.8 mm", DESIGN, "thinnest printed wall the design allows (e.g. lid wall beside the channel)"),
    ("pad_reach", "8 mm", DESIGN, "corner pads run this far along each wall from the outer corner point of the wall_t walls"),
    ("overlap", "0.5 mm", DESIGN, "internal overlap used whenever one solid is unioned onto another"),
    ("ridge_clip", "0.2 mm", DESIGN, "pocket ridges clipped flat this far below their knife edge (knife edges break FreeCAD booleans and cannot be printed)"),

    ("hinge_axis_out", "4.5 mm", DESIGN, "hinge axis distance outward from the lid's back face"),
    ("knuckle_len", "3 mm", DESIGN, "length of each lid knuckle along the hinge axis"),
    ("knuckle_gap", "10 mm", DESIGN, "gap between a hinge's two lid knuckles (room for the free leaf's middle knuckle)"),
    ("pin_dia", "5 mm", DESIGN, "cone pin base diameter, on the knuckle's inner face"),
    ("pin_angle", "50 deg", DESIGN, "angle between the cone pin's flank and the knuckle face"),
    ("knuckle_flare", "30 deg", DESIGN, "tilt of each knuckle's outer end face about a vertical line, so the knuckle is longer where it joins the lid"),
    ("pin_tip_r", "1 mm", DESIGN, "radius of the cone pin's rounded tip (tangent to the flank)"),
    ("leaf_r", "3.5 mm", DESIGN, "free leaf's knuckle radius"),
    ("dovetail_drop", "3 mm", DESIGN, "the dovetail (and the hinge rib's top) starts this far below the parting line"),
    ("dovetail_len", "10 mm", DESIGN, "dovetail length along the leaf (the slot's depth below the rib's top)"),
    ("dovetail_t", "3 mm", DESIGN, "dovetail thickness; also how far the hinge rib stands proud of the swung-down leaf's underside"),
    ("dovetail_w", "10.4 mm", DESIGN, "dovetail width at its narrow (outer) face (wider than knuckle_gap, so the leaf body clears the slot's opening for any hinge_clearance)"),
    ("dovetail_angle", "60 deg", DESIGN, "angle between the dovetail's sides and its wide (bed) face"),
    ("hinge_nub_lift", "1 mm", DESIGN, "the hinge nub's flat underside (the ledge the leaf's notch catches on) lies this far above the dovetail's top (rib_top)"),
    ("hinge_nub_h", "1 mm", DESIGN, "hinge nub height (flat top and underside)"),
    ("leaf_notch_h", "1.5 mm", DESIGN, "height of the notch across the leaf's bed face that takes the hinge nub"),
    ("leaf_notch_d", "0.8 mm", DESIGN, "depth of the leaf's notch"),
    ("hinge_rib_w", "20 mm", DESIGN, "hinge rib width along X"),
    ("rib_flare_below", "2 mm", DESIGN, "each hinge rib has its full depth from this far below its dovetail slot's floor up; below that it narrows at 45 deg into the back wall"),
    ("lock_lip_w", "10 mm", DESIGN, "width of the lid's lock lip"),
    ("lock_lip_e", "5 mm", DESIGN, "how far the lock lip stands out of the lid's front face"),
    ("lock_k_u", "1.5 mm", DESIGN, "K, where the hook bar bears on the lip (the unloaded bar's center): u"),
    ("lock_stop_rise", "0.5 mm", DESIGN, "the stop along the lip's front edge stands this far above the bar's center"),
    ("bar_r", "1.25 mm", DESIGN, "radius of the hook bar's round underside (and half its width)"),
    ("lock_bar_drop", "0.5 mm", DESIGN, "the unloaded hook bar's underside lies this far below K (lid_h / 2)"),
    ("lobe_r", "3 mm", DESIGN, "radius of the latch's pivot lobes (base, lever, hook) and half the lever's thickness"),
    ("latch_base_hw", "4.6 mm", DESIGN, "half width of the latch base"),
    ("plate_t", "2.5 mm", DESIGN, "thickness of each lever plate and hook arm"),
    ("slot_in_u", "=-1 mm", DESIGN, "the pad slot's wide face, outward from the front rim face (negative: inside the rim band)"),
    ("pad_top", "0 mm", DESIGN, "top of the lock pad, from the parting line: 0 = flush with it, so the lid's lip rests on the pad and the latch's pull goes straight into it"),
    ("pad_bot", "=-12 mm", DESIGN, "bottom of the lock pad's front face, from the parting line (45 deg underside below)"),
    ("lock_key_h", "3 mm", DESIGN, "the latch base's dovetail has its full depth only in its lowest lock_key_h (the slot likewise): upside down it won't go in"),
    ("lock_key_d", "0.5 mm", DESIGN, "above the key the dovetail is this much shallower (its wide face moved out), with a 45 deg flare between"),
    ("lock_detent_ramp", "30 deg", DESIGN, "the detent nub's underside (the ramp the base rides up) leans this far off the slot's wide face"),
    ("pad_margin", "1.2 mm", DESIGN, "pad width beyond the slot's wide face, each side"),
    ("latch_top", "=-2 mm", DESIGN, "top of the latch base, from the parting line (its print bed face)"),
    ("pivot_dist", "6 mm", DESIGN, "distance between the lever's pivot (P0) and the hook's pivot (P1)"),
    ("over_center", "15 deg", DESIGN, "how far P1 is past the dead center line (P0 to the lip), closed"),
    ("lever_len", "15 mm", DESIGN, "P0 to the lever's handle bar axis"),
    ("end_slant", "20 deg", DESIGN, "the lever's handle end: a straight cut this far off square, the outer side longest (a ledge for the finger)"),
    ("rib_root_fillet", "1 mm", DESIGN, "fillet in the inside corners where each hinge rib meets the back wall (0 = none)"),
    ("bottom_chamfer", "2 mm", DESIGN, "chamfer on every edge of the bottom part on the print bed (0 = none)"),
    ("rib_fillet", "1 mm", DESIGN, "fillet on each hinge rib's outer vertical corners, applied after bottom_chamfer (0 = none)"),
    ("lid_chamfer", "2 mm", DESIGN, "chamfer on the lid's top outline; the knuckle tops stay sharp (0 = none)"),
    ("lip_chamfer", "2 mm", DESIGN, "chamfer on each lock lip's lower front edge (0 = none)"),
    ("lever_tip_fillet", "2 mm", DESIGN, "fillet on the lever's handle end: the outer corner (0 = none)"),
    ("lever_heel_fillet", "1 mm", DESIGN, "fillet on the lever's handle end: the wall-side corner (0 = none)"),
    ("axle_r", "1.75 mm", DESIGN, "radius of the latch's D-shaped through-axles"),
    ("axle_flat", "1.4 mm", DESIGN, "the axles' flat (on the print bed's side) is this far from the axis"),
    ("hole_trunc_extra", "0.35 mm", DESIGN, "the axle holes' teardrop point is cut off this far beyond the hole radius"),
    ("bar_bow", "0.5 mm", DESIGN, "the hook bar is bowed this much toward P1 at its center (spring)"),

    ("gf_pitch", "42 mm", GRIDFINITY, "grid pitch"),
    ("gf_unit_h", "7 mm", GRIDFINITY, "height unit"),
    ("bp_ch_low", "0.7 mm", GRIDFINITY, "baseplate pocket: bottom 45 deg chamfer"),
    ("bp_vert", "1.8 mm", GRIDFINITY, "baseplate pocket: vertical section"),
    ("bp_ch_high", "2.15 mm", GRIDFINITY, "baseplate pocket: top 45 deg chamfer"),
    ("bp_top_r", "4 mm", GRIDFINITY, "baseplate pocket: corner radius at the top (42 x 42 opening)"),
    ("base_ch_low", "0.8 mm", GRIDFINITY, "bin base: bottom 45 deg chamfer"),
    ("base_vert", "1.8 mm", GRIDFINITY, "bin base: vertical section"),
    ("base_ch_high", "2.15 mm", GRIDFINITY, "bin base: top 45 deg chamfer"),
    ("base_top", "41.5 mm", GRIDFINITY, "bin base: size at its top"),
    ("base_top_r", "3.75 mm", GRIDFINITY, "bin base: corner radius at its top"),
    ("stack_ch_low", "0.7 mm", GRIDFINITY, "bin stacking lip: bottom 45 deg chamfer"),
    ("stack_vert", "1.8 mm", GRIDFINITY, "bin stacking lip: vertical section"),
    ("stack_ch_high", "1.9 mm", GRIDFINITY, "bin stacking lip: top 45 deg chamfer"),

    ("grid_w", "=gf_x * gf_pitch", DERIVED, "cavity width (X)"),
    ("grid_d", "=gf_y * gf_pitch + back_clearance", DERIVED, "cavity depth (Y): the grid from the front wall, back_clearance behind it"),
    ("outer_w", "=grid_w + 2 * wall_t", DERIVED, "box outer width (X)"),
    ("outer_d", "=grid_d + 2 * wall_t", DERIVED, "box outer depth (Y)"),
    ("rim_w", "=outer_w + 2 * rim_extra", DERIVED, "outer width at the parting line (X)"),
    ("rim_d", "=outer_d + 2 * rim_extra", DERIVED, "outer depth at the parting line (Y)"),
    ("bp_h", "=bp_ch_low + bp_vert + bp_ch_high", DERIVED, "baseplate pocket depth"),
    ("base_h", "=base_ch_low + base_vert + base_ch_high", DERIVED, "bin base profile height"),
    ("stack_lip_h", "=stack_ch_low + stack_vert + stack_ch_high", DERIVED, "bin stacking lip height"),
    ("bin_top_z", "=floor_t + gf_z_units * gf_unit_h + stack_lip_h", DERIVED, "top of the bins' stacking lips"),
    ("ceiling_z", "=bin_top_z + feet_z_clearance", DERIVED, "underside of the lid ceiling"),
    ("box_h", "=ceiling_z + top_t", DERIVED, "box outer height"),
    ("split_z", "=ceiling_z - base_h", DERIVED, "lid rim = bottom of the feet = top of the bottom part's walls"),
    ("lid_h", "=box_h - split_z", DERIVED, "lid height"),
    ("lip_r", "=(lip_thickness ^ 2 / 4 + lip_height ^ 2) / (2 * lip_height)", DERIVED, "radius of the channel's arc (the bead's is lip_clearance less)"),
    ("lip_c", "=lip_r - lip_height", DERIVED, "the channel's and the bead's arcs are centered this far below the split"),

    ("hinge_pitch", "=grid_w / hinge_count", DERIVED, "back wall segment per hinge; one hinge is centered in each"),
    ("hinge_c0", "=-grid_w / 2 + hinge_pitch / 2", DERIVED, "X of the first hinge's center"),
    ("hinge_len", "=2 * knuckle_len + knuckle_gap", DERIVED, "length of one hinge's lid knuckle set"),
    ("hinge_axis_z", "=lid_h / 2", DERIVED, "hinge axis height above the lid's rim plane (the print bed): the hinge is centered on the lid"),
    ("knuckle_r", "=lid_h / 2", DERIVED, "knuckle radius (centered on the hinge axis, tangent to the lid top and the bed)"),
    ("knuckle_back", "=hinge_axis_out + knuckle_r", DERIVED, "the knuckle's depth behind the lid's back face"),
    ("knuckle_flare_ext", "=knuckle_back * tan(knuckle_flare)", DERIVED, "extra knuckle length at the lid face (per knuckle) from the flare"),
    ("hinge_root_len", "=hinge_len + 2 * knuckle_flare_ext", DERIVED, "length of one hinge along the lid's back face"),
    ("pin_apex", "=pin_dia / 2 * tan(pin_angle)", DERIVED, "sharp-cone apex distance from the knuckle face"),
    ("pin_tip_c", "=pin_apex - pin_tip_r / cos(pin_angle)", DERIVED, "tip sphere center, from the knuckle face"),
    ("pin_len", "=pin_tip_c + pin_tip_r", DERIVED, "pin length from the knuckle face"),
    ("pin_tan_z", "=pin_tip_c + pin_tip_r * cos(pin_angle)", DERIVED, "where the tip sphere meets the flank: distance from the face"),
    ("pin_tan_r", "=pin_tip_r * sin(pin_angle)", DERIVED, "where the tip sphere meets the flank: cone radius"),
    ("leaf_w", "=knuckle_gap - 2 * hinge_clearance", DERIVED, "free leaf width along the axis"),
    ("leaf_tan", "=leaf_r / sqrt(2)", DERIVED, "the leaf arc's 225 deg tangent point lies this far toward the lid and below the axis"),
    ("leaf_foot", "=hinge_axis_out + hinge_axis_z - 2 * leaf_tan", DERIVED, "where the leaf's 45 deg underside meets the bed, outward from the lid's back face"),
    ("dovetail_start", "=hinge_axis_z + dovetail_drop", DERIVED, "dovetail start, from the axis along the leaf"),
    ("leaf_len", "=dovetail_start + dovetail_len", DERIVED, "leaf end, from the axis along the leaf"),
    ("leaf_top_angle", "=atan2(dovetail_t - hinge_axis_z; leaf_len) + acos(leaf_r / sqrt(leaf_len ^ 2 + (dovetail_t - hinge_axis_z) ^ 2))", DERIVED, "direction (from +out toward +z) of the point where the leaf's top line touches its knuckle arc"),
    ("socket_depth", "=pin_apex + hinge_clearance / cos(pin_angle) - hinge_clearance", DERIVED, "sharp socket cone's apex distance from the leaf's end face (flank hinge_clearance from the pin's)"),
    ("dovetail_base_w", "=dovetail_w + 2 * dovetail_t / tan(dovetail_angle)", DERIVED, "dovetail width at its wide (bed) face, nominal"),
    ("dovetail_side_in", "=dovetail_clearance / sin(dovetail_angle)", DERIVED, "each dovetail side is moved in by this, horizontally (dovetail_clearance normal to the side)"),
    ("leaf_face_gap", "=hinge_axis_out - hinge_axis_z", DERIVED, "gap between the swung-down leaf's underside and the lid's back face; the slot's wide face is in that plane"),
    ("rib_top", "=split_z - dovetail_drop", DERIVED, "top of the hinge ribs"),
    ("slot_floor", "=rib_top - dovetail_len", DERIVED, "floor of the dovetail slots: nominal, at the seated leaf's end (the hinge, not the floor, sets the leaf's height)"),
    ("hinge_nub_bot", "=rib_top + hinge_nub_lift", DERIVED, "the hinge nub's flat underside (the ledge), z"),
    ("hinge_nub_top", "=hinge_nub_bot + hinge_nub_h", DERIVED, "the hinge nub's top, z"),
    ("leaf_notch_bot", "=hinge_nub_bot - nub_clearance", DERIVED, "the seated leaf's notch: its lower edge (the one that catches on the ledge), z"),
    ("rib_depth", "=rim_d / 2 + leaf_face_gap + dovetail_t - outer_d / 2", DERIVED, "how far the hinge ribs stand out of the back wall"),
    ("rib_full", "=slot_floor - rib_flare_below", DERIVED, "the hinge ribs have their full depth from here up to rib_top"),

    ("lock_pitch", "=grid_w / lock_count", DERIVED, "front wall segment per lock; one lock is centered in each"),
    ("lock_c0", "=-grid_w / 2 + lock_pitch / 2", DERIVED, "X of the first lock's center"),
    ("lever_in", "=latch_base_hw + latch_clearance", DERIVED, "lever plates: inner half width"),
    ("pad_front", "=slot_in_u + dovetail_t", DERIVED, "the pad's front face (and the slot's narrow face), u"),
    ("lock_dovetail_side_in", "=lock_dovetail_clearance / sin(dovetail_angle)", DERIVED, "the base's dovetail sides are moved in by this, horizontally"),
    ("lock_slot_w", "=2 * (latch_base_hw + lock_dovetail_side_in)", DERIVED, "the slot's narrow width: the base's tongue is the base's full width"),
    ("lock_slot_base_w", "=lock_slot_w + 2 * dovetail_t / tan(dovetail_angle)", DERIVED, "the slot's wide width"),
    ("pad_hw", "=lock_slot_base_w / 2 + pad_margin", DERIVED, "half width of the lock pad"),
    ("lever_out", "=max(lever_in + plate_t; pad_hw)", DERIVED, "lever plates: outer half width — at least plate_t, and out to the pad's sides so the hook arms (clear of the pad) have no more side play on the lever than latch_clearance"),
    ("hook_in", "=lever_out + latch_clearance", DERIVED, "hook arms: inner half width — clear of the lever plates and of the pad"),
    ("latch_w", "=2 * (hook_in + plate_t)", DERIVED, "total latch width (outside of the hook arms)"),
    ("lock_nub_h", "=lock_dovetail_clearance + lock_detent", DERIVED, "how far the detent nub stands out of the slot's wide face"),
    ("lock_nub_top", "=pad_bot - lock_dovetail_clearance", DERIVED, "the detent nub's flat top (the ledge under the seated base), z"),
    ("lock_slot_top", "=latch_top + lock_dovetail_clearance", DERIVED, "the slot's closed top (roof), z"),
    ("lock_w", "=max(latch_w; max(2 * pad_hw; lock_lip_w))", DERIVED, "the lock's footprint along X"),
    ("lock_p0_u", "=pad_front + latch_clearance + lobe_r", DERIVED, "P0, the lever's pivot: u"),
    ("lock_p0_z", "=latch_top - lobe_r", DERIVED, "P0: z"),
    ("lock_k_z", "=lid_h / 2", DERIVED, "K: z (the lip's top)"),
    ("lock_bar_c_z", "=lid_h / 2 + bar_r - lock_bar_drop", DERIVED, "the unloaded bar's center: z (u = lock_k_u)"),
    ("lock_p1_angle", "=atan2(lock_p0_z - lock_k_z; lock_p0_u - lock_k_u) - over_center", DERIVED, "direction P0 -> P1, counterclockwise from +u (atan2 sense): the line K -> P0 continued, turned over_center toward the wall"),
    ("lock_p1_u", "=lock_p0_u + pivot_dist * cos(lock_p1_angle)", DERIVED, "P1, the hook's pivot: u"),
    ("lock_p1_z", "=lock_p0_z + pivot_dist * sin(lock_p1_angle)", DERIVED, "P1: z"),
    ("hook_angle", "=atan2(lock_bar_c_z - lock_p1_z; lock_k_u - lock_p1_u)", DERIVED, "direction P1 -> the bar"),
    ("lock_seat_r", "=bar_r + lock_seat_clearance", DERIVED, "radius of the seat's curve in the lip"),
    ("lock_seat_u", "=lock_k_u + lock_seat_clearance * cos(hook_angle)", DERIVED, "the seat curve's center, lock_seat_clearance from the unloaded bar's center away from P1 (so the bar meets it where the hook pulls): u"),
    ("lock_seat_z", "=lock_bar_c_z + lock_seat_clearance * sin(hook_angle)", DERIVED, "the seat curve's center: z"),
    ("lock_stop_top", "=lock_bar_c_z + lock_stop_rise", DERIVED, "top of the stop along the lip's front edge: z (the lip's full height there)"),
    ("bar_h_u", "=lock_k_u - hook_preload * cos(hook_angle)", DERIVED, "the bar as built (hook_preload short of the channel's center): u"),
    ("bar_h_z", "=lock_bar_c_z - hook_preload * sin(hook_angle)", DERIVED, "the bar as built: z"),
    ("hook_l", "=sqrt((bar_h_u - lock_p1_u) ^ 2 + (bar_h_z - lock_p1_z) ^ 2)", DERIVED, "P1 to the bar's center"),
    ("hook_nl", "=hook_angle + 90 deg - asin((lobe_r - bar_r) / hook_l)", DERIVED, "outward normal of the hook arm's wall-side edge (tangent to the lobe and the bar)"),
    ("hook_q_u", "=bar_h_u + bar_r", DERIVED, "Q, the bar's top corner on the +u side: u"),
    ("hook_q_z", "=bar_h_z + bar_r", DERIVED, "Q: z"),
    ("hook_nr", "=atan2(hook_q_z - lock_p1_z; hook_q_u - lock_p1_u) - acos(lobe_r / sqrt((hook_q_u - lock_p1_u) ^ 2 + (hook_q_z - lock_p1_z) ^ 2))", DERIVED, "outward normal of the hook arm's outer edge (tangent to the lobe, through Q); it lies on the print bed"),
    ("hook_t0p_u", "=lock_p1_u + lobe_r * cos(hook_nr)", DERIVED, "T0+, the outer edge's tangent point on the lobe: u"),
    ("hook_t0p_z", "=lock_p1_z + lobe_r * sin(hook_nr)", DERIVED, "T0+: z"),
    ("hook_t0m_u", "=lock_p1_u + lobe_r * cos(hook_nl)", DERIVED, "T0-, the wall-side edge's tangent point on the lobe: u"),
    ("hook_t0m_z", "=lock_p1_z + lobe_r * sin(hook_nl)", DERIVED, "T0-: z"),
    ("hook_t1m_u", "=bar_h_u + bar_r * cos(hook_nl)", DERIVED, "T1-, the wall-side edge's tangent point on the bar: u"),
    ("hook_t1m_z", "=bar_h_z + bar_r * sin(hook_nl)", DERIVED, "T1-: z"),
    ("lock_hole_trunc", "=axle_r + latch_clearance + hole_trunc_extra", DERIVED, "the holes' teardrop point is cut off this far from the axis"),
    ("lever_print_angle", "=-lock_p1_angle", DERIVED, "the lever turns this much (counterclockwise in u-z) about P0 from closed to print pose"),
    ("hook_print_angle", "=90 deg - hook_nr", DERIVED, "the hook turns this much about P1 from closed to print pose (its outer edge onto the bed)"),
    ("lever_low", "=min(lock_p0_z + (lever_len + lobe_r) * sin(lock_p1_angle) + lobe_r * cos(lock_p1_angle); lock_p0_z + (lever_len + lobe_r - 2 * lobe_r * tan(end_slant)) * sin(lock_p1_angle) - lobe_r * cos(lock_p1_angle))", DERIVED, "the closed lever's lowest point, z: the lower of its end's two corners (the outer tip and the slant's wall-side end)"),
]


def markdown_table():
    """The user's parameters (the Params sheet) as a Markdown table, for README.md."""
    rows = ["| Name | Default | Meaning |", "|---|---|---|"]
    rows += [f"| `{name}` | {val} | {comment} |" for name, val, tier, comment in PARAMS if tier in USER_TIERS]
    return "\n".join(rows) + "\n"
