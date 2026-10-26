#!/usr/bin/env python3
# NO_RESTART
# Patch 107 - Ultima-Anmeldung, zweiter Anlauf, sauber.
#
#   Fehler in Patch 105: Ich habe terminal64 einzeln beendet und darauf
#   gesetzt, dass der Watchdog schnell genug nachzieht. Tat er nicht, am
#   Ende lief gar kein Terminal mehr und der zweite Durchgang lief ins
#   Leere. Der Test war kaputt, nicht zwingend die Methode.
#
#   Diesmal: Konfiguration schreiben, dann den DIENST neu starten. Der
#   Watchdog startet das Terminal dabei garantiert und liest die Datei.
#   Erst danach wird geprueft. Scheitert es, wird aufgeraeumt und noch
#   einmal normal gestartet, damit auf keinen Fall ein totes Terminal
#   zurueckbleibt.
#
#   Das Passwort wird nie ausgegeben, die Datei hat Rechte 0600 und wird
#   in jedem Fall geloescht.
import os, subprocess, time
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
MARKE = os.path.join(TT, ".patch107_laeuft")
UNIT = "teletrader.service"

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH107 " + t
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

if os.path.exists(MARKE):
    try: alt = time.time() - os.path.getmtime(MARKE)
    except Exception: alt = 0
    if alt < 900:
        melde("laeuft bereits"); raise SystemExit(0)
try: open(MARKE, "w").write("x")
except Exception: pass

def weg():
    for p in (INI, FLAG):
        try:
            if os.path.exists(p): os.remove(p)
        except Exception: pass

def terminal_da():
    return bool(sh("pgrep -f '[t]erminal64' | head -1", t=20).strip())

def warte_terminal(sek):
    ende = time.time() + sek
    while time.time() < ende:
        time.sleep(5)
        if terminal_da():
            return True
    return False

login = passwort = server = ""
try:
    with open(ENV, encoding="utf-8") as f:
        for z in f:
            s = z.strip()
            if s.startswith("LIVE_MT5_LOGIN="):      login = s.split("=", 1)[1].strip()
            elif s.startswith("LIVE_MT5_PASSWORD="): passwort = s.split("=", 1)[1].strip()
            elif s.startswith("LIVE_MT5_SERVER="):   server = s.split("=", 1)[1].strip()
except Exception as e:
    melde("ABBRUCH: .env nicht lesbar"); weg(); raise SystemExit(0)

if not (login.isdigit() and passwort and server):
    melde("ABBRUCH: Zugangsdaten unvollstaendig"); weg(); raise SystemExit(0)

melde("Vorbedingung Terminal laeuft: " + ("ja" if terminal_da() else "NEIN"))

INHALT = ("[Common]\n"
          "Login=" + login + "\n"
          "Password=" + passwort + "\n"
          "Server=" + server + "\n"
          "AutoConfiguration=false\n"
          "[Experts]\n"
          "AllowLiveTrading=1\n"
          "Enabled=1\n")
try:
    weg()
    fd = os.open(INI, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(INHALT.encode("utf-8"))
    fd = os.open(FLAG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write((WINPFAD + "\n").encode("utf-8"))
    melde("Konfiguration geschrieben (0600)")
except Exception as e:
    melde("ABBRUCH: nicht schreibbar: " + str(e)); weg(); raise SystemExit(0)

melde("Dienstneustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
melde("Terminal wieder oben: " + ("ja" if warte_terminal(180) else "NEIN"))

treffer = "0"
for _ in range(30):            # bis 150 s
    time.sleep(5)
    treffer = sh("L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
                 "[ -n \"$L\" ] && grep -ac 'ultima' \"$L\" || echo 0", t=30).strip()
    if treffer.isdigit() and int(treffer) > 0:
        break

weg()
melde("Konfigurationsdatei geloescht: " + str(not os.path.exists(INI)))

if treffer.isdigit() and int(treffer) > 0:
    melde("ULTIMA IM TERMINAL-LOG (" + treffer + " Zeilen)")
    melde("Belege: " + sh(
        "L=$(ls -t '" + MT5DIR + "'/logs/*.log 2>/dev/null | head -1); "
        "grep -ai 'ultima' \"$L\" | tail -4 | sed -E 's/[0-9]{6,}/***/g'", t=40))
else:
    melde("keine Spur von Ultima im Terminal-Log")

if not terminal_da():
    melde("Terminal fehlt - noch ein Neustart zur Sicherheit")
    melde(sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))
    melde("danach: " + ("laeuft" if warte_terminal(150) else "LAEUFT NICHT"))

melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1", t=30))
try: os.remove(MARKE)
except Exception: pass
print("Patch 107 fertig")
