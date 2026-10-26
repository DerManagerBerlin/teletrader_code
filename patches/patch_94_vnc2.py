#!/usr/bin/env python3
# Patch 94 - VNC neu starten, diesmal brauchbar.
#
#   Fehler in Patch 93: "-once" beendet den Server, sobald der erste
#   Client die Verbindung wieder loest. Alex' erster Versuch hat damit die
#   einzige Sitzung verbraucht, danach lief nichts mehr und er sah nur
#   eine Zeitueberschreitung.
#
#   Jetzt: -forever, damit mehrere Versuche moeglich sind, aber das Ganze
#   unter "timeout 1800". Nach 30 Minuten ist der Zugang zu, ohne dass
#   jemand daran denken muss. Ein dauerhaft offener Bildschirm auf einem
#   Rechner mit Handelskonto bleibt ausgeschlossen.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH94 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=25):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Zeitlimit/Fehler: " + str(e)[:80]

melde("vorher laufend: " + (sh("pgrep -a x11vnc | grep -v grep | head -1") or "nein"))

# Alte Instanz sauber beenden, falls eine haengt. Keine Mustersuche auf der
# eigenen Kommandozeile, deshalb pgrep auf den Programmnamen.
alt = sh("pgrep -x x11vnc | head -3").replace(" | ", " ")
for pid in alt.split():
    if pid.isdigit():
        sh("kill " + pid + " 2>/dev/null; echo ok")
        melde("alte Instanz " + pid + " beendet")
time.sleep(1)

sh("cd " + HOME + " && DISPLAY=:99 nohup timeout 1800 x11vnc -display :99 "
   "-nopw -forever -quiet -rfbport 5902 >> " + HOME + "/x11vnc.log 2>&1 & disown",
   t=8)
time.sleep(4)

melde("Prozess: " + (sh("pgrep -a x11vnc | grep -v grep | head -1") or "LAEUFT NICHT"))
melde("Port 5902: " + (sh("ss -tln 2>/dev/null | grep -c 5902") or "0") + " Listener")
melde("lokal erreichbar: " + sh(
    "timeout 5 bash -c 'echo > /dev/tcp/127.0.0.1/5902' 2>&1 && echo JA || echo NEIN"))
melde("laeuft bis: " + sh("date -u -d '+30 minutes' '+%H:%M UTC'"))
melde("Log: " + sh("tail -2 " + HOME + "/x11vnc.log 2>/dev/null"))
print("Patch 94 fertig")
