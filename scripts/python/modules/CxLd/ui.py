from PySide2 import QtWidgets

def make_separator(color=25):
    separator = QtWidgets.QWidget()
    separator.setFixedHeight(1)
    separator.setStyleSheet("background-color : rgb({0}, {0}, {0})".format(color))
    return separator
