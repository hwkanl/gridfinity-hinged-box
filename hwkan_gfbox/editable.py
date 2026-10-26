"""Edit box: the open box's print shapes (what goes into each STL) as
PartDesign Bodies with frozen copies as their Base Features, in their own
document, for the user's own features; and their export. The copies don't
follow rebuilds of the box."""
import json
import os

import FreeCAD as App
import MeshPart

from hwkan_gfbox import export
from hwkan_gfbox.build import check_recompute

DOC_NAME = "hwkan_gfbox_editable"
META_KEY = "hwkan_gfbox"  # Meta entry marking an edited box: the box's build_info as JSON
GAP = 10.0  # mm between the bodies along X


def frozen(shape, offset):
    """A copy of shape moved by offset, every move baked into the geometry
    (a Body's BaseFeature ignores the feature's Placement; CLAUDE.md)."""
    shape = shape.copy()
    move = App.Placement(offset, App.Rotation()).multiply(shape.Placement)
    shape.Placement = App.Placement()
    shape.transformShape(move.toMatrix(), True)
    return shape


def unsaved_edit_document():
    """The open edited box that was never saved (the one Edit box replaces), or None."""
    for doc in App.listDocuments().values():
        if is_edited(doc) and not doc.FileName:
            return doc
    return None


def make_editable(doc):
    """A new document DOC_NAME (App makes the name unique; an open edited
    box that was never saved is closed first, a saved one is left alone)
    with one PartDesign::Body per export.PARTS entry, labelled like its STL,
    side by side along X on the bed plane, marked with the box's build_info.
    Everything is computed before any document is touched. Returns it."""
    frozen_parts = []
    x = 0.0
    for part in export.PARTS:
        shape = export.print_shape(doc, part)
        bb = shape.optimalBoundingBox(False)
        frozen_parts.append((part, os.path.splitext(export.stl_name(doc, part))[0],
                             frozen(shape, App.Vector(x - bb.XMin, 0, 0))))
        x += bb.XLength + GAP
    info = json.dumps(export.build_info(doc))
    old = unsaved_edit_document()
    if old is not None:
        App.closeDocument(old.Name)
    out = App.newDocument(DOC_NAME)
    for part, label, shape in frozen_parts:
        base = out.addObject("Part::Feature", f"{part}_frozen")
        base.Label = f"{label} (frozen)"
        base.Shape = shape
        body = out.addObject("PartDesign::Body", part)
        body.Label = label
        body.BaseFeature = base
    meta = out.Meta
    meta[META_KEY] = info
    out.Meta = meta
    out.recompute()
    return out


def is_edited(doc):
    return META_KEY in doc.Meta


def build_info(doc):
    """The build_info of the box an edited document was made from."""
    try:
        info = json.loads(doc.Meta[META_KEY])
        info["parameters"]["lock_count"]
    except (KeyError, TypeError, ValueError) as e:
        raise export.ExportError(f"not a valid edited box: {e!r}")
    return info


def export_edited(doc, out_dir, fine=False):
    """Check every body's solids, then write one STL per Body
    (<label>.stl, on the bed as export.place_on_bed) plus build_info.json
    (the box's, with "edited": true). Nothing is written if a check fails.
    Returns the STL paths."""
    doc.recompute()
    check_recompute(doc)
    bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
    if not bodies:
        raise export.ExportError("this edited box has no PartDesign bodies")
    build_info(doc)  # fail before writing anything if the marker is damaged
    seen = set()
    for body in bodies:
        label = body.Label
        if (not label or os.path.basename(label) != label or any(c in label for c in '<>:"/\\|?*')):
            raise export.ExportError(f"{label!r}: the body's label is not a plain file name")
        if label.lower() in seen:
            raise export.ExportError(f"{label}: another body has the same label (ignoring case)")
        seen.add(label.lower())
        if body.Tip is None or body.BaseFeature is None:
            raise export.ExportError(f"{label}: the body has no tip or base feature")
    for body in bodies:
        if not body.Shape.Solids:
            raise export.ExportError(f"{body.Label}: no solid")
        for k, solid in enumerate(body.Shape.Solids):
            export.check_part(f"{body.Label} solid {k + 1}", solid)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for body in bodies:
        shape = export.place_on_bed([s.copy() for s in body.Shape.Solids])
        mesh = MeshPart.meshFromShape(Shape=shape, Relative=False, **export.MESH_SETTINGS[fine])
        path = os.path.join(out_dir, f"{body.Label}.stl")
        mesh.write(path)
        written.append(path)
    info = build_info(doc)
    info["edited"] = True
    with open(os.path.join(out_dir, "build_info.json"), "w") as f:
        json.dump(info, f, indent=2)
    return written
