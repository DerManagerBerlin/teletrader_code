#!/usr/bin/env python3
# Patch 60 - repariert die Algo-Trading-Reaktivierung.
#
#   Lage: der Bot laeuft wieder auf Demo, aber das Terminal hat AutoTrading
#   aus. Jede Orderaenderung scheitert mit
#       retcode=10027  comment='AutoTrading disabled by client'
#   Die SL-Leiter versucht es alle 3 Sekunden fuer zwei Tickets erneut und
#   flutet dabei das Log.
#
#   Der Bot kann das nicht selbst loesen: er laeuft unter Wine und bekommt
#   bei jedem Aufruf eines Linux-Programms WinError 2. Deshalb gibt es
#   algoenabler.service, einen nativen Linux-Watcher, der auf die Flagdatei
#   ENABLE_ALGO_REQUEST wartet und dann per xdotool Ctrl+E auf das
#   MT5-Fenster schickt. Dieser Watcher antwortet seit heute Abend nicht
#   mehr, vermutlich weil er die vielen Terminal-Neustarts nicht ueberlebt
#   hat oder sein Fenster-Handle veraltet ist.
#
#   Dieser Patch laeuft ueber ttpull und damit nativ unter Linux, kann also
#   genau das tun, was dem Bot verwehrt ist:
#     1. Zustand protokollieren: Dienst, xdotool, DISPLAY, Fensterliste,
#        Alter der Flagdatei.
#     2. algoenabler.service neu starten, erst mit sudo, sonst als
#        Benutzerdienst.
#     3. Die Flagdatei neu schreiben, damit der Watcher sofort etwas zu tun
#        hat.
#
#   Bewusst NICHT: ein blindes Ctrl+E von hier aus. Die Tastenkombination
#   schaltet um. Ohne den Zustand von trade_allowed zu kennen, den nur die
#   MT5-Anbindung unter Wine liefert, koennte ich AutoTrading damit
#   ausschalten statt ein. Die Entscheidung bleibt beim Watcher, der den
#   Zustand kennt.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
FLAG = "ENABLE_ALGO_REQUEST"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH algo: " + t + "\n")
    except Exception:
        pass

def sh(cmd, timeout=15):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.returncode * 0 * "" + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

def melde(label, text):
    for zeile in (text.splitlines() or ["(leer)"]):
        s = label + ": " + zeile[:200]
        print(s); log(s)

# ── 1. Zustand ──────────────────────────────────────────────────────────
melde("Dienst", sh("systemctl is-active algoenabler.service 2>&1; "
                   "systemctl --user is-active algoenabler.service 2>&1"))
melde("Unit", sh("systemctl list-units --all --no-pager --no-legend 2>/dev/null "
                 "| grep -i algo | head -3; "
                 "systemctl --user list-units --all --no-pager --no-legend 2>/dev/null "
                 "| grep -i algo | head -3"))
melde("xdotool", sh("command -v xdotool || echo NICHT_INSTALLIERT"))
melde("DISPLAY", sh("echo DISPLAY=${DISPLAY:-leer}; "
                    "ls /tmp/.X11-unix/ 2>/dev/null | head -4"))
melde("Terminal", sh("pgrep -af terminal64 | head -2"))
melde("Fenster", sh("for d in :0 :1 :99; do "
                    "n=$(DISPLAY=$d xdotool search --name 'MetaTrader\\|MT5' 2>/dev/null | head -2); "
                    "[ -n \"$n\" ] && echo \"$d -> $n\"; done; echo fertig"))

if os.path.exists(FLAG):
    try:
        alter = int(time.time() - os.path.getmtime(FLAG))
        melde("Flag", FLAG + " vorhanden, " + str(alter) + "s alt "
              "(unbearbeitet = Watcher reagiert nicht)")
    except Exception:
        pass
else:
    melde("Flag", FLAG + " nicht vorhanden")

# ── 2. Watcher neu starten ──────────────────────────────────────────────
r = sh("sudo -n systemctl restart algoenabler.service 2>&1 && echo SYSTEM_OK")
if "SYSTEM_OK" in r:
    melde("Neustart", "algoenabler.service per sudo neu gestartet")
else:
    r2 = sh("systemctl --no-ask-password --user restart algoenabler.service 2>&1 "
            "&& echo USER_OK")
    if "USER_OK" in r2:
        melde("Neustart", "algoenabler.service als Benutzerdienst neu gestartet")
    else:
        melde("Neustart", "FEHLGESCHLAGEN sudo: " + r[:120])
        melde("Neustart", "FEHLGESCHLAGEN user: " + r2[:120])

# ── 3. Anforderung neu stellen ──────────────────────────────────────────
try:
    with open(FLAG, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat() + "\n")
    melde("Flag", "neu geschrieben, Watcher sollte jetzt Ctrl+E schicken")
except Exception as e:
    melde("Flag", "konnte nicht geschrieben werden: " + str(e))

time.sleep(8)
melde("Flag", (FLAG + " noch da (Watcher hat NICHT reagiert)")
      if os.path.exists(FLAG) else (FLAG + " abgeraeumt - Watcher laeuft"))
melde("Dienst", sh("systemctl is-active algoenabler.service 2>&1; "
                   "systemctl --user is-active algoenabler.service 2>&1"))
print("Patch 60 fertig")
