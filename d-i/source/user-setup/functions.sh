# Returns a true value if there seems to be a system user account.
# OVERRIDE_SYSTEM_USER overrides this to assume that no system user account
# exists.
is_system_user () {
	if [ "$OVERRIDE_SYSTEM_USER" ]; then
		return 1
	fi

	if ! [ -e $ROOT/etc/passwd ]; then
		return 1
	fi
	
        # Assume NIS, or any uid from 1000 to 29999,  means there is a user.
        if grep -q '^+:' $ROOT/etc/passwd || \
           grep -q '^[^:]*:[^:]*:[1-9][0-9][0-9][0-9]:' $ROOT/etc/passwd || \
           grep -q '^[^:]*:[^:]*:[12][0-9][0-9][0-9][0-9]:' $ROOT/etc/passwd; then
                return 0
        else
                return 1
        fi
}

# Returns a true value if root already has a password.
root_password () {
	if ! [ -e $ROOT/etc/passwd ]; then
		return 1
	fi
	
	# Assume there is a root password if NIS is being used.
	if grep -q '^+:' $ROOT/etc/passwd; then
		return 0
	fi

	if [ -e $ROOT/etc/shadow ] && \
	   [ "`grep ^root: $ROOT/etc/shadow | cut -d : -f 2`" ] && \
	   [ "`grep ^root: $ROOT/etc/shadow | cut -d : -f 2`" != '*' ]; then
		return 0
	fi
	
	if [ -e $ROOT/etc/passwd ] && \
		[ "`grep ^root: $ROOT/etc/passwd | cut -d : -f 2`" ] && \
		[ "`grep ^root: $ROOT/etc/passwd | cut -d : -f 2`" != 'x' ]; then
			return 0
	fi

	return 1
}
