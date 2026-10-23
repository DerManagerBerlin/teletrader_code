#!/usr/bin/env python3
# Patch 48 - idempotent. Fehler aus Patch 46.
#
#   Patch 46 haengt die Erkennung der TP-Meldung in parse_scalp_signal.
#   Dieser Parser laeuft aber nicht nur fuer eingehende Nachrichten: der
#   Verpasste-Signale-Scan jagt alle 5 bis 10 Minuten ALTE Nachrichten
#   erneut hindurch. Jede dieser Wiederholungen hat die TP-Stufe erneut
#   gesetzt, auch wenn die Meldung zu einem laengst beendeten Trade gehoerte.
#
#   Gesehen am 23.10., Signal 13:37 UTC:
#     13:37:23  Signal, 4 Layer   -> gleichzeitig "Kanal meldet TP1"
#     13:42:25  erneut "Kanal meldet TP1" (Wiederholung der alten Meldung)
#     13:42:26  Leiter zieht TP2-Layer und Runner auf Entry/BE
#     13:43:45  beide bei BE raus
#     13:45:27  erst JETZT meldet der Kanal TP1 fuer dieses Signal
#   Die Leiter hat also drei Minuten zu frueh abgesichert, auf Basis einer
#   Meldung des vorigen Trades.
#
#   Neu: die Erkennung haengt nicht mehr im Parser, sondern ausschliesslich
#   am Live-Eingang eingehender Kanalnachrichten. Wiederholungen aus dem
#   Verpasste-Signale-Scan und aus den Simulationsbefehlen loesen nichts
#   mehr aus.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "PATCH48" in src:
    print("schon angewendet"); raise SystemExit(0)
if "_tp_meldung_pruefen" not in src:
    print("FEHLER: Patch 46 fehlt"); sys.exit(1)
shutil.copyfile(F, F + ".bak_48")

# ── 1. Aufruf aus dem Parser entfernen ───────────────────────────────────
A_OLD = '''    _tp_meldung_pruefen(text)          # PATCH46

    def _f(s):
'''
A_NEW = '''    # PATCH48: Erkennung hier entfernt - der Parser laeuft auch fuer
    # wiederholte alte Nachrichten aus dem Verpasste-Signale-Scan.
    def _f(s):
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── 2. Nur am Live-Eingang aufrufen ──────────────────────────────────────
B_OLD = '''            if _regex_only_channel(channel_name):
                # Starres Kanal-Template: deterministischer Parser, KEIN Claude-API-Call
                result = parse_scalp_signal(text)
'''
B_NEW = '''            if _regex_only_channel(channel_name):
                # Starres Kanal-Template: deterministischer Parser, KEIN Claude-API-Call
                _tp_meldung_pruefen(text)      # PATCH48: nur hier, live
                result = parse_scalp_signal(text)
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 48 OK - TP-Meldung zaehlt nur noch am Live-Eingang")
