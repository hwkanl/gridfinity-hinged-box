"""Entry point for hwkan_gfbox.build.edit_params_main (usage: see that module's docstring).
FreeCAD GUI only: run it as a macro before build_box.py."""
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Import this checkout's package: put it first on sys.path and drop any
# hwkan_gfbox modules already loaded (in the GUI, FreeCAD's Python keeps
# them between macro runs, so code edits would otherwise be ignored).
if PROJECT in sys.path:
    sys.path.remove(PROJECT)
sys.path.insert(0, PROJECT)
for _name in [m for m in sys.modules if m == "hwkan_gfbox" or m.startswith("hwkan_gfbox.")]:
    del sys.modules[_name]

from hwkan_gfbox.build import edit_params_main  # noqa: E402
from hwkan_gfbox.fcmain import run  # noqa: E402

run(edit_params_main)
