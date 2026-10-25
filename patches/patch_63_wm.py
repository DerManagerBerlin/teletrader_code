#!/usr/bin/env python3
# Patch 63 - Window-Manager auf :99 starten.
#
#   Patch 62 hat alle drei Zustellwege durchprobiert, das Journal zeigt
#   "Ctrl+E an WID 10485761 gesendet (Methode 0, direkt an WID)" und
#   AutoTrading bleibt aus. Wine nimmt synthetische Tastenereignisse nicht
#   an, und ohne Window-Manager bekommt das Fenster keinen echten Fokus,
#   also greift auch der XTEST-Weg nicht.
#
#   Dieser Patch startet einen Window-Manager auf :99, falls keiner laeuft.
#   Danach funktionieren windowactivate und Fokus normal, und der
#   bestehende Watcher kann seine Taste zustellen.
#   Installieren kann ich nichts, dafuer fehlt sudo. Es wird nur gestartet,
#   was schon da ist.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
FLAG = "ENABLE_ALGO_REQUEST"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH wm: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=25):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

melde("WM vorhanden? " + sh(
    "DISPLAY=:99 xprop -root _NET_SUPPORTING_WM_CHECK 2>&1 | head -1"))
melde("laufende WM-Prozesse: " + (sh(
    "pgrep -a -f 'openbox|fluxbox|matchbox|icewm|jwm|marco|xfwm|mutter|twm' "
    "| grep -v 'bash -lc' | head -3") or "(keine)"))

KANDIDATEN = ["openbox", "matchbox-window-manager", "fluxbox", "icewm",
              "jwm", "blackbox", "twm", "mutter", "xfwm4", "marco"]
gefunden = []
for k in KANDIDATEN:
    p = sh("command -v " + k + " 2>/dev/null")
    if p and not p.startswith("Fehler"):
        gefunden.append((k, p))
melde("installierte WM: " + (", ".join(k for k, _ in gefunden) or "KEINER"))

wm_da = "_NET_SUPPORTING_WM_CHECK(WINDOW)" in sh(
    "DISPLAY=:99 xprop -root _NET_SUPPORTING_WM_CHECK 2>&1 | head -1")

if wm_da:
    melde("Ein Window-Manager laeuft bereits, nichts zu starten.")
elif not gefunden:
    melde("Kein Window-Manager installiert. Ohne sudo kann ich keinen "
          "nachinstallieren. Naechster Weg waere, AutoTrading ueber die "
          "MT5-Konfigurationsdatei plus Terminal-Neustart zu setzen.")
else:
    name, pfad = gefunden[0]
    args = "--sm-disable" if name == "openbox" else ""
    melde("starte " + name + " auf :99")
    sh("cd " + TT + " && DISPLAY=:99 nohup " + pfad + " " + args +
       " >> wm.log 2>&1 & disown; sleep 1; echo gestartet", timeout=20)
    time.sleep(4)
    neu = sh("DISPLAY=:99 xprop -root _NET_SUPPORTING_WM_CHECK 2>&1 | head -1")
    melde("WM danach: " + neu)
    if "_NET_SUPPORTING_WM_CHECK(WINDOW)" not in neu:
        melde("WM ist nicht hochgekommen, siehe " + TT + "/wm.log: " +
              sh("tail -3 " + TT + "/wm.log 2>/dev/null").replace("\n", " | ")[:200])

# Methode auf windowactivate stellen und Anforderung ausloesen
try:
    with open(os.path.join(TT, ".algo_methode"), "w", encoding="utf-8") as f:
        f.write("2\n")
except Exception:
    pass
try:
    with open(os.path.join(TT, FLAG), "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat() + "\n")
    melde("Anforderung gestellt (Methode 2, windowactivate)")
except Exception as e:
    melde("Flag-Fehler: " + str(e))

time.sleep(8)
melde("Journal: " + sh("journalctl -u algoenabler.service -n 2 --no-pager 2>/dev/null "
                       "| tail -2").replace("\n", " | ")[:280])
melde("Aktives Fenster: " + sh(
    "DISPLAY=:99 xdotool getactivewindow getwindowname 2>&1 | head -1"))
print("Patch 63 fertig")
