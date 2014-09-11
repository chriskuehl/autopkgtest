# VirtSubproc is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006-2007 Canonical Ltd.
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

import __main__

import sys
import os
from urllib.parse import quote as url_quote
from urllib.parse import unquote as url_unquote
import signal
import subprocess
import traceback
import errno
import time
import pipes
import socket
import shutil

import adtlog

progname = "<VirtSubproc>"
devnull_read = open('/dev/null', 'r')
caller = __main__
copy_timeout = int(os.getenv('ADT_VIRT_COPY_TIMEOUT', '300'))

downtmp_open = None  # downtmp after opening testbed
downtmp = None  # current downtmp (None after close)
auxverb = None  # prefix to run command argv in testbed
cleaning = False
in_mainloop = False


class Quit(RuntimeError):

    def __init__(self, ec, m):
        self.ec = ec
        self.m = m


class Timeout(RuntimeError):
    pass


def alarm_handler(*a):
    raise Timeout()


def timeout_start(to):
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(to)


def timeout_stop():
    signal.alarm(0)


class FailedCmd(RuntimeError):

    def __init__(self, e):
        self.e = e


def bomb(m):
    if in_mainloop:
        raise Quit(12, progname + ": failure: %s" % m)
    else:
        sys.stderr.write(m)
        sys.stderr.write('\n')
        sys.exit(1)


def ok():
    print('ok')


def cmdnumargs(c, ce, nargs=0, noptargs=0):
    if len(c) < 1 + nargs:
        bomb("too few arguments to command `%s'" % ce[0])
    if noptargs is not None and len(c) > 1 + nargs + noptargs:
        bomb("too many arguments to command `%s'" % ce[0])


def cmd_capabilities(c, ce):
    cmdnumargs(c, ce)
    return caller.hook_capabilities()


def cmd_quit(c, ce):
    cmdnumargs(c, ce)
    raise Quit(0, '')


def cmd_close(c, ce):
    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`close' when not open")
    cleanup()


def cmd_print_execute_command(c, ce):
    global auxverb

    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`print-execute-command' when not open")
    return [','.join(map(url_quote, auxverb))]


def preexecfn():
    caller.hook_forked_inchild()


def execute_timeout(instr, timeout, *popenargs, **popenargsk):
    '''Popen wrapper with timeout supervision

    If instr is given, it is fed into stdin, otherwise stdin will be /dev/null.

    Return (status, stdout, stderr)
    '''
    adtlog.debug('execute-timeout: ' + ' '.join(popenargs[0]))
    sp = subprocess.Popen(*popenargs,
                          preexec_fn=preexecfn,
                          universal_newlines=True,
                          **popenargsk)
    if instr is None:
        popenargsk['stdin'] = devnull_read
    timeout_start(timeout)
    try:
        (out, err) = sp.communicate(instr)
    except Timeout:
        sp.kill()
        sp.wait()
        raise
    timeout_stop()
    status = sp.wait()
    return (status, out, err)


def check_exec(argv, downp=False, outp=False, timeout=0):
    '''Run successful command (argv list)

    Command must succeed (exit code 0) and not produce any stderr. If downp is
    True, command is run in testbed. If outp is True, stdout will be captured
    and returned. stdin is set to /dev/null.

    Returns stdout (or None if outp is False).
    '''
    global auxverb

    if downp:
        real_argv = auxverb + argv
    else:
        real_argv = argv
    if outp:
        stdout = subprocess.PIPE
    else:
        stdout = None

    (status, out, err) = execute_timeout(None, timeout, real_argv,
                                         stdout=stdout)

    if status:
        bomb("%s%s failed (exit status %d)" %
             ((downp and "(down) " or ""), argv, status))
    if err:
        bomb("%s unexpectedly produced stderr output `%s'" %
             (argv, err))

    if outp and out and out[-1] == '\n':
        out = out[:-1]
    return out


class timeout:
    def __init__(self, secs, exit_msg=None):
        '''Context manager that times out after given number of seconds.

        If exit_msg is given, the program bomb()s with that message,
        otherwise it raises a Timeout exception.
        '''
        self.secs = secs
        self.exit_msg = exit_msg

    def __enter__(self):
        timeout_start(self.secs)

    def __exit__(self, type_, value, traceback):
        timeout_stop()
        if type_ is Timeout and self.exit_msg:
            bomb(self.exit_msg)
            return True
        return False


def get_unix_socket(path):
    '''Open a connected client socket to given Unix socket with a 5s timeout'''

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with timeout(5, 'Timed out waiting for %s socket\n' % path):
        while True:
            try:
                s.connect(path)
                break
            except socket.error:
                continue
    return s


def expect(sock, search_bytes, timeout_sec, description=None):
    adtlog.debug('expect: "%s"' % search_bytes.decode())
    what = '"%s"' % (description or search_bytes or 'data')
    out = b''
    with timeout(timeout_sec,
                 description and ('timed out waiting for %s' % what) or None):
        while True:
            time.sleep(0.1)
            block = sock.recv(4096)
            # adtlog.debug('expect: got block: %s' % block)
            out += block
            if search_bytes is None or search_bytes in out:
                adtlog.debug('expect: found "%s"' % what)
                break


def cmd_open(c, ce):
    global auxverb, downtmp, downtmp_open
    cmdnumargs(c, ce)
    if downtmp:
        bomb("`open' when already open")
    caller.hook_open()
    adtlog.debug("auxverb = %s, downtmp = %s" % (str(auxverb), downtmp))
    downtmp = caller.hook_downtmp(downtmp_open)
    if downtmp_open and downtmp_open != downtmp:
        bomb('virt-runner failed to restore downtmp path %s, gave %s instead'
             % (downtmp_open, downtmp))
    downtmp_open = downtmp
    return [downtmp]


def downtmp_mktemp(path):
    '''Generate a downtmp

    When a path is given, this is the downtmp that we created when opening the
    testbed the first time. We always want to keep the same path between
    resets, as built package trees sometimes refer to absolute paths and thus
    fail if they get moved around.
    '''
    if path:
        check_exec(['mkdir', '--mode=1777', '--parents', downtmp_open],
                   downp=True)
        return path
    else:
        d = check_exec(['mktemp', '--directory', '/tmp/adt-run.XXXXXX'],
                       downp=True, outp=True)
        check_exec(['chmod', '1777', d], downp=True)
        return d


def downtmp_remove():
    global downtmp, auxverb
    if downtmp:
        execute_timeout(None, copy_timeout,
                        auxverb + ['rm', '-rf', '--', downtmp])
        downtmp = None


def cmd_revert(c, ce):
    global auxverb, downtmp, downtmp_open
    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`revert' when not open")
    if 'revert' not in caller.hook_capabilities():
        bomb("`revert' when `revert' not advertised")
    caller.hook_revert()
    downtmp = caller.hook_downtmp(downtmp_open)
    if downtmp_open and downtmp_open != downtmp:
        bomb('virt-runner failed to restore downtmp path %s, gave %s instead'
             % (downtmp_open, downtmp))
    adtlog.debug("auxverb = %s, downtmp = %s" % (str(auxverb), downtmp))

    return [downtmp]


def cmd_reboot(c, ce):
    global downtmp
    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`reboot' when not open")
    if 'reboot' not in caller.hook_capabilities():
        bomb("`reboot' when `reboot' not advertised")

    # save current downtmp
    check_exec(['sh', '-ec', '''rm -f /var/cache/autopkgtest/tmpdir.tar
        mkdir -p /var/cache/autopkgtest/
        tar --create --absolute-names -f /var/cache/autopkgtest/tmpdir.tar '%s'
        ''' % downtmp], downp=True, timeout=copy_timeout)
    adtlog.debug('cmd_reboot: saved current downtmp, rebooting')

    caller.hook_reboot()

    # restore downtmp
    check_exec(['sh', '-ec', '''
        tar --extract --absolute-names -f /var/cache/autopkgtest/tmpdir.tar
        rm -r /var/cache/autopkgtest/'''],
               downp=True, timeout=copy_timeout)
    adtlog.debug('cmd_reboot: saved current downtmp, rebooting')


def get_downtmp_host():
    '''Return host directory of the testbed's downtmp dir, if supported'''

    for cap in caller.hook_capabilities():
        if cap.startswith('downtmp-host='):
            return cap.split('=', 1)[1]
    return None


def copytree(src, dst):
    '''Like shutils.copytree(), but merges with existing dst'''

    if not os.path.exists(dst):
        shutil.copytree(src, dst, symlinks=True)
        return

    for f in os.listdir(src):
        fsrc = os.path.join(src, f)
        subprocess.check_call(['cp', '-r', '--preserve=timestamps,links',
                               '--target-directory', dst, fsrc])


def copyup_shareddir(tb, host, is_dir, downtmp_host):
    adtlog.debug('copyup_shareddir: tb %s host %s is_dir %s downtmp_host %s'
                 % (tb, host, is_dir, downtmp_host))

    host = os.path.normpath(host)
    tb = os.path.normpath(tb)
    downtmp_host = os.path.normpath(downtmp_host)

    timeout_start(copy_timeout)
    try:
        tb_tmp = None
        if tb.startswith(downtmp):
            # translate into host path
            tb = downtmp_host + tb[len(downtmp):]
        else:
            tb_tmp = os.path.join(downtmp, os.path.basename(host))
            adtlog.debug('copyup_shareddir: tb path %s is not already in '
                         'downtmp, copying to %s' % (tb, tb_tmp))
            check_exec(['cp', '-r', '--preserve=timestamps,links', tb, tb_tmp],
                       downp=True)
            # translate into host path
            tb = os.path.join(downtmp_host, os.path.basename(host))

        if tb == host:
            tb_tmp = None
        else:
            adtlog.debug('copyup_shareddir: tb(host) %s is not already at '
                         'destination %s, copying' % (tb, host))
            if is_dir:
                copytree(tb, host)
            else:
                shutil.copy(tb, host)

        if tb_tmp:
            adtlog.debug('copyup_shareddir: rm intermediate copy: %s' % tb)
            check_exec(['rm', '-rf', tb_tmp], downp=True)
    finally:
        timeout_stop()


def copydown_shareddir(host, tb, is_dir, downtmp_host):
    adtlog.debug('copydown_shareddir: host %s tb %s is_dir %s downtmp_host %s'
                 % (host, tb, is_dir, downtmp_host))

    host = os.path.normpath(host)
    tb = os.path.normpath(tb)
    downtmp_host = os.path.normpath(downtmp_host)

    timeout_start(copy_timeout)
    try:
        host_tmp = None
        if host.startswith(downtmp_host):
            # translate into tb path
            host = downtmp + host[len(downtmp_host):]
        else:
            host_tmp = os.path.join(downtmp_host, os.path.basename(tb))
            if is_dir:
                if os.path.exists(host_tmp):
                    try:
                        shutil.rmtree(host_tmp)
                    except OSError as e:
                        adtlog.warning('cannot remove old %s, moving it '
                                       'instead: %s' % (host_tmp, e))
                        # some undeletable files? hm, move it aside instead
                        counter = 0
                        while True:
                            p = host_tmp + '.old%i' % counter
                            if not os.path.exists(p):
                                os.rename(host_tmp, p)
                                break
                            counter += 1

                shutil.copytree(host, host_tmp, symlinks=True)
            else:
                shutil.copy(host, host_tmp)
            # translate into tb path
            host = os.path.join(downtmp, os.path.basename(tb))

        if host == tb:
            host_tmp = None
        else:
            check_exec(['rm', '-rf', tb], downp=True)
            check_exec(['cp', '-r', '--preserve=timestamps,links', host, tb],
                       downp=True)
        if host_tmp:
            (is_dir and shutil.rmtree or os.unlink)(host_tmp)
    finally:
        timeout_stop()


def copyupdown(c, ce, upp):
    cmdnumargs(c, ce, 2)
    copyupdown_internal(ce[0], c[1:], upp)


def copyupdown_internal(wh, sd, upp):
    '''Copy up/down a file or dir.

    wh: 'copyup' or 'copydown'
    sd: (source, destination) paths
    upp: True for copyup, False for copydown
    '''
    if not downtmp:
        bomb("%s when not open" % wh)
    if not sd[0] or not sd[1]:
        bomb("%s paths must be nonempty" % wh)
    dirsp = sd[0][-1] == '/'
    if dirsp != (sd[1][-1] == '/'):
        bomb("% paths must agree about directoryness"
             " (presence or absence of trailing /)" % wh)

    # if we have a shared directory, we just need to copy it from/to there; in
    # most cases, it's testbed end is already in the downtmp dir
    downtmp_host = get_downtmp_host()
    if downtmp_host:
        try:
            if upp:
                copyup_shareddir(sd[0], sd[1], dirsp, downtmp_host)
            else:
                copydown_shareddir(sd[0], sd[1], dirsp, downtmp_host)
        except Timeout:
            raise FailedCmd(['timeout'])
        return

    isrc = 0
    idst = 1
    ilocal = 0 + upp
    iremote = 1 - upp

    deststdout = devnull_read
    srcstdin = devnull_read
    remfileq = pipes.quote(sd[iremote])
    if not dirsp:
        rune = 'cat %s%s' % ('><'[upp], remfileq)
        if upp:
            deststdout = open(sd[idst], 'w')
        else:
            srcstdin = open(sd[isrc], 'r')
            status = os.fstat(srcstdin.fileno())
            if status.st_mode & 0o111:
                rune += '; chmod +x -- %s' % (remfileq)
        localcmdl = ['cat']
    else:
        taropts = [None, None]
        taropts[isrc] = '-c .'
        taropts[idst] = '--preserve-permissions --extract --no-same-owner'

        rune = 'cd %s; tar %s -f -' % (remfileq, taropts[iremote])
        if upp:
            try:
                os.mkdir(sd[ilocal])
            except (IOError, OSError) as oe:
                if oe.errno != errno.EEXIST:
                    raise
        else:
            rune = ('if ! test -d %s; then mkdir -- %s; fi; ' % (
                remfileq, remfileq)
            ) + rune

        localcmdl = ['tar', '--directory', sd[ilocal]] + (
            ('%s -f -' % taropts[ilocal]).split()
        )
    downcmdl = auxverb + ['sh', '-ec', rune]

    if upp:
        cmdls = (downcmdl, localcmdl)
    else:
        cmdls = (localcmdl, downcmdl)

    adtlog.debug(str(["cmdls", str(cmdls)]))
    adtlog.debug(str(["srcstdin", str(srcstdin), "deststdout",
                      str(deststdout), "devnull_read", devnull_read]))

    subprocs = [None, None]
    adtlog.debug(" +< %s" % ' '.join(cmdls[0]))
    subprocs[0] = subprocess.Popen(cmdls[0], stdin=srcstdin,
                                   stdout=subprocess.PIPE,
                                   preexec_fn=preexecfn)
    adtlog.debug(" +> %s" % ' '.join(cmdls[1]))
    subprocs[1] = subprocess.Popen(cmdls[1], stdin=subprocs[0].stdout,
                                   stdout=deststdout,
                                   preexec_fn=preexecfn)
    subprocs[0].stdout.close()
    try:
        timeout_start(copy_timeout)
        for sdn in [1, 0]:
            adtlog.debug(" +" + "<>"[sdn] + "?")
            status = subprocs[sdn].wait()
            if not (status == 0 or (sdn == 0 and status == -13)):
                timeout_stop()
                bomb("%s %s failed, status %d" %
                     (wh, ['source', 'destination'][sdn], status))
        timeout_stop()
    except Timeout:
        for sdn in [1, 0]:
            subprocs[sdn].kill()
            subprocs[sdn].wait()
        raise FailedCmd(['timeout'])


def cmd_copydown(c, ce):
    copyupdown(c, ce, False)


def cmd_copyup(c, ce):
    copyupdown(c, ce, True)


def cmd_shell(c, ce):
    cmdnumargs(c, ce, 1, None)
    if not downtmp:
        bomb("`shell' when not open")
    # runners can provide a hook if they need a special treatment
    try:
        caller.hook_shell(*c[1:])
    except AttributeError:
        adtlog.debug('cmd_shell: using default shell command, dir %s' % c[1])
        cmd = 'cd "%s"; ' % c[1]
        for e in c[2:]:
            cmd += 'export "%s"; ' % e
        cmd += 'bash -i'
        with open('/dev/tty', 'rb') as sin:
            with open('/dev/tty', 'wb') as sout:
                with open('/dev/tty', 'wb') as serr:
                    subprocess.call(auxverb + ['sh', '-c', cmd],
                                    stdin=sin, stdout=sout, stderr=serr)


def command():
    sys.stdout.flush()
    while True:
        try:
            ce = sys.stdin.readline().strip()
            # FIXME: This usually means EOF (as checked below), but with Python
            # 3 we often get empty strings here even though this is supposed to
            # block for new input.
            if ce == '':
                time.sleep(0.1)
                continue
            break
        except IOError as e:
            if e.errno == errno.EAGAIN:
                time.sleep(0.1)
                continue
            else:
                raise
    if not ce:
        bomb('end of file - caller quit?')
    ce = ce.rstrip().split()
    c = list(map(url_unquote, ce))
    if not c:
        bomb('empty commands are not permitted')
    adtlog.debug('executing ' + ' '.join(ce))
    c_lookup = c[0].replace('-', '_')
    try:
        f = globals()['cmd_' + c_lookup]
    except KeyError:
        bomb("unknown command `%s'" % ce[0])
    try:
        r = f(c, ce)
        if not r:
            r = []
        r.insert(0, 'ok')
    except FailedCmd as fc:
        r = fc.e
    print(' '.join(r))

signal_list = [	signal.SIGHUP, signal.SIGTERM,
                signal.SIGINT, signal.SIGPIPE]


def sethandlers(f):
    for signum in signal_list:
        signal.signal(signum, f)


def cleanup():
    global downtmp, cleaning
    adtlog.debug("cleanup...")
    sethandlers(signal.SIG_DFL)
    # avoid recursion if something bomb()s in hook_cleanup()
    if not cleaning:
        cleaning = True
        if downtmp:
            caller.hook_cleanup()
        cleaning = False
        downtmp = None


def error_cleanup():
    try:
        ok = False
        try:
            cleanup()
            ok = True
        except Quit as q:
            sys.stderr.write(q.m)
            sys.stderr.write('\n')
        except:
            sys.stderr.write('Unexpected cleanup error:\n')
            traceback.print_exc()
            sys.stderr.write('\n')
        if not ok:
            sys.stderr.write('while cleaning up because of another error:\n')
    except:
        pass


def prepare():
    def handler(sig, *any):
        cleanup()
        os.kill(os.getpid(), sig)
    sethandlers(handler)


def mainloop():
    global in_mainloop
    in_mainloop = True

    try:
        while True:
            command()
    except Quit as q:
        error_cleanup()
        if q.m:
            sys.stderr.write(q.m)
            sys.stderr.write('\n')
        sys.exit(q.ec)
    except:
        error_cleanup()
        sys.stderr.write('Unexpected error:\n')
        traceback.print_exc()
        sys.exit(16)
    finally:
        in_mainloop = False


def main():
    ok()
    prepare()
    mainloop()
