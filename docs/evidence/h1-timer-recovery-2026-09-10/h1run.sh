#!/bin/bash
# usage: h1run.sh <label> <wait-seconds> [tee args...]
# One foreground run: tee on 8205 -> modem 8105 with the given fault args,
# axcall M0LTE -> GB7RDG through the tee, two node commands from stdin, then
# an idle wait long enough for the T3 keepalive to show (or not), then EOF.
label=$1; wait=$2; shift 2
log=~/axtest/$label.log; out=~/axtest/$label.axcall.out
rm -f "$log" "$out"
python3 /tmp/kisstee.py --listen 8205 --modem 127.0.0.1:8105 --log "$log" "$@" > ~/axtest/$label.tee.out 2>&1 &
teepid=$!
sleep 1
date -u +"# run $label started %Y-%m-%dT%H:%M:%SZ, tee args: $*" | tee -a "$out"
( sleep 12; printf "I\n"; sleep 14; printf "N\n"; sleep "$wait" ) \
  | timeout 480 /tmp/axcall GB7RDG -s M0LTE -t 127.0.0.1:8205 --keepalive 120 --frack 6 >> "$out" 2>&1
echo "# axcall exit $?" >> "$out"
sleep 4
kill $teepid 2>/dev/null; wait $teepid 2>/dev/null
date -u +"# run $label ended %Y-%m-%dT%H:%M:%SZ" >> "$out"
echo "=== $log"; cat "$log"; echo "=== $out"; cat "$out"
