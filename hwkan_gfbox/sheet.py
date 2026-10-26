"""The parameter sheets: Params (the inputs and the preset's name: what users
change), Preset (the preset's values the box was built with) and Internal
(design, Gridfinity and derived values): creation, reading and safe writing."""
import math
import re

from hwkan_gfbox.params import (DEFAULT_PRESET, DERIVED, DESIGN, GRIDFINITY, INPUT, INTERNAL_SHEET, PARAMS,
                                PRESET_SHEET, PRESET_TIERS, SECTIONS, USER_SHEET, sheet_of)

SHEET_NAME = USER_SHEET  # the sheet callers pass around; value() finds the others
_ROWS = {row[0]: row for row in PARAMS}
_SHEET_OF_NAME = {name: sheet_of(tier) for name, _, tier, _ in PARAMS}
PRESET_ALIAS = "preset"  # the Params cell naming the preset the tolerance and fit values come from
SOURCE_ALIAS = "preset_source"  # the Preset cell naming the preset its values were loaded from
PRESET_TITLE = "Preset (its tolerance and fit values are on the Preset sheet)"
PRESET_NOTE = ("The values this box was built with, from the preset named on Params. Every build "
               "writes them: edit the preset file (scripts/presets.py path NAME), not these cells.")


class ParamError(ValueError):
    """A parameter value or override is not acceptable."""


def _cell_text(val, tier):
    """Cell content for a row: names in a formula that live on another sheet
    point at it (Params.gf_x, Preset.lip_clearance)."""
    if not val.startswith("="):
        return val
    own = sheet_of(tier)

    def name(m):
        other = _SHEET_OF_NAME.get(m.group(), own)
        return m.group() if other == own else f"{other}.{m.group()}"
    return re.sub(r"\b[a-z_][a-z0-9_]*\b", name, val)


def _fill(sheet, tiers, note=None):
    for col, text in zip("ABCD", ("name", "value", "tier", "comment")):
        sheet.set(f"{col}1", text)
    row = 1
    if note:
        row += 1
        sheet.set(f"A{row}", "'" + note)
    for tier, title in SECTIONS:
        if tier not in tiers:
            continue
        row += 2
        sheet.set(f"A{row}", title)
        for name, val, t, comment in PARAMS:
            if t != tier:
                continue
            row += 1
            sheet.set(f"A{row}", name)
            sheet.set(f"B{row}", _cell_text(val, t))
            sheet.setAlias(f"B{row}", name)
            sheet.set(f"C{row}", tier)
            sheet.set(f"D{row}", "'" + comment)
    return row


def _add_text_cell(sheet, row, title, alias, comment):
    """A section holding one text cell (a preset's name), below the others."""
    row += 2
    sheet.set(f"A{row}", title)
    row += 1
    sheet.set(f"A{row}", alias)
    sheet.set(f"B{row}", "'" + DEFAULT_PRESET)
    sheet.setAlias(f"B{row}", alias)
    sheet.set(f"C{row}", "preset")
    sheet.set(f"D{row}", "'" + comment)


def create_params_sheet(doc):
    """Add the Params, Preset and Internal sheets to doc (columns name |
    value | tier | comment, grouped by section; each value cell aliased with
    the parameter name). Returns the Params sheet."""
    params = doc.addObject("Spreadsheet::Sheet", USER_SHEET)
    preset = doc.addObject("Spreadsheet::Sheet", PRESET_SHEET)
    internal = doc.addObject("Spreadsheet::Sheet", INTERNAL_SHEET)
    _add_text_cell(params, _fill(params, [INPUT]), PRESET_TITLE, PRESET_ALIAS,
                   "a preset name (scripts/presets.py list) or a JSON file; "
                   "empty: no preset, the values on the Preset sheet are kept")
    _add_text_cell(preset, _fill(preset, PRESET_TIERS, PRESET_NOTE), "Source", SOURCE_ALIAS,
                   "the preset these values were loaded from (a rebuild tells a moved "
                   "document from a mistyped preset name by it)")
    _fill(internal, [tier for tier, _ in SECTIONS if tier != INPUT and tier not in PRESET_TIERS])
    doc.recompute()
    return params


def _target(sheet, name):
    """The sheet (Params, Preset or Internal, in sheet's document) that holds name."""
    return sheet.Document.getObject(sheet_of(_ROWS[name][2]))


def value(sheet, name):
    """Current value of a parameter as a float (lengths in mm, angles in
    degrees). `sheet` is any sheet of the document; the name is read
    from the one that holds it."""
    v = _target(sheet, name).get(name)
    return float(getattr(v, "Value", v))


def _is_number(text):
    try:
        return math.isfinite(float(text))
    except ValueError:
        return False


def set_param(sheet, name, text):
    """Write one override into the sheet. Returns a list of warnings.

    Inputs and tolerances may be set; design constants may be set with a
    warning; Gridfinity constants and derived values are refused. A bare
    number for a length gets " mm" (for an angle " deg") appended (without a
    unit the cell would become dimensionless and break every expression that uses it).
    """
    if name not in _ROWS:
        raise ParamError(f"unknown parameter '{name}'")
    _, default, tier, _ = _ROWS[name]
    if tier in (GRIDFINITY, DERIVED):
        raise ParamError(f"'{name}' is a {tier} value and cannot be set")
    text = text.strip()
    unit = next((u for u in ("mm", "deg") if default.endswith(" " + u)), None)
    if _is_number(text):
        if unit:
            text += " " + unit
    elif not (unit and text.endswith(unit) and _is_number(text[:-len(unit)])):
        raise ParamError(f"'{name}': expected a number{f' ({unit})' if unit else ''}, got '{text}'")
    # Written as an expression so a leading minus isn't read as text.
    target = _target(sheet, name)
    target.set(target.getCellFromAlias(name), "=" + text)
    if tier == DESIGN:
        return [f"warning: '{name}' is an internal design constant; "
                "the model is not guaranteed to rebuild correctly"]
    return []


def apply_overrides(sheet, overrides):
    """Apply (name, value) pairs in order. Returns all warnings."""
    warnings = []
    for name, text in overrides:
        warnings += set_param(sheet, name, text)
    return warnings


def _user(sheet):
    return sheet.Document.getObject(USER_SHEET)


def _text(holder, alias):
    """A text cell's content ("" if empty), or None if holder or the cell is
    missing. Read with getContents: an empty text cell can't be read by its alias."""
    cell = holder.getCellFromAlias(alias) if holder is not None else None
    if cell is None:
        return None
    return holder.getContents(cell).lstrip("'").strip()


def set_preset(sheet, ref):
    """Write the preset's name (or path) into the preset cell, and as the
    source of the values on the Preset sheet."""
    params = _user(sheet)
    params.set(params.getCellFromAlias(PRESET_ALIAS), "'" + ref)
    preset = sheet.Document.getObject(PRESET_SHEET)
    if preset is not None and preset.getCellFromAlias(SOURCE_ALIAS) is not None:
        preset.set(preset.getCellFromAlias(SOURCE_ALIAS), "'" + ref)


def sheet_preset(sheet):
    """The preset cell's text ("" if empty), or None if the document has no
    preset cell (an older generator's)."""
    return _text(_user(sheet), PRESET_ALIAS)


def sheet_source(sheet):
    """The preset the Preset sheet's values were loaded from ("" if none),
    or None if the document doesn't record it (an older generator's)."""
    return _text(sheet.Document.getObject(PRESET_SHEET), SOURCE_ALIAS)


def _holder(sheet, name):
    """The sheet in sheet's document holding name: its own, or Params in a
    document from before the Preset sheet; None if neither has it."""
    for sheet_name in (sheet_of(_ROWS[name][2]), USER_SHEET):
        holder = sheet.Document.getObject(sheet_name)
        if holder is not None and holder.getCellFromAlias(name) is not None:
            return holder
    return None


def preset_values(sheet):
    """{name: mm} for every preset value the document holds (an older one
    may lack some, or hold them on Params)."""
    found = {}
    for name, _, tier, _ in PARAMS:
        holder = _holder(sheet, name) if tier in PRESET_TIERS else None
        if holder is not None:
            v = holder.get(name)
            found[name] = float(getattr(v, "Value", v))
    return found


def sheet_overrides(sheet):
    """(name, value) pairs, in PARAMS order, for every input whose cell
    differs from its default: what a rebuild needs to keep the user's box.
    The preset's values are not included (a rebuild reloads them from the
    preset; see build.sheet_settings), nor Internal values: users don't edit
    them, and a cell there that differs from today's default is usually an
    older generator's default. Parameters the document lacks are left out."""
    overrides = []
    for name, default, tier, _ in PARAMS:
        if tier != INPUT:
            continue
        # Cells hold expressions ("=0.25 mm"); defaults come with or without the "=".
        # A document from an older generator may lack a parameter: it keeps its default.
        target = _target(sheet, name)
        cell = target.getCellFromAlias(name)
        if cell is None:
            continue
        text = target.getContents(cell).lstrip("=")
        if text != default.lstrip("="):
            overrides.append((name, text))
    return overrides
