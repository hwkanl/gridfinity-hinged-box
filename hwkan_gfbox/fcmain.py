"""Entry-point helpers for scripts that run under freecadcmd or in the GUI.

freecadcmd quirks this works around (verified on FreeCAD 1.1.3):
- arguments after the script name are treated as files to open, so
  scripts/fc.sh passes them in the FC_ARGS environment variable instead;
- stdout is lost when a script calls sys.exit();
- an uncaught exception still exits with status 0;
- a script's __name__ is its file's base name, not "__main__", so entry
  scripts (scripts/*.py) call run(main) unconditionally and modules in
  this package never run anything on import.
"""
import os
import shlex
import sys
import traceback

import FreeCAD as App


def script_args():
    """Arguments given to scripts/fc.sh, as a list of strings."""
    return shlex.split(os.environ.get("FC_ARGS", ""))


def run(main):
    """Call main(args) -> int exit status.

    Headless: print any traceback, flush, and hard-exit with the status.
    GUI: call main([]) and return its status; never exit FreeCAD.
    """
    if App.GuiUp:
        return main([])
    try:
        code = main(script_args())
    except SystemExit as e:
        code = 0 if e.code is None else (e.code if isinstance(e.code, int) else 1)
    except BaseException:
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code or 0)
