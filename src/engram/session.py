# transcript save/load

# Saves the transcript so a crash can resume


#?  Why this file and usecase 


import os

_read_mtimes = {}


def reset():
    _read_mtimes.clear()


def mark_read(path):
    _read_mtimes[path] = os.stat(path).st_mtime_ns


def read_mtime(path):
    return _read_mtimes.get(path)