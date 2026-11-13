#!/usr/bin/env python3
# patch_151_leiter.py
#
# Die volle Layer-Leiter wieder herstellen. Gestern kam trotz MAX_LAYERS=4
# immer nur ein Layer zustande. Ursache war nicht die Verteilung, sondern
# die Lotgroesse: calculate_layers rechnet LOT_PER_100 * (Balance/100), bei
# 1000 EUR also 0.05 je Layer. Vier davon sind bei 80 Pips Stop rund 144 EUR
# Risiko, also 14,5 %. Der Deckel von 5 % hat daraufhin auf einen Layer
# zurueckgeschnitten. Im Log steht beides direkt untereinander:
#   Layer-Verteilung: 4 Layer = 2x TP1, 1x TP2 + 1 Runner
#   Layer-Verteilung: 1 Layer, alle ohne festes Ziel
#
# Richtig herum: ein Layer zu 0.01 Lot kostet bei 80 Pips 7,23 EUR, der
# Deckel von 50 EUR traegt also sechs davon. Sechs ist genau die volle
# Leiter: 2x TP1, je 1x TP2/TP3/TP4, 1 Runner.
#
#   LOT_PER_100   -> 0.001   ergibt 0.01 Lot je Layer bei 1000 Balance
#   MAX_LAYERS    -> 6       inklusive der kanalspezifischen Varianten
#   MAX_RISK_PCT  bleibt 0.05
#
# Damit wird bei TP1 abgesichert, ohne den Runner aufzugeben.
import io, os, re, stat, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
ENV = os.path.join(TT, ".env")
PUB = os.path.join(HOME, "ttpub")
if not os.path.exists(ENV):
    ENV = ".env"
_z = []


def sag(t):
    t = str(t)
    print("PATCH151 " + t)
    _z.append(t)


SOLL = {"LOT_PER_100": "0.001", "MAX_LAYERS": "6", "MAX_RISK_PCT": "0.05",
        "PARTIAL_GEWICHTE": "2,1,1,1", "RUNNER_ONLY": "true"}
PRAEFIX = {"MAX_LAYERS_": "6", "MAX_RISK_PCT_": "0.05", "LOT_PER_100_": "0.001"}

alt = io.open(ENV, encoding="utf-8", errors="surrogateescape").read()
zeilen = alt.split("\n")


def key(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (key(z) for z in zeilen) if k)
gesetzt = []
for i, z in enumerate(zeilen):
    k = key(z)
    if not k:
        continue
    if k in SOLL:
        zeilen[i] = k + "=" + SOLL[k]
        gesetzt.append(k)
        continue
    for p, v in PRAEFIX.items():
        if k.startswith(p) and k != p.rstrip("_"):
            zeilen[i] = k + "=" + v
            gesetzt.append(k)
            break
fehlt = [k for k in SOLL if k not in gesetzt]
if fehlt:
    if zeilen and zeilen[-1].strip() != "":
        zeilen.append("")
    zeilen.append("# PATCH151 volle Layer-Leiter")
    for k in fehlt:
        zeilen.append(k + "=" + SOLL[k])
        gesetzt.append(k)

neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nichts geaendert")
    sys.exit(1)
fd = os.open(ENV + ".bak151", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
fd = os.open(ENV + ".p151", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    os.chmod(ENV + ".p151", stat.S_IMODE(os.stat(ENV).st_mode))
except Exception:
    pass
os.replace(ENV + ".p151", ENV)
sag("env gesetzt: " + " ".join(sorted(set(gesetzt))))
sag("erwartet: 6 Layer a 0.01 Lot = 43,40 EUR Risiko bei 80 Pips Stop")
sag("Verteilung 2x TP1, 1x TP2, 1x TP3, 1x TP4, 1 Runner")
sag("fertig")
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("LEITER151 " + x + "\n")
except Exception:
    pass
