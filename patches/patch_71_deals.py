#!/usr/bin/env python3
# Patch 71 - exportiert die echte Handelshistorie aus MT5.
#
#   Fuer das Briefing-Diagramm (Kontostand ueber Tradeanzahl) brauche ich
#   die abgeschlossenen Trades mit Gewinn je Position. Bisher rekonstruiere
#   ich das aus Balance-Zeilen im Log, und das reicht nur so weit zurueck
#   wie recent.log, also drei Tage.
#
#   Der Patch haengt sich an den LIVECHECK-Block im Startup. Der laeuft
#   unter Wine-Python und hat damit das MetaTrader5-Modul, anders als das
#   Patch-Skript selbst. Geschrieben wird nach ~/ttpub/deals.csv, von wo
#   sync.sh die Datei mitnimmt.
#
#   Rein lesend: history_deals_get, keine Auftraege, keine Aenderung am
#   Handelsverhalten. Kontonummer kommt nicht mit in die Datei.
import os, re, shutil
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
                    " [INFO] AUTOPATCH deals: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

MARKE = "DEALEXPORT"
with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if MARKE in src:
    melde("schon vorhanden, nichts zu tun"); raise SystemExit(0)

ANKER = '    if os.getenv("LIVECHECK", "true").lower() == "true":\n'
if ANKER not in src:
    melde("FEHLER: Anker nicht gefunden"); raise SystemExit(1)

NEU = '''    if os.getenv("DEALEXPORT", "true").lower() == "true":
        try:
            import csv as _csv
            from datetime import datetime as _dt, timedelta as _td
            _von = _dt.now() - _td(days=120)
            _dl = mt5.history_deals_get(_von, _dt.now()) or []
            _ziel = os.path.join(os.path.expanduser("~"), "ttpub", "deals.csv")
            os.makedirs(os.path.dirname(_ziel), exist_ok=True)
            _n = 0
            with open(_ziel, "w", encoding="utf-8", newline="") as _fh:
                _w = _csv.writer(_fh, delimiter=";")
                _w.writerow(["zeit", "ticket", "position_id", "symbol",
                             "typ", "entry", "volume", "preis", "profit",
                             "swap", "commission", "comment"])
                for _d in _dl:
                    try:
                        _w.writerow([
                            _dt.fromtimestamp(_d.time).strftime("%Y-%m-%d %H:%M:%S"),
                            _d.ticket, _d.position_id, _d.symbol, _d.type,
                            _d.entry, _d.volume, _d.price,
                            round(_d.profit, 2), round(_d.swap, 2),
                            round(_d.commission, 2),
                            str(_d.comment)[:40]])
                        _n += 1
                    except Exception:
                        continue
            log.info("DEALEXPORT " + str(_n) + " Deals -> " + _ziel)
        except Exception as _de:
            log.error("DEALEXPORT Fehler: " + str(_de))
'''

shutil.copyfile(BOT, BOT + ".bak_71")
src = src.replace(ANKER, NEU + ANKER, 1)
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("DEALEXPORT eingebaut, Syntax ok")
except Exception as e:
    shutil.copyfile(BOT + ".bak_71", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 71 fertig")
