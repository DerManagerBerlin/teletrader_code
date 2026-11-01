#!/usr/bin/env python3
# patch_139_sichtbar.py
#
# Dringend. XAUUSD steht auf dem Livekonto nicht in der Marktuebersicht,
# und fuer ein nicht ausgewaehltes Symbol liefert MT5 bid=0 und ask=0.
# Meine eigene Nullkurs-Sperre aus Patch 135 wuerde damit JEDES Signal
# abweisen. Patch 134 hatte das Symbol zwar ausgewaehlt, der Neustart des
# Terminals danach hat die Auswahl aber wieder verloren.
#
# Die Schleuse waehlt das Symbol jetzt selbst aus, bevor sie den Kurs liest,
# und liest danach neu. Erst wenn der Kurs dann immer noch null ist, wird
# abgelehnt.
import io, os, sys, py_compile

BOT = os.path.join(os.path.expanduser("~"), "teletrader", "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"


def sag(t):
    print("PATCH139 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "PATCH139" in src:
    sag("schon vorhanden")
    sys.exit(0)

A = ("            _sti = mt5.symbol_info_tick(sig.symbol)\n"
     "            _ssi = mt5.symbol_info(sig.symbol)\n"
     "            if _sti and _ssi and _ssi.point:\n")
N = ("            _ssi = mt5.symbol_info(sig.symbol)\n"
     "            # PATCH139: Symbol erst in die Marktuebersicht holen. Fuer\n"
     "            # ein nicht ausgewaehltes Symbol liefert MT5 bid=0/ask=0,\n"
     "            # und die Nullkurs-Sperre unten wuerde jedes Signal\n"
     "            # abweisen. Ein Terminal-Neustart verliert die Auswahl.\n"
     "            if _ssi is None or not _ssi.visible:\n"
     "                mt5.symbol_select(sig.symbol, True)\n"
     "                import time as _t139\n"
     "                _t139.sleep(0.5)\n"
     "                _ssi = mt5.symbol_info(sig.symbol)\n"
     "                log.info(\"Symbolauswahl nachgeholt: \" + str(sig.symbol) +\n"
     "                         \" sichtbar=\" + str(getattr(_ssi, 'visible', None)))\n"
     "            _sti = mt5.symbol_info_tick(sig.symbol)\n"
     "            if _sti and _ssi and _ssi.point:\n")
if src.count(A) != 1:
    sag("FEHLER: Anker " + str(src.count(A)) + "x")
    sys.exit(1)
src = src.replace(A, N, 1)

tmp = BOT + ".p139"
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
sag("fertig: Schleuse holt das Symbol vorher in die Marktuebersicht")
