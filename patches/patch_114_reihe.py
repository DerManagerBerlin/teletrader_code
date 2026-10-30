#!/usr/bin/env python3
# Patch 114 - Kontostandsreihe auch bei Aenderung fortschreiben.
#
#   Bisher schreibt die Reihe nur beim Oeffnen eines Trades (Patch 74).
#   Schliessungen dazwischen fehlen, deshalb zeigt das Diagramm einen
#   veralteten Stand, solange kein neues Signal kommt. Am Dienstag war das
#   bereits einmal irrefuehrend, und heute lief ein Trade mit +140 Pips,
#   ohne dass die Reihe sich bewegte.
#
#   Diese Aenderung haengt sich an die Equity-Guardian-Schleife, die
#   ohnehin jede Minute laeuft. Geschrieben wird nur, wenn sich der
#   Kontostand gegenueber der letzten Zeile geaendert hat. Es entstehen
#   also keine Dubletten und keine Zeilen im Leerlauf.
#
#   Rein ergaenzend, kein Eingriff in die Handelslogik.
import os, shutil
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH114 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if "REIHE_LAUFEND" in src:
    melde("schon vorhanden"); raise SystemExit(0)

ANKER = ("                equity    = info.equity\n")
if ANKER not in src:
    melde("ABBRUCH: Anker nicht gefunden"); raise SystemExit(0)

NEU = ('''                try:  # REIHE_LAUFEND (Patch 114)
                    _kr = "Z:\\\\home\\\\alexander_lacher\\\\ttpub\\\\kontostand.csv"
                    _letzt = None
                    if os.path.exists(_kr):
                        with open(_kr, "r", encoding="utf-8") as _fh:
                            _zz = [z for z in _fh.read().splitlines() if z.strip()]
                        if len(_zz) > 1:
                            _letzt = _zz[-1].split(";")[1]
                    _jetzt = str(round(info.balance, 2))
                    if _letzt is not None and _jetzt != _letzt:
                        with open(_kr, "a", encoding="utf-8") as _fh:
                            _fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
                                      ";" + _jetzt + ";Abschluss\\n")
                except Exception:
                    pass
''' + ANKER)

shutil.copyfile(BOT, BOT + ".bak_114")
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src.replace(ANKER, NEU, 1))

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Reihe wird jetzt auch bei Abschluessen fortgeschrieben")
except Exception as e:
    shutil.copyfile(BOT + ".bak_114", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)
print("Patch 114 fertig")
