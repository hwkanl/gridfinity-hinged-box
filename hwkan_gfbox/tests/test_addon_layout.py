"""Guards that keep the project ready to be wrapped as a FreeCAD addon.

An installed addon's directory is put on FreeCAD's sys.path, so every
top-level package in it shares one namespace with all other addons, and
code imported by a headless addon must not need the GUI.
"""
import importlib
import os
import pkgutil
import sys
import xml.etree.ElementTree as ET

import hwkan_gfbox

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(hwkan_gfbox.__file__)))
NS = {"p": "https://wiki.freecad.org/Package_Metadata"}


def test_hwkan_gfbox_is_the_only_top_level_package():
    packages = sorted(
        name for name in os.listdir(PROJECT)
        if os.path.isfile(os.path.join(PROJECT, name, "__init__.py")))
    assert packages == ["hwkan_gfbox"], packages


def test_package_imports_without_the_gui():
    for info in pkgutil.walk_packages(hwkan_gfbox.__path__, "hwkan_gfbox."):
        importlib.import_module(info.name)
    assert "FreeCADGui" not in sys.modules


def test_package_xml_names_the_workbench_initgui_defines():
    root = ET.parse(os.path.join(PROJECT, "package.xml")).getroot()
    assert root.find("p:name", NS).text == "Gridfinity Hinged Box"
    assert root.find("p:license", NS).text == "LGPL-2.1-or-later"
    assert os.path.isfile(os.path.join(PROJECT, root.find("p:license", NS).get("file")))
    assert root.find("p:version", NS).text == hwkan_gfbox.__version__
    wb = root.find("p:content/p:workbench", NS)
    assert wb.find("p:classname", NS).text == "HwkanGfboxWorkbench"
    with open(os.path.join(PROJECT, "InitGui.py")) as f:
        text = f.read()
    compile(text, "InitGui.py", "exec")
    assert "class HwkanGfboxWorkbench(" in text and "addWorkbench(HwkanGfboxWorkbench())" in text
    for icon in (root.find("p:icon", NS).text, wb.find("p:icon", NS).text):
        assert os.path.isfile(os.path.join(PROJECT, icon)), icon


def test_every_command_has_an_icon():
    from hwkan_gfbox import workbench
    assert os.path.isfile(workbench.icon("workbench"))
    for cmd_id, icon_name, *_ in workbench.COMMAND_TABLE:
        assert os.path.isfile(workbench.icon(icon_name)), cmd_id
    assert workbench.COMMANDS == [c[0] for c in workbench.COMMAND_TABLE]
