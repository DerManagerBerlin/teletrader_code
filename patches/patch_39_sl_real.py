#!/usr/bin/env python3
# Patch 39 - idempotent.
#   Das Risiko-Sizing rechnete die SL-Distanz vom Signal-Entry aus, nicht vom
#   Kurs, zu dem wir tatsaechlich einsteigen. Steht der Markt beim Eintreffen
#   des Signals schon gegen uns, ist die echte Distanz groesser und damit das
#   Risiko hoeher als das Budget erlaubt.
#   Beispiel 21.10. 16:10: gerechnet mit SL=8.0 -> 5 Layer = 3,7%, tatsaechlich
#   90 Pips SL = 4,2% vom Konto.
#   Neu: Referenz ist der schlechtere von Signal-Entry und aktuellem Kurs.
#   Abschaltbar mit SL_DIST_VOM_MARKT=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "SL_DIST_VOM_MARKT" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_39")

A_OLD = '''    sl_distance = 0.0
    if sig.entry and sig.sl:
        sl_distance = abs(sig.entry - sig.sl)
'''
A_NEW = '''    sl_distance = 0.0
    if sig.entry and sig.sl:
        sl_distance = abs(sig.entry - sig.sl)
        # Der Stop liegt fest, unser Einstieg nicht. Ist der Markt schon gegen
        # uns gelaufen, wird die echte Distanz groesser - und mit ihr das
        # Risiko. Fuer die Lot- und Layerrechnung deshalb den schlechteren der
        # beiden Bezugspunkte nehmen.
        if os.getenv("SL_DIST_VOM_MARKT", "true").lower() == "true":
            try:
                _tk_r = mt5.symbol_info_tick(sig.symbol)
                if _tk_r:
                    _ref_r = _tk_r.ask if sig.direction == "BUY" else _tk_r.bid
                    _d_markt = abs(_ref_r - sig.sl)
                    if _d_markt > sl_distance:
                        log.info("SL-Distanz vom Markt statt vom Signal: " +
                                 str(round(sl_distance, 2)) + " -> " +
                                 str(round(_d_markt, 2)) + " (Einstieg " +
                                 str(round(_ref_r, 2)) + " statt " +
                                 str(sig.entry) + ")")
                        sl_distance = _d_markt
            except Exception:
                pass
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 39 OK - SL-Distanz aus dem echten Einstiegskurs")
