#!/usr/bin/env python3
# Patch 96 - VNC verzoegert starten, damit es den Neustart ueberlebt.
#
#   Fehler in 93 und 94: ttpull startet teletrader.service nach JEDEM
#   angewendeten Patch neu. Dabei wird auch Xvfb neu gestartet, und
#   x11vnc haengt an genau diesem Display und stirbt mit. Beide Male war
#   der VNC-Server also schon wieder weg, bevor Alex verbinden konnte.
#   Zweimal dieselbe Ursache, und ich habe zuerst die Firewall verdaechtigt.
#
#   Jetzt wird ein abgekoppelter Helfer gestartet, der 150 Sekunden
#   wartet, bis der Dienstneustart durch und das neue Xvfb oben ist, und
#   erst dann x11vnc startet. Harter Ablauf nach 40 Minuten bleibt.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
HELFER = os.path.join(HOME, "vnc_spaet.sh")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH96 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=25):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

SKRIPT = '''#!/usr/bin/env bash
# Von Patch 96 geschrieben. Wartet den Dienstneustart ab und startet dann
# x11vnc auf dem frischen Xvfb. Meldet das Ergebnis nach ttpub/status.txt.
set -u
STATUS="$HOME/ttpub/status.txt"
sagen() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') VNCSPAET $*" >> "$STATUS"; }
sleep 150
# auf ein lebendes Display warten
for i in $(seq 1 30); do
  DISPLAY=:99 xdpyinfo >/dev/null 2>&1 && break
  sleep 5
done
if ! DISPLAY=:99 xdpyinfo >/dev/null 2>&1; then
  sagen "Display :99 kam nicht hoch, kein VNC"
  exit 1
fi
pkill -x x11vnc 2>/dev/null
sleep 1
DISPLAY=:99 nohup timeout 2400 x11vnc -display :99 -nopw -forever -quiet \\
  -rfbport 5902 >> "$HOME/x11vnc.log" 2>&1 &
sleep 4
if pgrep -x x11vnc >/dev/null; then
  sagen "VNC laeuft auf 5902, offen bis $(date -u -d '+40 minutes' '+%H:%M UTC')"
else
  sagen "VNC konnte nicht gestartet werden, siehe x11vnc.log"
fi
'''

try:
    with open(HELFER, "w", encoding="utf-8") as f:
        f.write(SKRIPT)
    os.chmod(HELFER, 0o755)
    melde("Helfer geschrieben")
except Exception as e:
    melde("FEHLER: " + str(e)); raise SystemExit(1)

melde("Syntax: " + (sh("bash -n '" + HELFER + "' && echo ok") or "?"))
# setsid koppelt ihn vom cron-Lauf ab, sonst stirbt er mit ttpull
sh("setsid nohup '" + HELFER + "' >/dev/null 2>&1 < /dev/null & disown; echo ab", t=8)
time.sleep(2)
melde("Helfer gestartet, VNC kommt in rund 3 Minuten auf Port 5902")
print("Patch 96 fertig")
