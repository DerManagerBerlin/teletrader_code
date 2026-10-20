#!/usr/bin/env python3
# Patch 31 - idempotent.
#  A) Layer-Verteilung: je ein Partial auf TP1, TP2, TP3 ... und IMMER ein
#     Runner obendrauf. Reichen die Layer nicht fuer alle TPs, fallen die
#     HINTEREN TPs weg, der Runner bleibt. Schalter PARTIAL_LADDER.
#  B) Layerzahl wird am Risikobudget gedeckelt. Bisher hat die Mindest-Lotgroesse
#     das Zielrisiko still ueberschritten: 3 Layer a 0.01 Lot = 21 EUR bei
#     einem Budget von 18.80. Jetzt wird stattdessen die Layerzahl gesenkt.
#     Schalter LAYERS_FIT_RISK.
# Die SL-Logik bleibt unberuehrt.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "PARTIAL_LADDER" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_31")

A_OLD = '''        _ptp = int(os.getenv("PARTIAL_AT_TP", "1"))
        if _ptp != 0 and num_tps > 0 and num_layers >= 2:
            _idx  = (num_tps - 1) if _ptp < 0 else min(_ptp, num_tps) - 1
            _ziel = tps[_idx]
            log.info("Layer-Verteilung: " + str(num_layers) +
                     " Layer = 1 Partial auf TP" + str(_idx + 1) +
                     " (" + str(_ziel) + ") + " + str(num_layers - 1) +
                     " Runner (PARTIAL_AT_TP)")
            return {_ziel: 1, 0: num_layers - 1}
'''
A_NEW = '''        # TP-Leiter: je ein Layer auf TP1, TP2, TP3 ... plus IMMER ein Runner.
        # Zu wenige Layer -> die hinteren TPs fallen weg, der Runner bleibt.
        if (os.getenv("PARTIAL_LADDER", "true").lower() == "true"
                and num_tps > 0 and num_layers >= 2):
            _n = min(num_tps, num_layers - 1)       # so viele TPs wie moeglich
            _v = {}
            for _i in range(_n):
                _v[tps[_i]] = _v.get(tps[_i], 0) + 1
            _v[0] = num_layers - _n                 # Rest laeuft offen
            log.info("Layer-Verteilung: " + str(num_layers) + " Layer = Partials auf "
                     + ", ".join("TP" + str(_i + 1) + " (" + str(tps[_i]) + ")"
                                 for _i in range(_n))
                     + " + " + str(_v[0]) + " Runner (PARTIAL_LADDER)")
            return _v
        _ptp = int(os.getenv("PARTIAL_AT_TP", "1"))
        if _ptp != 0 and num_tps > 0 and num_layers >= 2:
            _idx  = (num_tps - 1) if _ptp < 0 else min(_ptp, num_tps) - 1
            _ziel = tps[_idx]
            log.info("Layer-Verteilung: " + str(num_layers) +
                     " Layer = 1 Partial auf TP" + str(_idx + 1) +
                     " (" + str(_ziel) + ") + " + str(num_layers - 1) +
                     " Runner (PARTIAL_AT_TP)")
            return {_ziel: 1, 0: num_layers - 1}
'''
B_OLD = '''                _want = balance * _trg / max(1, num_layers) / (sl_distance * _pv)
                _want = _norm_lot(sig.symbol, _want)
'''
B_NEW = '''                _want = balance * _trg / max(1, num_layers) / (sl_distance * _pv)
                _want = _norm_lot(sig.symbol, _want)
                # Die Mindest-Lotgroesse kann das Budget sprengen. Dann nicht
                # still mehr riskieren, sondern weniger Layer eroeffnen.
                if os.getenv("LAYERS_FIT_RISK", "true").lower() == "true":
                    _je_layer = _want * sl_distance * _pv
                    if _je_layer > 0:
                        _passt = int((balance * _trg) // _je_layer)
                        _passt = max(1, min(num_layers, _passt))
                        if _passt != num_layers:
                            log.info("Layerzahl ans Risiko angepasst: " +
                                     str(num_layers) + " -> " + str(_passt) +
                                     " (je Layer " + str(round(_je_layer, 2)) +
                                     ", Budget " + str(round(balance * _trg, 2)) + ")")
                            num_layers = _passt
'''
for n, o, x in (("A", A_OLD, A_NEW), ("B", B_OLD, B_NEW)):
    if src.count(o) != 1:
        print("FEHLER Anker " + n + ":", src.count(o)); sys.exit(1)
    src = src.replace(o, x)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 31 OK - TP-Leiter + Layerzahl am Risikobudget")
