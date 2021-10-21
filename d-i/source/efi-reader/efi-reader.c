/* @file efi-reader.c
 * 
 * Read EFI variables and populate debconf database for debian-installer
 * Copyright (C) 2003, Alastair McKinstry <mckinstry@debian.org>
 * Released under the GNU Public License; see file COPYING for details
 */

#include <linux/types.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <debian-installer.h>
#include <cdebconf/debconfclient.h>

#include "table.h"

/* snarfed from linux kernel efivars.c
 */
typedef u_int16_t efi_char16_t;
#if 0
typedef u_int8_t __u8;
typedef u_int32_t __u32;
#endif
typedef struct { __u8 b[16]; } efi_guid_t;
typedef unsigned long efi_status_t;

typedef struct _efi_variable_t {
	efi_char16_t  VariableName[1024/sizeof(efi_char16_t)];
	efi_guid_t    VendorGuid;
	unsigned long DataSize;
	__u8          Data[1024];
	efi_status_t  Status;
	__u32         Attributes;
} __attribute__((packed)) efi_variable_t;



/**
 * Get the three-letter lang code from /proc
 * return 1 if error, 0 on success
 */
int get_efi_lang_code (char *lang_code)
{
	int fd, err, sz;
	efi_variable_t var_data;

	/* Snarfed variable def. from linux/arch/ia64/kernel/efivars.c
	 * Probably should check out a more official interface, in case the format
	 * of /proc changes.
	 */
	fd = open ("/proc/efi/vars/Lang-8be4df61-93ca-11d2-aa0d-00e098032b8c", O_RDONLY);
	if (fd < 0) {
		err = errno;
		di_error ("Failed to open /proc/efi/vars/Lang-*");
		di_error (strerror (err));
		return 1;
	}
	sz = read (fd, &var_data, sizeof (efi_variable_t));
	close (fd);
	if (sz == sizeof (efi_variable_t)) { // success
		strncpy (lang_code, (const char *) var_data.Data, 3);
		return 0;
	}
	return 1;
}

/**
 * locales prefer the language to be a two-letter code;
 * translate three-letter -> two-letter if possible (eg eng -> en)
 */
char *two_code (char *three_code)
{
	int t = 0;
	while (trans_table[t].threecode[0] != '\0' ) {
		if (strcmp (three_code, trans_table[t].threecode) == 0) 
			return trans_table[t].twocode;
		t++;
	}
	return three_code;
}

#define ATTRIBUTE_UNUSED __attribute__ ((__unused__))

/* Read certain variables from EFI and populate debian-installer, as required.
 * At the moment, just read Lang"
 * Check out the 
 */
int main (int argc ATTRIBUTE_UNUSED, char *argv[] ATTRIBUTE_UNUSED)
{
	char lang_code[4];
	static struct debconfclient *client;

	di_system_init("efi-reader");
	client = debconfclient_new ();
	if (get_efi_lang_code(lang_code)) 
		exit (1);
	debconf_set (client, "debian-installer/language", two_code (lang_code));
	exit (0);
}  


/*
 * Local Variables:
 * c-basic-offset: 8
 * tab-width: 8
 * indent-tabs-mode: t
 * End:
 */
   
