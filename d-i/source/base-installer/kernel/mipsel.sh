arch_get_kernel_flavour () {
	case "$SUBARCH" in
		r3k-kn02|r4k-kn04|sb1-bcm91250a|sb1a-bcm91480b)
			echo "$SUBARCH"
			return 0
		;;
		qemu-mips32)
			echo "qemu"
			return 0
		;;
		cobalt)
			echo r5k-cobalt
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
	return 1
}

arch_get_kernel () {
	# use the more generic package versioning for 2.6 ff.
	case "$KERNEL_MAJOR" in
		2.6)
			version="$KERNEL_MAJOR"
			echo "linux-image-$version-$1"
			;;
		*)      warning "Unsupported kernel major '$KERNEL_MAJOR'."
			;;
	esac
}
