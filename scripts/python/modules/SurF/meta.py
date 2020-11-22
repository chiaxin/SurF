import substance_painter.ui         as spui
import substance_painter.event      as spev
import substance_painter.project    as sppj
import substance_painter.textureset as spts
import substance_painter.export     as spex
import substance_painter.logging    as splg

class Metadata(object):
    def __init__(self, name):
        self.name = name
        self.meta = sppj.Metadata(self.name)

    def set(self, key, value):
        self.meta.set(key, value)

    def list(self):
        return self.meta.list()

    def get(self, key):
        return self.meta.get(key)
