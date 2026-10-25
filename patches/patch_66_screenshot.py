#!/usr/bin/env python3
# Patch 66 - Screenshot von Display :99 in den Mirror legen.
#   Ich rate seit einer Stunde, warum Ctrl+E nicht wirkt. Statt weiter zu
#   raten: das Bild ansehen. sync.sh macht "git add -A" in ~/ttpub, alles
#   was dort liegt landet im Repo.
#   Versucht mehrere Werkzeuge, nimmt das erste das klappt.
import os, subprocess, glob
from datetime import datetime, timezone

def log(t):
    try:
        with open("bot.log", "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH shot: " + t + "\n")
    except Exception:
        pass

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

def melde(t):
    print(t); log(t)

ZIEL = os.path.join(os.path.expanduser("~"), "ttpub", "mt5.png")
os.makedirs(os.path.dirname(ZIEL), exist_ok=True)

melde("Werkzeuge: " + sh("for t in import xwd scrot maim convert ffmpeg; do "
                         "printf '%s=%s ' $t $(command -v $t >/dev/null && echo ja || echo nein); done"))

VERSUCHE = [
    ("import",  "DISPLAY=:99 import -window root '%s'" % ZIEL),
    ("scrot",   "DISPLAY=:99 scrot -o '%s'" % ZIEL),
    ("maim",    "DISPLAY=:99 maim '%s'" % ZIEL),
    ("xwd+conv","DISPLAY=:99 xwd -root -silent > /tmp/s.xwd && convert /tmp/s.xwd '%s'" % ZIEL),
    ("ffmpeg",  "ffmpeg -y -loglevel error -f x11grab -video_size 1280x1024 -i :99 "
                "-frames:v 1 '%s'" % ZIEL),
]
ok = False
for name, cmd in VERSUCHE:
    out = sh(cmd)
    if os.path.exists(ZIEL) and os.path.getsize(ZIEL) > 2000:
        melde("Screenshot mit " + name + " erstellt, " +
              str(os.path.getsize(ZIEL)) + " Bytes -> ~/ttpub/mt5.png")
        ok = True
        break
    melde(name + " ohne Erfolg: " + out[:120])
if not ok:
    melde("kein Screenshot moeglich")

# Dazu der Fenstertitel und ob Dialoge offen sind
melde("Fenster: " + sh(
    "for w in $(DISPLAY=:99 xdotool search --name '.' 2>/dev/null); do "
    "t=$(DISPLAY=:99 xdotool getwindowname $w 2>/dev/null); "
    "g=$(DISPLAY=:99 xdotool getwindowgeometry $w 2>/dev/null | tr '\\n' ' '); "
    "[ -n \"$t\" ] && echo \"$w|$t|$g\"; done | head -8").replace("\n", " || ")[:400])
melde("WM: " + sh("DISPLAY=:99 xprop -root _NET_SUPPORTING_WM_CHECK 2>&1 | head -1"))
print("Patch 66 fertig")
