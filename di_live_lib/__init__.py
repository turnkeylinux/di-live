# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Copyright (c) 2009-2025 TurnKey GNU/Linux <admin@turnkeylinux.org>

import logging
import os
import subprocess
import sys
from collections.abc import Sequence

import debconf

PIPE = subprocess.PIPE
LOG_FILE = "/var/log/di-live.log"


def setup_logging(
    log_file: str = LOG_FILE,
    log_level: int | None = None,
) -> logging.Logger:
    """Configure di-live logging - call once per 'di-live.d/' script."""
    if log_level is None:
        log_level = int(
            os.getenv("DEBUG", os.getenv("DILIVE_DEBUG", logging.INFO))
        )
    logger = logging.getLogger()
    # ensure no duplicate handlers - just in case...
    if logger.handlers:
        return logger
    logger.setLevel(log_level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d"
        " - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


# module logger for these common functions/classes
logger = logging.getLogger(__name__)


class Chroot:
    """Run commands inside a chroot."""

    def __init__(
        self, newroot: str, environ: dict[str, str] | None = None
    ) -> None:
        logger.debug(f"Chroot.__init__({newroot=}, {environ=})")
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
        stdout: int | None = None,
    ) -> None:
        """Leverages system function to execute command in chroot."""
        logger.debug(f"Chroot.system({command=}, {shell=}, {stdout=})")
        system(command, shell=shell, stdout=stdout, env=self.environ)

    def exit(self) -> None:
        # hack to escape python chroot and get back to initial cwd
        logger.debug("Chroot.exit()")
        os.fchdir(self.real_root)
        os.chroot(".")
        os.chdir(self.initial_cwd)
        self.targetmounts.umount()

    def __del__(self) -> None:
        logger.debug("Chroot.__del__()")
        self.exit()


class DiliveDebconf:
    """debconf wrapper class to create new debconf dialogs and progress info.

    It can use existing di-live templates, or generate new ones dynamically
    using generic templates included in the di-live package.
    """

    def __init__(self, title: str | None = None) -> None:
        logger.debug(f"DiliveDebconf.__init__({title=})")
        if title:
            self.db = debconf.Debconf(run_frontend=True, title=title)
        else:
            self.db = debconf.Debconf(run_frontend=True)
        logger.debug('DiliveDebconf.db.capb("backup")')
        self.db.capb("backup")

    def _db_input(
        self,
        template: str,
        description: str | None = None,
        default: str | None = None,
    ) -> str:
        logger.debug(
            f"DiliveDebconf._db_input({template=}, {description=}, {default=})"
        )
        logger.debug(f"DiliveDebconf.db.reset({template})")
        self.db.reset(template)
        if description:
            logger.debug(
                f"DiliveDebconf.db.subst('{template}', 'DESCRIPTION',"
                f" '{description}')"
            )
            self.db.subst(template, "DESCRIPTION", description)
        if default:
            logger.debug(f"DiliveDebconf.db.set('{template}', '{default}')")
            self.db.set(template, default)
        logger.debug(f"DiliveDebconf.db.input({debconf.HIGH}, {template})")
        self.db.input(debconf.HIGH, template)
        try:
            logger.debug("DiliveDebconf.db.go()")
            self.db.go()
        except debconf.DebconfError as e:
            logger.debug("DiliveDebconf.db.stop()")
            self.db.stop()
            sys.exit(e.args[0])

        ret = self.db.get(template)
        logger.debug(f"DiliveDebconf.db.reset({template})")
        self.db.reset(template)
        return ret

    def get_input(
        self,
        template: str = "di-live/get-string",
        description: str | None = None,
        default: str | None = None,
    ) -> str:
        logger.debug(
            f"DiliveDebconf.get_input({template=}, {description=}, {default=})"
        )
        return self._db_input(template, description, default)

    def get_password(self, description: str, allow_empty: bool = False) -> str:
        logger.debug(
            f"DiliveDebconf.get_password({description=}, {allow_empty=})"
        )
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
        logger.debug(
            f"DiliveDebconf.progress_init({steps=}, {template=},"
            f" {description=})"
        )
        if description:
            logger.debug(
                f"DiliveDebconf.db.subst('{template}', 'DESCRIPTION',"
                f" '{description}')"
            )
            self.db.subst(template, "DESCRIPTION", description)
        self.progress_steps = steps
        progress = f"START 0 {steps} {template}"
        logger.debug(f"DiliveDebconf.db.progress({progress})")
        self.db.progress(progress)

    def progress_step(self, step_no: int) -> None:
        logger.debug(f"DiliveDebconf.progress_step({step_no=})")
        if step_no > self.progress_steps:
            return
        progress = f"STEP {step_no}"
        logger.debug(f"DiliveDebconf.db.progress({progress})")
        self.db.progress(progress)


class TargetMounts:
    """Set up and remove required mountpoints for a chroot."""

    def __init__(self, target: str = "/target") -> None:
        logger.debug(f"TargetMounts.__init__({target=})")
        self.targetdev = os.path.join(target, "dev")
        self.targetproc = os.path.join(target, "proc")
        self.targetsys = os.path.join(target, "sys")
        self.targetrun = os.path.join(target, "run")
        self.mount()

    def mount(self) -> None:
        logger.debug("TargetMounts.mount()")
        def _mount(primary_dir: str, secondary_dir: str) -> None:
            system(["mount", "-o", "bind", primary_dir, secondary_dir])

        if not is_mounted(self.targetdev):
            _mount("/dev", self.targetdev)
        if not is_mounted(self.targetproc):
            _mount("/proc", self.targetproc)
        if not is_mounted(self.targetsys):
            _mount("/sys", self.targetsys)

    def umount(self) -> None:
        logger.debug("TargetMounts.umount()")
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
        logger.debug("TargetMounts.__del__()")
        self.umount()


class ExecError(Exception):
    """Accessible attributes:

    command     executed command
    exitcode    non-zero exitcode returned by command
    """

    def __init__(self, command: str, exitcode: int) -> None:
        logger.debug(f"ExecError.__init__({command=}, {exitcode=})")
        Exception.__init__(self, command, exitcode)
        self.command = command
        self.exitcode = exitcode

    def __str__(self) -> str:
        return (
            f"non-zero exitcode ({self.exitcode}) for command: {self.command}"
        )


def prepend_path(path: str) -> None:
    logger.debug(f"prepend_path({path=})")
    os.environ["PATH"] = f"{path}:{os.getenv('PATH', '')}"


def system(
    command: str | list[str],
    shell: bool = False,
    stdout: int | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Execute command.

    If command returns non-zero exitcode raises ExecError

    command may either be:
     - a list containing individual items/arguments; or
     - if shell=True, a list containing a single string.
    """
    logger.debug(f"system({command=}, {shell=}, {stdout=}, {env=})")
    if env is None:
        env = dict(os.environ)
    if shell and isinstance(command, list):
        raise ExecError(f"command is a list ({command}) but shell=True", 1)
    elif not shell and isinstance(command, str):
        raise ExecError(f"command is a string ({command}) but shell=False", 1)
    logger.info(f"Running command: {command}")
    run_command = subprocess.run(
        command, shell=shell, env=env, stderr=PIPE, stdout=stdout
    )
    if run_command.returncode != 0:
        logger.info(
            f"Command {run_command.args}: Exit code {run_command.returncode}"
            f"\n\tSTDERR: {run_command.stderr.decode()}"
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
    logger.debug(f"dilive_system({command=})")
    prepend_path("/usr/lib/di-live/compat")
    try:
        system(command)
    except ExecError as e:
        logger.info(str(e))
        sys.exit(e.exitcode)


def preset_debconf(
    resets: list[str] | None = None,
    preseeds: Sequence[tuple[str, str | bool]] | None = None,
    seen: list[tuple[str, bool]] | None = None,
) -> None:
    logger.debug(f"preset_debconf({resets=}, {preseeds=}, {seen=})")
    db = debconf.Debconf(run_frontend=True)

    if resets:
        for template in resets:
            logger.debug(f"debconf.Debconf().reset({template=})")
            db.reset(template)

    if preseeds:
        for template, value in preseeds:
            logger.debug(f"debconf.Debconf().set({template=}, {value=})")
            db.set(template, value)

    if seen:
        for template, value in seen:
            logger.debug(
                f"debconf.Debconf().fset({template=}, 'seen', {value=})"
            )
            db.fset(template, "seen", value)


def is_mounted(directory: str) -> bool:
    logger.debug(f"is_mounted({directory})")
    with open("/proc/mounts") as fob:
        for line in fob.readlines():
            _host, guest, *_others = line.split(" ")
            if guest == directory:
                return True
    return False


def target_mounted(target: str = "/target") -> bool:
    logger.debug(f"target_mounted({target=})")
    if not os.path.exists(target) or not is_mounted(target):
        db = debconf.Debconf(run_frontend=True)
        dconf = "debconf.Debconf()"
        logger.debug(f"{dconf}.capb('backup')")
        db.capb("backup")
        logger.debug(
            f"{dconf}.input({debconf.CRITICAL},"
            " 'base-installer/no_target_mounted')"
        )
        db.input(debconf.CRITICAL, "base-installer/no_target_mounted")
        logger.debug(f"{dconf}.go()")
        db.go()
        return False
    return True
