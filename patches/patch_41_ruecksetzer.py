#!/usr/bin/env python3
# Patch 41 - idempotent. Reine Messung, greift NICHT in den Handel ein.
#   Offene Frage: wie breit muss der Trail sein? Dafuer fehlt genau eine
#   Zahl - wie tief die Ruecksetzer sind, die wir unterwegs aushalten
#   muessen. Der Kanal meldet nur erreichte Stufen, nie die Rueckgaenge
#   dazwischen, und unsere mfe.csv endet am Ausstieg. Beides kann die
#   Frage deshalb nicht beantworten.
#   Neu: der Trailing-Loop rechnet aus den M1-Bars seit Eroeffnung den
#   tiefsten Ruecksetzer vom laufenden Hoch und loggt ihn, sobald er einen
#   neuen Hoechstwert erreicht. Eine Zeile pro neuem Maximum, also wenige
#   pro Position.
#     Ruecksetzer #418756378 42.3p vom Hoch 180.0p (Trail 72.0p)
#   Daraus laesst sich die Breite in ein paar Tagen aus Messwerten setzen
#   statt sie zu schaetzen.
#   Abschaltbar mit MESSE_RUECKSETZER=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "MESSE_RUECKSETZER" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_41")

# --- 1. Speicher fuer das bisherige Maximum je Ticket -------------------
A_OLD = 'def _trail_breite(_basis_pips, _hoch_pips, _pip):\n'
A_NEW = '''_rs_max = {}   # PATCH41: Ticket -> bisher tiefster Ruecksetzer in Pips

def _trail_breite(_basis_pips, _hoch_pips, _pip):
'''
if src.count(A_OLD) != 1:
    print("FEHLER Anker 1:", src.count(A_OLD)); sys.exit(1)
src = src.replace(A_OLD, A_NEW)

# --- 2. Messung im Trailing-Loop, vor der Min-Profit-Schwelle ----------
# Anker ist die Stops-Level-Zeile direkt nach der _ext-Berechnung.
B_OLD = '''                        _stops = getattr(sym_info, "trade_stops_level", 0) or 0
                        _mind  = max(_stops * sym_info.point, sym_info.point * 10)
'''
B_NEW = '''                        # PATCH41: tiefster Ruecksetzer vom laufenden Hoch.
                        # Nur Messung, kein Einfluss auf den Stop.
                        if os.getenv("MESSE_RUECKSETZER", "true").lower() == "true":
                            try:
                                _rb = mt5.copy_rates_from_pos(pos.symbol,
                                                              mt5.TIMEFRAME_M1, 0, 240)
                                if _rb is not None and len(_rb):
                                    _rt0 = float(pos.time)
                                    _rbuy = (pos.type == mt5.POSITION_TYPE_BUY)
                                    _rh = None; _rtief = 0.0
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
                                    if _rh is not None and _rtief > 0:
                                        _rp = round(_rtief / pip, 1)
                                        _rhoch = round(abs(_rh - pos.price_open) / pip, 1)
                                        if _rp > _rs_max.get(pos.ticket, 0.0) + 0.9:
                                            _rs_max[pos.ticket] = _rp
                                            _rbr = _trail_breite(_tp_pips, _rhoch, pip) / pip
                                            log.info("Ruecksetzer #" + str(pos.ticket) +
                                                     " " + str(_rp) + "p vom Hoch " +
                                                     str(_rhoch) + "p (Trail " +
                                                     str(round(_rbr, 1)) + "p)")
                                if len(_rs_max) > 400:
                                    _offen = set(x.ticket for x in (positions or []))
                                    for _k in [k for k in _rs_max if k not in _offen]:
                                        _rs_max.pop(_k, None)
                            except Exception:
                                pass
                        _stops = getattr(sym_info, "trade_stops_level", 0) or 0
                        _mind  = max(_stops * sym_info.point, sym_info.point * 10)
'''
if src.count(B_OLD) != 1:
    print("FEHLER Anker 2:", src.count(B_OLD)); sys.exit(1)
src = src.replace(B_OLD, B_NEW)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 41 OK - Ruecksetzertiefe wird gemessen und geloggt")
