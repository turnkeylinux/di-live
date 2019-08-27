# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import os
import sys
import debconf

from subprocess import run, PIPE

PIPE = PIPE

LOGFILE = '/var/log/di-live.log'


def log(s):
    with open(LOGFILE, 'a') as fob:
        fob.write(s + "\n")


class Chroot:
    """Run commands inside a chroot"""

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

    def system(self, *command, shell=False, stdout=None):
        """execute system command in chroot -> None"""
        system(command, shell=shell, stdout=stdout, env=self.environ)

    def exit(self):
        # hack to escape python chroot and get back to initial cwd
        os.fchdir(self.real_root)
        os.chroot('.')
        os.chdir(self.initial_cwd)
        self.targetmounts.umount()

    def __del__(self):
        self.exit()

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
        except debconf.DebconfError as e:
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

        return password


class TargetMounts:
    def __init__(self, target='/target'):
        self.targetdev = os.path.join(target, 'dev')
        self.targetproc = os.path.join(target, 'proc')
        self.targetsys = os.path.join(target, 'sys')
        self.targetrun = os.path.join(target, 'run')
        self.mount()

    def mount(self):
        def _mount(primary_dir, secondary_dir):
            system("mount", "-o", "bind", primary_dir, secondary_dir)

        if not is_mounted(self.targetdev):
            _mount("/dev", self.targetdev)
        if not is_mounted(self.targetproc):
            _mount("/proc", self.targetproc)
        if not is_mounted(self.targetsys):
            _mount("/sys", self.targetsys)

    def umount(self):
        def _umount(mounted_dir):
            system("umount", "-f", mounted_dir)

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


def system(command, *args, shell=False, stdout=None, write_log=True, env=os.environ):
    """Executes <command> with <*args> -> None
    If command returns non-zero exitcode raises ExecError"""
    if isinstance(command, str):
        command = [command]
    else: # handle if it's a tuple (or list)
        comand = list(command)
    if args:
        command.extend(args)
    if write_log:
        log('Running command: {}'.format(command))
    run_command = run(command, stderr=PIPE, stdout=stdout, shell=shell, env=env)
    if run_command.returncode != 0:
        if write_log:
            log('Command {}: Exit code {}\nSTDERR: {}'.format(
                run_command.args,
                run_command.returncode,
                run_command.stderr.decode()))
        raise ExecError(command, run_command.returncode)


def dilive_system(command, *args):
    """convenience function for di-live debconf related command execution
    - prepend compat to path
    - catch and log execution exception, exit with exitcode
    - stderr is redirected to the logfile by system()
    """
    prepend_path('/usr/lib/di-live/compat')
    try:
        system(command, *args)
    except ExecError as e:
        log(str(e))
        sys.exit(e.exitcode)


def preset_debconf(resets=None, preseeds=None, seen=None):
    debconf.runFrontEnd()
    db = debconf.Debconf()

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
        debconf.runFrontEnd()
        db = debconf.Debconf()

        db.capb('backup')
        db.input(debconf.CRITICAL, 'base-installer/no_target_mounted')
        db.go()
        return False

    return True
