#!/usr/bin/env python3
# Patch 80 - offene Positionen und Equity beim Start mitloggen.
#
#   Anlass: Der Runner #421989978 lief bis +204 Pips, danach steht im Log
#   17 Minuten lang nichts mehr zu ihm, und der Kontostand ist unveraendert
#   bei 926,37. Entweder ist die Position noch offen und die Trailing-
#   Verwaltung schweigt, oder sie wurde ohne Gewinn geschlossen. Aus dem
#   Log ist das nicht zu entscheiden, weil offene Positionen nirgends
#   protokolliert werden.
#
#   Ergaenzt LIVECHECK um Equity, freie Margin und eine Zeile je offener
#   Position. Rein lesend.
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
                    " [INFO] AUTOPATCH pos: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if "POSCHECK" in src:
    melde("schon vorhanden"); raise SystemExit(0)

ANKER = '            log.info("LIVECHECK Handel pausiert=" + str(is_trading_paused()))\n'
if ANKER not in src:
    melde("FEHLER: Anker nicht gefunden"); raise SystemExit(1)

NEU = '''            try:  # POSCHECK
                _eq = getattr(info, "equity", None)
                _fm = getattr(info, "margin_free", None)
                log.info("POSCHECK Balance=" + str(round(info.balance, 2)) +
                         " Equity=" + (str(round(_eq, 2)) if _eq is not None else "?") +
                         " FreieMargin=" + (str(round(_fm, 2)) if _fm is not None else "?"))
                _ps = mt5.positions_get() or []
                if not _ps:
                    log.info("POSCHECK keine offenen Positionen")
                for _p in _ps[:12]:
                    log.info("POSCHECK offen #" + str(_p.ticket) +
                             " " + str(_p.symbol) +
                             " " + ("BUY" if _p.type == 0 else "SELL") +
                             " vol=" + str(_p.volume) +
                             " open=" + str(_p.price_open) +
                             " sl=" + str(_p.sl) + " tp=" + str(_p.tp) +
                             " profit=" + str(round(_p.profit, 2)) +
                             " magic=" + str(_p.magic))
                _os_ = mt5.orders_get() or []
                if _os_:
                    log.info("POSCHECK " + str(len(_os_)) + " offene Auftraege")
            except Exception as _pe:
                log.error("POSCHECK Fehler: " + str(_pe))
'''

shutil.copyfile(BOT, BOT + ".bak_80")
src = src.replace(ANKER, ANKER + NEU, 1)
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("POSCHECK eingebaut, Syntax ok")
except Exception as e:
    shutil.copyfile(BOT + ".bak_80", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 80 fertig")
