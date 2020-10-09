from PySide2 import QtWidgets, QtGui
from os.path import realpath, dirname, isfile, isdir, join
import bfUtils.ui
import substance_painter.ui as ui
import substance_painter.export as spex

#
__Version__ = "0.1.0 (beta)"
__Title__   = "Archive"
#

Icon = join(dirname(realpath(__file__)), "icons", "ArchiveIcon.svg")

plugin_widgets = []

def make_separator():
    separator = QtWidgets.QWidget()
    separator.setFixedHeight(1)
    separator.setStyleSheet("background-color : rgb(25, 25, 25)")
    return separator

def export_testing():
    presets = {
        "exportPath" : r"S:\cxcg\abc\Maya\temp\Guitar",
        "exportShaderParams" : True,
        "defaultExportPreset": "VRay",
        "exportPresets" : [{
            "name" : "VRay",
            "maps" : [{
                    "fileName" : "$textureSet/Test_$textureSet_Color(_$udim)",
                    "channels" : [
                        {
                            "destChannel": "R",
                            "srcChannel" : "R",
                            "srcMapType" : "documentMap",
                            "srcMapName" : "diffuse"
                        },
                        {
                            "destChannel": "G",
                            "srcChannel" : "G",
                            "srcMapType" : "documentMap",
                            "srcMapName" : "diffuse"
                        },
                        {
                            "destChannel": "B",
                            "srcChannel" : "B",
                            "srcMapType" : "documentMap",
                            "srcMapName" : "diffuse"
                        }
                    ]
                }
            ]
        }],
        "exportList" : [
            {
                "rootPath" : "BodyWood",
                "filter" : {
                    "uvTiles" : [[0, 0], [1, 0], [2, 0]]
                }
            }
        ],
        "exportParameters" : [{
            "parameters" : {
                "fileFormat" : "tif",
                "bitDepth" : "8",
                "dithering" : True,
                "sizeLog2" : 12,
                "paddingAlgorithm" : "diffusion",
                "dilationDistance" : 16
            }
        }]
    }
    result = spex.export_project_textures(presets)
    #print(result)
    #print(dir(result))
    #textures = spex.list_project_textures(presets)
    #for texture in textures:
    #    print(texture)

class ArchiveUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(__Title__)
        self.setWindowIcon(QtGui.QIcon(Icon))
        self.initUI()

    def initUI(self):
        main_layout = QtWidgets.QVBoxLayout()
        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget(scroll_area)
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        for i in range(12):
            scroll_layout.addWidget(QtWidgets.QLabel("%04d" % i))
        button = QtWidgets.QPushButton("<h1>Testing</h1>")
        line = QtWidgets.QFrame()
        line.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
        line.setLineWidth(5)
        sp = bfUtils.ui.make_separator()
        main_layout.addWidget(line)
        main_layout.addWidget(sp)
        main_layout.addWidget(button)
        main_layout.addWidget(QtWidgets.QLabel("************"))
        self.setLayout(main_layout)
        button.clicked.connect(export_testing)

def start_plugin():
    archive_ui = ArchiveUI()
    ui.add_dock_widget(archive_ui)
    plugin_widgets.append(archive_ui)

def close_plugin():
    for widget in plugin_widgets:
        ui.delete_ui_element(widget)

if __name__ == "__main__":
    start_plugin()
