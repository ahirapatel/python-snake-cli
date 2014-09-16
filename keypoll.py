#!/usr/bin/env python2.7
import tty
import termios
import sys
import select
import fcntl
import os

# Only hit one key.. please.
def print_key():
    fd = sys.stdin.fileno()
    # Store settings for stdin, because we have to restore them later.
    old_settings = termios.tcgetattr(fd)
    try:
        # No echo and have stdin work on a char-by-char basis.
        tty.setraw(fd)
        sys.stdout.write("\rPlease hit the key for which you want the values of\n")
        # Use the poll object from the select module to wait 3 seconds for a
        # user key press.
        p = select.poll()
        p.register(fd, select.POLLIN)
        res = p.poll(3000)
        if res:
            # Keep options for stdin, then add the nonblocking flag to it.
            flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            ch = sys.stdin.read()
            # We need to do a list join because things like arrow keys are 3 values
            # even though letters may be only one value.
            sys.stdout.write('\r' + ' '.join([str(ord(x)) for x in ch]) + '\n')
        else:
            sys.stdout.write("\rYou took too long to press a key.\n")
    finally:
        # Restore our old settings for the terminal.
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

print_key()
