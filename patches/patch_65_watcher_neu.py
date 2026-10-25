#!/usr/bin/env python3
# Patch 65 - minimal. Startet nur den Watcher neu.
#
#   Beobachtung: Ctrl+E hat genau einmal gewirkt, naemlich unmittelbar
#   nachdem der algoenabler-Prozess neu gestartet war (23:00:41). Danach
#   laeuft der Checker des Bots alle 84 Sekunden ins Leere.
#   Der Watcher scheint nach laengerer Laufzeit keine wirksame Verbindung
#   zum X-Server mehr zu haben.
#
#   Dieser Patch tut genau eine Sache: den Watcher beenden, damit systemd
#   ihn frisch startet. KEINE Flagdatei, keine .env, kein Code. Den
#   Tastendruck loest der Bot selbst aus, der fragt ohnehin alle 84
#   Sekunden an. Ein zusaetzlicher Druck von mir wuerde nur wieder
#   zurueckschalten, genau das ist mir bei Patch 64 passiert.
import subprocess
from datetime import datetime, timezone

def log(t):
    try:
        with open("bot.log", "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH watcher: " + t + "\n")
    except Exception:
        pass

def sh(cmd, timeout=20):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

def melde(t):
    print(t); log(t)

pid = sh("systemctl show -p MainPID --value algoenabler.service 2>/dev/null").strip()
if pid.isdigit() and int(pid) > 1:
    melde("Watcher PID " + pid + " wird beendet, systemd startet ihn neu")
    melde(sh("kill " + pid + " && echo ok || echo Fehler"))
else:
    melde("keine MainPID gefunden: " + repr(pid))
melde("Laufzeit vorher: " + sh(
    "systemctl show -p ActiveEnterTimestamp --value algoenabler.service 2>/dev/null"))
print("Patch 65 fertig - kein Tastendruck ausgeloest, das macht der Bot")
