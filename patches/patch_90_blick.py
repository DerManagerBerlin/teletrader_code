#!/usr/bin/env python3
# Patch 90 - einfacher Blick ins frisch aufgeraeumte bot.log. Aendert nichts.
import os, subprocess
from datetime import datetime, timezone
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT): TT = "."
LOG = os.path.join(TT, "bot.log")
STATUS = os.path.join(HOME, "ttpub", "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH90 " + t
    print(z)
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f: f.write(z + "\n")
    except Exception: pass

def sh(c, t=60):
    try:
        r = subprocess.run(["bash","-lc",c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip()
    except Exception as e: return "Fehler: " + str(e)

melde("Groesse: " + sh("ls -l --time-style=+%H:%M:%S '" + LOG + "'"))
melde("neueste Zeitmarke: " + sh(
    "grep -oE '^2026-[0-9-]+ [0-9:]+' '" + LOG + "' | tail -1"))
melde("LIVECHECK letzte: " + sh(
    "grep 'LIVECHECK Modus' '" + LOG + "' | tail -1")[:190])
melde("POSCHECK letzte: " + sh(
    "grep 'POSCHECK' '" + LOG + "' | tail -3").replace("\n", " || ")[:300])
melde("Algo-Warnungen (letzte 500 Zeilen): " + sh(
    "tail -500 '" + LOG + "' | grep -c 'Algo Trading deaktiviert'"))
for z in sh("tail -12 '" + LOG + "'").splitlines():
    melde("TAIL " + z[:170])
print("Patch 90 fertig")
