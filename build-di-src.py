#!/usr/bin/python3

import argparse
import os
import shutil
import subprocess
from os.path import exists, join

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


def get_src(package: str, version: str) -> None:
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
    shutil.move(join("tmp", f"{package}-{version}"), local_src)
    for base, dirnames, filenames in os.walk(local_src):
        if "po" in dirnames:
            shutil.rmtree(join(base, "po"))
        for file in filenames:
            if file.endswith("templates"):
                file = join(base, file)
                lines = []
                with open(file) as fob:
                    for line in fob:
                        if line.startswith("_"):
                            line = line[1:]
                        elif line.startswith("#"):
                            continue
                        lines.append(line)
                with open(file, "w") as fob:
                    fob.writelines(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--suite",
        default="stable",
        help="suite or codename to download source package for (default:"
        " 'stable')",
    )
    args = parser.parse_args()
    for package in packages:
        print(f"Checking for source package: {package}")
        version = get_version(package, args.suite)
        print(f"Downloading source package version: {version}")
        get_src(package, version)


if __name__ == "__main__":
    main()
