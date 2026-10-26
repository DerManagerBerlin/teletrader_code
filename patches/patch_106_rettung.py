#!/usr/bin/env python3
# Patch 106 - Terminal zurueckholen.
#
#   Patch 105 hat das Terminal beendet und darauf gesetzt, dass der
#   Watchdog es rechtzeitig neu startet. Das Pruefenster war zu kurz, am
#   Ende lief kein Terminal mehr. Ohne Terminal kann der Bot nicht
#   handeln, deshalb hat das Vorrang vor allem anderen.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
LOG = os.path.join(TT, "bot.log")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
UNIT = "teletrader.service"

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH106 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=90):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

# Reste aus Patch 105 wegraeumen, damit nichts Altes mitstartet
for p in (os.path.join(TT, "ultima_start.ini"), os.path.join(TT, ".mt5_start_cfg")):
    try:
        if os.path.exists(p):
            os.remove(p); melde("Rest entfernt: " + os.path.basename(p))
    except Exception:
        pass

melde("Terminal vorher: " + (sh("pgrep -f '[t]erminal64' | head -1") or "laeuft nicht"))
melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))

for _ in range(30):
    time.sleep(5)
    if sh("pgrep -f '[t]erminal64' | head -1", t=20).strip():
        break
melde("Terminal nachher: " + (sh("pgrep -f '[t]erminal64' | head -1") or "LAEUFT IMMER NOCH NICHT"))

stand = ""
for _ in range(36):
    time.sleep(5)
    stand = sh("grep 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null | tail -1", t=20)
    if stand:
        break
melde("LIVECHECK: " + (stand[:180] or "keine"))
melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1"))
print("Patch 106 fertig")
