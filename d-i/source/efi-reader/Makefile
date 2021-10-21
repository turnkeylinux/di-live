
ifdef DEBUG
DEB_BUILD_OPTIONS := debug:${DEB_BUILD_OPTIONS}
endif

CFLAGS := -W -Wall  -I.

ifneq (,$(findstring debug,$(DEB_BUILD_OPTIONS)))
CFLAGS += -g  -DDEBUG=1
OBJS += xmalloc.o
STRIP= /bin/true
else
CFLAGS +=  -fomit-frame-pointer -Os
STRIPTOOL=strip
STRIP= $(STRIPTOOL) --remove-section=.note --remove-section=.comment
endif

LDOPTS = -ldebian-installer -ldebconfclient


all: efi-reader

efi-reader: table.h efi-reader.c
	$(CC) $(CFLAGS) efi-reader.c -o $@ $(LDOPTS)
	$(STRIP) $@

table.h:
	sh ./create-table.sh

clean:
	rm -f *~ table.h efi-reader demo.templates demo

install: efi-reader
	install -m 755 efi-reader ${DESTDIR}/usr/bin/efi-reader

.PHONY: demo
	ln -sf debian/templates demo.templates
	chmod a+x debian/postinst
	rm -f demo
	ln -s debian/postinst demo
	DEBCONF_DEBUG=developer /usr/share/debconf/frontend ./demo
	rm -f demo.templates demo

