# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
"""Common di-live functions and classes."""

import os
import subprocess
import sys
from subprocess import PIPE

import debconf

LOGFILE = "/var/log/di-live.log"


def log(msg: str) -> None:
    with open(LOGFILE, "a") as fob:
        fob.write(f"{msg}\n")


class Chroot:
    """Run commands inside a chroot."""

    def __init__(
        self, newroot: str, environ: dict[str, str] | None = None
    ) -> None:
        if environ is None:
            environ = {}
        # hack to allow exiting the chroot later - see rest in __del__()
        self.real_root = os.open("/", os.O_RDONLY)
        self.initial_cwd = os.getcwd()

        PATH = "/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/bin:/usr/sbin"
        self.environ = {
            "HOME": "/root",
            "TERM": os.environ["TERM"],
            "LC_ALL": "C",
            "PATH": PATH,
        }
        self.environ.update(environ)

        self.targetmounts = TargetMounts(newroot)

        # enter chroot and explicitly change to chroot's root; as python cwd
        # is not auto updated and python cwd may not exist in chroot
        os.chroot(newroot)
        os.chdir("/")

    def system(
        self,
        command: str | list[str],
        shell: bool = False,
        stdout: bool | None = None,
    ) -> None:
        """Leverages system function to execute command in chroot."""
        system(command, shell=shell, stdout=stdout, env=self.environ)

    def exit(self) -> None:
        # hack to escape python chroot and get back to initial cwd
        os.fchdir(self.real_root)
        os.chroot(".")
        os.chdir(self.initial_cwd)
        self.targetmounts.umount()

    def __del__(self) -> None:
        self.exit()


class DiliveDebconf:
    """debconf wrapper class to create new debconf dialogs and progress info.

    It can use existing di-live templates, or generate new ones dynamically
    using generic templates included in the di-live package.
    """

    def __init__(self, title: str | None = None) -> None:
        if title:
            self.db = debconf.Debconf(run_frontend=True, title=title)
        else:
            self.db = debconf.Debconf(run_frontend=True)
        self.db.capb("backup")

    def _db_input(
        self,
        template: str,
        description: str | None = None,
        default: str | None = None,
    ) -> str:
        self.db.reset(template)
        if description:
            self.db.subst(template, "DESCRIPTION", description)
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

    def get_input(
        self,
        template: str = "di-live/get-string",
        description: str | None = None,
        default: str | None = None,
    ) -> str:
        return self._db_input(template, description, default)

    def get_password(self, description: str, allow_empty: bool = False) -> str:
        while 1:
            password = self._db_input("di-live/password", description)
            if password == self._db_input("di-live/password_again"):
                if not password and not allow_empty:
                    self._db_input("di-live/password_empty")
                    continue

                break

            self._db_input("di-live/password_mismatch")

        return password

    def progress_init(
        self,
        steps: int,
        template: str = "di-live/progress/generic",
        description: str | None = None,
    ) -> None:
        if description:
            self.db.subst(template, "DESCRIPTION", description)
        self.progress_steps = steps
        self.db.progress(f"START 0 {steps} {template}")

    def progress_step(self, step_no: int) -> None:
        if step_no > self.progress_steps:
            return
        self.db.progress(f"STEP {step_no}")


class TargetMounts:
    """Set up and remove required mountpoints for a chroot."""

    def __init__(self, target: str = "/target") -> None:
        self.targetdev = os.path.join(target, "dev")
        self.targetproc = os.path.join(target, "proc")
        self.targetsys = os.path.join(target, "sys")
        self.targetrun = os.path.join(target, "run")
        self.mount()

    def mount(self) -> None:
        def _mount(primary_dir: str, secondary_dir: str) -> None:
            system(["mount", "-o", "bind", primary_dir, secondary_dir])

        if not is_mounted(self.targetdev):
            _mount("/dev", self.targetdev)
        if not is_mounted(self.targetproc):
            _mount("/proc", self.targetproc)
        if not is_mounted(self.targetsys):
            _mount("/sys", self.targetsys)

    def umount(self) -> None:
        def _umount(mounted_dir: str) -> None:
            system(["umount", "-f", mounted_dir])

        if is_mounted(self.targetsys):
            with open("/proc/mounts") as fob:
                for line in fob.readlines():
                    _host, guest, *_others = line.split(" ")
                    if (
                        guest.startswith(self.targetsys)
                        and not guest == self.targetsys
                    ):
                        _umount(guest)
            _umount(self.targetsys)
        if is_mounted(self.targetdev):
            _umount(self.targetdev)
        if is_mounted(self.targetproc):
            _umount(self.targetproc)
        if is_mounted(self.targetrun):
            _umount(self.targetrun)

    def __del__(self) -> None:
        self.umount()


class ExecError(Exception):
    """Accessible attributes:

    command     executed command
    exitcode    non-zero exitcode returned by command
    """

    def __init__(self, command: str, exitcode: int) -> None:
        Exception.__init__(self, command, exitcode)
        self.command = command
        self.exitcode = exitcode

    def __str__(self) -> str:
        return (
            f"non-zero exitcode ({self.exitcode}) for command: {self.command}"
        )


def prepend_path(path: str) -> None:
    os.environ["PATH"] = f"{path}:{os.getenv('PATH', '')}"


def system(
    command: str | list[str],
    shell: bool = False,
    stdout: bool | None = None,
    write_log: bool = True,
    env: dict[str, str] | None = None,
) -> None:
    """Execute command.

    If command returns non-zero exitcode raises ExecError

    command may either be:
     - a list containing individual items/arguments; or
     - if shell=True, a list containing a single string.
    """
    if env is None:
        env = dict(os.environ)
    if shell and isinstance(command, list):
        raise ExecError(f"command is a list ({command}) but shell=True", 1)
    elif not shell and isinstance(command, str):
        raise ExecError(f"command is a string ({command}) but shell=False", 1)
    log(f"Running command: {command}")
    run_command = subprocess.run(
        command, shell=shell, env=env, stderr=PIPE, stdout=stdout
    )
    if run_command.returncode != 0:
        if write_log:
            log(
                f"Command {run_command.args}: Exit code"
                f" {run_command.returncode}"
                f"\nSTDERR: {run_command.stderr.decode()}"
            )
        if isinstance(command, list):
            command = " ".join(command)
        raise ExecError(command, run_command.returncode)


def dilive_system(command: list[str]) -> None:
    """Di-live debconf related command execution.

    - command must be a list - and is passed to system()
    - prepend compat to path
    - catch and log execution exception, exit with exitcode
    - stderr is redirected to the logfile by system()
    """
    prepend_path("/usr/lib/di-live/compat")
    try:
        system(command)
    except ExecError as e:
        log(str(e))
        sys.exit(e.exitcode)


def preset_debconf(
    resets: list[str] | None = None,
    preseeds: list[tuple[str, int]] | None = None,
    seen: list[tuple[str, int]] | None = None,
) -> None:
    db = debconf.Debconf(run_frontend=True)

    if resets:
        for template in resets:
            db.reset(template)

    if preseeds:
        for template, value in preseeds:
            db.set(template, value)

    if seen:
        for template, value in seen:
            db.fset(template, "seen", value)


def is_mounted(directory: str) -> bool:
    with open("/proc/mounts") as fob:
        for line in fob.readlines():
            _host, guest, *_others = line.split(" ")
            if guest == directory:
                return True
    return False


def target_mounted(target: str = "/target") -> bool:
    if not os.path.exists(target) or not is_mounted(target):
        db = debconf.Debconf(run_frontend=True)
        db.capb("backup")
        db.input(debconf.CRITICAL, "base-installer/no_target_mounted")
        db.go()
        return False
    return True
