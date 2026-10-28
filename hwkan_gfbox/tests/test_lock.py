"""Lock: lip (lid), pad and slot (bottom), latch (base, lever, hook).
Spec: docs/superpowers/specs/2026-10-02-lock-design.md."""
import math
import os
import runpy

import FreeCAD as App
import Part

from hwkan_gfbox.build import DOC_NAME, ROOT, build
from hwkan_gfbox.parts import lock
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import value
from hwkan_gfbox.tests.helpers import built, is_sound, near, v
from hwkan_gfbox.tests.test_hinge import _sheet
from hwkan_gfbox.verify import gap, latch_fit_checks


def test_lock_derived_defaults():
    s = _sheet(("latch_clearance", "0.2"), ("lock_detent", "0.35"))  # the values these were worked out for
    for name, want, tol in (
            ("latch_base_hw", 4.6, 1e-9), ("lever_in", 4.8, 1e-9), ("lever_out", 7.647521, 1e-6),
            ("hook_in", 7.847521, 1e-6), ("latch_w", 20.695042, 1e-6), ("pad_front", 2, 1e-9), ("lock_slot_w", 9.430940, 1e-6),
            ("lock_slot_base_w", 12.895042, 1e-6), ("pad_hw", 7.647521, 1e-6),
            ("lock_slot_top", -1.9, 1e-9), ("lock_w", 20.695042, 1e-6), ("lock_pitch", 64, 1e-9),
            ("lock_c0", -32, 1e-9), ("lock_p0_u", 5.2, 1e-9), ("lock_p0_z", -5, 1e-9),
            ("lock_p1_angle", -82.368676, 1e-5), ("lock_p1_u", 5.996790, 1e-6),
            ("lock_p1_z", -10.946859, 1e-6), ("hook_angle", 106.107484, 1e-5),
            ("bar_h_u", 1.555488, 1e-6), ("bar_h_z", 4.432851, 1e-6), ("hook_l", 16.008143, 1e-6),
            ("hook_nl", 189.831403, 1e-5), ("hook_q_u", 2.805488, 1e-6), ("hook_q_z", 5.682851, 1e-6),
            ("hook_nr", 21.068003, 1e-5), ("hook_t0p_u", 8.796253, 1e-6), ("hook_t0p_z", -9.868431, 1e-6),
            ("hook_t0m_u", 3.040846, 1e-6), ("hook_t0m_z", -11.459107, 1e-6),
            ("hook_t1m_u", 0.323845, 1e-6), ("hook_t1m_z", 4.219414, 1e-6),
            ("lever_print_angle", 82.368676, 1e-5), ("hook_print_angle", 68.931997, 1e-5),
            ("lever_low", -22.442181, 1e-6), ("lock_hole_trunc", 2.3, 1e-9)):
        assert near(value(s, name), want, tol), (name, value(s, name))


def _check_invariants(s):
    g = lambda n: value(s, n)
    pt = lambda n: (g(n + "_u"), g(n + "_z"))
    P0, P1, BAR = (g("lock_p0_u"), g("lock_p0_z")), (g("lock_p1_u"), g("lock_p1_z")), (g("bar_h_u"), g("bar_h_z"))
    Q, T0p, T0m, T1m = pt("hook_q"), pt("hook_t0p"), pt("hook_t0m"), pt("hook_t1m")
    K = (g("lock_k_u"), g("lock_k_z"))
    d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    dot = lambda a, b, ang: ((b[0] - a[0]) * math.cos(math.radians(ang))
                             + (b[1] - a[1]) * math.sin(math.radians(ang)))
    assert near(d(P1, P0), g("pivot_dist"), 1e-9)
    assert near(d(T0m, P1), g("lobe_r"), 1e-9)
    assert near(d(T1m, BAR), g("bar_r"), 1e-9)
    assert near(d(T0p, P1), g("lobe_r"), 1e-9)
    assert abs(dot(T0m, T1m, g("hook_nl"))) < 1e-9
    assert abs(dot(T0p, Q, g("hook_nr"))) < 1e-9
    # over center: P1 on the -u side of the line K -> P0
    cross = (P0[0] - K[0]) * (P1[1] - K[1]) - (P0[1] - K[1]) * (P1[0] - K[0])
    assert cross < 0, cross  # K -> P0 points down: its left (cross > 0) is +u, so the wall side is cross < 0
    assert near(d(BAR, (g("lock_k_u"), g("lock_bar_c_z"))), g("hook_preload"), 1e-9)


def test_lock_geometry_invariants():
    _check_invariants(_sheet())
    _check_invariants(_sheet(("lobe_r", "3.5"), ("bar_r", "1.0"), ("pivot_dist", "7")))


def lock_centers(doc):
    return [v(doc, "lock_c0") + k * v(doc, "lock_pitch") for k in range(int(v(doc, "lock_count")))]


def uz(doc, x, u, z):
    """Model point of profile point (u, z) at x."""
    return lock.point(doc, u, z, x)


def in_part(doc, label, x, u, z):
    return get(doc, label).Shape.isInside(uz(doc, x, u, z), 1e-6, True)


def _check_lip_and_pad(doc):
    lh, e = v(doc, "lid_h"), v(doc, "lock_lip_e")
    for c in lock_centers(doc):
        # lip: solid in front of the lid face, nothing beside the lip
        assert in_part(doc, "Lid", c, 0.3, lh / 4) and in_part(doc, "Lid", c, e - 0.1, lh / 4)
        assert not in_part(doc, "Lid", c, e + 0.1, lh / 4)
        assert not in_part(doc, "Lid", c + v(doc, "lock_lip_w") / 2 + 0.1, 0.3, lh / 4)
        # seat: its floor runs back to the lid face; its curve (radius
        # lock_seat_r around the seat center) on the outer side below the center
        su, sz, sr, top = (v(doc, n) for n in ("lock_seat_u", "lock_seat_z", "lock_seat_r", "lock_stop_top"))
        floor = sz - sr
        assert not in_part(doc, "Lid", c, 0.1, floor + 0.1) and in_part(doc, "Lid", c, 0.1, floor - 0.1)
        assert not in_part(doc, "Lid", c, su, floor + 0.1) and in_part(doc, "Lid", c, su, floor - 0.1)
        s45 = math.sqrt(0.5)
        assert not in_part(doc, "Lid", c, su + (sr - 0.1) * s45, sz - (sr - 0.1) * s45)
        assert in_part(doc, "Lid", c, su + (sr + 0.1) * s45, sz - (sr + 0.1) * s45)
        # stop: from the seat's opening (straight up above the seat center) to the front edge, lock_stop_top tall
        assert not in_part(doc, "Lid", c, su + sr - 0.1, top - 0.1) and in_part(doc, "Lid", c, su + sr + 0.1, top - 0.1)
        assert in_part(doc, "Lid", c, e - 0.1, top - 0.1) and not in_part(doc, "Lid", c, e - 0.1, top + 0.1)
        # pad: solid beside the slot, open in the slot, closed above the slot's roof
        pf, pt, pb, hw = v(doc, "pad_front"), v(doc, "pad_top"), v(doc, "pad_bot"), v(doc, "pad_hw")
        st, sw = v(doc, "lock_slot_top"), v(doc, "lock_slot_w")
        assert in_part(doc, "Bottom", c + hw - 0.3, pf - 0.1, pb + 0.1)
        assert not in_part(doc, "Bottom", c + hw + 0.1, pf - 0.1, pb + 0.1)
        assert not in_part(doc, "Bottom", c, pf - 0.1, pb + 0.1)          # slot open
        assert not in_part(doc, "Bottom", c, pf - 0.1, st - 0.05)
        assert in_part(doc, "Bottom", c, pf - 0.1, st + 0.05)             # roof
        assert in_part(doc, "Bottom", c, pf - 0.1, pt - 0.05)
        assert not in_part(doc, "Bottom", c, pf - 0.1, pt + 0.05)        # pad top (no band in front of the rim face)
        assert not in_part(doc, "Bottom", c + hw - 0.3, pf + 0.1, pb + 1)  # front face
        # the slot's narrow width at the front face
        assert not in_part(doc, "Bottom", c + sw / 2 - 0.1, pf - 0.01, pb + 1)
        assert in_part(doc, "Bottom", c + sw / 2 + 0.1, pf - 0.01, pb + 1)
        # the 45 deg underside: solid just above it, open just below it (beside the slot)
        assert in_part(doc, "Bottom", c + hw - 0.3, pf - 1, pb - 1 + 0.1)
        assert not in_part(doc, "Bottom", c + hw - 0.3, pf - 1, pb - 1 - 0.1)
        # slot open at the bottom: inside the slot, just above the underside,
        # across the slot's depth; solid there beside the slot
        for u in (v(doc, "slot_in_u") + 0.05, pf - 0.1):
            z = pb - (pf - u) + 0.05
            assert not in_part(doc, "Bottom", c, u, z), (c, u, z)
            assert in_part(doc, "Bottom", c + hw - 0.3, u, z), (c, u, z)


def test_lip_pad_and_slot():
    doc = built()
    for label in ("LockLips", "LockPads", "LockSlots"):
        assert len(get(doc, label).Shape.Solids) == int(v(doc, "lock_count")), label
    for label in ("Lid", "Bottom"):
        shape = get(doc, label).Shape
        assert is_sound(shape) and len(shape.Solids) == 1, label
    _check_lip_and_pad(doc)


def test_lip_pad_and_slot_other_counts_and_sizes():
    for overrides in ([("lock_count", "1")], [("hinge_count", "3"), ("lock_count", "3")],
                      [("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3")]):
        doc = built(*overrides)
        for label in ("Lid", "Bottom"):
            shape = get(doc, label).Shape
            assert is_sound(shape) and len(shape.Solids) == 1, (overrides, label)
        _check_lip_and_pad(doc)


def _first(doc, label):
    return get(doc, label).Shape


def lever_uz(doc, du, dz):
    """Closed-pose (u, z) of the lever point (du, dz) from P0 in its print
    frame (P0 -> P1 along +u): turned by lock_p1_angle about P0."""
    t = math.radians(v(doc, "lock_p1_angle"))
    return (v(doc, "lock_p0_u") + du * math.cos(t) - dz * math.sin(t),
            v(doc, "lock_p0_z") + du * math.sin(t) + dz * math.cos(t))


def test_base_and_lever():
    doc = built()
    lc, dc = v(doc, "latch_clearance"), v(doc, "lock_dovetail_clearance")
    for label in ("LatchBases", "LatchLevers"):
        solids = get(doc, label).Shape.Solids
        assert len(solids) == int(v(doc, "lock_count")) and all(is_sound(s) for s in solids), label
    # the lever as designed, before its end fillets (test_cosmetics checks those)
    base, lever = _first(doc, "LatchBase"), _first(doc, "LatchLeverBare")
    assert is_sound(base) and is_sound(lever)
    bottom, lid = get(doc, "Bottom").Shape, get(doc, "Lid").Shape
    assert base.common(bottom).Volume < 1e-6 and gap(base, bottom) >= dc - 1e-3, gap(base, bottom)
    assert lever.common(base).Volume < 1e-6 and gap(lever, base) >= lc - 1e-3, gap(lever, base)
    assert gap(lever, bottom) >= lc - 1e-3 and gap(lever, lid) >= lc - 1e-3
    c = v(doc, "lock_c0")
    p0u, p0z, r = v(doc, "lock_p0_u"), v(doc, "lock_p0_z"), v(doc, "lobe_r")
    # base: tongue in the slot, body around P0, hole at P0 (its point down)
    assert base.isInside(uz(doc, c, v(doc, "pad_front") - 0.2, v(doc, "pad_bot") + 1), 1e-6, True)
    assert base.isInside(uz(doc, c, p0u, p0z + r - 0.1), 1e-6, True)
    hr = v(doc, "axle_r") + lc
    assert not base.isInside(uz(doc, c, p0u, p0z), 1e-6, True)
    assert not base.isInside(uz(doc, c, p0u, p0z - hr - 0.2), 1e-6, True)   # teardrop point
    assert base.isInside(uz(doc, c, p0u, p0z + hr + 0.2), 1e-6, True)
    assert base.isInside(uz(doc, c, p0u, p0z - v(doc, "lock_hole_trunc") - 0.1), 1e-6, True)
    # lever: its axle at P0 (through the base's hole), plates beside the base
    assert lever.isInside(uz(doc, c, p0u, p0z), 1e-6, True)
    assert lever.isInside(uz(doc, c + v(doc, "lever_in") + 0.1, p0u, p0z + r - 0.1), 1e-6, True)
    assert not lever.isInside(uz(doc, c + v(doc, "lever_in") - 0.1, p0u, p0z + r - 0.1), 1e-6, True)
    li, lo, L = v(doc, "lever_in"), v(doc, "lever_out"), v(doc, "lever_len")
    lev = lambda x, du, dz: lever.isInside(uz(doc, x, *lever_uz(doc, du, dz)), 1e-6, True)
    # the axle's flat on the print bed's side (+z in the print frame)
    af = v(doc, "axle_flat")
    assert lev(c, 0, -af - 0.1) and not lev(c, 0, af + 0.1)
    # plates along the lever (clear of the holes at P1), open between them;
    # the handle bar across
    pd = v(doc, "pivot_dist")
    for du in (r, pd + hr + 0.5, L - r - 0.2):
        assert lev(c + (li + lo) / 2, du, 0) and lev(c - (li + lo) / 2, du, 0), du
        assert not lev(c, du, 0), du
    assert lev(c, L - r + 0.2, 0) and lev(c, L, 0)
    assert not lev(c + lo + 0.1, L, 0)
    # the slanted end: the outer side (+z, print frame) longest
    tip, slant = L + r, math.radians(v(doc, "end_slant"))
    assert lev(c, tip - 0.1, r - 0.1) and not lev(c, tip + 0.1, r - 0.1)
    wall_end = tip - (2 * r - 0.1) * math.tan(slant)
    assert lev(c, wall_end - 0.1, -r + 0.1) and not lev(c, wall_end + 0.1, -r + 0.1)
    # the holes at P1, teardrop point toward -z (print frame)
    assert not lev(c + (li + lo) / 2, pd, 0) and not lev(c + (li + lo) / 2, pd, -hr - 0.2)
    assert lev(c + (li + lo) / 2, pd, hr + 0.2)
    # ... its point cut off lock_hole_trunc from the axis
    tr = v(doc, "lock_hole_trunc")
    assert not lev(c + (li + lo) / 2, pd, -tr + 0.1) and lev(c + (li + lo) / 2, pd, -tr - 0.1)
    bb = lever.optimalBoundingBox()
    assert near(bb.ZMin, v(doc, "split_z") + v(doc, "lever_low"), 1e-3), (bb.ZMin, v(doc, "lever_low"))


def _check_latch(doc):
    """The closed latch: verify's checks (soundness, solid counts, gaps, the
    hook's bar pressing into the lip only)."""
    failed = [name for name, ok in latch_fit_checks(doc) if not ok]
    assert not failed, failed


def test_hook():
    doc = built()
    _check_latch(doc)
    hook = get(doc, "LatchHook").Shape
    assert is_sound(hook)
    c = v(doc, "lock_c0")
    # the axle at P1 runs through the lever's holes; the bar between the arms, bowed toward P1
    p1u, p1z = v(doc, "lock_p1_u"), v(doc, "lock_p1_z")
    assert hook.isInside(uz(doc, c, p1u, p1z), 1e-6, True)
    bu, bz, a = v(doc, "bar_h_u"), v(doc, "bar_h_z"), math.radians(v(doc, "hook_angle"))
    bow, rb = v(doc, "bar_bow"), v(doc, "bar_r")
    assert hook.isInside(uz(doc, c, bu - bow * math.cos(a), bz - bow * math.sin(a)), 1e-6, True)
    assert hook.isInside(uz(doc, c + v(doc, "hook_in") + 0.1, bu, bz), 1e-6, True)
    # the bow: at the center the round underside is moved toward P1
    du, dz = -math.cos(a), -math.sin(a)  # toward P1
    assert hook.isInside(uz(doc, c, bu + (rb + bow - 0.1) * du, bz + (rb + bow - 0.1) * dz), 1e-6, True)
    assert not hook.isInside(uz(doc, c, bu + (rb + bow + 0.1) * du, bz + (rb + bow + 0.1) * dz), 1e-6, True)
    # arms only beyond hook_in: open between them on the lobe and the web
    hi = v(doc, "hook_in")
    assert not hook.isInside(uz(doc, c, p1u, p1z + v(doc, "lobe_r") - 0.2), 1e-6, True)
    assert hook.isInside(uz(doc, c + hi + 0.1, p1u, p1z + v(doc, "lobe_r") - 0.2), 1e-6, True)
    assert not hook.isInside(uz(doc, c + v(doc, "latch_w") / 2 + 0.1, p1u, p1z + v(doc, "lobe_r") - 0.2),
                             1e-6, True)
    # the D-axle's flat faces hook_nr; round on the opposite side
    nr, af, ar = math.radians(v(doc, "hook_nr")), v(doc, "axle_flat"), v(doc, "axle_r")
    assert not hook.isInside(uz(doc, c, p1u + (af + 0.1) * math.cos(nr), p1z + (af + 0.1) * math.sin(nr)), 1e-6, True)
    assert hook.isInside(uz(doc, c, p1u - (ar - 0.1) * math.cos(nr), p1z - (ar - 0.1) * math.sin(nr)), 1e-6, True)


def test_latch_other_counts_and_sizes():
    # the same cached builds as test_lip_pad_and_slot_other_counts_and_sizes
    for overrides in ([("lock_count", "1")], [("hinge_count", "3"), ("lock_count", "3")],
                      [("gf_x", "2"), ("gf_y", "2"), ("gf_z_units", "3")]):
        _check_latch(built(*overrides))


MOCKUP = os.path.join(ROOT, "docs", "superpowers", "specs", "lock-options", "latch_mockup_alt2.py")


def _mockup_parts():
    """Run the mockup against a fresh default build named DOC_NAME (the
    mockup reads that document). Returns its namespace and the build."""
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc, _ = build()
    return runpy.run_path(MOCKUP, run_name="__main__"), doc


def _differences(a, b):
    """(a - b, b - a) volumes from the first boolean method whose results
    are consistent (both >= 0 and the same common volume either way). The
    mockup's 72-gons put vertices on our circles, and its bar's chords run
    within ~1 um of our bar's round faces (and its tangent seam at the
    equator); the exact booleans between such near-identical solids can
    fail (common larger than either solid) or, fuzzy, return null shapes.
    The fuzzy values are far below every check. A failure that comes out
    as 'disjoint' is still consistent and fails the volume check."""
    va, vb = a.Volume, b.Volume
    tried = []
    # exact first, then fuzzy: 1e-5 (worked at 20.0 mm width), 1e-6 (needed at 20.7), 1e-4 (coarsest) last
    for fuzz in (None, 1e-5, 1e-6, 1e-4):
        try:
            if fuzz is None:
                ab, ba, both = a.cut(b).Volume, b.cut(a).Volume, a.common(b).Volume
            else:
                ab, ba, both = a.cut(b, fuzz).Volume, b.cut(a, fuzz).Volume, a.common(b, fuzz).Volume
        except Exception as e:
            tried.append((fuzz, repr(e)))
            continue
        tried.append((fuzz, ab, ba, both))
        # the common, computed on its own, must agree with both differences
        # (so an empty, non-null result can't pass)
        if ab >= -1e-6 and ba >= -1e-6 and abs(both - (va - ab)) <= 1e-3 * vb \
                and abs(both - (vb - ba)) <= 1e-3 * vb:
            return ab, ba, fuzz
    raise AssertionError(("no consistent boolean", tried))


def _same(a, b, name):
    va, vb = a.Volume, b.Volume
    assert abs(va - vb) <= 0.005 * vb, (name, va, vb)
    ba, bb = a.optimalBoundingBox(), b.optimalBoundingBox()
    for k in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
        assert abs(getattr(ba, k) - getattr(bb, k)) <= 0.05, (name, k, getattr(ba, k), getattr(bb, k))
    ab, ba_, fuzz = _differences(a, b)
    assert ab <= 0.005 * vb and ba_ <= 0.005 * vb, (name, ab, ba_)
    print(f"  mockup {name}: volume {va:.3f} vs {vb:.3f}, differences {ab:.4f} / {ba_:.4f} (fuzzy {fuzz})")


def test_lock_matches_mockup():
    if not os.path.exists(MOCKUP):  # the mockup is not in the published addon
        print(f"skipped: no {MOCKUP}")
        return
    m, doc = _mockup_parts()
    try:
        c = v(doc, "lock_c0")
        shift = App.Vector(c, 0, 0)
        rd, sz = v(doc, "rim_d"), v(doc, "split_z")
        _same(get(doc, "LatchHook").Shape, m["hook"].translated(shift), "hook")
        # the base only in front of its dovetail key: the key was added after
        # the test prints (probes in test_dovetail_key)
        key_u = v(doc, "slot_in_u") + v(doc, "lock_dovetail_clearance") + v(doc, "lock_key_d")
        before_key = Part.makeBox(40, 40, 60, App.Vector(c - 20, -rd / 2 - key_u - 40, sz - 40))
        _same(get(doc, "LatchBase").Shape.common(before_key), m["base"].translated(shift).common(before_key), "base")
        # the lever only within lever_len of P0: its end's slant was flipped
        # after the test print (outer side longest; probes in test_base_and_lever),
        # and only within the mockup's plate width: the plates were widened
        # out to the hook arms (side play)
        hw = v(doc, "lever_in") + v(doc, "plate_t")
        p0 = App.Vector(c - hw, -rd / 2 - v(doc, "lock_p0_u"), sz + v(doc, "lock_p0_z"))
        near_p0 = Part.makeCylinder(v(doc, "lever_len"), 2 * hw, p0, App.Vector(1, 0, 0))
        _same(get(doc, "LatchLever").Shape.common(near_p0), m["lever"].translated(shift).common(near_p0), "lever")
        # lip and pad: the halves' material in front of the rim face at the first lock
        front = Part.makeBox(30, 20, 40, App.Vector(c - 15, -rd / 2 - 20, sz - 30))
        # the lip only out to the mockup's 3 mm and below the seat's floor: it
        # was lengthened, then given its seat and stop after test prints
        # (probes in _check_lip_and_pad)
        floor = v(doc, "lock_seat_z") - v(doc, "lock_seat_r")
        lip_front = Part.makeBox(30, 3, 30 + floor - 0.01, App.Vector(c - 15, -rd / 2 - 3, sz - 30))
        _same(get(doc, "Lid").Shape.common(lip_front), m["lip"].translated(shift).common(lip_front), "lip")
        _same(get(doc, "Bottom").Shape.common(front), m["pad"].translated(shift).common(front), "pad")
    finally:
        for name in list(App.listDocuments()):
            if name.startswith(("lock_mockup_alt2", "lock_print_alt2", DOC_NAME)):
                App.closeDocument(name)


def test_dovetail_key():
    """The base's dovetail has its full depth only in its lowest lock_key_h
    (the slot likewise, with a 45 deg flare above): upside down it won't
    go in."""
    doc = built()
    c, si, dc = v(doc, "lock_c0"), v(doc, "slot_in_u"), v(doc, "lock_dovetail_clearance")
    kh, kd, pb = v(doc, "lock_key_h"), v(doc, "lock_key_d"), v(doc, "pad_bot")
    base = get(doc, "LatchBase").Shape
    at = lambda u, z: lock.point(doc, u, z, c)
    # the base: full depth below the key, shallower above its flare
    assert base.isInside(at(si + dc + 0.1, pb + kh - 0.2), 1e-6, True)
    assert not base.isInside(at(si + dc + 0.1, pb + kh + kd + 0.2), 1e-6, True)
    assert base.isInside(at(si + dc + kd + 0.1, pb + kh + kd + 0.2), 1e-6, True)
    # the 45 deg flare: halfway out, open just above it, solid just below it
    assert not base.isInside(at(si + dc + kd / 2, pb + kh + kd / 2 + 0.1), 1e-6, True)
    assert base.isInside(at(si + dc + kd / 2, pb + kh + kd / 2 - 0.1), 1e-6, True)
    # the slot: open at full depth below its key, closed there above the flare
    assert not in_part(doc, "Bottom", c, si + 0.05, pb + kh - 0.2)
    assert in_part(doc, "Bottom", c, si + 0.05, pb + kh + dc + kd + 0.2)
    assert not in_part(doc, "Bottom", c, si + kd + 0.05, pb + kh + dc + kd + 0.2)
    # upside down (turned about the u axis at mid height), it can't be seated:
    # at its seated height it runs into the bottom part
    flipped = base.copy()
    flipped.rotate(at(si, (pb + v(doc, "latch_top")) / 2), App.Vector(0, 1, 0), 180)
    assert flipped.common(get(doc, "Bottom").Shape).Volume > 1, flipped.common(get(doc, "Bottom").Shape).Volume


def test_detent():
    """A nub on the slot's wide face just below the seated base: flat on
    top (the base can drop lock_dovetail_clearance onto it, no further), a
    lock_detent_ramp ramp underneath; only the base's full-depth part
    (below its key) runs into it on the way in."""
    doc = built()
    c, si, dc = v(doc, "lock_c0"), v(doc, "slot_in_u"), v(doc, "lock_dovetail_clearance")
    h, top, ramp = v(doc, "lock_nub_h"), v(doc, "lock_nub_top"), math.radians(v(doc, "lock_detent_ramp"))
    bot = top - h / math.tan(ramp)
    assert in_part(doc, "Bottom", c, si + 0.05, top - 0.05)
    assert in_part(doc, "Bottom", c, si + h - 0.02, top - 0.02)
    assert not in_part(doc, "Bottom", c, si + 0.05, top + 0.05)
    assert not in_part(doc, "Bottom", c, si + h + 0.05, top - 0.05)
    # the ramp: solid just above it, open just below it
    u = si + h / 2
    zr = bot + (u - si) / math.tan(ramp)
    assert in_part(doc, "Bottom", c, u, zr + 0.05)
    assert not in_part(doc, "Bottom", c, u, zr - 0.05)

    base, bottom = get(doc, "LatchBase").Shape, get(doc, "Bottom").Shape

    def dropped(d):
        moved = base.copy()
        moved.translate(App.Vector(0, 0, -d))
        return moved.common(bottom).Volume
    assert dropped(dc - 0.01) <= 1e-9
    assert dropped(dc + 0.05) > 1e-4
    # lower still, with the full-depth part below the nub, the shallow part passes it
    pb, kh, kd = v(doc, "pad_bot"), v(doc, "lock_key_h"), v(doc, "lock_key_d")
    assert dropped(pb + kh + kd - bot + 0.1) <= 1e-9
