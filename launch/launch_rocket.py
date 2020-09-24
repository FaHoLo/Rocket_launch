import asyncio
import curses
from glob import glob
from itertools import cycle
import os
import random
import time

from explosion import explode
from gameover import show_gameover
import game_scenario
from obstacles import Obstacle
from physics import update_speed
import utils


BORDER_WIDTH = 1
DERIVED_WINDOW_HEIGHT = 1
ROCKET_FIRE_ROW_SIZE = 3
TIC_TIMEOUT = 0.1

coroutines = []
obstacles = []
obstacles_in_last_collisions = []
year = 1957


def draw(canvas):
    """Draw all frames and events in event loop."""

    canvas.nodelay(True)
    curses.curs_set(False)
    rows_number, columns_number = canvas.getmaxyx()
    frames = collect_frames()

    coroutines.extend([
        *generate_stars(canvas, columns_number, rows_number),
        control_rocket(canvas, (frames['rocket_frame_1'],
                       frames['rocket_frame_2']), rows_number, columns_number),
        fill_orbit_with_garbage(canvas, frames, columns_number),
        count_years(),
    ])
    # Declare year window coroutine separately, it will be called
    # after the rest, so the other objects will not shown into its area.
    # The other way of doing that trick is to use coros.insert(-1, new_coro) instead
    # of coros.append(new_coro) for all new coroutines, so we can guarantee that
    # the last element will always be the same, but this method looks less obvious
    # inside the code. If a large number of trailing coroutines appear, it is better
    # to create a new trailing coroutine list and run it after the rest.
    year_window_coroutine = show_year_window(canvas, rows_number, columns_number)

    while True:
        for coroutine in coroutines.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)
        year_window_coroutine.send(None)
        canvas.border()
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)


def collect_frames(foldername='frames'):
    """Collect .txt frames from folder."""

    frame_paths = glob(os.path.join(foldername, '*.txt'))
    frames = {}
    for frame_path in frame_paths:
        with open(frame_path, 'r') as file:
            frame_file = os.path.split(frame_path)[-1]
            frame_name = os.path.splitext(frame_file)[0]
            frames[frame_name] = file.read()
    return frames


def generate_stars(canvas, columns_number, rows_number, stars_amount=250):
    """Generate blinking stars coroutine list with random coordinates of canvas."""

    star_symbols = '+*.:'
    coords = (
        (
            random.randint(
                BORDER_WIDTH,
                rows_number-BORDER_WIDTH*3-DERIVED_WINDOW_HEIGHT
            ),
            random.randint(BORDER_WIDTH, columns_number-BORDER_WIDTH*2)
        )
        for _ in range(stars_amount)
    )
    return [
        blink(canvas, row, column, random.randint(10, 30),
              random.choice(star_symbols))
        for row, column in coords
    ]


async def blink(canvas, row, column, offset_tics, symbol='*'):
    """Blink the symbol on canvas."""

    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await utils.sleep(offset_tics)

        canvas.addstr(row, column, symbol)
        await utils.sleep(3)

        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await utils.sleep(5)

        canvas.addstr(row, column, symbol)
        await utils.sleep(3)


async def control_rocket(canvas, rocket_frames, rows_number, columns_number):
    """Draw rocket frames, change its coordinates and fires by keyboard commands."""

    row_pozition, column_pozition = rows_number/2, columns_number/2
    frame_row_size = utils.get_frame_size(
        max(rocket_frames, key=get_frame_row_size))[0]
    frame_column_size = utils.get_frame_size(
        max(rocket_frames, key=get_frame_column_size))[1]
    limits = {
        'min_row': BORDER_WIDTH,
        'min_column': BORDER_WIDTH,
        'max_row': (rows_number - frame_row_size -
                    BORDER_WIDTH*2 - DERIVED_WINDOW_HEIGHT),
        'max_column': columns_number - frame_column_size - BORDER_WIDTH,
    }
    row_speed = column_speed = 0
    rocket_animation = (rocket_frames[0], rocket_frames[0],
                        rocket_frames[1], rocket_frames[1])

    for frame in cycle(rocket_animation):
        for obstacle in obstacles:
            if obstacle.has_collision(row_pozition, column_pozition,
                                      frame_row_size-ROCKET_FIRE_ROW_SIZE,
                                      frame_column_size):
                coroutines.append(show_gameover(canvas))
                return
        utils.draw_frame(canvas, row_pozition, column_pozition, frame)
        row_pozition, column_pozition, row_speed, column_speed =\
            handle_control_commands(
                canvas, frame, row_pozition, column_pozition,
                limits, row_speed, column_speed
            )
        await asyncio.sleep(0)
        utils.draw_frame(canvas, row_pozition, column_pozition, frame,
                         negative=True)


def get_frame_row_size(frame):
    return utils.get_frame_size(frame)[0]


def get_frame_column_size(frame):
    return utils.get_frame_size(frame)[1]


def handle_control_commands(canvas, frame, row_pozition, column_pozition,
                            limits,  row_speed, column_speed):
    """Handle keyboard commands and change rocket coordinates."""

    row_direction, column_direction, space_pressed = \
        utils.read_controls(canvas)
    row_speed, column_speed = update_speed(
        row_speed, column_speed,
        row_direction, column_direction)

    utils.draw_frame(canvas, row_pozition, column_pozition, frame,
                     negative=True)

    row_pozition += row_speed
    column_pozition += column_speed

    row_pozition = min(max(row_pozition, limits['min_row']), limits['max_row'])
    column_pozition = min(max(column_pozition, limits['min_column']),
                          limits['max_column'])

    if year > 2020 and space_pressed:
        fire_row = row_pozition
        fire_column = column_pozition + utils.get_frame_size(frame)[1] // 2
        coroutines.append(fire(canvas, fire_row, fire_column, rows_speed=-2))

    utils.draw_frame(canvas, row_pozition, column_pozition, frame)
    return row_pozition, column_pozition, row_speed, column_speed


async def fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    """Display animation of gun shot, direction and speed can be specified."""

    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)

    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        for obstacle in obstacles:
            if obstacle.has_collision(row, column):
                obstacles_in_last_collisions.append(obstacle)
                return
        row += rows_speed
        column += columns_speed


async def fill_orbit_with_garbage(canvas, frames, columns_number,
                                  spawn_rate_range=(5, 15)):
    """Fill orbit with random garbage in random columns."""

    trash_frames = [
        frames['duck'],
        frames['hubble'],
        frames['lamp'],
        frames['trash_large'],
        frames['trash_small'],
        frames['trash_xl'],
    ]
    trash_speeds = (0.5, 0.6)

    while True:
        delay = game_scenario.get_garbage_delay_tics(year)
        if not delay:
            await asyncio.sleep(0)
            continue
        coroutines.append(fly_garbage(
            canvas=canvas,
            column=random.randint(BORDER_WIDTH, columns_number-BORDER_WIDTH),
            garbage_frame=random.choice(trash_frames),
            speed=random.choice(trash_speeds)
        ))
        await utils.sleep(delay)


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""

    rows_number, columns_number = canvas.getmaxyx()

    column = max(column, 0)
    column = min(column, columns_number - 1)

    # Get frame row size and run it higher so
    # that it appears gradually instead suddenly
    row = - utils.get_frame_size(garbage_frame)[0] + BORDER_WIDTH + 1

    row_size, column_size = utils.get_frame_size(garbage_frame)
    obstacle = Obstacle(row, column, row_size, column_size)
    obstacles.append(obstacle)

    while obstacle.row < rows_number - BORDER_WIDTH*2 - DERIVED_WINDOW_HEIGHT:
        if obstacle in obstacles_in_last_collisions:
            obstacles_in_last_collisions.remove(obstacle)
            coroutines.append(explode(canvas, obstacle.row+row_size//2,
                              obstacle.column+column_size//2))
            break
        utils.draw_frame(canvas, obstacle.row, obstacle.column, garbage_frame)
        await asyncio.sleep(0)
        utils.draw_frame(canvas, obstacle.row, obstacle.column, garbage_frame,
                         negative=True)
        obstacle.row += speed
    obstacles.remove(obstacle)


async def count_years(ticks_in_year=15):
    """Count years every ticks_in_year."""

    global year
    while True:
        await utils.sleep(ticks_in_year)
        year += 1


async def show_year_window(canvas, rows_number, columns_number):
    """Show window with year and year phrase at the bottom of canvas."""

    start_row = rows_number - BORDER_WIDTH * 2 - DERIVED_WINDOW_HEIGHT
    start_column = 0
    notify_window = canvas.derwin(start_row, start_column)
    text_offset = 2
    while True:
        try:
            phrase = game_scenario.PHRASES[year]
        except KeyError:
            # Do not delete the previous phrase, as it is difficult
            # to read it in a "year"
            pass
        # Add offset to the text using spaces, so there will be no other
        # objects in offset (like when we add offset in window.addstr(...))
        text = f'{" "*text_offset}{year}: {phrase}'.ljust(
            columns_number-BORDER_WIDTH*2, ' ')
        notify_window.border()
        notify_window.addstr(1, BORDER_WIDTH, text)
        await asyncio.sleep(0)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
