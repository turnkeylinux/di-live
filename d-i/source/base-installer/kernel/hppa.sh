arch_get_kernel_flavour () {
	echo "$MACHINE"
	return 0
}

arch_check_usable_kernel () {
	case "$1" in
	    *-dbg)
		return 1
		;;
	    *-parisc | *-parisc-*)
	        OS32=$(grep "^capabilities.*os32.*" "$CPUINFO")
		if [ -n "$OS32" ]; then
			return 0
		fi
		;;
	    *-parisc64 | *-parisc64-*)
		OS64=$(grep "^capabilities.*os64.*" "$CPUINFO")
		if [ -n "$OS64" ]; then
			return 0
		fi
		;;
	esac
	return 1
}

arch_get_kernel () {
	echo "linux-image-$1"
}
