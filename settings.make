prefix =	/usr
dest_prefix =	$(DESTDIR)$(prefix)
share =		$(dest_prefix)/share
bindir =	$(dest_prefix)/bin
mandir =	$(share)/man
man1dir =	$(mandir)/man1
pkgname =	autopkgtest
docdir =	$(share)/doc/$(pkgname)
pythondir = 	$(share)/$(pkgname)/python

INSTALL =		install
INSTALL_DIRS =		$(INSTALL) -d
INSTALL_PROGRAM =	$(INSTALL) -m 0755
INSTALL_DATA =		$(INSTALL) -m 0644
INSTALL_DOC =		$(INSTALL) -m 0644
