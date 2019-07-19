#!/bin/sh

set -e
. /usr/share/debconf/confmodule
#set -x

if [ "$(uname)" != Linux ]; then
	exit 0
fi

# Install mmc modules if no other disks are found
# (ex: embedded device with µSD storage)
# TODO: more checks?
if [ -z "$(list-devices disk)" ]; then
	anna-install mmc-modules || true
fi

log () { 
	logger -t disk-detect "$@"
}

is_not_loaded() {
	! ((cut -d" " -f1 /proc/modules | grep -q "^$1\$") || \
	   (cut -d" " -f1 /proc/modules | sed -e 's/_/-/g' | grep -q "^$1\$"))
}

list_modules_dir() {
	if [ -d "$1" ]; then
		find $1 -type f | sed 's/\.ko$//; s/.*\///'
	fi
}

list_disk_modules() {
	# FIXME: not all of this stuff is disk driver modules, find a way
	# to separate out only the disk stuff.
	list_modules_dir /lib/modules/*/kernel/drivers/ide
	list_modules_dir /lib/modules/*/kernel/drivers/scsi
	list_modules_dir /lib/modules/*/kernel/drivers/block
	list_modules_dir /lib/modules/*/kernel/drivers/message/fusion
	list_modules_dir /lib/modules/*/kernel/drivers/message/i2o
}

disk_found() {
	for try in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
		if search-path parted_devices; then
			# Use partman's parted_devices if available.
			if [ -n "$(parted_devices)" ]; then
				return 0
			fi
		else
			# Essentially the same approach used by partitioner and
			# autopartkit to find their disks.
			if [ -n "$(list-devices disk)" ]; then
				return 0
			fi
		fi

		# Wait for disk to be activated.
		if [ "$try" != 15 ]; then
			sleep 2
		fi
	done

	return 1
}

module_probe() {
	local module="$1"
	local priority="$2"
	local modinfo=""
	local devs=""
	local olddevs=""
	local newdev=""
	
	if ! log-output -t disk-detect modprobe -v "$module"; then
		# Prompt the user for parameters for the module.
		local template="hw-detect/retry_params"
		local question="$template/$module"
		db_unregister "$question"
		db_register "$template" "$question"
		db_subst "$question" MODULE "$module"
		db_input critical "$question" || [ $? -eq 30 ]
		db_go
		db_get "$question"
		local params="$RET"

		if [ -n "$params" ]; then
			if ! log-output -t disk-detect modprobe -v "$module" $params; then
				db_unregister "$question"
				db_subst hw-detect/modprobe_error CMD_LINE_PARAM "modprobe -v $module $params"
				db_input critical hw-detect/modprobe_error || [ $? -eq 30 ]
				db_go
				false
			else
				# Module loaded successfully
				if [ "$params" != "" ]; then
					register-module "$module" "$params"
				fi
			fi
		fi
	fi
}

multipath_probe() {
	MP_VERBOSE=2
	# Look for multipaths...
	if [ ! -f /etc/multipath.conf ]; then
		cat <<EOF >/etc/multipath.conf
defaults {
    user_friendly_names yes
}
EOF
	fi
	log-output -t disk-detect /sbin/multipath -v$MP_VERBOSE

	if multipath -l 2>/dev/null | grep -q '^mpath[a-z]\+ '; then
		return 0
	else
		return 1
	fi
}

if ! hw-detect disk-detect/detect_progress_title; then
	log "hw-detect exited nonzero"
fi

while ! disk_found; do
	CHOICES=""
	for mod in $(list_disk_modules | sort); do
		CHOICES="${CHOICES:+$CHOICES, }$mod"
	done

	if [ -n "$CHOICES" ]; then
		db_capb backup
		db_subst disk-detect/module_select CHOICES "$CHOICES"
		db_input high disk-detect/module_select || [ $? -eq 30 ]
		if ! db_go; then
			exit 10
		fi
		db_capb

		db_get disk-detect/module_select
		if [ "$RET" = "continue with no disk drive" ]; then
			exit 0
		elif [ "$RET" != "none of the above" ]; then
			module="$RET"
			if [ -n "$module" ] && is_not_loaded "$module" ; then
				register-module "$module"
				module_probe "$module"
			fi
			continue
		fi
	fi

	if [ -e /usr/lib/debian-installer/retriever/media-retriever ]; then
		db_capb backup
		db_input critical hw-detect/load_media
		if ! db_go; then
			exit 10
		fi
		db_capb
		db_get hw-detect/load_media
		if [ "$RET" = true ] && \
		   anna media-retriever && \
		   hw-detect disk-detect/detect_progress_title; then
			continue
		fi
	fi

	db_capb backup
	db_input high disk-detect/cannot_find
	if ! db_go; then
		exit 10
	fi
	db_capb
done

# Activate support for Serial ATA RAID
db_get disk-detect/dmraid/enable
if [ "$RET" = true ]; then
	if anna-install dmraid-udeb; then
		# Device mapper support is required to run dmraid
		if is_not_loaded dm-mod; then
			module_probe dm-mod || true
		fi

		if dmraid -c -s >/dev/null 2>&1; then
			logger -t disk-detect "Serial ATA RAID disk(s) detected; enabling dmraid support"
			# Activate only those arrays which have all disks
			# present.
			for dev in $(dmraid -r -c); do
				[ -e "$dev" ] || continue
				log-output -t disk-detect dmraid-activate "$(basename "$dev")"
			done
		else
			logger -t disk-detect "No Serial ATA RAID disks detected"
		fi
	fi
fi

# Activate support for DM Multipath
db_get disk-detect/multipath/enable
if [ "$RET" = true ]; then
	if anna-install multipath-udeb; then
		MODULES="dm-mod dm-multipath dm-round-robin"
		# We need some dm modules...
		depmod -a >/dev/null 2>&1 || true
		for MODULE in $MODULES; do
			if is_not_loaded $MODULE; then
				module_probe $MODULE || true
			fi
		done

		# ensure multipath and sg3 udev rules are run before we probe
                # to see if there are new devices.
		update-dev >/dev/null

		# Look for multipaths...
		if multipath_probe; then
			logger -t disk-detect "Multipath devices found; enabling multipath support"
			if ! anna-install partman-multipath; then
				/sbin/multipath -F
				logger -t disk-detect "Error loading partman-multipath; multipath devices deactivated"
			fi
		else
			logger -t disk-detect "No multipath devices detected"
		fi
	fi
fi

check-missing-firmware
