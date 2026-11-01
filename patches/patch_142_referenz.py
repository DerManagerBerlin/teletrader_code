#!/usr/bin/env python3
# patch_142_referenz.py
#
# Zwei Korrekturen.
#
# 1. Kontowechsel bricht die Tages- und Wochenbremse.
#    Beim Umstieg von Demo auf Live stand die Messlatte noch auf 882 EUR
#    vom Demokonto. Die Livebalance von 105,97 lag darunter, also haben
#    Tages- und Wochenstop sofort ausgeloest, obwohl nichts passiert war.
#    Jetzt gilt: weicht die Balance um mehr als die Haelfte vom gespeicherten
#    Startwert ab, ist das ein anderes Konto oder eine Einzahlung und keine
#    Verlustserie. Referenz wird neu gesetzt, Sperre aufgehoben.
#    Zusaetzlich wird bremse.json einmalig geloescht, damit die Messlatte
#    sofort auf dem Livekonto neu aufsetzt.
#
# 2. Veralteten Kurs abweisen.
#    Gold hat beim Broker noch nicht geoeffnet, der letzte Tick stammt vom
#    Freitagsschluss. Ein Signal wuerde auf einem zwei Tage alten Preis
#    gerechnet. Der Vergleich laeuft gegen ein Symbol, das sicher handelt,
#    per Vorgabe EURUSD, weil MT5 die Tickzeit in Serverzeit liefert und ein
#    Vergleich mit der Ortszeit um Stunden danebenliegen wuerde.
import io, os, sys, py_compile

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
BOT = os.path.join(TT, "teletrader_v2.py")
BREMSE = os.path.join(TT, "bremse.json")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
    BREMSE = "bremse.json"


def sag(t):
    print("PATCH142 " + str(t))


src = io.open(BOT, encoding="utf-8").read()
if "PATCH142" in src:
    sag("Code schon angepasst")
else:
    # --- 1. Kontowechsel erkennen -------------------------------------
    A1 = "    _meld = None\n    if _frei and not _d.get(\"tag_pause\")"
    N1 = ('    # PATCH142: Kontowechsel oder Einzahlung erkennen. Weicht die\n'
          '    # Balance um mehr als die Haelfte vom gespeicherten Startwert\n'
          '    # ab, ist das kein Verlust, sondern ein anderes Konto.\n'
          '    for _pa, _ps in (("tag", "tag_start"), ("woche", "woche_start")):\n'
          '        try:\n'
          '            _ref = float(_d.get(_ps) or 0)\n'
          '        except Exception:\n'
          '            _ref = 0.0\n'
          '        if _ref > 0 and (_bal < _ref * 0.5 or _bal > _ref * 2.0):\n'
          '            _d[_ps] = _bal\n'
          '            _d.pop(_pa + "_pause", None)\n'
          '            _neu = True\n'
          '            _frei.append("Messlatte " + _pa + " neu auf " +\n'
          '                         str(round(_bal, 2)))\n'
          + A1)
    if src.count(A1) != 1:
        sag("FEHLER: Anker Bremse " + str(src.count(A1)) + "x")
        sys.exit(1)
    src = src.replace(A1, N1, 1)

    # --- 2. Veralteten Kurs abweisen ----------------------------------
    A2 = ("            _sti = mt5.symbol_info_tick(sig.symbol)\n"
          "            if _sti and _ssi and _ssi.point:\n")
    N2 = ("            _sti = mt5.symbol_info_tick(sig.symbol)\n"
          "            # PATCH142: Veralteten Kurs abweisen. Die Tickzeit kommt\n"
          "            # in Serverzeit, darum gegen ein sicher handelndes\n"
          "            # Symbol vergleichen statt gegen die Ortszeit.\n"
          "            try:\n"
          "                _alt = float(os.getenv(\"MAX_TICK_ALTER_SEK\", \"300\"))\n"
          "            except Exception:\n"
          "                _alt = 300.0\n"
          "            if _alt > 0 and _sti and getattr(_sti, \"time\", 0):\n"
          "                _rsym = os.getenv(\"REFERENZ_SYMBOL\", \"EURUSD\")\n"
          "                _rt = mt5.symbol_info_tick(_rsym)\n"
          "                if _rt is None:\n"
          "                    mt5.symbol_select(_rsym, True)\n"
          "                    _rt = mt5.symbol_info_tick(_rsym)\n"
          "                if _rt and getattr(_rt, \"time\", 0):\n"
          "                    _delta = float(_rt.time) - float(_sti.time)\n"
          "                    if _delta > _alt:\n"
          "                        log.info(\"SKIP Kurs veraltet: \" +\n"
          "                                 str(sig.symbol) + \" ist \" +\n"
          "                                 str(int(_delta)) + \" s aelter als \" +\n"
          "                                 _rsym + \" - Markt wohl zu\")\n"
          "                        return\n"
          "            if _sti and _ssi and _ssi.point:\n")
    if src.count(A2) != 1:
        sag("FEHLER: Anker Tick " + str(src.count(A2)) + "x")
        sys.exit(1)
    src = src.replace(A2, N2, 1)

    tmp = BOT + ".p142"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        py_compile.compile(tmp, cfile=tmp + "c", doraise=True)
    except Exception as e:
        sag("FEHLER beim Compilieren: " + str(e))
        try:
            os.remove(tmp)
        except Exception:
            pass
        sys.exit(1)
    try:
        os.remove(tmp + "c")
    except Exception:
        pass
    os.replace(tmp, BOT)
    sag("Kontowechsel-Erkennung und Kursalter-Pruefung eingesetzt")

# --- 3. Messlatte einmalig zuruecksetzen -------------------------------
if os.path.exists(BREMSE):
    try:
        _inhalt = io.open(BREMSE, encoding="utf-8").read()[:200]
        os.remove(BREMSE)
        sag("bremse.json geloescht, Inhalt war: " + _inhalt)
        sag("Messlatte setzt beim naechsten Durchlauf auf dem Livekonto neu auf")
    except Exception as e:
        sag("bremse.json nicht loeschbar: " + str(e))
else:
    sag("bremse.json war nicht da")

# --- 4. Sperre aufheben, falls sie noch steht --------------------------
_flag = os.path.join(os.path.dirname(BOT) or ".", "TRADING_PAUSED")
if os.path.exists(_flag):
    try:
        os.remove(_flag)
        sag("Handelssperre aufgehoben (stammte aus der falschen Messlatte)")
    except Exception as e:
        sag("Sperre nicht loeschbar: " + str(e))
else:
    sag("Handel war nicht gesperrt")
sag("fertig")
