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

prefix =	/usr
share =		$(DESTDIR)$(prefix)/share
bindir =	$(DESTDIR)$(prefix)/bin
man1dir =	$(share)/man/man1
pkgname =	autopkgtest
docdir =	$(share)/doc/$(pkgname)
pythondir = 	$(share)/$(pkgname)/python

INSTALL =	install
INSTALL_DIRS =	$(INSTALL) -d
INSTALL_PROG =	$(INSTALL) -m 0755
INSTALL_DATA =	$(INSTALL) -m 0644

programs =	virt-subproc/adt-virt-chroot \
		virt-subproc/adt-virt-null \
		virt-subproc/adt-virt-schroot \
		virt-subproc/adt-virt-lxc \
		virt-subproc/adt-virt-qemu \
		tools/adt-buildvm-ubuntu-cloud \
		tools/adt-build-lxc \
		runner/adt-run

pythonfiles =	lib/VirtSubproc.py \
		lib/adtlog.py \
		lib/testdesc.py \
		$(NULL)

all:
	# nothing to build

install:
	$(INSTALL_DIRS) $(bindir) $(docdir) $(man1dir) $(pythondir)
	set -e; for f in $(programs); do \
		$(INSTALL_PROG) $$f $(bindir); \
		test ! -f $$f.1 || $(INSTALL_DATA) $$f.1 $(man1dir); \
		done
	$(INSTALL_PROG) tools/adt-setup-vm $(share)/$(pkgname)
	$(INSTALL_DATA) $(pythonfiles) $(pythondir)
	$(INSTALL_DATA) CREDITS $(docdir)
	$(INSTALL_DATA) doc/README*[!~] $(docdir)

clean:
	rm -f */*.pyc
