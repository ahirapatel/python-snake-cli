#!/usr/bin/env python2.7
import os
import sys
import termios
import tty
import threading
import time
import signal
import fcntl
import select

# Returns (height,width)
def get_terminal_dimensions():
    rows, columns = os.popen('stty size', 'r').read().split()
    return (int(rows), int(columns))

def get_terminal_height():
    return get_terminal_dimensions()[0]

def get_terminal_width():
    return get_terminal_dimensions()[1]

def move_to_start_of_line():
    sys.stdout.write("\r")

def move_up_one_line():
    sys.stdout.write("\033[1A")

def move_up_n_lines(n):
    sys.stdout.write("\033[1A".ljust(n))

# Moves down a line after moving up.
def clear_curr_line():
    sys.stdout.write(' '.ljust(get_terminal_width()) + '\r')

# This is used to print output to the alternative screen buffer.
# Programs like 'man' and 'tmux' print to it, making it so that
# when you leave them, their output is gone and you are back to
# the output from before running those commands.
def start_alternate_screen():
    sys.stdout.write("\033[?1049h\033[H")
    sys.stdout.flush()

def end_alternate_screen():
    sys.stdout.write("\033[?1049l")
    sys.stdout.flush()

def movement_listener():
    global movement

    arrow_key_start = '\x1b'

    fd = sys.stdin.fileno()
    # Store settings for stdin, because we have to restore them later.
    old_settings = termios.tcgetattr(fd)
    # No echo and have stdin work on a char-by-char basis.
    tty.setraw(fd)
    # Keep options for stdin, then add the nonblocking flag to it.
    flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    # Poll object.
    p = select.poll()
    p.register(fd, select.POLLIN)
    try:
        while True:
            res = p.poll(100)
            ch = sys.stdin.read(1) if res else None
            if (ch and ord(ch) == 3) or game_over:  # Ctrl-c or game ended.
                break
            if arrow_key_start == ch:
                try:
                    ch += sys.stdin.read(2)
                except IOError:
                    continue        # There was no more data to read.
                if ch == '\x1b[A':
                    movement = "up"
                elif ch == '\x1b[B':
                    movement = "down"
                elif ch == '\x1b[C':
                    movement = "right"
                elif ch == '\x1b[D':
                    movement = "left"
    finally:
        # Restore our old settings for the terminal.
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags)
        quit()



# TODO: make a game board class with get(coord_tuple), set(coord_tuple, value).
# TODO: make head draw as a different character.
# TODO: terminal has gaps between lines, try to balance this with gaps between chars on each line.
movement = "up"
movement_dicts = {"up" : (-1,0), "down" : (1,0), "left" : (0,-1), "right" : (0,1)}
head = (0,0)
tail = (0,0)
snake_body = []

game_over = False

snake_symbol = 'o'
empty_symbol = ' '
food_symbol = '*'
def play(board):
    global movement
    global game_over

    while True:
        if game_over:
            quit()
        update_game_board(board)
        draw_game_board(board)
        time.sleep(.5)

def update_game_board(board):
    global movement
    global movement_dicts
    global head
    global empty_symbol
    global snake_symbol
    global food_symbol

    def add_position((a,b), (c,d)):
        return (a+c, b+d)

    def valid_coords((a,b)):
        #return not(0 > a > get_terminal_height()) or not(0 > b > get_terminal_width())
        # TODO: Doesn't work for all bounds. Check later.
        return a >= 0 and a <= get_terminal_height() and b >= 0 and b <= get_terminal_width()

    new_head = add_position(head, movement_dicts[movement])
    if valid_coords(new_head):
        # Tail is removed each turn, and head moves in appropriate direction.
        removed_tail = snake_body[-1]
        del snake_body[-1]
        game_board[removed_tail[0]][removed_tail[1]] = empty_symbol

        snake_body.insert(0, new_head)

        # TODO: Loop in the case of where two foods are next to each other.
        # TODO: Make the above insert, this if, and below game_board access
        #       look less weirdly organized.
        if game_board[new_head[0]][new_head[1]] == food_symbol:
            game_board[new_head[0]][new_head[1]] = snake_symbol
            new_head = add_position(new_head, movement_dicts[movement])
            snake_body.insert(0, new_head)

        game_board[new_head[0]][new_head[1]] = snake_symbol

        head = new_head
    else:
        quit()

def draw_game_board(board):
    move_to_start_of_line()
    for rows in board:
        for col in rows:
            sys.stdout.write(col)
        # The \r was unneeded until I used the movement_listener function.
        sys.stdout.write('\n\r')


def init():
    global head
    global snake_symbol
    global food_symbol

    rows, cols = get_terminal_dimensions()
    # game_board[y_coord][x_coord] is how I made this work. No real reason.
    game_board = [([empty_symbol] * cols) for x in xrange(rows)]
    head = (rows / 2, cols / 2)
    game_board[head[0]][head[1]] = snake_symbol
    snake_body.append(head)

    game_board[20][20] = food_symbol
    game_board[10][30] = food_symbol
    game_board[30][50] = food_symbol

    return game_board

def signal_handler(signal, frame):
    quit(signal)

def quit(signal=None, message=""):
    global game_over
    game_over = True
    end_alternate_screen()
    sys.stdout.write(message)
    if signal:
        os._exit(0)
    else:
        sys.exit(0)

if __name__ == "__main__":
    start_alternate_screen()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    key_listener = threading.Thread(target = movement_listener)
    key_listener.start()

    game_board = init()
    play(game_board)
