#!/usr/bin/env python3
# patch_141_goldtick.py
# NO_RESTART - liest nur.
#
# Zwei offene Fragen zur Marktoeffnung:
# 1. Kommen echte Kurse? Dafuer das Symbol auswaehlen und den Tick lesen.
# 2. Die Balance ist von 105,97 auf 112,32 gestiegen, ohne dass im Log ein
#    Trade steht und ohne offene Position. Also Historie abfragen.
import io, os, re, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
_z = []


def sag(t):
    t = str(t)
    print("PATCH141 " + t)
    _z.append(t)


def env_wert(key, vor=""):
    try:
        with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
            for ln in f:
                m = re.match(r"^\s*(?:export\s+)?" + re.escape(key) +
                             r"\s*=\s*(.*?)\s*$", ln.rstrip("\n"))
                if m:
                    v = m.group(1)
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    return v
    except Exception:
        pass
    return vor


W = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                           "Python*", "python.exe"))
if not W:
    sag("ABBRUCH: Wine-Python fehlt")
    sys.exit(0)

PROBE = os.path.join(TT, ".probe141.py")
CODE = '''import os
from datetime import datetime, timedelta
import MetaTrader5 as mt5
p = os.environ.get("TTPATH") or ""
a = {"path": p} if p else {}
if os.environ.get("TTPORT") == "true":
    a["portable"] = True
print("INIT", mt5.initialize(**a), mt5.last_error())
s = os.environ.get("TTSYM")
si = mt5.symbol_info(s)
if si is None or not si.visible:
    mt5.symbol_select(s, True)
    si = mt5.symbol_info(s)
print("SICHTBAR", None if si is None else si.visible)
import time as _w
for _i in range(6):
    t = mt5.symbol_info_tick(s)
    if t and si and t.bid:
        print("TICK bid", t.bid, "ask", t.ask, "zeit", t.time,
              "| Spread", round((t.ask - t.bid) / (si.point * 10), 1), "Pips")
        break
    print("TICK Versuch", _i + 1, "noch keiner")
    _w.sleep(10)
# Zum Vergleich: welche Symbole liefern ueberhaupt Kurse
for _s2 in ("BTCUSD", "EURUSD", "XAUUSD", "XAGUSD"):
    mt5.symbol_select(_s2, True)
    _t2 = mt5.symbol_info_tick(_s2)
    print("VERGLEICH", _s2, "bid", None if not _t2 else _t2.bid,
          "zeit", None if not _t2 else _t2.time)
_alle = [x.name for x in (mt5.symbols_get() or []) if "XAU" in x.name.upper()]
print("XAU-SYMBOLE", ", ".join(_alle[:14]))
ai = mt5.account_info()
if ai:
    print("KONTO Balance", round(ai.balance, 2), "Equity", round(ai.equity, 2),
          "Credit", round(getattr(ai, "credit", 0), 2),
          "Profit", round(getattr(ai, "profit", 0), 2))
print("POSITIONEN", len(mt5.positions_get() or []))
print("ORDERS", len(mt5.orders_get() or []))
von = datetime.now() - timedelta(days=1)
bis = datetime.now() + timedelta(days=1)
dl = mt5.history_deals_get(von, bis)
print("DEALS gesamt", 0 if dl is None else len(dl), mt5.last_error())
for d in (dl or [])[-3:]:
    print("DEAL", d.time, d.symbol, "typ", d.type, "entry", d.entry,
          "vol", d.volume, "preis", d.price, "profit", round(d.profit, 2),
          "swap", round(d.swap, 2), "komm", round(d.commission, 2),
          "magic", d.magic, "kommentar", str(d.comment)[:28])
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)
_u = dict(os.environ)
_u.update({"TTPATH": env_wert("MT5_TERMINAL_PATH", ""),
           "TTPORT": env_wert("MT5_TERMINAL_PORTABLE", "false").lower(),
           "TTSYM": env_wert("LIVE_GOLD_SYMBOL", "XAUUSD"),
           "DISPLAY": ":99", "WINEDEBUG": "-all"})
try:
    _p = subprocess.run(["wine", W[0], "Z:" + PROBE.replace("/", "\\")],
                        env=_u, capture_output=True, text=True, timeout=300)
    _aus = ((_p.stdout or "") + "\n" + (_p.stderr or "")).strip()
except Exception as e:
    _aus = "Fehler: " + str(e)
finally:
    try:
        os.remove(PROBE)
    except Exception:
        pass
for _l in _aus.splitlines():
    _l = _l.strip()
    if _l.startswith(("INIT", "SICHTBAR", "TICK", "KONTO", "POSITIONEN",
                      "ORDERS", "DEALS", "DEAL", "VERGLEICH", "XAU-SYMBOLE")):
        sag(_l[:210])
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("GOLD141 " + x + "\n")
except Exception:
    pass
