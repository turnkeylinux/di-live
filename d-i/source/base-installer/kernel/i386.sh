arch_get_kernel_flavour () {
	VENDOR=`grep '^vendor_id' "$CPUINFO" | head -n1 | cut -d: -f2`
	FAMILY=`grep '^cpu family' "$CPUINFO" | head -n1 | cut -d: -f2`
	MODEL=`grep '^model[[:space:]]*:' "$CPUINFO" | head -n1 | cut -d: -f2`
	case "$VENDOR" in
		" AuthenticAMD"*)
			case "$FAMILY" in
				" 6"|" 15"|" 16")	echo k7 ;;
				" 5")			echo k6 ;;
				*)			echo 486 ;;
			esac
			;;
		" GenuineIntel"|" GenuineTMx86"*)
			case "$FAMILY" in
				" 6"|" 15")	echo 686 ;;
				" 5")		echo 586 ;;
				*)		echo 486 ;;
			esac
			;;
		" CentaurHauls")
			case "$FAMILY" in
				" 6")
					case "$MODEL" in
						" 9"|" 10")		echo 686 ;;
						*)		echo 586 ;;
					esac
					;;
				*)		echo 486 ;;
			esac
			;;
		*) echo 486 ;;
	esac
	return 0
}

arch_check_usable_kernel () {
	if expr "$1" : '.*-386.*' >/dev/null; then return 0; fi
	if [ "$2" = 486 ]; then return 1; fi
	if expr "$1" : '.*-generic.*' >/dev/null; then return 0; fi
	if expr "$1" : '.*-virtual.*' >/dev/null; then return 0; fi
	if expr "$1" : '.*-rt.*' >/dev/null; then return 0; fi
	if [ "$2" = 586 ] || [ "$2" = k6 ]; then return 1; fi
	if expr "$1" : '.*-server.*' >/dev/null; then return 0; fi
	if expr "$1" : '.*-xen.*' >/dev/null; then return 0; fi

	# default to usable in case of strangeness
	warning "Unknown kernel usability: $1 / $2"
	return 0
}

arch_get_kernel () {
	imgbase=linux-image

	if [ "$1" = k7 ] || [ "$1" = k6 ] || [ "$1" = 686 ] || [ "$1" = 586 ]; then
		echo "linux-generic"
		echo "linux-image-generic"
		echo "linux-virtual"
		echo "linux-image-virtual"
		echo "linux-rt"
		echo "linux-image-rt"
	fi
	if [ "$1" = k7 ] || [ "$1" = 686 ]; then
		echo "linux-server"
		echo "linux-image-server"
		echo "linux-server-bigiron"
		echo "linux-image-server-bigiron"
		echo "linux-xen"
		echo "linux-image-xen"
	fi
	echo "linux-386"
	echo "linux-image-386"
}
