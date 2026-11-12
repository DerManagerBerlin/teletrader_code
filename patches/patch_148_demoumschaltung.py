#!/usr/bin/env python3
# patch_148_demoumschaltung.py
#
# Umschaltung auf das neue Demokonto bei Ultima Markets, 1000 EUR.
# Zurueck auf die urspruengliche Bauweise, weil der Kontostand es wieder
# hergibt. Die Kleinkonto-Kruecken von Patch 118 werden zurueckgenommen:
#
#   MAX_LAYERS            1 -> 4   (2x TP1, 1x TP2, 1 Runner)
#   MAX_POS_PER_SYMBOL    1 -> 6   sonst blockieren sich die Layer selbst
#   MAX_RISK_PCT       0.10 -> 0.05  die 10 % waren nur fuer 57 EUR noetig
#
# Auch die kanalspezifischen Varianten werden mitgezogen, die schlagen
# sonst die Grundwerte. Zielrisiko, Bremsen, Symbolschleuse und die
# Runner-Leine aus Patch 115 bleiben unveraendert.
#
# Zurueck auf Live heisst: DEMO_MODE=false UND MAX_RISK_PCT wieder hoch,
# sonst handelt ein kleines Livekonto gar nicht mehr.
import io, os, re, stat, sys

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
ENV = os.path.join(TT, ".env")
PUB = os.path.join(HOME, "ttpub")
if not os.path.exists(ENV):
    ENV = ".env"
    TT = "."
_z = []


def sag(t):
    t = str(t)
    print("PATCH148 " + t)
    _z.append(t)


SOLL = {
    "DEMO_MODE": "true",
    "MAX_LAYERS": "4",
    "MAX_POS_PER_SYMBOL": "6",
    "MAX_RISK_PCT": "0.05",
}
PRAEFIX = {"MAX_LAYERS_": "4", "MAX_RISK_PCT_": "0.05"}

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
    zeilen.append("# PATCH148 Demokonto Ultima, 1000 EUR")
    for k in fehlt:
        zeilen.append(k + "=" + SOLL[k])
        gesetzt.append(k)

neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nichts geaendert")
    sys.exit(1)
fd = os.open(ENV + ".bak148", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
fd = os.open(ENV + ".p148", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    os.chmod(ENV + ".p148", stat.S_IMODE(os.stat(ENV).st_mode))
except Exception:
    pass
os.replace(ENV + ".p148", ENV)
sag("env gesetzt: " + " ".join(sorted(set(gesetzt))))

# Messlatte der Bremsen zuruecksetzen, sonst vergleicht sie 1000 gegen 0.01
_b = os.path.join(TT, "bremse.json")
if os.path.exists(_b):
    try:
        os.remove(_b)
        sag("bremse.json geloescht, Messlatte setzt auf dem Demokonto neu auf")
    except Exception as e:
        sag("bremse.json: " + str(e))
else:
    sag("bremse.json war nicht da")

_f = os.path.join(TT, "TRADING_PAUSED")
if os.path.exists(_f):
    try:
        os.remove(_f)
        sag("Handelssperre aufgehoben")
    except Exception as e:
        sag("Sperre: " + str(e))

sag("fertig, der Neustart verbindet auf das Demokonto")
try:
    os.makedirs(PUB, exist_ok=True)
    with io.open(os.path.join(PUB, "status.txt"), "a", encoding="utf-8") as f:
        for x in _z:
            f.write("UMSCHALT148 " + x + "\n")
except Exception:
    pass
