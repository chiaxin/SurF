from PySide2 import QtWidgets
from typing import Type

_QLayoutType = Type[QtWidgets.QLayout]
_QWidgetType = Type[QtWidgets.QWidget]


def make_separator(color: int = 25) -> QtWidgets.QWidget:
    """
    :param color: The line's color, default is RGB(25, 25, 25)
    :return:
        QtWidget.QWidget
    """
    separator: QtWidgets.QWidget = QtWidgets.QWidget()
    separator.setFixedHeight(1)
    separator.setStyleSheet(f"background-color : rgb({color}, {color}, {color})")
    return separator


def clean_layout(layout: QtWidgets.QLayout) -> None:
    """
    Looping clean-up layout.
    :param layout: QLayout object.
    """
    while layout.count():
        item: QtWidgets.QLayout = layout.takeAt(0)
        widget: QtWidgets.QWidget = item.widget()
        if widget is not None:
            widget.deleteLater()
        else:
            clean_layout(item.layout())
