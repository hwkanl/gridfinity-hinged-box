"""Cosmetics: fillets and chamfers on the finished parts, applied last.
Spec: docs/superpowers/specs/2026-10-04-cosmetics-design.md.

Part::Fillet / Part::Chamfer keep their edges as numbers and their sizes
as plain values, so the edges are chosen here, by position, from the
sheet's values at build time: after a Params change the model is rebuilt,
not recomputed. Each chain starts at the part's bare object
(<Part>Bare) and its last object is labelled <Part>Finished; the stacking
features (parts/stacking.py) then make the part itself.
"""
import Part

from hwkan_gfbox.parts.hinge import rib_out_y
from hwkan_gfbox.shapes import BuildError, hide
from hwkan_gfbox.sheet import SHEET_NAME, value

EPS = 1e-4  # mm: edge positions are computed from the same values the model uses


def vertical_at(points):
    """Select vertical straight edges through any of the (x, y) points."""
    def select(e):
        bb = e.BoundBox
        return (isinstance(e.Curve, Part.Line) and bb.XLength < EPS and bb.YLength < EPS
                and any(abs(bb.XMin - x) < EPS and abs(bb.YMin - y) < EPS for x, y in points))
    return select


def along_x_at(points):
    """Select straight edges along X through any of the (y, z) points."""
    def select(e):
        bb = e.BoundBox
        return (isinstance(e.Curve, Part.Line) and bb.YLength < EPS and bb.ZLength < EPS
                and any(abs(bb.YMin - y) < EPS and abs(bb.ZMin - z) < EPS for y, z in points))
    return select


def slanted_at(xs, y0, z0):
    """Select straight edges in a plane X = x (any of xs) along the 45 deg
    line through (y0, z0), rising outward (Y - y0 = Z - z0)."""
    def select(e):
        bb = e.BoundBox
        return (isinstance(e.Curve, Part.Line) and bb.XLength < EPS and bb.YLength > EPS
                and any(abs(bb.XMin - x) < EPS for x in xs)
                and all(abs((p.Point.y - y0) - (p.Point.z - z0)) < EPS for p in e.Vertexes))
    return select


def any_of(*selects):
    """Select edges any of the predicates selects."""
    return lambda e: any(select(e) for select in selects)


def in_plane_z(z, y_max=float("inf")):
    """Select edges lying in the plane Z = z, not reaching past Y = y_max."""
    def select(e):
        bb = e.BoundBox
        return abs(bb.ZMin - z) < EPS and abs(bb.ZMax - z) < EPS and bb.YMax <= y_max + EPS
    return select


def apply(doc, kind, label, base, param, select, expected=None):
    """A Part::<kind> ("Fillet" or "Chamfer") of size `param` on the edges
    of base for which select(edge) holds; base itself if the size is 0.
    Raises BuildError if no edges (or not `expected` edges) are found or
    the result is not one sound solid."""
    size = value(doc.getObject(SHEET_NAME), param)
    if size == 0:
        return base
    doc.recompute()
    edges = [i + 1 for i, e in enumerate(base.Shape.Edges) if select(e)]
    if not edges or (expected is not None and len(edges) != expected):
        raise BuildError(f"{param}: found {len(edges)} edges on {base.Label}"
                         + (f", expected {expected}" if expected is not None else ""))
    obj = doc.addObject(f"Part::{kind}", label)
    obj.Label = label  # addObject may suffix the Name if it exists; get() needs the exact Label
    obj.Base = base
    obj.Edges = [(i, size, size) for i in edges]
    hide(base)
    doc.recompute()
    sound = obj.isValid() and not obj.Shape.isNull() and len(obj.Shape.Solids) == 1
    why = ""
    if sound:
        try:
            obj.Shape.check(True)
        except Exception as e:
            sound, why = False, f" ({str(e).splitlines()[0] if str(e) else 'check failed'})"
    if not sound:
        raise BuildError(f"{param} = {size:g} mm: the {kind.lower()} on {base.Label} "
                         f"is not one sound solid{why}; try a smaller value")
    return obj


def _finish(obj, label):
    obj.Label = label  # addObject may suffix the Name if it exists; get() needs the exact Label
    return obj


def finish_bottom(doc, bare):
    """Bottom: R rib_root_fillet in the inside corners of the hinge ribs
    (their vertical corners and where their 45 deg underside meets the
    wall), bottom_chamfer on every edge at Z = 0, then R rib_fillet on the
    ribs' outer corners (their vertical corners, the knee at rib_full and
    the underside's two slanted edges). The outer fillet comes after the
    chamfer: a chamfer wider than the radius of an arc it follows
    self-intersects (it no longer meets the ribs, but stays in that order)."""
    sheet = doc.getObject(SHEET_NAME)

    def v(name):
        return value(sheet, name)

    n = int(v("hinge_count"))
    sides = [v("hinge_c0") + k * v("hinge_pitch") + d * v("hinge_rib_w") / 2
             for k in range(n) for d in (-1, 1)]
    wall_y = v("outer_d") / 2
    rib_y, full = rib_out_y(doc), v("rib_full")
    foot = full - v("rib_depth")  # where the 45 deg underside meets the wall
    obj = apply(doc, "Fillet", "BottomRibRootFillet", bare, "rib_root_fillet",
                any_of(vertical_at([(x, wall_y) for x in sides]), along_x_at([(wall_y, foot)])), 3 * n)
    obj = apply(doc, "Chamfer", "BottomChamfer", obj, "bottom_chamfer", in_plane_z(0))
    obj = apply(doc, "Fillet", "BottomRibFillet", obj, "rib_fillet",
                any_of(vertical_at([(x, rib_y) for x in sides]), along_x_at([(rib_y, full)]),
                       slanted_at(sides, wall_y, foot)), 5 * n)
    return _finish(obj, "BottomFinished")


def finish_lid(doc, bare):
    """Lid: lid_chamfer on its top outline (edges in Z = box_h within the
    rim's Y extent: the knuckle tops reach past it and stay sharp), then
    lip_chamfer on each lock lip's lower front edge."""
    sheet = doc.getObject(SHEET_NAME)

    def v(name):
        return value(sheet, name)

    obj = apply(doc, "Chamfer", "LidTopChamfer", bare, "lid_chamfer",
                in_plane_z(v("box_h"), y_max=v("rim_d") / 2))
    lip_y = -(v("rim_d") / 2 + v("lock_lip_e"))
    obj = apply(doc, "Chamfer", "LidLipChamfer", obj, "lip_chamfer",
                along_x_at([(lip_y, v("split_z"))]), int(v("lock_count")))
    return _finish(obj, "LidFinished")
