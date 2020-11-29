#
# SurF.utils
#   The Utilities for tools.
#
# Author : Chia Xin Lin ( nnnight@gmail.com )
#
# Substance Painter Version : 2020.2.0 (6.2.0)
#

import substance_painter.logging as splg
import tempfile
import json


def reverse_replace(s, old, new, occurrence):
    buffers = s.rsplit(old, occurrence)
    return new.join(buffers)


def log(message: str) -> None:
    splg.info(message)


def warn(message: str) -> None:
    splg.warning(message)


def err(message: str) -> None:
    splg.error(message)
