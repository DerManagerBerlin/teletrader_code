#!/usr/bin/env python3
# patch_135_nulltick.py
#
# Die Spread-Schleuse aus Patch 124 laesst einen Kurs von 0,0 durch: die
# Spanne ist dann rechnerisch null und damit kleiner als jede Grenze. Genau
# das steht aber beim Wochenstart in den ersten Sekunden im Terminal, bevor
# der Kursstrom wach ist. Ein Einstieg auf 0,0 wuerde vom Broker abgelehnt
# oder, schlimmer, zu einem unsinnigen Preis gefuellt. Also mit abfangen.
import io, os, sys, py_compile

BOT = os.path.join(os.path.expanduser("~"), "teletrader", "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"


def sag(t):
    print("PATCH135 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "Nullkurs" in src:
    sag("schon vorhanden")
    sys.exit(0)

A = ("            if _sti and _ssi and _ssi.point:\n"
     "                _spip = _ssi.point * 10\n")
N = ("            if _sti and _ssi and _ssi.point:\n"
     "                # PATCH135: Nullkurs abfangen. Beim Wochenstart steht\n"
     "                # der Kurs kurz auf 0,0 und die Spanne waere dann\n"
     "                # rechnerisch null, also kleiner als jede Grenze.\n"
     "                if not float(_sti.bid) or not float(_sti.ask):\n"
     "                    log.info(\"SKIP Nullkurs: \" + str(sig.symbol) +\n"
     "                             \" bid=\" + str(_sti.bid) +\n"
     "                             \" ask=\" + str(_sti.ask))\n"
     "                    return\n"
     "                _spip = _ssi.point * 10\n")
if src.count(A) != 1:
    sag("FEHLER: Anker " + str(src.count(A)) + "x")
    sys.exit(1)
src = src.replace(A, N, 1)

tmp = BOT + ".p135"
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
sag("fertig: Einstieg bei Kurs 0,0 wird abgelehnt")
