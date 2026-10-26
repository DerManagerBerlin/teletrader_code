#!/usr/bin/env python3
# Patch 97 - Live-Umstieg, jetzt mit passender Bibliothek.
#
#   Neue Lage: Die MetaTrader5-Bibliothek stand auf 5.0.5735, das Terminal
#   auf Build 6230. Seit Patch 95 steht sie auf 5.0.6231. Genau diese
#   Luecke erklaert das bisherige Bild: Anhaengen ging immer, der
#   Kontowechsel endete dreimal im IPC-Timeout, und das Terminal
#   protokollierte dabei nicht einen einzigen Anmeldeversuch.
#
#   Deshalb diesmal NICHT ueber common.ini, sondern auf dem normalen Weg:
#   DEMO_MODE=false, Neustart, und der Bot meldet sich selbst an.
#
#   Zweistufig, weil MT5 bei jedem Kontowechsel AutoTrading abschaltet:
#     Stufe 1: live anmelden
#     Stufe 2: [Experts] Enabled=1 und noch ein Neustart, damit gehandelt
#              werden kann
#   Scheitert Stufe 1, geht alles zurueck auf Demo.
import os, re, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
LOG = os.path.join(TT, "bot.log")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
INI = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                   "PU Prime MT5 Terminal", "Config", "common.ini")
MARKE = os.path.join(TT, ".patch97_laeuft")
UNIT = "teletrader.service"

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH97 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=90):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

if os.path.exists(MARKE):
    try:
        alt = time.time() - os.path.getmtime(MARKE)
    except Exception:
        alt = 0
    if alt < 1200:
        melde("laeuft bereits seit " + str(int(alt)) + "s"); raise SystemExit(0)
try:
    open(MARKE, "w").write(datetime.now().isoformat())
except Exception:
    pass

def lib():
    return sh("WINEDEBUG=-all DISPLAY=:99 wine '" + HOME +
              "/.wine/drive_c/Program Files/Python311/python.exe' -c "
              "\"import MetaTrader5 as m;print(m.__version__)\" 2>/dev/null "
              "| tr -d '\\r' | tail -1", t=120)
melde("Bibliothek: " + lib())

def env_setzen(demo):
    with open(ENV, encoding="utf-8") as f:
        zeilen = f.readlines()
    neu, da = [], False
    for z in zeilen:
        if z.strip().startswith("DEMO_MODE="):
            neu.append("DEMO_MODE=" + ("true" if demo else "false") + "\n"); da = True
        else:
            neu.append(z)
    if not da:
        neu.append("DEMO_MODE=" + ("true" if demo else "false") + "\n")
    tmp = ENV + ".tmp97"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(neu); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, 0o600); os.replace(tmp, ENV)
    with open(ENV, encoding="utf-8") as f:
        return ("DEMO_MODE=" + ("true" if demo else "false")) in f.read()

def kodierung(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return "utf-16"
    if b[:3] == b"\xef\xbb\xbf": return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4: return "utf-16-le"
    return "utf-8"

def algo_an():
    try:
        with open(INI, "rb") as f: roh = f.read()
        kod = kodierung(roh); t = roh.decode(kod, errors="strict")
        crlf = "\r\n" in t
        zs = t.split("\r\n") if crlf else t.split("\n")
        ab = ""
        for i, z in enumerate(zs):
            s = z.strip()
            if s.startswith("[") and s.endswith("]"): ab = s.lower(); continue
            if ab == "[experts]" and re.match(r"^\s*Enabled\s*=", z, re.I):
                zs[i] = "Enabled=1"
        st = os.stat(INI); tmp = INI + ".neu97"
        with open(tmp, "wb") as f:
            f.write((("\r\n" if crlf else "\n").join(zs)).encode(kod))
            f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, INI)
        return True
    except Exception as e:
        melde("Enabled nicht setzbar: " + str(e)); return False

def zaehler():
    n = sh("grep -c 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null || echo 0", t=20).strip()
    return int(n) if n.isdigit() else 0

def warte_auf_neue(vor, sek):
    ende = time.time() + sek
    while time.time() < ende:
        time.sleep(5)
        if zaehler() > vor:
            return sh("grep 'LIVECHECK Modus' '" + LOG + "' | tail -1", t=20)
    return ""

sh("cp -p '" + ENV + "' '" + ENV + ".bak_97'")
for f_ in ("LOGIN_FAILS", os.path.join(TT, "LOGIN_FAILS")):
    try:
        if os.path.exists(f_): os.remove(f_)
    except Exception: pass

melde("Stufe 1: .env auf live " +
      ("gesetzt" if env_setzen(False) else "NICHT gesetzt"))
vor = zaehler()
melde("Neustart 1: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
zeile = warte_auf_neue(vor, 330)
melde("Ergebnis 1: " + (zeile[:190] or "keine neue LIVECHECK-Zeile in 330 s"))

if "Modus=LIVE" in zeile:
    melde("LIVE steht")
    if "TradeAllowed=True" in zeile:
        melde("AutoTrading ist bereits an, fertig")
    else:
        melde("Stufe 2: AutoTrading setzen (MT5 schaltet es beim Kontowechsel ab)")
        algo_an()
        vor = zaehler()
        melde("Neustart 2: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
        z2 = warte_auf_neue(vor, 300)
        melde("Ergebnis 2: " + (z2[:190] or "keine neue Zeile in 300 s"))
else:
    melde("Live nicht bestaetigt - zurueck auf Demo")
    env_setzen(True)
    algo_an()
    vor = zaehler()
    melde("Neustart zurueck: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
    melde("Demo wieder da: " + (warte_auf_neue(vor, 240)[:170] or "NICHT bestaetigt"))

try: os.remove(MARKE)
except Exception: pass
print("Patch 97 fertig")
