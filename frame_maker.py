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
from PIL import Image, ImageDraw, ImageFont
import csv
from os import listdir
from os.path import isfile, join
from threading import Thread
from queue import Queue
import tqdm

def get_rgb(c):
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

class FrameConstructor():
    def __init__(self,TILESIZE,DISPLAY_Y_SIZE,DISPLAY_X_SIZE,DATASIZE):
        self.TILESIZE = 32
        self.DISPLAY_Y_SIZE = DISPLAY_Y_SIZE
        self.DISPLAY_X_SIZE = DISPLAY_X_SIZE
        self.DATASIZE = DATASIZE
        self.png_array = np.ndarray(shape=(TILESIZE*DISPLAY_Y_SIZE,TILESIZE*DISPLAY_X_SIZE,DATASIZE),dtype=np.uint8)
        self.sprite_playerpng = get_image("player.png")
        self.sprite_wallpng = get_image("wall.png")
        self.sprite_floorpng = get_image("floor.png")
        self.sprite_featpng = get_image("feat.png")
        self.sprite_mainpng = get_image("main.png")
        self.sprite_iconspng = get_image("icons.png")


    def clear_png_array(self):
        self.png_array = np.ndarray(shape=(self.TILESIZE*self.DISPLAY_Y_SIZE,self.TILESIZE*self.DISPLAY_X_SIZE,self.DATASIZE),dtype=np.uint8)

    def construct_char_tile(self,y,x,fg,bg,char):
        fontname = "Menlo.ttc"
        fontsize = 28
        colorText = (fg.name).replace('BRIGHT','')
        colorBackground = (bg.name).replace('BRIGHT','')
        
        bold = 1 if ("BRIGHT" in fg.name) else 0
        text = char
        img = Image.new('RGB', (32, 32), colorBackground)
        font = ImageFont.truetype(fontname, fontsize,index=bold)
        d = ImageDraw.Draw(img)
        d.text((0, -1), text, fill=colorText, font=font)
        return np.asarray(img)

    def construct_tile(self,y,x,fg,bg,char):
        # sprite_image = get_image("player.png")

        # fg = self.display.screen.tiles[y][x].fgcolor
        # bg = self.display.screen.tiles[y][x].bgcolor
        # char = self.display.screen.tiles[y][x].char

        #Default
        source_png = self.sprite_floorpng
        sprite_index_y = 0
        sprite_index_x = 32 
        sprite_size_x = 32
        sprite_size_y = 32

        #EMPTY
        if fg == Colors.WHITE and bg == Colors.BLACK and char == ' ':
            source_png = self.sprite_floorpng
            sprite_index_y = 0
            sprite_index_x = 0
        #EMPTY 2
        elif fg == Colors.BLUE and bg == Colors.BLACK and char == ' ':
            source_png = self.sprite_floorpng
            sprite_index_y = 0
            sprite_index_x = 0 
        #FLOOR SEEN
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == '.':
            source_png = self.sprite_floorpng
            sprite_index_y = 0
            sprite_index_x = 64


        #FLOOR UNSEEN
        elif fg == Colors.BLUE and bg == Colors.BLACK and char == '.':
            source_png = self.sprite_floorpng
            sprite_index_y = 0
            sprite_index_x = 544
        #Water
        elif fg == Colors.BLUE and bg == Colors.BLACK and char == '≈':
            source_png = self.sprite_floorpng
            sprite_index_y = 0
            sprite_index_x = 576


        #WALL SEEN
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == '#':
            source_png = self.sprite_wallpng
            sprite_index_y = 0
            sprite_index_x = 0
        #WALL UNSEEN //opacity reduced
        elif fg == Colors.BLUE and bg == Colors.BLACK and char == '#':
            source_png = self.sprite_wallpng
            sprite_index_y = 32
            sprite_index_x = 352


        #Downstairs trapdoor (untraveled)
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == '>':
            source_png = self.sprite_featpng
            sprite_index_y = 224
            sprite_index_x = 192
            sprite_size_x = 30
            sprite_size_y = 25
        #Downstairs (untraveled)
        elif fg == Colors.BRIGHTWHITE and bg == Colors.BRIGHTBLACK and char == '>':
            source_png = self.sprite_featpng
            sprite_index_y = 224
            sprite_index_x = 128
            sprite_size_x = 32
            sprite_size_y = 32
        #UPSTAIRS (traveled)
        elif fg == Colors.GREEN and bg == Colors.BLACK and char == '<':
            source_png = self.sprite_featpng
            sprite_index_y = 224
            sprite_index_x = 160
            sprite_size_x = 32
            sprite_size_y = 32
        #UPSTAIRS
        elif fg == Colors.BLACK and bg == Colors.GREEN and char == '<':
            source_png = self.sprite_featpng
            sprite_index_y = 224
            sprite_index_x = 160
            sprite_size_x = 32
            sprite_size_y = 32

        #EXIT
        elif fg == Colors.BRIGHTBLUE and bg == Colors.BRIGHTBLACK and char == '<':
            source_png = self.sprite_featpng
            sprite_index_y = 224
            sprite_index_x = 96


        #AUTOTRAVEL FOOTSTEP OUT OF LOS
        elif fg == Colors.BLACK and bg == Colors.BLUE and char == '.':
            source_png = self.sprite_iconspng
            sprite_index_y = 32
            sprite_index_x = 160
            sprite_size_x = 18
            sprite_size_y = 16
        #AUTOTRAVEL FOOTSTEP IN LOS
        elif fg == Colors.BLACK and bg == Colors.WHITE and char == '.':
            source_png = self.sprite_iconspng
            sprite_index_y = 32
            sprite_index_x = 160
            sprite_size_x = 18
            sprite_size_y = 16

 
        #GOLD
        elif fg == Colors.BRIGHTYELLOW and bg == Colors.BRIGHTBLACK and char == '$':
            source_png = self.sprite_mainpng
            sprite_index_y = 690
            sprite_index_x = 0
            sprite_size_x = 30
            sprite_size_y = 30
        #DEAD enemy bloodstain
        elif fg == Colors.RED and bg == Colors.BLACK and char == '.':
            source_png = self.sprite_mainpng
            sprite_index_y = 690
            sprite_index_x = 190
            sprite_size_x = 30
            sprite_size_y = 25
        #DEAD enemy bloodstain (inverted with items?)
        elif fg == Colors.BLACK and bg == Colors.RED and char == '.':
            source_png = self.sprite_mainpng
            sprite_index_y = 690
            sprite_index_x = 190
            sprite_size_x = 30
            sprite_size_y = 25

        #PLAYER CHARACTER
        elif fg == Colors.BLACK and bg == Colors.WHITE and char == '@':
            source_png = self.sprite_playerpng
            sprite_index_y = 1766
            sprite_index_x = 299+32
            sprite_size_x = 22
            sprite_size_y = 30
        #PLAYER CHARACTER INVERTED
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == '@':
            source_png = self.sprite_playerpng
            sprite_index_y = 1766
            sprite_index_x = 299+32
            sprite_size_x = 22
            sprite_size_y = 30
        #BAT
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == 'b':
            source_png = self.sprite_playerpng
            sprite_index_y = 694
            sprite_index_x = 127
            sprite_size_x = 32
            sprite_size_y = 25
        #BAT (sleeping)
        elif fg == Colors.WHITE and bg == Colors.BLUE and char == 'b':
            source_png = self.sprite_playerpng
            sprite_index_y = 694
            sprite_index_x = 127
            sprite_size_x = 32
            sprite_size_y = 25
        #frilled lizard
        elif fg == Colors.GREEN and bg == Colors.BLACK and char == 'l':
            source_png = self.sprite_playerpng
            sprite_index_y = 742
            sprite_index_x = 249
            sprite_size_x = 28
            sprite_size_y = 21
        #frilled lizard (sleeping)
        elif fg == Colors.GREEN and bg == Colors.BLUE and char == 'l':
            source_png = self.sprite_playerpng
            sprite_index_y = 742
            sprite_index_x = 249
            sprite_size_x = 28
            sprite_size_y = 21
        #dead frilled lizard corpse
        elif fg == Colors.GREEN and bg == Colors.BLACK and char == '†':
            source_png = self.sprite_mainpng
            sprite_index_y = 690
            sprite_index_x = 696
            sprite_size_x = 32
            sprite_size_y = 20
        #QUOKA
        elif fg == Colors.BRIGHTWHITE and bg == Colors.BRIGHTBLACK and char == 'r':
            source_png = self.sprite_playerpng
            sprite_index_y = 742
            sprite_index_x = 523
            sprite_size_x = 28
            sprite_size_y = 25
        #QUOKA (sleeping)
        elif fg == Colors.BRIGHTWHITE and bg == Colors.BRIGHTBLUE and char == 'r':
            source_png = self.sprite_playerpng
            sprite_index_y = 742
            sprite_index_x = 523
            sprite_size_x = 28
            sprite_size_y = 25
        #dead QUOKA corpse 
        elif fg == Colors.BRIGHTWHITE and bg == Colors.BRIGHTBLACK and char == '†':
            source_png = self.sprite_mainpng
            sprite_index_y = 690
            sprite_index_x = 849
            sprite_size_x = 32
            sprite_size_y = 21
        #Kobold (sleeping)
        elif fg == Colors.YELLOW and bg == Colors.BLUE and char == 'K':
            source_png = self.sprite_playerpng
            sprite_index_y = 1446
            sprite_index_x = 876
            sprite_size_x = 30
            sprite_size_y = 31
        #Kobold
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == 'K':
            source_png = self.sprite_playerpng
            sprite_index_y = 1446
            sprite_index_x = 876
            sprite_size_x = 30
            sprite_size_y = 31
        #rat
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == 'r':
            source_png = self.sprite_playerpng
            sprite_index_y = 742
            sprite_index_x = 400
            sprite_size_x = 31
            sprite_size_y = 21
        #giant cockroach
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == 'B':
            source_png = self.sprite_playerpng
            sprite_index_y = 694
            sprite_index_x = 96
            sprite_size_x = 31
            sprite_size_y = 29
        #giant cockroach unaware wandering
        elif fg == Colors.BLACK and bg == Colors.YELLOW and char == 'B':
            source_png = self.sprite_playerpng
            sprite_index_y = 694
            sprite_index_x = 96
            sprite_size_x = 31
            sprite_size_y = 29
        #goblin (sleeping)
        elif fg == Colors.WHITE and bg == Colors.BLUE and char == 'g':
            source_png = self.sprite_playerpng
            sprite_index_y = 1446
            sprite_index_x = 851
            sprite_size_x = 25
            sprite_size_y = 26
        #goblin
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == 'g':
            source_png = self.sprite_playerpng
            sprite_index_y = 1446
            sprite_index_x = 851
            sprite_size_x = 25
            sprite_size_y = 26
        #ADDER
        elif fg == Colors.GREEN and bg == Colors.BLACK and char == 'S':
            source_png = self.sprite_playerpng
            sprite_index_y = 998
            sprite_index_x = 406
            sprite_size_x = 32
            sprite_size_y = 24
        #ADDER SLEEPING
        elif fg == Colors.GREEN and bg == Colors.BLUE and char == 'S':
            source_png = self.sprite_playerpng
            sprite_index_y = 998
            sprite_index_x = 406
            sprite_size_x = 32
            sprite_size_y = 24
        #BALL PYTHON?
        #Colors.BRIGHTGREEN Colors.BRIGHTYELLOW S
        #Colors.BRIGHTGREEN Colors.BRIGHTBLACK †
        #moccasin?
        #TELEPORT TRAP
        elif fg == Colors.BRIGHTBLUE and bg == Colors.BRIGHTBLACK and char == '^':
            source_png = self.sprite_featpng
            sprite_index_y = 192
            sprite_index_x = 304
            sprite_size_x = 32
            sprite_size_y = 22
        #ECTOPLASM (sleeping)
        elif fg == Colors.WHITE and bg == Colors.BLUE and char == 'J':
            source_png = self.sprite_playerpng
            sprite_index_y = 1318
            sprite_index_x = 528
            sprite_size_x = 32
            sprite_size_y = 24
        #ECTOPLASM
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == 'J':
            source_png = self.sprite_playerpng
            sprite_index_y = 1318
            sprite_index_x = 528
            sprite_size_x = 32
            sprite_size_y = 24
        #Colors.YELLOW Colors.BLACK < upstairs oneway
        # Colors.BRIGHTWHITE Colors.BRIGHTBLACK < upstairs normal? untraveled?
        # Colors.YELLOW Colors.BLACK ( stone ?

        #potion
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == '!':
            source_png = self.sprite_mainpng
            sprite_index_y = 504
            sprite_index_x = 910
            sprite_size_x = 25
            sprite_size_y = 27  
        #hunting sling
        elif fg == Colors.YELLOW and bg == Colors.BLACK and char == ')':
            source_png = self.sprite_mainpng
            sprite_index_y = 192
            sprite_index_x = 809
            sprite_size_x = 32
            sprite_size_y = 29
        #ROBE
        elif fg == Colors.RED and bg == Colors.BLACK and char == '[':
            source_png = self.sprite_mainpng
            sprite_index_y = 288
            sprite_index_x = 137
            sprite_size_x = 29
            sprite_size_y = 29
        #Robe walked on or robe stash
        elif fg == Colors.BLACK and bg == Colors.RED and char == '[':
            source_png = self.sprite_mainpng
            sprite_index_y = 288
            sprite_index_x = 137
            sprite_size_x = 29
            sprite_size_y = 29   
        #long sword
        elif fg == Colors.BRIGHTCYAN and bg == Colors.BRIGHTBLACK and char == ')':
            source_png = self.sprite_mainpng
            sprite_index_y = 128
            sprite_index_x = 851
            sprite_size_x = 28
            sprite_size_y = 28 
        #sling bullet   
        elif fg == Colors.CYAN and bg == Colors.BLACK and char == '(':
            source_png = self.sprite_mainpng
            sprite_index_y = 224
            sprite_index_x = 633
            sprite_size_x = 15
            sprite_size_y = 11
        #unknown scroll 
        elif fg == Colors.BRIGHTBLUE and bg == Colors.BRIGHTBLACK and char == '?':
            source_png = self.sprite_mainpng
            sprite_index_y = 412
            sprite_index_x = 433
            sprite_size_x = 27
            sprite_size_y = 28  
        #whip/common weapon
        elif fg == Colors.WHITE and bg == Colors.BLACK and char == ')':
            source_png = self.sprite_mainpng
            sprite_index_y = 128
            sprite_index_x = 32
            sprite_size_x = 31
            sprite_size_y = 29  
        # Colors.CYAN Colors.BLACK ) => common dagger
        elif fg == Colors.CYAN and bg == Colors.BLACK and char == ')':
            source_png = self.sprite_mainpng
            sprite_index_y = 128
            sprite_index_x = 437
            sprite_size_x = 17
            sprite_size_y = 17  

        # else:
        #     print(Colors(fg),Colors(bg),char)

        #get individual character sprite image
        image = source_png[sprite_index_y:sprite_size_y+sprite_index_y,sprite_index_x:sprite_size_x+sprite_index_x,:]
        #apply sprite image to a 32x32 image (center the sprite)
        tile_image = np.zeros(shape=(32,32,3))
        offset_y = int((32-sprite_size_y)/2)
        offset_x = int((32-sprite_size_x)/2)
        tile_image[offset_y:offset_y+image.shape[0],offset_x:offset_x+image.shape[1],:] = image[:,:,0:3]
        return tile_image

    def write_tile(self,y,x,fg,bg,char):
        r = y*self.TILESIZE
        c = x*self.TILESIZE
        if(x<38 and y < 18):
            image = self.construct_tile(y,x,fg,bg,char)
            #Stamps the 32x32x3 tile to the final png_array
            self.png_array[r:r+image.shape[0], c:c+image.shape[1],:] = image.astype(np.uint8)
        else:
            image = self.construct_char_tile(y,x,fg,bg,char)
            self.png_array[r:r+image.shape[0], c:c+image.shape[1],:] = image.astype(np.uint8)

def process_frame(f):
    fc = FrameConstructor(TILESIZE=32,DISPLAY_Y_SIZE=29,DISPLAY_X_SIZE=81,DATASIZE=3)
    print(f)
    fc.clear_png_array()
    with open(f,mode='r') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='"',quoting=csv.QUOTE_MINIMAL)
        for row in spamreader:
            y = int(row[0])
            x = int(row[1])
            fg = Colors(int(row[2]))
            bg = Colors(int(row[3]))
            char = row[4]
            fc.write_tile(y,x,fg,bg,char)
        # if not np.array_equal(previous_frame,fc.png_array):
        img = png.from_array(fc.png_array.reshape(fc.TILESIZE*fc.DISPLAY_Y_SIZE,fc.TILESIZE*fc.DISPLAY_X_SIZE*fc.DATASIZE),"RGB")
        img.save(str(f).replace('.csv','') + '.png')


q = Queue()

# TILESIZE = 32
# DISPLAY_Y_SIZE = 29
# DISPLAY_X_SIZE = 81
# DATASIZE = 3
if __name__ ==  '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", help="specify single frame to run",type=int,default=0)
    parser.add_argument("-rs", help="specify range frame to run",type=int,default=0)
    parser.add_argument("-re", help="specify range frame to run",type=int,default=0)
    parser.add_argument("-p", help="specify parallel run",action='store_true')

    global_args = parser.parse_args()

    q = Queue()
    start = time.time()

    mypath = './data'

    #Default Run All Frames
    onlyfiles = [join(mypath,f) for f in listdir(mypath) if isfile(join(mypath, f)) and f.endswith('.csv')]
    
    #Run Single Frame
    if global_args.f != 0:
        onlyfiles = ['./data/'+str(global_args.f)+'.csv']

    #Run Frame Range
    elif global_args.rs !=0 and global_args.re !=0:
        templist = []
        for file in onlyfiles:
            fileno = int(file.replace('./data/','').replace('.csv',''))
            if fileno >= int(global_args.rs) and fileno<= int(global_args.re):
                templist.append('./data/'+str(fileno)+'.csv')
        onlyfiles = templist


    print(onlyfiles)
    func_args = []

    #Generate Workload
    for f in onlyfiles:
        func_args.append((f))

    if not global_args.p:
        #Single Thread Run
        for f in func_args:
            process_frame(f)
    else:
        #Multiprocessing Run
        pool = Pool()
        try:
            for _ in tqdm.tqdm(pool.imap_unordered(process_frame, func_args), total=len(func_args)):
                pass
        except KeyboardInterrupt:
            # Allow ^C to interrupt from any thread.
            sys.stdout.write('\033[0m')
            sys.stdout.write('User Interupt\n')
        pool.close()
