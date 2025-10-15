arch_get_kernel_flavour () {
	echo loong64
}

arch_check_usable_kernel () {
	case "$1" in
	    *-dbg|*-signed-template)
		return 1
		;;
	    *-loong64 | *-loong64-*)
		# Allow any other hyphenated suffix
		return 0
		;;
	    *)
		return 1
		;;
	esac
}

arch_get_kernel () {
	echo "linux-image-loong64"
}
