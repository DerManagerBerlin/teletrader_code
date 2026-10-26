#!/usr/bin/env python3
# Patch 89 - bot.log aufraeumen und damit die Sicht wiederherstellen.
#
#   Befund aus Patch 88:
#     bot.log ist 292 MB gross, und seine letzten Zeilen stammen von 15:19,
#     obwohl der Bot seit 17:10 laeuft. Das ist das typische Bild einer
#     Datei mit Loch: Sie wurde abgeschnitten, waehrend ein Prozess sie
#     noch mit alter Schreibposition offen hielt. Dadurch wirkt das Log,
#     als liefe es rueckwaerts, und ich habe daraus die letzte Stunde
#     falsche Schluesse gezogen.
#
#   Vorgehen: die letzten 20000 Zeilen retten, Rest wegwerfen, Datei
#   ersetzen und den Dienst neu starten, damit keine alten Dateihandles
#   mehr darauf zeigen. Erst nach dem Neustart ist das Log wieder ehrlich.
#
#   Gemeldet wird nach ttpub/status.txt, weil bot.log gerade nichts taugt.
import os, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
LOG = os.path.join(TT, "bot.log")
STATUS = os.path.join(HOME, "ttpub", "status.txt")
UNIT = "teletrader.service"

def melde(t):
    zeile = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH89 " + t
    print(zeile)
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass

def sh(cmd, timeout=180):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)

melde("Platte vorher: " + sh("df -h " + TT + " | tail -1"))
try:
    gr = os.path.getsize(LOG)
except Exception:
    gr = -1
melde("bot.log: " + str(gr) + " Bytes")

if gr < 20_000_000:
    melde("Log ist unauffaellig gross, kein Eingriff noetig")
    print("Patch 89 fertig"); raise SystemExit(0)

NEU = LOG + ".gekuerzt"
melde("rette letzte 20000 Zeilen: " +
      sh("tail -n 20000 '" + LOG + "' > '" + NEU + "' 2>&1 && "
         "wc -l < '" + NEU + "' && echo ok"))

if not (os.path.exists(NEU) and os.path.getsize(NEU) > 0):
    melde("ABBRUCH: Kuerzung fehlgeschlagen, bot.log bleibt unangetastet")
    print("Patch 89 fertig"); raise SystemExit(0)

# Alte Datei beiseite, gekuerzte an ihre Stelle. Die laufenden Prozesse
# schreiben noch in die alte Inode, bis der Neustart sie ersetzt.
melde("ersetzen: " + sh("mv '" + LOG + "' '" + LOG + ".alt' && "
                        "mv '" + NEU + "' '" + LOG + "' && "
                        "chmod 664 '" + LOG + "' && echo ok"))
melde("alte Datei loeschen: " + sh("rm -f '" + LOG + ".alt' && echo ok"))
melde("Platte nachher: " + sh("df -h " + TT + " | tail -1"))

melde("Neustart, damit keine alten Dateihandles bleiben: " +
      sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))

# Jetzt muss das Log wieder ehrlich sein
stand = ""
for _ in range(30):              # bis 150 s
    time.sleep(5)
    stand = sh("grep 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null | tail -1")
    if stand:
        break
melde("LIVECHECK nach Neustart: " + (stand[:180] or "(noch nichts)"))
melde("letzte Zeitmarke: " + sh(
    "grep -oE '^2026-[0-9-]+ [0-9:]+' '" + LOG + "' 2>/dev/null | tail -1"))
melde("neue Groesse: " + sh("ls -l --time-style=+%H:%M:%S '" + LOG + "'"))
melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1"))
print("Patch 89 fertig")
