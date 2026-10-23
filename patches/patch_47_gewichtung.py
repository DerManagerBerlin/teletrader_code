#!/usr/bin/env python3
# Patch 47 - idempotent. Code + .env.
#
# (A) Fehler in Patch 43. Die Sperre lautet "_reached <= _eig", blockiert die
#     Leiter also fuer einen Layer mit hartem TP bei seiner eigenen UND bei
#     allen niedrigeren Stufen. Richtig ist nur die eigene und hoeher: ein
#     Layer mit Ziel TP3 soll bei TP1 ruhig auf Entry gezogen werden, das
#     steht seinem Ziel nicht im Weg. Nur beim eigenen Ziel gibt es den
#     Wettlauf zwischen BE-Stop und eigenem TP.
#     Ohne diese Korrektur verliert jeder TP2/TP3/TP4-Layer seinen
#     BE-Schutz, und das kostet nach den gemessenen Wahrscheinlichkeiten:
#       harter TP2  ohne BE  +9.5 Pips   mit BE  +29.8 Pips
#       harter TP3  ohne BE -12.2 Pips   mit BE  +25.8 Pips
#       harter TP4  ohne BE -14.9 Pips   mit BE  +28.5 Pips
#     Relevant wird das erst mit (B), deshalb beides in einem Patch.
#
# (B) Gewichtete Layer-Verteilung. PARTIAL_GEWICHTE="2,1,1,1" bedeutet:
#     2 Einheiten auf TP1, dann je 1 auf TP2, TP3, TP4, und der Rest laeuft
#     als Runner. Es bleibt IMMER mindestens ein Runner uebrig, und die
#     hinteren Ziele fallen weg, wenn das Risikobudget nicht reicht.
#     Zwei Einheiten auf TP1 sind dasselbe wie 0.02 Lot, nur ueber die
#     bestehende Mengenlogik, also ohne Eingriff in die Orderroutine.
#     Bei 4 Layern: 2x TP1 + 1x TP2 + 1 Runner.
#     Bei 3 Layern: 2x TP1 + 1 Runner.
#     Bei 6 Layern: 2x TP1 + TP2 + TP3 + TP4 + 1 Runner.
#
#     Grundlage, 59 Signale ab 19.10., Erwartungswert je 80 Pips Risiko:
#       harter TP1   +21 Pips     (81% Trefferquote)
#       harter TP2   +23 Pips     (56%)
#       harter TP3   +16 Pips     (34%)
#       harter TP4   +15 Pips     (27%)
#       Runner        +5 Pips     (gemessen seit Patch 42)
#     Die Ziele sind untereinander fast gleich gut, Wahrscheinlichkeit und
#     Auszahlung heben sich auf. Der Unterschied liegt zwischen harten
#     Zielen und Runnern, Faktor vier. Deshalb Gewicht auf die Ziele und
#     nur noch ein Runner fuer den Tail.
#     Erwartung je Signal bei 4 Layern: +67 statt +36 Pips.
#     Zurueckdrehen: PARTIAL_GEWICHTE= (leer) -> wieder PARTIAL_AT_TP.
import shutil, py_compile, sys, os
from datetime import datetime, timezone

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "PARTIAL_GEWICHTE" in src:
    print("Code schon angewendet")
else:
    shutil.copyfile(F, F + ".bak_47")

    # ── (A) Sperre nur ab der eigenen Stufe ──────────────────────────────
    A_OLD = '                        if _eig and _reached <= _eig:\n'
    A_NEW = '                        if _eig and _reached >= _eig:\n'
    if src.count(A_OLD) != 1:
        print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)
    src = src.replace(A_OLD, A_NEW)

    # ── (B) Gewichtete Verteilung, vor PARTIAL_LADDER ────────────────────
    B_OLD = '''        if (os.getenv("PARTIAL_LADDER", "true").lower() == "true"
                and num_tps > 0 and num_layers >= 2):
'''
    B_NEW = '''        # PATCH47: gewichtete Verteilung. "2,1,1,1" = 2 Einheiten auf TP1,
        # je 1 auf TP2/TP3/TP4, Rest Runner. Mindestens 1 Runner bleibt.
        _gw = (os.getenv("PARTIAL_GEWICHTE", "") or "").strip()
        if _gw and num_tps > 0 and num_layers >= 2:
            _ws = []
            try:
                _ws = [int(float(x)) for x in _gw.replace(";", ",").split(",")
                       if x.strip()]
            except Exception:
                _ws = []
            if _ws and any(w > 0 for w in _ws):
                _v = {}
                _frei = num_layers - 1          # ein Layer bleibt fuer den Runner
                _txt = []
                for _i, _w in enumerate(_ws):
                    if _i >= num_tps or _frei <= 0:
                        break
                    _take = min(max(0, _w), _frei)
                    if _take <= 0:
                        continue
                    _v[tps[_i]] = _v.get(tps[_i], 0) + _take
                    _frei -= _take
                    _txt.append(str(_take) + "x TP" + str(_i + 1) +
                                " (" + str(tps[_i]) + ")")
                _rest = num_layers - sum(_v.values())
                if _rest < 1:                   # Sicherung: Runner nie opfern
                    _k = sorted(_v.keys())[-1]
                    _v[_k] -= 1
                    if _v[_k] <= 0:
                        _v.pop(_k, None)
                    _rest = num_layers - sum(_v.values())
                _v[0] = _rest
                log.info("Layer-Verteilung: " + str(num_layers) + " Layer = " +
                         ", ".join(_txt) + " + " + str(_rest) +
                         " Runner (PARTIAL_GEWICHTE " + _gw + ")")
                return _v
        if (os.getenv("PARTIAL_LADDER", "true").lower() == "true"
                and num_tps > 0 and num_layers >= 2):
'''
    if src.count(B_OLD) != 1:
        print("FEHLER Anker B:", src.count(B_OLD)); sys.exit(1)
    src = src.replace(B_OLD, B_NEW)

    open(F, "w", encoding="utf-8").write(src)
    py_compile.compile(F, doraise=True)
    print("Patch 47 Code OK - Leitersperre korrigiert, Gewichtung eingebaut")

# ── .env ────────────────────────────────────────────────────────────────
ENV, LOG = ".env", "bot.log"
SOLL = {"PARTIAL_GEWICHTE": "2,1,1,1"}
ZEIGEN = ["TARGET_RISK_PCT", "MAX_LAYERS_XAUUSD", "LAYERS_FIT_RISK",
          "PARTIAL_GEWICHTE", "PARTIAL_LADDER", "PARTIAL_AT_TP",
          "LADDER_START_STAGE", "LADDER_MAX_STAGE",
          "TRAILING_STOP_PIPS_XAUUSD", "TRAILING_STOP_MIN_PROFIT_PIPS_XAUUSD",
          "TRAIL_GIVEBACK_PCT", "TP_AUS_MELDUNG", "LEITER_SCHONT_TP_LAYER",
          "NACHHOLEN", "SL_DIST_VOM_MARKT"]

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
    shutil.copyfile(ENV, ENV + ".bak_47")
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
