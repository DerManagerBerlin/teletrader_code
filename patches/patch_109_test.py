#!/usr/bin/env python3
# NO_RESTART
# Patch 109 - Entscheidungstest: funktioniert ein Kontowechsel ueberhaupt?
#
#   Im Terminal sind PU-Prime-Livekonten MIT gespeichertem Passwort
#   hinterlegt (19071951 stand im Navigator). Fuer Ultima ist keins
#   gespeichert. Dieser Test schaltet common.ini testweise auf das
#   gespeicherte PU-Prime-Konto, genau der Weg, der bei Ultima wirkungslos
#   blieb.
#
#     Klappt es  -> der Weg stimmt, es fehlt nur das Ultima-Passwort.
#     Klappt es nicht -> Kontowechsel ist grundsaetzlich kaputt, dann
#                        lohnt kein weiterer Versuch auf diesem Unterbau.
#
#   Auf dem Testkonto liegen 0,22 USD, es wird nichts gehandelt. Danach
#   wird in jedem Fall auf das Demokonto zurueckgestellt.
import os, re, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
INI = os.path.join(MT5DIR, "Config", "common.ini")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
UNIT = "teletrader.service"

TEST_LOGIN, TEST_SERVER = "19071951", "PUPrime-Live2"
DEMO_LOGIN, DEMO_SERVER = "700190957", "PUPrime-Demo"

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH109 " + t
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
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

def kod(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return "utf-16"
    if b[:3] == b"\xef\xbb\xbf": return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4: return "utf-16-le"
    return "utf-8"

def setze(login, server):
    with open(INI, "rb") as f: roh = f.read()
    k = kod(roh); t = roh.decode(k, errors="strict")
    crlf = "\r\n" in t
    zs = t.split("\r\n") if crlf else t.split("\n")
    ab = ""
    for i, z in enumerate(zs):
        s = z.strip()
        if s.startswith("[") and s.endswith("]"): ab = s.lower(); continue
        if ab == "[common]" and re.match(r"^\s*Login\s*=", z, re.I):  zs[i] = "Login=" + login
        elif ab == "[common]" and re.match(r"^\s*Server\s*=", z, re.I): zs[i] = "Server=" + server
        elif ab == "[experts]" and re.match(r"^\s*Enabled\s*=", z, re.I): zs[i] = "Enabled=1"
    st = os.stat(INI); tmp = INI + ".neu109"
    with open(tmp, "wb") as f:
        f.write((("\r\n" if crlf else "\n").join(zs)).encode(k)); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, INI)

def logtreffer(konto):
    return sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
              "[ -n \"$L\" ] && grep -ac \"" + konto + "\" \"$L\" || echo 0", t=40).strip()

if not os.path.exists(INI):
    melde("ABBRUCH: common.ini fehlt"); raise SystemExit(0)

sh("cp -p '" + INI + "' '" + INI + ".bak_109'")
vor = logtreffer(TEST_LOGIN)
melde("Treffer fuer Testkonto vor dem Versuch: " + vor)

try:
    setze(TEST_LOGIN, TEST_SERVER)
    melde("common.ini auf " + TEST_SERVER + " / ***" + TEST_LOGIN[-3:] + " gesetzt")
except Exception as e:
    melde("ABBRUCH beim Schreiben: " + str(e)); raise SystemExit(0)

melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))

nach = vor
for _ in range(30):
    time.sleep(5)
    nach = logtreffer(TEST_LOGIN)
    try:
        if int(nach) > int(vor): break
    except Exception: pass

erfolg = False
try:
    erfolg = int(nach) > int(vor)
except Exception:
    pass

if erfolg:
    melde("ERGEBNIS: Kontowechsel FUNKTIONIERT (" + vor + " -> " + nach + " Zeilen)")
    melde("Belege: " + sh(
        "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
        "grep -a \"" + TEST_LOGIN + "\" \"$L\" | tail -3 | sed -E 's/[0-9]{6,}/***/g'", t=40))
else:
    melde("ERGEBNIS: Kontowechsel bewirkt NICHTS (" + vor + " -> " + nach + ")")

# In jedem Fall zurueck auf Demo
try:
    setze(DEMO_LOGIN, DEMO_SERVER)
    melde("zurueck auf Demo gesetzt")
except Exception as e:
    melde("Ruecksetzen fehlgeschlagen: " + str(e))
    sh("cp -p '" + INI + ".bak_109' '" + INI + "'")
melde("Neustart zurueck: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
time.sleep(25)
melde("Terminal: " + (sh("pgrep -f '[t]erminal64' | head -1") or "LAEUFT NICHT"))
melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1", t=30))
print("Patch 109 fertig")
