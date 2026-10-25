#!/usr/bin/env python3
# Patch 57 - NOTFALL. Holt den Bot zurueck auf Demo.
#
#   Nach /live um 22:50 kamen keine Heartbeats mehr. Der Prozess ist also
#   nach dem Neustart nicht wieder hochgekommen, vermutlich weil
#   connect_mt5() im Live-Modus scheitert und main() dann zurueckkehrt.
#   Damit nimmt der Bot auch keine Telegram-Befehle mehr entgegen, /demo
#   kann niemand mehr lesen. Der Patch-Kanal laeuft per Cron und ist davon
#   unabhaengig, deshalb geht es hierueber.
#
#   Setzt DEMO_MODE=true und loescht den Fehlversuchszaehler aus Patch 56.
#   ttpull startet den Dienst danach ohnehin neu.
#   Aendert sonst nichts, insbesondere bleiben die LIVE_-Zugangsdaten
#   unberuehrt.
import os, shutil
from datetime import datetime, timezone

ENV, LOG = ".env", "bot.log"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH env: " + t + "\n")
    except Exception:
        pass

if not os.path.exists(ENV):
    print("FEHLER: .env fehlt"); raise SystemExit(1)

zeilen = open(ENV, encoding="utf-8").read().splitlines()
neu = []; gesetzt = []
for z in zeilen:
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); k, v = k.strip(), v.strip()
        if k == "DEMO_MODE":
            if v.lower() != "true":
                neu.append("DEMO_MODE=true"); gesetzt.append("DEMO_MODE: " + v + " -> true")
            else:
                neu.append(z)
            continue
    neu.append(z)
if not any(l.strip().startswith("DEMO_MODE=") for l in neu):
    neu.append("DEMO_MODE=true"); gesetzt.append("DEMO_MODE: (fehlte) -> true")

if gesetzt:
    shutil.copyfile(ENV, ENV + ".bak_57")
    with open(ENV + ".tmp_57", "w", encoding="utf-8") as f:
        f.write("\n".join(neu) + "\n")
    os.chmod(ENV + ".tmp_57", 0o600)
    os.replace(ENV + ".tmp_57", ENV)
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("DEMO_MODE stand schon auf true")

for _f in ("LOGIN_FAILS",):
    if os.path.exists(_f):
        try:
            os.remove(_f); print("geloescht: " + _f)
        except Exception as _e:
            print("konnte " + _f + " nicht loeschen: " + str(_e))

akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
print("Stand: DEMO_MODE=" + akt.get("DEMO_MODE", "?") +
      " DEMO_MT5_LOGIN=" + akt.get("DEMO_MT5_LOGIN", "?") +
      " DEMO_MT5_SERVER=" + akt.get("DEMO_MT5_SERVER", "?") +
      " LIVE_MT5_LOGIN=" + akt.get("LIVE_MT5_LOGIN", "?") +
      " LIVE_MT5_SERVER=" + akt.get("LIVE_MT5_SERVER", "?"))
log("Patch 57 NOTFALL: zurueck auf DEMO_MODE=" + akt.get("DEMO_MODE", "?"))
