#!/usr/bin/python3

import shutil
import subprocess
import sys
from os.path import basename
from typing import NoReturn

import debconf

DEBCONF_METHODS_TO_ADD = (
    # new line for debconf.pyi - line added will be:
    # f"   def {METHOD_TO_ADD} -> None: ..."
    "capb(self, arg: str)",
    "metaget(self, arg1: str, arg2: str)",
    "reset(self, arg: str)",
    "subst(self, arg1: str, arg2: str, arg3: str)",
    "input(self, arg1: str, arg2: str)",
    "go(self)",
    "get(self, arg: str)",
)


def fatal(msg: str) -> NoReturn:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    stubgen = shutil.which("stubgen")
    if stubgen is None:
        fatal("stubgen not found in PATH - please install 'mypy'")
    for py_file in ("di-live.d/common.py", debconf.__file__):
        stubs_file = f"stubs/{basename(py_file)}i"
        print(f"- '{stubs_file}'\t- regenerating type stub for {py_file}")
        stubgen_proc = subprocess.run(
            [stubgen, "--output=stubs", py_file],
            capture_output=True,
            text=True,
        )
        if stubgen_proc.returncode != 0:
            fatal(
                f"type stub generation failed:\n{stubgen_proc.stdout.strip()}"
            )
    # manually add Debconf methods used in di-live.py
    new_debconf_stub = []
    debconf_stub = f"stubs/{basename(debconf.__file__)}i"
    with open(debconf_stub) as fob:
        in_debconf_cls = False
        for line in fob:
            if not in_debconf_cls or line != "\n":
                new_debconf_stub.append(line)
            else:
                print(
                    f"- '{debconf_stub}'\t- adding dynamically generated"
                    " Debconf methods used by di-live (edit this script and"
                    " re-run if used methods change)"
                )
                for method_to_add in DEBCONF_METHODS_TO_ADD:
                    new_debconf_stub.append(
                        f"   def {method_to_add} -> None: ...\n"
                    )
                new_debconf_stub.append("\n")
                in_debconf_cls = False
            if line.startswith("class Debconf:"):
                in_debconf_cls = True
    with open(debconf_stub, "w") as fob:
        fob.writelines(new_debconf_stub)
    print(
        "Done: successfully regenerated type stubs (in 'stubs/') - please test"
        " by running 'mypy' and commit any changes as relevant"
    )


if __name__ == "__main__":
    main()
