#!/usr/bin/env python3
# Patch 49 - Code + .env, idempotent.
#
# (A) GTMO umgeht den Lose-Streak-Schutz. Im Code steht fest verdrahtet:
#         _is_gtmo = "gtmo" oder "goldtrader" im Kanalnamen
#         if (_streak_lim > 0 and not _is_gtmo and ...)
#     Nach drei Stops in Folge pausiert also jeder Kanal ausser GTMO. Das
#     stammt aus der Zeit, als GTMO VIP der Hauptkanal war. Fuer einen
#     zweiten Kanal auf kleinem Risiko ist genau dieser Schutz sinnvoll.
#     Neu: LOSE_STREAK_GILT_AUCH_GTMO=true schaltet den Schutz auch fuer
#     GTMO ein. Mit false bleibt das alte Verhalten.
#
# (B) Parameter fuer GTMO auf kleinem Risiko. Die Aufloesung laeuft ueber
#     _env_for_channel: jedes Wort des Kanalnamens ab drei Buchstaben wird
#     als Token geprueft, "GTMO Free Signals" trifft also TARGET_RISK_PCT_GTMO.
#         TARGET_RISK_PCT_GTMO = 0.010   (statt 0.038 im Hauptkanal)
#         MAX_LAYERS_GTMO      = 2
#     Bei 952 Euro Konto sind 1% rund 9,50 Euro. Bei 8 Punkten Stop reicht
#     das fuer eine Einheit, LAYERS_FIT_RISK kuerzt also auf 1 Layer plus
#     Runner, sobald das Budget mehr hergibt.
#
# (C) Die konfigurierten Kanalnamen werden beim Start geloggt, damit
#     sichtbar ist, welche TG_CHANNEL-Slots belegt sind. Keine Tokens,
#     keine Zugangsdaten, nur die Kanalnamen.
#
# NICHT in diesem Patch: der Kanal selbst. TG_CHANNEL_1..5 muss den
# Benutzernamen oder Titel des Kanals enthalten, und der Telethon-Account
# muss Mitglied sein. Das kann nur von Hand gesetzt werden.
import shutil, py_compile, sys, os
from datetime import datetime, timezone

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "LOSE_STREAK_GILT_AUCH_GTMO" in src:
    print("Code schon angewendet")
else:
    shutil.copyfile(F, F + ".bak_49")

    # ── (A) Streak-Schutz auch fuer GTMO erlauben ────────────────────────
    A_OLD = '''    _is_gtmo = any(k in sig.source_channel.lower()
                   for k in ("gtmo", "goldtrader"))
'''
    A_NEW = '''    _is_gtmo = any(k in sig.source_channel.lower()
                   for k in ("gtmo", "goldtrader"))
    # PATCH49: Der Streak-Schutz war fuer GTMO fest abgeschaltet. Fuer einen
    # Zweitkanal auf kleinem Risiko ist er gerade dort sinnvoll.
    if os.getenv("LOSE_STREAK_GILT_AUCH_GTMO", "true").lower() == "true":
        _is_gtmo = False
'''
    if src.count(A_OLD) != 1:
        print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)
    src = src.replace(A_OLD, A_NEW)

    # ── (C) Konfigurierte Kanalnamen loggen ──────────────────────────────
    C_OLD = '''    print(f"{Fore.GREEN}✅ Bereit – überwache {len(channel_entities)} Kanäle{Style.RESET_ALL}\\n")
'''
    C_NEW = '''    print(f"{Fore.GREEN}✅ Bereit – überwache {len(channel_entities)} Kanäle{Style.RESET_ALL}\\n")
    try:   # PATCH49: sichtbar machen, welche Slots belegt sind
        _slots = [(i + 1, (c or "").strip()) for i, c in enumerate(TG_CHANNELS)]
        log.info("Kanal-Slots: " + " | ".join(
            "TG_CHANNEL_" + str(i) + "=" + (c if c else "(leer)")
            for i, c in _slots))
        log.info("Aufgeloeste Kanaele: " + ", ".join(
            str(getattr(e, "title", None) or getattr(e, "username", None) or "?")
            for e in channel_entities))
    except Exception:
        pass
'''
    if src.count(C_OLD) != 1:
        print("FEHLER Anker C:", src.count(C_OLD)); sys.exit(1)
    src = src.replace(C_OLD, C_NEW)

    open(F, "w", encoding="utf-8").write(src)
    py_compile.compile(F, doraise=True)
    print("Patch 49 Code OK - Streak-Schutz fuer GTMO, Kanal-Slots werden geloggt")

# ── .env ────────────────────────────────────────────────────────────────
ENV, LOG = ".env", "bot.log"
SOLL = {"TARGET_RISK_PCT_GTMO": "0.010",
        "MAX_LAYERS_GTMO": "2",
        "LOSE_STREAK_GILT_AUCH_GTMO": "true"}
ZEIGEN = ["TARGET_RISK_PCT", "TARGET_RISK_PCT_GTMO", "MAX_LAYERS_XAUUSD",
          "MAX_LAYERS_GTMO", "LAYERS_FIT_RISK", "PARTIAL_GEWICHTE",
          "LOSE_STREAK_LIMIT", "LOSE_STREAK_PAUSE_MIN",
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
    shutil.copyfile(ENV, ENV + ".bak_49")
    open(ENV, "w", encoding="utf-8").write("\n".join(neu) + "\n")
    print("env geaendert: " + " | ".join(gesetzt))
else:
    print("env: nichts zu tun")

# Belegte Kanal-Slots melden (nur Namen, keine Zugangsdaten)
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
