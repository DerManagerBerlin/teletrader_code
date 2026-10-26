#!/usr/bin/env python3
# Patch 73 - findet heraus, warum der Deal-Export 0 Zeilen liefert.
#
#   Stand: Pfad stimmt (Datei landet in ttpub), aber history_deals_get
#   gibt nichts zurueck. Mein "or []" verschluckt dabei den Fehler, ich
#   sehe also nicht, ob die Abfrage leer ist oder scheitert.
#
#   Dieser Patch ersetzt die eine Abfragezeile durch eine Fassung, die
#   last_error mitschreibt und drei Spannen vergleicht: ganzes Jahr,
#   letzte 7 Tage, letzte 24 Stunden. Zusaetzlich history_deals_total,
#   das unabhaengig von der Rueckgabe zaehlt, und die Kontonummer, auf
#   der gesucht wird.
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
                    " [INFO] AUTOPATCH dealdiag: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

ALT = ('            _von = _dt(2026, 1, 1)\n'
       '            _dl = mt5.history_deals_get(_von, _dt.now() + _td(days=2)) or []\n')

NEU = ('            _bis = _dt.now() + _td(days=2)\n'
       '            _spannen = [("Jahr", _dt(2026, 1, 1)),\n'
       '                        ("7Tage", _dt.now() - _td(days=7)),\n'
       '                        ("24h", _dt.now() - _td(days=1))]\n'
       '            _dl = []\n'
       '            try:\n'
       '                _ai = mt5.account_info()\n'
       '                log.info("DEALDIAG Konto=" + str(getattr(_ai, "login", "?")) +\n'
       '                         " Server=" + str(getattr(_ai, "server", "?")))\n'
       '            except Exception as _ae:\n'
       '                log.info("DEALDIAG account_info: " + str(_ae))\n'
       '            for _nm, _vb in _spannen:\n'
       '                try:\n'
       '                    _tot = mt5.history_deals_total(_vb, _bis)\n'
       '                except Exception as _te:\n'
       '                    _tot = "Fehler " + str(_te)\n'
       '                _r = mt5.history_deals_get(_vb, _bis)\n'
       '                log.info("DEALDIAG " + _nm + ": total=" + str(_tot) +\n'
       '                         " get=" + ("None" if _r is None else str(len(_r))) +\n'
       '                         " last_error=" + str(mt5.last_error()))\n'
       '                if _r and len(_r) > len(_dl):\n'
       '                    _dl = list(_r)\n')

if ALT not in src:
    melde("Anker nicht gefunden - Patch 72 fehlt oder schon ersetzt")
    raise SystemExit(0)

shutil.copyfile(BOT, BOT + ".bak_73")
src = src.replace(ALT, NEU, 1)
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Diagnose eingebaut, Syntax ok")
except Exception as e:
    shutil.copyfile(BOT + ".bak_73", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 73 fertig")
