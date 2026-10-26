"""Builders for parametric Part objects whose dimensions are FreeCAD
expressions: strings referring to the Params sheet, e.g. "Internal.grid_w / 2".

Robustness rules (see the spec): only primitives, ruled lofts of rounded
rectangles, arrays and booleans; nothing refers to a face or edge by index.
"""
import Draft
import FreeCAD as App


class BuildError(RuntimeError):
    """A feature failed to recompute or gave an unusable shape."""


# Center of the first (-X, -Y) grid cell.
FIRST_CELL_X = "-Internal.grid_w / 2 + Internal.gf_pitch / 2"
FIRST_CELL_Y = "-Internal.grid_d / 2 + Internal.gf_pitch / 2"


def get(doc, label):
    """The one object with this label. (Draft objects can't be given a
    Name, so the generator identifies every object by Label.)"""
    found = doc.getObjectsByLabel(label)
    if len(found) != 1:
        raise KeyError(f"expected one object labelled {label!r}, found {len(found)}")
    return found[0]


def _bind(obj, exprs):
    for prop, expr in exprs.items():
        obj.setExpression(prop, expr)


def hide(*objs):
    for obj in objs:
        obj.Visibility = False


def place(obj, x, y, z):
    """Bind obj's placement position to the expressions x, y, z."""
    _bind(obj, {".Placement.Base.x": x, ".Placement.Base.y": y, ".Placement.Base.z": z})


def box(doc, label, size_x, size_y, z0, height):
    """Part::Box centered in XY, from z0 up by height."""
    b = doc.addObject("Part::Box", label)
    b.Label = label
    _bind(b, {
        "Length": size_x,
        "Width": size_y,
        "Height": height,
        ".Placement.Base.x": f"-({size_x}) / 2",
        ".Placement.Base.y": f"-({size_y}) / 2",
        ".Placement.Base.z": z0,
    })
    return b


def rounded_rect(doc, label, size_x, size_y, radius, cx, cy, z):
    """Closed rounded-rectangle wire (Draft Rectangle) of `size_x` by `size_y`
    and corner `radius`, centered on (cx, cy) at height z. Hidden: it is a
    loft section."""
    r = Draft.make_rectangle(1, 1, face=False)
    r.Label = label
    _bind(r, {
        "Length": size_x,
        "Height": size_y,
        "FilletRadius": radius,
        ".Placement.Base.x": f"({cx}) - ({size_x}) / 2",
        ".Placement.Base.y": f"({cy}) - ({size_y}) / 2",
        ".Placement.Base.z": z,
    })
    hide(r)
    return r


def ruled_loft(doc, label, sections):
    """Solid, ruled Part::Loft through the given section objects."""
    loft = doc.addObject("Part::Loft", label)
    loft.Label = label
    loft.Sections = sections
    loft.Solid = True
    loft.Ruled = True
    return loft


def profile_loft(doc, label, size, radius, cx, cy, levels):
    """Ruled loft through rounded squares centered on (cx, cy).

    levels: [(z, inset), ...] bottom-up. Each section is the reference
    square (side `size`, corner `radius`) inset by `inset` on every side,
    corner radius reduced by the same amount -- so a level pair whose
    inset differs by its height difference is a 45 degree chamfer.
    """
    sections = [
        rounded_rect(doc, f"{label}_s{i}", f"({size}) - 2 * ({inset})",
                     f"({size}) - 2 * ({inset})", f"({radius}) - ({inset})", cx, cy, z)
        for i, (z, inset) in enumerate(levels)
    ]
    return ruled_loft(doc, label, sections)


def offset_loft(doc, label, levels):
    """Ruled loft through outlines of the cavity rectangle offset outward.

    levels: [(z, t), ...] bottom-up. Each section is the cavity rectangle
    (grid_w by grid_d) offset outward by `t`, with corner radius `t`
    (concentric with the cavity corner), centered on the origin.
    """
    sections = [
        rounded_rect(doc, f"{label}_s{i}", f"Internal.grid_w + 2 * ({t})",
                     f"Internal.grid_d + 2 * ({t})", t, "0 mm", "0 mm", z)
        for i, (z, t) in enumerate(levels)
    ]
    return ruled_loft(doc, label, sections)


def offset_prism(doc, label, t, z0, height):
    """Prism of the cavity rectangle offset outward by `t` (see offset_loft),
    from z0 up by height."""
    return offset_loft(doc, label, [(z0, t), (f"({z0}) + ({height})", t)])


def cell_array(doc, label, base):
    """base repeated gf_x by gf_y at gf_pitch, as a compound (not fused).
    base must sit in the first cell (see FIRST_CELL_X/Y)."""
    arr = Draft.make_ortho_array(base, App.Vector(1, 0, 0), App.Vector(0, 1, 0),
                                 App.Vector(0, 0, 1), 1, 1, 1, use_link=False)
    arr.Label = label
    arr.Fuse = False
    _bind(arr, {
        "NumberX": "Params.gf_x",
        "NumberY": "Params.gf_y",
        ".IntervalX.x": "Internal.gf_pitch",
        ".IntervalY.y": "Internal.gf_pitch",
    })
    hide(base)
    return arr


def _boolean(doc, type_id, label, **links):
    obj = doc.addObject(type_id, label)
    obj.Label = label
    for prop, value in links.items():
        setattr(obj, prop, value)
    obj.Refine = True
    return obj


def fuse(doc, label, objs):
    obj = _boolean(doc, "Part::MultiFuse", label, Shapes=list(objs))
    hide(*objs)
    return obj


def cut(doc, label, base, tool):
    obj = _boolean(doc, "Part::Cut", label, Base=base, Tool=tool)
    hide(base, tool)
    return obj


def common(doc, label, base, tool):
    obj = _boolean(doc, "Part::Common", label, Base=base, Tool=tool)
    hide(base, tool)
    return obj


def primitive(doc, type_id, label, exprs, rotation=None):
    """A Part primitive with its properties bound to expressions."""
    obj = doc.addObject(type_id, label)
    obj.Label = label
    _bind(obj, exprs)
    if rotation is not None:
        obj.Placement.Rotation = rotation
    return obj


def per_count(doc, unit, label, count, pitch):
    """unit (built at the first position) repeated along X `count` times at
    `pitch` (both expressions), as a compound (not fused)."""
    array = Draft.make_ortho_array(unit, App.Vector(1, 0, 0), App.Vector(0, 1, 0),
                                   App.Vector(0, 0, 1), 1, 1, 1, use_link=False)
    array.Label = label
    array.Fuse = False
    _bind(array, {"NumberX": count, ".IntervalX.x": pitch})
    hide(unit)
    return array


def half_space(doc, label, x0, length, py, pz, direction, half):
    """Half-space: a big box along X from x0 over `length`, bounded by the
    line through (py, pz) in the YZ plane whose direction makes the angle
    `direction` with +Y (counterclockwise toward +Z). It keeps the side left
    of that direction: the box's local +Y runs along the line, local +Z into
    the kept side. `half` sizes the box (larger than the part). Angles past
    180 deg work: FreeCAD keeps the +X axis rather than flipping it."""
    hs = primitive(doc, "Part::Box", label, {
        "Length": length,
        "Width": f"2 * {half}",
        "Height": half,
    })
    hs.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 0)
    hs.setExpression(".Placement.Rotation.Angle", direction)
    place(hs, x0, f"({py}) - {half} * cos({direction})", f"({pz}) - {half} * sin({direction})")
    return hs
