#!/bin/bash
# usage: measure.sh <scratch dir> <tag>  -- capture Mac display 3 + tablet while ramp.html is on the Xiaomi display
S=$1; T=$2
adb shell screencap -p /sdcard/t.png && adb pull /sdcard/t.png $S/${T}tab.png >/dev/null && screencapture -x -D 3 $S/${T}mac.png
python3 "$(dirname "$0")/ramp_read.py" $S ${T}mac.png ${T}tab.png > $S/$T.txt
