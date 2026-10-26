#!/usr/bin/env python3
# Patch 88 - reine Lesung: Laufen mehrere Bot-Prozesse?
#
#   Befund: bot.log wandert rueckwaerts. Die letzte LIVECHECK-Zeile ist
#   wieder von 15:17, obwohl es spaetere gab. Das passiert, wenn zwei
#   Prozesse dieselbe Datei mit eigenen Schreibpositionen offen halten:
#   der aeltere ueberschreibt mit seinem Puffer das Neuere.
#
#   Zwei gleichzeitig laufende Bots wuerden auch doppelt handeln. Deshalb
#   zuerst nachsehen, nichts beenden.
import os, subprocess
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
LOG = os.path.join(TT, "bot.log")
STATUS = os.path.join(HOME, "ttpub", "status.txt")

def melde(t):
    zeile = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH88 " + t
    print(zeile)
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

melde("=== Prozesse ===")
for z in sh("ps -eo pid,lstart,etimes,args | grep -i '[t]eletrader_v2' "
            "| head -8").splitlines():
    melde("PS " + z[:190])

melde("Anzahl Bot-Prozesse: " + sh(
    "ps -eo args | grep -c '[t]eletrader_v2\\.py'"))
melde("terminal64: " + sh("ps -eo pid,etimes,args | grep -m2 '[t]erminal64' "
                          "| head -2").replace("\n", " | ")[:200])
melde("Xvfb: " + sh("ps -eo pid,etimes,args | grep -m1 '[X]vfb'")[:150])
melde("watchdog: " + sh("ps -eo pid,etimes,args | grep '[w]atchdog.sh' "
                        "| head -3").replace("\n", " | ")[:200])

melde("=== bot.log ===")
melde("Groesse/Zeit: " + sh("ls -l --time-style=+%H:%M:%S '" + LOG + "' 2>/dev/null"))
melde("letzte Zeitmarke: " + sh(
    "grep -oE '^2026-[0-9-]+ [0-9:]+' '" + LOG + "' 2>/dev/null | tail -1"))
melde("offene Schreiber: " + (sh(
    "command -v lsof >/dev/null && lsof '" + LOG + "' 2>/dev/null | tail -5 "
    "|| echo '(lsof fehlt)'").replace("\n", " | "))[:250])
melde("Prozesse mit bot.log offen: " + (sh(
    "for p in $(ls /proc | grep -E '^[0-9]+$'); do "
    "ls -l /proc/$p/fd 2>/dev/null | grep -q 'bot\\.log' && "
    "echo -n \"$p($(tr '\\0' ' ' < /proc/$p/cmdline 2>/dev/null | cut -c1-40)) \"; "
    "done; echo") or "(keine)")[:300])

melde("=== systemd ===")
melde("teletrader: " + sh("systemctl show -p MainPID -p NRestarts -p ActiveState "
                          "--value teletrader.service 2>/dev/null").replace("\n", " | "))
melde("Dienst seit: " + sh("systemctl show -p ActiveEnterTimestamp --value "
                           "teletrader.service 2>/dev/null"))
print("Patch 88 fertig")
