#!/usr/bin/python3

import argparse
import os
import shutil
import subprocess
from os.path import exists, isdir, join

packages = (
    "base-installer",
    "debian-installer-utils",
    "grub-installer",
    "hw-detect",
    "live-installer",
    "partconf",
    "partman-auto",
    # this was in original tkl di-live source, but not in Debina?
    # "partman-auto-loop",
    "partman-auto-lvm",
    "partman-base",
    "partman-basicfilesystems",
    "partman-basicmethods",
    "partman-ext3",
    "partman-lvm",
    "partman-partitioning",
    "partman-target",
    "preseed",
    "partman-efi",
)


class DiSrcError(Exception):
    pass


def clean_tmp_dir(force: bool = False) -> None:
    if force or not isdir("tmp"):
        shutil.rmtree("tmp", ignore_errors=True)
        os.makedirs("tmp")
        return
    tmp_dirs = [item.path for item in os.scandir("tmp") if item.is_dir()]
    if tmp_dirs:
        for tmp_dir in tmp_dirs:
            shutil.rmtree(tmp_dir)


def get_version(package: str, suite: str = "stable") -> str:
    rmadison_proc = subprocess.run(
        [
            "/usr/bin/rmadison",
            package,
            "--source-and-binary",
            "--architecture=amd64,all",
            f"--suite={suite}",
        ],
        capture_output=True,
        text=True,
    )
    if rmadison_proc.returncode != 0:
        raise DiSrcError(
            f"Failed to get '{package}' version:"
            f" {rmadison_proc.stderr.strip()}"
        )
    found_version = ""
    rmadison_stdout = rmadison_proc.stdout.strip()
    for line in rmadison_stdout.split("\n"):
        if line:
            # e.g.: bootstrap-base | 1.226 | stable | amd64
            _, version, _, _ = list(map(str.strip, line.split("|")))
            if not found_version:
                found_version = version
            elif found_version != version:
                raise DiSrcError(
                    f"Version mismatches for {package}: \n\n{rmadison_stdout}"
                )
    if not found_version:
        raise DiSrcError(f"No version found for {package}")
    return found_version


def clean_template(template_path: str, verbose: bool = False) -> None:
    """Remove translation related placeholders and comments."""
    def echo(msg: str) -> None:
        if verbose:
            print(msg)
    lines = []
    with open(template_path) as fob:
        for line in fob:
            if line.startswith("_"):
                if line.startswith("_Description:"):
                    line = line[1:]
                elif line.startswith("__Choices:"):
                    line = line[2:]
                if "[" in line:
                    echo("   * cleaning line:")
                    echo(f"    - {line}")
                    new_line = ""
                    for char in line:
                        if char == "[":
                            new_line = new_line + "\n"
                            break
                        new_line = new_line + char
                    line = new_line
                    echo("   * new line:")
                    echo(f"    - {line}")
            elif line.startswith("#"):
                if (
                    line.startswith("# :sl")
                    or line.startswith("#flag:translate")
                    or "translate" in line.lower()
                ):
                    echo("   * ignoring line:")
                    echo(f"    - {line}")
                    continue
            lines.append(line)
    with open(template_path, "w") as fob:
        fob.writelines(lines)


def get_src(package: str, version: str, verbose_clean: bool = False) -> None:
    os.makedirs("tmp", exist_ok=True)
    dsc = f"{package}_{version}.dsc"
    url = join(
        "http://deb.debian.org/debian/pool/main",
        f"{package[0]}",
        package,
        dsc,
    )
    dget_proc = subprocess.run(
        ["/usr/bin/dget", url], cwd="tmp", capture_output=True, text=True
    )
    if dget_proc.returncode == 2:
        raise DiSrcError(
            f"Error validating {dsc} - perhaps try importing the relevant keys"
            f":\n{dget_proc.stderr}"
        )
    elif dget_proc.returncode != 0:
        raise DiSrcError(
            f"Error downloading, verifying or unpacking {dsc}:"
            f"\n{dget_proc.stderr}"
        )
    local_src = join("d-i/source", package)
    if exists(local_src):
        shutil.rmtree(local_src)
    print(f"* Processing {package} source code")
    shutil.move(join("tmp", f"{package}-{version}"), local_src)
    for base, dirnames, filenames in os.walk(local_src):
        # remove translations - we only support english
        if "po" in dirnames:
            print(f"* Removing {package} translations")
            shutil.rmtree(join(base, "po"))
        for file in filenames:
            if file.endswith("templates"):
                template = join(base, file)
                print(f"* Cleaning {package} d-i template: {template}")
                clean_template(template, verbose=verbose_clean)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--suite",
        default="stable",
        help="suite or codename to download source package for (default:"
        " 'stable')",
    )
    parser.add_argument(
        "-f",
        "--force-download",
        action="store_true",
        help="force download of source packages (will reuse cached copies by"
        " if they exist by default)"
    )
    parser.add_argument(
        "-v",
        "--verbose-template-clean",
        action="store_true",
        help="enable verbose messages when cleaning templates - useful for"
        " debugging template issues"
    )
    args = parser.parse_args()
    clean_tmp_dir(force=args.force_download)
    for package in packages:
        print(f"* Checking for source package: {package}")
        version = get_version(package, args.suite)
        print(
            f"* Downloading and/or verfiying source package version: {version}"
        )
        get_src(package, version, verbose_clean=args.verbose_template_clean)


if __name__ == "__main__":
    main()
