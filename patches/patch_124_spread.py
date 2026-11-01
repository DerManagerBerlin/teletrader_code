#!/usr/bin/env python3
# patch_124_spread.py
#
# Spread-Schleuse vor dem Einstieg. Zum Wochenstart am Sonntagabend und bei
# News reisst der Spread kurz auf ein Vielfaches auf. Gold liegt normal bei
# 3,2 Pips; zur Eroeffnung sind 30 und mehr ueblich. Ein Einstieg kostet dann
# mehr als der erste Teilgewinn einbringt. MAX_SPREAD_PIPS=0 schaltet aus.
import io, os, re, stat, sys, py_compile

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
BOT = os.path.join(TT, "teletrader_v2.py")
ENV = os.path.join(TT, ".env")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
    ENV = ".env"


def sag(t):
    print("PATCH124 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "MAX_SPREAD_PIPS" in src:
    sag("Spread-Schleuse schon vorhanden")
else:
    ANKER = "    # PATCH118: Symbolschleuse."
    if src.count(ANKER) != 1:
        sag("FEHLER: Anker Symbolschleuse " + str(src.count(ANKER)) + "x")
        sys.exit(1)
    NEU = ('    # PATCH124: Spread-Schleuse. Zum Wochenstart und bei News reisst\n'
           '    # der Spread kurzzeitig auf ein Vielfaches auf.\n'
           '    try:\n'
           '        _msp = float(os.getenv("MAX_SPREAD_PIPS", "0") or 0)\n'
           '    except Exception:\n'
           '        _msp = 0.0\n'
           '    if _msp > 0:\n'
           '        try:\n'
           '            _sti = mt5.symbol_info_tick(sig.symbol)\n'
           '            _ssi = mt5.symbol_info(sig.symbol)\n'
           '            if _sti and _ssi and _ssi.point:\n'
           '                _spip = _ssi.point * 10\n'
           '                _spr = (float(_sti.ask) - float(_sti.bid)) / _spip\n'
           '                if _spr > _msp:\n'
           '                    log.info("SKIP Spread: " + str(sig.symbol) +\n'
           '                             " " + str(round(_spr, 1)) +\n'
           '                             " Pips > " + str(_msp) + " erlaubt")\n'
           '                    return\n'
           '        except Exception as _spe:\n'
           '            log.error("Spread-Schleuse: " + str(_spe))\n'
           '\n')
    src = src.replace(ANKER, NEU + ANKER, 1)
    tmp = BOT + ".p124"
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
    sag("Spread-Schleuse eingesetzt")

# ----------------------------------------------------------------- .env
try:
    with io.open(ENV, encoding="utf-8", errors="surrogateescape") as f:
        alt = f.read()
except Exception as e:
    sag("env nicht lesbar: " + str(e))
    sys.exit(0)
zeilen = alt.split("\n")


def key(z):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", z)
    return m.group(1) if m else None


alt_keys = set(k for k in (key(z) for z in zeilen) if k)
hit = False
for i, z in enumerate(zeilen):
    if key(z) == "MAX_SPREAD_PIPS":
        zeilen[i] = "MAX_SPREAD_PIPS=15"
        hit = True
if not hit:
    if zeilen and zeilen[-1].strip() != "":
        zeilen.append("")
    zeilen.append("MAX_SPREAD_PIPS=15")
neu = "\n".join(zeilen)
if not neu.endswith("\n"):
    neu += "\n"
if alt_keys - set(k for k in (key(z) for z in neu.split("\n")) if k):
    sag("FEHLER: .env waere unvollstaendig geworden - nicht geschrieben")
    sys.exit(0)
fd = os.open(ENV + ".bak124", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(alt)
fd = os.open(ENV + ".p124", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with io.open(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
    f.write(neu)
try:
    os.chmod(ENV + ".p124", stat.S_IMODE(os.stat(ENV).st_mode))
except Exception:
    pass
os.replace(ENV + ".p124", ENV)
sag("fertig: MAX_SPREAD_PIPS=15, Gold liegt normal bei 3,2")
