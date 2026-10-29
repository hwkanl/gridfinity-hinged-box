"""Lock: per lock, a lip on the lid, a pad with a dovetail slot on the
bottom, and the latch (base, lever, hook), printed in place as one part.
Spec: docs/superpowers/specs/2026-10-02-lock-design.md.

Profile frame: u outward from the front rim face (y = -rim_d / 2 - u), z up
from the parting line (Z = split_z + z); u runs toward -Y, so a
counterclockwise turn in (u, z) is a turn about -X in the model. Everything
is built at the first lock (x = lock_c0) and repeated per lock.
"""
import math

import Draft
import FreeCAD as App

from hwkan_gfbox.parts import cosmetics
from hwkan_gfbox.shapes import _bind, common, cut, fuse, half_space, hide, per_count, place, primitive, ruled_loft
from hwkan_gfbox.sheet import SHEET_NAME, value

C = "Internal.lock_c0"
ALONG_X = App.Rotation(App.Vector(0, 1, 0), 90)  # Part primitive axis Z -> X
MINUS_X = App.Vector(-1, 0, 0)  # the model axis of a counterclockwise turn in (u, z)
# Half-space boxes: larger than the whole lock in (u, z).
LOCK_HALF = "4 * (Internal.lever_len + Internal.lid_h + Internal.lobe_r)"
# The pad's lowest point (its 45 deg underside meets the wall), z.
PAD_LOW = "(Internal.pad_bot - (Internal.pad_front + Internal.rim_extra + Internal.overlap))"
P0 = ("Internal.lock_p0_u", "Internal.lock_p0_z")  # the lever's pivot (u, z)
P1 = ("Internal.lock_p1_u", "Internal.lock_p1_z")  # the hook's pivot (u, z)
BAR = ("Internal.bar_h_u", "Internal.bar_h_z")     # the hook bar's center as built (u, z)


def Y(u):
    return f"(-Internal.rim_d / 2 - ({u}))"


def Z(z):
    return f"(Internal.split_z + ({z}))"


def point(doc, u, z, x=0):
    """Model point of profile point (u, z) at x: the numeric twin of Y() and Z()."""
    sheet = doc.getObject(SHEET_NAME)
    return App.Vector(x, -value(sheet, "rim_d") / 2 - u, value(sheet, "split_z") + z)


def lever_point(doc, du, dz, x=0):
    """Model point of the closed lever's point (du, dz) in its print frame
    (P0 at the origin, P0 -> P1 along +u, the outer side +z): turned by
    lock_p1_angle about P0."""
    sheet = doc.getObject(SHEET_NAME)
    t = math.radians(value(sheet, "lock_p1_angle"))
    return point(doc, value(sheet, "lock_p0_u") + du * math.cos(t) - dz * math.sin(t),
                 value(sheet, "lock_p0_z") + du * math.sin(t) + dz * math.cos(t), x)


def _per_lock(doc, unit, label):
    return per_count(doc, unit, label, "Params.lock_count", "Internal.lock_pitch")


def _box(doc, label, u0, u1, z0, z1, hw):
    """Box over u in [u0, u1], z in [z0, z1], x in lock_c0 +- hw. (Placed at
    Y(u1): u runs toward -Y, so u1 is the box's lowest Y.)"""
    b = primitive(doc, "Part::Box", label, {
        "Length": f"2 * ({hw})",
        "Width": f"({u1}) - ({u0})",
        "Height": f"({z1}) - ({z0})",
    })
    place(b, f"{C} - ({hw})", Y(u1), Z(z0))
    return b


def _cylinder(doc, label, u, z, r, hw):
    """Cylinder along X on (u, z), radius r, x in lock_c0 +- hw."""
    c = primitive(doc, "Part::Cylinder", label, {"Radius": r, "Height": f"2 * ({hw})"}, ALONG_X)
    place(c, f"{C} - ({hw})", Y(u), Z(z))
    return c


def _half(doc, label, u, z, theta, hw):
    """Half-space keeping the side left of the direction theta (an angle
    expression, from +u toward +z) through (u, z), over x in lock_c0 +- hw.
    (u runs toward -Y, so the (u, z) frame is mirrored: the direction theta
    is 180 deg - theta in (Y, Z) and its left is the right there, i.e. the
    left of the opposite direction, -theta, written 360 deg - theta.
    Verified by the underside probes in test_lock.)"""
    return half_space(doc, label, f"{C} - ({hw})", f"2 * ({hw})", Y(u), Z(z),
                      f"360 deg - ({theta})", LOCK_HALF)


def build_lock_lips(doc):
    """LockLips: a block on the lid's front face (from `overlap` inside it out
    to lock_lip_e, from the parting line up to lock_stop_top) with the seat
    for the hook bar cut next to the lid face: a curve of radius
    lock_seat_r around the seat center (the bar's lower outer side bears on
    it), open straight up above that center and back to the lid face from
    its floor. What stays along the front edge is the stop."""
    hw = "Internal.lock_lip_w / 2"
    su, sz, r = "Internal.lock_seat_u", "Internal.lock_seat_z", "Internal.lock_seat_r"
    top, ov = "Internal.lock_stop_top", "Internal.overlap"
    block = _box(doc, "LockLipBlock", f"-{ov}", "Internal.lock_lip_e", "0 mm", top, hw)
    cut_hw = f"{hw} + {ov}"
    seat = fuse(doc, "LockSeat", [
        _cylinder(doc, "LockSeatCurve", su, sz, r, cut_hw),
        _box(doc, "LockSeatBack", f"-2 * {ov}", su, f"{sz} - {r}", f"{top} + {ov}", cut_hw),
        _box(doc, "LockSeatOpening", su, f"{su} + {r}", sz, f"{top} + {ov}", cut_hw)])
    return _per_lock(doc, cut(doc, "LockLip", block, seat), "LockLips")


def build_lock_pads(doc):
    """LockPads: the pad on the rim band, from `overlap` inside the wall below
    the band out to pad_front, pad_top down to pad_bot at the front, with a
    45 deg underside running in and down from there. The block reaches
    `overlap` below PAD_LOW, so the underside plane doesn't pass exactly
    through its edge (the result is the same)."""
    hw = "Internal.pad_hw"
    block = _box(doc, "LockPadBlock", "-(Internal.rim_extra + Internal.overlap)", "Internal.pad_front",
                 f"{PAD_LOW} - Internal.overlap", "Internal.pad_top", hw)
    # the underside line through (pad_front, pad_bot), direction 45 deg (out and up): keep above it
    under = _half(doc, "LockPadUnderside", "Internal.pad_front", "Internal.pad_bot", "45 deg", f"{hw} + Internal.overlap")
    return _per_lock(doc, common(doc, "LockPad", block, under), "LockPads")


def _key_cut(doc, label, u_full, z_key, hw):
    """What the key takes off a dovetail whose wide face is at u = u_full:
    above z_key the wide face moves out by lock_key_d, through a 45 deg flare
    from (u_full, z_key) to (u_full + lock_key_d, z_key + lock_key_d), so it
    prints without a flat overhang either way up. x in lock_c0 +- hw."""
    thin = f"({u_full}) + Internal.lock_key_d"
    region = _box(doc, f"{label}Region", f"({u_full}) - {LOCK_HALF}", thin,
                  f"({z_key}) - {LOCK_HALF}", f"({z_key}) + {LOCK_HALF}", hw)
    # the 45 deg line through (u_full, z_key), pointing out and up: keeps its wall side
    return common(doc, label, region, _half(doc, f"{label}Flare", u_full, z_key, "45 deg", hw))


def build_lock_slots(doc):
    """LockSlots: the nominal dovetail per lock (wide face lock_slot_base_w at
    slot_in_u, narrowing outward at dovetail_angle), from below the pad
    (open at the bottom) up to lock_slot_top (the closed roof), continued
    `overlap` past the pad's front face. The wedge's local +Y points outward
    (-Y) after turning it 180 deg about Z; the turn also mirrors X, which is
    harmless because the wedge is symmetric in X."""
    low = f"({PAD_LOW} - Internal.overlap)"
    height = f"Internal.lock_slot_top - {low}"
    narrow_hw = "(Internal.lock_slot_w / 2 - Internal.overlap / tan(Internal.dovetail_angle))"
    slot = primitive(doc, "Part::Wedge", "LockSlotWedge", {
        "Xmin": "-Internal.lock_slot_base_w / 2",
        "Xmax": "Internal.lock_slot_base_w / 2",
        "X2min": f"-{narrow_hw}",
        "X2max": narrow_hw,
        "Ymin": "0 mm",
        "Ymax": "Internal.dovetail_t + Internal.overlap",
        "Zmin": "0 mm",
        "Zmax": height,
        "Z2min": "0 mm",
        "Z2max": height,
    }, App.Rotation(App.Vector(0, 0, 1), 180))
    place(slot, C, Y("Internal.slot_in_u"), Z(low))
    # the key: full depth only up to lock_key_h above pad_bot (plus the roof's clearance)
    key = _key_cut(doc, "LockSlotKey", "Internal.slot_in_u",
                   "Internal.pad_bot + Internal.lock_key_h + Preset.latch_dovetail_fit",
                   "Internal.lock_slot_base_w / 2 + Internal.overlap")
    return _per_lock(doc, cut(doc, "LockSlot", cut(doc, "LockSlotKeyed", slot, key), _detent_nub(doc)), "LockSlots")


def _detent_nub(doc):
    """The detent: a nub left standing on the slot's wide face just below the
    seated base, lock_nub_h out, across the slot. Flat on top (lock_nub_top,
    the ledge that keeps the base in), underneath a ramp lock_detent_ramp
    off the face that the base's full-depth part rides up and snaps over
    (the part above the key is lock_key_d shallower and clears it)."""
    si, h, top = "Internal.slot_in_u", "Internal.lock_nub_h", "Internal.lock_nub_top"
    bot = f"({top} - {h} / tan(Internal.lock_detent_ramp))"
    hw = "Internal.lock_slot_base_w / 2"
    block = _box(doc, "LockNubBlock", f"{si} - Internal.overlap", f"{si} + {h}",
                 f"{bot} - Internal.overlap", top, hw)
    # the ramp through (slot_in_u, bot), out and up: keeps its wall side
    ramp = _half(doc, "LockNubRamp", si, bot, "90 deg - Internal.lock_detent_ramp", hw)
    return common(doc, "LockNub", block, ramp)


def _teardrop(doc, label, u, z, hw):
    """Axle hole on (u, z), x in lock_c0 +- hw: radius axle_r +
    latch_clearance, with a 45 deg point toward -z (away from the print bed
    of the frame it is built in), cut off lock_hole_trunc from the axis. The
    point is a square of side r with one corner on the axis, turned so its
    diagonal points down (box diagonal at 45 deg in (Y, Z), turned -135 deg
    about X: -90 deg, i.e. -Z)."""
    r = "(Internal.axle_r + Preset.latch_clearance)"
    round_ = _cylinder(doc, f"{label}Round", u, z, r, hw)
    square = primitive(doc, "Part::Box", f"{label}Point", {
        "Length": f"2 * ({hw})", "Width": r, "Height": r,
    }, App.Rotation(App.Vector(1, 0, 0), -135))
    place(square, f"{C} - ({hw})", Y(u), Z(z))
    keep = _box(doc, f"{label}Trunc", f"({u}) - {r}", f"({u}) + {r}",
                f"({z}) - Internal.lock_hole_trunc", z, f"({hw}) + Internal.overlap")
    return fuse(doc, label, [round_, common(doc, f"{label}Tip", square, keep)])


def _axle_up(doc, label, u, z, hw):
    """D-shaped axle on (u, z), x in lock_c0 +- hw: radius axle_r, flat
    axle_flat from the axis on the +z side (the print bed's side in the
    frame it is built in)."""
    round_ = _cylinder(doc, f"{label}Round", u, z, "Internal.axle_r", hw)
    keep = _box(doc, f"{label}Keep", f"({u}) - Internal.axle_r - Internal.overlap",
                f"({u}) + Internal.axle_r + Internal.overlap",
                f"({z}) - Internal.axle_r - Internal.overlap", f"({z}) + Internal.axle_flat",
                f"({hw}) + Internal.overlap")
    return common(doc, label, round_, keep)


def build_latch_bases(doc):
    """LatchBases: the dovetail tongue (the slot moved in by
    latch_dovetail_fit: narrow face = the base's full width, flush with
    the pad's front face), from pad_bot up to latch_top, plus the body around
    P0 (from `overlap` inside the tongue out to P0, latch_top down to the
    lobe's bottom, and the lobe), with the teardrop hole for the lever's axle
    at P0. The base prints upside down on latch_top, so the hole points -z."""
    hw = "Internal.latch_base_hw"
    t = "(Internal.dovetail_t - Preset.latch_dovetail_fit)"
    wide = f"(Internal.latch_base_hw + {t} / tan(Internal.dovetail_angle))"
    height = "Internal.latch_top - Internal.pad_bot"
    tongue = primitive(doc, "Part::Wedge", "LatchTongue", {
        "Xmin": f"-{wide}", "Xmax": wide, "X2min": f"-{hw}", "X2max": hw,
        "Ymin": "0 mm", "Ymax": t, "Zmin": "0 mm", "Zmax": height, "Z2min": "0 mm", "Z2max": height,
    }, App.Rotation(App.Vector(0, 0, 1), 180))
    place(tongue, C, Y("Internal.slot_in_u + Preset.latch_dovetail_fit"), Z("Internal.pad_bot"))
    block = _box(doc, "LatchBaseBlock", "Internal.pad_front - Internal.overlap", P0[0],
                 f"{P0[1]} - Internal.lobe_r", "Internal.latch_top", hw)
    lobe = _cylinder(doc, "LatchBaseLobe", *P0, "Internal.lobe_r", hw)
    solid = fuse(doc, "LatchBaseSolid", [tongue, block, lobe])
    # the key: the tongue has its full depth only in its lowest lock_key_h
    key = _key_cut(doc, "LatchBaseKey", "Internal.slot_in_u + Preset.latch_dovetail_fit",
                   "Internal.pad_bot + Internal.lock_key_h", f"{wide} + Internal.overlap")
    keyed = cut(doc, "LatchBaseKeyed", solid, key)
    unit = cut(doc, "LatchBase", keyed, _teardrop(doc, "LatchBaseHole", *P0, f"{hw} + Internal.overlap"))
    return _per_lock(doc, unit, "LatchBases")


def _finish_lever(doc, bare):
    """The lever's cosmetics (spec #6, #7), on the unit in its closed pose,
    before the array: lever_tip_fillet on the handle end's outer corner
    (print frame (lever_len + lobe_r, +lobe_r)), lever_heel_fillet on its
    wall-side corner (the slant's other end, at -lobe_r). Both edges run
    along X across the handle."""
    sheet = doc.getObject(SHEET_NAME)
    r = value(sheet, "lobe_r")
    tip = value(sheet, "lever_len") + r
    heel = tip - 2 * r * math.tan(math.radians(value(sheet, "end_slant")))
    obj = bare
    for kind_label, param, (du, dz) in (("LatchLeverTipFillet", "lever_tip_fillet", (tip, r)),
                                        ("LatchLeverHeelFillet", "lever_heel_fillet", (heel, -r))):
        p = lever_point(doc, du, dz)
        obj = cosmetics.apply(doc, "Fillet", kind_label, obj, param, cosmetics.along_x_at([(p.y, p.z)]), 1)
    obj.Label = "LatchLever"
    return obj


def build_latch_levers(doc):
    """LatchLevers: built in print pose (P0 -> P1 along +u, the outer face
    on the bed at z = P0.z + lobe_r = latch_top): two plates
    (lever_in..lever_out) of a lobe at P0 and a body to the handle end, the
    handle bar across the full width over the last lobe_r before the handle
    axis (lever_len from P0) and beyond, the end a straight cut end_slant
    off square with the outer side (+z here, the bed) longest, a ledge for
    the finger; the D-axle at P0 (flat
    on the bed side, +z), teardrop holes at P1 (point -z). Then swung into
    the closed pose about P0 by its Placement: a turn of -lever_print_angle
    in (u, z) = +lever_print_angle about +X (u runs toward -Y; verified: the
    handle hangs down, lowest Z = split_z + lever_low):
    p -> R p + (A - R A), R (0, y, z) = (0, y cos - z sin, y sin + z cos)."""
    u0, z0 = P0
    r, hw = "Internal.lobe_r", "Internal.lever_out"
    tip = f"({u0} + Internal.lever_len + {r})"
    block = _box(doc, "LeverBlock", u0, tip, f"{z0} - {r}", f"{z0} + {r}", hw)
    # the end: through the outer tip (tip, z0 + r), direction 90 deg -
    # end_slant (from the wall side up and out to it): keep the left (toward the lever)
    slant = _half(doc, "LeverEnd", tip, f"{z0} + {r}", "90 deg - Internal.end_slant", f"{hw} + Internal.overlap")
    lobe = _cylinder(doc, "LeverLobe", u0, z0, r, hw)
    profile = fuse(doc, "LeverProfile", [common(doc, "LeverBody", block, slant), lobe])
    gap = _box(doc, "LeverGap", f"{u0} - {r} - Internal.overlap", f"{u0} + Internal.lever_len - {r}",
               f"{z0} - {r} - Internal.overlap", f"{z0} + {r} + Internal.overlap", "Internal.lever_in")
    plates = cut(doc, "LeverPlates", profile, gap)
    solid = fuse(doc, "LeverSolid", [plates, _axle_up(doc, "LeverAxle", u0, z0, hw)])
    holes = _teardrop(doc, "LeverHoles", f"{u0} + Internal.pivot_dist", z0, f"{hw} + Internal.overlap")
    unit = cut(doc, "LatchLeverBare", solid, holes)
    unit.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 0)
    unit.setExpression(".Placement.Rotation.Angle", "Internal.lever_print_angle")
    a = "Internal.lever_print_angle"
    ya, za = Y(u0), Z(z0)
    place(unit, "0 mm",
          f"{ya} - ({ya} * cos({a}) - {za} * sin({a}))",
          f"{za} - ({ya} * sin({a}) + {za} * cos({a}))")
    return _per_lock(doc, _finish_lever(doc, unit), "LatchLevers")


# The bowed bar's stations: (x / hook_in) for a ruled loft, as in the
# mockup: 17 stations over the arms' gap with the bow factor
# 1 - (x / hook_in)^2, plus a straight section `overlap` into each arm.
_STATIONS = [i / 8 - 1 for i in range(17)]


def _bar_sections(doc, label):
    """The bar's circle and rectangle sections (x = const planes) along the
    bow: center BAR - bow(x) * (cos, sin)(hook_angle)."""
    xs = ["-(Internal.hook_in + Internal.overlap)"] + [f"Internal.hook_in * {s:g}" for s in _STATIONS] + \
         ["Internal.hook_in + Internal.overlap"]
    bows = ["0 mm"] + [f"Internal.bar_bow * {1 - s * s:g}" for s in _STATIONS] + ["0 mm"]
    circles, rects = [], []
    for i, (x, bow) in enumerate(zip(xs, bows)):
        u = f"({BAR[0]} - ({bow}) * cos(Internal.hook_angle))"
        z = f"({BAR[1]} - ({bow}) * sin(Internal.hook_angle))"
        circle = primitive(doc, "Part::Circle", f"{label}Circle{i}", {"Radius": "Internal.bar_r"}, ALONG_X)
        place(circle, f"{C} + ({x})", Y(u), Z(z))
        rect = Draft.make_rectangle(1, 1, face=False)
        rect.Label = f"{label}Rect{i}"
        # local X -> model +Y, local Y -> model +Z (normal along X)
        rect.Placement.Rotation = App.Rotation(App.Vector(1, 1, 1), 120)
        _bind(rect, {"Length": "2 * Internal.bar_r", "Height": "Internal.bar_r"})
        place(rect, f"{C} + ({x})", Y(f"{u} + Internal.bar_r"), Z(z))
        hide(circle, rect)
        circles.append(circle)
        rects.append(rect)
    return circles, rects


def _bowed_bar(doc):
    """The hook's bar between the arms: round underside (circle loft) and
    square top (rectangle loft), bowed bar_bow toward P1 at the center."""
    circles, rects = _bar_sections(doc, "HookBar")
    bar = fuse(doc, "HookBar", [ruled_loft(doc, "HookBarRound", circles),
                                ruled_loft(doc, "HookBarTop", rects)])
    # Not refined: refining merges the faces that meet tangentially at the
    # bar's equator into a shape that passes check(True) but breaks later
    # booleans (bar & lip came out empty, bar - mockup larger than the bar).
    bar.Refine = False
    return bar


def _hook_web(doc, hw):
    """The quadrilateral T0- -> T0+ -> Q -> T1- (counterclockwise in u-z),
    the part of the arm's hull between the lobe and the bar: one half-space
    per edge, each keeping the left of the edge's direction."""
    pts = [("Internal.hook_t0m_u", "Internal.hook_t0m_z"), ("Internal.hook_t0p_u", "Internal.hook_t0p_z"),
           ("Internal.hook_q_u", "Internal.hook_q_z"), ("Internal.hook_t1m_u", "Internal.hook_t1m_z")]
    names = ("Back", "Outer", "Front", "Wall")
    sides = []
    for k, name in enumerate(names):
        (ua, za), (ub, zb) = pts[k], pts[(k + 1) % 4]
        sides.append(_half(doc, f"HookWeb{name}", ua, za, f"atan2(({zb}) - ({za}); ({ub}) - ({ua}))", hw))
    web = sides[0]
    for k, side in enumerate(sides[1:], 1):
        web = common(doc, f"HookWeb{k}", web, side)
    return web


def build_latch_hooks(doc):
    """LatchHooks: closed pose. Two arms (hook_in..latch_w / 2) of the hull
    of the lobe at P1 and the bar section at BAR (lobe + bar section + web),
    the bowed bar between them, and the D-axle at P1 through the lever's
    holes with its flat toward hook_nr (the edge that lies on the print bed)."""
    hw, r0, rb = "Internal.latch_w / 2", "Internal.lobe_r", "Internal.bar_r"
    lobe = _cylinder(doc, "HookLobe", *P1, r0, hw)
    bar_round = _cylinder(doc, "HookBarSectionRound", *BAR, rb, hw)
    bar_top = _box(doc, "HookBarSectionTop", f"{BAR[0]} - {rb}", f"{BAR[0]} + {rb}", BAR[1], f"{BAR[1]} + {rb}", hw)
    # the web is hw wide like the lobe and the bar section (not hw + overlap,
    # which stuck 0.5 out past the arms)
    profile = fuse(doc, "HookProfile", [lobe, bar_round, bar_top, _hook_web(doc, hw)])
    middle = _box(doc, "HookGap", f"{P1[0]} - {LOCK_HALF}", f"{P1[0]} + {LOCK_HALF}",
                  f"{P1[1]} - {LOCK_HALF}", f"{P1[1]} + {LOCK_HALF}", "Internal.hook_in")
    arms = cut(doc, "HookArms", profile, middle)
    axle_round = _cylinder(doc, "HookAxleRound", *P1, "Internal.axle_r", hw)
    flat = _half(doc, "HookAxleFlat",
                 f"{P1[0]} + Internal.axle_flat * cos(Internal.hook_nr)",
                 f"{P1[1]} + Internal.axle_flat * sin(Internal.hook_nr)",
                 "Internal.hook_nr + 90 deg", f"{hw} + Internal.overlap")
    axle = common(doc, "HookAxle", axle_round, flat)
    unit = fuse(doc, "LatchHook", [arms, _bowed_bar(doc), axle])
    unit.Refine = False  # as for HookBar: refined, hook & lip came out empty
    return _per_lock(doc, unit, "LatchHooks")
