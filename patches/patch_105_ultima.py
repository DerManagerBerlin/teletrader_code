#!/usr/bin/env python3
# NO_RESTART
# Patch 105 - Terminal einmalig am Ultima-Konto anmelden.
#
#   Ablauf: Konfigurationsdatei aus der .env erzeugen, Terminal beenden,
#   der Watchdog startet es mit dieser Datei neu, MT5 meldet sich selbst
#   an. Danach wird die Datei geloescht.
#
#   Das Passwort wird gelesen, in eine Datei mit Rechten 0600 geschrieben
#   und nie ausgegeben. Es steht weder in diesem Skript noch in einer
#   Meldung. Die Datei liegt nur Sekunden auf der Platte.
#
#   Die .env bleibt in diesem Patch auf DEMO. Erst wenn das Terminal
#   nachweislich am Livekonto haengt, wird umgeschaltet.
import os, re, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
ENV = os.path.join(TT, ".env")
INI = os.path.join(TT, "ultima_start.ini")
FLAG = os.path.join(TT, ".mt5_start_cfg")
WINPFAD = "Z:\\home\\alexander_lacher\\teletrader\\ultima_start.ini"
MT5DIR = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                      "PU Prime MT5 Terminal")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH105 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=60):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

def aufraeumen():
    for p in (INI, FLAG):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

login = passwort = server = ""
try:
    with open(ENV, encoding="utf-8") as f:
        for z in f:
            s = z.strip()
            if s.startswith("LIVE_MT5_LOGIN="):    login = s.split("=", 1)[1].strip()
            elif s.startswith("LIVE_MT5_PASSWORD="): passwort = s.split("=", 1)[1].strip()
            elif s.startswith("LIVE_MT5_SERVER="):   server = s.split("=", 1)[1].strip()
except Exception as e:
    melde("ABBRUCH: .env nicht lesbar: " + str(e)); raise SystemExit(0)

if not (login.isdigit() and passwort and server):
    melde("ABBRUCH: Zugangsdaten unvollstaendig"); raise SystemExit(0)
melde("Ziel: Konto ***" + login[-3:] + " @ " + server + ", Passwort vorhanden")

INHALT = ("[Common]\n"
          "Login=" + login + "\n"
          "Password=" + passwort + "\n"
          "Server=" + server + "\n"
          "AutoConfiguration=false\n"
          "[Experts]\n"
          "AllowLiveTrading=1\n"
          "Enabled=1\n")

def schreibe(kodierung):
    aufraeumen()
    fd = os.open(INI, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(INHALT.encode(kodierung))
    fd2 = os.open(FLAG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd2, "wb") as f:
        f.write((WINPFAD + "\n").encode("utf-8"))

def terminal_neu():
    pid = sh("pgrep -f '[t]erminal64' | head -1").strip()
    if pid.isdigit():
        sh("kill " + pid + " 2>/dev/null; echo ok")
        melde("Terminal " + pid + " beendet, Watchdog startet es neu")
    else:
        melde("kein Terminal gefunden")

def angemeldet():
    """Steht im Terminal-Log eine Anmeldung auf dem Livekonto?"""
    return sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
              "[ -n \"$L\" ] && grep -ic \"'" + login + "'\" \"$L\" || echo 0").strip()

for kod, name in (("utf-8", "UTF-8"), ("utf-16-le", "UTF-16")):
    melde("Versuch mit " + name + "-Konfiguration")
    try:
        schreibe(kod)
    except Exception as e:
        melde("Datei nicht schreibbar: " + str(e)); continue
    terminal_neu()
    treffer = "0"
    for _ in range(24):          # bis 120 s
        time.sleep(5)
        treffer = angemeldet()
        if treffer.isdigit() and int(treffer) > 0:
            break
    aufraeumen()
    if treffer.isdigit() and int(treffer) > 0:
        melde("TREFFER: Terminal-Log nennt das Livekonto (" + treffer + " Zeilen)")
        melde("Belege: " + sh(
            "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
            "grep -i \"'" + login + "'\" \"$L\" | tail -3 | "
            "sed -E 's/[0-9]{6,}/***/g'"))
        break
    melde("keine Anmeldung sichtbar nach " + name)
else:
    melde("Beide Kodierungen ohne Erfolg")

aufraeumen()
melde("Konfigurationsdatei geloescht: " + str(not os.path.exists(INI)))
melde("Terminal laeuft: " + (sh("pgrep -f '[t]erminal64' | head -1") or "NEIN"))
melde("letzte Terminal-Zeilen: " + sh(
    "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
    "[ -n \"$L\" ] && tail -6 \"$L\" | grep -viE 'pass' | "
    "sed -E 's/[0-9]{6,}/***/g' | tr '\\n' '|' || echo '(kein Log)'"))
print("Patch 105 fertig")
