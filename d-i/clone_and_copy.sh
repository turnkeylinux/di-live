#!/bin/bash -e

fatal() { echo "Fatal: $@" >&2; exit 1; }

clone_and_copy() {
	repo=$1
	ver=$2
	[[ -n "$repo" ]] || fatal "repo not set."
    [[ -n "$ver" ]] || fatal "ver not set."
    git clone --depth=1 --branch=$ver https://salsa.debian.org/installer-team/${repo}.git source/${repo}-src
    rm -r source/${repo}-src/.git
    cp -a source/${repo}-src/. source/${repo}
    rm -rf source/${repo}-src
    git add source/${repo}
    git commit -m "Commit updated ${repo} code (tag: $ver)." \
        || echo "nothing to commit, skipping to next."
}

# versions need to be updated from https://salsa.debian.org/installer-team
repos="	base-installer:1.206
        debian-installer-utils:1.140
        grub-installer:1.181
        hw-detect:1.147
        live-installer:master
        partconf:master
        partman-auto:157
        partman-auto-lvm:85
        partman-base:217
        partman-basicfilesystems:156
        partman-basicmethods:72
        partman-ext3:107
        partman-lvm:140
        partman-partitioning:140
        partman-target:122
        preseed:1.109"

for item in $repos; do
	repo=${item%:*}
	ver=${item#*:}
	clone_and_copy $repo $ver
done
