#!/usr/bin/env python3
# NO_RESTART
# Patch 103 - den Startabschnitt des Watchdogs woertlich lesen.
#   Patch 102 hat nur Zeilen mit "terminal64" gefunden, die eigentliche
#   Startzeile benutzt aber die Variable $MT5. Deshalb hier der Block um
#   Zeile 93 herum. Zeilen mit Zugangsdaten bleiben draussen.
import os, re
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
WD = os.path.join(TT, "watchdog.sh")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH103 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

GEHEIM = re.compile(r"(?i)(pass|pwd|kennwor|token|secret|api[_-]?key)")
try:
    with open(WD, encoding="utf-8", errors="replace") as f:
        zeilen = f.read().splitlines()
except Exception as e:
    melde("nicht lesbar: " + str(e)); raise SystemExit(0)

melde("Datei hat " + str(len(zeilen)) + " Zeilen")
for i in range(85, min(len(zeilen), 118)):
    z = zeilen[i]
    if GEHEIM.search(z):
        melde("Z" + str(i + 1) + ": (ausgelassen)")
    else:
        melde("Z" + str(i + 1) + ": " + z.rstrip()[:165])
print("Patch 103 fertig")
