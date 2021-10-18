Debian di source code
=====================

This directory includes the Debian di source code which is used as a core
component of di-live.

Updating
--------

This repo is updated by updating the Debian source code first, then
patching/adjusting as required.

Thse commands should be run within the same directory as this file.

Find the 'repo' variable and check for the latest tag/release of each repo that
has a version number. I.e.:

- base-installer_
- debian-installer-utils_
- grub-installer_
- hw-detect_
- live-installer_ # Note currently using master
- partconf_ # Note currently using master
- partman-auto_
- partman-auto-lvm_
- partman-base_
- partman-basicfilesystems_
- partman-basicmethods_
- partman-ext3_
- partman-lvm_
- partman-partitioning_
- partman-target_
- preseed_

Once you have updated (where relevant), then commit and run the clone_and_copy.sh script::

    git add clone_and_copy.sh
    gc -m "Update clone_and_copy script with latest versions."
    ./clone_and_copy.sh

.. _baseinstaller: https://salsa.debian.org/installer-team/base-installer/-/tags
.. _debian-installer-utils: https://salsa.debian.org/installer-team/debian-installer-utils/-/tags
.. _grub-installer: https://salsa.debian.org/installer-team/grub-installer/-/tags
.. _hw-detect: https://salsa.debian.org/installer-team/hw-detect/-/tags
.. _live-installer: https://salsa.debian.org/installer-team/live-installer/-/tags
.. _partconf: https://salsa.debian.org/installer-team/partconf/-/tags
.. _partman-auto: https://salsa.debian.org/installer-team/partman-auto/-/tags
.. _partman-auto-lvm: https://salsa.debian.org/installer-team/partman-auto-lvm/-/tags
.. _partman-base: https://salsa.debian.org/installer-team/partman-base/-/tags
.. _partman-basicfilesystems: https://salsa.debian.org/installer-team/partman-basicfilesystems/-/tags
.. _partman-basicmethods: https://salsa.debian.org/installer-team/partman-basicmethods/-/tags
.. _partman-ext3: https://salsa.debian.org/installer-team/partman-ext3/-/tags
.. _partman-lvm: https://salsa.debian.org/installer-team/partman-lvm/-/tags
.. _partman-partitioning: https://salsa.debian.org/installer-team/partman-partitioning/-/tags
.. _partman-target: https://salsa.debian.org/installer-team/partman-target/-/tags
.. _preseed: https://salsa.debian.org/installer-team/preseed/-/tags
