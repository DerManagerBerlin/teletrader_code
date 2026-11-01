#!/usr/bin/env python3
# patch_128_login.py
# NO_RESTART - der laufende Bot wird nicht angefasst.
#
# Ein einziger, kontrollierter Loginversuch auf das Livekonto, gegen das neu
# installierte Ultima-Terminal. Hoechstens zwei Versuche insgesamt, danach
# sperrt sich der Patch selbst: wiederholte Fehlversuche sperren das Konto
# beim Broker.
#
# Zugangsdaten werden aus der .env gelesen und nur als Umgebungsvariable an
# den Wine-Python-Prozess gereicht. Sie werden nie ausgegeben, die
# Kontonummer erscheint nur maskiert.
import io, os, re, glob, subprocess, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
PUB = os.path.join(HOME, "ttpub")
ENV = os.path.join(TT, ".env")
ZAEHLER = os.path.join(TT, ".ultima_login_versuche")
WINEPY = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "Python311", "python.exe")
_z = []


def sag(t):
    t = str(t)
    print("PATCH128 " + t)
    _z.append(t)


def schreiben():
    try:
        os.makedirs(PUB, exist_ok=True)
        with io.open(os.path.join(PUB, "status.txt"), "a",
                     encoding="utf-8") as f:
            for x in _z:
                f.write("LOGIN128 " + x + "\n")
    except Exception:
        pass


def win_pfad(p):
    """Linux-Pfad im Wine-Prefix -> Windows-Pfad. mt5.initialize(path=...)
    laeuft unter Wine-Python und versteht nur C:\\..., nicht /home/..."""
    m = p.replace("\\", "/")
    k = m.find("/drive_c/")
    if k >= 0:
        return "C:\\" + m[k + len("/drive_c/"):].replace("/", "\\")
    return p


def env_wert(key):
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
    except Exception as e:
        sag("env nicht lesbar: " + str(e))
    return ""


# ------------------------------------------------------------- 1. Sperren
try:
    _n = int(io.open(ZAEHLER).read().strip() or 0)
except Exception:
    _n = 0
if _n >= 2:
    sag("ABBRUCH: schon " + str(_n) + " Versuche. Datei .ultima_login_versuche "
        "loeschen, um erneut zu erlauben.")
    schreiben()
    sys.exit(0)

# --------------------------------------------------------- 2. Terminal suchen
_kand = [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "Program Files", "*", "terminal64.exe"))
    if "ultima" in p.lower()]
if not _kand:
    sag("ABBRUCH: kein Ultima-Terminal gefunden, Installation 120 pruefen")
    schreiben()
    sys.exit(0)
TERM = _kand[0]
sag("Terminal: " + os.path.basename(os.path.dirname(TERM)))
sag("Windows-Pfad: " + win_pfad(TERM))

if not os.path.exists(WINEPY):
    _w = glob.glob(os.path.join(HOME, ".wine", "drive_c", "Program Files",
                                "Python*", "python.exe"))
    if not _w:
        sag("ABBRUCH: Wine-Python nicht gefunden")
        schreiben()
        sys.exit(0)
    WINEPY = _w[0]

# ------------------------------------------------- 3. AutoTrading vorbereiten
# Ein frisches Terminal hat [Experts] Enabled=0. Ohne das wuerde jede Order
# mit 10027 abgelehnt. Gleiche Behandlung wie damals bei PU Prime.
_cfgs = []
for _m in ("config", "Config"):
    _cfgs += glob.glob(os.path.join(os.path.dirname(TERM), _m, "common.ini"))
_cfgs += glob.glob(os.path.join(HOME, ".wine", "drive_c", "users", "*",
                                "*", "MetaQuotes", "Terminal", "*", "config",
                                "common.ini"))
sag("common.ini gefunden: " + str(len(_cfgs)))

# ------------------------------------------------------------ 4. Zugangsdaten
_lg = env_wert("LIVE_MT5_LOGIN")
_pw = env_wert("LIVE_MT5_PASSWORD")
_sv = env_wert("LIVE_MT5_SERVER")
if not _lg or not _pw or not _sv:
    sag("ABBRUCH: Live-Zugangsdaten in .env unvollstaendig")
    schreiben()
    sys.exit(0)
try:
    _lgi = int(re.sub(r"\D", "", _lg))
except Exception:
    sag("ABBRUCH: LIVE_MT5_LOGIN ist keine Zahl")
    schreiben()
    sys.exit(0)
sag("Zugangsdaten vollstaendig, Konto ***" + str(_lgi)[-3:] +
    ", Server " + _sv)

# ------------------------------------------------------------- 5. Testskript
PROBE = os.path.join(TT, ".probe128.py")
CODE = '''import os
import MetaTrader5 as mt5
p = os.environ.get("TTPATH")
ok = mt5.initialize(path=p,
                    portable=True,
                    login=int(os.environ.get("TTLOGIN")),
                    password=os.environ.get("TTPASS"),
                    server=os.environ.get("TTSERVER"),
                    timeout=180000)
print("INIT", ok, mt5.last_error())
if not ok:
    # Ein frisches Terminal braucht beim ersten Start laenger als der
    # IPC-Timeout. Kein zweiter Anmeldeversuch, nur anhaengen und nachsehen.
    import time
    time.sleep(25)
    ok2 = mt5.initialize(path=p, portable=True, timeout=180000)
    print("NACHSCHAU", ok2, mt5.last_error())
ti = mt5.terminal_info()
if ti:
    print("TERMINAL", ti.name, "build", ti.build,
          "connected", ti.connected, "trade_allowed", ti.trade_allowed)
ai = mt5.account_info()
if ai:
    print("KONTO ***" + str(ai.login)[-3:],
          "| Server", ai.server, "| Waehrung", ai.currency,
          "| Balance", round(ai.balance, 2),
          "| Equity", round(ai.equity, 2),
          "| TradeAllowed", ai.trade_allowed)
    for s in ("XAUUSD", "XAUUSD.s", "XAUUSD.m", "GOLD"):
        si = mt5.symbol_info(s)
        if si:
            print("SYMBOL", si.name, "min", si.volume_min, "step",
                  si.volume_step, "digits", si.digits, "stops",
                  si.trade_stops_level, "visible", si.visible)
else:
    print("KEIN KONTO", mt5.last_error())
mt5.shutdown()
'''
fd = os.open(PROBE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8") as f:
    f.write(CODE)

_win = "Z:" + PROBE.replace("/", "\\")
_umg = dict(os.environ)
_umg.update({"TTPATH": win_pfad(TERM), "TTLOGIN": str(_lgi), "TTPASS": _pw,
             "TTSERVER": _sv, "DISPLAY": ":99", "WINEDEBUG": "-all"})
with io.open(ZAEHLER, "w") as f:
    f.write(str(_n + 1))
sag("Versuch " + str(_n + 1) + " von 2 laeuft")

try:
    _p = subprocess.run(["wine", WINEPY, _win], env=_umg,
                        capture_output=True, text=True, timeout=420)
    _aus = ((_p.stdout or "") + "\n" + (_p.stderr or "")).strip()
except Exception as e:
    _aus = "Fehler beim Start: " + str(e)
finally:
    try:
        os.remove(PROBE)
    except Exception:
        pass

_geheim = [x for x in (_pw, _lg) if x]
for _zeile in _aus.splitlines():
    _zeile = _zeile.strip()
    if not _zeile:
        continue
    for _g in _geheim:
        _zeile = _zeile.replace(_g, "***")
    if _zeile.startswith(("INIT", "NACHSCHAU", "TERMINAL", "KONTO", "SYMBOL", "KEIN KONTO")):
        sag(_zeile[:220])
    elif "Error" in _zeile or "error" in _zeile or "Traceback" in _zeile:
        sag("FEHLER " + _zeile[:200])

if "INIT True" in _aus or "KONTO ***" in _aus:
    sag("ERGEBNIS: Login auf das Livekonto hat funktioniert")
else:
    sag("ERGEBNIS: Login nicht erfolgreich - kein zweiter Versuch von selbst")
schreiben()
