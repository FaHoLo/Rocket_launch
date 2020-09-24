import asyncio

from utils import draw_frame, get_frame_size


GAMEOVER_FRAME = '''\
   _____                         ____                 
  / ____|                       / __ \                
 | |  __  __ _ _ __ ___   ___  | |  | |_   _____ _ __ 
 | | |_ |/ _` | '_ ` _ \ / _ \ | |  | \ \ / / _ \ '__|
 | |__| | (_| | | | | | |  __/ | |__| |\ V /  __/ |   
  \_____|\__,_|_| |_| |_|\___|  \____/  \_/ \___|_|   
'''


async def show_gameover(canvas):
    """Show gameover frame in the center of canvas."""
    rows_number, columns_number = canvas.getmaxyx()
    row_size, column_size = get_frame_size(GAMEOVER_FRAME)
    corner_row = rows_number // 2 - row_size // 2
    corner_column = columns_number // 2 - column_size // 2

    while True:
        draw_frame(canvas, corner_row, corner_column, GAMEOVER_FRAME)
        await asyncio.sleep(0)
