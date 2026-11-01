#!/usr/bin/env python3
# patch_138_oeffnung.py (Kontrolle zur Marktoeffnung)
# NO_RESTART - haengt sich nur an das laufende Terminal und berichtet.
#
# Abnahme vor dem Scharfschalten: Modus, Konto maskiert, Waehrung, Balance,
# AutoTrading, die Daten des eingestellten Goldsymbols und was 0.01 Lot bei
# 80 Pips Stop tatsaechlich kosten. Keine Order, kein Login, keine
# Zugangsdaten.
import io, os, re, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
_z = []


def sag(t):
    t = str(t)
    print("PATCH138 " + t)
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


DEMO = (env_wert("DEMO_MODE", "true").lower() == "true")
SYM = (env_wert("DEMO_GOLD_SYMBOL", "XAUUSD.p") if DEMO
       else env_wert("LIVE_GOLD_SYMBOL", "XAUUSD.s"))
PFAD = env_wert("MT5_TERMINAL_PATH_DEMO" if DEMO else "MT5_TERMINAL_PATH", "")
sag("Modus laut .env: " + ("DEMO" if DEMO else "LIVE") + " | Symbol " + SYM)
sag("Terminalpfad: " + (PFAD or "(nicht gesetzt)"))

WINEPY = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                                "Python*", "python.exe"))
if not WINEPY:
    sag("ABBRUCH: Wine-Python nicht gefunden")
    sys.exit(0)

PROBE = os.path.join(TT, ".probe138.py")
CODE = '''import os
import MetaTrader5 as mt5
p = os.environ.get("TTPATH") or ""
args = {"path": p} if p else {}
if p and os.environ.get("TTPORT") == "true":
    args["portable"] = True
ok = mt5.initialize(**args)
print("INIT", ok, mt5.last_error())
ti = mt5.terminal_info()
if ti:
    print("TERMINAL", ti.name, "build", ti.build, "connected", ti.connected,
          "trade_allowed", ti.trade_allowed)
ai = mt5.account_info()
if ai:
    print("KONTO ***" + str(ai.login)[-3:], "| Server", ai.server,
          "| Waehrung", ai.currency, "| Balance", round(ai.balance, 2),
          "| Equity", round(ai.equity, 2), "| FreieMargin",
          round(ai.margin_free, 2), "| Hebel", ai.leverage,
          "| TradeAllowed", ai.trade_allowed)
    s = os.environ.get("TTSYM") or ""
    si = mt5.symbol_info(s)
    if si is None:
        mt5.symbol_select(s, True)
        si = mt5.symbol_info(s)
    if si is None:
        print("SYMBOL FEHLT", s)
        alle = [x.name for x in (mt5.symbols_get() or [])
                if "XAU" in x.name.upper()]
        print("XAU-KANDIDATEN", ", ".join(alle[:12]))
    else:
        t = mt5.symbol_info_tick(s)
        spr = ((t.ask - t.bid) / (si.point * 10)) if (t and si.point) else -1
        print("SYMBOL", si.name, "| min", si.volume_min, "| step",
              si.volume_step, "| digits", si.digits, "| stops",
              si.trade_stops_level, "| sichtbar", si.visible,
              "| Spread", round(spr, 1), "Pips")
        if si.trade_tick_size:
            pipwert = (si.trade_tick_value / si.trade_tick_size) * si.point * 10
            print("RECHNUNG 0.01 Lot:", round(pipwert * 0.01, 4),
                  ai.currency, "je Pip |", "80 Pips Stop =",
                  round(pipwert * 0.01 * 80, 2), ai.currency, "=",
                  round(pipwert * 0.01 * 80 / max(ai.balance, 0.01) * 100, 1),
                  "% vom Konto")
        print("MARGIN 0.01 Lot:", mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY, s, 0.01, (t.ask if t else 0)), ai.currency)
    print("POSITIONEN", len(mt5.positions_get() or []))
else:
    print("KEIN KONTO", mt5.last_error())
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)
_win = "Z:" + PROBE.replace("/", "\\")
_umg = dict(os.environ)
_umg.update({"TTPATH": PFAD, "TTSYM": SYM,
             "TTPORT": env_wert("MT5_TERMINAL_PORTABLE", "false").lower(), "DISPLAY": ":99",
             "WINEDEBUG": "-all"})
try:
    _p = subprocess.run(["wine", WINEPY[0], _win], env=_umg,
                        capture_output=True, text=True, timeout=300)
    _aus = ((_p.stdout or "") + "\n" + (_p.stderr or "")).strip()
except Exception as e:
    _aus = "Fehler: " + str(e)
finally:
    try:
        os.remove(PROBE)
    except Exception:
        pass

for _zeile in _aus.splitlines():
    _zeile = _zeile.strip()
    if _zeile.startswith(("INIT", "TERMINAL", "KONTO", "SYMBOL", "RECHNUNG",
                          "MARGIN", "POSITIONEN", "KEIN KONTO",
                          "XAU-KANDIDATEN")):
        sag(_zeile[:220])

for k in ("MAX_LAYERS", "MAX_POS_PER_SYMBOL", "MAX_RISK_PCT", "NUR_SYMBOLE",
          "MAX_SPREAD_PIPS", "LOSE_STREAK_LIMIT", "TAGESSTOP_PCT",
          "WOCHENSTOP_PCT", "RUNNER_ONLY", "RUNNER_LEINE_AB_PIPS",
          "TRADING_HOUR_START", "TRADING_HOUR_END", "AUTO_CONFIRM_LIVE"):
    sag("  " + k + "=" + (env_wert(k) or "(nicht gesetzt)"))

try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("CHECK138 " + x + "\n")
except Exception:
    pass
