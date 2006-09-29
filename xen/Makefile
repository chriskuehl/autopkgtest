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

include ../settings.make

programs =	cleanup setup on-testbed with-testbed
shareprograms =	fixups fixups-inside
sharefiles =	readconfig

exec_prefix =	adt-xenlvm-

install:	all
	$(INSTALL_DIRS) -d $(bindir) $(docdir) $(man1dir) \
		$(sharedir) $(etcinitdddir) $(xenscripts)
	set -e; for f in $(programs) $(shareprograms); do \
		$(INSTALL_PROGRAM) $$f $(sharedir); \
		done
	set -e; for f in $(programs); do \
		ln -s $(sharedir)/$$f $(bindir)/$(exec_prefix)$$f; \
		test ! -f $$f.1 || $(INSTALL_DOC) $$f.1 \
			$(man1dir)/$(exec_prefix)$$f; \
		done
	set -e; for f in $(sharefiles); do \
		$(INSTALL_DATA) $$f $(sharedir); \
		done
	$(INSTALL_DATA) initscript $(etcinitddir)/adtxenlvm$(cfg_suffix)
	$(INSTALL_DATA) vif-route-adt $(xenscripts)/vif-route-adt$(cfg_suffix)

all:		readconfig

readconfig:	sed-readconfig readconfig.in
	sed -f $^ >$@.new && mv -f $@.new $@

sed-readconfig:	README Makefile
	echo '/@@varlist@@/{h' >$@.new
	sed -n 's,^adt_\([_0-9a-z]*\)[ 	].*,s/\\*/\1/p;g,p' <$< >>$@.new
	echo 'd}' >>$@.new && mv -f $@.new $@
