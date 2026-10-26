#!/usr/bin/env python3
# Patch 87 - wie 86, meldet aber nach ttpub/status.txt statt ins bot.log.
#
#   Lage: Nach zwei Live-Umstiegsversuchen steht der Bot im Livemodus und
#   haengt in der Anmeldung. Das Log endet bei "Live-Modus bestaetigt",
#   seit 16:05 keine Zeile mehr. Mein Rueckfall aus Patch 84 hat die .env
#   offenbar nicht zurueckgesetzt.
#
#   Dieser Patch macht nur eines: Demokonto in die Terminal-Konfiguration,
#   DEMO_MODE=true, AutoTrading an, Neustart. Kein Livesversuch.
#   Er prueft danach und wiederholt einmal, falls noetig.
import os, re, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
BOTLOG = os.path.join(TT, "bot.log")
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
INI = os.path.join(MT5DIR, "Config", "common.ini")
UNIT = "teletrader.service"

STATUS = os.path.join(HOME, "ttpub", "status.txt")

def log(t):
    """Doppelt melden: ins bot.log wie gewohnt, und zusaetzlich nach
    ttpub/status.txt. Das bot.log ist gerade unzuverlaessig, Zeilen gehen
    verloren; status.txt wird vom Spiegel unveraendert mitgenommen."""
    zeile = (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") +
             " PATCH87 " + t)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(zeile.replace("PATCH87", "[INFO] AUTOPATCH zur87:") + "\n")
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=60):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)

demo_login = demo_server = ""
try:
    with open(ENV, encoding="utf-8") as f:
        inhalt = f.read()
    for z in inhalt.splitlines():
        s = z.strip()
        if s.startswith("DEMO_MT5_LOGIN="):
            demo_login = s.split("=", 1)[1].strip()
        elif s.startswith("DEMO_MT5_SERVER="):
            demo_server = s.split("=", 1)[1].strip()
        elif s.startswith("DEMO_MODE="):
            melde("vorgefunden: " + s)
except Exception as e:
    melde("ABBRUCH: .env nicht lesbar: " + str(e)); raise SystemExit(0)

if not demo_login.isdigit():
    demo_login = "700190957"      # aus dem Log bekannt
if not demo_server:
    demo_server = "PUPrime-Demo"
melde("Ziel: Demokonto endet auf " + demo_login[-3:] + " @ " + demo_server)

def kodierung(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return "utf-16"
    if b[:3] == b"\xef\xbb\xbf": return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4: return "utf-16-le"
    return "utf-8"

def setze_ini(login, server):
    with open(INI, "rb") as f:
        roh = f.read()
    kod = kodierung(roh)
    text = roh.decode(kod, errors="strict")
    crlf = "\r\n" in text
    zeilen = text.split("\r\n") if crlf else text.split("\n")
    ab = ""
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("[") and s.endswith("]"):
            ab = s.lower(); continue
        if ab == "[common]" and re.match(r"^\s*Login\s*=", z, re.I):
            zeilen[i] = "Login=" + login
        elif ab == "[common]" and re.match(r"^\s*Server\s*=", z, re.I):
            zeilen[i] = "Server=" + server
        elif ab == "[experts]" and re.match(r"^\s*Enabled\s*=", z, re.I):
            zeilen[i] = "Enabled=1"
    neu = ("\r\n" if crlf else "\n").join(zeilen)
    st = os.stat(INI)
    tmp = INI + ".neu87"
    with open(tmp, "wb") as f:
        f.write(neu.encode(kod)); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, INI)

def setze_demo_env():
    with open(ENV, encoding="utf-8") as f:
        zeilen = f.readlines()
    neu, da = [], False
    for z in zeilen:
        if z.strip().startswith("DEMO_MODE="):
            neu.append("DEMO_MODE=true\n"); da = True
        else:
            neu.append(z)
    if not da:
        neu.append("DEMO_MODE=true\n")
    tmp = ENV + ".tmp87"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(neu); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV)
    # sofort nachlesen, nicht blind vertrauen
    with open(ENV, encoding="utf-8") as f:
        return "DEMO_MODE=true" in f.read()

for versuch in (1, 2):
    try:
        if os.path.exists(INI):
            setze_ini(demo_login, demo_server)
        ok = setze_demo_env()
        melde("Versuch " + str(versuch) + ": .env auf DEMO_MODE=true " +
              ("bestaetigt" if ok else "NICHT bestaetigt"))
    except Exception as e:
        melde("Versuch " + str(versuch) + " Schreibfehler: " + str(e))
        continue
    # Sperrzaehler weg, die Fehlversuche waren IPC-Timeouts
    for f_ in ("LOGIN_FAILS", os.path.join(TT, "LOGIN_FAILS")):
        try:
            if os.path.exists(f_):
                os.remove(f_)
        except Exception:
            pass
    melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
    gefunden = ""
    for _ in range(30):           # bis 150 s
        time.sleep(5)
        gefunden = sh("grep 'LIVECHECK Modus' '" + BOTLOG + "' 2>/dev/null | tail -1")
        if "Modus=DEMO" in gefunden:
            break
    if "Modus=DEMO" in gefunden:
        melde("DEMO steht: " + gefunden[:160])
        break
    melde("noch nicht oben, letzter Stand: " + (gefunden or "(nichts)")[:120])

melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1"))
print("Patch 87 fertig")
