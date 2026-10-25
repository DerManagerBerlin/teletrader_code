#!/usr/bin/env python3
# Patch 50 - .env, idempotent. Aendert KEINEN Code.
#
#   Patch 49 hat TARGET_RISK_PCT_GTMO=0.010 gesetzt. Das greift aber nur,
#   wenn der KANALTITEL das Wort "gtmo" enthaelt. Der Titel kommt aus
#   Telegram (entity.title), nicht aus dem Benutzernamen, und die Suche
#   zerlegt ihn in Woerter ab drei Buchstaben:
#       "GOLD TRADER MO"      -> ['gold', 'trader']        kein Treffer
#       "GOLDTRADER MO FX"    -> ['goldtrader']            kein Treffer
#       "GTMo Free Signals"   -> ['gtmo', ...]             Treffer
#   Bei den ersten beiden Schreibweisen waere der Kanal still auf das
#   globale TARGET_RISK_PCT von 0.038 zurueckgefallen, also fast das
#   Vierfache des gewollten Risikos. Genau das soll nicht passieren.
#
#   Neu: dieselben Werte zusaetzlich unter allen plausiblen Token des
#   Kanals. _env_for_channel nimmt den ersten Treffer in Wortreihenfolge,
#   damit ist jede Schreibweise abgedeckt.
#
#   Keine Nebenwirkung auf den Hauptkanal: "XAUUSD SCALPING" zerlegt sich
#   in ['xauusd', 'scalping'] und trifft keines dieser Token.
#   Wenn spaeter ein weiterer Kanal mit "gold" oder "trader" im Titel
#   dazukommt, erbt er die 1% - das ist die vorsichtige Richtung.
#
#   Kanal-Benutzername laut QR-Code: Gold_trader_mo_Goldtradermofx
#   Eintragen von Hand in den ersten freien TG_CHANNEL_n Slot.

import os, shutil
from datetime import datetime, timezone

ENV, LOG = ".env", "bot.log"
_TOK = ["GTMO", "GOLDTRADER", "GOLDTRADERMOFX", "GOLD", "TRADER"]
SOLL = {}
for _t in _TOK:
    SOLL["TARGET_RISK_PCT_" + _t] = "0.010"
    SOLL["MAX_LAYERS_" + _t] = "2"
ZEIGEN = ["TARGET_RISK_PCT", "TARGET_RISK_PCT_GTMO", "TARGET_RISK_PCT_GOLD",
          "TARGET_RISK_PCT_TRADER", "TARGET_RISK_PCT_GOLDTRADER",
          "MAX_LAYERS_XAUUSD", "MAX_LAYERS_GTMO", "MAX_LAYERS_GOLD",
          "LAYERS_FIT_RISK", "PARTIAL_GEWICHTE", "LOSE_STREAK_LIMIT",
          "LOSE_STREAK_GILT_AUCH_GTMO", "REGEX_ONLY_CHANNELS"]

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
    shutil.copyfile(ENV, ENV + ".bak_50")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("nichts zu tun")

akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
_slots = []
for i in range(1, 6):
    _v = akt.get("TG_CHANNEL_" + str(i), "")
    _slots.append("TG_CHANNEL_" + str(i) + "=" + (_v if _v else "(leer)"))
print("Kanal-Slots: " + " | ".join(_slots))
log("Kanal-Slots: " + " | ".join(_slots))
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
