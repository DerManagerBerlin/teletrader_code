#!/usr/bin/env python3
# NO_RESTART
# Patch 108 - den Anfang von watchdog.sh lesen. Aendert nichts.
#   Patch 107 hat die Konfiguration geschrieben, aber MT5 hat sie nicht
#   gelesen. Verdacht: Der Watchdog startet das Terminal beim Hochfahren
#   an einer anderen Stelle als in der Nachstart-Pruefung, die ich
#   erweitert habe. Also den Anfang ansehen.
import os, re
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
WD = os.path.join(TT, "watchdog.sh")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH108 " + t
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

melde("Zeilen gesamt: " + str(len(zeilen)))
for i in range(0, min(len(zeilen), 86)):
    z = zeilen[i].rstrip()
    if not z.strip():
        continue
    if GEHEIM.search(z):
        melde("Z" + str(i + 1) + ": (ausgelassen)")
    else:
        melde("Z" + str(i + 1) + ": " + z[:160])
print("Patch 108 fertig")
