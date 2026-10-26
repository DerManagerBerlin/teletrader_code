#!/usr/bin/env python3
# Patch 79 - prueft die Neustart-Kette aus Patch 77, ohne auf LIVE zu gehen.
#
#   Geprueft wird genau der Weg, den /live und /algotrading jetzt nehmen:
#     Flagge TERMINAL_RESTART_REQUEST schreiben
#       -> Watcher sieht sie, loescht sie
#       -> algo_set.py setzt [Experts] Enabled=1
#       -> sudo systemctl restart teletrader.service
#       -> Terminal und Bot kommen neu hoch, AutoTrading an
#
#   Es wird kein Konto gewechselt und keine .env angefasst. Der Test
#   laeuft nur, wenn gerade keine Position offen ist; sonst bricht er ab,
#   weil ein Neustart den Trailing-Stop kurz aussetzen laesst.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
REQ = os.path.join(TT, "TERMINAL_RESTART_REQUEST")
WLOG = os.path.join(TT, "algo_set.log")
STAMP = os.path.join(TT, ".letzter_neustart")

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH nstest: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=40):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)

# --- Sicherheitshalt: laeuft gerade eine Position? -----------------------
#     Der Bot schreibt zu jeder offenen Position im Minutentakt Zeilen.
offen = sh("tail -400 '" + os.path.join(TT, 'bot.log') + "' 2>/dev/null | "
           "grep -cE 'Trail-SL|Ruecksetzer #|MFE #'")
try:
    offen_n = int(offen.strip())
except Exception:
    offen_n = -1
letzte = sh("tail -400 '" + os.path.join(TT, 'bot.log') + "' 2>/dev/null | "
            "grep -E 'Trail-SL|Ruecksetzer #|MFE #' | tail -1 | cut -c1-19")
melde("Positionsspuren in den letzten 400 Zeilen: " + str(offen_n) +
      (" zuletzt " + letzte if letzte else ""))

# Nur abbrechen, wenn die letzte Spur sehr frisch ist (unter 5 Minuten).
abbruch = False
if letzte and len(letzte) >= 19:
    try:
        t_let = datetime.strptime(letzte[:19], "%Y-%m-%d %H:%M:%S")
        alter = (datetime.now() - t_let).total_seconds()
        melde("letzte Positionsspur ist " + str(int(alter)) + "s alt")
        if alter < 300:
            abbruch = True
    except Exception as e:
        melde("Zeitvergleich nicht moeglich: " + str(e))

if abbruch:
    melde("ABBRUCH: Position scheint offen, kein Testneustart")
    print("Patch 79 uebersprungen")
    raise SystemExit(0)

# --- Sperre zuruecksetzen, damit der Test nicht an den 120 s haengt ------
try:
    if os.path.exists(STAMP):
        os.remove(STAMP)
except Exception:
    pass

vorher = sh("wc -l < '" + WLOG + "' 2>/dev/null || echo 0").strip()
melde("algo_set.log vorher: " + vorher + " Zeilen")

try:
    with open(REQ, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat() + "\n")
    melde("Flagge geschrieben")
except Exception as e:
    melde("FEHLER: Flagge nicht schreibbar: " + str(e)); raise SystemExit(1)

time.sleep(5)
melde("Flagge nach 5s: " + ("NOCH DA (Watcher reagiert nicht)"
                            if os.path.exists(REQ) else "abgeraeumt"))
melde("Journal: " + sh("journalctl -t algo_enabler -n 3 --no-pager 2>/dev/null "
                       "| tail -3"))
time.sleep(25)
melde("algo_set.log nachher: " +
      sh("tail -3 '" + WLOG + "' 2>/dev/null || echo '(leer)'"))
melde("Dienst: " + sh("systemctl is-active teletrader.service 2>&1 | head -1") +
      " | seit: " + sh("systemctl show -p ActiveEnterTimestamp --value "
                       "teletrader.service 2>/dev/null"))
print("Patch 79 fertig")
