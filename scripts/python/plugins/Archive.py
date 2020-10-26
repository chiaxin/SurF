#
# Archive
#
# Author : Chia Xin Lin ( nnnight@gmail.com )
#
# Version : 0.1.01 (beta)
#
# First Build : 2020/10/21
# Last Updated: 2020/10/21
#
# Substance Painter Version : 2020.2.0 (6.2.0)
#

from PySide2 import QtWidgets, QtGui
from os.path import realpath, dirname, isfile, isdir, join, splitext
import CxLd.ui
import CxLd.meta
import json
import substance_painter.ui         as spui
import substance_painter.event      as spev
import substance_painter.project    as sppj
import substance_painter.textureset as spts
import substance_painter.export     as spex
import substance_painter.logging    as splg

# -----------------------------------------
__Version__= "0.1.01 (beta)"
__Author__ = "Chia Xin Lin"
__Email__  = "nnnight@gmail.com"
__Contact__= "https://github.com/chiaxin"
__Title__  = "Archive"
# -----------------------------------------

Icon = join(dirname(realpath(__file__)), "icons", "ArchiveIcon.svg")

PluginWidgets = []

class ArchiveData(object):
    def __init__(self, description=""):
        self.data = dict()
        self.shaders = dict()
        self.description = description
        texture_sets = spts.all_texture_sets()
        for texture_set in texture_sets:
            ts_name = texture_set.name()
            self.shaders[ts_name] = []
            stack = spts.Stack.from_name(texture_set.name())
            for ch_name, channel_type in spts.ChannelType.__members__.items():
                if stack.has_channel(channel_type):
                    channel = stack.get_channel(channel_type)
                    if ch_name.startswitch("User"):
                        self.shaders[ts_name].append(ch_name+":"+channel.label())
                    else:
                        self.shaders[ts_name].apppend(ch_name)
        self.data["Texture_Sets"] = self.data

    def get_path(self):
        if not sppj.is_open():
            return ""
        file_path = sppj.file_path()
        self.directory = dirname(file_path)
        self.project_name = basename(file_path)
        file_name, extension = splitext(self.project_name)
        self.info_json = "Substance_Painter_Archive.json"
        self.info_path = join(self.directory, self.info_json)
        

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
    spui.add_dock_widget(archive_ui)
    PluginWidgets.append(archive_ui)

def close_plugin():
    for widget in PluginWidgets:
        spui.delete_ui_element(widget)

if __name__ == "__main__":
    start_plugin()
