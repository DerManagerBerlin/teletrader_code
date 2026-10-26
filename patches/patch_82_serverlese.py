#!/usr/bin/env python3
# Patch 82 - liest nur nach, welcher Live-Server hinterlegt ist und
# welche Server das Terminal ueberhaupt kennt. Aendert nichts.
#
#   Grund: Der Live-Login endet in IPC timeout, ohne Ablehnung. Das passt
#   dazu, dass das Konto bei Ultima Markets liegt, das Terminal aber von
#   PU Prime stammt. Bevor ein dritter Versuch verbraucht wird (danach
#   greift die Sperre aus Patch 56), will ich wissen, worauf er zielt.
#
#   Kontonummern und Passwoerter werden NICHT ausgegeben.
import os, re, subprocess
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
MT5 = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                   "PU Prime MT5 Terminal")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH srv: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:400]
    except Exception as e:
        return "Fehler: " + str(e)

# Nur Servernamen und Modus, nichts weiter
try:
    with open(ENV, encoding="utf-8") as f:
        for z in f:
            s = z.strip()
            if re.match(r"^(DEMO_MODE|LIVE_MT5_SERVER|DEMO_MT5_SERVER|"
                        r"LIVE_GOLD_SYMBOL|LIVE_FX_SUFFIX)=", s, re.I):
                melde(".env " + s)
            elif re.match(r"^LIVE_MT5_LOGIN=", s, re.I):
                _v = s.split("=", 1)[1].strip()
                melde(".env LIVE_MT5_LOGIN endet auf " + _v[-3:] +
                      " (" + str(len(_v)) + " Stellen)")
            elif re.match(r"^LIVE_MT5_PASSWORD=", s, re.I):
                _v = s.split("=", 1)[1].strip()
                melde(".env LIVE_MT5_PASSWORD gesetzt, Laenge " + str(len(_v)))
except Exception as e:
    melde(".env nicht lesbar: " + str(e))

# Welche Server kennt das Terminal? srv-Dateien tragen den Servernamen.
melde("bekannte Server: " + sh(
    "find '" + MT5 + "/config' -maxdepth 2 -iname '*.srv' -printf '%f ' "
    "2>/dev/null | head -c 300"))
melde("Terminal-Logs heute: " + sh(
    "ls -1t '" + MT5 + "/logs' 2>/dev/null | head -3"))
melde("letzte Terminal-Zeilen: " + sh(
    "L=$(ls -t '" + MT5 + "'/logs/*.log 2>/dev/null | head -1); "
    "[ -n \"$L\" ] && grep -iE 'login|authoriz|connect|server' \"$L\" "
    "| tail -6 || echo '(kein Log)'"))
print("Patch 82 fertig")
