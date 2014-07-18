# adt_run_args is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006-2014 Canonical Ltd.
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

import os
import re
import sys
import argparse
from glob import glob

import adtlog
import testdesc

__all__ = ['parse_args']


timeouts = {'short': 100, 'copy': 300, 'install': 3000, 'test': 10000,
            'build': 100000}


def is_click_src(path):
    '''Check if path is a click source tree'''

    if os.path.isdir(os.path.join(path, 'click')):
        return True
    if glob(os.path.join(path, 'manifest.json*')):
        return True
    return False


def interpret_implicit_args(parser, args):
    '''Heuristically translate positional arguments to actions'''

    known_suffix = {
        '.dsc': '--source',
        '.deb': '--binary',
        '.changes': '--changes',
        '.click': '--click',
    }
    pos = 0
    result = []

    while pos < len(args):
        # jump over option args
        if args[pos] == '-B':
            args[pos] = '--no-built-binaries'
        if args[pos].startswith('--') and 'binaries' in args[pos]:
            result.append(args[pos])
            pos += 1
            continue

        if args[pos].startswith('--'):
            result.append(args[pos])
            if '=' not in args[pos]:
                try:
                    result.append(args[pos + 1])
                except IndexError:
                    pass
                pos += 1
            pos += 1
            continue

        # actions based on file name suffix
        for suffix, action in known_suffix.items():
            if args[pos].endswith(suffix):
                result += [action, args[pos]]
                break
        else:
            if is_click_src(args[pos]):
                result += ['--click-source', args[pos]]
            elif os.path.isdir(args[pos]) and args[pos].endswith('//'):
                result += ['--unbuilt-tree', args[pos]]
            elif os.path.isdir(args[pos]) and args[pos].endswith('/'):
                result += ['--built-tree', args[pos]]
            # actions based on patterns
            elif re.match('[0-9a-z][0-9a-z.+-]+$', args[pos]):
                result += ['--apt-source', args[pos]]
            else:
                parser.error('%s: unsupported action argument' % args[pos])

        pos += 1

    return result

actions = None
built_binaries = None


class ActionArg(argparse.Action):
    def __call__(self, parser, args, value, option_string=None):
        global actions, built_binaries
        if option_string == '--changes':
            try:
                files = testdesc.parse_rfc822(value).__next__()['Files']
            except (StopIteration, KeyError):
                parser.error('%s is invalid and does not contain Files:'
                             % value)
            dsc_dir = os.path.dirname(value)
            for f in files.split():
                if '.' in f and '_' in f:
                    fpath = os.path.join(dsc_dir, f)
                    if f.endswith('.deb'):
                        actions.append(('binary', fpath, None))
                    elif f.endswith('.dsc'):
                        actions.append(('source', fpath, False))
            return

        if option_string in ('--apt-source', '--built-tree'):
            bins = False
        # these are the only types where built_binaries applies
        elif option_string in ('--unbuilt-tree', '--source'):
            bins = built_binaries
        else:
            bins = None
        actions.append((option_string.lstrip('-'), value, bins))


class BinariesArg(argparse.Action):
    def __call__(self, parser, args, value, option_string=None):
        global built_binaries

        if option_string == '--no-built-binaries':
            built_binaries = False
        elif option_string == '--built-binaries':
            built_binaries = True
        else:
            raise NotImplementedError('cannot handle BinariesArg ' +
                                      option_string)


def parse_args(arglist=None):
    '''Parse adt-run command line arguments.

    Return (options, actions, virt-server-args).
    '''
    global actions, built_binaries

    actions = []
    built_binaries = True

    # action parser; instantiated first to use generated help
    action_parser = argparse.ArgumentParser(usage=argparse.SUPPRESS,
                                            add_help=False)
    action_parser.add_argument(
        '--unbuilt-tree', action=ActionArg, metavar='DIR or DIR//',
        help='run tests from unbuilt Debian source tree DIR')
    action_parser.add_argument(
        '--built-tree', action=ActionArg, metavar='DIR or DIR/',
        help='run tests from built Debian source tree DIR')
    action_parser.add_argument(
        '--source', action=ActionArg, metavar='DSC or some/pkg.dsc',
        help='build DSC and use its tests and/or generated binary packages')
    action_parser.add_argument(
        '--binary', action=ActionArg, metavar='DEB or some/pkg.deb',
        help='use binary package DEB for subsequent tests')
    action_parser.add_argument(
        '--changes', action=ActionArg, metavar='CHANGES or some/pkg.changes',
        help='run tests from dsc and binary debs from a .changes file')
    action_parser.add_argument(
        '--apt-source', action=ActionArg, metavar='SRCPKG or somesrc',
        help='download with apt-get source in testbed and use its tests')
    action_parser.add_argument(
        '--click-source', action=ActionArg, metavar='CLICKSRC or some/src',
        help='click source tree for subsequent --click package')
    action_parser.add_argument(
        '--click', action=ActionArg, metavar='CLICKPKG or some/pkg.click',
        help='install click package into testbed (path to *.click) or '
        'use an already installed click package ("com.example.myapp") '
        'and run its tests (from preceding --click-source)')
    action_parser.add_argument(
        '--override-control', action=ActionArg,
        metavar='CONTROL', help='run tests from control file CONTROL instead,'
        ' (applies to next Debian test suite only)')
    action_parser.add_argument(
        '-B', '--no-built-binaries', nargs=0, action=BinariesArg,
        help='do not use any binaries from subsequent --source or '
        '--unbuilt-tree actions')
    action_parser.add_argument(
        '--built-binaries', nargs=0, action=BinariesArg,
        help='use binaries from subsequent --source or --unbuilt-tree actions')

    # main / options parser
    usage = '%(prog)s [options] action [action ...] --- virt-server [options]'
    description = '''Test installed binary packages using the tests in the source package.

Actions specify the source and binary packages to test, or change
what happens with package arguments:
%s
''' % action_parser.format_help().split('\n', 1)[1]

    epilog = '''The --- argument separates the adt-run actions and options from the
virt-server which provides the testbed. See e. g. man adt-virt-schroot for
details.'''

    parser = argparse.ArgumentParser(
        usage=usage, description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog,
        add_help=False)
    # logging
    g_log = parser.add_argument_group('logging options')
    g_log.add_argument('-o', '--output-dir',
                       help='Write test artifacts (stdout/err, log, debs, etc)'
                       ' to OUTPUT-DIR, emptying it beforehand')
    # backwards compatible alias
    g_log.add_argument('--tmp-dir', dest='output_dir',
                       help='Alias for --output-dir for backwards '
                       'compatibility')
    g_log.add_argument('-l', '--log-file', dest='logfile',
                       help='Write the log LOGFILE, emptying it beforehand,'
                       ' instead of using OUTPUT-DIR/log')
    g_log.add_argument('--summary-file', dest='summary',
                       help='Write a summary report to SUMMARY, emptying it '
                       'beforehand')
    g_log.add_argument('-q', '--quiet', action='store_const', dest='verbosity',
                       const=0, default=1,
                       help='Suppress all messages from %(prog)s itself '
                       'except for the test results')

    # test bed setup
    g_setup = parser.add_argument_group('test bed setup options')
    g_setup.add_argument('--setup-commands', metavar='COMMANDS_OR_PATH',
                         action='append', default=[],
                         help='Run these commands after opening the testbed '
                         '(e. g. "apt-get update" or adding apt sources); '
                         'can be a string with the commands, or a file '
                         'containing the commands')
    g_setup.add_argument('-U', '--apt-upgrade', dest='setup_commands',
                         action='append_const',
                         const='(apt-get update || (sleep 15; apt-get update))'
                         ' && apt-get dist-upgrade -y -o '
                         'Dpkg::Options::="--force-confnew"',
                         help='Run apt update/dist-upgrade before the tests')
    g_setup.add_argument('--apt-pocket', metavar='POCKETNAME', action='append',
                         default=[],
                         help='Enable additional apt source for POCKETNAME')
    g_setup.add_argument('--copy', metavar='HOSTFILE:TESTBEDFILE',
                         action='append', default=[],
                         help='Copy file or dir from host into testbed after '
                         'opening')

    # privileges
    g_priv = parser.add_argument_group('user/privilege handling options')
    g_priv.add_argument('-u', '--user',
                        help='run tests as USER (needs root on testbed)')
    g_priv.add_argument('--gain-root', dest='gainroot',
                        help='Command to gain root during package build, '
                        'passed to dpkg-buildpackage -r')

    # debugging
    g_dbg = parser.add_argument_group('debugging options')
    g_dbg.add_argument('-d', '--debug', action='store_const', dest='verbosity',
                       const=2,
                       help='Show lots of internal adt-run debug messages')
    g_dbg.add_argument('-s', '--shell-fail', action='store_true',
                       help='Run a shell in the testbed after any failed '
                       'build or test')
    g_dbg.add_argument('--shell', action='store_true',
                       help='Run a shell in the testbed after every test')

    # timeouts
    g_time = parser.add_argument_group('timeout options')
    for k in timeouts:
        g_time.add_argument(
            '--timeout-' + k, type=int, dest='timeout_' + k, metavar='T',
            default=timeouts[k],
            help='set %s timeout to T seconds (default: %%(default)s)' % k)
    g_time.add_argument(
        '--timeout-factor', type=float, metavar='FACTOR', default=1.0,
        help='multiply all default timeouts by FACTOR')

    # locale
    g_loc = parser.add_argument_group('locale options')
    g_loc.add_argument('--leave-lang', dest='set_lang', action='store_false',
                       default='C.UTF-8',
                       help="leave LANG on testbed set to testbed's default")
    g_loc.add_argument('--set-lang', metavar='LANGVAL', default='C.UTF-8',
                       help='set LANG on testbed to LANGVAL '
                       '(default: %(default)s)')

    # misc
    g_misc = parser.add_argument_group('other options')
    g_misc.add_argument(
        '--gnupg-home', dest='gnupghome', default='~/.autopkgtest/gpg',
        help='use GNUPGHOME rather than ~/.autopkgtest (for signing private '
        'apt archive)')
    g_misc.add_argument(
        '-h', '--help', action='help', default=argparse.SUPPRESS,
        help='show this help message and exit')

    # first, expand argument files
    file_parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    arglist = file_parser.parse_known_args(arglist)[1]

    # split off virt-server args
    try:
        sep = arglist.index('---')
        virt_args = arglist[sep + 1:]
        arglist = arglist[:sep]
    except ValueError:
        # still allow --help
        virt_args = None

    # parse options first
    (args, action_args) = parser.parse_known_args(arglist)
    adtlog.verbosity = args.verbosity
    adtlog.debug('Parsed options: %s' % args)
    adtlog.debug('Remaining arguments: %s' % action_args)

    # now turn implicit "bare" args into option args, so that we can parse them
    # with argparse, and split off the virt-server args
    action_args = interpret_implicit_args(parser, action_args)
    adtlog.debug('Interpreted actions: %s' % action_args)
    adtlog.debug('Virt runner arguments: %s' % virt_args)

    if not virt_args:
        parser.error('You must specify --- <virt-server>...')

    action_parser.parse_args(action_args)

    # this timeout is for adt-virt-*, so pass it down via environment
    os.environ['ADT_VIRT_COPY_TIMEOUT'] = str(args.timeout_copy)

    if not actions:
        parser.error('You must specify at least one action')

    # if we have --setup-commands and it points to a file, read its contents
    for i, c in enumerate(args.setup_commands):
        if os.path.exists(c):
            with open(c, encoding='UTF-8') as f:
                args.setup_commands[i] = f.read().strip()

    # parse --copy arguments
    copy_pairs = []
    for arg in args.copy:
        try:
            (host, tb) = arg.split(':', 1)
        except ValueError:
            parser.error('--copy argument must be HOSTPATH:TESTBEDPATH: %s'
                         % arg)
        if not os.path.exists(host):
            parser.error('--copy host path %s does not exist' % host)
        copy_pairs.append((host, tb))
    args.copy = copy_pairs

    return (args, actions, virt_args)
