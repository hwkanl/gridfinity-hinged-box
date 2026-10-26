# Gridfinity Hinged Box: FreeCAD runs this file at GUI startup (exec'd in
# FreeCAD's namespace, not imported as a module). The commands live in
# hwkan_gfbox.workbench, imported only when the workbench is first activated.
import os

import FreeCADGui


class HwkanGfboxWorkbench(FreeCADGui.Workbench):
    MenuText = "Gridfinity Hinged Box"
    ToolTip = "Parametric Gridfinity hinged box: build, export STLs, test prints, calibration"

    def __init__(self):
        import hwkan_gfbox
        self.__class__.Icon = os.path.join(os.path.dirname(hwkan_gfbox.__file__),
                                           "resources", "icons", "workbench.svg")

    def Initialize(self):
        from hwkan_gfbox import workbench
        workbench.register()
        self.appendToolbar("Gridfinity Hinged Box", workbench.COMMANDS)
        self.appendMenu("Gridfinity Hinged Box", workbench.COMMANDS)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(HwkanGfboxWorkbench())
