"""README.md is the user guide: its parameter table is generated from PARAMS,
and its images, names and links must be real."""
import os
import re

from hwkan_gfbox.build import ROOT
from hwkan_gfbox.export import PARTS
from hwkan_gfbox.params import PARAMS, markdown_table
from hwkan_gfbox.testprints import TEST_SET
from hwkan_gfbox.workbench import COMMAND_TABLE

# What Export STLs writes (the lid and bottom carry the grid size, e.g.
# lid_3x2x6.stl, so the README names them as bottom and lid).
EXPORT_FILES = {f"{name}.stl" for name in PARTS} | {"build_info.json"}


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _readme():
    return _read("README.md")


def _slug(heading):
    """GitHub's anchor for a heading."""
    return re.sub(r"[^a-z0-9 -]", "", heading.strip().lower()).replace(" ", "-")


def test_readme_parameter_table_is_current():
    assert markdown_table() in _readme(), (
        "README.md's parameter table is out of date; replace it with the output of\n"
        "  python3 -c 'from hwkan_gfbox.params import markdown_table; print(markdown_table(), end=\"\")'")


def test_readme_images_exist():
    """Every ![...](path) in README.md is a file under images/."""
    for path in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", _readme()):
        assert path.startswith("images/") and os.path.isfile(os.path.join(ROOT, path)), path


def test_readme_names_are_real():
    """Backticked snake_case words are parameters, test parts (with or
    without .stl) or exported files."""
    known = {n for n, _, _, _ in PARAMS} | set(TEST_SET) | {f"{n}.stl" for n in TEST_SET} | EXPORT_FILES
    for word in re.findall(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+(?:\.[a-z]+)?)`", _readme()):
        assert word in known, word


def test_readme_links_resolve():
    """Links to DEVELOPING.md#anchor point at a heading there."""
    anchors = {_slug(h) for h in re.findall(r"^#+ (.+)$", _read("DEVELOPING.md"), re.M)}
    for anchor in re.findall(r"\]\(DEVELOPING\.md#([^)]+)\)", _readme()):
        assert anchor in anchors, anchor


def test_readme_names_the_commands():
    """Every workbench command's menu text appears in the README."""
    for _, _, menu, _, _, _ in COMMAND_TABLE:
        assert menu in _readme(), menu


def test_readme_has_no_control_characters():
    """A "\v" typed through a Python string once became a vertical tab in a path."""
    for name in ("README.md", "DEVELOPING.md"):
        bad = [(i, repr(c)) for i, c in enumerate(_read(name)) if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, (name, bad[:5])


def test_readme_preset_folders():
    """The preset folders the README names are FreeCAD's user data folders."""
    assert r"`%APPDATA%\FreeCAD\v1-1\`" in _readme() and "`~/.local/share/FreeCAD/v1-1/`" in _readme()
