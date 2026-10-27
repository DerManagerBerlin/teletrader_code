#!/usr/bin/env python3
# Patch 113 - meinen Fehlalarm aus Patch 112 zuruecknehmen.
#
#   Patch 112 hat die Startpruefung durch resolve_symbol geschickt. Der
#   Aufloeser schreibt im Fallback alles gross, aus "XAUUSD.s" wird
#   "XAUUSD.S", und symbol_info findet das nicht. Ergebnis: ein Fehlalarm
#   weg, ein neuer dazu.
#
#   Richtig ist das Einfachste: Beide Namen stehen bereits korrekt in der
#   Konfiguration (GOLD_SYMBOL="XAUUSD.s", BTC_SYMBOL="BTCUSD"). Sie
#   werden unveraendert geprueft. Der urspruengliche Fehler war allein
#   das angehaengte FX_SUFFIX bei BTC.
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
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH113 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

ALT = ("            for _sym in [resolve_symbol(GOLD_SYMBOL),\n"
       "                         resolve_symbol(BTC_SYMBOL)]:\n")
NEU = ("            # Patch 113: Namen unveraendert pruefen. resolve_symbol\n"
       "            # macht im Fallback aus 'XAUUSD.s' ein 'XAUUSD.S'.\n"
       "            for _sym in [GOLD_SYMBOL, BTC_SYMBOL]:\n")

if "Patch 113" in src:
    melde("schon gepatcht"); raise SystemExit(0)
if ALT not in src:
    melde("ABBRUCH: Anker nicht gefunden"); raise SystemExit(0)

shutil.copyfile(BOT, BOT + ".bak_113")
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src.replace(ALT, NEU, 1))

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Startpruefung prueft GOLD_SYMBOL und BTC_SYMBOL unveraendert")
except Exception as e:
    shutil.copyfile(BOT + ".bak_113", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)
print("Patch 113 fertig")
