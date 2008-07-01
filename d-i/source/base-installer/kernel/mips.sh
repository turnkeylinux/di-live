arch_get_kernel_flavour () {
	case "$SUBARCH" in
		r4k-ip22|r5k-ip22|r5k-ip32|sb1-bcm91250a|sb1a-bcm91480b)
			echo "$SUBARCH"
			return 0
		;;
		qemu-mips32)
			echo "qemu"
			return 0
		;;
		*)
			warning "Unknown $ARCH subarchitecture '$SUBARCH'."
			return 1
		;;
	esac
}

arch_check_usable_kernel () {
	# Subarchitecture must match exactly.
	if expr "$1" : ".*-$2.*" >/dev/null; then return 0; fi
	# For 2.6, the r4k-ip22 kernel will do for r5k-ip22 as well.
	if expr "$1" : ".*-2\.6.*-r4k-ip22.*" >/dev/null && \
	   [ "$2" = r5k-ip22 ]; then
		return 0
	fi
	return 1
}

arch_get_kernel () {
	# use the more generic package versioning for 2.6 ff.
	case "$KERNEL_MAJOR" in
		2.6)
			case $1 in
				r5k-ip22)
					set r4k-ip22
					;;
			esac
			echo "linux-image-$KERNEL_MAJOR-$1"
			;;
		*)      warning "Unsupported kernel major '$KERNEL_MAJOR'."
			;;
	esac
}
