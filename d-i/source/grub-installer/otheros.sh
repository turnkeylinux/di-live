grub2_write_chain() {
	uuid="$($chroot $ROOT grub-probe --target fs_uuid --device $partition)"
	cat >> $tmpfile <<EOF

# This entry automatically added by the Debian installer for a non-linux OS
# on $partition
menuentry "$title" {
	set root=$grubdrive
EOF
	if [ -n "$uuid" ] ; then
		cat >> $tmpfile <<EOF
	search $no_floppy --fs-uuid --set=root $uuid
EOF
	fi
	# DOS/Windows can't deal with booting from a non-first hard drive
	case $shortname in
	    MS*|Win*)
		if $chroot $ROOT dpkg --compare-versions $grub_debian_version gt 1.96+20090609-1 && \
		  [ "$title" != "Windows Vista (loader)" ]; then
			    cat >> $tmpfile <<EOF
	drivemap -s (hd0) \$root
EOF
		fi
		;;
	    esac
	cat >> $tmpfile <<EOF
	chainloader +1
}
EOF

} # grub2_write_chain end

grub2_write_linux() {
	cat >> $tmpfile <<EOF

# This entry automatically added by the Debian installer for an existing
# linux installation on $mappedpartition.
menuentry "$label (on $mappedpartition)" {
	set root=$grubdrive
EOF
	uuid="$($chroot $ROOT grub-probe --target fs_uuid --device $partition)"
	if [ -n "$uuid" ] ; then
		cat >> $tmpfile <<EOF
	search $no_floppy --fs-uuid --set=root $uuid
EOF
	fi
	cat >> $tmpfile <<EOF
	linux $kernel $params
EOF
	if [ -n "$initrd" ]; then
		cat >> $tmpfile <<EOF
	initrd $initrd
EOF
	fi
	cat >> $tmpfile <<EOF
}

EOF
} # grub2_write_linux end

grub2_write_hurd() {
	cat >> $tmpfile <<EOF

# This entry automatically added by the Debian installer for an existing
# hurd installation on $partition.
menuentry "$title (on $partition)" {
	set root=$grubdrive
EOF
	uuid="$($chroot $ROOT grub-probe --target fs_uuid --device $partition)"
	if [ -n "$uuid" ] ; then
		cat >> $tmpfile <<EOF
	search $no_floppy --fs-uuid --set=root $uuid
EOF
	fi
	cat >> $tmpfile <<EOF
	multiboot /boot/gnumach.gz root=device:$hurddrive
	module /hurd/ext2fs.static ext2fs --readonly \\
			--multiboot-command-line=\${kernel-command-line} \\
			--host-priv-port=\${host-port} \\
			--device-master-port=\${device-port} \\
			--exec-server-task=\${exec-task} -T typed \${root} \\
			\$(task-create) \$(task-resume)
	module /lib/ld.so.1 exec /hurd/exec \$(exec-task=task-create)
}

EOF
} # grub2_write_hurd end
