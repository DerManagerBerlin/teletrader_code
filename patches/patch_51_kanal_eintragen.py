#!/usr/bin/env python3
# Patch 51 - .env, idempotent. Aendert KEINEN Code.
#
# (A) Kanal eintragen. Der Code loest Benutzernamen direkt ueber
#     get_entity() auf, die numerische ID ist also nicht noetig. Sie steht
#     auch nirgends, wo ich sie finden koennte: .env war nie im Mirror, und
#     in der Loghistorie stehen nur Titel ("GTMO VIP"), keine IDs.
#         TG_CHANNEL_3 = Gold_trader_mo_Goldtradermofx
#     Slot 3 war leer, 1 und 2 bleiben unberuehrt (XAUUSD und BTC SCALPING).
#
# (B) Das eigentliche Risiko an der Sache. Die Zuordnung des Zielrisikos
#     laeuft ueber Woerter im Kanaltitel. Patch 50 deckt GTMO, GOLD,
#     TRADER, GOLDTRADER ab. Heisst der Kanal aber zum Beispiel
#     "FREE SIGNALS" oder "MO FX", trifft keines dieser Token, und der
#     Kanal faellt auf das globale TARGET_RISK_PCT zurueck. Das steht auf
#     0.038, also fast dem Vierfachen des gewollten Risikos.
#     Dasselbe gilt fuer BTC SCALPING, der mitlaeuft und bisher kein
#     einziges Signal geschickt hat: kommt dort eines, handelt der Bot es
#     mit vollen 3,8%.
#
#     Neu umgedreht: das hohe Risiko bekommt nur noch der Kanal, der es
#     haben soll, und der globale Wert wird zum vorsichtigen Standard.
#         TARGET_RISK_PCT_XAUUSD = 0.038   (Hauptkanal, Token "xauusd")
#         TARGET_RISK_PCT_BTC    = 0.010
#         TARGET_RISK_PCT        = 0.010   (war 0.038)
#     Aufloesung in Wortreihenfolge, erster Treffer gewinnt:
#         "XAUUSD SCALPING"  -> ['xauusd','scalping'] -> 0.038
#         "BTC SCALPING"     -> ['btc','scalping']    -> 0.010
#         "GTMO VIP"         -> ['gtmo','vip']        -> 0.010
#         alles andere       -> global                -> 0.010
#     Ein unbekannter Kanal kann damit nicht mehr versehentlich mit vollem
#     Risiko handeln. Sollte der Hauptkanal seinen Titel aendern, faellt er
#     auf 1% statt auf 3,8% - das ist die richtige Richtung.
#
#     Zurueckdrehen: TARGET_RISK_PCT=0.038, TG_CHANNEL_3= (leer).

import os, shutil
from datetime import datetime, timezone

ENV, LOG = ".env", "bot.log"
KANAL = "Gold_trader_mo_Goldtradermofx"
SOLL = {"TARGET_RISK_PCT_XAUUSD": "0.038",
        "TARGET_RISK_PCT_BTC": "0.010",
        "TARGET_RISK_PCT": "0.010"}
ZEIGEN = ["TARGET_RISK_PCT", "TARGET_RISK_PCT_XAUUSD", "TARGET_RISK_PCT_BTC",
          "TARGET_RISK_PCT_GTMO", "TARGET_RISK_PCT_GOLD", "TARGET_RISK_PCT_TRADER",
          "MAX_LAYERS_XAUUSD", "MAX_LAYERS_GTMO", "MAX_LAYERS_GOLD",
          "LAYERS_FIT_RISK", "PARTIAL_GEWICHTE", "LOSE_STREAK_LIMIT",
          "LOSE_STREAK_GILT_AUCH_GTMO"]

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
alt = {}
for z in zeilen:
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); alt[k.strip()] = v.strip()

# ── (A) freien Slot suchen, aber nur wenn der Kanal noch nirgends steht ──
gesetzt = []
slot = None
if any((alt.get("TG_CHANNEL_" + str(i), "") or "").strip().lower() == KANAL.lower()
       for i in range(1, 6)):
    print("Kanal steht schon in einem Slot")
else:
    for i in range(1, 6):
        if not (alt.get("TG_CHANNEL_" + str(i), "") or "").strip():
            slot = i
            break
    if slot is None:
        print("WARNUNG: kein freier TG_CHANNEL-Slot, Kanal nicht eingetragen")

neu = []
for z in zeilen:
    s = z.strip(); fertig = False
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); k, v = k.strip(), v.strip()
        if slot is not None and k == "TG_CHANNEL_" + str(slot):
            neu.append(k + "=" + KANAL)
            gesetzt.append(k + ": (leer) -> " + KANAL)
            fertig = True
        elif k in SOLL:
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
if slot is not None and ("TG_CHANNEL_" + str(slot)) not in alt:
    neu.append("TG_CHANNEL_" + str(slot) + "=" + KANAL)
    gesetzt.append("TG_CHANNEL_" + str(slot) + ": (fehlte) -> " + KANAL)

if gesetzt:
    shutil.copyfile(ENV, ENV + ".bak_51")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("geaendert: " + " | ".join(gesetzt))
else:
    print("nichts zu tun")

akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
_slots = ["TG_CHANNEL_" + str(i) + "=" + (akt.get("TG_CHANNEL_" + str(i), "") or "(leer)")
          for i in range(1, 6)]
print("Kanal-Slots: " + " | ".join(_slots))
log("Kanal-Slots: " + " | ".join(_slots))
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
