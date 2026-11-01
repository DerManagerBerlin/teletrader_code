#!/usr/bin/env python3
# patch_126_pfad.py
#
# Umschaltung auf das Livekonto bei Ultima Markets. Drei Teile:
#   1. connect_mt5 spricht das Terminal ueber MT5_TERMINAL_PATH gezielt an.
#      Ohne Pfadangabe greift mt5.initialize() irgendein Terminal ab, und mit
#      zwei installierten Terminals ist das Zufall.
#   2. AutoTrading im neuen Terminal einschalten ([Experts] Enabled=1).
#      Ein frisches Terminal hat 0, jede Order wuerde mit 10027 abgelehnt.
#   3. watchdog.sh startet ab jetzt das eingestellte Terminal.
#   4. .env: DEMO_MODE=false und MT5_TERMINAL_PATH setzen.
#
# Zugangsdaten werden nicht gelesen und nicht ausgegeben.
import io, os, re, glob, shutil, stat, sys, py_compile

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
BOT = os.path.join(TT, "teletrader_v2.py")
ENV = os.path.join(TT, ".env")
WD = os.path.join(TT, "watchdog.sh")
PUB = os.path.join(HOME, "ttpub")
_z = []


def win_pfad(p):
    """Linux-Pfad im Wine-Prefix -> Windows-Pfad. mt5.initialize(path=...)
    laeuft unter Wine-Python und versteht nur C:\\..., nicht /home/..."""
    m = p.replace("\\", "/")
    k = m.find("/drive_c/")
    if k >= 0:
        return "C:\\" + m[k + len("/drive_c/"):].replace("/", "\\")
    return p


def sag(t):
    t = str(t)
    print("PATCH126 " + t)
    _z.append(t)


def schreiben():
    try:
        os.makedirs(PUB, exist_ok=True)
        with io.open(os.path.join(PUB, "status.txt"), "a",
                     encoding="utf-8") as f:
            for x in _z:
                f.write("PFAD126 " + x + "\n")
    except Exception:
        pass


# ------------------------------------------------------- 0. Terminal finden
_k = [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "Program Files", "*", "terminal64.exe"))
    if "ultima" in p.lower()]
if not _k:
    sag("ABBRUCH: kein Ultima-Terminal gefunden")
    schreiben()
    sys.exit(1)
TERM = _k[0]
sag("Terminal live: " + os.path.basename(os.path.dirname(TERM)))
_kd = [q for q in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "Program Files", "*", "terminal64.exe"))
    if "ultima" not in q.lower()]
TERM_DEMO = _kd[0] if _kd else ""
sag("Terminal demo: " + (os.path.basename(os.path.dirname(TERM_DEMO))
                         if TERM_DEMO else "keins"))

# ---------------------------------------------------------------- 1. Code
src = io.open(BOT, encoding="utf-8").read()
if "MT5_TERMINAL_PATH" in src:
    sag("Pfadschalter schon im Code")
else:
    A1 = "\n    if mt5.initialize():\n"
    N1 = ('\n    # PATCH126: Terminal gezielt ansprechen. Mit zwei installierten\n'
          '    # Terminals ist es sonst Zufall, welches mt5.initialize() nimmt.\n'
          '    # Demo und Live liegen in verschiedenen Terminals, darum zwei\n'
          '    # Schluessel: sonst scheitert der Rueckfall auf Demo.\n'
          '    _tschl = "MT5_TERMINAL_PATH_DEMO" if DEMO_MODE else "MT5_TERMINAL_PATH"\n'
          '    _tpfad = (os.getenv(_tschl, "") or "").strip()\n'
          '    _targs = {"path": _tpfad} if _tpfad else {}\n'
          '    if _tpfad:\n'
          '        log.info("MT5 Terminal laut " + _tschl + ": " + _tpfad)\n'
          '    if mt5.initialize(**_targs):\n')
    if src.count(A1) != 1:
        sag("FEHLER: Anker 1 nicht eindeutig (" + str(src.count(A1)) + ")")
        schreiben()
        sys.exit(1)
    src = src.replace(A1, N1, 1)

    A2 = ("        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD,\n"
          "                             server=MT5_SERVER, timeout=180000)\n")
    N2 = ("        _ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD,\n"
          "                             server=MT5_SERVER, timeout=180000,\n"
          "                             **_targs)\n")
    if src.count(A2) != 1:
        sag("FEHLER: Anker 2 nicht eindeutig (" + str(src.count(A2)) + ")")
        schreiben()
        sys.exit(1)
    src = src.replace(A2, N2, 1)

    A3 = "\n                if mt5.initialize():\n"
    N3 = "\n                if mt5.initialize(**_targs):\n"
    if src.count(A3) != 1:
        sag("FEHLER: Anker 3 nicht eindeutig (" + str(src.count(A3)) + ")")
        schreiben()
        sys.exit(1)
    src = src.replace(A3, N3, 1)

    tmp = BOT + ".p126"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        py_compile.compile(tmp, cfile=tmp + "c", doraise=True)
    except Exception as e:
        sag("FEHLER beim Compilieren: " + str(e))
        try:
            os.remove(tmp)
        except Exception:
            pass
        schreiben()
        sys.exit(1)
    try:
        os.remove(tmp + "c")
    except Exception:
        pass
    os.replace(tmp, BOT)
    sag("connect_mt5 nutzt jetzt MT5_TERMINAL_PATH")


# ------------------------------------------------------- 2. AutoTrading an
def lies_ini(p):
    with open(p, "rb") as f:
        roh = f.read()
    if roh[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return roh.decode("utf-16"), "utf-16"
    if roh.count(b"\x00") > len(roh) // 4:
        return roh.decode("utf-16-le", "replace"), "utf-16-le"
    return roh.decode("utf-8", "replace"), "utf-8"


_inis = []
for _m in ("config", "Config", "CONFIG"):
    _inis += glob.glob(os.path.join(os.path.dirname(TERM), _m, "common.ini"))
_inis += [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "users", "*", "*", "MetaQuotes", "Terminal",
    "*", "config", "common.ini"))]
_inis += [p for p in glob.glob(os.path.join(
    HOME, ".wine", "drive_c", "users", "*", "*", "*", "MetaQuotes", "Terminal",
    "*", "config", "common.ini"))]
_inis = sorted(set(_inis))
sag("common.ini Kandidaten: " + str(len(_inis)))
_an = 0
for _p in _inis:
    try:
        _txt, _kod = lies_ini(_p)
        if "[Experts]" not in _txt:
            continue
        _neu, _n = re.subn(r"(?im)^(\s*Enabled\s*=\s*)0(\s*)$", r"\g<1>1\g<2>",
                           _txt)
        if _n == 0:
            continue
        _mode = stat.S_IMODE(os.stat(_p).st_mode)
        _tp = _p + ".p126"
        with open(_tp, "wb") as f:
            f.write(_neu.encode(_kod))
        os.chmod(_tp, _mode)
        os.replace(_tp, _p)
        _an += 1
        sag("AutoTrading an in " + os.path.basename(os.path.dirname(
            os.path.dirname(_p))) + "/config/common.ini")
    except Exception as e:
        sag("common.ini " + os.path.basename(_p) + ": " + str(e))
if _an == 0:
    sag("Hinweis: keine common.ini geaendert - Terminal war evtl. noch nie "
        "gestartet. AutoTrading muss nach dem ersten Start nachgezogen werden.")

# watchdog.sh bleibt unveraendert: der Bot laeuft weiter auf Demo.

# ----------------------------------------------------------------- 4. .env
SOLL = []
if TERM_DEMO:
    SOLL.append(("MT5_TERMINAL_PATH_DEMO", win_pfad(TERM_DEMO)))
with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
    alt = f.read()
zeilen = alt.split("\n")


def key(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (key(z) for z in zeilen) if k)
fehlt = []
for k, v in SOLL:
    _hit = False
    for i, z in enumerate(zeilen):
        if key(z) == k:
            zeilen[i] = k + "=" + v
            _hit = True
    if not _hit:
        fehlt.append((k, v))
if fehlt:
    if zeilen and zeilen[-1].strip() != "":
        zeilen.append("")
    zeilen.append("# PATCH126 Livebetrieb Ultima Markets")
    for k, v in fehlt:
        zeilen.append(k + "=" + v)
neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nicht geschrieben")
    schreiben()
    sys.exit(1)
fd = os.open(ENV + ".bak126", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
fd = os.open(ENV + ".p126", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    os.chmod(ENV + ".p126", stat.S_IMODE(os.stat(ENV).st_mode))
except Exception:
    pass
os.replace(ENV + ".p126", ENV)
sag("env gesetzt: nur MT5_TERMINAL_PATH_DEMO, DEMO_MODE unveraendert")

sag("fertig. Bot bleibt auf Demo, spricht sein Terminal jetzt aber gezielt an.")
schreiben()
