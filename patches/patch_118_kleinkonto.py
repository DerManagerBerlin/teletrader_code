#!/usr/bin/env python3
# patch_118_kleinkonto.py
#
# Stellt den Bot auf das 100-EUR-Konto um:
#   1. Symbolschleuse NUR_SYMBOLE im Code (Gold durch, alles andere raus).
#   2. .env auf 1 Layer, 1 Position pro Symbol, Bremsen scharf.
#
# Rechnung dahinter: Gold min 0.01 Lot = 0,10 $ je Pip, Signale haben rund
# 80 Pips Stop, also etwa 6,9 EUR Risiko. Bei 100 EUR sind das 6,9 %. Unter
# MAX_RISK_PCT 0.08 wuerde _enforce_risk_cap die Layerzahl auf 0 rechnen und
# der Bot gar nicht mehr handeln. Darum 0.10 und dafuer harte Tagesbremse.
#
# Die .env wird zeilenweise bearbeitet: nur die hier genannten Schluessel
# werden ersetzt oder angehaengt, alles andere bleibt unberuehrt. Werte
# werden nie gelesen und nie ausgegeben.
import io, os, re, sys, stat, py_compile

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
    TT = os.getcwd()
ENV = os.path.join(TT, ".env")


def sag(t):
    print("PATCH118 " + str(t))


# =============================================================== 1. Code
src = io.open(BOT, encoding="utf-8").read()
if "NUR_SYMBOLE" in src:
    sag("Symbolschleuse schon vorhanden")
else:
    _kand = [z for z in src.split("\n") if "Doppelposition-Schutz" in z]
    if len(_kand) != 1:
        sag("FEHLER: Ankerzeile Doppelposition-Schutz " + str(len(_kand)) + "x")
        sys.exit(1)
    ANKER = _kand[0] + "\n"
    NEU = ('    # PATCH118: Symbolschleuse. NUR_SYMBOLE=XAUUSD laesst nur Gold\n'
           '    # durch. Mit 100 EUR ist BTC nicht handelbar: 170 Pips Spread\n'
           '    # gegen Signale mit 120 Pips Stop ist ein sicherer Verlust.\n'
           '    _nur = (os.getenv("NUR_SYMBOLE", "") or "").strip()\n'
           '    if _nur:\n'
           '        _erl = [x.strip().upper() for x in\n'
           '                _nur.replace(";", ",").split(",") if x.strip()]\n'
           '        _ssym = str(getattr(sig, "symbol", "") or "").upper()\n'
           '        if not any(x in _ssym for x in _erl):\n'
           '            log.info("SKIP Symbolschleuse: " + str(sig.symbol) +\n'
           '                     " nicht in NUR_SYMBOLE=" + _nur)\n'
           '            return\n'
           '\n')
    if src.count(ANKER) != 1:
        sag("FEHLER: Anker Doppelposition-Schutz nicht eindeutig (" +
            str(src.count(ANKER)) + ")")
        sys.exit(1)
    src = src.replace(ANKER, NEU + ANKER, 1)
    tmp = BOT + ".p118"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        py_compile.compile(tmp, cfile=tmp + "c", doraise=True)
    except Exception as e:
        sag("FEHLER beim Compilieren: " + str(e))
        try:
            os.remove(tmp)
        except Exception:
            pass
        sys.exit(1)
    try:
        os.remove(tmp + "c")
    except Exception:
        pass
    os.replace(tmp, BOT)
    sag("Symbolschleuse eingesetzt")

# ================================================================ 2. .env
SOLL = [
    ("NUR_SYMBOLE", "XAUUSD"),
    ("MAX_LAYERS", "1"),
    ("MAX_POS_PER_SYMBOL", "1"),
    ("MAX_RISK_PCT", "0.10"),
    ("LOSE_STREAK_LIMIT", "2"),
    ("TAGESSTOP_PCT", "0.12"),
    ("WOCHENSTOP_PCT", "0.25"),
    ("EQUITY_GUARD_PCT", "0.70"),
    ("RUNNER_ONLY", "true"),
    ("RUNNER_FREI", "true"),
    ("RUNNER_LEINE_AB_PIPS", "250"),
    ("LLM_AKTIV", "false"),
]

if not os.path.exists(ENV):
    sag("FEHLER: .env nicht gefunden unter " + ENV)
    sys.exit(1)

with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
    alt = f.read()
alt_zeilen = alt.split("\n")


def schluessel(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (schluessel(z) for z in alt_zeilen) if k)
neu_zeilen = list(alt_zeilen)
gesetzt, ergaenzt = [], []
for k, v in SOLL:
    getroffen = False
    for i, z in enumerate(neu_zeilen):
        if schluessel(z) == k:
            if not getroffen:
                neu_zeilen[i] = k + "=" + v
                getroffen = True
            else:
                neu_zeilen[i] = "# PATCH118 doppelt, deaktiviert: " + z
    if getroffen:
        gesetzt.append(k)
    else:
        ergaenzt.append(k)

# Kanal-spezifische Layer-Vorgaben wuerden MAX_LAYERS ueberstimmen
for i, z in enumerate(neu_zeilen):
    k = schluessel(z)
    if k and k.startswith("MAX_LAYERS_"):
        neu_zeilen[i] = k + "=1"
        gesetzt.append(k)
    if k and k.startswith("MAX_RISK_PCT_"):
        neu_zeilen[i] = k + "=0.10"
        gesetzt.append(k)

if ergaenzt:
    if neu_zeilen and neu_zeilen[-1].strip() != "":
        neu_zeilen.append("")
    neu_zeilen.append("# PATCH118 Kleinkonto 100 EUR")
    for k, v in SOLL:
        if k in ergaenzt:
            neu_zeilen.append(k + "=" + v)

neu = "\n".join(neu_zeilen)
if not neu.endswith("\n"):
    neu += "\n"
neu_keys = set(k for k in (schluessel(z) for z in neu.split("\n")) if k)
fehlt = alt_keys - neu_keys
if fehlt:
    sag("FEHLER: Schluessel waeren verloren gegangen (" + str(len(fehlt)) +
        ") - .env unveraendert")
    sys.exit(1)

bak = ENV + ".bak118"
fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
tmpe = ENV + ".p118"
fd = os.open(tmpe, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    _m = stat.S_IMODE(os.stat(ENV).st_mode)
    os.chmod(tmpe, _m)
except Exception:
    pass
os.replace(tmpe, ENV)

sag("env ersetzt: " + " ".join(sorted(set(gesetzt))))
sag("env ergaenzt: " + " ".join(sorted(ergaenzt)) if ergaenzt else "env ergaenzt: keine")
sag("env Zeilen " + str(len(alt_zeilen)) + " -> " + str(len(neu_zeilen)) +
    ", Schluessel " + str(len(alt_keys)) + " -> " + str(len(neu_keys)) +
    ", Sicherung .env.bak118")
sag("fertig: 1 Layer, nur Gold, Tagesstop 12 %, Wochenstop 25 %, "
    "Serienbremse nach 2 Verlusten")
