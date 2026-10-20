#!/usr/bin/env python3
# Patch 26 - idempotent (mehrfach ausfuehrbar)
#   A) PARTIAL_AT_TP    - ein Layer nimmt TP1 als Partial mit, Rest laeuft weiter
#   B) LADDER_MAX_STAGE - Leiter nur bis Stufe N, darueber uebernimmt der Trail
#   C) channel_msgs.log - Kanalnachrichten VOLLSTAENDIG mitschreiben
#   D) mfe.csv          - Hoechststand je Position beim Schliessen festhalten
import shutil, py_compile, sys, hashlib

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
shutil.copyfile(F, F + ".bak_26")
done, skip = [], []

# ------------------------------------------------------------ A) Partial TP1
A_OLD = '''    if os.getenv("RUNNER_ONLY", "false").lower() == "true":
        log.info("Layer-Verteilung: " + str(num_layers) +
                 " Layer, alle ohne festes Ziel (RUNNER_ONLY)")
        return {0: num_layers}
'''
A_NEW = '''    if os.getenv("RUNNER_ONLY", "false").lower() == "true":
        # Partial: ein Layer nimmt einen festen TP mit, der Rest laeuft weiter
        # und wird von Leiter + Trailing gefuehrt.
        #   PARTIAL_AT_TP = 1 -> TP1 (Vorgabe) | 2 -> TP2 | -1 -> letzter TP | 0 -> aus
        _ptp = int(os.getenv("PARTIAL_AT_TP", "1"))
        if _ptp != 0 and num_tps > 0 and num_layers >= 2:
            _idx  = (num_tps - 1) if _ptp < 0 else min(_ptp, num_tps) - 1
            _ziel = tps[_idx]
            log.info("Layer-Verteilung: " + str(num_layers) +
                     " Layer = 1 Partial auf TP" + str(_idx + 1) +
                     " (" + str(_ziel) + ") + " + str(num_layers - 1) +
                     " Runner (PARTIAL_AT_TP)")
            return {_ziel: 1, 0: num_layers - 1}
        log.info("Layer-Verteilung: " + str(num_layers) +
                 " Layer, alle ohne festes Ziel (RUNNER_ONLY)")
        return {0: num_layers}
'''
if "PARTIAL_AT_TP" in src:
    skip.append("A Partial")
elif src.count(A_OLD) == 1:
    src = src.replace(A_OLD, A_NEW); done.append("A Partial")
else:
    print("FEHLER Anker A:", src.count(A_OLD)); sys.exit(1)

# -------------------------------------------------------- B) LADDER_MAX_STAGE
B_OLD = '''                    _lstart = max(1, int(os.getenv("LADDER_START_STAGE", "1")))
                    if _reached <= _stage_old or _reached < _lstart:
                        continue
'''
B_NEW = '''                    _lstart = max(1, int(os.getenv("LADDER_START_STAGE", "1")))
                    # LADDER_MAX_STAGE: hoechste Stufe, die die Leiter noch setzt.
                    # 0 = unbegrenzt (alt). 1 = nur BE, danach fuehrt der Trail.
                    # Verhindert, dass der SL auf einem gerade durchlaufenen
                    # TP-Niveau geparkt und vom naechsten Ruecksetzer geholt wird.
                    _lmax = int(os.getenv("LADDER_MAX_STAGE", "0"))
                    if _lmax > 0 and _reached > _lmax:
                        continue
                    if _reached <= _stage_old or _reached < _lstart:
                        continue
'''
if "LADDER_MAX_STAGE" in src:
    skip.append("B Leiter-Deckel")
elif src.count(B_OLD) == 1:
    src = src.replace(B_OLD, B_NEW); done.append("B Leiter-Deckel")
else:
    print("FEHLER Anker B:", src.count(B_OLD)); sys.exit(1)

# -------------------------------------------------------- C) volles Kanal-Log
C_OLD = '''            log.info(f"\U0001f4e8 Neue Nachricht aus {channel_name}: {text[:60]!r}")
'''
C_NEW = '''            log.info(f"\U0001f4e8 Neue Nachricht aus {channel_name}: {text[:60]!r}")
            # Vollstaendiger Text in eigene Datei: das Hauptlog kuerzt auf 60
            # Zeichen, damit gehen die Tages-Summaries des Signalgebers
            # (inkl. "max. +N Pips" je Signal) verloren.
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "channel_msgs.log"), "a",
                          encoding="utf-8") as _cf:
                    _cf.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\\t" +
                              str(channel_name) + "\\t" +
                              str(text).replace("\\n", "\\\\n") + "\\n")
            except Exception:
                pass
'''
if "channel_msgs.log" in src:
    skip.append("C Kanal-Log")
elif src.count(C_OLD) == 1:
    src = src.replace(C_OLD, C_NEW); done.append("C Kanal-Log")
else:
    print("FEHLER Anker C:", src.count(C_OLD)); sys.exit(1)

# --------------------------------------------------------------- D) MFE-Logging
D_OLD = '''                    pos = open_pos.get(tk)
                    if pos is None:
                        _peaks.pop(tk, None)
                        continue
'''
D_NEW = '''                    pos = open_pos.get(tk)
                    if pos is None:
                        # Position zu -> Hoechststand (MFE) einmalig festhalten.
                        _pk = _peaks.pop(tk, None)
                        if _pk is None:
                            _pk = rec.get("peak")
                        if _pk is not None:
                            try:
                                _en = float(rec.get("entry") or 0.0)
                                _ib = bool(rec.get("is_buy"))
                                _mfe = ((float(_pk) - _en) if _ib
                                        else (_en - float(_pk)))
                                _p = os.path.join(os.path.dirname(
                                        os.path.abspath(__file__)), "mfe.csv")
                                _neu = not os.path.exists(_p)
                                with open(_p, "a", encoding="utf-8") as _mf:
                                    if _neu:
                                        _mf.write("zeit;ticket;symbol;richtung;"
                                                  "entry;hoch;mfe_punkte;stufe\\n")
                                    _mf.write(";".join([
                                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        str(tk), str(rec.get("symbol") or ""),
                                        "BUY" if _ib else "SELL",
                                        str(round(_en, 3)),
                                        str(round(float(_pk), 3)),
                                        str(round(_mfe, 3)),
                                        str(int(rec.get("stage") or 0))]) + "\\n")
                                log.info("MFE #" + str(tk) + " " +
                                         str(rec.get("symbol") or "") + ": Hoch +" +
                                         str(round(_mfe, 1)) + " Punkte, Stufe " +
                                         str(int(rec.get("stage") or 0)))
                            except Exception as _me:
                                log.error("MFE-Log #" + str(tk) + ": " + str(_me))
                        try:
                            _d = _load_runners()
                            if str(tk) in _d:
                                _d.pop(str(tk), None)
                                _save_runners(_d)
                        except Exception:
                            pass
                        continue
'''
if "mfe.csv" in src:
    skip.append("D MFE")
elif src.count(D_OLD) == 1:
    src = src.replace(D_OLD, D_NEW); done.append("D MFE")
else:
    print("FEHLER Anker D:", src.count(D_OLD)); sys.exit(1)

open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 26 OK")
print("  neu     :", ", ".join(done) if done else "-")
print("  schon da:", ", ".join(skip) if skip else "-")
