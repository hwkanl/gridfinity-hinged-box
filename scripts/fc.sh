#!/usr/bin/env bash
# Run a FreeCAD Python script headless:
#     scripts/fc.sh SCRIPT.py [ARGS...]
# FreeCAD is found via $FREECAD (path to freecadcmd or to a FreeCAD
# AppImage), else `freecadcmd` on PATH. ARGS reach the script through the
# FC_ARGS environment variable (freecadcmd would treat them as files to
# open); scripts read them with hwkan_gfbox.fcmain.script_args().
set -euo pipefail
if [[ $# -lt 1 ]]; then
    echo "usage: scripts/fc.sh SCRIPT.py [ARGS...]" >&2
    exit 64
fi
fc="${FREECAD:-}"
if [[ -z "$fc" ]]; then
    if command -v freecadcmd >/dev/null 2>&1; then
        fc=freecadcmd
    else
        echo "fc.sh: FreeCAD not found; set FREECAD to freecadcmd or the FreeCAD AppImage" >&2
        exit 127
    fi
fi
script="$1"
shift
if [[ $# -gt 0 ]]; then
    FC_ARGS="$(printf '%q ' "$@")"
else
    FC_ARGS=""
fi
export FC_ARGS
if [[ "$fc" == *.AppImage ]]; then
    exec "$fc" freecadcmd "$script"
else
    exec "$fc" "$script"
fi
