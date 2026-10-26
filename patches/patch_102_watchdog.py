#!/usr/bin/env python3
# NO_RESTART
# Patch 102 - wie startet der Watchdog das Terminal? Rein lesend.
#
#   Eingaben erreichen Wine auf keinem Weg, auch nicht ueber VNC mit
#   laufendem Window-Manager. Der Login von Hand faellt damit aus.
#   Alternative: MT5 liest beim Start eine Konfigurationsdatei mit Konto,
#   Server und Passwort und meldet sich selbst an. Dafuer muss die
#   Startzeile des Terminals bekannt sein.
#
#   Zugangsdaten werden nicht ausgegeben.
import os, re, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH102 " + t
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
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)[:60]

GEHEIM = re.compile(r"(?i)(pass|pwd|kennwor|token|secret|api[_-]?key)")

WD = None
for k in (os.path.join(TT, "watchdog.sh"), os.path.join(HOME, "watchdog.sh"),
          os.path.join(PUB, "watchdog.sh")):
    if os.path.exists(k):
        WD = k; break
melde("watchdog: " + (WD or "nicht gefunden"))

if WD:
    try:
        with open(WD, encoding="utf-8", errors="replace") as f:
            zeilen = f.read().splitlines()
    except Exception as e:
        zeilen = []
        melde("nicht lesbar: " + str(e))
    for i, z in enumerate(zeilen, 1):
        if re.search(r"(?i)terminal64|MT5=|wine .*exe|portable", z):
            if GEHEIM.search(z):
                melde("Z" + str(i) + ": (Zeile mit Zugangsdaten ausgelassen)")
            else:
                melde("Z" + str(i) + ": " + z.strip()[:170])

melde("laufende Startzeile: " + sh(
    "tr '\\0' ' ' < /proc/$(pgrep -f '[t]erminal64' | head -1)/cmdline "
    "2>/dev/null | cut -c1-170")[:200])
melde("Wine-Prefix: " + sh("grep -ho 'WINEPREFIX=[^ ]*' '" + (WD or "/dev/null") +
                           "' 2>/dev/null | head -1") or "(keiner, Standard ~/.wine)")
print("Patch 102 fertig")
