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
    global game_over
    global orig_term_settings
    global orig_flags
    global key_quit

    arrow_key_start = '\x1b'

    fd = sys.stdin.fileno()
    # Store settings for stdin, because we have to restore them later.
    orig_term_settings = termios.tcgetattr(fd)
    # No echo and have stdin work on a char-by-char basis.
    tty.setraw(fd)
    # Keep options for stdin, then add the nonblocking flag to it.
    orig_flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_flags | os.O_NONBLOCK)
    # Poll object.
    p = select.poll()
    p.register(fd, select.POLLIN)
    try:
        while True:
            res = p.poll(100)
            ch = sys.stdin.read(1) if res else None
            if (ch and ord(ch) == 3):  # Ctrl-c or game ended.
                key_quit = True
                break
            elif game_over:
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
        termios.tcsetattr(fd, termios.TCSADRAIN, orig_term_settings)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_flags)

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


# TODO: make head draw as a different character.
# TODO: Spawn things on board as previous part is eaten.
# TODO: Redraw only the parts of the board that change, eg the snake, because
#       sometimes it seems the screen takes too long to print and it tears.
GREEN = '\033[92m'
YELLOW = '\033[93m'
TEAL = '\033[36m'
END = '\033[0m'

num_food = 40
movement = "up"
movement_dicts = {"up" : (-1,0), "down" : (1,0), "left" : (0,-1), "right" : (0,1)}
head = (0,0)
snake_body = []

game_over = False
sig_quit = False
key_quit = False

snake_symbol = GREEN + 'o' + END
empty_symbol = ' '
food_symbol = YELLOW + '*' + END
wall_symbol = TEAL + '|' + END

orig_term_settings = None
orig_flags = None

def exit_as_needed():
    global game_over
    if game_over:
        quit(message="Game Over!")
    elif num_food == 0:
        quit(message="You win!")
    elif sig_quit:
        quit(kill_all=True, message="Process was politely terminated.")
    elif key_quit:
        quit(message="User quit")


def play(board):
    while True:
        exit_as_needed()
        update_game_board(board)
        draw_game_board(board)
        # TODO: Make speed based on parameter.
        time.sleep(.1)

def update_game_board(board):
    global head
    global num_food
    global game_over

    def add_position((a,b), (c,d)):
        return (a+c, b+d)

    # NOTE: Snake head moves and keeps moving if food present, but maybe I want
    #       to make it so the user can choose where to move after food is eaten
    # Move the head in the right direction, then keep going if food is present.
    food_or_move = True
    while food_or_move:
        new_head = add_position(head, movement_dicts[movement])

        # Check if snake is within the board, and if it collides with itself.
        if board.is_valid_coord(new_head) and board.get(new_head) != snake_symbol:
            # Food is present so keep moving the head by relooping.
            food_or_move = (game_board.get(new_head) == food_symbol)
            num_food = num_food - 1 if food_or_move else num_food
            # Place the new head.
            snake_body.insert(0, new_head)
            game_board.set(new_head, snake_symbol)
            head = new_head
        else:
            game_over = True
            break

    # Tail is removed each turn.
    removed_tail = snake_body[-1]
    del snake_body[-1]
    game_board.set(removed_tail, empty_symbol)

def draw_game_board(board):
    sys.stdout.write(str(board))
    sys.stdout.flush()


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
        coord = (r,c)
        if not game_board.is_valid_coord(coord) or coord == head:
            continue
        game_board.set((r,c), food_symbol)
        i += 1

    quit.cleaning_up = False

    return game_board

def signal_handler(signal, frame):
    global sig_quit
    sig_quit = True

def quit(kill_all=None, message=""):
    global game_over
    global key_quit
    global sig_quit

    if quit.cleaning_up == True:
        sys.exit(0)
    quit.cleaning_up = True
    game_over = True
    key_quit = True
    sig_quit = True

    # Restore terminal settings to how they were before.
    end_alternate_screen()
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, orig_term_settings)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_flags)

    if message:
        sys.stdout.write(message + '\n')

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
