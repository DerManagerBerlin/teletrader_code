#!/usr/bin/env python3
# Patch 30 - idempotent. Trailing Stop folgt dem echten Hochpunkt.
#   Bisher las der Trail nur den Tick im Poll-Moment (alle 30 s). Am 20.10.
#   lief ein BUY auf +134 Pips, der Trail sah zuletzt +100 und liess den SL
#   bei +50 stehen -> Ausstieg 34 Pips unter dem Moeglichen.
#   Neu: Hoechst-/Tiefstkurs seit Eroeffnung aus M1-Bars (wie die SL-Leiter),
#   Abstand davon statt vom Tick. Mindestabstand zum Kurs wird eingehalten.
#   Poll-Intervall 30 s -> TRAILING_POLL_SECONDS (Vorgabe 10).
#   Abschaltbar mit TRAIL_USE_M1_PEAK=false.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "TRAIL_USE_M1_PEAK" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_30")

A_OLD = '''                        trail_dist = _tp_pips * pip
                        min_profit = _mp_pips * pip
'''
A_NEW = '''                        trail_dist = _tp_pips * pip
                        min_profit = _mp_pips * pip
                        # Hoechststand seit Eroeffnung aus M1-Bars. Ohne das
                        # sieht der Trail nur den Tick im Poll-Moment und
                        # verpasst Spitzen, die zwischen zwei Durchlaeufen
                        # liegen.
                        _ext = None
                        if os.getenv("TRAIL_USE_M1_PEAK", "true").lower() == "true":
                            try:
                                _bars = mt5.copy_rates_from_pos(pos.symbol,
                                                                mt5.TIMEFRAME_M1, 0, 240)
                                if _bars is not None and len(_bars):
                                    _t0 = float(pos.time)
                                    _buy = (pos.type == mt5.POSITION_TYPE_BUY)
                                    _w = [float(b["high" if _buy else "low"]) for b in _bars
                                          if float(b["time"]) >= _t0]
                                    if _w:
                                        _ext = max(_w) if _buy else min(_w)
                            except Exception:
                                _ext = None
                        _stops = getattr(sym_info, "trade_stops_level", 0) or 0
                        _mind  = max(_stops * sym_info.point, sym_info.point * 10)
'''
B_OLD = '''                            new_sl = round(current - trail_dist, sym_info.digits)
                            # NIE schlechter als Entry: sonst schreibt der Trail
                            # einen Verlust fest, obwohl die Position im Plus ist.
                            new_sl = max(new_sl, round(pos.price_open, sym_info.digits))
                            if pos.sl and new_sl <= pos.sl:
                                continue
'''
B_NEW = '''                            _ref = max(current, _ext) if _ext else current
                            new_sl = round(_ref - trail_dist, sym_info.digits)
                            # NIE schlechter als Entry: sonst schreibt der Trail
                            # einen Verlust fest, obwohl die Position im Plus ist.
                            new_sl = max(new_sl, round(pos.price_open, sym_info.digits))
                            if new_sl > current - _mind:
                                continue   # zu nah am Kurs, naechster Durchlauf
                            if pos.sl and new_sl <= pos.sl:
                                continue
'''
C_OLD = '''                            new_sl = round(current + trail_dist, sym_info.digits)
                            new_sl = min(new_sl, round(pos.price_open, sym_info.digits))
                            if pos.sl and new_sl >= pos.sl:
                                continue
'''
C_NEW = '''                            _ref = min(current, _ext) if _ext else current
                            new_sl = round(_ref + trail_dist, sym_info.digits)
                            new_sl = min(new_sl, round(pos.price_open, sym_info.digits))
                            if new_sl < current + _mind:
                                continue   # zu nah am Kurs, naechster Durchlauf
                            if pos.sl and new_sl >= pos.sl:
                                continue
'''
D_OLD = '''            except Exception as e:
                log.error("Trailing-Stop Fehler: " + str(e))
            await asyncio.sleep(30)
'''
D_NEW = '''            except Exception as e:
                log.error("Trailing-Stop Fehler: " + str(e))
            await asyncio.sleep(max(3.0, float(os.getenv("TRAILING_POLL_SECONDS", "10"))))
'''
for name, o, n in (("A", A_OLD, A_NEW), ("B", B_OLD, B_NEW),
                   ("C", C_OLD, C_NEW), ("D", D_OLD, D_NEW)):
    if src.count(o) != 1:
        print("FEHLER Anker " + name + ":", src.count(o)); sys.exit(1)
    src = src.replace(o, n)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 30 OK - Trail folgt M1-Hochpunkt, Poll 10s")
