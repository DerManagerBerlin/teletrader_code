#!/usr/bin/env python3
# Patch 111 - zwei Fehler, die heute das BTC-Signal gekostet haben.
#
#   1) Parser: Das Signal lautete "ICH GEHE JETZT BUY". Der Parser sucht
#      das Instrument strikt direkt vor BUY/SELL und las deshalb "jetzt"
#      als Instrument. Diese Strenge hat einen guten Grund, sie verhindert,
#      dass eine Tagesuebersicht ("SELL - TP4 +328 Pips") als Signal
#      gelesen wird. Deshalb wird sie NICHT gelockert.
#      Stattdessen: Wenn das gefundene Wort kein bekanntes Instrument ist,
#      wird der Nachrichtenkopf (erste 140 Zeichen) nach einem bekannten
#      Instrument durchsucht. Nur wenn dort GENAU EINES vorkommt, wird es
#      genommen. Die Richtung kommt weiterhin ausschliesslich aus dem
#      strengen Muster.
#
#   2) BTCUSD.s gibt es beim Broker nicht. Welcher Name stimmt, weiss ich
#      nicht, deshalb listet LIVECHECK ab jetzt alle Symbole auf, die
#      "BTC" enthalten. Danach kann ich den richtigen eintragen.
import os, shutil
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
PUB = os.path.join(HOME, "ttpub")
STATUS = os.path.join(PUB, "status.txt")

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH111 " + t
    print(z)
    try:
        os.makedirs(PUB, exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if "KOPFSUCHE" in src:
    melde("schon gepatcht"); raise SystemExit(0)

getan = []

A1 = ('    if _raw_sym not in _SCALP_SYMS:\n'
      '        return _noise("unbekanntes Instrument \'" + _raw_sym +\n'
      '                      "\' - in _SCALP_SYMS ergaenzen")\n')
N1 = ('    if _raw_sym not in _SCALP_SYMS:\n'
      '        # KOPFSUCHE (Patch 111): Fuellwoerter wie in "ICH GEHE JETZT BUY"\n'
      '        # haben den Parser auf "jetzt" gelenkt. Die Richtung bleibt am\n'
      '        # strengen Muster, nur das Instrument darf aus dem Kopf kommen,\n'
      '        # und nur wenn dort genau eines vorkommt.\n'
      '        _kopf = t[:140].lower()\n'
      '        _treffer = set()\n'
      '        for _k, _v in _SCALP_SYMS.items():\n'
      '            if re.search(r"\\b" + re.escape(_k) + r"\\b", _kopf):\n'
      '                _treffer.add(_v)\n'
      '        if len(_treffer) == 1:\n'
      '            symbol = _treffer.pop()\n'
      '            log.info("Instrument aus dem Kopf gelesen: " + symbol +\n'
      '                     " (direkt vor BUY/SELL stand \'" + str(_raw_sym) + "\')")\n'
      '        else:\n'
      '            return _noise("unbekanntes Instrument \'" + _raw_sym +\n'
      '                          "\', Kopf ergab " + str(len(_treffer)) + " Treffer")\n'
      '    else:\n'
      '        symbol = _SCALP_SYMS[_raw_sym]\n')
if A1 in src:
    src = src.replace(A1, N1, 1); getan.append("Kopfsuche fuer Instrument")
else:
    melde("WARNUNG: Parser-Anker nicht gefunden")

# die alte Zuweisung direkt danach entfaellt, sie steht jetzt in beiden Zweigen
A1b = N1 + '    symbol = _SCALP_SYMS[_raw_sym]\n'
if A1b in src:
    src = src.replace(A1b, N1, 1); getan.append("doppelte Zuweisung entfernt")

A2 = ('                            log.error("LIVECHECK " + str(_sym) +\n'
      '                                      " NICHT VERFUEGBAR - Symbolname pruefen")\n'
      '                            continue\n')
N2 = ('                            log.error("LIVECHECK " + str(_sym) +\n'
      '                                      " NICHT VERFUEGBAR - Symbolname pruefen")\n'
      '                            try:  # Patch 111: passende Namen zeigen\n'
      '                                _basis = str(_sym)[:3].upper()\n'
      '                                _alle = mt5.symbols_get() or []\n'
      '                                _pass = [s.name for s in _alle\n'
      '                                         if _basis in s.name.upper()][:12]\n'
      '                                log.error("LIVECHECK Kandidaten fuer " +\n'
      '                                          _basis + ": " + (", ".join(_pass)\n'
      '                                          or "(keine)"))\n'
      '                            except Exception as _ke:\n'
      '                                log.error("LIVECHECK Kandidatensuche: " + str(_ke))\n'
      '                            continue\n')
if A2 in src:
    src = src.replace(A2, N2, 1); getan.append("BTC-Kandidaten auflisten")
else:
    melde("WARNUNG: LIVECHECK-Anker nicht gefunden")

if not getan:
    melde("nichts geaendert"); raise SystemExit(1)

shutil.copyfile(BOT, BOT + ".bak_111")
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("fertig: " + ", ".join(getan))
except Exception as e:
    shutil.copyfile(BOT + ".bak_111", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)
print("Patch 111 fertig")
