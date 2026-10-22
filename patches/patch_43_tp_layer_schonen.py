#!/usr/bin/env python3
# Patch 43 - idempotent.
#   Die SL-Leiter zieht beim TP1-Signal JEDEN Layer auf Entry/BE, auch den
#   Layer, dessen eigener harter TP genau auf TP1 liegt. Oszilliert der Kurs
#   um TP1, gewinnt der BE-Stop das Rennen gegen den eigenen TP: die
#   gebuchten +50 Pips werden zur Nullrunde.
#
#   Zweimal am 22.10. belegt:
#     15:15 UTC SELL  TP1 4051.00. Leiter setzt 15:32:02 BE, Partial-Layer
#                     fliegt 15:32:25 auf BE raus. Danach faellt der Kurs
#                     auf 4050.40, also 6 Pips UNTER den TP. Beweis: das
#                     mfe-Hoch des Partials steht bei 4050.88, das der
#                     laenger offenen Runner bei 4050.40 - der Kurs war
#                     also erst nach dem BE-Ausstieg dort.
#     20:10 UTC SELL  TP1 4021.38, tiefster Bid 4021.34. Alle vier Layer
#                     um 20:17:44 auf BE statt +50.
#   Der Signalgeber hat in beiden Faellen recht: der Markt war am TP1. Nur
#   unser TP-Layer war da schon von der eigenen Leiter geschlossen.
#
#   Neu: ein Layer mit hartem TP wird von der Leiter nicht angefasst,
#   solange sein eigenes Ziel noch aussteht. Er laeuft in seinen TP oder in
#   seinen SL. Erst fuer Stufen OBERHALB seines eigenen Ziels greift die
#   Leiter wieder. Echte Runner (tp=0) bleiben unberuehrt.
#
#   Preis dafuer: erreicht der Kurs TP1 nicht mehr und dreht, nimmt der
#   TP-Layer den vollen SL statt bei BE auszusteigen. TP1 wird in 78% der
#   Signale erreicht (36 von 46 seit 19.10.), der Erwartungswert bleibt
#   damit klar positiv.
#   Abschaltbar mit LEITER_SCHONT_TP_LAYER=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "LEITER_SCHONT_TP_LAYER" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_43")

A_OLD = '''                    _lmax = int(os.getenv("LADDER_MAX_STAGE", "0"))
                    if _lmax > 0 and _reached > _lmax:
                        continue
'''
A_NEW = '''                    _lmax = int(os.getenv("LADDER_MAX_STAGE", "0"))
                    if _lmax > 0 and _reached > _lmax:
                        continue
                    # PATCH43: Layer mit hartem TP nicht auf BE ziehen, solange
                    # sein eigenes Ziel noch aussteht - sonst schliesst die
                    # Leiter ihn, bevor sein TP fuellen kann.
                    if (os.getenv("LEITER_SCHONT_TP_LAYER", "true").lower() == "true"
                            and pos.tp and float(pos.tp) > 0):
                        _eig = 0
                        _tol = abs(float(pos.tp)) * 2e-6 + 0.005
                        for _i, _tp in enumerate(_tps):
                            if abs(float(_tp) - float(pos.tp)) <= _tol:
                                _eig = _i + 1
                                break
                        if _eig and _reached <= _eig:
                            log.info("SL-Leiter: #" + str(tk) + " hat eigenen TP" +
                                     str(_eig) + " - Leiter laesst ihn laufen")
                            continue
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 43 OK - Leiter schont den Layer mit eigenem TP")
