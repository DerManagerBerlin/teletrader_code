#!/usr/bin/env python3
# Patch 28 - .env, idempotent. Aendert KEINEN Code.
#   LADDER_MAX_STAGE -> 1   (Leiter nur bis BE, danach fuehrt der Trail)
# Schreibt den Stand der risikorelevanten Schluessel ins bot.log.
# Zugangsdaten werden weder gelesen noch ausgegeben.
import os, shutil
from datetime import datetime, timezone

ENV = ".env"
LOG = "bot.log"
SOLL = {
    "TARGET_RISK_PCT":    "0.02",
    "LADDER_START_STAGE": "1",
    "PARTIAL_AT_TP":      "1",
}
ZEIGEN = ["TARGET_RISK_PCT", "MAX_TOTAL_HEAT_PCT", "MAX_RISK_PCT_SCALPING",
          "MAX_LAYERS", "MAX_LAYERS_XAUUSD", "RUNNER_ONLY", "PARTIAL_AT_TP",
          "ZONE_STAFFELN", "LADDER_START_STAGE", "LADDER_MAX_STAGE",
          "TRAILING_STOP_PIPS", "TRAILING_STOP_MIN_PROFIT_PIPS"]

def log(txt):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH env: " + txt + "\n")
    except Exception:
        pass

if not os.path.exists(ENV):
    print("FEHLER: .env nicht gefunden"); raise SystemExit(1)

zeilen = open(ENV, encoding="utf-8").read().splitlines()
alt, neu_zeilen, gesetzt = {}, [], []

for z in zeilen:
    s = z.strip()
    ersetzt = False
    if s and not s.startswith("#") and "=" in s:
        k = s.split("=", 1)[0].strip()
        v = s.split("=", 1)[1].strip()
        alt[k] = v
        if k in SOLL:
            if v != SOLL[k]:
                neu_zeilen.append(k + "=" + SOLL[k])
                gesetzt.append(k + ": " + v + " -> " + SOLL[k])
            else:
                neu_zeilen.append(z)
            ersetzt = True
    if not ersetzt:
        neu_zeilen.append(z)

for k, v in SOLL.items():
    if k not in alt:
        neu_zeilen.append(k + "=" + v)
        gesetzt.append(k + ": (fehlte) -> " + v)

if gesetzt:
    shutil.copyfile(ENV, ENV + ".bak_28")
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(neu_zeilen) + "\n")
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("nichts zu tun, Werte stehen bereits")

stand = open(ENV, encoding="utf-8").read().splitlines()
akt = {}
for z in stand:
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        akt[s.split("=", 1)[0].strip()] = s.split("=", 1)[1].strip()
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
