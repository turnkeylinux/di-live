## Shared code for all guided partitioning components

auto_init_disk() {
	local dev
	dev="$1"

	# Create new disk label; don't prompt for label
	. /lib/partman/lib/disk-label.sh
	create_new_label "$dev" no || return 1

	cd $dev

	free_space=''
	open_dialog PARTITIONS
	while { read_line num id size type fs path name; [ "$id" ]; }; do
		if [ "$fs" = free ]; then
			free_space=$id
			free_size=$size
			free_type=$type
		fi
	done
	close_dialog
}

# Each disk must have at least one primary partition after autopartitioning.
ensure_primary() {
	if echo "$scheme" | grep -q '\$primary{'; then
		# Recipe provides one primary partition
		return
	fi

	cd $dev

	open_dialog PARTITIONS
	local have_primary=
	local id type
	while { read_line x1 id x2 type x3 x4 x5; [ "$id" ]; }; do
		if [ "$type" = primary ]; then
			have_primary=1
		fi
	done
	close_dialog

	if [ "$have_primary" ]; then
		# Existing disk provides one primary partition
		return
	fi

	# Neither disk nor recipe provides a primary partition. Force the
	# first partition in the recipe (arbitrarily chosen) to be primary.
	scheme="$(
		local first=1
		foreach_partition '
			if [ "$first" ]; then
				echo "$* \$primary{ }"
				first=
			else
				echo "$*"
			fi'
	)"
}

### XXXX: I am not 100% sure if this is exactly what this code is doing.
### XXXX: Rename is of course an option. Just remember to do it here, in
### XXXX: perform_recipe and in partman-auto-lvm.
create_primary_partitions() {
	cd $dev

	while [ "$free_type" = pri/log ] && \
	      echo $scheme | grep '\$primary{' >/dev/null; do
		pull_primary
		set -- $primary
		open_dialog NEW_PARTITION primary $4 $free_space beginning ${1}000001
		read_line num id size type fs path name
		close_dialog
		if [ -z "$id" ]; then
			db_progress STOP
			autopartitioning_failed
		fi
		neighbour=$(partition_after $id)
		if [ "$neighbour" ]; then
			open_dialog PARTITION_INFO $neighbour
			read_line x1 new_free_space x2 new_free_type fs x3 x4
			close_dialog
		fi
		if [ -z "$neighbour" ] || [ "$fs" != free ] || \
		   [ "$new_free_type" = primary ] || \
		   [ "$new_free_type" = unusable ]; then
			open_dialog DELETE_PARTITION $id
			close_dialog
			open_dialog NEW_PARTITION primary $4 $free_space end ${1}000001
			read_line num id size type fs path name
			close_dialog
			if [ -z "$id" ]; then
				db_progress STOP
				autopartitioning_failed
			fi
			neighbour=$(partition_before $id)
			if [ "$neighbour" ]; then
				open_dialog PARTITION_INFO $neighbour
				read_line x1 new_free_space x2 new_free_type fs x3 x4
				close_dialog
			fi
			if [ -z "$neighbour" ] || [ "$fs" != free ] ||
			   [ "$new_free_type" = unusable ]; then
				open_dialog DELETE_PARTITION $id
				close_dialog
				break
			fi
		fi
		shift; shift; shift; shift
		setup_partition $id $*
		primary=''
		scheme="$logical"
		free_space=$new_free_space
		free_type="$new_free_type"
	done
}

create_partitions() {
    foreach_partition '
	if [ -z "$free_space" ]; then
		db_progress STOP
		autopartitioning_failed
	fi
	open_dialog PARTITION_INFO $free_space
	read_line x1 free_space x2 free_type fs x3 x4
	close_dialog
	if [ "$fs" != free ]; then
		free_type=unusable
	fi

	case "$free_type" in
	    primary|logical)
		type="$free_type"
		;;
	    pri/log)
		type=logical
		;;
	    unusable)
		db_progress STOP
		autopartitioning_failed
		;;
	esac

	if [ "$last" = yes ]; then
		open_dialog NEW_PARTITION $type $4 $free_space full ${1}000001
	else
		open_dialog NEW_PARTITION $type $4 $free_space beginning ${1}000001
	fi
	read_line num id size type fs path name
	close_dialog
	if [ -z "$id" ]; then
		db_progress STOP
		autopartitioning_failed
	fi

	# Mark the partition LVM only if it is actually LVM and add it to vgpath
	if echo "$*" | grep -q "method{ lvm }"; then
		devfspv_devices="$devfspv_devices $path"
		open_dialog GET_FLAGS $id
		flags=$(read_paragraph)
		close_dialog
		open_dialog SET_FLAGS $id
		write_line "$flags"
		write_line lvm
		write_line NO_MORE
		close_dialog
	fi
	shift; shift; shift; shift
	setup_partition $id $*
	free_space=$(partition_after $id)'
}

get_auto_disks() {
	local dev device

	for dev in $DEVICES/*; do
		[ -d "$dev" ] || continue

		# Skip /dev/mapper/X and /dev/mdX devices
		device=$(cat $dev/device)
		$(echo "$device" | grep -q "/dev/md[0-9]*$") && continue
		$(echo "$device" | grep -q "/dev/mapper/") && continue

		printf "$dev\t$(device_name $dev)\n"
	done
}

select_auto_disk() {
	local DEVS

	DEVS=$(get_auto_disks)
	[ -n "$DEVS" ] || return 1
	debconf_select critical partman-auto/select_disk "$DEVS" "" || return 1
	echo "$RET"
	return 0
}

# TODO: Add a select_auto_disks() function
# Note: This needs a debconf_multiselect equiv.
