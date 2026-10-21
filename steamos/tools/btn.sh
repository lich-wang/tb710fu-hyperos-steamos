#!/bin/sh
# btn.sh : buttons currently down on the game X server (:1), per input device
export DISPLAY=:1
for id in $(xinput list --id-only 2>/dev/null); do
  d=$(xinput query-state $id 2>/dev/null | grep -E "button\[[1-5]\]=down" | tr -d '\t' | tr '\n' ' ')
  [ -n "$d" ] && echo "$id $(xinput list --name-only $id): $d"
done
echo "--"
