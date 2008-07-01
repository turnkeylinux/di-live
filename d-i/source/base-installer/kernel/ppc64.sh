arch_get_kernel_flavour () {
        echo "$ARCH"
}

arch_check_usable_kernel () {
	if expr "$1" : ".*-$2.*" >/dev/null; then return 0; fi
	return 1
}

arch_get_kernel () {
	echo "linux-image-$KERNEL_MAJOR-$1"
}

