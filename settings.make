prefix =	/usr/local
share =		$(prefix)/share
bindir =	$(prefix)/bin
mandir =	$(share)/man
man1dir =	$(mandir)/man1
docdir =	$(share)/doc/autopkgtest

INSTALL =		install
INSTALL_DIRS =		$(INSTALL) -d
INSTALL_PROGRAM =	$(INSTALL) -m 0755
INSTALL_DOC =		$(INSTALL)

