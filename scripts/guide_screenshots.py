"""Screenshots for the user guide (hwkan_gfbox.screenshots) into images/.
Runs in the FreeCAD GUI only: open it as a macro and execute it, or start
FreeCAD with it (freecad scripts/guide_screenshots.py). It closes FreeCAD
when done if it started it."""
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

import FreeCAD as App  # noqa: E402

from hwkan_gfbox.fcmain import run  # noqa: E402


def main(args):
    if not App.GuiUp:
        print("guide_screenshots.py needs the FreeCAD GUI", file=sys.stderr)
        return 2
    from PySide import QtCore

    from hwkan_gfbox import screenshots

    quit_after = os.environ.get("HWKAN_SHOTS_QUIT") == "1"

    def shoot():
        try:
            for path in screenshots.take(os.path.join(PROJECT, "images")):
                App.Console.PrintMessage(f"wrote {path}\n")
        finally:
            if quit_after:
                import FreeCADGui
                FreeCADGui.getMainWindow().close()

    QtCore.QTimer.singleShot(3000, shoot)  # once the GUI's event loop runs
    return 0


run(main)
