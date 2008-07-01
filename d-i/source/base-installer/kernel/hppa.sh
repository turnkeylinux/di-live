arch_get_kernel_flavour () {
	echo "$MACHINE"
	return 0
}

arch_check_usable_kernel () {
	if expr "$1" : '.*-parisc-' >/dev/null; then return 0; fi
	if expr "$1" : '.*-parisc$' >/dev/null; then return 0; fi
 	if expr "$1" : '.*-hppa32.*' >/dev/null; then return 0; fi
	if expr "$1" : '.*-32.*' >/dev/null; then return 0; fi
	if [ "$2" = parisc ]; then return 1; fi
	if expr "$1" : '.*-parisc64.*' >/dev/null; then return 0; fi
 	if expr "$1" : '.*-hppa64.*' >/dev/null; then return 0; fi
	if expr "$1" : '.*-64.*' >/dev/null; then return 0; fi

	# default to usable in case of strangeness
	warning "Unknown kernel usability: $1 / $2"
	return 0
}

arch_get_kernel () {
	case $1 in
		parisc)		family=hppa32 ;;
		parisc64)	family=hppa64 ;;
	esac

	echo "linux-$family"
	echo "linux-image-$family"
}
