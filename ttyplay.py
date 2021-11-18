import struct
import io
import sys
import time
from enum import Enum
import subprocess
import png
import numpy as np
import argparse
from multiprocessing import Process, Pool, Array, Lock, Value
from PIL import Image
import csv

# https://www.utf8-chartable.de/unicode-utf8-table.pl
# https://chromium.googlesource.com/apps/libapps/+/a5fb83c190aa9d74f4a9bca233dac6be2664e9e9/hterm/doc/ControlSequences.md#SCS
# https://en.wikipedia.org/wiki/ASCII
# https://en.wikipedia.org/wiki/ANSI_escape_code

def verbose_print(a):
    if global_args.verbose:
        print(a)

def print_err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def clear_screen():
    """
    Clear and reset screen and set sane settings.

    :return: None.
    """
    cmds = (('clear',), ('reset',), ('stty', 'sane'))
    for cmd in cmds:
        subprocess.check_call(cmd)

class Colors(Enum):
    BLACK = 1
    RED = 2
    GREEN = 3
    YELLOW = 4
    BLUE = 5
    MAGENTA = 6
    CYAN = 7
    WHITE = 8
    BRIGHTBLACK = 9
    BRIGHTRED = 10
    BRIGHTGREEN = 11
    BRIGHTYELLOW = 12
    BRIGHTBLUE = 13
    BRIGHTMAGENTA = 14
    BRIGHTCYAN = 15
    BRIGHTWHITE = 16


class Cursor:
  def __init__(self,x,y,x_size,y_size):
    self.x = x
    self.y = y
    self.x_size = x_size
    self.y_size = y_size
  def inc_1_ch(self):
    self.x+=1
    if self.x == self.x_size:
        self.x = 0
        self.y += 1

class Tile:
  def __init__(self,fg,bg,char):
    self.fgcolor = fg
    self.bgcolor = bg
    self.char = char

  def get_rgb(self,c):
    if c == Colors.BLACK:
        return [0,0,0]
    elif c == Colors.RED:
        return [205,0,0]
    elif c == Colors.GREEN:
        return [0,205,0]
    elif c == Colors.YELLOW:
        return [205,205,0]
    elif c == Colors.BLUE:
        return [0,0,238]
    elif c == Colors.MAGENTA:
        return [205,0,205]
    elif c == Colors.CYAN:
        return [0,205,205]
    elif c == Colors.WHITE:
        return [229,229,229]
    elif c == Colors.BRIGHTBLACK:
        return [127,127,127]
    elif c == Colors.BRIGHTRED:
        return [255,0,0]
    elif c == Colors.BRIGHTGREEN:
        return [0,255,0]
    elif c == Colors.BRIGHTYELLOW:
        return [255,255,0]
    elif c == Colors.BRIGHTBLUE:
        return [0,0,255]
    elif c == Colors.BRIGHTMAGENTA:
        return [255,0,255]
    elif c == Colors.BRIGHTCYAN:
        return [0,255,255]
    elif c == Colors.BRIGHTWHITE:
        return [255,255,255]
    else:
        raise Exception("UNKNOWN COLOR")
  def get_fg_color(self):
    if self.char != ' ':
        return self.get_rgb(self.fgcolor)
    else:
        return [0,0,0]
  def get_bg_color(self):
    return self.get_rgb(self.bgcolor)

class Screen:
  def __init__(self,x_size,y_size):
    self.tiles = [x[:] for x in [[Tile(Colors.WHITE,Colors.BLACK,' ')] * x_size] * y_size] 
    self.x_size = x_size
    self.y_size = y_size
    self.clear()

  def clear(self):
    for x in range(0,self.x_size):
      for y in range(0,self.y_size):
        self.tiles[y][x] = Tile(Colors.WHITE,Colors.BLACK,' ')

  def clear_line(self,row,start,end):
    for x in range(start,end):
      self.tiles[row][x] = Tile(Colors.WHITE,Colors.BLACK,' ')

  def type(self,x,y,ch,fg,bg):
    self.tiles[y][x] = Tile(fg,bg,ch)

class Display(object):
  def __init__(self):
    x = 81
    y = 29
    self.cursor = Cursor(0,0,x,y) 
    self.screen = Screen(x,y)
    self.x_size = x
    self.y_size = y
    self.fg = Colors.WHITE
    self.bg = Colors.BLACK
    self.default_fg = Colors.WHITE
    self.default_bg = Colors.BLACK
    self.top_margin = 1
    self.bottom_margin = 24
    self.BRIGHT_MODE = False

  def clear_screen(self):
    self.screen.clear()

  def clear_line(self,row,start,end):
    self.screen.clear_line(row,start,end)

  def shift_all_one_row_up(self,start_y,end_y):
    for x in range(0,self.x_size):
        for y in range(start_y,end_y):
            self.screen.tiles[y][x] = self.screen.tiles[y+1][x]

  def shift_all_one_row_down(self,start_y,end_y):
    for x in range(0,self.x_size):
        for y in range(end_y,start_y,-1):
            self.screen.tiles[y][x] = self.screen.tiles[y-1][x]
    for x in range(0,self.x_size):
        self.screen.tiles[start_y][x] = Tile(Colors.WHITE,Colors.BLACK,' ')

  def handle_scrolling(self):
        #Scrolling
    if self.cursor.y > self.bottom_margin:
        self.shift_all_one_row_up(self.top_margin,self.bottom_margin)
        for x in range(0,self.x_size):
            self.screen.tiles[self.bottom_margin][x] = Tile(Colors.WHITE,Colors.BLACK,' ')
        self.cursor.y -= 1

  def delete_line(self):
    self.shift_all_one_row_up(self.cursor.y,self.bottom_margin)
    for x in range(0,self.x_size):
        self.screen.tiles[self.bottom_margin][x] = Tile(Colors.WHITE,Colors.BLACK,' ')

  def CSI_P(self,n):
    #NOTE: SHOULD THIS SHIFT THE LINE OVER?
    for x in range(self.cursor.x-n,self.cursor.x):
        self.screen.tiles[self.cursor.y][x] = Tile(Colors.WHITE,Colors.BLACK,' ')

  def reverse_line_feed(self):
    self.shift_all_one_row_down(self.top_margin-1,self.bottom_margin)

  def CSI_A(self, n):
    #Cursor up (default up)
    if n ==0:
        self.cursor.y -= 1
    else:
        self.cursor.y -= n

  def CSI_J(self,n):
    verbose_print("DOING J")
    #Clears part of the screen. .   
    if n == 0:
        self.clear_line(self.cursor.y,self.cursor.x,self.x_size)
        for y in range(self.cursor.y+1,self.y_size):
            self.clear_line(y,0,self.x_size)
    # If n is 0 (or missing), clear from cursor to end of screen
    elif n == 1:
        self.clear_line(self.cursor.y,0,self.cursor.x)
        for y in range(0,self.cursor.y):
            self.clear_line(y,0,self.x_size)
    # If n is 1, clear from cursor to beginning of the screen.
    elif n == 2 or n == 3:
        self.clear_screen()
    # If n is 2, clear entire screen (and moves cursor to upper left on DOS ANSI.SYS).
    # If n is 3, clear entire screen and delete all lines saved in the scrollback buffer (this feature was added for xterm and is supported by other terminal applications).

  def CSI_H(self,x,y):
    # Cursor Position
    if y == 0:
        y = 1
    verbose_print("DOING H (x,y):" + str(x) +','+ str(y))
    self.cursor.x = x
    self.cursor.y = y
    self.handle_scrolling()

  def CSI_G(self,x):
    # Cursor Position
    verbose_print("DOING G")
    self.cursor.x = x

  def CSI_T(self,n):
    # Scroll Down
    verbose_print("DOING T")
    for x in range(0,n):
        self.shift_all_one_row_down(self.top_margin,self.bottom_margin)

  def CSI_L(self,n):
    # Insert Lines
    verbose_print("DOING L")
    for x in range(0,n):
        self.shift_all_one_row_down(self.cursor.y,self.bottom_margin)

  def CSI_S(self,n):
    # Scroll 
    verbose_print("DOING S")
    for x in range(0,n):
        self.shift_all_one_row_up(self.top_margin,self.bottom_margin)

  def CSI_d(self,y):
    verbose_print("DOING d" + str(y))
    if y == 0:
        y=1
    self.cursor.y = y

  def CSI_r(self,top,bottom):
    self.top_margin = top
    self.bottom_margin = bottom

  def CSI_X(self,n):
    verbose_print("DOING X")
    self.clear_line(self.cursor.y,self.cursor.x,self.cursor.x + n-1)

  def CSI_M(self,n):
    verbose_print("DOING M")
    if n == 0: #default 1 if ^[M
        n = 1
    #delete n lines
    for x in range(0,n):
        self.delete_line()

  def CSI_C(self,n):
    verbose_print("DOING C")
    if n == 0:
        n = 1
    for x in range(0,n):
        self.cursor.inc_1_ch()

  def CSI_K(self,n):
    verbose_print("DOING K")
    if n == 0:
        self.clear_line(self.cursor.y,self.cursor.x,self.x_size)
    elif n == 1:
        self.clear_line(self.cursor.y,0,self.cursor.x)
    elif n == 2:
        self.clear_line(self.cursor.y,0,self.x_size)
    # !arg1 or arg1 == 0: Clear cursor to end of line
    # arg1 == 1: Clear start of line to cursor
    # arg1 == 2: Clear line

  def write_ch(self,ch):
    if ch == '\r':
        self.cursor.x = 0
    elif ch == '\n':
        self.cursor.x = 0
        self.cursor.y += 1
    else:
        self.screen.type(self.cursor.x,self.cursor.y,ch,self.fg,self.bg)
        self.cursor.inc_1_ch()

    self.handle_scrolling()

  def set_color(self,n):
    if self.BRIGHT_MODE and ((n>=30 and n<=37)or(n>=40 and n<=47)):
        n+=60


    verbose_print("set_color {}".format(n))
    if n == 0:
        self.fg = self.default_fg
        self.bg = self.default_bg
        self.BRIGHT_MODE = False
    if n ==1:
        self.BRIGHT_MODE = True
    if n == 39:
        self.fg = self.default_fg
    elif n == 49:
        self.bg = self.default_bg
    elif n == 30:
        self.fg = Colors.BLACK
    elif n == 31:
        self.fg = Colors.RED
    elif n == 32:
        self.fg = Colors.GREEN
    elif n == 33:
        self.fg = Colors.YELLOW
    elif n == 34:
        self.fg = Colors.BLUE
    elif n == 35:
        self.fg = Colors.MAGENTA
    elif n == 36:
        self.fg = Colors.CYAN
    elif n == 37:
        self.fg = Colors.WHITE

    elif n == 40:
        self.bg = Colors.BLACK
    elif n == 41:
        self.bg = Colors.RED
    elif n == 42:
        self.bg = Colors.GREEN
    elif n == 43:
        self.bg = Colors.YELLOW
    elif n == 44:
        self.bg = Colors.BLUE
    elif n == 45:
        self.bg = Colors.MAGENTA
    elif n == 46:
        self.bg = Colors.CYAN
    elif n == 47:
        self.bg = Colors.WHITE

    elif n == 90:
        self.fg = Colors.BRIGHTBLACK
    elif n == 91:
        self.fg = Colors.BRIGHTRED
    elif n == 92:
        self.fg = Colors.BRIGHTGREEN
    elif n == 93:
        self.fg = Colors.BRIGHTYELLOW
    elif n == 94:
        self.fg = Colors.BRIGHTBLUE
    elif n == 95:
        self.fg = Colors.BRIGHTMAGENTA
    elif n == 96:
        self.fg = Colors.BRIGHTCYAN
    elif n == 97:
        self.fg = Colors.BRIGHTWHITE

    elif n == 100:
        self.bg = Colors.BRIGHTBLACK
    elif n == 101:
        self.bg = Colors.BRIGHTRED
    elif n == 102:
        self.bg = Colors.BRIGHTGREEN
    elif n == 103:
        self.bg = Colors.BRIGHTYELLOW
    elif n == 104:
        self.bg = Colors.BRIGHTBLUE
    elif n == 105:
        self.bg = Colors.BRIGHTMAGENTA
    elif n == 106:
        self.bg = Colors.BRIGHTCYAN
    elif n == 107:
        self.bg = Colors.BRIGHTWHITE

def get_image(image_path):
    """Get a numpy array of an image so that one can access values[x][y]."""
    image = Image.open(image_path, "r")
    width, height = image.size
    pixel_values = list(image.getdata())
    if image.mode == "RGBA":
        channels = 4
    elif image.mode == "L":
        channels = 1
    else:
        print("Unknown mode: %s" % image.mode)
        return None
    pixel_values = np.array(pixel_values).reshape((height,width,  channels))
    return pixel_values

class TtyPlay(object):
    """
    A class to read, analyze and play ttyrecs
    """
    def __init__(self, f, speed=1.0):
        """
        Create a new ttyrec player.

        :param f: An open file object or a path to file.
        :param speed: Speed multipier, used to divide delays.
        """
        if isinstance(f, io.IOBase):
            self.file = f
        else:
            self.file = open(f, 'rb')
        self.speed = speed  # Multiplier of speed
        self.seconds = 0  # sec field of header
        self.useconds = 0  # usec field of header
        self.length = 0  # len field of header
        self.frameno = 0  # Number of current frame in file
        self.duration = 0.0  # Computed duration of previous frame
        self.frame = bytes()  # Payload of the frame
        self.display = Display()
        self.stop_count = 0
        self.display_buffer = b''
        self.TILESIZE = 32
        self.DATASIZE = 3
        self.FORGROUND_SIZE = 16


        self.previous_frame = np.ndarray(shape=(self.TILESIZE*self.display.y_size,self.TILESIZE*self.display.x_size*self.DATASIZE),dtype=np.uint8)

    def save_frame(self):
        frame_data = []
        # image = image[0+32*sprite_index_y:32+32*sprite_index_y,0+32*sprite_index_x:32+32*sprite_index_x,:]
        for y in range(0,self.display.y_size):
            for x in range(0,self.display.x_size):
                fg = self.display.screen.tiles[y][x].fgcolor
                bg = self.display.screen.tiles[y][x].bgcolor
                char = self.display.screen.tiles[y][x].char
                frame_data.append([y,x,fg.value,bg.value,char])

        if not np.array_equal(self.previous_frame,frame_data):
            with open('./data/' + str(self.frameno) + '.csv', mode='w') as frame_file:
                frame_info_writer = csv.writer(frame_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for y in range(0,self.display.y_size):
                    for x in range(0,self.display.x_size):
                        fg = self.display.screen.tiles[y][x].fgcolor
                        bg = self.display.screen.tiles[y][x].bgcolor
                        char = self.display.screen.tiles[y][x].char
                        frame_info_writer.writerow([y,x,fg.value,bg.value,char])
            self.previous_frame = frame_data

        # exit(0)

    def compute_framelen(self, sec, usec):
        """
        Compute the length of previous frame.

        :param sec: Current frame sec field
        :param usec: Current frame usec field
        :return: Float duration of previous frame in seconds
        """
        secdiff = sec - self.seconds
        usecdiff = (usec / 1000000.0) - (self.useconds / 1000000.0)
        duration = (secdiff + usecdiff) / self.speed
        if duration < 0:
            raise ValueError("ttyrec frame is in past")
        return duration

    def compute_framedelays(self):
        """
        Walk through the ttyrec file and calculate lengths of all frames.

        :return: List, containing delays for each frame.
        """
        self.file.seek(0)
        delays = []
        while self.read_frame(loop=True):
            if self.frameno > 1:
                delays.append(self.duration)
        return delays

    def read_frame(self, loop=False):
        """
        Read a ttyrec frame (header and payload).

        :param loop: If True, rewind ttyrec after reaching EOF (don't close).
        :return: True, if there's more to read, False if reached EOF.
        """
        header = self.file.read(12)
        if len(header) == 0:
            if loop:
                self.file.seek(0)
                self.frameno = 0
            else:
                self.file.close()
            return False
        elif len(header) < 12:
            raise ValueError("Short read: Couldn't read a whole ttyrec header!")
        seconds, useconds, length = struct.unpack('<III', header)
        self.frame = self.file.read(length)
        if len(self.frame) < length:
            raise ValueError("Short read: Couldn't read a whole ttyrec frame!")
        self.frameno += 1
        if self.frameno > 1:
            self.duration = self.compute_framelen(seconds, useconds)
        self.seconds = seconds
        self.useconds = useconds
        self.length = length
        return True

    def display_frame(self):
        """
        Print the frame to stdout.

        :return: None
        """
        verbose_print(self.frame)

        self.frame = self.display_buffer + self.frame            
        self.display_buffer = b''
        #exclude the encapsulating b' ___ '
        chidx = 0
        # while chidx < len(self.frame)-10:
        while (chidx < len(self.frame) and len(self.frame) < 2048) or chidx < len(self.frame)-10:
            if self.frame[chidx] == 0x08:
            #BACKSPACE
                chidx+=1
                self.display.cursor.x -= 1
                #TODO: SEE IF THIS NEEDS TO BE COMMENTED/UNCOMMENTED --v:
                self.display.screen.tiles[self.display.cursor.y][self.display.cursor.x] = Tile(Colors.WHITE,Colors.BLACK,' ')

            #Handle UNICODE                https://www.utf8-chartable.de/unicode-utf8-table.pl
            elif self.frame[chidx] == 0xe2:
                chidx+=1
                if self.frame[chidx] == 0x80:
                    chidx+=1
                    if self.frame[chidx] == 0xa0:
                        chidx+=1
                        self.display.write_ch('†')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' †' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                elif self.frame[chidx] == 0x88:
                    chidx+=1
                    if self.frame[chidx] == 0x86:
                        chidx+=1
                        self.display.write_ch('∆')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ∆' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    elif self.frame[chidx] == 0x9e:
                        chidx+=1
                        self.display.write_ch('∞')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ∞' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    elif self.frame[chidx] == 0xa9:
                        chidx+=1
                        self.display.write_ch('∩')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ∩' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)                
                elif self.frame[chidx] == 0x89:
                    chidx+=1
                    if self.frame[chidx] == 0x88:
                        chidx+=1
                        self.display.write_ch('≈')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ≈' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)
                elif self.frame[chidx] == 0x8c:
                    chidx+=1
                    if self.frame[chidx] == 0xa0:
                        chidx+=1
                        self.display.write_ch('⌠')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ⌠' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)    
                elif self.frame[chidx] == 0x96:
                    chidx+=1
                    if self.frame[chidx] == 0x93:
                        chidx+=1
                        self.display.write_ch('▓')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ▓' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)
                elif self.frame[chidx] == 0x97:
                    chidx+=1
                    if self.frame[chidx] == 0x8b:
                        chidx+=1
                        self.display.write_ch('○')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ○' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)
                elif self.frame[chidx] == 0x98:
                    chidx+=1
                    if self.frame[chidx] == 0xbc:
                        chidx+=1
                        self.display.write_ch('☼')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ☼' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)
                elif self.frame[chidx] == 0x99:
                    chidx+=1
                    if self.frame[chidx] == 0xa3:
                        chidx+=1
                        self.display.write_ch('♣')
                        verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ♣' + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                    else:
                        print("UNHANDLED UNICODE")
                        exit(0)
                else:
                    print("UNHANDLED UNICODE")
                    exit(0)
            #HANDLE ESCAPE
            elif self.frame[chidx] == 27:
                chidx+=1
                if self.frame[chidx] == ord('7') or self.frame[chidx] == ord('8'):
                    chidx+=1
                    #NOOP
                    #7 Save Cursor
                    #8 Restore Cursor
                #Keypad Numeric Mode
                elif self.frame[chidx] == ord('>'):
                    chidx+=1
                    #NOOP?
                #Control Sequence Introducer
                elif self.frame[chidx] == ord('['):
                    chidx+=1

                    #Get number (break at non number sequence)
                    number = 0
                    power = 1
                    while (chidx < len(self.frame)-1) and (self.frame[chidx] >= ord('0') and self.frame[chidx] <= ord('9')):
                        number*=10
                        number+= (int)(chr(self.frame[chidx]))
                        chidx+=1

                    #Handle ANSI Control Sequences
                    #Cursor Forware
                    if self.frame[chidx] == ord('C'):
                        chidx+=1
                        #NOTE: if number is 0 should it still move forward?
                        self.display.CSI_C(number)
                    #Delete line
                    elif self.frame[chidx] == ord('M'):
                        chidx+=1
                        #NOTE: if number is 0 should it still delete a line? (does ^[M mean delete 1 line?)
                        self.display.CSI_M(number)
                    #Scroll Down
                    elif self.frame[chidx] == ord('T'):
                        chidx+=1
                        self.display.CSI_S(number)
                    #Scroll UP
                    elif self.frame[chidx] == ord('S'):
                        chidx+=1
                        self.display.CSI_T(number)
                    #Insert Lines
                    elif self.frame[chidx] == ord('L'):
                        chidx+=1
                        self.display.CSI_L(number)
                    # Erase Characters (Delete arg1 characters after cursor)
                    elif self.frame[chidx] == ord('X'):
                        chidx+=1
                        self.display.CSI_X(number)
                    # Erase in Line
                    elif self.frame[chidx] == ord('K'):
                        chidx+=1
                        if number >= 0 and number <= 2:
                            self.display.CSI_K(number)
                        else:
                            print("Unhandled clear line")
                    #VPA Move cursor to arg1 row
                    elif self.frame[chidx] == ord('d'):
                        chidx+=1
                        self.display.CSI_d(number)
                    #Reset Mode
                    elif self.frame[chidx] == ord('l'):
                        chidx+=1
                        if number == 4:
                            verbose_print("Insertion Replacement Mode")
                        else:
                            print("Unhandled reset")
                            exit(0)
                    #Private Modes DECSET DECRST 
                    elif self.frame[chidx] == ord('?'):
                        chidx+=1
                        number = 0
                        power = 1
                        while self.frame[chidx] >= ord('0') and self.frame[chidx] <= ord('9'):
                            number*=10
                            number+= (int)(chr(self.frame[chidx]))
                            chidx+=1
                        if (number == 1 or number==7 or number == 12 or number == 25 or
                            number == 1047 or number == 1048 or number == 1049 or
                            number == 1051 or number == 1052 or number == 1060 or number==1061) and (self.frame[chidx] == ord('l') or self.frame[chidx] == ord('h')):
                            verbose_print("[?"+str(number) + chr(self.frame[chidx]))
                            chidx+=1
                            #1 Application Cursor Keys
                            #7 Wrap around
                            #12 Start blinking cursor
                            #25 Show Cursor

                            #1047 Use Alternate Screen Buffer
                            #1048 Save cursor as in DECSC
                            #1049 Combine 1047 and 1048 modes and clear
                            #1051 Set Sun function-key mode
                            #1052 Set HP function-key mode
                            #1060 Set legacy keyboard emulation (X11R6)
                            #1061 Set VT220 keyboard emulation
                            #NOOP JUST IGNORE
                        elif (number==1 or number == 0)and self.frame[chidx] == ord('c'):
                            verbose_print("[?"+str(number) + chr(self.frame[chidx]))
                            chidx+=1
                            # [?1c https://stackoverflow.com/questions/59847747/what-does-the-esc-1c-escape-sequence-do-on-the-linux-console
                        else:
                            print("Unhandled [?_l or [?_h")
                            exit(0)
                    #Erase in Display
                    elif self.frame[chidx] == ord('J'):
                        if number >= 0 and number <= 3:
                            self.display.CSI_J(number)
                            chidx+=1
                        else:
                            print("Unhandled CSI ^[#J")
                            exit(0)
                    #(Select Graphic Rendition)
                    elif self.frame[chidx] == ord('m'):
                        self.display.set_color(number)
                        chidx+=1
                    #Delete arg1 characters before cursor
                    elif self.frame[chidx] == ord('P'):
                        self.display.CSI_P(number)
                        chidx+=1
                    #Cursor UP
                    elif self.frame[chidx] == ord('A'):
                        self.display.CSI_A(number)
                        chidx+=1
                    #Cursor Position
                    elif self.frame[chidx] == ord('H'):
                        self.display.CSI_H(0,number)
                        chidx+=1
                    elif self.frame[chidx] == ord('G'):
                        self.display.CSI_G(number)
                        chidx+=1
                    elif self.frame[chidx] == ord(';'):
                        chidx+=1
                        number2 = 0
                        power2 = 1
                        while self.frame[chidx] >= ord('0') and self.frame[chidx] <= ord('9'):
                            number2*=10
                            number2+= (int)(chr(self.frame[chidx]))
                            chidx+=1
                        #Cursor Position
                        if self.frame[chidx] == ord('H'):
                            #Moves the cursor to row n, column m
                            self.display.CSI_H(number2,number)
                            chidx+=1
                        #Select Graphic Rendition
                        elif self.frame[chidx] == ord('m'):
                            self.display.set_color(number)
                            self.display.set_color(number2)
                            chidx+=1
                        #Set Top and Bottom Margins
                        elif self.frame[chidx] == ord('r'):
                            self.display.CSI_r(number,number2)
                            verbose_print("set_margins")
                            chidx+=1
                        else:
                            chidx+=1
                            number3 = 0
                            while self.frame[chidx] >= ord('0') and self.frame[chidx] <= ord('9'):
                                number3*=10
                                number3+= (int)(chr(self.frame[chidx]))
                                chidx+=1
                            if self.frame[chidx] == ord('m'):
                                self.display.set_color(number)
                                self.display.set_color(number2)
                                self.display.set_color(number3) #ex: \x1b[0;10;1m - 1 means BOLD BRIGHT so make the next stuff bright
                                chidx+=1
                            else:
                                print("UNHANDLED CSI ESCAPE ^[#;#*",(chr(self.frame[chidx])))
                                exit(0)
                    else:
                        print("UNHANDLED CSI ESCAPE Letter:" + chr(self.frame[chidx]))
                        exit(0)

                elif self.frame[chidx] == ord(')'):
                    chidx+=1
                    #Set G1 character set to 
                    # https://chromium.googlesource.com/apps/libapps/+/a5fb83c190aa9d74f4a9bca233dac6be2664e9e9/hterm/doc/ControlSequences.md#SCS
                    if self.frame[chidx] == ord('0'): #Graphics
                        verbose_print("set_ascii 0)")
                        chidx+=1
                        #NOOP JUST IGNORE

                elif self.frame[chidx] == ord('('):
                    #Set G0 character set (VT100) [Graphic Codesets for GL/GR (SCS)]
                    chidx+=1
                    if self.frame[chidx] == ord('B'):
                        #United States (ASCII)
                        verbose_print("set_ascii (B")
                        chidx+=1
                        #NOOP JUST IGNORE
                    else:
                        print("UNHANDLED Graphic Codeset")
                #Keypad Application Mode
                elif self.frame[chidx] == ord('='):
                    chidx+=1
                    verbose_print("Keypad Application Mode")
                # Reverse Line Feed? (Reverse Index?) (Move up one line keeping column position)
                elif self.frame[chidx] == ord('M'):
                    chidx+=1
                    self.display.reverse_line_feed()
                    verbose_print("Reverse Line Feed")
                else:
                    print("UNHANDLED NON CSI ESCAPE")
                    exit(0)
            else:
                self.display.write_ch(chr(self.frame[chidx]))
                if len(self.frame) > chidx:
                    verbose_print(str(chidx) + ' ' + str(self.frame[chidx]) + ' ' + chr(self.frame[chidx]) + " cursor(x,y):"+str(self.display.cursor.x) + "," + str(self.display.cursor.y))
                chidx+=1        

            if len(self.frame) >= 2060 and int(str(chidx)) > 2050:
                self.display_buffer = self.frame[chidx:]
                chidx = len(self.frame)

        if chidx < len(self.frame):
            self.display_buffer = self.frame[chidx:]
            chidx = len(self.frame)
        #sys.stdout.write(str(self.frame, errors='ignore'))
        sys.stdout.flush()
        self.stop_count += 1

        print("FRAME:" + str(self.frameno))

        self.save_frame()

    def close(self):
        """
        Close the ttyrec file object.

        :return: None
        """
        self.frame = None
        self.file.close()

    def __enter__(self):
        """
        Allows to use ttyrec player with context management.

        :return: Self
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Allows to use ttyrec player with context management.

        :param exc_type: Exception type (if any).
        :param exc_val: Exception object (if any).
        :param exc_tb: Exception backtrace (if any).
        :return: None
        """
        self.file.close()

if __name__ ==  '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-verbose", help="increase output verbosity",action="store_true")
    parser.add_argument("-path", help="specify path of ttyrec",required=True)
    global_args = parser.parse_args()

    tp = TtyPlay(global_args.path, 1.0)
    vislength = 0.0
    delays = tp.compute_framedelays()
    fps = 30
    try:
        while tp.read_frame():
            # if tp.frameno > 291800:
            if tp.frameno > -1:
                tp.display_frame()

                if tp.frameno <= len(delays):
                    vislength += delays[tp.frameno - 1]
                    if vislength <= 0.1:  # GIF counts delays in hundredths of seconds
                        continue  # We discard frames that are less than this.
                    else:
                        vislength = 0.0
                # Let the terminal emulator draw the frame. Without this it's possible
                # to capture partial draws. It's not a strict guarantee, but seems to
                # work reasonably well.
                time.sleep(1.0 / fps)
                #GET DATA

    except ChildProcessError as e:
        clear_screen()
        print_err("Main processing loop failed:")
        print_err("{0}: {1}".format(type(e).__name__, e))
        sys.exit(1)
    except KeyboardInterrupt:
        time.sleep(0.1)
        clear_screen()
        print_err("User has cancelled rendering")
        sys.exit(1)

    clear_screen()
    print("DONE")


