#!/usr/bin/env python3
# Patch 67 - AutoTrading per Mausklick einschalten.
#
#   Befund aus dem Screenshot von Patch 66:
#     - Es steht KEIN Dialogfenster offen. Meine Annahme war falsch.
#     - Das MT5-Fenster ist sauber, Symbolleiste sichtbar, der Knopf
#       "Algo Trading" traegt das rote Quadrat, also AutoTrading aus.
#     - WM-Check: "no such atom on any window" - das openbox aus Patch 63
#       laeuft nicht mehr.
#
#   Ohne Window-Manager bekommt kein Fenster Tastaturfokus. Genau deshalb
#   kommt Ctrl+E nirgends an, egal ueber welchen Weg ich es schicke. Ein
#   Mausklick braucht keinen Fokus: XTEST setzt den Zeiger auf dem Server,
#   und das Fenster unter dem Zeiger bekommt das Ereignis.
#
#   Der Knopf liegt im Screenshot (Wurzelfenster, 1024x768) bei etwa
#   x=322 (Symbol) bis x=400 (Beschriftung), y=62. Geklickt wird die Mitte
#   der Beschriftung, damit ein kleiner Versatz nicht auf den Nachbarknopf
#   faellt.
#
#   Genau EIN Klick, weil der Knopf umschaltet. Vorher wird ein eventuell
#   liegengebliebenes ENABLE_ALGO_REQUEST entfernt, damit der Watcher nicht
#   gleichzeitig eine Taste schickt und gegen den Klick arbeitet.
import os, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
TT = os.path.join(os.path.expanduser("~"), "teletrader")
if not os.path.isdir(TT):
    TT = "."
PUB = os.path.join(os.path.expanduser("~"), "ttpub")
FLAG = os.path.join(TT, "ENABLE_ALGO_REQUEST")
DISP = "DISPLAY=:99"

KLICK_X = 355
KLICK_Y = 62

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH klick: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=30):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "Fehler: " + str(e)

def schuss(ziel):
    """Screenshot nach PUB/<ziel>. scrot ist laut Patch 66 vorhanden."""
    p = os.path.join(PUB, ziel)
    sh("rm -f '" + p + "'")
    sh(DISP + " scrot -o '" + p + "' 2>&1 | head -1", timeout=30)
    if os.path.exists(p) and os.path.getsize(p) > 2000:
        return ziel + " " + str(os.path.getsize(p)) + " Bytes"
    return ziel + " FEHLGESCHLAGEN"

BOTLOG = os.path.join(TT, "bot.log")

def deakt_zaehler():
    n = sh("grep -c 'Algo Trading deaktiviert' '" + BOTLOG + "' 2>/dev/null").strip()
    return int(n) if n.isdigit() else -1

vorher = deakt_zaehler()

# 1. Watcher ruhigstellen: liegengebliebene Anforderung weg
if os.path.exists(FLAG):
    try:
        os.remove(FLAG); melde("altes ENABLE_ALGO_REQUEST entfernt")
    except Exception as e:
        melde("Flag nicht entfernbar: " + str(e))

# 2. Zeigerposition merken, Fenster bestaetigen
melde("Fenster: " + sh(DISP + " xdotool search --name PUPrime 2>/dev/null | head -1"))
melde("Zeiger vorher: " + sh(DISP + " xdotool getmouselocation 2>&1 | head -1"))

# 3. Ein einziger Klick auf den Knopf
melde("klicke auf " + str(KLICK_X) + "," + str(KLICK_Y) + ": " + sh(
    DISP + " xdotool mousemove " + str(KLICK_X) + " " + str(KLICK_Y) +
    " 2>&1; sleep 0.4; " + DISP + " xdotool click --clearmodifiers 1 2>&1; echo ok"))

time.sleep(3)
melde(schuss("mt5_nach_klick.png"))

# 4. Zweiter Blick nach gut einer Minute: bleibt es an?
#    Kurz genug, dass der naechste cron-Lauf (alle 5 Min) nicht ueberholt
#    und den Patch ein zweites Mal startet - das waere ein zweiter Klick.
time.sleep(75)
melde(schuss("mt5_spaeter.png"))
nachher = deakt_zaehler()
melde("Meldung 'Algo Trading deaktiviert' vorher=" + str(vorher) +
      " nachher=" + str(nachher) +
      (" -> KEINE neue Meldung" if nachher == vorher and vorher >= 0
       else " -> weiterhin aus"))

# 5. Zeiger aus dem Weg, damit kein Tooltip den naechsten Screenshot verdeckt
sh(DISP + " xdotool mousemove 700 400 2>&1")
print("Patch 67 fertig")
