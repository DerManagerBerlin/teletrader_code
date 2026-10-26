#!/usr/bin/env python3
# Patch 93 - VNC-Zugang fuer eine einzelne Sitzung oeffnen.
#
#   Alex muss sich einmal von Hand im MT5-Terminal am Ultima-Konto
#   anmelden, damit das Passwort dort gespeichert wird. Dafuer braucht er
#   Sicht auf Display :99. x11vnc laeuft nicht als Dienst und ist nach
#   jeder Sitzung weg.
#
#   Bewusst NICHT wie frueher mit "-forever": Der Server beendet sich,
#   sobald die Sitzung endet, und auch dann, wenn innerhalb von 10 Minuten
#   niemand kommt. Ein dauerhaft offener Bildschirm auf einem Rechner mit
#   Handelskonto ist das Risiko nicht wert.
#
#   Ein Passwort waere besser, scheidet hier aber aus: Es muesste ueber
#   status.txt zu Alex, und die Datei landet in einem oeffentlichen Repo.
#   Deshalb der enge Zeitrahmen statt eines Geheimnisses im Klartext.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH93 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=40):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Fehler: " + str(e)

melde("x11vnc vorhanden: " + (sh("command -v x11vnc") or "NEIN"))
laeuft = sh("pgrep -a x11vnc | grep -v grep | head -2")
melde("laeuft schon: " + (laeuft or "nein"))

if not laeuft:
    # -once statt -forever: beendet sich nach der Sitzung
    # -timeout 600: beendet sich, wenn in 10 Minuten niemand verbindet
    melde("starte: " + sh(
        "cd " + HOME + " && DISPLAY=:99 nohup x11vnc -display :99 -nopw -once "
        "-timeout 600 -quiet -rfbport 5902 >> " + HOME + "/x11vnc.log 2>&1 & "
        "disown; sleep 2; echo gestartet"))
    time.sleep(2)

melde("Prozess: " + (sh("pgrep -a x11vnc | grep -v grep | head -1") or "LAEUFT NICHT"))
melde("Port 5902: " + (sh("ss -tln 2>/dev/null | grep 5902 | head -2") or "KEIN LISTEN"))
melde("Log: " + sh("tail -3 " + HOME + "/x11vnc.log 2>/dev/null"))
print("Patch 93 fertig")
