#!/usr/bin/env python3
# Patch 70 - AutoTrading in der MT5-Konfiguration einschalten.
#
#   Befund aus Patch 69:
#       Config/common.ini -> [Experts] Enabled=0
#   Das ist der Schalter selbst, den Ctrl+E nur umlegt. Er steht auf aus,
#   daher retcode 10027 bei jedem Auftrag. Tastatur und Maus waren die
#   falsche Spur.
#
#   Schwierigkeit: MT5 schreibt common.ini im Betrieb und beim Beenden neu.
#   Eine Aenderung am laufenden Terminal kann also wieder ueberschrieben
#   werden. Sauber waere "Dienst stoppen, schreiben, starten" - aber die
#   sudoers-Regel erlaubt nur 'systemctl restart teletrader.service', kein
#   stop. Und selbst Prozesse abzuschiessen kommt nicht in Frage, der
#   Watchdog haengt daran.
#
#   Deshalb: schreiben, neu starten, und waehrend das Terminal unten ist in
#   kurzen Abstaenden nachsehen und bei Bedarf erneut schreiben. Geschrieben
#   wird nur, wenn der Wert nicht schon 1 ist, und immer atomar.
#   Kodierung, Zeilenenden und Rechte bleiben wie vorgefunden, eine
#   Sicherung liegt daneben. Der Inhalt wird nie ausgegeben, die Datei
#   enthaelt Kontodaten.
import os, re, subprocess, time
from datetime import datetime, timezone

LOG = "bot.log"
HOME = os.path.expanduser("~")
INI = os.path.join(HOME, ".wine", "drive_c", "Program Files",
                   "PU Prime MT5 Terminal", "Config", "common.ini")
UNIT = "teletrader.service"

def log(t):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,000") +
                    " [INFO] AUTOPATCH algoan: " + t + "\n")
    except Exception:
        pass

def melde(t):
    print(t); log(t)

def sh(cmd, timeout=90):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip().replace("\n", " | ")[:300]
    except Exception as e:
        return "Fehler: " + str(e)

def mt5_laeuft():
    return bool(sh("pgrep -f '[t]erminal64' | head -1", timeout=15).strip())

def kodierung(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if b[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if b.count(b"\x00") > len(b) // 4:
        return "utf-16-le"
    return "utf-8"

def wert():
    """Aktueller Wert von [Experts] Enabled, oder None."""
    try:
        with open(INI, "rb") as f:
            roh = f.read()
        t = roh.decode(kodierung(roh), errors="replace")
        m = re.search(r"\[Experts\](.*?)(\r?\n\[|\Z)", t, re.S | re.I)
        if not m:
            return None
        e = re.search(r"^\s*Enabled\s*=\s*(\d)", m.group(1), re.M | re.I)
        return e.group(1) if e else None
    except Exception:
        return None

def setze():
    """[Experts] Enabled=1 setzen. Gibt einen kurzen Hinweis zurueck."""
    with open(INI, "rb") as f:
        roh = f.read()
    kod = kodierung(roh)
    text = roh.decode(kod, errors="strict")
    crlf = "\r\n" in text
    zeilen = text.split("\r\n") if crlf else text.split("\n")

    im_abschnitt = False
    gesetzt = False
    vorher = None
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("[") and s.endswith("]"):
            im_abschnitt = (s.lower() == "[experts]")
            continue
        if im_abschnitt and re.match(r"^\s*Enabled\s*=", z, re.I):
            vorher = s.split("=", 1)[1].strip()
            if vorher == "1":
                return "stand bereits auf 1"
            zeilen[i] = "Enabled=1"
            gesetzt = True
            break
    if not gesetzt:
        for i, z in enumerate(zeilen):
            if z.strip().lower() == "[experts]":
                zeilen.insert(i + 1, "Enabled=1")
                gesetzt = True
                vorher = "(Schluessel fehlte)"
                break
    if not gesetzt:
        return "kein Abschnitt [Experts] gefunden"

    neu = ("\r\n" if crlf else "\n").join(zeilen)
    st = os.stat(INI)
    tmp = INI + ".neu"
    with open(tmp, "wb") as f:
        f.write(neu.encode(kod))
        f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, INI)
    return "Enabled " + str(vorher) + " -> 1 (" + kod + \
           (", CRLF)" if crlf else ", LF)")

if not os.path.exists(INI):
    melde("common.ini nicht gefunden: " + INI); raise SystemExit(0)

sh("cp -p '" + INI + "' '" + INI + ".bak_70'")
melde("Sicherung: " + ("ok" if os.path.exists(INI + ".bak_70") else "FEHLT") +
      ", Wert vorher: " + str(wert()))

# 1. Erster Schreibversuch am laufenden Terminal
try:
    melde("Schreibversuch 1: " + setze())
except Exception as e:
    melde("FEHLER: " + str(e)); raise SystemExit(1)

# 2. Neustart ueber systemd. Nur 'restart' ist erlaubt.
melde("Neustart: " + (sh("sudo -n systemctl restart " + UNIT +
                         " 2>&1 && echo OK") or "(keine Ausgabe)"))

# 3. Waehrend das Terminal unten ist: Wert halten. Sobald es wieder oben
#    ist und 10 s stabil 1 zeigt, ist die Sache durch.
nachschreiben = 0
oben_seit = None
t0 = time.time()
while time.time() - t0 < 150:
    laeuft = mt5_laeuft()
    w = wert()
    if w != "1":
        try:
            setze(); nachschreiben += 1
        except Exception:
            pass
        oben_seit = None
    elif laeuft:
        if oben_seit is None:
            oben_seit = time.time()
        elif time.time() - oben_seit > 12:
            break
    else:
        oben_seit = None
    time.sleep(1.5)

melde("Terminal " + ("laeuft" if mt5_laeuft() else "laeuft NICHT") +
      ", Wert jetzt: " + str(wert()) +
      ", Nachschreiben noetig: " + str(nachschreiben) + "x")

# 4. Bild zur Kontrolle: der Knopf muss gruen sein statt rot
PUB = os.path.join(HOME, "ttpub", "mt5_algo.png")
time.sleep(15)
sh("rm -f '" + PUB + "'; DISPLAY=:99 scrot -o '" + PUB + "' 2>&1 | head -1", timeout=40)
melde("Bild: " + (str(os.path.getsize(PUB)) + " Bytes"
                  if os.path.exists(PUB) else "fehlgeschlagen"))
print("Patch 70 fertig")
