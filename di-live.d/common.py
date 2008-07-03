
import os
import sys

def prepend_path(path):
    os.environ['PATH'] = path + ":" + os.environ.get('PATH')

def system(command):
    """if command returns non-zero exitcode, exit with it"""
    error = os.system(command)
    if error:
        sys.exit(os.WEXITSTATUS(error))

