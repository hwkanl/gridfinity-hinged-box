"""The README's parameter table is generated from PARAMS."""
import os

from hwkan_gfbox.build import ROOT
from hwkan_gfbox.params import markdown_table


def test_readme_parameter_table_is_current():
    with open(os.path.join(ROOT, "README.md")) as f:
        readme = f.read()
    assert markdown_table() in readme, (
        "README.md's parameter table is out of date; replace it with the output of\n"
        "  python3 -c 'from hwkan_gfbox.params import markdown_table; print(markdown_table(), end=\"\")'")
