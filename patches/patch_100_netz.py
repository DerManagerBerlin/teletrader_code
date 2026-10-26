#!/usr/bin/env python3
# Patch 100 - warum kommt VNC nicht an? Drei Annahmen pruefen.
#
#   Bisher vorausgesetzt, nie geprueft:
#     a) Die externe IP ist noch 34.159.42.212 (aus dem August).
#     b) Auf dem Server selbst blockt keine Firewall.
#     c) x11vnc laeuft zum Zeitpunkt des Versuchs wirklich noch.
#   Dazu: wo liegt ttpull.sh wirklich (Patch 98 fand sie nicht).
#
#   Danach wird VNC verzoegert neu gestartet, damit es den Neustart
#   ueberlebt, den dieser Patch ausloest.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")
HELFER = os.path.join(HOME, "vnc_login.sh")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH100 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=30):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:260]
    except Exception as e:
        return "Zeitlimit: " + str(e)[:60]

# a) Externe IP direkt vom Metadatendienst der Google Cloud
MD = ("curl -s --max-time 8 -H 'Metadata-Flavor: Google' "
      "http://169.254.169.254/computeMetadata/v1/instance/")
melde("externe IP: " + (sh(MD + "network-interfaces/0/access-configs/0/external-ip")
                        or "(nicht abrufbar)"))
melde("interne IP: " + (sh(MD + "network-interfaces/0/ip") or "?"))
melde("Instanz: " + (sh(MD + "name") or "?") + " / Zone: " +
      (sh(MD + "zone").split("/")[-1] if sh(MD + "zone") else "?"))

# b) Firewall auf dem Server selbst
melde("ufw: " + (sh("command -v ufw >/dev/null && ufw status 2>/dev/null | head -3 "
                    "|| echo '(ufw nicht installiert)'")))
melde("nft/iptables: " + (sh("(command -v nft >/dev/null && nft list ruleset 2>/dev/null "
                             "| head -5) || (iptables -S 2>/dev/null | head -5) "
                             "|| echo '(nicht lesbar ohne root)')")))

# c) Laeuft x11vnc jetzt?
melde("x11vnc: " + (sh("pgrep -a x11vnc | grep -v grep | head -1") or "LAEUFT NICHT"))
melde("Listener 5902: " + (sh("ss -tln 2>/dev/null | grep 5902") or "KEINER"))
melde("x11vnc.log: " + sh("tail -3 " + HOME + "/x11vnc.log 2>/dev/null"))

# d) Wo liegt ttpull.sh?
melde("ttpull.sh: " + (sh("find $HOME -maxdepth 3 -name 'ttpull.sh' "
                          "-printf '%p ' 2>/dev/null") or "(nicht gefunden)"))
melde("crontab: " + sh("crontab -l 2>/dev/null | grep -vE '^\\s*#' | head -6"))

# VNC verzoegert neu starten (der Neustart durch diesen Patch kommt zuerst)
if os.path.exists(HELFER):
    sh("setsid nohup '" + HELFER + "' >/dev/null 2>&1 < /dev/null & disown; echo ab", t=8)
    melde("VNC-Helfer erneut gestartet, Fenster in rund 3 Minuten")
else:
    melde("VNC-Helfer fehlt: " + HELFER)
print("Patch 100 fertig")
