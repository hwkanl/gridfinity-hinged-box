import os

import FreeCAD as App

from hwkan_gfbox import outdirs

GROUP = outdirs.GROUP + "_test"


def _clear():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod").RemGroup("hwkan_gfbox_test")


def test_last_dir_defaults_to_the_home_folder():
    _clear()
    try:
        want = os.path.join(os.path.expanduser("~"), *(["Documents"] if os.name == "nt" else []), "hwkan_gfbox")
        assert outdirs.last_dir(outdirs.EXPORT, GROUP) == want
    finally:
        _clear()


def test_remember_keeps_the_folder_per_command():
    _clear()
    try:
        outdirs.remember(outdirs.EXPORT, "some/where", GROUP)
        assert outdirs.last_dir(outdirs.EXPORT, GROUP) == os.path.abspath("some/where")
        assert outdirs.last_dir(outdirs.TEST_PRINTS, GROUP) == outdirs.default_dir()
    finally:
        _clear()
