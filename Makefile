# This file is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# See the file CREDITS for a full list of credits information (often
# installed as /usr/share/doc/autopkgtest/CREDITS).

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

programs =	virt-chroot/adt-virt-chroot \
		runner/adt-run

install:
	$(INSTALL_DIRS) -d $(bindir) $(docdir) $(man1dir)
	set -e; for f in $(programs); do \
		$(INSTALL_PROGRAM) $$f $(bindir); \
		test ! -f $$f.1 || $(INSTALL_DOC) $$f.1 $(man1dir); \
		done
	$(INSTALL_DOC) CREDITS debian/changelog $(docdir)
