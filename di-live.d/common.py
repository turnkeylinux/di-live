
import os
import sys
import commands

mkarg = commands.mkarg

LOGFILE = '/var/log/di-live.log'
def log(s):
    file(LOGFILE, 'a').write(s + "\n")

def prepend_path(path):
    os.environ['PATH'] = path + ":" + os.environ.get('PATH')

class ExecError(Exception):
    """Accessible attributes:
    command     executed command
    exitcode    non-zero exitcode returned by command
    """
    def __init__(self, command, exitcode):
        Exception.__init__(self, command, exitcode)
        self.command = command
        self.exitcode = exitcode

    def __str__(self):
        str = "non-zero exitcode (%d) for command: %s" % (self.exitcode,
                                                          self.command)
        return str

def fmt_command(command, *args):
    return command + " ".join([mkarg(arg) for arg in args])

def system(command, *args):
    """Executes <command> with <*args> -> None
    If command returns non-zero exitcode raises ExecError"""

    sys.stdout.flush()
    sys.stderr.flush()

    command = fmt_command(command, *args)
    error = os.system(command)
    if error:
        exitcode = os.WEXITSTATUS(error)
        raise ExecError(command, exitcode)

def dilive_system(command, *args):
    """convenience function for di-live debconf related command execution
    - prepend compat to path
    - catch and log execution exception, exit with exitcode
    """
    prepend_path('/usr/lib/di-live/compat')
    try:
        system(command, *args)
    except ExecError, e:
        log(str(e))
        sys.exit(e.exitcode)

