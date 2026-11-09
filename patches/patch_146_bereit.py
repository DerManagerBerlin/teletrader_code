#!/usr/bin/env python3
# patch_146_bereit.py
# NO_RESTART - liest nur.
#
# Nach dem Auffuellen: ist der Bot wieder handlungsfaehig? Geprueft werden
# Terminal, AutoTrading, Kontostand, die Risikogrenze gegen die ueblichen
# Stopweiten, offene Positionen und ob noch eine Sperre steht.
import io, os, re, json, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
_z = []


def sag(t):
    t = str(t)
    print("PATCH146 " + t)
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


# --- Sperren ---
_flag = os.path.join(TT, "TRADING_PAUSED")
sag("Handelssperre: " + ("STEHT NOCH" if os.path.exists(_flag) else "keine"))
try:
    _b = json.load(io.open(os.path.join(TT, "bremse.json"), encoding="utf-8"))
    sag("bremse.json: " + json.dumps(_b)[:160])
except Exception as e:
    sag("bremse.json: " + str(e)[:80])

W = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                           "Python*", "python.exe"))
if not W:
    sag("ABBRUCH: Wine-Python fehlt")
    sys.exit(0)

PROBE = os.path.join(TT, ".probe146.py")
CODE = '''import os
import MetaTrader5 as mt5
p = os.environ.get("TTPATH") or ""
a = {"path": p} if p else {}
if os.environ.get("TTPORT") == "true":
    a["portable"] = True
print("INIT", mt5.initialize(**a), mt5.last_error())
ti = mt5.terminal_info()
if ti:
    print("TERMINAL verbunden", ti.connected, "| AutoTrading", ti.trade_allowed)
ai = mt5.account_info()
s = os.environ.get("TTSYM")
si = mt5.symbol_info(s)
if si is None or not si.visible:
    mt5.symbol_select(s, True)
    si = mt5.symbol_info(s)
t = mt5.symbol_info_tick(s)
if ai and si:
    print("KONTO ***" + str(ai.login)[-3:], "| Balance", round(ai.balance, 2),
          "| Equity", round(ai.equity, 2), "| frei", round(ai.margin_free, 2),
          "| TradeAllowed", ai.trade_allowed)
    if t and si.point:
        print("KURS bid", t.bid, "| Spread",
              round((t.ask - t.bid) / (si.point * 10), 1), "Pips")
    pip = (si.trade_tick_value / si.trade_tick_size) * si.point * 10 * 0.01
    kappe = ai.balance * float(os.environ.get("TTCAP", "0.10"))
    print("GRENZE 0.01 Lot =", round(pip, 4), "je Pip | Kappe",
          round(kappe, 2), "bei", os.environ.get("TTCAP"), "Anteil")
    for sp in (76, 80, 93, 100, 120):
        r = pip * sp
        print("PRUEFUNG Stop", sp, "Pips = Risiko", round(r, 2),
              "->", "PASST" if r <= kappe else "zu gross")
    print("MAXSTOP rechnerisch", round(kappe / pip, 0), "Pips")
print("POSITIONEN", len(mt5.positions_get() or []))
for q in (mt5.positions_get() or []):
    print("POS", q.symbol, "vol", q.volume, "magic", q.magic,
          "profit", round(q.profit, 2), "sl", q.sl, "tp", q.tp)
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)
_u = dict(os.environ)
_u.update({"TTPATH": env_wert("MT5_TERMINAL_PATH", ""),
           "TTPORT": env_wert("MT5_TERMINAL_PORTABLE", "false").lower(),
           "TTSYM": env_wert("LIVE_GOLD_SYMBOL", "XAUUSD"),
           "TTCAP": env_wert("MAX_RISK_PCT", "0.10"),
           "DISPLAY": ":99", "WINEDEBUG": "-all"})
try:
    _p = subprocess.run(["wine", W[0], "Z:" + PROBE.replace("/", "\\")],
                        env=_u, capture_output=True, text=True, timeout=240)
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
    if _l.startswith(("INIT", "TERMINAL", "KONTO", "KURS", "GRENZE",
                      "PRUEFUNG", "MAXSTOP", "POSITIONEN", "POS")):
        sag(_l[:200])
for k in ("MAX_RISK_PCT", "MAX_LAYERS", "NUR_SYMBOLE", "LOSE_STREAK_LIMIT",
          "TAGESSTOP_PCT", "WOCHENSTOP_PCT", "REGEX_ONLY_CHANNELS"):
    sag("  " + k + "=" + (env_wert(k) or "(nicht gesetzt)"))
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("BEREIT146 " + x + "\n")
except Exception:
    pass
