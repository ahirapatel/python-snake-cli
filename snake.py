#!/usr/bin/env python
import os
import sys
import termios
import tty
import threading
import time
import signal
import fcntl
import select
from random import randint

# Returns (height,width)
def get_terminal_dimensions():
    rows, columns = os.popen('stty size', 'r').read().split()
    return (int(rows), int(columns))

def get_terminal_height():
    return get_terminal_dimensions()[0]

def get_terminal_width():
    return get_terminal_dimensions()[1]

# The terminal coordinates start at (1,1) so add 1 to properly work with
# our 0 indexed lists.
def go_to_terminal_coords(r,c):
    sys.stdout.write("\033[{0};{1}f".format(r+1,c+1))

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

def movement_listener(snake):
    global game_over
    global key_quit

    arrow_key_start = '\x1b'
    # The bytes that match up with the paired movement.
    bytes_to_movement_dict = {'\x1b[A' : "up",'\x1b[B' : "down",'\x1b[C' : "right",'\x1b[D' : "left"}

    fd = sys.stdin.fileno()
    # Store settings for stdin, because we have to restore them later.
    orig_term_settings = termios.tcgetattr(fd)
    quit.orig_term_settings = orig_term_settings
    # No echo and have stdin work on a char-by-char basis.
    tty.setraw(fd)
    # Keep options for stdin, then add the nonblocking flag to it.
    orig_flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    quit.orig_flags = orig_flags
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
                snake.set_movement(bytes_to_movement_dict.get(ch))
    finally:
        # Restore our old settings for the terminal.
        termios.tcsetattr(fd, termios.TCSADRAIN, orig_term_settings)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_flags)

# TODO: Add board drawing/printing functions to the Board class.
class Board(object):
    def __init__(self, coord):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        board_rows, board_cols = coord

        self.rows = board_rows - 1
        # Terminal line heights are greater than character widths, so correct
        # for this by halving columns and padding with grid_symbol.
        self.columns = board_cols // 2
        # game_board[y_coord][x_coord] is how I made this work. No real reason.
        # TODO: Change to (x,y), because I don't like it this way.
        self.board = [([grid_symbol] * self.columns) for x in range(self.rows)]
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

    def is_valid_coord(self, coord):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        a, b = coord
        return a >= 1 and a < self.height()-1 and b >= 1 and b < self.width()-1

    def width(self):
        return self.columns

    def height(self):
        return self.rows

    def draw_initial_board(self):
        bstr = ""
        for rows in self.board:
            bstr += empty_symbol.join(rows) + "\n\r"
        sys.stdout.write(bstr)
        # Since I do skip drawing every other character spot on the terminal
        # to make the map feel more even, I can't just print the walls from
        # list or else there will be gaps.
        horiz_walls = ''.join(wall_symbol * (self.columns*2-1))
        go_to_terminal_coords(0,0)
        sys.stdout.write(horiz_walls)           # Top wall.
        go_to_terminal_coords(self.rows-1, 0)
        sys.stdout.write(horiz_walls)           # Bottom wall.
        sys.stdout.flush()

    def draw(self, coord, symbol):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        r, c = coord
        go_to_terminal_coords(r,c*2)                        # Go to location.
        sys.stdout.write(symbol)                            # Write to location.
        go_to_terminal_coords(self.rows, self.columns*2)    # Go to edge of terminal.
        sys.stdout.flush()                                  # Flush to have it draw.

    def draw_no_gaps(self, coord, symbol):
        self.draw(coord, symbol + symbol)

class Snake(object):
    movement_dicts = {"up" : (-1,0), "down" : (1,0), "left" : (0,-1), "right" : (0,1)}

    def __init__(self, head):
        self.movement = "up"                # Current direction.
        self.removed_tail = head            # Where the tail used to be.
        self.head = head                    # Where the head is currently.
        self.snake_body = [head]            # The parts of the snake body.
        self.just_eaten = grid_symbol       # What the snake ate this tick.
        self.lock = threading.Lock()        # Lock for self.movement read/write.
        # TODO: Can probably make this redundant, but do I like this way better?
        self.movement_processed = True      # To ensure we don't process.

    def move(self):
        def add_position(coord1, coord2):
            if len(coord1) != 2 or len(coord2) != 2:
                raise Exception # TODO: An actual exception
            a, b = coord1
            c, d = coord2
            return (a+c, b+d)

        self.lock.acquire()

        # Move the head to its new position.
        self.head = add_position(self.head, self.movement_dicts[self.movement])
        self.snake_body.insert(0, self.head)
        # Remove the tail.
        self.removed_tail = self.snake_body[-1]
        del self.snake_body[-1]
        # This movement was processed.
        self.movement_processed = True

        self.lock.release()
        return self.head

    def consume(self, target):
        # If food is eaten, then grow by adding the tail in the spot from
        # where it was previously removed.
        self.just_eaten = target
        if target == food_symbol:
            self.snake_body.append(self.removed_tail)

    def is_hungry(self):
        return self.just_eaten != food_symbol

    def is_dead(self):
        return self.just_eaten in [wall_symbol, snake_symbol]

    def set_movement(self, new_movement):
        # The snake body shouldn't be able to turn the direction it came from,
        # So ignore those key presses.
        # TODO: Can probably neatify this.
        self.lock.acquire()
        if self.movement_processed:
            self.movement_processed = False
            opposite_list = [("left", "right"), ("right", "left"), ("down", "up"), ("up", "down")]
            move_pair = (self.movement, new_movement)
            if not( (move_pair in opposite_list and len(self.snake_body) != 1) or new_movement is None ):
                self.movement = new_movement
        self.lock.release()

    def get_head(self):
        return self.snake_body[0]

    def get_old_tail(self):
        return self.removed_tail


# TODO: Less globals. Soon.
# TODO: make head draw as a different character.
# TODO: Looks terrible on light backgrounds.
GREEN = '\033[92m'
YELLOW = '\033[93m'
TEAL = '\033[36m'
BLUEBACK = "\x1b[44m"
END = '\033[0m'

num_food = 40

game_over = False
sig_quit = False
key_quit = False

snake_symbol = GREEN + 'o' + END
empty_symbol = ' '
grid_symbol = '.'
food_symbol = YELLOW + '*' + END
wall_symbol = BLUEBACK + GREEN + '|' + END

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


def play(board, snake):
    while True:
        exit_as_needed()
        update_game_board(board, snake)
        draw_game_board(board, snake)
        # TODO: Make speed based on parameter.
        time.sleep(.1)

def update_game_board(board, snake):
    global num_food
    global game_over

    # Move the head in the right direction, then keep going if food is present.
    new_head = snake.move()

    # TODO: Make better flowing by passing snake the game board, or game board the snake.
    game_board.set(snake.get_old_tail(), grid_symbol)
    snake.consume(game_board.get(new_head))
    game_board.set(new_head, snake_symbol)

    # Check if snake is within the board, and if it collides with itself.
    if board.is_valid_coord(new_head) and not snake.is_dead():
        if not snake.is_hungry():
            num_food = num_food - 1
            spawn_new_food(game_board)
    else:
        game_over = True

def spawn_new_food(game_board):
    spawned = False
    while not spawned:
        r = randint(0, game_board.height()-1)
        c = randint(0, game_board.width()-1)
        coord = (r,c)
        if not game_board.is_valid_coord(coord) or game_board.get(coord) in [snake_symbol, wall_symbol]:
            continue
        game_board.set(coord, food_symbol)
        game_board.draw(coord, food_symbol)
        spawned = True

# A normal game of snake is pretty easy, just sweep the board from left to right.
# So let's attempt to make it harder a wee bit.
def spawn_obstacle(game_board):
    # TODO: Food can become impossible to reach with the obstacles.
    # TODO: Moving obstacles.
    # Just draw the obstacle as below (add a list of strings) to have it as
    # an obstacle on the map. Note that they will be stretched out because
    # 2 terminal columns = 1 game column and 1 terminal row == 1 game row.
    # It looks a little weird because of this though.
    obstacles = [   ["x" * 25],
                    ["x"] * 35,
                    ["xxxxx",
                     "  x  ",
                     "  x  "], # T symbol
                    ["   xxx   ",
                     "  x  x xx",
                     "xxx  x   ",
                     "     xxx "], # I have no idea what this is
                    ["x         x",
                     " x       x ",
                     "  xx x xx  ",
                     " x       x ",
                     "x         x"], # No idea part two.
                    ["    xx        ",
                     "  xx    xxxxx ",
                     "xx    xx     x",
                     "x     x      x",
                     "xx     x    xx",
                     " xx        xx ",
                     "  xx      xx  ",
                     "    xxxxxx    "] # Spiral thingy.
                ]
    def obstacle_validate(coord, obs):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        r, c = coord
        for y, curr_row in enumerate(obs):
            for x, curr_char in enumerate(curr_row):
                if not game_board.is_valid_coord((y+r,x+c)) or game_board.get((y+r,x+c)) in [snake_symbol, food_symbol, wall_symbol]:
                    return False
        return True

    def obstacle_make(coord, obs):
        if len(coord) != 2:
            raise Exception # TODO: An actual exception
        r, c = coord
        for y, curr_row in enumerate(obs):
            for x, curr_char in enumerate(curr_row):
                if curr_char == 'x':
                    game_board.set((y+r,x+c), wall_symbol)
                    game_board.draw_no_gaps((y+r,x+c), wall_symbol)

    location_found = False
    while not location_found:
        r = randint(0, game_board.height()-1)
        c = randint(0, game_board.width()-1)
        obs_idx = randint(0, len(obstacles)-1)
        coord = (r,c)
        location_found = obstacle_validate(coord, obstacles[obs_idx])
        if location_found:
            obstacle_make(coord, obstacles[obs_idx])

# TODO: Just make game_board have a queue of things to draw, then call it instead
# of this.
def draw_game_board(board, snake):
    if snake.is_hungry():
        game_board.draw(snake.get_old_tail(), grid_symbol)
    game_board.draw(snake.get_head(), snake_symbol)

def init():
    game_board = Board(get_terminal_dimensions())

    # TODO: I don't like this.
    snake = Snake((game_board.height() // 2, game_board.width() // 2))
    game_board.set(snake.get_head(), snake_symbol)

    # Draw the initial board, and then only redraw the changes.
    game_board.draw_initial_board()

    # TODO: Make num_food based on board size
    spawn_new_food(game_board)
    # TODO: Have something to stop spawning walls, not an arbitrary number.
    for i in range(25):
        spawn_obstacle(game_board)

    return game_board, snake

def signal_handler(signal, frame):
    global sig_quit
    sig_quit = True

def quit(kill_all=None, message=""):
    global game_over
    global key_quit
    global sig_quit

    game_over = True

    # Restore terminal settings to how they were before.
    end_alternate_screen()
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, quit.orig_term_settings)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, quit.orig_flags)

    if message:
        sys.stdout.write(message + '\n')

    if signal:
        os._exit(0)
    else:
        sys.exit(0)

if __name__ == "__main__":
    # TODO: Getting to the setraw can take too long due to the obstacles,
    #       so setraw immediately here, or make a drawing queue and draw after
    #       setraw has been called. An arrow key or something can be printed
    #       messing up our ever so delicate alignment.
    start_alternate_screen()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    game_board, snake = init()

    key_listener = threading.Thread(target = movement_listener, args=(snake,))
    key_listener.start()

    play(game_board, snake)
