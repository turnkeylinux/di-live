# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
"""Common di-live functions and classes."""
import os
import sys
import debconf
import subprocess
from subprocess import PIPE
from typing import List

import chroot

LOGFILE = '/var/log/di-live.log'


def log(s):
    with open(LOGFILE, 'a') as fob:
        fob.write(s + "\n")


class DiliveDebconf:
    """debconf wrapper class to create new debconf dialogs and progress info.

    It can use existing di-live templates, or generate new ones dynamically
    using generic templates included in the di-live package.
    """

    def __init__(self, title=None):
        if title:
            self.db = debconf.Debconf(run_frontend=True, title=title)
        else:
            self.db = debconf.Debconf(run_frontend=True)
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
        except debconf.DebconfError as e:
            self.db.stop()
            sys.exit(e.args[0])

        ret = self.db.get(template)
        self.db.reset(template)
        return ret

    def get_input(self, template='di-live/get-string', description=None,
                  default=None):
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

        return password

    def progress_init(self, steps, template='di-live/progress/generic',
                      description=None):
        if description:
            self.db.subst(template, 'DESCRIPTION', description)
        self.progress_steps = steps
        self.db.progress('START 0 {} {}'.format(steps, template))

    def progress_step(self, step_no):
        if step_no > self.progress_steps:
            return
        self.db.progress('STEP {}'.format(step_no))


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
    os.environ['PATH'] = f"{path}:{os.environ.get('PATH')}"


def system(command, shell=False, stdout=None, write_log=True,
           env=os.environ) -> None:
    """Execute command.

    If command returns non-zero exitcode raises ExecError

    command may either be:
     - a list containing individual items/arguments; or
     - if shell=True, a list containing a single string.
    """
    command = list(command)
    if write_log:
        log('Running command: {}'.format(command))
    run_command = subprocess.run(command, shell=shell, env=env,
                                 stderr=PIPE, stdout=stdout)
    if run_command.returncode != 0:
        if write_log:
            log('Command {}: Exit code {}\nSTDERR: {}'.format(
                run_command.args,
                run_command.returncode,
                run_command.stderr.decode()))
        raise ExecError(command, run_command.returncode)


def dilive_system(command):
    """Di-live debconf related command execution.

    - command must be a list - and is passed to system()
    - prepend compat to path
    - catch and log execution exception, exit with exitcode
    - stderr is redirected to the logfile by system()
    """
    prepend_path('/usr/lib/di-live/compat')
    try:
        system(command)
    except ExecError as e:
        log(str(e))
        sys.exit(e.exitcode)


def preset_debconf(resets=None, preseeds=None, seen=None):
    db = debconf.Debconf(run_frontend=True)

    if resets:
        for template in resets:
            db.reset(template)

    if preseeds:
        for template, value in preseeds:
            db.set(template, value)

    if seen:
        for template, value in seen:
            db.fset(template, 'seen', value)


def target_mounted(target='/target'):

    if not os.path.exists(target) or chroot.is_mounted(target):
        db = debconf.Debconf(run_frontend=True)
        db.capb('backup')
        db.input(debconf.CRITICAL, 'base-installer/no_target_mounted')
        db.go()
        return False
    return True


def is_efi():
    """Function to determine if 'efi' is in kernel commandline."""
    with open('/proc/cmdline', 'r') as fob:
        if 'efi' in fob.readline().split():
            return True
        else:
            return False
