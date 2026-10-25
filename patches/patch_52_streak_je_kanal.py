#!/usr/bin/env python3
# Patch 52 - Code + .env, idempotent.
#
#   Beim Prüfen von Patch 49 im Log aufgefallen: LOSE_STREAK_LIMIT=0.
#   Der Code prueft "if _streak_lim > 0 and ...", der Lose-Streak-Schutz
#   ist also komplett abgeschaltet, fuer jeden Kanal. Patch 49 hat zwar die
#   GTMO-Ausnahme entfernt, das lief aber ins Leere, weil die Bremse selbst
#   nicht scharf ist.
#
#   Der Grenzwert wird global gelesen, es gibt ihn bisher nicht je Kanal.
#   Fuer den Hauptkanal will ich daran nichts aendern, der laeuft seit acht
#   Handelstagen so. Fuer einen neuen, ungeprueften Kanal auf kleinem
#   Risiko ist die Bremse dagegen genau richtig.
#
#   Neu: der Grenzwert wird ueber _env_for_channel aufgeloest, also je
#   Kanaltitel ueberschreibbar, mit dem globalen Wert als Rueckfallebene.
#       LOSE_STREAK_LIMIT          = 0   (unveraendert, Hauptkanal)
#       LOSE_STREAK_LIMIT_GOLD     = 3
#       LOSE_STREAK_LIMIT_TRADER   = 3
#       LOSE_STREAK_LIMIT_GTMO     = 3
#       LOSE_STREAK_LIMIT_GTMOFX   = 3
#   Kanaltitel laut Log: "Gold Trader Mo🤴🏽(Gtmofx)" -> Token
#   ['gold','trader','gtmofx'], erster Treffer "gold" -> Grenzwert 3.
#   Nach drei Stops in Folge pausiert der Kanal LOSE_STREAK_PAUSE_MIN
#   Minuten. Der Hauptkanal bleibt davon unberuehrt.
import shutil, py_compile, sys, os
from datetime import datetime, timezone

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "PATCH52" in src:
    print("Code schon angewendet")
else:
    shutil.copyfile(F, F + ".bak_52")
    A_OLD = '''        _streak_lim = int(float(os.getenv("LOSE_STREAK_LIMIT", "3")))
'''
    A_NEW = '''        # PATCH52: je Kanal ueberschreibbar, global als Rueckfallebene.
        _streak_lim = int(float(_env_for_channel(
            "LOSE_STREAK_LIMIT", sig.source_channel, "3")))
'''
    if src.count(A_OLD) != 1:
        print("FEHLER Anker:", src.count(A_OLD)); sys.exit(1)
    src = src.replace(A_OLD, A_NEW)
    open(F, "w", encoding="utf-8").write(src)
    py_compile.compile(F, doraise=True)
    print("Patch 52 Code OK - Lose-Streak-Grenzwert je Kanal")

ENV, LOG = ".env", "bot.log"
SOLL = {"LOSE_STREAK_LIMIT_GOLD": "3",
        "LOSE_STREAK_LIMIT_TRADER": "3",
        "LOSE_STREAK_LIMIT_GTMO": "3",
        "LOSE_STREAK_LIMIT_GTMOFX": "3",
        "LOSE_STREAK_PAUSE_MIN": "60"}
ZEIGEN = ["TARGET_RISK_PCT", "TARGET_RISK_PCT_XAUUSD", "TARGET_RISK_PCT_GOLD",
          "MAX_LAYERS_XAUUSD", "MAX_LAYERS_GOLD", "LOSE_STREAK_LIMIT",
          "LOSE_STREAK_LIMIT_GOLD", "LOSE_STREAK_PAUSE_MIN",
          "LOSE_STREAK_GILT_AUCH_GTMO", "PARTIAL_GEWICHTE"]

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
    shutil.copyfile(ENV, ENV + ".bak_52")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("env geaendert: " + " | ".join(gesetzt))
else:
    print("env: nichts zu tun")
akt = {}
for z in open(ENV, encoding="utf-8").read().splitlines():
    s = z.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1); akt[k.strip()] = v.strip()
log("geaendert: " + (" | ".join(gesetzt) if gesetzt else "nichts"))
log("Stand: " + " ".join(k + "=" + akt[k] for k in ZEIGEN if k in akt))
