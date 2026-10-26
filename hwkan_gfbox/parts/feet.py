"""Gridfinity feet on the lid underside: one shrunken bin base per cell,
hanging from the ceiling into each bin's stacking lip."""
from hwkan_gfbox.shapes import FIRST_CELL_X, FIRST_CELL_Y, cell_array, profile_loft


def build_feet(doc):
    """Feet array. Each foot's bottom is at split_z (= ceiling_z - base_h);
    its top extends `overlap` into the ceiling."""
    foot = profile_loft(doc, "FootCell",
                        "Internal.base_top - 2 * Preset.feet_xy_clearance",
                        "Internal.base_top_r - Preset.feet_xy_clearance",
                        FIRST_CELL_X, FIRST_CELL_Y, [
                            ("Internal.split_z", "Internal.base_ch_high + Internal.base_ch_low"),
                            ("Internal.split_z + Internal.base_ch_low", "Internal.base_ch_high"),
                            ("Internal.split_z + Internal.base_ch_low + Internal.base_vert", "Internal.base_ch_high"),
                            ("Internal.ceiling_z", "0 mm"),
                            ("Internal.ceiling_z + Internal.overlap", "0 mm"),
                        ])
    return cell_array(doc, "Feet", foot)
