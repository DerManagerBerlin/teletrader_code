#!/usr/bin/env python3
# patch_134_symbol.py
# NO_RESTART - haengt sich nur an das laufende Terminal.
#
# XAUUSD steht auf dem Livekonto noch nicht in der Marktuebersicht
# (sichtbar=False). Der Handelspfad holt es zwar selbst nach, aber dann erst
# im Moment des ersten Signals. Einmal vorher auswaehlen spart den Umweg und
# sorgt dafuer, dass die Spread-Schleuse von Anfang an echte Kurse sieht.
import io, os, re, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
_z = []


def sag(t):
    t = str(t)
    print("PATCH134 " + t)
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


SYM = env_wert("LIVE_GOLD_SYMBOL", "XAUUSD")
PFAD = env_wert("MT5_TERMINAL_PATH", "")
PORT = env_wert("MT5_TERMINAL_PORTABLE", "false").lower()
WINEPY = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                                "Python*", "python.exe"))
if not WINEPY:
    sag("ABBRUCH: Wine-Python nicht gefunden")
    sys.exit(0)

PROBE = os.path.join(TT, ".probe134.py")
CODE = '''import os
import MetaTrader5 as mt5
p = os.environ.get("TTPATH") or ""
a = {"path": p} if p else {}
if p and os.environ.get("TTPORT") == "true":
    a["portable"] = True
print("INIT", mt5.initialize(**a), mt5.last_error())
s = os.environ.get("TTSYM")
si = mt5.symbol_info(s)
print("VORHER sichtbar", None if si is None else si.visible)
print("SELECT", mt5.symbol_select(s, True), mt5.last_error())
si = mt5.symbol_info(s)
print("NACHHER sichtbar", None if si is None else si.visible)
t = mt5.symbol_info_tick(s)
if t:
    print("TICK bid", t.bid, "ask", t.ask)
else:
    print("TICK keiner - Markt geschlossen")
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)
_umg = dict(os.environ)
_umg.update({"TTPATH": PFAD, "TTSYM": SYM, "TTPORT": PORT,
             "DISPLAY": ":99", "WINEDEBUG": "-all"})
try:
    _p = subprocess.run(["wine", WINEPY[0], "Z:" + PROBE.replace("/", "\\")],
                        env=_umg, capture_output=True, text=True, timeout=240)
    _aus = ((_p.stdout or "") + "\n" + (_p.stderr or "")).strip()
except Exception as e:
    _aus = "Fehler: " + str(e)
finally:
    try:
        os.remove(PROBE)
    except Exception:
        pass
for _zl in _aus.splitlines():
    _zl = _zl.strip()
    if _zl.startswith(("INIT", "VORHER", "SELECT", "NACHHER", "TICK")):
        sag(_zl[:200])
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("SYM134 " + x + "\n")
except Exception:
    pass
