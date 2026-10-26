"""The box body: the cavity the bins sit in, the outer solid, and their difference."""
from hwkan_gfbox.shapes import FIRST_CELL_X, FIRST_CELL_Y, box, cell_array, cut, fuse, offset_prism, profile_loft


def build_cavity(doc):
    """Cavity = one baseplate pocket per cell + one open bin space above them."""
    pocket = profile_loft(doc, "PocketCell", "Internal.gf_pitch", "Internal.bp_top_r",
                          FIRST_CELL_X, FIRST_CELL_Y, [
                              ("Internal.floor_t", "Internal.bp_ch_high + Internal.bp_ch_low"),
                              ("Internal.floor_t + Internal.bp_ch_low", "Internal.bp_ch_high"),
                              ("Internal.floor_t + Internal.bp_ch_low + Internal.bp_vert", "Internal.bp_ch_high"),
                              ("Internal.floor_t + Internal.bp_h", "0 mm"),
                              ("Internal.floor_t + Internal.bp_h + Internal.overlap", "0 mm"),
                          ])
    pockets = cell_array(doc, "Pockets", pocket)
    # Starts ridge_clip below the pocket tops, clipping the knife-edge
    # ridges between pockets to a flat strip.
    bin_space = box(doc, "BinSpace", "Internal.grid_w", "Internal.grid_d",
                    "Internal.floor_t + Internal.bp_h - Internal.ridge_clip",
                    "Internal.ceiling_z - Internal.floor_t - Internal.bp_h + Internal.ridge_clip")
    return fuse(doc, "Cavity", [pockets, bin_space])


def build_box_solid(doc):
    """The plain outer solid: the cavity rectangle offset by wall_t with
    concentric rounded corners (ribs will be added to this later)."""
    return offset_prism(doc, "BoxSolid", "Internal.wall_t", "0 mm", "Internal.box_h")


def build_box(doc):
    """Box = outer solid minus cavity."""
    return cut(doc, "Box", build_box_solid(doc), build_cavity(doc))
