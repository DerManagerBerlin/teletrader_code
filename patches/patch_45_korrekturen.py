#!/usr/bin/env python3
# Patch 45 - idempotent. Drei Korrekturen an den Patches 41, 43 und 44.
#
# (1) Patch 43 loggte "Leiter laesst ihn laufen" bei JEDEM Durchlauf der
#     Leiter, nicht einmal je Ticket. Ergebnis: 4350 Zeilen in bot.log
#     innerhalb weniger Stunden. Das verkuerzt das nutzbare Logfenster, weil
#     sync.sh die letzten 8000 Zeilen spiegelt.
#     Neu: eine Zeile je Ticket.
#
# (2) Patch 44 merkte denselben Kandidaten immer wieder vor. Der
#     Verpasste-Signale-Scan parst alte Nachrichten alle 10 Minuten neu,
#     jeder Durchlauf lief in den Ablehnungszweig und legte den Kandidaten
#     erneut an. Am 23.10. viermal fuer Entry 4009.02, jedes Mal sofort
#     wieder verworfen, weil TP1 laengst durch war.
#     Neu: ein bereits vorgemerkter oder erledigter Entry wird fuer
#     NACHHOL_SPERRE_MIN (Standard 180) Minuten nicht neu angelegt.
#
# (3) Patch 41 misst den Ruecksetzer unbrauchbar: Median 63 Pips bei einem
#     Hoch von nur 37 Pips. Zwei Fehler steckten drin.
#     a) Die Anfangsphase zaehlte mit, in der die Position noch im Minus
#        stand. Das ist der erste Gegenlauf, kein Ruecksetzer aus dem Gewinn.
#     b) Schwerwiegender: in jedem Bar, der ein neues Extrem setzt, wurde
#        das Hoch desselben Bars gegen das Tief desselben Bars gerechnet.
#        Damit floss die ganze Bar-Spanne als "Ruecksetzer" ein, obwohl aus
#        M1-Bars nicht hervorgeht, ob das Hoch vor oder nach dem Tief lag.
#     Neu: gezaehlt wird erst ab MESSE_AB_PIPS (Standard 20) Gewinn, und es
#     werden ZWEI Werte geloggt, weil M1 die Reihenfolge innerhalb eines
#     Bars nicht hergibt:
#       min = nur gegen das Extrem der VORHERIGEN Bars (Untergrenze)
#       max = inklusive der Spanne des Extrem-Bars (Obergrenze)
#     Der echte Wert liegt dazwischen. Fuer die Trail-Breite ist die
#     Obergrenze die sichere Seite.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "_leiter_gemeldet" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_45")

# ── (1) Leiter-Logzeile nur einmal je Ticket ─────────────────────────────
A_OLD = '''                        if _eig and _reached <= _eig:
                            log.info("SL-Leiter: #" + str(tk) + " hat eigenen TP" +
                                     str(_eig) + " - Leiter laesst ihn laufen")
                            continue
'''
A_NEW = '''                        if _eig and _reached <= _eig:
                            if tk not in _leiter_gemeldet:
                                _leiter_gemeldet.add(tk)
                                if len(_leiter_gemeldet) > 500:
                                    _leiter_gemeldet.clear()
                                log.info("SL-Leiter: #" + str(tk) + " hat eigenen TP" +
                                         str(_eig) + " - Leiter laesst ihn laufen")
                            continue
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# ── Speicher fuer (1) und (2) auf Modulebene ─────────────────────────────
B_OLD = '_NACHHOL_DATEI = "nachholen.json"\n'
B_NEW = '''_NACHHOL_DATEI = "nachholen.json"
_leiter_gemeldet = set()    # PATCH45: Tickets, fuer die die Leiter schon gemeldet hat
_nachhol_erledigt = {}      # PATCH45: Entry-Schluessel -> Zeitstempel der Vormerkung
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

# ── (2) Mehrfachvormerkung desselben Signals verhindern ──────────────────
C_OLD = '''        if not (symbol and direction and entry and sl and tps.get(1)):
            return
        liste = [k for k in _nachhol_lesen()
'''
C_NEW = '''        if not (symbol and direction and entry and sl and tps.get(1)):
            return
        # PATCH45: derselbe Entry wird nicht alle 10 Minuten neu angelegt.
        # Der Verpasste-Signale-Scan parst alte Nachrichten wiederholt und
        # landet jedes Mal hier.
        _schl = str(symbol) + "|" + str(direction) + "|" + str(round(float(entry), 2))
        _jetzt = datetime.now().timestamp()
        _sperre = float(os.getenv("NACHHOL_SPERRE_MIN", "180")) * 60.0
        _vor = _nachhol_erledigt.get(_schl)
        if _vor is not None and (_jetzt - _vor) < _sperre:
            return
        if len(_nachhol_erledigt) > 300:
            for _k in [k for k, v in _nachhol_erledigt.items()
                       if (_jetzt - v) > _sperre]:
                _nachhol_erledigt.pop(_k, None)
        _nachhol_erledigt[_schl] = _jetzt
        liste = [k for k in _nachhol_lesen()
'''
if src.count(C_OLD) != 1:
    print("FEHLER Anker 3:", src.count(C_OLD)); sys.exit(1)
src = src.replace(C_OLD, C_NEW)

# ── (3) Ruecksetzer erst ab echtem Gewinn zaehlen ────────────────────────
D_OLD = '''                                    _rh = None; _rtief = 0.0
                                    for _b in _rb:
                                        if float(_b["time"]) < _rt0:
                                            continue
                                        _hi = float(_b["high"]); _lo = float(_b["low"])
                                        if _rbuy:
                                            _rh = _hi if _rh is None else max(_rh, _hi)
                                            _rtief = max(_rtief, _rh - _lo)
                                        else:
                                            _rh = _lo if _rh is None else min(_rh, _lo)
                                            _rtief = max(_rtief, _hi - _rh)
'''
D_NEW = '''                                    _rh = None; _rtief = 0.0; _rtmin = 0.0
                                    # PATCH45: erst ab echtem Gewinn zaehlen, und
                                    # den Ruecksetzer gegen das Extrem der
                                    # VORHERIGEN Bars rechnen. Sonst geht die
                                    # Spanne des Extrem-Bars als Ruecksetzer
                                    # durch, obwohl M1 die Reihenfolge von Hoch
                                    # und Tief im Bar nicht hergibt.
                                    _ab = float(os.getenv("MESSE_AB_PIPS", "20")) * pip
                                    _scharf = False
                                    for _b in _rb:
                                        if float(_b["time"]) < _rt0:
                                            continue
                                        _hi = float(_b["high"]); _lo = float(_b["low"])
                                        if _scharf and _rh is not None:
                                            # Untergrenze: gegen das bisherige Extrem
                                            if _rbuy:
                                                _rtmin = max(_rtmin, _rh - _lo)
                                            else:
                                                _rtmin = max(_rtmin, _hi - _rh)
                                        if _rbuy:
                                            _rh = _hi if _rh is None else max(_rh, _hi)
                                        else:
                                            _rh = _lo if _rh is None else min(_rh, _lo)
                                        if not _scharf:
                                            _gew = ((_rh - pos.price_open) if _rbuy
                                                    else (pos.price_open - _rh))
                                            if _gew < _ab:
                                                continue
                                            _scharf = True
                                        # Obergrenze: inklusive Spanne dieses Bars
                                        if _rbuy:
                                            _rtief = max(_rtief, _rh - _lo)
                                        else:
                                            _rtief = max(_rtief, _hi - _rh)
'''
if src.count(D_OLD) != 1:
    print("FEHLER Anker 4:", src.count(D_OLD)); sys.exit(1)
src = src.replace(D_OLD, D_NEW)

# ── (3b) beide Grenzen loggen ────────────────────────────────────────────
E_OLD = '''                                            log.info("Ruecksetzer #" + str(pos.ticket) +
                                                     " " + str(_rp) + "p vom Hoch " +
                                                     str(_rhoch) + "p (Trail " +
                                                     str(round(_rbr, 1)) + "p)")
'''
E_NEW = '''                                            log.info("Ruecksetzer #" + str(pos.ticket) +
                                                     " " + str(round(_rtmin / pip, 1)) +
                                                     "-" + str(_rp) + "p vom Hoch " +
                                                     str(_rhoch) + "p (Trail " +
                                                     str(round(_rbr, 1)) + "p)")
'''
if src.count(E_OLD) != 1:
    print("FEHLER Anker 5:", src.count(E_OLD)); sys.exit(1)
src = src.replace(E_OLD, E_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 45 OK - Logspam, Mehrfachvormerkung und Messfenster korrigiert")
