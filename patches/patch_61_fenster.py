#!/usr/bin/env python3
# Patch 61 - Diagnose. Aendert nichts.
#
#   Aus Patch 60: algoenabler.service ist AKTIV und raeumt die Flagdatei ab,
#   der Watcher laeuft also. AutoTrading bleibt trotzdem aus. Das Ctrl+E
#   kommt demnach nicht am richtigen Fenster an.
#   Dazu zwei Spuren:
#     - Das Display ist :99 (/tmp/.X11-unix/X99), nicht :0.
#     - Meine Fenstersuche in Patch 60 fand nichts, aber das Muster war
#       falsch: xdotool nutzt erweiterte regulaere Ausdruecke, dort ist die
#       Alternative "|" und nicht "\|". Ich habe also nach dem Literal
#       gesucht. Eigener Fehler, deshalb hier nochmal sauber.
#   MT5-Fenstertitel enthalten die Kontonummer. Nach dem Hin und Her
#   zwischen 700190957 und 34706330 kann der Titel ein anderer sein als
#   der, auf den der Watcher wartet.
#
#   Dieser Patch listet alle Fenster auf :99 mit Titel und zeigt, wonach
#   der Watcher sucht.
import subprocess
from datetime import datetime, timezone

LOG = "bot.log"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH fenster: " + t + "\n")
    except Exception:
        pass

def sh(cmd, timeout=20):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

def melde(label, text, maxz=14):
    for i, zeile in enumerate((text.splitlines() or ["(leer)"])):
        if i >= maxz:
            print(label + ": ..."); log(label + ": ...")
            break
        s = label + ": " + zeile[:200]
        print(s); log(s)

melde("Displays", sh("ls /tmp/.X11-unix/ 2>/dev/null"))
melde("Fenster99", sh(
    "for w in $(DISPLAY=:99 xdotool search --name '.' 2>/dev/null); do "
    "t=$(DISPLAY=:99 xdotool getwindowname $w 2>/dev/null); "
    "[ -n \"$t\" ] && echo \"$w  $t\"; done | head -14"))
melde("Sichtbar99", sh(
    "DISPLAY=:99 xdotool search --onlyvisible --name '.' 2>/dev/null | wc -l"))
melde("Aktiv99", sh("DISPLAY=:99 xdotool getactivewindow getwindowname 2>&1 | head -2"))
melde("Unit", sh("systemctl cat algoenabler.service 2>/dev/null | head -20"))
melde("Skript", sh(
    "f=$(systemctl cat algoenabler.service 2>/dev/null "
    "| grep -oP 'ExecStart=.*?\\K(/\\S+\\.(sh|py))' | head -1); "
    "echo \"Datei: ${f:-unbekannt}\"; "
    "[ -n \"$f\" ] && [ -r \"$f\" ] && grep -nE 'xdotool|search|DISPLAY|name|key' \"$f\" | head -12"))
melde("Journal", sh("journalctl -u algoenabler.service -n 12 --no-pager 2>/dev/null "
                    "| tail -12"))
print("Patch 61 fertig")
