#!/usr/bin/env python3
# Patch 74 - fuehrt eine eigene Kontostandsreihe je Trade.
#
#   Warum nicht ueber MT5: history_deals_total liefert fuer das ganze Jahr
#   0 bei last_error (1,'Success'). Das Terminal hat die Historie dieses
#   Kontos schlicht nie geladen. Daran haenge ich nicht weiter herum.
#
#   Stattdessen schreibt der Bot bei jedem Lot-Sizing, also einmal je
#   Trade, Zeit und Kontostand in ttpub/kontostand.csv. Genau diese Reihe
#   brauche ich fuer das Briefing-Diagramm (Kontostand ueber Tradeanzahl).
#   Angehaengt wird nur, wenn sich der Wert geaendert hat, damit
#   Mehrfachaufrufe beim selben Signal keine Dubletten erzeugen.
#
#   Reines Mitschreiben, kein Eingriff in die Handelslogik. Faellt der
#   Schreibversuch aus, laeuft der Trade trotzdem.
import os, shutil
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH kstand: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

if "KONTOSTANDREIHE" in src:
    melde("schon vorhanden"); raise SystemExit(0)

ANKER = '    log.info("Lot-Sizing: Balance=" + str(round(balance, 0)) + "$" +\n'
if ANKER not in src:
    melde("FEHLER: Anker nicht gefunden"); raise SystemExit(1)

NEU = '''    try:  # KONTOSTANDREIHE - eine Zeile je Trade fuer das Briefing
        _kr = "Z:\\\\home\\\\alexander_lacher\\\\ttpub\\\\kontostand.csv"
        _letzt = None
        if os.path.exists(_kr):
            try:
                with open(_kr, "r", encoding="utf-8") as _fh:
                    _zz = [z for z in _fh.read().splitlines() if z.strip()]
                if len(_zz) > 1:
                    _letzt = _zz[-1].split(";")[1]
            except Exception:
                _letzt = None
        else:
            try:
                with open(_kr, "w", encoding="utf-8") as _fh:
                    _fh.write("zeit;balance;kanal\\n")
            except Exception:
                pass
        _jetzt = str(round(balance, 2))
        if _jetzt != _letzt:
            with open(_kr, "a", encoding="utf-8") as _fh:
                _fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
                          ";" + _jetzt + ";" + str(channel)[:40] + "\\n")
    except Exception:
        pass
'''

shutil.copyfile(BOT, BOT + ".bak_74")
src = src.replace(ANKER, NEU + ANKER, 1)
with open(BOT, "w", encoding="utf-8") as f:
    f.write(src)

# --- Grundstock: die 79 bisher bekannten Werte ---------------------------
#   Bis Trade 74 aus dem Verlauf vom 24.10. rekonstruiert, danach die fuenf
#   Trades vom 26.10. aus bot.log. Ohne genaue Uhrzeit, deshalb als
#   "rekonstruiert" gekennzeichnet. Nur anlegen, nie ueberschreiben.
REIHE = [830, 838, 812, 865, 880, 907, 847, 860, 875, 884, 827, 797, 825,
         841, 878, 903, 847, 861, 937, 909, 884, 857, 839, 839, 859, 885,
         909, 868, 869, 884, 842, 792, 825, 927, 936, 886, 886, 916, 899,
         917, 930, 940, 950, 904, 913, 922, 926, 946, 907, 878, 888, 907,
         924, 936, 944, 909, 931, 939, 950, 953, 956, 920, 920, 925, 929,
         933, 955, 959, 988, 955, 923, 927, 935, 952, 957, 926, 940, 953,
         974]
KR = os.path.join(os.path.expanduser("~"), "ttpub", "kontostand.csv")
try:
    os.makedirs(os.path.dirname(KR), exist_ok=True)
    if os.path.exists(KR) and os.path.getsize(KR) > 20:
        melde("kontostand.csv existiert bereits, kein Grundstock")
    else:
        with open(KR, "w", encoding="utf-8") as f:
            f.write("zeit;balance;kanal\n")
            for i, v in enumerate(REIHE, 1):
                f.write(";" + str(float(v)) + ";rekonstruiert Nr " + str(i) + "\n")
        melde("Grundstock geschrieben: " + str(len(REIHE)) + " Werte")
except Exception as e:
    melde("Grundstock fehlgeschlagen: " + str(e))

import py_compile
try:
    py_compile.compile(BOT, doraise=True)
    melde("Kontostandsreihe eingebaut, Syntax ok")
except Exception as e:
    shutil.copyfile(BOT + ".bak_74", BOT)
    melde("FEHLER, zurueckgerollt: " + str(e)); raise SystemExit(1)

print("Patch 74 fertig")
