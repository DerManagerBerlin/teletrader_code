#!/usr/bin/env python3
# Patch 29 - .env, idempotent. Aendert KEINEN Code.
#   LADDER_MAX_STAGE -> 1
#   Die Leiter zieht den Stop nur noch bei TP1 auf Break-Even und hoert
#   dann auf. Danach fuehrt der Trailing Stop. Grund: der Signalgeber
#   meldet in einem Monat 93x "SL auf Entry (BE)" und kein einziges Mal
#   ein Nachziehen auf TP1/TP2. Unsere Leiter parkte den Stop 30-40 Pips
#   hinter dem Kurs und wurde dort vom naechsten Ruecksetzer geholt.
# Zurueck: LADDER_MAX_STAGE=0 in der .env setzen und Bot neu starten.
import os, shutil
from datetime import datetime, timezone

ENV, LOG = ".env", "bot.log"
SOLL = {"LADDER_MAX_STAGE": "1"}
ZEIGEN = ["TARGET_RISK_PCT", "MAX_TOTAL_HEAT_PCT", "RUNNER_ONLY", "PARTIAL_AT_TP",
          "LADDER_START_STAGE", "LADDER_MAX_STAGE", "ZONE_STAFFELN",
          "TRAILING_STOP_PIPS", "TRAILING_STOP_MIN_PROFIT_PIPS"]

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH env: " + t + "\n")
    except Exception:
        pass

if not os.path.exists(ENV):
    print("FEHLER: .env nicht gefunden"); raise SystemExit(1)

zeilen = open(ENV, encoding="utf-8").read().splitlines()
alt, neu, gesetzt = {}, [], []
for z in zeilen:
    s = z.strip(); fertig = False
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); k, v = k.strip(), v.strip()
        alt[k] = v
        if k in SOLL:
            if v != SOLL[k]:
                neu.append(k + "=" + SOLL[k]); gesetzt.append(k + ": " + v + " -> " + SOLL[k])
            else:
                neu.append(z)
            fertig = True
    if not fertig:
        neu.append(z)
for k, v in SOLL.items():
    if k not in alt:
        neu.append(k + "=" + v); gesetzt.append(k + ": (fehlte) -> " + v)

if gesetzt:
    shutil.copyfile(ENV, ENV + ".bak_29")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("nichts zu tun, Wert steht bereits")

akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
