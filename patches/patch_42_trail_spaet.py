#!/usr/bin/env python3
# Patch 42 - .env, idempotent. Aendert KEINEN Code.
#   TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD -> 100  (war 30)
#
# Grund: der Trail steht mit 30 Pips mitten im Rauschen. Gemessen am
# 22.10., drei Mal dasselbe Muster:
#   02:55 SELL  Hoch 54p, 30p Ruecksetzer holt uns bei +21  -> Kanal +460
#   09:30 SELL  Hoch 98p, 30p Ruecksetzer holt uns bei +66  -> Kanal +260
#   13:25 SELL  Hoch 57p, 30p Ruecksetzer holt uns bei +25  -> Kanal +310
# In allen drei Faellen meldete der Kanal KEIN "BE HIT", der Kurs kam also
# nie zum Entry zurueck. Ein Stop auf Entry haette alle drei gehalten, der
# 30er-Trail hat alle drei zerschnitten.
#
# Neu: die Runner bleiben nach TP1 auf Entry (BE) stehen und werden erst
# ab +100 Pips getrailt, dann mit der dynamischen Breite aus Patch 40.
# Damit liegt der Stop waehrend der verwundbaren Phase nicht im Rauschen.
#
# Preis dafuer: bei Signalen, die zum Entry zuruecklaufen, geben die Runner
# ihren Gewinn ab statt 10 bis 48 Pips mitzunehmen. Das sind 46% der
# Signale (21 von 46 seit dem 19.10.). Dagegen stehen 33% Laeufer, die im
# Schnitt 84 statt 37 Pips bringen.
# Erwartung je Runner: +13 statt +6 Pips, je Layer +15 statt +9.
# Hoehere Streuung, mehr Nullrunden, dickerer Tail.
#
# Zurueckdrehen: TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD=30
# BTC bleibt unangetastet.

import os, shutil
from datetime import datetime, timezone
ENV, LOG = ".env", "bot.log"
SOLL = {"TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD": "100"}
ZEIGEN = ["TARGET_RISK_PCT","MAX_LAYERS_XAUUSD","PARTIAL_LADDER","LAYERS_FIT_RISK",
          "LADDER_START_STAGE","LADDER_MAX_STAGE","PARTIAL_AT_TP",
          "TRAILING_STOP_PIPS_XAUUSD","TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD",
          "TRAIL_GIVEBACK_PCT","TRAIL_MAX_PIPS","SCALP_ENTRY_MAX_PIPS_XAUUSD",
          "SL_DIST_VOM_MARKT","MESSE_RUECKSETZER"]

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH env: " + t + "\n")
    except Exception:
        pass

if not os.path.exists(ENV):
    print("FEHLER: .env fehlt"); raise SystemExit(1)

neu = []; alt = {}; gesetzt = []
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip(); fertig = False
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); k, v = k.strip(), v.strip(); alt[k] = v
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
    shutil.copyfile(ENV, ENV + ".bak_42")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("nichts zu tun")

akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
