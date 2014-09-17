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

class Board(object):
    def __init__(self, (board_rows, board_cols)):
        self.rows = board_rows - 1
        # Terminal line heights are greater than character widths, so correct
        # for this by halving columns and padding empty_symbol in __str__()
        self.columns = board_cols / 2
        # game_board[y_coord][x_coord] is how I made this work. No real reason.
        # TODO: Change to (x,y), because I don't like it this way.
        self.board = [([empty_symbol] * self.columns) for x in xrange(self.rows)]
        self.board[0] = [wall_symbol] * self.columns
        self.board[-1] = [wall_symbol] * self.columns
        for columns in self.board:
            columns[0] = wall_symbol
            columns[-1] = wall_symbol
    def get(self, coord):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        r, c = coord
        return self.board[r][c]
    def set(self, coord, value):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        r, c = coord
        self.board[r][c] = value
    def is_valid_coord(self, (a,b)):
        return a >= 1 and a < self.height()-1 and b >= 1 and b < self.width()-1 \
                and self.get((a,b)) != wall_symbol
    def width(self):
        return self.columns
    def height(self):
        return self.rows
    def __str__(self):
        bstr = ""
        for rows in self.board:
            for col in rows:
                # empty_symbol is for char width and line height discrepancy.
                bstr += col + empty_symbol
            # The \r was unneeded until I used the movement_listener function.
            bstr += '\n\r'
        return bstr


# TODO: Make everything pretty colors.
# TODO: make head draw as a different character.
num_food = 35
movement = "up"
movement_dicts = {"up" : (-1,0), "down" : (1,0), "left" : (0,-1), "right" : (0,1)}
head = (0,0)
snake_body = []

game_over = False

snake_symbol = 'o'
empty_symbol = ' '
food_symbol = '*'
wall_symbol = '|'
def play(board):
    while True:
        if game_over:
            quit()
        update_game_board(board)
        draw_game_board(board)
        # TODO: Make speed based on parameter.
        time.sleep(.2)

def update_game_board(board):
    global head

    def add_position((a,b), (c,d)):
        return (a+c, b+d)

    new_head = add_position(head, movement_dicts[movement])
    if board.is_valid_coord(new_head):
        # Tail is removed each turn, and head moves in appropriate direction.
        removed_tail = snake_body[-1]
        del snake_body[-1]
        game_board.set(removed_tail, empty_symbol)

        snake_body.insert(0, new_head)

        # TODO: Loop in the case of where two foods are next to each other.
        # TODO: Make the above insert, this if, and below game_board access
        #       look less weirdly organized.
        if game_board.get(new_head) == food_symbol:
            game_board.set(new_head, snake_symbol)
            new_head = add_position(new_head, movement_dicts[movement])
            snake_body.insert(0, new_head)

        game_board.set(new_head, snake_symbol)

        head = new_head
    else:
        quit()

def draw_game_board(board):
    sys.stdout.write(str(board))


def init():
    import random
    global head

    game_board = Board(get_terminal_dimensions())

    # TODO: I don't like this.
    head = (game_board.height() / 2, game_board.width() / 2)
    snake_body.append(head)
    game_board.set(head, snake_symbol)

    # TODO: Make num_food based on board size
    i = 0
    while i < num_food:
        r = random.randint(0, game_board.height()-1)
        c = random.randint(0, game_board.width()-1)
        # TODO: check this isn't on top of the snake
        if not game_board.is_valid_coord((r,c)):
            continue
        game_board.set((r,c), food_symbol)
        i += 1


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
