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

include settings.make

programs =	virt-subproc/adt-virt-chroot \
		virt-subproc/adt-virt-xenlvm \
		virt-subproc/adt-virt-null \
		runner/adt-run \
		runner/adt-testreport-onepackage

examples =	runner/onepackage-config \
		runner/ubuntu-config

pythonfiles =	virt-subproc/VirtSubproc.py

all:
	cd xen && $(MAKE)

install-here:
	$(INSTALL_DIRS) -d $(bindir) $(docdir) $(man1dir) \
		$(pythondir) $(examplesdir)
	set -e; for f in $(programs); do \
		$(INSTALL_PROGRAM) $$f $(bindir); \
		test ! -f $$f.1 || $(INSTALL_DOC) $$f.1 $(man1dir); \
		done
	$(INSTALL_DATA) $(pythonfiles) $(pythondir)
	$(INSTALL_DOC) CREDITS debian/changelog $(docdir)
	$(INSTALL_DOC) doc/README*[!~] $(docdir)
	$(INSTALL_DOC) $(examples) $(examplesdir)

install: install-here
	cd xen && $(MAKE) install

clean:
	cd xen && $(MAKE) clean
