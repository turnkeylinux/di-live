# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import re
import os
import sys
import debconf
import commands

mkarg = commands.mkarg

LOGFILE = '/var/log/di-live.log'
def log(s):
    file(LOGFILE, 'a').write(s + "\n")

class Chroot:
    def __init__(self, newroot, environ={}):
        self.environ = { 'HOME': '/root',
                         'TERM': os.environ['TERM'],
                         'LC_ALL': 'C',
                         'PATH': "/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/bin:/usr/sbin" }
        self.environ.update(environ)
        self.path = os.path.realpath(newroot)

    def _prepare_command(self, *command):
        env = ['env', '-i' ] + [ name + "=" + val
                                 for name, val in self.environ.items() ]

        command = fmt_command(*command)
        return ("chroot", self.path, 'sh', '-c', " ".join(env) + " " + command)

    def system(self, *command):
        """execute system command in chroot -> None"""
        system(*self._prepare_command(*command))

class Debconf:
    def __init__(self):
        debconf.runFrontEnd()
        self.db = debconf.Debconf()
        self.db.capb('backup')

    def _db_input(self, template, description=None, default=None):
        self.db.reset(template)
        if description:
            self.db.subst(template, 'DESCRIPTION', description)
        if default:
            self.db.set(template, default)
        self.db.input(debconf.HIGH, template)
        try:
            self.db.go()
        except debconf.DebconfError, e:
            self.db.stop()
            sys.exit(e[0])

        ret = self.db.get(template)
        self.db.reset(template)
        return ret

    def get_input(self, description, default=None):
        template = 'di-live/get-string'
        return self._db_input(template, description, default)

    def get_password(self, description, allow_empty=False):
        while 1:
            password = self._db_input('di-live/password', description)
            if password == self._db_input('di-live/password_again'):
                if not password and not allow_empty:
                    self._db_input('di-live/password_empty')
                    continue
                
                break

            self._db_input('di-live/password_mismatch')

        return re.escape(password)


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

def prepend_path(path):
    os.environ['PATH'] = path + ":" + os.environ.get('PATH')

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

def preset_debconf(resets=None, preseeds=None):
    debconf.runFrontEnd()
    db = debconf.Debconf()

    if resets:
        for template in resets:
            db.reset(template)

    if preseeds:
        for template, value in preseeds:
            db.set(template, value)

def is_mounted(dir):
    mounts = file("/proc/mounts").read()
    if mounts.find(dir) != -1:
        return True
    return False

def target_mounted(target='/target'):
    if not os.path.exists(target) or not is_mounted(target):
        debconf.runFrontEnd()
        db = debconf.Debconf()

        db.capb('backup')
        db.input(debconf.CRITICAL, 'base-installer/no_target_mounted')
        db.go()
        return False

    return True


