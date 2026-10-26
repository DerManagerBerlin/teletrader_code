#!/usr/bin/env python3
# Patch 95 - MetaTrader5-Bibliothek auf den Stand des Terminals bringen.
#
#   Verdacht: Terminal ist Build 6230, die Python-Bibliothek 5.0.5735.
#   Das Anhaengen an eine laufende Sitzung funktioniert damit, ein
#   Kontowechsel nicht. Passt zum Befund: initialize() ohne Parameter
#   klappt immer, initialize(login=..., server=...) endet im IPC-Timeout,
#   und im Terminal-Log steht kein einziger Anmeldeversuch. Die Anfrage
#   erreicht das Terminal also gar nicht.
#
#   Der Patch laeuft unter Linux-Python, ruft aber Wine-Python auf, denn
#   dort lebt die Bibliothek. Vorher wird die alte Version notiert, damit
#   ein Zurueck moeglich ist. Danach Neustart und Kontrolle, dass der Bot
#   auf Demo weiterhin sauber hochkommt. Kein Livesversuch in diesem Patch.
import os, re, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
LOG = os.path.join(TT, "bot.log")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
UNIT = "teletrader.service"
WPY = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                   "Python311", "python.exe")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH95 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=300):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        out = (r.stdout + r.stderr)
        # Wine-Rauschen rauswerfen
        out = "\n".join(z for z in out.splitlines()
                        if not re.match(r"^(wine|fixme|err|\d{4}:)", z.strip(), re.I))
        return out.strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Zeitlimit/Fehler: " + str(e)[:90]

WINE = "WINEDEBUG=-all DISPLAY=:99 wine '" + WPY + "'"

alt = sh(WINE + " -c \"import MetaTrader5 as m; print(m.__version__)\"", t=120)
melde("Bibliothek vorher: " + (alt or "(nicht lesbar)"))
melde("Terminal-Build: " + sh(
    "L=$(ls -t '" + HOME + "/.wine/drive_c/Program Files/PU Prime MT5 Terminal'"
    "/logs/*.log 2>/dev/null | head -1); [ -n \"$L\" ] && "
    "grep -m1 -o 'build [0-9]*' \"$L\" || echo '?'", t=60))

if not re.match(r"^\d+\.\d+\.\d+", (alt or "").strip()):
    melde("ABBRUCH: Version nicht ermittelbar, nichts angefasst")
    print("Patch 95 fertig"); raise SystemExit(0)

melde("aktualisiere: " + sh(
    WINE + " -m pip install --upgrade --no-input MetaTrader5 2>&1 | tail -3", t=600))

neu = sh(WINE + " -c \"import MetaTrader5 as m; print(m.__version__)\"", t=120)
melde("Bibliothek nachher: " + (neu or "(nicht lesbar)"))

if not re.match(r"^\d+\.\d+\.\d+", (neu or "").strip()):
    melde("Version nach dem Update nicht lesbar - rolle zurueck auf " + alt)
    melde(sh(WINE + " -m pip install --no-input 'MetaTrader5==" + alt.strip() +
             "' 2>&1 | tail -2", t=600))

melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK", t=90))

vor = sh("grep -c 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null || echo 0")
stand = ""
for _ in range(36):
    time.sleep(5)
    n = sh("grep -c 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null || echo 0", t=20)
    try:
        if int(n) > int(vor):
            stand = sh("grep 'LIVECHECK Modus' '" + LOG + "' | tail -1", t=20)
            break
    except Exception:
        pass
melde("LIVECHECK neu: " + (stand[:180] or "KEINE in 180 s - bitte pruefen"))
melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1", t=30))
print("Patch 95 fertig")
