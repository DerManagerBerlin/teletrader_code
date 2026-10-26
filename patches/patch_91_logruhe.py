#!/usr/bin/env python3
# Patch 91 - Telegram-Abfragen aus dem Log nehmen und frisch anfangen.
#
#   Befund: Der Bot schreibt alle sechs Sekunden eine Zeile
#     "HTTP Request: GET .../getUpdates ... 200 OK"
#   Das sind rund 14000 Zeilen am Tag an reinem Rauschen. So ist bot.log
#   auf 292 MB gewachsen und dabei beschaedigt worden. Die letzte Stunde
#   habe ich aus diesem kaputten Log falsche Schluesse gezogen.
#
#   Zwei Eingriffe:
#   1) httpx, httpcore und telegram werden auf WARNING gesetzt. Fehler
#      bleiben sichtbar, der Erfolgsfall verschwindet. Am Verhalten des
#      Bots aendert das nichts, nur an seiner Gespraechigkeit.
#   2) bot.log wird leer neu angelegt. Die geretteten 20000 Zeilen von
#      vorhin enthalten noch Luecken aus der beschaedigten Datei und
#      machen jede Suche darin unzuverlaessig.
import os, shutil, subprocess, time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
TT = os.path.join(HOME, "teletrader")
if not os.path.isdir(TT):
    TT = "."
BOT = os.path.join(TT, "teletrader_v2.py")
if not os.path.exists(BOT):
    BOT = "teletrader_v2.py"
LOG = os.path.join(TT, "bot.log")
STATUS = os.path.join(HOME, "ttpub", "status.txt")
UNIT = "teletrader.service"

def melde(t):
    z = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " PATCH91 " + t
    print(z)
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass

def sh(c, t=90):
    try:
        r = subprocess.run(["bash", "-lc", c], capture_output=True, text=True, timeout=t)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:250]
    except Exception as e:
        return "Fehler: " + str(e)

with open(BOT, "r", encoding="utf-8") as f:
    src = f.read()

MARKE = "LOGRUHE"
ANKER = "logging.getLogger().addFilter(_tok_filter)\n"
if MARKE in src:
    melde("Logruhe schon eingebaut")
elif ANKER not in src:
    melde("FEHLER: Anker nicht gefunden, Code bleibt unveraendert")
else:
    NEU = ANKER + (
        "# LOGRUHE (Patch 91): Die Telegram-Abfrage schrieb alle 6 Sekunden\n"
        "# eine Erfolgszeile. Das hat bot.log auf 292 MB getrieben. Fehler\n"
        "# bleiben sichtbar, nur der Normalfall schweigt jetzt.\n"
        "for _lname in ('httpx', 'httpcore', 'telegram', 'telethon'):\n"
        "    logging.getLogger(_lname).setLevel(logging.WARNING)\n")
    shutil.copyfile(BOT, BOT + ".bak_91")
    src = src.replace(ANKER, NEU, 1)
    with open(BOT, "w", encoding="utf-8") as f:
        f.write(src)
    import py_compile
    try:
        py_compile.compile(BOT, doraise=True)
        melde("Logruhe eingebaut, Syntax ok")
    except Exception as e:
        shutil.copyfile(BOT + ".bak_91", BOT)
        melde("FEHLER, zurueckgerollt: " + str(e))
        print("Patch 91 fertig"); raise SystemExit(1)

# Frisches, leeres Log
melde("altes Log: " + sh("ls -l --time-style=+%H:%M:%S '" + LOG + "' 2>/dev/null"))
melde("leeren: " + sh("mv -f '" + LOG + "' '" + LOG + ".rest' 2>/dev/null; "
                      ": > '" + LOG + "'; chmod 664 '" + LOG + "'; "
                      "rm -f '" + LOG + ".rest'; echo ok"))

melde("Neustart: " + sh("sudo -n systemctl restart " + UNIT + " 2>&1 && echo OK"))

# Jetzt ehrlich pruefen: es muss eine NEUE LIVECHECK-Zeile erscheinen
stand = ""
for _ in range(36):            # bis 180 s
    time.sleep(5)
    stand = sh("grep 'LIVECHECK Modus' '" + LOG + "' 2>/dev/null | tail -1")
    if stand:
        break
melde("LIVECHECK neu: " + (stand[:190] or "(keine in 180 s)"))
melde("POSCHECK: " + sh("grep 'POSCHECK' '" + LOG + "' | tail -2")[:250])
melde("Groesse jetzt: " + sh("ls -l --time-style=+%H:%M:%S '" + LOG + "'"))
melde("getUpdates-Zeilen: " + sh("grep -c getUpdates '" + LOG + "' || echo 0"))
melde("Dienst: " + sh("systemctl is-active " + UNIT + " 2>&1 | head -1"))
print("Patch 91 fertig")
