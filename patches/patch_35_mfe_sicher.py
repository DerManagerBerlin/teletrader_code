#!/usr/bin/env python3
# Patch 35 - idempotent. Aendert NICHTS am Handeln, nur an der Messung.
#   Problem: prune_runners() loescht Eintraege aus runners.json, sobald die
#   Position zu ist. Laeuft es vor der SL-Leiter, geht der Hoechststand
#   verloren und es entsteht keine mfe.csv-Zeile. Am 20.10. sind so die
#   Messpunkte des 15:17-Signals verschwunden.
#   Loesung: der Hoechststand wird laufend in runners.json mitgeschrieben,
#   und prune_runners schreibt die MFE-Zeile, bevor es den Eintrag entfernt.
import shutil, py_compile, sys

F = "teletrader_v2.py"
src = open(F, encoding="utf-8").read()
if "_schreib_mfe" in src:
    print("schon angewendet"); raise SystemExit(0)
shutil.copyfile(F, F + ".bak_35")

# ---- 1) gemeinsame Schreibfunktion vor prune_runners einsetzen
A_OLD = '''def prune_runners():
    """Entfernt Runner-Eintraege, deren Position nicht mehr offen ist."""
'''
A_NEW = '''def _schreib_mfe(tk, rec):
    """Haengt eine Zeile an mfe.csv. Wird von der SL-Leiter UND von
    prune_runners aufgerufen, je nachdem wer die geschlossene Position
    zuerst bemerkt."""
    try:
        _pk = rec.get("peak")
        if _pk is None:
            return False
        _en = float(rec.get("entry") or 0.0)
        _ib = bool(rec.get("is_buy"))
        _mfe = (float(_pk) - _en) if _ib else (_en - float(_pk))
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mfe.csv")
        _neu = not os.path.exists(_p)
        with open(_p, "a", encoding="utf-8") as _f:
            if _neu:
                _f.write("zeit;ticket;symbol;richtung;entry;hoch;mfe_punkte;stufe\\n")
            _f.write(";".join([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(tk), str(rec.get("symbol") or ""),
                "BUY" if _ib else "SELL",
                str(round(_en, 3)), str(round(float(_pk), 3)),
                str(round(_mfe, 3)), str(int(rec.get("stage") or 0))]) + "\\n")
        log.info("MFE #" + str(tk) + " " + str(rec.get("symbol") or "") +
                 ": Hoch +" + str(round(_mfe, 1)) + " Punkte, Stufe " +
                 str(int(rec.get("stage") or 0)))
        return True
    except Exception as _e:
        log.error("MFE-Schreiben #" + str(tk) + ": " + str(_e))
        return False


def prune_runners():
    """Entfernt Runner-Eintraege, deren Position nicht mehr offen ist."""
'''
# ---- 2) prune_runners schreibt vor dem Loeschen
B_OLD = '''        removed = [t for t in list(d.keys()) if t not in open_tk]
        for t in removed:
            d.pop(t, None)
'''
B_NEW = '''        removed = [t for t in list(d.keys()) if t not in open_tk]
        for t in removed:
            _r = d.get(t)
            if isinstance(_r, dict):
                _schreib_mfe(t, _r)
            d.pop(t, None)
'''
# ---- 3) Leiter schreibt den Hoechststand laufend in runners.json
C_OLD = '''                    _peaks[tk] = _ext
'''
C_NEW = '''                    _peaks[tk] = _ext
                    # Hoechststand mitschreiben, damit er auch dann vorliegt,
                    # wenn prune_runners den Eintrag zuerst einsammelt.
                    try:
                        _alt = rec.get("peak")
                        _pt = (mt5.symbol_info(pos.symbol).point
                               if mt5.symbol_info(pos.symbol) else 0.01) * 10
                        if _alt is None or abs(float(_alt) - _ext) >= _pt:
                            _dd = _load_runners()
                            if str(tk) in _dd and isinstance(_dd[str(tk)], dict):
                                _dd[str(tk)]["peak"] = round(float(_ext), 3)
                                _save_runners(_dd)
                                rec["peak"] = round(float(_ext), 3)
                    except Exception:
                        pass
'''
for n, o, x in (("A", A_OLD, A_NEW), ("B", B_OLD, B_NEW), ("C", C_OLD, C_NEW)):
    if src.count(o) != 1:
        print("FEHLER Anker " + n + ":", src.count(o)); sys.exit(1)
    src = src.replace(o, x)
open(F, "w", encoding="utf-8").write(src)
py_compile.compile(F, doraise=True)
print("Patch 35 OK - MFE geht nicht mehr verloren")
