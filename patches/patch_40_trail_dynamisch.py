#!/usr/bin/env python3
# Patch 40 - idempotent.
#   Der Trail gibt immer genau seine eigene Breite zurueck. Mit 30 Pips fest
#   heisst das: egal wie weit der Trade laeuft, 30 Pips gehen am Ende ab.
#   Bei einem Hoch von 50 Pips ist das vertretbar, bei einem Hoch von 460
#   ist es unsinnig - und genau das ist am 22.10. zweimal passiert:
#     02:55 SELL  Kanal meldete bis +460 Pips, unsere Runner raus bei +21
#     09:30 SELL  Kanal meldete bis +260 Pips, unsere Runner raus bei +66
#   Neu: die Trail-Breite waechst mit dem Hoechststand. Unterhalb der
#   Kniehoehe bleibt alles wie bisher, darueber wird ein fester Anteil des
#   Hoechststands zurueckgegeben.
#     TRAIL_GIVEBACK_PCT=0.40  Anteil des Hoechststands als Puffer
#     TRAIL_MAX_PIPS=250       Obergrenze der Breite
#   Mit Basis 30 Pips liegt das Knie bei 75 Pips Hoch:
#     Hoch  50 -> Breite 30 -> Ausstieg  20   (wie bisher)
#     Hoch  80 -> Breite 32 -> Ausstieg  48
#     Hoch 260 -> Breite 104 -> Ausstieg 156
#     Hoch 460 -> Breite 184 -> Ausstieg 276
#   Der SL wandert dabei weiter monoton (0,6 x Hoch ist in Hoch steigend),
#   der bestehende Ratschen-Check bleibt also wirksam.
#   Abschaltbar mit TRAIL_GIVEBACK_PCT=0 - dann exakt das alte Verhalten.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "TRAIL_GIVEBACK_PCT" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_40")

# --- 1. Helfer auf Modulebene -------------------------------------------
A_OLD = 'TRAILING_STOP_MIN_PROFIT = float(os.getenv("TRAILING_STOP_MIN_PROFIT_PIPS", "15"))\n'
A_NEW = '''TRAILING_STOP_MIN_PROFIT = float(os.getenv("TRAILING_STOP_MIN_PROFIT_PIPS", "15"))

def _trail_breite(_basis_pips, _hoch_pips, _pip):
    """Trail-Breite in Kurspunkten, waechst mit dem Hoechststand (PATCH40).
    Ein fester Trail gibt bei jedem Trade gleich viel zurueck, auch wenn der
    Trade dreihundert Pips weit gelaufen ist. Oberhalb der Kniehoehe deshalb
    einen Anteil des Hoechststands als Puffer nehmen statt eine feste Zahl.
    TRAIL_GIVEBACK_PCT=0 schaltet zurueck auf das alte feste Verhalten."""
    try:
        _anteil = float(os.getenv("TRAIL_GIVEBACK_PCT", "0.40"))
        _max    = float(os.getenv("TRAIL_MAX_PIPS", "250"))
    except Exception:
        _anteil, _max = 0.40, 250.0
    if _anteil <= 0:
        return _basis_pips * _pip
    _breite = max(float(_basis_pips), _anteil * max(0.0, float(_hoch_pips)))
    return min(_breite, _max) * _pip
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# --- 2. BUY-Zweig: Breite aus dem Hoch statt fest ------------------------
B_OLD = '''                            _ref = max(current, _ext) if _ext else current
                            new_sl = round(_ref - trail_dist, sym_info.digits)
'''
B_NEW = '''                            _ref = max(current, _ext) if _ext else current
                            trail_dist = _trail_breite(
                                _tp_pips, (_ref - pos.price_open) / pip, pip)
                            new_sl = round(_ref - trail_dist, sym_info.digits)
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

# --- 3. SELL-Zweig ------------------------------------------------------
C_OLD = '''                            _ref = min(current, _ext) if _ext else current
                            new_sl = round(_ref + trail_dist, sym_info.digits)
'''
C_NEW = '''                            _ref = min(current, _ext) if _ext else current
                            trail_dist = _trail_breite(
                                _tp_pips, (pos.price_open - _ref) / pip, pip)
                            new_sl = round(_ref + trail_dist, sym_info.digits)
'''
if src.count(C_OLD) != 1:
    print("FEHLER Anker 3:", src.count(C_OLD)); sys.exit(1)
src = src.replace(C_OLD, C_NEW)

# --- 4. Breite mitloggen, damit die Wirkung nachpruefbar ist -------------
D_OLD = '''                                     " (+" + str(round(profit_pips/pip, 1)) + "p)")
'''
D_NEW = '''                                     " (+" + str(round(profit_pips/pip, 1)) + "p" +
                                     " | Trail " + str(round(trail_dist/pip, 1)) + "p)")
'''
if src.count(D_OLD) != 1:
    print("FEHLER Anker 4:", src.count(D_OLD)); sys.exit(1)
src = src.replace(D_OLD, D_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 40 OK - Trail-Breite waechst mit dem Hoechststand")
