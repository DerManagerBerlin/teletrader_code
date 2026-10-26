#!/usr/bin/env python3
# NO_RESTART
# Patch 110 - wurde die Konfiguration ueberhaupt uebergeben? Rein lesend.
#   Patch 107 hat .mt5_start_cfg geschrieben und neu gestartet. Ob der
#   Watchdog die Datei gesehen hat, steht in seinem eigenen Log als
#   "MT5 Start mit Konfiguration". Das habe ich nicht geprueft.
import os, re, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH110 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=40):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)[:60]

melde("WATCHLOG-Zeile im Skript: " + sh(
    "grep -n 'WATCHLOG=' '" + os.path.join(TT, 'watchdog.sh') + "' | head -2"))
kandidaten = sh("ls -1t " + TT + "/*.log " + HOME + "/*.log 2>/dev/null | head -8")
melde("Logdateien: " + kandidaten.replace(" | ", " "))

melde("Treffer 'Start mit Konfiguration': " + sh(
    "grep -rl 'Start mit Konfiguration' " + TT + " " + HOME +
    " --include='*.log' 2>/dev/null | head -3" ) or "(keine Datei)")
melde("Zeilen dazu: " + sh(
    "grep -rh 'Start mit Konfiguration\\|MT5 neu starten' " + TT + " " + HOME +
    " --include='*.log' 2>/dev/null | tail -5"))
melde("Patch 104 im Watchdog aktiv: " + sh(
    "grep -c 'mt5_start_cfg' '" + os.path.join(TT, 'watchdog.sh') + "'"))
melde("Reste: " + sh("ls -la " + TT + "/.mt5_start_cfg " + TT +
                     "/ultima_start.ini 2>&1 | head -3"))
print("Patch 110 fertig")
