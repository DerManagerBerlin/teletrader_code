#!/usr/bin/env python3
# Patch 112 - Fehlalarm "BTCUSD.s NICHT VERFUEGBAR" beseitigen.
#
#   Befund: Der Broker fuehrt BTC als "BTCUSD", ohne Endung. Der
#   Handelsweg loest das korrekt ueber SYMBOL_MAP auf ("btcusd" ->
#   BTC_SYMBOL). Nur die Startpruefung baut den Namen von Hand zusammen,
#   als BTC_SYMBOL + FX_SUFFIX, und sucht deshalb "BTCUSD.s".
#
#   Der BTC-Handel war also nie blockiert, die Meldung war ein Fehlalarm
#   in der Pruefung selbst. Ich hatte das falsch zugeordnet.
#
#   Fix: Die Pruefung nutzt denselben Aufloeser wie der Handel. Damit
#   prueft sie kuenftig das Symbol, das tatsaechlich gehandelt wird.
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
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH112 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

ALT = "            for _sym in [GOLD_SYMBOL, BTC_SYMBOL + FX_SUFFIX]:\n"
NEU = ("            # Patch 112: denselben Aufloeser wie der Handel benutzen.\n"
       "            # BTC_SYMBOL + FX_SUFFIX ergab 'BTCUSD.s', das es beim\n"
       "            # Broker nicht gibt. Gehandelt wird 'BTCUSD'.\n"
       "            for _sym in [resolve_symbol(GOLD_SYMBOL),\n"
       "                         resolve_symbol(BTC_SYMBOL)]:\n")

if NEU in src or "Patch 112" in src:
    melde("schon gepatcht"); raise SystemExit(0)
if ALT not in src:
    melde("ABBRUCH: Anker nicht gefunden"); raise SystemExit(0)

shutil.copyfile(BOT, BOT + ".bak_112")
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src.replace(ALT, NEU, 1))

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Startpruefung nutzt jetzt resolve_symbol")
except Exception as e:
    shutil.copyfile(BOT + ".bak_112", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)
print("Patch 112 fertig")
