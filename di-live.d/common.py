# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
"""Common di-live functions and classes."""
import os
import sys
import debconf
import subprocess
from subprocess import PIPE
from typing import List

LOGFILE = '/var/log/di-live.log'


def log(s):
    with open(LOGFILE, 'a') as fob:
        fob.write(s + "\n")


class Chroot:
    """Run commands inside a chroot."""

    def __init__(self, newroot, environ={}):
        # hack to allow exiting the chroot later - see rest in __del__()
        self.real_root = os.open('/', os.O_RDONLY)
        self.initial_cwd = os.getcwd()

        PATH = "/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/bin:/usr/sbin"
        self.environ = {'HOME': '/root',
                        'TERM': os.environ['TERM'],
                        'LC_ALL': 'C',
                        'PATH': PATH}
        self.environ.update(environ)

        self.targetmounts = TargetMounts(newroot)

        # enter chroot and explicitly change to chroot's root; as python cwd
        # is not auto updated and python cwd may not exist in chroot
        os.chroot(newroot)
        os.chdir('/')

    def system(self, command, shell=False, stdout=None) -> None:
        """Leverages system function to execute command in chroot."""
        system(command, shell=shell, stdout=stdout, env=self.environ)

    def exit(self):
        # hack to escape python chroot and get back to initial cwd
        os.fchdir(self.real_root)
        os.chroot('.')
        os.chdir(self.initial_cwd)
        self.targetmounts.umount()

    def __del__(self):
        self.exit()


class DiliveDebconf:
    """debconf wrapper class to create new debconf dialogs and progress info.

    It can use existing di-live templates, or generate new ones dynamically
    using generic templates included in the di-live package.
    """

    def __init__(self):
        self.db = debconf.Debconf(run_frontend=True)
        self.db.capb('backup')

    def _db_input(self, template, description, default):
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
        if template == 'di-live/progress/generic' and description:
            self.db.subst(template, 'DESCRIPTION', description)
        self.progress_steps = steps
        self.db.progress('START 0 {} {}'.format(steps, template))

    def progress_step(self, step_no):
        if step_no > self.progress_steps:
            return
        self.db.progress('STEP {}'.format(step_no))


class TargetMounts:
    """Set up and remove required mountpoints for a chroot."""

    def __init__(self, target='/target'):
        self.targetdev = os.path.join(target, 'dev')
        self.targetproc = os.path.join(target, 'proc')
        self.targetsys = os.path.join(target, 'sys')
        self.targetrun = os.path.join(target, 'run')
        self.mount()

    def mount(self):
        def _mount(primary_dir, secondary_dir):
            system(["mount", "-o", "bind", primary_dir, secondary_dir])

        if not is_mounted(self.targetdev):
            _mount("/dev", self.targetdev)
        if not is_mounted(self.targetproc):
            _mount("/proc", self.targetproc)
        if not is_mounted(self.targetsys):
            _mount("/sys", self.targetsys)

    def umount(self):
        def _umount(mounted_dir):
            system(["umount", "-f", mounted_dir])

        if is_mounted(self.targetsys):
            with open("/proc/mounts", 'r') as fob:
                for line in fob.readlines():
                    host, guest, *others = line.split(' ')
                    if (guest.startswith(self.targetsys)
                            and not guest == self.targetsys):
                        _umount(guest)
            _umount(self.targetsys)
        if is_mounted(self.targetdev):
            _umount(self.targetdev)
        if is_mounted(self.targetproc):
            _umount(self.targetproc)
        if is_mounted(self.targetrun):
            _umount(self.targetrun)

    def __del__(self):
        self.umount()


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


def is_mounted(directory):
    with open("/proc/mounts", 'r') as fob:
        for line in fob.readlines():
            host, guest, *others = line.split(' ')
            if guest == directory:
                return True
    return False


def target_mounted(target='/target'):

    if not os.path.exists(target) or not is_mounted(target):
        db = debconf.Debconf(run_frontend=True)
        db.capb('backup')
        db.input(debconf.CRITICAL, 'base-installer/no_target_mounted')
        db.go()
        return False
    return True
