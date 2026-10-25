#!/usr/bin/env python3
# Patch 53 - idempotent.
#
#   "Cut loss here" wird nicht als Schliessbefehl erkannt. Geprueft gegen
#   is_close_signal():
#       "Cut loss here"                                    -> False
#       "Cut loss, sorry, we will re-enter probably ..."    -> False
#       "Close now"                                        -> True
#   CLOSE_WORDS_STRONG enthaelt nur Varianten mit "close"/"exit". GTMO
#   schreibt aber "cut loss", und zwar als seinen Standard, wenn er einen
#   Trade vor dem Stop beendet. Beide Beispiele oben stammen woertlich aus
#   seinem Kanal (25.10. Screenshot und 23.09. aus der Loghistorie).
#   Folge: er steigt aus, wir bleiben drin bis zum SL.
#
#   Neu: die Cut-Varianten kommen in die starke Liste. Geschlossen wird
#   ohnehin nur kanalweise ueber close_positions_by_channel, ein Cut-Befehl
#   aus GTMO kann also keine Positionen des Hauptkanals anfassen.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "PATCH53" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_53")

A_OLD = '''    "close sell", "close buy", "exit now", "exit immediately",
    "get out now", "close everything", "close it",
]
'''
A_NEW = '''    "close sell", "close buy", "exit now", "exit immediately",
    "get out now", "close everything", "close it",
    # PATCH53: GTMO beendet Trades mit "cut loss", nicht mit "close".
    "cut loss", "cut the loss", "cut losses", "cut it here",
    "cut now", "cut here",
]
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 53 OK - 'cut loss' wird als Schliessbefehl erkannt")
