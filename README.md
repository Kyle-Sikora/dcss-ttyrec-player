# dcss-ttyrec-player
A ttyrec reader for DCSS that takes in the ascii ttyrec files and creates tiled frames

When you do something cool in DCSS, or survive a close call, it's great! But it'd be even better if you could share your experience in an instant replay in a tiles version of what happened. A DCSS ttyrec reader would be able to make tiled DCSS highlights of all games, helping make DCSS more easily sharable.

While this cannot fully reconstruct the tiles output from a ttyrec, it is possible to get pretty close.

# usage

ttyplay.py - takes in the ttyrec and outputs .csv files of frame data

      python3 ttyplay.py -path [PATH TO TTYREC] -verbose

frame_maker.py - reads in the .csv files from ttyplay.py and generates .png files of the frames.

      python3 frame_maker.py -f 100 -p
      
      -p: parallel
      -f: individual frame number
      -rs,-re: run frames in range [rs;re]
