#
#
#
#
#

def reverse_replace(s, old, new, occurrence):
    buffers = s.rsplit(old, occurrence)
    return new.join(buffers)
