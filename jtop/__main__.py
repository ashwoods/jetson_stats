#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2018, Raffaello Bonghi <raffaello@rnext.it>
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright 
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its 
#    contributors may be used to endorse or promote products derived 
#    from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND 
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, 
# BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE 
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
    Graphic reference:
    http://urwid.org/examples/index.html
    https://npyscreen.readthedocs.io/
    https://github.com/chubin/cheat.sh
    
    https://stackoverflow.com/questions/6840420/python-rewrite-multiple-lines-in-the-console
    
    https://docs.python.org/3.3/howto/curses.html#attributes-and-color
    http://toilers.mines.edu/~jrosenth/101python/code/curses_plot/
"""
import re, argparse, time
# System and signal
import signal, os, sys
# Logging
import logging
# control command line
import curses
# Launch command
import subprocess as sp
# Tegrastats objext reader
from .jtop import Tegrastats
# GUI jtop interface
from .jtopgui import JTOPGUI, all_info, GPU, Variables

def signal_handler(sig, frame):
    """
        Close the system when catch SIGIN (CTRL-C)
    """
    tegra.close()
    sys.exit(0)
    
# The easiest way to use curses is to use a wrapper around a main function
# Essentially, what goes in the main function is the body of your program,
# The `stdscr' parameter passed to it is the curses screen generated by our
# wrapper.
def gui(stdscr, args, tegra):
    # In this program, we don't want keystrokes echoed to the console,
    # so we run this to disable that
    curses.noecho()

    # Additionally, we want to make it so that the user does not have to press
    # enter to send keys to our program, so here is how we get keys instantly
    curses.cbreak()
    # Define pairing colorss
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)

    # Hide the cursor
    curses.curs_set(0)

    # Lastly, keys such as the arrow keys are sent as funny escape sequences to
    # our program. We can make curses give us nicer values (such as curses.KEY_LEFT)
    # so it is easier on us.
    stdscr.keypad(True)
    
    # Refreshing page curses loop
    # https://stackoverflow.com/questions/54409978/python-curses-refreshing-text-with-a-loop
    stdscr.nodelay(1)
    # Initialization Menu
    pages = JTOPGUI(stdscr, [ {"name":"ALL",  "func": all_info}, 
                              {"name":"GPU",  "func": GPU}, 
                              {"name":"INFO", "func": Variables},
                            ])
    # Start with selected page
    pages.set(args.page)
    # Here is the loop of our program, we keep clearing and redrawing in this loop
    while True:
        # First, clear the screen
        stdscr.erase()
        # Write head of the jtop
        head_string = "jtop - Raffaello Bonghi"
        stdscr.addstr(0, 0, head_string, curses.A_BOLD)
        if os.getuid() != 0:
            stdscr.addstr(0, len(head_string) + 1, "- PLEASE RUN WITH SUDO", curses.color_pair(1))
        stdscr.addstr(1, 0, os.environ["JETSON_DESCRIPTION"] + " - Jetpack " + os.environ["JETSON_JETPACK"] + " [L4T " + os.environ["JETSON_L4T"] + "]", curses.A_BOLD)
        
        # Read status tegra
        stat = tegra.read
        # Draw pages
        pages.draw(stat)
        # Draw the screen
        stdscr.refresh()
        # Set a timeout and read keystroke
        stdscr.timeout(args.refresh)
        key = stdscr.getch()
        # keyboard check list
        if key == curses.KEY_LEFT:
            pages.decrease()
        elif key == curses.KEY_RIGHT:
            pages.increase()
        elif key in [ ord(str(n)) for n in range(10) ]:
            num = int(chr(key))
            pages.set(num)
        elif key == ord('q') or key == ord('Q'):
            break

def import_os_variables(SOURCE, PATTERN="JETSON_"):
    if os.path.isfile(SOURCE):
        proc = sp.Popen(['bash', '-c', 'source {} && env'.format(SOURCE)], stdout=sp.PIPE)
        source_env = {tup[0].strip(): tup[1].strip() for tup in map(lambda s: s.strip().split('=', 1), proc.stdout)}
        return { k: v for k, v in source_env.items() if PATTERN in k }
    else:
        logging.error("File does not exist")
        return {}
        
def main():
    # Add arg parser
    parser = argparse.ArgumentParser(description='jtop is system monitoring utility that runs on the terminal')
    parser.add_argument('-r', dest="refresh", help='refresh interval', type=int, default='500')
    parser.add_argument('--server', help='Run jtop json server', action="store_true", default=False)
    parser.add_argument('-p', dest="port", help='Set server port', default='5555')
    parser.add_argument('--debug', dest="debug", help='Run with debug logger', action="store_true", default=False)
    parser.add_argument('--page', dest="page", help='Open fix page', type=int, default=1)
    # Parse arguments
    args = parser.parse_args()
    # Set logging level
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, filename='jtop.log', filemode='w', 
                            format='%(name)s - %(levelname)s - %(message)s')
    # Catch SIGINT (CTRL-C)
    signal.signal(signal.SIGINT, signal_handler)
    # Load all Jetson variables
    for k, v in import_os_variables('/etc/jetson_easy/jetson_variables').items():
        os.environ[k] = v
    # Open tegrastats reader and run the curses wrapper
    with Tegrastats(interval=args.refresh) as tegra:
        if args.server:
            while True:
                # Read tegra stats
                stat = tegra.read()
                # TODO: Convert print to server post
                print(stat)
                # Sleep before send new stat
                time.sleep(1)
        else:
            # Call the curses wrapper
            curses.wrapper(gui, args, tegra)

if __name__ == "__main__":
    main()
#EOF
