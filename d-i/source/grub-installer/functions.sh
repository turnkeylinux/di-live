# Make sure mtab in the chroot reflects the currently mounted partitions.
update_mtab_procfs() {
	grep "$ROOT" /proc/mounts | (
	while read devpath mountpoint fstype options n1 n2 ; do
		devpath=`mapdevfs $devpath || echo $devpath`
		mountpoint=`echo $mountpoint | sed "s%^$ROOT%%"`
		# The sed line removes the mount point for root.
		if [ -z "$mountpoint" ] ; then
			mountpoint="/"
		fi
		echo $devpath $mountpoint $fstype $options $n1 $n2
	done ) > $mtab
}

# No /proc/mounts available, build one (Hurd)
update_mtab_scratch() {
	echo "$rootfs / $rootfstype defaults 0 1" > $mtab
	if [ "$bootfs" != "$rootfs" ]; then
		echo "$bootfs /boot $bootfstype defaults 0 2" >> $mtab
	fi
}

update_mtab() {
	[ "$ROOT" ] || return 0

	[ ! -h "$ROOT/etc/mtab" ] || return 0

	mtab=$ROOT/etc/mtab

	if [ -e /proc/mounts ]; then
		update_mtab_procfs
	else
		update_mtab_scratch
	fi
}

is_floppy () {
	echo "$1" | grep -q '(fd' || echo "$1" | grep -q "/dev/fd" || echo "$1" | grep -q floppy
}

log () {
	logger -t grub-installer "$*${DEBCONF_DEBUG:+		[${0##*/}]}"
}

error () {
	log "error: $*"
}

info() {
	log "info: $*"
}

debug () {
	[ -z "${DEBCONF_DEBUG}" ] || log "debug: $*"
}

die () {
	local template="$1" ; shift
	local fstype="$1" ; shift
	local path="$1" ; shift


	error "$@"
	db_subst "$template" FSTYPE "$fstype"
	db_subst "$template" PATH "$path"
	db_input critical "$template" || [ $? -eq 30 ]
	db_go || true
	exit 1
}

# on_exit() takes a command, and pushes it onto a stack of commands, which
# are later executed by perform_exit_stack() (via trap) in LIFO order.
EXIT_STACK=""
on_exit() {
	if [ 1 != $# ]; then
		error "$0: on_exit() expects exactly 1 argument, but was given $# ${*:+(args:$(printf " [%s]" "$@"))}"
		exit 1
	fi
	EXIT_STACK=$(printf '%s\n%s' "$1" "$EXIT_STACK")
}

perform_exit_stack () {
	printf '%s\n' "$EXIT_STACK" | \
		while read -r cmd; do
			debug "perform_exit_stack(): Running \"$cmd\""
			eval "$cmd" || info "attempt to run \"$cmd\" failed [$?] when exiting \"$0\" (non-fatal)"
		done
	debug "perform_exit_stack(): exiting \"$0\""
}
trap perform_exit_stack HUP INT QUIT KILL PIPE TERM EXIT

mountvirtfs () {
	fstype="$1"
	path="$2"
	failure_response="${3:-fatal}"

	if grep -q "[[:space:]]$fstype\$" /proc/filesystems && \
	   ! grep -q "^[^ ]\+ \+$path " /proc/mounts; then
		if mkdir -p "$path"; then
			if mount -t "$fstype" "$fstype" "$path"; then
				log "Success mounting $path"
				on_exit "umount '$path'"
				return
			else
				failed_action="Mounting"
			fi
		else
			failed_action="Creating"
		fi

		log_msg="$failed_action '$path' failed ($failure_response error)"
		# if here, a failure has occured (otherwise would 'return' above)
		if [ "$failure_response" != "fatal" ]; then
			info "$log_msg"
		else
			die grub-installer/mounterr "$fstype" "$path" "$log_msg"
		fi
	fi
}
