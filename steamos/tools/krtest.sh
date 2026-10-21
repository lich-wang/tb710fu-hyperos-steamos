#!/bin/bash
# krtest.sh APPID "ENV=val ..." [LOG]
# Launch a Steam game with extra environment (via ~/.config/steam/env/gfx.txt, read by
# steam-launch-wrapper), tap the screen a few times (tap.py), report whether it is still running.
#   NOTAP=1  no taps, just wait 30 s
#   LOG      file the game writes to, e.g. launch options "%command% >/tmp/game.log 2>&1"
# Used to bisect Turnip/zink/FEX options without someone holding the tablet.
APP=${1:?usage: krtest.sh APPID "ENV=val ..." [LOG]}; ENVS=${2:-}; LOGF=${3:-/tmp/game.log}
H=$(dirname "$0")
export DISPLAY=:0
mkdir -p ~/.config/steam/env; : > ~/.config/steam/env/gfx.txt
for kv in $ENVS; do echo "$kv" >> ~/.config/steam/env/gfx.txt; done
steam -ifrunning steam://rungameid/$APP >/dev/null 2>&1 &
for i in $(seq 1 60); do [ "$(xprop -root GAMESCOPE_FOCUSED_APP | grep -o '[0-9]*$')" = "$APP" ] && break; sleep 1; done
echo "focused after ${i}s"; sleep 12
if [ -n "${NOTAP:-}" ]; then sleep 30
else python3 "$H/tap.py" 16000,10000 16000,12000 12000,10000 20000,10000 16000,14000 16000,8000; sleep 5; fi
alive=$(pgrep -f "AppId=$APP" | head -1)
echo "alive=${alive:-no} focused=$(xprop -root GAMESCOPE_FOCUSED_APP | grep -o '[0-9]*$')"
[ -f "$LOGF" ] && grep -E "DEVICE LOST|error" "$LOGF" | grep -v gameoverlay | tail -3
: > ~/.config/steam/env/gfx.txt
