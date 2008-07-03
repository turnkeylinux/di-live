
import os
import sys

LOGFILE = '/var/log/di-live.log'
def log(s):
    file(LOGFILE, 'a').write(s + "\n")

def prepend_path(path):
    os.environ['PATH'] = path + ":" + os.environ.get('PATH')

def system(command):
    """if command returns non-zero exitcode, exit with it
    not a good coding practice, but we need this for debconf
    """
    error = os.system(command)
    if error:
        exitcode = os.WEXITSTATUS(error)
        log("non-zero exitcode (%d) for command: %s" % (exitcode, command))
        sys.exit(exitcode)


