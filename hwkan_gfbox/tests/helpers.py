"""Shared helpers for geometry tests."""
import FreeCAD as App

from hwkan_gfbox.build import build
from hwkan_gfbox.shapes import get
from hwkan_gfbox.sheet import value

_cache = {}


def built(*overrides):
    """The document built with these (name, value) overrides, cached."""
    if overrides not in _cache:
        _cache[overrides] = build(list(overrides), doc_name="test")[0]
    return _cache[overrides]


def v(doc, name):
    return value(doc.getObject("Params"), name)


def inside(doc, label, x, y, z):
    """True if (x, y, z) is inside the solid labelled `label`."""
    return get(doc, label).Shape.isInside(App.Vector(x, y, z), 1e-6, True)


def is_sound(shape):
    """Valid by both FreeCAD's quick check and the thorough BOP check
    (which also catches self-intersections that isValid() misses)."""
    if shape.isNull() or not shape.isValid():
        return False
    try:
        shape.check(True)
    except Exception:
        return False
    return True


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


def first_cell(doc):
    """Center (x, y) of the first (-X, -Y) cell."""
    c = v(doc, "bin_clearance") + v(doc, "gf_pitch") / 2
    return -v(doc, "grid_w") / 2 + c, -v(doc, "grid_d") / 2 + c


def cell_centers(doc):
    cx, cy = first_cell(doc)
    p = v(doc, "gf_pitch")
    return [(cx + i * p, cy + j * p)
            for i in range(int(v(doc, "gf_x"))) for j in range(int(v(doc, "gf_y")))]
