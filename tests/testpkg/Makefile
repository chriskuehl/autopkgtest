build:
	/bin/echo -e "#!/bin/sh -e\necho built script OK" > test_built
	chmod 755 test_built

clean:
	rm -f test_built

distclean: clean

install: build
	install -D -m755 test_static $(DESTDIR)/usr/bin/test_static
	install -D -m755 test_built $(DESTDIR)/usr/bin/test_built
