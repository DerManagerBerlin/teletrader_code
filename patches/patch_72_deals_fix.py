#!/usr/bin/env python3
# Patch 72 - repariert den Deal-Export aus Patch 71.
#
#   Zwei Fehler in Patch 71:
#   1) Ziel war os.path.expanduser("~"). Unter Wine-Python ist das das
#      Windows-Profil, die Datei landete in
#      C:\users\alexander_lacher\ttpub\deals.csv. Der Linux-sync.sh schaut
#      aber in /home/alexander_lacher/ttpub und hat sie nie gesehen.
#      Neu: fester Wine-Pfad Z:\home\alexander_lacher\ttpub (Z: ist unter
#      Wine die Linux-Wurzel), so wie der Bot auch signal_examples.json
#      oeffnet.
#   2) history_deals_get lieferte 0 Deals. Das Fenster endete auf
#      datetime.now(); MT5 rechnet in Serverzeit, und bei Versatz faellt
#      der juengste Teil heraus. Neu: Anfang fest auf 2026-01-01 und Ende
#      zwei Tage in der Zukunft.
import os, shutil
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH dealfix: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

ALT_ZEIT = '            _von = _dt.now() - _td(days=120)\n' \
           '            _dl = mt5.history_deals_get(_von, _dt.now()) or []\n'
NEU_ZEIT = '            _von = _dt(2026, 1, 1)\n' \
           '            _dl = mt5.history_deals_get(_von, _dt.now() + _td(days=2)) or []\n'

ALT_ZIEL = '            _ziel = os.path.join(os.path.expanduser("~"), "ttpub", "deals.csv")\n' \
           '            os.makedirs(os.path.dirname(_ziel), exist_ok=True)\n'
NEU_ZIEL = '            _ziel = "Z:\\\\home\\\\alexander_lacher\\\\ttpub\\\\deals.csv"\n' \
           '            try:\n' \
           '                os.makedirs(os.path.dirname(_ziel), exist_ok=True)\n' \
           '            except Exception:\n' \
           '                pass\n'

fehlt = []
if ALT_ZEIT not in src:
    fehlt.append("Zeitfenster")
if ALT_ZIEL not in src:
    fehlt.append("Zielpfad")
if fehlt:
    melde("Anker nicht gefunden: " + ", ".join(fehlt) +
          " (schon gepatcht?)" )
    if len(fehlt) == 2:
        raise SystemExit(0)

shutil.copyfile(BOT, BOT + ".bak_72")
src = src.replace(ALT_ZEIT, NEU_ZEIT, 1).replace(ALT_ZIEL, NEU_ZIEL, 1)

# Logzeile um den Pfad ergaenzen, damit ich sehe wohin es wirklich ging
src = src.replace(
    '            log.info("DEALEXPORT " + str(_n) + " Deals -> " + _ziel)\n',
    '            log.info("DEALEXPORT " + str(_n) + " Deals -> " + _ziel +\n'
    '                     " | vorhanden=" + str(os.path.exists(_ziel)))\n', 1)

with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Zeitfenster und Zielpfad korrigiert, Syntax ok")
except Exception as e:
    shutil.copyfile(BOT + ".bak_72", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 72 fertig")
