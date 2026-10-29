"""Parameter validation, run before any geometry is built."""
import math

from hwkan_gfbox.params import DESIGN_GAPS, FIT, INPUT, PARAMS, TOLERANCE
from hwkan_gfbox.sheet import ParamError, value

FEET_XY_CLEARANCE_MAX = 0.5  # mm; keeps the feet's bottom corner radius positive


def validate(sheet):
    """Raise ParamError listing every problem; return None when valid.
    The sheet must be recomputed first."""
    def v(name):
        return value(sheet, name)

    errors = []
    for name, _, tier, _ in PARAMS:
        if tier == INPUT and (v(name) != int(v(name)) or v(name) < 1):
            errors.append(f"{name} must be a whole number >= 1 (got {v(name):g})")
        if (tier in (TOLERANCE, FIT) or name in DESIGN_GAPS) and v(name) < 0:
            errors.append(f"{name} must be >= 0 (got {v(name):g} mm)")
    if min(v("gf_x"), v("gf_y")) < 2:
        errors.append("gf_x and gf_y must be at least 2 for a hinged box "
                      f"(got {v('gf_x'):g} x {v('gf_y'):g})")
    if v("gf_x") < v("gf_y"):
        errors.append("gf_x must be >= gf_y (the hinges go on an X side): swap them "
                      f"(got {v('gf_x'):g} x {v('gf_y'):g})")
    if v("hinge_count") < 2:
        errors.append(f"hinge_count must be at least 2 (got {v('hinge_count'):g})")
    for name in ("hinge_count", "lock_count"):
        if v(name) > v("gf_x"):
            errors.append(f"{name} must be at most gf_x, one per grid unit "
                          f"(got {v(name):g} on a {v('gf_x'):g} wide box)")
    if v("feet_xy_clearance") > FEET_XY_CLEARANCE_MAX:
        errors.append(f"feet_xy_clearance must be <= {FEET_XY_CLEARANCE_MAX:g} mm "
                      f"(got {v('feet_xy_clearance'):g} mm)")
    side_wall = (v("wall_t") + v("rim_extra") - v("lip_thickness")) / 2
    if side_wall < v("min_wall") - 1e-9:
        errors.append("lid wall beside the channel must be at least min_wall "
                      f"((wall_t + rim_extra - lip_thickness) / 2 = "
                      f"({v('wall_t'):g} + {v('rim_extra'):g} - {v('lip_thickness'):g}) / 2 = "
                      f"{side_wall:g} < {v('min_wall'):g} mm)")
    lt, lh, lc = v("lip_thickness"), v("lip_height"), v("lip_clearance")
    if not 0 < lh < lt / 2:
        errors.append("lip_height must be between 0 and lip_thickness / 2: the channel is a circular "
                      f"arc shallower than a half circle (got {lh:g} mm, lip_thickness {lt:g} mm)")
    elif lc >= lh:
        errors.append(f"lip_clearance must be less than lip_height, or there is no bead ({lc:g} >= {lh:g} mm)")
    else:
        # As the lid opens, the channel's edge nearest the hinge moves forward and
        # up, perpendicular to its radius from the hinge axis. It lifts off the
        # bead only if the arc there is less steep than that motion.
        lip_r = (lt * lt / 4 + lh * lh) / (2 * lh)
        rim_mid = (v("wall_t") + v("rim_extra")) / 2
        if lip_r >= rim_mid:
            errors.append(f"the channel's arc radius ({lip_r:g} mm, from lip_thickness and lip_height) must be "
                          f"less than (wall_t + rim_extra) / 2 = {rim_mid:g} mm, the rim's corner radius, "
                          "or the swept ring folds over itself at the corners; make lip_height larger")
        edge = math.degrees(math.asin(lt / 2 / lip_r))
        limit = math.degrees(math.atan2(
            v("hinge_axis_out") + (v("wall_t") + v("rim_extra") - lt) / 2, v("hinge_axis_z")))
        if edge >= limit:
            errors.append(f"the channel is too steep for the lid to lift off the bead as it opens: its arc "
                          f"meets the split at {edge:g} deg from vertical, which must be less than {limit:g} deg "
                          "(set by the hinge axis position); make lip_height smaller or lip_thickness larger")
    if v("rim_band_h") <= v("rim_extra"):
        errors.append("rim_band_h must be greater than rim_extra "
                      f"({v('rim_band_h'):g} <= {v('rim_extra'):g} mm)")
    if v("lip_height") >= v("base_h"):
        errors.append("lip_height (the channel depth) must be less than base_h "
                      f"({v('lip_height'):g} >= {v('base_h'):g} mm)")
    if v("pad_reach") < v("wall_t"):
        errors.append(f"pad_reach must be at least wall_t ({v('pad_reach'):g} < {v('wall_t'):g} mm)")
    if 2 * v("pad_reach") >= min(v("outer_w"), v("outer_d")):
        errors.append("2 * pad_reach must be less than outer_w and outer_d "
                      f"(2 * {v('pad_reach'):g} >= {min(v('outer_w'), v('outer_d')):g} mm)")
    if v("stack_h") <= 0 or v("stack_w") <= 2 * v("stack_h"):
        errors.append("the stacking notches need stack_h > 0 and stack_w > 2 * stack_h (a flat top) "
                      f"({v('stack_h'):g}, {v('stack_w'):g} mm)")
    if v("groove_in") <= 0:
        errors.append("the stacking grooves must stay in the wall: wall_t / 2 - stack_w / 2 - stack_clearance * sqrt(2) "
                      f"must be > 0 ({v('groove_in'):g} mm); make stack_w smaller")
    flat = v("wall_t") + v("rim_extra") - max(v("bottom_chamfer"), v("lid_chamfer"))
    if v("groove_out") >= min(v("wall_t"), flat):
        errors.append("the stacking grooves must stay in the wall and inside the bottom's and lid's chamfers: "
                      f"wall_t / 2 + stack_w / 2 + stack_clearance * sqrt(2) = {v('groove_out'):g} mm must be less "
                      f"than {min(v('wall_t'), flat):g} mm; make stack_w smaller")
    if v("stack_reach") + v("stack_clearance") + v("bottom_chamfer") > v("pad_reach"):
        errors.append("the stacking grooves must end inside the corner pads: stack_reach + stack_clearance + "
                      f"bottom_chamfer ({v('stack_reach') + v('stack_clearance') + v('bottom_chamfer'):g} mm) must be "
                      f"at most pad_reach ({v('pad_reach'):g} mm)")
    if v("knuckle_r") <= v("pin_dia") / 2:
        errors.append("knuckle_r must be greater than pin_dia / 2 "
                      f"({v('knuckle_r'):g} <= {v('pin_dia') / 2:g} mm)")
    if not 0 < v("pin_angle") < 90:
        errors.append(f"pin_angle must be between 0 and 90 deg (got {v('pin_angle'):g})")
    elif v("pin_tip_c") <= 0:
        errors.append(f"pin_tip_c must be > 0 (got {v('pin_tip_c'):g} mm): "
                      "the pin's tip sphere must sit in front of the knuckle face")
    if 2 * v("pin_len") >= v("knuckle_gap"):
        errors.append("2 * pin_len must be less than knuckle_gap, or the pins meet "
                      f"(2 * {v('pin_len'):g} >= {v('knuckle_gap'):g} mm)")
    if not 0 <= v("knuckle_flare") < 90:
        errors.append(f"knuckle_flare must be between 0 and 90 deg, 90 excluded (got {v('knuckle_flare'):g})")
        raise ParamError("invalid parameters:\n  " + "\n  ".join(errors))
    if v("hinge_root_len") >= v("hinge_pitch"):
        errors.append("neighbouring hinges must not touch at the flared root: hinge_root_len must be "
                      f"less than hinge_pitch ({v('hinge_root_len'):g} >= {v('hinge_pitch'):g} mm); lower hinge_count")
    hinge_far = v("grid_w") / 2 - v("hinge_pitch") / 2 + v("hinge_root_len") / 2
    if hinge_far > v("outer_w") / 2 - v("pad_reach"):
        errors.append("every hinge must clear the corner pads, measured at the flared root "
                      f"({hinge_far:g} > outer_w / 2 - pad_reach = {v('outer_w') / 2 - v('pad_reach'):g} mm); "
                      "lower hinge_count")
    if 0 < v("pin_angle") < 90:
        pin_base = v("pin_dia") / 2 + v("overlap") / math.tan(math.radians(v("pin_angle")))
        if pin_base >= v("knuckle_r"):
            errors.append("pin_dia / 2 + overlap / tan(pin_angle) must be less than knuckle_r "
                          f"(the pin's widened base must fit in the knuckle; {pin_base:g} >= {v('knuckle_r'):g} mm)")
    hc, dc = v("hinge_clearance"), v("hinge_dovetail_fit")
    if hc <= 0:
        errors.append(f"hinge_clearance must be > 0 (got {hc:g} mm): the free leaf is printed in place")
    if v("leaf_r") <= v("pin_dia") / 2 + hc:
        errors.append("leaf_r must be greater than pin_dia / 2 + hinge_clearance: the socket must fit in "
                      f"the leaf knuckle ({v('leaf_r'):g} <= {v('pin_dia') / 2 + hc:g} mm)")
    if 0 < v("pin_angle") < 90 and 2 * v("socket_depth") >= v("leaf_w"):
        errors.append("2 * socket_depth must be less than leaf_w, or a leaf's two sockets meet "
                      f"(2 * {v('socket_depth'):g} >= {v('leaf_w'):g} mm)")
    if v("dovetail_len") <= 0:
        errors.append(f"dovetail_len must be > 0 (got {v('dovetail_len'):g} mm)")
    if not 0 < v("dovetail_t") <= v("hinge_axis_z") + v("leaf_r"):
        errors.append("dovetail_t must be > 0 and <= hinge_axis_z + leaf_r, so the leaf body's top line can "
                      f"touch the knuckle arc ({v('dovetail_t'):g} vs {v('hinge_axis_z') + v('leaf_r'):g} mm)")
    if not 0 < v("dovetail_angle") < 90:
        errors.append(f"dovetail_angle must be between 0 and 90 deg (got {v('dovetail_angle'):g})")
    else:
        # implied by the body-clearance and socket rules; kept as the spec's guard
        if v("dovetail_w") - 2 * v("dovetail_side_in") <= 0:
            errors.append("dovetail_w - 2 * hinge_dovetail_fit / sin(dovetail_angle) must be > 0 "
                          f"({v('dovetail_w'):g} - 2 * {v('dovetail_side_in'):g} mm)")
        body_gap = (v("dovetail_w") - v("leaf_w")) / 2 * math.sin(math.radians(v("dovetail_angle")))
        if body_gap < dc - 1e-9:
            errors.append("the leaf body must clear the slot by hinge_dovetail_fit: (dovetail_w - leaf_w) / 2 "
                          f"* sin(dovetail_angle) = {body_gap:g} < {dc:g} mm")
        if v("hinge_rib_w") < v("dovetail_base_w") + 2 * v("min_wall"):
            errors.append("hinge_rib_w must be >= dovetail_base_w + 2 * min_wall: the rib must hold the slot "
                          f"({v('hinge_rib_w'):g} < {v('dovetail_base_w') + 2 * v('min_wall'):g} mm)")
    if v("rib_full") - v("rib_depth") <= 0:
        errors.append("the hinge ribs' 45 deg underside must meet the back wall above the bed: rib_full - rib_depth = "
                      f"{v('rib_full') - v('rib_depth'):g} mm (raise gf_z_units or lower rib_flare_below)")
    rib_far = v("grid_w") / 2 - v("hinge_pitch") / 2 + v("hinge_rib_w") / 2
    if rib_far > v("outer_w") / 2 - v("pad_reach"):
        errors.append("the hinge ribs must clear the corner pads "
                      f"({rib_far:g} > outer_w / 2 - pad_reach = {v('outer_w') / 2 - v('pad_reach'):g} mm); "
                      "lower hinge_count")
    if v("hinge_rib_w") >= v("hinge_pitch"):
        errors.append("neighbouring hinge ribs must not touch: hinge_rib_w must be less than hinge_pitch "
                      f"({v('hinge_rib_w'):g} >= {v('hinge_pitch'):g} mm); lower hinge_count")
    if not 0 <= v("hinge_detent_height") < v("leaf_notch_d"):
        errors.append(f"hinge_detent_height must be between 0 and leaf_notch_d = {v('leaf_notch_d'):g} mm "
                      f"(got {v('hinge_detent_height'):g} mm)")
    if v("hinge_nub_lift") < v("overlap") or v("hinge_nub_h") <= 0:
        errors.append(f"the hinge nub must stand clear above the slot (hinge_nub_lift >= {v('overlap'):g} mm) "
                      "and hinge_nub_h must be > 0")
    if v("hinge_nub_top") >= v("split_z"):
        errors.append("the hinge nub must stay below the parting line: hinge_nub_lift + hinge_nub_h must be less "
                      f"than dovetail_drop ({v('hinge_nub_lift') + v('hinge_nub_h'):g} >= {v('dovetail_drop'):g} mm)")
    if v("leaf_notch_bot") + v("leaf_notch_h") <= v("hinge_nub_top"):
        errors.append("the leaf's notch must reach past the hinge nub's top: leaf_notch_h must be > "
                      f"hinge_nub_h + hinge_detent_clearance = {v('hinge_nub_h') + v('hinge_detent_clearance'):g} mm")
    if v("slot_floor") <= 0:
        errors.append("the slot floor must stay above the box bottom: split_z - dovetail_drop - dovetail_len "
                      f"= {v('slot_floor'):g} <= 0 mm")
    if v("hinge_axis_z") < v("leaf_tan"):
        errors.append("hinge_axis_z must be >= leaf_r / sqrt(2) so the leaf's 45 deg underside reaches the bed "
                      f"in front of the axis ({v('hinge_axis_z'):g} < {v('leaf_tan'):g} mm)")
    room = v("hinge_axis_out") - hc
    reach = math.hypot(v("hinge_axis_z") - 2 * v("leaf_tan"), v("hinge_axis_z"))
    if reach > room + 1e-9:
        errors.append(f"the leaf's front (its 45 deg foot, {reach:g} mm from the axis) must clear the lid face by "
                      f"hinge_clearance over the whole swing: at most hinge_axis_out - hinge_clearance = {room:g} mm")
    if v("leaf_r") > room + 1e-9:
        errors.append(f"leaf_r must be <= hinge_axis_out - hinge_clearance ({v('leaf_r'):g} > {room:g} mm)")
    if v("hinge_axis_z") + v("leaf_r") > v("lid_h") + 1e-9:
        errors.append("the leaf top must stay below the lid top: hinge_axis_z + leaf_r = "
                      f"{v('hinge_axis_z') + v('leaf_r'):g} > lid_h = {v('lid_h'):g} mm")
    if v("dovetail_start") < v("knuckle_r") + hc - 1e-9:
        errors.append("the dovetail must clear the lid knuckles: dovetail_start (hinge_axis_z + dovetail_drop) "
                      f"= {v('dovetail_start'):g} must be >= knuckle_r + hinge_clearance = {v('knuckle_r') + hc:g} mm")
    for name in ("lever_low", "hook_l", "hook_nl", "hook_nr", "lever_print_angle", "hook_print_angle"):
        if not math.isfinite(v(name)):
            errors.append(f"{name} is not a finite number ({v(name)}): the lock's mechanism geometry is "
                          "degenerate for these parameters (check pivot_dist, over_center, lobe_r, bar_r)")
    if v("pivot_dist") <= 0:
        errors.append(f"pivot_dist must be > 0 (got {v('pivot_dist'):g} mm)")
    if not 0 < v("over_center") < 90:
        errors.append(f"over_center must be between 0 and 90 deg (got {v('over_center'):g})")
    if not 0 < v("bar_r") < v("lobe_r"):
        errors.append(f"bar_r must be > 0 and less than lobe_r (got {v('bar_r'):g}, lobe_r {v('lobe_r'):g} mm)")
    if v("lock_lip_e") <= 0:
        errors.append(f"lock_lip_e must be > 0 (got {v('lock_lip_e'):g} mm)")
    if v("lock_lip_e") > 0:
        # the seat: next to the lid face, its floor and the stop at least min_wall thick
        su, sz, sr, top, mw = (v(n) for n in ("lock_seat_u", "lock_seat_z", "lock_seat_r", "lock_stop_top", "min_wall"))
        if su <= 0:
            errors.append(f"the lip's seat must lie in front of the lid face: lock_seat_u = {su:g} mm must be > 0 "
                          "(raise lock_k_u)")
        if sz - sr < mw:
            errors.append(f"the lip under the seat must be at least min_wall ({mw:g} mm) thick: its floor, "
                          f"lock_seat_z - lock_seat_r = {sz - sr:g} mm above the parting line (lower lock_bar_drop "
                          "or latch_seat_clearance)")
        if v("lock_lip_e") - (su + sr) < mw:
            errors.append("the stop along the lip's front edge must be at least min_wall wide: lock_lip_e - "
                          f"(lock_seat_u + lock_seat_r) = {v('lock_lip_e') - (su + sr):g} mm < {mw:g} mm "
                          "(raise lock_lip_e or lower lock_k_u)")
        if not sz <= top <= v("lid_h"):
            errors.append(f"the stop's top (lock_stop_top = {top:g} mm) must be between the seat's center "
                          f"({sz:g} mm) and the lid top (lid_h = {v('lid_h'):g} mm): adjust lock_stop_rise")
    above_key = v("dovetail_t") - v("latch_dovetail_fit") - v("lock_key_d")
    if above_key < v("min_wall") or v("lock_key_d") <= 0:
        errors.append("the latch base's dovetail above its key must be at least min_wall thick and the key "
                      f"must have depth: dovetail_t - latch_dovetail_fit - lock_key_d = {above_key:g} mm, "
                      f"lock_key_d = {v('lock_key_d'):g} mm")
    if not 0 < v("lock_key_h") < v("latch_top") - v("pad_bot") - v("lock_key_d"):
        errors.append(f"lock_key_h must be > 0 and leave room for the flare below the base's top "
                      f"(got {v('lock_key_h'):g}, base height {v('latch_top') - v('pad_bot'):g} mm)")
    # The part above the key passes the nub with lock_key_d - latch_detent_height to
    # spare (the nub moves out with latch_dovetail_fit); touching is fine,
    # the plastic flexes.
    if not 0 <= v("latch_detent_height") <= v("lock_key_d"):
        errors.append(f"latch_detent_height must be between 0 and lock_key_d = {v('lock_key_d'):g} mm, so the base's "
                      f"shallower part above its key passes the nub (got {v('latch_detent_height'):g} mm)")
    if not 0 < v("lock_detent_ramp") < 90:
        errors.append(f"lock_detent_ramp must be between 0 and 90 deg (got {v('lock_detent_ramp'):g})")
    lc = v("latch_clearance")
    if lc <= 0:
        errors.append(f"latch_clearance must be > 0 (got {lc:g} mm): the latch is printed in place")
    if v("latch_base_hw") <= 0:
        errors.append(f"latch_base_hw must be > 0 (got {v('latch_base_hw'):g} mm)")
    if v("split_z") + v("lever_low") < -1e-9:
        errors.append("the closed latch must not reach below the box bottom: the lever's tip is "
                      f"{-v('lever_low'):g} mm below the parting line, which is only {v('split_z'):g} mm up; "
                      "raise gf_z_units")
    if v("lock_w") >= v("lock_pitch"):
        errors.append("neighbouring locks must not touch: lock_w must be less than lock_pitch "
                      f"({v('lock_w'):g} >= {v('lock_pitch'):g} mm); lower lock_count")
    if v("pad_top") > 1e-9:
        errors.append(f"pad_top must be <= 0, or the pad runs into the lid's lip (got {v('pad_top'):g} mm)")
    roof = v("pad_top") - v("lock_slot_top")
    if roof < v("min_wall") - 1e-9:
        errors.append("the slot's roof must be at least min_wall thick: pad_top - lock_slot_top = "
                      f"{roof:g} < {v('min_wall'):g} mm")
    lock_far = v("grid_w") / 2 - v("lock_pitch") / 2 + v("lock_w") / 2
    if lock_far > v("outer_w") / 2 - v("pad_reach"):
        errors.append("the locks must clear the corner pads "
                      f"({lock_far:g} > outer_w / 2 - pad_reach = {v('outer_w') / 2 - v('pad_reach'):g} mm); "
                      "lower lock_count")
    if errors:
        raise ParamError("invalid parameters:\n  " + "\n  ".join(errors))
