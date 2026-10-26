"""Entry point for hwkan_gfbox.publish (usage: see that module's docstring)."""
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from hwkan_gfbox.fcmain import run  # noqa: E402
from hwkan_gfbox.publish import main  # noqa: E402

run(main)
