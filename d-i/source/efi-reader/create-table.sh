#!/bin/sh

# Build iso-639-2 to iso-639-1 table for efi-reader
# 
#

cat > table.h << EOF

struct {
	char threecode[4];
	char twocode[3];
	} trans_table[] = {
EOF

isoquery -i 639 -c | cut -f1,3 | \
sed -r '/\t$/d; s/(.+)\t(.+)/{"\1"\,"\2"}\,/' \
>> table.h


cat >> table.h << EOF
 { "","" },
};

EOF
