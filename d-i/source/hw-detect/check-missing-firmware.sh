#!/bin/sh
set -e
. /usr/share/debconf/confmodule

DENIED=/tmp/missing-firmware-denied

if [ "x$1" = "x-n" ]; then
	NONINTERACTIVE=1
	shift
else
	NONINTERACTIVE=""
fi

IFACES="$@"

log () {
	logger -t check-missing-firmware "$@"
}

log_output() {
	log-output -t check-missing-firmware "$@"
}

# USB is special, and we don't want to take it all done:
get_usb_module() {
	address="$1"
	device="/sys/bus/usb/devices/$address"

	# Make sure there's a single subdirectory (e.g. 4-1.5:1.0 below 4-1.5):
	subdirs=$(find -L "$device" -maxdepth 1 -type d -name "$address:*")
	subdirs_n=$(echo "$subdirs" | wc -w)
	if [ $(echo "$subdirs" | wc -w) != 1 ]; then
		log "failed to perform usb $address lookup (got: $subdirs_n entries, expected: 1)"
		log "=> sticking with the usb module"
		echo 'usb'
		return
	fi

	# Make sure driver resolution returns something:
	driver=$(basename $(readlink "$subdirs/driver") 2>/dev/null)
	if [ "$driver" = "" ]; then
		log "failed to perform usb $address lookup (no driver found)"
		log "=> sticking with the usb module"
		echo 'usb'
		return
	fi
	echo $driver
}

# MHI is special, but different from USB; at least with ath11k_pci,
# /sys/bus/mhi/devices/mhi0* doesn't list anything ath11k-related.
# The mhi module's holders directory lists ath11k_pci and qrtr_mhi
# though!
get_mhi_holders() {
	holders=$(find -L /sys/module/mhi/holders/ -mindepth 1 -maxdepth 1 -exec basename {} ';')
	if [ "$holders" = "" ]; then
		log "failed to perform mhi lookup (no holders found)"
		log "=> sticking with the mhi module"
		echo 'mhi'
	else
		echo $holders
	fi
}

# Some modules only try to load firmware once brought up. So bring up and
# then down any interfaces specified by ethdetect. Don't touch interfaces
# that users might have configured (manually or via preseeding) though!
upnics() {
	for iface in $IFACES; do
		# Don't rely on ip's output, it lacks at least state UP/DOWN:
		sys_iface="/sys/class/net/$iface"
		if grep -qs ^up$ "$sys_iface/operstate"; then
			log "leaving network interface $iface alone (state=up)"
			continue
		elif [ -e "$sys_iface/master" ]; then
			# Most likely bonding:
			master=$(basename $(readlink "$sys_iface/master") 2>/dev/null)
			log "leaving network interface $iface alone (master=${master:-<unknown>})"
			continue
		fi
		log "taking network interface $iface up/down"
		ip link set "$iface" up || true
		ip link set "$iface" down || true
	done
}

# Checks if a given module is a nic module and has an interface that
# is up and has an IP address. Such modules should not be reloaded,
# to avoid taking down the network after it's been configured.
nic_is_configured() {
	module="$1"

	for iface in $(ip -o link show up | cut -d : -f 2); do
		dir="/sys/class/net/$iface/device/driver"
		if [ -e "$dir" ] && [ "$(basename "$(readlink "$dir")")" = "$module" ]; then
			if ip address show scope global dev "$iface" | grep -q 'scope global'; then
				return 0
			fi
		fi
	done

	return 1
}

get_fresh_dmesg() {
	dmesg_file=/tmp/dmesg.txt
	dmesg_ts=/tmp/dmesg-ts.txt

	# Get current dmesg:
	dmesg > $dmesg_file

	# Truncate if needed:
	if [ -f $dmesg_ts ]; then
		# Transform [foo] into \[foo\] to make it possible to search for
		# "^$tspattern" (-F for fixed string doesn't play well with ^ to
		# anchor the pattern on the left):
		tspattern=$(cat $dmesg_ts | sed 's,\[,\\[,;s,\],\\],')
		log "looking at dmesg again, restarting from timestamp: $(cat $dmesg_ts)"

		# Find the line number for the first match, empty if not found:
		ln=$(grep -n "^$tspattern" $dmesg_file |sed 's/:.*//'|head -n 1)
		if [ ! -z "$ln" ]; then
			log "timestamp found, truncating dmesg accordingly"
			sed -i "1,$ln d" $dmesg_file
		else
			log "timestamp not found, using whole dmesg"
		fi
	else
		log "looking at dmesg for the first time"
	fi

	if [ -s $dmesg_file ]; then
		# Save the last timestamp:
		grep -o '^\[ *[0-9.]\+\]' $dmesg_file | tail -n 1 > $dmesg_ts
		log "saving timestamp for a later use: $(cat $dmesg_ts)"
	else
		log "keeping timestamp (no new lines): $(cat $dmesg_ts)"
	fi

	# Write and clean-up:
	cat $dmesg_file
	rm $dmesg_file
}

check_missing () {
	upnics

	# Give modules some time to request firmware.
	sleep 1

	modules=""
	files=""

	# Parse dmesg using a started parttern to detect firmware
	# files the kernel drivers look for (#725714):
	fwlist=/tmp/check-missing-firmware-dmesg.list
	get_fresh_dmesg | sed -rn 's/^(\[[^]]*\] )?([^ ]+) ([^ ]+): firmware: failed to load ([^ ]+) .*/\2 \3 \4/p' > $fwlist
	while read module address fwfile ; do
	    # rewrite module is necessary
	    case "$module" in
		usb)
		    module=$(get_usb_module "$address")
		    log "using module $module instead of usb $address"
		;;
		mhi)
		    module=$(get_mhi_holders)
		    log "using $module instead of mhi"
		;;
	    esac

	    # ignore specific files:
	    #  - iwlwifi, debug-only (#969264, #966218)
	    if [ "$fwfile" = "iwl-debug-yoyo.bin" ]; then
		log "ignoring firmware file $fwfile requested by $module"
		continue
	    fi

	    log "looking for firmware file $fwfile requested by $module"
	    if [ ! -e /lib/firmware/$fwfile ] ; then
		if grep -q "^$fwfile$" $DENIED 2>/dev/null; then
		    log "listed in $DENIED"
		    continue
		fi
		files="${files:+$files }$fwfile"
		modules="$module${modules:+ $modules}"
	    fi
	done < $fwlist

	if [ -n "$modules" ]; then
		# Uniquify since a single module may request *many* firmware files,
		# and a file might be requested several times:
		modules=$(echo $modules | tr " " "\n" | sort -u)
		files=$(echo $files | tr " " "\n" | sort -u)
		log "missing firmware files ($files) for $modules"
		return 0
	else
		log "no missing firmware in loaded kernel modules"
		return 1
	fi
}

# If found, copy firmware file; preserve subdirs.
try_copy () {
	local fwfile=$1
	local sdir file f target

	sdir=$(dirname $fwfile | sed "s/^\.$//")
	file=$(basename $fwfile)
	for f in "/media/$fwfile" "/media/firmware/$fwfile" \
		 ${sdir:+"/media/$file" "/media/firmware/$file"}; do
		if [ -e "$f" ]; then
			target="/lib/firmware${sdir:+/$sdir}"
			log "copying loose file $file from '$(dirname $f)' to '$target'"
			mkdir -p "$target"
			rm -f "$target/$file"
			cp -aL "$f" "$target" || true
			break
		fi
	done
}

first_try=1
first_ask=1
ask_load_firmware () {
	if [ "$first_try" ]; then
		first_try=""
		return 0
	fi

	if [ "$NONINTERACTIVE" ]; then
		if [ ! "$first_ask" ]; then
			return 1
		else
			first_ask=""
			return 0
		fi
	fi

	db_subst hw-detect/load_firmware FILES "$files"
	if ! db_input high hw-detect/load_firmware; then
		if [ ! "$first_ask" ]; then
			exit 1;
		else
			first_ask=""
		fi
	fi
	if ! db_go; then
		exit 10 # back up
	fi
	db_get hw-detect/load_firmware
	if [ "$RET" = true ]; then
		return 0
	else
		echo "$files" | tr ' ' '\n' >> $DENIED
		return 1
	fi
}

list_deb_firmware () {
	udpkg -c "$1" \
		| grep '^\./lib/firmware/' \
		| sed -e 's!^\./lib/firmware/!!' \
		| grep -v '^$'
}

check_deb_arch () {
	arch=$(udpkg -f "$1" | grep '^Architecture:' | sed -e 's/Architecture: *//')
	[ "$arch" = all ] || [ "$arch" = "$(udpkg --print-architecture)" ]
}

get_deb_component () {
	# This trusts the contents of the .deb, but packages in the archive could
	# have overrides (controlled by ftpmaster):
	section=$(udpkg -f "$1" | grep '^Section:' | sed -e 's/Section: *//')
	if ! echo "$section" | grep -qs '/'; then
		echo "main"
	else
		echo "$section" | sed 's,/.*,,'
	fi
}

# Remove non-accepted firmware package
remove_pkg() {
	pkgname="$1"
	# Remove all files listed in /var/lib/dpkg/info/$pkgname.md5sums
	for file in $(cut -d" " -f 2- /var/lib/dpkg/info/$pkgname.md5sums) ; do
		rm /$file
	done
}

install_firmware_pkg () {
	# cache deb for installation into /target later
	mkdir -p /var/cache/firmware/
	cp -aL "$1" /var/cache/firmware/ || true
	filename="$(basename "$1")"
	pkgname="$(udpkg -f "$1" | grep '^Package:' | sed -e 's/^Package: *//')"
	udpkg --unpack "/var/cache/firmware/$filename"
	if [ -f /var/lib/dpkg/info/$pkgname.preinst ] ; then
		# Run preinst script to see if the firmware
		# license is accepted Exit code of preinst
		# decide if the package should be installed or
		# not.
		if /var/lib/dpkg/info/$pkgname.preinst ; then
			:
		else
			remove_pkg "$pkgname"
			rm "/var/cache/firmware/$filename"
			removed=1
		fi
	fi
	if [ "$removed" != 1 ]; then
		echo "$2" >> /var/cache/firmware/components
		echo "$pkgname $2 dmesg" >> /var/log/firmware-summary
	fi
}

# Try to load debs that contain the missing firmware.
# This does not use anna because debs can have arbitrary
# dependencies, which anna might try to install.
check_for_firmware() {
	echo "$files" | sed -e 's/ /\n/g' >/tmp/grepfor
	for dir in $@; do
		# An index file might exist, mapping firmware files to firmware
		# packages, saving us from iterating over each firmware *.deb:
		if [ -f $dir/Contents-firmware ]; then
			log "lookup with $dir/Contents-firmware"
			# Duplicating stdin makes license prompts work again (#1033921). The
			# workaround is meant for Bookworm, but this should be reconsidered
			# (#1035356, #1029843).
			{
			grep -f /tmp/grepfor $dir/Contents-firmware | while read fw_file fw_pkg_file component; do
				# Don't install a package for each file it ships!
				if grep -qs "^$fw_pkg_file$" /tmp/pkginstalled 2>/dev/null; then
					continue
				fi
				if check_deb_arch "$dir/$fw_pkg_file"; then
					log "installing firmware package $dir/$fw_pkg_file ($component)"
					install_firmware_pkg "$dir/$fw_pkg_file" "$component" <&9 || true
					echo "$fw_pkg_file" >> /tmp/pkginstalled
				fi
			done
			} 9<&0
			continue
		fi

		# If no such index exists, fall back to iterating over everyone:
		log "lookup without $dir/Contents-firmware"
		for filename in $dir/*.deb; do
			if [ -f "$filename" ]; then
				if check_deb_arch "$filename" && list_deb_firmware "$filename" | grep -qf /tmp/grepfor; then
					log "installing firmware package $filename"
					install_firmware_pkg "$filename" $(get_deb_component "$filename") || true
				fi
			fi
		done
	done
	rm -f /tmp/grepfor
	rm -f /tmp/pkginstalled
}

# For those who don't want to load any firmware, even if available on
# installation images (#1029848). The loop is still entered so that
# logs are generated.
db_get hw-detect/firmware-lookup
firmware_lookup="$RET"

# NOTE: The ask_load_firmware function returns true the first time around,
# without asking any questions. For consistency, skip mountmedia calls during
# the first iteration of the loop. For systems which have all firmware material
# found in {,/cdrom}/firmware, this also means a noticeable speed-up.
loop=0
while check_missing && ask_load_firmware; do
	loop=$((loop+1))
	log "mainloop iteration #$loop"

	if [ "$firmware_lookup" = "never" ]; then
		log "firmware lookup disabled (=$firmware_lookup), exiting"
		exit 0
	fi

	# first, check if needed firmware debs are available on the
	# PXE initrd or the installation CD.
	if [ -d /firmware ]; then
		check_for_firmware /firmware
	fi
	if [ -d /cdrom/firmware ]; then
		check_for_firmware /cdrom/firmware
	fi

	# Whether we should keep both mountmedia calls, and whether mountmedia
	# is doing a good job is discussed in #1029543:
	if [ "$loop" -gt 1 ]; then
		# second, look for loose firmware files on the media device.
		if mountmedia; then
			for file in $files; do
				try_copy "$file"
			done
			umount /media || true
		fi

		# last, look for firmware debs on the media device
		if mountmedia driver; then
			check_for_firmware /media /media/firmware
			umount /media || true
		fi
	fi

	# remove and reload modules so they see the new firmware
	for module in $modules; do
		if ! nic_is_configured $module; then
			log "removing and loading kernel module $module"
			log_output modprobe -r $module || true
			log_output modprobe $module || true

			# iterate to avoid dealing with multiplicity explicitly:
			for driver in $(find /sys/bus/*/drivers -name "$module"); do
				# module name mentioned in dmesg might differ from the actual module
				# (rtw_8821ce vs. rtw88_8821ce, see #973733); also beware of the
				# module symlink, it doesn't always exist:
				if [ -e "$driver/module" ]; then
					actual_module=$(basename $(readlink -f "$driver/module"))
					if [ "$actual_module" != "$module" ]; then
						log "removing and loading kernel module $actual_module as well (actual module for $module)"
						log_output modprobe -r $actual_module || true
						log_output modprobe $actual_module || true
					fi
				fi
			done
		fi
	done
done
